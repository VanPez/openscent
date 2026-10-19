#!/usr/bin/env python3
"""Fetch Olfatorium's own product descriptions (stdlib only).

PERMISSION: the owner of Olfatorium granted, in writing on 2026-10-13, that the short descriptor
words from descriptions Olfatorium wrote themselves may be included in OpenScent under CC BY 4.0,
credited with a link, in a separate labelled layer (also on-chain). The grant does NOT cover text
Olfatorium took from other sources -- their synthetics page says some descriptions are third-party,
and the API does not mark which. So this script only COLLECTS; nothing it writes enters the corpus.
Every word is read by Ivan first (see corpus/olfatorium/descriptions-review.md).

Evidence of the grant: outreach/permission-emails.md and outreach/olfatorium-*.png (local only).

What it does
  1. GET the public WooCommerce Store API (https://olfatorium.com/wp-json/wc/store/v1/products),
     100 per page, with a pause between requests and a user agent that names the project.
  2. Keep the raw JSON in corpus/olfatorium/raw/ (gitignored -- the folder is local only).
  3. Write corpus/olfatorium/descriptions.tsv: id, name, slug, permalink, categories, the structured
     "Perfil olfativo" attribute, CAS, short description and long description as plain text.

Network: this is NOT PubChem, so the Mac is fine (the PubChem-on-Hetzner rule does not apply).
Usage:  python3 pipeline/olfatorium_fetch.py            # fetch + write the TSV
        python3 pipeline/olfatorium_fetch.py --offline   # rebuild the TSV from the saved raw JSON
"""
import argparse
import csv
import html
import json
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "corpus" / "olfatorium"
RAW = OUT / "raw"
API = "https://olfatorium.com/wp-json/wc/store/v1/products"
UA = ("OpenScent/0.1 (open odour dataset; permission granted by the shop owner 2026-10-13; "
      "contact openscent.data@gmail.com)")
PAUSE = 2.5      # seconds between requests
PER_PAGE = 100
MAX_PAGES = 10   # safety stop; the shop had 212 products on 2026-10-13


class _Text(HTMLParser):
    """HTML -> plain text. Keeps paragraph/list breaks as newlines; drops <script>/<style>/<pre>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "pre"):
            self.skip += 1
        elif tag in ("p", "br", "li", "div", "h1", "h2", "h3", "h4", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "pre") and self.skip:
            self.skip -= 1
        elif tag in ("p", "li", "div", "h1", "h2", "h3", "h4", "tr"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def to_text(markup: str) -> str:
    p = _Text()
    p.feed(markup or "")
    text = html.unescape("".join(p.parts))
    text = re.sub(r"[ \t ]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def fetch_all() -> list:
    RAW.mkdir(parents=True, exist_ok=True)
    products, page = [], 1
    while page <= MAX_PAGES:
        url = f"{API}?per_page={PER_PAGE}&page={page}"
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            total_pages = int(r.headers.get("X-WP-TotalPages", "1"))
            body = r.read()
        (RAW / f"products-p{page}.json").write_bytes(body)
        batch = json.loads(body)
        products += batch
        print(f"page {page}/{total_pages}: {len(batch)} products", file=sys.stderr)
        if page >= total_pages:
            break
        page += 1
        time.sleep(PAUSE)
    return products


def load_raw() -> list:
    out = []
    for f in sorted(RAW.glob("products-p*.json"), key=lambda p: int(re.findall(r"\d+", p.stem)[0])):
        out += json.loads(f.read_bytes())
    return out


def attr(product: dict, name: str) -> str:
    for a in product.get("attributes", []):
        if a.get("name", "").strip().lower() == name.lower():
            return "; ".join(t.get("name", "") for t in a.get("terms", []))
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="rebuild the TSV from saved raw JSON")
    args = ap.parse_args()
    products = load_raw() if args.offline else fetch_all()
    OUT.mkdir(parents=True, exist_ok=True)
    cols = ["id", "name", "slug", "permalink", "categories", "perfil_olfativo", "cas",
            "short_description", "description"]
    with open(OUT / "descriptions.tsv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(cols)
        for p in products:
            one_line = lambda s: s.replace("\t", " ").replace("\n", " ⏎ ")
            w.writerow([
                p.get("id"), html.unescape(p.get("name", "")), p.get("slug", ""), p.get("permalink", ""),
                "; ".join(c.get("name", "") for c in p.get("categories", [])),
                attr(p, "Perfil olfativo"), attr(p, "CAS No."),
                one_line(to_text(p.get("short_description", ""))),
                one_line(to_text(p.get("description", ""))),
            ])
    print(f"wrote {OUT / 'descriptions.tsv'} ({len(products)} products)", file=sys.stderr)


if __name__ == "__main__":
    main()
