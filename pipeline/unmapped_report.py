#!/usr/bin/env python3
"""
unmapped_report.py — READ ONLY. What would each unmapped descriptor buy, if mapped?

    python3 pipeline/unmapped_report.py
    python3 pipeline/unmapped_report.py amber sandalwood      # detail for named tags

status.py reports "N distinct, M uses" and stops. This asks the next question: which
MOLECULES does each unmapped surface form carry, how many are new to the tag it would
map onto, and — the column that matters most — HOW MANY DOCUMENTS they come from.

ALWAYS READ THE DOCS COLUMN BEFORE THE MOLS COLUMN
--------------------------------------------------
Written 2026-09-05 after this script's first output was used to claim two tags could
cross the bar for free:

    ambergris   3 molecules -> amber 28 -> 31        all three from US6573391B1
    camphery    3 molecules -> camphoraceous -> 31   all three from US4173584A

Both crossings are arithmetically real. The bar is stated as >=30 MOLECULES with no
document-spread requirement, so nothing forbids them. But a tag crossing on one patent's
single structural series is not the same fact as a tag crossing on nine patents, and the
project already distrusts exactly this shape everywhere else: docs>=20 for vocabulary
admission, boilerplate.py for copied context windows, dedupe_families.py because "eight
continuations of one filing are one party saying one thing eight times".

The molecule count alone cannot see that. So it is not printed alone.

WHAT IT DOES NOT DO
-------------------
Writes nothing, proposes nothing, decides nothing. odor_terms.tsv is human-written and
is the only place span text becomes a tag; this script exists so that the human writing
it can see what a line would do before adding it.

Imports status.py's loaders rather than reimplementing them — reimplementing the tag
load is exactly how the 20/11/15 disagreement of 2026-09-05 happened.
"""
from __future__ import annotations
import collections, importlib.util, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

spec = importlib.util.spec_from_file_location("status", HERE / "status.py")
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)        # __name__ == "status", so its main() does not run

surf = status.load_tags()
norm = status.norm
BAR = status.BAR


def collect():
    """tag -> molecules (as status.py counts them), and the unmapped side beside it."""
    tag_mols: dict[str, set[str]] = collections.defaultdict(set)
    un_mols: dict[str, set[str]] = collections.defaultdict(set)
    un_docs: dict[str, set[str]] = collections.defaultdict(set)
    un_uses: collections.Counter = collections.Counter()
    un_sent: dict[str, list[str]] = collections.defaultdict(list)

    for r in status.jsonl(status.REVIEW):
        if r.get("decision") != "approve":
            continue
        mols = [norm(m) for m in (r.get("molecules") or []) if m.strip()]
        for d in (r.get("tags") or r.get("descriptors") or []):
            d = d.strip().lower()
            if not d:
                continue
            tag = surf.get(d)
            if tag is None:
                un_uses[d] += 1
                un_mols[d].update(mols)
                un_docs[d].add(r.get("source_id") or "?")
                if len(un_sent[d]) < 2:
                    un_sent[d].append((r.get("sentence") or "")[:200])
            else:
                tag_mols[tag].update(mols)

    # PubChem has no review gate and no source_id of the same kind; it contributes to the
    # tag side only, exactly as status.py does.
    for r in status.jsonl(status.PUBCHEM):
        if r.get("excluded"):
            continue
        t = (r.get("tag") or "").strip()
        m = norm(r.get("molecule_name") or "")
        if t and m:
            tag_mols[t].add(m)

    return tag_mols, un_mols, un_docs, un_uses, un_sent


def main() -> int:
    tag_mols, un_mols, un_docs, un_uses, un_sent = collect()
    wanted = [a.lower() for a in sys.argv[1:] if not a.startswith("-")]

    print(f"unmapped descriptors: {len(un_uses)} distinct, {sum(un_uses.values())} uses")
    print("(approved text with no odor_terms.tsv entry — candidates, not errors)\n")
    print(f"{'surface form':<24}{'uses':>5}{'mols':>6}{'docs':>6}   would map onto")
    print("-" * 88)
    for d, mols in sorted(un_mols.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(mols) < 2:
            continue
        stem = d.split()[0][:5]
        near = [t for t in sorted(tag_mols) if stem and (stem in t or t[:5] in d)]
        bits = []
        for t in near[:2]:
            have, new = len(tag_mols[t]), len(mols - tag_mols[t])
            after = have + new
            mark = "  CROSSES" if have < BAR <= after else ""
            bits.append(f"{t} {have}->{after}{mark}")
        flag = " <- ONE DOCUMENT" if len(un_docs[d]) == 1 and bits else ""
        print(f"{d:<24}{un_uses[d]:>5}{len(mols):>6}{len(un_docs[d]):>6}   "
              f"{'  ·  '.join(bits)}{flag}")

    if not wanted:
        wanted = [t for t, s in sorted(tag_mols.items(), key=lambda kv: -len(kv[1]))
                  if len(s) < BAR][:4]
        print(f"\n\nDETAIL — the {len(wanted)} tags nearest the bar "
              f"(name tags on the command line to choose others)")

    for t in wanted:
        have = tag_mols.get(t, set())
        print(f"\n=== {t}  ({len(have)} molecules, needs {max(0, BAR - len(have))}) ===")
        hits = [(d, m) for d, m in un_mols.items()
                if t[:5] in d or d[:5] in t or d in t or t in d]
        if not hits:
            print("  (nothing unmapped matches by name — try the table above)")
        for d, mols in sorted(hits, key=lambda kv: -len(kv[1])):
            print(f"  {d:<24}{un_uses[d]:>3} uses {len(mols):>3} mols "
                  f"{len(mols - have):>3} NEW  {len(un_docs[d])} doc(s): "
                  f"{sorted(un_docs[d])[:3]}")
            for s in un_sent[d][:1]:
                print(f"      {s!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
