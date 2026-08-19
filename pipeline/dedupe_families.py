#!/usr/bin/env python3
"""
dedupe_families.py — one publication per patent family. Run before merging a walk.

    python3 dedupe_families.py patent-ids-A23L27_00-ops.json
    python3 dedupe_families.py patent-ids-A23L27_00-ops.json --write

WHAT IS BEING REMOVED, AND WHY IT IS NOT DATA LOSS
--------------------------------------------------
The A23L27/00 walk returned 10,762 US publications belonging to 9,346 families. The 1,416
extras are not additional patents. They are the same invention published again — an
application and the patent granted from it, or a continuation filed years later with a
near-identical description.

They arrive because the US filter runs per series digit: pn=US1* returns a family's grant,
pn=US2* returns that family's application publication. Two queries, two representatives,
one disclosure.

Keeping them would corrupt the two counters the vocabulary rests on:

  documents      docs>=20 treats each document as an INDEPENDENT attestation. Eight
                 continuations of one filing are one party saying one thing eight times.
                 A term appearing in all eight would look twenty-times attested when it
                 has been said once.
  boilerplate    boilerplate.py measures the share of a term's DOCUMENTS carrying one
                 identical context window. Duplicate disclosures share their text wholesale,
                 so they inflate exactly the signal that detection depends on — and would
                 make genuine boilerplate look like independent corroboration.

This is the same error the corpus already guards against between documents (passages.py
found four boilerplate paragraphs copied across patents). Family duplicates are that
problem in a harder-to-see form, because the documents really are different documents.

WHICH PUBLICATION IS KEPT
-------------------------
Grants first (kind code B), then the lowest publication number. A granted patent carries
the examined, final text; where there is no grant the earliest application is the original
disclosure rather than a continuation of it. The choice matters little for extraction —
the descriptions are near-identical, which is the whole point — but it must be STATED and
DETERMINISTIC so that a re-run produces the same corpus.
"""
from __future__ import annotations
import collections, json, pathlib, re, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"


def rank(pub: str):
    """Sort key: grants before applications, then genuinely earliest.

    The number must be compared NUMERICALLY. Sorted as text, "US10517323" precedes
    "US7501144" because '1' < '7', so the first version of this kept a 2019 grant over
    the 2009 original of the same family — the opposite of the stated rule, silently.
    """
    m = re.match(r"^US(\d+)([A-Z])(\d?)$", pub)
    if not m:
        return (2, 10 ** 12, pub)
    num, kind = int(m.group(1)), m.group(2)
    return (0 if kind == "B" else 1, num, pub)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = "--write" in sys.argv
    if not args:
        sys.exit("usage: dedupe_families.py <walk-file.json> [--write]")

    src = CORPUS / args[0]
    d = json.loads(src.read_text())
    ids, fams = d["ids"], (d.get("families") or {})
    if not fams:
        sys.exit("no family ids in this file — it predates family capture. Re-walk.")

    missing = [i for i in ids if not fams.get(i)]
    if missing:
        print(f"! {len(missing)} ids have no family id, e.g. {missing[:5]}")
        print("  Keeping them all: an unknown family cannot be shown to duplicate another.")

    by = collections.defaultdict(list)
    for i in ids:
        f = fams.get(i)
        by[f or f"__nofamily__{i}"].append(i)

    keep, dropped = [], []
    for f, members in by.items():
        members = sorted(members, key=rank)
        keep.append(members[0])
        dropped += members[1:]

    print(f"{len(ids)} publications -> {len(keep)} families")
    print(f"dropping {len(dropped)} duplicate disclosures ({len(dropped)/len(ids)*100:.1f}%)\n")
    print("examples of what is being dropped (kept -> dropped):")
    shown = 0
    for f, members in by.items():
        if len(members) < 2 or shown >= 6:
            continue
        members = sorted(members, key=rank)
        print(f"  {members[0]:<20} <- {', '.join(members[1:])}")
        shown += 1

    if not write:
        print("\nDry run. Add --write to produce the deduped file.")
        return 0

    out = dict(d)
    out["ids"] = sorted(keep)
    out["families"] = {i: fams.get(i, "") for i in keep}
    out["deduped_from"] = len(ids)
    out["deduped_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    dest = src.with_name(src.stem + "-dedup.json")
    dest.write_text(json.dumps(out))
    print(f"\n-> {dest.name}")
    print(f"   merge THIS file, not the original:\n   python3 merge_ids.py {dest.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
