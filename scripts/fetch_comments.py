"""選手コメント・記者の見解を保存する(今は大村だけ。予想にはまだ使わない。言葉と結果を突き合わせるために貯める)
例: python scripts/fetch_comments.py --start 20240101            (大村の過去分をさかのぼって取る)
    python scripts/fetch_comments.py --start 20261101 --end 20261104
・元: 大村の予想サイト「展示航走終了後の直前生予想」(yosou/include/chokuzen_comment.php?day=&race=)。展示の後・締切前に出る
・保存先: data/comments/24/<日付>.json
  {"レース番号": {"boats": {"枠": {"toban": 登番, "comment": 節間のコメント, "kehai": 当日気配のコメント, "kehai_at": 時刻,
                                  "motor": モーター評価(1〜7), "tenji": 記者の展示評価(7点満点), "st": 展示ST, "ex": 展示タイム}},
                 "kisya": 記者の直前予想の文, "updated": ページの更新時刻}}
・注意: ページは1日中書き足されるので、後から取った分には「レース後」のコメント(そのレースより後の時刻)も混ざる。
  使う時は当日気配の時刻(kehai_at)がそのレースの締切より前のものだけにする(後の時刻のものを使うと答えを見たことになる)
・空だった日は {} で残して次から取りに行かない。1Rが空の日が8日続いたら止める。1回ごとに1.2秒あける
"""
import argparse
import datetime as dt
import html as htmlmod
import json
import re
import time
import urllib.request

import pandas as pd

from common import DATA, UA, now_jst

URL = "https://omurakyotei.jp/yosou/include/chokuzen_comment.php?day={date}&race={race:02d}"


def _txt(s):
    s = re.sub(r"<br\s*/?>|</p>", " ", s or "")
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def parse(h):
    out = {"boats": {}}
    up = re.search(r'更新時間：<strong[^>]*>([^<]+)</strong>', h or "")
    if up:
        out["updated"] = up.group(1).strip()
    t = re.search(r'id="tblchokuzen_detail"[^>]*>(.*?)</table>', h or "", re.S)
    for row in re.findall(r"<tr>(.*?)</tr>", t.group(1) if t else "", re.S):
        w = re.search(r'<th class="tei\d">\s*(\d)\s*</th>', row)
        tds = [re.sub(r"<[^>]+>", "", v).strip() for v in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if not w or len(tds) < 9:
            continue
        b = out["boats"].setdefault(w.group(1), {})
        b["st"], b["ex"] = tds[0], tds[1]
        try:
            b["tenji"] = int(tds[-1])
        except ValueError:
            pass
    t = re.search(r'id="tblcomment"[^>]*>(.*?)(?:</table>|$)', h or "", re.S)
    for row in re.split(r"<tr[^>]*>", t.group(1) if t else "")[1:]:
        w = re.search(r'<th class="tei\d">\s*(\d)\s*</th>', row)
        if not w:
            continue
        b = out["boats"].setdefault(w.group(1), {})
        tb = re.search(r"toban=(\d+)", row)
        if tb:
            b["toban"] = tb.group(1)
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(tds) >= 3:
            c = tds[1]
            k = re.search(r"\(当日気配\)(.*?)</font>", c, re.S)
            if k:
                kt = _txt(k.group(1))
                at = re.search(r"\[(\d{1,2}:\d{2})\]\s*$", kt)
                b["kehai"] = re.sub(r"\s*\[\d{1,2}:\d{2}\]\s*$", "", kt).strip("「」 ")
                if at:
                    b["kehai_at"] = at.group(1)
                c = c[:c.find("<font")] if "<font" in c else c
            b["comment"] = _txt(c)
            m = re.search(r'motor_hyoka">(\d)点', tds[2])
            if m:
                b["motor"] = int(m.group(1))
    k = re.search(r'id="kisyacomment".*?<div class="tinymce">(.*?)</div>', h or "", re.S)
    if k:
        out["kisya"] = _txt(k.group(1))
    return out if out["boats"] else {}


def fetch(date, race):
    try:
        with urllib.request.urlopen(urllib.request.Request(URL.format(date=date, race=int(race)), headers=UA), timeout=30) as r:
            return parse(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"コメントを取れませんでした(24-{race} {date}): {e!r}")
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="20240101")
    ap.add_argument("--end", default=None)
    ap.add_argument("--max-minutes", type=float, default=330)
    a = ap.parse_args()
    end = a.end or f"{now_jst() - dt.timedelta(days=1):%Y%m%d}"
    progs = [pd.read_parquet(p, columns=["date", "jcd", "race"]) for y in range(int(a.start[:4]), int(end[:4]) + 1)
             if (p := DATA / "programs" / f"{y}.parquet").exists()]
    prog = pd.concat(progs)
    prog = prog[(prog.jcd == "24") & (prog.date >= a.start) & (prog.date <= end)]
    out_dir = DATA / "comments" / "24"
    out_dir.mkdir(parents=True, exist_ok=True)
    t0, miss, n_ok = time.time(), 0, 0
    for date in sorted(prog.date.unique(), reverse=True):
        if time.time() - t0 > a.max_minutes * 60:
            print("時間切れ")
            break
        fp = out_dir / f"{date}.json"
        if fp.exists():
            miss = 0 if json.loads(fp.read_text()) else miss + 1
            continue
        got = {}
        for i, race in enumerate(sorted(int(r) for r in prog[prog.date == date].race.unique())):
            o = fetch(date, race)
            time.sleep(1.2)
            if o:
                got[str(race)] = o
            elif i == 0:
                break
        fp.write_text(json.dumps(got, ensure_ascii=False))
        if got:
            miss, n_ok = 0, n_ok + 1
        else:
            miss += 1
            if miss >= 8:
                print(f"{date}より古い分は残っていないとみて止める")
                break
    print(f"大村のコメント: {n_ok}日分を取得")


if __name__ == "__main__":
    main()
