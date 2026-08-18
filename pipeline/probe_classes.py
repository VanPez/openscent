#!/usr/bin/env python3
"""
probe_classes.py — measure what a CPC class would ADD, before paying to fetch it.

    python3 probe_classes.py                    # the three candidate classes
    python3 probe_classes.py A23L27/00 C11D3/50 # specific ones

RUN THIS FROM THE MAC. Google Patents refuses /xhr/query from Hetzner — that is what
caused the 503 storm on 2026-08-01. Search from the Mac, bulk-fetch from Hetzner.

WHY PROBE INSTEAD OF JUST WIDENING
----------------------------------
2,588 patents produced ~400 usable rows, and 400 molecules over 67 tags is 6 each. Only
14 tags reach Mike's 30-molecule bar, so the corpus has to grow — but "more patents" is
not automatically "more molecules". A class can be large and still add nothing, either
because its patents are already in the set under a second CPC code, or because they are
formulation documents that never name a compound.

Discovery is cheap. Fetching 20,000 pages is not, and it is a day of somebody's
bandwidth. So measure first:

  total     ids the class returns in the sampled windows
  new       ids NOT already in corpus/patent-ids.json      <- the only number that matters
  overlap   share already held

A class with 90% overlap is free to add and gains nothing. A class with 90% new ids is
where the molecules are.

WHAT IT DOES NOT DO
-------------------
It does not tell you whether the new patents CONTAIN odour descriptions — only that they
are different documents. Two sampled windows are also not the whole class; the extrapolation
assumes the class is spread evenly over time, which it is not (patenting accelerates). Treat
the estimate as an order of magnitude, not a count.

Nothing here writes to corpus/patent-ids.json. Results go to corpus/class-probe.json.
"""
from __future__ import annotations
import json, os, pathlib, sys, time

_here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_here))
from harvest import search_window, ROOT   # noqa: E402 — same delays, same backoff

CANDIDATES = ["A23L27/00", "C11D3/50", "A61K8/00"]

# Two windows far apart, so a class that only became active recently is not judged on a
# decade when it did not exist. 3-year windows, matching search_all's step.
WINDOWS = [(2013, 2016), (2022, 2025)]
SPAN_YEARS = 2027 - 2001          # what search_all would actually walk


def main() -> int:
    classes = [a for a in sys.argv[1:] if not a.startswith("-")] or CANDIDATES
    idfile = ROOT / "corpus" / "patent-ids.json"
    have = set(json.loads(idfile.read_text())) if idfile.exists() else set()
    print(f"already held: {len(have)} ids\n")
    if not have:
        print("! corpus/patent-ids.json not found — 'new' will equal 'total'.\n")

    cooldown = float(os.environ.get("PROBE_COOLDOWN", 60))
    out = {}
    for n, cpc in enumerate(classes):
        if n:
            print(f"(cooling down {cooldown:.0f}s between classes)\n")
            time.sleep(cooldown)
        print(f"=== {cpc} ===")
        got, failed = [], False
        for lo, hi in WINDOWS:
            ids = search_window(cpc, lo, hi)
            # A window that returns nothing is ambiguous: either the class is genuinely
            # empty for those years, or we were rate limited. On 2026-08-18 two classes
            # reported "0 ids, 0 new" purely from 503s, which reads like a verdict and is
            # not one. Treat an empty window as a FAILURE to measure, not a measurement.
            if not ids:
                failed = True
                print(f"  {lo}-{hi}:  NO DATA — empty or rate limited, not a result")
                continue
            n_new = len([i for i in ids if i not in have])
            flag = "  <-- HIT THE CAP, real count is higher" if len(ids) >= 1000 else ""
            print(f"  {lo}-{hi}: {len(ids):4d} ids, {n_new:4d} new{flag}")
            got += ids
        uniq = sorted(set(got))
        new = [i for i in uniq if i not in have]
        if failed:
            print("  ! at least one window returned nothing — this class is UNMEASURED.")
            print("    Re-run it alone after a cooldown:")
            print(f"    OPENSCENT_DELAY_MIN=6 OPENSCENT_DELAY_MAX=12 "
                  f"python3 probe_classes.py {cpc}")
        if not uniq:
            out[cpc] = {"status": "unmeasured"}
            print()
            continue
        sampled_years = sum(hi - lo for lo, hi in WINDOWS)
        est_new = int(len(new) * SPAN_YEARS / sampled_years) if sampled_years else 0
        overlap = (1 - len(new) / len(uniq)) * 100 if uniq else 0
        print(f"  sampled {len(uniq)} unique · {len(new)} new · {overlap:.0f}% already held")
        print(f"  rough full-class estimate: ~{est_new:,} new patents\n")
        out[cpc] = {"sampled_unique": len(uniq), "sampled_new": len(new),
                    "overlap_pct": round(overlap, 1), "est_new_full_class": est_new,
                    "windows": WINDOWS,
                    "status": "partial" if failed else "ok"}

    dest = ROOT / "corpus" / "class-probe.json"
    dest.write_text(json.dumps(out, indent=1))
    ok = {k: v for k, v in out.items() if v.get("status") == "ok"}
    bad = [k for k, v in out.items() if v.get("status") != "ok"]
    tot = sum(v["est_new_full_class"] for v in ok.values())
    print("=" * 60)
    print(f"combined estimate from FULLY MEASURED classes: ~{tot:,} new "
          f"patents on top of {len(have)}")
    if bad:
        print(f"UNMEASURED or partial, do not read as zero: {', '.join(bad)}")
    print("Extrapolated from two windows — an order of magnitude, not a count.")
    print(f"-> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
