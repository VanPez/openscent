#!/usr/bin/env python3
"""
build_csv.py — the PubChem half as ONE all-numeric CSV, for GL1F.

    python3 pipeline/build_csv.py
    -> reports/openscent-pubchem.csv  +  reports/openscent-pubchem-columns.md

Needs rdkit (pip install rdkit) and corpus/raw-pubchem/smiles.json from
pubchem_smiles.py. Reads only; writes the two files above.

WHAT M ASKED FOR (2026-09-06/07, GenesisL1 TG)
----------------------------------------------
"Simplify it to 1 csv file with 20-30 columns and 1000-1500 rows. Make all features
numeric." Then, once told the patent half needs OPSIN first: "Yes send 650 with whatever
numeric columns you got." And on the column budget: "You actually choose task in ui and so
labels/classes there... One may be label for one task and feature for another" — which is
why this does not agonise over which columns are labels. Everything is numeric; GL1F
decides. Also: "Consider numeric codification of tags", hence primary_tag_id.

FEATURES ARE COMPUTED HERE, NOT FETCHED
---------------------------------------
Only the STRUCTURE comes from PubChem. Every descriptor below is RDKit over that
structure, offline and deterministic. Asking PubChem for logP or TPSA would tie the
feature table to a remote service's descriptor version — unreproducible, and the same
objection this project makes to hand-supplied vocabulary.

WHY THESE 22 DESCRIPTORS AND NOT 200
------------------------------------
RDKit offers 200+, and Morgan fingerprints offer thousands. With 648 rows that is how you
overfit: feature importances computed on the same data you then select with are biased,
and at ~30 positives for the smaller tags the ranking is noise. M's own first instinct was
"20-30 features at best", which is the statistically sane number here. These are the
interpretable bulk/shape/polarity descriptors that structure-odour work actually uses.

THE LABELS ARE THIN AND THE CSV SHOULD NOT HIDE IT
--------------------------------------------------
54 tags appear across these molecules; only 15 reach 10 molecules, and the mean is 1.41
tags per molecule. So this carries a 0/1 column for each of the 15 and nothing for the
tail — a column with 4 positives in 648 rows teaches a tree nothing and invites a
spurious split.

These are HSDB safety records, not a perfume catalogue: `chlorine` (18 molecules) is a
real tag here, and industrial solvents sit beside the aroma chemicals. A model will find
`n_halogen` predicts `chlorine` almost perfectly. That is the data being honest, not the
model being clever.

NO GROUP COLUMN, DELIBERATELY
-----------------------------
The patent rows cluster hard by source document, and a random split there leaks — 36
cyclohexenones from one patent are near-identical structures. THESE rows do not: one row
per CID, drawn from independent HSDB records, no document clustering to leak. So there is
nothing to group on and no group_id is emitted. When the patent half joins, it will need
one.
"""
from __future__ import annotations
import collections, csv, json, pathlib, sys

from rdkit import Chem, RDLogger
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

RDLogger.DisableLog("rdApp.*")

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROWS = ROOT / "corpus" / "rows" / "pubchem-rows.jsonl"
CACHE = ROOT / "corpus" / "raw-pubchem" / "smiles.json"
OUT = ROOT / "reports" / "openscent-pubchem.csv"
DOC = ROOT / "reports" / "openscent-pubchem-columns.md"
MIN_MOLECULES_PER_TAG = 10


def descriptors(m) -> dict:
    """22 interpretable numbers. Order is fixed so the CSV is diffable across runs."""
    atoms = [a.GetSymbol() for a in m.GetAtoms()]
    return {
        "mw": round(Descriptors.MolWt(m), 3),
        "heavy_atoms": m.GetNumHeavyAtoms(),
        "n_carbon": atoms.count("C"),
        "n_oxygen": atoms.count("O"),
        "n_nitrogen": atoms.count("N"),
        "n_sulfur": atoms.count("S"),
        "n_halogen": sum(atoms.count(x) for x in ("F", "Cl", "Br", "I")),
        "heteroatoms": Lipinski.NumHeteroatoms(m),
        "logp": round(Crippen.MolLogP(m), 4),
        "molar_refractivity": round(Crippen.MolMR(m), 4),
        "tpsa": round(rdMolDescriptors.CalcTPSA(m), 3),
        "labute_asa": round(rdMolDescriptors.CalcLabuteASA(m), 3),
        "h_donors": Lipinski.NumHDonors(m),
        "h_acceptors": Lipinski.NumHAcceptors(m),
        "rot_bonds": Lipinski.NumRotatableBonds(m),
        "rings": rdMolDescriptors.CalcNumRings(m),
        "aromatic_rings": rdMolDescriptors.CalcNumAromaticRings(m),
        "aliphatic_rings": rdMolDescriptors.CalcNumAliphaticRings(m),
        "saturated_rings": rdMolDescriptors.CalcNumSaturatedRings(m),
        "fraction_csp3": round(rdMolDescriptors.CalcFractionCSP3(m), 4),
        "valence_electrons": Descriptors.NumValenceElectrons(m),
        "bertz_complexity": round(Descriptors.BertzCT(m), 3),
    }


def main() -> int:
    cache = json.loads(CACHE.read_text())
    by_cid: dict[int, set] = collections.defaultdict(set)
    names: dict[int, str] = {}
    for line in ROWS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith('{"_comment"'):
            continue
        r = json.loads(line)
        if r.get("excluded"):
            continue
        cid, tag = r.get("molecule_cid"), (r.get("tag") or "").strip()
        if cid and tag:
            by_cid[cid].add(tag)
            names.setdefault(cid, r.get("molecule_name", ""))

    tag_counts = collections.Counter(t for s in by_cid.values() for t in s)
    kept = sorted(t for t, n in tag_counts.items() if n >= MIN_MOLECULES_PER_TAG)
    # rarest first, so primary_tag_id picks the MOST SPECIFIC tag a molecule carries.
    # Most-common-wins would label two thirds of the file `pungent` and teach nothing.
    specificity = sorted(kept, key=lambda t: (tag_counts[t], t))
    tag_id = {t: i + 1 for i, t in enumerate(specificity)}      # 0 = none of the kept tags

    rows, skipped = [], []
    for cid in sorted(by_cid):
        rec = cache.get(str(cid)) or {}
        smi = rec.get("smiles")
        m = Chem.MolFromSmiles(smi) if smi else None
        if m is None:
            skipped.append((cid, names.get(cid, ""), rec.get("formula", "")))
            continue
        tags = by_cid[cid]
        present = [t for t in specificity if t in tags]
        row = {"cid": cid}
        row.update(descriptors(m))
        for t in kept:
            row[f"tag_{t}"] = 1 if t in tags else 0
        row["n_tags"] = len(tags)
        row["primary_tag_id"] = tag_id[present[0]] if present else 0
        rows.append(row)

    cols = list(rows[0].keys())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # --- verification, because a CSV that is silently wrong is the whole problem ------
    bad = [(r["cid"], k) for r in rows for k, v in r.items()
           if v is None or isinstance(v, str)]
    assert not bad, f"non-numeric cells: {bad[:5]}"
    assert len({r["cid"] for r in rows}) == len(rows), "duplicate cid"

    print(f"rows    {len(rows)}   ({len(skipped)} skipped, structure unparseable)")
    for cid, nm, f in skipped:
        print(f"   skip {cid} {nm} ({f}) — hypervalent halogen, RDKit rejects the valence")
    print(f"columns {len(cols)} = 1 id + 22 descriptors + {len(kept)} tags + 2 summary")
    print(f"labels  {len(kept)} tags with >={MIN_MOLECULES_PER_TAG} molecules "
          f"(of {len(tag_counts)} present)")
    print(f"-> {OUT}")

    lines = ["# openscent-pubchem.csv — columns", "",
             f"{len(rows)} rows, one per PubChem CID. All values numeric.", "",
             "`cid` is an identifier, NOT a feature — exclude it in the GL1F dataset tab.",
             "", "## descriptors (RDKit, computed from the structure)", ""]
    for k in list(rows[0]):
        if k.startswith("tag_") or k in ("cid", "n_tags", "primary_tag_id"):
            continue
        lines.append(f"- `{k}`")
    lines += ["", "## labels", "",
              f"`tag_<name>` — 1 if the molecule carries that odour tag. {len(kept)} tags "
              f"with >= {MIN_MOLECULES_PER_TAG} molecules:", ""]
    for t in sorted(kept, key=lambda x: -tag_counts[x]):
        lines.append(f"- `tag_{t}` — {tag_counts[t]} molecules")
    lines += ["", "`n_tags` — how many tags this molecule carries (mean 1.41, max 9).", "",
              "`primary_tag_id` — single-class codification for multiclass tasks. The "
              "MOST SPECIFIC (rarest) tag the molecule carries; 0 if it carries none of "
              "the kept tags:", ""]
    for t in specificity:
        lines.append(f"- {tag_id[t]} = {t} ({tag_counts[t]} molecules)")
    lines += ["", "## provenance", "",
              "Odour tags: HSDB records via PubChem, public domain. Structures: PubChem "
              "PUG REST. Descriptors: RDKit, offline. Nothing here is generated — every "
              "tag traces to a quoted HSDB span in corpus/rows/pubchem-rows.jsonl.", "",
              "These are SAFETY records, not a perfume catalogue: `tag_chlorine` is real, "
              "and `n_halogen` will predict it almost perfectly.", ""]
    DOC.write_text("\n".join(lines), encoding="utf-8")
    print(f"-> {DOC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
