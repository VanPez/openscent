#!/usr/bin/env python3
"""catalog.py — the MATERIALS CATALOGUE: every common commercial perfumery compound, described or not.

WHY (Ivan, 2026-09-26)
----------------------
"What good is my list if there's not even the most common molecules in it for people to
browse." Two shop lists (De Hekserij, Olfatorium) gave 208 distinct single compounds; 116 have
no description in any admissible source we hold (gaps.py, origin probe 2026-09-26). Their shop
descriptors are all-rights-reserved and stay out. Their IDENTITY and PHYSICAL PROPERTIES are
facts, so every compound gets a catalogue row; the descriptor field says honestly whether the
corpus has a description, and if not, that none was found.

WHAT IS IN A ROW, AND UNDER WHAT TERMS
--------------------------------------
  identity     PubChem CID, title, IUPAC name, formula, SMILES, InChI, InChIKey, CAS  (facts)
  commercial   names it is sold under ("Iso E Super", "Hedione HC"): a shop label is kept only if
               PubChem lists it as a synonym or the shop marked it with a maker's code "(IFF)".
               Nominative use; trademark notice in corpus/catalog/README.md
  computed     MW, exact mass, XLogP3, TPSA, H-bond donors/acceptors, rotatable bonds —
               computed BY PubChem (NCBI, a US-government work: public domain)
  measured     vapour pressure, boiling point, logP — ONLY values whose PubChem source is a
               US-government database (ALLOWED below), copied verbatim with the source name.
               Values deposited by others (Good Scents, Sigma-Aldrich, ILO ICSC, HMDB…) are
               dropped even when they are the only value.
  corpus       descriptor_status + tags, from gaps.tsv (status.py's rows, never re-derived)
NOT in a row: which shop sells it. A shop catalogue can be an EU sui-generis database; the
catalogue describes compounds, and the paper says how they were chosen.

The catalogue is NOT corpus rows. status.py does not read it; the CC0 extraction claim of
the corpus is untouched by anything here.

USAGE
  python3 pipeline/catalog.py --fetch     # NETWORK (Hetzner): -> corpus/catalog/pubchem-props.json
                                          #   add --refetch-measured to redo the experimental pages
  python3 pipeline/catalog.py --fetch-3d  # NETWORK (Hetzner): -> corpus/catalog/conformers.json
  python3 pipeline/catalog.py             # offline: -> corpus/catalog/materials.tsv
"""
from __future__ import annotations
import csv, difflib, importlib.util, json, os, pathlib, random, re, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAT = ROOT / "corpus" / "catalog"
PROPS = CAT / "pubchem-props.json"
GAPS = ROOT / "corpus" / "gaps" / "gaps.tsv"
PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
VIEW = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound"
UA = "OpenScent/0.1 (research corpus; github.com/VanPez)"

# computed by PubChem itself. PubChem renamed its SMILES properties in 2025 (SMILES /
# ConnectivitySMILES); the old names are the fallback if the new ones are refused.
COMPUTED = ["Title", "IUPACName", "MolecularFormula", "MolecularWeight", "ExactMass", "SMILES",
            "InChI", "InChIKey", "XLogP", "TPSA", "HBondDonorCount", "HBondAcceptorCount", "RotatableBondCount"]
COMPUTED_OLD = [p if p != "SMILES" else "IsomericSMILES" for p in COMPUTED]
MEASURED = {"Vapor Pressure": "vapour_pressure", "Boiling Point": "boiling_point", "LogP": "logp_measured",
            # added 2026-09-27 (the fields of a perfumer's spec sheet), same source rule:
            "Density": "density", "Melting Point": "melting_point", "Flash Point": "flash_point",
            "Odor Threshold": "odour_threshold", "Color/Form": "appearance"}
# US-government sources only (17 U.S.C. 105). Anything else is dropped, however useful.
ALLOWED = re.compile(r"Hazardous Substances Data Bank|HSDB|ChemIDplus|CAMEO Chemicals|NIOSH|"
                     r"\bEPA\b|Environmental Protection Agency|National Toxicology Program|"
                     r"\bFDA\b|Food and Drug Administration|\bNOAA\b|\bCDC\b|ATSDR|\bNCATS\b|"
                     # added 2026-09-26 after the first build dropped them: both are US agencies
                     r"Occupational Safety and Health Administration|\bOSHA\b|U\.S\. Department of Energy", re.I)


def get_json(url, tries=5):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return {"_http": e.code}
            if e.code not in (429, 500, 502, 503, 504) or k == tries - 1:
                raise
            print(f"    HTTP {e.code}, retry in {10 * 2 ** k}s"); time.sleep(10 * 2 ** k)
        finally:
            time.sleep(random.uniform(1.0, 2.0))


def save(p):
    tmp = PROPS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(p, ensure_ascii=False, indent=0), encoding="utf-8"); os.replace(tmp, PROPS)


def value_text(v: dict) -> str:
    if "StringWithMarkup" in v:
        return " ".join(s.get("String", "") for s in v["StringWithMarkup"]).strip()
    if "Number" in v:
        return " ".join(str(n) for n in v["Number"]) + (f" {v['Unit']}" if v.get("Unit") else "")
    return ""


def walk(sec, out):
    """collect Information lists under the headings in MEASURED, anywhere in the tree"""
    h = sec.get("TOCHeading")
    if h in MEASURED:
        out.setdefault(h, []).extend(sec.get("Information", []))
    for s in sec.get("Section", []):
        walk(s, out)


def fetch():
    CAT.mkdir(parents=True, exist_ok=True)
    cids = [r["cid"] for r in csv.DictReader(open(GAPS, encoding="utf-8"), delimiter="\t")]
    p = json.loads(PROPS.read_text(encoding="utf-8")) if PROPS.exists() else {"computed": {}, "measured": {}}
    todo = [c for c in cids if c not in p["computed"]]
    print(f"{len(cids)} compounds; computed properties for {len(todo)}")
    for k in range(0, len(todo), 100):
        chunk = todo[k:k + 100]
        j = get_json(f"{PUG}/compound/cid/{','.join(chunk)}/property/{','.join(COMPUTED)}/JSON")
        if j.get("_http"):
            j = get_json(f"{PUG}/compound/cid/{','.join(chunk)}/property/{','.join(COMPUTED_OLD)}/JSON")
        for row in (j.get("PropertyTable") or {}).get("Properties", []):
            row["SMILES"] = row.get("SMILES") or row.pop("IsomericSMILES", "")
            p["computed"][str(row["CID"])] = row
        save(p)
    # --refetch-measured: redo the PubChem experimental pages (needed once, 2026-09-27, when
    # MEASURED grew: the first fetch kept only VP / BP / logP and discarded the rest).
    todo = cids if "--refetch-measured" in sys.argv else [c for c in cids if c not in p["measured"]]
    print(f"measured properties (US-government sources only) for {len(todo)}")
    for i, cid in enumerate(todo, 1):
        j = get_json(f"{VIEW}/{cid}/JSON?heading=" + urllib.parse.quote("Experimental Properties"))
        got, kept = {}, {}
        rec = (j or {}).get("Record") or {}
        for s in rec.get("Section", []):
            walk(s, got)
        refs = {r.get("ReferenceNumber"): r for r in rec.get("Reference", [])}
        for h, infos in got.items():
            for inf in infos:
                ref = refs.get(inf.get("ReferenceNumber"), {})
                src = ref.get("SourceName", "")
                txt = value_text(inf.get("Value", {}))
                entry = {"value": txt, "source": src, "url": ref.get("URL", "")}
                kept.setdefault(MEASURED[h], []).append({**entry, "allowed": bool(ALLOWED.search(src))})
        p["measured"][cid] = kept
        if i % 10 == 0 or i == len(todo):
            save(p); print(f"  {i}/{len(todo)}")
    save(p)
    print("done")


CONF = CAT / "conformers.json"


def fetch_3d():
    """PubChem's computed 3D conformer per CID, stored compactly for the preview's built-in viewer.

    WHY FETCH ONCE (2026-09-26): the aroma-index viewer downloads the conformer from PubChem on
    every click. When PubChem throttled Ivan's IP, every 3D box went blank. Stored here, the page
    needs no network at all. Conformers are computed by PubChem (NCBI): public domain.
    404 = PubChem has no 3D conformer (too flexible, too large, salts/mixtures) -> stored as null."""
    cids = [r["cid"] for r in csv.DictReader(open(GAPS, encoding="utf-8"), delimiter="\t")]
    c = json.loads(CONF.read_text(encoding="utf-8")) if CONF.exists() else {}
    todo = [x for x in cids if x not in c]
    print(f"{len(cids)} compounds; 3D conformers to fetch {len(todo)}")
    for i, cid in enumerate(todo, 1):
        j = get_json(f"{PUG}/compound/cid/{cid}/record/JSON?record_type=3d")
        comp = ((j or {}).get("PC_Compounds") or [None])[0]
        if not comp:
            c[cid] = None
        else:
            conf = comp["coords"][0]["conformers"][0]
            bonds = comp.get("bonds", {})
            c[cid] = {"el": comp["atoms"]["element"],
                      "xyz": [[round(a, 3), round(b, 3), round(z, 3)] for a, b, z in
                              zip(conf["x"], conf["y"], conf.get("z", [0] * len(conf["x"])))],
                      "b": [[a - 1, b - 1, o] for a, b, o in zip(bonds.get("aid1", []), bonds.get("aid2", []),
                                                              bonds.get("order", [1] * len(bonds.get("aid1", []))))]}
        if i % 10 == 0 or i == len(todo):
            tmp = CONF.with_suffix(".json.tmp"); tmp.write_text(json.dumps(c, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, CONF); print(f"  {i}/{len(todo)}")
    print(f"done: {sum(1 for v in c.values() if v)} with 3D, {sum(1 for v in c.values() if v is None)} without")


def ec_valid(ec: str) -> bool:
    """EC (EINECS/ELINCS) numbers carry a check digit: weights 1..6 on the first six digits, mod 11."""
    d = re.sub(r"\D", "", ec)
    return len(d) == 7 and sum((i + 1) * int(x) for i, x in enumerate(d[:6])) % 11 == int(d[6])


def identifiers(syns):
    """EC and FEMA numbers as PubChem lists them among the synonyms ("EINECS 202-086-7",
    "FEMA No. 2381"). No fetch: the synonym cache already holds them. Several EC numbers for one
    CID are real (isomers, mixtures) and are all kept, in PubChem's order; bad checksums dropped."""
    ec, fema = [], []
    for x in syns:
        m = re.match(r"(?:EINECS|EC)\s*(\d{3}-\d{3}-\d)$", x)
        if m and ec_valid(m.group(1)) and m.group(1) not in ec:
            ec.append(m.group(1))
        m = re.match(r"FEMA\s*(?:No\.?|Number)?\s*(\d{4})\b", x, re.I)
        if m and m.group(1) not in fema:
            fema.append(m.group(1))
    return {"ec_number": " | ".join(ec), "fema_number": " | ".join(fema)}


def build():
    spec = importlib.util.spec_from_file_location("g", ROOT / "pipeline" / "gaps.py")
    g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
    p = json.loads(PROPS.read_text(encoding="utf-8"))
    origin = {}
    oc = ROOT / "corpus" / "gaps" / "origin-candidates.json"
    if oc.exists():
        origin = json.loads(oc.read_text(encoding="utf-8"))
    syn = {}
    for shop in g.SHOPS:
        syn.update(json.loads((ROOT / "corpus" / shop / "pubchem-cache.json").read_text(encoding="utf-8"))["syn"])
    allerg = {}                                  # corpus/catalog/eu-allergens.tsv, 2026-09-27
    af = CAT / "eu-allergens.tsv"
    if af.exists():
        for line in af.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith(("#", "cas\t")):
                c_, src_ = line.split("\t", 1)
                allerg[c_] = src_
    rows, dropped = [], {}
    for r in csv.DictReader(open(GAPS, encoding="utf-8"), delimiter="\t"):
        cid = r["cid"]
        c = p["computed"].get(cid, {})
        # TRADE names only, not a shop's own labels ("Vainillin", "Aldehyde C12 Lauric"): a
        # name counts if the shop marked it with a maker's code — "(IFF)", "(Giv)" — or if
        # PubChem lists it as a synonym. Generic chemical names are already in name/iupac_name.
        # Loose comparison ("Iso E Super" == "Iso-E super"), as in hekserij_link.loose.
        lz = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
        known = {lz(s) for s in syn.get(cid, [])}
        trade, common = [], ""
        for prod in r["products"].split(" | "):
            v = g.shop_variants(prod)
            if not v:
                continue
            # common_name: the first label a perfumer would search for (Hekserij's English
            # label comes first). A generic name like "Ionone beta" is a fact, not a claim.
            common = common or v[0]
            if (g.SUPPLIER.search(prod) or lz(v[0]) in known) and lz(v[0]) != lz(c.get("Title", "")) \
                    and lz(v[0]) not in {lz(x) for x in trade}:
                trade.append(v[0])
        # Olfatorium-only materials carry Spanish shop labels ("Vainillin", "Acetato de Bencilo").
        # Narrowly: only a near-spelling of the PubChem title is a shop's local spelling of the
        # same name ("Vainillin" ~ "Vanillin"). Trade names (Cedramber, Habanolide) and industry
        # labels ("Aldehyde C-11 MOA") are far from the title and stay as they are.
        # (2026-09-27: this block had slipped INSIDE the loop's trade-name test on 09-26, which
        # emptied commercial_names for most materials. Restored.)
        t = c.get("Title", "")
        if "hekserij" not in r["shops"] and t and lz(t) != lz(common) \
                and difflib.SequenceMatcher(None, lz(t), lz(common)).ratio() >= 0.9:
            common = t
        ids = identifiers(syn.get(cid, []))
        m = p["measured"].get(cid, {})
        meas = {}
        for key in MEASURED.values():
            ok = [e for e in m.get(key, []) if ALLOWED.search(e["source"])]
            for e in m.get(key, []):
                if not ALLOWED.search(e["source"]):
                    dropped[e["source"]] = dropped.get(e["source"], 0) + 1
            # value i belongs to source i (2026-09-27: the two lists used to be de-duplicated
            # separately, which misaligned them as soon as one source gave two values)
            pairs = list(dict.fromkeys((e["value"], e["source"]) for e in ok if e["value"]))
            meas[key] = " || ".join(v for v, _ in pairs)
            meas[key + "_source"] = " || ".join(src for _, src in pairs)
        if r["status"] == "in corpus":
            dstat = "described in the corpus"
            why = r["matched_by"]
        else:
            dstat = "no admissible description found"
            o = origin.get(cid)
            why = (f"PubChem links {o['us_docs']} US patents, {o['held']} held; none describes it in a "
                   f"sentence the corpus kept" if o else "")
        rows.append({
            "cid": cid, "common_name": common, "pubchem_title": c.get("Title", ""),
            "commercial_names": " | ".join(trade), "cas": r["cas"],
            "iupac_name": c.get("IUPACName", ""), "formula": c.get("MolecularFormula", ""),
            "mw": c.get("MolecularWeight", ""), "exact_mass": c.get("ExactMass", ""),
            "xlogp3": c.get("XLogP", ""), "tpsa": c.get("TPSA", ""),
            "hbd": c.get("HBondDonorCount", ""), "hba": c.get("HBondAcceptorCount", ""),
            "rotatable_bonds": c.get("RotatableBondCount", ""),
            "smiles": c.get("SMILES", ""), "inchikey": c.get("InChIKey", ""), "inchi": c.get("InChI", ""),
            **ids, **meas,
            "eu_allergen": next((allerg[c_] for c_ in r["cas"].split(", ") if c_ in allerg), ""),
            "descriptor_status": dstat, "corpus_tags": r["corpus_tags"], "status_note": why,
        })
    rows.sort(key=lambda x: (x["descriptor_status"] != "described in the corpus", (x["common_name"] or x["pubchem_title"]).lower()))
    out = CAT / "materials.tsv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t"); w.writeheader(); w.writerows(rows)
    n_desc = sum(r["descriptor_status"] == "described in the corpus" for r in rows)
    has = lambda k: sum(1 for r in rows if r[k])
    print(f"{len(rows)} compounds · described {n_desc} · no admissible description {len(rows) - n_desc}")
    print(f"computed properties {has('mw')} · EC {has('ec_number')} · FEMA {has('fema_number')} · EU allergen {has('eu_allergen')}")
    print("measured (US-government sources only): " + " · ".join(f"{k} {has(k)}" for k in MEASURED.values()))
    if dropped:
        print("measured values DROPPED for their source: " + ", ".join(f"{s or '?'} {n}" for s, n in
              sorted(dropped.items(), key=lambda kv: -kv[1])[:12]))
    print(f"written -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    if "--fetch-3d" in sys.argv:
        fetch_3d()
    elif "--fetch" in sys.argv:
        fetch()
    else:
        build()
