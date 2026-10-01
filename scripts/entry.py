"""締切が近いレースの展示情報を1レース1回だけ見に行き、進入を反映した確定版を作る

・締切の30分前〜2分前のレースが対象(10分おきに実行する想定)
・展示の進入が取れたらそのレースは「確認済み」にして、二度と見に行かない
・展示がまだ出ていなければ、次の実行で取り直す
・進入に加えて、展示タイム・水面気象(風向・風速・波高・天候)も同じページから拾う
"""
import datetime as dt
import json
import re
import time
import urllib.request

import pandas as pd

import predict
from common import DATA, JST, UA, download, now_jst
from store import upsert

URL = "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno={race}&jcd={jcd}&hd={date}"
TENJI_RE = re.compile(r'toban=(\d+)">.*?<td rowspan="2">[\d.]+kg</td>\s*<td rowspan="4">([\d.]+)</td>', re.S)
WIND_SPEED_RE = re.compile(r"風速</span>\s*<span[^>]*>(\d+)m</span>")
WAVE_RE = re.compile(r"波高</span>\s*<span[^>]*>(\d+)cm</span>")
WEATHER_RE = re.compile(r'is-weather">\s*<p[^>]*></p>\s*<div[^>]*>\s*<span[^>]*>([^<]+)</span>')
WIND_DIR_RE = re.compile(r'is-windDirection">\s*<p class="weather1_bodyUnitImage is-wind(\d+)"')
# icon_wind1_1〜16は北から時計回り22.5度刻み(1=北を画像で確認済み)。17=無風(矢印なしを確認済み)。
# 「向き」自体は推定含みだが、風速・波高・天候(雨雪判定)は文字から直接取れるので確度が高い。
WIND_DIR_MAP = {i: d for i, d in enumerate(
    ["北", "北", "北東", "北東", "東", "東", "南東", "南東",
     "南", "南", "南西", "南西", "西", "西", "北西", "北西"], start=1)}


def fetch_order(date, jcd, race):
    """展示の進入(枠番をコース順に)を返す。取れなければNone"""
    h = _fetch(date, jcd, race)
    if h is None:
        return None, None
    i = h.find("スタート展示")
    if i < 0:
        return None, None
    nums = re.findall(r'boatImage1Number is-type\d">(\d)</span>', h[i:i + 6000])
    order = [int(x) for x in nums]
    return (order if sorted(order) == [1, 2, 3, 4, 5, 6] else None), h


def fetch_tenji(h):
    """waku順(1〜6)の展示タイムを返す。取れなければNone"""
    m = TENJI_RE.findall(h)
    if len(m) != 6:
        return None
    return [float(t) for _, t in m]


def fetch_weather(h):
    """水面気象(風向・風速・波高・雨雪)を返す。取れなければNone"""
    ws, wv = WIND_SPEED_RE.search(h), WAVE_RE.search(h)
    wt = WEATHER_RE.search(h)
    if not (ws and wv and wt):
        return None
    wd_m = WIND_DIR_RE.search(h)
    wind_dir = "無風" if (wd_m and int(wd_m.group(1)) == 17) else WIND_DIR_MAP.get(int(wd_m.group(1))) if wd_m else None
    return dict(wind_dir=wind_dir, wind=float(ws.group(1)), wave=float(wv.group(1)),
                rain=wt.group(1) in ("雨", "雪"))


def _fetch(date, jcd, race):
    try:
        req = urllib.request.Request(URL.format(race=race, jcd=jcd, date=date), headers=UA)
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return None


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
            order, h = fetch_order(date, r.jcd, r.race)
            time.sleep(1.0)
            if order:
                rec = dict(order=order)
                tenji = fetch_tenji(h)
                if tenji:
                    rec["tenji"] = tenji
                weather = fetch_weather(h)
                if weather:
                    rec.update(weather)
                entries[key] = rec
                todo.append(key)
    if todo:
        ep.write_text(json.dumps(entries))
        predict.run(date, only=set(todo))
    print(f"展示反映: {len(todo)}レース {todo}")

    # 締切を過ぎたばかり(2〜20分以内)のレースがあれば、結果をレース単位の
    # 待ち時間で取り直す(以前は1日3回のupdate.yml頼みで、最後にまとめて
    # しか結果が反映されなかった)
    just_closed = any(
        r.deadline and dt.timedelta(minutes=0) <= now - dt.datetime.strptime(
            date + r.deadline, "%Y%m%d%H:%M").replace(tzinfo=JST) <= dt.timedelta(minutes=20)
        for r in prog.itertuples()
    )
    if just_closed:
        today = now.date()
        if download("K", today, force=True):
            upsert("K", [today])
        print("結果を更新しました")


if __name__ == "__main__":
    main()
