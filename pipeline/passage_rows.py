#!/usr/bin/env python3
"""passage_rows.py — build PASSAGE-SCOPE rows. Adopted by Ivan 2026-09-24, narrow form.

WHAT A PASSAGE ROW CLAIMS, AND HOW IT DIFFERS FROM A SENTENCE ROW
----------------------------------------------------------------
A sentence row says: this molecule smells of these descriptors, both verbatim in ONE
sentence. A passage row says the same, but the molecule is named in the sentence
IMMEDIATELY BEFORE and the odour sentence refers back to it with an anaphor ("This
compound", "It", "The product"). A PERSON decided what the anaphor refers to, so the
row asserts a RESOLVED REFERENCE. That is a weaker claim than a sentence row makes, and
the file keeps it separate for that reason (see REVIEW-RULES.md, "Passage scope").

The conditions set on 2026-09-10 are enforced here:
  * the row records BOTH sentences, and which one supplied which span
      molecule    -> verbatim in `antecedent`
      anaphor     -> verbatim in `sentence`
      descriptors -> verbatim in `sentence`
  * it carries `link: "human-resolved"`
  * passage rows live in their OWN FILE, corpus/rows/passage-rows.jsonl. To get the
    sentence-scope corpus with its original guarantee, leave that file out
    (`status.py --sentence-scope`)
  * their precision is measured SEPARATELY and never inherited from sentence rows

NARROW FORM, as adopted: window 1 only. The antecedent must name EXACTLY ONE compound,
and the anaphor must pick it out unambiguously. If a "THIS" of the composition could be
the referent ("a cosmetic powder is prepared with X. It has…"), the row is rejected:
there the odour belongs to the composition.

PROPOSE-ONLY. Claude proposes; `review_decision` is Ivan's. status.py counts a passage row
only once `review_decision == "approve"`. Re-running this script KEEPS decisions already
recorded (matched on source_id + full sentence).

INPUT   corpus/staging/pairs.jsonl  (passage_probe.py --dump, run on Hetzner)
OUTPUT  corpus/rows/passage-rows.jsonl
USAGE   python3 pipeline/passage_rows.py            # dry run: print, check, write nothing
        python3 pipeline/passage_rows.py --write
"""
from __future__ import annotations
import collections, importlib.util, json, os, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAIRS = ROOT / "corpus" / "staging" / "pairs.jsonl"
OUT = ROOT / "corpus" / "rows" / "passage-rows.jsonl"
spec = importlib.util.spec_from_file_location("st", ROOT / "pipeline" / "status.py")
st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)

# (source_id, start of sentence) -> (proposal, molecule span in antecedent, anaphor span, EXCL, why)
P = {
 ("US3686177A", "This material is a colorless crystalline solid having a tobacco-honey"):
   ("approve", "2,3-dimethyl- 5,6,7,8-tetrahydroquinoxaline", "This material", set(),
    "Antecedent names one product: 'provides 1.76 g. of X'. The sentence-scope row was rejected on 09-24 (#13) for exactly this anaphor."),
 ("US3748145A", "This material is a colorless crystalline solid having a tobacco-honey"):
   ("approve", "2,3-dimethyl-5,6,7, S-tetrahydroquinoxaline", "This material", set(),
    "Same compound as US3686177A, different patent (attestation). OCR 'S' for 8 in the span — normalise at linkage."),
 ("US3956196A", "This compound also displays tobacco notes."):
   ("approve", "4,5 -decamethyleneoxazole", "This compound", set(),
    "Antecedent: 'The 4,5 -decamethyleneoxazole of the formula II also has a musk-like odour'. Already in the corpus (musk, amber); this adds tobacco."),
 ("US3773525A", "This material has a sweet, tobacco-like fragrance note."):
   ("reject", "5,7,7-trimethyl-2,3,4,6,7,8-hexahydroquinoxaline", "This material", set(),
    "The antecedent names TWO compounds (a garbled cyclopentapyrazine, then the hexahydroquinoxaline). The nearer one is probably meant, but the narrow rule needs exactly one."),
 ("US2849491A", "It had a pleasant fruity odor reminiscent of fresh apple juice."):
   ("approve", "6,8- dirnethyl-5-nonen-2-one", "It", {"pleasant", "fresh"},
    "Antecedent: 'The product X distilled at…'. 'fresh' qualifies the juice, not the odour — dropped. 'dirnethyl' is OCR for dimethyl — normalise at linkage."),
 ("US3452105A", "The compound, boiling point at 94 C./0.02 mm; n =1.4984, has an intensive"):
   ("approve", "3-hydroxy-6-cyclohexylidene-1-hexene", "The compound", set(),
    "Antecedent: 'the thus-prepared, crude X was purified by distillation'. The boiling point pins it to that compound."),
 ("US3549714A", "The compound, boiling point at 94 C./0.02 mm.; n =1.4984, has an intensive"):
   ("approve", "3-hydroxy-6-cyclohexylidene-l-hexene", "The compound", set(),
    "Same compound as US3452105A, different patent (attestation). 'l-hexene' is OCR for 1-."),
 ("US3709929A", "It has a very pleasant, pure fruit-like note reminiscent in particular of plum"):
   ("approve", "4-methyl-2-pentanol crotonate", "It", {"pleasant"},
    "Antecedent: 'X does not have any of these disadvantages.' 'plum and apple preserves' are foods named as smells."),
 ("US4190561A", "The product has a fruity odour particularly reminiscent of apples."):
   ("approve", "1,5,5-trimethyl-4-(1-isovaleroyloxyethyl)-cyclohex-1-ene", "The product", set(),
    "Antecedent: '50.6 g of pure X are obtained'."),
}


def main(argv):
    surf = st.load_tags()
    forms = sorted(surf, key=len, reverse=True)
    rx = re.compile(r"\b(" + "|".join(map(re.escape, forms)) + r")\b", re.I)
    pairs = [json.loads(l) for l in PAIRS.read_text(encoding="utf-8").splitlines() if l.strip()]
    kept = {}
    if OUT.exists():
        for l in OUT.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                kept[(r["source_id"], r["sentence"])] = (r.get("review_decision"), r.get("review_note"))
    rows, bad, found = [], [], set()
    for p in pairs:
        for (sid, start), (prop, mol, ana, excl, why) in P.items():
            if p["source_id"] != sid or not p["sentence"].startswith(start):
                continue
            found.add((sid, start))
            prev, s = p["prev"], p["sentence"]
            descs, seen = [], set()
            for m in rx.finditer(s):
                w = m.group(0)
                if w.lower() in excl or w.lower() in seen:
                    continue
                seen.add(w.lower()); descs.append(w)
            if mol not in prev: bad.append((sid, "molecule not in antecedent", mol))
            if ana not in s: bad.append((sid, "anaphor not in sentence", ana))
            for d in descs:
                if d not in s: bad.append((sid, "descriptor not in sentence", d))
            dec, note = kept.get((sid, s), (None, None))
            rows.append({"source_id": sid, "scope": "passage", "window": 1, "link": "human-resolved",
                         "antecedent": prev, "sentence": s, "molecule": mol, "anaphor": ana,
                         "descriptors": descs, "proposed_decision": prop, "proposed_why": why,
                         "proposed_by": "claude", "review_decision": dec, "review_note": note})
    missing = set(P) - found
    for m in missing: bad.append((m[0], "pair not found in pairs.jsonl", m[1][:50]))
    for r in rows:
        tags = sorted({surf[d.lower()] for d in r["descriptors"] if d.lower() in surf})
        print(f"{r['proposed_decision']:<8}{r['source_id']:<13}{r['molecule'][:48]:<50}{tags}  decided={r['review_decision']}")
    if bad:
        print("REFUSING:"); [print("  ", b) for b in bad]; return 1
    print(f"\n{len(rows)} passage rows, every span verbatim in its own sentence")
    if "--write" in argv:
        tmp = OUT.with_suffix(".jsonl.tmp")
        tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        os.replace(tmp, OUT)
        print(f"written -> {OUT.relative_to(ROOT)}")
    else:
        print("dry run — nothing written (--write to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
