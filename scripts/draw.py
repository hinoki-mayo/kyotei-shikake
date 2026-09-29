"""スリット隊形・1マーク隊形のSVGを作る

重なりチェック:
・ラベル同士、ラベルとボート、ラベルとターンマークが重なったら位置をずらす
・ずらしても重なるラベルは図から外す(説明は図の下の一覧に必ず出る)
・進路の矢印はターンマークから一定距離を空けた型だけを使う
"""
import math

BC = ["#FFFFFF", "#222222", "#D9453F", "#3A7FD5", "#E8A83A", "#4E9A3E"]
LC = ["#FFFFFF", "#C9C9C9", "#EF7A74", "#86B7F2", "#F4C774", "#86C977"]
TC = ["#222", "#fff", "#fff", "#fff", "#222", "#fff"]
FONT = "font-family=\"'Hiragino Sans','Noto Sans JP',sans-serif\""
RED, GREEN, GRAY, DARK = "#A32D2D", "#0F6E56", "#5F5E5A", "#444441"
DEFS = ('<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" '
        'orient="auto-start-reverse"><path d="M1 1L9 5L1 9z" fill="context-stroke" stroke="context-stroke"/>'
        '</marker></defs>')
HULL = "M-17,-8 L6,-8 Q15,-5 18,0 Q15,5 6,8 L-17,8 Z"
BUOY = (200, 128)

# 1マークの実際の隊形(広がり)を、コース×決まり手から連続的な位置として計算する。
# 角度は buoy を中心に「+40°=まだ手前(進入)」→「0°=マーク横」→「-90°=真上(回頭中)」
# →「-170°=回り切って直線へ(脱出)」の順に減っていく(実際のターンの向きと一致)。
ANGLE_APPROACH, ANGLE_EXIT = 40, -170
BASE_RADIUS = [28, 46, 64, 84, 104, 124]          # コース1〜6の基準半径(内をタイトに、外を広く)
RADIUS_ADJUST = {"まくり": -20, "まくり外": -20, "まくり差し": -14, "差し": -16, "隙間": -10}
COURSE_DELAY = [0, 10, 22, 36, 52, 70]             # 外のコースほど「マークまでまだ距離がある」分の遅れ
PROGRESS_CUT = {"まくり": -20, "まくり外": -20, "まくり差し": -15, "差し": -11, "隙間": -8,
                "叩かれ注意": 8, "流れて残す": 4}
LATE_PENALTY, BAD_PENALTY = 12, 16


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


def _turn_geometry(sc):
    """各艇の(半径, 角度)を「実際にどこにいそうか」から連続的に計算する。
    半径=マークからの距離(コース+仕掛けで内外が動く)、角度=回頭の進み具合。"""
    pressed, shu, mv, sub, smv = sc["pressed"], sc["shu"], sc["move"], sc["sub"], sc["sub_move"]
    roles = sc["roles"]
    radius, progress = {}, {}
    for k in range(6):
        role = roles.get(k)
        r = BASE_RADIUS[k] + RADIUS_ADJUST.get(role, 0)
        p = COURSE_DELAY[k] + PROGRESS_CUT.get(role, 0)
        if k in sc["bad"]:
            r += BAD_PENALTY * 0.6
            p += BAD_PENALTY
        if k in sc["late"] and role not in PROGRESS_CUT:
            r += LATE_PENALTY * 0.5
            p += LATE_PENALTY
        if k == 0:
            r = BASE_RADIUS[0] + (6 if pressed else 0)
            p = COURSE_DELAY[0] + (10 if pressed else -6)
        radius[k], progress[k] = r, p
    lo, hi = min(progress.values()), max(progress.values())
    span = max(hi - lo, 1e-6)
    angle = {}
    for k in range(6):
        t = (progress[k] - lo) / span   # 0=最も進んでいる, 1=最も遅れている
        angle[k] = ANGLE_EXIT + t * (ANGLE_APPROACH - ANGLE_EXIT)
    # 近すぎる艇を半径方向にずらして衝突を避ける
    order = sorted(range(6), key=lambda k: angle[k])
    for a, b in zip(order, order[1:]):
        da = angle[a] - angle[b]
        dr = radius[a] - radius[b]
        if abs(da) < 9 and abs(dr) < 22:
            radius[a] += 11
            radius[b] -= 11
    return radius, angle


def turn_svg(sc, waku):
    pressed, shu, mv = sc["pressed"], sc["shu"], sc["move"]
    radius, angle = _turn_geometry(sc)
    s = [f'<svg viewBox="0 0 380 304" width="100%" role="img" xmlns="http://www.w3.org/2000/svg">'
         f'<title>1マーク隊形</title>', DEFS, '<rect width="380" height="272" rx="10" fill="#1B4560"/>',
         f'<circle cx="{BUOY[0]}" cy="{BUOY[1]}" r="11" fill="#E8742E"/>'
         f'<circle cx="{BUOY[0]}" cy="{BUOY[1]}" r="5" fill="#FAC775"/>']
    paths, boats = [], []
    obs = [(BUOY[0] - 13, BUOY[1] - 13, BUOY[0] + 13, BUOY[1] + 13)]
    pos = {}
    for k in range(6):
        i = waku[k] - 1
        i2, r, a = waku[k] - 1, radius[k], angle[k]
        rad = math.radians(a)
        x = BUOY[0] + r * math.cos(rad)
        y = BUOY[1] + r * math.sin(rad)
        x = max(20, min(360, x))
        y = max(16, min(252, y))
        heading = a - 90
        main = k == shu
        # 軌道: 同じ半径の円弧を、少し手前の角度から現在地まで描く(実際に辿ってきた道筋)
        trail_deg = 42 if main else 30
        a0 = a + trail_deg
        rad0 = math.radians(a0)
        x0, y0 = BUOY[0] + r * math.cos(rad0), BUOY[1] + r * math.sin(rad0)
        large = 0
        sweep = 1 if a0 > a else 0
        w = 4 if main else 2.2
        op = "" if main else ' opacity="0.6"'
        paths.append(f'<path d="M{x0:.0f} {y0:.0f} A{r:.0f} {r:.0f} 0 {large} {sweep} {x:.0f} {y:.0f}" '
                     f'stroke="{LC[i]}" stroke-width="{w}" fill="none" stroke-linecap="round"{op} '
                     f'marker-end="url(#ah)"/>')
        boats.append(_boat(x, y, heading, i2, "#fff" if main else "#777", 1.5 if main else 0.5))
        pos[k] = (x, y, a)
        obs.append((x - 17, y - 17, x + 17, y + 17))
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
        x, y, a = pos[k]
        rad = math.radians(a)
        lx, ly = x + 30 * math.cos(rad), y + 30 * math.sin(rad)
        lab.add(lx, ly - 10, text, col, "#D3D1C7" if col == DARK else "#fff", right=math.cos(rad) < 0)
    legend = (f'<rect x="0" y="284" width="12" height="12" rx="2" fill="{RED}"/><text x="17" y="294" font-size="12" '
              f'fill="currentColor" {FONT}>主役・展開が向く</text>'
              f'<rect x="130" y="284" width="12" height="12" rx="2" fill="{GREEN}"/><text x="147" y="294" font-size="12" '
              f'fill="currentColor" {FONT}>内で残す</text>'
              f'<rect x="222" y="284" width="12" height="12" rx="2" fill="{DARK}"/><text x="239" y="294" font-size="12" '
              f'fill="currentColor" {FONT}>展開が向かない</text>')
    return "".join(s + paths + boats + lab.out) + legend + "</svg>"
