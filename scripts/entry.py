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

import bet
import live_result
import predict
from common import DATA, JST, UA, apply_deadlines, now_jst

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


DL_ROW = re.compile(r"締切予定時刻</td>(.*?)</tr>", re.S)


def parse_deadlines(h):
    """公式のレースページ上の「締切予定時刻」の一覧(1R〜12R)。読めなければNone"""
    m = DL_ROW.search(h or "")
    if not m:
        return None
    ts = re.findall(r"<td[^>]*>\s*(\d{1,2}:\d{2})\s*</td>", m.group(1))
    return [t.zfill(5) for t in ts] if ts else None


def fix_deadlines(date, prog0, found):
    """found: {場: [時刻]}。朝の番組表(prog0)と違う場を data/deadlines に残し、予想ファイルの締切もそろえる。直したらTrue"""
    cur = {(r.jcd, int(r.race)): r.deadline for r in prog0.itertuples()}
    fp = DATA / "deadlines" / f"{date}.json"
    saved = json.loads(fp.read_text()) if fp.exists() else {}
    new = {}
    for jcd, ds in found.items():
        if saved.get(jcd) != ds and (jcd in saved or any(cur.get((jcd, i + 1)) not in (None, t) for i, t in enumerate(ds))):
            new[jcd] = ds
    if new:
        saved.update(new)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(json.dumps(saved))
        print(f"締切の変更を反映: {new}")
    pp = DATA / "predictions" / f"{date}.json"
    if saved and pp.exists():
        st = json.loads(pp.read_text())
        n = 0
        for key, x in st.get("races", {}).items():
            j, r = key.split("-")
            if j in saved and int(r) <= len(saved[j]) and x.get("deadline") != saved[j][int(r) - 1]:
                x["deadline"] = saved[j][int(r) - 1]
                n += 1
        if n:
            pp.write_text(json.dumps(st, ensure_ascii=False, indent=0))
    return bool(new)


def main():
    now = now_jst()
    date = f"{now:%Y%m%d}"
    pp = DATA / "programs" / f"{date[:4]}.parquet"
    if not pp.exists():
        return
    prog = pd.read_parquet(pp, columns=["date", "jcd", "race", "deadline"])
    prog0 = prog[prog.date == date].drop_duplicates(["jcd", "race"])
    prog = apply_deadlines(prog0, date)
    found = {}
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
            ds = parse_deadlines(h)
            if ds:
                found[r.jcd] = ds
            if order:
                rec = dict(order=order)
                tenji = fetch_tenji(h)
                if tenji:
                    rec["tenji"] = tenji
                try:   # 展示のスタート(ST)。枠番順、フライングはマイナス、取れなければNone
                    import math
                    import fetch_before_hist
                    est = fetch_before_hist.parse_est(h)
                    if est:
                        rec["est"] = [None if (est.get(w) is None or math.isnan(est.get(w))) else round(float(est[w]), 2)
                                      for w in range(1, 7)]
                except Exception as e:
                    print(f"展示STを読めませんでした({key}): {e!r}")
                weather = fetch_weather(h)
                if weather:
                    rec.update(weather)
                try:   # 選手ごとの直前情報(体重・調整重量・チルト・プロペラ・部品交換・前走)。10/26から保存
                    import fetch_before_hist
                    ex = fetch_before_hist.parse_extra(h)
                    if ex:
                        rec["extra"] = ex
                except Exception as e:
                    print(f"直前情報の選手欄を読めませんでした({key}): {e!r}")
                entries[key] = rec
                todo.append(key)
    if fix_deadlines(date, prog0, found):
        prog = apply_deadlines(prog, date)
    if todo:
        ep.write_text(json.dumps(entries))
        predict.run(date, only=set(todo))
    print(f"展示反映: {len(todo)}レース {todo}")
    # 買い目は購入係(buyer.py・常駐)が締切5分前に候補、2分前に確定で決める。ここでは決めない

    # 締切後のレースは、公式サイトのレース結果ページから結果を取り込む。
    # (以前は当日の成績ファイルを取り直していたが、成績ファイルは全レース終了後に
    #  まとめて公開されるので日中は毎回空振りしていた)
    live_result.run(prog, now)


if __name__ == "__main__":
    main()
