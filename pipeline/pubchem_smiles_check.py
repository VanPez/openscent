#!/usr/bin/env python3
"""
pubchem_smiles_check.py — look a list of SMILES and names up in PubChem. RUNS ON HETZNER.

    scp pipeline/pubchem_smiles_check.py <in.json> root@46.224.42.12:/opt/openscent/
    ssh root@46.224.42.12 'cd /opt/openscent && python3 pubchem_smiles_check.py in.json out.json'
    scp root@46.224.42.12:/opt/openscent/out.json outreach/

NEVER FROM THE MAC (PubChem throttles the home IP; DEVLOG 2026-09-26). Standard library only.

Input: {"items": [{"id": "...", "kind": "smiles" | "name", "q": "..."}, ...]}

  smiles  POST compound/fastidentity/smiles/cids  (identity_type=same_connectivity: every stereoisomer
          sharing the connectivity), then compound/cid/<cids>/property for up to 10 of them.
  name    GET compound/name/<name>/cids, then the property call, then compound/cid/<first>/synonyms.

Output: the raw answers, nothing chosen, per item: n_cids, up to 10 records (InChIKey, ConnectivitySMILES,
IUPACName, Title, MolecularFormula) and, for names, the first 100 synonyms. Comparing and judging happen
offline. A 404 means PubChem has no such record — an answer, not an error.

Written 2026-10-03 for the check of the 18 set-aside names against Joe's SMILES list (DEVLOG 10-03 night).
"""
from __future__ import annotations
import json, pathlib, random, sys, time, urllib.error, urllib.parse, urllib.request

IN = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])
UA = "OpenScent/0.1 (research corpus; contact via github.com/VanPez)"
DELAY = (1.0, 2.0)
BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
PROPS = "SMILES,ConnectivitySMILES,InChIKey,IUPACName,Title,MolecularFormula"
MAX_CIDS = 10


def call(url: str, data: bytes | None = None, tries: int = 4):
    """-> (http_status, parsed JSON or None). 400/404 are answers. 5xx/429/network: back off."""
    time.sleep(random.uniform(*DELAY))
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return e.code, None
            err = f"HTTP {e.code}"
        except Exception as e:
            err = str(e)
        if attempt == tries - 1:
            return 0, {"error": err}
        time.sleep(5 * (attempt + 1))
    return 0, None


def cids_from(body, status):
    """Handle a plain CID list or an asynchronous ListKey answer."""
    if status != 200 or not body:
        return []
    if "IdentifierList" in body:
        return body["IdentifierList"].get("CID", [])
    key = (body.get("Waiting") or {}).get("ListKey")
    for _ in range(10):
        if not key:
            return []
        time.sleep(3)
        st, b = call(f"{BASE}/listkey/{key}/cids/JSON")
        if st == 200 and b and "IdentifierList" in b:
            return b["IdentifierList"].get("CID", [])
    return []


def props(cids):
    if not cids:
        return []
    st, b = call(f"{BASE}/cid/{','.join(str(c) for c in cids[:MAX_CIDS])}/property/{PROPS}/JSON")
    return (b or {}).get("PropertyTable", {}).get("Properties", []) if st == 200 else []


def main():
    items = json.loads(IN.read_text())["items"]
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    for i, it in enumerate(items, 1):
        if it["id"] in done:
            continue
        rec = {"kind": it["kind"], "q": it["q"]}
        if it["kind"] == "smiles":
            st, b = call(f"{BASE}/fastidentity/smiles/cids/JSON?identity_type=same_connectivity",
                         data=urllib.parse.urlencode({"smiles": it["q"]}).encode())
            cids = cids_from(b, st)
            rec.update(http=st, n_cids=len(cids), cids=cids[:MAX_CIDS])
        else:
            st, b = call(f"{BASE}/name/{urllib.parse.quote(it['q'], safe='')}/cids/JSON")
            cids = cids_from(b, st)
            rec.update(http=st, n_cids=len(cids), cids=cids[:MAX_CIDS])
        rec["props"] = props(cids)
        if it["kind"] == "name" and cids:
            st, b = call(f"{BASE}/cid/{cids[0]}/synonyms/JSON")
            syn = ((b or {}).get("InformationList", {}).get("Information") or [{}])[0].get("Synonym", []) if st == 200 else []
            rec["synonyms_cid"] = cids[0]
            rec["synonyms"] = syn[:100]
            rec["n_synonyms"] = len(syn)
        done[it["id"]] = rec
        OUT.write_text(json.dumps(done, indent=1, ensure_ascii=False))
        print(f"[{i}/{len(items)}] {it['id']}: http {rec['http']}, {rec['n_cids']} cid(s)", flush=True)


if __name__ == "__main__":
    main()
