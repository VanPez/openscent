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

# v2 — bare "note(s)" and "character" added as odour head nouns. v1 missed the
# KARANAL captive sentence ("...woody ambery notes that it brings...") because it
# only matched the bigram "fragrance note". Cost: more candidates to filter.
ODOUR  = re.compile(r"\b(odou?rs?|smells?|olfactive|notes?|characters?|nuances?)\b", re.I)
# Descriptor-only headings carry no odour word and no verb: "PERFUME PROPERTIES
# Fruity, woody, pineapple-like." Accepted via a separate path (see decide()).
HEADING = re.compile(r"\b(perfume|odou?r|organoleptic)\s+(propert|characteristic)", re.I)
DESCR  = re.compile(r"\b(has|have|having|possess(?:es|ing)?|exhibit(?:s|ing)?|"
                    r"is described as|described with|imparts?|reminiscent|"
                    r"characteri[sz]ed as|shows?|display(?:s|ing)?|"
                    # v2: commercial-register verbs. Formulation patents describe
                    # captives as "valued for"/"prized for" rather than "has" —
                    # missed the KARANAL sentence (t07), which is the captive case
                    # this whole source type exists to capture.
                    r"valued for|prized for|known for|appreciated for|noted for)\b", re.I)
# --- NAMED, v3. The v2 rule was broken in both directions at once. ---------------
#
# Measured over the 3,379 candidates from the full 2,588-patent run, the single most
# common token satisfying "this sentence names a compound" was **floral** (624×),
# followed by natural 278, material 250, chemical 134, herbal 111, animal 41. The gate
# meant to prove a molecule is named was being satisfied by the words that describe the
# smell — `[a-z]+al\b` matches "floral" exactly as well as "lilial".
#
# Simultaneously it MISSED real names: `[a-z]+ol\b` fails on the plural "alkoxynonenols",
# and "-yne" was not in the suffix list at all, so "1,3-undecadien-5-yne" did not match.
# Several rows were accepted for the wrong reason — right answer, broken reasoning.
#
# v3 accepts on any of four independent signals, and the stoplist is a human-written
# table in the same spirit as odor_terms.tsv: published, arguable, and known to be
# incomplete rather than pretending to be exhaustive.

# Parentheses are not optional in practice: patents write "the compounds of Formula (I)"
# far more often than "Formula I". The first draft of this rule required whitespace then a
# bare numeral and silently missed every parenthesised reference — caught by checking what
# v3 newly rejected, not by reasoning about it. The trailing \b matters: without it,
# "[IVX]+" happily matches the "i" of "compound in the composition".
# RETIRED 2026-08-03 — see decide()/named(). "Example 3", "compound (I.4)", "formula (I)"
# are POINTERS, not names: the structure is defined elsewhere in the document. At
# sentence scope they are the same failure as "the material" (t10) and "this feedstock"
# (t11), and the held-out round showed them producing unusable rows (h05 h17). Kept only
# so the reasoning is visible; nothing calls it. Restore it the day extraction gains a
# context window, at which point it becomes the *right* rule rather than the wrong one.
NAMED_EXPLICIT = re.compile(r"\b(example|compound|formula|structure)s?\s*\(?\s*(\d+|[IVX]+)\b",
                            re.I)

# Systematic-nomenclature punctuation: locants, stereo prefixes. Very high precision —
# ordinary English does not contain "8-alkoxy-4,8-dimethylnon-1-ene".
NAMED_LOCANT = re.compile(r"\d\s*[,-]\s*\d|\b\d+-\(|\b\d+-[a-z]{3,}|\([EZRS][,)]|"
                          r"\b(alpha|beta|gamma|delta|cis|trans|ortho|meta|para)-", re.I)

# Registered trade names — the captive case (KARANAL®, ISO E SUPER™). The symbol is
# required: bare capitals match patent section headings and country codes.
NAMED_TRADE = re.compile(r"\b[A-Z][A-Za-z0-9\- ]{2,}\s*[®™]")

# Chemical suffixes, now including plurals and -yne/-ane, which v2 omitted.
NAMED_SUFFIX = re.compile(r"\b[a-z][a-z0-9\-]{2,}(?:ols?|als?|ones?|ates?|enes?|ynes?|"
                          r"anes?|oates?|phenols?|aldehydes?|acetates?|lactones?|"
                          r"oxides?|ketones?|esters?|ethers?)\b", re.I)

# Common English words that end in a chemical suffix, plus — the reason this list exists
# — odour DESCRIPTORS that do. Every entry was observed in the real candidate set or is a
# near neighbour of one. Incomplete by construction; add to it when a false accept shows up.
NAMED_STOP = frozenset("""
floral herbal animal vegetal oriental mineral
material materials natural chemical chemicals essential additional general functional
conventional optional commercial industrial final total typical normal original personal
principal potential traditional internal external overall individual technical identical
several special local central medical physical practical critical vertical spherical
numerical theoretical universal ideal real oval level novel panel equal usual visual actual
one none done alone gone bone tone tones stone zone zones phone undertone overtone
gene scene hygiene serene obscene convene intervene
state rate date late gate create generate separate indicate evaluate demonstrate
incorporate operate concentrate formulate relate estimate appropriate approximate moderate
immediate adequate accurate candidate intermediate ultimate alternate private corporate
climate certificate delicate duplicate update validate associate initiate facilitate
communicate dedicate illustrate particulate legitimate
""".split())

def named(s: str) -> bool:
    """Does this sentence plausibly name a resolvable compound?

    Four independent signals; any one suffices. Kept as a function rather than a bare
    regex because the suffix test needs a stoplist, and score.py mirrors this path."""
    # NAMED_EXPLICIT deliberately absent — see the note on it above. A pointer to a
    # structure defined elsewhere cannot be resolved from one sentence.
    if NAMED_LOCANT.search(s) or NAMED_TRADE.search(s):
        return True
    return any(m.group(0).lower() not in NAMED_STOP for m in NAMED_SUFFIX.finditer(s))

# Retained so older callers and the test harness keep working; `named()` is the gate.
NAMED = NAMED_SUFFIX
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
    # --- v2 additions, each from a scored false positive in testset.jsonl ---
    (re.compile(r"selected from the group consisting of", re.I),   "claim enumeration (d14)"),
    (re.compile(r"\bpreferably\b.{0,40}\bhaving\b|\bmay (also )?(impart|modify|enhance)\b", re.I),
                                                                   "hypothetical/preferential (d13,d14)"),
    (re.compile(r"i\.?e\.?,?\s+odou?r,?\s+propert|\bodou?r\s+properties\b", re.I),
                                                                   "odour-as-category, no descriptor (d12)"),
    (re.compile(r"\bby combining\b", re.I),                        "hypothetical combination (d13)"),

    # ---- v4: derived from the 21 held-out false positives, 2026-08-03 -------------
    # That set is SPENT. These rules were written from its failure categories, so the
    # next held-out draw is the only thing that can say whether they work. Nothing
    # here was iterated against those 50 sentences — one pass, then re-measure.

    # 1. Negation. "do not have an odor note of lily of the valley", "no inherent
    #    odour", "no longer perceptible". A statement that something does NOT smell
    #    is true and unusable: there is no descriptor to attach. (h07 h17 h22 h23)
    (re.compile(r"\b(no|not|hardly|never|scarcely|barely)\b[^.]{0,45}"
                r"\b(odou?r|smell|aroma|note)s?\b", re.I),         "negation / absence of odour"),
    (re.compile(r"\b(devoid of|free from|lacks?|lacking)\b[^.]{0,30}"
                r"\b(odou?r|smell|aroma)", re.I),                  "negation / absence of odour"),

    # 2. Comparison and intensity. "significantly higher odor intensity", "a more
    #    intense odor than", "changed significantly in odour". Magnitude and change,
    #    not character — the same error class as `odour value`. (h04 h18 h20 h21)
    (re.compile(r"\b(more|less|higher|lower|greater|stronger|weaker|better|worse)\b"
                r"[^.]{0,25}\b(odou?r|smell|aroma|intensit)", re.I), "comparative / intensity"),
    (re.compile(r"\bodou?r\s+(intensity|quality|adhesion|performance|impression)\b", re.I),
                                                                   "odour-as-property"),
    (re.compile(r"\b(olfactive|olfactory)\s+performance\b", re.I),  "quality word, not descriptor"),
    (re.compile(r"\bchang(?:e|es|ed|ing)\b[^.]{0,25}\b(odou?r|note|smell)", re.I),
                                                                   "change over time, not a descriptor"),

    # 3. Prior-art framing. "Patent Document 2 discloses", "described in patent
    #    document U.S.", "1967, 3356 describes the use of". The sentence reports what
    #    another document says; the subject is usually a cited compound and the claim
    #    is second-hand. RISKIEST RULE HERE — `disclose` is common patent English and
    #    this may cost real rows. Watch it in the next held-out round. (h07 h13 h22)
    (re.compile(r"\bpatent document\b|\bdisclos(?:e|es|ed|ure)\b|\bdescribed in\b", re.I),
                                                                   "prior-art citation"),

    # 4. Definitional meta-text. "Note that the 'fragrance composition' is a
    #    composition that ...". Defines a term rather than describing a smell. (h08)
    (re.compile(r"\bnote that\b|\bis a composition that\b", re.I),  "definitional meta-text"),
]
SENT = re.compile(r"(?<=[.;])\s+(?=[A-Z0-9(])")

def norm(s: str) -> str:
    """Deterministic, versioned. Applied identically to source and span before any
    verbatim comparison — see handrun-01 (OCR noise in pre-2000 scans)."""
    return re.sub(r"\s+", " ", s).strip()

NORM_VERSION = "norm/1"


def decide(s: str) -> tuple[bool, str]:
    """THE accept path. Single implementation, three callers.

    This existed in triplicate — once here (inside extract), once in score.py, once in
    heldout.py — and they drifted, which is the entirely predictable outcome. The
    HEADING rule was written into the two scorers and never into extract(), so:

      - the test set rewarded accepting "PERFUME PROPERTIES Fruity, woody, pineapple-like"
        (hand-run 01's find, and the reason the rule exists),
      - the production extractor rejected it,
      - and score.py's docstring claimed to mirror extract() while measuring something
        extract() does not do.

    Caught only because the held-out sampler reported 3,424 accepted where extract had
    reported 3,191. Reconciling two numbers that should have matched is what found it;
    reading the code had not.

    Returns (accepted, reason) — the reason string is used for stats and for the
    disagreement reports, so keep the labels stable.
    """
    if not (25 < len(s) < 320):        return False, "length"
    for rx, lbl in EXCLUDE:
        if rx.search(s):               return False, lbl
    # HEADING path REMOVED 2026-08-03. It was built for "PERFUME PROPERTIES Fruity,
    # woody, pineapple-like" — and a descriptor-only heading, by definition, names no
    # molecule, so at sentence scope it can never yield a row. The held-out round
    # confirmed it: "Odor characteristics: scallion, pickle." is exactly the target
    # case and is correctly a drop. The regex also matched ordinary prose ("in addition
    # to its excellent odour characteristics..."), accepting it with no verb and no
    # name. Recover these with a context window, not with this rule.
    if not ODOUR.search(s):            return False, "no odour word"
    if not DESCR.search(s):            return False, "no description verb"
    if not named(s):                   return False, "no compound/example name"
    return True, "kept"

def extract() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, stats = [], dict(docs=0, sents=0, odour=0, excluded=0, kept=0)
    for f in sorted(RAW.glob("*.txt")):
        text = norm(f.read_text(encoding="utf-8"))
        stats["docs"] += 1
        for s in SENT.split(text):
            stats["sents"] += 1
            if 25 < len(s) < 320 and ODOUR.search(s): stats["odour"] += 1
            ok, why = decide(s)
            if not ok:
                # everything that isn't one of the four structural misses is an
                # EXCLUDE rule firing, and those are the interesting rejections
                if why not in ("length", "no odour word", "no description verb",
                               "no compound/example name"):
                    stats["excluded"] += 1
                continue
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
