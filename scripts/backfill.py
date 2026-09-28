"""過去データの一括取得。例: python scripts/backfill.py --start 2020-10-01 --end 2021-09-30

・公式サーバーに負担をかけないよう1ファイルごとに間を空けます(既定1秒)
・1か月ごとに表へ保存するので、途中で止まっても保存済みの月は失われません
・すでに表に入っている日は飛ばすので、同じコマンドを流し直せば続きから再開します
"""
import argparse
import datetime as dt

import pandas as pd

from common import DATA, daterange, download
from store import KINDS, upsert


def done_dates(kind: str, years):
    s = set()
    for y in years:
        p = DATA / KINDS[kind][0] / f"{y}.parquet"
        if p.exists():
            s |= set(pd.read_parquet(p, columns=["date"])["date"].unique())
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--kinds", default="K,B", help="K=競走成績, B=番組表")
    ap.add_argument("--sleep", type=float, default=0.83)
    a = ap.parse_args()
    start, end = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    days = list(daterange(start, end))
    months = {}
    for d in days:
        months.setdefault((d.year, d.month), []).append(d)
    for kind in a.kinds.split(","):
        skip = done_dates(kind, {d.year for d in days})
        for (y, m), ds in months.items():
            todo = [d for d in ds if f"{d:%Y%m%d}" not in skip]
            if not todo:
                print(f"{kind} {y}-{m:02d}: 取得済み")
                continue
            got = sum(download(kind, d, sleep=a.sleep) for d in todo)
            print(f"{kind} {y}-{m:02d}: {got}/{len(todo)}日ぶん取得", flush=True)
            upsert(kind, todo)


if __name__ == "__main__":
    main()
