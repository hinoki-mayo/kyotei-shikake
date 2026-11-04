"""オリジナル展示(まわり足・半周ラップ・展示タイム・直線タイム)を、出している場の公式サイトから保存する
・今は桐生だけ(選手・タイムデータのページ)。表は「選手 × 日ごとに2枠(その日の1走目・2走目)」の形
・保存先: data/orig_tenji/<場コード>/<日付>.json
    {"title": 節の名前, "fetched_at": 時刻, "racers": {選手名: {"まわり足": [12枠], "半周ラップ": [...], "展示タイム": [...], "直線タイム": [...]}}}
  枠は 初日1走目, 初日2走目, 2日目1走目, ... の順。空はnull。どのレースの数字かは番組表と名前で後から照らし合わせる
・ほかに、直前情報に「オリジナル展示データ」(一周・まわり足・直線)を出している場はレースごとに取る(RACE_SITES)。
  展示を取り込む時(entry.py)に一緒に取り、展示の記録(data/entries)の "orig" に {枠: {一周, まわり足, 直線}} で入れる
・予想にはまだ使わない(貯めてから効くか確かめる)
"""
import datetime as dt
import json
import re
import sys
import urllib.request

from common import DATA, UA, now_jst

SITES = {"01": "https://www.kiryu-kyotei.com/modules/raceinfo/?page=index_timedata"}
KINDS = ("まわり足", "半周ラップ", "展示タイム", "直線タイム")
# 直前情報のオリジナル展示データ(kind=2)を出している場。同じ作りのページ
RACE_SITES = {"06": "www.boatrace-hamanako.jp", "08": "www.boatrace-tokoname.jp", "10": "www.boatrace-mikuni.jp",
              "13": "www.boatrace-amagasaki.jp", "20": "www.wmb.jp", "21": "www.boatrace-ashiya.com", "23": "www.boatrace-karatsu.jp",
              "14": "www.n14.jp", "19": "www.boatrace-shimonoseki.jp"}
RACE_URL = "https://{host}/modules/yosou/group-cyokuzen.php?day={date}&race={race}&if=1&kind=2"
# 宮島は作りが違う: トップページの直前情報を POST(race, date) で読み込む。返事は「####」区切りで、その中の「まわり足」がある区切りが直前情報の表
MIYAJIMA_URL = "https://www.boatrace-miyajima.com/race_common/require/kaisai_reload.php"
RACE_SITES["17"] = "www.boatrace-miyajima.com"
# 大村は予想サイトの「展示航走終了後の直前生予想」の表(一周・回り足・直線)。過去の日付も選べる
OMURA_URL = "https://omurakyotei.jp/yosou/include/chokuzen_comment.php?day={date}&race={race:02d}"
RACE_SITES["24"] = "omurakyotei.jp"
# 平和島・丸亀はスマホのレース情報のページ。yoso05(5番目のタブ=直前)+レース番号。その日の分しか置かれていない
SP_YOSO_URL = "https://{host}/asp/kyogi/{jcd}/sp/yoso05{race:02d}.htm"
RACE_SITES["04"] = "www.heiwajima.gr.jp"
RACE_SITES["15"] = "www.marugameboat.jp"
RACE_KINDS = ("一周", "まわり足", "直線", "半周")


def parse_race(h):
    """直前情報のオリジナル展示データの表 → {枠: {一周: 秒, まわり足: 秒, 直線: 秒}}。読めなければ{}"""
    thead = re.search(r"<thead>(.*?)</thead>", h or "", re.S)
    tbody = re.search(r"<tbody>(.*?)</tbody>", h or "", re.S)
    if not thead or not tbody:
        return {}
    labels = [t for t in (re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<th[^>]*>(.*?)</th>", thead.group(1), re.S))
              if t in RACE_KINDS]
    if not labels:
        return {}
    out = {}
    for row in re.split(r"<tr[^>]*>", tbody.group(1)):
        cells = re.findall(r"<td([^>]*)>(.*?)</td>", row, re.S)
        w = next((re.sub(r"<[^>]+>", "", v).strip() for a, v in cells if re.search(r"\bwaku\b", a)), None)
        if not w or not w.isdigit():
            continue
        i5 = max((i for i, (a, _) in enumerate(cells) if re.search(r"\bcol5\b", a)), default=None)   # 鳴門はチルトもcol5なので最後のcol5(展示)の後ろから読む
        if i5 is None:
            continue
        vals = {}
        for lab, (_, v) in zip(labels, cells[i5 + 1:i5 + 1 + len(labels)]):
            try:
                vals[lab] = float(re.sub(r"<[^>]+>", "", v).strip())
            except ValueError:
                vals[lab] = None
        if any(x is not None for x in vals.values()):
            out[w] = vals
    return out


def parse_miyajima(h):
    """宮島の直前情報の表 → {枠: {一周, まわり足, 直線}}。列は 体重・チルト・展示・一周・まわり足・直線 の順"""
    out = {}
    for row in re.split(r"<tr[^>]*>", h or ""):
        w = re.search(r'<p class="wakuban[^"]*">\s*(\d)\s*</p>', row)
        if not w:
            continue
        vals = []
        for v in re.findall(r'<i class="bold">([^<]*)</i>', row):
            try:
                vals.append(float(v.strip()))
            except ValueError:
                vals.append(None)
        if len(vals) >= 6:
            o = dict(zip(("一周", "まわり足", "直線"), vals[3:6]))
            if any(x is not None for x in o.values()):
                out[w.group(1)] = o
    return out


def parse_omura(h):
    """大村の直前の表 → {枠: {一周, まわり足, 直線}}。行は展示の進入順で、先頭の見出しが枠番。列は ST・展示T・一周・回り足・直線 の順"""
    t = re.search(r'<table[^>]*id="tblchokuzen_detail"[^>]*>(.*?)</table>', h or "", re.S)
    out = {}
    for row in re.findall(r"<tr>(.*?)</tr>", t.group(1) if t else "", re.S):
        w = re.search(r'<th class="tei\d">\s*(\d)\s*</th>', row)
        tds = [re.sub(r"<[^>]+>", "", v).strip() for v in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if not w or len(tds) < 5:
            continue
        vals = []
        for v in tds[2:5]:
            try:
                vals.append(float(v))
            except ValueError:
                vals.append(None)
        if any(x is not None for x in vals):
            out[w.group(1)] = dict(zip(("一周", "まわり足", "直線"), vals))
    return out


def parse_heiwajima(h):
    """平和島の「オリジナルデータ」の表 → {枠: {一周, まわり足, 直線}}。艇ごとに「タイム」「時速」の2行があり、タイムの行を読む"""
    t = re.search(r'<table[^>]*id="tyoku01"[^>]*>(.*?)</table>', h or "", re.S)
    out = {}
    for body in re.findall(r"<tbody>(.*?)</tbody>", t.group(1) if t else "", re.S):
        w = re.search(r'class="waku0(\d)"', body)
        row = re.search(r"タイム</th>(.*?)</tr>", body, re.S)
        if not w or not row:
            continue
        vals = []
        for v in re.findall(r"<td[^>]*>([^<]*)</td>", row.group(1))[:3]:
            try:
                vals.append(float(v.strip()))
            except ValueError:
                vals.append(None)
        if len(vals) == 3 and any(x is not None for x in vals):
            out[w.group(1)] = dict(zip(("一周", "まわり足", "直線"), vals))
    return out


def parse_marugame(h):
    """丸亀の「オリジナル展示データ」の表 → {枠: {一周, まわり足, 直線}}。列は 枠・体重・チルト・展示・一周・まわり足・直線 の順"""
    i = (h or "").find("オリジナル展示データ")
    t = re.search(r"<table.*?</table>", h[h.rfind("<table", 0, i):] if i >= 0 else "", re.S)
    out = {}
    for body in re.findall(r"<tbody>(.*?)</tbody>", t.group(0) if t else "", re.S):
        tr = re.search(r"<tr[^>]*>(.*?)</tr>", body, re.S)
        tds = [re.sub(r"<[^>]+>", "", v).strip() for v in re.findall(r"<td[^>]*>(.*?)</td>", tr.group(1) if tr else "", re.S)]
        if len(tds) < 7 or not tds[0].isdigit():
            continue
        vals = []
        for v in tds[4:7]:
            try:
                vals.append(float(v))
            except ValueError:
                vals.append(None)
        if any(x is not None for x in vals):
            out[tds[0]] = dict(zip(("一周", "まわり足", "直線"), vals))
    return out


def fetch_miyajima(date, race):
    import urllib.parse
    data = urllib.parse.urlencode({"race": int(race), "date": date}).encode()
    req = urllib.request.Request(MIYAJIMA_URL, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8", errors="replace")
    if f'value="{date}"' not in raw:   # 日付の一覧にその日が無い(=別の節の数字が返ってきた)時は使わない
        return {}
    dt = raw.split("####")
    seg = next((x for x in dt if "まわり足" in x), "")   # 直前情報の表(並び順が変わっても見つけられるよう、中身で探す)
    return parse_miyajima(seg)


def fetch_race(jcd, date, race):
    """その場がオリ展を出していれば、そのレースのオリ展 {枠: {...}}。出していない・取れなければ{}"""
    host = RACE_SITES.get(jcd)
    if not host:
        return {}
    try:
        if jcd == "17":
            return fetch_miyajima(date, race)
        if jcd in ("04", "15"):
            req = urllib.request.Request(SP_YOSO_URL.format(host=host, jcd=jcd, race=int(race)), headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                h = r.read().decode("utf-8", errors="replace")
            # その日の分しか置かれないので、動画のリンクの日付(raceDate=)がその日と合う時だけ使う(過去の日付で別の日の数字を取らないため)
            if date not in set(re.findall(r"raceDate=(\d{8})", h)):
                return {}
            return parse_heiwajima(h) if jcd == "04" else parse_marugame(h)
        if jcd == "24":
            req = urllib.request.Request(OMURA_URL.format(date=date, race=int(race)), headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return parse_omura(r.read().decode("utf-8", errors="replace"))
        req = urllib.request.Request(RACE_URL.format(host=host, date=date, race=int(race)), headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            return parse_race(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"オリ展を取れませんでした({jcd}-{race}): {e!r}")
        return {}


def parse(h):
    title = re.search(r'<h2 class="ttl02[^"]*">\s*<span>([^<]+)</span>', h)
    body = h[h.find('<tbody>'):h.find('</tbody>')]
    racers, name = {}, None
    for row in re.split(r'<tr class="(?:odd|even)">', body)[1:]:
        m = re.search(r'<td class="name"[^>]*>([^<]+)</td>', row)
        if m:
            name = re.sub(r"\s+", "", m.group(1).replace("　", ""))
        k = re.search(r'<td class="timeKind">([^<]+)</td>', row)
        if not name or not k or k.group(1) not in KINDS:
            continue
        vals = []
        for v in re.findall(r'<td class="time">([^<]*)</td>', row):
            v = v.strip()
            try:
                vals.append(float(v))
            except ValueError:
                vals.append(None)
        racers.setdefault(name, {})[k.group(1)] = vals
    return (title.group(1).strip() if title else ""), racers


def main():
    now = now_jst()
    for jcd, url in SITES.items():
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                h = r.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"{jcd}: 取れませんでした {e!r}")
            continue
        title, racers = parse(h)
        if not racers:
            print(f"{jcd}: 表が読めませんでした")
            continue
        p = DATA / "orig_tenji" / jcd / f"{now:%Y%m%d}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(dict(title=title, fetched_at=f"{now:%Y-%m-%d %H:%M}", racers=racers), ensure_ascii=False))
        print(f"{jcd}: {title} {len(racers)}人")


if __name__ == "__main__":
    main()
