"""サイトの「当てる予想」: 情報部と市場の確率を混ぜて、艇ごとの1着・2着・3着の確率と、普段の力との比べ(熱い/冷たい)を出す

・2連単は flex.blend2(情報部と市場を混ぜた確率)。1着・2着の確率はここから出す
・3連単も同じやり方で混ぜる(過去データでは市場の重みが9割近い)。3着の確率はここから出す
・オッズがまだ無い時(展示前など)は情報部の予想だけで出す
・普段の力＝その選手のそのコースでの過去の1着率・2着以内率(実績予想くん2号の月初の累積)を、
  走った回数が少ないほどコースの平均へ寄せたもの。今日の確率がそれより大きく上なら「熱い」、下なら「冷たい」
・確定オッズ(2025/1〜2026/10)で、混ぜた予想の2連単1点目の的中は23.8〜24.3%(情報部だけ23.0〜23.3%、人気順23.5〜23.9%)
"""
import json

import bet
import flex
from common import DATA

W3_P, W3_Q = 0.186, 0.906   # 3連単の混ぜ方(2025年・2026年それぞれで学んで、もう片方で確かめた値の平均)
COURSE_BASE = {1: (0.549, 0.722), 2: (0.134, 0.385), 3: (0.129, 0.346), 4: (0.106, 0.277), 5: (0.062, 0.189), 6: (0.020, 0.082)}
K = 15   # 選手の記録をコースの平均へ寄せる強さ(走った回数換算)


def load_odds(date):
    """展示反映の更新が締切前に取ったオッズ {場-R: {t, o2:{(枠,枠):倍}, o3:{(枠,枠,枠):倍}}}"""
    p = DATA / "odds_live" / f"{date}.json"
    if not p.exists():
        return {}
    out = {}
    for k, v in json.loads(p.read_text()).items():
        out[k] = dict(t=v.get("t", ""), o2={c: x for c, x in zip(bet.ODDS2_ORDER, v.get("o2") or []) if x},
                      o3={c: x for c, x in zip(bet.ODDS_ORDER, v.get("o3") or []) if x})
    return out


def fetch_live(date, preds, now, workers=6):
    """購入係用: 展示が出たレース(締切の25分前〜2分前)の2連単・3連単オッズを取って data/odds_live に残す。取ったレースを返す"""
    import datetime as dt
    from concurrent.futures import ThreadPoolExecutor
    from common import JST
    todo = []
    for k, x in preds.items():
        if x.get("version") != "final" or not x.get("deadline"):
            continue
        t = dt.datetime.strptime(date + x["deadline"], "%Y%m%d%H:%M").replace(tzinfo=JST)
        if dt.timedelta(minutes=2) <= t - now <= dt.timedelta(minutes=25):
            todo.append((k, x["jcd"], int(x["race"])))
    if not todo:
        return []
    with ThreadPoolExecutor(workers) as ex:
        f3 = [ex.submit(bet.fetch_odds, date, j, r) for _, j, r in todo]
        f2 = [ex.submit(bet.fetch_odds2, date, j, r) for _, j, r in todo]
        got = [(a.result(), b.result()) for a, b in zip(f3, f2)]
    p = DATA / "odds_live" / f"{date}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    saved = json.loads(p.read_text()) if p.exists() else {}
    done = []
    for (k, _, _), (o3, o2) in zip(todo, got):
        if o2:
            saved[k] = dict(t=f"{now:%H:%M}", o2=[o2.get(c) for c in bet.ODDS2_ORDER], o3=[(o3 or {}).get(c) for c in bet.ODDS_ORDER])
            done.append(k)
    if done:
        p.write_text(json.dumps(saved, ensure_ascii=False, separators=(",", ":")))
    return done


def _blend3(pred, o3):
    tri = pred.get("tri")
    waku = [b["waku"] for b in pred["boats"]]
    rows = []
    for (i, j, k), ix in bet.PI.items():
        o = o3.get((waku[i] - 1, waku[j] - 1, waku[k] - 1))
        if o:
            rows.append((i, j, k, o, tri[ix]))
    if len(rows) < 100:
        return []
    inv = sum(1 / r[3] for r in rows)
    import math
    sc = [math.exp(W3_P * math.log(max(p, 1e-6)) + W3_Q * math.log(max((1 / o) / inv, 1e-6))) for *_, o, p in rows]
    tot = sum(sc)
    return [(i, j, k, s / tot) for (i, j, k, _, _), s in zip(rows, sc)]


def _base(pred, date):
    """艇ごとの普段の力(そのコースでの1着率・2着以内率)。分からなければコースの平均"""
    try:
        import gbm_win
        hc, _ = gbm_win._hist(date[:6])
    except Exception:
        hc = None
    out = []
    for c, b in enumerate(pred["boats"], start=1):
        w0, t0 = COURSE_BASE[c]
        rw = rt2 = rn = 0
        if hc is not None and (b["toban"], c) in hc.index:
            r = hc.loc[(b["toban"], c)]
            rw, rt2, rn = float(r.rw), float(r.rt2), float(r.rn)
        out.append(((rw + K * w0) / (rn + K), (rt2 + K * t0) / (rn + K), int(rn)))
    return out


def _reasons(pred, k, live):
    """その艇の今日の材料(良い材料, 悪い材料)"""
    b = pred["boats"][k]
    good, bad = [], []
    mot = sorted(range(6), key=lambda x: -(pred["boats"][x].get("motor_2r") or 0))
    if k in mot[:2]:
        good.append("モーター上位")
    elif k in mot[-1:]:
        bad.append("モーター下位")
    st = sorted(range(6), key=lambda x: pred["st"][x])
    if k in st[:2]:
        good.append("スタート速い")
    elif k in st[-2:]:
        bad.append("スタート遅め")
    tj = (live or {}).get("tenji")
    if tj and len(tj) == 6 and all(tj):
        tw = sorted(range(6), key=lambda x: tj[pred["boats"][x]["waku"] - 1])
        if k in tw[:2]:
            good.append("展示タイム上位")
        elif k in tw[-1:]:
            bad.append("展示タイム最下位")
    if b["course"] != b["waku"]:
        (good if b["course"] < b["waku"] else bad).append(f"{b['waku']}枠→{b['course']}コース")
    if pred["fcnt"][k]:
        bad.append(f"F{pred['fcnt'][k]}持ち")
    tag = (pred.get("scene") or {}).get("tags", {}).get(str(k))
    if tag:
        good.append(tag)
    return good, bad


def roles(p1, p2, p3):
    """その艇の狙いどころ(頭あり・2着が熱い・3着押さえ・消し寄り)"""
    out = []
    if p1 >= 0.20:
        out.append("頭あり")
    if p2 >= 0.25:
        out.append("2着が熱い")
    elif p2 >= 0.15 and p1 < 0.20:
        out.append("2着まで")
    if p3 >= 0.25 and p1 + p2 < 0.35 and p2 < 0.25:
        out.append("3着押さえ")
    if p1 + p2 + p3 < 0.20:
        out.append("消し寄り")
    return out


def scenarios(pred, s2, s3, p1, n=3, floor=0.07):
    """展開ごとの予想: 勝ちそうな艇ごとに、その確率と、その時の2着・3着の候補(条件つき確率の上位2つ)"""
    waku = [b["waku"] for b in pred["boats"]]
    out = []
    for a in sorted(range(6), key=lambda x: -p1[x])[:n]:
        if p1[a] < floor:
            break
        sec = sorted(((j, p / p1[a]) for i, j, _, p in s2 if i == a), key=lambda x: -x[1])[:2]
        ta = sum(p for i, _, _, p in s3 if i == a) or 1
        thr = {}
        for i, _, k, p in s3:
            if i == a:
                thr[k] = thr.get(k, 0) + p / ta
        thr = sorted(thr.items(), key=lambda x: -x[1])[:2]
        name = "イン逃げ" if a == 0 else f"{a + 1}コース({waku[a]}号艇)が勝つ"
        out.append(dict(name=name, head=waku[a], p=p1[a], sec=[(waku[j], q) for j, q in sec], thr=[(waku[k], q) for k, q in thr]))
    return out


def view(pred, date, odds=None, live=None):
    """{src, at, boats:[{waku, name, p1, p2, p3, base1, base2, n, heat, good, bad}], top2:[(組, 確率)], top3:[(組, 確率)]}"""
    if not pred or not pred.get("tri"):
        return None
    waku = [b["waku"] for b in pred["boats"]]
    o2, o3 = (odds or {}).get("o2"), (odds or {}).get("o3")
    s2 = flex.blend2(pred, o2, live) if o2 else []
    s3 = _blend3(pred, o3) if o3 else []
    tri = pred["tri"]
    if not s3:
        s3 = [(i, j, k, tri[ix]) for (i, j, k), ix in bet.PI.items()]
    if not s2:
        acc = {}
        for i, j, _, p in s3:
            acc[(i, j)] = acc.get((i, j), 0) + p
        s2 = [(i, j, None, p) for (i, j), p in acc.items()]
    p1, p2, p3 = [0.0] * 6, [0.0] * 6, [0.0] * 6
    for i, j, _, p in s2:
        p1[i] += p
        p2[j] += p
    for _, _, k, p in s3:
        p3[k] += p
    base = _base(pred, date)
    boats = []
    for k, b in enumerate(pred["boats"]):
        b1, b2, n = base[k]
        top2 = p1[k] + p2[k]
        heat = 0
        if top2 >= b2 + 0.10 and top2 >= b2 * 1.3:
            heat = 1
        elif top2 <= b2 - 0.10 and top2 <= b2 * 0.7:
            heat = -1
        good, bad = _reasons(pred, k, live)
        boats.append(dict(waku=b["waku"], name=b["name"], course=b["course"], p1=p1[k], p2=p2[k], p3=p3[k],
                          base1=b1, base2=b2, n=n, heat=heat, good=good, bad=bad, roles=roles(p1[k], p2[k], p3[k])))
    top2 = sorted(((f"{waku[i]}-{waku[j]}", p) for i, j, _, p in s2), key=lambda x: -x[1])[:5]
    top3 = sorted(((f"{waku[i]}-{waku[j]}-{waku[k]}", p) for i, j, k, p in s3), key=lambda x: -x[1])[:5]
    return dict(src="混ぜた" if o2 else "情報部のみ", at=(odds or {}).get("t", ""), boats=boats, top2=top2, top3=top3,
                scen=scenarios(pred, s2, s3, p1))
