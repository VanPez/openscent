#!/usr/bin/env python3
"""card_json.py — the molecule card (v1) of one token as plain JSON: field title -> field content, nothing else.

    python3 pipeline/card_json.py Ethylvanillin                      # print the card of a molecule (name or InChIKey)
    python3 pipeline/card_json.py Ethylvanillin --out reports/x.json
    python3 pipeline/card_json.py --all --out /tmp/cards.jsonl        # every token, one card per line

Reads release/v1.0 (molecules.tsv, evidence.tsv) and the PubChem files fetched on Hetzner (corpus/3d/conformers.json,
corpus/props/pubchem-props.json). The fields are those of reports/molecule-card-v1.md, B1, B2, B4, B5, B6, B7 and B8; the
explanations stay in that file. Offline; no network."""
from __future__ import annotations
import argparse, csv, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REL = ROOT / "release" / "v1.0"


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
    texts = {}
    for e in es:
        k = (e["quote"], e["source_id"])
        t = texts.setdefault(k, {"Text": e["quote"], "Molecule": [], "Odour words": [],
                                 "Source": e["source_url"] or e["source_id"]})
        if e["molecule_span"] not in t["Molecule"]:
            t["Molecule"].append(e["molecule_span"])
        if e["descriptor_span"] not in t["Odour words"]:
            t["Odour words"].append(e["descriptor_span"])
    for t in texts.values():
        t["Molecule"] = " / ".join(t["Molecule"])
    x = v3.get("c3d")
    return {
        "Structure name": r["label"],
        "Other names": [s for s in r["name_spellings"].split(" | ") if s],
        "Structure": r["smiles"],
        "Scent": [t for t in r["tags"].split(";") if t],
        "Text description": list(texts.values()),
        "XLogP3": (props.get(str(cid)) or {}).get("xlogp") if cid else None,
        "3D conformer": {"Atoms": x["el"], "Coordinates": x["xyz"], "Bonds": x["b"]} if x else None,
        "PubChem CID": cid,
    }


def pretty(o, ind=0):
    """JSON with one field per line; a list of plain values (an atom, a bond, a list of words) stays on one line."""
    pad, sub = "  " * ind, "  " * (ind + 1)
    if isinstance(o, dict):
        return "{\n" + ",\n".join(sub + json.dumps(k, ensure_ascii=False) + ": " + pretty(v, ind + 1)
                                  for k, v in o.items()) + "\n" + pad + "}" if o else "{}"
    if isinstance(o, list) and any(isinstance(v, (dict, list)) for v in o):
        return "[\n" + ",\n".join(sub + pretty(v, ind + 1) for v in o) + "\n" + pad + "]"
    return json.dumps(o, ensure_ascii=False, separators=(", ", ": "))


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
        text = pretty(card(hit[0], ev.get(hit[0]["molecule_id"], []), c3, props)) + "\n"
    if a.out:
        pathlib.Path(a.out).write_text(text, encoding="utf-8")
        print(f"-> {a.out} ({len(text.encode('utf-8')):,} bytes)")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
