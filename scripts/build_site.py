"""予想データからサイト(静的HTML)を作る。出力先は site/

構成
・トップ / 日付ページ : 24場のマス目。展開予想が出た場は色付き「展開予想！」
・場ページ           : 1R〜12Rの一覧。展開予想が出たレースを強調
・レースページ       : 出走表 ／ スタートスリット ／ 1マーク の3タブ(それぞれ別ページ)
広告は ads/ フォルダのタグを決まった位置に差し込む(図の上や途中には置かない)
"""
import datetime as dt
import functools
import html
import json
import os
import pathlib
import shutil

import pandas as pd

import bet as bet_mod
import flex
import org_tree
import race_view
import shadow_staff
import live_result
import share
from common import DATA, ROOT, now_jst
from draw import slit_svg, turn_svg
from parse import VENUES

CFG = json.loads((ROOT / "site_config.json").read_text())
for _key, _file in (("ad_head", "head.html"), ("ad_slot", "slot.html"), ("ads_txt", "ads.txt")):
    _p = ROOT / "ads" / _file
    if _p.exists() and _p.read_text().strip():
        CFG[_key] = _p.read_text().strip()

OUT = pathlib.Path(os.environ.get("SITE_OUT") or ROOT / "site")   # 購入係は裏で別の場所に作ってから差し替える
BC = ["#FFFFFF", "#222222", "#D9453F", "#3A7FD5", "#E8A83A", "#4E9A3E"]
TC = ["#222", "#fff", "#fff", "#fff", "#222", "#fff"]
WD = "月火水木金土日"
PTS = {"01": 10, "02": 8, "03": 6, "04": 4, "05": 2, "06": 1}
DAYS_BACK = 0

CSS = """
:root{--shadow:0 1px 2px rgba(16,24,40,.05);--herobd:transparent;--bg:#f4f5f7;--card:#fff;--tx:#1f2328;--sub:#6b7079;--bd:#e3e5e9;--navy:#1B2A4A;--ac:#185FA5;--hot:#E8742E;--red:#A32D2D;--green:#0F6E56;--off:#eceef1;--gain:#2A6FDB;--loss:#C7443A;--mark:#FFF1C9}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f1114;--card:#191c21;--tx:#eceef1;--sub:#a1a7b0;--bd:#2a2f37;--ac:#8EC0F2;--off:#22262d;--gain:#5B95EC;--loss:#E8705F;--mark:#4A3D14;--navy:#151f33;--shadow:none;--herobd:#2c3d63;--red:#EE7B7B;--green:#2FA57F}}
:root[data-theme=dark]{--bg:#0f1114;--card:#191c21;--tx:#eceef1;--sub:#a1a7b0;--bd:#2a2f37;--ac:#8EC0F2;--off:#22262d;--gain:#5B95EC;--loss:#E8705F;--mark:#4A3D14;--navy:#151f33;--shadow:none;--herobd:#2c3d63;--red:#EE7B7B;--green:#2FA57F}
*{box-sizing:border-box}html{color-scheme:light dark}:root[data-theme=light]{color-scheme:light}:root[data-theme=dark]{color-scheme:dark}
body{margin:0;background:var(--bg);color:var(--tx);font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans','Hiragino Kaku Gothic ProN','Yu Gothic',Meiryo,sans-serif;line-height:1.6;
-webkit-text-size-adjust:100%}
a{color:inherit;text-decoration:none}
header{position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;background:var(--navy);color:#fff;padding:0 16px;height:48px;font-weight:700;font-size:16px}
.thm{background:rgba(255,255,255,.12);color:#fff;border:0;border-radius:16px;padding:5px 12px;font:inherit;font-size:12px;font-weight:700;letter-spacing:.02em;cursor:pointer}
main{max-width:760px;margin:0 auto;padding:10px 14px}h1{font-size:20px;font-weight:700;line-height:1.4;margin:12px 0 8px}
h2{font-size:16px;font-weight:700;margin:20px 0 8px}
.sub{color:var(--sub);font-size:13px}.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:12px 14px;margin:10px 0;box-shadow:var(--shadow)}
.pc,.dl,.tot-num,.pc-roi,.rno,.nums,.org-stat,.res .sub{font-variant-numeric:tabular-nums}
.dnav{display:flex;justify-content:space-between;align-items:center;margin:8px 0}.dnav a,.dnav span.x{background:var(--card);border:1px solid var(--bd);border-radius:20px;padding:4px 14px;font-size:14px}
.dnav span.x{opacity:.35}
.grid{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--bd);border-radius:6px;overflow:hidden;background:var(--bd);gap:1px}
.tile{position:relative;background:var(--card);min-height:92px;padding:6px 4px;text-align:center;display:flex;flex-direction:column;justify-content:center}
.headb{position:absolute;top:-8px;right:-6px;width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;border:2px solid var(--card);box-shadow:0 1px 3px rgba(0,0,0,.3)}
.tile b{font-size:16px}.tile .d{font-size:12px;color:var(--sub)}.tile .st{font-size:12px;font-weight:700;color:var(--sub)}
.tile.none{background:var(--off);color:var(--sub);opacity:.55}.tile.none b{font-weight:500}
.tile.hot{background:var(--hot);color:#fff}.tile.hot .d,.tile.hot .st{color:#fff}
.tile.done{opacity:.6}.tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:4px;margin:1px;color:#fff;background:#6b7a90}
.hotb{display:inline-block;background:#fff;color:var(--hot);font-size:11px;font-weight:700;border-radius:10px;padding:0 8px;margin-top:2px}
.list a{display:flex;gap:10px;align-items:center;padding:10px 4px;border-bottom:1px solid var(--bd)}.list a:last-child{border:0}
.rno{width:46px;font-weight:700;font-size:16px}.rst{margin-left:auto;font-size:12px;font-weight:700;border-radius:12px;padding:2px 10px;white-space:nowrap}
.s-hot{background:var(--hot);color:#fff}.s-wait{background:var(--off);color:var(--sub)}.s-done{color:var(--sub)}
.tabs{display:flex;border-bottom:2px solid var(--bd);margin:8px -14px;padding:0 14px;position:sticky;top:48px;z-index:10;background:var(--bg)}.tabs a{flex:1 1 auto;min-width:0;text-align:center;padding:10px 0;font-size:12.5px;font-weight:700;color:var(--sub);white-space:nowrap}
.tabs a.on{color:var(--tx);border-bottom:3px solid var(--hot);margin-bottom:-2px}.tabs a .lk{font-size:10px;font-weight:500;white-space:normal;display:block;line-height:1.3}
.viewrow{display:flex;gap:6px;margin:10px 0}.viewbtn{flex:1;text-align:center;padding:9px 0;border:1px solid var(--bd);background:var(--card);border-radius:10px;font-size:13px;font-weight:700;color:var(--sub);cursor:pointer}
.viewbtn.on{background:var(--hot);color:#fff;border-color:var(--hot)}
.total-card{padding:16px 16px 10px}.tot-num{font-size:30px;font-weight:800;margin:2px 0}.tot-chart{margin-top:6px}
.plan-grid{display:grid;grid-template-columns:1fr;gap:10px;margin:10px 0}
.plan-card{display:block;background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:12px 14px;text-decoration:none;color:var(--tx)}
.pc-head{display:flex;justify-content:space-between;align-items:baseline}.pc-head b{font-size:14.5px}
.pc-roi{font-size:18px;font-weight:800}.pc-chart{margin:6px 0 2px}.pc-foot{display:flex;justify-content:space-between}
.pc-split{margin-top:8px;border-top:1px solid var(--bd);padding-top:4px}.pc-srow{display:grid;grid-template-columns:1fr auto 3.2em;gap:8px;font-size:13px;padding:2px 0;align-items:baseline}.pc-srow b{text-align:right}
.back-lk{display:inline-block;margin:6px 0 2px;color:var(--ac);font-size:13px}
.room-head{display:flex;gap:14px;align-items:center;margin:8px 0 12px}
.org-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px}
.org-tile{display:flex;gap:10px;align-items:center;background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:10px 12px;margin:0}
.org-tile>div{min-width:0}.org-tile b{display:block;font-size:14.5px}.org-tile .sub{display:block;font-size:12px;line-height:1.45}
.org-stat{display:block;font-size:12.5px;margin-top:2px}.org-stat b,.org-stat .sub{display:inline!important;font-size:inherit!important}
.lvn{display:inline-block;color:var(--sub);font-weight:700;margin-right:4px}
.org-grid2{display:grid;grid-template-columns:1fr 1fr;gap:6px}.org-grid2 .org-mini .sub{font-size:11px}
.org-fold>summary{list-style:none;cursor:pointer;position:relative}.org-fold>summary::-webkit-details-marker{display:none}
.fold-n{position:absolute;right:10px;top:6px;font-size:11px}.org-fold[open] .fold-n{opacity:.4}
.tree .org-mini{padding:5px 8px}.tree li{padding-top:6px}.org-boss{border:2px solid #7A5AE0;margin-top:6px}
.lv{font-weight:800;font-size:14px;margin:4px 0}.lv .sub{font-weight:500;font-size:12px}
.tree,.tree ul{list-style:none;margin:0;padding:0 0 0 16px;position:relative}.tree{margin-left:22px}
.tree li{position:relative;padding:8px 0 0 16px}
.tree li::before{content:'';position:absolute;left:0;top:0;bottom:0;border-left:2px solid var(--bd)}
.tree li:last-child::before{bottom:auto;height:34px}
.tree li::after{content:'';position:absolute;left:0;top:34px;width:14px;border-top:2px solid var(--bd)}
.tree>li>.lv{margin-top:6px}
.org-mini{display:flex;gap:8px;align-items:center;background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:6px 10px}
.org-mini>div{min-width:0}.org-mini b{display:block;font-size:13px}.org-mini .sub{display:block;font-size:11.5px;line-height:1.4}.org-mini .org-stat{font-size:12px;margin:0}
.boat{display:flex;gap:10px;padding:10px 0;border-bottom:1px solid var(--bd)}.boat:last-child{border:0}
.chip{width:30px;height:30px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-weight:700;flex:none;border:1px solid var(--bd)}
.face{width:32px;height:44px;object-fit:cover;border-radius:4px;flex:none;background:var(--off)}
.trifecta{background:linear-gradient(135deg,var(--hot),#B8511E);color:#fff;text-align:center;padding:16px 12px}
.trifecta .sub{color:rgba(255,255,255,.85)}
.tri-main{display:flex;align-items:center;justify-content:center;gap:6px;font-size:26px;font-weight:800;margin-bottom:8px}
.tri-chip{background:#fff;color:var(--hot);border-radius:8px;padding:2px 10px;min-width:36px}
.tri-ar{font-size:18px;opacity:.8}
.tri-pct{font-size:15px;font-weight:700;margin-left:8px;background:rgba(0,0,0,.2);border-radius:12px;padding:2px 10px}
.tri-subrow{font-size:13px;opacity:.9;margin-top:2px}
.nums{display:grid;grid-template-columns:repeat(3,1fr);gap:2px 8px;font-size:13px;margin-top:4px}.nums span{color:var(--sub);font-size:11px;display:block}
.lab{display:inline-block;font-size:12px;padding:2px 8px;border-radius:6px;color:#fff;margin:2px 4px 2px 0}
.lock{text-align:center;padding:36px 12px}.rnav{display:flex;justify-content:space-between;margin:14px 0}.rnav a{color:var(--ac)}
.ad{margin:16px 0;text-align:center;overflow:hidden}
.sum{padding:14px}.rank{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:8px;font-weight:800;font-size:19px;color:#fff;margin-right:8px;flex:none}
.rank-S{background:#C0392B}.rank-A{background:#E8742E}.rank-B{background:#6b7a90}.rank-C{background:#444441}
.sumhead{display:flex;align-items:center}.sumhead b{font-size:17px}.big5{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 2px}
.big5 span{background:var(--off);border:1px solid var(--bd);border-radius:8px;padding:4px 9px;font-weight:700;font-size:15px}
.big5 small{font-weight:500;color:var(--sub);font-size:11px;margin-left:3px}
.brow>summary{list-style:none;cursor:pointer;display:flex;gap:8px;align-items:center;padding:8px 0;border-bottom:1px solid var(--bd)}
.brow>summary::-webkit-details-marker{display:none}.brow[open]>summary{border-bottom:0}
.brow .nm{flex:1;min-width:0;font-weight:700;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar{width:72px;height:8px;border-radius:4px;background:var(--off);flex:none;position:relative}.bar i{display:block;height:100%;background:var(--hot);border-radius:4px}.bar u{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--tx);opacity:.55}.pc small{display:block;font-weight:500;font-size:10px;color:var(--sub);white-space:nowrap}.hero{background:var(--navy);color:#fff;border:1px solid var(--herobd);border-radius:14px;padding:14px 14px 12px;margin:10px 0}.hero .hl{font-size:21px;font-weight:700;line-height:1.3}.hero .hs{font-size:13px;opacity:.85;margin-top:4px}.stack{display:flex;height:30px;border-radius:8px;overflow:hidden;margin:12px 0 4px;background:#fff2}.stack span{display:flex;align-items:center;justify-content:center;font-weight:800;font-size:13px;min-width:0;overflow:hidden}.hero .cap{font-size:11px;opacity:.7}.res{display:flex;gap:8px;align-items:center;padding:9px 2px;border-bottom:1px solid var(--bd)}.res:last-child{border:0}.res .t{flex:1;min-width:0}.res .t b{font-size:14px}.ok{background:var(--green);color:#fff;border-radius:6px;padding:2px 7px;font-size:12px;font-weight:700;white-space:nowrap}.ng{color:var(--sub);font-size:12px;white-space:nowrap}
.pc{width:38px;text-align:right;font-weight:800;font-size:14px;flex:none}.bdet{padding:0 0 8px 38px;border-bottom:1px solid var(--bd);font-size:12.5px}
.rl{display:inline-block;font-size:10.5px;padding:0 5px;border-radius:5px;color:#fff;margin-left:3px;vertical-align:1px}
.btnrow{display:flex;gap:8px;margin:10px 0}.btnrow a{flex:1;text-align:center;padding:12px 0;border-radius:12px;box-shadow:var(--shadow);background:var(--card);border:1px solid var(--bd);font-weight:700;font-size:13.5px}
.nx{display:flex;gap:10px;align-items:center;padding:10px 2px;border-bottom:1px solid var(--bd)}.nx:last-child{border:0}
.nx .rank{width:30px;height:30px;font-size:16px;margin:0}.nx .rank-w{background:var(--off);color:var(--sub);font-size:11px}
.nx .t{flex:1;min-width:0}.nx .t b{font-size:15px}.nx .t .sub{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nx .dl{font-weight:800;font-size:15px;text-align:right}.nx .dl small{display:block;font-weight:500;font-size:11px;color:var(--sub)}
.help>summary{cursor:pointer;color:var(--sub);font-size:12.5px;margin:6px 0}.help p{font-size:12.5px;color:var(--sub);margin:4px 0}
footer{max-width:760px;margin:24px auto;padding:12px;font-size:12px;color:var(--sub)}footer a{color:var(--ac)}svg{display:block;color:var(--tx)}
"""


def page(title, body, desc="", path="", noindex=False):
    robots = '<meta name="robots" content="noindex">' if noindex else ""
    gsc = f'<meta name="google-site-verification" content="{html.escape(CFG["gsc_verify"])}">' if CFG.get("gsc_verify") else ""
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">{robots}
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}｜{CFG['site_name']}</title><meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{CFG['base_url']}{path}"><meta property="og:title" content="{html.escape(title)}">
<meta property="og:site_name" content="{CFG['site_name']}">{gsc}<meta name="theme-color" content="#1B2A4A">
<style>{CSS}</style>{CFG.get('ad_head', '')}</head><body>
<header><a href="/">{CFG['site_name']}</a></header><main>{body}</main>
<footer>{CFG['site_name']}は、展示の進入をもとにデータから見た1マークの展開の傾向を掲載しています。着順を保証するものではありません。舟券の購入は20歳から。<br>
<a href="/record.html">的中実績</a>・<a href="/venue/">全24場の特徴</a>・<a href="/about.html">運営者情報</a>・<a href="/privacy.html">プライバシーポリシー</a>・<a href="/disclaimer.html">免責事項</a>・<a href="/contact.html">お問い合わせ</a></footer>
</body></html>"""


def ad():
    return f'<div class="ad">{CFG["ad_slot"]}</div>' if CFG.get("ad_slot") else ""


def jp(d):
    x = dt.datetime.strptime(d, "%Y%m%d")
    return f"{x.month}月{x.day}日（{WD[x.weekday()]}）"


def dl_dt(date, deadline):
    return dt.datetime.strptime(date + deadline, "%Y%m%d%H:%M").replace(tzinfo=now_jst().tzinfo)


def chip(w):
    return f'<span class="chip" style="background:{BC[w - 1]};color:{TC[w - 1]}">{w}</span>'


# ---------- 集計(今期勝率・節間成績) ----------
RES_COLS = ["date", "jcd", "race", "rank", "toban", "waku", "kimarite", "combo3t", "payout3t"]


def _read_results_year(p):
    """combo3t/payout3t列がまだ無い古いファイル(追加前に書かれたもの)にも対応する"""
    try:
        return pd.read_parquet(p, columns=RES_COLS)
    except Exception:
        df = pd.read_parquet(p, columns=[c for c in RES_COLS if c not in ("combo3t", "payout3t")])
        df["combo3t"], df["payout3t"] = None, None
        return df


def load_results(since):
    fr = []
    for y in range(int(since[:4]), now_jst().year + 1):
        p = DATA / "results" / f"{y}.parquet"
        if p.exists():
            fr.append(_read_results_year(p))
    if not fr:
        return pd.DataFrame(columns=["date", "jcd", "race", "rank", "toban", "pt"])
    r = pd.concat(fr)
    r = r[r.date >= since].copy()
    r["pt"] = r["rank"].map(PTS).fillna(0)
    return r


def period_start(date):
    y, m = int(date[:4]), int(date[4:6])
    return f"{y}0501" if 5 <= m <= 10 else (f"{y}1101" if m >= 11 else f"{y - 1}1101")


class Stats:
    def __init__(self, res):
        self.res = res

    def season(self, date):
        r = self.res[(self.res.date >= period_start(date)) & (self.res.date < date)]
        return r.groupby("toban").pt.mean()

    def series(self, jcd, date, day):
        """節間の着順と得点率(一般的な配点での目安)"""
        start = (dt.datetime.strptime(date, "%Y%m%d") - dt.timedelta(days=max(day, 1) - 1)).strftime("%Y%m%d")
        r = self.res[(self.res.jcd == jcd) & (self.res.date >= start) & (self.res.date < date)].sort_values(["date", "race"])
        if r.empty:
            return {}, 0
        g = r.groupby("toban").agg(pt=("pt", "mean"), n=("pt", "size"),
                                   seq=("rank", lambda s: " ".join(x.lstrip("0") if x.startswith("0") else x for x in s)))
        g["pos"] = g.pt.rank(ascending=False, method="min").astype(int)
        return g.to_dict("index"), len(g)

    def recent(self, jcd, date, days=30):
        """その場の最近(days日)の傾向: レース数・1号艇の1着率・万舟率・一番の高配当"""
        lo = (dt.datetime.strptime(date, "%Y%m%d") - dt.timedelta(days=days)).strftime("%Y%m%d")
        r = self.res[(self.res.jcd == jcd) & (self.res.date >= lo) & (self.res.date < date)]
        if r.empty:
            return None
        races = r.drop_duplicates(["date", "race"])
        w1 = r[(r.waku == 1)]["rank"].eq("01").mean()
        pay = races.payout3t.dropna()
        top = races.loc[pay.idxmax()] if len(pay) else None
        return dict(n=len(races), days=races.date.nunique(), w1=float(w1), manshu=float((pay >= 10000).mean()) if len(pay) else None,
                    top=(top.date, int(top.race), top.combo3t, int(top.payout3t)) if top is not None else None)

    def race_result(self, jcd, date, race):
        r = self.res[(self.res.jcd == jcd) & (self.res.date == date) & (self.res.race == race)]
        if len(r) != 6:
            return None
        return dict(by_waku=dict(zip(r.waku.astype(int), r["rank"])), kimarite=r.kimarite.iloc[0],
                    combo3t=r.combo3t.iloc[0], payout3t=r.payout3t.iloc[0])

    def big_payouts(self, date, thr=10000):
        """その日の万舟以上(3連単)を配当が高い順に返す"""
        r = self.res[(self.res.date == date) & (self.res.payout3t >= thr)].drop_duplicates(["jcd", "race"])
        return r.sort_values("payout3t", ascending=False)[["jcd", "race", "combo3t", "payout3t"]].to_dict("records")


# ---------- ページ ----------
def race_status(date, r, pred, now):
    if now >= dl_dt(date, r["deadline"]):
        return "done"
    if pred and pred.get("version") == "final":
        return "hot"
    return "wait"


def tabs(base, cur, locked, result_ready):
    lk = '<span class="lk">展示後</span>' if locked else ""
    rlk = "" if result_ready else '<span class="lk">レース後</span>'
    items = [("予想", f"{base}.html", "pred", lk), ("展開", f"{base}-turn.html", "turn", lk),
             ("出走表", f"{base}-entry.html", "entry", ""), ("結果", f"{base}-result.html", "result", rlk)]
    return '<nav class="tabs">' + "".join(
        f'<a class="{"on" if k == cur else ""}" href="{u}">{t}{x}</a>' for t, u, k, x in items) + "</nav>"


def race_head(date, v, info, cur, locked, base, result_ready=False):
    return (f'<p class="sub" style="margin:4px 0 0"><a href="/{date}/">{jp(date)}</a> ＞ <a href="/{date}/{info["jcd"]}/">{v}</a>'
            f'・{html.escape(info["title"])} {info["day"]}日目</p>'
            f'<h1 style="margin:2px 0 0">{v} {info["race"]}R <span class="sub">{html.escape(info["rtype"])}・締切 {info["deadline"]}</span></h1>'
            f'{tabs(base, cur, locked, result_ready)}')


def rnav(date, jcd, race, races, suffix):
    prev = f'<a href="/{date}/{jcd}/{race - 1:02d}{suffix}.html">← {race - 1}R</a>' if race - 1 in races else "<span></span>"
    nxt = f'<a href="/{date}/{jcd}/{race + 1:02d}{suffix}.html">{race + 1}R →</a>' if race + 1 in races else "<span></span>"
    return f'<div class="rnav">{prev}{nxt}</div>'


def labels(pred):
    sc, bs = pred["scene"], pred["boats"]
    f = lambda ks: "・".join(str(bs[k]["waku"]) for k in ks) or "なし"
    return (f'<span class="lab" style="background:var(--red)">頭注目 {f(sc["head"])}</span>'
            f'<span class="lab" style="background:var(--green)">連絡み注目 {f(sc["ren"])}</span>'
            f'<span class="lab" style="background:#444441">展開不向き {f(sc["bad"])}</span>'
            f'<p class="sub" style="margin:4px 2px 0">展開不向き＝1着になりにくい、という意味です（2・3着まで否定するものではありません）。</p>')


def entry_page(date, info, boats, season, series, n_series, pred, races, result_ready=False):
    """出走表タブ: 選手の顔・級・勝率・モーター・節間成績"""
    v = VENUES[info["jcd"]]
    base = f'{info["race"]:02d}'
    locked = not (pred and pred.get("version") == "final")
    order = [b["waku"] for b in pred["boats"]] if not locked else None
    rows = ""
    for b in boats:
        s = series.get(b["toban"], {})
        sea = season.get(b["toban"])
        sea_s = f"{sea:.2f}" if sea is not None else "―"
        ser_s = f'節間{s["pt"]:.2f}（{s["pos"]}位/{n_series}）' if s else "節間―"
        rows += (f'<div class="boat">{chip(b["waku"])}'
                 f'<img class="face" src="https://www.boatrace.jp/racerphoto/{b["toban"]}.jpg" loading="lazy" '
                 f'alt="" onerror="this.remove()">'
                 f'<div style="flex:1;min-width:0">'
                 f'<div style="display:flex;justify-content:space-between;gap:8px;align-items:baseline">'
                 f'<b style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{html.escape(b["name"])}</b>'
                 f'<span class="sub" style="flex:none">今期{sea_s}</span></div>'
                 f'<div class="sub" style="font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                 f'{b["grade"]}・{b["age"]}歳・{html.escape(b["branch"])}｜全国{b["nat_win"]:.2f}/当地{b["loc_win"]:.2f}｜'
                 f'モ{b["motor_2r"]:.1f}%｜{ser_s}</div></div></div>')
    entry = ("展示の進入：" + " ".join(str(w) for w in order)) if order else "展示の進入が出たら、予想と展開を公開します（締切の約20分前）。"
    body = (race_head(date, v, info, "entry", locked, base, result_ready)
            + f'<div class="card">{rows}</div><p class="sub">{entry}</p>'
            + ad() + rnav(date, info["jcd"], info["race"], races, "-entry"))
    return page(f"{v}{info['race']}R 出走表 {jp(date)}", body,
                f"{v}{info['race']}Rの出走表。今期勝率・節間成績つき。", f"/{date}/{info['jcd']}/{base}-entry.html")


RANKS = (("S", 0.5, "ガチガチ", "57%"), ("A", 0.4, "堅め", "44%"), ("B", 0.3, "やや混戦", "33%"), ("C", 0.0, "混戦", "22%"))


def predict_page(date, info, pred, races, result_ready=False):
    """予想タブ(レースの最初のページ): 堅さのランク・本命・おすすめの目と、6艇の1着の確率を1画面で"""
    v = VENUES[info["jcd"]]
    base = f'{info["race"]:02d}'
    locked = not (pred and pred.get("version") == "final")
    vw = None if locked else race_view_of(date, info, pred)
    pre = ""
    if locked and pred and pred.get("tri"):
        pv = race_view_of(date, info, pred)
        if pv:
            hl, hs = hook(pv)
            pre = (f'<div class="hero"><div class="cap">展示前の見立て</div><div class="hl">{html.escape(hl)}</div>'
                   + (f'<div class="hs">{html.escape(hs)}</div>' if hs else "") + stack_bar(pv)
                   + '<div class="cap">1着の確率（色＝艇の色）。展示のあとに見直します</div></div>')
    if not vw:
        content = pre + ('<div class="card lock"><b>展示が出たら予想を公開します</b><br>'
                   f'<span class="sub">締切の約20分前（{info["deadline"]}締切）に更新されます</span></div>'
                   f'<div class="btnrow"><a href="{base}-entry.html">出走表を見る</a></div>' + NUDGE)
    else:
        p5 = sum(p for _, p in vw["top3"][:5])
        rk, _, word, hist = next(x for x in RANKS if p5 >= x[1])
        bs = sorted(vw["boats"], key=lambda b: -b["p1"])
        fav = bs[0]
        head = (f'<div class="sumhead"><span class="rank rank-{rk}">{rk}</span><div><b>{word}のレース</b><br>'
                f'<span class="sub">本命 {fav["waku"]}号艇 {html.escape(fav["name"])}（1着{_pct(fav["p1"])}）</span></div></div>')
        if rk in ("S", "A"):
            picks = "".join(f'<span>{c}<small>{_pct(p)}</small></span>' for c, p in vw["top3"][:5])
            mid = (f'<div class="sub" style="margin-top:10px">3連単 おすすめ5点（どれかが来る見込み <b style="color:var(--tx)">{p5:.0%}</b>）</div>'
                   f'<div class="big5">{picks}</div>')
        else:
            cands = "".join(f'<span>{b["waku"]}号艇<small>{_pct(b["p1"])}</small></span>' for b in bs[:3] if b["p1"] >= 0.07)
            mid = ('<div class="sub" style="margin-top:10px">混戦なので5点に絞りにくいレース。頭の候補（1着の確率）</div>'
                   f'<div class="big5">{cands}</div><div class="sub">見送るのもアリ。展開タブで勝ち方ごとの並びを確認できます。</div>')
        t2 = "　".join(f'{c} <span class="sub">{_pct(p)}</span>' for c, p in vw["top2"][:3])
        hl, hs = hook(vw)
        hero = (f'<div class="hero"><div class="hl">{html.escape(hl)}</div>' + (f'<div class="hs">{html.escape(hs)}</div>' if hs else "")
                + stack_bar(vw) + '<div class="cap">1着の確率（色＝艇の色）</div></div>')
        summary = hero + f'<div class="card sum">{head}{mid}<div class="sub" style="margin-top:8px">2連単の上位　<b style="color:var(--tx)">{t2}</b></div></div>'
        rows = ""
        for b in sorted(vw["boats"], key=lambda b: b["waku"]):
            heat = "🔥" if b["heat"] > 0 else ("🧊" if b["heat"] < 0 else "")
            rl = "".join(f'<span class="rl" style="background:{ROLE_COLOR[r]}">{r}</span>' for r in b["roles"])
            why = "・".join(b["good"]) + (("｜" if b["good"] else "") + "・".join(b["bad"]) if b["bad"] else "")
            rows += (f'<details class="brow"><summary>{chip(b["waku"])}<span class="nm">{html.escape(b["name"])} {heat}{rl}</span>'
                     f'<span class="bar"><i style="width:{min(100, b["p1"] * 100):.0f}%"></i><u style="left:{min(99, b["base1"] * 100):.0f}%"></u></span>'
                     f'<span class="pc">{_pct(b["p1"])}<small>いつも{_pct(b["base1"])}</small></span></summary>'
                     f'<div class="bdet">1着 {_pct(b["p1"])}・2着 {_pct(b["p2"])}・3着 {_pct(b["p3"])}<br>'
                     f'普段（{b["course"]}コース）は 1着{_pct(b["base1"])}・2着以内{_pct(b["base2"])}'
                     + (f'<br>{html.escape(why)}' if why else "") + '</div></details>')
        src = (f'情報部の予想と{vw["at"]}時点のオッズを混ぜた確率' if vw["src"] == "混ぜた" else "情報部の予想だけの確率（オッズを混ぜる前）")
        help_ = ('<details class="help"><summary>？ この予想の見方</summary>'
                 f'<p>{src}です。艇の行をタップすると、2着・3着の確率と、普段のそのコースの成績、今日の材料が開きます。</p>'
                 '<p>ランクは「おすすめ5点のどれかが来る見込み」で決めています。過去のレースでの実際の的中率は '
                 + "、".join(f"{r}（{w}）{h}" for r, _, w, h in RANKS) + '。</p>'
                 '<p>棒の縦線＝そのコースのいつもの1着率。棒が線より長ければ今日は普段より頭がある。🔥＝普段より2着以内に来やすい、🧊＝来にくい。頭あり＝1着20%以上、2着が熱い＝2着25%以上、'
                 '2着まで＝頭は薄いが2着はある、3着押さえ＝3着25%以上、消し寄り＝3着以内がかなり薄い。</p></details>')
        content = (summary + '<h2 style="margin:12px 0 0">6艇の1着の確率 <span class="sub">タップで詳しく</span></h2>'
                   f'<div class="card" style="padding:2px 12px">{rows}</div>' + help_
                   + f'<div class="btnrow"><a href="{base}-turn.html">展開を見る</a><a href="{base}-entry.html">出走表</a></div>')
    body = race_head(date, v, info, "pred", locked, base, result_ready) + content + ad() + rnav(date, info["jcd"], info["race"], races, "")
    return page(f"{v}{info['race']}R 予想 {jp(date)}", body,
                f"{v}{info['race']}Rの予想。1着・2着・3着の確率と堅さのランク、おすすめの目。", f"/{date}/{info['jcd']}/{base}.html")


@functools.lru_cache(maxsize=4)
def _odds_live(date):
    return race_view.load_odds(date)


@functools.lru_cache(maxsize=4)
def _entries(date):
    p = DATA / "entries" / f"{date}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _pct(x):
    return f"{x * 100:.0f}%" if x >= 0.095 else f"{x * 100:.1f}%"


ROLE_COLOR = {"頭あり": "var(--red)", "2着が熱い": "#d4537e", "2着まで": "#888780", "3着押さえ": "var(--green)", "消し寄り": "#444441"}


def hook(vw):
    """レースの「つかみ」: ひとことの見出しと、その下の一行(普段より熱い艇)"""
    bs = vw["boats"]
    fav = max(bs, key=lambda b: b["p1"])
    inb = next((b for b in bs if b["course"] == 1), bs[0])
    if fav is inb:
        t = (f"イン逃げ濃厚 {_pct(fav['p1'])}" if fav["p1"] >= 0.6 else
             f"インが本命 {_pct(fav['p1'])}" if fav["p1"] >= 0.45 else f"インが本命も混戦（{_pct(fav['p1'])}）")
    elif inb["p1"] < inb["base1"] - 0.1:
        t = f"インが危ない！ {fav['waku']}号艇の頭 {_pct(fav['p1'])}"
    else:
        t = f"{fav['waku']}号艇が本命 {_pct(fav['p1'])}"
    hot = max((b for b in bs if b is not fav), key=lambda b: b["p1"] + b["p2"] - b["base2"])
    d = hot["p1"] + hot["p2"] - hot["base2"]
    sub = (f"{hot['waku']}号艇が普段より熱い（2着以内 {_pct(hot['p1'] + hot['p2'])}／いつもは{_pct(hot['base2'])}）"
           if d >= 0.08 else "")
    return t, sub


def stack_bar(vw):
    """6艇の1着の確率を、艇の色の帯で1本に"""
    seg = ""
    for b in sorted(vw["boats"], key=lambda b: b["waku"]):
        w = b["waku"]
        lab = f'{w}' if b["p1"] >= 0.06 else ""
        seg += f'<span style="width:{b["p1"] * 100:.1f}%;background:{BC[w - 1]};color:{TC[w - 1]}">{lab}</span>'
    return f'<div class="stack">{seg}</div>'


def race_view_of(date, info, pred):
    key = f'{info["jcd"]}-{info["race"]:02d}'
    live = _entries(date).get(key)
    try:
        return race_view.view(pred, date, _odds_live(date).get(key), live if isinstance(live, dict) else None)
    except Exception as e:
        print(f"当てる予想を作れませんでした({key}): {e!r}")
        return None


def scen_card(v):
    """展開ごとの予想(勝ちそうな艇ごとに、その時の2着・3着の候補)"""
    if not v or not v.get("scen"):
        return ""
    out = ""
    for x in v["scen"]:
        sec = "・".join(f'{w}号艇<span class="sub">{_pct(q)}</span>' for w, q in x["sec"])
        thr = "・".join(f'{w}号艇<span class="sub">{_pct(q)}</span>' for w, q in x["thr"])
        out += (f'<div class="boat">{chip(x["head"])}<div style="flex:1;min-width:0"><div><b>{html.escape(x["name"])}</b> '
                f'<b style="color:var(--red)">{_pct(x["p"])}</b></div>'
                f'<div class="sub">2着 {sec}</div><div class="sub">3着 {thr}</div></div></div>')
    return ('<h2>展開ごとの予想</h2><div class="card"><p class="sub" style="margin:0 0 6px">勝ちそうな艇の順に、その展開になる確率と、'
            'その時に2着・3着へ来やすい艇(その展開になった時の確率)。</p>' + out + '</div>')


def view_card(date, info, pred):
    """当てる予想: 艇ごとの1着・2着・3着の確率と、普段の力との比べ(🔥熱い・🧊冷たい)"""
    v = race_view_of(date, info, pred)
    if not v:
        return ""
    rows = ""
    for b in v["boats"]:
        heat = ' <b style="color:var(--red)">🔥熱い</b>' if b["heat"] > 0 else (' <b style="color:var(--ac)">🧊冷たい</b>' if b["heat"] < 0 else "")
        why = "・".join(b["good"]) + (("｜" if b["good"] else "") + "・".join(b["bad"]) if b["bad"] else "")
        rl = "".join(f'<span class="lab" style="background:{ROLE_COLOR[r]};font-size:11px;padding:1px 6px;margin-left:4px">{r}</span>'
                     for r in b["roles"])
        rows += (f'<div class="boat">{chip(b["waku"])}<div style="flex:1;min-width:0">'
                 f'<div><b>{html.escape(b["name"])}</b>{heat}{rl}</div>'
                 f'<div class="sub">1着 <b style="color:var(--tx)">{_pct(b["p1"])}</b>・2着 {_pct(b["p2"])}・3着 {_pct(b["p3"])}'
                 f'　<span style="white-space:nowrap">普段 {b["course"]}コースで1着{_pct(b["base1"])}・2着以内{_pct(b["base2"])}</span></div>'
                 + (f'<div class="sub" style="font-size:11px">{html.escape(why)}</div>' if why else "") + '</div></div>')
    t2 = " ".join(f'<span style="white-space:nowrap">{c} <span class="sub">{_pct(p)}</span></span>' for c, p in v["top2"])
    t3 = " ".join(f'<span style="white-space:nowrap">{c} <span class="sub">{_pct(p)}</span></span>' for c, p in v["top3"])
    src = (f'情報部の予想と、{v["at"]}時点のオッズ(市場)を混ぜた確率' if v["src"] == "混ぜた"
           else "情報部の予想だけの確率(締切の約25分前からオッズを混ぜます)")
    return (f'<h2>当てる予想</h2><div class="card"><p class="sub" style="margin:0 0 6px">{src}。'
            '🔥＝普段のそのコースの成績より今日は2着以内に来やすい、🧊＝来にくい。'
            '頭あり＝1着20%以上、2着が熱い＝2着25%以上、3着押さえ＝3着25%以上で1・2着は薄い。</p>' + rows
            + f'<div style="margin-top:8px"><b>2連単</b> {t2}</div><div style="margin-top:4px"><b>3連単</b> {t3}</div></div>')


NUDGE = '<script>fetch("/api/nudge",{method:"POST",keepalive:true}).catch(()=>{})</script>'
NUDGE_UPDATE = '<script>fetch("/api/nudge-update",{method:"POST",keepalive:true}).catch(()=>{})</script>'


def locked_body():
    return ('<div class="card lock"><b>展示の進入が出たら公開します</b><br>'
            '<span class="sub">締切の約20分前に更新されます</span></div>' + NUDGE)


def slit_page(date, info, pred, races, result_ready=False):
    v = VENUES[info["jcd"]]
    base = f'{info["race"]:02d}'
    locked = not (pred and pred.get("version") == "final")
    if locked:
        content = locked_body()
    else:
        sc = pred["scene"]
        waku = [b["waku"] for b in pred["boats"]]
        tags = {int(k): x for k, x in sc["tags"].items()}
        order = sorted(range(6), key=lambda k: pred["st"][k])
        rank = "".join(f'<div class="boat">{chip(pred["boats"][k]["waku"])}<div><b>{i + 1}番手</b> '
                       f'<span class="sub">{html.escape(pred["boats"][k]["name"])}・{pred["boats"][k]["course"]}コース'
                       f'{"・" + tags[k] if k in tags else ""}{"・F" + str(pred["fcnt"][k]) + "持ち" if pred["fcnt"][k] else ""}</span></div></div>'
                       for i, k in enumerate(order))
        content = (slit_svg(pred["st"], waku, tags, sc["late"])
                   + '<p class="sub">右ほどスタートが速い予想。選手ごとのコース別STとF持ちから予想しています。</p>'
                   + f'<h2>スリットの並び</h2><div class="card">{rank}</div>')
    body = race_head(date, v, info, "slit", locked, base, result_ready) + content + ad() + rnav(date, info["jcd"], info["race"], races, "-slit")
    return page(f"{v}{info['race']}R スタートスリット予想 {jp(date)}", body, f"{v}{info['race']}Rのスタートスリット隊形予想",
                f"/{date}/{info['jcd']}/{base}-slit.html")


def _scenarios_html(pred):
    """展開シナリオ集: 起こりうる勝ち方ごとの図・文章・買い目の形と、全艇の勝ち方。
    一番起こりやすいシナリオだけ開いた状態で見せて、残りは折りたたむ(ページが長くなりすぎないように)"""
    sc = pred.get("scenarios")
    if not sc or not sc.get("list"):
        return ""
    waku = [b["waku"] for b in pred["boats"]]

    def card(i, s):
        scene = dict(s["scene"], roles={int(k): v for k, v in s["scene"]["roles"].items()})
        try:
            svg = turn_svg(scene, waku)
        except Exception:
            svg = ""   # ボートが重なって描けない配置のときは図なしで出す
        return (f'<div class="card"><b>シナリオ{i}　{waku[s["w"]]}の{s["m"]}</b> '
                f'<span class="sub">（起こる確率 {s["prob"]:.0%}）</span>{svg}'
                f'<p style="margin:6px 0">{html.escape("。".join(s["lines"]))}。</p>'
                f'<p class="sub" style="margin:0">買い目の形 <b style="color:var(--tx);font-size:16px">{s["combo"]}</b></p></div>')

    first, rest = sc["list"][0], sc["list"][1:]
    cards = card(1, first)
    if rest:
        rest_html = "".join(card(i, s) for i, s in enumerate(rest, 2))
        cards += f'<details><summary class="sub" style="padding:10px 4px">他{len(rest)}通りのシナリオを見る</summary>{rest_html}</details>'
    heads = "".join(
        f'<div class="boat">{chip(waku[h["w"]])}<div><b>{h["m"]}</b>が本線 <span class="sub">勝つ確率 {h["prob"]:.0%}</span></div></div>'
        for h in sorted(sc["heads"], key=lambda h: -h["prob"]))
    return (f'<h2>展開シナリオ</h2><p class="sub">起こりうる勝ち方を確率の高い順に並べています。'
            f'2・3着は、その勝ち方になったときに残りやすい艇です。決まり手は4種類(逃げ・まくり・差し・まくり差し)で区別しています。</p>'
            f'{cards}<h2>全艇、頭ならこう勝つ</h2><div class="card">{heads}</div>')


def turn_page(date, info, pred, races, result_ready=False):
    v = VENUES[info["jcd"]]
    base = f'{info["race"]:02d}'
    locked = not (pred and pred.get("version") == "final")
    if locked:
        content = locked_body()
    else:
        sc = pred["scene"]
        sc2 = dict(sc, roles={int(k): x for k, x in sc["roles"].items()}, tags={int(k): x for k, x in sc["tags"].items()})
        waku = [b["waku"] for b in pred["boats"]]
        lines = "".join(f'<div class="boat">{chip(b["waku"])}<div><span class="sub">{html.escape(b["name"])}</span><br>'
                        f'{html.escape(sc["lines"].get(str(k), "展開待ち"))}</div></div>' for k, b in enumerate(pred["boats"]))
        tags = {int(k): x for k, x in sc["tags"].items()}
        content = (scen_card(race_view_of(date, info, pred))
                   + '<h2>スタートと1マーク</h2><div class="card">'
                   + slit_svg(pred["st"], waku, tags, sc["late"])
                   + '<p class="sub" style="margin:4px 0 8px">スタートの隊形の予想（右ほど速い）。</p>'
                   + turn_svg(sc2, waku) + f'<div style="margin-top:6px">{labels(pred)}</div></div>'
                   + '<details class="help"><summary>もっと詳しく（各艇の動き・展開シナリオ）</summary>'
                   + f'<h2>各艇の展開</h2><div class="card">{lines}</div>' + _trifecta_card(pred) + _scenarios_html(pred) + '</details>')
    body = race_head(date, v, info, "turn", locked, base, result_ready) + content + ad() + rnav(date, info["jcd"], info["race"], races, "-turn")
    return page(f"{v}{info['race']}R 展開予想 {jp(date)}", body, f"{v}{info['race']}Rの展開予想。勝ち方ごとの確率と2着・3着、スタート隊形と1マーク",
                f"/{date}/{info['jcd']}/{base}-turn.html")


def _verdict_card(pred, by_waku):
    """展開予想の答え合わせ。順位を予想したわけではないので「的中/ハズレ」ではなく
    「仕掛け成功/不発」のように、あくまで仕掛け・展開の当たり外れとして書く。"""
    sc, boats = pred["scene"], pred["boats"]

    def rank_of(k):
        return by_waku.get(boats[k]["waku"])

    rows = []
    for k in sc.get("head", []):
        ok = rank_of(k) == "01"
        rows.append((boats[k]["waku"], "頭注目", "仕掛け成功！" if ok else "不発", ok))
    for k in sc.get("ren", []):
        ok = rank_of(k) in ("01", "02", "03")
        rows.append((boats[k]["waku"], "連絡み注目", "連絡み成功" if ok else "絡めず", ok))
    for k in sc.get("bad", []):
        ok = rank_of(k) != "01"
        rows.append((boats[k]["waku"], "展開不向き", "想定通り" if ok else "番狂わせ", ok))
    if not rows:
        return ""
    items = "".join(
        f'<div class="boat">{chip(w)}<div><b>{lab}</b><br>'
        f'<span class="sub" style="color:{"var(--green)" if ok else "var(--red)"}">{txt}</span></div></div>'
        for w, lab, txt, ok in rows)
    return f'<h2>展開予想の答え合わせ</h2><div class="card">{items}</div>'


def result_page(date, info, pred, races, result):
    v = VENUES[info["jcd"]]
    base = f'{info["race"]:02d}'
    locked = not (pred and pred.get("version") == "final")
    if result is None:
        content = ('<div class="card lock"><b>結果はまだ発表されていません</b><br>'
                   '<span class="sub">レース終了後、しばらくしてから反映されます</span></div>')
    else:
        by_waku, kimarite = result["by_waku"], result["kimarite"]
        order = sorted(by_waku.items(), key=lambda kv: kv[1])
        rows = "".join(f'<div class="boat">{chip(w)}<div><b>{r.lstrip("0") if r.isdigit() else r}着</b></div></div>'
                       for w, r in order)
        content = f'<h2>着順（決まり手：{html.escape(kimarite) or "―"}）</h2><div class="card">{rows}</div>'
        if pred and not locked:
            content += _verdict_card(pred, by_waku)
    body = race_head(date, v, info, "result", locked, base, result is not None) + content + ad() \
        + rnav(date, info["jcd"], info["race"], races, "-result")
    return page(f"{v}{info['race']}R 結果 {jp(date)}", body, f"{v}{info['race']}Rの結果と展開予想の答え合わせ",
                f"/{date}/{info['jcd']}/{base}-result.html")


def _trifecta_card(pred):
    tri = pred["scene"].get("trifecta")
    if not tri:
        return ""
    waku = [b["waku"] for b in pred["boats"]]
    i1, j1, k1, p1 = tri[0]
    arrow = '<span class="tri-ar">→</span>'
    chips = arrow.join(f'<span class="tri-chip">{waku[x]}</span>' for x in (i1, j1, k1))
    main = f'<div class="tri-main">{chips}<span class="tri-pct">{p1 * 100:.1f}%</span></div>'
    sub = "".join(f'<div class="tri-subrow">{waku[i]}-{waku[j]}-{waku[k]} <span class="sub">{p * 100:.1f}%</span></div>'
                  for i, j, k, p in tri[1:])
    return (f'<h2>本命シナリオ</h2><div class="card trifecta">{main}{sub}'
            f'<p class="sub" style="margin-top:8px">展開予想から機械的に導いた参考の着順です。的中や払戻を保証するものではありません。</p></div>')


def plans_of(bet):
    """保存された買い目を {買い方: 内容} に。5通り化する前の形式(6点1通り)は「バランス」として扱う"""
    if not bet:
        return {}
    return bet["plans"] if "plans" in bet else {"balance": bet}


def settle(plan, result):
    """買い方1つ分の収支。(投資, 払戻) / 見送り・結果待ちはNone。払戻は100円あたりの配当×口数。
    2連単の買い方(bet="2t")は2連単の結果で精算する"""
    if not plan or plan.get("skip") or not result:
        return None
    gone = returned_boats(result)
    keep = [t for t in plan["tickets"] if not gone & {int(x) for x in t["combo"].split("-")}]
    refund = sum(t["units"] for t in plan["tickets"]) * 100 - sum(t["units"] for t in keep) * 100
    ret = 0
    for kind in {t.get("bet", plan.get("bet", "3t")) for t in keep}:   # 買い目ごとに券種が違うプランもある
        combo, pay = result.get(f"combo{kind}"), result.get(f"payout{kind}")
        if not combo or pay is None or pd.isna(pay):
            return None
        ret += sum(t["units"] * int(pay) for t in keep
                   if t.get("bet", plan.get("bet", "3t")) == kind and t["combo"] == combo)
    return plan["stake"] - refund, ret   # 返還された目は、買わなかったのと同じ扱い(投資から引く)


RETURN_MARKS = ("F", "L", "K", "欠")   # フライング・出遅れ・欠場 → その艇を含む舟券は返還


def returned_boats(result):
    """返還になった艇の枠番の集合(フライング・出遅れ・欠場。結果に名前が無い艇も欠場とみなす)"""
    bw = result.get("by_waku") or {}
    out = {int(w) for w, r in bw.items() if str(r).strip().startswith(RETURN_MARKS)}
    if len(bw) >= 3:
        out |= {w for w in range(1, 7) if w not in {int(x) for x in bw}}
    return out


TRIAL_NOTE = ('<div class="card" style="border:2px dashed var(--hot)"><b style="color:var(--hot)">試験運用中</b>'
              '<br><span class="sub" style="color:var(--tx)">買い目モデルを検証するために、試験的に公開しています。'
              '成績はまだ検証中で、回収を保証するものではありません。参考程度にご覧ください。</span></div>')
SKIP_TEXT = {"balance": "的中確率30%以上で期待回収率100%を超える組み合わせがありませんでした",
             "in_hit": "1コース頭で期待回収率80%以上の組み合わせがありませんでした",
             "in_ev": "1コース頭で的中確率15%以上の組み合わせがありませんでした",
             "out_hit": "1コース以外の頭で期待回収率70%以上の組み合わせがありませんでした",
             "out_ana": f"1コース以外が頭で{bet_mod.ANA_ODDS}倍以上の目がありませんでした",
             "e2_top1": "展示の進入が枠なりでなく、頭注目が1以外のレースだけ買います",
             "pick2": f"1コース1着確率{bet_mod.PICK2_NIGE_MAX:.0%}未満の厳選レースのみ対象。本命・次点の"
                      f"どちらかでもオッズ{bet_mod.PICK2_MIN_ODDS}〜{bet_mod.PICK2_MAX_ODDS}倍の目が無ければ見送り",
             "pickin": f"1コース1着確率{bet_mod.PICKIN_NIGE_MIN:.0%}以上のレースのみ対象。2連単の確率1位が"
                       f"オッズ{bet_mod.PICKIN_MIN_ODDS}倍未満なら見送り",
             "pick2tan": f"1コース以外の本命・次点の2連単の確率1位が{bet_mod.PICK2TAN_PROB_MIN:.0%}以上の時だけ"
                         "買います",
             "pick6a": "A級が6コースだけで、1〜5コースが全員B級のレースのみ対象",
             "pick21t": f"2コースの予想スタートが1コースより{bet_mod.PICK21_ST_GAP}秒以上速いレースのみ対象",
             "pick21": f"2コースの予想スタートが1コースより{bet_mod.PICK21_ST_GAP}秒以上速いレースのみ対象",
             "pickura": "B級インのレースで、実績だけの予想が市場の1着確率の"
                        f"{bet_mod.PICKURA_RATIO}倍以上・{bet_mod.PICKURA_MIN_P:.0%}以上と見る他艇がいる時だけ買います",
             "pickbinc": f"B級インの条件に加えて、風速{bet_mod.PICKBIN_CALM_WIND}m以下で、他の艇の市場の1着確率が全部"
                         f"{bet_mod.PICKBINX_RIVAL_MAX:.0%}未満のレースのみ対象",
             "pickbint": f"B級インの条件に加えて、風速{bet_mod.PICKBIN_CALM_WIND}m以下で、1コースの展示タイムが一番速いレースのみ対象",
             "pickbinx": f"B級インの条件に加えて、他の艇の市場の1着確率が全部{bet_mod.PICKBINX_RIVAL_MAX:.0%}未満で、"
                         "1コースの予想スタートが一番速いレースのみ対象",
             "pickbin": f"1コースが本物のB級(勝率{bet_mod.PICKBIN_FAKE_WIN}未満・直近でA級なし・F持ちでない)で、"
                        f"1コース1着確率{bet_mod.PICKBIN_HP_MIN:.0%}以上のレースのみ対象"}


def _safe_plan_card(name, pl, result):
    """1プランのカードが作れなくても、サイト全体の更新は止めない"""
    try:
        return _plan_card(name, pl, result)
    except Exception as e:
        print(f"買い目カードを作れませんでした({name}): {e!r}")
        return ""


def _plan_card(name, pl, result):
    title = f'<h2>{bet_mod.PLANS.get(name, name)}</h2>'
    if pl.get("skip"):
        return title + f'<div class="card"><b>見送り</b><br><span class="sub">{SKIP_TEXT.get(name, "条件に合う買い目がありませんでした")}</span></div>'
    if pl.get("bet") == "2t":
        chips = "".join(f'<span class="tri-chip">{html.escape(t["combo"])}</span>' for t in pl["tickets"])
        form = f'<div class="tri-main"><span class="sub" style="font-size:14px">2連単</span>{chips}</div>'
    elif pl.get("himo"):
        himo = "".join(str(x) for x in pl["himo"])
        form = (f'<div class="tri-main"><span class="tri-chip">{pl["head"]}</span><span class="tri-ar">→</span>'
                f'<span class="tri-chip">{himo}</span><span class="tri-ar">→</span><span class="tri-chip">{himo}</span></div>')
    else:
        form = f'<div class="tri-main" style="font-size:20px">{len(pl["tickets"])}点</div>'
    evt = f'・期待回収率 {pl["ev"]:.0%}' if pl.get("ev") is not None else ""
    hitp = f'・的中確率 {pl["hit"]:.0%}' if pl.get("hit") is not None else ""
    head = (f'<div class="card trifecta">{form}<p class="sub">投資 {pl["stake"]:,}円{hitp}{evt}</p></div>')
    scen = f'<p style="margin:6px 2px">{html.escape(pl["scenario"])}</p>' if pl.get("scenario") else ""
    rows = "".join(
        f'<div class="boat"><div style="flex:1"><b>{t["combo"]}</b>' + (f' <span class="sub">({t["role"]})</span>' if t.get("role") else "")
        + f' <span class="sub">× {t["units"]}口（{t["units"] * 100:,}円）</span><br>'
        f'<span class="sub">' + (f'オッズ {t["odds"]:.1f}・確率 {t["prob"]:.1%}・期待値 {t["prob"] * t["odds"]:.2f}' if t.get("odds") and t.get("prob") is not None
                                 else (f'オッズ {t["odds"]:.1f}' if t.get("odds") else (f'確率 {t["prob"]:.1%}' if t.get("prob") is not None else ""))) + '</span></div></div>'
        for t in pl["tickets"])
    out = title + head + scen + f'<details class="card"><summary class="sub">買い目 {len(pl["tickets"])}点を見る</summary>{rows}</details>'
    st = settle(pl, result)
    if st:
        stake, ret = st
        col = "var(--green)" if ret >= stake else "var(--red)"
        out += (f'<div class="card"><span style="color:{col};font-weight:700">{"的中" if ret else "不的中"}　'
                f'払戻 {ret:,}円 / 投資 {stake:,}円（{ret - stake:+,}円）</span></div>')
    return out


def _org_race_html(date, pred, result, bet, key=None):
    """レースごとの組織の判断: 決裁者が採用した提案・上がってきた提案(箱・自信度・採用)・結果"""
    plans = {n: pl for n, pl in plans_of(bet).items()
             if not (n in bet_mod.OPS_PLANS + bet_mod.SHADOW_PLANS and pl.get("logic") != bet_mod.OPS_LOGIC)}
    if key:   # 記録と同じく、45秒前のオッズで作り直した買い目で判断する(決裁者A r2)
        plans = _kessai_plans(date, key, pred, bet, {n: pl for n, pl in plans.items() if not pl.get("skip")})
    props = org_tree.proposals(plans, pred)
    for pr in props:
        pr["conf"] = org_tree.conf_of(pr, conf_for(date))
        sp = settle(dict(tickets=pr["tickets"], stake=pr["stake"], bet=pr["bet"]), result) if result else None
        pr["ret"] = sp[1] if sp else None
        pr["paid"] = sp[0] if sp else pr["stake"]   # 返還分を引いた投資
    picked = {(c["leaf"], c["head"]) for c in org_tree.decide(props, conf_for(date), adopt=org_tree.adopt_for(date))}
    w2c = {b["waku"]: i + 1 for i, b in enumerate(pred["boats"])}

    def path(pr):
        g = ".".join(pr["leaf"].split(".")[:2])
        tags = "・".join(org_tree.TAG_LABEL[t.split(".")[-1]] for t in pr["tags"])
        return (f'{org_tree.NODES[g]} ＞ {ALL_PLAN_LABELS.get(pr["plan"], pr["plan"])}' + (f' ＞ {tags}' if tags else ""))

    def hit_combo(kind):
        return (result or {}).get(f"combo{kind}")

    def row(pr, big=False):
        hc = hit_combo(pr["bet"])
        tk = " ".join(f'<span style="white-space:nowrap{";color:var(--green);font-weight:700" if t["combo"] == hc else ""}">{t["combo"]} {t["units"] * 100:,}円</span>'
                      for t in pr["tickets"])
        ad = (pr["leaf"], pr["head"]) in picked
        badge = (f'<span class="lab" style="background:{"#7A5AE0" if ad else "#9aa0a8"}">{"採用" if ad else "不採用"}</span>')
        res = ""
        if pr["ret"] is not None:
            col = "var(--green)" if pr["ret"] >= pr["paid"] else "var(--red)"
            word = "返還" if pr["paid"] == 0 else ("的中" if pr["ret"] else "外れ")
            res = f'<b style="color:{col}">{word} {round(pr["ret"] - pr["paid"]):+,}円</b>'
        cc = "var(--green)" if pr["conf"] >= org_tree.adopt_for(date) else "var(--sub)"
        return (f'<div class="boat">{chip(pr["head"])}<div style="flex:1;min-width:0">'
                f'<div style="display:flex;justify-content:space-between;gap:6px"><span>{badge}<b>{pr["head"]}号艇頭</b> '
                f'<span class="sub">{w2c.get(pr["head"])}コース</span></span>{res}</div>'
                f'<span class="sub">{path(pr)}</span><br>'
                f'<span class="sub">自信度 <b style="color:{cc}">{pr["conf"]:.0%}</b>・{pr["stake"]:,}円・{"2連単" if pr["bet"] == "2t" else "3連単"}</span>'
                + (f'<details><summary class="sub">買い目{len(pr["tickets"])}点</summary><span class="sub">{tk}</span></details>' if not big else f'<div class="sub">{tk}</div>')
                + '</div></div>')
    chosen = [pr for pr in props if (pr["leaf"], pr["head"]) in picked]
    if chosen:
        st = sum(c["paid"] for c in chosen)
        tot = ""
        if all(c["ret"] is not None for c in chosen):
            ret = round(sum(c["ret"] for c in chosen))
            tot = f'<p style="margin:6px 0 0"><b style="color:{"var(--green)" if ret >= st else "var(--red)"}">採用分 払戻 {ret:,}円 / 投資 {st:,}円（{ret - st:+,}円）</b></p>'
        head = (f'<div class="card" style="border:2px solid #7A5AE0"><b>最終決裁者の判断: {len(chosen)}件採用</b>'
                + "".join(row(c, True) for c in sorted(chosen, key=lambda c: -c["conf"])) + tot + '</div>')
    else:
        why = "提案がありません" if not props else f"自信度{org_tree.adopt_for(date):.0%}以上の提案がありません"
        head = f'<div class="card" style="border:2px solid #7A5AE0"><b>最終決裁者の判断: 見送り</b><br><span class="sub">{why}</span></div>'
    body = head
    if props:
        body += '<h2>上がってきた提案 <span class="sub">頭ごと・自信度の高い順</span></h2>'
        for side in ("in", "out"):
            ps = sorted([pr for pr in props if pr["leaf"].startswith(side + ".")], key=lambda pr: -pr["conf"])
            if ps:
                body += f'<div class="card"><b>{org_tree.NODES[side]}</b>' + "".join(row(pr) for pr in ps) + '</div>'
    return body + f'<p class="sub">同じ頭(同じ結果)を取り合う提案は自信度が一番高いものだけが上がり、自信度{org_tree.adopt_for(date):.0%}以上は全部採用します。<a href="/ops.html" style="color:var(--ac)">予想組織図</a></p>'


def bet_page(date, info, pred, races, result, bet):
    v = VENUES[info["jcd"]]
    base = f'{info["race"]:02d}'
    if bet is None:
        content = ('<div class="card lock"><b>買い目はまだ決まっていません</b><br>'
                   '<span class="sub">締切の約2〜9分前にオッズを見て、1レース1回だけ決めます</span></div>')
    else:
        content = f'<p class="sub">{bet.get("odds_at", "")}時点のオッズで決めた買い目です</p>'
        if result and result.get("combo3t"):
            pay = "" if pd.isna(result.get("payout3t")) else f'（{int(result["payout3t"]):,}円）'
            e2 = (f'<br><span class="sub">2連単 {html.escape(result["combo2t"])}（{int(result["payout2t"]):,}円）</span>'
                  if result.get("combo2t") and result.get("payout2t") else "")
            content += f'<div class="card"><b>結果 {html.escape(result["combo3t"])}</b>{pay}{e2}</div>'
        cards = "".join(_safe_plan_card(n, pl, result) for n, pl in plans_of(bet).items())
        if pred and date >= ORG_SINCE:
            try:
                content += _org_race_html(date, pred, result, bet, f'{info["jcd"]}-{info["race"]:02d}')
            except Exception as e:   # 組織の判断が作れなくても、サイト全体の更新は止めない
                print(f"組織の判断を作れませんでした({date} {info['jcd']}-{info['race']}): {e!r}")
            content += f'<details class="card"><summary class="sub">資料室: 各プランの買い目カード(旧プランも含む)</summary>{cards}</details>'
        else:
            content += cards
    content = TRIAL_NOTE + content
    content += ('<p class="sub">展開予想とは別に、モデルの確率とオッズから読んだ市場の確率を混ぜて機械的に組んでいます。'
                'オッズは締切までに動くため、表示の期待回収率は目安です。<a href="/ops.html" style="color:var(--ac)">予想組織図</a></p>')
    body = race_head(date, v, info, "bet", False, base, result is not None) + content \
        + rnav(date, info["jcd"], info["race"], races, "-bet")
    return page(f"{v}{info['race']}R 試験用買い目 {jp(date)}", body, "", f"/{date}/{info['jcd']}/{base}-bet.html", noindex=True)


EXTRA_PLANS = {"switch": "切り替え(頭注目1→イン的中/他→以外的中)", "flow": "頭-連-流し(頭注目→連絡み→総流し)"}


def _flow(pred, result):
    """頭-連-流し: 頭注目→連絡み→残り全部。(投資, 払戻)"""
    sc, waku = pred["scene"], [b["waku"] for b in pred["boats"]]
    h = waku[sc["head"][0]]
    ren = [waku[k] for k in sc["ren"] if waku[k] != h]
    pts = [f"{h}-{a}-{x}" for a in ren for x in range(1, 7) if x not in (h, a)]
    if not pts:
        return None
    return 100 * len(pts), (int(result["payout3t"]) if result["combo3t"] in pts else 0)


def _kessai_plans(date, key, pred, b, plans):
    """決裁者A r2(10/19から): 締切45秒前のオッズが記録されていれば、見込みの確定オッズに直して社員の買い目を作り直す。
    まだ45秒前より前なら、渡された(2分前に決めた)買い目のまま"""
    s45 = (b.get("stages") or {}).get("直前")
    if not (date >= KESSAI_R2_SINCE and s45 and s45.get("o2") and s45.get("o3")):
        return plans
    o2f, o3f = flex.expected_final(pred, {c: v for c, v in zip(bet_mod.ODDS2_ORDER, s45["o2"]) if v},
                                   {c: v for c, v in zip(bet_mod.ODDS_ORDER, s45["o3"]) if v})
    lv = _entries(date).get(key)
    try:
        made = bet_mod.make_bet(pred, o3f, o2f, date, lv if isinstance(lv, dict) else None)["plans"]
        # 外の1着専門は、45秒前と確定で「1着専門÷市場」がほぼ変わらない(10/17〜19で中央1.005倍)ので、45秒前のオッズそのままで判断する
        made["pickwin"] = dict(skip=True, bet="2t") if date < KESSAI_R3_SINCE else bet_mod._pickwin(pred, {c: v for c, v in zip(bet_mod.ODDS2_ORDER, s45["o2"]) if v},
                                            lv if isinstance(lv, dict) else None)
        made["pickwin"]["logic"] = bet_mod.OPS_LOGIC
        if date < KESSAI_R3_SINCE:
            made["pickinwin"] = dict(skip=True, bet="2t")
        return {n: pl for n, pl in made.items() if n in org_tree.ORG_PLANS and not pl.get("skip")}
    except Exception as e:
        print(f"決裁者Aの作り直しに失敗({date} {key}): {e!r}")
        return plans


def bets_upcoming(now=None):
    """運用プランの「これから」: 今日、締切前に買い目を決めたがまだ結果が出ていないレース(締切順)"""
    now = now or now_jst()
    date = f"{now:%Y%m%d}"
    bp = DATA / "bets" / f"{date}.json"
    if not bp.exists():
        return []
    live = live_result.load(date)
    pp = DATA / "predictions" / f"{date}.json"
    preds = json.loads(pp.read_text())["races"] if pp.exists() else {}
    out = []
    for key, b in json.loads(bp.read_text()).items():
        if (live.get(key) or {}).get("combo2t"):
            continue   # 結果が出たものは実績の方に出る
        jcd, race = key.split("-")
        base = dict(v=jcd, r=int(race), t=(preds.get(key) or {}).get("deadline", ""), at=b.get("odds_at", ""), st=b.get("stage", ""))
        plans = {n: pl for n, pl in plans_of(b).items()
                 if n in bet_mod.OPS_PLANS + bet_mod.SHADOW_PLANS and pl.get("logic") == bet_mod.OPS_LOGIC and not pl.get("skip")}
        for n, pl in plans.items():
            out.append(dict(base, p=n, tk=[[t["combo"], t["units"], t.get("role"), t.get("odds")] for t in pl["tickets"]]))
        pred = preds.get(key)
        if pred and plans:   # 決裁者Aが採用した提案(1提案4,000円)。45秒前の判断があればそちら(記録と同じ買い目)
            kp = _kessai_plans(date, key, pred, b, plans)
            st45 = "最終(45秒前)" if kp is not plans else base["st"]
            for c in org_tree.decide(org_tree.proposals(kp, pred), conf_for(date), adopt=org_tree.adopt_for(date)):
                lab = f'{ALL_PLAN_LABELS.get(c["plan"], c["plan"])}・自信度{c["conf"]:.0%}'
                out.append(dict(base, p="kessai", st=st45, tk=[[t["combo"], t["units"], lab, t.get("odds")] for t in c["tickets"]]))
    return sorted(out, key=lambda x: (x["t"], x["v"]))


def quick_bet_pages(now, keys):
    """購入係用: 決めたレースの「試験買い目」ページだけ作り直す(サイト全体は作り直さない)"""
    date = f"{now:%Y%m%d}"
    p = DATA / "programs" / f"{date[:4]}.parquet"
    if not keys or not p.exists():
        return
    prog = pd.read_parquet(p)
    day = prog[prog.date == date]
    preds = json.loads((DATA / "predictions" / f"{date}.json").read_text())["races"]
    bp = DATA / "bets" / f"{date}.json"
    bets = json.loads(bp.read_text()) if bp.exists() else {}
    for key in keys:
        jcd, race = key.split("-")
        g = day[day.jcd == jcd]
        x = g[g.race == int(race)]
        if x.empty:
            continue
        info = dict(jcd=jcd, race=int(race), rtype=x.rtype.iloc[0], deadline=x.deadline.iloc[0], title=x.title.iloc[0],
                    day=int(x.day.iloc[0]))
        d = OUT / date / jcd
        d.mkdir(parents=True, exist_ok=True)
        try:
            (d / f"{race}-bet.html").write_text(bet_page(date, info, preds.get(key), set(g.race.astype(int)), None, bets.get(key)))
        except Exception as e:
            print(f"試験買い目ページを作れませんでした({key}): {e!r}")


def quick_upcoming(now=None):
    """購入係用: 「これから」のデータだけ作り直す(サイト全体は作り直さない)"""
    (OUT / "bets-upcoming.json").write_text(json.dumps(bets_upcoming(now), ensure_ascii=False, separators=(",", ":")))


ORG_CONF = org_tree.load_confidence()


KESSAI_R3_SINCE = "20261020"   # 決裁者A r3: 外の1着専門を社員に入れた日
KESSAI_C_SINCE = "20261020"   # 決裁者C(重ね型・記録だけ)を始めた日
OUTW_SINCE = "20261020"   # 外の1着専門の記録を始めた日
URA_M_SINCE = "20261020"   # 裏の穴×来そう一致の記録を始めた日(10/19に過去2年で見つけた)
KESSAI_R2_SINCE = "20261019"   # 決裁者A r2: 2年分の表・採用103%・45秒前のオッズを見込みの確定オッズに直して判断
FLEX_WIN_SINCE = "20261019"   # v2 の頭の確率を1着専門で直し、3連単への切り替えも始めた日(前の日は前の形で記録)


@functools.lru_cache(maxsize=None)
def conf_for(date):
    """その日に決裁者が使っていた自信度の表(表を作り直しても、前の日の判断は書き換えない)"""
    return org_tree.load_confidence(date)


def bets_records():
    """集計画面用に、結果が出たレースごとの記録を作る(買い方ごとの投資・払戻と、絞り込み用の条件)"""
    files = sorted((DATA / "bets").glob("*.json"))
    if not files:
        return []
    res = load_results(files[0].stem)
    keyed = {(r.date, r.jcd, int(r.race)): dict(combo3t=r.combo3t, payout3t=r.payout3t)
             for r in res.drop_duplicates(["date", "jcd", "race"]).itertuples() if isinstance(r.combo3t, str) and r.combo3t}
    out = []
    for f in files:
        date = f.stem
        live = live_result.load(date)   # 成績ファイルがまだの日は、レース結果ページから取り込んだ結果で補う
        pp = DATA / "predictions" / f"{date}.json"
        preds = json.loads(pp.read_text())["races"] if pp.exists() else {}
        bf = DATA / "bets_backfill" / f"{date}.json"
        backfill = json.loads(bf.read_text()) if bf.exists() else {}
        rpf = DATA / "bets_replay" / f"{date}.json"
        replay = json.loads(rpf.read_text()) if rpf.exists() else {}   # 今の方法・確定オッズで作り直したもの(replay_live.py)
        day = json.loads(f.read_text())
        for key in backfill.keys() - day.keys():   # 取り逃がして後から作り直したレース
            day[key] = {"plans": backfill[key]}
        for key in replay.keys() - day.keys():     # 実戦で決められなかったレースも、再生の方には数える
            day[key] = {"plans": {}, "replay_only": True}
        for key, b in day.items():
            jcd, race = key.split("-")
            result = {**live.get(key, {}), **(keyed.get((date, jcd, int(race))) or {})}   # 2連単は結果ページの記録から
            if not result.get("combo3t") or pd.isna(result.get("payout3t")):
                continue
            if b.get("stage") == "候補" and "確定" not in b.get("stages", {}):
                continue   # 締切2分前の確定まで行かなかったレースは数えない
            plans = plans_of(b)
            fill = backfill.get(key, {})   # 切り替え前の買い目を今のロジックで作り直したもの(backfill_ops.py)
            plans = {**plans, **{n: pl for n, pl in fill.items() if plans.get(n, {}).get("logic") != bet_mod.OPS_LOGIC}}
            st = {}
            for n, pl in plans.items():
                if n in bet_mod.OPS_PLANS + bet_mod.SHADOW_PLANS and pl.get("logic") != bet_mod.OPS_LOGIC:
                    continue   # 運用プランは今の版のロジックで作った買い目だけ集計する
                st[n] = 0 if pl.get("skip") else list(settle(pl, result))
            pred = preds.get(key)
            fx_rec = None
            new = date >= FLEX_WIN_SINCE   # 10/19から: 45秒前のオッズ・見込みの確定オッズ・1着専門・3連単への切り替え
            stg = b.get("stages") or {}
            s2 = (stg.get("直前") or stg.get("確定")) if new else stg.get("確定")   # 決裁者v2(柔軟型・記録だけ)
            if pred and s2 and s2.get("o2") and date >= ORG_SINCE:
                lv = _entries(date).get(key)
                fx = flex.picks(pred, {c: v for c, v in zip(bet_mod.ODDS2_ORDER, s2["o2"]) if v},
                                lv if isinstance(lv, dict) else None, win=new,
                                o3={c: v for c, v in zip(bet_mod.ODDS_ORDER, s2.get("o3") or []) if v} if new else None, drift=new)
                sp = settle(dict(tickets=fx, stake=sum(t["units"] for t in fx) * 100), result) if fx else None
                st["flex"] = list(sp) if sp else 0
                fx_rec = [[t["combo"], t["odds"], round(t["ev"], 2), t.get("odds_f")] for t in fx] if sp else None
                o2s = {c: v for c, v in zip(bet_mod.ODDS2_ORDER, s2["o2"]) if v}
                o3s = {c: v for c, v in zip(bet_mod.ODDS_ORDER, s2.get("o3") or []) if v}
                for pk, tks in (("setsuD", shadow_staff.setsu_d(pred, o2s)),
                                ("hot3", shadow_staff.hot3(pred, o2s, o3s, lv if isinstance(lv, dict) else None))):
                    sp = settle(dict(tickets=tks, stake=len(tks) * shadow_staff.STAKE), result) if tks else None
                    st[pk] = list(sp) if sp else 0
                if date >= OUTW_SINCE:   # 外の1着専門(記録だけ・4,000円/頭)
                    tks = shadow_staff.out_win(pred, o2s, lv if isinstance(lv, dict) else None)
                    sp = settle(dict(tickets=tks, stake=sum(t["units"] for t in tks) * 100), result) if tks else None
                    st["outW"] = list(sp) if sp else 0
                    tks = shadow_staff.in_sec(pred, o2s, o3s, lv if isinstance(lv, dict) else None)
                    sp = settle(dict(tickets=tks, stake=sum(t["units"] for t in tks) * 100), result) if tks else None
                    st["inSec"] = list(sp) if sp else 0
                    tks = shadow_staff.in_win(pred, o2s, lv if isinstance(lv, dict) else None)
                    sp = settle(dict(tickets=tks, stake=sum(t["units"] for t in tks) * 100), result) if tks else None
                    st["inW"] = list(sp) if sp else 0
            rp = replay.get(key)
            if rp and pred and date >= ORG_SINCE:   # 今の方法で再生(確定オッズ)した時の、最終決裁者の採用
                ch = []
                for pr in org_tree.decide(org_tree.proposals({n: pl for n, pl in rp.items() if not pl.get("skip")}, pred), conf_for(date), adopt=org_tree.adopt_for(date)):
                    sp = settle(dict(tickets=pr["tickets"], stake=pr["stake"], bet=pr["bet"]), result)
                    if sp:
                        ch.append(sp)
                st["kessai_r"] = [sum(a for a, _ in ch), round(sum(b for _, b in ch))] if ch else 0
            if b.get("replay_only"):
                out.append(dict(d=date, v=jcd, r=int(race), res=result["combo3t"], pay=int(result["payout3t"]), s=st,
                                t=(pred or {}).get("deadline", "")))
                continue
            st_ka = None
            c_a = None   # 決裁者C(重ね型)の、Aの採用を強弱つけて買った分 [投資, 払戻]
            if pred and date >= ORG_SINCE:   # 予想組織: 頭ごとの提案の記録と、決裁者A(自信度型)の判断
                live_plans = {n: pl for n, pl in plans.items() if isinstance(st.get(n), list)}
                live_plans = _kessai_plans(date, key, pred, b, live_plans)
                props = org_tree.proposals(live_plans, pred)
                pp = []
                for pr in props:
                    sp = settle(dict(tickets=pr["tickets"], stake=pr["stake"], bet=pr["bet"]), result)
                    if sp:
                        pr["ret"], pr["paid"] = sp[1], sp[0]   # 投資は返還分を引いたもの
                        pp.append([pr["leaf"], pr["tags"], sp[0], round(sp[1]), round(org_tree.conf_of(pr, conf_for(date)), 3), pr["head"]])
                if props:
                    chosen = [pr for pr in org_tree.decide(props, conf_for(date), adopt=org_tree.adopt_for(date)) if "ret" in pr]
                    st["kessai"] = [sum(c["paid"] for c in chosen), round(sum(c["ret"] for c in chosen))] if chosen else 0
                    # 社員候補(記録だけ・10/20から): 裏の穴の頭が「イン以外で一番来そうな艇」(情報部の1着確率)と同じ時
                    tri = pred.get("tri")
                    wf = None
                    if tri:
                        p1 = [sum(tri[bet_mod.PI[(i, j, k)]] for j in range(6) for k in range(6) if len({i, j, k}) == 3)
                              for i in range(6)]
                        top = max(range(1, 6), key=lambda i: p1[i]) + 1   # コース
                        mt = [c for c in chosen if c["leaf"].startswith("out.") and c.get("course") == top]
                        st["uraM"] = [sum(c["paid"] for c in mt), round(sum(c["ret"] for c in mt))] if mt else 0
                        st["uraM2"] = ([sum(c["paid"] for c in chosen + mt), round(sum(c["ret"] for c in chosen + mt))]
                                       if chosen else 0)
                        # 社員候補(記録だけ・10/20から): 裏の穴のうち、1着専門が頭を市場の1.2倍以上と見る時だけ(45秒前のオッズ)
                        o2k = {c: v for c, v in zip(bet_mod.ODDS2_ORDER, ((b.get("stages") or {}).get("直前") or {}).get("o2") or []) if v}
                        lvk = _entries(date).get(key)
                        wf = shadow_staff.win_ratio(pred, o2k, lvk if isinstance(lvk, dict) else None) if o2k else None
                        if wf:
                            fz = [c for c in chosen if c["leaf"].startswith("out.") and wf[c["course"] - 1] >= 1.2]
                            st["uraF"] = [sum(c["paid"] for c in fz), round(sum(c["ret"] for c in fz))] if fz else 0
                    if date >= KESSAI_C_SINCE:   # 決裁者B(厳選型・10/20から): Aの採用のうち、1着専門の後押し(比1.2以上)があるものだけ
                        sel = [c for c in chosen if wf and wf[c["course"] - 1] >= 1.2]
                        st["kessaiB"] = [sum(c["paid"] for c in sel), round(sum(c["ret"] for c in sel))] if sel else 0
                    if date >= KESSAI_C_SINCE and chosen:
                        # 決裁者C(重ね型): 1着専門の後押し(比1.2以上)が無ければ1/4、あれば等倍、自信度が採用ライン以上の提案が同じ頭に2つ以上なら×2
                        adopt = org_tree.adopt_for(date)
                        c_a = [0, 0]
                        for c in chosen:
                            f = 1.0 if wf and wf[c["course"] - 1] >= 1.2 else 0.25
                            gv = sum(1 for p in props if p.get("course") == c.get("course") and org_tree.conf_of(p, conf_for(date)) >= adopt)
                            f *= 2 if gv >= 2 else 1
                            c_a[0] += c["paid"] * f
                            c_a[1] += c["ret"] * f
                    picked = {(c["leaf"], c["head"]) for c in chosen}
                    for x in pp:   # 6つ目: 決裁者に採用されたか
                        x.append(int((x[0], x[5]) in picked))
                        del x[5]
                    # 採用した提案の中身(当たったレースの一覧用): [箱, 頭, 買い目, 投資, 払戻]
                    st_ka = [[c["leaf"], c["head"], " ".join(f'{t["combo"]} {t["units"] * 100}円' for t in c["tickets"]), c["paid"], round(c["ret"])]
                             for c in chosen]
            if date >= KESSAI_C_SINCE:   # 決裁者C = Aの採用を強弱つけた分 + 足し買い(熱い一点・外/インの1着専門)
                parts = ([c_a] if c_a and c_a[0] else []) + [st[k] for k in ("hot3",) if isinstance(st.get(k), list)]   # 外の1着専門は10/20からAの社員(pickwin)なので足し買いにしない
                st["kessaiC"] = [round(sum(a for a, _ in parts)), round(sum(r for _, r in parts))] if parts else 0
            rec = dict(d=date, v=jcd, r=int(race), res=result["combo3t"], pay=int(result["payout3t"]), s=st,
                       t=(preds.get(key) or {}).get("deadline", ""))   # 締切時刻(一覧を時刻順に並べる)
            if st_ka:
                rec["ka"] = st_ka
            if fx_rec:
                rec["fx"] = fx_rec
            p2 = plans.get("pick2")
            if p2 and not p2.get("skip"):
                rec["tk"] = [[t["combo"], t["units"], t.get("role")] for t in p2["tickets"]]
            pin = plans.get("pickin")
            if pin and not pin.get("skip") and "pickin" in st:
                rec["pickin_tk"] = [[t["combo"], t["units"], None] for t in pin["tickets"]]
            pbi = plans.get("pickbin")
            if pbi and not pbi.get("skip") and "pickbin" in st:
                rec["pickbin_tk"] = [[t["combo"], t["units"], t.get("role")] for t in pbi["tickets"]]
            p21t = plans.get("pick21t")
            if p21t and not p21t.get("skip") and "pick21t" in st:
                rec["pick21t_tk"] = [[t["combo"], t["units"], t.get("role")] for t in p21t["tickets"]]
            p21 = plans.get("pick21")
            if p21 and not p21.get("skip") and "pick21" in st:
                rec["pick21_tk"] = [[t["combo"], t["units"], None] for t in p21["tickets"]]
            p6a = plans.get("pick6a")
            if p6a and not p6a.get("skip") and "pick6a" in st:
                rec["pick6a_tk"] = [[t["combo"], t["units"], t.get("role")] for t in p6a["tickets"]]
            for pk in ("pickbinx", "pickbinc", "pickbint", "pickura", "pickgen", "pickfav", "pickoutfav") + bet_mod.SANKA_PLANS:
                pl = plans.get(pk)
                if pl and not pl.get("skip") and pk in st:
                    rec[pk + "_tk"] = [[t["combo"], t["units"], t.get("role")] for t in pl["tickets"]]
            pu = plans.get("pickura")
            if pu and not pu.get("skip") and "pickura" in st:
                tags = sorted({t for h in pu.get("heads", []) for t in h.get("tags", [])})
                rec["pickura_tag"] = int(bool(tags))   # 絞り込み候補の印があるか
                rec["pickura_tags"] = tags             # 裏の穴部の部員(印ごと)の集計用
            p2t = plans.get("pick2tan")
            if p2t and not p2t.get("skip") and "pick2tan" in st:
                rec["pick2tan_tk"] = [[t["combo"], t["units"], t.get("role")] for t in p2t["tickets"]]
            if pred and pred.get("scene"):
                h1 = pred["scene"]["head"][0] == 0
                rec.update(h1=h1, mae=any(bb["waku"] != bb["course"] for bb in pred["boats"]),
                           g1=pred["boats"][0]["grade"])
                pick = plans.get("in_hit" if h1 else "out_hit")
                st["switch"] = 0 if (not pick or pick.get("skip")) else list(settle(pick, result))
                fl = _flow(pred, result)
                if fl:
                    st["flow"] = list(fl)
            if pred and date >= ORG_SINCE:
                rec["pp"] = pp
            out.append(rec)
    return out


BETS_JS = r"""
const PL=__PLANS__, VN=__VENUES__;
let D=[];
const $=id=>document.getElementById(id), yen=n=>n.toLocaleString();
function filt(){
  const per=$('per').value, cond=$('cond').value;
  const ds=[...new Set(D.map(x=>x.d))].sort(), last=ds[ds.length-1];
  const keep=per==='all'?null:new Set(ds.slice(-({today:1,d7:7,d30:30})[per]));
  return D.filter(x=>(!keep||keep.has(x.d))&&(cond==='all'||(cond==='h1'&&x.h1===true)||(cond==='h2'&&x.h1===false)
    ||(cond==='mae'&&x.mae)||(cond==='mae2'&&x.mae&&x.h1===false)||(cond==='b'&&(x.g1||'').startsWith('B'))||(cond==='a1'&&x.g1==='A1')));
}
function agg(rows,plan){
  const t={n:0,hit:0,st:0,ret:0,skip:0};
  for(const x of rows){const v=x.s[plan]; if(v===undefined)continue; if(v===0){t.skip++;continue}
    t.n++; t.st+=v[0]; t.ret+=v[1]; if(v[1]>0)t.hit++;}
  return t;
}
function line(name,t){
  if(!t.n) return `<div class="boat"><div style="flex:1"><b>${name}</b><br><span class="sub">購入なし（見送り${t.skip}R）</span></div></div>`;
  const roi=t.ret/t.st, col=roi>=1?'var(--green)':'var(--red)';
  return `<div class="boat"><div style="flex:1"><b>${name}</b>　<b style="color:${col};font-size:17px">${Math.round(roi*100)}%</b><br>`+
   `<span class="sub">${t.n}R購入・${t.hit}R的中（${Math.round(t.hit/t.n*100)}%）・見送り${t.skip}R<br>投資 ${yen(t.st)}円 → 払戻 ${yen(t.ret)}円（${t.ret-t.st>=0?'+':''}${yen(t.ret-t.st)}円）</span></div></div>`;
}
function render(){
  const rows=filt(), g=$('grp').value, sel=$('plan').value;
  const plans=sel==='all'?Object.keys(PL):[sel];
  $('n').textContent=`対象 ${rows.length}レース`;
  if(g==='sum'){ $('out').innerHTML=`<div class="card">${plans.map(p=>line(PL[p],agg(rows,p))).join('')}</div>`; return; }
  const key=g==='day'?(x=>x.d):(x=>x.v), groups={};
  for(const x of rows)(groups[key(x)]=groups[key(x)]||[]).push(x);
  const ks=Object.keys(groups).sort(); if(g==='day')ks.reverse();
  $('out').innerHTML=ks.map(k=>{
    const lab=g==='day'?`${+k.slice(4,6)}月${+k.slice(6)}日`:VN[k];
    return `<h2>${lab} <span class="sub">${groups[k].length}R</span></h2><div class="card">${plans.map(p=>line(PL[p],agg(groups[k],p))).join('')}</div>`;
  }).join('');
}
fetch('/bets-data.json').then(r=>r.json()).then(j=>{D=j;render()});
document.addEventListener('change',e=>{if(['per','cond','grp','plan'].includes(e.target.id))render()});
"""


def archive_body():
    """資料室: 旧プランも含めた試験用買い目の集計(期間・条件・集計単位・買い方で絞り込み)。データは bets-data.json"""
    plans = {**bet_mod.PLANS, **EXTRA_PLANS}
    opt = lambda pairs: "".join(f'<option value="{v}">{t}</option>' for v, t in pairs)
    sel = 'style="font-size:15px;padding:6px;border-radius:8px;border:1px solid var(--bd);background:var(--card);color:var(--tx);width:100%"'
    controls = (
        '<div class="card" style="display:grid;grid-template-columns:1fr 1fr;gap:8px">'
        f'<label class="sub">期間<select id="per" {sel}>{opt([("today", "今日"), ("d7", "直近7日"), ("d30", "直近30日"), ("all", "全期間")])}</select></label>'
        f'<label class="sub">条件<select id="cond" {sel}>{opt([("all", "全レース"), ("h1", "頭注目=1"), ("h2", "頭注目≠1"), ("mae", "進入変化あり"), ("mae2", "進入変化×頭注目≠1"), ("b", "1コースがB級"), ("a1", "1コースがA1")])}</select></label>'
        f'<label class="sub">集計<select id="grp" {sel}>{opt([("sum", "合計"), ("day", "日別"), ("venue", "場別")])}</select></label>'
        f'<label class="sub">買い方<select id="plan" {sel}>{opt([("all", "全部")] + list(plans.items()))}</select></label>'
        '</div><p class="sub" id="n"></p>')
    js = BETS_JS.replace("__PLANS__", json.dumps(plans, ensure_ascii=False)).replace("__VENUES__", json.dumps(VENUES, ensure_ascii=False))
    return (TRIAL_NOTE + controls + '<div id="out"><p class="sub">読み込み中…</p></div>'
            '<p class="sub">結果が出たレースだけを集計しています。「切り替え」「頭-連-流し」は、保存してある予想と結果から計算した仮想の成績です。'
            '「頭-連-流し」は全レースで買った場合なので、条件で「頭注目≠1」などに絞って見てください。</p>'
            f'<script>(()=>{{{js}}})()</script>')


def nige_records():
    """逃げ判定の集計用に、結果が出たレースごとの予想(頭注目・1コース勝率・2〜6コースの確率順)と勝った艇のコースを作る"""
    files = sorted((DATA / "predictions").glob("*.json"))
    if not files:
        return []
    res = load_results(files[0].stem)
    keyed = {(r.date, r.jcd, int(r.race)): r.combo3t
             for r in res.drop_duplicates(["date", "jcd", "race"]).itertuples() if isinstance(r.combo3t, str) and r.combo3t}
    out = []
    for f in files:
        date = f.stem
        live = live_result.load(date)
        for key, pred in json.loads(f.read_text())["races"].items():
            sc = pred.get("scene")
            jcd, race = key.split("-")
            combo = keyed.get((date, jcd, int(race))) or (live.get(key) or {}).get("combo3t")
            if not sc or not isinstance(combo, str) or not combo:
                continue
            course = {b["waku"]: b["course"] for b in pred["boats"]}   # 展示の進入で見たコース
            hp = sc["head_prob"]
            out.append(dict(d=date, v=jcd, r=int(race), h=sc["head"][0] + 1, p1=hp[0],
                            o=[k + 1 for k in sorted(range(1, 6), key=lambda k: -hp[k])[:2]],
                            w=course.get(int(combo.split("-")[0]))))
    return out


NIGE_JS = r"""
const VN=__VENUES__, REF=__REF__;
let D=[];
const $=id=>document.getElementById(id), pct=(a,b)=>b?Math.round(a/b*1000)/10+'%':'―';
function filt(){
  const per=$('per').value, ds=[...new Set(D.map(x=>x.d))].sort();
  const keep=per==='all'?null:new Set(ds.slice(-({today:1,d7:7,d30:30})[per]));
  return D.filter(x=>!keep||keep.has(x.d));
}
const row=(label,a,n,ref)=>`<div class="boat"><div style="flex:1"><b>${label}</b><br><span class="sub">${a}/${n}R・過去の目安 ${ref}</span></div><b style="font-size:20px">${pct(a,n)}</b></div>`;
function block(rs){
  const h1=rs.filter(x=>x.h===1), h2=rs.filter(x=>x.h!==1), lost=rs.filter(x=>x.w!==1), lost2=lost.filter(x=>x.h!==1);
  const c=(arr,f)=>arr.filter(f).length;
  let s='<div class="card"><b>逃げ予想（頭注目=1）</b>'+row('インが逃げた',c(h1,x=>x.w===1),h1.length,REF.h1)+'</div>';
  s+='<div class="card"><b>イン飛び予想（頭注目≠1）</b>'+row('インが飛んだ',c(h2,x=>x.w!==1),h2.length,REF.h2)
    +row('頭注目の艇が1着',c(h2,x=>x.w===x.h),h2.length,REF.h2head)+'</div>';
  s+='<div class="card"><b>インが飛んだレースの頭（2〜6コースの確率順）</b>'
    +row('確率1位が1着',c(lost,x=>x.w===x.o[0]),lost.length,REF.o1)
    +row('確率2位までに1着',c(lost,x=>x.o.includes(x.w)),lost.length,REF.o2)
    +row('うちイン飛び予想だったレース：確率1位が1着',c(lost2,x=>x.w===x.o[0]),lost2.length,REF.o1h2)
    +row('うちイン飛び予想だったレース：2位までに1着',c(lost2,x=>x.o.includes(x.w)),lost2.length,REF.o2h2)+'</div>';
  const bands=[[0,.3,'30%未満'],[.3,.45,'30〜45%'],[.45,.6,'45〜60%'],[.6,.75,'60〜75%'],[.75,1.01,'75%以上']];
  s+='<div class="card"><b>1コースの1着確率（予想）と実際に逃げた率</b>'+bands.map(([lo,hi,lab],i)=>{
    const g=rs.filter(x=>x.p1>=lo&&x.p1<hi), avg=g.length?Math.round(g.reduce((a,x)=>a+x.p1,0)/g.length*100):0;
    return row(`予想 ${lab}（平均${avg}%）`,c(g,x=>x.w===1),g.length,REF.band[i]);
  }).join('')+'</div>';
  return s;
}
function render(){
  const rows=filt(), g=$('grp').value;
  $('n').textContent=`対象 ${rows.length}レース`;
  if(g==='sum'){ $('out').innerHTML=block(rows); return; }
  const key=g==='day'?(x=>x.d):(x=>x.v), groups={};
  for(const x of rows)(groups[key(x)]=groups[key(x)]||[]).push(x);
  const ks=Object.keys(groups).sort(); if(g==='day')ks.reverse();
  $('out').innerHTML=ks.map(k=>`<h2>${g==='day'?`${+k.slice(4,6)}月${+k.slice(6)}日`:VN[k]} <span class="sub">${groups[k].length}R</span></h2>`+block(groups[k])).join('');
}
fetch('/nige-data.json').then(r=>r.json()).then(j=>{D=j;render()});
document.addEventListener('change',e=>{if(['per','grp'].includes(e.target.id))render()});
"""

# 2025年1月〜2026年9月(約9.2万R)の検証値。過去の結果に当時のモデルをあてて出したもの(実際の進入で判定)
NIGE_REF = dict(h1="65.2%", h2="65.0%", h2head="30.4%", o1="46.2%", o2="71.6%", o1h2="47.6%", o2h2="73.3%",
                band=["22.9%", "38.0%", "52.7%", "67.5%", "79.4%"])


def nige_body():
    """逃げ判定係の部屋の中身(インが逃げたか・飛んだときに頭を当てたか)。データは nige-data.json"""
    opt = lambda pairs: "".join(f'<option value="{v}">{t}</option>' for v, t in pairs)
    sel = 'style="font-size:15px;padding:6px;border-radius:8px;border:1px solid var(--bd);background:var(--card);color:var(--tx);width:100%"'
    controls = (
        '<div class="card" style="display:grid;grid-template-columns:1fr 1fr;gap:8px">'
        f'<label class="sub">期間<select id="per" {sel}>{opt([("today", "今日"), ("d7", "直近7日"), ("d30", "直近30日"), ("all", "全期間")])}</select></label>'
        f'<label class="sub">集計<select id="grp" {sel}>{opt([("sum", "合計"), ("day", "日別"), ("venue", "場別")])}</select></label>'
        '</div><p class="sub" id="n"></p>')
    js = NIGE_JS.replace("__VENUES__", json.dumps(VENUES, ensure_ascii=False)).replace("__REF__", json.dumps(NIGE_REF, ensure_ascii=False))
    return (controls + '<div id="out"><p class="sub">読み込み中…</p></div>'
            '<p class="sub">結果が出たレースだけを集計しています。コースは展示の進入で見ています。「過去の目安」は、2025年1月〜2026年9月の約9.2万レースに'
            'モデルをあてて出した数字です。「2〜6コースの確率順」は、1コースを除いたモデルの1着確率の高い順です。</p>'
            f'<script>(()=>{{{js}}})()</script>')


PICK_HI = 0.80   # 1コース1着確率がこれ以上なら「かなり確度高い逃げ」
PICK_LO = 0.20   # pressed判定の中で、これ未満なら「厳選・逃げないレース」
# 2022年1月〜2026年9月(約24.5万R、うちpressed判定8万R)を本番と同じModelで再現した検証値
# lo_head2は/nige.htmlの「確率2位までに1着(うちイン飛び予想だったレース)」の全期間値を流用(厳選帯専用の値ではない目安)
PICK_REF = dict(hi="83.3%", lo="84.0%", lo_head="46.7%", lo_head2=NIGE_REF["o2h2"])


def pick_entry(date, jcd, info, pred, now):
    """予想(final版・締切前)から、1コース1着確率が極端に高い/低いレースだけを抜き出す。
    閾値はscripts/analyze_escape_miss.pyのバックテストに基づく(PICK_REF)。
    厳選帯の頭候補は、/nige.htmlの集計(nige_records)と同じ「確率の素の順位」で上位2艇(本命・次点)を出す
    (scene.pyのshuは意外性を混ぜた選び方で定義が別物になるため、ここでは使わない)。"""
    if not pred or pred.get("version") != "final" or now >= dl_dt(date, info["deadline"]):
        return None
    sc = pred["scene"]
    nige = sc["nige"]
    waku = [b["waku"] for b in pred["boats"]]
    base = dict(date=date, jcd=jcd, race=info["race"], deadline=info["deadline"])
    if nige >= PICK_HI:
        return ("hi", dict(base, nige=nige, waku1=waku[0]))
    if sc["pressed"] and nige < PICK_LO:
        hp = sc["head_prob"]
        top2 = sorted(range(1, 6), key=lambda k: -hp[k])[:2]
        scen_by_w = {}
        for s in pred.get("scenarios", {}).get("list", []):
            scen_by_w.setdefault(s["w"], s)
        cands = []
        for k in top2:
            s = scen_by_w.get(k)
            cands.append(dict(waku=waku[k], prob=hp[k],
                              move=(s["m"] if s else ""),
                              lines=(s["lines"] if s else [sc["lines"].get(str(k), "")])))
        return ("lo", dict(base, nige=nige, cands=cands))
    return None


PICK_JS = r"""
const VN=__VENUES__, REF=__REF__, HI=__HI__, LO=__LO__;
let D=[];
const $=id=>document.getElementById(id), pct=(a,b)=>b?Math.round(a/b*1000)/10+'%':'―';
function filt(){
  const per=$('per3').value, ds=[...new Set(D.map(x=>x.d))].sort();
  const keep=per==='all'?null:new Set(ds.slice(-({today:1,d7:7,d30:30})[per]));
  return D.filter(x=>!keep||keep.has(x.d));
}
const row=(label,a,n,ref)=>`<div class="boat"><div style="flex:1"><b>${label}</b><br><span class="sub">${a}/${n}R・過去の目安 ${ref}</span></div><b style="font-size:20px">${pct(a,n)}</b></div>`;
function render(){
  const rows=filt(), hi=rows.filter(x=>x.p1>=HI), lo=rows.filter(x=>x.p1<LO);
  const c=(arr,f)=>arr.filter(f).length, lostHit=lo.filter(x=>x.w!==1);
  $('n3').textContent=`対象 ${rows.length}レース（うち確度高い逃げ ${hi.length}R・厳選の逃げないレース ${lo.length}R）`;
  let s='<div class="card"><b>かなり確度高い逃げ（1コース1着確率80%以上）</b>'+row('実際に逃げ切った',c(hi,x=>x.w===1),hi.length,REF.hi)+'</div>';
  s+='<div class="card"><b>厳選・逃げないレース（1コース1着確率20%未満）</b>'+row('実際に1コース以外が勝った',c(lo,x=>x.w!==1),lo.length,REF.lo)
    +row('うち本命(確率1位)が1着',c(lostHit,x=>x.w===x.o[0]),lostHit.length,REF.lo_head)
    +row('うち本命・次点のどちらかが1着',c(lostHit,x=>x.o.includes(x.w)),lostHit.length,REF.lo_head2)+'</div>';
  $('out3').innerHTML=s;
}
fetch('/nige-data.json').then(r=>r.json()).then(j=>{D=j;render()});
document.addEventListener('change',e=>{if(e.target.id==='per3')render()});
"""


def pick_body(hi_list, lo_list):
    """逃げ判定係の「今日の極端なレース」(今日・明日の厳選レース一覧+この基準自体の過去集計)。一覧は静的、集計はnige-data.jsonを流用"""
    def link(x):
        return f"/{x['date']}/{x['jcd']}/{x['race']:02d}-turn.html"
    hi_cards = "".join(
        f'<a class="boat" href="{link(x)}">{chip(x["waku1"])}<div><b>{VENUES[x["jcd"]]} {x["race"]}R</b> '
        f'<span class="sub">締切{x["deadline"]}・1コース1着確率{x["nige"]:.0%}</span></div></a>'
        for x in sorted(hi_list, key=lambda x: -x["nige"]))
    def cand_block(c, label):
        return (f'<div style="display:flex;gap:10px;width:100%">{chip(c["waku"])}<div style="flex:1">'
                f'<span class="sub">{label}・確率{c["prob"]:.0%}{"・" + c["move"] if c["move"] else ""}</span>'
                f'<p class="sub" style="margin:2px 0 0;color:var(--tx)">{html.escape("。".join(c["lines"]))}。</p></div></div>')
    lo_cards = "".join(
        f'<a class="boat" href="{link(x)}" style="flex-direction:column;align-items:flex-start;gap:6px">'
        f'<div><b>{VENUES[x["jcd"]]} {x["race"]}R</b> <span class="sub">締切{x["deadline"]}・1コース1着確率{x["nige"]:.0%}</span></div>'
        + cand_block(x["cands"][0], "本命") + cand_block(x["cands"][1], "次点") + '</a>'
        for x in sorted(lo_list, key=lambda x: x["nige"]))
    NONE_MSG = '<p class="sub">現在、該当レースはありません。</p>'
    opt = lambda pairs: "".join(f'<option value="{v}">{t}</option>' for v, t in pairs)
    sel = 'style="font-size:15px;padding:6px;border-radius:8px;border:1px solid var(--bd);background:var(--card);color:var(--tx);width:100%"'
    js = (PICK_JS.replace("__VENUES__", json.dumps(VENUES, ensure_ascii=False)).replace("__REF__", json.dumps(PICK_REF, ensure_ascii=False))
          .replace("__HI__", str(PICK_HI)).replace("__LO__", str(PICK_LO)))
    return ('<p class="sub">今日・明日の確定済み予想(展示反映後)から、1コースの1着確率が極端に高い/低いレースだけを抜き出しています。'
              'それ以外の帯は「よくわからない」として対象外です。厳選レースの頭は、本命(確率1位)だけだと的中率が低いので次点(確率2位)も併記しています。</p>'
            + f'<h2>かなり確度高い逃げ（1コース1着確率{PICK_HI:.0%}以上）</h2>'
            + f'<div class="card list">{hi_cards or NONE_MSG}</div>'
            + f'<h2>厳選・逃げないレース（1コース1着確率{PICK_LO:.0%}未満）</h2>'
            + f'<div class="card list">{lo_cards or NONE_MSG}</div>'
            + '<h2>この基準自体の成績</h2>'
            + '<div class="card" style="display:grid;grid-template-columns:1fr;gap:8px">'
            + f'<label class="sub">期間<select id="per3" {sel}>{opt([("today", "今日"), ("d7", "直近7日"), ("d30", "直近30日"), ("all", "全期間")])}</select></label>'
            + '</div><p class="sub" id="n3"></p><div id="out3"><p class="sub">読み込み中…</p></div>'
            + '<p class="sub">結果が出たレースのみ集計。「過去の目安」は2022年1月〜2026年9月・約24.5万レースにこの基準をあてた検証値。</p>'
            + f'<script>(()=>{{{js}}})()</script>')


DASH_PLANS = {"pickura": "B級イン・裏の穴", "pickbin": "B級イン・2連単"}
SHADOW_LABELS = {"pickoutfav": "外の本命", "pickfav": "イン頭・軽視された2着", "pickgen": "一般職・市場が軽く見る艇", "pickbinc": "B級イン・凪で強敵なし", "pickbint": "B級イン・凪で展示1位",
                 "pickbinx": "B級イン・絞り込み", "pickin": "内・2連単・逆張り", "pick21": "2差し1残し・2連単2-1",
                 "pick21t": "2差し1残し・3連単2-1-□", "pick6a": "6コースだけA級・2連単",
                 "pick2tan": "外・2連単"}   # 立説中(総合収支に含めない)。並びが優先度(上ほど有望)
# 3連単(pick2)は実オッズで良い結果が出てないためダッシュボードには出さない。
# bet.py側の集計(bets-data.json)は変わらず続けているので、見たくなれば/ops/pick2.htmlで確認できる。

UPCOMING_JS = r"""
function renderUpcoming(el, U, PL, VN, only){
  const rows=U.filter(x=>!only||(Array.isArray(only)?only.includes(x.p):x.p===only));
  if(!rows.length){ el.innerHTML='<div class="card"><b>これから</b><p class="sub" style="margin:4px 0 0">締切前に決めた買い目はまだありません(締切5分前に候補、2分前に確定します)。</p></div>'; return; }
  el.innerHTML='<div class="card"><b>これから</b> <span class="sub">締切前に決めた買い目・結果待ち</span>'+rows.map(x=>
    `<div class="boat" style="flex-direction:column;align-items:flex-start;gap:2px"><div><b>${x.t} ${VN[x.v]} ${x.r}R</b>`+
    (x.st?` <span class="lab" style="background:${x.st==='確定'?'#7A5AE0':'#9aa0a8'}">${x.st}</span>`:'')+
    ((only&&!Array.isArray(only))?'':` <span class="sub">${PL[x.p]||x.p}</span>`)+`</div><div>`+
    x.tk.map(([c,u,role,o])=>{const mk=(role||'').includes('【');   // 絞り込み候補の印がある頭は目立たせる
      return `<span style="${mk?'background:var(--mark);border-radius:6px;padding:1px 4px':''}"><span class="tri-chip" style="font-size:15px">${c}</span> <span class="sub">${mk?'★':''}${role?role+' ':''}${(u*100).toLocaleString()}円${o?'・'+o+'倍':''}</span></span>`;}).join('　')+
    `</div></div>`).join('')+'<p class="sub" style="margin:6px 0 0">締切5分前に「候補」、2分前にその時のオッズで「確定」。オッズは決めた時点のもの。</p></div>';
}
"""

CHART_JS = r"""
// 日ごとの損益: 累積の折れ線 + 日別の棒(0を境に上下) + タップで日の詳細 + 表
const WD='日月火水木金土';
function mdw(d){const t=new Date(+d.slice(0,4),+d.slice(4,6)-1,+d.slice(6));return `${+d.slice(4,6)}/${+d.slice(6)}(${WD[t.getDay()]})`;}
function sgn(n){return (n>0?'+':'')+n.toLocaleString()+'円';}
function pnlCharts(el, days){
  // days: [{d, st, ret, n, hit}] 日付順
  if(!days.length){ el.innerHTML='<p class="sub">まだ実績がありません</p>'; return; }
  let cum=0; const pts=days.map(x=>{cum+=x.ret-x.st; return {...x, pl:x.ret-x.st, cum};});
  const pct=(r,s)=>{if(!s) return 0; const v=r/s*100; return v<100?Math.floor(v):Math.round(v);};
  const W=600, H1=130, H2=90, n=pts.length, step=W/n, uid='c'+Math.random().toString(36).slice(2,8);
  const cx=i=>step*(i+0.5);
  const cmin=Math.min(0,...pts.map(p=>p.cum)), cmax=Math.max(0,...pts.map(p=>p.cum)), cr=(cmax-cmin)||1;
  const cy=v=>6+(cmax-v)/cr*(H1-12);
  const line=`0,${cy(0).toFixed(1)} `+pts.map((p,i)=>`${cx(i).toFixed(1)},${cy(p.cum).toFixed(1)}`).join(' ');   // 0円から始める
  const pmax=Math.max(1,...pts.map(p=>Math.abs(p.pl))), mid=H2/2, by=v=>mid-v/pmax*(mid-4);
  const bw=Math.max(2,Math.min(26,step-2));
  const bars=pts.map((p,i)=>{const y=by(p.pl), top=Math.min(y,mid), h=Math.max(1.5,Math.abs(y-mid));
    return `<rect x="${(cx(i)-bw/2).toFixed(1)}" y="${top.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="2" fill="var(${p.pl>=0?'--gain':'--loss'})"/>`;}).join('');
  const hits=pts.map((p,i)=>`<rect data-i="${i}" x="${(i*step).toFixed(1)}" y="0" width="${step.toFixed(1)}" height="100%" fill="transparent"/>`).join('');
  const last=pts[n-1];
  el.innerHTML=
    `<div class="sub" style="display:flex;justify-content:space-between"><span>累計損益の推移</span><span>最高 ${sgn(cmax)}</span></div>`+
    `<svg id="${uid}a" viewBox="0 0 ${W} ${H1}" width="100%" height="${H1}" preserveAspectRatio="none" style="touch-action:pan-y">`+
      `<line x1="0" x2="${W}" y1="${cy(0)}" y2="${cy(0)}" stroke="var(--sub)" stroke-width="1" stroke-dasharray="3,3" vector-effect="non-scaling-stroke"/>`+
      `<line class="gd" x1="0" x2="0" y1="0" y2="${H1}" stroke="var(--sub)" stroke-width="1" vector-effect="non-scaling-stroke" visibility="hidden"/>`+
      `<polyline points="${line}" fill="none" stroke="var(--ac)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`+
      hits+`</svg>`+
    `<div class="sub" style="display:flex;justify-content:space-between;margin-bottom:6px"><span>最低 ${sgn(cmin)}</span><span>${n}日分</span></div>`+
    `<div class="sub">日別の損益 <span style="color:var(--gain)">■</span>プラス <span style="color:var(--loss)">■</span>マイナス</div>`+
    `<svg id="${uid}b" viewBox="0 0 ${W} ${H2}" width="100%" height="${H2}" preserveAspectRatio="none" style="touch-action:pan-y">`+
      `<line x1="0" x2="${W}" y1="${mid}" y2="${mid}" stroke="var(--bd)" stroke-width="1" vector-effect="non-scaling-stroke"/>`+
      `<line class="gd" x1="0" x2="0" y1="0" y2="${H2}" stroke="var(--sub)" stroke-width="1" vector-effect="non-scaling-stroke" visibility="hidden"/>`+
      bars+hits+`</svg>`+
    `<div class="sub" style="display:flex;justify-content:space-between"><span>${mdw(pts[0].d)}</span><span>${mdw(last.d)}</span></div>`+
    `<div id="${uid}i" class="card" style="margin:8px 0 4px;padding:8px 10px;background:var(--off)"></div>`+
    `<details><summary class="sub">日別の表を見る</summary><div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:6px;white-space:nowrap">`+
      `<tr class="sub" style="text-align:right"><th style="text-align:left">日付</th><th>レース</th><th>的中</th><th>的中率</th><th>投資</th><th>払戻</th><th>損益</th><th>回収率</th><th>累計</th></tr>`+
      pts.slice().reverse().map(p=>`<tr style="text-align:right;border-top:1px solid var(--bd)"><td style="text-align:left">${mdw(p.d)}</td><td>${p.n}</td><td>${p.hit}</td><td>${p.n?Math.round(p.hit/p.n*100):0}%</td>`+
        `<td>${p.st.toLocaleString()}</td><td>${p.ret.toLocaleString()}</td><td style="font-weight:700">${sgn(p.pl)}</td><td>${pct(p.ret,p.st)}%</td><td>${sgn(p.cum)}</td></tr>`).join('')+
    `</table></div></details>`;
  const info=document.getElementById(uid+'i');
  const show=i=>{const p=pts[i];
    info.innerHTML=`<b>${mdw(p.d)}</b>　損益 <b>${sgn(p.pl)}</b>（回収率 ${pct(p.ret,p.st)}%）<br>`+
      `<span class="sub">${p.n}レース・的中 ${p.hit}（${p.n?Math.round(p.hit/p.n*100):0}%）・投資 ${p.st.toLocaleString()}円 → 払戻 ${p.ret.toLocaleString()}円・累計 ${sgn(p.cum)}</span>`;
    for(const k of ['a','b']){const g=document.querySelector('#'+uid+k+' .gd'); g.setAttribute('x1',cx(i)); g.setAttribute('x2',cx(i)); g.setAttribute('visibility','visible');}
  };
  for(const k of ['a','b']) document.getElementById(uid+k).addEventListener('pointermove',e=>{const r=e.target.closest('rect[data-i]'); if(r) show(+r.dataset.i);});
  for(const k of ['a','b']) document.getElementById(uid+k).addEventListener('click',e=>{const r=e.target.closest('rect[data-i]'); if(r) show(+r.dataset.i);});
  show(n-1);
}
"""

PLAN_SINCE = {"pick2": bet_mod.PICK2_LOGIC_SINCE, "pick2tan": bet_mod.PICK2TAN_LOGIC_SINCE,
              "pickin": bet_mod.PICKIN_LOGIC_SINCE, "pickbin": bet_mod.PICKBIN_LOGIC_SINCE,
              "pick6a": bet_mod.PICK6A_LOGIC_SINCE, "pick21": bet_mod.PICK21_LOGIC_SINCE,
              "pick21t": bet_mod.PICK21_LOGIC_SINCE, "pickbinx": bet_mod.PICKBINX_LOGIC_SINCE,
              "pickbinc": bet_mod.PICKBINC_LOGIC_SINCE, "pickbint": bet_mod.PICKBINT_LOGIC_SINCE,
              "pickura": bet_mod.PICKURA_LOGIC_SINCE,
              "sankabin": bet_mod.SANKA_LOGIC_SINCE, "sankagap": bet_mod.SANKA_LOGIC_SINCE,
              "pickgen": bet_mod.GEN_LOGIC_SINCE,
              "pickfav": bet_mod.FAV_LOGIC_SINCE,
              "pickoutfav": bet_mod.OUTFAV_LOGIC_SINCE}
SANKA_LABELS = {"sankabin": "参加枠・自信のB級イン", "sankagap": "参加枠・市場より強いイン"}
ALL_PLAN_LABELS = {"pick2": "外・3連単", **DASH_PLANS, **SHADOW_LABELS, **SANKA_LABELS}   # 詳細ページ用。pick2はダッシュボード非表示だがページ自体は残す



# ===== 予想組織図 =====
# 試験用買い目の収支を「予想する子たちの組織」として見せる。
# 最上位に最終決裁者、その下に情報部(見立てを出すだけで買わない係)と買い目予想部(部長=買い目の型、部員=絞り込み)。
# 数字はすべて bets-data.json(実際に記録した買い目の精算)から出す。情報部の静的な数字は確定オッズでの検証値。

def robot_svg(color, acc="antenna", size=56, badge=False, dim=False):
    """ロボットのキャラ(インラインSVG)。acc: antenna / crown / glasses / headset / visor / radar"""
    eye = "#7FE3FF"
    top = {
        "crown": '<polygon points="19,13 22,1 29,8 32,0 35,8 42,1 45,13" fill="#F2C230" stroke="#B8901A" stroke-width="1"/>',
        "radar": f'<path d="M22 9 A12 12 0 0 1 42 9" fill="none" stroke="{color}" stroke-width="2.5"/><path d="M26 10 A7 7 0 0 1 38 10" fill="none" stroke="{color}" stroke-width="2.5"/><line x1="32" y1="6" x2="32" y2="13" stroke="{color}" stroke-width="2.5"/>',
    }.get(acc, f'<line x1="32" y1="4" x2="32" y2="13" stroke="{color}" stroke-width="2.5"/><circle cx="32" cy="4" r="3.2" fill="{color}"/>')
    face = {
        "glasses": f'<circle cx="25" cy="28" r="5.6" fill="none" stroke="#fff" stroke-width="1.6"/><circle cx="39" cy="28" r="5.6" fill="none" stroke="#fff" stroke-width="1.6"/><line x1="30.6" y1="28" x2="33.4" y2="28" stroke="#fff" stroke-width="1.6"/>',
        "headset": f'<path d="M10 28 A22 22 0 0 1 54 28" fill="none" stroke="#2B2F36" stroke-width="3"/><path d="M54 32 Q54 42 44 42" fill="none" stroke="#2B2F36" stroke-width="2"/><circle cx="43" cy="42" r="2.2" fill="#2B2F36"/>',
        "visor": '<rect x="17" y="24" width="30" height="8" rx="4" fill="#FF6B6B" opacity=".85"/>',
    }.get(acc, "")
    star = ('<polygon points="32,50 34,55 39.5,55 35,58.3 36.8,63 32,60 27.2,63 29,58.3 24.5,55 30,55" fill="#F2C230"/>'
            if badge else "")
    return (f'<svg viewBox="0 0 64 64" width="{size}" height="{size}" aria-hidden="true" style="flex:none{";opacity:.55;filter:grayscale(.6)" if dim else ""}">'
            + top
            + f'<rect x="6" y="23" width="5" height="12" rx="2.5" fill="{color}"/><rect x="53" y="23" width="5" height="12" rx="2.5" fill="{color}"/>'
            f'<rect x="10" y="12" width="44" height="34" rx="11" fill="{color}"/>'
            '<rect x="16" y="18" width="32" height="21" rx="7" fill="#17202B"/>'
            f'<circle cx="25" cy="28" r="3.3" fill="{eye}"/><circle cx="39" cy="28" r="3.3" fill="{eye}"/>'
            f'<rect x="28" y="33.5" width="8" height="2" rx="1" fill="{eye}"/>'
            + face
            + f'<rect x="18" y="47" width="28" height="16" rx="6" fill="{color}" opacity=".8"/>'
            + star + '</svg>')


def _plan_status(pk):
    if pk in bet_mod.OPS_PLANS:
        return "運用中"
    if pk in bet_mod.SANKA_PLANS:
        return "参加枠"
    if pk in bet_mod.SHADOW_PLANS:
        return "立説中"
    return "休止"


ORG_KESSAI = dict(id="kessai", name="最終決裁者", color="#7A5AE0", acc="crown",
                  role="レースごとに、どの部の提案を採るか(全部見送りも含めて)決める")
ORG_INFO = [
    dict(id="jisseki", name="実績予想くん", role="本予想(過去の成績から1着確率・展開・3連単確率)", color="#2A8C82", acc="glasses",
         stat="インの勝率はほぼピッタリ"),
    dict(id="gbm", name="実績予想くん2号", role="オッズを見ない1着確率(GBM)", color="#3D7FD0", acc="glasses",
         stat="市場が軽く見る外の艇を見つける"),
    dict(id="market", name="市場オッズ係", role="オッズから「みんなが思う確率」と券種の値段", color="#D9861A", acc="headset",
         stat="全体では一番正確"),
    dict(id="nige", name="逃げ判定係", role="イン逃げ型か外頭型か、本物のB級インか", color="#C2533A", acc="visor",
         stat="1か外かの当たり66%"),
    dict(id="chokuzen", name="直前情報係", role="展示タイム・展示ST・風・波・進入を集めて渡す", color="#5B6B80", acc="radar",
         stat="単独では効かない・材料係"),
]
def _org_page(title, path, body, upcoming=None):
    """組織図系のページ。upcoming: 「これから」に出すプラン(Noneなら出さない、[]なら全運用プラン)"""
    js = (ORG_JS.replace("__ORG__", json.dumps(_org_json(), ensure_ascii=False))
                .replace("__VENUES__", json.dumps(VENUES, ensure_ascii=False)))
    js = UPCOMING_JS + CHART_JS + js
    if upcoming is not None:
        only = upcoming or list(bet_mod.OPS_PLANS)
        js += (f"fetch('/bets-upcoming.json').then(r=>r.json()).then(u=>renderUpcoming($('up'),u,ORG.labels,VN,"
               f"{json.dumps(only)})).catch(()=>{{}});")
    return page(title, body + f'<script>{js}</script>', "", path, noindex=True)


def _room_head(color, acc, name, role, badge=False, back="/ops.html", back_label="組織図に戻る"):
    return (f'<a class="back-lk" href="{back}">← {back_label}</a>'
            f'<div class="room-head">{robot_svg(color, acc, 76, badge)}<div><h1 style="margin:0">{name}</h1>'
            f'<span class="sub">{role}</span></div></div>')


ORG_SINCE = bet_mod.PICKURA_LOGIC_SINCE   # 組織(提案ごとの記録・決裁者)の集計開始日
GROUP_COLOR = {"in": "#2F6BD8", "in.B": "#2F6BD8", "in.A": "#5B8DEF",
               "out": "#B0457A", "out.c2": "#3C8C4E", "out.c34": "#B0457A", "out.c56": "#8A6A2E"}
# ③の箱ごとに、どの説(プラン)が入りうるか。ここに無くても自信度の表や記録に出てきた箱は足す
TREE_SKELETON = {
    "in.B": ["pickinwin", "pickbin", "pickbinc", "pickbint", "pickbinx", "pickin", "pick6a", "pickfav", "pickgen", "sankabin", "sankagap"],
    "in.A": ["pickinwin", "pickin", "pick6a", "pickfav", "pickgen", "sankagap"],
    "out.c2": ["pickura", "pickgen", "pickoutfav"],
    "out.c34": ["pickura", "pickwin", "pickgen", "pickoutfav"],
    "out.c56": ["pickura", "pickgen", "pickoutfav"],
}
URA_TAGS = {"out.c2": ["tagM", "tagQ"], "out.c34": ["tagM", "tagQ", "tagW"], "out.c56": ["tagM", "tagQ"]}


def _tree_nodes():
    """木の箱の一覧 {id: dict(parent, label, level, color, plan, conf...)}。自信度は data/org/confidence.json"""
    conf = org_tree.load_confidence()
    ids = {"in", "out"} | set(TREE_SKELETON)
    for g, plans in TREE_SKELETON.items():
        ids |= {f"{g}.{pk}" for pk in plans}
    for g, tags in URA_TAGS.items():
        ids |= {f"{g}.pickura.{t}" for t in tags}
    ids |= set(conf)
    nodes = {}
    for nd in ids:
        p = nd.split(".")
        plan = p[2] if len(p) >= 3 else None
        label = (org_tree.NODES.get(nd) or (org_tree.TAG_LABEL.get(p[-1]) if len(p) == 4 else None)
                 or ALL_PLAN_LABELS.get(plan, plan))
        c = conf.get(nd, {})
        nodes[nd] = dict(parent=".".join(p[:-1]) or None, label=label, level=len(p) + 1, plan=plan,
                         color=GROUP_COLOR.get(".".join(p[:2]), "#6B7079"),
                         status=_plan_status(plan) if plan else "",
                         conf=c.get("conf"), n=c.get("n", 0), roi=c.get("roi"),
                         hit_rate=c.get("hit_rate"), avg_mult=c.get("avg_mult"))
    order = {pk: i for i, pk in enumerate(ORG_PLANS_ORDER)}
    for nd, x in nodes.items():
        x["children"] = sorted([k for k, y in nodes.items() if y["parent"] == nd],
                               key=lambda k: (order.get(k.split(".")[2], 99) if k.count(".") == 2 else 0, k))
    return nodes


ORG_PLANS_ORDER = ["pickbin", "pickbinc", "pickbint", "pickbinx", "pickin", "pick6a", "pickfav", "pickgen", "pickoutfav", "sankabin", "sankagap",
                   "pickura", "pick21", "pick21t", "pick2tan", "pick2"]


def _org_json():
    """JSに渡す組織データ(木の箱・各プランの名前と集計開始日)"""
    meta = {}
    try:
        meta = {k: v for k, v in json.loads(org_tree.CONF_P.read_text()).items() if k != "nodes"}
    except Exception:
        pass
    return dict(since={**PLAN_SINCE, "kessai": ORG_SINCE, "kessai_r": ORG_SINCE, "flex": ORG_SINCE, "setsuD": ORG_SINCE, "hot3": ORG_SINCE, "uraM": URA_M_SINCE, "uraM2": URA_M_SINCE, "outW": OUTW_SINCE, "inW": OUTW_SINCE, "uraF": OUTW_SINCE, "kessaiC": KESSAI_C_SINCE, "inSec": OUTW_SINCE, "kessaiB": KESSAI_C_SINCE}, orgSince=ORG_SINCE, ops=list(bet_mod.OPS_PLANS),
                labels={**ALL_PLAN_LABELS, "kessai": "決裁者A(自信度型)", "flex": "決裁者B(柔軟型)", "setsuD": "説D 1-3/1-4", "hot3": "3連単の熱い一点", "uraM": "裏の穴×来そう一致", "uraM2": "決裁者A・一致で2倍", "outW": "外の1着専門(3・4コース頭)", "inW": "インの1着専門(嫌われたイン)", "uraF": "裏の穴×1着専門の後押し", "kessaiC": "決裁者C(重ね型・記録だけ)", "kessaiB": "決裁者B(厳選型・記録だけ)", "inSec": "インの2着専門(本命型)"}, nodes=_tree_nodes(), confMeta=meta)


ORG_JS = r"""
const ORG=__ORG__, VN=__VENUES__;
let D=[];
const $=id=>document.getElementById(id), yen=n=>n.toLocaleString();
const sg=n=>(n>=0?'+':'')+yen(n)+'円';
const pc=(r,s)=>{if(!s) return '-'; const v=r/s*100; return (v<100?Math.floor(v):Math.round(v))+'%';};
const anc=n=>{const p=n.split('.'), o=[]; for(let i=p.length;i>0;i--) o.push(p.slice(0,i).join('.')); return o;};
// プランの記録(運用・立説の買い目そのもの)
function aggPlans(pks){
  const by={}; let n=0,hit=0,st=0,ret=0;
  for(const x of D){ for(const pk of pks){
    if(x.d<ORG.since[pk]) continue; const v=x.s[pk]; if(!Array.isArray(v)) continue;
    n++; hit+=v[1]>0?1:0; st+=v[0]; ret+=v[1];
    const g=(by[x.d]=by[x.d]||{st:0,ret:0,n:0,hit:0}); g.st+=v[0]; g.ret+=v[1]; g.n++; g.hit+=v[1]>0?1:0; } }
  return {n,hit,st,ret,days:Object.keys(by).sort().map(d=>({d,...by[d]}))};
}
// 箱の記録: その箱より下の提案(頭ごとに分けた買い目)の合計。a=決裁者に採用された分
function aggNode(node){
  const by={}; let n=0,hit=0,st=0,ret=0,an=0,ahit=0,ast=0,aret=0;
  for(const x of D){ if(x.d<ORG.orgSince||!x.pp) continue;
    for(const [leaf,tags,s,r,c,ad] of x.pp){
      const ns=new Set([leaf,...tags].flatMap(anc)); if(!ns.has(node)) continue;
      n++; hit+=r>0?1:0; st+=s; ret+=r;
      if(ad){an++; ahit+=r>0?1:0; ast+=s; aret+=r;}
      const g=(by[x.d]=by[x.d]||{st:0,ret:0,n:0,hit:0}); g.st+=s; g.ret+=r; g.n++; g.hit+=r>0?1:0; } }
  return {n,hit,st,ret,an,ahit,ast,aret,days:Object.keys(by).sort().map(d=>({d,...by[d]}))};
}
function board(a){
  if(!a.n) return '<span class="sub">まだ提案なし</span>';
  const roi=(r,s)=>s?`<b style="color:${r>=s?'var(--green)':'var(--red)'}">${pc(r,s)}</b>`:'-';
  return `<span class="sub">提案${a.n}・採用${a.an}・的中${a.hit}｜回収 全</span>${roi(a.ret,a.st)}<span class="sub">・採用</span>${roi(a.aret,a.ast)}`;
}
// 提案の当たり方のタイプ: 一番細かい箱(印があれば印の箱)の過去の的中率で決める
function typeOf(leaf,tags){
  for(const b of [...tags,leaf]) for(const a of anc(b)){ const x=ORG.nodes[a]; if(x&&x.hit_rate!=null) return x.hit_rate>=0.25?'🎯本命型':x.hit_rate>=0.08?'⚖️中穴型':'💣大穴型'; }
  return '？';
}
function kessaiTypes(){
  const days=[...new Set(D.filter(x=>x.pp&&x.pp.length).map(x=>x.d))].sort(), last=days[days.length-1];
  if(!last) return '<span class="sub">まだ記録なし</span>';
  const g={};
  for(const x of D){ if(x.d!==last||!x.pp) continue;
    for(const [leaf,tags,s,r,c,ad] of x.pp){ if(!ad) continue; const t=typeOf(leaf,tags);
      const a=(g[t]=g[t]||{n:0,hit:0,st:0,ret:0}); a.n++; a.hit+=r>0?1:0; a.st+=s; a.ret+=r; } }
  const ks=Object.keys(g).sort();
  if(!ks.length) return `<span class="sub">${+last.slice(4,6)}/${+last.slice(6)}は採用なし</span>`;
  return `<span class="sub">${+last.slice(4,6)}/${+last.slice(6)}(結果が出た分)</span>`+ks.map(t=>{const a=g[t];
    return `<div class="boat" style="padding:4px 0"><div style="flex:1"><b>${t}</b> <span class="sub">${a.n}件・的中${a.hit}</span></div><b style="color:${a.ret>=a.st?'var(--green)':'var(--red)'}">${sg(a.ret-a.st)}</b></div>`;}).join('');
}
// 決裁者が採用したレースの一覧(新しい順)。当たりだけ/全部を切り替え
let KR_ALL=false, KR_N=30;
function kessaiRaces(){
  const rows=D.filter(x=>x.ka&&x.ka.length&&(KR_ALL||x.ka.some(k=>k[4]>0)))
    .sort((a,b)=>(b.d+b.t).localeCompare(a.d+a.t));
  const tg=`<div class="sub" style="margin-bottom:6px"><a href="#" data-kr="hit" style="${KR_ALL?'':'font-weight:700'}">当たりだけ</a>｜<a href="#" data-kr="all" style="${KR_ALL?'font-weight:700':''}">全部</a>　${rows.length}レース</div>`;
  if(!rows.length) return tg+'<span class="sub">まだありません</span>';
  return tg+rows.slice(0,KR_N).map(x=>{
    const rr=String(x.r).padStart(2,'0'), st=x.ka.reduce((a,k)=>a+k[3],0), rt=x.ka.reduce((a,k)=>a+k[4],0);
    return `<div style="border-top:1px solid var(--bd);padding:6px 0"><div style="display:flex;justify-content:space-between">`+
      `<a href="/${x.d}/${x.v}/${rr}-bet.html"><b>${+x.d.slice(4,6)}/${+x.d.slice(6)} ${VN[x.v]||x.v} ${x.r}R</b></a>`+
      `<b style="color:${rt>=st?'var(--green)':'var(--red)'}">${sg(rt-st)}</b></div>`+
      `<div class="sub">結果 ${x.res}（3連単 ${yen(x.pay)}円）</div>`+
      x.ka.map(k=>`<div class="sub">${k[4]>0?'✅':'・'} ${typeOf(k[0],[])} ${ORG.labels[k[0].split('.').pop()]||k[0]}｜${k[2]}${k[4]>0?`｜払戻 ${yen(k[4])}円`:''}</div>`).join('')+
      `</div>`;}).join('')+
    (rows.length>KR_N?`<div style="text-align:center;margin-top:6px"><a href="#" data-kr="more">もっと見る</a></div>`:'');
}
document.addEventListener('click',e=>{const a=e.target.closest('[data-kr]'); if(!a) return; e.preventDefault();
  const k=a.dataset.kr; if(k==='more') KR_N+=30; else {KR_ALL=k==='all'; KR_N=30;}
  document.querySelectorAll('[data-stat="kessai-races"]').forEach(el=>el.innerHTML=kessaiRaces());});
function boardTable(a){
  if(!a.n) return '<p class="sub">まだ提案なし</p>';
  const row=(lab,n,h,s,r)=>`<tr><td style="text-align:left">${lab}</td><td>${n}</td><td>${h}</td><td>${n?Math.round(h/n*100):0}%</td><td>${yen(s)}</td><td>${yen(r)}</td><td style="font-weight:700;color:${r>=s?'var(--green)':'var(--red)'}">${s?pc(r,s):'-'}</td></tr>`;
  return `<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12.5px;text-align:right;white-space:nowrap">`+
    `<tr class="sub"><th style="text-align:left"></th><th>件数</th><th>的中</th><th>的中率</th><th>投資</th><th>払戻</th><th>回収率</th></tr>`+
    row('全提案',a.n,a.hit,a.st,a.ret)+row('うち採用',a.an,a.ahit,a.ast,a.aret)+row('うち不採用',a.n-a.an,a.hit-a.ahit,a.st-a.ast,a.ret-a.aret)+`</table></div>`;
}
function statLine(a, unit){
  if(!a.n) return '<span class="sub">まだ記録なし</span>';
  return `<b style="color:${a.ret>=a.st?'var(--green)':'var(--red)'}">${pc(a.ret,a.st)}</b> <span class="sub">${a.n}${unit||'件'}・的中${Math.round(a.hit/a.n*100)}%・${sg(a.ret-a.st)}</span>`;
}
function fill(){
  document.querySelectorAll('[data-stat]').forEach(el=>{
    const k=el.dataset.stat;
    if(k==='ops') el.innerHTML=statLine(aggPlans(ORG.ops),'R');
    else if(k==='kessai') el.innerHTML=statLine(aggPlans(['kessai']),'R');
    else if(k==='kessai_r') el.innerHTML=statLine(aggPlans(['kessai_r']),'R');
    else if(k.startsWith('plan:')) el.innerHTML=statLine(aggPlans([k.slice(5)]),'R');
    else if(k.startsWith('node:')) el.innerHTML=board(aggNode(k.slice(5)));
    else if(k.startsWith('table:')) el.innerHTML=boardTable(aggNode(k.slice(6)));
    else if(k==='kessai-types') el.innerHTML=kessaiTypes();
    else if(k==='kessai-races') el.innerHTML=kessaiRaces();
  });
  document.querySelectorAll('[data-pnl]').forEach(el=>{
    const k=el.dataset.pnl;
    pnlCharts(el, (k.startsWith('node:')?aggNode(k.slice(5)):aggPlans(k.split(','))).days);
  });
}
fetch('/bets-data.json').then(r=>r.json()).then(j=>{D=j;fill()});
"""


def _type_html(x):
    t = org_tree.hit_type(x.get("hit_rate"))
    if not t:
        return ""
    mult = f'・当たると平均{x["avg_mult"]:.0f}倍' if x.get("avg_mult") else ""
    return f'<span class="org-stat sub">{t[1]}{t[0]}(的中{x["hit_rate"]:.0%}{mult})</span>'


def _conf_html(x):
    if x.get("conf") is None:
        return '<span class="org-stat sub">自信度 まだなし</span>'
    c = x["conf"]
    col = "var(--green)" if c >= org_tree.ADOPT else "var(--sub)"
    return (f'<span class="org-stat">自信度 <b style="color:{col}">{c:.0%}</b> '
            f'<span class="sub">(過去{x["n"]:,}件・素{x["roi"]:.0%})</span></span>' + _type_html(x))


def _node_tile(nd, x, size=40, cls="org-mini"):
    dim = x["status"] == "休止" or (x.get("conf") is not None and x["conf"] < org_tree.ADOPT)
    acc = "visor" if x["level"] == 5 else "antenna"
    st = f' <span class="sub">{x["status"]}</span>' if x["status"] and x["level"] == 4 else ""
    return (f'<a class="{cls}" href="/org/n/{nd}.html">{robot_svg(x["color"], acc, size, dim=dim)}'
            f'<div><b><span class="lvn">{"①②③④⑤"[x["level"] - 1]}</span>{x["label"]}{st}</b>{_conf_html(x)}'
            f'<span class="org-stat" data-stat="node:{nd}"></span></div></a>')


def _tree_html(nodes, root):
    """root の子から下を木(ul)で描く。③の箱は開閉式(中の④⑤は閉じておく)"""
    def rec(nd):
        x = nodes[nd]
        kids = "".join(f"<li>{rec(k)}</li>" for k in x["children"])
        tile = _node_tile(nd, x, 34 if x["level"] <= 3 else 28)
        if x["level"] == 3 and kids:
            return (f'<details class="org-fold"><summary>{tile}<span class="fold-n sub">{len(x["children"])}つの説 ▼</span></summary>'
                    f'<ul>{kids}</ul></details>')
        return tile + (f"<ul>{kids}</ul>" if kids else "")
    return '<ul class="tree">' + "".join(f"<li>{rec(k)}</li>" for k in nodes[root]["children"]) + "</ul>"


def org_home():
    """トップ(/ops.html): シナリオの木。①最終決裁 → ②イン逃げ/イン負け → ③誰が勝つか → ④説(プラン) → ⑤絞り(印)"""
    k = ORG_KESSAI
    nodes = _tree_nodes()
    nodes["_root"] = dict(children=["in", "out"])
    info = "".join(
        f'<a class="org-mini" href="/org/{x["id"]}.html">{robot_svg(x["color"], x["acc"], 28)}'
        f'<div><b>{x["name"]}</b><span class="sub">{x["stat"]}</span></div></a>' for x in ORG_INFO)
    meta = _org_json()["confMeta"]
    per = f'{jp(meta["period"][0])}〜{jp(meta["period"][1])}' if meta.get("period") else "未作成"
    body = ('<h1>予想組織図</h1>'
            + '<p class="sub" style="margin:0">①決裁 → ②イン逃げ/負け → ③誰が勝つか → ④説 → ⑤絞り。タップでその子の部屋へ(③は開閉)。</p>'
            + '<details class="sub" style="margin:4px 0 8px"><summary>見方</summary>'
              '試験用買い目(お金は賭けていません)を、シナリオの木で並べています。各プランの買い目は頭の艇ごとに「提案」に分けて、頭のコースの箱に入れます。'
              f'同じ頭(同じ結果)を取り合う提案は自信度(推定回収率)が一番高いものだけが上に上がり、決裁者は上がってきた提案のうち自信度{org_tree.ADOPT:.0%}以上を全部採用します(複数OK、無ければ見送り)。'
              f'自信度＝その箱の提案を確定オッズの過去データ({per})で精算した回収率を、件数が少ないほど一つ上の箱の自信度へ寄せた値({org_tree.SHRINK}件で半々)。決裁者の採用線({org_tree.ADOPT:.0%})以上が緑。'
              f'各箱の「提案・採用・的中・回収(全提案/採用分)」は{jp(ORG_SINCE)}からの実戦の記録です。</details>'
            + '<div class="lv">⓪ モニター</div>'
            + f'<a class="org-tile org-boss" href="/org/monitor.html">{_monitor_img(44)}<div><b>モニター</b>'
              '<span class="sub">決裁者A・B・Cを見張って、どれを本命にするか決める</span></div></a>'
            + '<div class="lv">① 最終決裁</div>'
            + _kessai_tiles()
            + '<span class="org-stat sub">参考: Aの再生(確定オッズ) <span data-stat="kessai_r"></span>・v0(全部採用) <span data-stat="ops"></span></span>'
            + _tree_html(nodes, "_root")
            + '<div id="up"></div>'
            + '<h2>情報部 <span class="sub">全部の箱に材料を渡す係(買わない)</span></h2><div class="org-grid2">' + info + '</div>'
            + '<h2>資料室</h2><a class="org-tile" href="/org/archive.html"><div><b>旧プランの記録</b>'
              '<span class="sub">組織図にする前の試験プラン(バランス・イン的中重視など)も含めた全記録を、期間・条件・場で絞って見る</span></div></a>')
    return _org_page("予想組織図", "/ops.html", body, upcoming=["kessai"])


MONITOR = dict(name="モニター", role="組織の一番上。決裁者A・B・Cの成績を見張って、どの決裁者を本命にするか決める(判定は10/31・11/17)",
               img="/img/monitor_face.jpg")


def _monitor_img(size):
    return f'<img src="{MONITOR["img"]}" alt="モニター" width="{size}" height="{size}" style="border-radius:50%;object-fit:cover;flex:none">'


def _kessai_tiles():
    """決裁者A・C・Bの部屋へのタイル(成績つき)"""
    k = ORG_KESSAI
    rows = (("kessai.html", "決裁者A(自信度型)", "kessai", "自信度103%以上の提案を全部4,000円で採用"),
            ("kessai-c.html", "決裁者C(重ね型・記録だけ)", "plan:kessaiC", "Aと同じ採用で、1着専門の後押しや重なりで金額に強弱"),
            ("kessai-b.html", "決裁者B(厳選型・記録だけ)", "plan:kessaiB", "Aの採用のうち、1着専門の後押しがあるものだけ買う(10/20から)"))
    return "".join(f'<a class="org-tile org-boss" href="/org/{u}">{robot_svg(k["color"], k["acc"], 36)}'
                   f'<div><b>{n}</b><span class="sub">{d}</span><span class="org-stat"><span data-stat="{st}"></span></span></div></a>'
                   for u, n, st, d in rows)


def monitor_room():
    body = (f'<a class="back-lk" href="/ops.html">← 組織図に戻る</a>'
            f'<div class="room-head">{_monitor_img(76)}<div><h1 style="margin:0">{MONITOR["name"]}</h1>'
            f'<span class="sub">{MONITOR["role"]}</span></div></div>'
            + '<div class="card"><b>見張っている決裁者</b><p class="sub" style="margin:4px 0 6px">どれもお金は使わず記録だけ。'
              '同じレースでそれぞれ判断し、成績を並べる。r1・r2…は同じ決裁者の中で買い方を直した版。</p>'
            + _kessai_tiles() + '</div>'
            + '<div class="card"><b>決裁者Aの成績</b><div data-stat="kessai"></div><div data-pnl="kessai" style="margin-top:6px"></div></div>'
            + '<div class="card"><b>決裁者Cの成績</b><div data-stat="plan:kessaiC"></div><div data-pnl="kessaiC" style="margin-top:6px"></div></div>'
            + '<div class="card"><b>判定の予定</b><p class="sub" style="margin:4px 0 0">10/31(14日)と11/17(30日)に、A・Cの成績と社員候補を比べて、'
              '本命の決裁者と社員の入れ替えを決める。決め方は運用メモに事前に書いてある。</p></div>'
            + '<div class="card"><b>社員候補(記録だけ)</b><p class="sub" style="margin:2px 0 6px">'
              '事前に決めた条件を別の年で確かめて残った買い方。1点1,000円・締切2分前のオッズで判断。成績がよければ社員にする。</p>'
              '<div><b>説D 1-3/1-4</b> <span class="sub">インが堅い(本予想60%以上)時の、8〜12倍で割安な1-3・1-4(2連単)</span></div>'
              '<div data-stat="plan:setsuD"></div>'
              '<div style="margin-top:8px"><b>3連単の熱い一点</b> <span class="sub">混ぜた2連単の確率×3着専門の3着確率で、割安2.0以上・100倍未満</span></div>'
              '<div data-stat="plan:hot3"></div>'
              '<div style="margin-top:8px"><b>裏の穴×来そう一致</b> <span class="sub">決裁者Aが採用した裏の穴のうち、頭の艇が'
              '「イン以外で情報部が一番来そうと見る艇」と同じ時だけ買う(10/20から。過去2年で194%・296%)</span></div>'
              '<div data-stat="plan:uraM"></div>'
              '<div style="margin-top:8px"><b>決裁者A・一致で2倍</b> <span class="sub">決裁者Aの買い方そのままで、上の一致した時だけ金額を2倍</span></div>'
              '<div data-stat="plan:uraM2"></div>'
              '<div style="margin-top:8px"><b>外の1着専門(3・4コース頭)</b> <span class="sub">3・4コースの艇の1着確率を1着専門が市場の1.5倍以上と見る時、'
              'その艇を頭に2連単3点・計4,000円(2着は2着専門の上位3艇、オッズに合わせて配分)。締切45秒前のオッズで判断(10/20から。年をまたいだ確かめで151%・159%)</span></div>'
              '<div data-stat="plan:outW"></div>'
              '<div style="margin-top:8px"><b>インの1着専門(嫌われたイン)</b> <span class="sub">1着専門がインの1着確率を市場の1.7倍以上と見る時、'
              'インを頭に2連単3点・計4,000円(2着は2着専門の上位3艇、オッズに合わせて配分)。10/20から。年をまたいだ確かめで259%・191%</span></div>'
              '<div data-stat="plan:inW"></div>'
              '<div style="margin-top:8px"><b>裏の穴×1着専門の後押し</b> <span class="sub">決裁者Aが採用した裏の穴のうち、1着専門が頭の艇を'
              '市場の1.2倍以上と見る時だけ買う(45秒前のオッズ)。10/20から。過去2年で166%・193%(今の裏の穴は123%・144%)</span></div>'
              '<div data-stat="plan:uraF"></div>'
              '<div style="margin-top:8px"><b>インの2着専門(本命型)</b> <span class="sub">インが頭の2連単1-Xで、1着専門のイン1着確率×2着専門の2着確率×見込みの確定オッズが1.1以上、'
              '見込みの確定オッズ3〜15倍の目を1点1,000円。10/20から。年をまたいだ確かめ(1.1以上)で3〜8倍120%・130%(的中約20%)、8〜15倍118%・118%</span></div>'
              '<div data-stat="plan:inSec"></div></div>'
            + '<div id="up"></div>')
    return _org_page("モニター", "/org/monitor.html", body, upcoming=["kessai"])


def kessai_room():
    k = ORG_KESSAI
    body = (_room_head(k["color"], k["acc"], "決裁者A(自信度型)", "社員の提案を自信度で選んで採用する", back="/org/monitor.html", back_label="モニターの部屋に戻る")
            + '<h2>決裁者A(自信度型)</h2>'
            + '<div class="card"><b>決め方</b><p class="sub" style="margin:4px 0 0">'
              '① 各社員の買い目を頭の艇ごとの「提案」に分け、入った箱の自信度(確定オッズの過去データでの推定回収率)を付ける。印があれば一番細かい印の箱の自信度。<br>'
              f'② 記録が少ない箱は一つ上の箱の自信度へ寄せる({org_tree.SHRINK}件で半々、一番上は控除率並みの{org_tree.PRIOR:.0%})。<br>'
              f'③ 同じ結果を取り合う提案(同じ頭の艇の買い目)同士だけを比べ、自信度が一番高い提案を1つ上げる。提案はどれも1回{org_tree.STAKE:,}円にそろえる。<br>'
              f'④ 上がってきた提案のうち、自信度{org_tree.ADOPT:.0%}以上は全部採用(違う頭なら複数残る)。1つも無ければ見送り。</p>'
              '<p class="sub" style="margin:6px 0 0"><b>r1</b>(〜10/18): 2026年の表・採用105%・締切2分前のオッズで社員が買い目を作る<br>'
              f'<b>r2</b>(10/19): 2025〜2026年の表・採用{org_tree.ADOPT:.0%}・締切45秒前のオッズを「見込みの確定オッズ」'
              '(割安に見える目ほど最後に下がる分を割り引いたもの)に直してから、社員が買い目を作り直す<br>'
              '<b>r3</b>(10/20〜): 3〜4コースの箱に社員「外の1着専門」(1着専門が市場の1.5倍以上と見る3・4コースの艇を頭に2連単3点)を入れ、'
              'イン側の箱に社員「インの1着専門」(1着専門がインを市場の1.7倍以上と見る時)を入れ、'
              '2コースなどの箱で一度も採用されなかった4人(2-1・2-1の3連単・2連単・外の2連単)を組織から外す</p></div>'
            + '<div class="card"><b>今日の採用の中身</b> <span class="sub">当たり方のタイプ別(🎯本命型=的中25%以上・⚖️中穴型=8〜25%・💣大穴型=8%未満)</span>'
              '<div data-stat="kessai-types" style="margin-top:6px"></div></div>'
            + '<div class="card"><b>決裁者Aの成績</b><div data-stat="kessai"></div><div data-pnl="kessai" style="margin-top:6px"></div></div>'
            + '<div class="card"><b>決裁者Aが採用したレース</b> <span class="sub">新しい順。✅＝当たった提案</span><div data-stat="kessai-races" style="margin-top:6px"></div></div>'
            + '<div class="card"><b>参考: 社員の提案を全部採用した場合</b><div data-stat="ops"></div><div data-pnl="ops" style="margin-top:6px"></div></div>'
            + '<div id="up"></div>')
    return _org_page("決裁者A", "/org/kessai.html", body, upcoming=["kessai"])


def kessai_c_room():
    k = ORG_KESSAI
    body = (_room_head(k["color"], k["acc"], "決裁者C(重ね型・記録だけ)", "Aと同じ採用で、後押しや重なりで金額に強弱をつける", back="/org/monitor.html", back_label="モニターの部屋に戻る")
            + '<h2>決裁者C(重ね型・記録だけ)</h2>'
            + '<div class="card"><b>決め方</b><p class="sub" style="margin:4px 0 0">決裁者Aと同じ提案を採用し、金額に強弱をつける(10/20から)。'
              '1着専門が頭の艇を市場の1.2倍以上と見ていなければ1/4(1,000円)、見ていれば等倍(4,000円)、'
              '自信度が採用ライン以上の提案が同じ頭に2つ以上あればさらに2倍。'
              'そこに足し買いとして、3連単の熱い一点(1点1,000円)を加える(外の1着専門・インの1着専門は10/20からAの社員)。</p>'
              '<p class="sub" style="margin:6px 0 0">過去2年の作り直し(Aの部分): 今のA 114%・123% → 135%・151%、投資は約半分で儲けは多い</p></div>'
            + '<div class="card"><b>決裁者Cの成績</b><div data-stat="plan:kessaiC"></div><div data-pnl="kessaiC" style="margin-top:6px"></div></div>'
            + '<div id="up"></div>')
    return _org_page("決裁者C", "/org/kessai-c.html", body)


def kessai_b_room():
    k = ORG_KESSAI
    body = (_room_head(k["color"], k["acc"], "決裁者B(厳選型・記録だけ)", "Aと同じ社員の提案から、1着専門の後押しがあるものだけ買う", back="/org/monitor.html", back_label="モニターの部屋に戻る")
            + '<div class="card"><b>決め方</b><p class="sub" style="margin:4px 0 0">決裁者Aと同じ提案を見て、Aが採用したもののうち、'
              '1着専門(実績・展示・スタートなどから1着を当てる係)が頭の艇を市場の1.2倍以上来ると見ているものだけを4,000円で買う。ほかは見送る(10/20から)。</p>'
              '<p class="sub" style="margin:6px 0 0">過去2年の作り直し: A 114%・123% → B 156%・179%(買う数はAの約3割)。'
              'A=全部買う、C=金額に強弱、B=絞る、の3つを同じ社員で比べる</p></div>'
            + '<div class="card"><b>決裁者Bの成績</b><div data-stat="plan:kessaiB"></div><div data-pnl="kessaiB" style="margin-top:6px"></div></div>'
            + '<h2>旧B(柔軟型・10/17〜19・記録だけ続ける)</h2>'
            + '<div class="card"><b>決め方</b><p class="sub" style="margin:4px 0 0">'
              f'情報部と市場の確率を混ぜて2連単30通りの確率を出し、割安な目を全部買う(頭はいくつでも・{flex.ODDS_MAX:.0f}倍未満・1点{flex.STAKE:,}円)。</p>'
              f'<p class="sub" style="margin:6px 0 0"><b>r1</b>(10/17〜18): 締切2分前のオッズで割安さ{flex.EV}以上<br>'
              f'<b>r2</b>(10/19〜): 締切45秒前のオッズを見込みの確定オッズに直して割安さ{flex.EV_DRIFT}以上。'
              '頭の確率は1着専門で直し、3着が固ければ3連単2点に切り替える</p></div>'
            + '<div class="card"><b>旧Bの成績</b><div data-stat="plan:flex"></div><div data-pnl="flex" style="margin-top:6px"></div></div>'
            + '<div id="up"></div>')
    return _org_page("決裁者B", "/org/kessai-b.html", body)


def node_room(nd, nodes):
    x = nodes[nd]
    lv = {2: "②シナリオ", 3: "③誰が勝つか", 4: "④説(買い方)", 5: "⑤絞り(印)"}[x["level"]]
    par = x["parent"]
    back = (f"/org/n/{par}.html", f'{nodes[par]["label"]}に戻る') if par else ("/ops.html", "組織図に戻る")
    pconf = nodes[par]["conf"] if par and nodes[par].get("conf") is not None else org_tree.PRIOR
    conf = ('<div class="card"><b>自信度</b>' + _conf_html(x)
            + (f'<p class="sub" style="margin:4px 0 0">素の回収率{x["roi"]:.0%}を、{x["n"]:,}件の重みで、上の箱の自信度{pconf:.0%}へ寄せた値'
               f'(上の箱の重み{org_tree.SHRINK}件)。</p>' if x.get("conf") is not None else "") + '</div>')
    kids = ('<h2>下の箱</h2><div class="org-grid">' + "".join(_node_tile(k, nodes[k]) for k in x["children"]) + '</div>'
            if x["children"] else "")
    plan = (f'<a class="org-tile" href="/ops/{x["plan"]}.html"><div><b>この説の買い目・ロジック・日別の記録</b>'
            f'<span class="sub">{ALL_PLAN_LABELS.get(x["plan"], x["plan"])}(全コースの頭をまとめた記録)</span></div></a>'
            if x["level"] == 4 else "")
    body = (_room_head(x["color"], "visor" if x["level"] == 5 else "antenna", x["label"], f'{lv}・{x["status"]}'.rstrip("・"),
                       back=back[0], back_label=back[1])
            + conf + kids
            + f'<div class="card"><b>成績ボード</b> <span class="sub">({jp(ORG_SINCE)}〜の実戦、頭ごとの提案。採用＝最終決裁者が選んだもの)</span>'
              f'<div data-stat="table:{nd}" style="margin-top:6px"></div></div>'
              f'<div class="card"><b>全提案の損益の推移</b><div data-pnl="node:{nd}" style="margin-top:6px"></div></div>' + plan)
    return _org_page(x["label"], f"/org/n/{nd}.html", body)


def _kv(rows):
    return "".join(f'<div class="boat"><div style="flex:1">{a}</div><b>{b}</b></div>' for a, b in rows)


def info_room(x, pick_hi=(), pick_lo=()):
    i = x["id"]
    if i == "jisseki":
        main = ('<div class="card"><b>仕事</b><p class="sub" style="margin:4px 0 0">過去の成績(選手・コース・モーター・展示など)から、各艇の1着確率、'
                '1マークの展開、3連単の確率を出す。サイトのレース予想ページはこの子の予想。</p></div>'
                '<div class="card"><b>インの1着確率: 予想と実際</b><span class="sub">(6/1〜10/13・約1.8万R)</span>'
                + _kv([("予想 21%", "実際 23%"), ("予想 35%", "実際 36%"), ("予想 45%", "実際 44%"), ("予想 55%", "実際 56%"),
                       ("予想 65%", "実際 66%"), ("予想 75%", "実際 75%"), ("予想 84%", "実際 82%")]) + '</div>'
                '<div class="card"><b>市場とのくらべ</b>' + _kv([("当たりの良さ(log loss・小さいほど良い)", "1.1924"), ("市場オッズ係", "1.1525")])
                + '<p class="sub" style="margin:4px 0 0">確率はよく合っているが、全体では市場の方がわずかに上手。だから買い目予想部は「市場とズレた所」だけを狙う。</p></div>')
    elif i == "gbm":
        main = ('<div class="card"><b>仕事</b><p class="sub" style="margin:4px 0 0">オッズを一切見ずに、選手のコース別成績・勝率・級・年齢・体重・モーター・ボート・'
                '平均ST・F・展示タイム・風・波から、勾配ブースティングで1着確率を出す。選手の成績は「その月より前」の累積だけを使う。</p></div>'
                '<div class="card"><b>確定オッズでの実力(6/1〜10/13)</b>'
                + _kv([("当たりの良さ(log loss)", "1.1808"), ("市場オッズ係", "1.1525"), ("実績予想くん(本予想)", "1.1924"),
                       ("B級インのレースで、市場の1.7倍以上と見た外の艇の1着", "市場の1.26〜1.28倍")])
                + '<p class="sub" style="margin:4px 0 0">全体では市場に負けるが、「B級インのレースで市場が軽く見る外の艇」は6〜7月・8〜10月の両方で市場より正しかった。'
                  'これが裏の穴部の元ネタ。市場と混ぜても良くならない。</p></div>')
    elif i == "market":
        main = ('<div class="card"><b>仕事</b><p class="sub" style="margin:4px 0 0">3連単・2連単のオッズから「みんなが思っている確率」を出す。'
                '同じ結果を2連単と3連単どちらで買うと高いかも出す。</p></div>'
                '<div class="card"><b>確定オッズでわかったこと</b>'
                + _kv([("全体の当たりの良さ(log loss)", "1.1525(一番)"), ("穴(人気薄)の実際の来る率", "市場の0.73〜0.85倍"),
                       ("本命の実際の来る率", "市場の1.03〜1.05倍"), ("インが弱いレース(実績予想18%)", "市場21%・実際20%"),
                       ("2連単と3連単の高い方で買う", "回収率+5〜10pt")])
                + '<p class="sub" style="margin:4px 0 0">締切直前にお金がインの頭に流れ込むので、締切前のオッズで見た妙味は確定オッズでは縮む。'
                  'だから買い目は締切1分前まで決め直す。</p></div>')
    elif i == "nige":
        main = ('<div class="card"><b>仕事</b><p class="sub" style="margin:4px 0 0">実績予想くんの確率から、このレースがイン逃げ型か外頭型かを判定し、'
                '本物のB級イン(B級・F持ちでない・1着確率20%以上)かを見て、どの部にレースを回すか決める。</p></div>'
                '<h2>判定の成績</h2>' + nige_body() + '<h2>今日の極端なレース</h2>' + pick_body(list(pick_hi), list(pick_lo)))
    else:
        main = ('<div class="card"><b>仕事</b><p class="sub" style="margin:4px 0 0">展示タイム・展示ST・風・波・進入(展示の並び)を集めて、'
                '実績予想くん・2号・逃げ判定係に渡す。締切の約10分前から5分おきに取り込む。</p></div>'
                '<div class="card"><b>わかったこと</b>'
                + _kv([("展示STだけで決まり手を予想", "市場に勝てない"), ("決まり手が分かれば2着が当たる(1.4〜1.8倍)", "レース後にしか分からない"),
                       ("凪・展示1位などで絞る(イン逃げ部の部員)", "立説中")])
                + '<p class="sub" style="margin:4px 0 0">単独で使うより、他の係の材料として効く。</p></div>')
    body = _room_head(x["color"], x["acc"], x["name"], x["role"]) + main
    return _org_page(x["name"], f"/org/{i}.html", body)


def archive_room():
    body = (_room_head("#6B7079", "antenna", "資料室", "組織図にする前の試験プランも含めた、試験用買い目の全記録")
            + archive_body())
    return page("資料室", body, "", "/org/archive.html", noindex=True)


def redirect_page(to):
    return (f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="robots" content="noindex">'
            f'<meta http-equiv="refresh" content="0;url={to}"><title>移動しました</title></head>'
            f'<body><a href="{to}">移動しました</a></body></html>')


DETAIL_JS = r"""
const VN=__VENUES__, SINCE=__SINCE__, PLAN=__PLAN__;
let D=[];
const $=id=>document.getElementById(id), yen=n=>n.toLocaleString();
function entries(){
  const out=[];
  for(const x of D){
    if(x.d<SINCE) continue;
    const v=x.s[PLAN];
    if(v===undefined) continue;
    out.push({d:x.d, t:x.t||'', v:x.v, r:x.r, res:x.res, pay:x.pay,
               skip:v===0, st:v===0?0:v[0], ret:v===0?0:v[1], tk:(PLAN==='pick2'?x.tk:x[PLAN+'_tk'])||[]});
  }
  return out;
}
function filt(){
  const per=$('per4').value, all=entries();
  const ds=[...new Set(all.map(x=>x.d))].sort();
  const keep=per==='all'?null:new Set(ds.slice(-({d30:30,d90:90})[per]));
  return all.filter(x=>!keep||keep.has(x.d));
}
function render(){
  const rows=filt(), used=rows.filter(x=>!x.skip);
  $('n4').textContent = `対象 ${rows.length}件中・購入 ${used.length}件・見送り ${rows.length-used.length}件`;
  if(!used.length){ $('out4').innerHTML='<div class="card"><p class="sub">まだ購入したレースがありません。</p></div>'; return; }
  const st=used.reduce((a,x)=>a+x.st,0), ret=used.reduce((a,x)=>a+x.ret,0);
  const roi=st?ret/st:0, hitN=used.filter(x=>x.ret>0).length;
  let s = `<div class="card"><b>通算</b> <b style="color:${roi>=1?'var(--green)':'var(--red)'};font-size:22px">${Math.round(roi*100)}%</b>`+
    `<br><span class="sub">投資 ${yen(st)}円 → 払戻 ${yen(ret)}円（${ret-st>=0?'+':''}${yen(ret-st)}円）・的中 ${hitN}/${used.length}件（${Math.round(hitN/used.length*100)}%）</span></div>`;
  const byDay={};
  for(const x of used){const g=(byDay[x.d]=byDay[x.d]||{st:0,ret:0,n:0,hit:0}); g.st+=x.st; g.ret+=x.ret; g.n++; g.hit+=x.ret>0?1:0;}
  s += `<div class="card"><b>損益の推移</b><div id="pnl4" style="margin-top:6px"></div></div>`;
  const oofune = used.filter(x=>x.ret>0 && x.pay>=10000).sort((a,b)=>b.pay-a.pay);
  if(oofune.length){
    s += `<div class="card"><b>万舟的中</b>` + oofune.map(x=>
      `<div class="boat"><div style="flex:1"><b>${VN[x.v]} ${x.r}R</b> <span class="sub">${+x.d.slice(4,6)}/${+x.d.slice(6)}・${x.res}</span></div>`+
      `<b style="color:var(--green)">${yen(x.pay)}円</b></div>`).join('') + `</div>`;
  }
  const list = used.slice().sort((a,b)=> b.d.localeCompare(a.d) || b.t.localeCompare(a.t) || b.r-a.r);   // 新しい日・締切が遅い順
  s += `<div class="card"><b>レース一覧</b>` + list.map(x=>{
    const hit=x.ret>0;
    const grp = {};
    const mk = {};
    for(const [c,u,role] of x.tk){ const k=(role||'').split('・')[0]||'買い目'; (grp[k]=grp[k]||[]).push([c,u]); if((role||'').includes('【')) mk[k]=(role.match(/【(.*)】/)||[])[1]; }
    const tk = Object.keys(grp).map(k=>
      `<div style="margin-top:2px${mk[k]?';background:var(--mark);border-radius:6px;padding:2px 4px':''}"><span class="sub" style="font-weight:700">${mk[k]?'★':''}${k}${mk[k]?' 【'+mk[k]+'】':''}</span> `+
      grp[k].map(([c,u])=>`<span class="sub" style="display:inline-block;margin:1px 6px 1px 0${(c===x.res||(c.length===3&&x.res&&x.res.startsWith(c+'-')))?';color:var(--green);font-weight:700':''}">${c}×${u}口</span>`).join('')
      +`</div>`).join('');
    return `<div class="boat" style="flex-direction:column;align-items:flex-start;gap:4px">`+
      `<div style="display:flex;width:100%"><div style="flex:1"><b>${Object.keys(mk).length?'★':''}${VN[x.v]} ${x.r}R</b> <span class="sub">${+x.d.slice(4,6)}/${+x.d.slice(6)}${x.t?' '+x.t:''}・結果 ${x.res}・投資${yen(x.st)}円</span></div>`+
      `<b style="color:${hit?'var(--green)':'var(--red)'}">${hit?'的中':'外れ'} ${x.ret-x.st>=0?'+':''}${yen(x.ret-x.st)}円</b></div>`+
      (tk?`<details style="width:100%"><summary class="sub">買い目(${x.tk.length}点)を見る</summary><div style="margin-top:4px">${tk}</div></details>`:'')+
      `</div>`;
  }).join('') + `</div>`;
  $('out4').innerHTML = s;
  pnlCharts($('pnl4'), Object.keys(byDay).sort().map(d=>({d,...byDay[d]})));
}
fetch('/bets-data.json').then(r=>r.json()).then(j=>{D=j;render()});
fetch('/bets-upcoming.json').then(r=>r.json()).then(u=>renderUpcoming($('up'),u,{},VN,PLAN)).catch(()=>{});
document.addEventListener('change',e=>{if(e.target.id==='per4')render()});
"""

def ops_detail_page(plan_key, logic_card_html):
    """プラン別の詳細ページ(/ops/<plan>.html)。期間別の実績・日別回収率・レース一覧・ロジック解説"""
    opt = lambda pairs: "".join(f'<option value="{v}">{t}</option>' for v, t in pairs)
    sel = 'style="font-size:15px;padding:6px;border-radius:8px;border:1px solid var(--bd);background:var(--card);color:var(--tx);width:100%"'
    js = (DETAIL_JS.replace("__VENUES__", json.dumps(VENUES, ensure_ascii=False))
                   .replace("__SINCE__", json.dumps(PLAN_SINCE[plan_key]))
                   .replace("__PLAN__", json.dumps(plan_key)))
    js = UPCOMING_JS + CHART_JS + js
    label = ALL_PLAN_LABELS[plan_key]
    side = "out" if plan_key in ("pickura", "pick21", "pick21t", "pick2tan", "pick2", "pickgen", "pickoutfav") else "in"
    body = (_room_head(GROUP_COLOR[side], "antenna", label, "④説(買い方)・" + _plan_status(plan_key) + "・全コースの頭をまとめた記録")
            + '<div id="up"></div>'
            + '<div class="card" style="display:grid;grid-template-columns:1fr;gap:8px">'
            + f'<label class="sub">期間<select id="per4" {sel}>{opt([("d30", "直近30日"), ("d90", "直近90日"), ("all", "全期間")])}</select></label>'
            + '</div><p class="sub" id="n4"></p><div id="out4"><p class="sub">読み込み中…</p></div>'
            + logic_card_html
            + f'<script>{js}</script>')
    return page(label, body, "", f"/ops/{plan_key}.html", noindex=True)


def _pick2_logic_card():
    b = bet_mod
    steps = [
        ("① 対象レース", f'「1コースが逃げない」と予想(pressed)、かつ1コース1着確率(nige)が{b.PICK2_NIGE_MAX:.0%}未満のレースだけ'),
        ("② 頭候補", "2〜6コースのうち、モデルの確率が高い順に2艇(本命・次点)"),
        ("③ 目の絞り込み", f'本命・次点それぞれ、5分前時点のオッズが{b.PICK2_MIN_ODDS}〜{b.PICK2_MAX_ODDS}倍の目の中から、期待値'
                        f'(確率×オッズ)が一番高い目の{b.PICK2_EV_RATIO:.0%}以上ある目を拾う(頭ごと最低{b.PICK2_MIN_TICKETS}・最大'
                        f'{b.PICK2_MAX_TICKETS}点、レースによって点数は変わる)。確率が一番高い目だけを選ぶと市場も同じだけ安く'
                        f'値付けしていて妙味が薄いので、あえて確率そのものではなく期待値で絞っている'),
        ("④ 配分", f'③で選んだ目の中で、期待値に比例して予算(頭ごと{b.PICK2_HEAD_BUDGET:,}円、本命・次点で合計'
                  f'{b.PICK2_HEAD_BUDGET * 2:,}円)を配る(最低1口=100円)'),
        ("⑤ 見送り", f'本命・次点の両方がオッズ{b.PICK2_MIN_ODDS}〜{b.PICK2_MAX_ODDS}倍の目を持っている時だけ買う。'
                   f'どちらかでも無ければ、そのレースは見送り(片頭だけで無理に買うと弱い: 実オッズ検証で的中率14%・回収率65.7%)'),
    ]
    rows = "".join(f'<div class="boat"><div><b>{title}</b><br><span class="sub">{body}</span></div></div>' for title, body in steps)
    return (
        f'<div class="card"><b>イン以外(pick2)のロジック</b>{rows}</div>'
        '<div class="card"><p class="sub" style="margin:0">2025年1月〜2026年9月・実際の締切オッズ198レースで検証。本線だけ'
        '10,000円保証+紐は均等100円、という配分より、期待値の高い目に期待値比例で配る方が回収率が良く'
        '(nige<18%帯で99.1%→120.5%)、点数を固定5点にするより「一番良い目に対してどれだけ肉薄してるか」'
        'でレースごとに点数を変える方がわずかに良かったため、この形にしています。また片頭だけしか買えない'
        'レースは的中率14%・回収率65.7%と弱かったので、両頭揃う時だけ買うようにしています(nige<22%帯で'
        '111.2%→113.1%)'
        '(目安であり保証ではありません。パラメータは今後の検証で変わることがあります)。</p></div>')


def _pick2tan_logic_card():
    b = bet_mod
    steps = [
        ("① 頭候補", "2〜6コースのうち、モデルの1着確率が高い順に2艇(本命・次点)"),
        ("② 対象の目", f'本命・次点それぞれ、2連単の確率が一番高い目。その確率が{b.PICK2TAN_PROB_MIN:.0%}以上の時だけ'
                     '買う(外の艇がはっきり本命のレースだけ。1日7〜8点程度)'),
        ("③ 買い方", f'1レース{b.PICK2TAN_BUDGET:,}円。本命・次点の両方が対象なら半分ずつ'),
        ("なぜ絞るか", "市場は外の艇を買いかぶっていて、外の頭の2連単は全体で回収率69%。旧ロジック"
                     "(インが崩れそうなレース=1コース1着確率22%未満)は、市場も外を買い込むため64%と一番弱かった。"
                     "外の艇がはっきり本命の時(確率20%以上)だけは108%だった"),
    ]
    rows = "".join(f'<div class="boat"><div><b>{title}</b><br><span class="sub">{body}</span></div></div>' for title, body in steps)
    return (
        f'<div class="card"><b>外・2連単(pick2tan)のロジック</b>{rows}</div>'
        '<div class="card"><p class="sub" style="margin:0">2026年10月2日〜13日・締切前の実オッズがある1,307レースの'
        '外の頭2,614点で検証。確率20%以上の79点で的中24・回収率108%。サンプルが小さく偶然と区別できないため、'
        '本番で確かめる試験プランです(目安であり保証ではありません)。</p></div>')


def _pick21_logic_card():
    b = bet_mod
    steps = [
        ("対象レース", f'2コースの予想スタート(平均ST)が1コースより{b.PICK21_ST_GAP}秒以上速いレース(1日15〜20レース程度)'),
        ("買い方", f'2連単2-1(2コース頭・1コース2着)の1点に{b.PICK21_UNITS * 100:,}円'),
        ("説", "スタートで内の艇より速い艇が勝つ時(差し・まくり差し)、すぐ内の艇は2着に残りやすい"
              "(2着の内訳を市場と比べると実際÷市場1.30)。対象の約半分は1コースがF持ちで、スタートを慎重に行って"
              "差されても2着には残る。市場は「F持ちのインは崩れる」と見て2-1をあまり買っていない可能性"),
    ]
    rows = "".join(f'<div class="boat"><div><b>{title}</b><br><span class="sub">{body}</span></div></div>' for title, body in steps)
    return (f'<div class="card"><b>2差し1残し・2連単2-1(pick21)のロジック</b>{rows}</div>'
            '<div class="card"><p class="sub" style="margin:0">立説中の運用です。2026年10月の記録194レースで的中28・回収率191%'
            '(一番大きい3件を除いても113%、前半116%・後半231%)。3・4コースで同じ形(3-2・4-3)は残らなかった。'
            'いろいろ見た中から見つけた形なので、本番で確かめる。総合収支には含めていません。</p></div>')


def _pick21t_logic_card():
    b = bet_mod
    steps = [
        ("対象レース", f'2連単2-1(pick21)と同じ: 2コースの予想スタートが1コースより{b.PICK21_ST_GAP}秒以上速いレース'),
        ("買い方", f'3連単2-1-□。3着はモデルの確率上位3艇で、{"・".join(f"{u * 100:,}円" for u in b.PICK21T_UNITS)}'
                 f'(合計{sum(b.PICK21T_UNITS) * 100:,}円)'),
        ("なぜ3着3艇か", "2-1で決まった時の3着は3コース10回・4コース6回・5コース12回・6コース7回とばらけていて、"
                      "1点だと95%、2点168%、3点185%、流し4点167%だった"),
    ]
    rows = "".join(f'<div class="boat"><div><b>{title}</b><br><span class="sub">{body}</span></div></div>' for title, body in steps)
    return (f'<div class="card"><b>2差し1残し・3連単2-1-□(pick21t)のロジック</b>{rows}</div>'
            '<div class="card"><p class="sub" style="margin:0">立説中の運用です。2026年9月末〜10月の記録242レースで的中32・'
            '回収率185%(2連単2-1は191%)。同じレースで2連単版と比べるために並べて記録しています。総合収支には含めていません。</p></div>')


def _pickura_logic_card():
    b = bet_mod
    steps = [
        ("① 対象レース", "B級イン・2連単と同じ(1コースが本物のB級・F持ちでない・モデルの1着確率20%以上)"),
        ("② 頭", "オッズを使わず実績だけで作った1着確率の予想(選手のコース別成績・勝率・級・年齢・体重・モーター・ボート・"
                 f"平均ST・F・展示タイム・風・波)が、市場の1着確率の{b.PICKURA_RATIO}倍以上かつ{b.PICKURA_MIN_P:.0%}以上と見る"
                 "1コース以外の艇。何艇でも"),
        ("③ 買い目と配分", f"頭1艇につき2着5艇を、オッズの逆数に比例して{b.PICKURA_UNITS * 100:,}円(単勝を買うのと同じ形)。"
                         "2着ごとに、2連単と3連単(3着4点をオッズ配分した合成)のオッズが高い方で買う"
                         "(同じ結果に高い値段の券種を選ぶだけ。確定オッズで回収率+5〜10ポイント)"),
        ("④ 印(★)", "あとで確かめるため、絞り込み候補に入った頭に★印を付け、運用画面で印あり・なしを分けて集計する: モーター上位×単勝相当10〜20倍、"
                 "インの市場35%未満×比1.7〜2.0、4コース×風3m以上"),
    ]
    rows = "".join(f'<div class="boat"><div><b>{t}</b><br><span class="sub">{x}</span></div></div>' for t, x in steps)
    return (f'<div class="card"><b>B級イン・裏の穴(pickura)のロジック</b>{rows}</div>'
            '<div class="card"><p class="sub" style="margin:0">実績だけの予想は2026年5月までで学習し、6〜10月の確定オッズで確かめた。'
            'B級インのレースは市場がインも外の艇も級で見すぎる。6〜7月395点・回収率90%、8〜10月502点・95%で、'
            '頭の1着は両方の期間とも市場の見立ての1.26倍・1.28倍。条件をいろいろ試して選んだものではなく、最初に決めた形のまま'
            '両方の期間でそろったので、立説中の優先度1。凪のB級イン系3つは6〜7月で100%を割った(84%・74%・78%)。</p></div>')


def _pickoutfav_logic_card():
    b = bet_mod
    steps = [("① 頭", f"2〜6コースの艇で、市場の1着確率(3連単オッズから)が{b.OUTFAV_Q:.0%}以上、本予想の1着確率が市場より{b.OUTFAV_GAP * 100:.0f}ポイント以上高い艇"),
             ("② 買い目", "頭1艇につき4,000円を単勝と同じ形(2着5艇をオッズ配分、2着ごとに2連単と3連単の高い方)"),
             ("③ 位置づけ", "確定オッズで2〜5月85%・6〜10月90%。固い外の本命は市場も正しく値付けしていて、単独では勝てない。"
                           "場・女子戦などのラベルで勝てる小さな箱が見つかった時に決裁者が使えるよう、社員として記録している")]
    rows = "".join(f'<div class="boat"><div><b>{t}</b><br><span class="sub">{x}</span></div></div>' for t, x in steps)
    return f'<div class="card"><b>外の本命(pickoutfav)のロジック</b>{rows}</div>'


def _pickfav_logic_card():
    b = bet_mod
    steps = [("① 対象", "全レース(インの級で条件を変える)"),
             ("② 買い目", f"1コースが頭の2連単のうち、オッズ{b.FAV_ODDS[0]}倍超〜{b.FAV_ODDS[1]}倍で、本予想の目の確率が市場の目の確率"
                         f"(2連単オッズから出した確率)の、B級インなら{b.FAV_RATIO_B[0]}〜{b.FAV_RATIO_B[1]}倍、A級インなら{b.FAV_RATIO_A[0]}倍以上の目"),
             ("③ 配分", f"1目{b.FAV_UNITS * 100:,}円。目ごとに、2連単と3連単(3着4点をオッズ配分した合成)の高い方で買う(確定オッズで+2〜3ポイント)"),
             ("④ 見つけ方と確かめ", "本命寄り(オッズ20倍まで)の目を、頭のコース×インの級×オッズの帯×比の帯の網の目にして、6〜10月の確定オッズで"
                                   "105%以上・300件以上のマスを選び、まっさらな2〜5月で何も変えずに確かめた。"
                                   "B級イン: 934件・的中12%・112% → 650件・108%、A級イン: 1,617件・的中11%・108% → 1,136件・100%。"
                                   "1着は市場もよく分かっているが、2着の組み合わせの値段にはズレが残っている")]
    rows = "".join(f'<div class="boat"><div><b>{t}</b><br><span class="sub">{x}</span></div></div>' for t, x in steps)
    return f'<div class="card"><b>イン頭・軽視された2着(pickfav)のロジック</b>{rows}</div>'


def _pickgen_logic_card():
    b = bet_mod
    bands = "・".join(lab for _, _, lab in b.GEN_BANDS)
    steps = [("① 対象", "全レース"),
             ("② 頭", f"オッズを見ない実績だけの予想(実績予想くん2号)が、市場の1着確率の{b.GEN_RATIO}倍以上・{b.GEN_MIN_P:.0%}以上と見る艇(インも含む)。何艇でも"),
             ("③ 買い目", f"頭1艇につき{b.GEN_UNITS * 100:,}円を単勝と同じ形(2着5艇をオッズ配分、2着ごとに2連単と3連単の高い方)"),
             ("④ 印", f"比の帯({bands}倍)×インの級(A/B)の印を付ける。人が条件を選ばず、網の目で機械的に作った社員。"
                     "どの印の箱が勝てるかは、組織図の自信度(確定オッズの過去データ)で決まる")]
    rows = "".join(f'<div class="boat"><div><b>{t}</b><br><span class="sub">{x}</span></div></div>' for t, x in steps)
    return f'<div class="card"><b>一般職・市場が軽く見る艇(pickgen)のロジック</b>{rows}</div>'


def _sanka_logic_card(pk):
    b = bet_mod
    cond = (f"本予想のインの1着確率{b.SANKA_BIN_P:.0%}以上で、インがB級(B1・B2)" if pk == "sankabin"
            else f"本予想のインの1着確率{b.SANKA_GAP_P:.0%}以上で、市場(3連単オッズから出した1着確率)より{b.SANKA_GAP * 100:.0f}ポイント以上高い")
    ev = ("確定オッズで6/1〜8/9は186R・的中72%・回収率92%、8/10〜10/13は180R・的中70%・回収率91%" if pk == "sankabin"
          else "確定オッズで6/1〜8/9は1,432R・的中64%・回収率89%、8/10〜10/13は1,424R・的中65%・回収率88%")
    steps = [("① 対象レース", cond),
             ("② 買い目と配分", f"インの頭で、2着5艇をオッズの逆数に比例して{b.SANKA_UNITS * 100:,}円(単勝と同じ形)。2着ごとに2連単と3連単の高い方で買う"),
             ("③ 位置づけ", "参加枠。本番の決裁者・総合収支とは別に集計する。過去は2期間とも回収率9割前後で、平均すると1割前後負ける前提の、楽しむ用の買い目"),
             ("④ 過去の成績", ev)]
    rows = "".join(f'<div class="boat"><div><b>{t}</b><br><span class="sub">{x}</span></div></div>' for t, x in steps)
    return f'<div class="card"><b>{SANKA_LABELS[pk]}({pk})のロジック</b>{rows}</div>'


def _calm_logic_card(key, name, cond, evidence):
    b = bet_mod
    steps = [
        ("① 対象レース", "B級イン・2連単と同じ(1コースが本物のB級・F持ちでない・モデルの1着確率20%以上)に加えて、"
                       f"展示の時点の風速が{b.PICKBIN_CALM_WIND}m以下、かつ{cond}"),
        ("② 買い目", "1コース頭の2連単。2着は2連単オッズの人気上位3艇"),
        ("③ 配分", f"オッズの逆数に比例して{b.PICKBINX_UNITS * 100:,}円を配る(どの目が来ても払戻がほぼ同じになる)"),
    ]
    rows = "".join(f'<div class="boat"><div><b>{t}</b><br><span class="sub">{x}</span></div></div>' for t, x in steps)
    return (f'<div class="card"><b>{name}({key})のロジック</b>{rows}</div>'
            f'<div class="card"><p class="sub" style="margin:0">{evidence}</p></div>')


def _pickbinc_logic_card():
    return _calm_logic_card("pickbinc", "B級イン・凪で強敵なし",
                            f"1コース以外の艇の市場の1着確率(3連単オッズから計算)が全部{bet_mod.PICKBINX_RIVAL_MAX:.0%}未満",
                            "8/10〜10/13の確定オッズで、B級インの対象1,699レースに28個の条件を1つ・2つ組み合わせた734通りを試し、"
                            "前半(8/10〜9/5)で良かったものを後半(9/6〜10/13)で確かめた中で残ったもの。前半44R・回収率114%、"
                            "後半85R・107%、インの1着は市場の見立ての1.52倍・1.27倍。穏やかな水面で他に強い艇がいなければ、"
                            "B級のインでも逃げ切りやすいのに、市場は級で割り引いているという説。立説中の優先度1。")


def _pickbint_logic_card():
    return _calm_logic_card("pickbint", "B級イン・凪で展示1位", "1コースの展示タイムが6艇で一番速い(同タイムを含む)",
                            "B級イン・凪で強敵なしと同じ探し方で残ったもう1つ。前半98R・回収率118%(上位3件を除いても103%)、"
                            "後半164R・103%、インの1着は市場の見立ての1.37倍・1.28倍。立説中の優先度2。")


def _pickbinx_logic_card():
    b = bet_mod
    steps = [
        ("① 対象レース", "B級イン・2連単と同じ(1コースが本物のB級・F持ちでない・モデルの1着確率20%以上)に加えて、"
                       f"1コース以外の艇の市場の1着確率(3連単オッズから計算)が全部{b.PICKBINX_RIVAL_MAX:.0%}未満、"
                       "かつ1コースの予想スタートが6艇で一番速いレース"),
        ("② 買い目", "1コース頭の2連単。2着は2連単オッズの人気上位3艇"),
        ("③ 配分", f"オッズの逆数に比例して{b.PICKBINX_UNITS * 100:,}円を配る(どの目が来ても払戻がほぼ同じになる)"),
    ]
    rows = "".join(f'<div class="boat"><div><b>{t}</b><br><span class="sub">{x}</span></div></div>' for t, x in steps)
    return (f'<div class="card"><b>B級イン・絞り込み(pickbinx)のロジック</b>{rows}</div>'
            '<div class="card"><p class="sub" style="margin:0">8/10〜10/13の確定オッズで確かめた結果から。B級イン全体は'
            '回収率81%だったが、他に強い艇がいない時はインの1着が市場の1.2倍(前半・後半とも)で的中率も約6割。'
            'さらに1コースの予想スタートが一番速い時は1.44倍・1.29倍、回収率115%・106%(85レース、1日1〜2レース)。'
            '20個ほど試した条件のうち一番良かったものなので、本番では下がる前提で記録している。'
            '2着はAI上位2艇・2位厚めより、人気上位3艇をオッズに合わせて配分する方が安定していた。</p></div>')


def _pick6a_logic_card():
    b = bet_mod
    steps = [
        ("対象レース", "A級が6コースだけで、1〜5コースが全員B級のレース(1日1〜2レース程度)"),
        ("買い方", f'1コース頭の2連単で、2着は6コース以外のモデル上位2艇。2着1位に{b.PICK6A_UNITS[0] * 100:,}円・'
                 f'2位に{b.PICK6A_UNITS[1] * 100:,}円(合計{sum(b.PICK6A_UNITS) * 100:,}円)'),
        ("説", "市場は6コースのA級を買いかぶっていて、直近の実オッズでは1着16%と見ているが、6年分の実際は8.3%。"
              "そのぶんインのB級が割り引かれている(6年分の実際47.5%・市場40%)"),
    ]
    rows = "".join(f'<div class="boat"><div><b>{title}</b><br><span class="sub">{body}</span></div></div>' for title, body in steps)
    return (f'<div class="card"><b>6コースだけA級・2連単(pick6a)のロジック</b>{rows}</div>'
            '<div class="card"><p class="sub" style="margin:0">立説中の運用です。6年分の着順(約3,100レース)では説どおりだが、'
            '市場の見立ては直近17レース分しかなく未確認。総合収支には含めていません。</p></div>')


def _pickbin_logic_card():
    b = bet_mod
    steps = [
        ("対象レース", f'1コースが「本物の」B級で、モデルの1コース1着確率が{b.PICKBIN_HP_MIN:.0%}以上のレースだけ。'
                     'ただし1コースがF持ちのレースは除く'),
        ("F持ちを除く理由", "インがF持ちだとスタートを慎重に行く分勝ち切れない(実際48.8%)のに、市場はFなしと同じに"
                         "見ている(47%)。B級インでもF持ちは回収率60%(79R)、Fなしは138%(251R)だった"),
        ("嘘B級の除外", f'B級でも全国勝率{b.PICKBIN_FAKE_WIN}以上、または直近{b.PICKBIN_FAKE_MONTHS // 12}年の番組表で'
                     '1度でもA級だった選手(フライング休み明けなどで一時的にB級の実力者)は対象外'),
        ("買い方", f'1コース頭の2連単で、2着はモデルの確率上位2艇の2点。2着1位に{b.PICKBIN_UNITS[0] * 100:,}円・'
                 f'2位に{b.PICKBIN_UNITS[1] * 100:,}円(2位の方が配当が良く、回収率も高かったので厚め)'),
        ("2着から外す艇", "外枠(4〜6コース)のA級は2着候補から外し、残りの上位2艇にする。市場は外枠のA級を"
                       "買いすぎていて(6コースA級の1着率は実際3.1%に対し市場6.1%)、2着に置いた目は回収率69%と弱かった"),
        ("なぜB級インか", "市場はB級のインを割り引きすぎている。実オッズ1,659レースで、本物B級インの1着率は"
                       "実際38.4%に対し、オッズから逆算した市場の確率は29.5%だった(A級インは65.8%対59.0%)。"
                       "嘘B級は逆にモデルが勝率の高さから過大評価していたので除外している"),
    ]
    rows = "".join(f'<div class="boat"><div><b>{title}</b><br><span class="sub">{body}</span></div></div>' for title, body in steps)
    return (f'<div class="card"><b>B級イン・2連単(pickbin)のロジック</b>{rows}</div>'
            '<div class="card"><p class="sub" style="margin:0">2026年10月2日〜13日・締切前の実オッズ1,659レースで検証。'
            'モデル20%以上の214レースで実際の1着率39.3%(市場28.9%)。2着の指定は1艇105%・2艇(この配分)113%・'
            '3艇98%・全艇94%で、2艇が一番良かった(301レース、90%区間93〜134%)。外枠A級を2着から外すと117%'
            '(いくつか試した中で選んだ形なので、本番では少し下がる前提で見る)。'
            'サンプルが小さく、まだ偶然と区別できないため、本番で実績を貯めて確かめる試験プランです。'
            '目安であり保証ではありません。</p></div>')


def _escape_logic_card():
    b = bet_mod
    steps = [
        ("対象レース", f'1コース1着確率(nige)が{b.PICKIN_NIGE_MIN:.0%}以上のレースだけ'),
        ("頭候補", "2連単(3連単ではない)で、確率が高い順に1位・2位の2艇を比べる"),
        ("逆張り判定", f'市場のオッズ比(2位オッズ÷1位オッズ)が、モデルの確率比(1位確率÷2位確率)を'
                   f'{b.PICKIN_GAP_MIN:.1f}以上上回っていたら、「市場がモデルの確率差以上に1位へ寄せすぎている」'
                   f'と判断し、2位の1点に予算{b.PICKIN_BUDGET:,}円を全額集中(オッズ{b.PICKIN_MIN_ODDS}倍未満は見送り)'),
        ("なぜ2位の逆張りか", "確率1位をそのまま買う旧ロジックは、1コースが堅いレース(nige80%以上)の実オッズ"
                        "フルセンサス検証(1,130レース)で回収率87.2%と勝てなかった。市場とモデルの確率の"
                        "ズレが大きい時だけ2位に切り替えると、同条件で146.6%(一番大きい的中3件を除いても"
                        "110.2%)と明確に上回った"),
        ("見送り", f'gapが{b.PICKIN_GAP_MIN:.1f}未満、または2位のオッズが{b.PICKIN_MIN_ODDS}倍未満なら、'
                 'そのレースは買わない(条件が狭いため月10〜15件程度とかなり稀)'),
    ]
    rows = "".join(f'<div class="boat"><div><b>{title}</b><br><span class="sub">{body}</span></div></div>' for title, body in steps)
    return (f'<div class="card"><b>イン(逃げ切り)・逆張りのロジック</b>{rows}</div>'
            '<div class="card"><p class="sub" style="margin:0">2026年6月〜10月・nige80%以上の実オッズ'
            'フルセンサス1,130レースで検証(確率1位そのまま=87.2%→gap逆張りで2位に切替=146.6%、'
            '一番大きい的中3件を除いても110.2%)。0.70〜0.80%帯はまだ未検証。目安であり保証ではありません。'
            'パラメータは今後の検証で変わることがあります。</p></div>')


def venue_page(date, jcd, infos, preds, now):
    v = VENUES[jcd]
    items = ""
    cur_marked = False
    lres = live_result.load(date)
    for i, info in enumerate(infos):
        pred = preds.get(f"{jcd}-{info['race']:02d}")
        st = race_status(date, info, pred, now)
        badge = {"hot": '<span class="rst s-hot">予想公開中</span>', "wait": '<span class="rst s-wait">展示待ち</span>',
                 "done": '<span class="rst s-done">締切</span>'}[st]
        if st == "hot":
            x = _rank_of(date, jcd, info["race"], pred)
            if x:
                (rk, _, word, _), fav, _ = x
                badge = (f'<span class="sub" style="margin-left:auto;text-align:right;font-size:12px">{html.escape(hook(x[2])[0])}</span>'
                         f'<span class="rank rank-{rk}" style="width:26px;height:26px;font-size:14px;margin:0 0 0 8px">{rk}</span>')
        if st == "done":
            res = lres.get(f"{jcd}-{info['race']:02d}")
            x = res and res.get("combo3t") and _rank_of(date, jcd, info["race"], pred)
            if x:
                lab, ok = _judge(x[2], res)
                badge = (f'<span class="sub" style="margin-left:auto">{res["combo3t"]}</span>'
                         + (f'<span class="ok" style="margin-left:8px">{lab.replace(" 的中", "")}◎</span>' if ok else '<span class="ng" style="margin-left:8px">外れ</span>'))
        cur_id = ""
        if not cur_marked and st in ("hot", "wait"):
            cur_id = ' id="cur"'
            cur_marked = True
        items += (f'<a{cur_id} href="/{date}/{jcd}/{info["race"]:02d}.html"><span class="rno">{info["race"]}R</span>'
                  f'<span><span class="sub">{info["deadline"]}</span> {html.escape(info["rtype"])}</span>{badge}</a>')
        if i == 5:
            items += f"</div>{ad()}<div class='card list'>"
    head = (f'<h1>{v} {jp(date)}</h1><p class="sub">{html.escape(infos[0]["title"])}・{infos[0]["day"]}日目'
            f'・<a href="/venue/{SLUG[jcd]}.html" style="color:var(--ac)">{v}の特徴</a></p>')
    scroll = '<script>document.getElementById("cur")?.scrollIntoView({block:"center"})</script>'
    return page(f"{v} {jp(date)} 出走表・展開予想", head + f"<div class='card list'>{items}</div>" + scroll,
                f"{v}の全レースの出走表と1マーク展開予想", f"/{date}/{jcd}/")


def _trifecta_matches(pred, combo3t):
    tri = pred.get("scene", {}).get("trifecta") if pred else None
    if not tri or not combo3t:
        return False
    waku = [b["waku"] for b in pred["boats"]]
    want = tuple(int(x) for x in combo3t.split("-"))
    top = tuple(waku[i] for i in tri[0][:3])
    return top == want


def _payout_html(date, payouts, preds):
    if not payouts:
        return ""
    rows = ""
    for p in payouts:
        jcd, race, combo, amt = p["jcd"], int(p["race"]), p["combo3t"], int(p["payout3t"])
        pred = preds.get(f"{jcd}-{race:02d}")
        badge = '<span class="rst s-hot">本命シナリオ的中！</span>' if _trifecta_matches(pred, combo) else ""
        rows += (f'<a href="/{date}/{jcd}/{race:02d}-result.html"><span class="rno" style="width:80px">{VENUES[jcd]} {race}R</span>'
                 f'<span>{combo} <b>{amt:,}円</b></span>{badge}</a>')
    return f"<h2>本日の高配当（万舟以上）</h2><div class='card list'>{rows}</div>"


def _with_live_payouts(payouts, date, thr=10000):
    """成績ファイルがまだのレースの万舟を、レース結果ページから取り込んだ結果で補う"""
    have = {(p["jcd"], int(p["race"])) for p in payouts}
    for k, v in live_result.load(date).items():
        jcd, race = k[:2], int(k[3:])
        if (jcd, race) not in have and v.get("payout3t") and v["payout3t"] >= thr:
            payouts.append(dict(jcd=jcd, race=race, combo3t=v["combo3t"], payout3t=v["payout3t"]))
    return sorted(payouts, key=lambda p: -p["payout3t"])


def _rank_of(date, jcd, race, pred):
    """レースの堅さのランク(S〜C)と本命の艇番。予想が出ていなければNone"""
    if not (pred and pred.get("version") == "final"):
        return None
    ck = (date, jcd, race, id(pred))
    if ck not in _RANK_CACHE:
        _RANK_CACHE[ck] = _rank_of_raw(date, jcd, race, pred)
    return _RANK_CACHE[ck]


_RANK_CACHE = {}


def _rank_of_raw(date, jcd, race, pred):
    vw = race_view_of(date, dict(jcd=jcd, race=race), pred)
    if not vw:
        return None
    p5 = sum(p for _, p in vw["top3"][:5])
    rk = next(x for x in RANKS if p5 >= x[1])
    fav = max(vw["boats"], key=lambda b: b["p1"])
    return rk, fav, vw


def _next_races_html(date, prog_day, preds, now, n=6):
    """トップの「次のレース」: 締切が近い順に、ランク・本命・おすすめの1点目"""
    rows = []
    for r in prog_day.drop_duplicates(["jcd", "race"]).itertuples():
        t = dl_dt(date, r.deadline)
        if t > now:
            rows.append((t, r.jcd, int(r.race), r.deadline))
    rows = sorted(rows)[:n]
    if not rows:
        return ""
    out = ""
    for t, j, race, dl in rows:
        x = _rank_of(date, j, race, preds.get(f"{j}-{race:02d}"))
        mins = int((t - now).total_seconds() // 60)
        if x:
            (rk, _, word, _), fav, vw = x
            badge = f'<span class="rank rank-{rk}">{rk}</span>'
            info = f'{hook(vw)[0]}・{vw["top3"][0][0]}'
        else:
            badge = '<span class="rank rank-w">展示<br>待ち</span>'
            op = (t - dt.timedelta(minutes=20)).strftime("%H:%M")
            pp = preds.get(f"{j}-{race:02d}")
            pv = race_view_of(date, dict(jcd=j, race=race), pp) if pp and pp.get("tri") else None
            info = f"見立て：{hook(pv)[0]}" if pv else f"{op}ごろ予想を公開"
        out += (f'<a class="nx" href="/{date}/{j}/{race:02d}.html">{badge}<span class="t"><b>{VENUES[j]} {race}R</b>'
                f'<span class="sub">{info}</span></span><span class="dl">{dl}<small>あと{mins}分</small></span></a>')
    return ('<h2>次のレース <span class="sub">S＝堅い 〜 C＝混戦・<a href="/today.html" style="color:var(--ac)">今日の注目</a></span></h2>'
            f'<div class="card" style="padding:2px 12px">{out}</div>')


def _judge(vw, res):
    """結果と予想の突き合わせ → (印の文字, 当たりか)"""
    c3, c2 = res.get("combo3t"), res.get("combo2t")
    fav = max(vw["boats"], key=lambda b: b["p1"])["waku"]
    if c3 in [c for c, _ in vw["top3"][:5]]:
        return "3連単5点 的中", True
    if c2 and c2 == vw["top2"][0][0]:
        return "2連単1番手 的中", True
    if c3 and c3.split("-")[0] == str(fav):
        return "本命1着", True
    return "外れ", False


def _recent_results_html(date, prog_day, preds, now, n=4):
    """トップの「さっきの結果」: 締切を過ぎたレースの結果と、予想が当たったか(外れも出す)"""
    live = live_result.load(date)
    rows = []
    for r in prog_day.drop_duplicates(["jcd", "race"]).itertuples():
        key = f"{r.jcd}-{int(r.race):02d}"
        res = live.get(key)
        if dl_dt(date, r.deadline) <= now and res and res.get("combo3t"):
            x = _rank_of(date, r.jcd, int(r.race), preds.get(key))
            if x:
                rows.append((r.deadline, r.jcd, int(r.race), res, x[2]))
    if not rows:
        return ""
    judged = [(dl, j, race, res, _judge(vw, res)) for dl, j, race, res, vw in rows]
    hit = sum(1 for *_, (_, ok) in judged if ok)
    out = ""
    for dl, j, race, res, (lab, ok) in sorted(judged, reverse=True)[:n]:
        pay = f'{int(res["payout3t"]):,}円' if res.get("payout3t") else ""
        mark = f'<span class="ok">{lab}</span>' if ok else f'<span class="ng">{lab}</span>'
        out += (f'<a class="res" href="/{date}/{j}/{race:02d}-result.html"><span class="t"><b>{VENUES[j]} {race}R</b> '
                f'<span class="sub">{res["combo3t"]} {pay}</span></span>{mark}</a>')
    return (f'<h2>さっきの結果 <span class="sub">今日 {len(judged)}レース中 {hit}レースで予想が的中・'
            '<a href="/record.html" style="color:var(--ac)">実績</a></span></h2>'
            f'<div class="card" style="padding:2px 12px">{out}</div>')


SLUG = {"01": "kiryu", "02": "toda", "03": "edogawa", "04": "heiwajima", "05": "tamagawa", "06": "hamanako", "07": "gamagori",
        "08": "tokoname", "09": "tsu", "10": "mikuni", "11": "biwako", "12": "suminoe", "13": "amagasaki", "14": "naruto",
        "15": "marugame", "16": "kojima", "17": "miyajima", "18": "tokuyama", "19": "shimonoseki", "20": "wakamatsu",
        "21": "ashiya", "22": "fukuoka", "23": "karatsu", "24": "omura"}


@functools.lru_cache(maxsize=1)
def _venue_stats():
    p = DATA / "venue_stats.json"
    return json.loads(p.read_text()) if p.exists() else {}


@functools.lru_cache(maxsize=1)
def rank_record():
    """的中実績: サイトに出した予想(締切前のオッズを混ぜたもの)を、結果と突き合わせた記録。
    {"all": {ランク: [レース数, 5点的中, 2連単1番手的中, 本命1着]}, 場コード: {...}, "since": 最初の日}"""
    out, since = {}, None
    for f in sorted((DATA / "odds_live").glob("*.json")):
        date = f.stem
        pp = DATA / "predictions" / f"{date}.json"
        if not pp.exists():
            continue
        preds = json.loads(pp.read_text())["races"]
        live = live_result.load(date)
        odds = race_view.load_odds(date)
        ents = _entries(date)
        for key, od in odds.items():
            res, pred = live.get(key), preds.get(key)
            if not res or not res.get("combo3t") or not pred or pred.get("version") != "final":
                continue
            try:
                lv = ents.get(key)
                v = race_view.view(pred, date, od, lv if isinstance(lv, dict) else None)
            except Exception:
                continue
            if not v:
                continue
            p5 = sum(p for _, p in v["top3"][:5])
            rk = next(x for x in RANKS if p5 >= x[1])[0]
            fav = max(v["boats"], key=lambda b: b["p1"])["waku"]
            row = [1, int(res["combo3t"] in [c for c, _ in v["top3"][:5]]), int(res.get("combo2t") == v["top2"][0][0]),
                   int(res["combo3t"].split("-")[0] == str(fav))]
            for g in ("all", key[:2]):
                a = out.setdefault(g, {}).setdefault(rk, [0, 0, 0, 0])
                for i, x in enumerate(row):
                    a[i] += x
            since = since or date
    out["since"] = since
    return out


def _record_table(rec):
    if not rec:
        return '<p class="sub">まだ記録がありません</p>'
    rows = ""
    for rk, _, word, hist in RANKS:
        a = rec.get(rk)
        if not a or not a[0]:
            continue
        n = a[0]
        rows += (f'<tr><td><span class="rank rank-{rk}" style="width:24px;height:24px;font-size:13px">{rk}</span></td><td>{n}</td>'
                 f'<td><b>{a[1] / n:.0%}</b> <span class="sub">({hist})</span></td><td>{a[2] / n:.0%}</td><td>{a[3] / n:.0%}</td></tr>')
    if not rows:
        return '<p class="sub">まだ記録がありません</p>'
    return ('<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px;text-align:center;white-space:nowrap">'
            '<tr class="sub"><th></th><th>レース</th><th>3連単5点</th><th>2連単1点</th><th>本命1着</th></tr>' + rows + '</table></div>'
            '<p class="sub" style="margin:4px 0 0">( )内は過去データでの見込み。ランクが高いほど当たる、が予想どおりかを見る表です。</p>')


def record_page():
    rec = rank_record()
    allr = rec.get("all", {})
    n = sum(a[0] for a in allr.values()) if allr else 0
    since = jp(rec["since"]) if rec.get("since") else "―"
    body = ('<h1>的中実績</h1><p class="sub">サイトに出した予想（締切前のオッズを混ぜた確率）を、レース結果と突き合わせた記録です。'
            f'{since}から {n}レース。毎日自動で更新します。</p>'
            '<h2>ランク別</h2><div class="card">' + _record_table(allr) + '</div>'
            '<h2>場ごと</h2><div class="card list">'
            + "".join(f'<a href="/venue/{SLUG[j]}.html"><span class="rno" style="width:70px">{VENUES[j]}</span>'
                      f'<span class="sub">{sum(a[0] for a in rec[j].values())}レース・3連単5点 '
                      f'{sum(a[1] for a in rec[j].values()) / max(1, sum(a[0] for a in rec[j].values())):.0%}</span></a>'
                      for j in sorted(k for k in rec if k not in ("all", "since")))
            + '</div>' + ad())
    return page("的中実績", body, "競艇予想のランク別・場ごとの的中実績。予想した確率どおりに当たっているかを毎日公開。", "/record.html")


def _venue_lines(jcd, st):
    """場の特徴をひとことで(全国平均と比べて)"""
    allc = _venue_stats().get("_all", {}).get("course", [0.55, 0.13, 0.12, 0.1, 0.06, 0.02])
    c1 = st["course"][0][0]
    out = []
    if c1 >= allc[0] + 0.03:
        out.append(f"インが強い場（1コースの1着 {c1:.0%}、全国平均 {allc[0]:.0%}）")
    elif c1 <= allc[0] - 0.03:
        out.append(f"インが弱めの場（1コースの1着 {c1:.0%}、全国平均 {allc[0]:.0%}）")
    else:
        out.append(f"インの強さは全国並み（1コースの1着 {c1:.0%}）")
    best = max(range(1, 6), key=lambda k: st["course"][k][0] - allc[k])
    if st["course"][best][0] - allc[best] >= 0.01:
        out.append(f"{best + 1}コースが全国平均より勝てる（{st['course'][best][0]:.0%}）")
    km = {k: v for k, v in st["kimarite"].items() if k != "逃げ"}
    if km:
        k, v = max(km.items(), key=lambda kv: kv[1])
        out.append(f"イン以外の決まり手は「{k}」が多い（1着の{v:.0%}）")
    if st.get("manshu") is not None:
        out.append(f"万舟（3連単100倍以上）は {st['manshu']:.0%}、3連単の真ん中の配当は {st['pay_median']:,.0f}円")
    if st.get("lady_in") is not None and st.get("lady_races", 0) >= 50:
        out.append(f"女子戦ではインの1着 {st['lady_in']:.0%}")
    return out


def venue_home(jcd, date, prog_day, preds, now, recent=None):
    """場の常設ページ(/venue/場.html): 今日のレースとランク、場の特徴、この場での的中実績"""
    v = VENUES[jcd]
    st = _venue_stats().get(jcd)
    g = prog_day[prog_day.jcd == jcd].drop_duplicates("race").sort_values("race") if len(prog_day) else prog_day
    rows = ""
    for r in g.itertuples():
        x = _rank_of(date, jcd, int(r.race), preds.get(f"{jcd}-{int(r.race):02d}"))
        badge = (f'<span class="sub" style="margin-left:auto">本命{x[1]["waku"]}</span>'
                 f'<span class="rank rank-{x[0][0]}" style="width:26px;height:26px;font-size:14px;margin:0 0 0 8px">{x[0][0]}</span>') if x else             ('<span class="rst s-done">締切</span>' if now >= dl_dt(date, r.deadline) else '<span class="rst s-wait">展示待ち</span>')
        rows += (f'<a href="/{date}/{jcd}/{int(r.race):02d}.html"><span class="rno">{int(r.race)}R</span>'
                 f'<span><span class="sub">{r.deadline}</span> {html.escape(r.rtype)}</span>{badge}</a>')
    today = (f'<h2>{jp(date)}のレース</h2><div class="card list">{rows}</div>' if rows
             else f'<h2>今日のレース</h2><div class="card"><p class="sub" style="margin:0">{jp(date)}は{v}の開催はありません。</p></div>')
    feat = ""
    if st:
        lines = "".join(f"<li>{html.escape(t)}</li>" for t in _venue_lines(jcd, st))
        allc = _venue_stats().get("_all", {}).get("course", [0] * 6)
        bars = "".join(f'<div class="boat" style="padding:5px 0">{chip(k + 1)}<span style="flex:1;font-size:13px">1着 <b>{st["course"][k][0]:.0%}</b>'
                       f'<span class="sub">（全国{allc[k]:.0%}）・2着以内 {st["course"][k][1]:.0%}</span></span>'
                       f'<span class="bar" style="width:90px"><i style="width:{st["course"][k][0] * 100 / 0.7:.0f}%"></i></span></div>'
                       for k in range(6))
        feat = (f'<h2>{v}の特徴</h2><div class="card"><ul style="margin:0;padding-left:18px;font-size:14px">{lines}</ul></div>'
                f'<h2>コース別の成績 <span class="sub">{st["since"][:4]}年〜・{st["races"]:,}レース</span></h2><div class="card">{bars}</div>')
    rec = rank_record().get(jcd)
    record = f'<h2>{v}での的中実績</h2><div class="card">{_record_table(rec)}</div>' if rec else ""
    rc = ""
    if recent:
        top = recent["top"]
        rc = (f'<h2>最近の{v} <span class="sub">直近30日・{recent["days"]}日間 {recent["n"]}レース</span></h2><div class="card"><ul style="margin:0;padding-left:18px;font-size:14px">'
              f'<li>1号艇の1着 {recent["w1"]:.0%}' + (f'（いつもは {st["course"][0][0]:.0%}）' if st else "") + '</li>'
              + (f'<li>万舟 {recent["manshu"]:.0%}</li>' if recent["manshu"] is not None else "")
              + (f'<li>一番の高配当 {jp(top[0])} {top[1]}R {top[2]} {top[3]:,}円</li>' if top else "") + '</ul></div>')
    faq = ""
    if st:
        c1 = st["course"][0][0]
        allc = _venue_stats().get("_all", {}).get("course", [0.55])
        faq = (f'<h2>{v}のよくある疑問</h2><div class="card" style="font-size:14px">'
               f'<p><b>{v}はインが強い？</b><br>1コースの1着は {c1:.0%} で、全国平均の {allc[0]:.0%} と比べて'
               f'{"強め" if c1 >= allc[0] + 0.03 else ("弱め" if c1 <= allc[0] - 0.03 else "ほぼ同じ")}です。</p>'
               + (f'<p><b>{v}は荒れる？</b><br>3連単が100倍以上になる万舟は {st["manshu"]:.0%}、配当の真ん中は {st["pay_median"]:,.0f}円です。</p>'
                  if st.get("manshu") is not None else "")
               + f'<p style="margin-bottom:0"><b>予想はいつ出る？</b><br>展示の進入が出たあと（締切の約20分前）に、1着・2着・3着の確率と堅さのランクを公開します。</p></div>')
    body = (f'<h1>{v}の競艇予想</h1><p class="sub">ボートレース{v}の今日のレースの予想（堅さのランクと本命）と、'
            f'コース別の成績などの特徴をまとめています。</p>' + today + feat + rc + record + faq
            + '<p class="sub"><a href="/venue/" style="color:var(--ac)">ほかの場を見る</a>・<a href="/record.html" style="color:var(--ac)">全体の的中実績</a></p>' + ad())
    return page(f"{v}の競艇予想・特徴", body, f"ボートレース{v}の今日の予想と、コース別の勝率・決まり手・万舟率などの特徴。", f"/venue/{SLUG[jcd]}.html")


def venue_index():
    st = _venue_stats()
    items = "".join(f'<a href="/venue/{SLUG[j]}.html"><span class="rno" style="width:70px">{VENUES[j]}</span>'
                    + (f'<span class="sub">イン1着 {st[j]["course"][0][0]:.0%}・万舟 {st[j]["manshu"]:.0%}</span>' if j in st and st[j].get("manshu") is not None else "")
                    + '</a>' for j in sorted(SLUG))
    return page("全24場の特徴", f'<h1>全24場の特徴と予想</h1><div class="card list">{items}</div>{ad()}',
                "ボートレース全24場のインの強さ・万舟率と、今日の予想。", "/venue/")



def today_page(date, prog_day, preds, now):
    """今日の注目レース(/today.html): これからのSランク(堅い)と、🔥の艇がいるレース、今日のSランクの答え合わせ"""
    live = live_result.load(date)
    up_s, up_hot, done_s = [], [], []
    for r in prog_day.drop_duplicates(["jcd", "race"]).itertuples():
        j, race = r.jcd, int(r.race)
        x = _rank_of(date, j, race, preds.get(f"{j}-{race:02d}"))
        if not x:
            continue
        (rk, _, word, _), fav, vw = x
        t = dl_dt(date, r.deadline)
        hot = [b for b in vw["boats"] if b["heat"] > 0 and b["p1"] + b["p2"] >= 0.3]
        item = (r.deadline, j, race, rk, fav, vw, hot)
        if t > now:
            if rk == "S":
                up_s.append(item)
            elif hot:
                up_hot.append(item)
        elif rk == "S" and live.get(f"{j}-{race:02d}"):
            res = live[f"{j}-{race:02d}"]
            done_s.append((item, res["combo3t"] in [c for c, _ in vw["top3"][:5]], res["combo3t"]))

    def card(it, extra=""):
        dl, j, race, rk, fav, vw, hot = it
        picks = " ".join(f'<span>{c}</span>' for c, _ in vw["top3"][:5]) if rk in ("S", "A") else ""
        return (f'<a class="nx" href="/{date}/{j}/{race:02d}.html"><span class="rank rank-{rk}">{rk}</span><span class="t">'
                f'<b>{VENUES[j]} {race}R</b><span class="sub">本命{fav["waku"]}号艇（{_pct(fav["p1"])}）{extra}</span>'
                + (f'<span class="big5" style="margin:4px 0 0">{picks}</span>' if picks else "")
                + f'</span><span class="dl">{dl}</span></a>')
    s_html = "".join(card(it) for it in sorted(up_s)[:10]) or '<p class="sub" style="margin:8px 0">これからのSランクはありません</p>'
    h_html = "".join(card(it, "・🔥" + "・".join(f'{b["waku"]}号艇' for b in it[6])) for it in sorted(up_hot)[:10]) \
        or '<p class="sub" style="margin:8px 0">これからの🔥はありません</p>'
    hit = sum(1 for _, ok, _ in done_s if ok)
    d_html = "".join(f'<div class="boat" style="padding:6px 0"><span style="flex:1"><b>{VENUES[it[1]]} {it[2]}R</b> '
                     f'<span class="sub">結果 {c3}</span></span><b style="color:{"var(--green)" if ok else "var(--sub)"}">{"的中" if ok else "はずれ"}</b></div>'
                     for it, ok, c3 in sorted(done_s))
    body = (f'<h1>今日の注目レース <span class="sub">{jp(date)}</span></h1>'
            '<p class="sub">これから締切のレースから、堅い（Sランク）レースのおすすめ5点と、普段より調子のいい艇（🔥）がいるレースを集めました。</p>'
            f'<h2>堅いレース（S）</h2><div class="card" style="padding:2px 12px">{s_html}</div>'
            f'<h2>🔥の艇がいるレース</h2><div class="card" style="padding:2px 12px">{h_html}</div>'
            + (f'<h2>今日のSランクの答え合わせ <span class="sub">5点で{hit}/{len(done_s)}的中</span></h2><div class="card">{d_html}</div>' if done_s else "")
            + '<div class="btnrow"><a href="/record.html">的中実績</a><a href="/">トップへ</a></div>' + ad())
    return page(f"今日の注目レース {jp(date)}", body, f"{jp(date)}の競艇の注目レース。堅いレースのおすすめ5点と、調子のいい艇。", "/today.html")


def grid_page(date, dates, prog_day, preds, now, path, payouts=None):
    tiles = ""
    hot_list = []
    for j in [f"{i:02d}" for i in range(1, 25)]:
        v = VENUES[j]
        g = prog_day[prog_day.jcd == j]
        if g.empty:
            tiles += f'<div class="tile none"><b>{v}</b></div>'
            continue
        infos = g.drop_duplicates("race").sort_values("race")
        dls = [dl_dt(date, x) for x in infos.deadline]
        hot = [r for r in infos.itertuples() if race_status(date, r._asdict(), preds.get(f"{j}-{r.race:02d}"), now) == "hot"]
        hot_list += [(r.deadline, j, r.race) for r in hot]
        ic = ""
        if max(infos.deadline) >= "19:00":
            ic = '<span class="tag" style="background:#3C3489">ナイター</span>'
        elif min(infos.deadline) <= "09:30":
            ic = '<span class="tag" style="background:#1D9E75">モーニング</span>'
        headb = ""
        if hot:
            cls, st = "hot", '<span class="hotb">予想公開中</span>'
            hp = preds.get(f"{j}-{hot[0].race:02d}")
            heads = hp["scene"]["head"] if hp else []
            if heads:
                w = hp["boats"][heads[0]]["waku"]
                headb = f'<span class="headb" style="background:{BC[w - 1]};color:{TC[w - 1]}">{w}</span>'
        elif now >= max(dls):
            cls, st = "done", '<span class="st">開催終了</span>'
        elif now < min(dls) - dt.timedelta(minutes=40):
            cls, st = "", f'<span class="st">1R {infos.deadline.iloc[0]}</span>'
        else:
            nxt = next((r for r, d in zip(infos.itertuples(), dls) if d > now), None)
            cls, st = "", f'<span class="st">{nxt.race}R展示待ち</span>' if nxt else ""
        tiles += (f'<a class="tile {cls}" href="/{date}/{j}/">{headb}<b>{v}</b><span class="d">{infos.day.iloc[0]}日目 {ic}</span>{st}</a>')
    i = dates.index(date)
    prev = f'<a href="/{dates[i - 1]}/">◀ 前日</a>' if i > 0 else '<span class="x">◀ 前日</span>'
    nxt = f'<a href="/{dates[i + 1]}/">翌日 ▶</a>' if i + 1 < len(dates) else '<span class="x">翌日 ▶</span>'
    body = (f'<div class="dnav">{prev}<b>{jp(date)}</b>{nxt}</div>'
            + _next_races_html(date, prog_day, preds, now)
            + _recent_results_html(date, prog_day, preds, now)
            + f'<h2>開催場 <span class="sub">場を選ぶと全レース</span></h2><div class="grid">{tiles}</div>'
            + (f'<details class="help"><summary>本日の高配当（万舟以上）を見る</summary>{_payout_html(date, payouts, preds)}</details>' if payouts else "")
            + '<div class="btnrow"><a href="/today.html">今日の注目</a><a href="/record.html">的中実績</a><a href="/venue/">場の特徴</a></div>'
            + f'{ad()}{NUDGE_UPDATE}')
    return page(f"{jp(date)} 全24場の展開予想", body, "全24場のスタートスリット・1マーク展開予想を展示後に公開", path)


SHARE_JS = """<script>
async function png(id){const svg=document.getElementById(id).innerHTML;
const img=new Image();img.src=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}));await img.decode();
const c=document.createElement('canvas');c.width=1200;c.height=675;c.getContext('2d').drawImage(img,0,0);
return new Promise(r=>c.toBlob(r,'image/png'))}
async function shareX(id){const t=document.getElementById(id+'-t').value;const b=await png(id);
const f=new File([b],id+'.png',{type:'image/png'});
try{await navigator.clipboard.writeText(t)}catch(e){}
if(navigator.canShare&&navigator.canShare({files:[f]})){try{await navigator.share({files:[f],text:t});return}catch(e){if(e.name==='AbortError')return}}
const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=f.name;a.click()}
async function copyT(id,btn){await navigator.clipboard.writeText(document.getElementById(id+'-t').value);btn.textContent='コピーしました'}
</script>"""


def share_page(days, stats):
    """X投稿用の隠しページ。仕掛け成功したレースの投稿文と画像を、配当が高い順に並べる。
    URLはGitHubのSecret(SHARE_KEY)で決まり、サイトのどこからもリンクしない"""
    items = []
    for date in days:
        pp = DATA / "predictions" / f"{date}.json"
        if not pp.exists():
            continue
        preds = json.loads(pp.read_text())["races"]
        ep = DATA / "entries" / f"{date}.json"
        ents = json.loads(ep.read_text()) if ep.exists() else {}
        live = live_result.load(date)
        for key, pred in preds.items():
            jcd, race = key[:2], int(key[3:])
            result = stats.race_result(jcd, date, race)
            if live.get(key):
                result = {**live[key], **(result or {})}
            k = share.successes(pred, result)
            if k is None:
                continue
            items.append((date, jcd, race, pred, result, ents.get(key), k))
    # 1号艇の逃げは当たって当然に見えるので万舟のときだけ。外からの仕掛け成功を先に出す
    pay = lambda x: x[4].get("payout3t") or 0
    out = sorted((x for x in items if x[6] != 0), key=lambda x: (x[0], pay(x)), reverse=True)
    nige = sorted((x for x in items if x[6] == 0 and pay(x) >= 10000), key=lambda x: (x[0], pay(x)), reverse=True)
    cards = ""
    for n, (date, jcd, race, pred, result, ent, k) in enumerate(out + nige):
        if n in (0, len(out)):
            cards += "<h2>外からの仕掛け成功</h2>" if n < len(out) else "<h2>1号艇の逃げ（万舟のみ）</h2>"
        v, cid = VENUES[jcd], f"c{n}"
        text = share.post_text(v, race, pred, result, ent, k)
        cards += (f'<div class="card"><b>{jp(date)} {v} {race}R</b> '
                  f'<span class="sub">{int(result.get("payout3t") or 0):,}円</span>'
                  f'<div id="{cid}" style="margin:8px 0">{share.card_svg(v, race, jp(date), pred, result, ent, k, CFG["base_url"])}</div>'
                  f'<textarea id="{cid}-t" rows="8" style="width:100%;font-size:14px">{html.escape(text)}</textarea>'
                  f'<div style="display:flex;gap:8px;margin-top:6px">'
                  f'<button onclick="shareX(\'{cid}\')" style="flex:2;padding:12px;font-weight:700;background:#000;color:#fff;border:0;border-radius:8px">画像つきでシェア</button>'
                  f'<button onclick="copyT(\'{cid}\',this)" style="flex:1;padding:12px;border-radius:8px">文をコピー</button></div></div>')
    if not cards:
        cards = '<div class="card lock"><b>まだ仕掛け成功のレースがありません</b><br><span class="sub">結果が出ると自動でここに並びます</span></div>'
    body = (f'<h1>X投稿用</h1><p class="sub">このページは運営者専用です（どこからもリンクしていません）。'
            f'「画像つきでシェア」で画像と文をXアプリに渡します。文が入らないときは貼り付けてください（コピー済み）。</p>'
            f'{cards}{SHARE_JS}')
    return page("X投稿用", body, "", "", noindex=True)


STATIC = {
    "about.html": ("運営者情報", "<h1>運営者情報</h1><div class='card'>{about}</div>"),
    "privacy.html": ("プライバシーポリシー", "<h1>プライバシーポリシー</h1><div class='card'><p>当サイトでは第三者配信の広告サービスを利用する場合があり、"
                     "広告配信事業者はユーザーの興味に応じた広告を表示するためにCookieを使用することがあります。Cookieにより個人を特定する情報は取得しません。"
                     "ブラウザの設定でCookieを無効にできます。</p><p>アクセス解析ツールを利用する場合があります。データは匿名で収集され、個人を特定するものではありません。</p></div>"),
    "disclaimer.html": ("免責事項", "<h1>免責事項</h1><div class='card'><p>当サイトの予想は過去データから見た展開の傾向であり、着順や払戻を保証するものではありません。"
                        "当サイトの情報を利用した結果について、当サイトは責任を負いません。</p><p>舟券の購入は20歳になってから。</p>"
                        "<p>出走表・成績などの事実データはBOATRACE公式の配信データをもとにしています。節間の得点率は一般的な配点で計算した目安です。</p></div>"),
    "contact.html": ("お問い合わせ", "<h1>お問い合わせ</h1><div class='card'><p>{contact}</p></div>"),
}


def main():
    now = now_jst()
    today = f"{now:%Y%m%d}"
    lo = (now - dt.timedelta(days=DAYS_BACK)).strftime("%Y%m%d")
    progs = []
    for y in {lo[:4], today[:4], f"{now + dt.timedelta(days=1):%Y}"}:
        p = DATA / "programs" / f"{y}.parquet"
        if p.exists():
            progs.append(pd.read_parquet(p))
    prog = pd.concat(progs) if progs else pd.DataFrame(columns=["date"])
    hi = (now + dt.timedelta(days=1)).strftime("%Y%m%d")
    prog = prog[(prog.date >= lo) & (prog.date <= hi)]
    dates = sorted(prog.date.unique())
    stats = Stats(load_results(period_start(lo) if dates else today))
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    urls = ["/"]
    pick_hi, pick_lo = [], []
    for date in dates:
        pd_path = DATA / "predictions" / f"{date}.json"
        preds = json.loads(pd_path.read_text())["races"] if pd_path.exists() else {}
        bp = DATA / "bets" / f"{date}.json"
        bets = json.loads(bp.read_text()) if bp.exists() else {}
        live = live_result.load(date)   # 成績ファイルが出るまでのつなぎ(レース結果ページから取り込んだ結果)
        day = prog[prog.date == date]
        season = stats.season(date)
        payouts = _with_live_payouts(stats.big_payouts(date), date)
        for jcd, g in day.groupby("jcd"):
            infos = [dict(jcd=jcd, race=int(r), rtype=x.rtype.iloc[0], deadline=x.deadline.iloc[0], title=x.title.iloc[0],
                          day=int(x.day.iloc[0])) for r, x in g.groupby("race")]
            series, n_series = stats.series(jcd, date, infos[0]["day"])
            races = {i["race"] for i in infos}
            d = OUT / date / jcd
            d.mkdir(parents=True, exist_ok=True)
            for info in infos:
                x = g[g.race == info["race"]].sort_values("waku")
                boats = x.to_dict("records")
                pred = preds.get(f"{jcd}-{info['race']:02d}")
                base = f'{info["race"]:02d}'
                result = stats.race_result(jcd, date, info["race"])
                if live.get(f"{jcd}-{base}"):   # 成績ファイルが出るまでのつなぎ。2連単の配当はこちらにしかない
                    result = {**live[f"{jcd}-{base}"], **(result or {})}
                ready = result is not None
                (d / f"{base}.html").write_text(predict_page(date, info, pred, races, ready))
                (d / f"{base}-entry.html").write_text(entry_page(date, info, boats, season, series, n_series, pred, races, ready))
                (d / f"{base}-slit.html").write_text(redirect_page(f"/{date}/{jcd}/{base}-turn.html"))   # スリットは展開タブに入れた
                (d / f"{base}-turn.html").write_text(turn_page(date, info, pred, races, ready))
                (d / f"{base}-result.html").write_text(result_page(date, info, pred, races, result))
                (d / f"{base}-bet.html").write_text(bet_page(date, info, pred, races, result, bets.get(f"{jcd}-{base}")))
                urls += [f"/{date}/{jcd}/{base}{s}.html" for s in ("", "-entry", "-turn", "-result")]
                ent = pick_entry(date, jcd, info, pred, now)
                if ent:
                    (pick_hi if ent[0] == "hi" else pick_lo).append(ent[1])
            (d / "index.html").write_text(venue_page(date, jcd, infos, preds, now))
            urls.append(f"/{date}/{jcd}/")
        (OUT / date).mkdir(exist_ok=True)
        (OUT / date / "index.html").write_text(grid_page(date, dates, day, preds, now, f"/{date}/", payouts))
        urls.append(f"/{date}/")
    top = today if today in dates else (dates[-1] if dates else None)
    if top:
        tp = DATA / "predictions" / f"{top}.json"
        preds = json.loads(tp.read_text())["races"] if tp.exists() else {}
        (OUT / "index.html").write_text(grid_page(top, dates, prog[prog.date == top], preds, now, "/",
                                                    _with_live_payouts(stats.big_payouts(top), top)))
    else:
        (OUT / "index.html").write_text(page("準備中", "<h1>準備中です</h1>", "", "/"))
    (OUT / "venue").mkdir(exist_ok=True)
    vday = prog[prog.date == top] if top else prog.iloc[0:0]
    vpreds = json.loads((DATA / "predictions" / f"{top}.json").read_text())["races"] if top and (DATA / "predictions" / f"{top}.json").exists() else {}
    for j in SLUG:
        (OUT / "venue" / f"{SLUG[j]}.html").write_text(venue_home(j, top or today, vday, vpreds, now, stats.recent(j, top or today)))
        urls.append(f"/venue/{SLUG[j]}.html")
    (OUT / "venue" / "index.html").write_text(venue_index())
    (OUT / "record.html").write_text(record_page())
    (OUT / "today.html").write_text(today_page(top or today, vday, vpreds, now))
    urls += ["/venue/", "/record.html", "/today.html"]
    (OUT / "bets-data.json").write_text(json.dumps(bets_records(), ensure_ascii=False, separators=(",", ":")))
    (OUT / "bets-upcoming.json").write_text(json.dumps(bets_upcoming(), ensure_ascii=False, separators=(",", ":")))
    (OUT / "nige-data.json").write_text(json.dumps(nige_records(), ensure_ascii=False, separators=(",", ":")))
    # 自分用(試験用買い目)のページは予想組織図にまとめた。サイトマップには入れない
    (OUT / "ops.html").write_text(org_home())
    (OUT / "org").mkdir(exist_ok=True)
    (OUT / "org" / "kessai.html").write_text(kessai_room())
    (OUT / "org" / "kessai-c.html").write_text(kessai_c_room())
    (OUT / "org" / "kessai-b.html").write_text(kessai_b_room())
    (OUT / "org" / "monitor.html").write_text(monitor_room())
    (OUT / "img").mkdir(exist_ok=True)
    for f in ("monitor.jpg", "monitor_face.jpg"):
        if (ROOT / "assets" / f).exists():
            shutil.copy(ROOT / "assets" / f, OUT / "img" / f)
    for x in ORG_INFO:
        (OUT / "org" / f'{x["id"]}.html').write_text(info_room(x, pick_hi, pick_lo))
    (OUT / "org" / "n").mkdir(exist_ok=True)
    nodes = _tree_nodes()
    for nd in nodes:
        (OUT / "org" / "n" / f"{nd}.html").write_text(node_room(nd, nodes))
    (OUT / "org" / "archive.html").write_text(archive_room())
    for old, to in (("bets.html", "/ops.html"), ("nige.html", "/org/nige.html"), ("pick.html", "/org/nige.html")):
        (OUT / old).write_text(redirect_page(to))   # 前のURLをブックマークしていても迷わないように
    (OUT / "ops").mkdir(exist_ok=True)
    for pk, logic_html in (("pick2", _pick2_logic_card()), ("pick2tan", _pick2tan_logic_card()), ("pickin", _escape_logic_card()),
                            ("pickbin", _pickbin_logic_card()), ("pick6a", _pick6a_logic_card()),
                            ("pick21", _pick21_logic_card()), ("pick21t", _pick21t_logic_card()),
                            ("pickbinx", _pickbinx_logic_card()), ("pickbinc", _pickbinc_logic_card()),
                            ("pickbint", _pickbint_logic_card()), ("pickura", _pickura_logic_card()),
                            ("pickgen", _pickgen_logic_card()), ("pickfav", _pickfav_logic_card()), ("pickoutfav", _pickoutfav_logic_card()), ("sankabin", _sanka_logic_card("sankabin")), ("sankagap", _sanka_logic_card("sankagap"))):
        (OUT / "ops" / f"{pk}.html").write_text(ops_detail_page(pk, logic_html))
    key = os.environ.get("SHARE_KEY")
    if key:   # 投稿用の隠しページ(今日と前日の仕掛け成功)。サイトマップには入れない
        (OUT / key).mkdir()
        (OUT / key / "index.html").write_text(share_page([today, f"{now - dt.timedelta(days=1):%Y%m%d}"], stats))
    for name, (title, body) in STATIC.items():
        (OUT / name).write_text(page(title, body.format(about=CFG.get("about", ""), contact=CFG.get("contact", "")), title, "/" + name))
        urls.append("/" + name)
    (OUT / "404.html").write_text(page("ページが見つかりません",
        '<h1>ページが見つかりません</h1><div class="card"><p>レースのページは、その日のうちだけ公開しています。'
        '終わったレースの結果や今日の予想は、こちらからどうぞ。</p></div>'
        '<div class="btnrow"><a href="/">今日のレース</a><a href="/today.html">今日の注目</a></div>'
        '<div class="btnrow"><a href="/venue/">場ごとの特徴</a><a href="/record.html">的中実績</a></div>', "", "/404.html", noindex=True))
    # サイトマップには、ずっと残るページだけを入れる(日付のページは翌日には消えるため)
    urls = [u for u in urls if not u[1:2].isdigit()]
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                     + "".join(f"<url><loc>{CFG['base_url']}{u}</loc></url>" for u in urls) + "</urlset>")
    for name in CFG.get("gsc_files", []):   # Search Console の所有権の確認ファイル(消さない)
        (OUT / name).write_text(f"google-site-verification: {name}")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {CFG['base_url']}/sitemap.xml\n")
    if CFG.get("ads_txt"):
        (OUT / "ads.txt").write_text(CFG["ads_txt"] + "\n")
    print(f"{len(urls)}ページ生成")


if __name__ == "__main__":
    main()
