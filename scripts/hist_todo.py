"""過去データ(odds_hist / before_hist)の取り残しを数える。Actionsの続き実行の判定用
例: python scripts/hist_todo.py odds_hist 2026-01-01 2026-05-31  → 取り残しの日数を出力(0なら完了)
・その日の実走レースの9割以上が保存されていれば取り終わりとみなす(公式に無いレースもあるため)
"""
import datetime as dt
import sys

import pandas as pd

from common import DATA, daterange
from fetch_odds_hist import races_of


def todo_days(kind, start, end):
    out = []
    for d in daterange(dt.date.fromisoformat(start), dt.date.fromisoformat(end)):
        ymd = f"{d:%Y%m%d}"
        n = len(races_of(d.year).get(ymd, []))
        if not n:
            continue
        got = 0
        for p in (DATA / kind / f"{ymd[:6]}.parquet", DATA / kind / f"{ymd}.parquet"):
            if p.exists():
                df = pd.read_parquet(p, columns=["date"]) if kind == "odds_hist" else pd.read_parquet(p, columns=["jcd"])
                got += int((df.date == ymd).sum()) if kind == "odds_hist" else len(df)
        if got < 0.9 * n:
            out.append(ymd)
    return out


if __name__ == "__main__":
    t = todo_days(*sys.argv[1:4])
    print(len(t))
    print(" ".join(t[:10]), file=sys.stderr)
