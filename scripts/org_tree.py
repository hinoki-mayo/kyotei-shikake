"""予想組織のシナリオの木と自信度

木: ①最終決裁 → ②シナリオ(イン逃げ/イン負け) → ③誰が勝つか → ④説(プラン) → ⑤絞り(印)
・各プランの買い目を「頭の艇」ごとに分けて「提案」にし、頭のコース(とインの級)で③の箱に入れる
・自信度＝その箱の提案の推定回収率。レースが少ない箱は一つ上の箱の自信度へ寄せる(親が無い一番上は控除率並みの75%へ)
・最終決裁者(v1): 同じ頭の艇の提案同士で一番自信度が高いものを上げ、自信度が100%以上なら全部採用(違う頭なら複数残る)
・自信度の表(data/org/confidence.json)は scripts/org_eval.py で、確定オッズの過去データから作る
"""
import json

import bet
from common import DATA

CONF_P = DATA / "org" / "confidence.json"
ORG_PLANS = tuple(bet.OPS_PLANS) + tuple(bet.SHADOW_PLANS) + ("pick2",)
PRIOR = 0.75   # 一番上(何も分からない時)の回収率の見込み＝控除率並み
SHRINK = 50    # 親へ寄せる強さ(レース数換算)。提案がこの数たまると自分の数字と親の数字が半々
STAKE = 4000   # 提案1回の金額。社員ごとの買い方の割合はそのままで、40口を整数で配り直して1回4,000円にそろえる
ADOPT = 1.05   # 決裁者が採用する自信度の下限。別期間の確かめで 95%: 107%・92%、105%: 129%(168件)・103%(302件)
               # (比の帯で細かくすると逆に悪化したので、今は比の帯は使っていない)

NODES = {
    "in": "イン逃げ(1着＝1コース)",
    "out": "イン負け(1着＝2〜6コース)",
    "in.B": "B級インが逃げる",
    "in.A": "A級インが逃げる",
    "out.c2": "2コースが勝つ",
    "out.c34": "3〜4コースが勝つ",
    "out.c56": "5〜6コースが勝つ",
}
TAGS = {"モーター上位×10〜20倍": "tagM", "インの市場35%未満×比1.7〜2.0": "tagQ", "4コース×風3m以上": "tagW"}
TAG_LABEL = {v: "★" + k for k, v in TAGS.items()}
for _i, (_lo, _hi, _lab) in enumerate(bet.GEN_BANDS):   # 一般職の印(比の帯×インの級)
    for _g in "AB":
        TAGS[f"比{_lab}×イン{_g}"] = f"g{_i + 1}{_g}"
        TAG_LABEL[f"g{_i + 1}{_g}"] = f"比{_lab}×イン{_g}級"
# 予想÷市場の比(頭の艇の 予想の1着確率÷市場の1着確率)の帯。説・印の箱の下に、帯ごとの箱を作って自信度を細かくする
RATIO_BANDS = [(0, 1.2, "r1"), (1.2, 1.7, "r2"), (1.7, 2.5, "r3"), (2.5, 1e9, "r4")]
RATIO_LABEL = {"r1": "比1.2倍未満", "r2": "比1.2〜1.7倍", "r3": "比1.7〜2.5倍", "r4": "比2.5倍以上"}


def band_of(ratio):
    if ratio is None or ratio != ratio:
        return None
    return next(b for lo, hi, b in RATIO_BANDS if lo <= ratio < hi)


def _bases(p):
    """提案が入る一番細かい箱(説の箱と印の箱)。比があれば、その下の比の帯の箱"""
    base = [p["leaf"]] + list(p["tags"])
    b = band_of(p.get("ratio"))
    return [f"{x}.{b}" for x in base] if b else base


def group_of(course, in_grade):
    if course == 1:
        return "in.B" if str(in_grade).startswith("B") else "in.A"
    return "out.c2" if course == 2 else ("out.c34" if course in (3, 4) else "out.c56")


def proposals(plans, pred):
    """プランの買い目を頭ごとの提案に分ける。[{leaf, tags, plan, head, course, bet, tickets, stake}]"""
    w2c = {b["waku"]: i + 1 for i, b in enumerate(pred["boats"])}
    gin = pred["boats"][0]["grade"]
    out = []
    for pk in ORG_PLANS:
        pl = plans.get(pk)
        if not pl or pl.get("skip"):
            continue
        by = {}
        for t in pl["tickets"]:
            by.setdefault(int(t["combo"].split("-")[0]), []).append(t)
        htags = {h["head"]: h.get("tags", []) for h in pl.get("heads", [])}
        for h, tks in by.items():
            c = w2c.get(h)
            if not c:
                continue
            leaf = f"{group_of(c, gin)}.{pk}"
            units = bet._alloc([t["units"] for t in tks], STAKE // 100)   # 40口を元の割合で整数に配り直す(0口の目は買わない)
            tks = [dict(t, units=u) for t, u in zip(tks, units) if u]
            out.append(dict(leaf=leaf, tags=[f"{leaf}.{TAGS[x]}" for x in htags.get(h, []) if x in TAGS],
                            plan=pk, head=h, course=c, bet=pl.get("bet", "3t"), tickets=tks, stake=STAKE))
    return out


def ancestors(node):
    """'out.c34.pickura.tagW' → ['out.c34.pickura.tagW', 'out.c34.pickura', 'out.c34', 'out']"""
    p = node.split(".")
    return [".".join(p[:i]) for i in range(len(p), 0, -1)]


def build_confidence(rows):
    """rows: [{node候補を含む提案の結果: leaf, tags, stake, ret}] → {node: dict(n, st, ret, roi, conf)}
    箱の成績は、その箱より下の提案すべての合計。自信度は上の箱から順に、親の自信度へ寄せて決める"""
    agg = {}
    for r in rows:
        nodes = set()
        for x in _bases(r):
            nodes.update(ancestors(x))
        for nd in nodes:
            a = agg.setdefault(nd, dict(n=0, st=0, ret=0, hit=0))
            a["n"] += 1
            a["st"] += r["stake"]
            a["ret"] += r["ret"]
            a["hit"] += int(r["ret"] > 0)
    conf = {}
    for nd in sorted(agg, key=lambda x: x.count(".")):
        a = agg[nd]
        par = ".".join(nd.split(".")[:-1])
        prior = conf[par]["conf"] if par in conf else PRIOR
        roi = a["ret"] / a["st"] if a["st"] else 0
        hr = a["hit"] / a["n"] if a["n"] else 0
        conf[nd] = dict(a, roi=round(roi, 4), conf=round((a["n"] * roi + SHRINK * prior) / (a["n"] + SHRINK), 4),
                        hit_rate=round(hr, 4), avg_mult=round(a["ret"] / a["hit"] / (a["st"] / a["n"]), 1) if a["hit"] else None)
    return conf


HIT_TYPES = ((0.25, "本命型", "🎯"), (0.08, "中穴型", "⚖️"), (0.0, "大穴型", "💣"))   # 過去の的中率で分ける


def hit_type(hit_rate):
    """当たり方のタイプ(本命型・中穴型・大穴型)。的中率が分からなければNone"""
    if hit_rate is None:
        return None
    return next((name, icon) for lo, name, icon in HIT_TYPES if hit_rate >= lo)


def load_confidence():
    try:
        return json.loads(CONF_P.read_text())["nodes"]
    except Exception:
        return {}


def conf_of(p, table):
    """提案の自信度。印があれば印の箱(一番細かい箱)、無ければ説の箱。表に無い箱は親をたどる"""
    def look(node):
        for a in ancestors(node):
            if a in table:
                return table[a]["conf"]
        return PRIOR
    bs = _bases(p)
    tags = bs[1:]
    return max(look(t) for t in tags) if tags else look(bs[0])


def decide(props, table, mode="head"):
    """最終決裁(v1)。同じ結果を取り合う提案(同じ頭の艇)同士だけ比べて一番自信度が高いものを上げ、
    上がった提案のうち自信度がADOPT以上のものは全部採用(違う頭なら複数残る)。mode="side"はイン側・負け側で1つずつ(比較用)"""
    best = {}
    for p in props:
        c = conf_of(p, table)
        k = (c, p.get("ratio") or 0)   # 自信度が同じなら、予想÷市場の比が大きい方
        g = p["head"] if mode == "head" else p["leaf"].split(".")[0]
        if c >= ADOPT and (g not in best or k > best[g][0]):
            best[g] = (k, p)
    return [dict(p, conf=k[0]) for k, p in best.values()]


def node_label(node):
    if node in NODES:
        return NODES[node]
    last = node.split(".")[-1]
    if last in RATIO_LABEL:
        return RATIO_LABEL[last]
    if last in TAG_LABEL:
        return TAG_LABEL[last]
    return bet.PLANS.get(last, last)
