#!/usr/bin/env python3
"""
passage_probe.py — how many rows is sentence scope actually costing us?

TWO MACHINES, BECAUSE THE DATA IS ON TWO MACHINES. Same split as the rest of the project:
Hetzner holds `corpus/raw/`, the Mac holds the rows and the ontology, and `/opt/openscent`
is a bare deployment with no `.git` and no `review.jsonl`.

  ON HETZNER — needs only harvest.py and the raw text:
    scp pipeline/passage_probe.py <hetzner>:/opt/openscent/pipeline/
    OPENSCENT_ROOT=/opt/openscent python3 pipeline/passage_probe.py --dump pairs.jsonl

  BACK ON THE MAC — the tag analysis, where the rows live:
    scp <hetzner>:/opt/openscent/pairs.jsonl .
    python3 pipeline/passage_probe.py --analyse pairs.jsonl

Run without `--dump` on a machine that has both and it does the whole thing at once.
Options: `--window N` (sentences to look back, default 1), `--examples N`.

It fetches NOTHING and writes nothing but the dump file. It counts.

The two-machine split is not fussiness. On 2026-08-19 a shell mix-up ran Mac commands on
Hetzner and vice versa and produced a 503 storm and a half-written `patent-ids.json`.
Keeping each step on the machine that owns its data is how that stopped happening.

WHAT IT MEASURES, AND WHY THAT NUMBER AND NOT ANOTHER
-----------------------------------------------------
`harvest.py` accepts a sentence only if it carries BOTH an odour claim and a compound
name. Its own comment, written when the HEADING path was removed on 2026-08-03, says of
the sentences it drops:

    Recover these with a context window, not with this rule.

Nobody has counted them. Four separate findings now point at sentence scope as the
binding recall constraint — the HEADING removal, `organoleptic-colon`'s 345 molecule-less
sentences (2026-09-07), `t09` in the test set, and the 2026-09-10 sandalwood sample where
ANAPHORA WAS THE LARGEST SINGLE CAUSE OF REJECTION, 6 of 24. Four arguments and no
measurement is how the 418 mistake happened.

THERE ARE TWO POPULATIONS, AND THE FIRST DRAFT OF THIS SCRIPT COUNTED ONLY ONE
------------------------------------------------------------------------------
The obvious population is sentences `decide()` DROPS for "no compound/example name" while
a sentence before them names one. That is not where most of the loss is.

The second population is sentences `decide()` ACCEPTS and review then REJECTS, because
the name it found was not a compound. Tested against the case that motivated all of this,
US5326748A:

    "It possesses a very strong sandalwood note, very woody, with a natural sandal
     character and a dry woody note reminiscent of the odor of cedarwood."

`decide()` keeps it. Not because it names anything — because `NAMED_SUFFIX` matched
**"natural"** (`natur` + `al`). The sentence sits in the queue, costs a reviewer a reading,
and is rejected for anaphora. The 2026-09-10 sandalwood sample is full of these: 6 of 24
rejections were anaphoric, and every one had been extracted.

So this counts a sentence as recoverable when it carries an odour claim and a description
verb and EITHER names nothing OR is explicitly anaphoric, and a sentence shortly before it
names a compound. `ODOUR`, `DESCR`, `DESCR_COLON` and `named()` are all imported from
harvest.py; only the composition differs, and it differs deliberately, because
`decide()`'s name test is the unreliable part here rather than the arbiter.

Pairs are counted against terms still short of the bar, because a pair feeding `sweet`
(213) buys nothing.

THE NUMBER IS A CEILING, NOT A YIELD
------------------------------------
Every pair still has to be adjudicated, and passage rows would be adjudicated HARDER than
sentence rows, because the reviewer must also judge whether the reference resolves. Expect
precision below the sentence-scope figure, not equal to it. `--examples` prints pairs to
read: read them before believing the total. That instruction is here because the same
script pattern reported 298 usable rows for a PubChem heading on 2026-09-10 and the true
answer was zero.

WHAT ADOPTING THIS WOULD COST, WHICH IS NOT A CODE CHANGE
---------------------------------------------------------
A passage row makes a claim the corpus does not currently make anywhere. Today a row says:
this sentence says this molecule smells of these things, and every span is verbatim in it.
A passage row says: this sentence says "It" smells of these things, and a human decided
"It" is the compound named in the previous sentence. **That is a RESOLVED REFERENCE, a
judgement rather than an extraction**, and REVIEW-RULES rejects it today by name
("anaphora, nothing named").

The verbatim invariant survives — both spans stay literal substrings of their own
sentences, nothing is generated. What changes is the claim. So if this is adopted:

  1. the row records BOTH sentences and which supplied which span, so a reader can
     check the resolution rather than trust it;
  2. it carries a flag marking the link as human-resolved;
  3. passage rows stay SEPARABLE, so anyone can filter to sentence-scope-only and get
     today's stricter guarantee unchanged. The existing corpus must not get weaker
     because a looser class was added beside it;
  4. precision is measured separately for passage rows and NEVER inherited.

And the danger has a name already: `pubchem.py`'s docstring calls the worst patent failure
"Example 3 resolving to the wrong structure — an accurate odour description bound to the
wrong molecule, which looks exactly like a valid row." Passage scope multiplies the
chances of exactly that. That is the argument against, and it is a real one.

DEFINITIONS ARE IMPORTED, NEVER REIMPLEMENTED
---------------------------------------------
`decide()`, `named()`, `SENT`, `ODOUR`, `DESCR` all come from harvest.py. A probe that
writes its own copy of the accept path measures the probe. That has cost this project two
days once already (score.py vs extract(), 2026-08-03) and a wrong 64%-vs-22.5% estimate
(propose.py, 2026-09-10).
"""
from __future__ import annotations
import collections, importlib.util, json, os, pathlib, random, re, sys

_here = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(os.environ.get("OPENSCENT_ROOT",
           _here.parent if _here.name == "pipeline" else _here / "openscent"))
BAR = 30

# A descriptor sentence whose subject is one of these is the high-confidence case: it
# explicitly points backwards and names nothing. "The compounds of formula (I)" is NOT
# here — that is a family, and it stays a reject at any scope.
ANAPHORIC = re.compile(r"^\s*(it|its|this compound|the compound|the novel compound|"
                       r"this material|the material|the product|this product|"
                       r"the latter|the former|this substance|the substance)\b", re.I)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "pipeline" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def short_terms(st, surf):
    """Terms still under the bar, counted exactly as status.py counts them."""
    counts: dict = collections.defaultdict(set)
    for r in st.jsonl(st.REVIEW):
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
    return counts, {t for t in set(surf.values()) if len(counts.get(t, ())) < BAR}


def analyse_dump(path: pathlib.Path, st, surf, n_examples: int) -> int:
    """The half that needs the corpus: which of these pairs would buy a TAG."""
    if not path.exists():
        print(f"!! {path} not found")
        return 2
    counts, short = short_terms(st, surf)
    rx = re.compile(r"\b(" + "|".join(sorted(map(re.escape, surf), key=len, reverse=True))
                    + r")\b", re.I)
    below: collections.Counter = collections.Counter()
    kinds: collections.Counter = collections.Counter()
    examples: list = []
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        total += 1
        kinds["anaphoric" if rec["anaphoric"] else "names nothing"] += 1
        kinds["already extracted" if rec["extracted_today"] else "never extracted"] += 1
        hits = {surf[m.group(0).lower()] for m in rx.finditer(rec["sentence"])
                if m.group(0).lower() in surf}
        for t in hits & short:
            below[t] += 1
        if hits & short:
            examples.append((rec["source_id"], rec["prev"][-160:], rec["sentence"][:200],
                             sorted(hits & short), rec["anaphoric"]))
    # EXAMPLES MUST BE A RANDOM SAMPLE, NOT THE FIRST N.
    # They were the first N until 2026-09-10, which meant every run printed the same
    # dozen rows from the US100-104 range. Re-running at --window 2 therefore looked
    # identical to --window 1 while the underlying set had grown by 1,546 pairs, and the
    # additions — which were the interesting part — were never shown. Seeded so a rerun
    # prints the same sample and two people can discuss the same rows.
    random.seed(20260910)
    anas = [e for e in examples if e[4]]
    picked = random.sample(anas, min(n_examples, len(anas))) if anas else \
             random.sample(examples, min(n_examples, len(examples)))
    print(f"{total} pairs from {path.name}   {dict(kinds)}\n")
    if below:
        print("BELOW-BAR TERMS THEY WOULD FEED (the only column that buys tags):")
        for t, c in below.most_common(25):
            have = len(counts.get(t, ()))
            print(f"   {t:<16}{have:>4} have, needs {BAR-have:<3}{c:>5} pairs")
        print(f"\n   total below-bar pairs: {sum(below.values())}")
    else:
        print("no pairs land on a term below the bar — passage scope buys rows, not tags")
    print(f"\n{'-'*72}\nEXAMPLES — seeded random sample of the ANAPHORIC subset, which is")
    print(f"the only part worth reading. READ THEM BEFORE BELIEVING THE TOTAL.\n{'-'*72}")
    for sid, prev, s, tags, _ in picked:
        print(f"\n{sid}   short terms: {tags}")
        print(f"   PREV: ...{prev.strip()}")
        print(f"   THIS: {s.strip()}")
    print(f"\n{'-'*72}")
    print("A CEILING, not a yield. Measured 2026-09-10 on two seeded samples: ~25% of the")
    print("anaphoric subset is admissible. The rest is composition-level language,")
    print("families, and surfactant boilerplate. Weight the totals accordingly.")
    return 0


def main(argv: list[str]) -> int:
    window = 1
    n_examples = 12
    if "--window" in argv:
        window = int(argv[argv.index("--window") + 1])
    if "--examples" in argv:
        n_examples = int(argv[argv.index("--examples") + 1])

    dump = argv[argv.index("--dump") + 1] if "--dump" in argv else None
    analyse = argv[argv.index("--analyse") + 1] if "--analyse" in argv else None

    # The tag analysis needs the rows and the ontology; the scan needs only harvest.py and
    # the raw text. Load each only where it is actually available, so a bare deployment
    # can do the half it can do instead of failing on an import it does not need.
    st = surf = None
    counts: dict = collections.defaultdict(set)
    short: set = set()
    if not dump:
        st = _load("status")
        surf = st.load_tags()

    if analyse:
        return analyse_dump(pathlib.Path(analyse), st, surf, n_examples)

    H = _load("harvest")
    raw_dir = H.RAW
    docs = sorted(raw_dir.glob("*.txt"))
    if not docs:
        print(f"!! no documents in {raw_dir}")
        print("   This must run where corpus/raw/ lives — Hetzner, not the Mac:")
        print("   OPENSCENT_ROOT=/opt/openscent python3 pipeline/passage_probe.py")
        return 2

    # Terms still short of the bar — only computable where the rows are. On a --dump run
    # this box has no review.jsonl, and the analysis half happens later on the Mac.
    if not dump:
        counts, short = short_terms(st, surf)

    pairs = 0
    anaphoric = 0
    below: collections.Counter = collections.Counter()
    reasons: collections.Counter = collections.Counter()
    per_doc: collections.Counter = collections.Counter()
    examples: list = []

    rx = None if dump else re.compile(
        r"\b(" + "|".join(sorted(map(re.escape, surf), key=len, reverse=True)) + r")\b", re.I)
    dump_fh = open(dump, "w", encoding="utf-8") if dump else None

    print(f"reading {len(docs)} documents from {raw_dir}, window={window} sentence(s)\n")
    for n, path in enumerate(docs, 1):
        if n % 500 == 0:
            print(f"  ...{n}/{len(docs)}")
        text = H.norm(path.read_text(encoding="utf-8", errors="ignore"))
        sents = H.SENT.split(text)
        for i, s in enumerate(sents):
            # Same gates as decide(), composed differently — see the docstring. A
            # sentence qualifies if it makes an odour claim and either names nothing or
            # points backwards explicitly.
            if not (25 < len(s) < 320):
                continue
            if any(r.search(s) for r, _ in H.EXCLUDE):
                continue
            if not H.ODOUR.search(s):
                continue
            if not (H.DESCR.search(s) or H.DESCR_COLON.search(s)):
                continue
            is_ana = bool(ANAPHORIC.match(s))
            if H.named(s) and not is_ana:
                continue                       # names something and does not point back
            extracted_today = H.decide(s)[0]
            # Does something just before it name a compound?
            found = None
            for back in range(1, window + 1):
                j = i - back
                if j < 0:
                    break
                prev = sents[j]
                if len(prev) > 600:
                    break                      # a wall of text is not a referent
                if H.named(prev):
                    found = prev
                    break
            if not found:
                reasons["no name in window"] += 1
                continue
            pairs += 1
            per_doc[path.stem] += 1
            if is_ana:
                anaphoric += 1
            reasons["already extracted, rejected at review" if extracted_today
                    else "never extracted"] += 1
            rec = {"source_id": path.stem, "anaphoric": is_ana,
                   "extracted_today": extracted_today, "prev": found, "sentence": s}
            if dump_fh:
                dump_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                continue
            hits = {surf[m.group(0).lower()] for m in rx.finditer(s)
                    if m.group(0).lower() in surf}
            for t in hits & short:
                below[t] += 1
            if len(examples) < n_examples and (is_ana or (hits & short)):
                examples.append((path.stem, found[-160:], s[:200], sorted(hits & short)))

    if dump_fh:
        dump_fh.close()
        print(f"\n{pairs} pairs written -> {dump}")
        print(f"  explicitly anaphoric: {anaphoric}"
              f"   never extracted: {reasons['never extracted']}"
              f"   already extracted and rejected: "
              f"{reasons['already extracted, rejected at review']}")
        print(f"  no name in window (unreachable): {reasons['no name in window']}")
        print("\nNow copy it to the Mac, where the rows and the ontology live:")
        print(f"  scp root@<hetzner>:{pathlib.Path(dump).resolve()} .")
        print(f"  python3 pipeline/passage_probe.py --analyse {pathlib.Path(dump).name}")
        print("\nThe below-bar breakdown is the number that decides this, and it cannot")
        print("be computed here — this box has no review.jsonl.")
        return 0

    print(f"\n{'='*72}")
    print(f"PAIRS RECOVERABLE AT PASSAGE SCOPE : {pairs}")
    print(f"  of which explicitly anaphoric    : {anaphoric}   "
          f"({100*anaphoric//max(1,pairs)}% — the high-confidence subset)")
    print(f"  never extracted                  : {reasons['never extracted']}")
    print(f"  ALREADY extracted, rejected at review for anaphora : "
          f"{reasons['already extracted, rejected at review']}")
    print(f"     ^ these already cost a reviewer a reading and produced nothing")
    print(f"  odour sentences with NO name in window (unreachable): "
          f"{reasons['no name in window']}")
    print(f"  documents contributing            : {len(per_doc)}")
    print(f"{'='*72}")
    if below:
        print("\nBELOW-BAR TERMS THEY WOULD FEED (the only column that buys tags):")
        for t, c in below.most_common(20):
            have = len(counts.get(t, ()))
            print(f"   {t:<16}{have:>4} have, needs {BAR-have:<3}{c:>5} pairs")
        print(f"\n   total below-bar pairs: {sum(below.values())}")
    else:
        print("\nno pairs land on a term below the bar — passage scope buys rows, not tags")

    print(f"\n{'-'*72}\nEXAMPLES — READ THESE BEFORE BELIEVING THE TOTAL\n{'-'*72}")
    for sid, prev, s, tags in examples:
        print(f"\n{sid}   short terms: {tags}")
        print(f"   PREV: ...{prev.strip()}")
        print(f"   THIS: {s.strip()}")
    print(f"\n{'-'*72}")
    print("This is a CEILING. Every pair still needs adjudicating, and passage rows are")
    print("harder to adjudicate than sentence rows because the reference must also be")
    print("judged. Expect precision BELOW the sentence-scope figure. See the docstring")
    print("for what adopting this would cost the corpus's central claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
