#!/usr/bin/env python3
"""
cpc_scope.py — does cpc="A23L27/00" include the subgroups under it, or only that symbol?

    python3 cpc_scope.py

WHY THIS STOPS THE MERGE
------------------------
The OPS walk of A23L27/00 finished in one minute with 589 US ids. The Google probe
estimated ~4,400. A 7.5x gap that the walk reports as a clean, complete result.

CPC is a tree. A23L27/00 is a main group; the actual documents mostly sit in subgroups
(A23L27/10 spices, /20 synthetic flavours, /30 sweeteners, and so on). If OPS matches the
symbol literally while Google expanded the hierarchy, then this walk collected the thin
population classified at the bare main group and missed the rest of the class.

That is not visible anywhere downstream. The ids that were never returned leave no trace:
no error, no gap marker, nothing to distinguish "this class is small" from "we asked the
wrong question". Which is exactly the failure this project keeps running into — the 998
Google cap, the 503-as-empty-class, the client-side US filter that lost half the US
patents. Same shape every time: a query that silently answers something narrower than
what was asked.

WHAT IT TESTS
-------------
Counts (all countries, no paging — only total-result-count is needed, so this is cheap)
for the main group, two subgroups, and three candidate syntaxes for hierarchical search.
If a subgroup returns documents that the main group's count cannot contain, the main group
is literal and the walk must enumerate subgroups or use whichever syntax expands.
"""
from __future__ import annotations
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ops  # noqa: E402

CASES = [
    ('cpc="A23L27/00"',      "main group, as walked"),
    ('cpc="A23L27/10"',      "a subgroup — spices/herbs"),
    ('cpc="A23L27/20"',      "a subgroup — synthetic flavours"),
    ('cpc=A23L27*',          "truncation: does * expand the tree?"),
    ('cpc="A23L27/00/low"',  "Espacenet 'low' notation, if OPS honours it"),
    ('cpc="A23L 27/00/low"', "same with the space form"),
]


def main() -> int:
    try:
        ops.load_env(); ops.token()
    except ops.OPSError as e:
        print(e); return 1

    print(f"{'query':<26} {'total':>8}   note")
    print("-" * 78)
    totals = {}
    for cql, note in CASES:
        try:
            total, _, _ = ops.search(cql, 1, 1)
            totals[cql] = total
            print(f"{cql:<26} {total:>8}   {note}")
        except ops.OPSError as e:
            msg = [l.strip() for l in str(e).splitlines() if "message>" in l]
            print(f"{cql:<26} {'ERR':>8}   {note} — {msg[0] if msg else 'failed'}")

    print("-" * 78)
    main_g = totals.get('cpc="A23L27/00"', 0)
    subs = [totals.get('cpc="A23L27/10"', 0), totals.get('cpc="A23L27/20"', 0)]
    print(f"main group      : {main_g}")
    print(f"two subgroups   : {subs[0]} + {subs[1]} = {sum(subs)}")
    if sum(subs) > main_g:
        print("\n-> Two subgroups alone exceed the main group's total. The main group is")
        print("   matched LITERALLY, and the 589-id walk covers a fraction of the class.")
        print("   Do NOT merge it. Either use a syntax above that expands the tree, or")
        print("   enumerate the subgroups explicitly.")
    elif sum(subs) == 0:
        print("\n-> Subgroups return nothing, which would mean the main group already")
        print("   contains them. Surprising given the Google estimate — check a third")
        print("   subgroup before believing it.")
    else:
        print("\n-> Subgroups are smaller than the main group, consistent with the main")
        print("   group including them. The 589 then needs a different explanation:")
        print("   most likely Google counted A- and B-publications separately where OPS")
        print("   returns one per family, plus Google's own estimate was extrapolated")
        print("   from two windows and could simply have been too high.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
