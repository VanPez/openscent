#!/usr/bin/env python3
"""
OpenScent — patent harvester.

Two separable stages, deliberately:

    python3 harvest.py fetch    # network. slow, polite, resumable, caches to corpus/raw/
    python3 harvest.py extract  # offline. re-runnable as often as the filter changes

Keeping them separate is the whole point: the extraction filter is not finished, and you
must not have to re-download 5,600 patents every time you improve a regex.

Sources
-------
Google Patents. Two undocumented-but-stable endpoints, no API key, no account:
    search    https://patents.google.com/xhr/query?url=<urlencoded query>
    fulltext  https://patents.google.com/patent/<id>/en

On politeness: this fetches one document at a time with a delay, caches everything, and
never re-fetches. Do not lower DELAY to be clever — losing this endpoint costs more than
the time it saves, and USPTO's own bulk data products are the sanctioned route for
genuinely large pulls (no key needed for those either).

US ONLY. Non-US patents do not carry the US no-copyright status the licence claim rests on.
"""
from __future__ import annotations
import json, re, sys, time, urllib.parse, urllib.request, pathlib, random

ROOT   = pathlib.Path(__file__).resolve().parent.parent
RAW    = ROOT / "corpus" / "raw"
OUT    = ROOT / "corpus" / "extracted"
DELAY  = (2.0, 4.0)          # seconds between fetches, randomised
UA     = "OpenScent/0.1 (research corpus; contact via github.com/VanPez)"

QUERIES = [
    # (label, query string) — country=US enforced in every one.
    ("compounds",   "cpc=C11B9/00&country=US&after=priority:20010101"),
    ("compounds_old","cpc=C11B9/00&country=US&before=priority:20010101"),
    ("formulations","cpc=A61Q13/00&country=US&after=priority:20050101"),
]

def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

# ---------------------------------------------------------------- discovery

def search(query: str, pages: int = 10) -> list[str]:
    ids = []
    for p in range(pages):
        url = ("https://patents.google.com/xhr/query?url="
               + urllib.parse.quote(f"{query}&num=100&page={p}"))
        try:
            j = json.loads(_get(url))
        except Exception as e:
            print(f"  ! search page {p} failed: {e}", file=sys.stderr); break
        cl = (j.get("results") or {}).get("cluster") or [{}]
        hits = cl[0].get("result") or []
        if not hits: break
        ids += [h["patent"]["publication_number"] for h in hits
                if h.get("patent", {}).get("publication_number")]
        time.sleep(random.uniform(*DELAY))
    return ids

# ---------------------------------------------------------------- fetching

DESC = re.compile(r'<section[^>]+itemprop="description".*?</section>', re.S)
TAGS = re.compile(r"<[^>]+>")

def fetch(ids: list[str]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    todo = [i for i in ids if not (RAW / f"{i}.txt").exists()]
    print(f"{len(ids)} known, {len(ids)-len(todo)} already cached, {len(todo)} to fetch")
    for n, pid in enumerate(todo, 1):
        try:
            html = _get(f"https://patents.google.com/patent/{pid}/en")
            m = DESC.search(html)
            text = TAGS.sub(" ", m.group(0)) if m else ""
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) < 500:
                print(f"  [{n}/{len(todo)}] {pid} — too short, skipped"); continue
            (RAW / f"{pid}.txt").write_text(text, encoding="utf-8")
            if n % 25 == 0: print(f"  [{n}/{len(todo)}] cached {pid}")
        except Exception as e:
            print(f"  [{n}/{len(todo)}] {pid} FAILED: {e}", file=sys.stderr)
        time.sleep(random.uniform(*DELAY))

# ---------------------------------------------------------------- extraction
# v1 filter. Every exclusion below was observed in a real patent — see
# reports/handrun-03-calibration.md. Tighten it here, then re-run `extract`;
# no re-fetching required.

ODOUR  = re.compile(r"\b(odou?rs?|smells?|fragrance notes?|olfactive)\b", re.I)
DESCR  = re.compile(r"\b(has|have|having|possess(?:es|ing)?|exhibit(?:s|ing)?|"
                    r"is described as|described with|imparts?|reminiscent|"
                    r"characteri[sz]ed as|shows?|display(?:s|ing)?)\b", re.I)
NAMED  = re.compile(r"\b(example\s+\d+|compound\s+\d+|[a-z]+(?:ol|al|one|ate|ene|ol|"
                    r"phenol|aldehyde|acetate|lactone|oxide)\b|\d+-\([a-z])", re.I)
EXCLUDE = [
    (re.compile(r"\bodou?r value\b", re.I),                     "odour-value metric"),
    (re.compile(r"\bodou?r (test|panel|grading|scale|score)\b", re.I), "test protocol"),
    (re.compile(r"\bmal[- ]?odou?r|deodori[sz]|counteract", re.I),"malodour context"),
    (re.compile(r"person skilled|skilled in the art", re.I),     "definitional"),
    (re.compile(r"\baccording to claim|said composition|embodiment\b", re.I), "claim language"),
    # NB no trailing \b — '%' is a non-word char, so \b would require a word char after it
    # and the exclusion silently failed on "75 wt. % of the alcohol". Caught by the smoke test.
    (re.compile(r"\b\d+(\.\d+)?\s*(wt\.?\s*%|weight percent|ppm)", re.I), "proportion claim"),
    (re.compile(r"\bcomprises?\b.*\b(alcohol|compound|ingredient)s?\b.*\bodou?r", re.I), "composition claim"),
    (re.compile(r"\b(distill|chromatograph|yield of|purified|filtrate|reflux)\b", re.I), "synthesis prose"),
]
SENT = re.compile(r"(?<=[.;])\s+(?=[A-Z0-9(])")

def norm(s: str) -> str:
    """Deterministic, versioned. Applied identically to source and span before any
    verbatim comparison — see handrun-01 (OCR noise in pre-2000 scans)."""
    return re.sub(r"\s+", " ", s).strip()

NORM_VERSION = "norm/1"

def extract() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, stats = [], dict(docs=0, sents=0, odour=0, excluded=0, kept=0)
    for f in sorted(RAW.glob("*.txt")):
        text = norm(f.read_text(encoding="utf-8"))
        stats["docs"] += 1
        for s in SENT.split(text):
            stats["sents"] += 1
            if not (25 < len(s) < 320) or not ODOUR.search(s): continue
            stats["odour"] += 1
            why = next((lbl for rx, lbl in EXCLUDE if rx.search(s)), None)
            if why: stats["excluded"] += 1; continue
            if not DESCR.search(s) or not NAMED.search(s): continue
            span = norm(s)
            assert span in text, f"REJECT {f.stem}: span not verbatim in source"
            stats["kept"] += 1
            rows.append({"source_id": f.stem, "sentence": span,
                         "char_offset": text.index(span),
                         "extractor": "v1", "normalisation": NORM_VERSION})
    (OUT / "candidates.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(json.dumps(stats, indent=1))
    print(f"-> {len(rows)} candidates written to {OUT/'candidates.json'}")
    print("   NOTE: candidates, not rows. Compound->structure linkage (OPSIN) is the next stage,")
    print("   and a human still reviews. Expect roughly a quarter of these to survive.")

# ---------------------------------------------------------------- main

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "fetch":
        allids = []
        for label, q in QUERIES:
            print(f"searching {label} …")
            got = search(q)
            print(f"  {len(got)} ids")
            allids += got
        allids = sorted(set(allids))
        (ROOT / "corpus" / "patent-ids.json").write_text(json.dumps(allids, indent=1))
        print(f"{len(allids)} distinct US patents\n")
        fetch(allids)
    elif cmd == "extract":
        extract()
    else:
        print(__doc__)
