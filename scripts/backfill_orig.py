"""オリ展(一周・まわり足・直線)の過去分を、各場の公式サイトの直前情報から取り込む(1場ずつ)
例: python scripts/backfill_orig.py --jcd 13 --start 20240101
・その場の開催日を新しい日から順にさかのぼる。1Rが空の日が8日続いたら、そこより古い分はもう残っていないとみて止める
・保存先: data/orig_race/<場>/<日付>.json  {"レース番号": {"枠": {"一周": 秒, "まわり足": 秒, "直線": 秒}}}
  空だった日は {} で残して、次から取りに行かない
・1回の取り込みごとに1.2秒あける
"""
import argparse
import datetime as dt
import json
import time

import pandas as pd

import fetch_orig
from common import DATA, now_jst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jcd", required=True)
    ap.add_argument("--start", default="20240101")
    ap.add_argument("--end", default=None)
    ap.add_argument("--max-minutes", type=float, default=330)
    a = ap.parse_args()
    end = a.end or f"{now_jst() - dt.timedelta(days=1):%Y%m%d}"
    progs = []
    for y in range(int(a.start[:4]), int(end[:4]) + 1):
        p = DATA / "programs" / f"{y}.parquet"
        if p.exists():
            progs.append(pd.read_parquet(p, columns=["date", "jcd", "race"]))
    prog = pd.concat(progs)
    prog = prog[(prog.jcd == a.jcd) & (prog.date >= a.start) & (prog.date <= end)]
    days = sorted(prog.date.unique(), reverse=True)
    out_dir = DATA / "orig_race" / a.jcd
    out_dir.mkdir(parents=True, exist_ok=True)
    t0, miss, n_ok = time.time(), 0, 0
    for date in days:
        if time.time() - t0 > a.max_minutes * 60:
            print("時間切れ")
            break
        fp = out_dir / f"{date}.json"
        if fp.exists():
            miss = 0 if json.loads(fp.read_text()) else miss + 1
            continue
        races = sorted(int(r) for r in prog[prog.date == date].race.unique())
        got = {}
        for i, race in enumerate(races):
            o = fetch_orig.fetch_race(a.jcd, date, race)
            time.sleep(1.2)
            if o:
                got[str(race)] = o
            elif i == 0:
                break   # 1Rが空ならその日は残っていない
        fp.write_text(json.dumps(got, ensure_ascii=False))
        if got:
            miss, n_ok = 0, n_ok + 1
        else:
            miss += 1
            if miss >= 8:
                print(f"{date}より古い分は残っていないとみて止める")
                break
    print(f"{a.jcd}: {n_ok}日分を取得")


if __name__ == "__main__":
    main()
