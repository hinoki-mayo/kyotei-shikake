"""運用プランの切り替え日に、切り替え前に作った買い目を今のロジックで作り直す(1日単位で比べるため)

・その日の締切前に記録した3連単オッズ(data/bets の odds)をそのまま使い、今のロジックで運用プランを組む
・2連単オッズは切り替え前は取っていないレースが多いので、3連単オッズから推定した値で代用する
  (どの目を買うかは確率で決まるので影響しない。pickinの見送り判定だけは推定オッズで行う)
・結果は data/bets_backfill/日付.json に別に保存し、元の記録(締切前に封印したもの)は書き換えない。
  集計(build_site.bets_records)は、元の記録に今のロジックの印が無いレースだけこちらで補う
例: python scripts/backfill_ops.py 20261014
"""
import json
import sys

import bet
from common import DATA
from place import PERMS


def est_odds2(odds_w):
    """3連単オッズから2連単オッズを推定(枠番基準)。控除率25%として市場の確率から逆算"""
    inv = sum(1 / o for o in odds_w.values())
    q = {}
    for (a, b, _), o in odds_w.items():
        q[(a, b)] = q.get((a, b), 0) + 1 / o / inv
    return {k: round(0.75 / v, 1) for k, v in q.items() if v > 0}


def run(date):
    bets = json.loads((DATA / "bets" / f"{date}.json").read_text())
    preds = json.loads((DATA / "predictions" / f"{date}.json").read_text())["races"]
    out = {}
    for key, rec in bets.items():
        plans = rec.get("plans", {})
        if all(plans.get(n, {}).get("logic") == bet.OPS_LOGIC for n in bet.OPS_PLANS):
            continue   # 今のロジックで作った記録がある
        pred = preds.get(key)
        if not pred or not pred.get("tri") or not rec.get("odds"):
            continue
        odds_w = {c: o for c, o in zip(bet.ODDS_ORDER, rec["odds"]) if o}
        made = bet.make_bet(pred, odds_w, est_odds2(odds_w), date)["plans"]
        out[key] = {n: dict(made[n], backfill=True, odds2_est=True) for n in bet.OPS_PLANS}
    p = DATA / "bets_backfill" / f"{date}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=0))
    bought = {n: sum(not v[n].get("skip") for v in out.values()) for n in bet.OPS_PLANS}
    print(f"{date}: {len(out)}レースを今のロジックで作り直し 購入 {bought}")


if __name__ == "__main__":
    for d in sys.argv[1:]:
        run(d)
