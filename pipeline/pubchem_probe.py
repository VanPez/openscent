#!/usr/bin/env python3
"""
pubchem_probe.py — how much odour is in PubChem headings we have never read?

    python3 pipeline/pubchem_probe.py --list           # what headings actually exist
    python3 pipeline/pubchem_probe.py --list odor      # ...matching a substring
    python3 pipeline/pubchem_probe.py                  # the candidates, page 1 each
    python3 pipeline/pubchem_probe.py --all            # every page (slower, still polite)

PAGE 1 IS NOT A SAMPLE. Results come back alphabetically: page 1 of `Physical Description`
runs Acetal, Acetaldehyde, Acetamide, Acetic acid... i.e. industrial C1-C3 chemistry, which
is the least perfumery-like slice of the 125 pages. Use it to decide whether a heading is
worth sizing; use --all before declining one on yield.
    python3 pipeline/pubchem_probe.py "Taste"          # one named heading

Use --list first. `Physical Description` was guessed on 2026-09-10 and returned
PUGVIEW.NotFound; heading strings are exact and are not what you would call them.

MEASURE BEFORE FETCHING. THIS SCRIPT FETCHES NOTHING INTO THE CORPUS.
---------------------------------------------------------------------
It writes cached pages to corpus/raw-pubchem/probe-*.json and prints a table. It does not
produce rows, does not touch pubchem-rows.jsonl, and does not touch review.jsonl. Deciding
to harvest a heading is a separate act, and it should be taken on the numbers below.

WHY THIS EXISTS
---------------
`pubchem.py` reads exactly two headings — `Odor` and `FEMA Number` — and has since
2026-08-01. On 2026-09-10 the patent review queue was exhausted: 22 of 67 terms at the bar
and ZERO productive rows left. Of the sourcing options measured to that date, three were
closed on evidence (A23L 27/00 at 0.17, C11D 3/50 at 0.36 with no sandalwood or animalic,
and re-extraction at a looser filter) and one was never measured at all: PubChem publishes
many other annotation headings from the same HSDB corpus, and several of them carry odour
text as a matter of course.

    "Physical Description"  colorless liquid WITH A FRUITY ODOR         <- the big one
    "Color/Form"            colorless to pale yellow liquid, floral odor
    "Taste"                 correlated with odour, and HSDB-sourced

The prize is not the sentence count. It is that PubChem rows carry `LinkedRecords.CID`, so
linkage is free and there is NO REVIEW GATE — the 653 molecules from `Odor` cost zero
adjudication. Any yield here converts to molecules at a rate the patent half cannot match
now that its queue is empty.

WHAT THE NUMBERS MEAN, AND THE TRAP THE FIRST VERSION FELL INTO
---------------------------------------------------------------
**Read the EXAMPLES, not the columns.** The first version of this script counted a
vocabulary word appearing anywhere in an annotation and called it an odour. Run on
2026-09-10 it reported `Color/Form` at 298 new CIDs and 157 below-bar hits — numbers good
enough to justify a harvest — and every one was spurious:

    powdery (333)  "GRAY POWDER"                    <- physical form, not an odour
    green    (44)  "Yellowish-green gas"            <- colour
    amber    (20)  "Amber, oily liquid"             <- colour, and `amber` is the tag
                                                       we most want
    acid     (14)  "Crystals from glacial acetic acid"  <- the solvent

Of 1,000 `Color/Form` annotations, ZERO mention odour at all. `Taste` fared better on
sense — "Pungent aromatic taste" is a real sensory claim — but a row in this corpus
asserts that a molecule SMELLS of something, and of 755 annotations only 3 mentioned
odour, none of them a compound we lacked.

So a hit now requires the annotation to SAY it is about odour (`ODOUR_SENSE` below).
Both counts are printed, `raw` and `attributed`, because the GAP between them is the
measurement: a heading where raw is large and attributed is zero is a heading full of
words we recognise being used to mean something else.

This is the third time the project has mistaken a token-shaped rule for a semantic
judgement — after the `named()` gate on ingredient enumerations (2026-09-07) and the
review queue's productivity ranking (2026-09-10). A word is not a claim.

Given a heading that survives that test, the remaining question is still whether it buys
TAGS rather than rows, per 2026-09-05: a source can be twice as rich as a declined one and
buy nothing if its descriptors land on terms already past the bar. Hence NEW CIDs and
BELOW-BAR HITS.

LICENCE POSTURE IS UNCHANGED AND UNRESOLVED
-------------------------------------------
Same door, same problem as `Odor`: HSDB is a US Government work, but a statement inside it
may summarise a copyrighted source, and the first record `Odor` ever returned cited the
Merck Index. Every probed annotation is therefore reported with its `SourceName` and
whether it cites anything at all. If a heading is adopted, it must go through
`triage_pubchem.py` exactly as `Odor` did — `reference_may_be_copyrighted` is a prompt for
review, never a finding.

POLITENESS
----------
NCBI states 5 requests/second and 400/minute. This does one request every 1-2 seconds with
jitter, i.e. ~2% of the allowance, and caches every page so a re-run costs nothing. Do not
remove the cache to "get fresh numbers" — that is a re-download to improve a regex, which
is the thing harvest.py's two-stage split exists to prevent.
"""
from __future__ import annotations
import collections, importlib.util, json, os, pathlib, random, re, sys, time
import urllib.request, urllib.parse

_here = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(os.environ.get("OPENSCENT_ROOT",
           _here.parent if _here.name == "pipeline" else _here / "openscent"))
RAW = ROOT / "corpus" / "raw-pubchem"
BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/annotations/heading/JSON"
HEADINGS_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/annotations/headings/JSON"
UA = "OpenScent/0.1 (research corpus; contact via github.com/VanPez)"
DELAY = (1.0, 2.0)
PAGE_CAP = 200
BAR = 30

CANDIDATES = ["Physical Description", "Color/Form", "Taste"]

# SOME HEADINGS REQUIRE heading_type. `Physical Description` returns PUGVIEW.NotFound
# without `&heading_type=Compound` and 125 pages of results with it — the same string,
# a 404 and a hit. The name was never wrong; the request was. Found 2026-09-10 by reading
# the per-compound index (/rest/pug_view/index/compound/<CID>/JSON), which lists the exact
# TOC headings a real molecule carries and is the right place to look before probing.
HEADING_TYPE = {"Physical Description": "Compound"}

# An annotation counts only if it says it is about smell. Without this the probe measures
# how many words we recognise, which for Color/Form was 383 of 1,000 and meant nothing:
# the words were colours. `aroma` and `fragrant` are included because HSDB uses them;
# `flavor`/`taste` are NOT — they are a different sense and a different claim.
ODOUR_SENSE = re.compile(r"\bodou?rs?\b|\bodou?rous\b|\bsmell(s|ing)?\b|\baroma(tic)?\b|"
                         r"\bfragran(t|ce)\b|\bscent(ed)?\b", re.I)

# ANNOTATION-LEVEL GATING IS NOT ENOUGH, AND THIS IS THE FOURTH TIME.
#
# Requiring the annotation to mention odour killed Color/Form (raw 383 -> 0). It did NOT
# save Physical Description, where a single sentence routinely carries a colour, a texture
# and an odour at once:
#
#   "amber colored liquids with a pungent odor"       amber is the COLOUR
#   "colorless to pale-yellow OILY liquid with an irritating odor"   oily is the TEXTURE
#   "ACETIC ACID, glacial ... strong odor of vinegar"  acid is in the compound NAME
#
# All three passed the annotation gate. `amber` was the top below-bar hit at 12, and all
# twelve were the colour — the tag we most want, scored entirely by false positives.
#
# So a term counts only inside the CLAUSE carrying the odour word. Clauses are split on
# punctuation and on the connectives that separate appearance from smell in this register
# ("with", "having", "and"). Crude, and deliberately so: it is a filter for a yield
# estimate, not an extractor. Rows would still be adjudicated by hand.
CLAUSE_SPLIT = re.compile(r"[.;,()]|\bwith\b|\bhaving\b|\band\b|\bbut\b", re.I)


def _status():
    spec = importlib.util.spec_from_file_location("status", ROOT / "pipeline" / "status.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def slug(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", h.lower()).strip("-")


def fetch_page(heading: str, page: int) -> dict:
    """Cached. A page already on disk is never re-requested."""
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"probe-{slug(heading)}-p{page:03d}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    url = f"{BASE}?heading={urllib.parse.quote(heading)}&page={page}"
    if heading in HEADING_TYPE:
        url += f"&heading_type={HEADING_TYPE[heading]}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        blob = r.read().decode("utf-8")
    path.write_text(blob, encoding="utf-8")
    time.sleep(random.uniform(*DELAY))
    return json.loads(blob)


def probe(heading: str, all_pages: bool, have_cids: set, surf: dict, short: set):
    first = fetch_page(heading, 1)
    ann_block = first.get("Annotations") or {}
    total_pages = int(ann_block.get("TotalPages") or 1)
    pages = range(1, min(total_pages, PAGE_CAP) + 1) if all_pages else [1]

    n_ann = n_raw = n_odour = n_single_cid = 0
    new_cids: set = set()
    below: collections.Counter = collections.Counter()
    sources: collections.Counter = collections.Counter()
    cites = 0
    examples: list = []
    raw_examples: list = []

    # The odour test uses the ONTOLOGY's surface forms, not a hand-written list. A probe
    # that invents its own vocabulary measures the probe, not the source.
    rx = re.compile(r"\b(" + "|".join(sorted(map(re.escape, surf), key=len, reverse=True)) + r")\b", re.I)

    for p in pages:
        blob = fetch_page(heading, p) if p != 1 else first
        for ann in (blob.get("Annotations") or {}).get("Annotation") or []:
            n_ann += 1
            cids = (ann.get("LinkedRecords") or {}).get("CID") or []
            if len(cids) == 1:
                n_single_cid += 1
            sources[ann.get("SourceName") or "?"] += 1

            # Gather the annotation's text ONCE, then judge it. The sense test has to see
            # the whole value: "Amber, oily liquid" and "amber, oily odour" differ only in
            # a word that may sit outside the fragment carrying the vocabulary hit.
            texts = []
            for data in ann.get("Data") or []:
                if data.get("Reference"):
                    cites += 1
                for swm in (data.get("Value") or {}).get("StringWithMarkup") or []:
                    s = swm.get("String") or ""
                    if s.strip():
                        texts.append(s)
            whole = " ".join(texts)

            hit_terms = {surf[m.group(0).lower()] for m in rx.finditer(whole)
                         if m.group(0).lower() in surf}
            if not hit_terms:
                continue
            n_raw += 1

            # Only terms sharing a clause with the odour word survive.
            in_clause = set()
            for clause in CLAUSE_SPLIT.split(whole):
                if not ODOUR_SENSE.search(clause):
                    continue
                for m in rx.finditer(clause):
                    t = surf.get(m.group(0).lower())
                    if t:
                        in_clause.add(t)
            if not in_clause:
                # The interesting failure: we recognised a word, the annotation was about
                # smell, and the word still was not the smell. Keep a few — this is the
                # column that stops a heading being adopted on a good-looking number.
                if len(raw_examples) < 5:
                    raw_examples.append((ann.get("Name"), whole.strip()[:150]))
                continue
            hit_terms = in_clause

            n_odour += 1
            if len(examples) < 6:
                examples.append((ann.get("Name"), whole.strip()[:200]))
            if len(cids) == 1 and cids[0] not in have_cids:
                new_cids.add(cids[0])
            for t in hit_terms & short:
                below[t] += 1
    return dict(heading=heading, total_pages=total_pages, pages_read=len(list(pages)),
                annotations=n_ann, raw=n_raw, odour=n_odour, single_cid=n_single_cid,
                new_cids=len(new_cids), below=below, sources=sources, cites=cites,
                examples=examples, raw_examples=raw_examples)


def list_headings(filt: str | None) -> int:
    """What headings exist, exactly as spelled. Guessing produced a 404 on 2026-09-10."""
    cache = RAW / "probe-headings.json"
    if cache.exists():
        blob = json.loads(cache.read_text(encoding="utf-8"))
    else:
        RAW.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(HEADINGS_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8")
        cache.write_text(raw, encoding="utf-8")
        blob = json.loads(raw)
    rows = (blob.get("InformationList") or {}).get("Annotation") or []
    names = sorted({(a.get("Heading") or "").strip() for a in rows} - {""})
    if filt:
        names = [n for n in names if filt.lower() in n.lower()]
    print(f"{len(names)} headings" + (f" matching {filt!r}" if filt else "") + ":")
    for n in names:
        print(f"  {n}")
    if not filt:
        print("\nNarrow it: --list odor · --list physical · --list taste")
    return 0


def main(argv: list[str]) -> int:
    all_pages = "--all" in argv
    named = [a for a in argv if not a.startswith("--")]
    if "--list" in argv:
        return list_headings(named[0] if named else None)
    headings = named or CANDIDATES

    st = _status()
    surf = st.load_tags()
    rows = list(st.jsonl(st.REVIEW))

    have_cids = {r.get("molecule_cid") for r in st.jsonl(st.PUBCHEM)
                 if not r.get("excluded") and r.get("molecule_cid")}

    counts: dict = collections.defaultdict(set)
    for r in rows:
        if r.get("decision") != "approve":
            continue
        for d in (r.get("descriptors") or []):
            t = surf.get(d.strip().lower())
            if t:
                counts[t].update(st.norm(m) for m in (r.get("molecules") or []) if m.strip())
    for r in st.jsonl(st.PUBCHEM):
        if r.get("excluded"):
            continue
        t = (r.get("tag") or "").strip()
        m = st.norm(r.get("molecule_name") or "")
        if t and m:
            counts[t].add(m)
    short = {t for t in set(surf.values()) if len(counts.get(t, ())) < BAR}

    print(f"holding {len(have_cids)} PubChem CIDs · {len(short)} of {len(set(surf.values()))} "
          f"terms below the bar of {BAR}")
    print(f"reading {'ALL pages' if all_pages else 'PAGE 1 ONLY — rerun with --all to size it'}\n")

    results = []
    for h in headings:
        try:
            results.append(probe(h, all_pages, have_cids, surf, short))
        except Exception as e:
            print(f"!! {h}: {e}")

    print(f"{'heading':<20}{'pages':>6}{'anns':>7}{'raw':>7}{'ODOUR':>7}{'1-CID':>7}"
          f"{'NEW CIDs':>10}{'below-bar':>11}")
    print("-" * 75)
    for r in results:
        print(f"{r['heading']:<20}{r['total_pages']:>6}{r['annotations']:>7}{r['raw']:>7}"
              f"{r['odour']:>7}{r['single_cid']:>7}{r['new_cids']:>10}"
              f"{sum(r['below'].values()):>11}")
    print("-" * 75)
    print("raw   = annotations containing a vocabulary word ANYWHERE. Means nothing on its own.")
    print("ODOUR = ...and the annotation says it is about smell. This is the real count.")
    print("A large gap between them is a heading using our words to mean something else —")
    print("Color/Form scored raw 383, ODOUR 0, on 2026-09-10. READ THE EXAMPLES.\n")

    for r in results:
        if not r["annotations"]:
            continue
        print(f"=== {r['heading']} ===  raw {r['raw']} -> odour {r['odour']}")
        if r["below"]:
            print("  terms still short that it would feed: " +
                  ", ".join(f"{t}({n})" for t, n in r["below"].most_common(10)))
        print(f"  sources: {dict(r['sources'].most_common(4))}")
        print(f"  annotations citing a reference: {r['cites']} "
              f"(licence triage required exactly as for Odor)")
        if r["examples"]:
            print("  ODOUR-ATTRIBUTED (what a row would be built from):")
            for name, s in r["examples"][:3]:
                print(f"    {name}: {s[:150]}")
        if r["raw_examples"]:
            print("  REJECTED — vocabulary word present, no odour claim:")
            for name, s in r["raw_examples"][:3]:
                print(f"    {name}: {s[:150]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
