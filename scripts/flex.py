"""決裁者v2(柔軟型・記録だけ): 情報部と市場の確率を混ぜて、割安な2連単を自由に選ぶ

・2連単30通りそれぞれの確率を、情報部の予想(3連単の確率を3着で合計)と市場(オッズの逆数を合計1にそろえたもの)の
  対数確率を重みづけして足し、レース内で合計1にそろえて作る(重みは確定オッズの過去データでロジスティック回帰)
・混ぜた確率×オッズが EV 以上、オッズが ODDS_MAX 未満の目を全部買う(頭はいくつでも・1点 STAKE 円)
・2025年で学んで2026年で確かめ / 2026年で学んで2025年で確かめ、のどちらでも
  割安1.3以上・8〜20倍で111%・116%、1〜8倍で103%・115%(確定オッズ)。重みは両年まとめて学んだもの
・10/19から: 締切45秒前のオッズで判断し、見込みの確定オッズ(下がり方を割り引いたもの)で割安さを見る。
  頭の確率を1着専門(win_spec)で直す。割安1.3以上・20倍未満で113%→134%(2026年)、114%→134%(2025年)
"""
import math

W_P, W_Q = 0.608, 0.513   # 情報部・市場の対数確率の重み(2025/1/1〜2026/10/13の確定2連単オッズで学習)
EV = 1.3
EV_DRIFT = 1.15   # 見込みの確定オッズで判断する時の下限(確定オッズの確かめで 割安1.15以上は114%・114%、1.2以上は120%・121%)
ODDS_MAX = 20.0
STAKE = 1000   # 1点の金額
# 締切45秒前のオッズ→確定オッズの下がり方(割安さの帯ごとの倍率)。割安に見える目ほど最後に買われて下がる。
# 10/17〜18の記録(20倍未満の2連単約1,600目)で測った値。記録がたまったら測り直す
DRIFT2 = ((0.7, 1.16), (0.9, 1.02), (1.0, 0.95), (1.1, 0.91), (1.2, 0.85), (99, 0.83))
DRIFT3 = 0.89   # 3連単に切り替えた目
# 3連単全部の目: 本予想の確率×45秒前オッズ(割安さ)の帯ごとの倍率(3連単は2連単ほど下がらない)
DRIFT3_ALL = ((0.7, 1.10), (0.9, 1.04), (1.2, 1.02), (1.5, 1.00), (99, 0.97))


def drift2(edge):
    return next(r for hi, r in DRIFT2 if edge <= hi)


def expected_final(pred, o2, o3):
    """締切前のオッズを、見込みの確定オッズに直す(2連単は混ぜた確率の割安さ、3連単は本予想の割安さの帯ごとの倍率)。
    決裁者A(自信度型)が社員の買い目を作り直す時に使う"""
    from bet import PI
    waku = [b["waku"] for b in pred["boats"]]
    o2f = dict(o2)
    for i, j, o, s in blend2(pred, o2, None, False):
        c = (waku[i] - 1, waku[j] - 1)
        o2f[c] = round(o * drift2(s * o), 1)
    o3f = dict(o3)
    tri = pred.get("tri") or []
    for (i, j, k), ix in PI.items():
        c = (waku[i] - 1, waku[j] - 1, waku[k] - 1)
        if c in o3f and tri:
            e = tri[ix] * o3f[c]
            o3f[c] = round(o3f[c] * next(r for hi, r in DRIFT3_ALL if e <= hi), 1)
    return o2f, o3f


def blend2(pred, o2, live=None, win=True):
    """2連単30通りの混ぜた確率。[(1着のコース-1, 2着のコース-1, オッズ, 確率)]。作れなければ[]
    1着専門(win_spec)が使えれば、頭ごとの確率を1着専門の1着確率に合わせて直す(2着の並びは混ぜた確率のまま)"""
    from bet import PI
    tri = pred.get("tri")
    if not tri or not o2:
        return []
    waku = [b["waku"] for b in pred["boats"]]
    rows = []
    for i in range(6):
        for j in range(6):
            if i == j:
                continue
            o = o2.get((waku[i] - 1, waku[j] - 1))
            if not o:
                continue
            p = sum(tri[PI[(i, j, k)]] for k in range(6) if k not in (i, j))
            rows.append((i, j, o, p))
    if len(rows) < 20:
        return []
    inv = sum(1 / o for *_, o, _ in rows)
    sc = [math.exp(W_P * math.log(max(p, 1e-5)) + W_Q * math.log(max((1 / o) / inv, 1e-5))) for i, j, o, p in rows]
    tot = sum(sc)
    out = [(i, j, o, s / tot) for (i, j, o, _), s in zip(rows, sc)]
    w = None
    if win:
        try:
            import win_spec
            w = win_spec.probs(pred, o2, live)
        except Exception:
            w = None
    if w:
        s1 = [0.0] * 6
        for i, _, _, pr in out:
            s1[i] += pr
        out = [(i, j, o, pr * w[i] / s1[i]) for i, j, o, pr in out if s1[i] > 0]
    return out


def picks(pred, o2, live=None, win=True, o3=None, drift=False):
    """pred: 予想(コース順の boats と tri)、o2: {(1着の枠-1, 2着の枠-1): オッズ} → [{combo, units, odds, prob, ev, bet}]
    o3(3連単オッズ)を渡すと、選んだ2連単ごとに「3着専門の上位2艇の3連単に半分ずつ」の見込み払戻と2連単のオッズを比べ、
    高い方を買う(確定オッズの確かめで 2連単だけ113%・114% → 116%・116%、3連単を選ぶのは4〜5回に1回)
    drift=True なら、締切前のオッズを見込みの確定オッズ(DRIFT2・DRIFT3)に直してから割安さを判断する"""
    waku = [b["waku"] for b in pred["boats"]]
    out = []
    for i, j, o, pr in blend2(pred, o2, live, win):
        of = o * drift2(pr * o) if drift else o   # 見込みの確定オッズ
        if pr * of < (EV_DRIFT if drift else EV) or o >= ODDS_MAX:
            continue
        t2 = dict(combo=f"{waku[i]}-{waku[j]}", units=STAKE // 100, odds=o, odds_f=round(of, 1), prob=round(pr, 4),
                  ev=round(pr * of, 2), bet="2t")
        p3 = None
        if o3:
            try:
                import third_spec
                p3 = third_spec.probs(pred, i, j, o3, live)
            except Exception:
                p3 = None
        if p3:
            top = sorted(p3.items(), key=lambda x: -x[1])[:2]
            odds3 = [o3.get((waku[i] - 1, waku[j] - 1, waku[c] - 1)) for c, _ in top]
            k3 = DRIFT3 if drift else 1.0
            if all(odds3) and sum(q * x * k3 for (_, q), x in zip(top, odds3)) / 2 > of:
                out += [dict(combo=f"{waku[i]}-{waku[j]}-{waku[c]}", units=STAKE // 200, odds=x, odds_f=round(x * k3, 1),
                             prob=round(pr * q, 4), ev=round(pr * q * x * k3, 2), bet="3t") for (c, q), x in zip(top, odds3)]
                continue
        out.append(t2)
    return sorted(out, key=lambda t: -t["ev"])
