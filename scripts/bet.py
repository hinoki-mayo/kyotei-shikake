"""試験用の買い目: 締切前の3連単オッズ × 2・3着モデルの確率で、1頭×3艇(6点)のフォーメーションを組む

・締切の約2〜9分前に1レース1回だけオッズを見に行き、買い目を data/bets/日付.json に保存する
・締切を過ぎたレースは書き換えない(予想と同じく封印)
・全60通り(1着6艇×2・3着候補3艇の組み合わせ10通り)のうち、的中確率が下限以上で
  期待回収率が最大のものを選ぶ。基準に届かなければ見送り
・口数は確率に比例して100円単位で配分(同じ目に複数口も可)。予算は1レース1,000〜2,000円
例: python scripts/bet.py   (entry.pyから毎回呼ばれる)
"""
import datetime as dt
import itertools
import json
import re
import time
import urllib.request

from common import DATA, JST, UA, now_jst
from place import PERMS

URL = "https://www.boatrace.jp/owpc/pc/race/odds3t?rno={race}&jcd={jcd}&hd={date}"
ODDS_RE = re.compile(r'class="oddsPoint[^"]*">([^<]*)<')
MIN_HIT = 0.30          # フォーメーション全体の的中確率の下限(確率重視)
MIN_EV = 1.00           # 期待回収率の下限(これ未満なら見送り)
BUDGET = (1000, 2000)   # 1レースの予算。期待回収率が高いほど上限に寄せる
WINDOW = (2, 9)         # 締切の何分前のレースを対象にするか

# 公式オッズ表の並び: 20行×6列(列=1着の枠)。列の中は(2着,3着)の昇順
ODDS_ORDER = [None] * 120
for _c in range(6):
    for _r, (_j, _k) in enumerate((j, k) for j in range(6) for k in range(6) if len({_c, j, k}) == 3):
        ODDS_ORDER[_r * 6 + _c] = (_c, _j, _k)
PI = {p: i for i, p in enumerate(PERMS)}
FORMS = [(w, s) for w in range(6) for s in itertools.combinations([x for x in range(6) if x != w], 3)]
FORM_IDX = [[PI[(w, a, b)] for a, b in itertools.permutations(s, 2)] for w, s in FORMS]


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


def plan(tri, odds_c, min_hit=MIN_HIT, min_ev=MIN_EV, budget=BUDGET):
    """tri: PERMS順の確率120個、odds_c: PERMS順のオッズ120個(売っていない目はNone)。コース基準。
    戻り値: (フォーメーション番号, 各点の口数, 期待回収率, 的中確率) / 見送りはNone"""
    best = None
    for fi, idx in enumerate(FORM_IDX):
        if any(odds_c[i] is None for i in idx):
            continue
        pp = [tri[i] for i in idx]
        hit = sum(pp)
        if hit < min_hit:
            continue
        ev = sum(p * p * odds_c[i] for p, i in zip(pp, idx)) / hit   # 確率比例で買ったときの期待回収率
        if best is None or ev > best[0]:
            best = (ev, fi, pp, hit)
    if best is None or best[0] < min_ev:
        return None
    ev, fi, pp, hit = best
    total = budget[0] + (budget[1] - budget[0]) * min(1.0, (ev - min_ev) / 0.5)
    units = [max(1, round(p / hit * total / 100)) for p in pp]
    while sum(units) * 100 > budget[1]:          # 丸めで上限を超えたら、一番多い目から1口ずつ減らす
        units[units.index(max(units))] -= 1
    return fi, units, ev, hit


def make_bet(pred, odds_w):
    """予想(コース基準)と枠番オッズから、保存用の買い目を作る"""
    waku = [b["waku"] for b in pred["boats"]]            # コース -> 枠番
    odds_c = [odds_w.get((waku[i] - 1, waku[j] - 1, waku[k] - 1)) for i, j, k in PERMS]
    r = plan(pred["tri"], odds_c)
    if r is None:
        return dict(skip=True)
    fi, units, ev, hit = r
    w, s = FORMS[fi]
    tickets = [dict(combo=f"{waku[PERMS[i][0]]}-{waku[PERMS[i][1]]}-{waku[PERMS[i][2]]}",
                    units=u, odds=odds_c[i], prob=round(pred["tri"][i], 4))
               for i, u in zip(FORM_IDX[fi], units)]
    return dict(skip=False, head=waku[w], himo=[waku[x] for x in s], ev=round(ev, 3), hit=round(hit, 3),
                stake=sum(u for u in units) * 100, tickets=tickets)


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
