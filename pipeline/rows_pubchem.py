#!/usr/bin/env python3
"""
OpenScent — turn PubChem candidates into corpus ROWS.

    python3 rows_pubchem.py

    in   corpus/extracted/pubchem-candidates.json   (2,082 records, CID already resolved)
         ontology/odor_terms.tsv                    (100 surface forms -> 67 tags)
    out  corpus/rows/pubchem-rows.jsonl             (one row per molecule+tag assertion)

WHY THIS SOURCE FIRST
---------------------
Linkage is free: PubChem returns the CID with the record, so there is no name-resolution
step and no chance of binding an accurate description to the wrong structure — the failure
mode flagged on 2026-07-31 as the one that produces a valid-looking bad row.

WHAT THIS SOURCE IS, STATED HONESTLY
------------------------------------
2,080 of the 2,082 records are HSDB. This is ONE database with free linkage, not a diverse
second source, and the paper should say so. Its register is a safety datasheet, not
perfumery: `pungent` (209 hits), `aromatic` (146), `acid`, `chlorine`. Thirteen of the 67
tags never occur here at all — `patchouli`, `oriental`, `aldehydic`, `leather`, `tobacco`,
`marine`. It covers molecules the patent corpus never discusses, which is exactly why it is
worth having, but it is complementary evidence rather than corroboration.

EXTRACT, NEVER GENERATE
-----------------------
A tag is emitted only when one of its surface forms occurs VERBATIM in the record's text.
The matched span, its offset, and the full quote are all carried on the row, so any reader
can check the assertion against the source. The span->tag step is the human-written
odor_terms.tsv and nothing else. Asserted, not intended: every emitted span is re-checked
against the stored quote before the row is written.

NEGATION
--------
26 records carry a negation cue ("not unpleasant", "no residual odor", "almost floral").
These are FLAGGED, not dropped, and not silently trusted: `needs_review` is set and the row
must be looked at before it enters the published corpus. Most are hedonic ("not unpleasant")
and would not produce a tag anyway, but "practically odorless" attached to a tag is a
positive assertion of something false, which is the worst kind of row.
"""
from __future__ import annotations
import json, os, pathlib, re, collections

_here = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(os.environ.get("OPENSCENT_ROOT",
           _here.parent if _here.name == "pipeline" else _here / "openscent"))

NEG = re.compile(r"\b(not|no|without|free of|odou?rless|nearly|almost|practically|devoid|"
                 r"faint|trace|slight)\b", re.I)


def load_tags() -> dict[str, str]:
    out = {}
    for line in (ROOT / "ontology" / "odor_terms.tsv").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        p = line.split("\t")
        if len(p) >= 2 and p[1].strip():
            f, t = p[0].strip().lower(), p[1].strip()
            if f in out and out[f] != t:
                raise SystemExit(f"odor_terms.tsv: '{f}' maps to both {out[f]} and {t}")
            out[f] = t
    return out


def main() -> int:
    tags = load_tags()
    src = json.loads((ROOT / "corpus" / "extracted" / "pubchem-candidates.json")
                     .read_text(encoding="utf-8"))
    rx = re.compile(r"\b(" + "|".join(re.escape(f) for f in
                    sorted(tags, key=len, reverse=True)) + r")\b", re.I)

    rows, per_tag, mols, flagged, skipped = [], collections.Counter(), set(), 0, 0
    for r in src:
        text = r.get("text") or ""
        if r.get("cid") is None or r.get("cid_ambiguous"):
            skipped += 1
            continue
        hits = list(rx.finditer(text))
        if not hits:
            continue
        neg = bool(NEG.search(text))
        seen = {}
        for m in hits:
            tag = tags[m.group(1).lower()]
            seen.setdefault(tag, m)          # first occurrence carries the offset
        for tag, m in seen.items():
            span = m.group(1)
            # EXTRACT, NEVER GENERATE — re-check the span against the stored quote.
            assert text[m.start():m.end()] == span, f"span not verbatim: {span!r}"
            rows.append({
                "molecule_cid": r["cid"],
                "molecule_name": r.get("name"),
                "tag": tag,
                "span": span,
                "span_offset": m.start(),
                "quote": text,
                "source": r.get("source_name"),
                "source_url": r.get("source_url"),
                "license_url": r.get("license_url"),
                "reference_may_be_copyrighted": r.get("reference_may_be_copyrighted", False),
                "expression_risk": r.get("expression_risk"),
                "fema_listed": r.get("fema_listed", False),
                "needs_review": neg,
                "review_reason": "negation cue in quote" if neg else None,
                "extractor": "rows_pubchem/v1",
            })
            per_tag[tag] += 1
            mols.add(r["cid"])
        flagged += neg

    dest = ROOT / "corpus" / "rows"
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / "pubchem-rows.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"records in       {len(src)}")
    print(f"skipped (no/ambiguous CID) {skipped}")
    print(f"ROWS OUT         {len(rows)}")
    print(f"distinct molecules {len(mols)}")
    print(f"flagged for review {flagged}   (negation cue)")
    print(f"tags used        {len(per_tag)}/67")
    print(f"\ntags reaching Mike's 30-molecule bar: "
          f"{sum(1 for _, n in per_tag.items() if n >= 30)}")
    print(f"\n{'tag':<14}{'rows':>6}")
    for t, n in per_tag.most_common(25):
        print(f"{t:<14}{n:>6}{'   <- >=30' if n >= 30 else ''}")
    print(f"\nnever attested here: "
          f"{', '.join(sorted(set(tags.values()) - set(per_tag)))}")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
