#!/usr/bin/env python3
"""
exclusion_probe.py — READ ONLY. Would a looser filter recover the tags we are short of?

    python3 exclusion_probe.py                       # the tags nearest the bar
    python3 exclusion_probe.py sandalwood animalic   # or name your own

RUN ON HETZNER — needs corpus/raw/ (5,346 documents) and harvest.py beside it.
Writes nothing, fetches nothing, touches no state.

THE QUESTION
------------
2026-09-05 left one sourcing option alive: re-extract the existing corpus at a looser
filter. "Looser" is not a plan, it is a direction. Before touching ODOUR / DESCR /
NAMED / HEADING / EXCLUDE — which TESTSET.md requires scoring before and after — this
asks whether there is anything there to recover, and specifically for the tags that are
short. C11D 3/50 was declined because it carried no sandalwood and no animalic at all;
if the corpus we already own is dropping such sentences, that is the cheaper source.

IT CALLS decide(), IT DOES NOT REIMPLEMENT IT
---------------------------------------------
The whole point is to measure THE FILTER WE RUN, so the filter is imported. Every
reimplementation in this project has eventually disagreed with the original — the
20/11/15 headline, the reversed odor_terms columns — and a probe that quietly tests a
slightly different filter would answer a question nobody asked.

WHAT THE DROP REASONS MEAN, AND WHICH ONE IS THE PRIZE
------------------------------------------------------
decide() returns four STRUCTURAL misses plus whatever EXCLUDE rule fired:

  no compound/example name  the sentence describes a smell but names nothing this
                            extractor recognises. THIS IS THE RECOVERABLE CLASS —
                            a real molecule may be there under a name NAMED_SUFFIX
                            does not match.
  no odour word             no odou?r/smell/note/character/nuance. Likelier to be
                            genuinely off-topic.
  no description verb       has/possesses/exhibits absent. Often a list or a heading.
  length                    outside 25..320 chars. Long sentences are usually
                            formulation prose; a context window, not a looser bound,
                            is the fix.
  <anything else>           an EXCLUDE rule fired. These are DELIBERATE rejections
                            (compositions, counterfactuals, reagents). Loosening here
                            does not recover rows, it readmits the errors the rules
                            were written to stop.

So read "dropped, and named() would still fail" as the ceiling on what loosening NAMED
could buy, and read the EXCLUDE tally as the part that should stay dropped.
"""
from __future__ import annotations
import collections, os, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
os.environ.setdefault("OPENSCENT_ROOT", str(HERE.parent))
sys.path.insert(0, str(HERE))
import harvest  # noqa: E402

DEFAULT_TAGS = ["sandalwood", "animalic", "amber", "aldehydic", "camphoraceous"]
STRUCTURAL = ("length", "no odour word", "no description verb", "no compound/example name")


def load_surface_forms(tags: set[str]) -> dict[str, str]:
    """surface_form -> tag, for the tags asked about. Surface FIRST, per the file."""
    p = HERE.parent / "ontology" / "odor_terms.tsv"
    if not p.exists():
        sys.exit(f"missing {p} — copy the current odor_terms.tsv to this machine first")
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "\t" not in line:
            continue
        surf, tag = [x.strip() for x in line.split("\t")[:2]]
        if tag in tags:
            out[surf.lower()] = tag
    return out


def main() -> int:
    tags = set(a.lower() for a in sys.argv[1:]) or set(DEFAULT_TAGS)
    forms = load_surface_forms(tags)
    if not forms:
        sys.exit(f"no surface forms in odor_terms.tsv for {sorted(tags)}")
    print(f"tags        {', '.join(sorted(tags))}")
    print(f"forms       {len(forms)}: {', '.join(sorted(forms))}")
    print(f"corpus      {harvest.RAW}\n")

    import re
    # Word-boundary match per surface form, built once. Sorted longest-first so that
    # "sandalwood oil" is tried before "sandal" and the longer form wins the label.
    pats = [(re.compile(r"(?<![a-z])" + re.escape(f) + r"(?![a-z])", re.I), f, t)
            for f, t in sorted(forms.items(), key=lambda kv: -len(kv[0]))]

    docs = sents = mentions = 0
    kept = collections.Counter()
    dropped = collections.Counter()
    reasons = collections.Counter()
    dropped_named = collections.Counter()      # drops where named() nonetheless passes
    examples: dict[str, list[str]] = collections.defaultdict(list)

    for f in sorted(harvest.RAW.glob("*.txt")):
        docs += 1
        text = harvest.norm(f.read_text(encoding="utf-8"))
        for s in harvest.SENT.split(text):
            sents += 1
            hit = None
            for rx, form, tag in pats:
                if rx.search(s):
                    hit = tag
                    break
            if hit is None:
                continue
            mentions += 1
            ok, why = harvest.decide(s)
            if ok:
                kept[hit] += 1
                continue
            dropped[hit] += 1
            label = why if why in STRUCTURAL else f"EXCLUDE:{why}"
            reasons[label] += 1
            if harvest.named(s):
                dropped_named[label] += 1
            if len(examples[label]) < 4:
                examples[label].append(f"{f.stem}  {s[:190]}")

    print(f"documents   {docs}\nsentences   {sents}\n")
    print(f"sentences mentioning one of these tags: {mentions}")
    print(f"  kept by the filter    {sum(kept.values()):5d}   (already in the queue)")
    print(f"  dropped               {sum(dropped.values()):5d}\n")

    print(f"{'per tag':<16}{'mentions':>9}{'kept':>7}{'dropped':>9}")
    for t in sorted(tags):
        print(f"{t:<16}{kept[t]+dropped[t]:>9}{kept[t]:>7}{dropped[t]:>9}")

    print(f"\n{'drop reason':<34}{'count':>7}{'of those, named()':>19}")
    print("-" * 60)
    for label, n in reasons.most_common():
        print(f"{label:<34}{n:>7}{dropped_named[label]:>19}")

    print("\n'named()' passing on a dropped sentence means a compound name IS visible")
    print("and something ELSE dropped it — the most recoverable rows in the table.")
    print("EXCLUDE: rows are deliberate rejections; loosening them readmits known errors.\n")

    for label, n in reasons.most_common():
        print(f"\n--- {label} ({n}) ---")
        for e in examples[label]:
            print(f"  {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
