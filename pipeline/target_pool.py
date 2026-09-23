#!/usr/bin/env python3
"""Draw a TARGETED batch: undecided rows carrying vocabulary for named near-bar tags.

Written 2026-09-23 for batch 6. Unlike hedione_pool.py this does NOT exclude rows
whose compound name carries a digit — it draws across the whole queue, filtered only
by tag vocabulary and noise. Measure before you fetch; this only reads review.jsonl.

  NOISE   hedione_pool.NOISE plus NOISE2 below. NOISE2 was fitted on batch 5's rejects;
          out of sample (batches 1-4) it lifted approve rate only 26% -> 29% and cost
          5 of 65 approves. It is a filter of convenience, not a judgement: excluded
          rows stay undecided.
  CAP     at most 3 rows per patent (batch 1 clustered 11 cigarette rows in one sitting).
  TAGS    default animalic aldehydic apple. tobacco left out on purpose — clusters.

USAGE  python3 pipeline/target_pool.py                       # count only
       python3 pipeline/target_pool.py draw [tag ...]         # write /tmp/batch.json
"""
import json, re, sys, pathlib, collections, importlib.util
ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("hp", ROOT / "pipeline/hedione_pool.py")
hp = importlib.util.module_from_spec(spec); spec.loader.exec_module(hp)
st = hp.st
NOISE2 = re.compile("|".join([
    r"\bof (our|the present|this) invention\b|\bpresent invention\b",
    r"\b(produced|prepared|obtained|synthesi[sz]ed) (according|in accordance|by the process)|\b(so|thus) (produced|obtained|prepared)\b",
    r"\bas little as\b|\bwill suffice\b|\bformulations?\b",
    r"^\s*(It|Its|They|These|This|Such)\b",
    r"\b(this|the|these|said|such) (new |novel )?(ketone|acetal|aldehyde|ester|alcohol|molecule|material|isomer|acetate|compound|product)s?\b",
    r"\bthe (trans|cis|syn|anti|[EZ]) isomer\b",
    r"\b(cologne|detergent|soap|powder|linen|fabric|shampoo|lotion|perfumed article)s?\b",
    r"\bgeneral formula\b|\bnovel (class|compounds)\b|\bthere (is|has been) a (real )?need\b"]), re.I)
CAP = 3

def draw(tags):
    surf = st.load_tags()
    forms = sorted([f for f, t in surf.items() if t in tags], key=len, reverse=True)
    rx = re.compile(r"\b(" + "|".join(map(re.escape, forms)) + r")\b", re.I)
    per = collections.Counter(); out = []
    for n, r in enumerate(st.jsonl(st.REVIEW)):
        if r.get("decision") or r.get("proposed_decision") or r.get("split_of") is not None: continue
        s = r.get("sentence", "")
        m = rx.search(s)
        if not m or hp.NOISE.search(s) or NOISE2.search(s): continue
        if per[r["source_id"]] >= CAP: continue
        per[r["source_id"]] += 1
        out.append({"n": n, "source_id": r["source_id"], "char_offset": r.get("char_offset"),
                    "sentence": s, "tag": surf[m.group(0).lower()] if m.group(0).lower() in surf else m.group(0)})
    return out

if __name__ == "__main__":
    a = sys.argv[1:]
    tags = set(a[1:]) or {"animalic", "aldehydic", "apple"}
    b = draw(tags)
    print(f"targeted pool ({', '.join(sorted(tags))}): {len(b)}", dict(collections.Counter(x['tag'] for x in b)))
    if a[:1] == ["draw"]:
        pathlib.Path("/tmp/batch.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
        for i, x in enumerate(b, 1): print(f"\n{i}. {x['source_id']} [{x['tag']}]\n   {x['sentence'][:450]}")
