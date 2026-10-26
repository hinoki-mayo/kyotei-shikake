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


def win_ratio(pred, o2, live=None):
    """コース順6艇の「1着専門の1着確率÷市場の1着確率」。作れなければNone"""
    import win_spec
    w = win_spec.probs(pred, o2, live) if o2 else None
    if not w:
        return None
    waku = [b["waku"] for b in pred["boats"]]
    inv = {}
    for (a, _), o in o2.items():
        if o:
            inv[a] = inv.get(a, 0) + 1 / o
    tot = sum(inv.values())
    return [w[i] / (inv.get(waku[i] - 1, 0) / tot) if inv.get(waku[i] - 1) else 0 for i in range(6)]


INSEC_EV = 1.1            # インの2着専門: 1着専門のイン1着確率×2着専門の2着確率×見込みの確定オッズ がこれ以上(確かめで1.1〜1.2も110%・129%)
INSEC_ODDS = (3.0, 15.0)  # 見込みの確定オッズの範囲


def in_sec(pred, o2, o3=None, live=None):
    """インの2着専門(本命型・10/19に見つけた): インが頭の2連単1-Xを、1着専門×2着専門の確率で見て、
    見込みの回収が1.1以上・見込みの確定オッズ3〜15倍の目を1点1,000円。
    年をまたいだ確かめ(確定オッズ): 3〜8倍 157%・138%(的中21〜25%)、8〜15倍 132%・117%"""
    import sec_spec
    import win_spec
    if not o2:
        return []
    w = win_spec.probs(pred, o2, live)
    p2 = sec_spec.probs(pred, 0, o2, live)
    if not w or not p2:
        return []
    o2f, _ = flex.expected_final(pred, o2, o3 or {})
    waku = [b["waku"] for b in pred["boats"]]
    out = []
    for j, q in p2.items():
        c = (waku[0] - 1, waku[j] - 1)
        of = o2f.get(c)
        if of and INSEC_ODDS[0] <= of < INSEC_ODDS[1] and w[0] * q * of >= INSEC_EV:
            out.append(dict(combo=f"{waku[0]}-{waku[j]}", units=STAKE // 100, odds=o2.get(c), odds_f=of, bet="2t"))
    return out


# 有力インターン生 E2・E3・E2の3連単版(10/21に見つけた・記録だけ・1点1,000円・締切45秒前のオッズで判断)
# 見立て: 情報部が45秒前の市場より高く見る目ほど、締切直前にお金が入って下がる(=後から市場が追いかけてくる)。
# 1号艇頭の目で、情報部÷45秒前の市場 ≥1.3 かつ 45秒前のオッズ3〜40倍 = E。
#   E2 = E かつ 1着専門÷市場(1号艇) ≥1.3 / E3 = E かつ 45秒前6倍まで / E2の3連単版 = 3連単で同じ条件・40倍まで
# 10/17〜20で探した形(E2: 当たり÷確定の見込み1.83倍・回収率115%)。10/21からが答え合わせ
LATE_R, LATE_WR, LATE_ODDS, LATE_E3_MAX = 1.3, 1.3, (3.0, 40.0), 6.0


def late_in(pred, o2, o3, live=None):
    """{"lateE2": 買い目, "lateE3": 買い目, "lateE23": 買い目}"""
    out = {"lateE2": [], "lateE3": [], "lateE23": []}
    tri = pred.get("tri")
    if not tri or not o2:
        return out
    waku = [b["waku"] for b in pred["boats"]]
    i1 = waku.index(1) if 1 in waku else None
    if i1 is None:
        return out
    inv2 = sum(1 / v for v in o2.values() if v)
    wr = win_ratio(pred, o2, live)
    wr1 = wr[i1] if wr else 0
    p2 = {}
    for (i, j, k), ix in PI.items():
        p2[(i, j)] = p2.get((i, j), 0) + tri[ix]
    for j in range(6):
        if j == i1:
            continue
        o = o2.get((0, waku[j] - 1))
        if not o or not (LATE_ODDS[0] <= o <= LATE_ODDS[1]):
            continue
        if p2[(i1, j)] / ((1 / o) / inv2) < LATE_R:
            continue
        t = dict(combo=f"1-{waku[j]}", units=STAKE // 100, odds=o, bet="2t")
        if wr1 >= LATE_WR:
            out["lateE2"].append(t)
        if o <= LATE_E3_MAX:
            out["lateE3"].append(t)
    if o3 and wr1 >= LATE_WR:
        inv3 = sum(1 / v for v in o3.values() if v)
        for (i, j, k), ix in PI.items():
            if i != i1:
                continue
            o = o3.get((0, waku[j] - 1, waku[k] - 1))
            if o and LATE_ODDS[0] <= o <= LATE_ODDS[1] and tri[ix] / ((1 / o) / inv3) >= LATE_R:
                out["lateE23"].append(dict(combo=f"1-{waku[j]}-{waku[k]}", units=STAKE // 100, odds=o, bet="3t"))
    return out


SANWARI_P, SANWARI_ODDS, SANWARI_YEN = 0.30, (3.3, 5.0), 1000


def sanwari(pred, o2, o3):
    """3割4倍(10/25から記録だけ・締切2分前のオッズ): 本命(混ぜた3連単確率の1番手)の頭の2連単を、確率の高い順に
    見込み30%に届くまで足し、どれが来ても払戻がそろう配分で1,000円。そろえた払戻が3.3〜5倍の時だけ。ランクC(混戦)は買わない。
    過去(確定オッズ・モデルは別の年): 2025年869R 的中32% 回収111%、2026年2〜10月462R 32% 113%"""
    import race_view
    if not o2 or not o3 or not pred.get("tri"):
        return []
    s3 = race_view._blend3(pred, o3)
    if not s3:
        return []
    waku = [b["waku"] for b in pred["boats"]]
    probs = sorted(((f"{waku[i]}-{waku[j]}-{waku[k]}", p) for i, j, k, p in s3), key=lambda x: -x[1])
    if sum(p for _, p in probs[:5]) < 0.3:   # ランクC
        return []
    fh = probs[0][0][0]
    p2 = {}
    for c, p in probs:
        p2[c[:3]] = p2.get(c[:3], 0) + p
    o2d = {f"{a + 1}-{b + 1}": x for (a, b), x in o2.items() if x}
    cand = sorted(((c, p, o2d[c]) for c, p in p2.items() if c[0] == fh and o2d.get(c)), key=lambda x: -x[1])
    pick, ps = [], 0.0
    for x in cand:
        pick.append(x)
        ps += x[1]
        if ps >= SANWARI_P:
            break
    if ps < SANWARI_P:
        return []
    inv = sum(1 / o for _, _, o in pick)
    if not (SANWARI_ODDS[0] <= 1 / inv <= SANWARI_ODDS[1]):
        return []
    return [dict(combo=c, units=max(1, round(SANWARI_YEN / 100 * (1 / o) / inv)), odds=o, bet="2t") for c, _, o in pick]


E45_RATIO, E45_ODDS, E45_UNITS = 1.3, (5.0, 20.0), 10


def e45(pred, o3):
    """45秒前の先回り(10/27から記録だけ・締切45秒前のオッズ): 情報部の3連単確率(混ぜる前)が、45秒前の市場の確率
    (1/オッズを全120通りで割り戻したもの)の1.3倍以上で、45秒前のオッズが5倍より上・20倍以下の目を、1点1,000円ずつ全部。
    見つけた9日分(10/17〜25・約1,300R)で、45秒前で選ぶと当たり106回(確定オッズの見込み78回)・回収94%、
    確定オッズで選び直すと63回(58回)・73%。条件はこの日に決めて変えない。答え合わせは10/27から"""
    import bet
    if not o3 or not pred.get("tri"):
        return []
    waku = [b["waku"] for b in pred["boats"]]
    inv = sum(1 / v for v in o3.values() if v and v > 0)
    if inv <= 0:
        return []
    out = []
    for n, (i, j, k) in enumerate(bet.PERMS):
        o = o3.get((waku[i] - 1, waku[j] - 1, waku[k] - 1))
        if not o or o <= 0:
            continue
        if E45_ODDS[0] < o <= E45_ODDS[1] and pred["tri"][n] >= E45_RATIO * (1 / o) / inv:
            out.append(dict(combo=f"{waku[i]}-{waku[j]}-{waku[k]}", units=E45_UNITS, odds=o))
    return out
