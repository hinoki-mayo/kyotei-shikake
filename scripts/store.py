"""変換した表を年ごとのparquetに保存・追記する"""
import datetime as dt

import pandas as pd

from common import DATA, raw_path, read_text
from parse import parse_program, parse_results

KINDS = {"K": ("results", parse_results), "B": ("programs", parse_program)}


def rows_for_day(kind: str, day: dt.date):
    path = raw_path(kind, day)
    if not path.exists():
        return []
    return KINDS[kind][1](read_text(path), f"{day:%Y%m%d}")


def upsert(kind: str, days):
    """指定日の分を差し替えて保存(同じ日を何度流しても重複しない)"""
    folder = DATA / KINDS[kind][0]
    folder.mkdir(parents=True, exist_ok=True)
    by_year = {}
    for d in days:
        by_year.setdefault(d.year, []).append(d)
    total = 0
    for year, ds in by_year.items():
        new = [r for d in ds for r in rows_for_day(kind, d)]
        path = folder / f"{year}.parquet"
        old = pd.read_parquet(path) if path.exists() else pd.DataFrame()
        keys = {f"{d:%Y%m%d}" for d in ds}
        if len(old):
            old = old[~old["date"].isin(keys)]
        df = pd.concat([old, pd.DataFrame(new)], ignore_index=True)
        if len(df):
            df = df.sort_values(["date", "jcd", "race", "waku"]).reset_index(drop=True)
            df.to_parquet(path, index=False, compression="zstd")
        total += len(new)
        print(f"{KINDS[kind][0]}/{year}.parquet: +{len(new)}行 (合計{len(df)}行)")
    return total
