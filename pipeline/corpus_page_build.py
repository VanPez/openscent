#!/usr/bin/env python3
"""
corpus_page_build.py — docs/corpus.html: every molecule of the v1.0 candidate, browsable, with a scent map.

    python3 pipeline/corpus_page_build.py            # reads release/v1.0/, writes docs/corpus.html

WHAT THE PAGE IS
----------------
One self-contained HTML file in the GenesisL1 family design (../THEME.md): no external fonts,
scripts, images or requests (outbound LINKS to patents / PubChem only). It lists ALL molecules of
release/v1.0 — the CC0 corpus, not the 208-material retail catalogue of docs/preview.html — with
a table (search, filters, every quote behind every tag, spans highlighted in place), a scent map
and a per-term view. Everything on it is read from release/v1.0 (molecules.tsv, evidence.tsv,
tags.tsv, manifest.json); nothing is typed in or generated.

THE SCENT MAP, AND WHAT IT DOES NOT CLAIM
-----------------------------------------
Position = similarity of a molecule's odour-tag PROFILE (t-SNE on sqrt tag counts, cosine
distance — the same method as the preview's map). Most molecules carry one to three tags, so many
share a profile: those form a tight group, spread on a spiral so that every molecule stays
visible; position inside a group means nothing. Colour = display family, not ontology. The map
says "described alike by the sources", never "smells alike".

Seeded and deterministic: the same release gives the same page (apart from the build time).
"""
from __future__ import annotations
import collections, csv, datetime, importlib.util, json, math, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REL = ROOT / "release" / "v1.0"
OUT = ROOT / "docs" / "corpus.html"

_spec = importlib.util.spec_from_file_location("site_build", ROOT / "pipeline" / "site_build.py")
SB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SB)


def rd(name):
    with (REL / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def main() -> int:
    import numpy as np
    M, E, T = rd("molecules.tsv"), rd("evidence.tsv"), rd("tags.tsv")
    man = json.loads((REL / "manifest.json").read_text(encoding="utf-8"))
    tags = [r["tag"] for r in T]
    ti = {t: i for i, t in enumerate(tags)}
    mi = {r["molecule_id"]: i for i, r in enumerate(M)}

    ev_by = collections.defaultdict(list)
    for e in E:
        ev_by[mi[e["molecule_id"]]].append(e)

    sty, how = [], []
    def code(table, v):
        if v not in table:
            table.append(v)
        return table.index(v)

    # ---- profiles -> map
    X = np.zeros((len(M), len(tags)))
    for i, es in ev_by.items():
        for e in es:
            X[i, ti[e["tag"]]] += 1
    X = np.sqrt(X)
    norm = X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)
    groups = collections.defaultdict(list)
    for i in range(len(M)):
        groups[tuple(np.round(norm[i], 4))].append(i)
    keys = sorted(groups)
    U = np.array(keys)
    print(f"{len(M)} molecules, {len(keys)} distinct tag profiles -> t-SNE", flush=True)
    Y = SB.tsne(U, perplexity=min(25.0, max(5.0, (len(keys) - 1) / 4)))
    lo, hi = np.percentile(Y, 3, axis=0), np.percentile(Y, 97, axis=0)
    Y = np.clip((Y - lo) / np.maximum(hi - lo, 1e-9), -0.04, 1.04)
    Y = (Y + 0.04) / 1.08
    pos = {}
    s = 0.0042
    for g, key in enumerate(keys):
        members = sorted(groups[key], key=lambda i: M[i]["molecule_id"])
        for j, i in enumerate(members):
            r, th = s * math.sqrt(j + 0.5) * (1 if len(members) > 1 else 0), j * 2.399963
            pos[i] = (round(float(Y[g, 0]) + r * math.cos(th), 4), round(float(Y[g, 1]) + r * math.sin(th), 4))

    fam_of = {t: k for k, (_, _, ts) in enumerate(SB.FAMILIES) for t in ts}

    def family(i):
        score = collections.Counter()
        for t, c in zip(tags, X[i]):
            if c and t in fam_of:
                score[fam_of[t]] += c * (0.6 if t in SB.GENERIC else 1)
        return score.most_common(1)[0][0] if score else len(SB.FAMILIES) - 1

    strength = {"direct": 0, "hand-derived": 1, "none": 2}
    mol, evid = [], {}
    for i, r in enumerate(M):
        es = ev_by[i]
        docs = []
        for e in es:
            for d in (e["documents"].split(";") if e["documents"] else []):
                if d and d not in docs:
                    docs.append(d)
        has_pat = any(e["source_type"].startswith("patent") for e in es)
        has_db = any(not e["source_type"].startswith("patent") for e in es)
        descs = sorted({e["descriptor_span"].lower() for e in es})
        mol.append([r["label"], r["name_spellings"], r["smiles"], r["inchikey"],
                    [ti[t] for t in r["tags"].split(";") if t], int(r["n_evidence"]), int(r["n_documents"]),
                    strength[r["structure_strength"]], (r["pubchem_cids"].split(";") or [""])[0],
                    pos[i][0], pos[i][1], family(i), (2 if has_pat and has_db else 1 if has_db else 0),
                    ";".join(r["structure_basis"].split(";")), " ".join(docs)[:300], ";".join(descs)[:200]])
        evid[i] = [[ti[e["tag"]], e["descriptor_span"], e["molecule_span"], e["quote"], e["antecedent"],
                    code(sty, e["source_type"]), e["source_id"], ";".join((e["documents"] or "").split(";")[:6]),
                    e["source_url"], code(how, e["how_decided"])] for e in sorted(es, key=lambda e: (e["tag"], e["evidence_id"]))]

    c = man["counts"]
    data = {"tags": [[r["tag"], int(r["molecules_v1_0"]), 1 if r["at_bar_30"] == "yes" else 0] for r in T],
            "fam": [[n, col] for n, col, _ in SB.FAMILIES], "m": mol, "sty": sty, "how": how,
            "counts": {"molecules": c["molecules"], "with_structure": c["molecules_with_structure"],
                       "name_only": c["molecules_name_only"], "hand": c["structure_hand_derived"],
                       "evidence": c["evidence_rows"], "at_bar": c["terms_at_bar"], "terms": c["terms_total"]},
            "built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"), "head": (man.get("git_head") or "")[:7]}

    def js(o):
        return json.dumps(o, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")

    page = TEMPLATE.replace("/*DATA*/", js(data)).replace("/*EVID*/", js(evid))
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size/1e6:.2f} MB)")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenScent corpus — every molecule of v1.0 (candidate)</title>
<meta name="description" content="Every molecule in the OpenScent v1.0 candidate: a CC0 structure–odour corpus built from US patents and US-government databases. Search, filter, read the quote behind every tag, and explore the scent map.">
<meta property="og:title" content="OpenScent corpus — every molecule of v1.0 (candidate)"><meta property="og:type" content="website">
<style>
:root{--paper:#f5f7f9;--card:#fff;--ink:#07111d;--mut:#687383;--faint:#718196;--line:#dce4ee;--line-strong:rgba(29,52,78,.3);
 --blue:#245cff;--blue-deep:#1647d9;--blue-pale:#eef3ff;--amber:#9a6a14;--amber-pale:#fdf6e9;--teal:#0f8f7f;--red:#bc4b47;
 --sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
 --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;--shadow:0 18px 50px rgba(28,60,98,.067);--page:1440px}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--blue)}
.topbar{position:sticky;top:0;z-index:6;border-bottom:1px solid rgba(7,17,29,.1);background:rgba(255,255,255,.94);backdrop-filter:blur(6px)}
.topbar-in{max-width:var(--page);margin:0 auto;padding:10px 28px;min-height:64px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:12px}.glyph{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;background:#fff;border:1px solid var(--line-strong)}
.wordmark b{display:block;font-size:17px;letter-spacing:-.01em}.wordmark span{font-family:var(--mono);font-size:10px;letter-spacing:.14em;color:var(--mut);text-transform:uppercase}
.nav{display:flex;align-items:center;gap:14px;flex-wrap:wrap;font-size:13px}.nav a{text-decoration:none}.nav a:hover{text-decoration:underline}
.badge{font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;padding:5px 10px;border:1px solid var(--line-strong);color:var(--mut);background:#fff;white-space:nowrap}
.badge.amber{border-color:rgba(154,106,20,.5);color:var(--amber);background:var(--amber-pale)}
.wrap{max-width:var(--page);margin:0 auto;padding:0 28px 60px}
.lab{display:flex;align-items:center;gap:10px;color:var(--mut);font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.14em;margin-top:30px}
.lab:before{content:"";width:26px;height:1px;background:var(--blue)}
h1{font-size:clamp(26px,4vw,40px);line-height:1.1;letter-spacing:-.025em;margin:10px 0 10px;max-width:900px}
h1 small{font:500 12px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--amber);border:1px solid rgba(154,106,20,.5);background:var(--amber-pale);padding:3px 8px;vertical-align:middle;margin-left:8px}
.lede{max-width:860px;color:#33414f;margin:0 0 4px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);margin:22px 0;background:#fff;border:1px solid var(--line-strong);box-shadow:var(--shadow)}
.stat{padding:15px 18px}.stat+.stat{border-left:1px solid var(--line)}
.stat .k{color:var(--mut);font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.1em}
.stat .v{font-family:var(--mono);font-size:22px;font-weight:500;margin-top:5px}.stat .v small{font-size:12px;color:var(--mut)}
.licbox{border:1px solid var(--line);border-left:3px solid var(--blue);background:#fff;padding:12px 16px;margin-bottom:14px;font-size:13.5px;color:#33414f}
.licbox b{color:var(--ink)}
.tabs{display:inline-flex;border:1px solid var(--line-strong);background:#fff;margin:6px 0 4px}
.tabs button{font:500 12px var(--mono);letter-spacing:.06em;text-transform:uppercase;padding:10px 18px;border:0;background:transparent;color:var(--mut);cursor:pointer}
.tabs button+button{border-left:1px solid var(--line)}.tabs button:hover{background:rgba(7,17,29,.05);color:var(--ink)}.tabs button.on{background:var(--blue);color:#fff}
.bar{position:sticky;top:64px;z-index:5;display:flex;align-items:center;gap:10px;background:var(--paper);padding:12px 0 14px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.bar input{flex:1;min-width:220px;font:14px var(--sans);padding:11px 14px;border:1px solid var(--line-strong);background:#fff;color:var(--ink);border-radius:9px;outline:none}
.bar input:focus,.bar select:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(36,92,255,.14)}
.bar select{font:13px var(--mono);padding:10px 12px;border:1px solid var(--line-strong);border-radius:9px;background:#fff;color:var(--ink);max-width:200px}
.btn{font:500 12px var(--mono);letter-spacing:.04em;padding:10px 14px;border:1px solid var(--line-strong);border-radius:9px;background:#fff;color:var(--ink);cursor:pointer}.btn:hover{border-color:var(--blue);color:var(--blue)}
.count{font-family:var(--mono);font-size:11.5px;color:var(--mut);white-space:nowrap;margin-left:auto}
.active{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 0;min-height:4px}
.panel{background:#fff;border:1px solid var(--line-strong);box-shadow:var(--shadow);margin-top:16px;border-top:3px solid var(--blue)}
table{width:100%;border-collapse:collapse}
th{font:500 10px var(--mono);text-transform:uppercase;letter-spacing:.09em;color:var(--mut);text-align:left;padding:10px 18px;border-bottom:1px solid var(--line-strong);background:#fbfcfd}
td{font-size:13.5px;padding:10px 18px;border-top:1px solid var(--line);vertical-align:top}
tr.row{cursor:pointer}tr.row:hover td{background:#f9fbfe}tr.row.open td{background:var(--blue-pale)}
td.num,th.num{font-family:var(--mono);text-align:right;white-space:nowrap}
.nm b{font-weight:600}.sub{color:var(--faint);font-size:11.5px;font-family:var(--mono);margin-top:1px;max-width:380px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tag{display:inline-block;font:10px var(--mono);letter-spacing:.06em;text-transform:uppercase;padding:2px 7px;margin:0 4px 4px 0;border:1px solid rgba(15,143,127,.4);color:var(--teal);background:rgba(15,143,127,.06);cursor:pointer}
.tag:hover{background:rgba(15,143,127,.16);border-color:var(--teal)}.tag.on{background:var(--teal);color:#fff;border-color:var(--teal)}
.st{font:10px var(--mono);letter-spacing:.06em;text-transform:uppercase;padding:2px 7px;border:1px solid var(--line-strong);color:var(--mut);white-space:nowrap}
.st.d{border-color:rgba(15,143,127,.4);color:var(--teal)}.st.h{border-color:rgba(154,106,20,.5);color:var(--amber);background:var(--amber-pale)}.st.n{border-color:rgba(188,75,71,.5);color:var(--red)}
.more{display:block;width:100%;padding:14px;border:0;border-top:1px solid var(--line);background:#fbfcfd;font:500 12px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--blue);cursor:pointer}.more:hover{background:var(--blue-pale)}
.empty{padding:40px 18px;text-align:center;color:var(--mut)}
.detail{padding:6px 18px 18px;background:var(--blue-pale);border-top:1px solid var(--line)}
.detail h3{margin:14px 0 4px;font-size:18px;letter-spacing:-.01em}
.kv{display:grid;grid-template-columns:130px 1fr;gap:4px 14px;font-size:12.5px;margin:8px 0 12px}.kv dt{color:var(--mut);font-family:var(--mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;padding-top:2px}
.kv dd{margin:0;font-family:var(--mono);font-size:12px;word-break:break-all}.kv dd.t{font-family:var(--sans);word-break:normal}
.evh{font:500 11px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--teal);margin:14px 0 6px}
.ev{background:#fff;border:1px solid var(--line);border-left:3px solid var(--teal);padding:9px 14px;margin-bottom:8px;font-size:13.5px}
.ev .ant{color:var(--faint);font-size:12.5px;margin-bottom:4px}
.ev mark.d{background:rgba(15,143,127,.2);color:inherit;padding:0 2px;border-bottom:2px solid var(--teal)}.ev mark.m{background:rgba(36,92,255,.14);color:inherit;padding:0 2px;border-bottom:2px solid var(--blue)}
.ev .meta{margin-top:6px;font:10.5px var(--mono);color:var(--faint);letter-spacing:.04em}.ev .meta a{margin-right:8px}
.mapwrap{position:relative;padding:0}#cv{display:block;width:100%;cursor:grab;touch-action:none;background:#fff}#cv.drag{cursor:grabbing}
.tip{position:absolute;pointer-events:none;background:var(--ink);color:#fff;font:12px var(--mono);padding:6px 9px;max-width:300px;z-index:3;display:none}
.zoom{position:absolute;right:12px;top:12px;display:flex;flex-direction:column;gap:6px}.zoom .btn{padding:6px 11px;background:#fff}
.legend{display:flex;gap:8px;flex-wrap:wrap;padding:12px 18px;border-top:1px solid var(--line)}
.lg{display:inline-flex;align-items:center;gap:7px;font:11px var(--mono);padding:4px 9px;border:1px solid var(--line-strong);background:#fff;cursor:pointer;color:var(--ink)}.lg i{width:10px;height:10px;border-radius:50%;display:inline-block}.lg.off{opacity:.4}
.note{font-size:12.5px;color:var(--mut);padding:0 18px 14px}
.tm{display:grid;grid-template-columns:150px 1fr 60px;gap:12px;align-items:center;padding:7px 18px;border-top:1px solid var(--line);cursor:pointer}.tm:hover{background:#f9fbfe}
.tm .n{font:12px var(--mono);text-transform:uppercase;letter-spacing:.06em}.tm .b{position:relative;height:12px;background:#eef2f7}.tm .b i{display:block;height:100%;background:var(--teal)}.tm .b i.low{background:#9cc9c2}
.tm .b u{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--amber)}.tm .c{font:12px var(--mono);text-align:right}
footer{max-width:var(--page);margin:0 auto;padding:10px 28px 50px;color:var(--mut);font-size:12.5px}footer p{max-width:900px}
@media(max-width:760px){.wrap,.topbar-in,footer{padding-left:16px;padding-right:16px}.stats{grid-template-columns:repeat(2,1fr)}.stat:nth-child(3){border-left:0}.stat:nth-child(n+3){border-top:1px solid var(--line)}
 th.hide,td.hide{display:none}td,th{padding:9px 12px}.kv{grid-template-columns:1fr}.tm{grid-template-columns:110px 1fr 46px}.bar{top:0;position:static}.count{margin-left:0}}
</style></head><body>
<header class="topbar"><div class="topbar-in">
 <div class="brand"><div class="glyph"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 9.2 13.8 11.7V16.7L9.5 19.2 5.2 16.7V11.7Z" stroke="#07111d" stroke-width="1.5"/><circle cx="9.5" cy="14.2" r="2.3" stroke="#245cff" stroke-width="1.3"/><path d="M13.8 11.7C15.9 10.6 14.7 8.4 16.7 7.2 18.7 6 17.7 3.8 19.9 2.8" stroke="#245cff" stroke-width="1.5"/></svg></div>
 <div class="wordmark"><b>OpenScent</b><span>A GenesisL1 project</span></div></div>
 <nav class="nav"><a href="preview.html">208-material preview</a><a href="https://github.com/VanPez/openscent">GitHub</a><span class="badge amber">v1.0 candidate</span></nav>
</div></header>
<main class="wrap">
 <div class="lab">The corpus</div>
 <h1>Every molecule in OpenScent v1.0<small>candidate</small></h1>
 <p class="lede">A CC0 structure–odour corpus built only from US patents and US-government databases. Each odour tag below is a word quoted verbatim from its source, with the sentence one click away. Nothing is generated.</p>
 <div class="stats" id="stats"></div>
 <div class="licbox" id="lic"></div>
 <div class="tabs" id="tabs"><button data-v="table" class="on">Table</button><button data-v="map">Scent map</button><button data-v="terms">Terms</button></div>
 <div class="bar" id="bar">
  <input id="q" type="search" placeholder="Search a name, InChIKey, patent number or odour word…" aria-label="Search">
  <select id="ftag" aria-label="Odour term"></select>
  <select id="fstr" aria-label="Structure"><option value="">any structure</option><option value="direct">structure read directly</option><option value="hand-derived">structure hand-derived</option><option value="none">no structure</option></select>
  <select id="fsrc" aria-label="Source"><option value="">any source</option><option value="0">patent text only</option><option value="1">government database only</option><option value="2">both</option></select>
  <button class="btn" id="reset">Reset</button><span class="count" id="count"></span>
 </div>
 <div class="active" id="active"></div>
 <section id="v-table"><div class="panel"><table><thead><tr><th>Molecule</th><th>Odour tags</th><th class="num hide">Quotes</th><th class="hide">Structure</th></tr></thead><tbody id="tb"></tbody></table><button class="more" id="more" hidden></button><div class="empty" id="empty" hidden>No molecule matches these filters.</div></div></section>
 <section id="v-map" hidden><div class="panel"><div class="mapwrap" id="mw"><canvas id="cv"></canvas><div class="tip" id="tip"></div><div class="zoom"><button class="btn" id="zi" aria-label="Zoom in">+</button><button class="btn" id="zo" aria-label="Zoom out">−</button><button class="btn" id="zr" aria-label="Reset view">⌂</button></div></div>
  <div class="legend" id="legend"></div>
  <div class="note">Each dot is a molecule, placed by how its sources describe it (the pattern of odour tags; t-SNE). Molecules with the same pattern form a tight group; position inside a group means nothing. Drag to pan, scroll to zoom, click a dot to read its quotes. Colours are a display aid, not a classification. <b>Close on the map means described alike, not smelling alike.</b></div>
  <div id="mapdetail"></div></div></section>
 <section id="v-terms" hidden><div class="panel"><div class="note" style="padding-top:12px">The 67 vocabulary terms by number of molecules. The amber mark is the 30-molecule bar a term needs to count as covered. Click a term to list its molecules.</div><div id="terms"></div></div></section>
</main>
<footer><p id="foot"></p><p>CC0 1.0 for the data; code Apache-2.0. A molecule appearing here says nothing about live patent claims covering it. Odour words describe what the sources say about smell; they are not claims about health or effects. Rows set aside by the model screen were not read by a human, so absence here is a recall limit, not a judgement.</p></footer>
<script id="data" type="application/json">/*DATA*/</script>
<script id="evid" type="application/json">/*EVID*/</script>
<script>
(function(){'use strict';
const D=JSON.parse(document.getElementById('data').textContent);let EV=null;
const ev=()=>EV||(EV=JSON.parse(document.getElementById('evid').textContent));
const TAGS=D.tags,FAM=D.fam,M=D.m,C=D.counts;
const F={label:0,spell:1,smiles:2,ik:3,tags:4,nev:5,ndoc:6,str:7,cid:8,x:9,y:10,fam:11,src:12,basis:13,docs:14,descs:15};
const STR=['direct','hand-derived','none'],STRL=['structure read directly','structure hand-derived','no structure'],STRC=['d','h','n'];
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt=n=>n.toLocaleString('en-US');
const st={view:'table',q:'',tags:[],str:'',src:'',shown:80,open:-1,sel:-1,fams:new Set()};
const H=M.map(m=>(m[F.label]+' '+m[F.spell]+' '+m[F.ik]+' '+m[F.tags].map(t=>TAGS[t][0]).join(' ')+' '+m[F.descs]+' '+m[F.docs]).toLowerCase());
const order=M.map((_,i)=>i).sort((a,b)=>M[b][F.nev]-M[a][F.nev]||M[a][F.label].localeCompare(M[b][F.label]));
function match(i){const m=M[i];
 if(st.tags.length&&!st.tags.every(t=>m[F.tags].includes(t)))return false;
 if(st.str!==''&&STR[m[F.str]]!==st.str)return false;
 if(st.src!==''&&String(m[F.src])!==st.src)return false;
 if(st.q&&!st.q.split(/\s+/).every(w=>H[i].includes(w)))return false;return true}
let hits=[];
function refilter(){hits=order.filter(match);$('count').textContent=fmt(hits.length)+' of '+fmt(M.length)+' molecules';
 const a=$('active');a.innerHTML=st.tags.map(t=>'<span class="tag on" data-t="'+t+'">'+esc(TAGS[t][0])+' ✕</span>').join('');
 $('ftag').value=st.tags.length===1?String(st.tags[0]):'';}
function chips(m){return m[F.tags].map(t=>'<span class="tag'+(st.tags.includes(t)?' on':'')+'" data-t="'+t+'">'+esc(TAGS[t][0])+'</span>').join('')}
function strb(m){const k=m[F.str];return '<span class="st '+STRC[k]+'">'+(k===0?'direct':k===1?'hand-derived':'no structure')+'</span>'}
function hl(q,d,mo){const R=[];const add=(s,c)=>{if(!s)return;const k=q.indexOf(s);if(k<0)return;if(R.some(r=>k<r[1]&&k+s.length>r[0]))return;R.push([k,k+s.length,c])};
 add(d,'d');add(mo,'m');R.sort((a,b)=>a[0]-b[0]);let o='',p=0;for(const r of R){o+=esc(q.slice(p,r[0]))+'<mark class="'+r[2]+'">'+esc(q.slice(r[0],r[1]))+'</mark>';p=r[1]}return o+esc(q.slice(p))}
function srcLink(e){const id=e[6];if(/^US\d/.test(id))return '<a href="https://patents.google.com/patent/'+encodeURIComponent(id)+'" target="_blank" rel="noopener">'+esc(id)+'</a>';
 return e[8]?'<a href="'+esc(e[8])+'" target="_blank" rel="noopener">'+esc(id||'source')+'</a>':esc(id)}
function detail(i){const m=M[i],E=ev()[i]||[];
 const pc=m[F.cid]?'https://pubchem.ncbi.nlm.nih.gov/compound/'+m[F.cid]:(m[F.ik]?'https://pubchem.ncbi.nlm.nih.gov/#query='+m[F.ik]:'');
 let h='<div class="detail"><h3>'+esc(m[F.label])+'</h3><dl class="kv">';
 if(m[F.ik])h+='<dt>InChIKey</dt><dd>'+esc(m[F.ik])+'</dd>';
 if(m[F.smiles])h+='<dt>SMILES</dt><dd>'+esc(m[F.smiles])+'</dd>';
 h+='<dt>Structure</dt><dd class="t">'+STRL[m[F.str]]+(m[F.basis]?' ('+esc(m[F.basis].replace(/;/g,', '))+')':'')+(m[F.str]===1?' — derived by a hand-authorised reading, see corpus/structures/rewrites.json':'')+(m[F.str]===2?' — counted by its name text alone':'')+'</dd>';
 h+='<dt>Spellings in sources</dt><dd class="t">'+esc(m[F.spell])+'</dd>';
 h+='<dt>Documents</dt><dd class="t">'+m[F.ndoc]+' · '+E.length+' quote'+(E.length===1?'':'s')+(pc?' · <a href="'+esc(pc)+'" target="_blank" rel="noopener">PubChem ↗</a>':'')+'</dd></dl>';
 const by={};E.forEach(e=>{(by[e[0]]=by[e[0]]||[]).push(e)});
 Object.keys(by).forEach(t=>{h+='<div class="evh">'+esc(TAGS[t][0])+' · '+by[t].length+'</div>';
  by[t].forEach(e=>{h+='<div class="ev">'+(e[4]?'<div class="ant">Preceding sentence: '+esc(e[4])+'</div>':'')+'“'+hl(e[3],e[1],e[2])+'”<div class="meta">'+srcLink(e)+(e[7]&&e[7].indexOf(';')>=0?'also in '+esc(e[7].split(';').slice(1,4).join(', '))+' · ':'')+esc(D.sty[e[5]])+' · '+esc(D.how[e[9]])+'</div></div>'})});
 return h+'</div>'}
function renderTable(){const tb=$('tb');const rows=hits.slice(0,st.shown);let h='';
 for(const i of rows){const m=M[i],sub=m[F.spell]&&m[F.spell]!==m[F.label]?m[F.spell]:'';
  h+='<tr class="row'+(st.open===i?' open':'')+'" data-i="'+i+'"><td class="nm"><b>'+esc(m[F.label])+'</b>'+(sub?'<div class="sub">'+esc(sub)+'</div>':'')+'</td><td>'+chips(m)+'</td><td class="num hide">'+m[F.nev]+'</td><td class="hide">'+strb(m)+'</td></tr>';
  if(st.open===i)h+='<tr><td colspan="4" style="padding:0">'+detail(i)+'</td></tr>'}
 tb.innerHTML=h;$('empty').hidden=hits.length>0;const mo=$('more');mo.hidden=hits.length<=st.shown;mo.textContent='Show '+Math.min(80,hits.length-st.shown)+' more of '+fmt(hits.length-st.shown)+' remaining'}
/* ---------------- map */
const cv=$('cv'),cx=cv.getContext('2d');let W=800,Hh=520,dpr=1,V={k:1,tx:0,ty:0},hov=-1,hitset=new Set();
const PAD=24,sx=x=>PAD+x*(W-2*PAD)*V.k+V.tx,sy=y=>PAD+y*(Hh-2*PAD)*V.k+V.ty;
function fit(){const r=$('mw').getBoundingClientRect();W=Math.max(300,r.width);Hh=Math.round(Math.min(Math.max(380,W*.62),740));dpr=window.devicePixelRatio||1;cv.width=W*dpr;cv.height=Hh*dpr;cv.style.height=Hh+'px';cx.setTransform(dpr,0,0,dpr,0,0)}
function vis(i){return hitset.has(i)&&(!st.fams.size||st.fams.has(M[i][F.fam]))}
function draw(){cx.clearRect(0,0,W,Hh);const r=Math.min(7,2.2*Math.sqrt(V.k));
 cx.fillStyle='rgba(104,115,131,.16)';for(let i=0;i<M.length;i++){if(vis(i))continue;cx.beginPath();cx.arc(sx(M[i][F.x]),sy(M[i][F.y]),r*.8,0,6.283);cx.fill()}
 for(let i=0;i<M.length;i++){if(!vis(i))continue;cx.fillStyle=FAM[M[i][F.fam]][1];cx.globalAlpha=.82;cx.beginPath();cx.arc(sx(M[i][F.x]),sy(M[i][F.y]),r,0,6.283);cx.fill()}
 cx.globalAlpha=1;const mark=(i,c)=>{if(i<0)return;const x=sx(M[i][F.x]),y=sy(M[i][F.y]);cx.lineWidth=2;cx.strokeStyle=c;cx.beginPath();cx.arc(x,y,r+4,0,6.283);cx.stroke()};
 mark(st.sel,'#07111d');mark(hov,'#245cff')}
function nearest(px,py){let b=-1,bd=100;for(let i=0;i<M.length;i++){if(!vis(i))continue;const dx=sx(M[i][F.x])-px,dy=sy(M[i][F.y])-py,d=dx*dx+dy*dy;if(d<bd){bd=d;b=i}}return b}
function renderMap(){fit();hitset=new Set(hits);draw();
 $('legend').innerHTML=FAM.map((f,k)=>'<span class="lg'+(st.fams.size&&!st.fams.has(k)?' off':'')+'" data-f="'+k+'"><i style="background:'+f[1]+'"></i>'+esc(f[0])+'</span>').join('');
 $('mapdetail').innerHTML=st.sel>=0?detail(st.sel):'<div class="note" style="padding-top:6px">Click a dot to read the quotes behind it.</div>'}
let drag=null;
cv.addEventListener('pointerdown',e=>{cv.setPointerCapture(e.pointerId);drag={x:e.clientX,y:e.clientY,tx:V.tx,ty:V.ty,moved:false};cv.classList.add('drag')});
cv.addEventListener('pointermove',e=>{const r=cv.getBoundingClientRect(),px=e.clientX-r.left,py=e.clientY-r.top;
 if(drag){const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>4)drag.moved=true;if(drag.moved){V.tx=drag.tx+dx;V.ty=drag.ty+dy;draw()}return}
 const n=nearest(px,py),tip=$('tip');if(n!==hov){hov=n;draw()}
 if(n>=0){tip.style.display='block';tip.style.left=Math.min(px+14,W-200)+'px';tip.style.top=(py+14)+'px';tip.textContent=M[n][F.label]+' · '+M[n][F.tags].map(t=>TAGS[t][0]).join(', ')}else tip.style.display='none'});
cv.addEventListener('pointerup',e=>{const was=drag;drag=null;cv.classList.remove('drag');if(was&&!was.moved){const r=cv.getBoundingClientRect(),n=nearest(e.clientX-r.left,e.clientY-r.top);st.sel=n;draw();$('mapdetail').innerHTML=n>=0?detail(n):'';if(n>=0)$('mapdetail').scrollIntoView({behavior:'smooth',block:'nearest'})}});
cv.addEventListener('pointerleave',()=>{$('tip').style.display='none';if(hov!==-1){hov=-1;draw()}});
function zoomAt(f,px,py){const k=Math.max(1,Math.min(40,V.k*f)),r=k/V.k;V.tx=px-(px-V.tx)*r+PAD*(r-1);V.ty=py-(py-V.ty)*r+PAD*(r-1);V.k=k;if(k===1){V.tx=0;V.ty=0}draw()}
cv.addEventListener('wheel',e=>{e.preventDefault();const r=cv.getBoundingClientRect();zoomAt(e.deltaY<0?1.25:.8,e.clientX-r.left,e.clientY-r.top)},{passive:false});
$('zi').onclick=()=>zoomAt(1.5,W/2,Hh/2);$('zo').onclick=()=>zoomAt(1/1.5,W/2,Hh/2);$('zr').onclick=()=>{V={k:1,tx:0,ty:0};draw()};
$('legend').addEventListener('click',e=>{const f=e.target.closest('.lg');if(!f)return;const k=+f.dataset.f;st.fams.has(k)?st.fams.delete(k):st.fams.add(k);renderMap()});
/* ---------------- terms */
function renderTerms(){const mx=Math.max(...TAGS.map(t=>t[1]));$('terms').innerHTML=TAGS.map((t,i)=>'<div class="tm" data-t="'+i+'"><span class="n">'+esc(t[0])+'</span><span class="b"><i class="'+(t[2]?'':'low')+'" style="width:'+Math.max(1,t[1]/mx*100)+'%"></i><u style="left:'+30/mx*100+'%"></u></span><span class="c">'+t[1]+'</span></div>').join('')}
/* ---------------- wiring */
function setView(v){st.view=v;document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('on',b.dataset.v===v));
 ['table','map','terms'].forEach(x=>$('v-'+x).hidden=x!==v);$('bar').style.display=v==='terms'?'none':'flex';$('active').style.display=v==='terms'?'none':'flex';
 if(v==='map')renderMap();if(v==='table')renderTable();if(v==='terms')renderTerms()}
function update(){st.shown=80;refilter();if(st.view==='table')renderTable();if(st.view==='map')renderMap()}
function toggleTag(t){const k=st.tags.indexOf(t);k>=0?st.tags.splice(k,1):st.tags.push(t);update()}
$('tabs').addEventListener('click',e=>{const b=e.target.closest('button');if(b)setView(b.dataset.v)});
$('q').addEventListener('input',e=>{st.q=e.target.value.trim().toLowerCase();update()});
$('ftag').innerHTML='<option value="">any odour term</option>'+TAGS.map((t,i)=>'<option value="'+i+'">'+esc(t[0])+' ('+t[1]+')</option>').join('');
$('ftag').onchange=e=>{st.tags=e.target.value===''?[]:[+e.target.value];update()};
$('fstr').onchange=e=>{st.str=e.target.value;update()};$('fsrc').onchange=e=>{st.src=e.target.value;update()};
$('reset').onclick=()=>{st.q='';st.tags=[];st.str='';st.src='';st.fams.clear();st.open=-1;st.sel=-1;$('q').value='';$('fstr').value='';$('fsrc').value='';V={k:1,tx:0,ty:0};update()};
document.addEventListener('click',e=>{const t=e.target.closest('.tag');if(t&&t.dataset.t!==undefined){e.stopPropagation();toggleTag(+t.dataset.t);return}
 const r=e.target.closest('tr.row');if(r){const i=+r.dataset.i;st.open=st.open===i?-1:i;renderTable()}
 const tm=e.target.closest('.tm');if(tm){st.tags=[+tm.dataset.t];update();setView('table');window.scrollTo({top:0})}});
$('more').onclick=()=>{st.shown+=80;renderTable()};
window.addEventListener('resize',()=>{if(st.view==='map')renderMap()});
$('stats').innerHTML=[['Molecules',fmt(C.molecules),'in release/v1.0'],['With a structure',fmt(C.with_structure),fmt(C.name_only)+' counted by name only'],['Terms at the bar',C.at_bar+' <small>of '+C.terms+'</small>','≥ 30 molecules'],['Quotes',fmt(C.evidence),'verbatim, each with its source']].map(s=>'<div class="stat"><div class="k">'+s[0]+'</div><div class="v">'+s[1]+'</div><div class="k" style="text-transform:none;letter-spacing:0;margin-top:2px">'+s[2]+'</div></div>').join('');
$('lic').innerHTML='<b>What you are looking at.</b> The v1.0 <i>candidate</i>: not frozen yet. '+fmt(C.hand)+' structures are hand-derived readings of OCR-damaged or obsolete names and '+fmt(C.name_only)+' molecules have no definite structure; both are marked. Database rows were extracted by rule from the odour clause; patent rows were each approved by a person.';
$('foot').textContent='Built '+D.built+' from release/v1.0 (git '+D.head+'). Every figure on this page is read from the release files.';
refilter();renderTable();
})();
</script></body></html>
"""

if __name__ == "__main__":
    raise SystemExit(main())
