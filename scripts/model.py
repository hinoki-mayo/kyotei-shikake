"""全場対応の仕掛け予想モデル

・選手×コースごとに「どの決まり手で勝つか」「STはどれくらいか」を過去データから集計
・データが少ない選手は、その場のコース別傾向に寄せる(縮小推定)
・予想ST、実力、潰れ合い、攻め手なしを組み合わせて、各艇×各決まり手の確率を出す
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


def load_results(until: str, years: int = 6) -> pd.DataFrame:
    """until(YYYYMMDD)より前の成績を読み込む"""
    y = int(until[:4])
    frames = []
    for yy in range(y - years, y + 1):
        p = DATA / "results" / f"{yy}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p, columns=["date", "jcd", "race", "rank", "toban", "course",
                                                      "stv", "kimarite"]))
    d = pd.concat(frames, ignore_index=True)
    d = d[(d.date < until) & d.stv.notna()].copy()
    d["course"] = d.course.astype(int)
    for m in M:
        d["w_" + m] = ((d["rank"] == "01") & (d.kimarite == m)).astype(float)
    return d


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
        y, m = int(today[:4]), int(today[4:6])
        start = f"{y}0501" if 5 <= m <= 10 else (f"{y}1101" if m >= 11 else f"{y - 1}1101")
        cur = h[h.date >= start]
        self.fcnt = cur[cur.stv < 0].groupby("toban").size()

    def race(self, jcd: str, entries: list):
        """entries: [{'course':1..6, 'toban':'4444'}, ...] コース順"""
        rate = np.zeros((6, 4))
        st = np.zeros(6)
        ab = np.zeros(6)
        fc = np.zeros(6, dtype=int)
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
        return self._probs(rate, st, ab), st, fc, rate

    @staticmethod
    def _probs(rate, st, ab):
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
