"""記録だけの社員候補(採用はしない。v1・v2と並べて成績を記録する)

・説D「1-3/1-4」: インの1着確率(本予想)≥0.6、1-3か1-4(コース)、2連単8〜12倍、本予想の確率×オッズ≥1.3 の2連単。
  2026/6〜10月で条件を決め(事前登録)、2025年で108%・2026年2〜10月で105%
・3連単の熱い一点: v2の混ぜた2連単確率(割安0.9以上・50倍未満の組)×3着専門の3着確率×3連単オッズ ≥2.0、100倍未満。
  2025年で学んだ3着専門で2026年191%、2026年で学んで2025年194%(1日約3点)
・どちらも1点1,000円。締切2分前(確定)に記録したオッズで判断する
"""
import flex
from bet import PI

STAKE = 1000


def setsu_d(pred, o2):
    tri = pred.get("tri")
    if not tri or not o2:
        return []
    waku = [b["waku"] for b in pred["boats"]]
    p2 = {(i, j): sum(tri[PI[(i, j, k)]] for k in range(6) if k not in (i, j)) for i in range(6) for j in range(6) if i != j}
    ph = sum(p for (i, _), p in p2.items() if i == 0)
    if ph < 0.6:
        return []
    out = []
    for j in (2, 3):
        o = o2.get((waku[0] - 1, waku[j] - 1))
        if o and 8 <= o < 12 and p2[(0, j)] * o >= 1.3:
            out.append(dict(combo=f"{waku[0]}-{waku[j]}", units=STAKE // 100, odds=o, bet="2t"))
    return out


def hot3(pred, o2, o3, live=None):
    import third_spec
    if not o2 or not o3:
        return []
    waku = [b["waku"] for b in pred["boats"]]
    out = []
    for a, b, o, s in flex.blend2(pred, o2, live, win=False):   # 確かめた時と同じく、1着専門で直す前の混ぜた確率
        if s * o < 0.9 or o >= 50:
            continue
        p3 = third_spec.probs(pred, a, b, o3, live)
        if not p3:
            continue
        for c, q in p3.items():
            o_ = o3.get((waku[a] - 1, waku[b] - 1, waku[c] - 1))
            if o_ and o_ < 100 and s * q * o_ >= 2.0:
                out.append(dict(combo=f"{waku[a]}-{waku[b]}-{waku[c]}", units=STAKE // 100, odds=o_, bet="3t"))
    return out


OUTW_RATIO = 1.5   # 外の1着専門: 1着専門の1着確率÷市場の1着確率がこれ以上
OUTW_UNITS = 40    # 頭1艇につき4,000円(2着をオッズの逆数で配分=どれが来ても払戻がほぼ同じ)
SEC_TOP = 3        # 2着は2着専門の上位3点


def out_win(pred, o2, live=None, courses=(2, 3), ratio=OUTW_RATIO):
    """外の1着専門(10/19に見つけた): 3・4コースの艇で、1着専門の1着確率が市場の1.5倍以上の時、その艇を頭に単勝と同じ形で買う。
    1着専門を片方の年で学んでもう片方で確かめて、2025年151%・2026年159%(確定オッズ・1日約3レース・的中約10%)。
    2コースは同じ条件で85%・119%と不安定なので入れない"""
    import win_spec
    if not o2:
        return []
    w = win_spec.probs(pred, o2, live)
    if not w:
        return []
    waku = [b["waku"] for b in pred["boats"]]
    inv = {}
    for (a, _), o in o2.items():
        if o:
            inv[a] = inv.get(a, 0) + 1 / o
    tot = sum(inv.values())
    out = []
    for i in courses:
        a = waku[i] - 1
        if a not in inv or w[i] / (inv[a] / tot) < ratio:
            continue
        legs = [(j, o2.get((a, waku[j] - 1))) for j in range(6) if j != i]
        if any(not o for _, o in legs):
            continue
        try:   # 10/20から: 2着は2着専門の上位3点に絞る(過去2年で5点154%・135% → 3点160%・149%)
            import sec_spec
            p2 = sec_spec.probs(pred, i, o2, live)
        except Exception:
            p2 = None
        if p2:
            top = sorted(p2, key=lambda j: -p2[j])[:SEC_TOP]
            legs = [(j, o) for j, o in legs if j in top]
        legs = [(waku[j], o) for j, o in legs]
        s = sum(1 / o for _, o in legs)
        for wj, o in legs:
            u = round(OUTW_UNITS * (1 / o) / s)
            if u:
                out.append(dict(combo=f"{waku[i]}-{wj}", units=u, odds=o, bet="2t"))
    return out


INW_RATIO = 1.7   # インの1着専門: インの1着確率を1着専門が市場の1.7倍以上と見る時


def in_win(pred, o2, live=None):
    """インの1着専門(10/19に見つけた): 1着専門がインの1着確率を市場の1.7倍以上と見る時(市場がインを嫌っている時)、
    インを頭に単勝と同じ形で買う。年をまたいだ確かめ(確定オッズ)で2025年259%・2026年191%(1年に約180レース、単勝相当は中央5〜7倍)"""
    return out_win(pred, o2, live, courses=(0,), ratio=INW_RATIO)
