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
    """Delegates to harvest.decide() — the single accept path.

    This function used to be its own copy of that logic and it drifted: it grew a
    HEADING rule that harvest.extract() never had, so this scorer measured a filter
    that did not exist. Do not reintroduce a local copy."""
    return H.decide(s)

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
