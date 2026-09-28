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
.tile{background:var(--card);min-height:92px;padding:6px 4px;text-align:center;display:flex;flex-direction:column;justify-content:center}
.tile b{font-size:16px}.tile .d{font-size:12px;color:var(--sub)}.tile .st{font-size:12px;font-weight:700;color:var(--sub)}
.tile.none{background:var(--off);color:var(--sub);opacity:.55}.tile.none b{font-weight:500}
.tile.hot{background:var(--hot);color:#fff}.tile.hot .d,.tile.hot .st{color:#fff}
.tile.done{opacity:.6}.tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:4px;margin:1px;color:#fff;background:#6b7a90}
.hotb{display:inline-block;background:#fff;color:var(--hot);font-size:11px;font-weight:700;border-radius:10px;padding:0 8px;margin-top:2px}
.list a{display:flex;gap:10px;align-items:center;padding:10px 4px;border-bottom:1px solid var(--bd)}.list a:last-child{border:0}
.rno{width:46px;font-weight:700;font-size:16px}.rst{margin-left:auto;font-size:12px;font-weight:700;border-radius:12px;padding:2px 10px;white-space:nowrap}
.s-hot{background:var(--hot);color:#fff}.s-wait{background:var(--off);color:var(--sub)}.s-done{color:var(--sub)}
.tabs{display:flex;border-bottom:2px solid var(--bd);margin:8px 0}.tabs a{flex:1;text-align:center;padding:10px 0;font-size:14px;font-weight:700;color:var(--sub)}
.tabs a.on{color:var(--tx);border-bottom:3px solid var(--hot);margin-bottom:-2px}.tabs a .lk{font-size:11px;font-weight:500}
.boat{display:flex;gap:10px;padding:10px 0;border-bottom:1px solid var(--bd)}.boat:last-child{border:0}
.chip{width:30px;height:30px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-weight:700;flex:none;border:1px solid var(--bd)}
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
def load_results(since):
    fr = []
    for y in range(int(since[:4]), now_jst().year + 1):
        p = DATA / "results" / f"{y}.parquet"
        if p.exists():
            fr.append(pd.read_parquet(p, columns=["date", "jcd", "race", "rank", "toban"]))
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


# ---------- ページ ----------
def race_status(date, r, pred, now):
    if now >= dl_dt(date, r["deadline"]):
        return "done"
    if pred and pred.get("version") == "final":
        return "hot"
    return "wait"


def tabs(base, cur, locked):
    lk = '<br><span class="lk">展示後に公開</span>' if locked else ""
    items = [("出走表", f"{base}.html", "info"), ("スタートスリット", f"{base}-slit.html", "slit"), ("1マーク", f"{base}-turn.html", "turn")]
    return '<nav class="tabs">' + "".join(
        f'<a class="{"on" if k == cur else ""}" href="{u}">{t}{lk if k != "info" else ""}</a>' for t, u, k in items) + "</nav>"


def race_head(date, v, info, cur, locked, base):
    return (f'<p class="sub"><a href="/{date}/">{jp(date)}</a> ＞ <a href="/{date}/{info["jcd"]}/">{v}</a></p>'
            f'<h1>{v} {info["race"]}R <span class="sub">{html.escape(info["rtype"])}</span></h1>'
            f'<p class="sub">締切 {info["deadline"]}・{html.escape(info["title"])} {info["day"]}日目</p>{tabs(base, cur, locked)}')


def rnav(date, jcd, race, races, suffix):
    prev = f'<a href="/{date}/{jcd}/{race - 1:02d}{suffix}.html">← {race - 1}R</a>' if race - 1 in races else "<span></span>"
    nxt = f'<a href="/{date}/{jcd}/{race + 1:02d}{suffix}.html">{race + 1}R →</a>' if race + 1 in races else "<span></span>"
    return f'<div class="rnav">{prev}{nxt}</div>'


def labels(pred):
    sc, bs = pred["scene"], pred["boats"]
    f = lambda ks: "・".join(str(bs[k]["waku"]) for k in ks) or "なし"
    return (f'<span class="lab" style="background:var(--red)">頭注目 {f(sc["head"])}</span>'
            f'<span class="lab" style="background:var(--green)">連絡み注目 {f(sc["ren"])}</span>'
            f'<span class="lab" style="background:#444441">展開不向き {f(sc["bad"])}</span>')


def info_page(date, info, boats, season, series, n_series, pred, races):
    v = VENUES[info["jcd"]]
    base = f'{info["race"]:02d}'
    locked = not (pred and pred.get("version") == "final")
    order = [b["waku"] for b in pred["boats"]] if not locked else None
    rows = ""
    for b in boats:
        s = series.get(b["toban"], {})
        sea = season.get(b["toban"])
        ser = (f'{s["seq"]}<br>{s["pt"]:.2f}（{s["pos"]}位/{n_series}）' if s else "―")
        rows += (f'<div class="boat">{chip(b["waku"])}<div style="flex:1"><b>{html.escape(b["name"])}</b> '
                 f'<span class="sub">{b["toban"]}・{b["grade"]}・{b["age"]}歳・{html.escape(b["branch"])}・{b["weight"]}kg</span>'
                 f'<div class="nums"><div><span>今期勝率</span>{f"{sea:.2f}" if sea is not None else "―"}</div>'
                 f'<div><span>全国／当地</span>{b["nat_win"]:.2f}／{b["loc_win"]:.2f}</div>'
                 f'<div><span>モーター2連</span>{b["motor_2r"]:.1f}%</div>'
                 f'<div style="grid-column:span 3"><span>節間成績・得点率（目安）</span>{ser}</div></div></div></div>')
    entry = ("展示の進入：" + " ".join(str(w) for w in order)) if order else "展示の進入が出たら、スタートスリットと1マークの展開予想を公開します（締切の約20分前）。"
    body = (race_head(date, v, info, "info", locked, base) + (f'<div class="card">{labels(pred)}</div>' if not locked else "")
            + f'<div class="card">{rows}</div><p class="sub">{entry}</p>' + (NUDGE if not order else "")
            + ad() + rnav(date, info["jcd"], info["race"], races, ""))
    return page(f"{v}{info['race']}R 出走表・展開予想 {jp(date)}", body,
                f"{v}{info['race']}Rの出走表と1マーク展開予想。今期勝率・節間成績つき。", f"/{date}/{info['jcd']}/{base}.html")


NUDGE = '<script>fetch("/api/nudge",{method:"POST",keepalive:true}).catch(()=>{})</script>'
NUDGE_UPDATE = '<script>fetch("/api/nudge-update",{method:"POST",keepalive:true}).catch(()=>{})</script>'


def locked_body():
    return ('<div class="card lock"><b>展示の進入が出たら公開します</b><br>'
            '<span class="sub">締切の約20分前に更新されます</span></div>' + NUDGE)


def slit_page(date, info, pred, races):
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
    body = race_head(date, v, info, "slit", locked, base) + content + ad() + rnav(date, info["jcd"], info["race"], races, "-slit")
    return page(f"{v}{info['race']}R スタートスリット予想 {jp(date)}", body, f"{v}{info['race']}Rのスタートスリット隊形予想",
                f"/{date}/{info['jcd']}/{base}-slit.html")


def turn_page(date, info, pred, races):
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
        content = f'<div class="card">{labels(pred)}</div>{turn_svg(sc2, waku)}<h2>各艇の展開</h2><div class="card">{lines}</div>'
    body = race_head(date, v, info, "turn", locked, base) + content + ad() + rnav(date, info["jcd"], info["race"], races, "-turn")
    return page(f"{v}{info['race']}R 1マーク展開予想 {jp(date)}", body, f"{v}{info['race']}Rの1マーク仕掛け・展開予想",
                f"/{date}/{info['jcd']}/{base}-turn.html")


def venue_page(date, jcd, infos, preds, now):
    v = VENUES[jcd]
    items = ""
    for i, info in enumerate(infos):
        pred = preds.get(f"{jcd}-{info['race']:02d}")
        st = race_status(date, info, pred, now)
        badge = {"hot": '<span class="rst s-hot">展開予想！</span>', "wait": '<span class="rst s-wait">展示待ち</span>',
                 "done": '<span class="rst s-done">締切</span>'}[st]
        link = f"/{date}/{jcd}/{info['race']:02d}{'-turn' if st == 'hot' else ''}.html"
        items += (f'<a href="{link}"><span class="rno">{info["race"]}R</span><span><span class="sub">{info["deadline"]}</span> '
                  f'{html.escape(info["rtype"])}</span>{badge}</a>')
        if i == 5:
            items += f"</div>{ad()}<div class='card list'>"
    head = f'<h1>{v} {jp(date)}</h1><p class="sub">{html.escape(infos[0]["title"])}・{infos[0]["day"]}日目</p>'
    return page(f"{v} {jp(date)} 出走表・展開予想", head + f"<div class='card list'>{items}</div>",
                f"{v}の全レースの出走表と1マーク展開予想", f"/{date}/{jcd}/")


def grid_page(date, dates, prog_day, preds, now, path):
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
        if hot:
            cls, st = "hot", '<span class="hotb">展開予想！</span>'
        elif now >= max(dls):
            cls, st = "done", '<span class="st">開催終了</span>'
        elif now < min(dls) - dt.timedelta(minutes=40):
            cls, st = "", f'<span class="st">1R {infos.deadline.iloc[0]}</span>'
        else:
            nxt = next((r for r, d in zip(infos.itertuples(), dls) if d > now), None)
            cls, st = "", f'<span class="st">{nxt.race}R展示待ち</span>' if nxt else ""
        tiles += (f'<a class="tile {cls}" href="/{date}/{j}/"><b>{v}</b><span class="d">{infos.day.iloc[0]}日目 {ic}</span>{st}</a>')
    i = dates.index(date)
    prev = f'<a href="/{dates[i - 1]}/">◀ 前日</a>' if i > 0 else '<span class="x">◀ 前日</span>'
    nxt = f'<a href="/{dates[i + 1]}/">翌日 ▶</a>' if i + 1 < len(dates) else '<span class="x">翌日 ▶</span>'
    hl = "".join(f'<a href="/{date}/{j}/{r:02d}-turn.html"><span class="rno" style="width:80px">{VENUES[j]} {r}R</span>'
                 f'<span class="sub">締切 {d}</span><span class="rst s-hot">展開予想！</span></a>'
                 for d, j, r in sorted(hot_list))
    hot_html = f"<h2>いま展開予想が出ているレース</h2><div class='card list'>{hl}</div>" if hl else ""
    body = (f'<div class="dnav">{prev}<b>{jp(date)}</b>{nxt}</div><div class="grid">{tiles}</div>'
            f'<p class="sub">展示の進入が出たレースから順に、スタートスリットと1マークの展開予想を公開します。</p>{hot_html}{ad()}{NUDGE_UPDATE}')
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
                (d / f"{base}.html").write_text(info_page(date, info, boats, season, series, n_series, pred, races))
                (d / f"{base}-slit.html").write_text(slit_page(date, info, pred, races))
                (d / f"{base}-turn.html").write_text(turn_page(date, info, pred, races))
                urls += [f"/{date}/{jcd}/{base}{s}.html" for s in ("", "-slit", "-turn")]
            (d / "index.html").write_text(venue_page(date, jcd, infos, preds, now))
            urls.append(f"/{date}/{jcd}/")
        (OUT / date).mkdir(exist_ok=True)
        (OUT / date / "index.html").write_text(grid_page(date, dates, day, preds, now, f"/{date}/"))
        urls.append(f"/{date}/")
    top = today if today in dates else (dates[-1] if dates else None)
    if top:
        tp = DATA / "predictions" / f"{top}.json"
        preds = json.loads(tp.read_text())["races"] if tp.exists() else {}
        (OUT / "index.html").write_text(grid_page(top, dates, prog[prog.date == top], preds, now, "/"))
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
