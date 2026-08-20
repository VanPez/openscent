#!/usr/bin/env python3
"""
class_size.py — how big is a CPC class, bare vs subtree? Counts only, cheap.

    python3 class_size.py                        # the four classes that matter
    python3 class_size.py C11B9/00 A61Q13/00

RUN FROM THE MAC (needs .env).

WHY THIS QUESTION, NOW
----------------------
The A23L27/00 subtree measured 0.17 candidates per patent against the existing corpus's
0.85 — one fifth the yield, because food patents describe TASTE and this extractor looks
for ODOUR. Not worth 7 hours of fetching and weeks of review for ~289 thinly spread rows.

But the corpus itself came from C11B9/00 and A61Q13/00, walked with GOOGLE, and we now
know OPS matches a CPC symbol literally: A23L27/00 went from 7,131 to 44,809 with /low.
If Google was also searching the bare symbol, then the classes we KNOW yield 0.85 have a
subtree that was never harvested.

That is the difference between adding patents at 0.17 and adding them at 0.85 — the same
fetch effort for five times the rows.

WHAT THE NUMBERS MEAN
---------------------
Totals are ALL COUNTRIES. The US share ran ~24% for A23L27/00 (10,762 of 44,809), and
family dedupe removed a further 13%, so a rough usable-US estimate is total x 0.21.
That is an extrapolation from one class; treat it as a planning figure, not a count.

Two requests per class, no paging.
"""
from __future__ import annotations
import json, pathlib, sys

_here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_here))
import ops  # noqa: E402

# The two the corpus was built from, plus the two never measured.
DEFAULT = ["C11B9/00", "A61Q13/00", "C11D3/50", "A61K8/00"]
US_SHARE = 0.24          # measured on A23L27/00
AFTER_DEDUPE = 0.87      # measured on A23L27/00


def one(cql):
    try:
        total, _, _ = ops.search(cql, 1, 1)
        return total
    except ops.OPSError as e:
        msg = [l.strip() for l in str(e).splitlines() if "message>" in l]
        return f"ERR {msg[0][:40] if msg else ''}"


def main() -> int:
    classes = [a for a in sys.argv[1:] if not a.startswith("-")] or DEFAULT
    try:
        ops.load_env(); ops.token()
    except ops.OPSError as e:
        print(e); return 1

    have = 0
    idf = _here.parent / "corpus" / "patent-ids.json"
    if idf.exists():
        have = len(json.loads(idf.read_text()))
    print(f"corpus today: {have} patents (from C11B9/00 + A61Q13/00 via Google)\n")

    print(f"{'class':<12} {'bare':>9} {'/low':>9} {'x':>6}   {'est. US, deduped':>18}")
    print("-" * 62)
    rows = []
    for c in classes:
        bare = one(f'cpc="{c}"')
        low = one(f'cpc="{c}/low"')
        if isinstance(bare, int) and isinstance(low, int) and bare:
            mult = f"{low / bare:.1f}x"
            est = int(low * US_SHARE * AFTER_DEDUPE)
            print(f"{c:<12} {bare:>9,} {low:>9,} {mult:>6}   {est:>18,}")
            rows.append((c, bare, low, est))
        else:
            print(f"{c:<12} {str(bare):>9} {str(low):>9}")
    print("-" * 62)

    if rows:
        tot = sum(r[3] for r in rows)
        print(f"\nestimated US patents across these classes, after family dedupe: ~{tot:,}")
        print(f"at the corpus's own 0.85 candidates/patent that is ~{int(tot*0.85):,} candidates,")
        print(f"~{int(tot*0.85*0.2):,} usable rows at 0.2 precision,")
        print(f"and ~{tot*3/3600:.0f} h of fetching at 3s.\n")
        print("REVIEW TIME IS THE REAL BUDGET, not fetch time. Every candidate needs a")
        print("human decision. 1,000 candidates is roughly ten sittings at the observed")
        print("rate. Judge these numbers against that, not against the hours of fetching.")
        print("\nAnd yield is UNMEASURED for any class not already in the corpus —")
        print("C11D3/50 and A61K8/00 could be 0.85 like perfume, or 0.17 like food.")
        print("Sample before fetching, exactly as A23L27/00 was sampled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
