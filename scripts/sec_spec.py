"""2着専門の情報部員: 1着の艇が決まった時に、残り5艇のうち誰が2着かを、市場の2着の見方を土台に学ぶ

・材料: 市場の2着の見方(その頭の2連単オッズの逆数を5艇で合計1にそろえたもの)、本予想の2着の見方、
  2着候補の艇の級・勝率・モーター・年齢・ST予想・F・平均との差・展示、頭の艇との位置(内側か・隣か)とSTの差、頭の艇の級・勝率
・2025年で学んで2026年で確かめ / 2026年で学んで2025年で確かめ、のどちらでも市場より正確(対数損失 1.331 vs 1.344、1.343 vs 1.354)
・学習: python scripts/sec_spec.py train 材料.parquet → data/models/sec_spec.pkl
"""
import functools
import math
import pickle
import sys

import numpy as np

from common import DATA

MODEL_P = DATA / "models" / "sec_spec.pkl"
B = ["c", "gA", "g1", "nat", "mot", "age", "st", "f", "d_nat", "d_mot", "d_st", "st_in", "d_ten", "ten_rk", "wind", "wave", "lp"]


@functools.lru_cache(maxsize=1)
def _load():
    return pickle.load(open(MODEL_P, "rb")) if MODEL_P.exists() else None


def probs(pred, a, o2, live=None):
    """頭がコースa(0始まり)の時の、残り5艇の2着確率 {コース(0始まり): 確率}。作れなければNone"""
    import win_spec
    from bet import PI
    M = _load()
    if M is None or not pred.get("tri") or not o2:
        return None
    rows = win_spec.features(pred, o2, live)
    if not rows:
        return None
    waku = [b["waku"] for b in pred["boats"]]
    cand = [j for j in range(6) if j != a]
    od = {j: o2.get((waku[a] - 1, waku[j] - 1)) for j in cand}
    if not all(od.values()):
        return None
    inv = {j: 1 / od[j] for j in cand}
    t = sum(inv.values())
    tri = pred["tri"]
    mp = {j: sum(tri[PI[(a, j, k)]] for k in range(6) if k not in (a, j)) for j in cand}
    ms = sum(mp.values()) or 1e-9
    ra = rows[a]
    X = []
    for j in cand:
        rb = rows[j]
        r = dict(lsq=math.log(max(inv[j] / t, 1e-6)), lsp=math.log(max(mp[j] / ms, 1e-6)), c1=a + 1, c2=j + 1,
                 inner=int(j < a), next_a=int(j == a + 1), prev_a=int(j == a - 1), d_st_a=rb["st"] - ra["st"],
                 a_gA=ra["gA"], a_nat=ra["nat"], a_lp=ra["lp"], **{f"b_{k}": rb[k] for k in B if k != "c"})
        X.append([r[f] for f in M["F"]])
    p = M["model"].predict_proba(np.array(X, dtype=float))[:, 1]
    p = p / p.sum()
    return dict(zip(cand, p))


def train(paths):
    import pandas as pd
    from sklearn.ensemble import HistGradientBoostingClassifier
    d = pd.concat([pd.read_parquet(p) for p in paths])
    F = ["lsq", "lsp", "c1", "c2", "inner", "next_a", "prev_a", "d_st_a", "a_gA", "a_nat", "a_lp"] + [f"b_{k}" for k in B if k != "c"]
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.04, max_leaf_nodes=15, min_samples_leaf=200,
                                       l2_regularization=1.0).fit(d[F], d.hit)
    MODEL_P.parent.mkdir(parents=True, exist_ok=True)
    pickle.dump(dict(model=m, F=F, period=[d.date.min(), d.date.max()]), open(MODEL_P, "wb"))
    print(f"学習 {len(d)}行({d.date.min()}〜{d.date.max()}) → {MODEL_P}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["train"]:
        train(sys.argv[2:])
