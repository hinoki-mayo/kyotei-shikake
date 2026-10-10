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
import os
import shutil

import pandas as pd

import bet as bet_mod
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
.tabs{display:flex;border-bottom:2px solid var(--bd);margin:8px 0}.tabs a{flex:1 1 auto;min-width:0;text-align:center;padding:10px 0;font-size:12.5px;font-weight:700;color:var(--sub);white-space:nowrap}
.tabs a.on{color:var(--tx);border-bottom:3px solid var(--hot);margin-bottom:-2px}.tabs a .lk{font-size:10px;font-weight:500;white-space:normal;display:block;line-height:1.3}
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


def page(title, body, desc="", path="", noindex=False):
    robots = '<meta name="robots" content="noindex">' if noindex else ""
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">{robots}
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
    lk = '<span class="lk">展示後に公開</span>' if locked else ""
    rlk = "" if result_ready else '<span class="lk">結果発表後に公開</span>'
    items = [("出走表", f"{base}.html", "info", ""), ("スタートスリット", f"{base}-slit.html", "slit", lk),
             ("1マーク", f"{base}-turn.html", "turn", lk), ("結果", f"{base}-result.html", "result", rlk),
             ("試験買い目", f"{base}-bet.html", "bet", "")]
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


def _narrative(pred):
    """各艇のコメント(scene.pyのlines)を、主役→2番手→残りの順でひとつの文章につなげる。
    新しい展開判定は増やさず、既にある材料を読みやすくまとめるだけ。"""
    sc, boats = pred["scene"], pred["boats"]
    lines = sc["lines"]
    order = [sc["shu"], sc["sub"]] + [k for k in range(6) if k not in (sc["shu"], sc["sub"])]
    parts = []
    for k in order:
        txt = lines.get(str(k))
        if not txt:
            continue
        parts.append(f'{boats[k]["waku"]}号艇は{txt}')
    if not parts:
        return ""
    return f'<h2>展開まとめ</h2><div class="card"><p class="sub" style="color:var(--tx)">{"。".join(parts)}。</p></div>'


def _scenarios_html(pred):
    """展開シナリオ集: 起こりうる勝ち方ごとの図・文章・買い目の形と、全艇の勝ち方"""
    sc = pred.get("scenarios")
    if not sc or not sc.get("list"):
        return ""
    waku = [b["waku"] for b in pred["boats"]]
    cards = ""
    for i, s in enumerate(sc["list"], 1):
        scene = dict(s["scene"], roles={int(k): v for k, v in s["scene"]["roles"].items()})
        try:
            svg = turn_svg(scene, waku)
        except Exception:
            svg = ""   # ボートが重なって描けない配置のときは図なしで出す
        cards += (f'<div class="card"><b>シナリオ{i}　{waku[s["w"]]}の{s["m"]}</b> '
                  f'<span class="sub">（起こる確率 {s["prob"]:.0%}）</span>{svg}'
                  f'<p style="margin:6px 0">{html.escape("。".join(s["lines"]))}。</p>'
                  f'<p class="sub" style="margin:0">買い目の形 <b style="color:var(--tx);font-size:16px">{s["combo"]}</b></p></div>')
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
        content = (f'<div class="card">{labels(pred)}</div>{turn_svg(sc2, waku)}<h2>各艇の展開</h2><div class="card">{lines}</div>'
                   + _trifecta_card(pred) + _narrative(pred) + _scenarios_html(pred))
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
    kind = plan.get("bet", "3t")
    combo, pay = result.get(f"combo{kind}"), result.get(f"payout{kind}")
    if not combo or pay is None or pd.isna(pay):
        return None
    ret = sum(t["units"] * int(pay) for t in plan["tickets"] if t["combo"] == combo)
    return plan["stake"], ret


TRIAL_NOTE = ('<div class="card" style="border:2px dashed var(--hot)"><b style="color:var(--hot)">試験運用中</b>'
              '<br><span class="sub" style="color:var(--tx)">買い目モデルを検証するために、試験的に公開しています。'
              '成績はまだ検証中で、回収を保証するものではありません。参考程度にご覧ください。</span></div>')
SKIP_TEXT = {"balance": "的中確率30%以上で期待回収率100%を超える組み合わせがありませんでした",
             "in_hit": "1コース頭で期待回収率80%以上の組み合わせがありませんでした",
             "in_ev": "1コース頭で的中確率15%以上の組み合わせがありませんでした",
             "out_hit": "1コース以外の頭で期待回収率70%以上の組み合わせがありませんでした",
             "out_ana": f"1コース以外が頭で{bet_mod.ANA_ODDS}倍以上の目がありませんでした",
             "e2_top1": "展示の進入が枠なりでなく、頭注目が1以外のレースだけ買います",
             "pick2": f"1コース1着確率{bet_mod.PICK2_NIGE_MAX:.0%}未満の厳選レースのみ対象。対象でも本命・次点とも"
                      f"オッズ{bet_mod.PICK2_MIN_ODDS}〜{bet_mod.PICK2_MAX_ODDS}倍の目がなければ見送り"}


def _plan_card(name, pl, result):
    title = f'<h2>{bet_mod.PLANS[name]}</h2>'
    if pl.get("skip"):
        return title + f'<div class="card"><b>見送り</b><br><span class="sub">{SKIP_TEXT[name]}</span></div>'
    if pl.get("bet") == "2t":
        form = f'<div class="tri-main"><span class="sub" style="font-size:14px">2連単</span><span class="tri-chip">{html.escape(pl["tickets"][0]["combo"])}</span></div>'
    elif pl.get("himo"):
        himo = "".join(str(x) for x in pl["himo"])
        form = (f'<div class="tri-main"><span class="tri-chip">{pl["head"]}</span><span class="tri-ar">→</span>'
                f'<span class="tri-chip">{himo}</span><span class="tri-ar">→</span><span class="tri-chip">{himo}</span></div>')
    else:
        form = f'<div class="tri-main" style="font-size:20px">{len(pl["tickets"])}点</div>'
    evt = f'・期待回収率 {pl["ev"]:.0%}' if pl.get("ev") is not None else ""
    head = (f'<div class="card trifecta">{form}<p class="sub">投資 {pl["stake"]:,}円・的中確率 {pl["hit"]:.0%}{evt}</p></div>')
    scen = f'<p style="margin:6px 2px">{html.escape(pl["scenario"])}</p>' if pl.get("scenario") else ""
    rows = "".join(
        f'<div class="boat"><div style="flex:1"><b>{t["combo"]}</b>' + (f' <span class="sub">({t["role"]})</span>' if t.get("role") else "")
        + f' <span class="sub">× {t["units"]}口（{t["units"] * 100:,}円）</span><br>'
        f'<span class="sub">' + (f'オッズ {t["odds"]:.1f}・確率 {t["prob"]:.1%}・期待値 {t["prob"] * t["odds"]:.2f}' if t.get("odds") else f'確率 {t["prob"]:.1%}') + '</span></div></div>'
        for t in pl["tickets"])
    out = title + head + scen + f'<details class="card"><summary class="sub">買い目 {len(pl["tickets"])}点を見る</summary>{rows}</details>'
    st = settle(pl, result)
    if st:
        stake, ret = st
        col = "var(--green)" if ret >= stake else "var(--red)"
        out += (f'<div class="card"><span style="color:{col};font-weight:700">{"的中" if ret else "不的中"}　'
                f'払戻 {ret:,}円 / 投資 {stake:,}円（{ret - stake:+,}円）</span></div>')
    return out


def bet_page(date, info, pred, races, result, bet):
    v = VENUES[info["jcd"]]
    base = f'{info["race"]:02d}'
    if bet is None:
        content = ('<div class="card lock"><b>買い目はまだ決まっていません</b><br>'
                   '<span class="sub">締切の約2〜9分前にオッズを見て、1レース1回だけ決めます</span></div>')
    else:
        content = f'<p class="sub">{bet.get("odds_at", "")}時点のオッズで決めた買い目です（買い方ごとに1,000〜2,000円）</p>'
        if result and result.get("combo3t"):
            pay = "" if pd.isna(result.get("payout3t")) else f'（{int(result["payout3t"]):,}円）'
            e2 = (f'<br><span class="sub">2連単 {html.escape(result["combo2t"])}（{int(result["payout2t"]):,}円）</span>'
                  if result.get("combo2t") and result.get("payout2t") else "")
            content += f'<div class="card"><b>結果 {html.escape(result["combo3t"])}</b>{pay}{e2}</div>'
        content += "".join(_plan_card(n, pl, result) for n, pl in plans_of(bet).items())
    content = TRIAL_NOTE + content
    content += ('<p class="sub">展開予想とは別に、モデルの確率とオッズから読んだ市場の確率を混ぜて機械的に組んでいます。'
                'オッズは締切までに動くため、表示の期待回収率は目安です。<a href="/bets.html" style="color:var(--ac)">通算の収支</a></p>')
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
        for key, b in json.loads(f.read_text()).items():
            jcd, race = key.split("-")
            result = {**live.get(key, {}), **(keyed.get((date, jcd, int(race))) or {})}   # 2連単は結果ページの記録から
            if not result.get("combo3t") or pd.isna(result.get("payout3t")):
                continue
            plans = plans_of(b)
            st = {}
            for n, pl in plans.items():
                st[n] = 0 if pl.get("skip") else list(settle(pl, result))
            pred = preds.get(key)
            rec = dict(d=date, v=jcd, r=int(race), res=result["combo3t"], pay=int(result["payout3t"]), s=st)
            if pred and pred.get("scene"):
                h1 = pred["scene"]["head"][0] == 0
                rec.update(h1=h1, mae=any(bb["waku"] != bb["course"] for bb in pred["boats"]),
                           g1=pred["boats"][0]["grade"])
                pick = plans.get("in_hit" if h1 else "out_hit")
                st["switch"] = 0 if (not pick or pick.get("skip")) else list(settle(pick, result))
                fl = _flow(pred, result)
                if fl:
                    st["flow"] = list(fl)
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


def bets_summary_page():
    """試験用買い目の集計画面(期間・条件・集計単位・買い方で絞り込み)。データは bets-data.json"""
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
    body = ('<h1>試験用買い目の収支</h1>' + own_tabs("bets") + TRIAL_NOTE + controls + '<div id="out"><p class="sub">読み込み中…</p></div>'
            '<p class="sub">結果が出たレースだけを集計しています。「切り替え」「頭-連-流し」は、保存してある予想と結果から計算した仮想の成績です。'
            '「頭-連-流し」は全レースで買った場合なので、条件で「頭注目≠1」などに絞って見てください。</p>'
            f'<script>{js}</script>')
    return page("試験用買い目の収支", body, "", "/bets.html", noindex=True)


def own_tabs(cur):
    """自分用ページ(収支・逃げ判定・狙い目・運用)の切り替えタブ"""
    items = [("bets", "/bets.html", "収支"), ("nige", "/nige.html", "逃げ判定"), ("pick", "/pick.html", "狙い目"),
             ("ops", "/ops.html", "運用")]
    return '<nav class="tabs">' + "".join(
        f'<a href="{u}"{" class=on" if k == cur else ""}>{t}</a>' for k, u, t in items) + '</nav>'


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


def nige_page():
    """逃げ判定(インが逃げたか・飛んだときに頭を当てたか)の集計画面。データは nige-data.json"""
    opt = lambda pairs: "".join(f'<option value="{v}">{t}</option>' for v, t in pairs)
    sel = 'style="font-size:15px;padding:6px;border-radius:8px;border:1px solid var(--bd);background:var(--card);color:var(--tx);width:100%"'
    controls = (
        '<div class="card" style="display:grid;grid-template-columns:1fr 1fr;gap:8px">'
        f'<label class="sub">期間<select id="per" {sel}>{opt([("today", "今日"), ("d7", "直近7日"), ("d30", "直近30日"), ("all", "全期間")])}</select></label>'
        f'<label class="sub">集計<select id="grp" {sel}>{opt([("sum", "合計"), ("day", "日別"), ("venue", "場別")])}</select></label>'
        '</div><p class="sub" id="n"></p>')
    js = NIGE_JS.replace("__VENUES__", json.dumps(VENUES, ensure_ascii=False)).replace("__REF__", json.dumps(NIGE_REF, ensure_ascii=False))
    body = ('<h1>逃げ判定</h1>' + own_tabs("nige") + controls + '<div id="out"><p class="sub">読み込み中…</p></div>'
            '<p class="sub">結果が出たレースだけを集計しています。コースは展示の進入で見ています。「過去の目安」は、2025年1月〜2026年9月の約9.2万レースに'
            'モデルをあてて出した数字です。「2〜6コースの確率順」は、1コースを除いたモデルの1着確率の高い順です。</p>'
            f'<script>{js}</script>')
    return page("逃げ判定", body, "", "/nige.html", noindex=True)


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


def pick_page(hi_list, lo_list):
    """狙い目(今日・明日の厳選レース一覧+この基準自体の過去集計)。一覧は静的、集計はnige-data.jsonを流用"""
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
    body = ('<h1>狙い目</h1>' + own_tabs("pick")
            + '<p class="sub">今日・明日の確定済み予想(展示反映後)から、1コースの1着確率が極端に高い/低いレースだけを抜き出しています。'
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
            + f'<script>{js}</script>')
    return page("狙い目", body, "", "/pick.html", noindex=True)


OPS_JS = r"""
const VN=__VENUES__, PLAN='pick2';
let D=[];
const $=id=>document.getElementById(id), yen=n=>n.toLocaleString();
function filt(){
  const per=$('per4').value, ds=[...new Set(D.map(x=>x.d))].sort();
  const keep=per==='all'?null:new Set(ds.slice(-({d30:30,d90:90})[per]));
  return D.filter(x=>x.s[PLAN]!==undefined && (!keep||keep.has(x.d)));
}
function render(){
  const rows=filt(), used=rows.filter(x=>x.s[PLAN]!==0);
  $('n4').textContent = `対象 ${rows.length}R中・購入 ${used.length}R・見送り ${rows.length-used.length}R`;
  if(!used.length){ $('out4').innerHTML='<div class="card"><p class="sub">まだ購入したレースがありません。</p></div>'; return; }
  const st=used.reduce((a,x)=>a+x.s[PLAN][0],0), ret=used.reduce((a,x)=>a+x.s[PLAN][1],0);
  const roi=st?ret/st:0, hitN=used.filter(x=>x.s[PLAN][1]>0).length;
  let s = `<div class="card"><b>通算</b> <b style="color:${roi>=1?'var(--green)':'var(--red)'};font-size:22px">${Math.round(roi*100)}%</b>`+
    `<br><span class="sub">投資 ${yen(st)}円 → 払戻 ${yen(ret)}円（${ret-st>=0?'+':''}${yen(ret-st)}円）・的中 ${hitN}/${used.length}R（${Math.round(hitN/used.length*100)}%）</span></div>`;
  const byDay={};
  for(const x of used)(byDay[x.d]=byDay[x.d]||[]).push(x);
  const days=Object.keys(byDay).sort();
  const bars = days.map(d=>{
    const g=byDay[d], gst=g.reduce((a,x)=>a+x.s[PLAN][0],0), gret=g.reduce((a,x)=>a+x.s[PLAN][1],0);
    const r=gst?gret/gst:0, h=Math.max(2,Math.min(120,r*60)), col=r>=1?'var(--green)':'var(--red)';
    return `<div style="display:flex;flex-direction:column;align-items:center;gap:3px;flex:1;min-width:22px">`+
      `<span class="sub" style="font-size:10px;white-space:nowrap">${Math.round(r*100)}%</span>`+
      `<div style="width:16px;height:${h}px;background:${col};border-radius:2px"></div>`+
      `<span class="sub" style="font-size:9px">${+d.slice(4,6)}/${+d.slice(6)}</span></div>`;
  }).join('');
  s += `<div class="card"><b>日別回収率</b><div style="position:relative;display:flex;align-items:flex-end;gap:4px;height:160px;margin-top:10px;overflow-x:auto;padding-bottom:2px;border-bottom:1px solid var(--bd)">${bars}</div></div>`;
  const oofune = used.filter(x=>x.s[PLAN][1]>0 && x.pay>=10000).sort((a,b)=>b.pay-a.pay);
  if(oofune.length){
    s += `<div class="card"><b>万舟的中</b>` + oofune.map(x=>
      `<div class="boat"><div style="flex:1"><b>${VN[x.v]} ${x.r}R</b> <span class="sub">${+x.d.slice(4,6)}/${+x.d.slice(6)}・${x.res}</span></div>`+
      `<b style="color:var(--green)">${yen(x.pay)}円</b></div>`).join('') + `</div>`;
  }
  const list = used.slice().sort((a,b)=> b.d.localeCompare(a.d) || b.r-a.r);
  s += `<div class="card"><b>レース一覧</b>` + list.map(x=>{
    const [xst,xret]=x.s[PLAN], hit=xret>0;
    return `<div class="boat"><div style="flex:1"><b>${VN[x.v]} ${x.r}R</b> <span class="sub">${+x.d.slice(4,6)}/${+x.d.slice(6)}・結果 ${x.res}・投資${yen(xst)}円</span></div>`+
      `<b style="color:${hit?'var(--green)':'var(--red)'}">${hit?'的中':'外れ'} ${xret-xst>=0?'+':''}${yen(xret-xst)}円</b></div>`;
  }).join('') + `</div>`;
  $('out4').innerHTML = s;
}
fetch('/bets-data.json').then(r=>r.json()).then(j=>{D=j;render()});
document.addEventListener('change',e=>{if(e.target.id==='per4')render()});
"""


def ops_page():
    """運用ボード(pick2プランの実績専用)。データはbets-data.jsonを流用"""
    opt = lambda pairs: "".join(f'<option value="{v}">{t}</option>' for v, t in pairs)
    sel = 'style="font-size:15px;padding:6px;border-radius:8px;border:1px solid var(--bd);background:var(--card);color:var(--tx);width:100%"'
    js = OPS_JS.replace("__VENUES__", json.dumps(VENUES, ensure_ascii=False))
    body = ('<h1>運用</h1>' + own_tabs("ops")
            + '<p class="sub">「厳選頭2頭」(pick2)プランの実績だけを見る画面です。'
              '日別の回収率・投資額/払戻額・レースごとの的中/外れ・万舟的中を確認できます。</p>'
            + '<div class="card" style="display:grid;grid-template-columns:1fr;gap:8px">'
            + f'<label class="sub">期間<select id="per4" {sel}>{opt([("d30", "直近30日"), ("d90", "直近90日"), ("all", "全期間")])}</select></label>'
            + '</div><p class="sub" id="n4"></p><div id="out4"><p class="sub">読み込み中…</p></div>'
            + f'<script>{js}</script>')
    return page("運用", body, "", "/ops.html", noindex=True)


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


def _with_live_payouts(payouts, date, thr=10000):
    """成績ファイルがまだのレースの万舟を、レース結果ページから取り込んだ結果で補う"""
    have = {(p["jcd"], int(p["race"])) for p in payouts}
    for k, v in live_result.load(date).items():
        jcd, race = k[:2], int(k[3:])
        if (jcd, race) not in have and v.get("payout3t") and v["payout3t"] >= thr:
            payouts.append(dict(jcd=jcd, race=race, combo3t=v["combo3t"], payout3t=v["payout3t"]))
    return sorted(payouts, key=lambda p: -p["payout3t"])


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
                (d / f"{base}.html").write_text(info_page(date, info, boats, season, series, n_series, pred, races, ready))
                (d / f"{base}-slit.html").write_text(slit_page(date, info, pred, races, ready))
                (d / f"{base}-turn.html").write_text(turn_page(date, info, pred, races, ready))
                (d / f"{base}-result.html").write_text(result_page(date, info, pred, races, result))
                (d / f"{base}-bet.html").write_text(bet_page(date, info, pred, races, result, bets.get(f"{jcd}-{base}")))
                urls += [f"/{date}/{jcd}/{base}{s}.html" for s in ("", "-slit", "-turn", "-result")]
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
    (OUT / "bets.html").write_text(bets_summary_page())   # 自分用なのでサイトマップには入れない
    (OUT / "bets-data.json").write_text(json.dumps(bets_records(), ensure_ascii=False, separators=(",", ":")))
    (OUT / "nige.html").write_text(nige_page())
    (OUT / "nige-data.json").write_text(json.dumps(nige_records(), ensure_ascii=False, separators=(",", ":")))
    (OUT / "pick.html").write_text(pick_page(pick_hi, pick_lo))
    (OUT / "ops.html").write_text(ops_page())
    key = os.environ.get("SHARE_KEY")
    if key:   # 投稿用の隠しページ(今日と前日の仕掛け成功)。サイトマップには入れない
        (OUT / key).mkdir()
        (OUT / key / "index.html").write_text(share_page([today, f"{now - dt.timedelta(days=1):%Y%m%d}"], stats))
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
