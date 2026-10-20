"""競走成績(K)・番組表(B)のテキストを表に変換する"""
import re
import unicodedata

VENUES = {"01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川", "06": "浜名湖",
          "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
          "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島", "17": "宮島", "18": "徳山",
          "19": "下関", "20": "若松", "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村"}

K_HDR = re.compile(r"\s+(\d+)R\s+(\S+)\s+H(\d+)m\s+(\S+)\s+風\s+(\S+)\s+(\d+)m\s+波\s+(\d+)cm")
PAYOUT_RE = re.compile(r"(\d+)R\s+(\d-\d-\d)\s+(\d+)")
K_BOAT = re.compile(r"\s+(\S\S|\S )\s*(\d)\s+(\d{4})\s+(.{8})\s*(\d+)\s+(\d+)\s+([\d.]+)\s+(\d)\s+(\S+)")
B_HEAD = re.compile(r"^([1-6]) (\d{4})(.{4})(\d{2})(.{2})(\d{2})([AB][12])(.*)$")   # 数字の欄が崩れた時の予備(新モーターで2連率が空欄など)
B_BOAT = re.compile(r"^([1-6]) (\d{4})(.{4})(\d{2})(.{2})(\d{2})([AB][12])"
                    r"\s*(\d+\.\d{2})\s*(\d+\.\d{2})\s*(\d+\.\d{2})\s*(\d+\.\d{2})"  # 全国勝率・2率・当地勝率・2率
                    r"\s*(\d{1,3})\s*(\d+\.\d{2})\s*(\d{1,3})\s*(\d+\.\d{2})")  # モーター・2率・ボート・2率(桁が詰まることがある)


def st_value(s: str):
    """ST文字列を数値に。F(フライング)はマイナス、L・欠場などはNone"""
    if re.fullmatch(r"F\d*\.\d+", s):
        return -float(s[1:])
    if re.fullmatch(r"\d*\.\d+", s):
        return float(s)
    return None


def parse_results(text: str, date: str):
    """競走成績 → 1行=1艇"""
    rows = []
    for jcd, body in re.findall(r"(\d\d)KBGN(.*?)\d\dKEND", text, re.S):
        payout = {}
        pi = body.find("[払戻金]")
        if pi >= 0:
            pj = body.find("着 艇", pi)
            seg = body[pi:pj] if pj >= 0 else body[pi:pi + 2000]
            for r, combo, amt in PAYOUT_RE.findall(seg):
                payout[int(r)] = (combo, int(amt))
        race = None
        info = {}
        for line in body.splitlines():
            m = K_HDR.match(line)
            if m:
                race = int(m.group(1))
                combo3t, payout3t = payout.get(race, (None, None))
                info = dict(rtype=m.group(2), distance=int(m.group(3)), weather=m.group(4),
                            wind_dir=m.group(5), wind=int(m.group(6)), wave=int(m.group(7)), kimarite="",
                            combo3t=combo3t, payout3t=payout3t)
                continue
            if race and "ﾚｰｽﾀｲﾑ" in line:
                info["kimarite"] = line.split("ﾚｰｽﾀｲﾑ")[1].strip()
                continue
            m = K_BOAT.match(line)
            if m and race:
                st_raw = m.group(9)
                rows.append(dict(date=date, jcd=jcd, venue=VENUES.get(jcd, jcd), race=race, **info,
                                 rank=m.group(1).strip(), waku=int(m.group(2)), toban=m.group(3),
                                 name=m.group(4).replace("　", "").strip(), motor=int(m.group(5)),
                                 boat=int(m.group(6)), tenji=float(m.group(7)), course=int(m.group(8)),
                                 st=st_raw, stv=st_value(st_raw)))
    return rows


def _loose_boat(line):
    """B_BOATで読めない行を、欄を数字の並びとして読み直す。勝率4つ・モーター番号・ボート番号は必須、2連率は無ければ0"""
    m = B_HEAD.match(line)
    if not m:
        return None
    nums = re.findall(r"\d+\.\d{2}|\d+", m.group(8))
    if len(nums) < 6:
        return None
    rates, rest = nums[:4], nums[4:]
    if not all("." in x for x in rates):
        return None
    motor = rest[0]
    i = 1
    motor_2r = rest[i] if i < len(rest) and "." in rest[i] else "0.00"
    i += 1 if motor_2r != "0.00" or (i < len(rest) and "." in rest[i]) else 0
    boat = rest[i] if i < len(rest) else "0"
    boat_2r = rest[i + 1] if i + 1 < len(rest) and "." in rest[i + 1] else "0.00"
    if "." in motor or "." in boat:
        return None
    return m.groups()[:7] + tuple(rates) + (motor, motor_2r, boat, boat_2r)


def parse_program(text: str, date: str):
    """番組表 → 1行=1艇"""
    rows = []
    for jcd, body in re.findall(r"(\d\d)BBGN(.*?)\d\dBEND", text, re.S):
        n0 = len(rows)
        race = None
        rtype = ""
        deadline = ""
        head = unicodedata.normalize("NFKC", body[:1500])
        dm = re.search(r"第\s*(\d+)日", head)
        day = int(dm.group(1)) if dm else 0
        title = ""
        blines = body.splitlines()
        for i, ln in enumerate(blines[:12]):
            if "番組表" in ln:
                for nx in blines[i + 1:i + 5]:
                    if nx.strip():
                        title = unicodedata.normalize("NFKC", nx).strip()
                        break
                break
        for line in body.splitlines():
            z = unicodedata.normalize("NFKC", line)
            m = re.match(r"\s*(\d+)R\s+(\S+)", z)
            if m and "締切" in z:
                race, rtype = int(m.group(1)), m.group(2)
                dl = re.search(r"締切予定(\d{1,2}):(\d{2})", z)
                deadline = f"{int(dl.group(1)):02d}:{dl.group(2)}" if dl else ""
                continue
            m = B_BOAT.match(line)
            g = m.groups() if m else _loose_boat(line)
            if g and race:
                rows.append(dict(date=date, jcd=jcd, venue=VENUES.get(jcd, jcd), race=race, rtype=rtype,
                                 deadline=deadline, day=day, title=title, waku=int(g[0]), toban=g[1], name=g[2].replace("　", ""), age=int(g[3]),
                                 branch=g[4].replace("　", ""), weight=int(g[5]), grade=g[6],
                                 nat_win=float(g[7]), nat_2r=float(g[8]), loc_win=float(g[9]),
                                 loc_2r=float(g[10]), motor=int(g[11]), motor_2r=float(g[12]),
                                 boat=int(g[13]), boat_2r=float(g[14])))
        if len(rows) == n0:   # 場がまるごと読めなかった時は、どんな行か分かるように少し出す
            samp = [unicodedata.normalize("NFKC", x) for x in body.splitlines() if re.match(r"^[1-6] \d{4}", x)][:3]
            print(f"番組表: {date} 場{jcd}が読めませんでした。選手の行の例: {samp}")
    return rows
