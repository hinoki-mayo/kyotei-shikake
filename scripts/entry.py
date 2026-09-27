"""締切が近いレースの展示情報を1レース1回だけ見に行き、進入を反映した確定版を作る

・締切の30分前〜2分前のレースが対象(10分おきに実行する想定)
・展示の進入が取れたらそのレースは「確認済み」にして、二度と見に行かない
・展示がまだ出ていなければ、次の実行で取り直す
"""
import datetime as dt
import json
import re
import time
import urllib.request

import pandas as pd

import predict
from common import DATA, JST, UA, now_jst

URL = "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno={race}&jcd={jcd}&hd={date}"


def fetch_order(date, jcd, race):
    """展示の進入(枠番をコース順に)を返す。取れなければNone"""
    try:
        req = urllib.request.Request(URL.format(race=race, jcd=jcd, date=date), headers=UA)
        with urllib.request.urlopen(req, timeout=40) as r:
            h = r.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    i = h.find("スタート展示")
    if i < 0:
        return None
    nums = re.findall(r'boatImage1Number is-type\d">(\d)</span>', h[i:i + 6000])
    order = [int(x) for x in nums]
    return order if sorted(order) == [1, 2, 3, 4, 5, 6] else None


def main():
    now = now_jst()
    date = f"{now:%Y%m%d}"
    pp = DATA / "programs" / f"{date[:4]}.parquet"
    if not pp.exists():
        return
    prog = pd.read_parquet(pp, columns=["date", "jcd", "race", "deadline"])
    prog = prog[prog.date == date].drop_duplicates(["jcd", "race"])
    ep = DATA / "entries" / f"{date}.json"
    ep.parent.mkdir(parents=True, exist_ok=True)
    entries = json.loads(ep.read_text()) if ep.exists() else {}
    todo = []
    for r in prog.itertuples():
        key = f"{r.jcd}-{r.race:02d}"
        if key in entries or not r.deadline:
            continue
        t = dt.datetime.strptime(date + r.deadline, "%Y%m%d%H:%M").replace(tzinfo=JST)
        if now + dt.timedelta(minutes=2) < t <= now + dt.timedelta(minutes=30):
            order = fetch_order(date, r.jcd, r.race)
            time.sleep(1.0)
            if order:
                entries[key] = order
                todo.append(key)
    if todo:
        ep.write_text(json.dumps(entries))
        predict.run(date, only=set(todo))
    print(f"展示反映: {len(todo)}レース {todo}")


if __name__ == "__main__":
    main()
