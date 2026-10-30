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
              "13": "www.boatrace-amagasaki.jp", "20": "www.wmb.jp", "21": "www.boatrace-ashiya.com", "23": "www.boatrace-karatsu.jp"}
RACE_URL = "https://{host}/modules/yosou/group-cyokuzen.php?day={date}&race={race}&if=1&kind=2"
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
        i5 = next((i for i, (a, _) in enumerate(cells) if re.search(r"\bcol5\b", a)), None)
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


def fetch_race(jcd, date, race):
    """その場がオリ展を出していれば、そのレースのオリ展 {枠: {...}}。出していない・取れなければ{}"""
    host = RACE_SITES.get(jcd)
    if not host:
        return {}
    try:
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
