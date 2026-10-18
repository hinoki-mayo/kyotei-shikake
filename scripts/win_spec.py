"""1着専門の情報部員: 市場の1着の見方を土台に、ずれだけを学んで1着確率を出す

・材料: 市場の1着確率(2連単オッズの逆数を頭ごとに合計)、本予想の1着確率・頭の確率、級・勝率・モーター・年齢・
  ST予想・F・平均との差、インとのST差、展示タイムの平均との差と順位、インの級・勝率・ST・F、進入の変化、風・波
・2025年で学んで2026年で確かめ / 2026年で学んで2025年で確かめ、のどちらでも市場より正確(対数損失 1.149 vs 1.163、
  1.168 vs 1.181)。v2(柔軟型)の頭の確率をこれで直すと、確定オッズで113%→134%・114%→134%
・学習: python scripts/win_spec.py train 材料1.parquet 材料2.parquet → data/models/win_spec.pkl
"""
import functools
import math
import pickle
import sys

import numpy as np

from common import DATA

MODEL_P = DATA / "models" / "win_spec.pkl"
F = ["lq", "lp", "hp", "c", "gA", "g1", "nat", "mot", "age", "st", "f", "d_nat", "d_mot", "d_st", "st_in", "st_left",
     "d_ten", "ten_rk", "in_gA", "in_nat", "in_st", "in_f", "cw", "wind", "wave"]


@functools.lru_cache(maxsize=1)
def _load():
    return pickle.load(open(MODEL_P, "rb")) if MODEL_P.exists() else None


def features(pred, o2, live=None):
    """コース順6艇の材料。o2: {(1着の枠-1, 2着の枠-1): オッズ}。作れなければNone"""
    from bet import PI
    tri, boats = pred.get("tri"), pred["boats"]
    if not tri or not o2:
        return None
    waku = [b["waku"] for b in boats]
    inv = {}
    for (a, _), o in o2.items():
        if o:
            inv[a] = inv.get(a, 0) + 1 / o
    if len(inv) < 6:
        return None
    tot = sum(inv.values())
    p1 = [sum(tri[PI[(i, j, k)]] for j in range(6) for k in range(6) if len({i, j, k}) == 3) for i in range(6)]
    tj = (live or {}).get("tenji")
    tw = [tj[w - 1] if tj and w - 1 < len(tj) else None for w in waku]
    tv = [x for x in tw if x]
    nat = [b.get("nat_win") or 0 for b in boats]
    mot = [b.get("motor_2r") or 0 for b in boats]
    st, fc = pred["st"], pred["fcnt"]
    hp = pred["scene"]["head_prob"]
    ib = boats[0]
    nan = float("nan")
    rows = []
    for i, b in enumerate(boats):
        rows.append(dict(
            lq=math.log(inv[waku[i] - 1] / tot), lp=math.log(max(p1[i], 1e-4)), hp=hp[i], c=i + 1,
            gA=int(str(b["grade"]).startswith("A")), g1=int(str(b["grade"]) == "A1"), nat=nat[i], mot=mot[i], age=b.get("age") or 0,
            st=st[i], f=fc[i], d_nat=nat[i] - np.mean(nat), d_mot=mot[i] - np.mean(mot), d_st=st[i] - np.mean(st),
            st_in=st[i] - st[0], st_left=(st[i] - st[i - 1]) if i > 0 else 0,
            d_ten=(tw[i] - np.mean(tv)) if tw[i] and tv else nan, ten_rk=(sorted(tv).index(tw[i]) + 1) if tw[i] and tv else nan,
            in_gA=int(str(ib["grade"]).startswith("A")), in_nat=nat[0], in_st=st[0], in_f=fc[0],
            cw=int(b["course"] != b["waku"]),
            wind=float((live or {}).get("wind", nan) if (live or {}).get("wind") is not None else nan),
            wave=float((live or {}).get("wave", nan) if (live or {}).get("wave") is not None else nan)))
    return rows


def probs(pred, o2, live=None):
    """コース順6艇の1着確率(合計1)。モデルや材料が無ければNone"""
    M = _load()
    rows = features(pred, o2, live) if M else None
    if not rows:
        return None
    X = np.array([[r[f] for f in M["F"]] for r in rows], dtype=float)
    p = M["model"].predict_proba(X)[:, 1]
    return list(p / p.sum())


def train(paths):
    import pandas as pd
    from sklearn.ensemble import HistGradientBoostingClassifier
    d = pd.concat([pd.read_parquet(p) for p in paths])
    m = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.03, max_leaf_nodes=15, min_samples_leaf=300,
                                       l2_regularization=1.0).fit(d[F], d.hit)
    MODEL_P.parent.mkdir(parents=True, exist_ok=True)
    pickle.dump(dict(model=m, F=F, period=[d.date.min(), d.date.max()]), open(MODEL_P, "wb"))
    print(f"学習 {len(d)}艇({d.date.min()}〜{d.date.max()}) → {MODEL_P}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["train"]:
        train(sys.argv[2:])
