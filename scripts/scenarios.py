"""展開シナリオ集: 「誰がどの決まり手で勝つか」(本体モデル)ごとに、2・3着モデルで残る艇を出し、
文章・買い目の形・1マークの図の材料を作る

・本体モデルのP[勝者, 決まり手]の高い順に、起こる確率が一定以上のものを並べる
・2・3着はその勝ち方を条件にした2・3着モデル(place.py)の確率から。
  「4のまくりなら内は叩かれて5が続く」「3がまくりに行くと内が空いて4が差す」のような違いがここで出る
・決まり手は4種類(逃げ・まくり・差し・まくり差し)しか区別できないので、文章はスリットの並びと決まり手から組む
"""
import numpy as np

import place

M = ["逃げ", "まくり", "差し", "まくり差し"]
MIN_PROB = 0.04   # これ未満の起こる確率のシナリオは出さない
MAX_N = 6


def _cond(P, st, pin, w, mv):
    """勝者w・決まり手mvのときの、各艇の2着確率と3着確率"""
    args = (P, st, pin["ab"], pin["tenji_z"], pin["motor"])
    p2 = place._softmax(place._feats(*args, w, mv) @ place.TH2, {w})
    p3 = np.zeros(6)
    for j in range(6):
        if j != w:
            p3 += p2[j] * place._softmax(place._feats(*args, w, mv, j) @ place.TH3, {w, j})
    return p2, p3


def _story(P, w, mv, s2, W):
    """シナリオの文章(枠番で書く)"""
    if mv == 0:
        att = max(range(1, 6), key=lambda k: P[k, 1] + P[k, 3])
        return [f"{W(0)}がスリットを決めて先マイ、そのまま逃げ切り",
                f"{W(att)}の攻めは届かず、2着は{'・'.join(W(k) for k in s2)}の争い"]
    if mv == 1:
        inner = [W(k) for k in range(1, w)]
        out = [f"{W(w)}がスリットで内より出て、そのまままくり",
               f"{W(0)}は抵抗するも流れる" + (f"、{'・'.join(inner)}は叩かれる" if inner else "")]
        if w + 1 < 6 and w + 1 in s2:
            out.append(f"{W(w + 1)}が{W(w)}の後ろについて続く")
        return out
    if mv == 2:
        return [f"{W(0)}が先マイを狙うがターンが膨らみ、{W(w)}が内側を差して先頭へ",
                f"{W(0)}は流れても2着に残す形" if s2 and s2[0] == 0 else f"{W(0)}は流れて後退"]
    inner = [k for k in range(1, w)]
    atk = max(inner, key=lambda k: P[k, 1]) if inner else None
    if atk is None:
        return [f"{W(0)}のターンが流れたところを、{W(w)}がまくり差しで先頭へ"]
    out = [f"{W(atk)}がまくりに行き、{W(0)}との間が開く", f"その間を{W(w)}が割って先頭へ"]
    if atk in s2:
        out.append(f"攻めた{W(atk)}も2着に残る形")
    return out


def _scene(P, w, mv, s2, s3):
    """1マークの図(draw.turn_svg)に渡す材料。コースは0始まり"""
    rest = [k for k in s2 if k not in (0, w)] + [k for k in s3 if k not in (0, w)]
    rest = list(dict.fromkeys(rest)) or [k for k in range(1, 6) if k != w]
    if w == 0:
        shu, sub = rest[0], (rest[1] if len(rest) > 1 else next(k for k in range(1, 6) if k != rest[0]))
        mv_shu = M[1 + int(np.argmax(P[shu, 1:]))]
        mv_sub = M[1 + int(np.argmax(P[sub, 1:]))]
        roles = {0: "逃げ", shu: mv_shu, sub: mv_sub}
    else:
        shu, sub = w, rest[0]
        if mv == 3:   # まくり差しは「内でまくりに行った艇」を2番手として描く(文章と合わせる)
            inner = [k for k in range(1, w)]
            if inner:
                sub = max(inner, key=lambda k: P[k, 1])
        mv_shu = M[mv]
        mv_sub = ("まくり" if mv == 3 and sub < w else
                  "続く" if (mv == 1 and sub == w + 1) else M[1 + int(np.argmax(P[sub, 1:]))])
        if mv_sub == "続く":
            mv_sub = "まくり差し"   # 図の型としては外から続く形で描く
        one = {1: "叩かれ", 2: "流れる", 3: "膨らむ"}[mv]
        roles = {0: one, shu: mv_shu, sub: mv_sub}
    if mv_sub == mv_shu and mv_shu != "差し" and not (mv == 3 and sub < w):
        mv_sub = "まくり差し" if mv_shu == "まくり" else "差し"
        roles[sub] = mv_sub
    keep = {w, *s2, *s3}
    bad = [k for k in range(6) if k not in keep]
    return dict(pressed=w != 0, shu=int(shu), move=mv_shu, sub=int(sub), sub_move=mv_sub,
                roles={str(k): v for k, v in roles.items()}, tags={}, head=[int(w)],
                ren=[int(k) for k in s2], bad=[int(k) for k in bad])


def build(P, st, pin, waku):
    """P: 6x4, st: 予想ST, pin: 2・3着モデルの入力, waku: コース->枠番。JSONにできる形で返す"""
    P = np.asarray(P, float)
    W = lambda c: str(waku[c])
    cands = sorted(((P[w, m], w, m) for w in range(6) for m in range(4) if P[w, m] > 0), reverse=True)
    out = []
    for pr, w, mv in [c for c in cands if c[0] >= MIN_PROB][:MAX_N]:
        p2, p3 = _cond(P, st, pin, w, mv)
        s2 = [int(k) for k in np.argsort(-p2) if k != w][:2]
        s3 = [int(k) for k in np.argsort(-p3) if k != w][:3]
        out.append(dict(w=int(w), m=M[mv], prob=round(float(pr), 3), lines=_story(P, w, mv, s2, W),
                        combo=f"{W(w)}-{''.join(W(k) for k in s2)}-{''.join(W(k) for k in s3)}",
                        scene=_scene(P, w, mv, s2, s3)))
    heads = [dict(w=k, m=M[int(np.argmax(P[k]))], prob=round(float(P[k].sum()), 3)) for k in range(6)]
    return dict(list=out, heads=heads)
