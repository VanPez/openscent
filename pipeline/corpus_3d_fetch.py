#!/usr/bin/env python3
"""
corpus_3d_fetch.py — PubChem's computed 3D conformers for the molecules of release/v1.0.

RUNS ON HETZNER (PubChem throttles Ivan's home IP; every PubChem step goes through the server).
Standard library only; resumable (rerun it and it skips what is done).

    python3 corpus_3d_fetch.py IN.json OUT.json [--limit N]

IN   a JSON list of {"ik": "<full InChIKey>", "cid": <int or null>}   (pipeline/corpus_3d_todo.py writes it)
OUT  {"<ik>": {"cid": <int|null>, "src": "cid"|"inchikey"|null, "c3d": {"el": [...], "xyz": [[x,y,z]...], "b": [[a,b,order]...]} | null}}

WHAT IT DOES
  1. Molecules that carry no CID are looked up by their FULL InChIKey in batches of 50 (one POST each). Only an
     exact InChIKey match counts: a stereo-flat structure whose stereoisomers are in PubChem gets no CID, because
     picking one of them would put the wrong molecule on the page.
  2. For every CID, PubChem's own computed 3D record (record_type=3d), stored as the preview already stores it
     (element numbers, coordinates to 3 decimals, bonds). 404 = PubChem has none (too flexible, too large, salts)
     -> c3d null. Nothing is computed here; these are PubChem (NCBI) conformers, public domain.

Polite by design: a descriptive User-Agent, 0.4-0.8 s between requests, back-off on 429/5xx.
"""
from __future__ import annotations
import json, os, random, sys, time, urllib.error, urllib.parse, urllib.request

PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
UA = "OpenScent/0.1 (research corpus; github.com/VanPez)"


def call(url, data=None, tries=6):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **({"Content-Type": "application/x-www-form-urlencoded"} if data else {})})
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
            time.sleep(random.uniform(0.4, 0.8))


def save(out, path):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    os.replace(tmp, path)


def conformer(cid):
    j = call(f"{PUG}/compound/cid/{cid}/record/JSON?record_type=3d")
    comp = ((j or {}).get("PC_Compounds") or [None])[0]
    if not comp:
        return None
    conf = comp["coords"][0]["conformers"][0]
    bonds = comp.get("bonds", {})
    return {"el": comp["atoms"]["element"],
            "xyz": [[round(a, 3), round(b, 3), round(z, 3)] for a, b, z in
                    zip(conf["x"], conf["y"], conf.get("z", [0] * len(conf["x"])))],
            "b": [[a - 1, b - 1, o] for a, b, o in zip(bonds.get("aid1", []), bonds.get("aid2", []),
                                                    bonds.get("order", [1] * len(bonds.get("aid1", []))))]}


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    if limit is not None:
        a = [x for x in a if x != str(limit)]
    src, dst = a[0], a[1]
    todo = json.load(open(src, encoding="utf-8"))
    if limit:
        # smoke test: the first N with a CID and the first N without one
        with_c = [t for t in todo if t.get("cid")][:limit]
        without = [t for t in todo if not t.get("cid")][:limit]
        todo = with_c + without
    out = json.load(open(dst, encoding="utf-8")) if os.path.exists(dst) else {}
    print(f"{len(todo)} molecules; already done {sum(1 for t in todo if t['ik'] in out)}", flush=True)

    # ---- 1. InChIKey -> CID, batches of 50, exact keys only
    need = [t["ik"] for t in todo if not t.get("cid") and t["ik"] not in out]
    for i in range(0, len(need), 50):
        batch = need[i:i + 50]
        j = call(f"{PUG}/compound/inchikey/property/InChIKey/JSON", data=urllib.parse.urlencode({"inchikey": ",".join(batch)}).encode())
        found = {}
        for p in (j.get("PropertyTable", {}).get("Properties", []) if isinstance(j, dict) else []):
            k, c = p.get("InChIKey"), p.get("CID")
            if k and c and (k not in found or c < found[k]):
                found[k] = c
        for k in batch:
            out[k] = {"cid": found.get(k), "src": "inchikey" if k in found else None, "c3d": None, "done": k not in found}
        print(f"  inchikey lookup {min(i + 50, len(need))}/{len(need)}: {len(found)} of {len(batch)} found", flush=True)
        save(out, dst)
    for t in todo:
        if t.get("cid") and t["ik"] not in out:
            out[t["ik"]] = {"cid": t["cid"], "src": "cid", "c3d": None, "done": False}

    # ---- 2. the conformers
    keys = [t["ik"] for t in todo]
    pend = sorted(k for k in keys if out[k]["cid"] and not out[k]["done"])
    print(f"conformers to fetch: {len(pend)}", flush=True)
    for n, k in enumerate(pend, 1):
        out[k]["c3d"] = conformer(out[k]["cid"])
        out[k]["done"] = True
        if n % 25 == 0 or n == len(pend):
            save(out, dst)
            print(f"  {n}/{len(pend)}", flush=True)
    save(out, dst)
    got = [out[k] for k in keys]
    print(f"done: {len(got)} molecules; with a CID {sum(1 for v in got if v['cid'])}; with a 3D conformer {sum(1 for v in got if v['c3d'])}", flush=True)


if __name__ == "__main__":
    main()
