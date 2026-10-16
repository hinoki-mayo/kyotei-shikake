"""過去レースの直前情報(展示の進入・展示ST・展示タイム・水面)を集める。決まり手の予想に使う
例: python scripts/fetch_before_hist.py --start 2026-08-10 --end 2026-10-13 [--shard 0 --shards 4]

・レース一覧は data/results/<年>.parquet から(実際に走ったレースだけ)。公式の直前情報ページを1レース1回見る
・保存先: data/before_hist/YYYYMMDD.parquet(1日1ファイル、1レース1行)
    date, jcd(int), race(int)
    order : 展示の進入(コース順に枠番を並べたもの、長さ6)。取れなければ空
    est   : 枠番順(1〜6)の展示ST(秒)。フライングはマイナス(F.03 → -0.03)、出遅れ・不明はNaN
    tenji : 枠番順の展示タイム
    wind, wave(m, cm), wind_dir
・応答が遅い(1ページ約9秒)ので2レースずつ同時に取る。保存済みのレースは飛ばす。20レース続けて取れなければ止める
"""
import argparse
import datetime as dt
import re
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

import entry
from common import DATA, daterange
from fetch_odds_hist import races_of

OUT = DATA / "before_hist"
STOP_EMPTY = 20
NUM_RE = re.compile(r'boatImage1Number is-type\d">(\d)</span>')
TIME_RE = re.compile(r'boatImage1Time[^"]*">\s*([^<\s]*)\s*<')
ANY_ST_RE = re.compile(r'>\s*(F\.\d\d|L\.\d\d|\.\d\d|F|L)\s*<')
shown = [False]


def st_value(s):
    """".08"→0.08、"F.03"→-0.03、"L"や読めない時はNaN"""
    m = re.fullmatch(r"(F|L)?0?\.(\d\d)", (s or "").strip())
    if not m or m.group(1) == "L":
        return np.nan
    v = int(m.group(2)) / 100
    return -v if m.group(1) == "F" else v


def parse_est(h):
    """スタート展示の表から {枠番: 展示ST} を返す"""
    i = h.find("スタート展示")
    if i < 0:
        return {}
    blk = h[i:i + 8000]
    if not shown[0]:
        shown[0] = True
        print("---- スタート展示の表(最初の1件だけ確認用に出す) ----")
        print(re.sub(r"\s+", " ", blk[:2500]))
        print("----")
    out = {}
    spans = [(m.start(), int(m.group(1))) for m in NUM_RE.finditer(blk)]
    for k, (pos, w) in enumerate(spans):
        end = spans[k + 1][0] if k + 1 < len(spans) else pos + 1500
        seg = blk[pos:end]
        t = TIME_RE.search(seg) or ANY_ST_RE.search(seg[30:])
        out[w] = st_value(t.group(1)) if t else np.nan
    return out


def fetch_one(ymd, jcd, race):
    order, h = entry.fetch_order(ymd, f"{jcd:02d}", race)
    if h is None:
        return None
    est = parse_est(h)
    tj = entry.fetch_tenji(h) or []
    wx = entry.fetch_weather(h) or {}
    return dict(date=ymd, jcd=jcd, race=race, order=order or [],
                est=[float(est.get(w, np.nan)) for w in range(1, 7)],
                tenji=[float(x) for x in tj] if tj else [],
                wind=wx.get("wind", np.nan), wave=wx.get("wave", np.nan), wind_dir=wx.get("wind_dir"))


def load_day(ymd):
    p = OUT / f"{ymd}.parquet"
    return pd.read_parquet(p).to_dict("records") if p.exists() else []


def save_day(ymd, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).sort_values(["jcd", "race"]).to_parquet(OUT / f"{ymd}.parquet", index=False)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--max-minutes", type=float, default=330)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    a = ap.parse_args(argv)
    deadline = time.time() + a.max_minutes * 60
    days = list(daterange(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)))
    days = [d for i, d in enumerate(days) if i % a.shards == a.shard]
    days = days[::-1]   # 新しい日から取る(長い期間を渡しても、使いたい直近のデータから先にそろう)
    pool = ThreadPoolExecutor(2)
    n_new = n_empty = streak = n_noest = 0
    stopped = False
    for d in days:
        ymd = f"{d:%Y%m%d}"
        rows = load_day(ymd)
        have = {(r["jcd"], r["race"]) for r in rows}
        todo = [(j, r) for j, r in races_of(d.year).get(ymd, []) if (j, r) not in have]
        got = 0
        for k in range(0, len(todo), 2):
            if time.time() > deadline:
                stopped = True
                break
            futs = [pool.submit(fetch_one, ymd, j, r) for j, r in todo[k:k + 2]]
            time.sleep(0.5)
            for f in futs:
                r = f.result()
                if r is None:
                    n_empty += 1
                    streak += 1
                    continue
                streak = 0
                got += 1
                n_new += 1
                n_noest += all(np.isnan(r["est"]))
                rows.append(r)
            if streak >= STOP_EMPTY:
                print(f"{STOP_EMPTY}レース続けて取れなかったので止めます({ymd})")
                stopped = True
                break
        if got:
            save_day(ymd, rows)
        print(f"{ymd}: {len(todo)}レース中 {got}レース取得(累計 新規{n_new} 取れず{n_empty} 展示ST無し{n_noest})", flush=True)
        if stopped:
            break
    print(f"完了: 新規{n_new}レース(取れず{n_empty}、展示STが読めなかった{n_noest})")


if __name__ == "__main__":
    main()
