"""Generate privacy.html and terms.html from the original site's legal text (audit/pages_text)."""
import html
import os
import re

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(BASE, "audit", "pages_text")

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — Rent a Bike BCN</title>
  <meta name="robots" content="noindex,follow">
  <link rel="icon" href="assets/img/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&amp;family=Inter:wght@400;500;600;700&amp;display=swap" rel="stylesheet">
  <link rel="stylesheet" href="assets/css/styles.css">
</head>
<body>
<header class="site-header is-scrolled">
  <div class="container nav">
    <a href="index.html" class="brand" aria-label="Rent a Bike BCN — home">
      <svg viewBox="0 0 46 32" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="10" cy="21" r="8" stroke="#0d1b2a" stroke-width="3"/><circle cx="36" cy="21" r="8" stroke="#0d1b2a" stroke-width="3"/><path d="M10 21 18 9h13l5 12M18 9l4 12 9-12M10 21h12M31 9l3-3M15 8h6" stroke="#e5303c" stroke-width="3"/></svg>
      <span>Rent a Bike<small>BCN · Barcelona</small></span>
    </a>
    <a class="btn btn-ink btn-sm" href="index.html">Back to site</a>
  </div>
</header>
<main class="legal">
  <div class="container">
    <a class="back" href="index.html">&larr; Home</a>
    <h1>{title}</h1>
{body}
  </div>
</main>
<footer class="site-footer" style="padding-bottom:3rem">
  <div class="container footer-bottom" style="margin-top:0;border-top:0;padding-top:0">
    <span>© Rent a Bike BCN &amp; Luggage Storage, Barcelona</span>
    <nav aria-label="Legal"><a href="privacy.html">Privacy Policy</a><a href="terms.html">Terms of Use</a></nav>
  </div>
</footer>
</body>
</html>
"""


def build(src_name, out_name, title):
    with open(os.path.join(SRC, src_name), encoding="utf-8") as f:
        lines = [l.strip() for l in f.read().splitlines()]
    start = next(i for i, l in enumerate(lines) if l == title) + 1
    end = next(i for i, l in enumerate(lines) if i > start and (l.startswith("©") or l == "Site's Webmaster"))
    out = []
    for line in lines[start:end]:
        if not line or line == "|":
            continue
        esc = html.escape(line)
        esc = re.sub(r"(https?://[^\s<]+)", r'<a href="\1" rel="noopener">\1</a>', esc)
        if re.fullmatch(r"(SECTION \d+ - )?[A-Z0-9 ,&'’\-–()/]{4,}", line):
            out.append(f"    <h2>{esc}</h2>")
        else:
            out.append(f"    <p>{esc}</p>")
    with open(os.path.join(BASE, out_name), "w", encoding="utf-8", newline="\n") as f:
        f.write(PAGE.format(title=title, body="\n".join(out)))
    print(out_name, len(out), "blocks")


if __name__ == "__main__":
    build("terms-of-use.html.txt", "terms.html", "Terms of Use")
    build("privacy-policy.html.txt", "privacy.html", "Privacy Policy")
