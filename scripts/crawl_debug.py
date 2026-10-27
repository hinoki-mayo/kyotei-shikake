"""調べもの用: 各場の公式サイトを少しだけたどって、展示・直前情報らしいページを保存する(運用には使わない)
例: python scripts/crawl_debug.py out/ https://www.boatrace-tokoname.jp/ ...
・同じサイトの中だけ、URLか文字に「展示・直前・オリジナル・tenji・before・race」などを含むリンクを2段までたどる
・1サイト最大25ページ、1ページごとに1.5秒あける。robots.txt で止められているURLは取らない
"""
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser

UA = {"User-Agent": "Mozilla/5.0 (kyotei-shikake research)"}
KEY = re.compile(r"展示|直前|オリジナル|周回|まわり足|一周|tenji|before|chokuzen|original|orig|Race|race|yosou|syusso|shusso|syutujo", re.I)


def get(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        for enc in ("utf-8", "shift_jis", "euc-jp"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                pass
        return raw.decode("utf-8", errors="replace")
    except Exception as e:
        return None


def crawl(start, out, n0):
    host = urllib.parse.urlparse(start).netloc
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"https://{host}/robots.txt")
    try:
        rp.read()
    except Exception:
        pass
    seen, todo, saved = set(), [(start, 0)], []
    while todo and len(saved) < 25:
        url, depth = todo.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            if not rp.can_fetch(UA["User-Agent"], url):
                continue
        except Exception:
            pass
        h = get(url)
        time.sleep(1.5)
        if h is None:
            continue
        n = n0 + len(saved)
        open(f"{out}/p{n:04d}.html", "w").write(h)
        saved.append(url)
        if depth >= 2:
            continue
        for href, text in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', h, re.S):
            u = urllib.parse.urljoin(url, href)
            if urllib.parse.urlparse(u).netloc != host or u in seen:
                continue
            t = re.sub(r"<[^>]+>", "", text)
            if KEY.search(u) or KEY.search(t):
                todo.append((u, depth + 1))
        for m in re.findall(r'location\.href\s*=\s*"([^"]+)"', h):
            todo.append((urllib.parse.urljoin(url, m), depth + 1))
    return saved


def main():
    out = sys.argv[1]
    n = 0
    with open(f"{out}/index.txt", "w") as idx:
        for start in sys.argv[2:]:
            got = crawl(start, out, n)
            for i, u in enumerate(got):
                idx.write(f"p{n + i:04d}.html {u}\n")
            n += len(got)
            print(start, len(got), flush=True)


if __name__ == "__main__":
    main()
