"""別会社「ズレ屋」(記録だけ): 市場の見込みと結果のズレだけを学ばせたモデルで、3連単の目を選んで記録する

・モデル: data/models/zure_v1.pkl (2024〜2025年で学習。2026年1〜10月の答え合わせで決めたルールを11/3から固定)
  1着・2着・3着それぞれ「市場の見込みより来そうか」を出し、3連単の目ごとに 1着×2着×3着 を掛けた点数にする
・市場の見込み: 締切45秒前のオッズ(data/bets の stages["直前"])。45秒前が無いレースは買わない
・ルール: 点数1.3以上・45秒前のオッズ100倍未満の目を全部、1点100円
・手がかり: 出走表・展示(進入・展示ST・展示タイム・風波)・選手のコース別成績(前2年)・節間の成績・当日の水面の流れ
  (その日それまでのレースのイン1着率・同じコースの1着数)・オリ展(取れている場だけ)
・外の嗅覚(11/4から): 4〜6コースが1着になる見込みを市場と比べ(外比)、1.2以上のレースで、外が頭・点数1.0以上・45秒前300倍未満の目を1点100円
・保存: data/zure/<日付>.json {レース: {"picks": [[目, 45秒前オッズ, 点数], ...], "res": 決まった目, "pay": 100円あたりの払戻, "orig": オリ展あり,
  "soto": 外比, "soto_picks": [[目, 45秒前オッズ, 点数], ...], "hm": [B隠れまくりの枠], "hm_picks": [[目, オッズ], ...], "hmo_picks": [...],
  "rank": 堅さのランク, "ab_picks": [[目, オッズ, 点数], ...]}}
・その日の結果が全部出てから(夜)まとめて作る。使うのはレース前に出ていた情報だけ(当日の流れはそのレースより前のレースの結果だけ)

例: python scripts/zure.py 20261103   (日付を省くと昨日と今日)
"""
import datetime as dt
import json
import pickle
import sys

import numpy as np
import pandas as pd

import bet as bet_mod
from common import DATA, now_jst

MODEL = DATA / "models" / "zure_v1.pkl"
SOTO_MODEL = DATA / "models" / "soto_v1.pkl"   # 外の嗅覚: 4〜6コースが1着になるかをレースごとに学んだモデル(2024〜2025年)
SOTO_MIN, SOTO_SC_MIN, SOTO_ODDS_MAX = 1.2, 1.0, 300.0   # 外比1.2以上のレースで、外が頭・点数1.0以上・300倍未満の目
SOTO_BF = ["est", "est_rank", "est_in", "tenji", "tenji_rk", "nat_win", "loc_win", "nat_2r", "motor_2r", "boat_2r", "grade_n", "n_c", "w_c", "atk_c",
           "sa_c", "r2_c", "stc_c", "f_pts", "f_last", "mh", "ms", "mt", "lap_rk", "mawari_rk", "choku_rk", "lap_dv", "mawari_dv", "choku_dv", "age", "weight"]
SOTO_RF = ["wind", "wave", "jcd_n", "in_today", "n_today", "venue_c"]
# B隠れまくり(11/5から): 3〜5コース・B級・そのコースのまくり率12%以上(10走以上)・展示STが内側より遅い か 4位以下 の艇
#   本線: その艇が頭・45秒前100倍未満の目を全部 / オリ展つき: その艇の直線が1〜4位なら300倍未満まで
HM_ATK, HM_ODDS, HMO_ODDS = 0.12, 100.0, 300.0
# ランク×鼻(11/5から): サイトの堅さのランクがA・Bで外比1.2以上のレースは、2・3コースが頭・点数1.0以上・45秒前100倍未満の目
#   (2026年の確かめで A 107%・B 132%)。消し: 外比0.8以下のレースの外頭(4〜6コース)はどのランクでも59〜71%なので記録だけ別に数える
RANKS = (("S", 0.5), ("A", 0.4), ("B", 0.3), ("C", 0.0))   # build_site.RANKS と同じ(おすすめ5点の確率の合計)
AB_SOTO, AB_SC, AB_ODDS = 1.2, 1.0, 100.0
# ズレ屋のまとめ(11/5から): 次の5つを合わせて買う(重なった目は1回)。確定オッズで2025年 119.7%・2026年 112.0%
#   ① hmo_picks  ② z2_picks: B隠れまくりが頭・100倍未満・2着にオリ展の遅い艇(一周5位以下かまわり足6位)が無い(オリ展のある場)
#   ③ z3_picks: 総合点1.65以上・100倍未満。総合点=点数×(B隠れまくりが頭1.25、その直線1〜4位でさらに1.2・5〜6位なら0.8)
#               ×(2着にオリ展の遅い艇0.85、3着に0.9)×(外比1.2以上のレースの外頭は外比(1〜1.5))
#   ④ ab_picks  ⑤ z5_picks: インが頭・点数1.4以上・100倍未満
Z3_MIN, Z5_SC = 1.65, 1.4
OUT = DATA / "zure"
SCORE_MIN, ODDS_MAX, UNIT = 1.3, 100.0, 100
SINCE = "20261103"   # この日からが本番の記録(前の日の分は参考)
GRADE_C = {"A1": 0, "A2": 1, "B1": 2, "B2": 3}
GRADE_N = {"A1": 4, "A2": 3, "B1": 2, "B2": 1}
PTS = {1: 10, 2: 8, 3: 6, 4: 4, 5: 2, 6: 1}
K3 = ["-".join(str(i + 1) for i in t) for t in bet_mod.ODDS_ORDER]


def _results(years):
    out = []
    for y in years:
        p = DATA / "results" / f"{y}.parquet"
        if p.exists():
            import pyarrow.parquet as pq
            have = set(pq.read_schema(p).names)
            cols = ["date", "jcd", "race", "rank", "waku", "toban", "course", "st", "kimarite", "combo3t", "payout3t"]
            out.append(pd.read_parquet(p, columns=[c for c in cols if c in have]))
    r = pd.concat(out, ignore_index=True)
    for c in ("course", "st", "waku"):
        r[c] = pd.to_numeric(r[c], errors="coerce")
    r["fin"] = pd.to_numeric(r["rank"].astype(str).str.lstrip("0"), errors="coerce")
    r["race"] = r.race.astype(int)
    return r


def _profiles(y):
    """選手のコース別成績と、場×コースの1着率(前2年)"""
    P = _results((y - 2, y - 1))
    P = P[P.course.between(1, 6)].copy()
    P["win"] = P.fin == 1
    P["atk"] = P.win & P.kimarite.isin(["まくり", "まくり差し"])
    P["sa"] = P.win & P.kimarite.isin(["差し", "まくり差し"])
    P["r2"] = P.fin == 2
    prof = P.groupby(["toban", "course"]).agg(n_c=("win", "size"), w_c=("win", "mean"), atk_c=("atk", "mean"), sa_c=("sa", "mean"),
                                              r2_c=("r2", "mean"), stc_c=("st", "mean")).reset_index()
    vb = P.groupby(["jcd", "course"]).win.mean().rename("venue_c").reset_index()
    return prof, vb


def _before(date, source):
    """展示: entries(本番) か before_hist(確かめ用) → [(jcd, race, order, est, tenji, wind, wave)]"""
    rows = []
    if source == "before_hist":
        bh = pd.read_parquet(DATA / "before_hist" / f"{date}.parquet")
        for b in bh.itertuples():
            rows.append((f"{int(b.jcd):02d}", int(b.race), None if b.order is None else list(b.order), None if b.est is None else list(b.est),
                         None if b.tenji is None else list(b.tenji), b.wind, b.wave))
    else:
        p = DATA / "entries" / f"{date}.json"
        E = json.loads(p.read_text()) if p.exists() else {}
        for k, e in E.items():
            if isinstance(e, dict):
                est = e.get("est")
                rows.append((k[:2], int(k[3:]), e.get("order"), None if not est else [np.nan if x is None else x for x in est],
                             e.get("tenji"), e.get("wind"), e.get("wave")))
    return rows


def _orig(date):
    rows = []
    for f in (DATA / "orig_race").glob(f"*/{date}.json"):
        jcd = f.parent.name
        for race, o in json.loads(f.read_text()).items():
            if len(o) != 6:
                continue
            for w, v in o.items():
                rows.append(dict(jcd=jcd, race=int(race), waku=int(w), lap=v.get("一周"), mawari=v.get("まわり足"), choku=v.get("直線")))
    O = pd.DataFrame(rows, columns=["jcd", "race", "waku", "lap", "mawari", "choku"])
    if O.empty:
        return O
    g = O.groupby(["jcd", "race"])
    for c in ("lap", "mawari", "choku"):
        O[c] = pd.to_numeric(O[c], errors="coerce")
        O[c + "_rk"] = g[c].rank(method="min")
        O[c + "_dv"] = O[c] - g[c].transform("mean")
        O[c + "_gap1"] = O[c] - g[c].transform("min")
    return O


def market(date, source):
    """{(jcd, race): (o3 dict 目→オッズ, 1着・2着・3着の見込み[6]×3)}。本番は45秒前、確かめ用は確定オッズ"""
    out = {}
    if source == "before_hist":
        import replay_hist
        for key, (o3, _o2) in replay_hist.odds_hist(date).items():
            o = {f"{a + 1}-{b + 1}-{c + 1}": v for (a, b, c), v in o3.items()}
            out[(key[:2], int(key[3:]))] = o
    else:
        p = DATA / "bets" / f"{date}.json"
        B = json.loads(p.read_text()) if p.exists() else {}
        for key, b in B.items():
            s45 = ((b or {}).get("stages") or {}).get("直前")
            if s45 and s45.get("o3"):
                out[(key[:2], int(key[3:]))] = {c: v for c, v in zip(K3, s45["o3"]) if v}
    res = {}
    for k, o in out.items():
        if len(o) < 100:
            continue
        inv = {c: 1 / v for c, v in o.items() if v and v > 0}
        z = sum(inv.values())
        m = np.zeros((3, 6))
        for c, q in inv.items():
            for pos, w in enumerate(c.split("-")):
                m[pos, int(w) - 1] += q / z
        res[k] = (o, m)
    return res


def features(date, source="entries"):
    y = int(date[:4])
    prof, vb = _profiles(y)
    R = _results((y - 1, y))
    cur = R[R.date <= date]
    pg = pd.read_parquet(DATA / "programs" / f"{y}.parquet",
                         columns=["date", "jcd", "race", "waku", "toban", "grade", "age", "weight", "nat_win", "loc_win", "nat_2r", "motor_2r", "boat_2r"])
    pg = pg[pg.date == date].copy()
    pg["waku"] = pd.to_numeric(pg.waku, errors="coerce")
    pg["race"] = pg.race.astype(int)
    pg["grade_n"] = pg.grade.map(GRADE_N).fillna(1.5)
    mk = market(date, source)
    rows = []
    for jcd, race, order, est, tj, wind, wave in _before(date, source):
        if not order or len(order) != 6 or est is None or len(est) != 6 or (jcd, race) not in mk:
            continue
        est = np.asarray(est, dtype=float)
        if np.isnan(est).any():
            continue
        tj = np.asarray(tj, dtype=float) if tj is not None and len(tj) == 6 else np.full(6, np.nan)
        crs = {int(w): i + 1 for i, w in enumerate(order)}
        m = mk[(jcd, race)][1]
        for w in range(1, 7):
            c = crs.get(w)
            inner = [ww for ww, cc in crs.items() if cc == c - 1]
            rows.append(dict(date=date, jcd=jcd, race=race, waku=w, course=c,
                             est=est[w - 1], est_rank=int((est < est[w - 1]).sum()) + 1, est_in=est[w - 1] - (est[inner[0] - 1] if inner else np.nan),
                             est_dev=est[w - 1] - est.mean(), tenji=tj[w - 1], tenji_dev=tj[w - 1] - np.nanmin(tj) if not np.isnan(tj).all() else np.nan,
                             wind=wind, wave=wave, mh=m[0, w - 1], ms=m[1, w - 1], mt=m[2, w - 1]))
    D = pd.DataFrame(rows)
    if D.empty:
        return D
    D = D.merge(pg, on=["date", "jcd", "race", "waku"], how="left")
    D = D.merge(prof, on=["toban", "course"], how="left").merge(vb, on=["jcd", "course"], how="left")
    # 節間(前6日の同じ場)
    d0 = (dt.datetime.strptime(date, "%Y%m%d") - dt.timedelta(days=6)).strftime("%Y%m%d")
    past = cur[(cur.date >= d0) & (cur.date < date)].copy()
    past["pts"] = past.fin.map(PTS)
    form = past.sort_values(["date", "race"]).groupby(["jcd", "toban"]).agg(f_pts=("pts", "mean"), f_n=("pts", "size"), f_last=("fin", "last")).reset_index()
    D = D.merge(form, on=["jcd", "toban"], how="left")
    D["key"] = D.jcd + "-" + D.race.map("{:02d}".format)
    g = D.groupby(["date", "key"])
    for c in ["nat_win", "loc_win", "motor_2r", "boat_2r", "tenji", "est"]:
        D[c + "_rk"] = g[c].rank(ascending=c in ("tenji", "est"))
        D[c + "_dv"] = D[c] - g[c].transform("mean")
    # 当日の流れ: そのレースより前のレースの結果だけ
    td = cur[cur.date == date]
    tw = td[td.fin == 1][["jcd", "race", "course"]].rename(columns={"course": "wcrs"})
    ins, crs_t, n_t = [], [], []
    for r in D.itertuples():
        e = tw[(tw.jcd == r.jcd) & (tw.race < r.race)]
        n = len(e)
        ins.append((e.wcrs == 1).mean() if n else np.nan)
        crs_t.append(float((e.wcrs == r.course).sum()) if n else np.nan)
        n_t.append(n)
    D["in_today"], D["crs_today"], D["n_today"] = ins, crs_t, n_t
    for c in ("mh", "ms", "mt"):
        x = D[c].clip(1e-4, 1 - 1e-4)
        D["lg_" + c] = np.log(x / (1 - x))
    D["jcd_n"] = D.jcd.astype(int)
    D["grade_c"] = D.grade.map(GRADE_C)
    O = _orig(date)
    if O.empty:
        for c in ("lap", "mawari", "choku"):
            for s in ("", "_rk", "_dv", "_gap1"):
                D[c + s] = np.nan
    else:
        D = D.merge(O, on=["jcd", "race", "waku"], how="left")
    D["has_o"] = D.lap.notna() | D.mawari.notna()
    return D, mk


def race_ranks(date):
    """サイトの予想ページと同じ堅さのランク {(jcd, race): "S"/"A"/"B"/"C"}"""
    import race_view
    pp = DATA / "predictions" / f"{date}.json"
    if not pp.exists():
        return {}
    preds = json.loads(pp.read_text()).get("races", {})
    odds = race_view.load_odds(date)
    pe = DATA / "entries" / f"{date}.json"
    ent = json.loads(pe.read_text()) if pe.exists() else {}
    out = {}
    for k, pred in preds.items():
        if pred.get("version") != "final":
            continue
        try:
            lv = ent.get(k)
            vw = race_view.view(pred, date, odds.get(k), lv if isinstance(lv, dict) else None)
        except Exception:
            continue
        if vw:
            p5 = sum(p for _, p in vw["top3"][:5])
            out[(k[:2], int(k[3:]))] = next(r for r, th in RANKS if p5 >= th)
    return out


def soto_ratio(D):
    """レースごとの外比(外の嗅覚の見込み ÷ 市場の見込み)。{(jcd, race): 外比}"""
    md, F = pickle.load(open(SOTO_MODEL, "rb"))
    d = D[D.course.between(1, 6)]
    d = d[d.groupby(["jcd", "race"]).course.transform("nunique") == 6]
    if d.empty:
        return {}
    w = d.pivot_table(index=["jcd", "race"], columns="course", values=SOTO_BF, aggfunc="first", dropna=False)
    w.columns = [f"{a}_c{b}" for a, b in w.columns]
    W = w.join(d[d.course == 1].set_index(["jcd", "race"])[SOTO_RF])
    W["m_out"] = W[["mh_c4", "mh_c5", "mh_c6"]].sum(axis=1)
    W["lg_out"] = np.log(W.m_out.clip(1e-4) / (1 - W.m_out.clip(None, 0.9999)))
    for c in F:
        if c not in W:
            W[c] = np.nan
    p = md.predict_proba(W[F])[:, 1]
    return {k: float(v) for k, v in zip(W.index, p / W.m_out.values)}


def picks(date, source="entries"):
    M, F = pickle.load(open(MODEL, "rb"))
    got = features(date, source)
    if not isinstance(got, tuple):
        return {}
    D, mk = got
    for t, m in (("y1", "mh"), ("y2", "ms"), ("y3", "mt")):
        D["r" + t[1]] = M[t].predict_proba(D[F])[:, 1] / D[m]
    soto = soto_ratio(D)
    ranks = race_ranks(date)
    R = _results((int(date[:4]),))
    R = R[R.date == date].drop_duplicates(["jcd", "race"]).set_index(["jcd", "race"])
    out = {}
    for (jcd, race), d in D.groupby(["jcd", "race"]):
        if len(d) != 6:
            continue
        r = {int(w): (a, b, c) for w, a, b, c in zip(d.waku, d.r1, d.r2, d.r3)}
        o3 = mk[(jcd, race)][0]
        pk = []
        for combo, od in o3.items():
            a, b, c = (int(x) for x in combo.split("-"))
            sc = r[a][0] * r[b][1] * r[c][2]
            if sc >= SCORE_MIN and od < ODDS_MAX:
                pk.append([combo, od, round(float(sc), 3)])
        rec = {"picks": sorted(pk, key=lambda x: -x[2]), "orig": bool(d.has_o.any())}
        rk_o = {int(x.waku): (x.lap_rk, x.mawari_rk, x.choku_rk) for x in d.itertuples()}
        slow = {w for w, (l, m, _) in rk_o.items() if (pd.notna(l) and l >= 5) or (pd.notna(m) and m >= 6)}
        hm = [int(x.waku) for x in d.itertuples() if 3 <= x.course <= 5 and (x.n_c or 0) >= 10 and (x.atk_c or 0) >= HM_ATK
              and x.grade_n <= 2 and (x.est_in > 0 or x.est_rank >= 4)]
        if hm:
            chk = {int(x.waku): x.choku_rk for x in d.itertuples()}
            rec["hm"] = hm
            rec["hm_picks"] = sorted([[c, od] for c, od in o3.items() if int(c[0]) in hm and od < HM_ODDS], key=lambda x: x[1])
            hmo = [w for w in hm if pd.notna(chk.get(w)) and chk[w] <= 4]
            if hmo:
                rec["hmo_picks"] = sorted([[c, od] for c, od in o3.items() if int(c[0]) in hmo and od < HMO_ODDS], key=lambda x: x[1])
        so = soto.get((jcd, race))
        rk = ranks.get((jcd, race))
        if rk:
            rec["rank"] = rk
        if so is not None and rk in ("A", "B") and so >= AB_SOTO:
            crs = dict(zip(d.waku.astype(int), d.course))
            ab = []
            for combo, od in o3.items():
                a, b, c = (int(x) for x in combo.split("-"))
                sc = r[a][0] * r[b][1] * r[c][2]
                if crs.get(a) in (2, 3) and sc >= AB_SC and od < AB_ODDS:
                    ab.append([combo, od, round(float(sc), 3)])
            if ab:
                rec["ab_picks"] = sorted(ab, key=lambda x: -x[2])
        crs_all = dict(zip(d.waku.astype(int), d.course))
        hmset = set(rec.get("hm", []))
        z2, z3, z5 = [], [], []
        for combo, od in o3.items():
            a, b, c = (int(x) for x in combo.split("-"))
            sc = r[a][0] * r[b][1] * r[c][2]
            if a in hmset and od < HM_ODDS and pd.notna(rk_o[a][2]) and b not in slow:
                z2.append([combo, od])
            m = 1.0
            if a in hmset:
                m *= 1.25
                ch = rk_o[a][2]
                if pd.notna(ch):
                    m *= 1.2 if ch <= 4 else 0.8
            m *= (0.85 if b in slow else 1.0) * (0.9 if c in slow else 1.0)
            if so is not None and so >= 1.2 and crs_all.get(a, 0) >= 4:
                m *= min(max(so, 1.0), 1.5)
            if od < 100 and sc * m >= Z3_MIN:
                z3.append([combo, od, round(float(sc * m), 3)])
            if crs_all.get(a) == 1 and sc >= Z5_SC and od < 100:
                z5.append([combo, od, round(float(sc), 3)])
        for key, v in (("z2_picks", z2), ("z3_picks", z3), ("z5_picks", z5)):
            if v:
                rec[key] = sorted(v, key=lambda x: x[1])
        if so is not None:
            rec["soto"] = round(so, 3)
            if so >= SOTO_MIN:
                crs = dict(zip(d.waku.astype(int), d.course))
                sp = []
                for combo, od in o3.items():
                    a, b, c = (int(x) for x in combo.split("-"))
                    sc = r[a][0] * r[b][1] * r[c][2]
                    if crs.get(a, 0) >= 4 and sc >= SOTO_SC_MIN and od < SOTO_ODDS_MAX:
                        sp.append([combo, od, round(float(sc), 3)])
                rec["soto_picks"] = sorted(sp, key=lambda x: -x[2])
        mt = {}
        for key in ("hmo_picks", "z2_picks", "z3_picks", "ab_picks", "z5_picks"):
            for x in rec.get(key, []):
                mt.setdefault(x[0], x[1])
        if mt:
            rec["matome"] = sorted(([c, o] for c, o in mt.items()), key=lambda x: x[1])
        if (jcd, race) in R.index:
            x = R.loc[(jcd, race)]
            if isinstance(x.combo3t, str):
                rec["res"], rec["pay"] = x.combo3t, int(x.payout3t) if pd.notna(x.payout3t) else 0
        out[f"{jcd}-{race:02d}"] = rec
    return out


def main(argv):
    dates = argv or [(now_jst() - dt.timedelta(days=1)).strftime("%Y%m%d"), now_jst().strftime("%Y%m%d")]
    OUT.mkdir(parents=True, exist_ok=True)
    for date in dates:
        pk = picks(date)
        if not pk:
            print(date, "なし")
            continue
        (OUT / f"{date}.json").write_text(json.dumps(pk, ensure_ascii=False, separators=(",", ":")))
        n = sum(len(v["picks"]) for v in pk.values())
        hit = sum(v.get("pay", 0) for v in pk.values() for c, *_ in v["picks"] if c == v.get("res"))
        print(f"{date}: {len(pk)}レース {sum(1 for v in pk.values() if v['picks'])}レースで{n}点 投資{n * UNIT:,}円 払戻{hit:,}円")
        sn = sum(len(v.get("soto_picks", [])) for v in pk.values())
        sh = sum(v.get("pay", 0) for v in pk.values() for c, *_ in v.get("soto_picks", []) if c == v.get("res"))
        print(f"  外の嗅覚: {sum(1 for v in pk.values() if v.get('soto_picks'))}レースで{sn}点 投資{sn * UNIT:,}円 払戻{sh:,}円")
        for key, nm in (("hm_picks", "B隠れまくり"), ("hmo_picks", "B隠れまくり(オリ展つき)"), ("ab_picks", "A・B×鼻で2・3コース頭"),
                         ("z2_picks", "②隠れまくり・2着オリ展"), ("z3_picks", "③総合点1.65以上"), ("z5_picks", "⑤イン頭・点数1.4以上"), ("matome", "★ズレ屋のまとめ")):
            hn = sum(len(v.get(key, [])) for v in pk.values())
            hh = sum(v.get("pay", 0) for v in pk.values() for c, *_ in v.get(key, []) if c == v.get("res"))
            print(f"  {nm}: {sum(1 for v in pk.values() if v.get(key))}レースで{hn}点 投資{hn * UNIT:,}円 払戻{hh:,}円")


if __name__ == "__main__":
    main(sys.argv[1:])
