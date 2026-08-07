#!/usr/bin/env python3
"""
OpenScent — independent attestations per term. The number that should have existed first.

    python3 attest.py            # ON THE HARVEST BOX (needs corpus/raw/)

THE PROBLEM THIS ENDS
---------------------
Three counters, each fixing the last one's blind spot, none of them right:

  occurrences  a term repeated 124x inside one patent scored 124.       (2026-08-04)
  documents    a sentence copied across 124 patents scored 124.         (2026-08-05)
  boilerplate  scored the term, not the passage, and used a wider
               window than vocab.py, so its ratios were not comparable.  (2026-08-05)

All three approximate the same underlying quantity and none measures it:

    INDEPENDENT ATTESTATION — how many DISTINCT pieces of text assert this term.

That is what Mike's "60-100 tags at >=30 molecules each" needs. This file computes it.

METHOD
------
Uses vocab.py's OWN `PRE`, `POST` and `STOP` by importing them. That is deliberate and
load-bearing: boilerplate.py's separate window is exactly why `spruce` read 0.30 there and
~1.0 in reality, and why its docs column said 360 where vocab.py said 124. Two counters
that disagree about what they are counting cannot be compared, so this one does not get
its own definition.

For every harvest hit, take the enclosing sentence, normalise it, and count DISTINCT
sentences per term. A sentence copied into 100 patents is ONE attestation.

    docs           patents where the term was harvested        (what vocab.py reports)
    attestations   distinct sentences it was harvested from    (what actually supports it)
    copy_factor    docs / attestations

    copy_factor ~1.0   every document said it in its own words   -> real
    copy_factor >3     mostly copied text                        -> suspect
    top_share          share of docs carried by the single most repeated sentence

WHAT IT STILL CANNOT DECIDE
---------------------------
Whether a repeated sentence is worthless. Standard phrasing is legitimate, and two labs
independently writing "fresh green note" is real agreement. But the passages found so far
are enumerations — "suitable fragrances include ... apple, cherry, grape, pear" — which
name an application field and assert nothing about any molecule. Distinguishing an
enumeration from an assertion is a human call. This prints the evidence for it.
"""
from __future__ import annotations
import collections, os, pathlib, re, sys

_here = pathlib.Path(__file__).resolve().parent
# vocab.py lives beside this file in the repo, but one level UP on the harvest box
# (/opt/vocab.py vs /opt/openscent/attest.py). Search both rather than requiring
# PYTHONPATH — a missing import here is silent about which copy it would have used,
# and a stale vocab.py means a different STOP list and incomparable numbers.
for _p in (_here, _here.parent, pathlib.Path("/opt")):
    if (_p / "vocab.py").exists():
        sys.path.insert(0, str(_p))
        print(f"rules from  {_p / 'vocab.py'}")
        break
else:
    sys.exit("vocab.py not found — attest.py must use ITS regexes, not a copy.")

from vocab import PRE, POST, STOP, ROOT   # noqa: E402  — same rules, by construction

RAW = ROOT / "corpus" / "raw"
ONT = ROOT / "ontology"
SPLIT = re.compile(r"(?<=[.;])\s+")
WS = re.compile(r"\s+")


def sentence_at(text: str, pos: int) -> str:
    """The sentence containing character `pos`, normalised."""
    a = text.rfind(". ", 0, pos) + 1
    b = text.find(". ", pos)
    if b == -1:
        b = min(len(text), pos + 400)
    return WS.sub(" ", text[a:b]).strip().lower()[:400]


def main() -> int:
    if not RAW.exists() or not any(RAW.glob("*.txt")):
        sys.exit(f"no corpus at {RAW} — run this on the box holding corpus/raw/")
    files = sorted(RAW.glob("*.txt"))

    docs = collections.defaultdict(set)              # term -> {filename}
    sents = collections.defaultdict(collections.Counter)  # term -> {sentence: n_docs}

    for i, f in enumerate(files, 1):
        if i % 500 == 0:
            print(f"  ...{i}/{len(files)}", flush=True)
        text = f.read_text(errors="ignore")
        local = collections.defaultdict(set)
        for rx, grp in ((PRE, 1), (POST, 1)):
            for m in rx.finditer(text):
                s = sentence_at(text, m.start())
                for w in re.split(r"[,\s]+|\band\b", m.group(grp)):
                    w = (w or "").strip("- ").lower()
                    if len(w) > 2 and w not in STOP and not w.isdigit():
                        local[w].add(s)
        for w, ss in local.items():
            docs[w].add(f.name)
            for s in ss:
                sents[w][s] += 1

    rows = []
    for w, dd in docs.items():
        c = sents[w]
        att = len(c)
        top_s, top_n = c.most_common(1)[0]
        rows.append((w, len(dd), att, len(dd) / att, top_n / len(dd), top_s))
    rows.sort(key=lambda r: -r[1])

    dest = ONT / "attestations.tsv"
    with dest.open("w", encoding="utf-8") as fh:
        fh.write("# INDEPENDENT ATTESTATIONS — distinct sentences a term was harvested from.\n")
        fh.write("# A sentence copied into 100 patents is ONE attestation.\n")
        fh.write("# Uses vocab.py's own PRE/POST/STOP, so `docs` matches vocab.py exactly.\n")
        fh.write("# term\tdocs\tattestations\tcopy_factor\ttop_share\ttop_sentence\n")
        for w, d, a, cf, ts, s in rows:
            fh.write(f"{w}\t{d}\t{a}\t{cf:.2f}\t{ts:.3f}\t{s[:300]}\n")

    print(f"\ncorpus     {len(files)} patents")
    print(f"terms      {len(rows)}")
    for thr in (30, 20):
        d_ok = sum(1 for r in rows if r[1] >= thr)
        a_ok = sum(1 for r in rows if r[2] >= thr)
        print(f">={thr}:  {d_ok:4d} by documents  ->  {a_ok:4d} by ATTESTATIONS")
    print(f"\n{'term':<16}{'docs':>6}{'attest':>8}{'copy':>7}{'top%':>7}")
    print("-" * 44)
    for w, d, a, cf, ts, s in [r for r in rows if r[1] >= 30][:45]:
        flag = "  <-- copied" if cf >= 3 or ts >= .5 else ""
        print(f"{w:<16}{d:>6}{a:>8}{cf:>7.1f}{ts*100:>6.0f}%{flag}")
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
