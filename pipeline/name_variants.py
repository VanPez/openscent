#!/usr/bin/env python3
"""
name_variants.py — the same molecule, counted twice, because the join is on name TEXT.

every tag with >=10 molecules:
    python3 pipeline/name_variants.py
just these tags:
    python3 pipeline/name_variants.py sandalwood amber
show the colliding names:
    python3 pipeline/name_variants.py --groups

(the descriptions are deliberately NOT trailing `#` comments — interactive zsh does not
strip those, and pasting one passes it as arguments. See the guard in main().)

WHY THIS FILE EXISTS
--------------------
status.py joins the two row sources on casefolded name text and its docstring is honest
about the consequence:

    treat the combined figure as an upper bound on distinct molecules

That warning was written about stereochemistry — `linalool` vs `(+)-linalool`. The bigger
source turns out to be SCANNING. A 1970s patent gives one molecule three spellings across
three documents:

    14-oxobicyclo [10.4.0]hexadecane
    14-oxobicyclo[10.4.0]hexadecane
    14 oxobicyc1o[10.4.0]hexadecane      <- note the digit 1 standing in for the letter l

All three are approved rows. All three are the same compound. `musk` counts them as three.

Measured 2026-09-10: 25 duplicate spellings across tags with >=10 molecules, 22 of them
in tags with >=20. **No tag at the bar falls below 30**, so the headline of 20 is
unaffected — this does NOT restate the 2026-09-05 lesson, status.py is still right about
the number it owns. What it changes is the two tags that were nearly there:

    sandalwood   29 printed  ->  28 real   needs 2, not 1
    amber        28 printed  ->  26 real   needs 4, not 2

which is the difference between "one approval closes it" and "one approval does not".

THIS SCRIPT DOES NOT DECIDE ANYTHING AND DOES NOT TOUCH status.py
-----------------------------------------------------------------
status.py owns the headline. Folding this squash into it would change the definition of
the number the whole project quotes, and that is Ivan's call, made deliberately, not a
patch applied mid-sitting. So this prints BOTH counts side by side and stops there.

WHY THE SQUASH IS DELIBERATELY TOO AGGRESSIVE
---------------------------------------------
It strips whitespace, hyphens, brackets, commas and quotes, then folds l->1, o->0, i->1.
That last group is the OCR confusion set, and folding it WILL merge names that are
genuinely different if a real molecule differs from another only by an i/l/o in a
position where the rest of the string matches. No such pair has been seen, but the risk
is real and one-directional: this OVER-merges, so its count is a LOWER bound exactly as
status.py's is an UPPER bound. The truth is between them, and printing both is the point.

Run with --groups and read the collisions before believing any single number.

THE FOURTH DUPLICATE SCOPE
--------------------------
2026-09-07 catalogued three: family duplicates across documents (19.4%), the same
sentence twice within one document (56), entity-split fragments within a sentence. This
is the fourth, and it is the first one that lands on the molecule counts rather than
being absorbed by counting in sets.
"""
from __future__ import annotations
import collections, importlib.util, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BAR = 30


def _status():
    spec = importlib.util.spec_from_file_location("status", ROOT / "pipeline" / "status.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def squash(name: str) -> str:
    """Collapse everything a scanner or a typesetter can move. Over-merges by design."""
    x = re.sub(r"[\s\-\(\)\[\],'’]", "", name.lower())
    return x.replace("l", "1").replace("o", "0").replace("i", "1")


def main(argv: list[str]) -> int:
    show_groups = "--groups" in argv
    wanted = {a for a in argv if not a.startswith("--")}

    st = _status()
    surf = st.load_tags()
    rows = list(st.jsonl(st.REVIEW))

    # AN UNKNOWN TAG NAME MUST NOT PRINT AN EMPTY TABLE.
    # It did, once, and the empty table looked exactly like "no duplicates found" —
    # `python3 name_variants.py  # every tag` in an interactive zsh, where
    # `interactive_comments` is OFF by default, so `#`, `every` and `tag` arrived as
    # three tag names and filtered the corpus down to nothing. A wrong answer that
    # renders as a clean report is this project's recurring failure; refuse instead.
    known = set(surf.values())
    unknown = sorted(wanted - known)
    if unknown:
        print(f"!! not tag names: {', '.join(repr(u) for u in unknown)}", file=sys.stderr)
        near = [t for t in sorted(known) if any(u and (u in t or t in u) for u in unknown)]
        if near:
            print(f"   did you mean: {', '.join(near[:6])}", file=sys.stderr)
        print("   (a '#' comment on the command line is NOT stripped by interactive zsh)",
              file=sys.stderr)
        print(f"   valid tags come from ontology/odor_terms.tsv — {len(known)} of them.",
              file=sys.stderr)
        return 2

    per_tag: dict[str, set[str]] = collections.defaultdict(set)
    for r in rows:
        if r.get("decision") != "approve":
            continue
        mols = [st.norm(m) for m in (r.get("molecules") or []) if m.strip()]
        for d in (r.get("descriptors") or r.get("tags") or []):
            t = surf.get(d.strip().lower())
            if t:
                per_tag[t].update(mols)
    for r in st.jsonl(st.PUBCHEM):
        if r.get("excluded"):
            continue
        t = (r.get("tag") or "").strip()
        m = st.norm(r.get("molecule_name") or "")
        if t and m:
            per_tag[t].add(m)
    for s in per_tag.values():
        s.discard("")

    rowsout, total = [], 0
    for tag, mols in per_tag.items():
        if wanted and tag not in wanted:
            continue
        if not wanted and len(mols) < 10:
            continue
        g: dict[str, list[str]] = collections.defaultdict(list)
        for m in mols:
            g[squash(m)].append(m)
        dups = {k: v for k, v in g.items() if len(v) > 1}
        n_dup = sum(len(v) - 1 for v in dups.values())
        total += n_dup
        rowsout.append((tag, len(mols), len(mols) - n_dup, n_dup, dups))

    rowsout.sort(key=lambda x: (-x[3], x[0]))

    print(f"{'tag':<16}{'printed':>8}{'real':>7}{'dupes':>7}   {'needs (printed -> real)':<26}")
    print("-" * 78)
    for tag, printed, real, n_dup, dups in rowsout:
        need_p = max(0, BAR - printed)
        need_r = max(0, BAR - real)
        note = ""
        if printed >= BAR > real:
            note = "  *** FALLS BELOW THE BAR ***"
        elif need_p != need_r:
            note = "  <-- moved"
        needs = f"{need_p} -> {need_r}" if need_p != need_r else str(need_p)
        print(f"{tag:<16}{printed:>8}{real:>7}{n_dup:>7}   {needs:<26}{note}")
        if show_groups and dups:
            for v in dups.values():
                for m in v:
                    print(f"      {m[:92]}")
                print()

    print("-" * 78)
    print(f"{total} duplicate spellings across the tags listed")
    print()
    print("printed = status.py's number, an UPPER bound (name-text join).")
    print("real    = this squash, a LOWER bound (it over-merges on purpose).")
    print("The truth is between them. Run --groups and read the collisions.")
    print("status.py is unchanged and still owns the headline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
