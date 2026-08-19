#!/usr/bin/env python3
"""
ops_smoke.py — second contact. Round 1 settled some questions and botched one.

    python3 ops_smoke.py

SETTLED 2026-08-19
------------------
  * Content-Type MUST be text/plain on search, despite a form-encoded body (415 otherwise)
  * cpc="A23L27/00"  works — 7,131 results.  cpc="A23L 27/00" returns 500. No space.
  * pn=US* is ILLEGAL: truncation needs >=3 leading characters and "US" is 2
  * results are sorted newest-first across ALL countries — the first page was pure WO

STILL OPEN, and why round 1 failed to answer it
-----------------------------------------------
The cap test asked for range 1900-2000. That is 101 items, and OPS caps a single request
at 100, so the 400 was about the SPAN, not the OFFSET. Two different limits, one test —
it could not have distinguished them. Redone here as three requests that vary one thing
at a time:

    1-100        span 100, low offset    -> is a full page allowed at all?
    1901-2000    span 100, high offset   -> is there a ~2000 ceiling?
    2001-2100    span 100, past it       -> confirms the ceiling is real, not a fluke

A test that changes two variables at once cannot attribute its own failure. Worth the
extra requests to avoid designing the walker around a guess.

Also checks whether `pd within` works, since country filtering has to be solved some
other way now and date-windowing is the fallback.
"""
from __future__ import annotations
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ops  # noqa: E402

CPC = 'cpc="A23L27/00"'


def show(label, cql, begin=1, end=25, dump_headers=False):
    print(f"\n--- {label}")
    print(f"    q = {cql}    range {begin}-{end}")
    try:
        total, ids, headers = ops.search(cql, begin, end)
    except ops.QuotaExceeded as e:
        print(f"    QUOTA: {e}"); return None
    except ops.OPSError as e:
        first = str(e).split("\n")
        print("    ERROR: " + " | ".join(x.strip() for x in first if "code>" in x or "message>" in x
                                         or x.startswith("HTTP")))
        return None
    us = [i for i in ids if i.startswith("US")]
    print(f"    total={total}  returned={len(ids)}  of which US={len(us)}")
    print(f"    first: {', '.join(ids[:3])}")
    if dump_headers:
        print("    headers:")
        for k, v in headers.items():
            print(f"      {k}: {v}")
    return total


def main() -> int:
    try:
        ops.load_env(); ops.token()
    except ops.OPSError as e:
        print(e); return 1
    print("auth ok")

    print("\n" + "=" * 68)
    print("Q1: is a full 100-item page allowed?  (isolates SPAN)")
    show("low offset, span 100", CPC, 1, 100, dump_headers=True)

    print("\n" + "=" * 68)
    print("Q2: where is the offset ceiling?  (isolates OFFSET, span held at 100)")
    show("offset 1901", CPC, 1901, 2000)
    show("offset 2001", CPC, 2001, 2100)
    print("\n-> if 1901 works and 2001 fails, the ceiling is 2000 and every window")
    print("   must be split until total-result-count <= 2000.")

    print("\n" + "=" * 68)
    print("Q3: does date windowing work? it is how we stay under the ceiling")
    show("pd within 2013-2015", f'{CPC} and pd within "2013 2015"', 1, 100)

    print("\n" + "=" * 68)
    print("Q4: can we filter US at query time? 'US2' has the 3 chars truncation needs")
    show("pn=US2*", f'{CPC} and pn=US2*', 1, 100)
    print("\n-> if this works it saves paging foreign results, but it is NOT required:")
    print("   country codes come back in every record, so US can be filtered locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
