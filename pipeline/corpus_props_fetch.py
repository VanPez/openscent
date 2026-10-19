#!/usr/bin/env python3
"""
corpus_props_fetch.py — PubChem-computed Formula, molecular weight and XLogP3 for the corpus page.

RUNS ON HETZNER (all PubChem traffic does). Standard library only.

    python3 corpus_props_fetch.py conformers.json props.json

IN   corpus/3d/conformers.json (written by corpus_3d_fetch.py): {inchikey: {"cid": n|null, ...}}
OUT  {"<cid>": {"f": "C15H22O", "mw": 218.33, "xlogp": 3.8 | null}}

One POST per 100 CIDs (PUG REST property table). These are values PubChem computed (XLogP3 by NCBI), public
domain; nothing is computed here. A compound PubChem gives no XLogP for stays null (shown as an empty cell)."""
import json, random, sys, time, urllib.error, urllib.parse, urllib.request

PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
UA = "OpenScent/0.1 (research corpus; github.com/VanPez)"


def call(url, data, tries=6):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return {"_http": e.code}
            if e.code not in (429, 500, 502, 503, 504) or k == tries - 1:
                raise
            print(f"    HTTP {e.code}, retry in {10 * 2 ** k}s", flush=True)
            time.sleep(10 * 2 ** k)
        finally:
            time.sleep(random.uniform(0.5, 1.0))


def main():
    cids = sorted({v["cid"] for v in json.load(open(sys.argv[1], encoding="utf-8")).values() if v.get("cid")})
    out = {}
    print(f"{len(cids)} CIDs", flush=True)
    for i in range(0, len(cids), 100):
        batch = cids[i:i + 100]
        j = call(f"{PUG}/compound/cid/property/MolecularFormula,MolecularWeight,XLogP/JSON",
                 urllib.parse.urlencode({"cid": ",".join(map(str, batch))}).encode())
        for p in (j.get("PropertyTable", {}).get("Properties", []) if isinstance(j, dict) else []):
            mw = p.get("MolecularWeight")
            out[str(p["CID"])] = {"f": p.get("MolecularFormula"), "mw": float(mw) if mw not in (None, "") else None,
                                  "xlogp": p.get("XLogP")}
        print(f"  {min(i + 100, len(cids))}/{len(cids)}  ({len(out)} returned)", flush=True)
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), separators=(",", ":"))
    print(f"done: {len(out)} of {len(cids)} CIDs; with formula {sum(1 for v in out.values() if v['f'])}; "
          f"with MW {sum(1 for v in out.values() if v['mw'] is not None)}; with XLogP {sum(1 for v in out.values() if v['xlogp'] is not None)}", flush=True)


if __name__ == "__main__":
    main()
