#!/usr/bin/env python3
"""
structures_pubchem.py — stage 2 of name -> structure: PubChem name lookup. RUNS ON HETZNER.

    scp pipeline/structures_pubchem.py corpus/structures/pubchem-todo.json root@46.224.42.12:/opt/openscent/
    ssh root@46.224.42.12 'cd /opt/openscent && python3 structures_pubchem.py [todo.json [out.json]]'
    scp root@46.224.42.12:/opt/openscent/pubchem-names.json corpus/structures/

NEVER FROM THE MAC. PubChem throttles Ivan's home IP (DEVLOG 2026-09-26); every PubChem fetch
goes through Hetzner. Standard library only — the box has no RDKit and needs none.

WHAT IT DOES
------------
For each name in pubchem-todo.json ("todo" = names OPSIN could not read, "check" = names OPSIN
DID read, sent through the same lookup to measure OPSIN against an independent resolver, "extra" =
names a hand-authorised rewrite is to be cross-checked against):

    1. PUG REST  compound/name/<name>/cids      (PubChem's own synonym match; 404 = not found)
    2. PUG REST  compound/cid/<cids>/property   SMILES, ConnectivitySMILES, InChIKey, IUPACName,
                                                Title, MolecularFormula  — in batches of 100

and writes ALL returned CIDs (up to 10) and their properties, nothing chosen. The same properties
call also covers "cids": PubChem-half CIDs that smiles.json has no InChIKey for (the 2026-09-24
Physical Description ingest added them), so the structure join can cover both halves. Choosing — and the
rule that a name which matches records of DIFFERENT connectivity is rejected as ambiguous — is
structures.py's job, offline, where the rule can be read and changed without a network call.

Resumable: results are cached per name in pubchem-names.json after every 10 names, so a dropped
connection costs nothing. Delay 1-2 s between requests (NCBI allows 5/s; this uses ~1/s), the
same politeness and User-Agent as pubchem.py. 349 names is about ten minutes.

Property names matter (see pubchem_smiles.py): an unknown one is silently absent, not an error.
"""
from __future__ import annotations
import json, pathlib, random, sys, time, urllib.error, urllib.parse, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
IN = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "pubchem-todo.json"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "pubchem-names.json"
UA = "OpenScent/0.1 (research corpus; contact via github.com/VanPez)"
DELAY = (1.0, 2.0)
BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
PROPS = "SMILES,ConnectivitySMILES,InChIKey,IUPACName,Title,MolecularFormula"
MAX_CIDS = 10


def get(url: str, tries: int = 4):
    """-> (http_status, body). 404/400 are answers, not failures. 5xx/429/network: back off."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return e.code, ""
            err = f"HTTP {e.code}"
        except Exception as e:
            err = str(e)
        if attempt == tries - 1:
            return -1, err
        wait = (2 ** attempt) * 5 + random.uniform(0, 3)
        print(f"    retry {attempt + 1}/{tries - 1} in {wait:.0f}s ({err})", file=sys.stderr, flush=True)
        time.sleep(wait)
    return -1, "unreachable"


def lookup(name: str) -> dict:
    url = f"{BASE}/name/{urllib.parse.quote(name, safe='')}/cids/JSON"
    code, body = get(url)
    if code == 200:
        cids = json.loads(body).get("IdentifierList", {}).get("CID", [])
        return {"status": "found" if cids else "notfound", "cids": cids[:MAX_CIDS], "n_cids": len(cids)}
    if code in (400, 404):
        return {"status": "notfound" if code == 404 else "badrequest", "cids": [], "n_cids": 0}
    return {"status": "error", "error": body, "cids": [], "n_cids": 0}


def main() -> int:
    work = json.loads(IN.read_text(encoding="utf-8"))
    names = sorted({e["name"] for part in ("todo", "check", "extra") for e in work.get(part, [])})
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"names": {}, "cids": {}}
    # an error is not an answer: retry it on the next run
    todo = [n for n in names if data["names"].get(n, {}).get("status") in (None, "error")]
    print(f"{len(names)} names · {len(names) - len(todo)} cached · {len(todo)} to look up", flush=True)

    for i, n in enumerate(todo, 1):
        data["names"][n] = lookup(n)
        if i % 10 == 0 or i == len(todo):
            OUT.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
            print(f"  {i}/{len(todo)}", flush=True)
        time.sleep(random.uniform(*DELAY))

    # CIDs the name lookups returned, plus CIDs the PubChem-half rows carry but have no InChIKey yet
    wanted = {c for v in data["names"].values() for c in v["cids"]} | set(work.get("cids", []))
    need = sorted(wanted - {int(c) for c in data["cids"]})
    print(f"{len(need)} CIDs need properties", flush=True)
    for i in range(0, len(need), 100):
        chunk = need[i:i + 100]
        code, body = get(f"{BASE}/cid/{','.join(map(str, chunk))}/property/{PROPS}/JSON")
        if code != 200:
            print(f"  properties batch {i // 100 + 1} failed ({code}) — re-run to retry", file=sys.stderr)
            continue
        for p in json.loads(body).get("PropertyTable", {}).get("Properties", []):
            data["cids"][str(p["CID"])] = {
                "smiles": p.get("SMILES") or p.get("ConnectivitySMILES"),
                "connectivity_smiles": p.get("ConnectivitySMILES"),
                "inchikey": p.get("InChIKey"), "iupac_name": p.get("IUPACName"),
                "title": p.get("Title"), "formula": p.get("MolecularFormula")}
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
        time.sleep(random.uniform(*DELAY))

    st = {}
    for v in data["names"].values():
        st[v["status"]] = st.get(v["status"], 0) + 1
    print(f"done · {st} · {len(data['cids'])} CIDs with properties -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
