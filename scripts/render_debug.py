"""調べもの用: 場の公式サイトをブラウザで開いて(ページを開いた後で読み込む作りにも対応)、オリジナル展示がどこにあるか探す(運用には使わない)
例: python scripts/render_debug.py out/ https://www.boatrace-toda.jp/ ...
・同じサイトの中だけ、文字かURLに「直前・展示・オリジナル・レース情報」などを含むリンクを2段までたどる。1サイト最大20ページ
・robots.txt で止められているURLは開かない。断られた(403など)ページはそれ以上たどらない
・ページの中身と、裏で読み込んだデータ(XHR・JSON)に「まわり足・一周・直線」があればURLを記録する
"""
import re
import sys
import time
import urllib.parse
import urllib.robotparser

from playwright.sync_api import sync_playwright

UA = "Mozilla/5.0 (kyotei-shikake research; headless)"
LINK = re.compile(r"直前|展示|オリジナル|レース情報|出走表|raceinfo|yosou|cyokuzen|chokuzen|tenji|before|race", re.I)
HIT = re.compile(r"まわり足|周回タイム|一周|オリジナル展示")


def main():
    out = sys.argv[1]
    idx = open(f"{out}/index.txt", "w")
    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(user_agent=UA)
        n = 0
        for start in sys.argv[2:]:
            host = urllib.parse.urlparse(start).netloc
            rp = urllib.robotparser.RobotFileParser(f"https://{host}/robots.txt")
            try:
                rp.read()
            except Exception:
                pass
            seen, todo, saved = set(), [(start, 0)], 0
            while todo and saved < 20:
                url, depth = todo.pop(0)
                if url in seen:
                    continue
                seen.add(url)
                try:
                    if not rp.can_fetch(UA, url):
                        idx.write(f"robots-NG {url}\n")
                        continue
                except Exception:
                    pass
                pg = ctx.new_page()
                hits = []
                pg.on("response", lambda r: hits.append(r.url) if r.request.resource_type in ("xhr", "fetch", "document") else None)
                try:
                    resp = pg.goto(url, wait_until="networkidle", timeout=40000)
                    st = resp.status if resp else 0
                    html = pg.content()
                except Exception as e:
                    idx.write(f"error {url} {e!r}\n")
                    pg.close()
                    continue
                txt_hit = bool(HIT.search(html))
                data_hit = []
                for u in hits:
                    if u == url or urllib.parse.urlparse(u).netloc != host:
                        continue
                    try:
                        body = ctx.request.get(u, timeout=20000).text()
                        if HIT.search(body):
                            data_hit.append(u)
                    except Exception:
                        pass
                open(f"{out}/p{n:04d}.html", "w").write(html)
                idx.write(f"p{n:04d} {st} text_hit={txt_hit} data_hit={data_hit[:5]} {url}\n")
                idx.flush()
                n += 1
                saved += 1
                if st >= 400 or depth >= 2:
                    pg.close()
                    continue
                for a in pg.query_selector_all("a[href]"):
                    try:
                        href, t = a.get_attribute("href"), a.inner_text()
                    except Exception:
                        continue
                    u = urllib.parse.urljoin(url, href or "")
                    if urllib.parse.urlparse(u).netloc == host and u not in seen and (LINK.search(u) or LINK.search(t or "")):
                        todo.append((u.split("#")[0], depth + 1))
                pg.close()
                time.sleep(1.5)
        br.close()


if __name__ == "__main__":
    main()
