#!/usr/bin/env python3
"""Stage SCREEN 1: the approves-only pass over the whole undecided queue (2026-09-24).

WHAT THIS IS
------------
Ivan's call, 2026-09-24: Claude reads every undecided row (2,646 of them) and stages only
the APPROVES, so he reviews those instead of the whole queue. Auto-reject stays off: the
rows Claude screens out are NOT rejected. They stay undecided, exactly as they were. For
the corpus that costs nothing, because only approvals count.

What it does cost is RECALL, and that is what the audit sample is for. A seeded random
50 of the screened-out rows are staged as proposed REJECTS, so Ivan sees them in
review.html and decides them like any other row. Every one he flips to approve is a row
the screen missed. That flip rate is the number the paper needs if it reports this
tranche, and it must be reported as a screen of the queue, not as full review.

INPUTS
  corpus/staging/screen/all.json    the undecided queue as drawn (i = 1..2646)
  corpus/staging/screen/vNN.py      Claude's verdicts, 13 chunks:
      A[i]     = ([molecule spans], EXCL, why)    approve (or split, if i is in SPLIT)
      SPLIT    = {i, ...}                          approve-type rows needing a P split
      REP[i]   = j                                 same-document repeat of row j (screened out)
      B[i]     = note                              screened out, but worth Ivan's eye
  Every row NOT in A is screened out.

OUTPUTS
  pipeline/propose-batch.jsonl + propose-in.jsonl       (then: python3 pipeline/propose.py apply)
  corpus/staging/screen/screen-v1.jsonl                 one line per queue row: the verdict and why
  corpus/staging/screen/audit-sample.json               the 50 audit rows (seed 20260924)

CHECKS, and it refuses to write if any fails:
  * every molecule span and every descriptor is a verbatim substring of its sentence
  * row matching on (source_id, full whitespace-normalised sentence), as stage_batch.py
An approve whose sentence has NO ontology descriptor left after EXCL is not staged. It is
listed in the output as 'no mapped descriptor': a row with no tag adds nothing to any count.
Same-document repeats against rows ALREADY approved are dropped the same way.

Every staged `why` starts with "[screen-v1]" so the tranche stays separable after merge.
"""
import json, re, random, importlib.util, pathlib, collections, sys

ROOT = pathlib.Path('.').resolve()
SCR = ROOT / "corpus/staging/screen"
spec = importlib.util.spec_from_file_location("status", ROOT / "pipeline/status.py")
st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)
surf = st.load_tags()
forms = sorted(surf, key=len, reverse=True)
rx = re.compile(r"\b(" + "|".join(map(re.escape, forms)) + r")\b", re.I)
AUDIT_N, AUDIT_SEED = 50, 20260924

rows = []
for l in open('corpus/rows/review.jsonl', encoding='utf-8'):
    l = l.strip()
    if not l or l.startswith('{"_comment"'):
        continue
    rows.append(json.loads(l))
def key(sid, s): return (sid, re.sub(r'\s+', ' ', s or '').strip())
idx = collections.defaultdict(list)
for n, r in enumerate(rows): idx[key(r['source_id'], r.get('sentence'))].append(n)

queue = json.load(open(SCR / "all.json", encoding='utf-8'))
Q = {x['i']: x for x in queue}

A, SPLIT, REP, B = {}, set(), {}, {}
for f in sorted(SCR.glob("v[0-9][0-9].py")):
    ns = {}
    exec(f.read_text(encoding='utf-8'), ns)
    for k in ("A", "REP", "B"):
        clash = set(ns.get(k, {})) & set({"A": A, "REP": REP, "B": B}[k])
        if clash: sys.exit(f"{f.name}: {k} redefines {sorted(clash)}")
    A.update(ns.get("A", {})); REP.update(ns.get("REP", {})); B.update(ns.get("B", {}))
    SPLIT |= ns.get("SPLIT", set())
both = set(A) & set(REP)
if both: sys.exit(f"rows both approved and marked repeat: {sorted(both)}")

# molecules already approved, per document and overall (casefold, exact)
approved_by_doc = collections.defaultdict(set); approved_any = set()
for r in rows:
    if r.get('decision') == 'approve':
        for m in (r.get('molecules') or []):
            approved_by_doc[r['source_id']].add(m.strip().casefold()); approved_any.add(m.strip().casefold())
for p in ("corpus/rows/pubchem-rows.jsonl", "corpus/rows/pubchem-physdesc-rows.jsonl"):
    for l in open(p, encoding='utf-8'):
        n = (json.loads(l).get('molecule_name') or '').strip().casefold()
        if n: approved_any.add(n)

bad, staged, nodesc, repeat_prev, side = [], [], [], [], []
batch_out, in_out = [], []
seen_in_screen = collections.defaultdict(set)   # molecules staged per doc within this screen
for i in sorted(Q):
    x = Q[i]; s = x['sentence']
    k = key(x['source_id'], s)
    open_ = [n for n in idx.get(k, []) if not rows[n].get('decision') and not rows[n].get('proposed_decision')]
    if i not in A:
        side.append({"i": i, "source_id": x['source_id'], "sentence": s,
                     "verdict": "repeat" if i in REP else "screened-out",
                     "note": B.get(i) or (f"same-document repeat of #{REP[i]}" if i in REP else None)})
        continue
    mols, excl, why = A[i]
    excl = {e.lower() for e in excl}
    descs, seen = [], set()
    for m in rx.finditer(s):
        w = m.group(0)
        if w.lower() in excl or w.lower() in seen: continue
        seen.add(w.lower()); descs.append(w)
    for v in mols + descs:
        if v not in s: bad.append((i, f"NOT VERBATIM {v!r}"))
    if not open_: bad.append((i, "no undecided row matches")); continue
    if len(open_) > 1: bad.append((i, f"AMBIGUOUS {open_}")); continue
    n = open_[0]
    tags = sorted({surf[d.lower()] for d in descs if d.lower() in surf})
    doc = x['source_id']
    if not tags:
        nodesc.append(i)
        side.append({"i": i, "source_id": doc, "sentence": s, "verdict": "approve-no-tag",
                     "molecules": mols, "note": why + " — no descriptor in the ontology; not staged."})
        continue
    mk = {m.strip().casefold() for m in mols}
    if mk <= approved_by_doc[doc] or mk <= seen_in_screen[doc]:
        repeat_prev.append(i)
        side.append({"i": i, "source_id": doc, "sentence": s, "verdict": "repeat",
                     "molecules": mols, "note": "same-document repeat of an approved molecule; not staged."})
        continue
    seen_in_screen[doc] |= mk
    new = [m for m in mols if m.strip().casefold() not in approved_any]
    dec = 'split' if i in SPLIT else 'approve'
    tail = f"  [adds molecule: {', '.join(new)}]" if new else "  [molecule already in — attestation]"
    batch_out.append({"n": n, "source_id": doc, "char_offset": rows[n].get("char_offset"), "sentence": s})
    in_out.append({"n": n, "decision": dec, "molecules": mols, "descriptors": descs,
                   "why": "[screen-v1] " + why + tail})
    staged.append((i, dec, mols, tags, bool(new)))
    side.append({"i": i, "source_id": doc, "sentence": s, "verdict": dec, "molecules": mols,
                 "descriptors": descs, "tags": tags, "note": why})

# audit sample: seeded, drawn from every screened-out row (repeats and no-tag rows excluded:
# those were read as approves, so they don't measure what the screen misses)
pool = [r for r in side if r["verdict"] == "screened-out"]
audit = random.Random(AUDIT_SEED).sample(pool, AUDIT_N)
for a in sorted(audit, key=lambda r: r["i"]):
    n = [m for m in idx[key(a['source_id'], a['sentence'])]
         if not rows[m].get('decision') and not rows[m].get('proposed_decision')]
    if len(n) != 1: bad.append((a['i'], f"audit row match {n}")); continue
    batch_out.append({"n": n[0], "source_id": a['source_id'], "char_offset": rows[n[0]].get("char_offset"), "sentence": a['sentence']})
    in_out.append({"n": n[0], "decision": "reject", "molecules": [], "descriptors": [],
                   "why": "[screen-v1 AUDIT] Screened out by Claude. Flip it if it is a row — every flip is a miss the screen made."})
    a["audit"] = True

if bad:
    print("REFUSING:"); [print("  ", b) for b in bad[:30]]; raise SystemExit(1)
if "--dry" not in sys.argv:
    pathlib.Path('pipeline/propose-batch.jsonl').write_text("".join(json.dumps(b, ensure_ascii=False) + "\n" for b in batch_out), encoding='utf-8')
    pathlib.Path('pipeline/propose-in.jsonl').write_text("".join(json.dumps(b, ensure_ascii=False) + "\n" for b in in_out), encoding='utf-8')
    (SCR / "screen-v1.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in side), encoding='utf-8')
    (SCR / "audit-sample.json").write_text(json.dumps(sorted(a["i"] for a in audit)), encoding='utf-8')
c = collections.Counter(r["verdict"] for r in side)
print(f"queue rows read: {len(Q)}   verdicts: {dict(c)}")
print(f"staged: {len(staged)} ({sum(1 for s in staged if s[1]=='split')} splits), "
      f"{sum(1 for s in staged if s[4])} add a molecule; + {len(audit)} audit rejects")
print(f"not staged: {len(nodesc)} approves with no mapped descriptor, {len(repeat_prev)} same-document repeats")
t = collections.Counter(t for s in staged for t in s[3])
print("tags fed:", ", ".join(f"{k} {v}" for k, v in t.most_common()))
print("DRY RUN — nothing written" if "--dry" in sys.argv else "written: propose-batch/in, screen-v1.jsonl, audit-sample.json")
