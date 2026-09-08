#!/usr/bin/env python3
"""
pubchem_smiles.py — structures for the PubChem rows. The missing half of a feature table.

    python3 pipeline/pubchem_smiles.py            # fetch, cache, report
    python3 pipeline/pubchem_smiles.py --status   # what is cached, no network

RUN FROM THE MAC. PubChem is not reachable from the Hetzner box or from Claude's sandbox;
pubchem.py has always run here and this follows it.

WHY THIS EXISTS
---------------
corpus/rows/pubchem-rows.jsonl carries molecule_cid and molecule_name and NOTHING
chemical. That is fine for counting molecules per tag — the CID is already a structure
identifier, which is why linkage was called "free" for this source — but it is not enough
to compute anything. A GBDT needs numbers, and numbers come from a structure.

M asked (2026-09-06) for "1 csv, 20-30 columns, 1000-1500 rows, all features numeric".
The labels exist. The features do not. This fetches the one thing standing between them.

WHAT IT ASKS FOR, AND WHY THAT IS ALL
-------------------------------------
CanonicalSMILES, InChIKey, MolecularFormula, MolecularWeight — from PUG REST's property
endpoint, up to 100 CIDs per request. Everything else a model might want (logP, TPSA,
ring counts, rotatable bonds) is COMPUTED FROM THE STRUCTURE by RDKit, offline and
deterministically. Asking PubChem for those instead would make the feature table depend
on a remote service's version of a descriptor, which is not reproducible and not
auditable — the same objection this project already makes to hand-supplied vocabulary.

InChIKey is fetched even though nothing uses it yet. status.py's docstring flags that the
patent/PubChem molecule join is a WEAK one on name text — "linalool" and "(+)-linalool"
stay separate — and says fixing it needs InChIKeys for both sides. This gets one side.

POLITENESS
----------
NCBI's stated limits are 5 requests/second and 400/minute. Batching 100 CIDs per request
makes 651 molecules into 7 requests, and there is still a 1-2s delay between them. That
is roughly 0.4% of the allowance.

CACHED, SO IT IS RUN ONCE
-------------------------
Results go to corpus/raw-pubchem/smiles.json, keyed by CID. A re-run fetches only CIDs
that are missing, so this is resumable and costs nothing on the second run.
"""
from __future__ import annotations
import json, pathlib, random, sys, time, importlib.util

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
ROWS = ROOT / "corpus" / "rows" / "pubchem-rows.jsonl"
CACHE = ROOT / "corpus" / "raw-pubchem" / "smiles.json"
BATCH = 100
# PROPERTY NAMES CHANGED AND THE OLD ONE FAILS SILENTLY.
#
# The first run (2026-09-08) asked for CanonicalSMILES and got HTTP 200, InChIKey,
# MolecularFormula and MolecularWeight for all 651 CIDs — and `"smiles": null` for every
# one of them. PUG REST no longer serves that name: it is now SMILES (isomeric, the
# default) and ConnectivitySMILES (the flat form the old CanonicalSMILES meant).
#
# An unknown property is not an error to PUG REST. It is simply absent from the response,
# so the request succeeds, the cache fills, and the one field the whole script exists for
# is empty. Ask for both names, and let the loader below take whichever arrives.
PROPS = "SMILES,ConnectivitySMILES,InChIKey,MolecularFormula,MolecularWeight"
URL = ("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cids}"
       "/property/" + PROPS + "/JSON")

# pubchem.py's retry/backoff and UA, imported rather than copied.
spec = importlib.util.spec_from_file_location("pubchem", HERE / "pubchem.py")
pubchem = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pubchem)


def live_cids() -> list[int]:
    """CIDs of rows that actually count — triage_pubchem.py MARKS retired rows rather
    than deleting them, and status.py skips them. Fetching structures for rows excluded
    on provenance or attribution grounds would put them back into a downstream file."""
    out, seen = [], set()
    for line in ROWS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith('{"_comment"'):
            continue
        r = json.loads(line)
        if r.get("excluded"):
            continue
        c = r.get("molecule_cid")
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def main() -> int:
    cids = live_cids()
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    # A CID cached WITHOUT a smiles is not done — that is exactly the state the
    # CanonicalSMILES rename left behind, and treating "present in cache" as "fetched"
    # would make the repair a no-op.
    missing = [c for c in cids
               if str(c) not in cache or not cache[str(c)].get("smiles")]
    print(f"live CIDs {len(cids)} · cached {len(cache)} · to fetch {len(missing)}")

    if "--status" in sys.argv:
        return 0
    if not missing:
        print("nothing to do")
        return 0

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(missing), BATCH):
        chunk = missing[i:i + BATCH]
        url = URL.format(cids=",".join(str(c) for c in chunk))
        print(f"  [{i//BATCH + 1}/{(len(missing)+BATCH-1)//BATCH}] {len(chunk)} cids",
              flush=True)
        data = json.loads(pubchem._get(url))
        for p in data.get("PropertyTable", {}).get("Properties", []):
            cid = p.get("CID")
            if cid is None:
                continue
            cache[str(cid)] = {
                "smiles": p.get("SMILES") or p.get("ConnectivitySMILES")
                          or p.get("CanonicalSMILES"),
                "connectivity_smiles": p.get("ConnectivitySMILES"),
                "inchikey": p.get("InChIKey"),
                "formula": p.get("MolecularFormula"),
                "mw": p.get("MolecularWeight"),
            }
        CACHE.write_text(json.dumps(cache, indent=1))     # save every batch, resumable
        if i + BATCH < len(missing):
            time.sleep(random.uniform(*pubchem.DELAY))

    got = sum(1 for c in cids if str(c) in cache)
    smi = sum(1 for c in cids if cache.get(str(c), {}).get("smiles"))
    print(f"\ncached {got} of {len(cids)} CIDs · {smi} with a SMILES")
    if got < len(cids):
        print(f"  {len(cids)-got} CIDs returned nothing — PubChem has the record but not")
        print("  the property, or the CID is retired. They simply have no features.")
    print(f"-> {CACHE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
