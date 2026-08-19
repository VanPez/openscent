#!/usr/bin/env python3
"""
ops_dump.py — print the raw XML for one query. A diagnostic, nothing more.

    python3 ops_dump.py                    # default: pn=US10000723
    python3 ops_dump.py 'cpc="A23L27/00"'

ops_idcheck.py showed that asking for the GRANT US10000723 returns US2015209688A1, its
pre-grant application publication. Before designing around that, we need to know whether
the record contains BOTH numbers and parse() simply picks the wrong one, or whether OPS
returns one representative publication per family and the grant is genuinely absent.

The first is a five-line fix. The second changes what discovery even means: the ids would
name different documents than the corpus holds, the overlap check would be meaningless,
and fetching both an application and its grant would double-count one disclosure in the
`documents` counter that the admission rule rests on.

Guessing between those two would be the expensive mistake. One request settles it.
"""
from __future__ import annotations
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ops  # noqa: E402

q = sys.argv[1] if len(sys.argv) > 1 else "pn=US10000723"


def main() -> int:
    try:
        ops.load_env(); ops.token()
    except ops.OPSError as e:
        print(e); return 1
    print(f"q = {q}\n" + "=" * 70)
    try:
        xml_text, _ = ops.raw_search(q, 1, 3)
    except ops.OPSError as e:
        print(e); return 1
    if xml_text is None:
        print("no results"); return 0
    print(xml_text[:4000])
    print("=" * 70)
    total, recs = ops.parse(xml_text)
    print(f"parse() sees total={total}, recs={recs}")
    print("\nLook for: does ONE search-result record carry more than one document-id?")
    print("If yes -> parse() bug. If each record has exactly one -> family behaviour.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
