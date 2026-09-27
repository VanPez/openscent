#!/usr/bin/env python3
"""site_build.py — build docs/preview.html: what OpenScent looks like to someone browsing it.

WHAT THE PAGE IS
----------------
A single self-contained HTML file in the GenesisL1 family design (../THEME.md, same as the
aroma-index). It shows the 208 commercial perfumery materials of corpus/catalog/materials.tsv:
for each, its identity and properties, and EVERY piece of corpus evidence behind its odour tags,
quoted verbatim with a link to the source. Materials with no admissible description are shown
too, with an empty, labelled slot where licensed descriptors would appear if a rights holder
releases them. It is the example to send with the permission emails.

WHAT IT IS NOT
--------------
Not the corpus release (that is CC0 files: rows, catalogue, ontology). Not generated text:
every odour word on the page is a verbatim substring of the quoted source, highlighted where it
sits. Figures in the header come from status.py, run at build time — never typed in.

USAGE   python3 pipeline/site_build.py            # -> docs/preview.html
"""
from __future__ import annotations
import collections, csv, datetime, html, importlib.util, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "preview.html"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "pipeline" / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def status_figures():
    out = subprocess.run([sys.executable, str(ROOT / "pipeline" / "status.py")], capture_output=True, text=True).stdout
    m = re.search(r"COMBINED\s+(\d+) of (\d+) at the bar\s+(\d+) molecules", out)
    if not m:
        sys.exit("could not read the COMBINED line from status.py — refusing to invent figures")
    return {"tags_at_bar": int(m[1]), "tags": int(m[2]), "molecules": int(m[3])}


def evidence_pools(st, surf, variants):
    """name-keyed and CID-keyed evidence, exactly the rows status.py counts. Names are indexed
    under every gaps.corpus_variants() form ("Timberol (1-(2,2,6-…)hexan-3-ol)" -> both halves)."""
    by_name, by_cid = collections.defaultdict(list), collections.defaultdict(list)
    exk = st.excluded_keys()
    ev = []
    def tags_of(ds):
        return sorted({surf[d.lower()] for d in ds if d.lower() in surf})
    for r in st.jsonl(st.REVIEW):
        if r.get("decision") != "approve":
            continue
        s = r.get("sentence") or ""
        if (r["source_id"], " ".join(s.split())) in exk:
            continue
        ds = [d for d in (r.get("descriptors") or []) if d.lower() in surf]
        for m in r.get("molecules") or []:
            ev.append({"kind": "patent", "src": r["source_id"], "quote": s, "mol": m, "descs": ds, "tags": tags_of(ds)})
    if st.PASSAGE.exists():
        for r in st.jsonl(st.PASSAGE):
            if r.get("review_decision") == "approve":
                ds = [d for d in r["descriptors"] if d.lower() in surf]
                ev.append({"kind": "passage", "src": r["source_id"], "quote": r["sentence"], "ante": r["antecedent"],
                           "mol": r["molecule"], "anaphor": r["anaphor"], "descs": ds, "tags": tags_of(ds)})
    if st.TARGETED.exists():
        for r in st.jsonl(st.TARGETED):
            if r.get("review_decision") == "approve":
                ds = [d for d in r["descriptors"] if d.lower() in surf]
                ev.append({"kind": "patent", "src": r["source_id"], "quote": r["sentence"], "mol": r["molecule"],
                           "descs": ds, "tags": tags_of(ds)})
    for e in ev:
        for v in variants(e["mol"]):
            if e not in by_name[st.norm(v)]:
                by_name[st.norm(v)].append(e)
    # PubChem rows: one quote may yield several tags -> merge per (cid, quote)
    merged = {}
    for r in st.jsonl(st.PUBCHEM):
        if r.get("excluded") or not r.get("molecule_cid"):
            continue
        k = (str(r["molecule_cid"]), r["quote"])
        e = merged.setdefault(k, {"kind": "hsdb", "src": r.get("source", "HSDB"), "url": r.get("source_url", ""),
                                  "quote": r["quote"], "mol": r.get("molecule_name", ""), "descs": [], "tags": []})
        if r.get("span") and r["span"] not in e["descs"]:
            e["descs"].append(r["span"])
        if r.get("tag") and r["tag"] not in e["tags"]:
            e["tags"].append(r["tag"])
    for r in st.jsonl(st.PHYSDESC):
        if (r.get("needs_review") and r.get("review_decision") != "approve") or not r.get("molecule_cid"):
            continue
        k = (str(r["molecule_cid"]), r["quote"])
        e = merged.setdefault(k, {"kind": "physdesc", "src": r.get("source_label") or r.get("source", ""),
                                  "url": r.get("source_url", ""), "quote": r["quote"], "mol": r.get("molecule_name", ""),
                                  "descs": [], "tags": []})
        if r.get("span") and r["span"] not in e["descs"]:
            e["descs"].append(r["span"])
        if r.get("tag") and r["tag"] not in e["tags"]:
            e["tags"].append(r["tag"])
    for (cid, _), e in merged.items():
        e["tags"].sort()
        by_cid[cid].append(e)
    return by_name, by_cid



# ---------------------------------------------------------------- scent map
# Display grouping ONLY — for colouring dots. Not part of the ontology and not a claim: the
# map's positions come from the corpus tags alone; colour is a reading aid.
FAMILIES = [
    ("Floral", "#e0529c", ["floral", "rose", "lily", "jasmine", "geranium", "violet"]),
    ("Fruity", "#f3722c", ["fruity", "apple", "pear", "berry", "pineapple", "peach", "juicy"]),
    ("Citrus", "#e9b10c", ["citrus", "lemon", "lime", "orange", "grapefruit"]),
    ("Green & herbal", "#43aa8b", ["green", "herbal", "lavender", "mint", "camphoraceous", "aromatic", "anisic", "hay", "eucalyptus"]),
    ("Woody & earthy", "#8d6346", ["woody", "sandalwood", "cedar", "patchouli", "earthy", "dry", "musty"]),
    ("Amber & musk", "#7b61ff", ["amber", "musk", "animalic", "powdery", "leather", "tobacco", "balsamic", "oriental"]),
    ("Sweet & gourmand", "#b5651d", ["sweet", "vanilla", "honey", "creamy", "coconut", "nutty", "coffee"]),
    ("Spicy & warm", "#d62828", ["spicy", "warm", "smoke"]),
    ("Fresh & aldehydic", "#2fa6d6", ["fresh", "aldehydic", "waxy", "fatty", "oily", "marine", "watery", "clean", "metallic", "wet"]),
    ("Sharp & other", "#6c757d", ["pungent", "acid", "chlorine", "soft", "neutral"]),
]
GENERIC = {"sweet", "fresh", "floral", "fruity", "pungent", "aromatic", "warm", "soft", "dry", "green"}


def tsne(X, perplexity=12.0, iters=1000, seed=20260926):
    """Exact t-SNE (van der Maaten & Hinton 2008) in numpy. Seeded: the page is reproducible."""
    import numpy as np
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    Xn = X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)
    D = np.clip(1 - Xn @ Xn.T, 0, 2)                      # cosine distance
    P = np.zeros((n, n)); target = np.log(perplexity)
    for i in range(n):
        lo, hi, beta = 1e-20, 1e20, 1.0
        d = np.delete(D[i], i)
        for _ in range(60):
            p = np.exp(-d * beta); sp = p.sum() or 1e-12
            H = np.log(sp) + beta * (d * p).sum() / sp
            if abs(H - target) < 1e-5:
                break
            if H > target: lo = beta; beta = beta * 2 if hi == 1e20 else (beta + hi) / 2
            else: hi = beta; beta = (beta + lo) / 2
        P[i, np.arange(n) != i] = p / sp
    P = (P + P.T) / (2 * n); P = np.maximum(P, 1e-12)
    Y = rng.normal(0, 1e-4, (n, 2)); V = np.zeros_like(Y); G = np.ones_like(Y)
    for it in range(iters):
        PP = P * (12 if it < 250 else 1)
        sq = (Y ** 2).sum(1); num = 1 / (1 + sq[:, None] + sq[None, :] - 2 * Y @ Y.T); np.fill_diagonal(num, 0)
        Q = np.maximum(num / num.sum(), 1e-12)
        grad = 4 * (((PP - Q) * num)[:, :, None] * (Y[:, None, :] - Y[None, :, :])).sum(1)
        mom = .5 if it < 250 else .8
        G = (G + .2) * ((grad > 0) != (V > 0)) + G * .8 * ((grad > 0) == (V > 0)); G = np.maximum(G, .01)
        V = mom * V - 200 * G * grad; Y = Y + V; Y -= Y.mean(0)
    return Y


def scent_map(mats):
    import numpy as np
    pts = [m for m in mats if m["tags"]]
    tags = sorted({t for m in pts for t in m["tags"]})
    ti = {t: i for i, t in enumerate(tags)}
    X = np.zeros((len(pts), len(tags)))
    for r, m in enumerate(pts):
        for e in m["ev"]:
            for t in e["tags"]:
                X[r, ti[t]] += 1
    X = np.sqrt(X)                                        # one very repeated tag must not drown the rest
    Y = tsne(X)
    # robust scaling: a few isolated materials (lone aldehydes) would otherwise squeeze the rest
    # into the middle. 3rd-97th percentile spans the frame; outliers sit on its edge.
    lo, hi = np.percentile(Y, 3, axis=0), np.percentile(Y, 97, axis=0)
    Y = np.clip((Y - lo) / np.maximum(hi - lo, 1e-9), -0.04, 1.04)
    Y = (Y + 0.04) / 1.08
    fam_of = {t: k for k, (_, _, ts) in enumerate(FAMILIES) for t in ts}
    out = []
    for r, m in enumerate(pts):
        score = collections.Counter()
        for t, i in ti.items():
            if X[r, i] and t in fam_of:
                score[fam_of[t]] += X[r, i] * (.6 if t in GENERIC else 1)
        f = score.most_common(1)[0][0] if score else len(FAMILIES) - 1
        out.append({"cid": m["cid"], "x": round(float(Y[r, 0]), 4), "y": round(float(Y[r, 1]), 4), "f": f})
    return {"fam": [[n, c] for n, c, _ in FAMILIES], "pts": out}


SPEC = [("appearance", "Appearance"), ("density", "Density"), ("melting_point", "Melting pt."),
        ("boiling_point", "Boiling pt."), ("flash_point", "Flash pt."), ("vapour_pressure", "Vapour pr."),
        ("logp_measured", "log Kow"), ("odour_threshold", "Odour thr.")]
SRC_SHORT = [("Hazardous Substances", "HSDB"), ("CAMEO", "CAMEO"), ("Department of Energy", "DOE PAC"),
             ("OSHA", "OSHA"), ("Occupational Safety", "OSHA"), ("NIOSH", "NIOSH"), ("EPA", "EPA"), ("NTP", "NTP")]


def spec_fields(r):
    """measured values from materials.tsv, value i paired with source i, at most 2 per field"""
    out = {}
    for key, _ in SPEC:
        vals, srcs = r.get(key, ""), r.get(key + "_source", "")
        if not vals:
            continue
        pairs = []
        for v, sname in zip(vals.split(" || "), srcs.split(" || ")):
            short = next((b for a, b in SRC_SHORT if a in sname), sname[:12])
            pairs.append([v[:140] + ("…" if len(v) > 140 else ""), short])
        out[key] = pairs[:2]
    return out


def build():
    st, g = _load("status"), _load("gaps")
    link = g._load("link", ROOT / "pipeline" / "hekserij_link.py")
    surf = st.load_tags()
    fig = status_figures()
    by_name, by_cid = evidence_pools(st, surf, g.corpus_variants)
    by_loose = collections.defaultdict(list)
    for k, v in by_name.items():
        by_loose[link.loose(k)].extend(v)

    names = collections.defaultdict(list)          # cid -> every name we know it by
    for shop in g.SHOPS:
        d = ROOT / "corpus" / shop
        cache = json.loads((d / "pubchem-cache.json").read_text(encoding="utf-8"))
        for r in csv.DictReader(open(d / "cas.tsv", encoding="utf-8"), delimiter="\t"):
            cids = (cache["cid"].get(r["cas"]) or []) if r["cas"] else []
            if not cids:
                continue
            cid = str(cids[0]); bad = link.BAD_SYNONYM.get(r["cas"], set())
            names[cid] += g.shop_variants(r["name"]) + ([r["inci"]] if r.get("inci") else [])
            names[cid] += [s for s in cache["syn"].get(cid, []) if s.lower() not in bad]

    cf = ROOT / "corpus" / "catalog" / "conformers.json"      # catalog.py --fetch-3d (Hetzner)
    conf = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else {}
    mats, n_ev, missing = [], 0, []
    for r in csv.DictReader(open(ROOT / "corpus" / "catalog" / "materials.tsv", encoding="utf-8"), delimiter="\t"):
        cid = r["cid"]
        found, seen = [], set()
        for e in by_cid.get(cid, []):
            k = (e["src"], e["quote"]); seen.add(k); found.append(e)
        for n in dict.fromkeys(names.get(cid, [])):
            hits = by_name.get(st.norm(n), [])
            if not hits and len(link.loose(n)) > 5:
                hits = by_loose.get(link.loose(n), [])
            for e in hits:
                k = (e["src"], e["quote"])
                if k not in seen:
                    seen.add(k); found.append(e)
        described = r["descriptor_status"] == "described in the corpus"
        if described and not found:
            missing.append(r["common_name"])
        n_ev += len(found)
        tagc = collections.Counter(t for e in found for t in e["tags"])
        mats.append({
            "cid": cid, "name": r["common_name"], "title": r["pubchem_title"], "trade": r["commercial_names"],
            "cas": r["cas"], "iupac": r["iupac_name"], "formula": r["formula"], "mw": r["mw"], "xlogp": r["xlogp3"],
            "tpsa": r["tpsa"], "hbd": r["hbd"], "hba": r["hba"], "smiles": r["smiles"], "inchikey": r["inchikey"],
            "ec": r.get("ec_number", ""), "fema": r.get("fema_number", ""), "allergen": r.get("eu_allergen", ""),
            "spec": spec_fields(r),
            "described": described, "note": r["status_note"],
            "tags": [t for t, _ in tagc.most_common()], "ev": found, "c3d": conf.get(cid) if conf else False,   # False = not fetched yet, None = PubChem has none
        })
    if missing:
        sys.exit(f"described in the catalogue but no evidence found for: {missing} — matching drifted from gaps.py")
    n_desc = sum(m["described"] for m in mats)
    data = {"fig": fig, "n": len(mats), "n_desc": n_desc, "n_ev": n_ev,
            "built": datetime.date.today().isoformat(), "mats": mats, "map": scent_map(mats)}
    page = TEMPLATE.replace("/*__SPEC__*/null", json.dumps(SPEC)).replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"{len(mats)} materials · {n_desc} described · {n_ev} evidence quotes · corpus {fig['molecules']} molecules, "
          f"{fig['tags_at_bar']}/{fig['tags']} tags at the bar")
    print(f"3D conformers embedded: {sum(1 for m in mats if m['c3d'])} of {len(mats)}"
          + ("" if conf else "  (none: run catalog.py --fetch-3d on Hetzner first)"))
    print(f"written -> {OUT.relative_to(ROOT)}  ({OUT.stat().st_size // 1024} KB)")


TEMPLATE = r"""<!DOCTYPE html>
<!--
  OpenScent — preview of the materials browser.
  WHAT: the 208 commercial perfumery materials of corpus/catalog/materials.tsv, each with its identity,
  public-domain properties and every piece of OpenScent evidence behind its odour tags, quoted verbatim.
  DATA: embedded below, built by pipeline/site_build.py from the corpus files and status.py. No network
  calls; links go out to Google Patents (US patents) and PubChem / NOAA CAMEO (government sources).
  RULE: every odour word shown is a verbatim substring of the quoted source (highlighted in place).
  DESIGN: GenesisL1 family (THEME.md). Single file, system fonts, no external assets.
  LOGO: aromatic ring with scent rising (2026-09-26), inline here and in docs/logo.svg.
-->
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenScent — Materials Preview</title><link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%2024%2024%22%3E%3Cg%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M9.5%209.2%20L13.8%2011.7%20L13.8%2016.7%20L9.5%2019.2%20L5.2%2016.7%20L5.2%2011.7%20Z%22%20stroke%3D%22%2307111d%22%20stroke-width%3D%221.5%22/%3E%3Ccircle%20cx%3D%229.5%22%20cy%3D%2214.2%22%20r%3D%222.3%22%20stroke%3D%22%23245cff%22%20stroke-width%3D%221.3%22/%3E%3Cpath%20d%3D%22M13.8%2011.7%20C15.9%2010.6%2014.7%208.4%2016.7%207.2%20C18.7%206%2017.7%203.8%2019.9%202.8%22%20stroke%3D%22%23245cff%22%20stroke-width%3D%221.5%22/%3E%3Cpath%20d%3D%22M16.9%2013.2%20C18.5%2012.4%2017.7%2010.8%2019.3%209.9%20C20.7%209.1%2020.2%207.7%2021.6%207%22%20stroke%3D%22%23245cff%22%20stroke-width%3D%221.1%22%20opacity%3D%22.5%22/%3E%3C/g%3E%3C/svg%3E"><style>
:root{--paper:#f5f7f9;--card:#fff;--ink:#07111d;--mut:#687383;--faint:#718196;--line:#dce4ee;--line-strong:rgba(29,52,78,.3);
 --blue:#245cff;--blue-deep:#1647d9;--blue-pale:#eef3ff;--amber:#9a6a14;--amber-pale:#fdf6e9;--teal:#0f8f7f;--red:#bc4b47;
 --sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
 --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;--shadow:0 18px 50px rgba(28,60,98,.067);--page:1440px}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--blue)}
.topbar{position:sticky;top:0;z-index:5;min-height:72px;border-bottom:1px solid rgba(7,17,29,.1);background:rgba(255,255,255,.94);backdrop-filter:blur(6px)}
.topbar-in{max-width:var(--page);margin:0 auto;padding:10px 28px;min-height:72px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:12px}
.glyph{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;background:#fff;border:1px solid var(--line-strong)}
.wordmark b{font-size:17px;font-weight:700;letter-spacing:-.01em;display:block}
.wordmark span{font-family:var(--mono);font-size:10px;letter-spacing:.14em;color:var(--mut);text-transform:uppercase}
.badge{font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;padding:5px 10px;border:1px solid var(--line-strong);color:var(--mut);background:#fff;white-space:nowrap}
.badge.proto{color:var(--amber);border-color:rgba(154,106,20,.45);background:var(--amber-pale)}
.badge.ok{color:var(--teal);border-color:rgba(15,143,127,.45);background:rgba(15,143,127,.07)}
.wrap{max-width:var(--page);margin:0 auto;padding:0 28px 64px}.hero{margin:26px 0}
.lab{display:flex;align-items:center;gap:10px;color:var(--mut);font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.14em}
.dash{width:18px;height:2px;background:var(--blue)}h1{font-size:34px;letter-spacing:-.02em;margin:10px 0 6px;font-weight:700;line-height:1.15}
.sub{color:var(--mut);font-size:15px;max-width:82ch}
.stats{display:grid;grid-template-columns:repeat(4,1fr);margin:22px 0;background:#fff;border:1px solid var(--line-strong);box-shadow:var(--shadow)}
.stat{padding:15px 18px}.stat+.stat{border-left:1px solid var(--line)}
.stat .k{color:var(--mut);font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.1em}
.stat .v{font-family:var(--mono);font-size:20px;font-weight:500;margin-top:5px}.stat .v small{font-size:12px;color:var(--mut)}
.note{background:var(--blue-pale);border:1px solid rgba(36,92,255,.25);padding:12px 16px;font-size:13.5px;color:#243a63;margin-bottom:22px}
.bar{position:sticky;top:72px;z-index:4;display:flex;align-items:center;gap:10px;background:var(--paper);padding:12px 0 14px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.bar input{flex:1;min-width:220px;font:14px var(--sans);padding:11px 14px;border:1px solid var(--line-strong);background:#fff;color:var(--ink);border-radius:9px;outline:none}
.bar input:focus{border-color:var(--blue);box-shadow:0 0 0 3px var(--blue-pale)}
.bar select{font:13px var(--mono);padding:10px 12px;border:1px solid var(--line-strong);border-radius:9px;background:#fff;color:var(--ink)}
.seg{display:flex;gap:4px}.seg button{font:600 12px var(--mono);border:0;background:none;color:var(--mut);padding:6px 12px;border-radius:999px;cursor:pointer}
.seg button:hover{background:rgba(7,17,29,.05);color:var(--ink)}.seg button.on{background:var(--blue);color:#fff}
.count{font-family:var(--mono);font-size:11px;color:var(--mut);white-space:nowrap}
.panel{background:#fff;border:1px solid var(--line-strong);box-shadow:var(--shadow);margin-top:16px;border-top:3px solid var(--blue)}
.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:980px}
th{font:500 10px var(--mono);text-transform:uppercase;letter-spacing:.09em;color:var(--mut);text-align:left;padding:10px 18px;border-bottom:1px solid var(--line-strong);background:#fbfcfd}
td{font-size:13.5px;padding:9px 18px;border-top:1px solid var(--line);vertical-align:top}
tr.row{cursor:pointer}tr.row:hover td{background:#f5f8fc}tr.row.open td{background:var(--blue-pale)}
td.num{font-family:var(--mono);text-align:right;white-space:nowrap}th.num{text-align:right}
.nm b{font-weight:600}.nm small{display:block;color:var(--faint);font-size:12px}
.tag{display:inline-block;font:10px var(--mono);letter-spacing:.06em;text-transform:uppercase;padding:2px 7px;margin:0 4px 4px 0;border:1px solid rgba(15,143,127,.4);color:var(--teal);background:rgba(15,143,127,.06)}
.detail td{background:#fbfcfd;padding:18px}
.tag.click{cursor:pointer}.tag.click:hover{background:rgba(15,143,127,.16);border-color:var(--teal)}
.tag.on{background:var(--teal);color:#fff;border-color:var(--teal)}
.src{font:9.5px var(--mono);letter-spacing:.06em;color:var(--faint);border:1px solid var(--line);padding:0 4px;margin-left:4px;white-space:nowrap}
.allerg{border:1px solid rgba(154,106,20,.45);background:var(--amber-pale);color:#5b430f;font-size:12.5px;padding:8px 10px;margin-bottom:10px}
.allerg span{font:10.5px var(--mono);color:var(--amber)}
.nm .al{font:9.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--amber);border:1px solid rgba(154,106,20,.45);background:var(--amber-pale);padding:1px 5px;margin-left:6px;vertical-align:2px}
.dgrid{display:grid;grid-template-columns:minmax(260px,340px) 1fr;gap:22px}
dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:6px 14px;font-size:13px}dt{font:10px var(--mono);text-transform:uppercase;letter-spacing:.09em;color:var(--mut);padding-top:3px}
dd{margin:0;font-family:var(--mono);font-size:12px;word-break:break-all}dd.est{color:var(--faint)}
.h3{font:10px var(--mono);text-transform:uppercase;letter-spacing:.12em;color:var(--mut);margin:0 0 10px}
.ev{background:#fff;border:1px solid var(--line);border-left:3px solid var(--teal);padding:10px 14px;margin-bottom:10px}
.ev.passage{border-left-color:var(--blue)}
.evh{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px;font:11px var(--mono);color:var(--mut)}
.q{font-size:13.5px;line-height:1.6;color:#1d2a38}.q mark{background:var(--blue-pale);color:var(--blue-deep);padding:0 2px;font-weight:600}
.q u{text-decoration:none;border-bottom:2px solid rgba(15,143,127,.55)}
.ante{font-size:12.5px;color:var(--mut);margin-bottom:6px}
.empty{border:1px solid rgba(154,106,20,.45);background:var(--amber-pale);padding:12px 14px;font-size:13.5px;color:#5b430f;margin-bottom:12px}
.slot{border:1px dashed var(--line-strong);padding:12px 14px;font-size:13px;color:var(--mut);background:#fff}
.slot b{font:10px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink);display:block;margin-bottom:4px}
.nav{display:flex;gap:4px}.nav a{font:600 12px var(--mono);text-decoration:none;color:var(--mut);padding:6px 12px;border-radius:999px;letter-spacing:.02em}
.nav a:hover{background:rgba(7,17,29,.05);color:var(--ink)}.nav a.active{background:var(--blue);color:#fff}
.legend{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
.chip{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line-strong);background:#fff;padding:5px 10px;font-size:12.5px;cursor:pointer}
.chip.off{opacity:.35}.chip .dot{width:11px;height:11px;border-radius:50%}.chip .n{font:10px var(--mono);color:var(--mut)}
.mapbox{background:#fff;border:1px solid var(--line-strong);box-shadow:var(--shadow);border-top:3px solid var(--blue)}
.mapbox svg{width:100%;height:auto;display:block}.mapbox circle{cursor:pointer;stroke:#fff;stroke-width:1.5}
.mapbox circle:hover{stroke:var(--ink);stroke-width:2}
.tip{position:fixed;z-index:20;pointer-events:none;background:#07111d;color:#eaf1ff;border-radius:8px;padding:9px 11px;font-size:12px;max-width:280px;box-shadow:0 10px 30px rgba(0,0,0,.28);display:none}
.tip b{font-size:12.5px}.tip .f{font:10px var(--mono);color:#9db6e8;text-transform:uppercase;letter-spacing:.06em;margin:2px 0 5px}
.v3d{background:#fff;border:1px solid var(--line-strong);height:260px;margin-bottom:6px;touch-action:none;cursor:grab}
.v3d canvas{width:100%;height:100%;display:block}.v3d.none{display:grid;place-items:center;cursor:default;font:11px var(--mono);color:var(--faint);letter-spacing:.06em;text-transform:uppercase}
.hint{font:11px var(--mono);color:var(--faint);margin-bottom:14px}
footer{border-top:1px solid var(--line);margin-top:36px;padding-top:16px;color:var(--mut);font-size:12.5px;line-height:1.8}
@media(max-width:760px){.stats{grid-template-columns:1fr 1fr}.stat:nth-child(3){border-left:0}.stat:nth-child(n+3){border-top:1px solid var(--line)}.dgrid{grid-template-columns:1fr}}
@media(max-width:640px){.wrap,.topbar-in{padding-left:16px;padding-right:16px}h1{font-size:26px}.bar{position:static}.stats{grid-template-columns:1fr}.stat+.stat{border-left:0;border-top:1px solid var(--line)}}
</style></head><body>
<header class="topbar"><div class="topbar-in">
 <div class="brand"><div class="glyph"><svg width="24" height="24" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 9.2 L13.8 11.7 L13.8 16.7 L9.5 19.2 L5.2 16.7 L5.2 11.7 Z" stroke="#07111d" stroke-width="1.5"/><circle cx="9.5" cy="14.2" r="2.3" stroke="#245cff" stroke-width="1.3"/><path d="M13.8 11.7 C15.9 10.6 14.7 8.4 16.7 7.2 C18.7 6 17.7 3.8 19.9 2.8" stroke="#245cff" stroke-width="1.5"/><path d="M16.9 13.2 C18.5 12.4 17.7 10.8 19.3 9.9 C20.7 9.1 20.2 7.7 21.6 7" stroke="#245cff" stroke-width="1.1" opacity=".5"/></g></svg></div><div class="wordmark"><b>OpenScent</b><span>Odour corpus · materials</span></div></div>
 <nav class="nav" id="nav"><a href="#materials" data-v="materials" class="active">Materials</a><a href="#map" data-v="map">Scent map</a></nav>
 <span class="badge proto" id="topbadge"></span>
</div></header>
<main class="wrap">
 <section class="hero">
  <div class="lab"><span class="dash"></span>CC0 odour corpus · preview</div>
  <h1>What common perfumery materials smell like, and who said so</h1>
  <p class="sub">Every odour word here is quoted, word for word, from a public-domain source: a US patent or a US-government
   database. Click a material to see the sentences behind its tags. Materials with no public-domain description are
   listed too, because the gap is part of the result.</p>
 </section>
 <div class="stats" id="stats"></div>
 <div class="note"><b>This preview</b> shows the 208 commercial perfumery materials used as a reference list, not the whole
  corpus. The corpus itself ships as CC0 data files (molecule → tag rows, each with its source quote and location).
  Descriptors from manufacturers or retailers are <b>not</b> used; if a rights holder releases theirs, they appear in a
  separate, labelled slot.</div>
 <div class="bar">
  <input id="q" type="search" placeholder="Search name, trade name, CAS, formula, tag…" autocomplete="off">
  <div class="seg" id="seg"><button data-f="all" class="on">All</button><button data-f="desc">Described</button><button data-f="none">No public description</button></div>
  <select id="tag"><option value="">Any tag</option></select>
  <span class="count" id="count"></span>
 </div>
 <div class="panel" id="matpanel"><div class="scroll"><table>
  <thead><tr><th style="width:26%">Material</th><th>Formula</th><th class="num">MW</th><th class="num">XLogP3</th><th style="width:34%">Odour tags (from evidence)</th><th class="num">Quotes</th><th>Status</th></tr></thead>
  <tbody id="tb"></tbody></table></div></div>
 <section id="mapview" style="display:none">
  <div class="note"><b>How to read it.</b> Each dot is one of the preview materials that has odour evidence, placed only from
   its corpus tags (t-SNE, cosine distance on tag counts): materials whose sources describe them alike sit close together.
   The axes have no units. Colour is a broad family, a reading aid, not a claim. With <span id="mapn"></span> materials this
   is illustrative, not a perceptual map. Click a dot to open its evidence.</div>
  <div class="legend" id="legend"></div>
  <div class="mapbox"><svg id="plot" viewBox="0 0 1000 640" preserveAspectRatio="xMidYMid meet"></svg></div>
 </section>
 <div class="tip" id="tip"></div>
 <footer id="foot"></footer>
</main>
<script>
const D=/*__DATA__*/null;
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=n=>Number(n).toLocaleString("en-US");
$("#topbadge").textContent=`Preview · ${D.n} materials`;
$("#stats").innerHTML=[
 ["Molecules in the corpus",fmt(D.fig.molecules)],
 ["Tags at the 30-molecule bar",`${D.fig.tags_at_bar} <small>/ ${D.fig.tags}</small>`],
 ["Materials in this preview",D.n],
 ["With a public-domain description",`${D.n_desc} <small>/ ${D.n}</small>`]
].map(([k,v])=>`<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");
const tags=[...new Set(D.mats.flatMap(m=>m.tags))].sort();
$("#tag").innerHTML+=tags.map(t=>`<option>${esc(t)}</option>`).join("");
// highlight verbatim spans: descriptors as <mark>, the molecule span underlined
function hl(q,descs,mol){
 const spans=[];const lower=q.toLowerCase();
 const add=(w,kind)=>{if(!w)return;const lw=w.toLowerCase();let i=0;
  while((i=lower.indexOf(lw,i))>-1){spans.push([i,i+lw.length,kind]);i+=lw.length;}};
 (descs||[]).forEach(d=>add(d,"d"));add(mol,"m");
 spans.sort((a,b)=>a[0]-b[0]||b[1]-a[1]);const keep=[];let end=-1;
 for(const s of spans){if(s[0]>=end){keep.push(s);end=s[1];}}
 let out="",p=0;for(const [a,b,k] of keep){out+=esc(q.slice(p,a))+(k==="d"?`<mark>${esc(q.slice(a,b))}</mark>`:`<u>${esc(q.slice(a,b))}</u>`);p=b;}
 return out+esc(q.slice(p));
}
function srcLink(e){
 if(e.kind==="patent"||e.kind==="passage")return `<a href="https://patents.google.com/patent/${encodeURIComponent(e.src)}/en" target="_blank" rel="noopener">${esc(e.src)}</a>`;
 return e.url?`<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.src)}</a>`:esc(e.src);
}
const SPEC=/*__SPEC__*/null;
const KIND={patent:"US patent",passage:"US patent · passage",hsdb:"US gov · PubChem",physdesc:"US gov · safety data"};
function detail(m){
 const pc=`<a href="https://pubchem.ncbi.nlm.nih.gov/compound/${m.cid}" target="_blank" rel="noopener">${m.cid}</a>`;
 const row=(k,v,cls="")=>v?`<dt>${k}</dt><dd class="${cls}">${v}</dd>`:"";
 const v3=m.c3d?`<div class="v3d"><canvas id="v3d"></canvas></div><div class="hint">Drag to rotate · scroll to zoom · PubChem computed conformer</div>`
  :`<div class="v3d none">${m.c3d===false?"3D not built into this preview yet":"No 3D conformer in PubChem"}</div><div class="hint">&nbsp;</div>`;
 const id=`<div>${v3}<p class="h3">Identity &amp; properties</p><dl>
  ${row("PubChem CID",pc)}${row("CAS",esc(m.cas))}${row("Sold as",esc(m.trade))}${row("IUPAC",esc(m.iupac))}
  ${row("EC / EINECS",esc(m.ec))}${row("FEMA",esc(m.fema))}
  ${row("SMILES",esc(m.smiles))}${row("InChIKey",esc(m.inchikey))}${row("Formula",esc(m.formula))}${row("Mol. weight",esc(m.mw)+" g/mol")}
  ${row("XLogP3",m.xlogp!==""?esc(m.xlogp)+` <span class="src">computed</span>`:"")}${row("TPSA",esc(m.tpsa))}
 </dl>
 ${m.allergen?`<div class="allerg" style="margin-top:14px">EU fragrance allergen · must be labelled above 0.001 % (leave-on) / 0.01 % (rinse-off)<br><span>${esc(m.allergen)}</span></div>`:""}
 <p class="h3" style="margin-top:16px">Measured · US-government sources</p>
 <dl>${SPEC.map(([k,l])=>m.spec[k]?row(l,m.spec[k].map(([v,s])=>`${esc(v)} <span class="src">${esc(s)}</span>`).join("<br>")):"").join("")}
  ${Object.keys(m.spec).length?"":`<dt>Measured</dt><dd class="est">none in a US-government source</dd>`}
 </dl></div>`;
 let ev;
 if(!m.ev.length){
  ev=`<p class="h3">Evidence</p><div class="empty"><b>No odour description in any public-domain source we hold.</b> ${esc(m.note)}.
   Its descriptions exist in manufacturer and retailer literature, which OpenScent does not copy.</div>
   <div class="slot"><b>Licensed descriptors</b>Empty. If the rights holder releases its short descriptor words under CC0 or CC BY 4.0,
   they appear here, credited to the licensor and kept apart from the patent-derived tags.</div>`;
 }else{
  ev=`<p class="h3">Evidence · ${m.ev.length} quote${m.ev.length>1?"s":""}</p>`+m.ev.map(e=>`<div class="ev ${e.kind==="passage"?"passage":""}">
   <div class="evh"><span class="badge">${KIND[e.kind]||e.kind}</span>${srcLink(e)}${e.tags.map(x=>tagChip(x)).join("")}</div>
   ${e.kind==="passage"?`<div class="ante">↳ antecedent: “${hl(e.ante,[],e.mol)}”</div>`:""}
   <div class="q">“${hl(e.quote,e.descs,e.kind==="passage"?e.anaphor:e.mol)}”</div></div>`).join("");
 }
 return `<tr class="detail"><td colspan="7"><div class="dgrid">${id}<div>${ev}</div></div></td></tr>`;
}
let filt="all",open=null;
function render(){
 const q=$("#q").value.trim().toLowerCase(),t=$("#tag").value;
 const rows=D.mats.filter(m=>(filt==="all"||(filt==="desc")===m.described)&&(!t||m.tags.includes(t))&&
  (!q||[m.name,m.title,m.trade,m.cas,m.formula,m.iupac,m.tags.join(" ")].join(" ").toLowerCase().includes(q)));
 $("#count").textContent=`${rows.length} of ${D.n}`;
 $("#tb").innerHTML=rows.map(m=>`<tr class="row${open===m.cid?" open":""}" data-cid="${m.cid}">
  <td class="nm"><b>${esc(m.name)}</b>${m.allergen?'<span class="al" title="EU fragrance allergen (labelling)">allergen</span>':""}<small>${esc(m.trade&&m.trade!==m.name?m.trade:m.title)}</small></td>
  <td style="font-family:var(--mono);font-size:12.5px">${esc(m.formula)}</td><td class="num">${esc(m.mw)}</td><td class="num">${esc(m.xlogp)}</td>
  <td>${m.tags.map(x=>tagChip(x)).join("")||'<span style="color:var(--faint)">—</span>'}</td>
  <td class="num">${m.ev.length||"—"}</td>
  <td>${m.described?'<span class="badge ok">Described</span>':'<span class="badge proto">No public description</span>'}</td></tr>
  ${open===m.cid?detail(m):""}`).join("")||`<tr><td colspan="7" style="text-align:center;color:var(--mut);padding:24px">No materials match.</td></tr>`;
 const cv=document.getElementById("v3d"),om=D.mats.find(m=>m.cid===open);
 if(cv&&om&&om.c3d)mol3d(cv,om.c3d);
}
// ---- built-in 3D viewer: no library, no network. Ball-and-stick, depth-sorted, CPK-style colours.
const EC={1:["#f4f6f8",.22],6:["#3c4652",.34],7:["#2f5bea",.34],8:["#d6453d",.34],9:["#5fbf8a",.3],15:["#e08a2b",.42],16:["#e2b32b",.42],17:["#1f9e5a",.4],35:["#a1401d",.44],53:["#7a3fa0",.48]};
const shade=(h,f)=>"#"+[1,3,5].map(i=>Math.round(parseInt(h.slice(i,i+2),16)*f).toString(16).padStart(2,"0")).join("");
function mol3d(cv,c){
 const ctx=cv.getContext("2d"),dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;
 cv.width=W*dpr;cv.height=H*dpr;ctx.scale(dpr,dpr);
 const n=c.xyz.length,cen=[0,1,2].map(k=>c.xyz.reduce((s,p)=>s+p[k],0)/n),P=c.xyz.map(p=>p.map((v,k)=>v-cen[k]));
 const R=Math.max(...P.map(p=>Math.hypot(p[0],p[1],p[2])))+.9;
 let yaw=.6,pitch=-.35,zoom=1,auto=true,drag=null;
 function draw(){
  ctx.clearRect(0,0,W,H);
  const s=Math.min(W,H)/(2*R)*zoom,cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
  const T=P.map(([x,y,z])=>{const x1=x*cy+z*sy,z1=-x*sy+z*cy;return [W/2+x1*s,H/2-(y*cp-z1*sp)*s,y*sp+z1*cp];});
  const items=c.b.map(([a,b,o])=>({z:(T[a][2]+T[b][2])/2-.05,a,b,o}));T.forEach((p,i)=>items.push({z:p[2],i}));
  items.sort((u,v)=>u.z-v.z);
  for(const it of items){
   if(it.i===undefined){
    const A=T[it.a],B=T[it.b],dx=B[0]-A[0],dy=B[1]-A[1],L=Math.hypot(dx,dy)||1,nx=-dy/L,ny=dx/L;
    const offs=it.o===2?[-2.4,2.4]:it.o===3?[-3.6,0,3.6]:[0];
    const ca=(EC[c.el[it.a]]||["#b36bd6"])[0],cb=(EC[c.el[it.b]]||["#b36bd6"])[0];
    for(const o of offs){const ax=A[0]+nx*o,ay=A[1]+ny*o,bx=B[0]+nx*o,by=B[1]+ny*o,mx=(ax+bx)/2,my=(ay+by)/2;
     ctx.lineCap="round";ctx.lineWidth=offs.length>1?2.6:4.2;ctx.strokeStyle="rgba(7,17,29,.35)";
     ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(bx,by);ctx.stroke();ctx.lineWidth-=1.6;
     ctx.strokeStyle=shade(ca==="#f4f6f8"?"#c9d0d8":ca,1);ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(mx,my);ctx.stroke();
     ctx.strokeStyle=shade(cb==="#f4f6f8"?"#c9d0d8":cb,1);ctx.beginPath();ctx.moveTo(mx,my);ctx.lineTo(bx,by);ctx.stroke();}
   }else{
    const [x,y]=T[it.i],[col,r]=EC[c.el[it.i]]||["#b36bd6",.38],rad=Math.max(2,r*s*.9);
    const g=ctx.createRadialGradient(x-rad*.35,y-rad*.4,rad*.08,x,y,rad);g.addColorStop(0,"#ffffff");g.addColorStop(.3,col);g.addColorStop(1,shade(col,.55));
    ctx.fillStyle=g;ctx.beginPath();ctx.arc(x,y,rad,0,7);ctx.fill();ctx.lineWidth=.6;ctx.strokeStyle="rgba(7,17,29,.3)";ctx.stroke();
   }
  }
 }
 (function frame(){if(!cv.isConnected)return;if(auto)yaw+=.005;draw();requestAnimationFrame(frame);})();
 cv.addEventListener("pointerdown",e=>{drag=[e.clientX,e.clientY];auto=false;cv.setPointerCapture(e.pointerId);cv.parentNode.style.cursor="grabbing";});
 cv.addEventListener("pointermove",e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*.01;pitch=Math.max(-1.5,Math.min(1.5,pitch+(e.clientY-drag[1])*.01));drag=[e.clientX,e.clientY];});
 cv.addEventListener("pointerup",()=>{drag=null;cv.parentNode.style.cursor="grab";});
 cv.addEventListener("wheel",e=>{e.preventDefault();zoom=Math.max(.5,Math.min(3,zoom*Math.exp(-e.deltaY*.0015)));},{passive:false});
}
// clicking a tag filters the list to materials carrying it; clicking the active tag clears it
function tagChip(x){return `<span class="tag click${x===$("#tag").value?" on":""}" data-tag="${esc(x)}" title="Show materials tagged ${esc(x)}">${esc(x)}</span>`;}
function setTag(x){$("#tag").value=$("#tag").value===x?"":x;open=null;render();
 const p=$("#matpanel");if(p&&p.scrollIntoView)p.scrollIntoView({block:"start",behavior:"smooth"});}
$("#tb").addEventListener("click",e=>{const tg=e.target.closest(".tag[data-tag]");if(tg){setTag(tg.dataset.tag);return;}
 const r=e.target.closest("tr.row");if(!r||e.target.closest("a"))return;open=open===r.dataset.cid?null:r.dataset.cid;render();});
$("#q").addEventListener("input",render);$("#tag").addEventListener("change",render);
$("#seg").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;filt=b.dataset.f;
 document.querySelectorAll("#seg button").forEach(x=>x.classList.toggle("on",x===b));render();});
$("#foot").innerHTML=`<b>Licence.</b> OpenScent corpus data: CC0 1.0. Odour evidence is quoted from US patents (not subject to copyright)
 and US-government databases (HSDB via PubChem, NOAA CAMEO, OSHA, NIOSH). Patents that quote copyrighted reference books are excluded.
 Identity and computed properties: PubChem (NCBI); EC and FEMA numbers as listed there. Measured properties only from
 US-government sources (HSDB, NOAA CAMEO, OSHA, NIOSH, DOE PAC), each value shown with its source. EU allergen status:
 Regulation (EC) 1223/2009 Annex III and Regulation (EU) 2023/1545 (EUR-Lex); later bans are not tracked.<br>
 <b>Method.</b> Extract, never generate: every tag rests on a verbatim quote reviewed by a person, and every odour word shown is
 highlighted where it sits in that quote.<br>
 <b>Trademarks.</b> Trade names (Iso E Super®, Cashmeran®, Hedione®, Helional® and others) belong to their owners, including IFF,
 Givaudan, dsm-firmenich, Symrise and Kao, and are used only to identify materials.<br>
 Built ${D.built} from the corpus files · ${fmt(D.n_ev)} quotes · preview, not the release.`;
// ---- scent map
const MP=D.map,byCid=Object.fromEntries(D.mats.map(m=>[m.cid,m])),hidden=new Set();
$("#mapn").textContent=MP.pts.length;
function drawMap(){
 const pad=40,W=1000,H=640;
 $("#plot").innerHTML=MP.pts.filter(p=>!hidden.has(p.f)).map(p=>`<circle cx="${(pad+p.x*(W-2*pad)).toFixed(1)}" cy="${(pad+(1-p.y)*(H-2*pad)).toFixed(1)}" r="8" fill="${MP.fam[p.f][1]}" data-cid="${p.cid}"></circle>`).join("");
 const cnt=MP.fam.map((_,i)=>MP.pts.filter(p=>p.f===i).length);
 $("#legend").innerHTML=MP.fam.map(([n,c],i)=>cnt[i]?`<span class="chip${hidden.has(i)?" off":""}" data-f="${i}"><span class="dot" style="background:${c}"></span>${esc(n)} <span class="n">${cnt[i]}</span></span>`:"").join("");
}
$("#legend").addEventListener("click",e=>{const c=e.target.closest(".chip");if(!c)return;const f=+c.dataset.f;hidden.has(f)?hidden.delete(f):hidden.add(f);drawMap();});
const tip=$("#tip");
$("#plot").addEventListener("mousemove",e=>{const c=e.target.closest("circle");if(!c){tip.style.display="none";return;}
 const m=byCid[c.dataset.cid],p=MP.pts.find(x=>x.cid===m.cid);
 tip.innerHTML=`<b>${esc(m.name)}</b><div class="f">${esc(MP.fam[p.f][0])}</div>${m.tags.map(esc).join(", ")}`;
 tip.style.display="block";tip.style.left=Math.min(e.clientX+14,innerWidth-300)+"px";tip.style.top=(e.clientY+14)+"px";});
$("#plot").addEventListener("mouseleave",()=>tip.style.display="none");
$("#plot").addEventListener("click",e=>{const c=e.target.closest("circle");if(!c)return;tip.style.display="none";
 $("#q").value="";filt="all";$("#tag").value="";document.querySelectorAll("#seg button").forEach(x=>x.classList.toggle("on",x.dataset.f==="all"));
 open=c.dataset.cid;show("materials");const r=document.querySelector(`tr.row[data-cid="${open}"]`);if(r)r.scrollIntoView({block:"center"});});
function show(v){
 const map=v==="map";$("#mapview").style.display=map?"":"none";
 for(const id of ["#matpanel"])$(id).style.display=map?"none":"";$(".bar").style.display=map?"none":"";
 document.querySelectorAll("#nav a").forEach(a=>a.classList.toggle("active",a.dataset.v===v));
 if(map)drawMap();else render();
}
$("#nav").addEventListener("click",e=>{const a=e.target.closest("a");if(!a)return;e.preventDefault();show(a.dataset.v);history.replaceState(null,"","#"+a.dataset.v);});
show(location.hash==="#map"?"map":"materials");
</script></body></html>
"""

if __name__ == "__main__":
    build()
