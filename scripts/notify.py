"""手で買う人向けの通知(決裁者Cのやり方)。購入係が段階を決めるたびに ntfy へ送る(買うのは人。自動では買わない)

・送り先: 環境変数 NTFY_TOPIC(GitHubのSecretsに登録)。無ければ何もしない
・中身: 決裁者Aが採用する提案(A級インが逃げる箱だけ)を、決裁者Cの強弱(1着専門の後押しが無ければ1/4、同じ頭に自信度が採用線以上の提案が2つ以上なら×2)で
  金額に直したもの。1提案4,000円が基準
・締切5分前「買いそう」→ 2分前「ほぼ決定」→ 45秒前「買う」(または「見送り」)
"""
import json
import os
import threading
import urllib.request

import bet as bet_mod
import build_site as B
import org_tree
import shadow_staff
from common import DATA

TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
_sent = set()
_last = {}   # レースごとに最後に送った中身(2分前が5分前と同じなら送らない)
ONLY = ("in.A.",)   # 通知するのはA級インが逃げる箱の提案だけ(10/26 モニターの希望)。全部に戻すなら ("",)
LABEL = {"候補": "買いそう(5分前)", "確定": "ほぼ決定(2分前)", "直前": "買う(45秒前)"}


def _send(title, msg, prio=3, tags=None):
    if not TOPIC:
        return
    body = json.dumps(dict(topic=TOPIC, title=title, message=msg, priority=prio, tags=tags or []), ensure_ascii=False).encode()
    try:
        req = urllib.request.Request("https://ntfy.sh/", data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        print(f"通知を送れませんでした: {e!r}", flush=True)


def _picks(date, key, stage, pred, b):
    """(採用 [(提案, 倍率)], 見送りになった提案)"""
    plans = {n: pl for n, pl in B.plans_of(b).items()
             if n in bet_mod.OPS_PLANS + bet_mod.SHADOW_PLANS and pl.get("logic") == bet_mod.OPS_LOGIC and not pl.get("skip")}
    if not plans:
        return [], []
    conf, adopt = B.conf_for(date), org_tree.adopt_for(date)
    dec = lambda pl: org_tree.decide(org_tree.proposals(pl, pred), conf, adopt=adopt)
    kp = B._kessai_plans(date, key, pred, b, plans) if stage == "直前" else plans
    got = [c for c in dec(kp) if c["leaf"].startswith(ONLY)]
    s = (b.get("stages") or {}).get(stage) or {}
    o2 = {c: v for c, v in zip(bet_mod.ODDS2_ORDER, s.get("o2") or []) if v}
    lv = B._entries(date).get(key)
    try:
        wf = shadow_staff.win_ratio(pred, o2, lv if isinstance(lv, dict) else None) if o2 else None
    except Exception:
        wf = None
    props = org_tree.proposals(kp, pred)
    out = []
    for c in got:
        f = 1.0 if wf and wf[c["course"] - 1] >= 1.2 else 0.25
        gv = sum(1 for p in props if p.get("course") == c.get("course") and org_tree.conf_of(p, conf) >= adopt)
        out.append((c, f * (2 if gv >= 2 else 1)))
    skipped = [c for c in dec(plans) if c["leaf"].startswith(ONLY)] if (stage == "直前" and not got) else []
    return out, skipped


def _text(pred, key, stage, picks, skipped):
    head = f'{pred.get("venue", key)}{int(key[-2:])}R {pred.get("deadline", "")}締切'
    if not picks:
        return f"見送り(45秒前) {head}", "2分前は買う見込みだったが、45秒前のオッズで見送り"
    lines, total = [], 0
    for c, f in picks:
        kind = "3連単" if c["tickets"] and c["tickets"][0]["combo"].count("-") == 2 else "2連単"
        tk = []
        for t in c["tickets"]:
            yen = max(100, int(round(t["units"] * 100 * f / 100)) * 100)
            total += yen
            tk.append(f'{t["combo"]} {yen:,}円')
        strong = "強" if f >= 1 else "弱"
        lines.append(f'{B.ALL_PLAN_LABELS.get(c["plan"], c["plan"])}({strong}×{f:g}) {kind}\n' + " / ".join(tk))
    return f"{LABEL[stage]} {head} 計{total:,}円", "\n".join(lines)


def after_decide(now, done):
    """購入係: decide_due が返した ['場-R:段階', ...] について通知を送る(裏で送るので見回りは止めない)"""
    if not TOPIC or not done:
        return
    date = f"{now:%Y%m%d}"
    try:
        bets = json.loads((DATA / "bets" / f"{date}.json").read_text())
        preds = json.loads((DATA / "predictions" / f"{date}.json").read_text())["races"]
    except Exception:
        return
    msgs = []
    for x in done:
        key, _, stage = x.partition(":")
        if (key, stage) in _sent or stage not in LABEL:
            continue
        pred, b = preds.get(key), bets.get(key)
        if not pred or not b:
            continue
        try:
            picks, skipped = _picks(date, key, stage, pred, b)
        except Exception as e:
            print(f"通知の中身を作れませんでした({key}): {e!r}", flush=True)
            continue
        if not picks and not (stage == "直前" and skipped and (key, "確定") in _sent):
            continue
        _sent.add((key, stage))
        title, msg = _text(pred, key, stage, picks, skipped)
        if stage == "確定" and _last.get(key) == msg:
            continue   # 5分前と同じ買い目なら2分前は送らない(45秒前の「買う」は必ず送る)
        _last[key] = msg
        msgs.append((title, msg, 5 if stage == "直前" and picks else 3))
    for t, m, p in msgs:
        threading.Thread(target=_send, args=(t, m, p), daemon=True).start()


def test():
    _send("競艇の通知テスト", "購入係からの通知が届いたら準備OK")


if __name__ == "__main__":
    test()
