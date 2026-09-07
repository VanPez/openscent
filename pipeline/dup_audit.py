#!/usr/bin/env python3
"""
dup_audit.py — READ ONLY. Which documents in corpus/raw are the same disclosure twice?

    python3 dup_audit.py                    # report
    python3 dup_audit.py --json groups.json # also write the groups for offline analysis

RUN ON HETZNER. Needs corpus/raw/ and harvest.py beside it. Writes nothing but the
optional --json report. Deletes nothing, and deliberately CANNOT: which copy to keep is
a decision with provenance consequences, and it belongs to a human.

THE QUESTION, DEFERRED SINCE 2026-08-20
---------------------------------------
discover_ops.py's docstring: "Google Patents had no family concept, so the existing
2,588-patent corpus may already contain that duplication; audit it before trusting any
count derived from it."

On 2026-09-07 that stopped being a hypothesis. descr_probe.py's output put 36 of its 88
hits in US10045551B2 and 36 in US20140023770A1 — identical counts, and the two carry the
sentence "Particular cyclohexenones are described as flavor modifiers..." verbatim
between them. One disclosure, published twice, both in the corpus.

WHY TEXT AND NOT OPS FAMILY IDS
-------------------------------
Asking OPS for a family id per publication is 5,346 requests at a 4.5s floor — about
seven hours — and it answers only for publications OPS returns under the number we hold,
which is exactly the assumption the pre-OPS corpus breaks. Text is free, offline, and is
the thing itself: dedupe_families.py already argues that duplicate disclosures "share
their text wholesale".

THE METHOD, AND THE TRAP IT AVOIDS
----------------------------------
Naive pairwise comparison is 14M pairs. Instead: index every sentence to the documents
containing it, then only compare documents that share a sentence.

But sentences shared by MANY documents are boilerplate, not evidence — passages.py found
paragraphs copied across unrelated patents, and counting those would make every perfume
patent look like a duplicate of every other. So a sentence occurring in more than
BOILERPLATE_MAX documents is discarded before pairing. What remains is rare text, which
is what actually identifies a disclosure.

CONTAINMENT, NOT JACCARD
------------------------
An application publication and the grant issued from it are not the same length — the
grant is the examined text and is usually shorter. Jaccard punishes that asymmetry and
would score a genuine pair at 0.6 while a threshold tuned for it lets unrelated pairs in.
Containment — shared / min(|A|,|B|) — asks "is the smaller document essentially inside
the larger", which is the actual relationship between a family's publications.

WHAT THE OUTPUT IS FOR
----------------------
Groups, not deletions. The next question after this one is which member of each group to
keep, and dedupe_families.py has already settled that rule for walk files (grants first,
then lowest publication number) — but applying it here removes DOCUMENTS from a corpus
that rows already point at, so it must be done deliberately and with merge_review.py in
the loop, not by this script.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, os, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
os.environ.setdefault("OPENSCENT_ROOT", str(HERE.parent))
sys.path.insert(0, str(HERE))
import harvest  # noqa: E402

MIN_SENT_CHARS = 40        # shorter lines are headings, numbers, fragments
BOILERPLATE_MAX = 5        # a sentence in more docs than this identifies nothing
MIN_SHARED = 3             # below this, a "match" is coincidence or a shared citation


def h(s: str) -> str:
    return hashlib.blake2b(s.encode("utf-8"), digest_size=12).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the groups here")
    ap.add_argument("--threshold", type=float, default=0.60,
                    help="containment above which two documents are one disclosure")
    a = ap.parse_args()

    print(f"corpus {harvest.RAW}")
    doc_sents: dict[str, set[str]] = {}
    index: dict[str, list[str]] = collections.defaultdict(list)

    for f in sorted(harvest.RAW.glob("*.txt")):
        text = harvest.norm(f.read_text(encoding="utf-8"))
        hs = {h(s) for s in harvest.SENT.split(text) if len(s) >= MIN_SENT_CHARS}
        doc_sents[f.stem] = hs
        for x in hs:
            index[x].append(f.stem)

    print(f"documents {len(doc_sents)} · distinct sentences {len(index)}")

    boiler = {x for x, ds in index.items() if len(ds) > BOILERPLATE_MAX}
    print(f"boilerplate sentences ignored: {len(boiler)} "
          f"(in more than {BOILERPLATE_MAX} documents)")

    pairs: collections.Counter = collections.Counter()
    for x, ds in index.items():
        if x in boiler or len(ds) < 2:
            continue
        for i in range(len(ds)):
            for j in range(i + 1, len(ds)):
                pairs[(ds[i], ds[j])] += 1

    print(f"document pairs sharing >=1 rare sentence: {len(pairs)}")

    edges = []
    for (x, y), n in pairs.items():
        if n < MIN_SHARED:
            continue
        # rare sentences only, on both sides, so the denominator matches the numerator
        ax = len(doc_sents[x] - boiler)
        ay = len(doc_sents[y] - boiler)
        if not ax or not ay:
            continue
        c = n / min(ax, ay)
        if c >= a.threshold:
            edges.append((x, y, n, round(c, 3)))

    print(f"pairs above containment {a.threshold}: {len(edges)}\n")

    # union-find, because duplication is not always pairwise: a family can put three or
    # more publications in the corpus and reporting them as three pairs hides that.
    parent: dict[str, str] = {}

    def find(v):
        parent.setdefault(v, v)
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    def union(u, v):
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv

    for x, y, _, _ in edges:
        union(x, y)

    groups: dict[str, list[str]] = collections.defaultdict(list)
    for v in list(parent):
        groups[find(v)].append(v)
    groups = {k: sorted(v) for k, v in groups.items() if len(v) > 1}

    dupes = sum(len(v) - 1 for v in groups.values())
    print(f"DUPLICATE GROUPS   {len(groups)}")
    print(f"REDUNDANT DOCUMENTS{dupes:>6}  ({dupes / len(doc_sents) * 100:.1f}% of the corpus)")
    print(f"documents after collapsing: {len(doc_sents) - dupes}\n")

    by_size = collections.Counter(len(v) for v in groups.values())
    print("group sizes:", dict(sorted(by_size.items())))

    print("\nlargest groups:")
    for g in sorted(groups.values(), key=lambda v: -len(v))[:15]:
        print(f"  {len(g)}  {', '.join(g)}")

    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(
            {"threshold": a.threshold, "min_shared": MIN_SHARED,
             "boilerplate_max": BOILERPLATE_MAX,
             "documents": len(doc_sents), "redundant": dupes,
             "groups": sorted(groups.values(), key=lambda v: (-len(v), v[0])),
             "edges": sorted(edges, key=lambda e: -e[3])[:500]}, indent=1))
        print(f"\n-> {a.json}")

    print("\nNOTHING WAS DELETED. Which member of a group to keep is a provenance")
    print("decision (dedupe_families.py: grants first, then lowest publication number),")
    print("and removing a document invalidates rows that point at it — so it goes")
    print("through merge_review.py, deliberately, not through this script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
