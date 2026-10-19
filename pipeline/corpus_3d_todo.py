#!/usr/bin/env python3
"""corpus_3d_todo.py — the work list for corpus_3d_fetch.py (which runs on Hetzner).

    python3 pipeline/corpus_3d_todo.py        # reads release/v1.0/molecules.tsv -> corpus/3d/todo.json

One entry per molecule that has a structure (mintable = yes): its full InChIKey and, when the release
carries one, its PubChem CID. Offline; no network."""
import csv, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
rows = list(csv.DictReader((ROOT / "release" / "v1.0" / "molecules.tsv").open(encoding="utf-8", newline=""), delimiter="\t"))
todo = [{"ik": r["inchikey"], "cid": int(r["pubchem_cids"].split(";")[0]) if r["pubchem_cids"] else None}
        for r in rows if r["mintable"] == "yes" and r["inchikey"]]
out = ROOT / "corpus" / "3d" / "todo.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(todo, separators=(",", ":")), encoding="utf-8")
print(f"{len(todo)} molecules ({sum(1 for t in todo if t['cid'])} with a CID, {sum(1 for t in todo if not t['cid'])} without) -> {out.relative_to(ROOT)}")
