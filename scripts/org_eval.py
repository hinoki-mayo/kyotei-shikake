"""予想組織の提案を、確定オッズの過去データで精算して自信度の表を作る
例: python scripts/org_eval.py --preds 予想フォルダ1 予想フォルダ2 --gbm 学習済みGBM.pkl --out 提案.parquet
    python scripts/org_eval.py --rows 提案.parquet --conf-from 20260601 20260809 --test 20260810 20261013

・予想は replay_hist.py --keep で作り直したもの(その日より前の成績だけのモデル)を使う
・直前情報(展示タイム・風・波・進入)は競走成績の値。2連単は確定2連単オッズ、3連単は競走成績の払戻(無ければ確定オッズ)で精算
・GBM(実績予想くん2号)は、確かめる期間より前だけで学習したものを --gbm で渡す(学習期間のレースで確かめないため)
・--conf-from の期間で自信度を作り、--test の期間で最終決裁者(v1)の成績を確かめる。--save なら自信度を data/org/confidence.json に保存
"""
import argparse
import json
import pathlib
import sys

import pandas as pd

import bet
import gbm_win
import org_tree
import replay_hist as rh
from common import DATA


def run(pred_dirs, gbm_path):
    if gbm_path:
        gbm_win.MODEL_P = pathlib.Path(gbm_path)
        gbm_win._load.cache_clear()
    files = sorted(f for d in pred_dirs for f in pathlib.Path(d).glob("*.json"))
    years = sorted({f.stem[:4] for f in files})
    res = pd.concat([pd.read_parquet(DATA / "results" / f"{y}.parquet") for y in years])
    rows = []
    for f in files:
        date = f.stem
        preds = json.loads(f.read_text())
        results = rh.day_results(res, date)
        odds = rh.odds_hist(date)
        n0 = len(rows)
        for key, pred in preds.items():
            if key not in results or key not in odds or not pred.get("tri"):
                continue
            o3, o2 = odds[key]
            if not o3 or not o2:
                continue
            r = results[key]
            live = {x: r[x] for x in ("order", "tenji", "wind_dir", "wind", "wave", "rain")}
            plans = bet.make_bet(pred, o3, o2, date, live)["plans"]
            for p in org_tree.proposals(plans, pred):
                ret, ok = 0, True
                for kind in {t.get("bet", p["bet"]) for t in p["tickets"]}:   # 2連単と3連単が混ざる提案もある
                    combo, pay = rh._hit(kind, r, o2, o3)
                    if combo is None:
                        ok = False
                        break
                    ret += sum(t["units"] * int(pay) for t in p["tickets"] if t.get("bet", p["bet"]) == kind and t["combo"] == combo)
                if not ok:
                    continue
                rows.append(dict(date=date, key=key, leaf=p["leaf"], tags=p["tags"], plan=p["plan"], head=p["head"],
                                 course=p["course"], stake=p["stake"], ret=ret))
        print(f"{date}: 提案 {len(rows) - n0}", file=sys.stderr, flush=True)
    return pd.DataFrame(rows)


def report(df, conf, label, mode="head"):
    """最終決裁者(v1)と、全部採用(参考)の成績"""
    props = df.to_dict("records")
    by_race = {}
    for p in props:
        by_race.setdefault((p["date"], p["key"]), []).append(p)
    st = ret = n = 0
    for ps in by_race.values():
        for p in org_tree.decide(ps, conf, mode):
            st += p["stake"]
            ret += p["ret"]
            n += 1
    print(f"■ {label}({mode}): 決裁者v1 {n}件 投資{st:,} 払戻{ret:,} 回収率{ret / st:.1%}" if st else f"■ {label}: 決裁者v1 採用なし")
    for pk, g in df.groupby("plan"):
        print(f"   参考 {pk:9s} 全部採用 {len(g):5d}件 回収率 {g.ret.sum() / g.stake.sum():.1%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preds", nargs="*")
    ap.add_argument("--gbm")
    ap.add_argument("--out")
    ap.add_argument("--rows")
    ap.add_argument("--conf-from", nargs=2)
    ap.add_argument("--test", nargs=2)
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    df = run(a.preds, a.gbm) if a.preds else pd.read_parquet(a.rows)
    if a.out:
        df.to_parquet(a.out, index=False)
    if a.conf_from:
        lo, hi = a.conf_from
        conf = org_tree.build_confidence(df[(df.date >= lo) & (df.date <= hi)].to_dict("records"))
        for nd in sorted(conf):
            c = conf[nd]
            print(f"{'  ' * nd.count('.')}{nd:28s} {c['n']:5d}件 回収率{c['roi']:7.1%} 自信度{c['conf']:7.1%}")
        if a.test:
            t = df[(df.date >= a.test[0]) & (df.date <= a.test[1])]
            report(t, conf, f"確かめ {a.test[0]}〜{a.test[1]}", "head")
            report(t, conf, f"確かめ {a.test[0]}〜{a.test[1]}", "side")
        if a.save:
            org_tree.CONF_P.parent.mkdir(parents=True, exist_ok=True)
            org_tree.CONF_P.write_text(json.dumps(dict(period=[lo, hi], shrink=org_tree.SHRINK, prior=org_tree.PRIOR, nodes=conf),
                                                  ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
