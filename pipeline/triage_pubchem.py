#!/usr/bin/env python3
"""
triage_pubchem.py — resolve the `expression_risk: review` rows before publication.

    python3 pipeline/triage_pubchem.py            # report
    python3 pipeline/triage_pubchem.py --write

WHY
---
`rows_pubchem.py` flags rows it is not willing to publish unreviewed. 77 carried
`expression_risk: review` and nobody had looked. That is fine while the repo is private
and not fine the moment it goes public, because the flag exists to catch exactly the two
things a public CC0 dataset must not contain: text that is not ours to republish, and
rows whose tag the source sentence does not actually support.

Rows are MARKED, never deleted — `excluded: true` plus a reason. The row stays in the
file so the decision is auditable and reversible; consumers (and status.py) skip excluded
rows. Deleting would destroy the evidence for a call that is partly a judgement.

THE TWO CATEGORIES, WHICH THE ORIGINAL FLAG CONFLATED
-----------------------------------------------------
1. PROVENANCE. Three rows quote flavour-industry register — "Odor description at 0.01%",
   "Aroma characteristics at 1.0%", "Detection: 20 ppb". The HSDB *record* is public
   domain, but HSDB cites its sources, and that phrasing is the house style of commercial
   flavour databases rather than of a safety datasheet. Origin is not provable from the
   record alone. Three rows are not worth the argument, and the README's rule that
   nothing GoodScents- or Leffingwell-derived touches any phase is worth more than they
   are. Dropped on suspicion, deliberately.

2. ATTRIBUTION. Four rows where the tag is not supported by the sentence, under the same
   rules as REVIEW-RULES.md applies to patents. Note that a negation cue is NOT by itself
   a reject — what matters is what the negation attaches to:

     DECAHYDRONAPHTHALENE  "resembling menthol; pure decalin does not smell of
                            naphthalene"  -> KEEP. The negation is on naphthalene. The
                            menthol resemblance is asserted plainly.
     ISOBUTYRIC ACID       "Pungent odor ... but not as unpleasant"  -> KEEP for
                            `pungent`. The negation is on "unpleasant".
     ISOBUTYRIC ACID       -> DROP for `acid`. The span came from "butyric acid" — the
                            name of the REFERENCE compound, not a descriptor. A
                            substring match inside a molecule name, which is the
                            reference-point failure REVIEW-RULES.md names.
     Nornicotine           "less pungent than that of nicotine"  -> DROP. A comparative.
                            The sentence asserts an amine odour and compares pungency; it
                            does not assert that nornicotine is pungent.
     INDOLE                "ALMOST FLORAL ... WHEN HIGHLY PURIFIED, OTHERWISE ...
                            FECES"  -> DROP. Hedged twice, and conditional on a
                            purification state. Indole genuinely is used in florals, which
                            is what makes this tempting; the sentence still does not
                            support the tag, and "when in doubt reject" applies hardest
                            where prior knowledge is arguing against the text.

None of the seven touches a tag near the bar.
"""
from __future__ import annotations
import json, pathlib, re, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
PUB = ROOT / "corpus" / "rows" / "pubchem-rows.jsonl"

# category 1 — flavour-industry register inside an HSDB record
TRADE = re.compile(r"aroma characteristics|odor description at|detection:\s*\d+\s*pp",
                   re.I)

# category 2 — (molecule_name, tag) pairs the sentence does not support
UNSUPPORTED = {
    ("ISOBUTYRIC ACID", "acid"):
        "span 'acid' is part of the reference compound name 'butyric acid', not a descriptor",
    ("Nornicotine", "pungent"):
        "comparative — 'less pungent than nicotine' does not assert pungency",
    ("INDOLE", "floral"):
        "hedged and conditional — 'ALMOST floral ... WHEN HIGHLY PURIFIED, otherwise feces'",
}


def main() -> int:
    write = "--write" in sys.argv
    head, rows = None, []
    for line in PUB.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith('{"_comment"'):
            head = line
            continue
        rows.append(json.loads(line))

    hits = []
    for r in rows:
        if r.get("excluded"):
            continue
        key = (r.get("molecule_name", ""), r.get("tag", ""))
        reason = None
        if TRADE.search(r.get("quote", "")):
            reason = ("provenance", "flavour-industry register quoted inside an HSDB "
                                    "record; origin not establishable from the record")
        elif key in UNSUPPORTED:
            reason = ("attribution", UNSUPPORTED[key])
        if reason:
            r["excluded"] = True
            r["excluded_category"] = reason[0]
            r["excluded_reason"] = reason[1]
            r["excluded_on"] = "2026-09-05"
            hits.append((r, reason))

    if not hits:
        print("nothing to exclude — already triaged, or the rules matched nothing")
        return 0

    for cat in ("provenance", "attribution"):
        sel = [(r, x) for r, x in hits if x[0] == cat]
        print(f"\n{cat.upper()}  ({len(sel)} rows)")
        for r, x in sel:
            print(f"  {r['molecule_name'][:28]:<30}{r['tag']:<10}{x[1]}")
            print(f"      {r['quote'][:100]}")

    kept = sum(1 for r in rows if not r.get("excluded"))
    print(f"\nexcluded {len(hits)}   remaining {kept} of {len(rows)}")

    still = [r for r in rows
             if r.get("expression_risk") == "review" and not r.get("excluded")]
    print(f"reviewed-and-kept: {len(still)} rows that carried the flag but pass")

    if not write:
        print("\nDry run. Add --write to apply.")
        return 0

    bak = PUB.with_suffix(f".jsonl.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    bak.write_text(PUB.read_text(encoding="utf-8"), encoding="utf-8")
    with PUB.open("w", encoding="utf-8") as fh:
        if head:
            fh.write(head + "\n")
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"backup  -> {bak.name}\nwritten -> {PUB.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
