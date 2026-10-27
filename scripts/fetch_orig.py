"""オリジナル展示(まわり足・半周ラップ・展示タイム・直線タイム)を、出している場の公式サイトから保存する
・今は桐生だけ(選手・タイムデータのページ)。表は「選手 × 日ごとに2枠(その日の1走目・2走目)」の形
・保存先: data/orig_tenji/<場コード>/<日付>.json
    {"title": 節の名前, "fetched_at": 時刻, "racers": {選手名: {"まわり足": [12枠], "半周ラップ": [...], "展示タイム": [...], "直線タイム": [...]}}}
  枠は 初日1走目, 初日2走目, 2日目1走目, ... の順。空はnull。どのレースの数字かは番組表と名前で後から照らし合わせる
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
