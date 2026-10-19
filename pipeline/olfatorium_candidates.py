#!/usr/bin/env python3
"""Candidate descriptor words from Olfatorium's own descriptions (stdlib only). PROPOSALS ONLY.

Input  : corpus/olfatorium/descriptions.tsv   (pipeline/olfatorium_fetch.py)
         corpus/olfatorium/olfatorium-gaps.tsv (the 45 single compounds with no descriptor in the corpus)
Output : corpus/olfatorium/candidates.tsv, candidates-review.md   (local only: the folder is gitignored)

Nothing here enters the corpus. Ivan reviews every line first (REVIEW-RULES.md applies unchanged).

How it stays "extract, never generate":
  * every SPAN is a verbatim substring of one SENTENCE of the shop's text -- checked below, the
    script stops if one is not;
  * the Spanish -> tag step is the only judgement, and it lands in the existing 67-tag vocabulary of
    ontology/odor_terms.tsv (same convention as the English forms: orange blossom -> floral,
    muguet -> lily, grassy -> green, refreshing -> fresh, dusty -> powdery ...);
  * confidence is "high" (plain word -> tag), "medium" (a judgement about the word or its sense) or
    "doubt" (the REVIEW-RULES say reject when in doubt: comparison, dose-dependent effect, typo, family
    name). "doubt" rows are listed for Ivan's decision and are NOT proposed for the layer.

What is deliberately NOT taken (REVIEW-RULES): blend effects and uses ("combina bien con notas
florales", "realza", "se emplea en"), intensity and judgement words (potente, duradera, elegante),
substances named as comparisons (nitroalmizcle, cetona de almizcle, cetonas de la rosa), negations and
comparatives ("no huele a whisky", "menos afrutada que"), and every English passage (supplier text).
Grant (Olfatorium owner, 2026-10-13): CC BY 4.0, only descriptions Olfatorium wrote themselves.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "corpus" / "olfatorium"
LAYER = ROOT / "licensed" / "olfatorium-rows.jsonl"   # OUTSIDE corpus/: CC BY 4.0, not part of the CC0 corpus or v1.0
DECISION = "Ivan 2026-10-19: all proposed lines approved, 'doubt' lines rejected"

# The public row carries the WORD, the tag and where to find it -- NOT the shop's sentence. The grant
# (owner of Olfatorium, 2026-10-13) covers "las palabras descriptivas breves", credited with a link; a
# whole sentence of a product description is more than that. The sentence stays in the local-only
# candidates.tsv; sentence_sha256 + offsets let anyone with the page verify the span.
LICENCE_BASIS = ("written permission of the owner of Olfatorium, 2026-10-13: short descriptor words from descriptions "
                 "Olfatorium wrote themselves, under CC BY 4.0, credited with a link, in a separate labelled layer "
                 "(also on-chain)")

# (gap-row name prefix, locator phrase, [(span, tag, confidence, note), ...]) lives in the LOCAL-ONLY file
# corpus/olfatorium/proposals.py: the locator phrases are pieces of the shop's sentences and the grant covers
# descriptor words, not sentences, so they are not kept in the repo. The public rows carry the words, the tags,
# the offsets and a sentence hash instead.
def _load_proposals():
    f = OUT / "proposals.py"
    if not f.exists():
        sys.exit(f"{f} is local-only data and is not in the repo; without it only layer rows already written can be used")
    import importlib.util
    spec = importlib.util.spec_from_file_location("olfatorium_proposals", f)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.PROPOSALS


PROPOSALS = _load_proposals()

# rows with nothing taken, and why
EXCLUDED = {
    "Cashmeran": "Spanish text is a translation of the English supplier text on the same page, plus a quoted marketing sentence",
    "Cassifix": "English supplier text (IFF R&D story)",
    "Evernyl": "the Spanish word list is a translation of the English line on the same page (supplier text)",
    "Helional": "the Spanish line is a translation of the English line on the same page (supplier text)",
    "Sagecete": "English supplier text only",
    "Tuberolide": "English supplier text only",
    "Undecavertol": "the Spanish is a translation of the supplier's English text and its development story",
    "Timbersilk": "same CAS and identical text as Iso E Super: one molecule, handled once",
    "Woodarom": "only blend and usage statements (combina bien con ...): nothing describes its own smell",
}


def nfc(s):
    return unicodedata.normalize("NFC", s)


def sentences(text):
    """segments (split on the newline marker), then sentences inside each segment."""
    out = []
    for seg in text.split(" ⏎ "):
        for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ«¿¡])", seg):
            s = s.strip()
            if s:
                out.append(s)
    return out


def cas_list(s):
    return [re.sub(r"\(.*?\)", "", x).strip() for x in re.split(r"[;,/]", s) if x.strip()]


def layer_row(r):
    """one row of the licensed layer: word + tag + locator, never the sentence."""
    p, sent, span = r["prod"], r["sentence"], nfc(r["span"])
    field = next(f for f in ("description", "short_description") if sent in nfc(p[f]))
    sent_off = nfc(p[field]).index(sent)
    approved = r["confidence"] != "doubt"
    return {
        "layer": "licensed",
        "source": "Olfatorium (olfatorium.com)",
        "source_url": r["page"],
        "attribution": "Olfatorium, https://olfatorium.com/",
        "licence": "CC BY 4.0",
        "licence_basis": LICENCE_BASIS,
        "molecule_cid": int(r["cid"]),
        "molecule_name": r["molecule"],
        "cas": r["cas"],
        "tag": r["tag"],
        "span": span,
        "language": "es",
        "field": field,
        "sentence_offset": sent_off,
        "span_offset": sent.index(span),
        "sentence_sha256": hashlib.sha256(sent.encode("utf-8")).hexdigest(),
        "text_basis": "plain text of the Store API field as built by pipeline/olfatorium_fetch.py, newlines shown as ' ⏎ '",
        "mapping_confidence": r["confidence"],
        "mapping_note": r["note"],
        "fetched": "2026-10-13",
        "extractor": "olfatorium_candidates/v1",
        "review_decision": "approve" if approved else "reject",
        "review_note": DECISION,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-layer", action="store_true", help="write licensed/olfatorium-rows.jsonl")
    args = ap.parse_args()
    prods = list(csv.DictReader(open(OUT / "descriptions.tsv", encoding="utf-8"), delimiter="\t"))
    gaps = [r for r in csv.DictReader(open(OUT / "olfatorium-gaps.tsv", encoding="utf-8"), delimiter="\t")
            if r["status"] == "gap"]
    bycas = defaultdict(list)
    for p in prods:
        for c in cas_list(p["cas"]):
            bycas[c].append(p)
        if "14901-07-06" in p["cas"]:
            bycas["14901-07-6"].append(p)

    def gap_row(prefix):
        m = [g for g in gaps if g["name"].startswith(prefix)]
        if len(m) != 1:
            sys.exit(f"key {prefix!r} matches {len(m)} gap rows")
        return m[0]

    rows, problems = [], []
    for prefix, snippet, picks in PROPOSALS:
        g = gap_row(prefix)
        p = bycas[g["cas"]][0]
        text = nfc(p["short_description"] + " ⏎ " + p["description"])
        hit = [s for s in sentences(text) if nfc(snippet) in s]
        if not hit:
            problems.append(f"{prefix}: snippet not found: {snippet!r}")
            continue
        sent = hit[0]
        for span, tag, conf, note in picks:
            if nfc(span) not in sent:
                problems.append(f"{prefix}: span {span!r} not in sentence {sent[:70]!r}")
                continue
            rows.append(dict(molecule=g["name"], cas=g["cas"], cid=g["cid"], page=p["permalink"], sentence=sent,
                             span=span, tag=tag, confidence=conf, note=note, prod=p))
    for k in EXCLUDED:
        gap_row(k)  # fails loudly on a bad key
    if problems:
        sys.exit("VERBATIM CHECK FAILED:\n  " + "\n  ".join(problems))

    cols = ["molecule", "cas", "tag", "confidence", "span", "sentence", "note", "page"]
    with open(OUT / "candidates.tsv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, cols, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    by_mol = defaultdict(list)
    for r in rows:
        by_mol[r["molecule"]].append(r)
    with open(OUT / "candidates-review.md", "w", encoding="utf-8") as fh:
        fh.write("# Olfatorium: candidate descriptor words for Ivan's review (LOCAL ONLY)\n\n")
        fh.write("Every span is a verbatim substring of a Spanish sentence of the shop's own text (checked by the script). "
                 "Tags are proposals into the existing 67. 'doubt' rows are NOT proposed. Source: Olfatorium, CC BY 4.0, "
                 "descriptions Olfatorium wrote themselves; credit with a link.\n\n")
        for mol, rs in by_mol.items():
            fh.write(f"## {mol}  (CAS {rs[0]['cas']})\n{rs[0]['page']}\n")
            for r in rs:
                fh.write(f"- **{r['tag']}** [{r['confidence']}] «{r['span']}» — {r['sentence']}"
                         f"{'  — ' + r['note'] if r['note'] else ''}\n")
            fh.write("\n")
        fh.write("## Rows with nothing taken\n")
        for k, why in EXCLUDED.items():
            fh.write(f"- {k}: {why}\n")

    if args.write_layer:
        with open(LAYER, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(layer_row(r), ensure_ascii=False) + "\n")
        n_ok = sum(1 for r in rows if r["confidence"] != "doubt")
        print(f"wrote {LAYER}: {len(rows)} rows ({n_ok} approve, {len(rows) - n_ok} reject)")

    prop = [r for r in rows if r["confidence"] != "doubt"]
    pairs = {(r["molecule"], r["tag"]) for r in prop}
    print(f"candidate lines: {len(rows)} ({len(prop)} proposed, {len(rows) - len(prop)} doubt)")
    print(f"molecules with >=1 proposed tag: {len({m for m, _ in pairs})} | distinct (molecule, tag) pairs: {len(pairs)}")
    near = ["tobacco", "sandalwood", "apple", "anisic", "grapefruit"]
    for t in near:
        proposed = sorted({m for m, tg in pairs if tg == t})
        doubtful = sorted({r["molecule"] for r in rows if r["tag"] == t and r["confidence"] == "doubt"})
        print(f"  {t}: proposed {proposed}  doubt {doubtful}")
    print("tags used:", sorted({t for _, t in pairs}))


if __name__ == "__main__":
    main()
