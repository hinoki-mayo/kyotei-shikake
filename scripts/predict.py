"""その日の全場・全レースの予想を作り、data/predictions/日付.json に保存する

・展示前は枠なり進入で「仮予想(pre)」、展示の進入を反映したら「確定版(final)」
・締切を過ぎたレースは絶対に書き換えない(封印)。更新履歴がそのまま事前公開の証明になる
例: python scripts/predict.py --date 20260928
"""
import argparse
import datetime as dt
import json

import numpy as np
import pandas as pd

from common import DATA, JST, now_jst, today_jst
from model import Model, load_results
from scene import build_scene


def load_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def closed(date, deadline):
    """締切を過ぎているか"""
    if not deadline:
        return False
    t = dt.datetime.strptime(date + deadline, "%Y%m%d%H:%M").replace(tzinfo=JST)
    return now_jst() >= t


def run(date, only=None, model=None, allow_late=False):
    prog_p = DATA / "programs" / f"{date[:4]}.parquet"
    if not prog_p.exists():
        return 0
    prog = pd.read_parquet(prog_p)
    prog = prog[prog.date == date]
    if prog.empty:
        print(f"{date}: 番組表なし")
        return 0
    out_p = DATA / "predictions" / f"{date}.json"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    store = load_json(out_p, {"date": date, "races": {}})
    entries_override = load_json(DATA / "entries" / f"{date}.json", {})
    model = model or Model(load_results(date), date)
    n = 0
    for (jcd, race), g in prog.groupby(["jcd", "race"]):
        key = f"{jcd}-{race:02d}"
        if only and key not in only:
            continue
        old = store["races"].get(key)
        g = g.sort_values("waku")
        deadline = g.deadline.iloc[0]
        order = entries_override.get(key)          # 展示の進入(枠番をコース順に)
        version = "final" if order else "pre"
        if old and (closed(date, deadline) or (old["version"] == "final" and version == "final" and not only)):
            continue
        if len(g) != 6:
            continue
        if not old and closed(date, deadline) and not allow_late:
            continue   # 締切後に新しく作った予想は載せない(後出し防止)
        order = order or [1, 2, 3, 4, 5, 6]
        byw = {int(r.waku): r for r in g.itertuples()}
        ents = [byw[w] for w in order]
        P, st, fc, rate = model.race(jcd, [dict(course=c + 1, toban=e.toban) for c, e in enumerate(ents)])
        sc = build_scene(P, st, fc)
        store["races"][key] = dict(
            jcd=jcd, venue=g.venue.iloc[0], race=int(race), rtype=g.rtype.iloc[0], deadline=deadline,
            version=version, predicted_at=now_jst().strftime("%Y-%m-%d %H:%M"),
            boats=[dict(course=c + 1, waku=int(e.waku), toban=e.toban, name=e.name, grade=e.grade,
                        age=int(e.age), branch=e.branch, nat_win=float(e.nat_win), motor_2r=float(e.motor_2r))
                   for c, e in enumerate(ents)],
            st=[round(float(x), 3) for x in st], fcnt=[int(x) for x in fc],
            prob=np.round(P, 4).tolist(), scene=_jsonable(sc))
        n += 1
    out_p.write_text(json.dumps(store, ensure_ascii=False, indent=0))
    print(f"{date}: {n}レース予想")
    return n


def _jsonable(sc):
    sc = dict(sc)
    for k in ("roles", "tags", "lines"):
        sc[k] = {str(a): b for a, b in sc[k].items()}
    for k in ("shu", "sub"):
        sc[k] = int(sc[k])
    for k in ("head", "ren", "bad", "late"):
        sc[k] = [int(x) for x in sc[k]]
    sc["pressed"] = bool(sc["pressed"])
    return sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", action="append", help="YYYYMMDD。省略時は今日と明日")
    a = ap.parse_args()
    t = today_jst()
    dates = a.date or [f"{t:%Y%m%d}", f"{t + dt.timedelta(days=1):%Y%m%d}"]
    for d in dates:
        run(d)


if __name__ == "__main__":
    main()
