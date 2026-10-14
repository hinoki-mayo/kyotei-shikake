"""過去レースの確定オッズを集める。
例: python scripts/fetch_odds_hist.py --start 2026-06-01 --end 2026-09-30 [--sleep 1.0] [--max-minutes 330]

市場の確率(オッズの逆数)と実際の結果を、数か月〜数年ぶんで比べるためのデータ。
・レース一覧は data/results/<年>.parquet から取る(実際に走ったレースだけ)
・3連単120通り・2連単30通りを bet.fetch_odds / bet.fetch_odds2 で取る(枠番キー、bet.py と同じ)
・1リクエストごとに間を空ける(既定1秒)。1レースで2リクエストなので1日(約150レース)で約5分、1回の実行(330分)で約2か月
・保存先: data/odds_hist/YYYYMM.parquet(1レース1行)
    date : str  YYYYMMDD
    jcd  : int  場コード
    race : int  レース番号
    o3   : 長さ120のfloat配列。並びは bet.ODDS_ORDER(公式オッズ表の順)。売っていない目・取れなかった目はNaN
    o2   : 長さ30のfloat配列。並びは 1-2,1-3,1-4,1-5,1-6,2-1,2-3,...,6-4,6-5(1着の枠の昇順→2着の枠の昇順)。欠けはNaN
  両方取れなかったレースは記録しない(次に流した時に取り直す)。続けて STOP_EMPTY レース取れなかったら、
  公式サイトが止まっているか古すぎて見られないとみて打ち切る
・保存済みのレースは飛ばすので、同じコマンドを流し直せば続きから再開する
・50レースごと・最後・--max-minutes 経過時に保存する(Actionsの時間切れ前にコミットするため)
"""
import argparse
import datetime as dt
import time

import numpy as np
import pandas as pd

import bet
from common import DATA, daterange

HIST = DATA / "odds_hist"
FLUSH_EVERY = 50
STOP_EMPTY = 20   # 続けてこれだけ取れなかったら打ち切る
# 2連単の並び: 1-2,1-3,...,6-5
O2_ORDER = [(a, b) for a in range(6) for b in range(6) if a != b]


def races_of(year, cache={}):
    """その年の実走レース {日付: [(jcd(int), race)]}"""
    if year not in cache:
        p = DATA / "results" / f"{year}.parquet"
        out = {}
        if p.exists():
            df = pd.read_parquet(p, columns=["date", "jcd", "race"]).drop_duplicates()
            df["jcd"] = df["jcd"].astype(int)
            df["race"] = df["race"].astype(int)
            for d, g in df.sort_values(["date", "jcd", "race"]).groupby("date"):
                out[d] = list(zip(g["jcd"], g["race"]))
        cache[year] = out
    return cache[year]


def to_arr(d, order):
    if not d:
        return []
    return [float(d.get(k, np.nan)) for k in order]


def load_month(ym):
    p = HIST / f"{ym}.parquet"
    if p.exists():
        return pd.read_parquet(p).to_dict("records")
    return []


def save_month(ym, rows):
    HIST.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=["date", "jcd", "race", "o3", "o2"])
    df["o3"] = df["o3"].apply(lambda x: [float(v) for v in x])
    df["o2"] = df["o2"].apply(lambda x: [float(v) for v in x])
    df.sort_values(["date", "jcd", "race"]).to_parquet(HIST / f"{ym}.parquet", index=False)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--max-minutes", type=float, default=330)
    a = ap.parse_args(argv)
    deadline = time.time() + a.max_minutes * 60
    days = list(daterange(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)))
    months = {}
    for d in days:
        months.setdefault(f"{d:%Y%m}", []).append(d)
    n_new = n_empty = streak = 0
    stopped = False
    for ym, ds in months.items():
        rows = load_month(ym)
        have = {(r["date"], int(r["jcd"]), int(r["race"])) for r in rows}
        unsaved = 0
        for d in ds:
            ymd = f"{d:%Y%m%d}"
            todo = [(j, r) for j, r in races_of(d.year).get(ymd, []) if (ymd, j, r) not in have]
            if not todo:
                continue
            got = 0
            for jcd, race in todo:
                if time.time() > deadline:
                    stopped = True
                    break
                o3 = bet.fetch_odds(ymd, f"{jcd:02d}", race)
                time.sleep(a.sleep)
                o2 = bet.fetch_odds2(ymd, f"{jcd:02d}", race)
                time.sleep(a.sleep)
                a3, a2 = to_arr(o3, bet.ODDS_ORDER), to_arr(o2, O2_ORDER)
                if not a3 and not a2:
                    n_empty += 1
                    streak += 1
                    if streak >= STOP_EMPTY:
                        print(f"{STOP_EMPTY}レース続けて取れなかったので止めます({ymd} {jcd:02d}場 {race}R)")
                        stopped = True
                        break
                    continue
                streak = 0
                got += 1
                rows.append({"date": ymd, "jcd": jcd, "race": race, "o3": a3, "o2": a2})
                have.add((ymd, jcd, race))
                n_new += 1
                unsaved += 1
                if unsaved >= FLUSH_EVERY:
                    save_month(ym, rows)
                    unsaved = 0
            print(f"{ymd}: {len(todo)}レース中 {got}レース取得(累計 新規{n_new} 取れず{n_empty})", flush=True)
            if stopped:
                break
        if unsaved:
            save_month(ym, rows)
        if stopped:
            print("途中で止めました。保存済みのぶんはそのまま使えます")
            break
    print(f"完了: 新規{n_new}レース(両方取れず飛ばした{n_empty}レース)")


if __name__ == "__main__":
    main()
