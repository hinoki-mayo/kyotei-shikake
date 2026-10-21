"""サイトの「予想」: 予算4,000円で、本線・抑え・穴に分けた3連単の買い目を作る

・確率は情報部とオッズを混ぜた3連単の確率(race_view)。オッズはその時点で取れたもの
・本線: 確率が一番高い目から、1番手の半分以上の確率がある目(最大3点)
・抑え: 本線の次に確率が高い目(20倍未満・最大4点)。本命と同じ頭は2点まで、残りは本命以外の頭の目(インばかりにしない)
・穴: 本命以外の頭で20倍以上、混ぜた確率×オッズが0.7以上の目を、確率が高い順に最大5点(同じ頭は2点まで)
・過去の確かめ(確定オッズ・2025年の7日おき7,185レース): 的中率44%・平均9点・回収率78%(市場並み)。
  本命以外の頭の目が平均5点入り、当たりの約3割は本命以外の頭(10/21に外の頭を増やす形に変更。前は的中48%・ほぼイン頭)
・本線の確率がとても高い(1番手35%以上、または本線の合計50%以上)レースは本線だけで厚く買う
・金額: どの目が当たっても払戻が予算以上(トリガミなし)になる最低額をまず置き、
  残りを 本線6:抑え2.5:穴1.5 の目安で配る。同じ段の中は当たった時の払戻がそろうように配る
・段の合計は 本線 > 抑え > 穴 にそろえる(そろわなければ一番確率の低い穴・抑えから外す)
"""
import math

BUDGET = 4000
UNIT = 100
HON_MAX, OSA_MAX, ANA_MAX = 3, 4, 5
HON_REL = 0.5        # 本線: 1番手の確率のこの割合以上
OSA_REL = 0.25       # 抑え: 1番手の確率のこの割合以上
ANA_ODDS = 20.0      # 穴: この倍率以上
OSA_FAV = 2          # 抑え: 本命と同じ頭の目はこの点数まで(インばかりにしない)
OSA_REL_OTHER = 0.15 # 抑え: 本命以外の頭の目は、1番手の確率のこの割合以上
ANA_PER_HEAD = 2     # 穴: 同じ頭の目はこの点数まで(いろいろな艇の頭を押さえる)
ANA_VALUE = 0.7      # 穴: 確率×オッズがこれ以上(平均は控除で約0.75。ひどく割高な目だけ外す)
ANA_PMIN = 0.004     # 穴: 確率がこれ以上
ONLY_TOP = 0.35      # 1番手がこの確率以上なら本線だけ
ONLY_SUM = 0.50      # 本線の合計がこの確率以上なら本線だけ
SHARE = {"本線": 0.60, "抑え": 0.25, "穴": 0.15}
TIERS = ("本線", "抑え", "穴")


def _pick(probs, odds):
    """probs: [(組, 確率)] / odds: {組: 倍}。段ごとの候補 {段: [(組, 確率, 倍)]}"""
    rows = sorted(((c, p, odds.get(c)) for c, p in probs if odds.get(c)), key=lambda x: -x[1])
    if not rows:
        return {}
    p1 = rows[0][1]
    hon = [r for r in rows[:HON_MAX] if r[1] >= HON_REL * p1]
    if p1 >= ONLY_TOP or sum(r[1] for r in hon) >= ONLY_SUM:
        return {"本線": hon}
    used = {r[0] for r in hon}
    fav = rows[0][0].split("-")[0]   # 本命の頭
    head = lambda r: r[0].split("-")[0]
    # 抑え: 本命の頭の目は OSA_FAV 点まで。残りは本命以外の頭の目から(1番手の OSA_REL_OTHER 倍以上)
    osa_f = [r for r in rows if r[0] not in used and head(r) == fav and r[1] >= OSA_REL * p1 and r[2] < ANA_ODDS][:OSA_FAV]
    osa_o = [r for r in rows if r[0] not in used and head(r) != fav and r[1] >= OSA_REL_OTHER * p1 and r[2] < ANA_ODDS][:OSA_MAX - len(osa_f)]
    osa = sorted(osa_f + osa_o, key=lambda x: -x[1])
    used |= {r[0] for r in osa}
    # 穴: 本命以外の頭だけ。ANA_ODDS 倍以上で割のいい目を、確率が高い順に(同じ頭は ANA_PER_HEAD 点まで)
    ana, per = [], {}
    for r in rows:
        if r[0] in used or head(r) == fav or r[2] < ANA_ODDS or r[1] < ANA_PMIN or r[1] * r[2] < ANA_VALUE:
            continue
        if per.get(head(r), 0) >= ANA_PER_HEAD:
            continue
        per[head(r)] = per.get(head(r), 0) + 1
        ana.append(r)
        if len(ana) >= ANA_MAX:
            break
    return {t: x for t, x in (("本線", hon), ("抑え", osa), ("穴", ana)) if x}


def _alloc(tiers, budget):
    """{段: [(組, 確率, 倍)]} → {組: 金額}。払えなければNone"""
    tk = [(t, c, p, o) for t in TIERS for c, p, o in tiers.get(t, [])]
    st = {c: UNIT * math.ceil(budget / o / UNIT) for _, c, _, o in tk}   # トリガミにならない最低額
    if sum(st.values()) > budget:
        return None
    w = {t: SHARE[t] for t in TIERS if tiers.get(t)}
    target = {t: budget * v / sum(w.values()) for t, v in w.items()}
    tot = lambda t: sum(st[c] for tt, c, _, _ in tk if tt == t)
    for _ in range((budget - sum(st.values())) // UNIT):
        t = max(w, key=lambda t: target[t] - tot(t))   # 目安から一番足りない段へ
        c = min((x for x in tk if x[0] == t), key=lambda x: st[x[1]] * x[3])[1]   # その段で払戻が一番少ない目へ
        st[c] += UNIT
    return st


def _ordered(st, tiers):
    s = [sum(st[c] for c, _, _ in tiers[t]) for t in TIERS if tiers.get(t)]
    return all(a > b for a, b in zip(s, s[1:]))


def make(probs, odds, budget=BUDGET):
    """予想を作る。[{tier, combo, p, odds, yen, pay}] (段・確率の順)。作れなければ []"""
    tiers = _pick(probs, odds)
    while tiers:
        st = _alloc(tiers, budget)
        if st is not None and _ordered(st, tiers):
            return [dict(tier=t, combo=c, p=p, odds=o, yen=st[c], pay=round(st[c] * o))
                    for t in TIERS for c, p, o in tiers.get(t, [])]
        # 払えない・段の大小がそろわない: 一番下の段の、一番確率の低い目を外す
        low = next(t for t in reversed(TIERS) if tiers.get(t))
        if low == "本線" and len(tiers["本線"]) == 1:
            return []
        tiers[low] = tiers[low][:-1]
        if not tiers[low]:
            del tiers[low]
    return []
