#!/usr/bin/env python3
"""
propose.py — Claude proposes, Ivan disposes. Batches candidates out and suggestions in.

    python3 propose.py export --n 150      # -> propose-batch.jsonl  (sentences only)
    python3 propose.py apply               # <- propose-in.jsonl, merged as SUGGESTIONS
    python3 propose.py status

WHY PROPOSALS AND NOT DECISIONS
-------------------------------
Measured blind on 2026-08-25 against 98 of Ivan's decisions:

    overall agreement    85.7%
    precision on reject  85.3%     <- auto-rejection needs >=98%
    molecule spans       93%       on rows both approved

Auto-rejecting at 85% precision would silently destroy about one real row in seven, and a
deleted row leaves no trace anywhere downstream — the same shape of loss as the capped
Google window and the 404-as-missing-patent. So nothing here writes `decision`.

What it writes is `proposed_*` fields. The UI pre-fills them, marks the row PROPOSED, and
Ivan's keypress is what creates the decision. The 93% span accuracy is the real prize:
the drag-selecting of long chemical names is the slow, error-prone part, and it is the
part a machine is actually good at.

THE EVAL SET IS BURNED
----------------------
heldout.py's discipline: if a rule changes because of what the set revealed, the set is
spent. It did — the mixture and unspecified-substituent rules were both settled by those
disagreements (see REVIEW-RULES.md). So 85.7% is not a clean estimate of accuracy under
the current rules, only the number that triggered writing them down. Re-measure on a
fresh sample before quoting it.

FORMAT
------
export writes: {"n", "source_id", "char_offset", "sentence"}
Claude returns:{"n", "decision", "molecules", "descriptors", "why"}

`why` is not decoration. It states which rule fired, so a wrong proposal is diagnosable as
a rule misapplied rather than a mystery — and so a systematic error shows up as the same
`why` repeated, which is exactly how a model fails.
"""
from __future__ import annotations
import collections, json, pathlib, re, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
HERE = pathlib.Path(__file__).resolve().parent
REVIEW = ROOT / "corpus" / "rows" / "review.jsonl"
BATCH = HERE / "propose-batch.jsonl"
INBOX = HERE / "propose-in.jsonl"

PROPOSED = ("proposed_decision", "proposed_molecules", "proposed_descriptors", "proposed_why")


def load():
    head = None
    rows = []
    for l in REVIEW.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        if l.startswith('{"_comment"'):
            head = l; continue
        rows.append(json.loads(l))
    return head, rows


def save(head, rows):
    bak = REVIEW.with_suffix(f".jsonl.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    bak.write_text(REVIEW.read_text(encoding="utf-8"), encoding="utf-8")
    with REVIEW.open("w", encoding="utf-8") as fh:
        if head:
            fh.write(head + "\n")
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"backup -> {bak.name}")


# PRODUCTIVE — copied verbatim from review.html so the two agree.
#
# The first export sorted by queue order and length, pulled the head of the queue, and
# came back 90% rejects (13 near-identical "compounds (2), (9), (13) ... having a spicy
# note" sentences from one patent). Effort spent, few rows gained.
#
# A sentence can only become a row if it contains BOTH a name-like span and a descriptor.
# Roughly 22% of candidates do, and precision within them is ~0.87 against ~0.2 over the
# whole queue. Same reviewing effort, several times the rows.
#
# This must match the UI's definition exactly. An earlier hand-rolled approximation of it
# estimated 64% productive where the UI's own rule says 22.5% — a proxy that disagrees
# with the thing it proxies is worse than no proxy, because it reads as a measurement.
VOCAB = ["acid", "aldehydic", "almond", "amber", "ambery", "animalic", "anise", "aniseed",
         "apple", "aquatic", "aromatic", "balsamic", "banana", "berry", "blossom-type",
         "burnt", "buttery", "camphor", "camphoraceous", "caramel", "cedarwood", "cheesy",
         "cinnamon", "citrus", "citrus-like", "clove", "coconut", "creamy", "diffusive",
         "dry", "earthy", "ether", "ethereal", "faecal", "fatty", "fish", "floral",
         "flowery", "fresh", "fruity", "gardenia", "grassy", "green", "herbal", "honey",
         "jasmin", "jasmine", "leafy", "leather", "leathery", "lemon", "lilac", "lily",
         "liquorice", "marine", "medicinal", "metallic", "mint", "minty", "mossy",
         "muguet", "musk", "musky", "nutty", "orange", "ozonic", "patchouli", "peach",
         "pear", "phenolic", "pine", "pineapple", "powdery", "radiant", "resinous",
         "roasted", "rose", "rosy", "sandalwood", "smoke", "smoky", "spicy", "sulfurous",
         "sweet", "tenacious", "terpenic", "tobacco", "transparent", "tropical", "vanilla",
         "vetiver", "violet", "watery", "waxy", "winey", "woody"]
_NAME = re.compile(r"\b[a-z0-9\[\]\(\),'\-]*\d[a-z0-9\[\]\(\),'\-]*(?:ol|al|one|ate|ene|ane|oate)\b", re.I)
_TAGW = re.compile(r"\b(" + "|".join(VOCAB) + r")\b", re.I)

# Sentences that cannot yield a row no matter what they contain. Filtering these is not
# cherry-picking — they are the ones the first batch wasted itself on.
_DEAD = re.compile(
    r"compounds?\s*\(\d+\)"              # "compounds (2), (9), (13)"
    r"|formula\s*\(\w+\)"                # "compound of formula (I)"
    r"|\bFIG\b|\bshows the\b"            # figure captions
    r"|\bas used herein\b|\bit is meant here\b"   # definitions
    r"|\balk(?:yl|oxy|enyl)\b",          # unspecified substituent -> now a REJECT rule
    re.I)


def productive(s: str) -> bool:
    return bool(s) and bool(_NAME.search(s)) and bool(_TAGW.search(s))


def cmd_export(n=150):
    _, rows = load()
    todo = [(k, r) for k, r in enumerate(rows)
            if not r.get("decision") and not r.get("proposed_decision")]
    live = [(k, r) for k, r in todo
            if productive(r["sentence"]) and not _DEAD.search(r["sentence"])]
    print(f"{len(todo)} undecided and unproposed")
    print(f"{len(live)} of them productive and not obviously dead "
          f"({len(live)/max(1,len(todo))*100:.0f}%)")
    live.sort(key=lambda kr: kr[1].get("queue_order", 0))
    take = live[:n]
    with BATCH.open("w", encoding="utf-8") as fh:
        for k, r in take:
            fh.write(json.dumps({"n": k, "source_id": r["source_id"],
                                 "char_offset": r.get("char_offset"),
                                 "sentence": r["sentence"]}, ensure_ascii=False) + "\n")
    print(f"exported {len(take)}")
    print(f"-> {BATCH.name}")
    print("`n` is the ROW INDEX in review.jsonl — return it unchanged.")


def cmd_apply():
    head, rows = load()
    props = [json.loads(l) for l in INBOX.read_text(encoding="utf-8").splitlines() if l.strip()]
    batch = {json.loads(l)["n"]: json.loads(l)
             for l in BATCH.read_text(encoding="utf-8").splitlines() if l.strip()}

    applied = skipped = bad = 0
    for p in props:
        k = p.get("n")
        if k is None or k >= len(rows):
            bad += 1; continue
        r = rows[k]
        b = batch.get(k)
        # The row must be the one that was sent out. Indices shift if review.jsonl is
        # rebuilt between export and apply, and a proposal landing on the wrong sentence
        # would be silent and catastrophic.
        if b and b["sentence"].strip() != (r.get("sentence") or "").strip():
            print(f"! row {k} no longer holds the sentence that was exported — skipped")
            bad += 1; continue
        if r.get("decision"):
            skipped += 1; continue        # never overwrite a human decision
        mols = [m for m in (p.get("molecules") or []) if m and m in r["sentence"]]
        drop = [m for m in (p.get("molecules") or []) if m not in mols]
        if drop:
            print(f"  row {k}: dropped non-verbatim span(s) {drop}")
        descs = [d for d in (p.get("descriptors") or []) if d and d in r["sentence"]]
        r["proposed_decision"] = p.get("decision")
        r["proposed_molecules"] = mols
        r["proposed_descriptors"] = descs
        r["proposed_why"] = p.get("why", "")
        applied += 1

    print(f"\napplied {applied} proposals, skipped {skipped} already-decided, {bad} bad")
    save(head, rows)
    print(f"written -> {REVIEW.name}")
    print("\nNOTHING was decided. Load review.jsonl in review.html; proposed rows are")
    print("pre-filled and marked. Your keypress is what makes it a decision.")


def cmd_status():
    _, rows = load()
    c = collections.Counter()
    for r in rows:
        if r.get("decision"):
            c["decided"] += 1
        elif r.get("proposed_decision"):
            c["proposed, awaiting you"] += 1
        else:
            c["untouched"] += 1
    for k, v in c.most_common():
        print(f"  {k:<24} {v}")
    agree = [r for r in rows if r.get("decision") and r.get("proposed_decision")]
    if agree:
        ok = sum(1 for r in agree if r["decision"] == r["proposed_decision"])
        print(f"\nrunning agreement on confirmed rows: {ok}/{len(agree)} "
              f"= {ok/len(agree)*100:.1f}%")
        print("  ^ accumulates as you work — a live accuracy estimate under current rules")
        why = collections.Counter(r.get("proposed_why", "?")[:40]
                                  for r in agree if r["decision"] != r["proposed_decision"])
        if why:
            print("  most common reasons behind WRONG proposals:")
            for w, n in why.most_common(5):
                print(f"    {n}x  {w}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 150
    if cmd == "export":
        cmd_export(n)
    elif cmd == "apply":
        cmd_apply()
    elif cmd == "status":
        cmd_status()
    else:
        print(__doc__)
