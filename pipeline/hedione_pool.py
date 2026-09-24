#!/usr/bin/env python3
"""Draw the next batch from the Hedione-class review pool.

WHY THIS EXISTS
---------------
review.html orders its queue by PRODUCTIVE(), which requires a compound-like
token CARRYING A DIGIT plus a vocabulary term. That rule is blind to
trivially-named chemistry: santalol, ambroxide, caryophyllene, Hedione. On
2026-09-23 status.py reported "0 PRODUCTIVE" with 3,286 rows still undecided,
and the queue looked exhausted. It was not. The blind spot measured 47%
productive — better than anything else left in the corpus.

Batches 1-4 were drawn with an INLINE command that was never saved, which meant
every new chat had to reconstruct the pool definition from prose. This script is
that command, written down. It is the definition of record.

SELF-CORRECTING BY DESIGN
-------------------------
The pool excludes any row that already carries a decision OR a proposed_decision.
So a batch that has been staged is out of the pool the moment propose.py runs,
and a batch that has been exported stays out. That means the draw does NOT have
to reproduce the historical seeds to be correct — re-running with any seed can
never hand back a row that has already been worked. Do not "fix" this by
hardcoding the old seeds; the exclusion is what guarantees correctness, not the
random state.

THE COUNT DOES NOT MATCH THE OLD ONE — READ THIS
-------------------------------------------------
The inline command reported a 713-row population and "405 remaining" before
batch 4. This script reports 821 after batch 4. The pool is NOT the same set:
the original NOISE list was reconstructed from prose, and this one is looser, so
it admits rows the old draw never saw. That is safe (worked rows are excluded by
decision/proposed_decision, so nothing can be double-drawn) but it means:

  * The measured 47% productive rate was obtained on the TIGHTER pool.
    Do not extrapolate 47% x 821. Re-measure from the next batch's own yield.
  * The yields to date are the real evidence: batch 1 31A/7S, batch 2 37A/1S,
    batch 3 24A/3S, batch 4 30A/8S (staged). That is a 38% mean approve rate
    trending flat, on a pool that this script has now widened.

USAGE
    python3 pipeline/hedione_pool.py            # report pool size only
    python3 pipeline/hedione_pool.py 100        # draw 100, write /tmp/batch.json
    python3 pipeline/hedione_pool.py 100 --seed 20260923
    python3 pipeline/hedione_pool.py 100 --noise2-first --out /tmp/b8/batch.json
      (--noise2-first: NOISE2-clean rows first, an ORDER not a filter; --out: /tmp/batch.json
       can be a stale unwritable file left by an earlier chat)

Run from the openscent root. Measure before you fetch; this only reads.
"""
import json, re, sys, random, pathlib, importlib.util

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("status", ROOT / "pipeline/status.py")
st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)

# A compound-like token that PRODUCTIVE() would catch: it carries a digit.
# The Hedione class is defined by the ABSENCE of one.
DIGIT_COMPOUND = re.compile(r"[A-Za-z][A-Za-z\-\[\]\(\),']*\d|\d[A-Za-z\-]")

# Markers that made a row near-certainly unproductive in batches 1-4. Excluding
# them is what lifts the pool from ~25% to the measured 47%. These are NOT a
# judgement — every excluded row stays undecided and can be reviewed later.
NOISE = re.compile(
    r"\b(this compound|said compound|the compound of|the substance|the product|"
    r"the mixture|the invention|according to the invention|of formula|formula [IVX]|"
    r"compounds of|derivatives of|composition|perfume base|accord|"
    r"wherein|R\d\s*represents|alkyl|alkenyl)\b", re.I)


def pool():
    surf = st.load_tags()
    forms = sorted(surf, key=len, reverse=True)
    rx = re.compile(r"\b(" + "|".join(map(re.escape, forms)) + r")\b", re.I)
    out = []
    for n, r in enumerate(st.jsonl(st.REVIEW)):
        if r.get("decision") or r.get("proposed_decision"):
            continue
        if r.get("split_of") is not None:
            continue
        s = r.get("sentence", "")
        if not rx.search(s):          # no odour vocabulary at all
            continue
        if DIGIT_COMPOUND.search(s):  # review.html already surfaces these
            continue
        if NOISE.search(s):           # anaphora / family / composition
            continue
        out.append({"n": n, "source_id": r["source_id"],
                    "char_offset": r.get("char_offset"), "sentence": s})
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    seed = 20260923
    if "--seed" in sys.argv:
        seed = int(sys.argv[sys.argv.index("--seed") + 1])
    p = pool()
    print(f"clean pool remaining: {len(p)}")
    if not args:
        sys.exit(0)
    k = min(int(args[0]), len(p))
    out = pathlib.Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else pathlib.Path("/tmp/batch.json")
    random.seed(seed)
    if "--noise2-first" in sys.argv:
        # ORDERING, not exclusion (DEVLOG 2026-09-23 night): rows that pass target_pool.NOISE2
        # are drawn first, the rest only if the clean tier runs out. Nothing leaves the pool.
        sp = importlib.util.spec_from_file_location("target_pool", ROOT / "pipeline/target_pool.py")
        tp = importlib.util.module_from_spec(sp); sp.loader.exec_module(tp)
        clean = [b for b in p if not tp.NOISE2.search(b["sentence"])]
        rest = [b for b in p if tp.NOISE2.search(b["sentence"])]
        print(f"NOISE2 tiers: {len(clean)} clean first, {len(rest)} after")
        batch = random.sample(clean, min(k, len(clean)))
        if len(batch) < k:
            batch += random.sample(rest, k - len(batch))
    else:
        batch = random.sample(p, k)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(batch, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"drew {k} -> {out}  (seed {seed})")
    for i, b in enumerate(batch, 1):
        print(f"\n{i}. {b['source_id']}\n   {b['sentence'][:400]}")
