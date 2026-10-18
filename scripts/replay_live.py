"""今の方法で、その日のレースを確定オッズで作り直す(再生)。実戦の記録(締切前に決めたもの)とは別に保存する
例: python scripts/replay_live.py 20261014 20261015

・締切を過ぎたレースの3連単・2連単の確定オッズを公式サイトから取り、今いる社員全員の買い目を作り直す
・結果は data/bets_replay/日付.json(レース → プランの買い目)。集計(build_site)で今の決裁者を当てはめ、
  実戦のv1と並べて「今の方法で再生(確定オッズ)」として出す。同じ日の実戦との差が、締切前に買うことによる差になる
・作り直し済みのレースは飛ばす(途中から再開できる)
・確定オッズそのものも data/odds_final/日付.json に残す(締切2分前に選んだ目が確定で何%動くかを測るため)
"""
import datetime as dt
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import bet
import org_tree
from common import DATA, JST, now_jst


def run(date, workers=8):
    preds = json.loads((DATA / "predictions" / f"{date}.json").read_text())["races"]
    ep = DATA / "entries" / f"{date}.json"
    entries = json.loads(ep.read_text()) if ep.exists() else {}
    p = DATA / "bets_replay" / f"{date}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    out = json.loads(p.read_text()) if p.exists() else {}
    fp = DATA / "odds_final" / f"{date}.json"   # 確定オッズそのもの(締切前のオッズとの差を測るため)
    fp.parent.mkdir(parents=True, exist_ok=True)
    final = json.loads(fp.read_text()) if fp.exists() else {}
    now = now_jst()
    todo = [(k, x) for k, x in preds.items() if x.get("tri") and (k not in out or k not in final)
            and dt.datetime.strptime(date + x["deadline"], "%Y%m%d%H:%M").replace(tzinfo=JST) < now]
    with ThreadPoolExecutor(workers) as ex:
        f3 = [ex.submit(bet.fetch_odds, date, x["jcd"], x["race"]) for _, x in todo]
        f2 = [ex.submit(bet.fetch_odds2, date, x["jcd"], x["race"]) for _, x in todo]
        got = [(a.result(), b.result()) for a, b in zip(f3, f2)]
    n = 0
    for (key, pred), (o3, o2) in zip(todo, got):
        if not o3 or not o2:
            continue
        final[key] = dict(o2=[o2.get(c) for c in bet.ODDS2_ORDER], o3=[o3.get(c) for c in bet.ODDS_ORDER])
        if key in out:
            continue
        live = entries.get(key) if isinstance(entries.get(key), dict) else None
        made = bet.make_bet(pred, o3, o2, date, live)["plans"]
        out[key] = {k: made[k] for k in org_tree.ORG_PLANS if k in made}
        n += 1
    p.write_text(json.dumps(out, ensure_ascii=False, indent=0))
    fp.write_text(json.dumps(final, separators=(",", ":")))
    print(f"{date}: {n}レースを今の方法・確定オッズで作り直し(合計 {len(out)}レース)・確定オッズ {len(final)}レース")


if __name__ == "__main__":
    for d in sys.argv[1:] or [f"{now_jst():%Y%m%d}"]:
        run(d)
