#!/usr/bin/env python3
"""
OpenScent — repeated-passage finder. The unit boilerplate.py misses.

    python3 passages.py [min_docs_for_a_passage] [min_docs_for_a_term]

WHY THIS EXISTS
---------------
boilerplate.py scores ONE TERM AT A TIME: what share of this term's documents carry one
identical context. That found `woodland` (0.87) and `forest` (0.74) and stopped there.

Reading the report's top_context column showed the flaw. Six flagged terms were not six
problems — they were THREE paragraphs:

  1. "...musk, flower scents such as lavender-like, rose-like, iris-like, carnation-like.
      other pleasant scents include herbal and woodland scents derived from pine, spruce
      and other forest smells."
  2. "lilac, lily, magnolia, mimosa, narcissus, freshly-cut hay, orange blossom, orchid,
      reseda, sweet pea, trefle..."
  3. "...of a sweet, fully ripe apple, the odor would be termed 'nice'. however, the odor
      of a typically tart apple can also be concise."

Each carries a DOZEN vocabulary terms. A term can score a harmless 0.30 and still be
nothing but a passenger in a paragraph shared with ten others — `lily` (0.30) and
`blossom` (0.25) are in paragraph 2 and neither looks bad alone.

So the unit to count is the REPEATED PASSAGE, not the word. This file counts passages and
reports which vocabulary each one carries.

WHAT IT DOES
------------
Splits every patent into sentences, normalises them, and counts how many DISTINCT
DOCUMENTS carry each one. Any sentence appearing in many documents is copied text, not
independent observation. For each, it lists the vocabulary terms inside.

READING THE OUTPUT
------------------
A passage in N documents contributes ONE attestation, not N — however many terms it
carries. Terms whose support comes mostly from such passages are not attested at all.

A repeated sentence is not automatically worthless: standard phrasing exists, and two
labs independently writing "fresh green note" is real agreement. The judgement is whether
the sentence ASSERTS something about a specific molecule or merely enumerates vocabulary.
Paragraphs 1-3 above all enumerate. That call stays human — this script only finds them.
"""
from __future__ import annotations
import collections, os, pathlib, re, sys

_here = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(os.environ.get("OPENSCENT_ROOT",
           _here.parent if _here.name == "pipeline" else _here / "openscent"))
RAW = ROOT / "corpus" / "raw"
ONT = ROOT / "ontology"

SPLIT = re.compile(r"(?<=[.;])\s+")
WS = re.compile(r"\s+")


def load_terms(min_docs: int) -> dict[str, str]:
    src = ONT / "harvested-terms-classified.tsv"
    if not src.exists():
        src = ONT / "harvested-terms-corpus.tsv"
    out = {}
    for line in src.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        p = line.split("\t")
        if len(p) >= 3 and p[2].strip().isdigit() and int(p[2]) >= min_docs:
            out[p[0].strip().lower()] = p[3].strip() if len(p) > 3 else ""
    return out


def main() -> int:
    min_pass = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    min_term = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    terms = load_terms(min_term)
    print(f"vocabulary  {len(terms)} terms at >={min_term} docs")

    if not RAW.exists() or not any(RAW.glob("*.txt")):
        sys.exit(f"no corpus at {RAW} — run this on the box holding corpus/raw/")

    files = sorted(RAW.glob("*.txt"))
    seen: dict[str, set[str]] = collections.defaultdict(set)
    for i, f in enumerate(files, 1):
        if i % 500 == 0:
            print(f"  ...{i}/{len(files)}", flush=True)
        for s in SPLIT.split(f.read_text(errors="ignore")):
            s = WS.sub(" ", s).strip().lower()
            if 40 < len(s) < 600:
                seen[s].add(f.name)
    print(f"corpus      {len(files)} patents, {len(seen)} distinct sentences\n")

    rx = re.compile(r"\b(" + "|".join(re.escape(t) for t in
                    sorted(terms, key=len, reverse=True)) + r")\b")
    rows = []
    for s, docs in seen.items():
        if len(docs) < min_pass:
            continue
        hits = sorted(set(rx.findall(s)))
        if hits:
            rows.append((len(docs), hits, s))
    rows.sort(key=lambda r: -(r[0] * len(r[1])))

    dest = ONT / "repeated-passages.tsv"
    with dest.open("w", encoding="utf-8") as fh:
        fh.write("# Sentences appearing in many DISTINCT patents, with the vocabulary they carry.\n")
        fh.write("# Each passage is ONE attestation regardless of how many documents repeat it.\n")
        fh.write("# docs\tn_terms\tterms\tpassage\n")
        for n, hits, s in rows:
            fh.write(f"{n}\t{len(hits)}\t{','.join(hits)}\t{s[:500]}\n")

    print(f"{len(rows)} repeated passages carrying vocabulary (>= {min_pass} docs)\n")
    print("=" * 78)
    for n, hits, s in rows[:15]:
        print(f"\n{n} patents · {len(hits)} terms · {', '.join(hits)}")
        print(f"  \"{s[:300]}{'…' if len(s) > 300 else ''}\"")

    poisoned = collections.Counter()
    for n, hits, _ in rows:
        for h in hits:
            poisoned[h] = max(poisoned[h], n)
    print("\n" + "=" * 78)
    print("\nTerms whose largest repeated passage covers the most documents:")
    print(f"{'term':<18}{'cls':<5}{'max passage docs':>18}")
    for t, n in poisoned.most_common(35):
        print(f"{t:<18}{terms.get(t,'-') or '-':<5}{n:>18}")
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
