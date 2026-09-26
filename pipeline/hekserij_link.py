#!/usr/bin/env python3
"""hekserij_link.py — which De Hekserij aroma chemicals are already in the corpus, by CAS -> PubChem CID.

WHY
---
Ivan wanted a full Hekserij list to compare against the corpus (DEVLOG 09-24). Name
matching is not enough: 96 of the 212 materials are sold under trade names, which the
patents almost never use. Every Hekserij product page states a CAS number, so the join
key here is CAS -> PubChem CID, and then either
    * the CID is in our PubChem rows (HSDB Odor / CAS Physical Description), or
    * one of PubChem's synonyms for that CID equals, after status.norm(), a molecule
      name in our approved patent or passage rows.

WHAT IT IS NOT
--------------
It is not a source. The shop's text is "All rights reserved", so nothing from its
descriptions enters the corpus. corpus/hekserij/cas.tsv holds only name, CAS and INCI,
which are facts, collected 2026-09-25 from the shop's public WooCommerce Store API.

TWO STEPS, SAME AS EVERY OTHER PUBCHEM SCRIPT
---------------------------------------------
    python3 pipeline/hekserij_link.py --fetch    # Mac, needs network; resumable, cached
    python3 pipeline/hekserij_link.py            # offline: match + report
Fetch: 1 request per CAS for the CID, then synonyms in batches of 10 CIDs; about 240
requests at 1-2 s. Cache: corpus/hekserij/pubchem-cache.json.
Output: corpus/hekserij/hekserij-gaps.tsv
"""
from __future__ import annotations
import csv, importlib.util, json, os, pathlib, random, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
HEK = ROOT / "corpus" / "hekserij"
CAS_TSV = HEK / "cas.tsv"
CACHE = HEK / "pubchem-cache.json"
OUT = HEK / "hekserij-gaps.tsv"
PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
UA = "OpenScent/0.1 (research corpus; contact via github.com/VanPez)"
DELAY = (1.0, 2.0)
spec = importlib.util.spec_from_file_location("st", ROOT / "pipeline" / "status.py")
st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)


def get_json(url, tries=6):
    """404 = no such compound (cached as empty). 503 ServerBusy / 429 / 5xx = PubChem
    throttling: back off 10, 20, 40… s and retry. Added 2026-09-25 after a 503 at 100/194."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code not in (429, 500, 502, 503, 504) or k == tries - 1:
                raise
            wait = 10 * 2 ** k
            print(f"    HTTP {e.code}, retry in {wait}s")
            time.sleep(wait)
        except urllib.error.URLError:
            if k == tries - 1:
                raise
            time.sleep(10 * 2 ** k)
        finally:
            time.sleep(random.uniform(*DELAY))


def load_cache():
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {"cid": {}, "syn": {}}


def save_cache(c):
    tmp = CACHE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(c, ensure_ascii=False, indent=0), encoding="utf-8")
    os.replace(tmp, CACHE)


def rows():
    with open(CAS_TSV, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def fetch():
    c = load_cache()
    cas = sorted({r["cas"] for r in rows() if r["cas"] and r["cas_valid"] == "yes"})
    todo = [x for x in cas if x not in c["cid"]]
    print(f"{len(cas)} CAS, {len(todo)} to resolve")
    for i, x in enumerate(todo, 1):
        j = get_json(f"{PUG}/compound/name/{urllib.parse.quote(x)}/cids/JSON")
        c["cid"][x] = (j or {}).get("IdentifierList", {}).get("CID", [])
        if i % 5 == 0:
            save_cache(c)
        if i % 20 == 0:
            print(f"  {i}/{len(todo)}")
    save_cache(c)
    cids = sorted({str(i) for v in c["cid"].values() for i in v[:1]} - set(c["syn"]))
    print(f"{len(cids)} CIDs need synonyms")
    for k in range(0, len(cids), 10):
        chunk = cids[k:k + 10]
        j = get_json(f"{PUG}/compound/cid/{','.join(chunk)}/synonyms/JSON") or {}
        for info in j.get("InformationList", {}).get("Information", []):
            c["syn"][str(info["CID"])] = info.get("Synonym", [])[:200]
        for x in chunk:
            c["syn"].setdefault(x, [])
        save_cache(c)
    print("cache complete")


# PubChem synonym lists are not clean: a synonym can name a DIFFERENT compound. Checked by
# hand 2026-09-25 (every synonym-route match listed with its position in the list):
BAD_SYNONYM = {
    "104-67-6": {"deltaundecalactone", "delta-undecalactone"},  # γ-undecalactone; δ is another compound
}

GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ω": "omega"}


def loose(s: str) -> str:
    """A second, looser key: Greek letters spelled out, then only [a-z0-9] kept.
    'β-damascenone' == 'beta-Damascenone' == 'beta damascenone'. Can merge names that
    differ only in punctuation (locant commas) — acceptable for a coverage comparison,
    and every such match is labelled 'loose name' in the output so it can be checked."""
    s = s.lower()
    for g, w in GREEK.items():
        s = s.replace(g, w)
    return "".join(ch for ch in s if ch.isalnum())


def match():
    c = load_cache()
    norm = st.norm
    surf = st.load_tags()
    by_cid, by_name = {}, {}
    for r in st.jsonl(st.PUBCHEM):
        if not r.get("excluded") and r.get("molecule_cid"):
            by_cid.setdefault(str(r["molecule_cid"]), set()).add(r.get("tag"))
    for r in st.jsonl(st.PHYSDESC):
        if (not r.get("needs_review") or r.get("review_decision") == "approve") and r.get("molecule_cid"):
            by_cid.setdefault(str(r["molecule_cid"]), set()).add(r.get("tag"))
    for r in st.jsonl(st.REVIEW):
        if r.get("decision") == "approve":
            tags = {surf[d.lower()] for d in (r.get("descriptors") or []) if d.lower() in surf}
            for m in r.get("molecules") or []:
                by_name.setdefault(norm(m), set()).update(tags)
    if st.PASSAGE.exists():
        for r in st.jsonl(st.PASSAGE):
            if r.get("review_decision") == "approve":
                by_name.setdefault(norm(r["molecule"]), set()).update(
                    surf[d.lower()] for d in r["descriptors"] if d.lower() in surf)
    by_loose = {}
    for k, v in by_name.items():
        by_loose.setdefault(loose(k), set()).update(v)
    out, n = [], {"in corpus": 0, "gap": 0, "not a single compound": 0, "no CAS / unresolved": 0}
    for r in rows():
        cids = c["cid"].get(r["cas"], []) if r["cas"] else []
        cid = str(cids[0]) if cids else ""
        route, tags = "", set()
        syns = [x for x in c["syn"].get(cid, []) if x.lower() not in BAD_SYNONYM.get(r["cas"], set())]
        if cid and cid in by_cid:
            route, tags = "pubchem CID", set(by_cid[cid])
        else:
            for s in [r["name"], r["inci"]] + syns:
                if s and norm(s) in by_name:
                    route, tags = f"patent name: {s}", set(by_name[norm(s)]); break
            if not route:
                for s in [r["name"], r["inci"]] + syns:
                    if s and len(loose(s)) > 5 and loose(s) in by_loose:
                        route, tags = f"loose name: {s}", set(by_loose[loose(s)]); break
        if r["single_compound"] != "yes":
            status = "not a single compound"
        elif route:
            status = "in corpus"
        elif not cid:
            status = "no CAS / unresolved"
        else:
            status = "gap"
        n[status] += 1
        out.append({**r, "cid": cid, "status": status, "matched_by": route,
                    "corpus_tags": ", ".join(sorted(t for t in tags if t))})
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]), delimiter="\t"); w.writeheader(); w.writerows(out)
    print(f"{len(out)} products: " + " · ".join(f"{k} {v}" for k, v in n.items()))
    print(f"written -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    if not CAS_TSV.exists():
        sys.exit("missing corpus/hekserij/cas.tsv")
    fetch() if "--fetch" in sys.argv else match()
