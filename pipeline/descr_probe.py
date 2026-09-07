#!/usr/bin/env python3
"""
descr_probe.py — READ ONLY. How much would ONE named DESCR extension actually admit?

    python3 descr_probe.py

RUN ON HETZNER. Needs corpus/raw/ and harvest.py beside it. Writes nothing.

WHY THIS AND NOT "LOOSEN THE FILTER"
------------------------------------
exclusion_probe.py (2026-09-07) found 18,545 dropped sentences mentioning the five tags
nearest the bar, 11,185 of them with a compound name visible. That number invites a
broad loosening and would punish it: the two largest classes are dominated by ingredient
enumerations —

    Spanish sage oil; sandalwood oil; celery seed oil; spike lavender oil; ...

— which pass named() because a list of oils is full of suffix-matching words, not
because any molecule is being given an odour. The 320-char bound exists for these.

The recoverable class is narrower and has a shape. DESCR requires a verb
(has / possesses / exhibits). Patents also write the same assertion with a COLON:

    Odor description of 2,3,5,5-tetramethylcyclohex-2-en-1-one: tobacco, spicy, leather.
    Organoleptic properties: a woody, humus odor, with patchouli and amber connotation

Molecule named, descriptors listed, attribution unambiguous, no verb anywhere. These are
currently dropped as "no description verb" (or caught by EXCLUDE:synthesis prose).

WHAT THIS MEASURES
------------------
For each candidate pattern, how many sentences it would NEWLY admit — that is, sentences
decide() drops today where the ONLY failing test is DESCR, and every other gate
(length, ODOUR, named) already passes. A pattern that admits sentences failing two gates
is not a DESCR fix.

Reported per pattern and pooled, because the patterns overlap and the union is what a
change would actually cost in review time.

THIS IS NOT A SCORE. TESTSET.md still governs.
Any edit to DESCR must be scored with score.py before and after, on testset.jsonl. This
probe says whether a change is WORTH scoring, not whether it is good.
"""
from __future__ import annotations
import collections, os, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
os.environ.setdefault("OPENSCENT_ROOT", str(HERE.parent))
sys.path.insert(0, str(HERE))
import harvest  # noqa: E402

# Candidate DESCR extensions. Deliberately narrow and named, so that whichever is
# adopted can be quoted in the DEVLOG as itself rather than as "we loosened DESCR".
CANDIDATES = [
    ("odour-description-of",
     re.compile(r"\b(odou?r|organoleptic|olfactive)\s+(description|propert\w+|"
                r"characteristic\w*)\s+of\b[^:]{0,120}:", re.I)),
    ("organoleptic-colon",
     re.compile(r"\b(odou?r|organoleptic|olfactive)\s+"
                r"(description|propert\w+|characteristic\w*|note\w*)\s*:", re.I)),
    ("described-as",
     re.compile(r"\b(is|are|was|were)\s+described\s+(as|to\s+be)\b", re.I)),
    ("smells-of",
     re.compile(r"\bsmell(?:s|ing)?\s+(of|like)\b", re.I)),
    ("imparts",
     re.compile(r"\bimparts?\b|\bconfers?\b|\bgives?\s+(?:a|an)\b", re.I)),
]


def main() -> int:
    docs = sents = 0
    only_descr = 0                       # drops where DESCR is the ONLY failing gate
    hits = collections.Counter()
    pooled = 0
    examples: dict[str, list[str]] = collections.defaultdict(list)

    for f in sorted(harvest.RAW.glob("*.txt")):
        docs += 1
        text = harvest.norm(f.read_text(encoding="utf-8"))
        for s in harvest.SENT.split(text):
            sents += 1
            ok, why = harvest.decide(s)
            if ok or why != "no description verb":
                continue
            # DESCR is the only failure by construction: decide() tests length, then
            # EXCLUDE, then ODOUR, then DESCR, then named() — so reaching this label
            # means length/EXCLUDE/ODOUR already passed. named() is still untested.
            if not harvest.named(s):
                continue
            only_descr += 1
            matched = False
            for name, rx in CANDIDATES:
                if rx.search(s):
                    hits[name] += 1
                    matched = True
                    if len(examples[name]) < 5:
                        examples[name].append(f"{f.stem}  {s[:200]}")
            if matched:
                pooled += 1

    print(f"documents {docs} · sentences {sents}\n")
    print(f"dropped as 'no description verb' WITH a compound name visible: {only_descr}")
    print("(these are the only sentences a DESCR change can convert — everything else")
    print(" fails another gate too, and a DESCR edit will not reach it)\n")

    print(f"{'candidate pattern':<24}{'admits':>8}{'share':>8}")
    print("-" * 40)
    for name, _ in CANDIDATES:
        n = hits[name]
        print(f"{name:<24}{n:>8}{(n / only_descr * 100 if only_descr else 0):>7.1f}%")
    print("-" * 40)
    print(f"{'UNION (all patterns)':<24}{pooled:>8}"
          f"{(pooled / only_descr * 100 if only_descr else 0):>7.1f}%")
    print(f"\nAt ~0.2 whole-queue precision the union is ~{int(pooled * 0.2)} usable rows.")
    print("Do not substitute 0.82 — that is precision within the productive subset.")

    for name, _ in CANDIDATES:
        if not examples[name]:
            continue
        print(f"\n--- {name} ({hits[name]}) ---")
        for e in examples[name]:
            print(f"  {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
