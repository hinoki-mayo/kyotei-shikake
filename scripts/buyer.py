"""購入係: レースの時間帯だけ常駐して、締切の決まった時刻に買い目を決める(お金は使わない試験運用)
例: python scripts/buyer.py --max-minutes 300

・15秒おきに見回り、締切5分前に「候補」、2分前に「確定」、45秒前にオッズだけ記録する(bet.STAGES)
・結果(30秒おき)とオッズ(2分おき)は、見回りとは別の係が自分の間隔で取りに行く
・決めたら「これから」とそのレースの試験買い目ページだけ作り直してサイトに出す(公開は裏で動かし、見回りは止めない。
  サイト全体は展示反映の5分おきの更新で作り直す)
・買い目は data/bets に書き、こまめにコミットする。展示反映の更新が作る予想を取り込むため、毎回 git pull する
・今日の最後のレースの締切を過ぎたか、max-minutes を過ぎたら終わる
"""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time

import threading

import bet
import build_site
import live_result
import race_view
from common import DATA, JST, ROOT, now_jst

TICK = 15        # 見回りの間隔(秒)
REBUILD_EVERY = 240   # サイト全体を裏で作り直す間隔(秒)。成績(v1など)を新しく保つ
PUSH_EVERY = 60  # 買い目のコミットをまとめる間隔(秒)
RESULT_EVERY = 30   # 締切を過ぎたレースの結果を見に行く間隔(秒)
ODDS_EVERY = 120    # サイトの「当てる予想」用に、締切前のオッズを取りに行く間隔(秒)


def git(*args, check=False):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode:
        print(r.stdout, r.stderr, file=sys.stderr)
    return r.returncode == 0


def sync(commit_msg=None):
    """自分の買い目をコミットして、展示反映の更新が作った予想などを取り込む"""
    if commit_msg:
        git("add", "data/bets", "data/live_results_fast", "data/odds_live")
        git("commit", "-q", "-m", commit_msg)
    if not git("pull", "-q", "--rebase", "--autostash"):
        git("rebase", "--abort")
    if commit_msg:
        for _ in range(3):
            if git("push", "-q"):
                break
            git("pull", "-q", "--rebase", "--autostash")


_deploy = {"proc": None, "again": False}


def deploy():
    """サイトを出す。時間がかかるので裏で動かし、見回りは止めない。出している最中に呼ばれたら、終わってからもう一度出す"""
    project = os.environ.get("CF_PROJECT")
    if not project:
        return
    p = _deploy["proc"]
    if p is not None and p.poll() is None:
        _deploy["again"] = True
        return
    log = ROOT / "deploy.log"
    if p is not None and p.returncode:
        print("サイトの公開に失敗:", log.read_text()[-500:] if log.exists() else "", file=sys.stderr)
    _deploy["again"] = False
    with open(log, "w") as f:   # 出力はファイルへ(パイプだと溜まって止まることがある)
        _deploy["proc"] = subprocess.Popen(["wrangler", "pages", "deploy", "site", f"--project-name={project}", "--branch=main"],
                                           cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)


def deploy_pending():
    p = _deploy["proc"]
    if _deploy["again"] and (p is None or p.poll() is not None):
        deploy()


_rebuild = {"proc": None, "at": 0.0}


def rebuild():
    """サイト全体を裏で site_new に作り、出来たら site と差し替える(見回りは止めない)。差し替えたらTrue"""
    p = _rebuild["proc"]
    if p is not None and p.poll() is None:
        return False
    swapped = False
    if p is not None:
        new, cur, old = ROOT / "site_new", ROOT / "site", ROOT / "site_old"
        if p.returncode == 0 and new.exists():
            shutil.rmtree(old, ignore_errors=True)
            if cur.exists():
                cur.rename(old)
            new.rename(cur)
            shutil.rmtree(old, ignore_errors=True)
            swapped = True
        else:
            print("サイト全体の作り直しに失敗", file=sys.stderr)
        _rebuild["proc"] = None
    if time.time() - _rebuild["at"] >= REBUILD_EVERY:
        _rebuild["at"] = time.time()
        _rebuild["proc"] = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "build_site.py")], cwd=ROOT,
                                            env={**os.environ, "SITE_OUT": str(ROOT / "site_new")},
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return swapped


_res = {"new": [], "lock": threading.Lock(), "on": False}


def _loop(every, fn, name):
    """見回りとは別に、every秒おきに fn を回し続ける(見回りが重くても結果やオッズの取り込みが遅れないように)"""
    def run():
        while True:
            t0 = time.time()
            try:
                fn(now_jst())
            except Exception as e:
                print(f"{name}で失敗:", repr(e), file=sys.stderr)
            time.sleep(max(1.0, every - (time.time() - t0)))
    threading.Thread(target=run, daemon=True).start()


def _results_once(now):
    p = DATA / "predictions" / f"{now:%Y%m%d}.json"
    if not p.exists():
        return
    races = {k: x.get("deadline") for k, x in json.loads(p.read_text())["races"].items()}
    t0 = time.time()
    new = live_result.run_fast(f"{now:%Y%m%d}", races, now)
    if new:
        print(f"{now:%H:%M:%S} 結果 {' '.join(new)}({time.time() - t0:.0f}秒)", flush=True)
        with _res["lock"]:
            _res["new"] += new


def results_bg(now):
    """締切を過ぎたレースの結果は裏の係が30秒おきに取りに行く。取れたレースを返す"""
    if not _res["on"]:
        _res["on"] = True
        _loop(RESULT_EVERY, _results_once, "結果の取り込み")
    with _res["lock"]:
        got, _res["new"] = _res["new"], []
    return got


def _odds_once(now):
    p = DATA / "predictions" / f"{now:%Y%m%d}.json"
    if p.exists():
        race_view.fetch_live(f"{now:%Y%m%d}", json.loads(p.read_text())["races"], now)


_odds = {"on": False}


def odds_bg(now):
    """サイトの予想用に、展示が出たレースのオッズを裏の係が2分おきに取りに行く"""
    if not _odds["on"]:
        _odds["on"] = True
        _loop(ODDS_EVERY, _odds_once, "オッズの取り込み")


_bd = {"th": None, "again": False, "done": False}


def bets_data_bg(now):
    """今日の集計(部屋の成績・採用したレースの一覧)を裏で作り直す(10〜20秒かかるので見回りは止めない)。出来たら次の見回りで出す"""
    th = _bd["th"]
    if th is not None and th.is_alive():
        _bd["again"] = True
        return
    _bd["again"] = False

    def work():
        build_site.quick_bets_data(now)
        _bd["done"] = True
    _bd["th"] = threading.Thread(target=work, daemon=True)
    _bd["th"].start()


def code_version():
    """scripts の中身の版(git のツリー)。変わったら購入係を起動し直す"""
    r = subprocess.run(["git", "rev-parse", "HEAD:scripts"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip()


def last_deadline(now):
    p = DATA / "predictions" / f"{now:%Y%m%d}.json"
    if not p.exists():
        return None
    ds = [x["deadline"] for x in json.loads(p.read_text())["races"].values() if x.get("deadline")]
    return dt.datetime.strptime(f"{now:%Y%m%d}" + max(ds), "%Y%m%d%H:%M").replace(tzinfo=JST) if ds else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minutes", type=float, default=300)
    a = ap.parse_args()
    end = time.time() + a.max_minutes * 60
    sync()
    ld = last_deadline(now_jst())
    if ld is not None and now_jst() > ld + dt.timedelta(minutes=10):
        print("今日の最後のレースの締切を過ぎているので何もしません")
        return
    ver = code_version()
    build_site.main()   # 最初にサイト全体を作っておく。その後は裏で4分おきに作り直して差し替え、決めた時は「これから」だけ差し替えて出す
    _rebuild["at"] = time.time()
    pending, last_push = [], time.time()
    while time.time() < end:
        t_tick = time.time()
        now = now_jst()
        ld = last_deadline(now)
        if ld is not None and now > ld + dt.timedelta(minutes=10):   # 最後のレースの結果まで取ってから終わる
            print("今日の最後のレースの締切を過ぎたので終わります")
            break
        try:
            done = bet.decide_due(now)
        except Exception as e:   # 1回の見回りで失敗しても常駐は続ける
            print("見回りで失敗:", repr(e), file=sys.stderr)
            done = []
        odds_bg(now)
        got = results_bg(now)
        if got:   # 結果が取れたら、そのレースの買い目ページをすぐ作り直し、サイト全体の作り直しも早める
            pending += [f"結果 {k}" for k in got]
            build_site.quick_upcoming(now)   # 結果が出たレースを「これから」から外す
            build_site.quick_bet_pages(now, got)
            bets_data_bg(now)   # 部屋の成績・採用したレースの一覧にもすぐ出す
            deploy()
            _rebuild["at"] = 0.0   # 結果ページなどサイト全体の作り直しも早める
        if rebuild():   # 裏で作り直したサイト全体に差し替えた(成績が新しくなる)
            build_site.quick_upcoming(now)
            bets_data_bg(now)   # 作り始めた後に出た結果も入れ直す
            deploy()
        if done:
            pending += done
            build_site.quick_upcoming(now)
            build_site.quick_bet_pages(now, sorted({x.split(":")[0] for x in done}))
            deploy()
        if _bd["done"]:
            _bd["done"] = False
            deploy()
        if _bd["again"] and not (_bd["th"] and _bd["th"].is_alive()):
            bets_data_bg(now)
        deploy_pending()
        if time.time() - t_tick > 30:
            print(f"{now:%H:%M:%S} 見回りに{time.time() - t_tick:.0f}秒かかった", flush=True)
        if time.time() - last_push >= PUSH_EVERY:
            sync(f"購入係 {now:%H:%M} {len(pending)}件" if pending else None)
            pending, last_push = [], time.time()
            if code_version() != ver:   # 新しいコードが来たら、残り時間で自分を起動し直す(決めた段階は記録に残っているので続きから)
                left = (end - time.time()) / 60
                print(f"新しいコードが来たので起動し直します(残り{left:.0f}分)", flush=True)
                os.execv(sys.executable, [sys.executable, __file__, "--max-minutes", f"{left:.1f}"])
        time.sleep(max(1, TICK - (time.time() % TICK)))
    if pending:
        sync(f"購入係 {now_jst():%H:%M} {len(pending)}件")


if __name__ == "__main__":
    main()
