"""予想データからサイト(静的HTML)を作る。出力先は site/

構成
・トップ / 日付ページ : 24場のマス目。展開予想が出た場は色付き「展開予想！」
・場ページ           : 1R〜12Rの一覧。展開予想が出たレースを強調
・レースページ       : 出走表 ／ スタートスリット ／ 1マーク の3タブ(それぞれ別ページ)
広告は ads/ フォルダのタグを決まった位置に差し込む(図の上や途中には置かない)
"""
import datetime as dt
import html
import json
import shutil

import pandas as pd

from common import DATA, ROOT, now_jst
from draw import slit_svg, turn_svg
from parse import VENUES

CFG = json.loads((ROOT / "site_config.json").read_text())
for _key, _file in (("ad_head", "head.html"), ("ad_slot", "slot.html"), ("ads_txt", "ads.txt")):
    _p = ROOT / "ads" / _file
    if _p.exists() and _p.read_text().strip():
        CFG[_key] = _p.read_text().strip()

OUT = ROOT / "site"
BC = ["#FFFFFF", "#222222", "#D9453F", "#3A7FD5", "#E8A83A", "#4E9A3E"]
TC = ["#222", "#fff", "#fff", "#fff", "#222", "#fff"]
WD = "月火水木金土日"
PTS = {"01": 10, "02": 8, "03": 6, "04": 4, "05": 2, "06": 1}
DAYS_BACK = 0

CSS = """
:root{--bg:#f4f5f7;--card:#fff;--tx:#1f2328;--sub:#6b7079;--bd:#e3e5e9;--navy:#1B2A4A;--ac:#185FA5;--hot:#E8742E;--red:#A32D2D;--green:#0F6E56;--off:#eceef1}
@media (prefers-color-scheme:dark){:root{--bg:#131518;--card:#1d2025;--tx:#e9eaec;--sub:#9aa0a8;--bd:#2d3138;--ac:#85B7EB;--off:#1a1c20}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font-family:'Hiragino Sans','Noto Sans JP',sans-serif;line-height:1.6}
a{color:inherit;text-decoration:none}header{background:var(--navy);color:#fff;padding:12px 16px;font-weight:700}
main{max-width:760px;margin:0 auto;padding:10px}h1{font-size:19px;margin:10px 0}h2{font-size:16px;margin:18px 0 8px}
.sub{color:var(--sub);font-size:13px}.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:10px 12px;margin:10px 0}
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
.tabs{display:flex;border-bottom:2px solid var(--bd);margin:8px 0}.tabs a{flex:1;text-align:center;padding:10px 0;font-size:12.5px;font-weight:700;color:var(--sub);white-space:nowrap}
.tabs a.on{color:var(--tx);border-bottom:3px solid var(--hot);margin-bottom:-2px}.tabs a .lk{font-size:11px;font-weight:500}
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
footer{max-width:760px;margin:24px auto;padding:12px;font-size:12px;color:var(--sub)}footer a{color:var(--ac)}svg{display:block;color:var(--tx)}
"""


def page(title, body, desc="", path=""):
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}｜{CFG['site_name']}</title><meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{CFG['base_url']}{path}"><meta property="og:title" content="{html.escape(title)}">
<meta property="og:site_name" content="{CFG['site_name']}"><style>{CSS}</style>{CFG.get('ad_head', '')}</head><body>
<header><a href="/">{CFG['site_name']}</a></header><main>{body}</main>
<footer>{CFG['site_name']}は、展示の進入をもとにデータから見た1マークの展開の傾向を掲載しています。着順を保証するものではありません。舟券の購入は20歳から。<br>
<a href="/about.html">運営者情報</a>・<a href="/privacy.html">プライバシーポリシー</a>・<a href="/disclaimer.html">免責事項</a>・<a href="/contact.html">お問い合わせ</a></footer>
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

    def race_result(self, jcd, date, race):
        r = self.res[(self.res.jcd == jcd) & (self.res.date == date) & (self.res.race == race)]
        if len(r) != 6:
            return None
        return dict(by_waku=dict(zip(r.waku.astype(int), r["rank"])), kimarite=r.kimarite.iloc[0])

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
    lk = '<br><span class="lk">展示後に公開</span>' if locked else ""
    rlk = "" if result_ready else '<br><span class="lk">結果発表後に公開</span>'
    items = [("出走表", f"{base}.html", "info", ""), ("スタートスリット", f"{base}-slit.html", "slit", lk),
             ("1マーク", f"{base}-turn.html", "turn", lk), ("結果", f"{base}-result.html", "result", rlk)]
    return '<nav class="tabs">' + "".join(
        f'<a class="{"on" if k == cur else ""}" href="{u}">{t}{x}</a>' for t, u, k, x in items) + "</nav>"


def race_head(date, v, info, cur, locked, base, result_ready=False):
    return (f'<p class="sub"><a href="/{date}/">{jp(date)}</a> ＞ <a href="/{date}/{info["jcd"]}/">{v}</a></p>'
            f'<h1>{v} {info["race"]}R <span class="sub">{html.escape(info["rtype"])}</span></h1>'
            f'<p class="sub">締切 {info["deadline"]}・{html.escape(info["title"])} {info["day"]}日目</p>'
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


def info_page(date, info, boats, season, series, n_series, pred, races, result_ready=False):
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
    entry = ("展示の進入：" + " ".join(str(w) for w in order)) if order else "展示の進入が出たら、スタートスリットと1マークの展開予想を公開します（締切の約20分前）。"
    body = (race_head(date, v, info, "info", locked, base, result_ready) + (f'<div class="card">{labels(pred)}</div>' if not locked else "")
            + f'<div class="card">{rows}</div><p class="sub">{entry}</p>' + (NUDGE if not order else "")
            + ad() + rnav(date, info["jcd"], info["race"], races, ""))
    return page(f"{v}{info['race']}R 出走表・展開予想 {jp(date)}", body,
                f"{v}{info['race']}Rの出走表と1マーク展開予想。今期勝率・節間成績つき。", f"/{date}/{info['jcd']}/{base}.html")


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
        content = (f'<div class="card">{labels(pred)}</div>{turn_svg(sc2, waku)}<h2>各艇の展開</h2><div class="card">{lines}</div>'
                   + _trifecta_card(pred))
    body = race_head(date, v, info, "turn", locked, base, result_ready) + content + ad() + rnav(date, info["jcd"], info["race"], races, "-turn")
    return page(f"{v}{info['race']}R 1マーク展開予想 {jp(date)}", body, f"{v}{info['race']}Rの1マーク仕掛け・展開予想",
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


def venue_page(date, jcd, infos, preds, now):
    v = VENUES[jcd]
    items = ""
    cur_marked = False
    for i, info in enumerate(infos):
        pred = preds.get(f"{jcd}-{info['race']:02d}")
        st = race_status(date, info, pred, now)
        badge = {"hot": '<span class="rst s-hot">展開予想！</span>', "wait": '<span class="rst s-wait">展示待ち</span>',
                 "done": '<span class="rst s-done">締切</span>'}[st]
        cur_id = ""
        if not cur_marked and st in ("hot", "wait"):
            cur_id = ' id="cur"'
            cur_marked = True
        items += (f'<a{cur_id} href="/{date}/{jcd}/{info["race"]:02d}.html"><span class="rno">{info["race"]}R</span>'
                  f'<span><span class="sub">{info["deadline"]}</span> {html.escape(info["rtype"])}</span>{badge}</a>')
        if i == 5:
            items += f"</div>{ad()}<div class='card list'>"
    head = f'<h1>{v} {jp(date)}</h1><p class="sub">{html.escape(infos[0]["title"])}・{infos[0]["day"]}日目</p>'
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
            cls, st = "hot", '<span class="hotb">展開予想！</span>'
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
    hl = "".join(f'<a href="/{date}/{j}/{r:02d}-turn.html"><span class="rno" style="width:80px">{VENUES[j]} {r}R</span>'
                 f'<span class="sub">締切 {d}</span><span class="rst s-hot">展開予想！</span></a>'
                 for d, j, r in sorted(hot_list))
    hot_html = f"<h2>いま展開予想が出ているレース</h2><div class='card list'>{hl}</div>" if hl else ""
    body = (f'<div class="dnav">{prev}<b>{jp(date)}</b>{nxt}</div><div class="grid">{tiles}</div>'
            f'<p class="sub">展示の進入が出たレースから順に、スタートスリットと1マークの展開予想を公開します。</p>{hot_html}'
            f'{_payout_html(date, payouts, preds)}{ad()}{NUDGE_UPDATE}')
    return page(f"{jp(date)} 全24場の展開予想", body, "全24場のスタートスリット・1マーク展開予想を展示後に公開", path)


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
    for date in dates:
        pd_path = DATA / "predictions" / f"{date}.json"
        preds = json.loads(pd_path.read_text())["races"] if pd_path.exists() else {}
        day = prog[prog.date == date]
        season = stats.season(date)
        payouts = stats.big_payouts(date)
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
                ready = result is not None
                (d / f"{base}.html").write_text(info_page(date, info, boats, season, series, n_series, pred, races, ready))
                (d / f"{base}-slit.html").write_text(slit_page(date, info, pred, races, ready))
                (d / f"{base}-turn.html").write_text(turn_page(date, info, pred, races, ready))
                (d / f"{base}-result.html").write_text(result_page(date, info, pred, races, result))
                urls += [f"/{date}/{jcd}/{base}{s}.html" for s in ("", "-slit", "-turn", "-result")]
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
                                                    stats.big_payouts(top)))
    else:
        (OUT / "index.html").write_text(page("準備中", "<h1>準備中です</h1>", "", "/"))
    for name, (title, body) in STATIC.items():
        (OUT / name).write_text(page(title, body.format(about=CFG.get("about", ""), contact=CFG.get("contact", "")), title, "/" + name))
        urls.append("/" + name)
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                     + "".join(f"<url><loc>{CFG['base_url']}{u}</loc></url>" for u in urls) + "</urlset>")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {CFG['base_url']}/sitemap.xml\n")
    if CFG.get("ads_txt"):
        (OUT / "ads.txt").write_text(CFG["ads_txt"] + "\n")
    print(f"{len(urls)}ページ生成")


if __name__ == "__main__":
    main()
