"""2・3着モデルと3連単120通りの確率

1着艇wと決まり手mが決まったとき、残りの艇から2着、さらに3着をソフトマックスで選ぶ。
決まり手はレース前には分からないので、本体モデルの確率P[w,m]で混ぜる:
    P(w,j,k) = Σ_m P[w,m] × p2(j | w,m) × p3(k | w,m,j)
「まくりで決まると内側の艇は沈み、外側がついていく」のような展開の癖を2・3着に反映する。
1着確率だけから順番に積むPlackett-Luceは本命寄りの目を大きく過大評価していた(23.8%と出した目が実際15.3%)。
"""
import itertools
import json
import pathlib

import numpy as np

PRM = json.loads((pathlib.Path(__file__).parent / "params.json").read_text())["place"]
TH2 = np.array(PRM["second"]["theta"])
TH3 = np.array(PRM["third"]["theta"])
PERMS = list(itertools.permutations(range(6), 3))   # コース(0始まり)の(1着,2着,3着)


def _feats(P, st, ab, tenji_z, motor, w, m, prev=None):
    """各艇の特徴量(6,F)。並びは学習時(params.jsonのnames)と同じ"""
    h = P.sum(1)
    k = np.arange(6)
    rel = k - w
    cols = [np.log(h + 1e-4)]
    for mi in range(4):
        for c in (rel <= -2, rel == -1, rel == 1, rel >= 2):    # 遠い内/すぐ内/すぐ外/遠い外
            cols.append(((m == mi) & c).astype(float))
    for c in range(1, 6):
        cols.append((k == c).astype(float))
    cols.append(np.clip(st - st[w], -0.2, 0.2) * 10)
    cols.append((st.mean() - st) * 10)
    cols.append(ab - ab.mean())
    cols.append(tenji_z)
    cols.append(motor)
    if prev is not None:
        relp = k - prev
        cols.append((np.abs(relp) == 1).astype(float))
        cols.append((relp < 0).astype(float))
    return np.stack(cols, -1)


def _softmax(s, used):
    s = s.copy()
    s[list(used)] = -np.inf
    e = np.exp(s - s[np.isfinite(s)].max())
    return e / e.sum()


def trifecta_probs(P, st, ab, tenji_z, motor):
    """コース順の入力から、PERMSの順に並べた3連単120通りの確率を返す"""
    P = np.asarray(P, float)
    out = np.zeros(120)
    idx = {p: i for i, p in enumerate(PERMS)}
    for w in range(6):
        for m in range(4):
            pm = P[w, m]
            if pm <= 1e-9:
                continue
            p2 = _softmax(_feats(P, st, ab, tenji_z, motor, w, m) @ TH2, {w})
            for j in range(6):
                if j == w:
                    continue
                p3 = _softmax(_feats(P, st, ab, tenji_z, motor, w, m, j) @ TH3, {w, j})
                for k in range(6):
                    if k not in (w, j):
                        out[idx[(w, j, k)]] += pm * p2[j] * p3[k]
    return out / out.sum()
