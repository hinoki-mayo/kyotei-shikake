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


def _feats(P, st, ab, tenji_z, motor, w, m, momentum=None, wind=0.0, wave=0.0, rain=0.0, prev=None):
    """各艇の特徴量(6,F)。並びは学習時(params.jsonのnames)と同じ。
    momentum/wind/wave/rainはround6研究で有意だった追加特徴(節間の勢い・天候×決まり手位置・
    実力の艇内順位)。momentumがNoneなら従来通り(27/29列)のまま返す(後方互換)"""
    h = P.sum(1)
    k = np.arange(6)
    rel = k - w
    kpc = []
    for mi in range(4):
        for c in (rel <= -2, rel == -1, rel == 1, rel >= 2):    # 遠い内/すぐ内/すぐ外/遠い外
            kpc.append(((m == mi) & c).astype(float))
    cols = [np.log(h + 1e-4), *kpc]
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
    if momentum is not None:
        mom_z = momentum / 3.0
        cols.append(mom_z - mom_z.mean())
        for c in kpc:
            cols.append(c * (wind / 5.0))
        for c in kpc:
            cols.append(c * (wave / 10.0))
        for c in kpc:
            cols.append(c * float(rain))
        rank = np.empty(6, dtype=int)
        rank[np.argsort(-ab, kind="stable")] = np.arange(1, 7)
        for r in range(2, 7):
            cols.append((rank == r).astype(float))
    return np.stack(cols, -1)


def _softmax(s, used):
    s = s.copy()
    s[list(used)] = -np.inf
    e = np.exp(s - s[np.isfinite(s)].max())
    return e / e.sum()


def trifecta_probs(P, st, ab, tenji_z, motor, momentum=None, wind=0.0, wave=0.0, rain=0.0):
    """コース順の入力から、PERMSの順に並べた3連単120通りの確率を返す。
    momentum(6艇)/wind/wave/rainを渡すと、round6で追加した特徴込みで計算する(渡さなければ従来通り)"""
    P = np.asarray(P, float)
    out = np.zeros(120)
    idx = {p: i for i, p in enumerate(PERMS)}
    for w in range(6):
        for m in range(4):
            pm = P[w, m]
            if pm <= 1e-9:
                continue
            p2 = _softmax(_feats(P, st, ab, tenji_z, motor, w, m, momentum, wind, wave, rain) @ TH2, {w})
            for j in range(6):
                if j == w:
                    continue
                p3 = _softmax(_feats(P, st, ab, tenji_z, motor, w, m, momentum, wind, wave, rain, prev=j) @ TH3, {w, j})
                for k in range(6):
                    if k not in (w, j):
                        out[idx[(w, j, k)]] += pm * p2[j] * p3[k]
    return out / out.sum()
