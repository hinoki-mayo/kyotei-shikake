"""運用プランの切り替え日に、切り替え前に作った買い目を今のロジックで作り直す(1日単位で比べるため)

・その日の締切前に記録した3連単オッズ(data/bets の odds)をそのまま使い、今のロジックで運用プランを組む
・2連単オッズは切り替え前は取っていないレースが多い。--fetch を付けると公式サイトから取りに行く
  (レース後に見るので確定オッズ。odds2_final の印を付ける)。付けない時は3連単オッズからの推定値で代用
  (どの目を買うかは確率で決まるので影響しない。pickinの見送り判定だけはこのオッズで行う)
・締切を過ぎたのに記録が無いレース(自動処理が止まって取り逃がしたもの)も、--fetch なら3連単・2連単の
  オッズを公式サイトから取って作り直す(どちらも確定オッズ。odds_final の印を付ける)
・結果は data/bets_backfill/日付.json に別に保存し、元の記録(締切前に封印したもの)は書き換えない。
  集計(build_site.bets_records)は、元の記録に今のロジックの印が無いレースだけこちらで補う
例: python scripts/backfill_ops.py --fetch 20261014
"""
import json
import sys
import time

import datetime as dt

import bet
from common import DATA, JST, now_jst


def est_odds2(odds_w):
    """3連単オッズから2連単オッズを推定(枠番基準)。控除率25%として市場の確率から逆算"""
    inv = sum(1 / o for o in odds_w.values())
    q = {}
    for (a, b, _), o in odds_w.items():
        q[(a, b)] = q.get((a, b), 0) + 1 / o / inv
    return {k: round(0.75 / v, 1) for k, v in q.items() if v > 0}


def run(date, fetch=False):
    bets = json.loads((DATA / "bets" / f"{date}.json").read_text())
    preds = json.loads((DATA / "predictions" / f"{date}.json").read_text())["races"]
    out = {}
    if fetch:   # 締切を過ぎたのに記録が無いレースは、確定オッズを取って記録の代わりにする
        now = now_jst()
        for key, pred in preds.items():
            t = dt.datetime.strptime(date + pred["deadline"], "%Y%m%d%H:%M").replace(tzinfo=JST)
            if key in bets or pred.get("version") != "final" or not pred.get("tri") or t > now:
                continue
            odds_w = bet.fetch_odds(date, pred["jcd"], pred["race"])
            time.sleep(1.0)
            odds2 = bet.fetch_odds2(date, pred["jcd"], pred["race"])
            time.sleep(1.0)
            if not odds_w:
                continue
            made = bet.make_bet(pred, odds_w, odds2 or est_odds2(odds_w), date)["plans"]
            out[key] = {n: dict(made[n], backfill=True, odds_final=True) for n in bet.OPS_PLANS + bet.SHADOW_PLANS}
    for key, rec in bets.items():
        plans = rec.get("plans", {})
        if all(plans.get(n, {}).get("logic") == bet.OPS_LOGIC for n in bet.OPS_PLANS + bet.SHADOW_PLANS):
            continue   # 今のロジックで作った記録がある
        pred = preds.get(key)
        if not pred or not pred.get("tri") or not rec.get("odds"):
            continue
        odds_w = {c: o for c, o in zip(bet.ODDS_ORDER, rec["odds"]) if o}
        odds2, mark = None, {"odds2_est": True}
        if fetch:
            odds2 = bet.fetch_odds2(date, pred["jcd"], pred["race"])
            time.sleep(1.0)   # 公式サーバーに負担をかけないよう間を空ける
            if odds2:
                mark = {"odds2_final": True}
        made = bet.make_bet(pred, odds_w, odds2 or est_odds2(odds_w), date)["plans"]
        out[key] = {n: dict(made[n], backfill=True, **mark) for n in bet.OPS_PLANS + bet.SHADOW_PLANS}
    p = DATA / "bets_backfill" / f"{date}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=0))
    bought = {n: sum(not v[n].get("skip") for v in out.values()) for n in bet.OPS_PLANS + bet.SHADOW_PLANS}
    real = sum(v[bet.OPS_PLANS[0]].get("odds2_final", False) for v in out.values())
    print(f"{date}: {len(out)}レースを今のロジックで作り直し(確定2連単オッズ {real}レース) 購入 {bought}")


if __name__ == "__main__":
    args = sys.argv[1:]
    for d in [a for a in args if a != "--fetch"]:
        run(d, fetch="--fetch" in args)
