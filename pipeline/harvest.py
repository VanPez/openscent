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
import json, os, re, sys, time, urllib.parse, urllib.request, pathlib, random

# Works both inside the repo (openscent/pipeline/harvest.py) and dropped anywhere on its
# own — e.g. a headless box. If it isn't sitting in a pipeline/ dir it makes ./openscent/
# beside itself. Override with OPENSCENT_ROOT=/some/path.
_here  = pathlib.Path(__file__).resolve().parent
ROOT   = pathlib.Path(os.environ.get("OPENSCENT_ROOT",
             _here.parent if _here.name == "pipeline" else _here / "openscent"))
RAW    = ROOT / "corpus" / "raw"
OUT    = ROOT / "corpus" / "extracted"
DELAY  = (2.0, 4.0)          # seconds between fetches, randomised
UA     = "OpenScent/0.1 (research corpus; contact via github.com/VanPez)"

# stdlib only — nothing to pip install, which is the point for a headless box.

# CPC classes to walk. country=US is enforced inside search_window() — non-US patents do
# not carry the US no-copyright status the licence claim depends on.
#   C11B 9/00  essential oils; perfumes — the odorant compounds themselves
#   A61Q 13/00 perfume formulations — weaker per-patent, but the best source for captives
CLASSES = ["C11B9/00", "A61Q13/00"]

def _get(url: str, tries: int = 4) -> str:
    """Retry with backoff. Google returns transient 503s under sustained querying;
    the first version treated one as fatal for the whole query and silently dropped
    the remaining pages."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if attempt == tries - 1:
                raise
            wait = (2 ** attempt) * 5 + random.uniform(0, 3)
            print(f"    retry {attempt+1}/{tries-1} in {wait:.0f}s ({e})", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("unreachable")

# ---------------------------------------------------------------- discovery
#
# Google Patents caps a result set at ~1,000 (10 pages x 100). A single query can
# therefore never enumerate the 5,660-patent C11B 9/00 US pool — the first run came
# back with exactly 998 and looked complete. The pool must be sliced into windows
# that each stay under the cap; date is the natural axis.

PAGE_CAP = 10

def search_window(cpc: str, lo: int, hi: int) -> list[str]:
    q = f"cpc={cpc}&country=US&after=priority:{lo}0101&before=priority:{hi}0101"
    ids, capped = [], False
    for p in range(PAGE_CAP):
        url = ("https://patents.google.com/xhr/query?url="
               + urllib.parse.quote(f"{q}&num=100&page={p}"))
        try:
            j = json.loads(_get(url))
        except Exception as e:
            print(f"    ! {cpc} {lo}-{hi} page {p} gave up: {e}", file=sys.stderr)
            break
        cl = (j.get("results") or {}).get("cluster") or [{}]
        hits = cl[0].get("result") or []
        if not hits: break
        ids += [h["patent"]["publication_number"] for h in hits
                if h.get("patent", {}).get("publication_number")]
        if p == PAGE_CAP - 1: capped = True
        time.sleep(random.uniform(*DELAY))
    if capped:
        print(f"    ! {cpc} {lo}-{hi} hit the 1000 cap — window too wide, results lost",
              file=sys.stderr)
    return ids

    # Default start is 2001, not 1960, and that is a deliberate ordering choice.
    # Pre-2001 patents are OCR-damaged scans whose odour claims attach to isomer
    # mixtures and GC peaks rather than single structures (handrun-01) — low yield,
    # high effort. Post-2001 text is pristine. Harvest the valuable half first; the
    # archaeology can be a second pass with START=1960 if it ever earns its place.

def search_all(cpc: str, start: int | None = None, end: int = 2027, step: int = 3) -> list[str]:
    """Walk the class in date windows, so no single query hits the 1000 cap."""
    if start is None:
        start = int(os.environ.get("OPENSCENT_START_YEAR", 2001))
    out = []
    for lo in range(start, end, step):
        hi = min(lo + step, end)
        got = search_window(cpc, lo, hi)
        if got: print(f"  {cpc} {lo}-{hi}: {len(got)}")
        out += got
    return out

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
        (ROOT / "corpus").mkdir(parents=True, exist_ok=True)   # was created too late; crashed the first run
        idfile = ROOT / "corpus" / "patent-ids.json"
        if idfile.exists():
            allids = json.loads(idfile.read_text())
            print(f"reusing {len(allids)} ids from {idfile.name} "
                  f"(delete it to re-run discovery)\n")
        else:
            allids = []
            for cpc in CLASSES:
                print(f"searching {cpc} in {3}-year windows …")
                allids += search_all(cpc)
                idfile.write_text(json.dumps(sorted(set(allids)), indent=1))  # save as we go
            allids = sorted(set(allids))
            idfile.write_text(json.dumps(allids, indent=1))
            print(f"\n{len(allids)} distinct US patents\n")
        fetch(allids)
    elif cmd == "extract":
        extract()
    elif cmd == "status":
        idf = ROOT / "corpus" / "patent-ids.json"
        known = len(json.loads(idf.read_text())) if idf.exists() else 0
        cached = len(list(RAW.glob("*.txt"))) if RAW.exists() else 0
        mb = sum(f.stat().st_size for f in RAW.glob("*.txt"))/1e6 if RAW.exists() else 0
        left = max(0, known - cached)
        eta  = left * sum(DELAY)/2 / 3600
        print(f"root      {ROOT}")
        print(f"known ids {known}")
        print(f"cached    {cached}  ({mb:.0f} MB)")
        print(f"remaining {left}   ~{eta:.1f} h at the current delay")
        cf = OUT / "candidates.json"
        if cf.exists():
            print(f"candidates {len(json.loads(cf.read_text()))} (from last extract run)")
    else:
        print(__doc__)
