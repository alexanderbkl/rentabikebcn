"""Offline mirror of rentabikebcn.com (stdlib only).

Usage: python scripts/clone_site.py
Output: ./clone/ (open clone/index.html or `python -m http.server -d clone`)
"""
import hashlib
import json
import os
import posixpath
import re
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from urllib.parse import quote, urljoin, urldefrag, urlsplit, unquote

ROOT = "https://www.rentabikebcn.com/"
HOSTS = {"rentabikebcn.com", "www.rentabikebcn.com"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "clone")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
TEXT_EXT = {".html", ".htm", ".css"}
ASSET_RE = r"\.(?:png|jpe?g|gif|svg|webp|ico|css|js|woff2?|ttf|eot|otf|mp4|webm|mp3|pdf|html?|json|xml)"

ATTR_RE = re.compile(
    r"""(\b(?:href|src|data-src|data-original|poster|data-background|background|action|data|content)\s*=\s*)(["'])(.*?)\2""",
    re.I | re.S,
)
SRCSET_RE = re.compile(r"""(\b(?:srcset|data-srcset)\s*=\s*)(["'])(.*?)\2""", re.I | re.S)
CSS_URL_RE = re.compile(r"""url\(\s*(["']?)(.*?)\1\s*\)""", re.I | re.S)
CSS_IMPORT_RE = re.compile(r"""@import\s+(["'])(.*?)\1""", re.I)
JS_STR_RE = re.compile(r"""["']([^"'\s<>]+?""" + ASSET_RE + r""")(?:\?[^"'\s]*)?["']""", re.I)

pages = {}      # url -> local relative path (posix)
meta = {}       # url -> content-type
failed = {}


def norm(url):
    url, _ = urldefrag(url.strip())
    p = urlsplit(url)
    if p.scheme not in ("http", "https"):
        return None
    host = p.netloc.lower()
    if host not in HOSTS:
        return None
    path = p.path or "/"
    if " " in path or ";charset" in path or "'" in path:
        return None
    q = ("?" + p.query) if p.query else ""
    return f"https://www.rentabikebcn.com{path}{q}"


def local_path(url, ctype=""):
    p = urlsplit(url)
    path = unquote(p.path)
    if path.endswith("/") or not path:
        path += "index.html"
    root, ext = posixpath.splitext(path)
    if not ext and "html" in ctype:
        path += ".html"
    if p.query:
        h = hashlib.md5(p.query.encode()).hexdigest()[:8]
        root, ext = posixpath.splitext(path)
        path = f"{root}__{h}{ext}"
    path = re.sub(r'[<>:"|?*]', "_", path)
    return path.lstrip("/")


def fetch(url):
    safe_url = quote(url, safe="/:?=&%+~@!$'()*,;")
    req = urllib.request.Request(safe_url, headers={"User-Agent": UA, "Accept": "*/*"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.geturl(), r.headers.get("Content-Type", ""), r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 403, 410):
                raise
        except Exception:
            pass
        time.sleep(1.5)
    raise RuntimeError("fetch failed")


def decode(data, ctype):
    m = re.search(r"charset=([\w-]+)", ctype, re.I)
    for enc in ([m.group(1)] if m else []) + ["utf-8", "cp1252"]:
        try:
            return data.decode(enc), enc
        except Exception:
            continue
    return data.decode("utf-8", "ignore"), "utf-8"


def extract(text, base, is_css, is_js=False):
    found = []
    if is_js:
        for m in JS_STR_RE.finditer(text):
            found.append(m.group(1))
        return found
    if not is_css:
        for m in ATTR_RE.finditer(text):
            found.append(m.group(3))
        for m in SRCSET_RE.finditer(text):
            for part in m.group(3).split(","):
                if part.strip():
                    found.append(part.strip().split()[0])
    for m in CSS_URL_RE.finditer(text):
        found.append(m.group(2))
    for m in CSS_IMPORT_RE.finditer(text):
        found.append(m.group(2))
    return found


def crawl():
    queue = deque([norm(ROOT + "index.html"), norm(ROOT)])
    for extra in ("sitemap.xml", "robots.txt"):
        queue.append(norm(ROOT + extra))
    seen = set(queue)
    texts = {}
    while queue:
        url = queue.popleft()
        try:
            final, ctype, data = fetch(url)
        except Exception as e:
            failed[url] = str(e)
            print("FAIL", url, e)
            continue
        fnorm = norm(final)
        if fnorm is None:
            failed[url] = f"redirected off-site to {final}"
            continue
        if fnorm != url and fnorm in pages:
            pages[url] = pages[fnorm]
            continue
        lp = local_path(fnorm, ctype)
        ext = posixpath.splitext(lp)[1].lower()
        dest = os.path.join(OUT, *lp.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        pages[url] = lp
        pages[fnorm] = lp
        meta[fnorm] = ctype
        print("OK  ", lp, len(data))

        is_css = ext == ".css" or "text/css" in ctype
        is_html = ext in (".html", ".htm") or "html" in ctype
        is_js = ext == ".js" or "javascript" in ctype
        is_xml = ext == ".xml" or "xml" in ctype
        if not (is_css or is_html or is_js or is_xml or ext == ".txt"):
            continue
        text, enc = decode(data, ctype)
        if is_html or is_css:
            texts[lp] = (fnorm, enc, is_css)
        if is_xml or ext == ".txt":
            refs = re.findall(r"https?://[^\s<>\"']+", text)
        else:
            refs = extract(text, fnorm, is_css, is_js)
        for r in refs:
            r = r.strip()
            if not r or r.startswith(("data:", "mailto:", "tel:", "javascript:", "#")):
                continue
            full = norm(urljoin(fnorm, r))
            if full is None and is_js and not r.startswith("http"):
                full = norm(urljoin(ROOT, r))
            if full and full not in seen:
                seen.add(full)
                queue.append(full)
    return texts


def rewrite(texts):
    for lp, (base, enc, is_css) in texts.items():
        dest = os.path.join(OUT, *lp.split("/"))
        with open(dest, "rb") as f:
            text, _ = decode(f.read(), f"charset={enc}")
        here = posixpath.dirname(lp)

        def fix(ref):
            r = ref.strip()
            if not r or r.startswith(("data:", "mailto:", "tel:", "javascript:", "#")):
                return ref
            frag = ""
            if "#" in r:
                r, frag = r.split("#", 1)
                frag = "#" + frag
            full = norm(urljoin(base, r))
            if full is None or full not in pages:
                return ref
            rel = posixpath.relpath(pages[full], here or ".")
            return rel.replace(" ", "%20") + frag

        def attr(m):
            return f"{m.group(1)}{m.group(2)}{fix(m.group(3))}{m.group(2)}"

        def srcset(m):
            parts = []
            for p in m.group(3).split(","):
                bits = p.strip().split()
                if bits:
                    bits[0] = fix(bits[0])
                    parts.append(" ".join(bits))
            return f"{m.group(1)}{m.group(2)}{', '.join(parts)}{m.group(2)}"

        def cssurl(m):
            return f"url({m.group(1)}{fix(m.group(2))}{m.group(1)})"

        def cssimp(m):
            return f"@import {m.group(1)}{fix(m.group(2))}{m.group(1)}"

        if not is_css:
            text = ATTR_RE.sub(attr, text)
            text = SRCSET_RE.sub(srcset, text)
        text = CSS_URL_RE.sub(cssurl, text)
        text = CSS_IMPORT_RE.sub(cssimp, text)
        with open(dest, "w", encoding=enc, errors="xmlcharrefreplace", newline="") as f:
            f.write(text)


def fix_muse_runtime():
    """Adobe Muse loads its scripts via RequireJS paths and a dead CDN; fetch them and drop the CDN."""
    sdir = os.path.join(OUT, "scripts")
    names = ["museconfig.js", "jquery-1.8.3.min.js", "museutils.js"]
    cfg = None
    for n in names:
        try:
            _, _, data = fetch(ROOT + "scripts/" + n)
        except Exception:
            continue
        with open(os.path.join(sdir, n), "wb") as f:
            f.write(data)
        if n == "museconfig.js":
            cfg = data.decode("utf-8", "ignore")
    if cfg:
        for n in re.findall(r'scripts/([\w.\-]+\.js)\?crc=', cfg):
            dest = os.path.join(sdir, n)
            if os.path.exists(dest):
                continue
            try:
                _, _, data = fetch(ROOT + "scripts/" + n)
                with open(dest, "wb") as f:
                    f.write(data)
            except Exception:
                pass  # listed by Muse but not deployed
        cfg = cfg.replace(
            'if(true&&document.location.protocol!="https:")c.paths.jquery=["http://musecdn.businesscatalyst.com/scripts/4.0/jquery-1.8.3.min",c.paths.jquery];',
            "",
        )
        with open(os.path.join(sdir, "museconfig.js"), "w", encoding="utf-8", newline="") as f:
            f.write(cfg)
    cdn = re.compile(
        r"""if \(document\.location\.protocol != 'https:'\) document\.write\('\\x3Cscript src="http://musecdn\.businesscatalyst\.com/scripts/4\.0/jquery-1\.8\.3\.min\.js" type="text/javascript">\\x3C/script>'\);"""
    )
    for root, _, files in os.walk(OUT):
        for fn in files:
            if fn.endswith(".html"):
                p = os.path.join(root, fn)
                with open(p, "rb") as f:
                    raw = f.read()
                new = cdn.sub("", raw.decode("latin-1")).encode("latin-1")
                if new != raw:
                    with open(p, "wb") as f:
                        f.write(new)


def main():
    os.makedirs(OUT, exist_ok=True)
    texts = crawl()
    rewrite(texts)
    fix_muse_runtime()
    manifest = {
        "files": sorted(set(pages.values())),
        "failed": failed,
    }
    with open(os.path.join(OUT, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nDone: {len(manifest['files'])} files, {len(failed)} failures")


if __name__ == "__main__":
    sys.exit(main())
