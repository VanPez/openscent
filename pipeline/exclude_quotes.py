#!/usr/bin/env python3
"""exclude_quotes.py — retire approved rows whose descriptors are a COPYRIGHTED REFERENCE WORK's wording.

DECIDED: Ivan, 2026-09-26 ("yes to all").

WHY
---
The corpus is CC0 because US patent text carries no copyright. That covers the patent's own
words. It does not cover a copyrighted text the patent QUOTES. Many IFF-era patents open with
"Arctander states that X has a powerful, grassy, green pungent odor and a rather poor
tenacity" — that is Arctander's 1969 monograph text (still in copyright), relayed verbatim or
nearly so. Same for Fenaroli's Handbook and The Good Scents Company database. Publishing those
sentences under CC0 would republish someone else's descriptors — exactly what the corpus
refuses to do with shop text.

THE LINE
--------
  EXCLUDED  the sentence relays the descriptor WORDING of a named reference work: Arctander
            (Perfume and Flavor Chemicals, 1969), Fenaroli's Handbook, The Good Scents Company.
            In quotation marks or not — reference works ARE their descriptor wording.
  KEPT      a patent restating in its own words a finding from the research literature
            ("Ohloff et al. have reported that 9-nordrimanol … produces an excellent amber
            odor"; "J. Agric. Food Chem., 2009 … has a leather-like, phenolic and ink-like
            odor"). A fact reported by a paper is not the paper's expression. 37 approved rows
            of this kind were read on 2026-09-26 and kept.
Measured before deciding (status.py counting, 2026-09-26): excluding the Arctander/Fenaroli/
Good Scents rows leaves 27 of 67 tags at the bar — the same 27.

HOW IT IS APPLIED
-----------------
Nothing in review.jsonl is changed: Ivan's decisions stay his. The rows are listed in
corpus/rows/exclusions.jsonl, keyed on (source_id, whitespace-normalised sentence), and
status.excluded_keys() makes status.py (and gaps.py / hekserij_link.py) skip them.

USAGE   python3 pipeline/exclude_quotes.py          # dry run: list
        python3 pipeline/exclude_quotes.py --write
"""
from __future__ import annotations
import importlib.util, json, os, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "corpus" / "rows" / "exclusions.jsonl"
spec = importlib.util.spec_from_file_location("st", ROOT / "pipeline" / "status.py")
st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)

WORKS = [
    ("Arctander, Perfume and Flavor Chemicals (1969)", re.compile(r"arctander|perfume and flavou?r chemicals", re.I)),
    ("Fenaroli's Handbook of Flavor Ingredients", re.compile(r"fenaroli", re.I)),
    ("The Good Scents Company database", re.compile(r"good ?scents", re.I)),
]


def main(argv):
    out, seen = [], set()
    for r in st.jsonl(st.REVIEW):
        if r.get("decision") != "approve":
            continue
        s = r.get("sentence") or ""
        work = next((w for w, rx in WORKS if rx.search(s)), None)
        if not work:
            continue
        key = (r["source_id"], " ".join(s.split()))
        if key in seen:
            continue
        seen.add(key)
        out.append({"source_id": r["source_id"], "sentence": key[1], "reason": "third-party-quote",
                    "quoted_work": work, "molecules": r.get("molecules") or [],
                    "decided": "Ivan 2026-09-26"})
    for o in out:
        print(f"{o['source_id']:<17}{o['quoted_work'][:12]:<13}{', '.join(o['molecules'])[:60]}")
    print(f"\n{len(out)} sentences")
    if "--write" in argv:
        tmp = OUT.with_suffix(".jsonl.tmp")
        tmp.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out), encoding="utf-8")
        os.replace(tmp, OUT)
        print(f"written -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
