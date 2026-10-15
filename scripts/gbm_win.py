"""実績だけで作る1着確率の予想(オッズは使わない)。B級イン・裏の穴(pickura)で使う

・選手のコース別の勝率・連対率、全国/当地勝率、級、年齢、体重、モーター・ボート、平均ST、F、
  展示タイム、風・波と、それらのレース内での順位・平均との差・インとの差から、勾配ブースティングで1着確率を出す
・選手の成績は「その月より前」の累積だけを使う(学習と本番で同じ作り方)
・確定オッズ6/1〜10/13で、市場(log loss 1.1525)には届かない(1.1808)が、今のモデル(1.1924)よりは良い。
  B級インのレースで市場が軽く見ている他艇(この予想÷市場が1.7倍以上)は、6〜7月・8〜10月とも1着が市場の1.26・1.28倍
学習: python scripts/gbm_win.py train  → data/models/gbm_win.pkl
"""
import functools
import pickle
import sys

import numpy as np
import pandas as pd

from common import DATA

MODEL_P = DATA / "models" / "gbm_win.pkl"
KEY = ["date", "jcd", "race"]
X = ["course", "gnum", "nat_win", "nat_2r", "loc_win", "motor_2r", "boat_2r", "age", "weight", "avgst", "cwr", "ct2r",
     "awr", "fy", "tenji", "wind", "wave",
     "nat_win_rk", "motor_2r_rk", "tenji_rk", "avgst_rk", "cwr_rk", "awr_rk",
     "nat_win_dm", "motor_2r_dm", "tenji_dm", "avgst_dm", "cwr_dm", "awr_dm",
     "in_nat_win", "in_avgst", "in_tenji", "in_cwr"]
PCOLS = ["date", "jcd", "race", "waku", "toban", "grade", "nat_win", "nat_2r", "loc_win", "motor_2r", "boat_2r", "age", "weight"]


def _results(years):
    fr = [pd.read_parquet(DATA / "results" / f"{y}.parquet",
                          columns=["date", "jcd", "race", "waku", "toban", "course", "stv", "tenji", "rank", "wind", "wave"])
          for y in years if (DATA / "results" / f"{y}.parquet").exists()]
    r = pd.concat(fr).drop_duplicates(["date", "jcd", "race", "waku"])
    r = r[r.course.notna()].copy()
    r["course"] = r.course.astype(int)
    r["ym"] = r.date.str[:6]
    r["w"] = (r["rank"] == "01").astype(int)
    r["t2"] = r["rank"].isin(["01", "02"]).astype(int)
    r["stok"] = r.stv.where(r.stv >= 0)
    r["f"] = (r.stv < 0).astype(int)
    return r


def _monthly(r):
    """選手×月・選手×コース×月の集計"""
    rc = r.groupby(["toban", "course", "ym"]).agg(w=("w", "sum"), t2=("t2", "sum"), n=("w", "size")).reset_index()
    ra = r.groupby(["toban", "ym"]).agg(w=("w", "sum"), n=("w", "size"), st_s=("stok", "sum"), st_n=("stok", "count"),
                                        f=("f", "sum")).reset_index()
    return rc, ra


def _priors(r):
    return dict(cprior=r.groupby("course").w.mean().to_dict(), gm=float(r.stok.mean()))


def _derive(d, pri):
    """累積の数値から特徴を作る(d: 1行1艇、1レース6行そろっていること)"""
    cp = d.course.map(pri["cprior"])
    d["cwr"] = (d.rw.fillna(0) + 10 * cp) / (d.rn.fillna(0) + 10)
    d["ct2r"] = (d.rt2.fillna(0) + 10 * cp * 2) / (d.rn.fillna(0) + 10)
    d["awr"] = (d.aw.fillna(0) + 20 * 0.167) / (d.an.fillna(0) + 20)
    d["avgst"] = (d.st_s.fillna(0) + 20 * pri["gm"]) / (d.st_n.fillna(0) + 20)
    d["fy"] = d.fy.fillna(0)
    d["gnum"] = d.grade.map({"A1": 4, "A2": 3, "B1": 2, "B2": 1})
    for f in ("nat_win", "motor_2r", "tenji", "avgst", "cwr", "awr"):
        d[f + "_rk"] = d.groupby(KEY)[f].rank(ascending=(f in ("tenji", "avgst")))
        d[f + "_dm"] = d[f] - d.groupby(KEY)[f].transform("mean")
    inn = d[d.course == 1].set_index(KEY)[["nat_win", "avgst", "tenji", "cwr"]].add_prefix("in_")
    d = d.drop(columns=[c for c in inn.columns if c in d.columns]).join(inn, on=KEY)
    return d


def train(until="20261014"):
    from sklearn.ensemble import HistGradientBoostingClassifier
    r = _results(range(2022, int(until[:4]) + 1))
    r = r[r.date < until]
    rc, ra = _monthly(r)
    rc = rc.sort_values(["toban", "course", "ym"])
    for c in ("w", "t2", "n"):
        rc["r" + c] = rc.groupby(["toban", "course"])[c].cumsum() - rc[c]   # その月より前の累積
    ra = ra.sort_values(["toban", "ym"])
    for c, o in (("w", "aw"), ("n", "an"), ("st_s", "st_s"), ("st_n", "st_n")):
        ra[o + "_c"] = ra.groupby("toban")[c].cumsum() - ra[c]
    ra["fy"] = ra.groupby("toban").f.transform(lambda s: s.rolling(6, min_periods=1).sum().shift(1).fillna(0))
    p = pd.concat([pd.read_parquet(DATA / "programs" / f"{y}.parquet", columns=PCOLS)
                   for y in range(2022, int(until[:4]) + 1)]).drop_duplicates(["date", "jcd", "race", "waku"])
    d = r.merge(p.drop(columns=["toban"]), on=["date", "jcd", "race", "waku"], how="inner")
    d = d.merge(rc[["toban", "course", "ym", "rw", "rt2", "rn"]], on=["toban", "course", "ym"], how="left")
    d = d.merge(ra[["toban", "ym", "aw_c", "an_c", "st_s_c", "st_n_c", "fy"]].rename(
        columns={"aw_c": "aw", "an_c": "an", "st_s_c": "st_s", "st_n_c": "st_n"}), on=["toban", "ym"], how="left")
    d = d[d.groupby(KEY).waku.transform("size") == 6]
    pri = _priors(r)
    d = _derive(d, pri)
    d = d[d.date >= "20230701"]
    m = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=31,
                                       l2_regularization=1.0).fit(d[X], d.w)
    MODEL_P.parent.mkdir(parents=True, exist_ok=True)
    pickle.dump(dict(model=m, X=X, pri=pri, until=until), open(MODEL_P, "wb"))
    print(f"学習 {len(d)}艇(〜{until}) → {MODEL_P}")


@functools.lru_cache(maxsize=1)
def _load():
    return pickle.load(open(MODEL_P, "rb")) if MODEL_P.exists() else None


@functools.lru_cache(maxsize=2)
def _hist(month):
    """その月の初めの時点の選手の累積成績(本番用)"""
    y = int(month[:4])
    r = _results(range(y - 4, y + 1))
    r = r[r.ym < month]
    rc, ra = _monthly(r)
    hc = rc.groupby(["toban", "course"]).agg(rw=("w", "sum"), rt2=("t2", "sum"), rn=("n", "sum"))
    ha = ra.groupby("toban").agg(aw=("w", "sum"), an=("n", "sum"), st_s=("st_s", "sum"), st_n=("st_n", "sum"))
    last6 = sorted(r.ym.unique())[-6:]
    ha["fy"] = ra[ra.ym.isin(last6)].groupby("toban").f.sum()
    return hc, ha


@functools.lru_cache(maxsize=2)
def _programs(date):
    p = pd.read_parquet(DATA / "programs" / f"{date[:4]}.parquet", columns=PCOLS)
    return p[p.date == date].drop_duplicates(["jcd", "race", "waku"]).set_index(["jcd", "race", "waku"])


def probs(pred, date, live=None):
    """予想(コース順のboats)と直前情報から、コース順の1着確率6つ。作れなければNone"""
    M = _load()
    if M is None:
        return None
    try:
        prog = _programs(date)
        hc, ha = _hist(date[:6])
    except Exception:
        return None
    tj = (live or {}).get("tenji")
    rows = []
    for c, b in enumerate(pred["boats"], start=1):
        k = (pred["jcd"], int(pred["race"]), int(b["waku"]))
        if k not in prog.index:
            return None
        pr = prog.loc[k]
        row = dict(date=date, jcd=pred["jcd"], race=int(pred["race"]), waku=int(b["waku"]), toban=b["toban"], course=c,
                   grade=pr.grade, nat_win=pr.nat_win, nat_2r=pr.nat_2r, loc_win=pr.loc_win, motor_2r=pr.motor_2r,
                   boat_2r=pr.boat_2r, age=pr.age, weight=pr.weight,
                   tenji=(tj[b["waku"] - 1] if tj and len(tj) == 6 else np.nan),
                   wind=(live or {}).get("wind", np.nan), wave=(live or {}).get("wave", np.nan))
        hcrow = hc.loc[(b["toban"], c)] if (b["toban"], c) in hc.index else None
        harow = ha.loc[b["toban"]] if b["toban"] in ha.index else None
        for f in ("rw", "rt2", "rn"):
            row[f] = hcrow[f] if hcrow is not None else np.nan
        for f in ("aw", "an", "st_s", "st_n", "fy"):
            row[f] = harow[f] if harow is not None else np.nan
        rows.append(row)
    d = _derive(pd.DataFrame(rows), M["pri"])
    p = M["model"].predict_proba(d[M["X"]].astype(float))[:, 1]
    return list(p / p.sum())


if __name__ == "__main__":
    if sys.argv[1:2] == ["train"]:
        train(*sys.argv[2:3])
