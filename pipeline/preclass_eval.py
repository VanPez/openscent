#!/usr/bin/env python3
"""
preclass_eval.py — measure how well Claude labels candidates, before trusting it to.

    python3 preclass_eval.py sample          # writes preclass-blind.jsonl (NO decisions)
    python3 preclass_eval.py score           # scores preclass-pred.jsonl against review.jsonl

THE QUESTION
------------
Claude is accurate on the candidates Ivan brings to it one at a time. That is not evidence
it would be accurate over 4,300 in bulk, for two reasons that pull in the same direction:

  selection  — the ones brought over are the HARD ones, discussed with framing, one at a
               time, with a reply that can say "actually, look at the second clause".
  correlation— a human reviewer's mistakes are scattered; a model's are systematic. Getting
               one construction wrong means getting it wrong the same way 200 times, which
               is far harder to notice afterwards than random error.

So: measure it. The apparatus and the discipline come from heldout.py — label blind, score
once, never tune. If a rule is changed because of what this set revealed, the set is burned
and a new one must be drawn.

GROUND TRUTH IS IVAN'S OWN 300 DECISIONS
----------------------------------------
No new labelling needed. `sample` strips the decisions and writes sentences only; Claude
writes predictions to preclass-pred.jsonl; `score` compares.

Rows whose source_id was DISCUSSED IN CHAT are excluded — Claude effectively supplied
those answers, and scoring against them would measure agreement with itself.

STRATIFIED, AND SCORED THAT WAY
-------------------------------
Decisions run ~5:1 approve:reject, and the number that matters for auto-rejection is
precision ON REJECTS — how often "reject" is really a reject. A uniform sample would
contain too few rejects to say anything. So take ALL rejects and an equal-ish number of
approves, then report per-class rather than a single accuracy figure, which would be
flattered by the majority class.

WHAT WOULD JUSTIFY AUTO-REJECTION
---------------------------------
Not overall accuracy. Specifically: of the rows Claude calls reject, how many did Ivan also
reject. A false reject silently deletes a real row and nothing downstream can see it — the
same shape of loss as every other failure in this project. >=98% would justify auto-reject;
below that, Claude proposes and Ivan disposes, which is still most of the speed-up.
"""
from __future__ import annotations
import json, pathlib, random, sys, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
REVIEW = ROOT / "corpus" / "rows" / "review.jsonl"
BLIND = pathlib.Path(__file__).resolve().parent / "preclass-blind.jsonl"
PRED = pathlib.Path(__file__).resolve().parent / "preclass-pred.jsonl"

# Discussed in conversation on 2026-08-19/20 — Claude supplied or shaped these answers.
CONTAMINATED = {
    "US10407378B2", "US10450532B2", "US10774289B2", "US11225629B2", "US20100130397A1",
    "US20120041077A1", "US20130310293A1", "US20150005213A1", "US20160207862A1",
    "US20160376521A1", "US20170275262A1", "US20020055453A1", "US20020055455A1",
    "US20030064146A1", "US20030069167A1", "US20040229770A1", "US20060135400A1",
    "US20090275669A1", "US20160333291A1", "US20130295229A1", "US20120308486A1",
    "US20090156456A1",
}


def load():
    return [json.loads(l) for l in REVIEW.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith('{"_comment"')]


def cmd_sample(n_per_class=60):
    rows = [r for r in load() if r.get("decision") in ("approve", "reject")]
    clean = [r for r in rows if r["source_id"] not in CONTAMINATED]
    print(f"{len(rows)} decided, {len(rows) - len(clean)} excluded as discussed in chat")
    by = collections.defaultdict(list)
    for r in clean:
        by[r["decision"]].append(r)
    rng = random.Random(20260825)
    sample = []
    for k in ("approve", "reject"):
        take = min(n_per_class, len(by[k]))
        sample += rng.sample(by[k], take)
        print(f"  {k}: {len(by[k])} available, {take} sampled")
    rng.shuffle(sample)
    with BLIND.open("w", encoding="utf-8") as fh:
        for n, r in enumerate(sample):
            fh.write(json.dumps({"n": n, "source_id": r["source_id"],
                                 "char_offset": r.get("char_offset"),
                                 "sentence": r["sentence"]}, ensure_ascii=False) + "\n")
    print(f"\n-> {BLIND.name}  ({len(sample)} sentences, NO decisions)")
    print("Claude writes predictions to preclass-pred.jsonl as:")
    print('  {"n": 0, "decision": "reject", "molecules": [], "descriptors": [], "why": "mixture"}')
    print("then: python3 preclass_eval.py score")


def cmd_score():
    truth = {}
    for r in load():
        if r.get("decision") in ("approve", "reject"):
            truth[(r["source_id"], (r.get("sentence") or "").strip())] = r
    blind = {json.loads(l)["n"]: json.loads(l)
             for l in BLIND.read_text(encoding="utf-8").splitlines() if l.strip()}
    preds = [json.loads(l) for l in PRED.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"{len(preds)} predictions against {len(blind)} blind rows\n")

    cm = collections.Counter()
    mol_ok = mol_bad = 0
    misses = []
    for p in preds:
        b = blind.get(p["n"])
        if not b:
            continue
        t = truth.get((b["source_id"], b["sentence"].strip()))
        if not t:
            continue
        got, want = p.get("decision"), t["decision"]
        cm[(want, got)] += 1
        if want != got:
            misses.append((b, want, got, p.get("why", "")))
        if want == got == "approve":
            tm = set(m.lower() for m in (t.get("molecules") or []))
            pm = set(m.lower() for m in (p.get("molecules") or []))
            if tm == pm:
                mol_ok += 1
            else:
                mol_bad += 1

    n = sum(cm.values())
    agree = cm[("approve", "approve")] + cm[("reject", "reject")]
    print(f"overall agreement       {agree}/{n} = {agree/n*100:.1f}%\n")
    print("                 Claude says")
    print("               approve  reject")
    for w in ("approve", "reject"):
        print(f"  Ivan {w:<8}{cm[(w,'approve')]:>7}{cm[(w,'reject')]:>8}")

    said_rej = cm[("approve", "reject")] + cm[("reject", "reject")]
    if said_rej:
        prec = cm[("reject", "reject")] / said_rej * 100
        print(f"\nPRECISION ON REJECT: {cm[('reject','reject')]}/{said_rej} = {prec:.1f}%")
        print("  ^ the number that decides whether auto-rejection is safe.")
        print("    A wrong reject deletes a real row and leaves no trace.")
        print("    >=98% justifies auto-reject; below that, propose-only.")
    if mol_ok + mol_bad:
        print(f"\nmolecule spans exactly right: {mol_ok}/{mol_ok+mol_bad} "
              f"({mol_ok/(mol_ok+mol_bad)*100:.0f}%) on agreed approvals")

    if misses:
        print(f"\n--- {len(misses)} DISAGREEMENTS (read every one; they are the finding) ---")
        for b, want, got, why in misses:
            print(f"\n  {b['source_id']}  Ivan={want}  Claude={got}")
            print(f"    why: {why}")
            print(f"    {b['sentence'][:220]}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "sample":
        cmd_sample()
    elif cmd == "score":
        cmd_score()
    else:
        print(__doc__)
