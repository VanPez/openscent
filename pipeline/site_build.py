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
            "vp": r["vapour_pressure"], "vp_src": r["vapour_pressure_source"],
            "bp": r["boiling_point"], "bp_src": r["boiling_point_source"],
            "described": described, "note": r["status_note"],
            "tags": [t for t, _ in tagc.most_common()], "ev": found,
        })
    if missing:
        sys.exit(f"described in the catalogue but no evidence found for: {missing} — matching drifted from gaps.py")
    n_desc = sum(m["described"] for m in mats)
    data = {"fig": fig, "n": len(mats), "n_desc": n_desc, "n_ev": n_ev,
            "built": datetime.date.today().isoformat(), "mats": mats}
    page = TEMPLATE.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"{len(mats)} materials · {n_desc} described · {n_ev} evidence quotes · corpus {fig['molecules']} molecules, "
          f"{fig['tags_at_bar']}/{fig['tags']} tags at the bar")
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
-->
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenScent — Materials Preview</title><style>
:root{--paper:#f5f7f9;--card:#fff;--ink:#07111d;--mut:#687383;--faint:#718196;--line:#dce4ee;--line-strong:rgba(29,52,78,.3);
 --blue:#245cff;--blue-deep:#1647d9;--blue-pale:#eef3ff;--amber:#9a6a14;--amber-pale:#fdf6e9;--teal:#0f8f7f;--red:#bc4b47;
 --sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
 --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;--shadow:0 18px 50px rgba(28,60,98,.067);--page:1440px}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--blue)}
.topbar{position:sticky;top:0;z-index:5;min-height:72px;border-bottom:1px solid rgba(7,17,29,.1);background:rgba(255,255,255,.94);backdrop-filter:blur(6px)}
.topbar-in{max-width:var(--page);margin:0 auto;padding:10px 28px;min-height:72px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:12px}
.glyph{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;background:#fff;border:1px solid var(--line-strong);font:600 13px var(--mono)}
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
footer{border-top:1px solid var(--line);margin-top:36px;padding-top:16px;color:var(--mut);font-size:12.5px;line-height:1.8}
@media(max-width:760px){.stats{grid-template-columns:1fr 1fr}.stat:nth-child(3){border-left:0}.stat:nth-child(n+3){border-top:1px solid var(--line)}.dgrid{grid-template-columns:1fr}}
@media(max-width:640px){.wrap,.topbar-in{padding-left:16px;padding-right:16px}h1{font-size:26px}.bar{position:static}.stats{grid-template-columns:1fr}.stat+.stat{border-left:0;border-top:1px solid var(--line)}}
</style></head><body>
<header class="topbar"><div class="topbar-in">
 <div class="brand"><div class="glyph">OS</div><div class="wordmark"><b>OpenScent</b><span>Odour corpus · materials</span></div></div>
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
 <div class="panel"><div class="scroll"><table>
  <thead><tr><th style="width:26%">Material</th><th>Formula</th><th class="num">MW</th><th class="num">XLogP3</th><th style="width:34%">Odour tags (from evidence)</th><th class="num">Quotes</th><th>Status</th></tr></thead>
  <tbody id="tb"></tbody></table></div></div>
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
const KIND={patent:"US patent",passage:"US patent · passage",hsdb:"US gov · PubChem",physdesc:"US gov · safety data"};
function detail(m){
 const pc=`<a href="https://pubchem.ncbi.nlm.nih.gov/compound/${m.cid}" target="_blank" rel="noopener">${m.cid}</a>`;
 const row=(k,v,cls="")=>v?`<dt>${k}</dt><dd class="${cls}">${v}</dd>`:"";
 const id=`<div><p class="h3">Identity &amp; properties</p><dl>
  ${row("PubChem CID",pc)}${row("CAS",esc(m.cas))}${row("Sold as",esc(m.trade))}${row("IUPAC",esc(m.iupac))}
  ${row("SMILES",esc(m.smiles))}${row("InChIKey",esc(m.inchikey))}${row("TPSA",esc(m.tpsa))}${row("H-bond d/a",m.hbd!==""?esc(m.hbd+" / "+m.hba):"")}
  ${row("Vapour pr.",m.vp?esc(m.vp)+`<br><span style="color:var(--faint)">${esc(m.vp_src)}</span>`:"",)}
  ${row("Boiling pt.",m.bp?esc(m.bp)+`<br><span style="color:var(--faint)">${esc(m.bp_src)}</span>`:"")}
  ${!m.vp&&!m.bp?`<dt>Measured</dt><dd class="est">none in a US-government source</dd>`:""}
 </dl></div>`;
 let ev;
 if(!m.ev.length){
  ev=`<p class="h3">Evidence</p><div class="empty"><b>No odour description in any public-domain source we hold.</b> ${esc(m.note)}.
   Its descriptions exist in manufacturer and retailer literature, which OpenScent does not copy.</div>
   <div class="slot"><b>Licensed descriptors</b>Empty. If the rights holder releases its short descriptor words under CC0 or CC BY 4.0,
   they appear here, credited to the licensor and kept apart from the patent-derived tags.</div>`;
 }else{
  ev=`<p class="h3">Evidence · ${m.ev.length} quote${m.ev.length>1?"s":""}</p>`+m.ev.map(e=>`<div class="ev ${e.kind==="passage"?"passage":""}">
   <div class="evh"><span class="badge">${KIND[e.kind]||e.kind}</span>${srcLink(e)}${e.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join("")}</div>
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
  <td class="nm"><b>${esc(m.name)}</b><small>${esc(m.trade&&m.trade!==m.name?m.trade:m.title)}</small></td>
  <td style="font-family:var(--mono);font-size:12.5px">${esc(m.formula)}</td><td class="num">${esc(m.mw)}</td><td class="num">${esc(m.xlogp)}</td>
  <td>${m.tags.map(x=>`<span class="tag">${esc(x)}</span>`).join("")||'<span style="color:var(--faint)">—</span>'}</td>
  <td class="num">${m.ev.length||"—"}</td>
  <td>${m.described?'<span class="badge ok">Described</span>':'<span class="badge proto">No public description</span>'}</td></tr>
  ${open===m.cid?detail(m):""}`).join("")||`<tr><td colspan="7" style="text-align:center;color:var(--mut);padding:24px">No materials match.</td></tr>`;
}
$("#tb").addEventListener("click",e=>{const r=e.target.closest("tr.row");if(!r||e.target.closest("a"))return;open=open===r.dataset.cid?null:r.dataset.cid;render();});
$("#q").addEventListener("input",render);$("#tag").addEventListener("change",render);
$("#seg").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;filt=b.dataset.f;
 document.querySelectorAll("#seg button").forEach(x=>x.classList.toggle("on",x===b));render();});
$("#foot").innerHTML=`<b>Licence.</b> OpenScent corpus data: CC0 1.0. Odour evidence is quoted from US patents (not subject to copyright)
 and US-government databases (HSDB via PubChem, NOAA CAMEO, OSHA, NIOSH). Patents that quote copyrighted reference books are excluded.
 Identity and computed properties: PubChem (NCBI). Measured properties only from US-government sources.<br>
 <b>Method.</b> Extract, never generate: every tag rests on a verbatim quote reviewed by a person, and every odour word shown is
 highlighted where it sits in that quote.<br>
 <b>Trademarks.</b> Trade names (Iso E Super®, Cashmeran®, Hedione®, Helional® and others) belong to their owners, including IFF,
 Givaudan, dsm-firmenich, Symrise and Kao, and are used only to identify materials.<br>
 Built ${D.built} from the corpus files · ${fmt(D.n_ev)} quotes · preview, not the release.`;
render();
</script></body></html>
"""

if __name__ == "__main__":
    build()
