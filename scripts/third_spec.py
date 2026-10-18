"""3着専門の情報部員: 1着・2着が決まった時に、残り4艇のうち誰が3着かを、市場の3着の見方を土台に学ぶ

・材料: 市場の3着の見方(その1-2の3連単オッズの逆数を4艇で合計1にそろえたもの)、本予想の3着の見方、1着確率、
  級・勝率・モーター・年齢・ST予想・F、4艇の平均との差、展示タイムの差、内側の艇の数、2着・1着の隣か、風・波
・2025年で学んで2026年で確かめ / 2026年で学んで2025年で確かめ、のどちらでも市場よりわずかに正確(イン逃げ・イン負けとも)
・学習: python scripts/third_spec.py train 材料1.parquet 材料2.parquet → data/models/third_spec.pkl
"""
import functools
import math
import pickle
import sys

import numpy as np

from common import DATA

MODEL_P = DATA / "models" / "third_spec.pkl"
F = ["lmq", "lmp", "win", "nat", "mot", "age", "gA", "st", "f", "d_nat", "d_mot", "d_st", "d_ten", "inner", "next_b", "next_a",
     "a", "b", "c", "wind", "wave"]


@functools.lru_cache(maxsize=1)
def _load():
    return pickle.load(open(MODEL_P, "rb")) if MODEL_P.exists() else None


def probs(pred, a, b, o3, live=None):
    """1着コースa・2着コースb(0始まり)の時の、残り4艇の3着確率 {コース(0始まり): 確率}。作れなければNone"""
    from bet import PI
    M = _load()
    if M is None or not pred.get("tri") or not o3:
        return None
    boats = pred["boats"]
    waku = [x["waku"] for x in boats]
    cand = [j for j in range(6) if j not in (a, b)]
    od = {j: o3.get((waku[a] - 1, waku[b] - 1, waku[j] - 1)) for j in cand}
    if not all(od.values()):
        return None
    inv = {j: 1 / od[j] for j in cand}
    t = sum(inv.values())
    mp = {j: pred["tri"][PI[(a, b, j)]] for j in cand}
    ms = sum(mp.values()) or 1e-9
    tj = (live or {}).get("tenji")
    tw = [tj[w - 1] if tj and w - 1 < len(tj) else None for w in waku]
    tv = [x for x in (tw[j] for j in cand) if x]
    nat = [boats[j].get("nat_win") or 0 for j in cand]
    mot = [boats[j].get("motor_2r") or 0 for j in cand]
    st = [pred["st"][j] for j in cand]
    nan = float("nan")
    rows = []
    for j in cand:
        x = boats[j]
        r = dict(lmq=math.log(inv[j] / t), lmp=math.log(max(mp[j] / ms, 1e-4)), win=float(sum(pred["prob"][j])),
                 nat=x.get("nat_win") or 0, mot=x.get("motor_2r") or 0, age=x.get("age") or 0, gA=int(str(x["grade"]).startswith("A")),
                 st=pred["st"][j], f=pred["fcnt"][j], d_nat=(x.get("nat_win") or 0) - np.mean(nat),
                 d_mot=(x.get("motor_2r") or 0) - np.mean(mot), d_st=pred["st"][j] - np.mean(st),
                 d_ten=(tw[j] - np.mean(tv)) if tw[j] and tv else nan, inner=int(sum(1 for k in cand if k < j)),
                 next_b=int(j == b + 1), next_a=int(j == a + 1), a=a + 1, b=b + 1, c=j + 1,
                 wind=float((live or {}).get("wind")) if (live or {}).get("wind") is not None else nan,
                 wave=float((live or {}).get("wave")) if (live or {}).get("wave") is not None else nan)
        rows.append([r[f] for f in M["F"]])
    p = M["model"].predict_proba(np.array(rows, dtype=float))[:, 1]
    p = p / p.sum()
    return dict(zip(cand, p))


def train(paths):
    import pandas as pd
    from sklearn.ensemble import HistGradientBoostingClassifier
    d = pd.concat([pd.read_parquet(p) for p in paths])
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.04, max_leaf_nodes=15, min_samples_leaf=200,
                                       l2_regularization=1.0).fit(d[F], d.hit)
    MODEL_P.parent.mkdir(parents=True, exist_ok=True)
    pickle.dump(dict(model=m, F=F, period=[d.date.min(), d.date.max()]), open(MODEL_P, "wb"))
    print(f"学習 {len(d)}行({d.date.min()}〜{d.date.max()}) → {MODEL_P}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["train"]:
        train(sys.argv[2:])
