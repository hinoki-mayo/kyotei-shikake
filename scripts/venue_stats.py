"""場ごとの特徴(場の常設ページ用): コース別の1着率・2着以内率、決まり手、3連単の配当の目安、女子戦の傾向
例: python scripts/venue_stats.py  → data/venue_stats.json(成績が増えたら時々作り直す)
・コース・着順・決まり手は 2024年〜今年の競走成績、3連単の配当は払戻のある年(2026年〜)だけ
"""
import json

import pandas as pd

from common import DATA

LADY = "女子|レディース|ヴィーナス|ビーナス|クイーンズ|オールレディ"


def main():
    years = [y for y in range(2024, 2031) if (DATA / "results" / f"{y}.parquet").exists()]
    r = pd.concat([pd.read_parquet(DATA / "results" / f"{y}.parquet") for y in years])
    r = r[r.course.notna()]
    pr = pd.concat([pd.read_parquet(DATA / "programs" / f"{y}.parquet", columns=["date", "jcd", "race", "title"])
                    for y in years if (DATA / "programs" / f"{y}.parquet").exists()]).drop_duplicates(["date", "jcd", "race"])
    r = r.merge(pr, on=["date", "jcd", "race"], how="left")
    r["lady"] = r.title.str.contains(LADY, na=False)
    r["w"] = r["rank"] == "01"
    r["t2"] = r["rank"].isin(["01", "02"])
    out = {}
    for jcd, g in r.groupby("jcd"):
        races = g.drop_duplicates(["date", "race"])
        w = g[g.w]
        c = g.groupby("course").agg(w=("w", "mean"), t2=("t2", "mean"))
        pay = races[races.payout3t.notna()].payout3t if "payout3t" in races else pd.Series(dtype=float)
        lady = g[g.lady]
        out[jcd] = dict(
            races=int(len(races)), since=str(g.date.min()),
            course=[[round(float(c.loc[k, "w"]), 3), round(float(c.loc[k, "t2"]), 3)] if k in c.index else [0, 0] for k in range(1, 7)],
            kimarite={k: round(float(v), 3) for k, v in w.kimarite.value_counts(normalize=True).items() if k},
            pay_median=float(pay.median()) if len(pay) else None,
            manshu=round(float((pay >= 10000).mean()), 3) if len(pay) else None,
            lady_races=int(lady.drop_duplicates(["date", "race"]).shape[0]),
            lady_in=round(float(lady[lady.course == 1].w.mean()), 3) if len(lady) else None)
    allc = r.groupby("course").w.mean()
    out["_all"] = dict(course=[round(float(allc.get(k, 0)), 3) for k in range(1, 7)])
    (DATA / "venue_stats.json").write_text(json.dumps(out, ensure_ascii=False, indent=0))
    print(f"{len(out) - 1}場 → {DATA / 'venue_stats.json'}")


if __name__ == "__main__":
    main()
