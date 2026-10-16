"""過去レースの確定オッズを集める。
例: python scripts/fetch_odds_hist.py --start 2026-06-01 --end 2026-09-30 [--sleep 1.0] [--max-minutes 330]

市場の確率(オッズの逆数)と実際の結果を、数か月〜数年ぶんで比べるためのデータ。
・レース一覧は data/results/<年>.parquet から取る(実際に走ったレースだけ)
・3連単120通り・2連単30通りを bet.fetch_odds / bet.fetch_odds2 で取る(枠番キー、bet.py と同じ)
・公式サイトの応答が1ページ約9秒と遅いので、3連単と2連単は同時に取る。1日(約150レース)で約25分。
  --shard i --shards n で日付を分け、Actionsで複数ジョブ同時に流す(各ジョブ自分の日付だけ取る)
・保存先: data/odds_hist/YYYYMMDD.parquet(1日1ファイル、1レース1行。初回の8月分だけ YYYYMM.parquet)
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
from concurrent.futures import ThreadPoolExecutor

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


def load_day(ymd):
    rows = []
    for p in (HIST / f"{ymd[:6]}.parquet", HIST / f"{ymd}.parquet"):
        if p.exists():
            df = pd.read_parquet(p)
            rows += df[df.date == ymd].to_dict("records")
    return rows


def save_day(ymd, rows):
    HIST.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=["date", "jcd", "race", "o3", "o2"])
    df["o3"] = df["o3"].apply(lambda x: [float(v) for v in x])
    df["o2"] = df["o2"].apply(lambda x: [float(v) for v in x])
    df.sort_values(["jcd", "race"]).to_parquet(HIST / f"{ymd}.parquet", index=False)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--max-minutes", type=float, default=330)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    a = ap.parse_args(argv)
    deadline = time.time() + a.max_minutes * 60
    days = list(daterange(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)))
    days = [d for i, d in enumerate(days) if i % a.shards == a.shard]
    days = days[::-1]   # 新しい日から取る(長い期間を渡しても、使いたい直近のデータから先にそろう)
    n_new = n_empty = streak = 0
    stopped = False
    pool = ThreadPoolExecutor(2)
    for d in days:
        ymd = f"{d:%Y%m%d}"
        rows = load_day(ymd)
        have = {(r["date"], int(r["jcd"]), int(r["race"])) for r in rows}
        todo = [(j, r) for j, r in races_of(d.year).get(ymd, []) if (ymd, j, r) not in have]
        if not todo:
            continue
        got = unsaved = 0
        for jcd, race in todo:
            if time.time() > deadline:
                stopped = True
                break
            f3 = pool.submit(bet.fetch_odds, ymd, f"{jcd:02d}", race)
            f2 = pool.submit(bet.fetch_odds2, ymd, f"{jcd:02d}", race)
            o3, o2 = f3.result(), f2.result()
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
            n_new += 1
            unsaved += 1
            if unsaved >= FLUSH_EVERY:
                save_day(ymd, rows)
                unsaved = 0
        if unsaved:
            save_day(ymd, rows)
        print(f"{ymd}: {len(todo)}レース中 {got}レース取得(累計 新規{n_new} 取れず{n_empty})", flush=True)
        if stopped:
            print("途中で止めました。保存済みのぶんはそのまま使えます")
            break
    print(f"完了: 新規{n_new}レース(両方取れず飛ばした{n_empty}レース)")


if __name__ == "__main__":
    main()
