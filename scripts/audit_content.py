"""Extract text, contact data and an image inventory from ./clone into ./audit."""
import csv
import html
import json
import os
import re
import struct
from html.parser import HTMLParser

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CLONE = os.path.join(BASE, "clone")
AUDIT = os.path.join(BASE, "audit")


class TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.title, self.in_title = [], 0, "", False
        self.meta = {}
        self.imgs = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag == "meta" and a.get("name") in ("description", "keywords"):
            self.meta[a["name"]] = a.get("content", "")
        if tag == "img":
            self.imgs.append((a.get("src") or a.get("data-src") or "", a.get("alt", "")))
            if a.get("alt", "").strip():
                self.out.append(f"[img alt: {a['alt'].strip()}]")
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1
        if tag == "title":
            self.in_title = False
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.out.append(data)


def read(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "ignore")


def image_size(path):
    try:
        with open(path, "rb") as f:
            h = f.read(32)
            if h[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", h[16:24])
            if h[:6] in (b"GIF87a", b"GIF89a"):
                return struct.unpack("<HH", h[6:10])
            if h[:2] == b"\xff\xd8":
                f.seek(2)
                while True:
                    b = f.read(1)
                    while b and b != b"\xff":
                        b = f.read(1)
                    while b == b"\xff":
                        b = f.read(1)
                    if not b:
                        return None
                    marker = b[0]
                    if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                        f.read(3)
                        hh, ww = struct.unpack(">HH", f.read(4))
                        return ww, hh
                    ln = struct.unpack(">H", f.read(2))[0]
                    f.seek(ln - 2, 1)
    except Exception:
        return None
    return None


def main():
    os.makedirs(os.path.join(AUDIT, "pages_text"), exist_ok=True)
    summary = {"pages": [], "emails": set(), "phones": set(), "social": set(), "addresses": set()}
    for root, _, files in os.walk(CLONE):
        for fn in files:
            if not fn.endswith(".html"):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, CLONE).replace("\\", "/")
            text = read(path)
            p = TextExtractor()
            p.feed(text)
            body = html.unescape("".join(p.out))
            body = re.sub(r"[ \t\u00a0]+", " ", body)
            body = re.sub(r"\n\s*\n+", "\n", body).strip()
            out = os.path.join(AUDIT, "pages_text", rel.replace("/", "__") + ".txt")
            with open(out, "w", encoding="utf-8") as f:
                f.write(f"URL: {rel}\nTITLE: {p.title.strip()}\nDESCRIPTION: {p.meta.get('description', '')}\n"
                        f"KEYWORDS: {p.meta.get('keywords', '')}\n\n{body}\n")
            summary["pages"].append({"file": rel, "title": p.title.strip(), "chars": len(body)})
            summary["emails"].update(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text))
            summary["phones"].update(re.findall(r"\+\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{3}", text))
            summary["social"].update(re.findall(r"https?://(?:www\.)?(?:instagram|facebook|tripadvisor|wa\.me|api\.whatsapp|maps\.google|goo\.gl|google\.com/maps|youtube)[^\s\"'<>)]*", text))
            summary["addresses"].update(re.findall(r"Carrer[^<\n\"]{3,40}\d+", text))

    rows = []
    for root, _, files in os.walk(os.path.join(CLONE, "images")):
        for fn in files:
            path = os.path.join(root, fn)
            size = image_size(path)
            rows.append({
                "file": os.path.relpath(path, CLONE).replace("\\", "/"),
                "bytes": os.path.getsize(path),
                "width": size[0] if size else "",
                "height": size[1] if size else "",
            })
    rows.sort(key=lambda r: -r["bytes"])
    with open(os.path.join(AUDIT, "images.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "bytes", "width", "height"])
        w.writeheader()
        w.writerows(rows)

    summary = {k: (sorted(v) if isinstance(v, set) else v) for k, v in summary.items()}
    with open(os.path.join(AUDIT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(len(summary["pages"]), "pages;", len(rows), "images")


if __name__ == "__main__":
    main()
