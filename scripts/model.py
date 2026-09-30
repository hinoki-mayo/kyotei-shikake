"""全場対応の仕掛け予想モデル

・選手×コースごとに「どの決まり手で勝つか」「STはどれくらいか」を過去データから集計
・データが少ない選手は、その場のコース別傾向に寄せる(縮小推定)
・予想ST、実力、潰れ合い、攻め手なしを組み合わせて、各艇×各決まり手の確率を出す
・(round2) 展示タイム・モーター/ボートの調整率・天候水面・節間の勢いも追加の手がかりとして使う。
  展示タイム・天候はレース直前まで分からないので、まだ分かっていない項目は
  影響ゼロ(ニュートラル)にフォールバックする。
"""
import datetime as dt
import json

import numpy as np
import pandas as pd

from common import DATA, ROOT

PRM = json.loads((ROOT / "scripts" / "params.json").read_text())
M = PRM["moves"]
WC = ["w_" + m for m in M]
K, KS = PRM["K"], PRM["KS"]
EQUIP_K = 50    # モーター/ボートの勝率シュリンケージ
WTHR_K = 40     # 風向つき場・コース勝率のシュリンケージ
PTS = {"01": 10, "02": 8, "03": 6, "04": 4, "05": 2, "06": 1}
PT_NEUTRAL = sum(PTS.values()) / 6   # 節間データがまだ無い選手に当てる中立値
R2 = PRM.get("round2_features")      # round2の追加特徴量(無ければ従来通り動く)


def load_results(until: str, years: int = 6) -> pd.DataFrame:
    """until(YYYYMMDD)より前の成績を読み込む"""
    y = int(until[:4])
    frames = []
    cols = ["date", "jcd", "race", "rank", "toban", "course", "stv", "kimarite",
            "motor", "boat", "tenji", "weather", "wind_dir", "wind", "wave"]
    for yy in range(y - years, y + 1):
        p = DATA / "results" / f"{yy}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p, columns=cols))
    d = pd.concat(frames, ignore_index=True)
    d = d[(d.date < until) & d.stv.notna()].copy()
    d["course"] = d.course.astype(int)
    for m in M:
        d["w_" + m] = ((d["rank"] == "01") & (d.kimarite == m)).astype(float)
    return d


def _meeting_momentum(hist: pd.DataFrame) -> dict:
    """場ごとに、直近の連続開催日(=今開催中の節、当日は含まない)の
    選手別の平均得点を返す。{jcd: Series(toban -> 平均pt)}"""
    d2 = hist[["date", "jcd", "toban", "rank"]].copy()
    d2["pt"] = d2["rank"].map(PTS).fillna(0.0)
    out = {}
    for jcd, g in d2.groupby("jcd"):
        dates = sorted(g["date"].unique(), reverse=True)
        run, prev = [], None
        for ds in dates:
            d0 = dt.datetime.strptime(ds, "%Y%m%d")
            if prev is not None and (prev - d0).days != 1:
                break
            run.append(ds)
            prev = d0
        if not run:
            continue
        out[jcd] = g[g["date"].isin(run)].groupby("toban").pt.mean()
    return out


class Model:
    def __init__(self, hist: pd.DataFrame, today: str):
        h = hist
        # 選手×コースの勝ち方と平均ST
        g = h.groupby(["toban", "course"]).agg(n=("stv", "size"), ss=("stv", "sum"),
                                               **{c: (c, "sum") for c in WC}).reset_index()
        self.prof = g.set_index(["toban", "course"])
        # 場×コースの傾向(縮小先)
        self.vc = h.groupby(["jcd", "course"])[WC].mean()
        self.gc = h.groupby("course")[WC].mean()
        # 直近1年の選手平均ST
        one = (dt.datetime.strptime(today, "%Y%m%d") - dt.timedelta(days=365)).strftime("%Y%m%d")
        r = h[h.date >= one]
        self.gm = h.stv.mean()
        self.cm = h.groupby("course").stv.mean()
        ro = r.groupby("toban").stv.agg(["sum", "count"])
        self.rm = (ro["sum"] + KS * self.gm) / (ro["count"] + KS)
        # 実力(1着率を縮小)
        w = h.assign(win=(h["rank"] == "01").astype(float)).groupby("toban").win.agg(["sum", "count"])
        self.ab = (w["sum"] + 20 * 0.167) / (w["count"] + 20)
        # 今期F数
        y, mo = int(today[:4]), int(today[4:6])
        start = f"{y}0501" if 5 <= mo <= 10 else (f"{y}1101" if mo >= 11 else f"{y - 1}1101")
        cur = h[h.date >= start]
        self.fcnt = cur[cur.stv < 0].groupby("toban").size()

        if R2:
            win = (h["rank"] == "01").astype(float)
            h2 = h.assign(win=win)
            self.global_fb = float(win.mean()) if len(h2) else 1 / 6
            self.jcd_fb = h2.groupby("jcd").win.mean()
            self.motor = h2.groupby(["jcd", "motor"]).win.agg(["sum", "size"])
            self.boat = h2.groupby(["jcd", "boat"]).win.agg(["sum", "size"])
            self.wg = h.groupby(["jcd", "course", "wind_dir"]).agg(
                n=("stv", "size"), **{c: (c, "sum") for c in WC})
            self.momentum = _meeting_momentum(h)

    def _equip_edge(self, table, jcd, num):
        fb = self.jcd_fb.get(jcd, self.global_fb)
        if (jcd, num) in table.index:
            row = table.loc[(jcd, num)]
            rate = (row["sum"] + EQUIP_K * fb) / (row["size"] + EQUIP_K)
        else:
            rate = fb
        return float(np.log(rate + 1e-4) - np.log(fb + 1e-4))

    def _weather_rate(self, jcd, course, wind_dir, prior):
        if wind_dir is None or (jcd, course, wind_dir) not in self.wg.index:
            return prior
        row = self.wg.loc[(jcd, course, wind_dir)]
        return (row[WC].values + WTHR_K * prior) / (row["n"] + WTHR_K)

    def race(self, jcd: str, entries: list, weather: dict = None):
        """entries: [{'course':1..6, 'toban':'4444', 'motor':.., 'boat':.., 'tenji':...}, ...] コース順
        weather: {'wind_dir':.., 'wind':.., 'wave':.., 'rain':bool} まだ分からなければNone"""
        rate = np.zeros((6, 4))
        wrate = np.zeros((6, 4))
        st = np.zeros(6)
        ab = np.zeros(6)
        fc = np.zeros(6, dtype=int)
        tenji = np.zeros(6)
        motor_edge = np.zeros(6)
        boat_edge = np.zeros(6)
        momentum = np.full(6, PT_NEUTRAL)
        have_tenji = R2 and all(e.get("tenji") for e in entries)
        wind_dir = weather.get("wind_dir") if (R2 and weather) else None
        for i, e in enumerate(entries):
            c, t = e["course"], e["toban"]
            prior = self.vc.loc[(jcd, c)].values if (jcd, c) in self.vc.index else self.gc.loc[c].values
            if (t, c) in self.prof.index:
                p = self.prof.loc[(t, c)]
                rate[i] = (p[WC].values + K * prior) / (p.n + K)
                base = self.rm.get(t, self.gm) + self.cm[c] - self.gm
                stp = (p.ss + KS * base) / (p.n + KS)
            else:
                rate[i] = prior
                stp = self.rm.get(t, self.gm) + self.cm[c] - self.gm
            fc[i] = int(self.fcnt.get(t, 0))
            s = PRM["st"]
            st[i] = s["a"] + s["b"] * stp + s["f1"] * (fc[i] == 1) + s["f2"] * (fc[i] >= 2)
            ab[i] = np.log(self.ab.get(t, 0.12))
            if R2:
                wrate[i] = self._weather_rate(jcd, c, wind_dir, prior)
                if have_tenji:
                    tenji[i] = e["tenji"]
                motor_edge[i] = self._equip_edge(self.motor, jcd, e.get("motor")) if e.get("motor") else 0.0
                boat_edge[i] = self._equip_edge(self.boat, jcd, e.get("boat")) if e.get("boat") else 0.0
                momentum[i] = self.momentum.get(jcd, {}).get(t, PT_NEUTRAL)
        extra = None
        if R2:
            extra = dict(tenji=tenji if have_tenji else None, wrate=wrate,
                         motor_edge=motor_edge, boat_edge=boat_edge, momentum=momentum,
                         wind=(weather or {}).get("wind", 0.0) if weather else 0.0,
                         wave=(weather or {}).get("wave", 0.0) if weather else 0.0,
                         rain=float((weather or {}).get("rain", False)) if weather else 0.0)
        return self._probs(rate, st, ab, extra), st, fc, rate

    @staticmethod
    def _probs(rate, st, ab, extra=None):
        inn = np.r_[st[0], st[:-1]]
        out = np.r_[st[1:], st[-1]]
        d_in, d_mean, d_out = inn - st, st.mean() - st, out - st
        abc = ab - ab.mean()
        thr = np.array(PRM["makuri_thr"])
        mk = (rate[:, 1] + rate[:, 3]) >= thr
        clash = float(mk[2] and mk[3]) * (1 + 10 * max(st[2] - st[3], 0))
        clash *= 1 - np.clip(max(abc[2], abc[3]), 0, 1)
        cl = np.zeros(6)
        cl[4] = cl[5] = clash
        no = np.zeros(6)
        for i in range(3, 6):
            no[i] = float(not mk[1:i].any())

        if R2 and extra is not None:
            p = np.array(R2["theta"])
            a0, a1 = p[:4], p[4:8]
            b = p[8:60].reshape(-1, 4)
            tenji_z = np.zeros(6)
            if extra["tenji"] is not None:
                tj = extra["tenji"]
                sd = tj.std() + 1e-3
                tenji_z = (tj.mean() - tj) / sd
            mom = extra["momentum"] / 3.0
            mom_z = mom - mom.mean()
            wind_b = np.full(6, extra["wind"] / 5.0)
            wave_b = np.full(6, extra["wave"] / 10.0)
            rain_b = np.full(6, extra["rain"])
            feats = (d_in, d_mean, d_out, abc, cl, no, tenji_z,
                     extra["motor_edge"], extra["boat_edge"], wind_b, wave_b, rain_b, mom_z)
            s = a0 * np.log(rate + 1e-4) + a1 * np.log(extra["wrate"] + 1e-4)
            for j, f in enumerate(feats):
                s = s + b[j] * f[:, None]
        else:
            p = np.array(PRM["logit"])
            a, b = p[:4], p[4:].reshape(-1, 4)
            s = a * np.log(rate + 1e-4)
            for j, f in enumerate((d_in, d_mean, d_out, abc, cl, no)):
                s = s + b[j] * f[:, None]
        s[1:, 0] = -np.inf   # 逃げは1コースだけ
        s[0, 1:] = -np.inf   # 1コースは逃げ(抜き・恵まれは除外)
        e = np.exp(s - s[np.isfinite(s)].max())
        e[~np.isfinite(s)] = 0
        return e / e.sum()
