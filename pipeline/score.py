#!/usr/bin/env python3
"""
Score the extraction filter against pipeline/testset.jsonl.

    python3 pipeline/score.py            # summary + every disagreement
    python3 pipeline/score.py -v         # also list the agreements

Purpose: stop arguing about filter changes and measure them. Any edit to the
EXCLUDE/DESCR/NAMED rules in harvest.py should be scored here before and after.

READ TESTSET.md. The set is small and recall-biased — every sentence in it was
surfaced by an earlier version of this filter, so it cannot see the sentences the
filter never showed anyone. Treat precision as meaningful and recall as a floor.
"""
from __future__ import annotations
import json, pathlib, sys, importlib.util

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("harvest", ROOT / "pipeline" / "harvest.py")
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)

def decide(s: str) -> tuple[bool, str]:
    """Mirror the accept path in harvest.extract() for a single sentence."""
    if not (25 < len(s) < 320):        return False, "length"
    for rx, lbl in H.EXCLUDE:
        if rx.search(s):               return False, lbl
    # Heading path: "PERFUME PROPERTIES Fruity, woody, pineapple-like." — a real
    # descriptor list with no odour noun and no verb. Accepted on the heading alone.
    if H.HEADING.search(s):            return True, "kept (heading)"
    if not H.ODOUR.search(s):          return False, "no odour word"
    if not H.DESCR.search(s):          return False, "no description verb"
    if not H.named(s):                 return False, "no compound/example name"
    return True, "kept"

rows = [json.loads(l) for l in open(ROOT/"pipeline"/"testset.jsonl") if l.strip()
        and not l.lstrip().startswith('{"_comment"')]
tp = fp = tn = fn = 0
bad = []
for r in rows:
    got, why = decide(r["text"])
    want = r["label"] == "keep"
    if   got and want:      tp += 1
    elif got and not want:  fp += 1; bad.append(("FALSE POSITIVE", r, why))
    elif not got and want:  fn += 1; bad.append(("MISSED",         r, why))
    else:                   tn += 1

prec = tp/(tp+fp) if tp+fp else 0.0
rec  = tp/(tp+fn) if tp+fn else 0.0
f1   = 2*prec*rec/(prec+rec) if prec+rec else 0.0
print(f"n={len(rows)}   keep={sum(1 for r in rows if r['label']=='keep')}  drop={sum(1 for r in rows if r['label']=='drop')}")
print(f"TP {tp}  FP {fp}  TN {tn}  FN {fn}")
print(f"precision {prec:.2f}   recall {rec:.2f}   F1 {f1:.2f}")
if bad:
    print(f"\n{len(bad)} disagreements:")
    for kind, r, why in bad:
        print(f"  [{kind}] {r['id']} ({r['src']}) — filter said: {why}")
        print(f"      {r['text'][:120]}")
        print(f"      expected {r['label']}: {r['why']}")
if "-v" in sys.argv:
    print("\nagreements:")
    for r in rows:
        got,_ = decide(r["text"])
        if got == (r["label"]=="keep"): print(f"  ok {r['id']} {r['label']:5} {r['text'][:80]}")
sys.exit(0)
