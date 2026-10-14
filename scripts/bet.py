"""試験用の買い目: 締切前の3連単オッズ × 2・3着モデルの確率で、5通りの買い方を組む

・締切の約2〜9分前に1レース1回だけオッズを見に行き、買い目を data/bets/日付.json に保存する
・締切を過ぎたレースは書き換えない(予想と同じく封印)
・確率は「モデル」と「オッズから読んだ市場の確率」を混ぜたもの(BLEND)。モデル単独だと
  穴目を大きく過大評価していた(万舟帯で予測0.62%→実際0.12%)。市場の方がかなり正確なので重みは市場寄り
・買い方(予算はどれも1通り1,000〜2,000円、100円単位、確率に比例して配分):
    balance   バランス           頭自由・1頭×3艇6点。的中確率30%以上で期待回収率最大。100%未満は見送り
    in_hit    イン・的中重視      1コース頭・6点。的中確率最大。期待回収率80%未満は見送り
    in_ev     イン・期待値重視    1コース頭・6点。期待回収率最大。的中確率15%未満は見送り
    out_hit   イン以外・的中重視  1コース以外頭・1頭×4艇12点。的中確率最大。期待回収率70%未満は見送り
                                (穴寄りの頭は控除率がそのまま効くので、80%だとほぼ全部見送りになる)
    out_ana   イン以外・穴        1コース以外頭・60倍以上の目から期待値順に最大10点。記録のため見送りなし
    e2_top1   2連単・確率1位      展示の進入が枠なりでなく、頭注目が1以外のレースだけ、2連単の確率1位を1点1,000円。
                                  2025-26年の過去6,621Rで回収率102%(2025年99%・2026年106%、21か月中13か月で100%超)。
                                  オッズは使わずモデルの確率だけで選ぶ(過去検証と同じ条件)
    pick2     厳選頭2頭           pressed かつ 1コース1着確率22%未満のレースだけ対象。確率上位2艇
                                  (本命・次点)の**両方**が2.25〜50倍の目を持っている時だけ買う
                                  (片方しか無ければ見送り。実オッズ検証で片頭だけのレースは的中率14%・
                                  回収率65.7%と明確に弱かった)。それぞれ、期待値(確率×オッズ)が
                                  一番高い目の60%以上ある目(頭ごと最低2・最大5点)を拾い、その中で期待値に
                                  比例して予算(頭ごと2,000円、合計4,000円)を配分。点数はレースごとに
                                  期待値のばらつきで自然に変わる(合計4〜10点が中心)。
                                  (2025-26年21か月・実オッズ198Rの検証: nige<22%で回収率111.2%→両頭必須に
                                  してから113.1%。的中保証+紐均等という配分より、上位数点に期待値比例で
                                  配る方が明確に良かったので変更。点数の厳密な最適値は探索するとノイズを
                                  拾うだけだったので、安定して効く範囲(60%)に留めている)
    pickin    イン逃げ2連単・逆張り 1コース1着確率(nige)が80%以上のレースだけ対象。確率1位をそのまま買う
                                  旧ロジックは実オッズ検証(nige>=80%・フルセンサス1,130R)でROI87.2%と
                                  勝てなかった。市場のオッズ比(2位/1位)がモデルの確率比(1位/2位)を
                                  PICKIN_GAP_MIN以上上回ってる時(=市場が確率差以上に1位に寄せすぎてる時)
                                  だけ、2連単の確率2位の1点に予算4,000円を全額集中する逆張りに変更。
                                  (同条件・実オッズ58Rの検証: ROI146.6%、一番大きい的中3件を除いても110.2%)。
                                  月13件程度とかなり稀な条件(2026-10-14からこのロジックで運用開始)。
    pick2tan  外・2連単          1コース以外の頭候補(本命・次点)それぞれ、2連単の確率1位の目が確率20%以上の
                                  時だけその1点を買う(2026-10-15から。旧: pick2と同じ対象(pressed かつ
                                  nige<22%)で確率1位を買う形は、記録済み62Rの再生で64%と弱かった)。
                                  以下は旧ロジックの検証メモ:
                                  (2026年6-10月・実オッズ875Rの検証: pick2(3連単)が94.9%止まりだったのに対し、
                                  2連単にすると本命185%・次点215%・両方で200%。一番大きい的中5件を除いても
                                  118%で、予測確率と実際の的中率もほぼ一致(過大評価なし)。pickinと同じ
                                  「2連単市場は3連単市場より値付けが甘い」構造がpick2側にもあったとみられる)
    pickbin   B級イン・2連単      1コースが「本物の」B級(勝率5.5未満、かつ直近3年にA級だった期がない=F明けなどで
                                  一時的にB級になった実力者を除く)で、モデルの1コース1着確率がPICKBIN_HP_MIN以上の
                                  レースだけ。1コース頭で、2着はモデルの確率上位2艇の2点(1位1,600円・2位2,400円)。
                                  外枠(4〜6コース)のA級は2着候補から外す(市場に買われすぎていて、2着に置いた
                                  目は回収率69%。外すと113%→117%)。
                                  (2026-10-02〜13・実オッズ1,659Rの検証: 本物B級インの1着率は実際38.4%に対し市場
                                  (3連単オッズから逆算)は29.5%と、市場が大きく割り引いていた。モデル20%以上の
                                  214Rでは実際39.3%・市場28.9%・モデル37.2%。2着の指定は1艇(1点)105%・2艇113%・
                                  3艇98%で、2艇が一番良かった(301R、90%区間93〜134%)。
                                  嘘B級は逆にモデルが過大評価(モデル43%→実際37%)していたので除外。
                                  まだサンプルが小さいので、本番で貯めて確かめるための試験プラン)
例: python scripts/bet.py   (entry.pyから毎回呼ばれる)
"""
import datetime as dt
import functools
import itertools
import json
import re
import time
import urllib.request

import numpy as np
import pandas as pd

from common import DATA, JST, UA, now_jst
from place import PERMS

URL = "https://www.boatrace.jp/owpc/pc/race/odds3t?rno={race}&jcd={jcd}&hd={date}"
ODDS_RE = re.compile(r'class="oddsPoint[^"]*">([^<]*)<')
BLEND = (0.13, 0.99)    # 確率の混ぜ方(モデル, 市場)の重み。2025-26年のランダム1,500レースの締切時オッズで推定(モデル0.13±0.05)
WINDOW = (2, 9)         # 締切の何分前のレースを対象にするか
ANA_ODDS = 60           # 穴狙いの対象にするオッズの下限
ANA_MAX = 10            # 穴狙いの最大点数
PLANS = {"balance": "バランス", "in_hit": "イン・的中重視", "in_ev": "イン・期待値重視",
         "out_hit": "イン以外・的中重視", "out_ana": "イン以外・穴", "e2_top1": "2連単・確率1位(進入変化×頭注目≠1)",
         "pick2": "厳選頭2頭(本命・次点)", "pickin": "イン逃げ2連単・逆張り(確率2位)",
         "pick2tan": "外・2連単(確率20%以上の本命頭)", "pickbin": "B級イン・2連単(2着2艇)"}
PICK2_NIGE_MAX = 0.22   # pressedの中でもこれ未満だけ対象(実オッズ検証: 頻度と回収率のバランスで22%に)
PICK2_MIN_ODDS = 2.25   # 5分前時点オッズなので、損益分岐の2倍より変動分の余裕を見て高め
PICK2_MAX_ODDS = 50     # これを超える穴目は除外(過大評価しがちで実オッズ検証でも回収率を下げていた)
PICK2_HEAD_BUDGET = 2000   # 本命・次点それぞれに配る予算(合計4,000円)。資金サイズ自体は回収率に
                           # 影響しない(実オッズ検証で確認済み)ので、好みで変えてよい
PICK2_EV_RATIO = 0.6    # 頭ごと、期待値が一番高い目のこの割合以上ある目を全部拾う(点数をレースで可変に)
PICK2_MIN_TICKETS = 2   # ↑に満たなくても最低これだけは拾う
PICK2_MAX_TICKETS = 5   # ↑の上限
PICK2_LOGIC_SINCE = "20261011"   # このロジックに変えた日(運用タブはこれ以降の実績だけ見る)
                        # (的中保証+紐均等より、上位数点に期待値比例配分の方が実オッズ検証で明確に良かった。
                        # 点数の厳密な最適値はノイズに乗るだけだったので、安定して効く60%に留めている)
PICKIN_NIGE_MIN = 0.80   # 1コース1着確率がこれ以上のレースだけ対象(逆張りgapシグナルは0.80以上でしか
                         # 検証してないため、旧ロジックの0.70から引き上げ)
PICKIN_GAP_MIN = 1.0     # 市場のオッズ比(2位/1位)がモデルの確率比(1位/2位)をこれだけ上回ったら、
                         # 「市場が確率差以上に1位に寄せすぎ」と判断して2位を狙う(実オッズ検証でgap>=1
                         # がROI146.6%・上位3件除いても110.2%と頑丈だった)
PICKIN_MIN_ODDS = 1.5    # 2連単オッズの下限
PICKIN_BUDGET = 4000     # 確率2位の1点に全額集中
PICKIN_LOGIC_SINCE = "20261015"   # 運用タブの集計開始日(3プランそろえて仕切り直し。逆張りロジックは10/14から)
PICK2TAN_BUDGET = 4000   # 1レースの予算。本命・次点の両方が対象なら半分ずつ
                              # (合計4,000円。実オッズ検証で両頭合計200%、一番大きい的中5件を除いても118%)
PICK2TAN_PROB_MIN = 0.20     # 外の頭の2連単確率1位がこれ以上の時だけ買う
PICK2TAN_LOGIC_SINCE = "20261015"   # 運用タブの集計をここから開始(3プランそろえて仕切り直し)
PICKBIN_HP_MIN = 0.20      # 1コース(本物B級)の1着確率がこれ以上のレースだけ対象
PICKBIN_FAKE_WIN = 5.5     # B級でも全国勝率がこれ以上なら「嘘B級」(F休み明けなどで一時的にB級の実力者)
PICKBIN_FAKE_MONTHS = 36   # 直近この月数の番組表で1度でもA級だった選手も「嘘B級」
PICKBIN_UNITS = (16, 24)   # 2着の確率1位・2位に何口ずつ(合計4,000円)。2位の方が配当が良く回収率も
                           # 高かった(1位のみ105%・2位のみ118%)ので2位を厚めに。均等111%→この配分113%
PICKBIN_LOGIC_SINCE = "20261015"   # 運用タブの集計開始日(3プランそろえて仕切り直し)
M = ["逃げ", "まくり", "差し", "まくり差し"]

# 公式オッズ表の並び: 20行×6列(列=1着の枠)。列の中は(2着,3着)の昇順
ODDS_ORDER = [None] * 120
for _c in range(6):
    for _r, (_j, _k) in enumerate((j, k) for j in range(6) for k in range(6) if len({_c, j, k}) == 3):
        ODDS_ORDER[_r * 6 + _c] = (_c, _j, _k)
PI = {p: i for i, p in enumerate(PERMS)}

# 2連単(odds2tfページ、3連単と同じ形式だが6列×5行)。ページの先頭30個が2連単、続く15個は2連複
URL2 = "https://www.boatrace.jp/owpc/pc/race/odds2tf?rno={race}&jcd={jcd}&hd={date}"
ODDS2_ORDER = [None] * 30
for _c in range(6):
    for _r, _j in enumerate(x for x in range(6) if x != _c):
        ODDS2_ORDER[_r * 6 + _c] = (_c, _j)


def _forms(heads, n):
    """1頭×n艇のフォーメーション一覧 [(頭, ヒモ, PERMSの添字)]"""
    return [(w, s, [PI[(w, a, b)] for a, b in itertools.permutations(s, 2)])
            for w in heads for s in itertools.combinations([x for x in range(6) if x != w], n)]


FORMS6 = _forms(range(6), 3)
FORMS_IN = _forms([0], 3)
FORMS_OUT = _forms(range(1, 6), 4)


def fetch_odds(date, jcd, race):
    """枠番の(1着,2着,3着)(0始まり) -> オッズ。取れなければNone"""
    try:
        req = urllib.request.Request(URL.format(race=race, jcd=jcd, date=date), headers=UA)
        with urllib.request.urlopen(req, timeout=40) as r:
            h = r.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    vals = ODDS_RE.findall(h)
    if len(vals) != 120:
        return None
    out = {}
    for combo, v in zip(ODDS_ORDER, vals):
        try:
            out[combo] = float(v)
        except ValueError:
            pass   # 欠場などで売っていない目
    return out


def fetch_odds2(date, jcd, race):
    """枠番の(1着,2着)(0始まり、2連単) -> オッズ。取れなければNone"""
    try:
        req = urllib.request.Request(URL2.format(race=race, jcd=jcd, date=date), headers=UA)
        with urllib.request.urlopen(req, timeout=40) as r:
            h = r.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    vals = ODDS_RE.findall(h)[:30]
    if len(vals) < 30:
        return None
    out = {}
    for combo, v in zip(ODDS2_ORDER, vals):
        try:
            out[combo] = float(v)
        except ValueError:
            pass
    return out


def blend(tri, odds_c):
    """モデルの確率と市場の確率(オッズの逆数を正規化)を混ぜる。売っていない目は0"""
    sold = np.array([o is not None and o > 0 for o in odds_c])
    q = np.where(sold, 1 / np.array([o if o else 1.0 for o in odds_c]), 0)
    q = q / q.sum()
    s = np.full(120, -np.inf)
    s[sold] = BLEND[0] * np.log(np.asarray(tri)[sold] + 1e-9) + BLEND[1] * np.log(q[sold])
    e = np.exp(s - s[sold].max())
    return e / e.sum()


def _units(pp, total, cap=2000):
    """確率に比例して100円単位で配分(最低1口、上限capを超えないよう調整)"""
    hit = sum(pp)
    units = [max(1, round(p / hit * total / 100)) for p in pp]
    while sum(units) * 100 > cap:
        units[units.index(max(units))] -= 1
    return units


def _form_stats(p, odds_c, idx):
    pp = [float(p[i]) for i in idx]
    hit = sum(pp)
    return pp, hit, sum(x * x * odds_c[i] for x, i in zip(pp, idx)) / hit   # 確率比例で買ったときの期待回収率


def pick(p, odds_c, forms, by, min_hit=0.0, min_ev=0.0):
    """formsの中から by('hit'|'ev')が最大のものを選ぶ。条件を満たさなければNone"""
    best = None
    for w, s, idx in forms:
        if any(odds_c[i] is None for i in idx):
            continue
        pp, hit, ev = _form_stats(p, odds_c, idx)
        if hit < min_hit or ev < min_ev:
            continue
        key = hit if by == "hit" else ev
        if best is None or key > best[0]:
            best = (key, w, s, idx, pp, hit, ev)
    return best and best[1:]


def plan(tri, odds_c):
    """コース基準の確率とオッズ(PERMS順)から5通りの買い目を作る。
    戻り値 {買い方: (頭, ヒモ, 添字, 口数, 的中確率, 期待回収率) or None(見送り)}"""
    p = blend(tri, odds_c)
    out = {}
    r = pick(p, odds_c, FORMS6, "ev", min_hit=0.30, min_ev=1.0)
    if r:
        w, s, idx, pp, hit, ev = r
        out["balance"] = (w, s, idx, _units(pp, 1000 + 1000 * min(1.0, (ev - 1.0) / 0.5)), hit, ev)
    for name, forms, by, mh, me, total in [("in_hit", FORMS_IN, "hit", 0, 0.8, 1000),
                                           ("in_ev", FORMS_IN, "ev", 0.15, 0, 1000),
                                           ("out_hit", FORMS_OUT, "hit", 0, 0.7, 1500)]:
        r = pick(p, odds_c, forms, by, mh, me)
        out[name] = r and (r[0], r[1], r[2], _units(r[3], total), r[4], r[5])
    cand = [i for i in range(120) if PERMS[i][0] != 0 and odds_c[i] and odds_c[i] >= ANA_ODDS]
    cand = sorted(cand, key=lambda i: -p[i] * odds_c[i])[:ANA_MAX]
    if cand:
        units = [2 if n < 5 else 1 for n in range(len(cand))]    # 期待値の高い上位5点は2口
        hit = float(sum(p[i] for i in cand))
        ev = float(sum(p[i] * odds_c[i] * u for i, u in zip(cand, units)) / sum(units))
        out["out_ana"] = (None, None, cand, units, hit, ev)
    else:
        out["out_ana"] = None
    return p, out


def _scenario(name, pred, p, w, s, idx, waku):
    """買い方ごとのシナリオの一文。勝つ確率は買い目と同じ混ぜた確率p、決まり手はモデルから"""
    P = pred["prob"]
    win = lambda c: float(sum(p[i] for i in range(120) if PERMS[i][0] == c))
    if w == 0:
        himo = "・".join(str(waku[x]) for x in s)
        return f"{waku[0]}号艇(1コース)が逃げる展開(1コースが勝つ確率{win(0):.0%})。2・3着は{himo}号艇の争い"
    if w is None:   # 穴: 一番多く入っている頭で説明する
        heads = [PERMS[i][0] for i in idx]
        w = max(set(heads), key=heads.count)
        lead = "1コースが崩れる波乱を想定。"
    else:
        lead = ""
    mv = max(range(1, 4), key=lambda m: P[w][m])
    tail = {"まくり": "内側の艇は叩かれやすく、外の艇が2・3着に続きやすい",
            "差し": "1コースは流れても2・3着に残りやすい",
            "まくり差し": "内と外の間を割って抜ける形"}[M[mv]]
    return f"{lead}{waku[w]}号艇({w + 1}コース)の{M[mv]}が決まる展開(この艇が勝つ確率{win(w):.0%})。{tail}"


def _pick2(pred, p, odds_c, waku):
    """厳選・逃げないレース専用(狙い目タブのpick.htmlより厳しいnige<PICK2_NIGE_MAX)。
    確率上位2艇(本命・次点)それぞれ、2.25〜50倍の目のうち期待値(確率×オッズ)が一番高い目の
    PICK2_EV_RATIO以上ある目(最低PICK2_MIN_TICKETS・最大PICK2_MAX_TICKETS点)を拾い、
    その中で期待値に比例して予算(頭ごとPICK2_HEAD_BUDGET円)を配分する。点数はレースごとに
    期待値のばらつきで自然に変わる。
    (的中時10,000円保証+紐は均等100円、という以前の配分より、上位数点に期待値比例で配る方が
    実オッズ検証で明確に回収率が良かった)"""
    sc = pred["scene"]
    if not (sc["pressed"] and sc["nige"] < PICK2_NIGE_MAX):
        return dict(skip=True)
    hp = sc["head_prob"]
    heads = sorted(range(1, 6), key=lambda k: -hp[k])[:2]
    label = {w: ("本命" if i == 0 else "次点") for i, w in enumerate(heads)}
    cand_by_head = {}
    for w in heads:
        cand = [i for i in range(120) if PERMS[i][0] == w and odds_c[i]
                and PICK2_MIN_ODDS <= odds_c[i] <= PICK2_MAX_ODDS]
        if cand:
            cand_by_head[w] = cand
    if len(cand_by_head) < 2:
        # 本命・次点どちらかしかオッズ圏内に入らないレースは、片頭だけで無理に買わず見送る
        # (実オッズ検証で、片頭だけのレースは的中率14%・回収率65.7%と明確に弱かった)
        return dict(skip=True)
    tickets = []   # (idx, units, role) の順
    used_heads = []
    for w in heads:
        cand = cand_by_head[w]
        cand_ev = sorted(((p[i] * odds_c[i], i) for i in cand), reverse=True)
        best_ev = cand_ev[0][0]
        idx = [i for ev, i in cand_ev if ev >= best_ev * PICK2_EV_RATIO][:PICK2_MAX_TICKETS]
        if len(idx) < PICK2_MIN_TICKETS:
            idx = [i for ev, i in cand_ev][:PICK2_MIN_TICKETS]
        used_heads.append(w)
        w8 = [p[i] * odds_c[i] for i in idx]   # 期待値に比例して配分
        tot = sum(w8)
        units = [max(1, round(x / tot * PICK2_HEAD_BUDGET / 100)) for x in w8]
        while sum(units) * 100 > PICK2_HEAD_BUDGET:
            units[units.index(max(units))] -= 1
        for rank, (i, u) in enumerate(zip(idx, units)):
            if u > 0:
                tickets.append((i, u, f"{label[w]}・{'本線' if rank == 0 else f'{rank + 1}位'}"))
    if not tickets:
        return dict(skip=True)
    idxs, units, roles = zip(*tickets)
    pp = [float(p[i]) for i in idxs]
    hit = float(sum(pp))
    stake = sum(units) * 100
    ev = float(sum(x * u * odds_c[i] for x, u, i in zip(pp, units, idxs)) / hit) if hit else 0.0
    parts = [f"{label[w]}は{waku[w]}号艇" for w in used_heads]
    scenario = (f"頭候補は確率上位2艇({'・'.join(parts)})。それぞれ、5分前時点のオッズが{PICK2_MIN_ODDS}〜{PICK2_MAX_ODDS}倍の目のうち、"
                f"期待値(確率×オッズ)が一番高い目の{PICK2_EV_RATIO:.0%}以上ある目を拾い、その中で期待値に比例して予算"
                f"(頭ごと{PICK2_HEAD_BUDGET:,}円)を配分しています")
    return dict(skip=False, head=None, himo=None, ev=round(ev, 3), hit=round(hit, 3), stake=stake,
                scenario=scenario,
                tickets=[dict(combo="-".join(str(waku[c]) for c in PERMS[i]), units=u, odds=odds_c[i],
                              prob=round(float(p[i]), 4), role=role) for i, u, role in zip(idxs, units, roles)])


def _pickin(pred, p, odds2_w, waku):
    """イン(1コースが堅いレース)専用・逆張り: 1コース1着確率(nige)がPICKIN_NIGE_MIN以上の時だけ、
    2連単の確率1位・2位を比べる。市場のオッズ比(2位オッズ/1位オッズ)が、モデルの確率比
    (1位確率/2位確率)をPICKIN_GAP_MIN以上上回っていたら、「市場がモデルの確率差以上に1位へ
    寄せすぎている」とみなし、2位の1点に予算を全額集中する(条件を満たさなければ見送り)。
    確率は3連単の確率(モデルとオッズのブレンド)を3着で足し上げたもの"""
    sc = pred["scene"]
    if sc["nige"] < PICKIN_NIGE_MIN or not odds2_w:
        return dict(skip=True, bet="2t")
    cand = []
    for j in range(1, 6):
        o = odds2_w.get((waku[0] - 1, waku[j] - 1))   # 2連単オッズは枠番で並んでいる
        if o is None:
            continue
        p2 = sum(p[PI[(0, j, k)]] for k in range(6) if k not in (0, j))
        cand.append((p2, j, o))
    if len(cand) < 2:
        return dict(skip=True, bet="2t")
    cand.sort(reverse=True)
    p1, j1, o1 = cand[0]
    p2, j2, o2 = cand[1]
    if o2 < PICKIN_MIN_ODDS:
        return dict(skip=True, bet="2t")
    our_ratio = p1 / p2 if p2 > 0 else 10.0
    mkt_ratio = o2 / o1 if o1 > 0 else 0.0
    gap = mkt_ratio - our_ratio
    if gap < PICKIN_GAP_MIN:
        return dict(skip=True, bet="2t")
    units = max(1, round(PICKIN_BUDGET / 100))
    return dict(skip=False, bet="2t", head=waku[0], himo=None, ev=round(p2 * o2, 3), hit=round(p2, 3),
                stake=units * 100,
                scenario=f"{waku[0]}号艇(1コース)が逃げて{waku[j2]}号艇が続く展開の逆張り1点"
                         f"(確率{p2:.0%}・オッズ{o2:.1f}倍。市場は{waku[j1]}号艇にモデルの確率差以上に"
                         f"寄せていた=gap{gap:.2f})",
                tickets=[dict(combo=f"{waku[0]}-{waku[j2]}", units=units, odds=o2, prob=round(p2, 4))])


def _pick2tan_picks(pred, p):
    """1コース以外の頭候補(確率上位2艇=本命・次点)それぞれ、2連単の確率1位の目のうち、
    確率がPICK2TAN_PROB_MIN以上のものだけ [(頭, 2着, 確率, 本命/次点)] (コース基準)"""
    hp = pred["scene"]["head_prob"]
    heads = sorted(range(1, 6), key=lambda k: -hp[k])[:2]
    out = []
    for rank, w in enumerate(heads):
        p2, j = max((sum(p[PI[(w, j, k)]] for k in range(6) if k not in (w, j)), j) for j in range(6) if j != w)
        if p2 >= PICK2TAN_PROB_MIN:
            out.append((w, j, float(p2), "本命" if rank == 0 else "次点"))
    return out


def _pick2tan(pred, p, odds2_w, waku):
    """1コース以外の艇がはっきり本命のレース専用の2連単。頭候補(本命・次点)それぞれ、2連単の確率1位の
    目が確率PICK2TAN_PROB_MIN以上の時だけ、その1点を買う。
    (旧: pressed かつ nige<22% のレースで確率1位を買う形は、記録済み62Rの再生で回収率64%。
    市場は外の艇を買いかぶっていて、「インが崩れそう」なレースほど外の目が割高だった。外の頭の2連単
    1,307R・2,614点のうち、確率20%以上の目だけが108%(79点・1日約8点)だったので、そこに絞った)"""
    if not odds2_w:
        return dict(skip=True, bet="2t")
    tickets = []
    for w, j, p2, role in _pick2tan_picks(pred, p):
        o = odds2_w.get((waku[w] - 1, waku[j] - 1))   # 2連単オッズは枠番で並んでいる
        if o is None:
            continue
        tickets.append(dict(combo=f"{waku[w]}-{waku[j]}", units=0, odds=o, prob=round(p2, 4), role=role))
    if not tickets:
        return dict(skip=True, bet="2t")
    for t in tickets:   # 1レースPICK2TAN_BUDGET円を対象の目で均等に
        t["units"] = PICK2TAN_BUDGET // 100 // len(tickets)
    hit = float(sum(t["prob"] for t in tickets))
    stake = sum(t["units"] for t in tickets) * 100
    ev = float(sum(t["prob"] * t["units"] * t["odds"] for t in tickets) / sum(t["prob"] for t in tickets))
    parts = [f"{t['role']}は{t['combo']}" for t in tickets]
    scenario = (f"1コース以外の艇がはっきり本命のレース。2連単の確率が{PICK2TAN_PROB_MIN:.0%}以上の目だけ"
                f"({'・'.join(parts)})")
    return dict(skip=False, bet="2t", head=None, himo=None, ev=round(ev, 3), hit=round(hit, 3), stake=stake,
                scenario=scenario, tickets=tickets)


@functools.lru_cache(maxsize=1)
def _grade_history():
    """登録番号 -> {年月: 級}。番組表の記録から(嘘B級の判定用)"""
    fr = [pd.read_parquet(f, columns=["date", "toban", "grade"])
          for f in sorted((DATA / "programs").glob("*.parquet"))[-4:]]
    if not fr:
        return {}
    df = pd.concat(fr).drop_duplicates(["toban", "date"])
    hist = {}
    for toban, ym, g in zip(df.toban, df.date.str[:6], df.grade):
        hist.setdefault(toban, {})[ym] = g
    return hist


def real_b(boat, date):
    """本物のB級か。F明けなどで一時的にB級になっている実力者(全国勝率が高い・直近でA級だった)は除く"""
    if not boat["grade"].startswith("B") or boat["nat_win"] >= PICKBIN_FAKE_WIN:
        return False
    hist = _grade_history().get(boat["toban"], {})
    y, m = int(date[:4]), int(date[4:6])
    for k in range(1, PICKBIN_FAKE_MONTHS + 1):
        yy, mm = divmod(y * 12 + m - 1 - k, 12)
        if hist.get(f"{yy}{mm + 1:02d}", "B").startswith("A"):
            return False
    return True


def _pickbin_target(pred, date):
    """B級イン・2連単の対象レースか(2連単オッズを取りに行くかの判定にも使う)"""
    return bool(date) and pred["scene"]["head_prob"][0] >= PICKBIN_HP_MIN and real_b(pred["boats"][0], date)


def _pickbin(pred, odds2_w, waku, date):
    """1コースが本物のB級で、モデルの1コース1着確率がPICKBIN_HP_MIN以上のレースだけ、
    1コース頭・2着はモデルの確率上位2艇の2点を買う(1位PICKBIN_UNITS[0]口・2位PICKBIN_UNITS[1]口)。
    ただし外枠(4〜6コース)のA級は2着候補から外し、残りの上位2艇にする。
    市場はB級のインを割り引きすぎている(実オッズ1,659Rで実際の1着率38.4%に対し市場29.5%)ので、
    その分を取りに行く。2位の方が配当が良く回収率も高かったので2位を厚めに。
    片方のオッズが取れなければ、もう片方に全額"""
    if not _pickbin_target(pred, date) or not odds2_w:
        return dict(skip=True, bet="2t")
    sec = {}
    for p, (a, b, _) in zip(pred["tri"], PERMS):
        if a == 0:
            sec[b] = sec.get(b, 0) + p
    # 外枠(4〜6コース)のA級は市場に買われすぎていて、2着に置いた目は回収率69%と弱かったので2着候補から外す
    cand = [j for j in sorted(sec, key=sec.get, reverse=True)
            if not (j >= 3 and pred["boats"][j]["grade"].startswith("A"))]
    picks = []
    for rank, j in enumerate(cand[:2]):
        o = odds2_w.get((waku[0] - 1, waku[j] - 1))
        if o is not None:
            picks.append((j, o, PICKBIN_UNITS[rank], f"2着{rank + 1}位"))
    if not picks:
        return dict(skip=True, bet="2t")
    if len(picks) == 1:
        picks = [(picks[0][0], picks[0][1], sum(PICKBIN_UNITS), picks[0][3])]
    tickets = [dict(combo=f"{waku[0]}-{waku[j]}", units=u, odds=o, prob=round(sec[j], 4), role=role)
               for j, o, u, role in picks]
    hit = sum(sec[j] for j, *_ in picks)
    stake = sum(t["units"] for t in tickets) * 100
    ev = sum(sec[j] * o * u for j, o, u, _ in picks) / sum(u for *_, u, _ in picks)
    hp = pred["scene"]["head_prob"][0]
    b = pred["boats"][0]
    himo = "・".join(str(waku[j]) for j, *_ in picks)
    return dict(skip=False, bet="2t", head=waku[0], himo=None, ev=round(ev, 3), hit=round(hit, 4), stake=stake,
                scenario=f"{waku[0]}号艇(1コース・{b['grade']}・勝率{b['nat_win']:.2f})が逃げて{himo}号艇が続く展開"
                         f"(1コースの1着確率{hp:.0%}。市場はB級のインを割り引きがち)",
                tickets=tickets)


def make_bet(pred, odds_w, odds2_w=None, date=None):
    """予想(コース基準)と枠番オッズから、保存用の買い目(5通り)を作る"""
    waku = [b["waku"] for b in pred["boats"]]            # コース -> 枠番
    odds_c = [odds_w.get((waku[i] - 1, waku[j] - 1, waku[k] - 1)) for i, j, k in PERMS]
    p, plans = plan(pred["tri"], odds_c)
    out = {}
    for name in PLANS:
        if name in ("pick2", "pickin", "pick2tan", "pickbin"):
            continue
        r = plans.get(name)
        if r is None:
            out[name] = dict(skip=True)
            continue
        w, s, idx, units, hit, ev = r
        tickets = [dict(combo="-".join(str(waku[c]) for c in PERMS[i]), units=u, odds=odds_c[i],
                        prob=round(float(p[i]), 4), model=round(pred["tri"][i], 4))
                   for i, u in zip(idx, units)]
        out[name] = dict(skip=False, head=None if w is None else waku[w],
                         himo=None if s is None else [waku[x] for x in s],
                         ev=round(float(ev), 3), hit=round(float(hit), 3), stake=sum(units) * 100,
                         scenario=_scenario(name, pred, p, w, s, idx, waku), tickets=tickets)
    out["e2_top1"] = _exacta_top1(pred, waku)
    out["pick2"] = _pick2(pred, p, odds_c, waku)
    out["pickin"] = _pickin(pred, p, odds2_w, waku)
    out["pick2tan"] = _pick2tan(pred, p, odds2_w, waku)
    out["pickbin"] = _pickbin(pred, odds2_w, waku, date)
    # 締切前オッズそのもの(公式表の並び)も残す。締切時オッズとの差の分析用
    raw = [odds_w.get(c) for c in ODDS_ORDER]
    return dict(plans=out, odds=raw, cond=_conditions(pred, waku))


def _exacta_top1(pred, waku):
    """進入変化×頭注目≠1のときだけ、2連単の確率1位(3連単の確率を3着で足し合わせたもの)を1点買う"""
    maeduke = any(b["waku"] != b["course"] for b in pred["boats"])   # 展示の進入が枠なりでない
    if not maeduke or pred["scene"]["head"][0] == 0:
        return dict(skip=True, bet="2t")
    q = {}
    for p, (a, b, _) in zip(pred["tri"], PERMS):
        q[(a, b)] = q.get((a, b), 0) + p
    (a, b), p = max(q.items(), key=lambda kv: kv[1])
    return dict(skip=False, bet="2t", head=waku[a], himo=None, ev=None, hit=round(p, 3), stake=1000,
                scenario=None, tickets=[dict(combo=f"{waku[a]}-{waku[b]}", units=10, odds=None, prob=round(p, 4))])


def _conditions(pred, waku):
    """あとで「どんなレースで当たるか」を分析するための条件"""
    bs, sc = pred["boats"], pred["scene"]
    return dict(g1=bs[0]["grade"], na1=sum(b["grade"] == "A1" for b in bs),
                wingap=round(bs[0]["nat_win"] - max(b["nat_win"] for b in bs[1:]), 2),
                p1=round(sum(pred["prob"][0]), 3), head=[waku[k] for k in sc["head"]],
                pressed=sc["pressed"], stgap=round(min(pred["st"][1:]) - pred["st"][0], 3))


def run(now=None):
    now = now or now_jst()
    date = f"{now:%Y%m%d}"
    pp = DATA / "predictions" / f"{date}.json"
    if not pp.exists():
        return []
    preds = json.loads(pp.read_text())["races"]
    bp = DATA / "bets" / f"{date}.json"
    bp.parent.mkdir(parents=True, exist_ok=True)
    bets = json.loads(bp.read_text()) if bp.exists() else {}
    done = []
    for key, pred in preds.items():
        if key in bets or pred.get("version") != "final" or not pred.get("tri"):
            continue
        t = dt.datetime.strptime(date + pred["deadline"], "%Y%m%d%H:%M").replace(tzinfo=JST)
        if not (now + dt.timedelta(minutes=WINDOW[0]) < t <= now + dt.timedelta(minutes=WINDOW[1])):
            continue
        odds = fetch_odds(date, pred["jcd"], pred["race"])
        time.sleep(1.0)
        if not odds:
            continue
        odds2 = None
        sc = pred["scene"]
        waku = [b["waku"] for b in pred["boats"]]
        p = blend(pred["tri"], [odds.get((waku[i] - 1, waku[j] - 1, waku[k] - 1)) for i, j, k in PERMS])
        need_odds2 = (sc["nige"] >= PICKIN_NIGE_MIN or bool(_pick2tan_picks(pred, p))
                      or _pickbin_target(pred, date))
        if need_odds2:   # pickin・pick2tan・pickbin対象の時だけ2連単オッズも取りに行く
            odds2 = fetch_odds2(date, pred["jcd"], pred["race"])
            time.sleep(1.0)
        bets[key] = dict(make_bet(pred, odds, odds2, date), odds_at=now.strftime("%H:%M"))
        done.append(key)
    if done:
        bp.write_text(json.dumps(bets, ensure_ascii=False, indent=0))
    print(f"試験用買い目: {len(done)}レース {done}")
    return done


if __name__ == "__main__":
    run()
