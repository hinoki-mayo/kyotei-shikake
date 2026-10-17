"""購入係: レースの時間帯だけ常駐して、締切の決まった時刻に買い目を決める(お金は使わない試験運用)
例: python scripts/buyer.py --max-minutes 300

・15秒おきに見回り、締切5分前に「候補」、2分前に「確定」、45秒前にオッズだけ記録する(bet.STAGES)
・決めたら「これから」とそのレースの試験買い目ページだけ作り直してサイトに出す(公開は裏で動かし、見回りは止めない。
  サイト全体は展示反映の5分おきの更新で作り直す)
・買い目は data/bets に書き、こまめにコミットする。展示反映の更新が作る予想を取り込むため、毎回 git pull する
・今日の最後のレースの締切を過ぎたか、max-minutes を過ぎたら終わる
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time

import bet
import build_site
from common import DATA, JST, ROOT, now_jst

TICK = 15        # 見回りの間隔(秒)
PUSH_EVERY = 60  # 買い目のコミットをまとめる間隔(秒)


def git(*args, check=False):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode:
        print(r.stdout, r.stderr, file=sys.stderr)
    return r.returncode == 0


def sync(commit_msg=None):
    """自分の買い目をコミットして、展示反映の更新が作った予想などを取り込む"""
    if commit_msg:
        git("add", "data/bets")
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
    build_site.main()   # 最初にサイト全体を作っておき、あとは「これから」だけ差し替えて出す
    pending, last_push = [], time.time()
    while time.time() < end:
        now = now_jst()
        ld = last_deadline(now)
        if ld is not None and now > ld:
            print("今日の最後のレースの締切を過ぎたので終わります")
            break
        try:
            done = bet.decide_due(now)
        except Exception as e:   # 1回の見回りで失敗しても常駐は続ける
            print("見回りで失敗:", repr(e), file=sys.stderr)
            done = []
        if done:
            pending += done
            build_site.quick_upcoming(now)
            build_site.quick_bet_pages(now, sorted({x.split(":")[0] for x in done}))
            deploy()
        deploy_pending()
        if time.time() - last_push >= PUSH_EVERY:
            sync(f"購入係 {now:%H:%M} {len(pending)}件" if pending else None)
            pending, last_push = [], time.time()
        time.sleep(max(1, TICK - (time.time() % TICK)))
    if pending:
        sync(f"購入係 {now_jst():%H:%M} {len(pending)}件")


if __name__ == "__main__":
    main()
