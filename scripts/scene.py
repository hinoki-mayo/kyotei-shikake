"""確率とスリット予想から「1マークの展開」を組み立てる

図・ラベル・コメントはすべてここで決めた役割から作るので、食い違いが起きない。
"""
import json
import pathlib

import numpy as np

PRM = json.loads((pathlib.Path(__file__).parent / "params.json").read_text())
BASE = np.array(PRM["base"])

M = ["逃げ", "まくり", "差し", "まくり差し"]
MOVE_TEXT = {"まくり": "スリットで内より出て、絞りに行く",
             "差し": "内でじっと差し場を待つ",
             "まくり差し": "外から内側の隙間を突く"}


def _consistent(move, k, st):
    """スリットの並びと矛盾する決まり手を直す(内に並ばれているのにまくり、など)"""
    if move == "まくり" and st[k - 1] - st[k] < 0.005:
        return "まくり差し", "内に並ばれ、まくりは難しくまくり差しへ"
    return move, None


def build_scene(P, st, fc):
    """P: 6x4の確率, st: コース順の予想ST, fc: F数"""
    nige = float(P[0, 0])
    ahead = [k for k in range(1, 6) if st[0] - st[k] >= 0.015]
    ahead_big = [k for k in range(1, 6) if st[0] - st[k] >= 0.03]
    pressed = nige < 0.45 or (bool(ahead_big) and nige < 0.6)

    Q = P.copy()
    Q[0] = 0
    Q[:, 0] = 0
    Q = Q * (Q / (BASE + 1e-6)) ** PRM["surprise"]   # 定番に寄りすぎないよう意外性を少し混ぜる
    order = sorted(((Q[k, m], k, m) for k in range(1, 6) for m in range(1, 4)), reverse=True)
    shu, mv = order[0][1], M[order[0][2]]
    mv, why = _consistent(mv, shu, st)
    sub, smv = None, None
    for _, k, m in order[1:]:
        if k != shu:
            sub, smv = k, M[m]
            break
    smv, _ = _consistent(smv, sub, st)
    if smv == mv and mv != "差し":
        smv = "まくり差し" if mv == "まくり" else "差し"
        if smv == "差し" and sub > 2:
            smv = "まくり差し"

    tags = {}
    for i in range(1, 5):
        if st[i] - min(st[i - 1], st[i + 1]) >= 0.03 and st[i] >= max(st[i - 1], st[i + 1]) - 0.005:
            tags[i] = "凹み"
    if st[3] <= st[2] - 0.02:
        tags[3] = "カド伸び"
    late = [k for k in range(6) if st[k] - st.min() >= 0.05]

    one_role = "先マイ" if not pressed else ("叩かれ注意" if mv == "まくり" else "流れて残す")
    roles = {0: one_role}
    roles[shu] = mv
    roles[sub] = smv

    head, ren, bad = [], [], []
    if not pressed:
        head = [0]
        ren = [shu, sub]
    else:
        head = [shu]
        ren = [sub]
        if mv == "まくり":
            bad += [k for k in range(0, shu) if k not in (sub,) and not (k == 1 and roles.get(1) == "差し")]
        else:
            ren.append(0)
    for k in range(6):
        if k not in roles and (tags.get(k) == "凹み" or k in late):
            bad.append(k)
    bad = [k for k in dict.fromkeys(bad) if k not in head and k not in ren]
    ren = [k for k in dict.fromkeys(ren) if k not in head]

    lines = {}
    lines[0] = (f"{shu + 1}コースの{mv}に攻められ、" + ("叩かれる形" if mv == "まくり" else "流れても残したい形") if pressed
                else ("スリットで並ばれず、先に回れる形" if not ahead else "やや並ばれるが、先マイは狙える形"))
    lines[shu] = why or MOVE_TEXT[mv]
    lines[sub] = {"まくり": "外から攻めに行く", "差し": "内でじっと差し場を待つ",
                  "まくり差し": "外の動き次第で隙間へ"}[smv]
    for k in range(1, 6):
        if k in lines:
            continue
        if pressed and mv == "まくり" and k < shu:
            lines[k] = f"{shu + 1}コースのまくりを受けて叩かれる形"
        elif tags.get(k) == "凹み":
            lines[k] = "スリットで凹み、展開待ち"
        elif k in late:
            lines[k] = "スリットで遅れ、届かない形"
        elif tags.get(k) == "カド伸び":
            lines[k] = "カドから伸びる並び"
    for k in range(6):
        if fc[k] >= 1 and k in lines:
            lines[k] += f"（F{fc[k]}持ち）"

    return dict(pressed=pressed, nige=round(nige, 3), shu=shu, move=mv, sub=sub, sub_move=smv,
                roles=roles, tags=tags, late=late, head=head, ren=ren, bad=bad, lines=lines,
                head_prob=[round(float(x), 3) for x in P.sum(1)])
