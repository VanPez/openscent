#!/usr/bin/env python3
"""
merge_review.py — carry existing review decisions onto a regenerated candidate set.

    python3 merge_review.py                       # report only
    python3 merge_review.py --write

WHY THIS EXISTS
---------------
The corpus doubled (2,588 -> 5,346 patents) and `harvest.py extract` rewrote
candidates.json from scratch: 2,205 -> 6,599. The review file holds 250 hand-made
decisions keyed to the OLD set. Loading the new candidates into the UI would present a
fresh queue and those decisions would simply be gone — not deleted, just never carried,
which is worse because nothing would report it.

Hours of judgement, lost to a file being regenerated. So the join happens here, once,
deliberately, with the losses counted.

THE JOIN KEY IS (source_id, sentence)
-------------------------------------
NOT char_offset. Offsets are stable only while the extractor's normalisation is stable,
and normalisation has changed twice already. The sentence text IS the evidence — it is
what was reviewed, what the verbatim check runs against, and what a molecule span was
selected from. If the text matches, the decision applies.

ORPHANS ARE REPORTED, NEVER DISCARDED QUIETLY
---------------------------------------------
A decided sentence that no longer appears in candidates.json means the extractor stopped
producing it. That is a real signal about a filter change, not noise, and it is written to
review-orphans.jsonl so the work can be recovered if the disappearance was a mistake.
"""
from __future__ import annotations
import json, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAND = ROOT / "corpus" / "extracted" / "candidates-new.json"
REVIEW = ROOT / "corpus" / "rows" / "review.jsonl"
OUT = REVIEW
ORPHANS = ROOT / "corpus" / "rows" / "review-orphans.jsonl"

DECIDED = ("decision", "molecules", "molecule", "descriptors", "reviewer", "split_of")


def key(r):
    return (r.get("source_id", ""), (r.get("sentence") or "").strip())


def main() -> int:
    write = "--write" in sys.argv
    cands = json.loads(CAND.read_text(encoding="utf-8"))

    head, old = None, []
    for l in REVIEW.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        if l.startswith('{"_comment"'):
            head = l; continue
        old.append(json.loads(l))

    # SPLITS SHARE A KEY WITH THEIR PARENT AND MUST NOT COLLAPSE.
    #
    # The review UI's P key duplicates a candidate so that one sentence naming two
    # compounds with DIFFERENT descriptions can be recorded as two rows — the cis/trans
    # and contrast cases. Parent and split have identical source_id and sentence.
    #
    # A dict keyed on (source_id, sentence) silently keeps one of each pair. The first
    # version of this script did exactly that and reported "245 of 245 carried, 0
    # orphaned" — a clean bill of health while discarding five of the most considered
    # decisions in the file. Caught only because 245 did not equal the 250 counted
    # earlier. Group into lists instead.
    decided: dict = {}
    for r in old:
        if r.get("decision"):
            decided.setdefault(key(r), []).append(r)
    n_decided = sum(len(v) for v in decided.values())
    n_splits = sum(len(v) - 1 for v in decided.values() if len(v) > 1)
    print(f"candidates (new) : {len(cands)}")
    print(f"review rows (old): {len(old)}, of which decided: {n_decided}")
    if n_splits:
        print(f"  including {n_splits} split row(s) sharing a sentence with their parent")

    out, carried = [], set()
    for c in cands:
        k = key(c)
        prev = decided.get(k)
        if not prev:
            out.append(dict(c))
            continue
        # parent first (split_of is None), then any splits, each as its own row
        ordered = sorted(prev, key=lambda r: (r.get("split_of") is not None,
                                              r.get("split_of") or 0))
        for p in ordered:
            row = dict(c)
            for f in DECIDED:
                if f in p:
                    row[f] = p[f]
            out.append(row)
        carried.add(k)

    n_carried = sum(len(decided[k]) for k in carried)
    orphans = [r for k, v in decided.items() if k not in carried for r in v]
    print(f"\ndecisions carried : {n_carried}")
    print(f"decisions ORPHANED: {len(orphans)}")
    if orphans:
        print("  (decided sentences no longer produced by the extractor)")
        for r in orphans[:5]:
            print(f"    {r['source_id']}  {r.get('decision')}  {r['sentence'][:70]}...")
    undecided = len(out) - n_carried
    print(f"\nnew queue: {len(out)} rows, {n_carried} decided, {undecided} to review")
    print(f"  (was {len(old)} rows, {n_decided} decided)")

    if not write:
        print("\nDry run. Add --write to rebuild review.jsonl.")
        return 0

    if n_carried != n_decided:
        print(f"\n! {n_decided - n_carried} decision(s) failed to carry. That suggests the join is")
        print("  wrong, not that the extractor changed. NOT writing — check first.")
        return 1

    bak = REVIEW.with_suffix(f".jsonl.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    bak.write_text(REVIEW.read_text(encoding="utf-8"), encoding="utf-8")
    with OUT.open("w", encoding="utf-8") as fh:
        if head:
            fh.write(head + "\n")
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    if orphans:
        with ORPHANS.open("w", encoding="utf-8") as fh:
            for r in orphans:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\norphans -> {ORPHANS.name}")
    print(f"backup  -> {bak.name}")
    print(f"written -> {OUT.name}  ({len(out)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
