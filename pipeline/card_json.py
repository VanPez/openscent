#!/usr/bin/env python3
"""card_json.py — the molecule card (v1) of one token as flat JSON: one key, one value, no hierarchy (Mike, 2026-10-29).

    python3 pipeline/card_json.py Ethylvanillin                      # print the card of a molecule (name or InChIKey)
    python3 pipeline/card_json.py Ethylvanillin --out reports/x.json
    python3 pipeline/card_json.py --all --out /tmp/cards.jsonl        # every token, one card per line

Reads release/v1.0 (molecules.tsv, evidence.tsv) and the PubChem files fetched on Hetzner (corpus/3d/conformers.json,
corpus/props/pubchem-props.json). The fields are those of reports/molecule-card-v1.md: B1, B4 (each quote and its source,
numbered), B5, B6, B7 and B8 (atoms and bonds as two strings). The explanations, and the rest of each evidence row, stay in
that file and in the release. Offline; no network."""
from __future__ import annotations
import argparse, csv, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REL = ROOT / "release" / "v1.0"

# atomic number -> symbol, for every element in the PubChem conformers of v1.0
SYM = {1: "H", 6: "C", 7: "N", 8: "O", 9: "F", 14: "Si", 15: "P", 16: "S", 17: "Cl", 35: "Br", 53: "I"}


def tsv(p):
    return list(csv.DictReader(p.open(encoding="utf-8", newline=""), delimiter="\t"))


def load():
    mols = [r for r in tsv(REL / "molecules.tsv") if r["mintable"] == "yes"]
    ev = {}
    for e in tsv(REL / "evidence.tsv"):
        ev.setdefault(e["molecule_id"], []).append(e)
    c3 = json.loads((ROOT / "corpus" / "3d" / "conformers.json").read_text(encoding="utf-8"))
    props = json.loads((ROOT / "corpus" / "props" / "pubchem-props.json").read_text(encoding="utf-8"))
    return mols, ev, c3, props


def card(r, es, c3, props):
    v3 = c3.get(r["inchikey"]) or {}
    cid = int(r["pubchem_cids"].split(";")[0]) if r["pubchem_cids"] else v3.get("cid")
    c = {"Structure name": r["label"],
         "SMILES": r["smiles"],
         "Scent": ", ".join(t for t in r["tags"].split(";") if t),
         "XLogP3": (props.get(str(cid)) or {}).get("xlogp") if cid else None,
         "PubChem CID": cid}
    texts = {}                                   # one quote can back several tags: it is listed once
    for e in es:
        texts.setdefault((e["quote"], e["source_id"]), e["source_url"] or e["source_id"])
    for i, ((q, _), src) in enumerate(texts.items(), 1):
        c[f"Text {i}"], c[f"Source {i}"] = q, src
    x = v3.get("c3d")                            # atoms: symbol x y z (Å); bonds: atom-atom order, atoms counted from 1
    c["3D atoms"] = "; ".join(f"{SYM[e]} {p[0]} {p[1]} {p[2]}" for e, p in zip(x["el"], x["xyz"])) if x else None
    c["3D bonds"] = "; ".join(f"{a + 1}-{b + 1} {o}" for a, b, o in x["b"]) if x else None
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("molecule", nargs="?", help="label or InChIKey")
    ap.add_argument("--all", action="store_true", help="every token, as JSON lines")
    ap.add_argument("--out")
    a = ap.parse_args()
    mols, ev, c3, props = load()
    if a.all:
        text = "".join(json.dumps(card(r, ev.get(r["molecule_id"], []), c3, props), ensure_ascii=False,
                                  separators=(",", ":")) + "\n" for r in mols)
    else:
        hit = [r for r in mols if a.molecule in (r["label"], r["inchikey"])]
        if len(hit) != 1:
            sys.exit(f"{len(hit)} tokens match {a.molecule!r}")
        text = json.dumps(card(hit[0], ev.get(hit[0]["molecule_id"], []), c3, props), ensure_ascii=False, indent=2) + "\n"
    if a.out:
        pathlib.Path(a.out).write_text(text, encoding="utf-8")
        print(f"-> {a.out} ({len(text.encode('utf-8')):,} bytes)")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
