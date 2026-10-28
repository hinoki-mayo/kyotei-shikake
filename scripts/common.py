"""共通処理: ダウンロードとLZH展開"""
import datetime as dt
import pathlib
import time
import urllib.request

import lhafile

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"    # 生ファイル(.lzh)の置き場。Gitには入れない
DATA = ROOT / "data"  # 変換後の表(parquet)。Gitに入れる
BASE = "https://www1.mbrace.or.jp/od2"
UA = {"User-Agent": "Mozilla/5.0 (kyotei-shikake data fetcher)"}
JST = dt.timezone(dt.timedelta(hours=9))


def now_jst() -> dt.datetime:
    """現在時刻(日本時間)。テスト用に環境変数 KYOTEI_NOW="2026-09-28 13:00" で上書きできる"""
    import os
    if os.environ.get("KYOTEI_NOW"):
        return dt.datetime.strptime(os.environ["KYOTEI_NOW"], "%Y-%m-%d %H:%M").replace(tzinfo=JST)
    return dt.datetime.now(JST)


def today_jst() -> dt.date:
    return now_jst().date()


def raw_path(kind: str, day: dt.date) -> pathlib.Path:
    """kind: 'K'=競走成績, 'B'=番組表"""
    return RAW / kind / f"{day:%Y}" / f"{kind.lower()}{day:%y%m%d}.lzh"


def download(kind: str, day: dt.date, sleep: float = 1.0, force: bool = False) -> bool:
    """1日分をダウンロード。無い日(休場・未公開)はFalse。サーバーに優しく毎回間を空ける"""
    path = raw_path(kind, day)
    if path.exists() and not force:
        return True
    url = f"{BASE}/{kind}/{day:%Y%m}/{kind.lower()}{day:%y%m%d}.lzh"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
            body = r.read()
    except Exception:
        time.sleep(sleep)
        return False
    time.sleep(sleep)
    if len(body) < 200:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    try:
        lhafile.Lhafile(str(path))
    except Exception:
        path.unlink()
        return False
    return True


def read_text(path: pathlib.Path) -> str:
    lf = lhafile.Lhafile(str(path))
    return "".join(lf.read(n).decode("cp932", errors="replace") for n in lf.namelist())


def daterange(start: dt.date, end: dt.date):
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


# ---------- 締切時刻の変更(遅延など) ----------
# 朝の番組表の締切が当日に変わる(天候で遅れるなど)ことがある。展示を取りに行った公式ページの
# 「締切予定時刻」の一覧と違えば data/deadlines/日付.json に {場: [1R..12Rの時刻]} で残し、番組表を読む所で上書きする
def deadline_fix(date):
    import json
    p = DATA / "deadlines" / f"{date}.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}


def apply_deadlines(prog, date=None):
    """番組表(DataFrame: date, jcd, race, deadline)に当日の締切の変更を反映したコピーを返す"""
    dates = [date] if date else sorted(set(prog["date"])) if len(prog) else []
    out = prog
    for d in dates:
        fx = deadline_fix(d)
        if not fx:
            continue
        if out is prog:
            out = prog.copy()
        for jcd, ds in fx.items():
            for i, t in enumerate(ds):
                if t:
                    out.loc[(out["date"] == d) & (out["jcd"] == jcd) & (out["race"] == i + 1), "deadline"] = t
    return out
