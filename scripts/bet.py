"""試験用の買い目: 締切前の3連単オッズ × 2・3着モデルの確率で、5通りの買い方を組む

・締切の約2〜9分前に1レース1回だけオッズを見に行き、買い目を data/bets/日付.json に保存する
・締切を過ぎたレースは書き換えない(予想と同じく封印)
・確率は「モデル」と「オッズから読んだ市場の確率」を混ぜたもの(BLEND)。モデル単独だと
  穴目を大きく過大評価していた(万舟帯で予測0.62%→実際0.12%)。市場の方がかなり正確なので重みは市場寄り
・買い方(予算はどれも1通り1,000〜2,000円、100円単位、確率に比例して配分):
    balance   バランス           頭自由・1頭×3艇6点。的中確率30%以上で期待回収率最大。100%未満は見送り
    in_hit    イン・的中重視      1コース頭・6点。的中確率最大。期待回収率80%未満は見送り
    in_ev     イン・期待値重視    1コース頭・6点。期待回収率最大。的中確率15%未満は見送り
    out_hit   イン以外・的中重視  1コース以外頭・1頭×4艇12点。的中確率最大。期待回収率70%未満は見送り
                                (穴寄りの頭は控除率がそのまま効くので、80%だとほぼ全部見送りになる)
    out_ana   イン以外・穴        1コース以外頭・60倍以上の目から期待値順に最大10点。記録のため見送りなし
例: python scripts/bet.py   (entry.pyから毎回呼ばれる)
"""
import datetime as dt
import itertools
import json
import re
import time
import urllib.request

import numpy as np

from common import DATA, JST, UA, now_jst
from place import PERMS

URL = "https://www.boatrace.jp/owpc/pc/race/odds3t?rno={race}&jcd={jcd}&hd={date}"
ODDS_RE = re.compile(r'class="oddsPoint[^"]*">([^<]*)<')
BLEND = (0.13, 0.99)    # 確率の混ぜ方(モデル, 市場)の重み。2025-26年のランダム1,500レースの締切時オッズで推定(モデル0.13±0.05)
WINDOW = (2, 9)         # 締切の何分前のレースを対象にするか
ANA_ODDS = 60           # 穴狙いの対象にするオッズの下限
ANA_MAX = 10            # 穴狙いの最大点数
PLANS = {"balance": "バランス", "in_hit": "イン・的中重視", "in_ev": "イン・期待値重視",
         "out_hit": "イン以外・的中重視", "out_ana": "イン以外・穴"}
M = ["逃げ", "まくり", "差し", "まくり差し"]

# 公式オッズ表の並び: 20行×6列(列=1着の枠)。列の中は(2着,3着)の昇順
ODDS_ORDER = [None] * 120
for _c in range(6):
    for _r, (_j, _k) in enumerate((j, k) for j in range(6) for k in range(6) if len({_c, j, k}) == 3):
        ODDS_ORDER[_r * 6 + _c] = (_c, _j, _k)
PI = {p: i for i, p in enumerate(PERMS)}


def _forms(heads, n):
    """1頭×n艇のフォーメーション一覧 [(頭, ヒモ, PERMSの添字)]"""
    return [(w, s, [PI[(w, a, b)] for a, b in itertools.permutations(s, 2)])
            for w in heads for s in itertools.combinations([x for x in range(6) if x != w], n)]


FORMS6 = _forms(range(6), 3)
FORMS_IN = _forms([0], 3)
FORMS_OUT = _forms(range(1, 6), 4)


def fetch_odds(date, jcd, race):
    """枠番の(1着,2着,3着)(0始まり) -> オッズ。取れなければNone"""
    try:
        req = urllib.request.Request(URL.format(race=race, jcd=jcd, date=date), headers=UA)
        with urllib.request.urlopen(req, timeout=40) as r:
            h = r.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    vals = ODDS_RE.findall(h)
    if len(vals) != 120:
        return None
    out = {}
    for combo, v in zip(ODDS_ORDER, vals):
        try:
            out[combo] = float(v)
        except ValueError:
            pass   # 欠場などで売っていない目
    return out


def blend(tri, odds_c):
    """モデルの確率と市場の確率(オッズの逆数を正規化)を混ぜる。売っていない目は0"""
    sold = np.array([o is not None and o > 0 for o in odds_c])
    q = np.where(sold, 1 / np.array([o if o else 1.0 for o in odds_c]), 0)
    q = q / q.sum()
    s = np.full(120, -np.inf)
    s[sold] = BLEND[0] * np.log(np.asarray(tri)[sold] + 1e-9) + BLEND[1] * np.log(q[sold])
    e = np.exp(s - s[sold].max())
    return e / e.sum()


def _units(pp, total, cap=2000):
    """確率に比例して100円単位で配分(最低1口、上限capを超えないよう調整)"""
    hit = sum(pp)
    units = [max(1, round(p / hit * total / 100)) for p in pp]
    while sum(units) * 100 > cap:
        units[units.index(max(units))] -= 1
    return units


def _form_stats(p, odds_c, idx):
    pp = [float(p[i]) for i in idx]
    hit = sum(pp)
    return pp, hit, sum(x * x * odds_c[i] for x, i in zip(pp, idx)) / hit   # 確率比例で買ったときの期待回収率


def pick(p, odds_c, forms, by, min_hit=0.0, min_ev=0.0):
    """formsの中から by('hit'|'ev')が最大のものを選ぶ。条件を満たさなければNone"""
    best = None
    for w, s, idx in forms:
        if any(odds_c[i] is None for i in idx):
            continue
        pp, hit, ev = _form_stats(p, odds_c, idx)
        if hit < min_hit or ev < min_ev:
            continue
        key = hit if by == "hit" else ev
        if best is None or key > best[0]:
            best = (key, w, s, idx, pp, hit, ev)
    return best and best[1:]


def plan(tri, odds_c):
    """コース基準の確率とオッズ(PERMS順)から5通りの買い目を作る。
    戻り値 {買い方: (頭, ヒモ, 添字, 口数, 的中確率, 期待回収率) or None(見送り)}"""
    p = blend(tri, odds_c)
    out = {}
    r = pick(p, odds_c, FORMS6, "ev", min_hit=0.30, min_ev=1.0)
    if r:
        w, s, idx, pp, hit, ev = r
        out["balance"] = (w, s, idx, _units(pp, 1000 + 1000 * min(1.0, (ev - 1.0) / 0.5)), hit, ev)
    for name, forms, by, mh, me, total in [("in_hit", FORMS_IN, "hit", 0, 0.8, 1000),
                                           ("in_ev", FORMS_IN, "ev", 0.15, 0, 1000),
                                           ("out_hit", FORMS_OUT, "hit", 0, 0.7, 1500)]:
        r = pick(p, odds_c, forms, by, mh, me)
        out[name] = r and (r[0], r[1], r[2], _units(r[3], total), r[4], r[5])
    cand = [i for i in range(120) if PERMS[i][0] != 0 and odds_c[i] and odds_c[i] >= ANA_ODDS]
    cand = sorted(cand, key=lambda i: -p[i] * odds_c[i])[:ANA_MAX]
    if cand:
        units = [2 if n < 5 else 1 for n in range(len(cand))]    # 期待値の高い上位5点は2口
        hit = float(sum(p[i] for i in cand))
        ev = float(sum(p[i] * odds_c[i] * u for i, u in zip(cand, units)) / sum(units))
        out["out_ana"] = (None, None, cand, units, hit, ev)
    else:
        out["out_ana"] = None
    return p, out


def _scenario(name, pred, p, w, s, idx, waku):
    """買い方ごとのシナリオの一文。勝つ確率は買い目と同じ混ぜた確率p、決まり手はモデルから"""
    P = pred["prob"]
    win = lambda c: float(sum(p[i] for i in range(120) if PERMS[i][0] == c))
    if w == 0:
        himo = "・".join(str(waku[x]) for x in s)
        return f"{waku[0]}号艇(1コース)が逃げる展開(1コースが勝つ確率{win(0):.0%})。2・3着は{himo}号艇の争い"
    if w is None:   # 穴: 一番多く入っている頭で説明する
        heads = [PERMS[i][0] for i in idx]
        w = max(set(heads), key=heads.count)
        lead = "1コースが崩れる波乱を想定。"
    else:
        lead = ""
    mv = max(range(1, 4), key=lambda m: P[w][m])
    tail = {"まくり": "内側の艇は叩かれやすく、外の艇が2・3着に続きやすい",
            "差し": "1コースは流れても2・3着に残りやすい",
            "まくり差し": "内と外の間を割って抜ける形"}[M[mv]]
    return f"{lead}{waku[w]}号艇({w + 1}コース)の{M[mv]}が決まる展開(この艇が勝つ確率{win(w):.0%})。{tail}"


def make_bet(pred, odds_w):
    """予想(コース基準)と枠番オッズから、保存用の買い目(5通り)を作る"""
    waku = [b["waku"] for b in pred["boats"]]            # コース -> 枠番
    odds_c = [odds_w.get((waku[i] - 1, waku[j] - 1, waku[k] - 1)) for i, j, k in PERMS]
    p, plans = plan(pred["tri"], odds_c)
    out = {}
    for name in PLANS:
        r = plans.get(name)
        if r is None:
            out[name] = dict(skip=True)
            continue
        w, s, idx, units, hit, ev = r
        tickets = [dict(combo="-".join(str(waku[c]) for c in PERMS[i]), units=u, odds=odds_c[i],
                        prob=round(float(p[i]), 4), model=round(pred["tri"][i], 4))
                   for i, u in zip(idx, units)]
        out[name] = dict(skip=False, head=None if w is None else waku[w],
                         himo=None if s is None else [waku[x] for x in s],
                         ev=round(float(ev), 3), hit=round(float(hit), 3), stake=sum(units) * 100,
                         scenario=_scenario(name, pred, p, w, s, idx, waku), tickets=tickets)
    # 締切前オッズそのもの(公式表の並び)も残す。締切時オッズとの差の分析用
    raw = [odds_w.get(c) for c in ODDS_ORDER]
    return dict(plans=out, odds=raw)


def run(now=None):
    now = now or now_jst()
    date = f"{now:%Y%m%d}"
    pp = DATA / "predictions" / f"{date}.json"
    if not pp.exists():
        return []
    preds = json.loads(pp.read_text())["races"]
    bp = DATA / "bets" / f"{date}.json"
    bp.parent.mkdir(parents=True, exist_ok=True)
    bets = json.loads(bp.read_text()) if bp.exists() else {}
    done = []
    for key, pred in preds.items():
        if key in bets or pred.get("version") != "final" or not pred.get("tri"):
            continue
        t = dt.datetime.strptime(date + pred["deadline"], "%Y%m%d%H:%M").replace(tzinfo=JST)
        if not (now + dt.timedelta(minutes=WINDOW[0]) < t <= now + dt.timedelta(minutes=WINDOW[1])):
            continue
        odds = fetch_odds(date, pred["jcd"], pred["race"])
        time.sleep(1.0)
        if not odds:
            continue
        bets[key] = dict(make_bet(pred, odds), odds_at=now.strftime("%H:%M"))
        done.append(key)
    if done:
        bp.write_text(json.dumps(bets, ensure_ascii=False, indent=0))
    print(f"試験用買い目: {len(done)}レース {done}")
    return done


if __name__ == "__main__":
    run()
