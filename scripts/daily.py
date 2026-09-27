"""毎日の更新。直近3日の競走成績と、今日・明日の番組表を取り直して表に反映する。

成績は当日夜〜翌日に確定・公開されるので、少し前の日まで毎回取り直しておくと取りこぼしがありません。
"""
import datetime as dt

from common import download, today_jst
from store import upsert


def main():
    t = today_jst()
    k_days = [t - dt.timedelta(days=i) for i in (2, 1, 0)]
    b_days = [t, t + dt.timedelta(days=1)]
    for d in k_days:
        download("K", d, force=True)
    for d in b_days:
        download("B", d, force=True)
    upsert("K", k_days)
    upsert("B", b_days)


if __name__ == "__main__":
    main()
