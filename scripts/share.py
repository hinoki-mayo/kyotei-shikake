"""X投稿用の素材(文と画像)を作る。サイト運営者だけが開く隠しページで使う

対象は「頭注目の艇が1着になった＝仕掛け成功」のレース。
理由は予想時点で持っていた材料(展示タイム・予想ST・モーター・展開の役割)だけから書く。
言い方は「仕掛け成功」で統一し、「的中」は使わない。
"""
import html
import unicodedata

from draw import BC, FONT, TC, turn_svg

CIRCLED = "①②③④⑤⑥"


def _rank(vals, k, low=True):
    """k番目の値が6艇中何位か(low=Trueなら小さいほど上位)"""
    v = vals[k]
    return 1 + sum(1 for x in vals if x is not None and (x < v if low else x > v))


def successes(pred, result):
    """1着になった頭注目の艇(コース順の番号)。なければNone"""
    if not pred or pred.get("version") != "final" or not result:
        return None
    for k in pred["scene"].get("head", []):
        if result["by_waku"].get(pred["boats"][k]["waku"]) == "01":
            return k
    return None


def reasons(pred, entry, k):
    """締切前の時点で、なぜこの艇を頭注目にしたか(強いものから最大3つ)"""
    sc, boats = pred["scene"], pred["boats"]
    out = []
    line = sc["lines"].get(str(k))
    if line:
        out.append(line.split("（")[0])
    if k != 0 and sc["nige"] < 0.5:
        out.append(f"{CIRCLED[boats[0]['waku'] - 1]}の逃げ切りは{sc['nige']:.0%}と低め")
    tenji = (entry or {}).get("tenji")
    if tenji and len(tenji) == 6:
        by_course = [tenji[b["waku"] - 1] for b in boats]
        r = _rank(by_course, k)
        if r <= 2:
            out.append(f"展示タイム{r}位（{by_course[k]:.2f}）")
    r = _rank(pred["st"], k)
    if r == 1:
        out.append("予想STが6艇トップ")
    motor = [b.get("motor_2r") for b in boats]
    if motor[k] is not None and _rank(motor, k, low=False) == 1:
        out.append(f"モーター2連率{motor[k]:.0f}%で6艇トップ")
    if k == 0 and not sc["pressed"]:
        out.append(f"逃げる確率{sc['nige']:.0%}")
    return out[:3]


def _xlen(s):
    """Xの文字数(全角は2、半角は1として数える。上限280)"""
    return sum(2 if unicodedata.east_asian_width(c) in "WFA" else 1 for c in s)


def post_text(venue, race, pred, result, entry, k):
    w = pred["boats"][k]["waku"]
    move = "逃げ" if k == 0 else (pred["scene"]["roles"].get(str(k)) or "仕掛け")
    head = f"【仕掛け成功】{venue}{race}R\n締切前に{CIRCLED[w - 1]}の{move}を予想 → 1着\n"
    tail = ""
    if result.get("combo3t") and result.get("payout3t"):
        tail += f"\n3連単 {result['combo3t']} {int(result['payout3t']):,}円"
    tail += f"\n#ボートレース{venue} #競艇"
    rs = reasons(pred, entry, k)
    while True:
        body = "".join(f"\n・{x}" for x in rs)
        text = head + ("\n📊 こう読んでいました" + body if rs else "") + tail
        if _xlen(text) <= 270 or not rs:
            return text
        rs = rs[:-1]


def _t(x, y, s, size=20, fill="#1f2328", weight=500, anchor="start"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" '
            f'{FONT}>{html.escape(s)}</text>')


def _chip(x, y, w, size=34):
    return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="6" fill="{BC[w - 1]}" stroke="#bbb"/>'
            + _t(x + size / 2, y + size * 0.72, str(w), size * 0.6, TC[w - 1], 700, "middle"))


def card_svg(venue, race, date_jp, pred, result, entry, k, site):
    """投稿に添える1枚(1200x675)。左に締切前の1マーク図、右に結果と理由"""
    waku = [b["waku"] for b in pred["boats"]]
    sc = dict(pred["scene"], roles={int(a): b for a, b in pred["scene"]["roles"].items()},
              tags={int(a): b for a, b in pred["scene"]["tags"].items()})
    try:
        fig = turn_svg(sc, waku).replace(
            '<svg viewBox="0 0 380 304" width="100%"', '<svg x="40" y="150" width="560" height="448" viewBox="0 0 380 304"', 1)
    except ValueError:
        fig = ""
    w = waku[k]
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675" color="#1f2328">',
         '<rect width="1200" height="675" fill="#f4f5f7"/>',
         '<rect width="1200" height="110" fill="#1B2A4A"/>',
         '<rect x="40" y="28" width="210" height="56" rx="28" fill="#E8742E"/>',
         _t(145, 66, "仕掛け成功！", 28, "#fff", 800, "middle"),
         _t(275, 68, f"{venue} {race}R", 36, "#fff", 800),
         _t(1160, 66, date_jp, 22, "#c9d1e0", 500, "end"),
         _t(40, 140, "締切前に出していた1マーク展開予想", 20, "#6b7079"), fig,
         '<rect x="630" y="140" width="530" height="490" rx="14" fill="#fff" stroke="#e3e5e9"/>',
         _t(660, 185, "結果", 20, "#6b7079")]
    order = sorted(result["by_waku"].items(), key=lambda kv: kv[1])[:3]
    for i, (bw, _) in enumerate(order):
        s.append(_chip(660 + i * 80, 200, int(bw), 48))
        if i < 2:
            s.append(_t(660 + i * 80 + 64, 232, "→", 20, "#6b7079", 700, "middle"))
    if result.get("payout3t"):
        s.append(_t(920, 236, f"{int(result['payout3t']):,}円", 30, "#A32D2D", 800))
    if result.get("kimarite"):
        s.append(_t(660, 285, f"決まり手：{result['kimarite']}", 20))
    s.append('<line x1="660" y1="310" x2="1130" y2="310" stroke="#e3e5e9"/>')
    s.append(_t(660, 350, "こう読んでいました", 20, "#6b7079"))
    s.append(_chip(660, 368, w, 40))
    s.append(_t(712, 397, "頭注目", 24, "#A32D2D", 800))
    y = 450
    for r in reasons(pred, entry, k):
        s.append(_t(660, y, f"・{r}", 22))
        y += 44
    s.append(_t(1160, 655, site.replace("https://", ""), 18, "#6b7079", 500, "end"))
    return "".join(s) + "</svg>"
