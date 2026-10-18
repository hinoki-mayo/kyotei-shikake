"""決裁者v2(柔軟型・記録だけ): 情報部と市場の確率を混ぜて、割安な2連単を自由に選ぶ

・2連単30通りそれぞれの確率を、情報部の予想(3連単の確率を3着で合計)と市場(オッズの逆数を合計1にそろえたもの)の
  対数確率を重みづけして足し、レース内で合計1にそろえて作る(重みは確定オッズの過去データでロジスティック回帰)
・混ぜた確率×オッズが EV 以上、オッズが ODDS_MAX 未満の目を全部買う(頭はいくつでも・1点 STAKE 円)
・2025年で学んで2026年で確かめ / 2026年で学んで2025年で確かめ、のどちらでも
  割安1.3以上・8〜20倍で111%・116%、1〜8倍で103%・115%(確定オッズ)。重みは両年まとめて学んだもの
"""
import math

W_P, W_Q = 0.608, 0.513   # 情報部・市場の対数確率の重み(2025/1/1〜2026/10/13の確定2連単オッズで学習)
EV = 1.3
ODDS_MAX = 20.0
STAKE = 1000   # 1点の金額


def picks(pred, o2):
    """pred: 予想(コース順の boats と tri)、o2: {(1着の枠-1, 2着の枠-1): オッズ} → [{combo, units, odds, prob, ev}]"""
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
    out = []
    for (i, j, o, _), s in zip(rows, sc):
        pr = s / tot
        if pr * o >= EV and o < ODDS_MAX:
            out.append(dict(combo=f"{waku[i]}-{waku[j]}", units=STAKE // 100, odds=o, prob=round(pr, 4), ev=round(pr * o, 2)))
    return sorted(out, key=lambda t: -t["ev"])
