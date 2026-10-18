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
FAST_FROM = 3      # 購入係は締切の3分後から見に行く(レースは締切の約2分後に始まり、約2分で終わる)


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
    """取り込んだ結果。展示反映の更新(5分おき)の分と、購入係がすぐ取った分(live_results_fast)を合わせる"""
    out = {}
    for d in ("live_results_fast", "live_results"):
        p = DATA / d / f"{date}.json"
        if p.exists():
            out.update(json.loads(p.read_text()))
    return {k: dict(v, by_waku={int(w): r for w, r in v["by_waku"].items()}) for k, v in out.items()}


def run_fast(date, races, now, workers=6):
    """購入係用: 締切を過ぎたレースの結果を、締切の FAST_FROM 分後から何度でも見に行く(並べて取る)。
    races: {場-R: 締切 'HH:MM'}。新しく取れたレースを返す。保存先は live_results_fast(展示反映の更新とぶつからないよう別ファイル)"""
    from concurrent.futures import ThreadPoolExecutor
    have = load(date)
    todo = []
    for key, dl in races.items():
        if key in have or not dl:
            continue
        t = dt.datetime.strptime(date + dl, "%Y%m%d%H:%M").replace(tzinfo=JST)
        if dt.timedelta(minutes=FAST_FROM) <= now - t <= dt.timedelta(minutes=WINDOW[1]):
            todo.append(key)
    if not todo:
        return []
    with ThreadPoolExecutor(workers) as ex:
        got = list(ex.map(lambda k: fetch_result(date, k.split("-")[0], int(k.split("-")[1])), todo))
    new = {k: r for k, r in zip(todo, got) if r and r["combo3t"]}
    if new:
        p = DATA / "live_results_fast" / f"{date}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        saved = json.loads(p.read_text()) if p.exists() else {}
        saved.update(new)
        p.write_text(json.dumps(saved, ensure_ascii=False))
    return sorted(new)


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
