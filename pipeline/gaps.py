#!/usr/bin/env python3
"""gaps.py — ONE gap list across every shop list, and where its origin patents are.

WHY THIS EXISTS (2026-09-26)
----------------------------
hekserij_link.py judged each shop product on its own, by exact name. Checking its "gaps"
against rows Ivan had already approved turned up compounds that were never gaps:
  * Polysantol, Muscenone — approved under exactly those names; the shop lists them as
    "Polysantol (Fir)", "Muscenone Delta" and PubChem's synonyms do not carry them
  * Norlimbanol — approved as "Timberol (1-(2,2,6-trimethylcyclohexyl)hexan-3-ol)": the
    trade name and the IUPAC name in ONE span, which matches neither alone
  * the same CID could be "in corpus" at one shop and a "gap" at the other
So here a compound is a PubChem CID, it carries the names from EVERY shop that sells it,
and both sides are cleaned:
  shop names    supplier codes "(IFF)", dilutions "10% in DPG", *ADR*, trailing grade
                words ("Delta", "Coeur", "HC", "Total"…) removed; "A aka B", "A / B" split
  corpus names  "X (Y)" also indexed as X and as Y; ® and ™ dropped
Every compound matched only through a cleaned variant is labelled so, for checking.

WHAT IT IS NOT: a source. Shop text never enters the corpus (all rights reserved).

USAGE
  python3 pipeline/gaps.py                 # offline: build corpus/gaps/gaps.tsv
  python3 pipeline/gaps.py --xrefs         # NETWORK (Hetzner — PubChem refuses Ivan's IP):
                                           #   PubChem patent IDs per gap CID -> patent-xrefs.json
  python3 pipeline/gaps.py --origin        # offline: which US patents we lack -> origin-ids.json

ORIGIN PATENTS — the measurement before any fetch
-------------------------------------------------
Every trade-name synthetic was patented by its maker, and a patent claiming a new odorant
states its odour. Our 5,366 patents come from CPC class walks (C11B 9/00, A23L 27/00); a
compound patent classified only under C07C never appeared in them. PubChem lists, per CID,
the patents that mention it (text-mined by Google / SureChEMBL). --origin keeps the US ones,
drops those we hold, and proposes the EARLIEST few per compound — the low patent numbers
are where an origin patent sits. Earliest is a proxy, not a proof: read before believing.
"""
from __future__ import annotations
import csv, importlib.util, json, os, pathlib, random, re, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOPS = ["hekserij", "olfatorium"]
OUTD = ROOT / "corpus" / "gaps"
XREFS = OUTD / "patent-xrefs.json"
PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


# ---------------------------------------------------------------- name cleaning
SUPPLIER = re.compile(r"\((?:IFF|Giv|Fir|Sym|Sy|DRT|nat|org|Kao|Robertet|Kephalis|Firmenich|Givaudan|Symrise)\)", re.I)
DILUTION = re.compile(r"\b\d+(?:[.,]\d+)?\s*%\s*(?:in\s+)?(?:DPG|TEC|IPM|ethanol|etanol|alcohol|BB|DEP)?\b\.?", re.I)
QUALIFIER = {"delta", "coeur", "hc", "total", "supra", "core", "kao", "extra", "pure", "velvet",
             "ifra", "crystals", "nat", "natural", "liquid", "95"}


def shop_variants(name: str) -> list[str]:
    s = DILUTION.sub(" ", name.replace("*ADR*", " "))
    s = SUPPLIER.sub(" ; ", s)          # a split point: "Auralva (IFF) aurantiol" names two things
    s = s.replace("&#8211;", "–")
    pieces = re.split(r"\s+(?:aka|/|–|-)\s+|\s*;\s*", s)
    out = []
    for p in pieces:
        inner = re.findall(r"\(([^)]*)\)", p)
        outer = re.sub(r"\([^)]*\)", " ", p)
        for v in [outer] + inner:
            v = " ".join(v.split())
            if not v:
                continue
            out.append(v)
            toks = v.split()
            while len(toks) > 1 and toks[-1].lower() in QUALIFIER:
                toks = toks[:-1]
                out.append(" ".join(toks))
    return list(dict.fromkeys(out))


def corpus_variants(m: str) -> list[str]:
    m = m.replace("®", "").replace("™", "").strip()
    out = [m]
    k = m.find(" (")
    if k > 0 and m.endswith(")"):
        out += [m[:k].strip(), m[k + 2:-1].strip()]
    return out


# ---------------------------------------------------------------- build the gap list
def build():
    st = _load("st", ROOT / "pipeline" / "status.py")
    link = _load("link", ROOT / "pipeline" / "hekserij_link.py")
    norm, loose, surf = st.norm, link.loose, st.load_tags()

    by_cid, by_name = {}, {}
    for r in st.jsonl(st.PUBCHEM):
        if not r.get("excluded") and r.get("molecule_cid"):
            by_cid.setdefault(str(r["molecule_cid"]), set()).add(r.get("tag"))
    for r in st.jsonl(st.PHYSDESC):
        if (not r.get("needs_review") or r.get("review_decision") == "approve") and r.get("molecule_cid"):
            by_cid.setdefault(str(r["molecule_cid"]), set()).add(r.get("tag"))
    def add(m, tags):
        for v in corpus_variants(m):
            if v:
                by_name.setdefault(norm(v), set()).update(tags)
    exk = st.excluded_keys()          # retired rows (exclude_quotes.py) do not count as coverage
    for r in st.jsonl(st.REVIEW):
        if r.get("decision") == "approve" and (r["source_id"], " ".join((r.get("sentence") or "").split())) not in exk:
            tags = {surf[d.lower()] for d in (r.get("descriptors") or []) if d.lower() in surf}
            for m in r.get("molecules") or []:
                add(m, tags)
    if st.PASSAGE.exists():
        for r in st.jsonl(st.PASSAGE):
            if r.get("review_decision") == "approve":
                add(r["molecule"], {surf[d.lower()] for d in r["descriptors"] if d.lower() in surf})
    if st.TARGETED.exists():            # targeted_rows.py, 2026-09-26
        for r in st.jsonl(st.TARGETED):
            if r.get("review_decision") == "approve":
                add(r["molecule"], {surf[d.lower()] for d in r["descriptors"] if d.lower() in surf})
    by_loose = {}
    for k, v in by_name.items():
        by_loose.setdefault(loose(k), set()).update(v)

    comp = {}            # cid -> compound record
    for shop in SHOPS:
        d = ROOT / "corpus" / shop
        cache = json.loads((d / "pubchem-cache.json").read_text(encoding="utf-8"))
        for r in csv.DictReader(open(d / "cas.tsv", encoding="utf-8"), delimiter="\t"):
            if r["single_compound"] != "yes" or not r["cas"]:
                continue
            cids = cache["cid"].get(r["cas"]) or []
            if not cids:
                continue
            cid = str(cids[0])
            c = comp.setdefault(cid, {"cid": cid, "cas": set(), "products": [], "shops": set(),
                                      "inci": set(), "syn": []})
            c["cas"].add(r["cas"]); c["shops"].add(shop); c["products"].append(r["name"])
            if r.get("inci"):
                c["inci"].add(r["inci"])
            if not c["syn"]:
                bad = link.BAD_SYNONYM.get(r["cas"], set())
                c["syn"] = [x for x in cache["syn"].get(cid, []) if x.lower() not in bad]

    rows, n = [], {"in corpus": 0, "gap": 0}
    for cid, c in comp.items():
        plain = list(dict.fromkeys(c["products"] + sorted(c["inci"]) + c["syn"]))
        cleaned = [v for p in c["products"] for v in shop_variants(p) if v not in plain]
        route, tags = "", set()
        if cid in by_cid:
            route, tags = "pubchem CID", by_cid[cid]
        for label, names in (("name", plain), ("CLEANED name", cleaned)):
            if route:
                break
            for s in names:
                if s and norm(s) in by_name:
                    route, tags = f"{label}: {s}", by_name[norm(s)]; break
            if route:
                break
            for s in names:
                if s and len(loose(s)) > 5 and loose(s) in by_loose:
                    route, tags = f"loose {label}: {s}", by_loose[loose(s)]; break
        status = "in corpus" if route else "gap"
        n[status] += 1
        rows.append({"cid": cid, "cas": ", ".join(sorted(c["cas"])), "products": " | ".join(c["products"]),
                     "shops": ", ".join(sorted(c["shops"])), "status": status, "matched_by": route,
                     "corpus_tags": ", ".join(sorted(t for t in tags if t))})
    rows.sort(key=lambda r: (r["status"], r["products"].lower()))
    OUTD.mkdir(exist_ok=True)
    with open(OUTD / "gaps.tsv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t"); w.writeheader(); w.writerows(rows)
    both = sum(1 for r in rows if r["status"] == "gap" and "," in r["shops"])
    print(f"{len(rows)} distinct compounds (single, with a CID) across {', '.join(SHOPS)}: "
          f"in corpus {n['in corpus']} · gap {n['gap']} (of which sold by both shops: {both})")
    print("matched only through CLEANED names — check these by eye:")
    for r in rows:
        if "CLEANED" in r["matched_by"]:
            print(f"   {r['products'][:50]:<52}{r['matched_by']}")
    print(f"written -> {(OUTD / 'gaps.tsv').relative_to(ROOT)}")


# ---------------------------------------------------------------- origin patents
def get_json(url, tries=5):
    req = urllib.request.Request(url, headers={"User-Agent": "OpenScent/0.1 (research corpus; github.com/VanPez)"})
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code not in (429, 500, 502, 503, 504) or k == tries - 1:
                raise
            print(f"    HTTP {e.code}, retry in {10 * 2 ** k}s"); time.sleep(10 * 2 ** k)
        finally:
            time.sleep(random.uniform(1.0, 2.0))


def xrefs():
    gaps = [r for r in csv.DictReader(open(OUTD / "gaps.tsv", encoding="utf-8"), delimiter="\t") if r["status"] == "gap"]
    x = json.loads(XREFS.read_text(encoding="utf-8")) if XREFS.exists() else {}
    todo = [r["cid"] for r in gaps if r["cid"] not in x]
    print(f"{len(gaps)} gap compounds, {len(todo)} to query")
    for i, cid in enumerate(todo, 1):
        j = get_json(f"{PUG}/compound/cid/{cid}/xrefs/PatentID/JSON") or {}
        info = (j.get("InformationList") or {}).get("Information") or [{}]
        x[cid] = info[0].get("PatentID", [])
        if i % 5 == 0 or i == len(todo):
            tmp = XREFS.with_suffix(".json.tmp"); tmp.write_text(json.dumps(x), encoding="utf-8"); os.replace(tmp, XREFS)
            print(f"  {i}/{len(todo)}")
    print("done")


def pkey(pid: str):
    """US patent id -> (kind, number) with the kind code dropped; None if not US.
    Granted: ('P', 3929676). Application: ('A', 20050123456) — year + 7-digit serial,
    whatever padding the source used (normalise_ids.py has the same rule)."""
    s = pid.replace("-", "").upper()
    m = re.match(r"^US(RE)?(\d+)([A-Z]\d?)?$", s)
    if not m:
        return None
    re_, num = m.group(1), m.group(2)
    if re_:
        return ("RE", int(num))
    if len(num) >= 10 and num.startswith("20"):
        return ("A", int(num[:4] + num[4:].rjust(7, "0")))
    return ("P", int(num))


def origin(per=3):
    gaps = {r["cid"]: r for r in csv.DictReader(open(OUTD / "gaps.tsv", encoding="utf-8"), delimiter="\t") if r["status"] == "gap"}
    x = json.loads(XREFS.read_text(encoding="utf-8"))
    held = {pkey(p) for p in json.loads((ROOT / "corpus" / "patent-ids.json").read_text())} - {None}
    out, ids, none, early_held = {}, set(), [], 0
    for cid, r in gaps.items():
        us = {}
        for p in x.get(cid, []):
            k = pkey(p)
            if k and k[0] in ("P", "A"):
                us.setdefault(k, p.replace("-", ""))
        if not us:
            none.append(r["products"]); continue
        granted = sorted(k for k in us if k[0] == "P")
        apps = sorted(k for k in us if k[0] == "A")
        if granted and granted[0] in held:
            early_held += 1
        cand = [us[k] for k in (granted[:per] + apps[:1]) if k not in held]
        out[cid] = {"products": r["products"], "us_docs": len(us), "held": sum(k in held for k in us),
                    "earliest": [us[k] for k in granted[:per] + apps[:1]], "to_fetch": cand}
        ids.update(cand)
    (OUTD / "origin-candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUTD / "origin-ids.json").write_text(json.dumps(sorted(ids), indent=1), encoding="utf-8")
    print(f"{len(gaps)} gap compounds · {len(out)} have ≥1 US patent in PubChem · {len(none)} have none")
    print(f"earliest granted US patent already held: {early_held} compounds")
    print(f"docs to fetch (≤{per} earliest granted + earliest application, not held): {len(ids)}")
    print("\nper compound: US docs / held / to fetch   earliest")
    for cid, v in sorted(out.items(), key=lambda kv: kv[1]["products"].lower()):
        print(f"  {v['products'][:34]:<36}{v['us_docs']:>5}{v['held']:>5}{len(v['to_fetch']):>4}   {' '.join(v['earliest'][:3])}")
    if none:
        print("\nno US patent listed in PubChem: " + "; ".join(p[:30] for p in none))
    print(f"\nwritten -> corpus/gaps/origin-candidates.json, origin-ids.json")


# ---------------------------------------------------------------- measurement before the fetch
# 2026-09-26, first --origin run: PubChem links every gap compound to US patents WE ALREADY
# HOLD — median 251 per compound — and for 41 of them the earliest granted US patent is
# among them. So the text is mostly in hand; what is missing is a describing sentence the
# extractor kept. Two questions before fetching 260 more documents:
#   HELD    in the earliest patents we hold for each compound, is there an odour sentence
#           about it that we dropped — and why (formula number, table, name variant)?
#   PILOT   one earliest NOT-held patent per compound (1961+ only: older numbers are OCR scans
#           where text-mining is noisy — Iso E Super "in" an 1895 patent): rows per document?
# --plan (Mac) writes corpus/gaps/origin-plan.json; --probe (Hetzner) fetches the pilot into
# corpus/raw-origin/ (NOT corpus/raw: nothing joins the corpus before Ivan decides) and dumps
# every odour sentence of every planned document to corpus/gaps/origin-sentences.jsonl.
GENERIC = {"perfume", "parfum", "fragrance", "flavor", "flavour", "aroma chemical", "dipropylene glycol"}
FIRST_1961 = 2966681          # first US patent number issued in 1961


def canon(pid: str) -> str:
    """Granted US id as our corpus writes it: no hyphens, no zero padding ('US-06987084-B2' -> 'US6987084B2')."""
    m = re.match(r"^US0*(\d+)([A-Z]\d?)?$", pid.replace("-", "").upper())
    return f"US{m.group(1)}{m.group(2) or ''}" if m else pid.replace("-", "")


def search_names(c_products, inci, syns, bad):
    cands = [v for p in c_products for v in shop_variants(p)] + list(inci) + syns[:15]
    names = []
    for n in cands:
        n = (n or "").strip()
        if not n or n.lower() in bad or n.lower() in GENERIC:
            continue
        if re.fullmatch(r"[\d\-]+", n) or sum(ch.isalpha() for ch in n) < 6:
            continue
        if ":" in n or re.match(r"(DTX|FEMA|UNII|EINECS|NSC|CHEBI|SCHEMBL|AKOS|MFCD|CAS)", n, re.I):
            continue
        if n.lower() not in {x.lower() for x in names}:
            names.append(n)
    return names


def plan(per=3):
    link = _load("link", ROOT / "pipeline" / "hekserij_link.py")
    gaps = {r["cid"]: r for r in csv.DictReader(open(OUTD / "gaps.tsv", encoding="utf-8"), delimiter="\t") if r["status"] == "gap"}
    x = json.loads(XREFS.read_text(encoding="utf-8"))
    held = {}
    for p in json.loads((ROOT / "corpus" / "patent-ids.json").read_text()):
        k = pkey(p)
        if k:
            held[k] = p
    info = {}                                   # cid -> products, inci, syns, bad
    for shop in SHOPS:
        d = ROOT / "corpus" / shop
        cache = json.loads((d / "pubchem-cache.json").read_text(encoding="utf-8"))
        for r in csv.DictReader(open(d / "cas.tsv", encoding="utf-8"), delimiter="\t"):
            cids = cache["cid"].get(r["cas"]) or [] if r["cas"] else []
            if not cids or str(cids[0]) not in gaps:
                continue
            cid = str(cids[0])
            i = info.setdefault(cid, {"products": [], "inci": set(), "syn": cache["syn"].get(cid, []), "bad": set()})
            i["products"].append(r["name"]); i["bad"] |= link.BAD_SYNONYM.get(r["cas"], set())
            if r.get("inci"):
                i["inci"].add(r["inci"])
    out, n_held, n_pilot = {}, set(), set()
    for cid, g in gaps.items():
        us = {}
        for p in x.get(cid, []):
            k = pkey(p)
            if k and k[0] == "P":
                us.setdefault(k, p)
        granted = sorted(us)
        held_early = [held[k] for k in granted if k in held][:per]
        pilot = [canon(us[k]) for k in granted[:per] if k not in held and k[1] >= FIRST_1961][:1]
        i = info[cid]
        out[cid] = {"product": g["products"], "names": search_names(i["products"], i["inci"], i["syn"], i["bad"]),
                    "held_docs": held_early, "pilot_docs": pilot}
        n_held.update(held_early); n_pilot.update(pilot)
    (OUTD / "origin-plan.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} gap compounds · held earliest docs to read {len(n_held)} · pilot docs to fetch {len(n_pilot)}")
    print(f"compounds with no search name: {[v['product'] for v in out.values() if not v['names']]}")
    print(f"written -> corpus/gaps/origin-plan.json")


def probe():
    H = _load("harvest", ROOT / "pipeline" / "harvest.py")
    import html as _html
    P = json.loads((OUTD / "origin-plan.json").read_text(encoding="utf-8"))
    RO = ROOT / "corpus" / "raw-origin"; RO.mkdir(parents=True, exist_ok=True)
    pilot = sorted({d for v in P.values() for d in v["pilot_docs"]})
    todo = [d for d in pilot if not (RO / f"{d}.txt").exists()]
    print(f"pilot: {len(pilot)} docs, {len(todo)} to fetch into {RO}")
    for n, pid in enumerate(todo, 1):
        try:
            page = H._get(f"https://patents.google.com/patent/{pid}/en")
            m = H.DESC.search(page)
            text = re.sub(r"\s+", " ", _html.unescape(H.TAGS.sub(" ", m.group(0)))).strip() if m else ""
            if len(text) >= 500:
                (RO / f"{pid}.txt").write_text(text, encoding="utf-8")
            else:
                print(f"  {pid}: no description text")
        except Exception as e:
            print(f"  {pid} FAILED: {e}")
        if n % 10 == 0:
            print(f"  {n}/{len(todo)}")
        time.sleep(random.uniform(*H.DELAY))
    out = open(OUTD / "origin-sentences.jsonl", "w", encoding="utf-8")
    n_docs = n_sent = 0
    for cid, v in P.items():
        rx = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(map(re.escape, sorted(v["names"], key=len, reverse=True))) + r")(?![A-Za-z0-9])", re.I) if v["names"] else None
        for kind, docs, base in (("held", v["held_docs"], H.RAW), ("pilot", v["pilot_docs"], RO)):
            for d in docs:
                f = base / f"{d}.txt"
                if not f.exists():
                    out.write(json.dumps({"cid": cid, "product": v["product"], "set": kind, "doc": d, "missing": True}) + "\n")
                    continue
                n_docs += 1
                text = H.norm(f.read_text(encoding="utf-8", errors="ignore"))
                mentions = len(rx.findall(text)) if rx else 0
                for s in H.SENT.split(text):
                    if not H.ODOUR.search(s):
                        continue
                    hit = sorted({m.group(0) for m in rx.finditer(s)}) if rx else []
                    descr = bool(H.DESCR.search(s) or H.DESCR_COLON.search(s))
                    # keep: every descriptive odour sentence, plus any odour sentence naming the
                    # compound whatever its length (tables arrive as one long "sentence")
                    if (descr and 25 < len(s) < 600) or hit:
                        out.write(json.dumps({"cid": cid, "product": v["product"], "set": kind, "doc": d,
                                              "doc_mentions": mentions, "names_in_sentence": hit, "descr": descr,
                                              "len": len(s), "sentence": s[:1500]}, ensure_ascii=False) + "\n")
                        n_sent += 1
    out.close()
    print(f"{n_docs} documents read, {n_sent} odour sentences -> corpus/gaps/origin-sentences.jsonl")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--xrefs" in a:
        xrefs()
    elif "--origin" in a:
        origin()
    elif "--plan" in a:
        plan()
    elif "--probe" in a:
        probe()
    else:
        build()
