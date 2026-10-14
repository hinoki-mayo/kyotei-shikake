"""過去オッズ(data/odds_hist)で運用・立説中プランを再生して、説を確かめ直す
例: python scripts/replay_hist.py 2026-08-10 2026-10-13 [--odds bets] [--out 保存先.parquet]

・予想は、その日より前の成績だけで作ったモデルで作り直す(展示の進入・展示タイム・天候は競走成績の値を使う)
・買い目は今の bet.make_bet。オッズは確定オッズ(odds_hist)。--odds bets なら締切前に記録したオッズ(data/bets)
・2連単の払戻は確定2連単オッズ×100、3連単は競走成績の払戻で精算する
・作った予想は一時フォルダに書き、data/predictions は書き換えない
"""
import argparse
import datetime as dt
import json
import sys
import tempfile
import pathlib

import numpy as np
import pandas as pd

import bet
import predict
from common import DATA, daterange
from model import Model, load_results

PLANS = bet.OPS_PLANS + bet.SHADOW_PLANS
O2_ORDER = [(a, b) for a in range(6) for b in range(6) if a != b]


def day_results(res, date):
    d = res[res.date == date]
    out = {}
    for (jcd, race), g in d.groupby(["jcd", "race"]):
        if len(g) != 6 or g.course.isna().any():
            continue
        g = g.sort_values("waku")
        rank = {int(w): r for w, r in zip(g.waku, g["rank"])}
        win = [w for w, r in rank.items() if r == "01"]
        sec = [w for w, r in rank.items() if r == "02"]
        out[f"{jcd}-{race:02d}"] = dict(
            order=[int(w) for w in g.sort_values("course").waku],
            tenji=[float(x) if x == x else None for x in g.tenji],
            wind_dir=g.wind_dir.iloc[0], wind=float(g.wind.iloc[0]), wave=float(g.wave.iloc[0]),
            rain=g.weather.iloc[0] == "雨",
            win=win[0] if win else None, sec=sec[0] if sec else None,
            combo3t=g.combo3t.dropna().iloc[0] if g.combo3t.notna().any() else None,
            payout3t=g.payout3t.dropna().iloc[0] if g.payout3t.notna().any() else None)
    return out


def odds_hist(date):
    p = DATA / "odds_hist" / f"{date[:6]}.parquet"
    if not p.exists():
        return {}
    df = pd.read_parquet(p)
    df = df[df.date == date]
    out = {}
    for r in df.itertuples():
        o3 = {c: v for c, v in zip(bet.ODDS_ORDER, r.o3) if v == v} if len(r.o3) else {}
        o2 = {c: v for c, v in zip(O2_ORDER, r.o2) if v == v} if len(r.o2) else {}
        out[f"{int(r.jcd):02d}-{int(r.race):02d}"] = (o3, o2)
    return out


def odds_bets(date):
    """締切前に記録した3連単オッズ(2連単は記録があるレースだけ)。テスト・比較用"""
    p = DATA / "bets" / f"{date}.json"
    if not p.exists():
        return {}
    out = {}
    for k, rec in json.loads(p.read_text()).items():
        if rec.get("odds"):
            o3 = {c: o for c, o in zip(bet.ODDS_ORDER, rec["odds"]) if o}
            out[k] = (o3, None)
    return out


def settle(plan, r, o2):
    if not plan or plan.get("skip"):
        return None
    if plan.get("bet") == "2t":
        if not r["win"] or not r["sec"] or not o2:
            return None
        pay = o2.get((r["win"] - 1, r["sec"] - 1))
        if pay is None:
            return None
        combo, pay = f"{r['win']}-{r['sec']}", round(pay * 100)
    else:
        combo, pay = r["combo3t"], r["payout3t"]
        if not combo or pay is None:
            return None
    ret = sum(t["units"] * int(pay) for t in plan["tickets"] if t["combo"] == combo)
    return plan["stake"], ret


def run_day(date, res, src, tmp):
    results = day_results(res, date)
    odds = odds_hist(date) if src == "hist" else odds_bets(date)
    if not results or not odds:
        return []
    (tmp / "entries").mkdir(exist_ok=True)
    (tmp / "entries" / f"{date}.json").write_text(json.dumps(
        {k: {x: v[x] for x in ("order", "tenji", "wind_dir", "wind", "wave", "rain")} for k, v in results.items()},
        ensure_ascii=False))
    predict.DATA = tmp
    predict.run(date, model=Model(load_results(date), date), allow_late=True)
    preds = json.loads((tmp / "predictions" / f"{date}.json").read_text())["races"]
    rows = []
    for key, pred in preds.items():
        if key not in results or key not in odds or not pred.get("tri"):
            continue
        o3, o2 = odds[key]
        if not o3:
            continue
        o2b = o2 or None
        made = bet.make_bet(pred, o3, o2b or bet_est_odds2(o3), date)["plans"]
        row = dict(date=date, key=key, hp0=pred["scene"]["head_prob"][0], f0=pred["fcnt"][0],
                   g0=pred["boats"][0]["grade"], st01=pred["st"][0] - pred["st"][1],
                   win=results[key]["win"], sec=results[key]["sec"], o2_real=bool(o2))
        for n in PLANS:
            s = settle(made[n], results[key], o2 or bet_est_odds2(o3))
            row[n + "_stake"], row[n + "_ret"] = (s if s else (0, 0))
        rows.append(row)
    return rows


def bet_est_odds2(o3):
    from backfill_ops import est_odds2
    return est_odds2(o3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--odds", default="hist", choices=["hist", "bets"])
    ap.add_argument("--out")
    a = ap.parse_args()
    s, e = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    res = pd.concat([pd.read_parquet(DATA / "results" / f"{y}.parquet") for y in range(s.year, e.year + 1)])
    res = res[(res.date >= f"{s:%Y%m%d}") & (res.date <= f"{e:%Y%m%d}")]
    rows = []
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        (tmp / "programs").symlink_to(DATA / "programs")
        for d in daterange(s, e):
            r = run_day(f"{d:%Y%m%d}", res, a.odds, tmp)
            rows += r
            print(f"{d:%Y%m%d}: {len(r)}レース", file=sys.stderr, flush=True)
    df = pd.DataFrame(rows)
    if a.out:
        df.to_parquet(a.out, index=False)
    for n in PLANS:
        b = df[df[n + "_stake"] > 0]
        st, rt = b[n + "_stake"].sum(), b[n + "_ret"].sum()
        print(f"{n:8s} {len(b):5d}R 的中{(b[n + '_ret'] > 0).sum():4d} 回収率 {rt / st:.1%}" if st else f"{n:8s} 0R")


if __name__ == "__main__":
    main()
