"""気象庁の潮位表(港ごと・1時間ごとの潮の高さ)を保存し、レースの締切時刻の潮を出す(予想にはまだ使わない)
例: python scripts/fetch_tide.py            (今年の分と、12月なら来年の分を取り直す)
    python scripts/fetch_tide.py 2024 2025  (年を指定)
・元: https://www.data.jma.go.jp/kaiyou/data/db/tide/suisan/txt/<年>/<地点記号>.txt (1行=1日。24時間分の潮位(cm)、日付、地点記号、満潮・干潮)
・保存先: data/tide/<地点記号>_<年>.txt
・場と港の対応(VENUE_STATION)は潮の影響がある場(海・河口)だけ。淡水の場(桐生・戸田・多摩川・びわこ・住之江・尼崎・芦屋)は入れない
"""
import sys
import time
import urllib.request

import numpy as np

from common import DATA, UA, now_jst

URL = "https://www.data.jma.go.jp/kaiyou/data/db/tide/suisan/txt/{year}/{st}.txt"
VENUE_STATION = {"03": "TK", "04": "TK", "06": "MI", "07": "NG", "08": "ZD", "09": "NG", "10": "ZG", "14": "KM", "15": "TX",
                 "16": "UN", "17": "Q8", "18": "QA", "19": "MO", "20": "MO", "22": "QF", "23": "KA", "24": "NS"}
# 東京・舞阪・名古屋・鬼崎・三国・小松島・多度津・宇野・広島・徳山・門司・博多・唐津・長崎
_CACHE = {}


def load(st, year):
    """{日付: [0〜23時の潮位cm]}"""
    if (st, year) in _CACHE:
        return _CACHE[(st, year)]
    out = {}
    p = DATA / "tide" / f"{st}_{year}.txt"
    if p.exists():
        for line in p.read_text(encoding="ascii", errors="ignore").splitlines():
            if len(line) < 80:
                continue
            try:
                v = [int(line[i * 3:i * 3 + 3]) for i in range(24)]
            except ValueError:
                continue
            out["20" + "".join(line[k:k + 2].replace(" ", "0") for k in (72, 74, 76))] = v
    _CACHE[(st, year)] = out
    return out


def at(jcd, date, hhmm):
    """その場・その日・その時刻の潮 → {"pos": その日の干満の中での高さ0〜1, "trend": 30分前→30分後の変化cm, "rng": その日の干満差cm} か None"""
    st = VENUE_STATION.get(jcd)
    v = load(st, int(date[:4])).get(date) if st else None
    if not v or not hhmm or ":" not in hhmm:
        return None
    h, m = map(int, hhmm.split(":"))
    t = h + m / 60
    lv = lambda x: float(np.interp(x, range(24), v))
    rng = max(v) - min(v)
    return {"pos": (lv(t) - min(v)) / max(rng, 1), "trend": lv(t + 0.5) - lv(t - 0.5), "rng": rng}


def main(argv):
    now = now_jst()
    years = [int(y) for y in argv] or ([now.year, now.year + 1] if now.month == 12 else [now.year])
    (DATA / "tide").mkdir(parents=True, exist_ok=True)
    for y in years:
        for st in sorted(set(VENUE_STATION.values())):
            try:
                with urllib.request.urlopen(urllib.request.Request(URL.format(year=y, st=st), headers=UA), timeout=40) as r:
                    b = r.read()
                if len(b) > 10000:
                    (DATA / "tide" / f"{st}_{y}.txt").write_bytes(b)
                    print(f"{st} {y}: 保存")
            except Exception as e:
                print(f"{st} {y}: 取れませんでした {e!r}")
            time.sleep(1.0)


if __name__ == "__main__":
    main(sys.argv[1:])
