#!/usr/bin/env python3
"""
OpenScent — PubChem odour harvester (second source, independent of the patent pipeline).

    python3 pubchem.py fetch     # network. paginated, cached, resumable
    python3 pubchem.py extract   # offline. re-runnable as the filter changes
    python3 pubchem.py status

Same two-stage split as harvest.py and for the same reason: the filter is not finished,
and you must not re-download to improve a regex.

Sources — two PUG View annotation headings, both plain JSON, no key, no account:
    odour   .../annotations/heading/JSON?heading=Odor
    fema    .../annotations/heading/JSON?heading=FEMA%20Number

WHY THIS SOURCE EXISTS ALONGSIDE THE PATENTS
--------------------------------------------
Linkage is free. PubChem hands back `LinkedRecords.CID`, so the dangerous patent failure
mode — resolving "Example 3" to the wrong structure and producing an accurate description
bound to the wrong molecule — cannot occur here. No OPSIN stage.

THE LICENCE CAVEAT, WHICH IS NOT OPTIONAL
-----------------------------------------
`../aroma-index/reports/license-scan.md` records the Odor heading as public domain because
2,356 of 2,358 annotations come from HSDB, a US National Library of Medicine work. That is
true of the *database*. It is not automatically true of the *statement*: HSDB summarises
prior literature, and the first record returned by this endpoint cites

    Budavari, S. (ed.). The Merck Index ... Merck and Co., Inc., 1996., p. 1511

— a copyrighted book. This is the `quotes_source` problem from hand-run 02, arriving through
a different door. Every row therefore carries its references verbatim and a
`reference_may_be_copyrighted` flag. The flag is a HEURISTIC over a publisher list; it is a
prompt for review, not a legal finding, and a false negative is entirely possible.

US GOVERNMENT WORK != EVERY FIELD IS FREE. Check `source_name` per row, never per heading.

FEMA rows are a SELECTION layer only — the FEMA number is an identifier (a fact), and the
association's own library text is proprietary and is not fetched. We store the number and
nothing else from FEMA.

Politeness: NCBI's stated limits are 5 requests/second and 400/minute. This does one request
every 1–2 seconds, i.e. ~2% of the allowance.
"""
from __future__ import annotations
import json, os, re, sys, time, random, pathlib, urllib.request, urllib.parse

_here = pathlib.Path(__file__).resolve().parent
ROOT  = pathlib.Path(os.environ.get("OPENSCENT_ROOT",
            _here.parent if _here.name == "pipeline" else _here / "openscent"))
RAW   = ROOT / "corpus" / "raw-pubchem"
OUT   = ROOT / "corpus" / "extracted"
DELAY = (1.0, 2.0)
UA    = "OpenScent/0.1 (research corpus; contact via github.com/VanPez)"

BASE  = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/annotations/heading/JSON"
HEADINGS = {"odor": "Odor", "fema": "FEMA Number"}
PAGE_CAP = 200          # sanity stop; real count comes from TotalPages in the response


def _get(url: str, tries: int = 4) -> str:
    """Retry with backoff. PubChem returns 503 under load and 429 if you are rude."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if attempt == tries - 1:
                raise
            wait = (2 ** attempt) * 5 + random.uniform(0, 3)
            print(f"    retry {attempt+1}/{tries-1} in {wait:.0f}s ({e})", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------- fetching

def fetch_heading(key: str, heading: str) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    page, total = 1, None
    while page <= PAGE_CAP:
        dest = RAW / f"{key}-p{page:03d}.json"
        if dest.exists():                      # resumable: never re-fetch a cached page
            try:
                total = total or json.loads(dest.read_text()).get("Annotations", {}).get("TotalPages")
            except Exception:
                pass
            if total and page >= total:
                break
            page += 1
            continue
        url = f"{BASE}?heading={urllib.parse.quote(heading)}&page={page}"
        body = _get(url)
        try:
            j = json.loads(body)
        except json.JSONDecodeError as e:
            print(f"  {key} p{page}: response was not JSON ({e}) — stopping", file=sys.stderr)
            break
        ann = (j.get("Annotations") or {}).get("Annotation") or []
        if not ann:
            print(f"  {key} p{page}: empty, stopping")
            break
        dest.write_text(body, encoding="utf-8")
        total = (j.get("Annotations") or {}).get("TotalPages") or total
        print(f"  {key} p{page}/{total or '?'}: {len(ann)} annotations cached")
        if total and page >= total:
            break
        page += 1
        time.sleep(random.uniform(*DELAY))


def fetch() -> None:
    for key, heading in HEADINGS.items():
        print(f"fetching heading {heading!r} …")
        fetch_heading(key, heading)


# ---------------------------------------------------------------- extraction
#
# Publishers whose presence in a Reference means the odour sentence may be summarising a
# copyrighted work. Deliberately over-broad: a false flag costs a human glance, a missed
# one costs the licence claim. Arctander and Fenaroli are on the list because they are
# exactly the fragrance references the sister project's scan already ruled out.
COPYRIGHTED_HINTS = [
    "merck index", "budavari", "o'neil", "wiley", "elsevier", "crc press", "crc handbook",
    "academic press", "springer", "van nostrand", "kirk-othmer", "ullmann", "hawley",
    "sigma-aldrich", "aldrich", "arctander", "fenaroli", "perfumer", "sax", "lewis, r",
    "mcgraw-hill", "john wiley", "taylor & francis", "royal society of chemistry",
]

# Reject non-descriptive statements. Each pattern is here because the Odor heading is a
# toxicology field, not a perfumery one: it records absence, thresholds and test protocols
# alongside genuine descriptions.
EXCLUDE = [
    (re.compile(r"\bodorless\b|\bodourless\b|\bno odor\b|\bnone\b", re.I), "absence-of-odour"),
    (re.compile(r"\bthreshold\b|\bppm\b|\bdetection limit\b", re.I),       "threshold/metric"),
    (re.compile(r"^\s*(not |no )?(available|data|reported|specified)", re.I), "no-data placeholder"),
]

def _rows_from_annotation(ann: dict, raw_blob: str) -> list[dict]:
    cids = (ann.get("LinkedRecords") or {}).get("CID") or []
    out = []
    for data in ann.get("Data") or []:
        refs = list(data.get("Reference") or [])
        joined = " ".join(refs).lower()
        flagged = [h for h in COPYRIGHTED_HINTS if h in joined]
        for swm in (data.get("Value") or {}).get("StringWithMarkup") or []:
            # NOT stripped. An earlier version stripped here, which silently made the
            # stored text differ from the source for any value with surrounding
            # whitespace — a provenance hole in the one field that must be exact.
            s = swm.get("String") or ""
            if not s.strip():
                continue
            # Verbatim guarantee, enforced not intended — same rule as harvest.py.
            #
            # The comparison must happen in ONE encoding. The parsed value is decoded
            # JSON; the cached page is encoded JSON. `LIKE "BRICK DUST"` (ANID 1392) is
            # stored on disk as LIKE \"BRICK DUST\", so testing the decoded string for
            # substring presence in the raw file fails on every value containing a quote,
            # a backslash or a newline — while being perfectly verbatim. Re-encode before
            # comparing. Try both ensure_ascii settings: we control our escaping, not
            # PubChem's, and it may emit \uXXXX where we would emit the literal character.
            if not any(json.dumps(s, ensure_ascii=ea)[1:-1] in raw_blob for ea in (False, True)):
                raise AssertionError(
                    f"REJECT {ann.get('ANID')}: span not verbatim in cached page: {s!r}")
            out.append({
                "cid": cids[0] if len(cids) == 1 else None,
                "cid_candidates": cids if len(cids) != 1 else None,
                "cid_ambiguous": len(cids) != 1,
                "name": ann.get("Name"),
                "text": s,
                "source_name": ann.get("SourceName"),
                "source_id": ann.get("SourceID"),
                "source_url": ann.get("URL"),
                "license_url": ann.get("LicenseURL"),
                "anid": ann.get("ANID"),
                "references": refs,
                "quotes_source": bool(refs),
                "reference_may_be_copyrighted": bool(flagged),
                "reference_flag_hits": flagged or None,
                # The citation is NOT the risk — the span length is. Copyright protects
                # expression, not facts, and "fragrant and penetrating odor" is a short
                # phrase stating a fact: no protectable expression to infringe. Measured
                # over the real data, flagged spans run to a median of 3 words and 87%
                # are <= 5. Treating a citation as disqualifying would have discarded
                # 1,148 rows to protect against a risk that isn't in them.
                #
                # The genuine case is authored prose, e.g. BENZYL ACETATE's "Powerful but
                # thin, sweet floral fresh ... reminiscent of Jasmin, Gardenia, Muguet",
                # cited to Merck Index p.189 — somebody wrote that. Only 39 rows exceed
                # 10 words AND carry a flagged citation, which is a hand-review, not a
                # licence problem. NOT legal advice; this is a triage field.
                "word_count": len(s.split()),
                "expression_risk": ("review" if flagged and len(s.split()) > 10
                                    else "low"),
                "extractor": "pubchem/v1",
            })
    return out


def extract() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stats = dict(pages=0, annotations=0, rows=0, excluded=0, no_cid=0,
                 flagged_reference=0, kept=0)

    # --- FEMA selection layer: CID -> FEMA number. Identifier only, no FEMA prose. ---
    fema: dict[int, str] = {}
    for f in sorted(RAW.glob("fema-p*.json")):
        j = json.loads(f.read_text(encoding="utf-8"))
        for ann in (j.get("Annotations") or {}).get("Annotation") or []:
            for cid in (ann.get("LinkedRecords") or {}).get("CID") or []:
                for data in ann.get("Data") or []:
                    for swm in (data.get("Value") or {}).get("StringWithMarkup") or []:
                        num = (swm.get("String") or "").strip()
                        if num:
                            fema[cid] = num

    rows = []
    for f in sorted(RAW.glob("odor-p*.json")):
        blob = f.read_text(encoding="utf-8")
        j = json.loads(blob)
        stats["pages"] += 1
        for ann in (j.get("Annotations") or {}).get("Annotation") or []:
            stats["annotations"] += 1
            for row in _rows_from_annotation(ann, blob):
                stats["rows"] += 1
                why = next((lbl for rx, lbl in EXCLUDE if rx.search(row["text"])), None)
                if why:
                    stats["excluded"] += 1
                    continue
                if row["cid_ambiguous"]:
                    stats["no_cid"] += 1
                    continue
                if row["reference_may_be_copyrighted"]:
                    stats["flagged_reference"] += 1
                row["fema_number"] = fema.get(row["cid"])
                # Named for what it records, not for what it implies. A FEMA number is an
                # industry association's GRAS designation — evidence the molecule is an
                # established flavour ingredient, not a safety certification and not a
                # curation of perfumery materials (acetone is FEMA 3326).
                #
                # ASYMMETRIC, and it matters: presence suggests an aroma molecule; ABSENCE
                # implies nothing. Iso E Super and the musks are fragrance-only and will
                # never carry a FEMA number. Never filter on this — it is metadata.
                row["fema_listed"] = row["fema_number"] is not None
                stats["kept"] += 1
                rows.append(row)

    dest = OUT / "pubchem-candidates.json"
    dest.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(stats, indent=1))
    print(f"\nFEMA selection layer: {len(fema)} CIDs carry a FEMA number")
    print(f"of the kept rows, {sum(1 for r in rows if r['fema_listed'])} are FEMA-listed, "
          f"{sum(1 for r in rows if not r['fema_listed'])} are not "
          f"(absence implies nothing — fragrance-only materials are never FEMA-listed)")
    print(f"-> {len(rows)} candidates written to {dest}")
    print("   NOTE: candidates, not corpus rows. A human still reviews, and every row with")
    print("   reference_may_be_copyrighted=true needs the cited work checked before use.")


def status() -> None:
    print(f"root    {ROOT}")
    for key in HEADINGS:
        n = len(list(RAW.glob(f"{key}-p*.json"))) if RAW.exists() else 0
        print(f"{key:7} {n} pages cached")
    cf = OUT / "pubchem-candidates.json"
    if cf.exists():
        rows = json.loads(cf.read_text())
        review = sum(1 for r in rows if r.get("expression_risk") == "review")
        fema_n = sum(1 for r in rows if r.get("fema_listed"))
        print(f"candidates {len(rows)}  ({fema_n} FEMA-listed, {review} need expression review)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if   cmd == "fetch":   fetch()
    elif cmd == "extract": extract()
    elif cmd == "status":  status()
    else: print(__doc__)
