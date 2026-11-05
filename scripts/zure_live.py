"""別会社ズレ屋のリアルタイム記録: 購入係が締切45秒前のオッズを取った瞬間に、そのレースのズレ屋の買い目を決めて残す(買うのは人)

・購入係(buyer.py)の見回りで decide_due が「場-R:直前」を返したら、そのレースだけ zure.picks を作る(裏で動かすので見回りは止めない)
・使うのはその時点で手元にある情報だけ(45秒前のオッズ・展示・展示の時に取れたオリ展・それまでのレースの速報)
・保存: data/zure_live/<日付>.json {レース: {"at": 決めた時刻, "matome": [[目, 45秒前オッズ], ...], "hmo_picks": ..., ...}}
  結果は入れない(答え合わせは夜の data/zure と、サイトの作り直しのときに結果と突き合わせる)
・まとめの買い目があれば ntfy(NTFY_TOPIC)へ「ズレ屋のまとめ 買う(45秒前)」を送る
"""
import json
import os
import threading
import traceback

from common import DATA, now_jst

KEYS = ("matome", "c6_picks", "hmo_picks", "z2_picks", "z3_picks", "ab_picks", "z5_picks", "hm_picks", "soto_picks", "picks", "rank", "soto", "hm", "orig")
_lock = threading.Lock()
_done = set()


def _save(date, key, rec):
    p = DATA / "zure_live" / f"{date}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    d = json.loads(p.read_text()) if p.exists() else {}
    d[key] = rec
    p.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")))


def _run(date, keys):
    import zure
    import notify
    with _lock:
        try:
            pk = zure.picks(date, only=set(keys))
        except Exception:
            traceback.print_exc()
            return
        at = f"{now_jst():%H:%M:%S}"
        for k in keys:
            v = pk.get(k)
            if not v:
                _save(date, k, {"at": at, "none": True})
                continue
            rec = {"at": at, **{x: v[x] for x in KEYS if x in v}}
            _save(date, k, rec)
            m = v.get("matome") or []
            if m and os.environ.get("NTFY_TOPIC"):
                from build_site import VENUES
                body = " ".join(f"{c}({o:.0f}倍)" for c, o in m[:30]) + (f" ほか{len(m) - 30}点" if len(m) > 30 else "")
                notify._send(f"ズレ屋のまとめ 買う(45秒前) {VENUES.get(k[:2], k[:2])}{int(k[3:])}R",
                             f"{len(m)}点・1点100円で{len(m) * 100:,}円\n{body}", 4)
            print(f"ズレ屋(リアルタイム) {k}: まとめ{len(m)}点", flush=True)


def on_decide(now, done):
    """購入係: decide_due が返した ['場-R:段階', ...] のうち「直前」のレースについて、裏でズレ屋の買い目を決める"""
    date = f"{now:%Y%m%d}"
    keys = [x.split(":")[0] for x in done or [] if x.endswith(":直前") and (date, x.split(":")[0]) not in _done]
    if not keys:
        return
    for k in keys:
        _done.add((date, k))
    threading.Thread(target=_run, args=(date, keys), daemon=True).start()
