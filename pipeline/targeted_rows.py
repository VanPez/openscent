#!/usr/bin/env python3
"""targeted_rows.py — sentence-scope rows found by LOOKING FOR a compound, not by the extractor.

WHAT THEY ARE
-------------
Ordinary sentence-scope rows: molecule and descriptors verbatim in ONE sentence of a US
patent, same review rules, same guarantee. What differs is how the sentence was found. The
origin probe (gaps.py --probe, 2026-09-26) read the earliest US patents for each commercial
compound missing from the corpus. A few odour sentences about those compounds had been
dropped by harvest.decide() (a junk prefix from the scan, no attribution verb it knows), and
one document (US7601682B2) was fetched outside the class walk, for the probe.

WHY A SEPARATE FILE
-------------------
review.jsonl is the extractor's queue: merge_review.py rebuilds it from candidates.json and
reports every decided row the extractor does not produce as an ORPHAN. Rows the extractor never
produced would trip that guard forever. So they live here, exactly as passage rows do, and
status.py counts them on their own line.

PROPOSE-ONLY. `review_decision` is Ivan's; status.py counts a row only once it is "approve".
Re-running keeps decisions already recorded (matched on source_id + sentence + molecule).

INPUT   corpus/gaps/origin-sentences.jsonl   (gaps.py --probe; the sentence text as harvest.norm made it)
OUTPUT  corpus/rows/targeted-rows.jsonl
USAGE   python3 pipeline/targeted_rows.py            # dry run
        python3 pipeline/targeted_rows.py --write
"""
from __future__ import annotations
import importlib.util, json, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "corpus" / "gaps" / "origin-sentences.jsonl"
OUT = ROOT / "corpus" / "rows" / "targeted-rows.jsonl"
spec = importlib.util.spec_from_file_location("st", ROOT / "pipeline" / "status.py")
st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)

# (source_id, start of sentence) -> list of (proposal, molecule, [descriptors], in_class_walk, why)
T = {
 ("US2875131A", "167-94) This invention relates to a novel aromatic aldehyde"): [
   ("approve", "cyclamen aldehyde", ["lily"], True,
    "Named, direct: 'Para-isopropyl a-methyl hydrocinnamic aldehyde, commonly called cyclamen aldehyde, has attained "
    "widespread use in perfumery for its lily or linden-blossom odor'. One compound, two names — the common name is the "
    "span (one row, not two). 'linden-blossom' has no tag. The scan's '167-94)' prefix is why the extractor dropped it."),
 ],
 ("US4052341A", "The characteristic of the 3-methyl-5-(2,2,3-trimethylcyclopent-3-en-1-yl)pentan-2-ol (6)"): [
   ("approve", "3-methyl-5-(2,2,3-trimethylcyclopent-3-en-1-yl)pentan-2-ol", ["sandalwood"], True,
    "Named, direct: '… is its intense sandalwood odor'. Sandalore (Givaudan). No attribution verb the extractor knows. "
    "Same patent's 'reminiscent of sandalwood oil' sentence is a same-document repeat — not staged."),
 ],
 ("US4482762A", "The 3,6-dimethyl-6-nonen-5-ol [Ia], for example"): [
   ("approve", "4-methyl-3-decen-5-ol", ["fruity", "fresh", "green", "violet"], True,
    "Undecavertol (Givaudan). The sentence describes TWO compounds; this row is [Ib]'s clause only: 'has above all fruity "
    "and very natural odour notes … pleasantly fresh-green and at the same time reminiscent of violets'. [Ia]'s flowery/"
    "green/warm/powdery are not carried. 'violet' is the verbatim stem of 'violets'."),
 ],
 ("US7601682B2", "Adjusting the weight ratios to the preferred values"): [
   ("approve", "Ambrocenide", ["woody"], False,
    "BORDERLINE, your call: '… the woody and/or ambergris note of the Ambrocenide®' asserts the note as Ambrocenide's, "
    "but without an attribution verb. 'ambergris' is HELD in the ontology. Document fetched outside the class walk "
    "(origin probe pilot, Symrise 2009)."),
   ("approve", "limonenal", ["fresh", "citrus"], False,
    "Same sentence, second compound: '… the fresh and/or citrus notes of the limonenal'. Same borderline as the row above."),
 ],
}


def main(argv):
    surf = st.load_tags()
    sents = {}
    for l in SRC.read_text(encoding="utf-8").splitlines():
        r = json.loads(l)
        if not r.get("missing"):
            sents.setdefault(r["doc"], set()).add(r["sentence"])
    kept = {}
    if OUT.exists():
        for r in st.jsonl(OUT):
            kept[(r["source_id"], r["sentence"], r["molecule"])] = (r.get("review_decision"), r.get("review_note"))
    rows, bad = [], []
    for (sid, start), items in T.items():
        hit = [s for s in sents.get(sid, ()) if s.startswith(start)]
        if len(hit) != 1:
            bad.append((sid, f"{len(hit)} sentences start with {start[:40]!r}")); continue
        s = hit[0]
        for prop, mol, descs, walk, why in items:
            if mol not in s:
                bad.append((sid, f"molecule not verbatim: {mol}"))
            for d in descs:
                if d not in s:
                    bad.append((sid, f"descriptor not verbatim: {d}"))
                if d.lower() not in surf:
                    bad.append((sid, f"descriptor has no tag: {d}"))
            dec, note = kept.get((sid, s, mol), (None, None))
            rows.append({"source_id": sid, "scope": "sentence", "found_by": "gaps.py origin probe 2026-09-26",
                         "in_class_walk": walk, "sentence": s, "molecule": mol, "descriptors": descs,
                         "tags": sorted({surf[d.lower()] for d in descs}),
                         "proposed_decision": prop, "proposed_why": why, "proposed_by": "claude",
                         "review_decision": dec, "review_note": note})
    for r in rows:
        print(f"{r['proposed_decision']:<8}{r['source_id']:<13}{r['molecule'][:50]:<52}{r['tags']}  decided={r['review_decision']}")
    if bad:
        print("REFUSING:"); [print("  ", b) for b in bad]; return 1
    print(f"\n{len(rows)} targeted rows, every span verbatim in its sentence")
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
