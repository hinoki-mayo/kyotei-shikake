"""スリット隊形・1マーク隊形のSVGを作る

重なりチェック:
・ラベル同士、ラベルとボート、ラベルとターンマークが重なったら位置をずらす
・ずらしても重なるラベルは図から外す(説明は図の下の一覧に必ず出る)
・進路の矢印はターンマークから一定距離を空けた型だけを使う
"""
BC = ["#FFFFFF", "#222222", "#D9453F", "#3A7FD5", "#E8A83A", "#4E9A3E"]
LC = ["#FFFFFF", "#C9C9C9", "#EF7A74", "#86B7F2", "#F4C774", "#86C977"]
TC = ["#222", "#fff", "#fff", "#fff", "#222", "#fff"]
FONT = "font-family=\"'Hiragino Sans','Noto Sans JP',sans-serif\""
RED, GREEN, GRAY, DARK = "#A32D2D", "#0F6E56", "#5F5E5A", "#444441"
DEFS = ('<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" '
        'orient="auto-start-reverse"><path d="M1 1L9 5L1 9z" fill="context-stroke" stroke="context-stroke"/>'
        '</marker></defs>')
HULL = "M-17,-8 L6,-8 Q15,-5 18,0 Q15,5 6,8 L-17,8 Z"
BUOY = (200, 120)

# 1マーク隊形の型(座標は手で検証済み。矢印はすべてマークから20px以上離れる)
SLOTS = {
    "one_hold": dict(xy=(246, 120), a=-90, path="M246 102 A46 46 0 0 0 164 94 L130 102", w=3.5, dash=False,
                     label=(60, 40)),
    "one_press": dict(xy=(252, 122), a=-95, path="M252 104 C256 86 252 72 240 62", w=2.5, dash=True,
                      label=(256, 40)),
    "差し": dict(xy=(216, 178), a=-50, path="M222 164 C230 150 228 134 224 122 C220 106 208 98 188 98",
               label=("right", 192, 168)),
    "まくり": dict(xy=(296, 152), a=-75, path="M300 136 C292 100 262 84 226 88 L204 94", label=(304, 96)),
    "まくり外": dict(xy=(296, 152), a=-75, path="M300 136 C302 100 284 72 254 54 L232 48", label=(304, 96)),
    "まくり差し": dict(xy=(302, 176), a=-88, path="M302 158 C300 122 266 88 236 72 L212 62", label=(196, 198)),
    "続く": dict(xy=(342, 204), a=-80, path="M344 188 C342 160 318 134 282 118", label=(250, 240)),
    "隙間": dict(xy=(250, 184), a=-55, path="M258 172 C262 162 264 154 272 146", label=(190, 206)),
}
TRAIL = [dict(xy=(150, 202), label=(126, 226)), dict(xy=(98, 224), label=(40, 248)),
         dict(xy=(56, 190), label=(10, 148)), dict(xy=(190, 236), label=(214, 244))]


def _boat(x, y, a, i, stroke="#777", sw=0.5):
    return (f'<g transform="translate({x} {y}) rotate({a})"><path d="{HULL}" fill="{BC[i]}" stroke="{stroke}" '
            f'stroke-width="{sw}"/></g><text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="central" '
            f'font-size="14" font-weight="500" fill="{TC[i]}" {FONT}>{i + 1}</text>')


def _tw(t):
    return sum(7 if c.isascii() else 12 for c in t) + 14


def _overlap(a, b, pad=2):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


class Labeler:
    def __init__(self, obstacles, ymax):
        self.obs = list(obstacles)
        self.out = []
        self.ymax = ymax

    def add(self, x, y, text, col, fg="#fff", right=False):
        w = _tw(text)
        if right:
            x = x - w
        cands = [(dx, dy) for dy in (0, 24, -24, 48, -48) for dx in (0, -40, 40, -80, 80)]
        cands.sort(key=lambda c: abs(c[0]) + abs(c[1]))   # 近い場所から試す
        for dx, dy in cands:
            bx = max(4, min(376 - w, x + dx))
            box = (bx, y + dy, bx + w, y + dy + 20)
            if box[1] < 2 or box[3] > self.ymax:
                continue
            if not any(_overlap(box, o) for o in self.obs):
                self.obs.append(box)
                bx, by = box[0], box[1]
                self.out.append(f'<rect x="{bx}" y="{by}" width="{w}" height="20" rx="4" fill="{col}"/>'
                                f'<text x="{bx + w / 2}" y="{by + 10}" text-anchor="middle" dominant-baseline="central" '
                                f'font-size="12" fill="{fg}" {FONT}>{text}</text>')
                return True
        return False


def slit_svg(st, waku, tags, late):
    s = [f'<svg viewBox="0 0 380 250" width="100%" role="img" xmlns="http://www.w3.org/2000/svg">'
         f'<title>スリット隊形</title>', '<rect width="380" height="250" rx="10" fill="#1F4A63"/>',
         '<line x1="250" y1="14" x2="250" y2="222" stroke="#9FC3D8" stroke-dasharray="4 4"/>',
         f'<text x="250" y="240" text-anchor="middle" font-size="12" fill="#9FC3D8" {FONT}>スリット</text>']
    obs = []
    boats = []
    for k in range(6):
        y = 30 + k * 36
        x = max(90, min(340, 250 + (0.15 - st[k]) * 700))
        i = waku[k] - 1
        s.append(f'<line x1="20" y1="{y}" x2="{x - 24:.0f}" y2="{y}" stroke="#2E6180" stroke-width="3"/>')
        boats.append(f'<polygon points="{x - 21:.0f},{y - 10} {x - 1:.0f},{y - 10} {x + 8:.0f},{y} {x - 1:.0f},{y + 10} '
                     f'{x - 21:.0f},{y + 10}" fill="{BC[i]}" stroke="#888" stroke-width="0.5"/>'
                     f'<text x="{x - 8:.0f}" y="{y}" text-anchor="middle" dominant-baseline="central" font-size="14" '
                     f'font-weight="500" fill="{TC[i]}" {FONT}>{i + 1}</text>')
        obs.append((x - 22, y - 11, x + 9, y + 11))
    lab = Labeler(obs, 222)
    for k in range(6):
        y = 30 + k * 36
        x = max(90, min(340, 250 + (0.15 - st[k]) * 700))
        t = tags.get(k) or ("遅れ" if k in late else None)
        if t:
            col = "#185FA5" if t == "カド伸び" else RED
            lab.add(x - 30, y - 10, t, col, right=True)
    return "".join(s + boats + lab.out) + "</svg>"


def turn_svg(sc, waku):
    pressed, shu, mv, sub, smv = sc["pressed"], sc["shu"], sc["move"], sc["sub"], sc["sub_move"]
    place = {}
    place[0] = "one_press" if pressed else "one_hold"
    used = set()
    # 同時に使うとボートが近すぎる型の組み合わせ
    clash = {("まくり", "まくり差し"), ("まくり外", "まくり差し"), ("差し", "隙間")}

    def ok(key):
        return key not in used and not any((u, key) in clash or (key, u) in clash for u in used)

    def put(k, move):
        key = "まくり外" if (move == "まくり" and not pressed) else move
        if key == "差し" and k >= 3:
            key = "隙間"   # 4コースより外の差しは、内の艇の間に割って入る形で描く
        for cand in (key, "続く", "隙間"):
            if ok(cand):
                used.add(cand)
                place[k] = cand
                return

    for k, move in sorted([(shu, mv), (sub, smv)]):   # 内側の艇から配置する
        put(k, move)
    s = [f'<svg viewBox="0 0 380 304" width="100%" role="img" xmlns="http://www.w3.org/2000/svg">'
         f'<title>1マーク隊形</title>', DEFS, '<rect width="380" height="272" rx="10" fill="#1B4560"/>',
         '<path d="M20 154 C140 154 224 156 246 138" stroke="#fff" stroke-width="10" fill="none" opacity="0.12" '
         'stroke-linecap="round"/>',
         f'<text x="24" y="140" font-size="12" fill="#9FC3D8" {FONT}>1の引き波</text>',
         f'<circle cx="{BUOY[0]}" cy="{BUOY[1]}" r="11" fill="#E8742E"/>'
         f'<circle cx="{BUOY[0]}" cy="{BUOY[1]}" r="5" fill="#FAC775"/>']
    paths, boats = [], []
    obs = [(BUOY[0] - 13, BUOY[1] - 13, BUOY[0] + 13, BUOY[1] + 13), (20, 128, 84, 144)]
    trail_i = 0
    pos = {}
    for k in range(6):
        i = waku[k] - 1
        if k in place:
            sl = SLOTS[place[k]]
            x, y = sl["xy"]
            main = k == shu
            w = sl.get("w", 5 if main else 3)
            dash = sl.get("dash", not main)
            da = 'stroke-dasharray="7 5"' if dash else ""
            paths.append(f'<path d="{sl["path"]}" stroke="{LC[i]}" stroke-width="{w}" fill="none" stroke-linecap="round" '
                         f'{da} marker-end="url(#ah)"/>')
            boats.append(_boat(x, y, sl["a"], i, "#fff" if main else "#777", 1.5 if main else 0.5))
            pos[k] = sl
        else:
            t = TRAIL[min(trail_i, len(TRAIL) - 1)]
            trail_i += 1
            x, y = t["xy"]
            boats.append(f'<g opacity="0.55">{_boat(x, y, -8, i)}</g>')
            pos[k] = t
        obs.append((x - 19, y - 19, x + 19, y + 19))
    centers = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in obs[2:]]
    for a in range(len(centers)):
        for b in range(a + 1, len(centers)):
            dx, dy = centers[a][0] - centers[b][0], centers[a][1] - centers[b][1]
            if dx * dx + dy * dy < 30 * 30:
                raise ValueError(f"ボートが重なっています: {centers[a]} {centers[b]}")
    lab = Labeler(obs, 268)
    for k in range(6):
        i = waku[k] - 1
        role = sc["roles"].get(k)
        if k in sc["head"]:
            col = RED
        elif k in sc["ren"]:
            col = GREEN if role == "差し" or k == 0 else RED
        elif k in sc["bad"]:
            col = DARK
        else:
            col = GRAY
        text = None
        if role:
            text = f"{i + 1} {role}"
        elif k in sc["bad"]:
            if pressed and mv == "まくり" and k < shu:
                text = f"{i + 1} 叩かれ"
            else:
                text = f"{i + 1} {'凹み' if sc['tags'].get(k) == '凹み' else '届かない'}"
        if not text:
            continue
        L = pos[k]["label"]
        if L[0] == "right":
            lab.add(L[1], L[2], text, col, right=True)
        else:
            lab.add(L[0], L[1], text, col, "#D3D1C7" if col == DARK else "#fff")
    legend = (f'<rect x="0" y="284" width="12" height="12" rx="2" fill="{RED}"/><text x="17" y="294" font-size="12" '
              f'fill="currentColor" {FONT}>主役・展開が向く</text>'
              f'<rect x="130" y="284" width="12" height="12" rx="2" fill="{GREEN}"/><text x="147" y="294" font-size="12" '
              f'fill="currentColor" {FONT}>内で残す</text>'
              f'<rect x="222" y="284" width="12" height="12" rx="2" fill="{DARK}"/><text x="239" y="294" font-size="12" '
              f'fill="currentColor" {FONT}>展開が向かない</text>')
    return "".join(s + paths + boats + lab.out) + legend + "</svg>"
