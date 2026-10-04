"""締切を過ぎたレースの結果を、公式サイトのレース結果ページから1レースずつ取り込む

公式の競走成績ファイル(K)はその日の全レースが終わってからまとめて公開されるので、
日中は結果タブや試験用買い目の収支がずっと空のままだった。その間のつなぎとして
data/live_results/日付.json に {場-R: 着順・決まり手・3連単の組と配当} を保存する。
夜に成績ファイルが公開されたら、そちらが正式なデータとして優先される。
"""
import datetime as dt
import json
import re
import time
import unicodedata
import urllib.request

from common import DATA, JST, UA, now_jst

URL = "https://www.boatrace.jp/owpc/pc/race/raceresult?rno={race}&jcd={jcd}&hd={date}"
RANK_RE = re.compile(r'<td class="is-fs14">([^<]+)</td>\s*<td class="is-fs14 is-fBold is-boatColor\d">(\d)</td>')
KIM_RE = re.compile(r'決まり手</th>.*?<td class="is-fs16">([^<]+)</td>', re.S)
TRI_RE = re.compile(r'3連単</td>(.*?)</tr>', re.S)
EXA_RE = re.compile(r'2連単</td>(.*?)</tr>', re.S)
WINDOW = (5, 90)   # 締切の何分後から何分後までのレースを見に行くか


def fetch_result(date, jcd, race):
    """{'by_waku': {枠: '01'..}, 'kimarite', 'combo3t', 'payout3t'} / まだ出ていなければNone"""
    try:
        req = urllib.request.Request(URL.format(race=race, jcd=jcd, date=date), headers=UA)
        with urllib.request.urlopen(req, timeout=40) as r:
            h = r.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    ranks = RANK_RE.findall(h)
    if len(ranks) < 3:      # 欠場があると6艇そろわない
        return None
    by_waku = {}
    for rk, w in ranks:
        rk = unicodedata.normalize("NFKC", rk).strip()
        by_waku[int(w)] = f"{int(rk):02d}" if rk.isdigit() else rk
    km = KIM_RE.search(h)
    combo, pay = _bet(TRI_RE, h, 3)
    combo2, pay2 = _bet(EXA_RE, h, 2)
    return dict(by_waku=by_waku, kimarite=km.group(1).strip() if km else "", combo3t=combo, payout3t=pay,
                combo2t=combo2, payout2t=pay2)


def _bet(rx, h, n):
    """券種の行から(組, 100円あたりの配当)"""
    m = rx.search(h)
    if not m:
        return None, None
    nums = re.findall(r'numberSet1_number[^>]*>(\d)<', m.group(1))
    yen = re.search(r'&yen;([\d,]+)', m.group(1))
    if len(nums) != n or not yen:
        return None, None
    return "-".join(nums), float(yen.group(1).replace(",", ""))


def load(date):
    p = DATA / "live_results" / f"{date}.json"
    if not p.exists():
        return {}
    return {k: dict(v, by_waku={int(w): r for w, r in v["by_waku"].items()}) for k, v in json.loads(p.read_text()).items()}


def run(prog, now=None):
    """prog: その日の番組表(jcd, race, deadline)。締切後で未取得のレースだけ見に行く"""
    now = now or now_jst()
    date = f"{now:%Y%m%d}"
    p = DATA / "live_results" / f"{date}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    saved = json.loads(p.read_text()) if p.exists() else {}
    done = []
    for r in prog.itertuples():
        key = f"{r.jcd}-{r.race:02d}"
        if key in saved or not r.deadline:
            continue
        t = dt.datetime.strptime(date + r.deadline, "%Y%m%d%H:%M").replace(tzinfo=JST)
        if not (dt.timedelta(minutes=WINDOW[0]) <= now - t <= dt.timedelta(minutes=WINDOW[1])):
            continue
        res = fetch_result(date, r.jcd, r.race)
        time.sleep(1.0)
        if res and res["combo3t"]:
            saved[key] = res
            done.append(key)
    if done:
        p.write_text(json.dumps(saved, ensure_ascii=False))
    print(f"レース結果: {len(done)}レース {done}")
    return done
