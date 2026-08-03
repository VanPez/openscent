#!/usr/bin/env python3
"""
Build and score a HELD-OUT set — the first honest accuracy number for the filter.

    python3 heldout.py sample     # ON HETZNER (needs corpus/raw). writes two files.
    python3 heldout.py score      # anywhere, once heldout-labelled.jsonl exists

Why this exists
---------------
`pipeline/testset.jsonl` scores 1.00/1.00 and that number means nothing: every rule was
written while looking at those 29 sentences, and when the filter disagreed with a label
the label moved (t10, t11). TESTSET.md says so at the top. This set is the fix.

Two rules make it honest, and both are easy to break by accident:

1. **Sentences the filter REJECTED must be in the sample.** A set built only from
   `candidates.json` cannot contain a sentence the filter has always missed, so recall
   measured against it is an upper bound on optimism, not an estimate. That is the exact
   flaw in the existing test set. So we sample from both strata.

2. **Label blind, score once, never tune.** `sample` writes the sentences WITHOUT the
   filter's decision, and the decisions to a separate key file. Label the first, then run
   `score`. If a rule is later changed because of what this set revealed, this set is
   burned and a new one must be drawn — say so in DEVLOG rather than quietly re-scoring.

Stratified, not uniform
-----------------------
Only ~12% of odour-bearing sentences are accepted, so a uniform sample of 50 would contain
~6 accepted rows and say nothing useful about precision. We sample equally from each
stratum and REWEIGHT by the true stratum sizes when scoring — otherwise precision looks
far worse than it is, because the accepted stratum is deliberately over-sampled.
"""
from __future__ import annotations
import json, os, pathlib, random, sys, importlib.util

_here = pathlib.Path(__file__).resolve().parent
ROOT  = pathlib.Path(os.environ.get("OPENSCENT_ROOT",
            _here.parent if _here.name == "pipeline" else _here / "openscent"))
RAW   = ROOT / "corpus" / "raw"
OUT   = ROOT / "pipeline"
SEED  = 20260801          # fixed, so the draw is reproducible and cannot be re-rolled
N_PER_STRATUM = 25        # 50 sentences total — enough to be informative, small enough to label

spec = importlib.util.spec_from_file_location("harvest", _here / "harvest.py")
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)

# Patents used in ANY tuning: the 29-sentence test set plus every patent named in a
# hand-run report. Sampling from these would leak the tuning data back in.
#
# KNOWN GAP, stated rather than hidden: handrun-03 sampled 25 patents and handrun-04
# sampled 60, and neither list was recorded. Those runs informed the EXCLUDE rules and
# the stop lists, so up to ~85 unidentifiable patents may survive this exclusion. The
# contamination is weaker than the test set's (aggregate statistics, not per-sentence
# tuning) but it is real, and any accuracy number from this set carries the caveat.
EXCLUDE_PATENTS = {
    "US10138441B2", "US11332693B2", "US20080064625A1", "US20080081779A1",
    "US20130089591A1", "US20180187123A1", "US20190376001A1", "US20210395639A1",
    "US3929677A", "US8709994B2", "US8852565B2", "US9109187B2", "US9962674B2",
    "US9988592B2", "USRE49502E1", "US4482465A",
}


def decide(s: str) -> tuple[bool, str]:
    """Mirror harvest.extract()'s accept path — and score.py's. Keep all three in step."""
    if not (25 < len(s) < 320):        return False, "length"
    for rx, lbl in H.EXCLUDE:
        if rx.search(s):               return False, lbl
    if H.HEADING.search(s):            return True,  "kept (heading)"
    if not H.ODOUR.search(s):          return False, "no odour word"
    if not H.DESCR.search(s):          return False, "no description verb"
    if not H.named(s):                 return False, "no compound/example name"
    return True, "kept"


def sample() -> None:
    if not RAW.exists():
        sys.exit(f"no corpus at {RAW} — run this on the box that holds corpus/raw/")
    OUT.mkdir(parents=True, exist_ok=True)   # on a headless box ROOT/pipeline may not exist
    accepted, rejected = [], []
    files = sorted(f for f in RAW.glob("*.txt") if f.stem not in EXCLUDE_PATENTS)
    print(f"{len(files)} patents in scope ({len(EXCLUDE_PATENTS)} excluded as tuning sources)")
    for f in files:
        text = H.norm(f.read_text(encoding="utf-8"))
        for s in H.SENT.split(text):
            if not H.ODOUR.search(s):     # odour-bearing only: the rest is not a judgement call
                continue
            ok, why = decide(s)
            (accepted if ok else rejected).append({"src": f.stem, "text": H.norm(s), "why": why})

    print(f"odour-bearing sentences: {len(accepted)+len(rejected)}  "
          f"(accepted {len(accepted)}, rejected {len(rejected)})")
    rng = random.Random(SEED)
    pick_a = rng.sample(accepted, min(N_PER_STRATUM, len(accepted)))
    pick_r = rng.sample(rejected, min(N_PER_STRATUM, len(rejected)))

    rows = []
    for i, r in enumerate(pick_a + pick_r):
        rows.append(dict(id=f"h{i+1:02d}", src=r["src"], text=r["text"],
                         _stratum="accept" if r in pick_a else "reject", _why=r["why"]))
    rng.shuffle(rows)                      # so the strata are not visible from the order

    unl = OUT / "heldout-unlabelled.jsonl"
    key = OUT / "heldout-key.json"
    with unl.open("w", encoding="utf-8") as fh:
        fh.write('{"_comment": "Label each row: set \\"label\\" to keep or drop, and say why. '
                 'Do NOT look at heldout-key.json until every row is labelled. '
                 'keep = this sentence could become a corpus row: it describes a smell AND '
                 'names a molecule that could be resolved to a structure."}\n')
        for r in rows:
            fh.write(json.dumps({"id": r["id"], "src": r["src"], "text": r["text"],
                                 "label": "", "why": ""}, ensure_ascii=False) + "\n")
    key.write_text(json.dumps({
        "seed": SEED,
        "strata_sizes": {"accept": len(accepted), "reject": len(rejected)},
        "sampled": {r["id"]: {"stratum": r["_stratum"], "filter_said": r["_why"]} for r in rows},
    }, indent=1), encoding="utf-8")
    print(f"\n-> {unl}   ({len(rows)} sentences, unlabelled, strata shuffled)")
    print(f"-> {key}   (the filter's answers — do not open until labelling is done)")


def score() -> None:
    key = json.loads((OUT / "heldout-key.json").read_text())
    lab = {}
    for line in (OUT / "heldout-labelled.jsonl").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith('{"_comment"'):
            continue
        r = json.loads(line)
        if r.get("label") in ("keep", "drop"):
            lab[r["id"]] = r
    if not lab:
        sys.exit("no labelled rows found in pipeline/heldout-labelled.jsonl")

    N = key["strata_sizes"]
    # Reweight: each sampled sentence stands for (stratum size / sampled from stratum) real ones.
    counts = {"accept": 0, "reject": 0}
    for i in key["sampled"].values():
        counts[i["stratum"]] += 1
    w = {s: N[s] / counts[s] for s in counts if counts[s]}

    tp = fp = tn = fn = 0.0
    disagree = []
    for rid, r in lab.items():
        meta = key["sampled"][rid]
        got  = meta["stratum"] == "accept"
        want = r["label"] == "keep"
        ww   = w[meta["stratum"]]
        if   got and want:      tp += ww
        elif got and not want:  fp += ww; disagree.append(("FALSE POSITIVE", rid, r, meta))
        elif not got and want:  fn += ww; disagree.append(("MISSED",         rid, r, meta))
        else:                   tn += ww

    prec = tp/(tp+fp) if tp+fp else 0.0
    rec  = tp/(tp+fn) if tp+fn else 0.0
    f1   = 2*prec*rec/(prec+rec) if prec+rec else 0.0
    print(f"labelled {len(lab)} of {len(key['sampled'])} sampled sentences")
    print(f"stratum sizes: accept {N['accept']}, reject {N['reject']}  (weights applied)")
    print(f"\nprecision {prec:.2f}   recall {rec:.2f}   F1 {f1:.2f}   <- HELD OUT, tune nothing on this")
    if disagree:
        print(f"\n{len(disagree)} disagreements:")
        for kind, rid, r, meta in disagree:
            print(f"  [{kind}] {rid} ({r['src']}) — filter: {meta['filter_said']}")
            print(f"      {r['text'][:120]}")
            print(f"      you said {r['label']}: {r.get('why','')}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if   cmd == "sample": sample()
    elif cmd == "score":  score()
    else: print(__doc__)
