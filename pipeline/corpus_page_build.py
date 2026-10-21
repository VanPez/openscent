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


def term_map(X, tags, fam_of, other):
    """Option D, in the page: the 67 terms placed by the molecules they share (t-SNE on each term's 0/1 vector over the
    molecules, the same method as the scent map), lines for the strongest co-occurrences, labels placed greedily so that
    they avoid each other and the dots. All in a 1000 x 680 SVG viewBox."""
    import numpy as np
    n = len(tags)
    B = (X.T > 0).astype(float)
    cnt = B.sum(1)
    sets = [set(np.where(B[j] > 0)[0]) for j in range(n)]
    J = np.zeros((n, n))
    for a in range(n):
        for b in range(a + 1, n):
            inter = len(sets[a] & sets[b])
            if inter:
                J[a, b] = J[b, a] = inter / len(sets[a] | sets[b])
    Y = SB.tsne(B, perplexity=7.0, iters=1500, seed=20261020)
    lo, hi = np.percentile(Y, 2, axis=0), np.percentile(Y, 98, axis=0)
    xy = np.clip((Y - lo) / np.maximum(hi - lo, 1e-9), -0.05, 1.05)
    Wd, Hd = 1000, 680
    P = np.c_[44 + (xy[:, 0] + .05) / 1.1 * 912, 34 + (xy[:, 1] + .05) / 1.1 * 612]
    rad = 4.5 + 0.95 * np.sqrt(cnt)
    edges = set()
    for a in range(n):
        for b in np.argsort(-J[a])[:2]:
            if J[a, b] > 0.02:
                edges.add((min(a, int(b)), max(a, int(b))))
        for b in range(a + 1, n):
            if J[a, b] >= 0.06:
                edges.add((a, b))
    fs = 11.0
    cw = 0.6 * fs
    placed, lab = [], [None] * n

    def box(cx, cy, text, anchor, bold):
        wid = len(text) * cw * (1.1 if bold else 1.0)
        hei = fs * 1.25
        x0 = cx if anchor == "start" else cx - wid if anchor == "end" else cx - wid / 2
        return (x0, cy - hei / 2, x0 + wid, cy + hei / 2)

    def hit(b1, b2):
        return not (b1[2] < b2[0] or b2[2] < b1[0] or b1[3] < b2[1] or b2[3] < b1[1])

    cands = ((0, -1, "middle"), (1, 0, "start"), (-1, 0, "end"), (0, 1, "middle"), (1, -1, "start"), (-1, -1, "end"),
             (1, 1, "start"), (-1, 1, "end"), (0, -2, "middle"), (2, 0, "start"), (-2, 0, "end"), (0, 2, "middle"))
    for j in np.argsort(-cnt):
        t = tags[j]
        bold = cnt[j] >= 60
        got = None
        for dx, dy, anc in cands:
            off = rad[j] + 3 + (4 if dx and dy else 0) + (8 if abs(dx) == 2 or abs(dy) == 2 else 0)
            cx = P[j, 0] + (dx * off if anc != "middle" else 0)
            cy = P[j, 1] + dy * off
            if anc == "middle" and dy == 0:
                continue
            bx = box(cx, cy, t, anc, bold)
            if bx[0] < 0 or bx[2] > Wd or bx[1] < 0 or bx[3] > Hd:
                continue
            if any(hit(bx, o) for o in placed):
                continue
            if any(hit(bx, (P[k, 0] - rad[k], P[k, 1] - rad[k], P[k, 0] + rad[k], P[k, 1] + rad[k])) for k in range(n) if k != j):
                continue
            got = (cx, cy, anc, bx)
            break
        if got is None:
            cx, cy = P[j, 0], P[j, 1] - rad[j] - 3
            got = (cx, cy, "middle", box(cx, cy, t, "middle", bold))
        placed.append(got[3])
        lab[j] = [round(float(got[0] - P[j, 0]), 1), round(float(got[1] - P[j, 1]), 1), got[2], 1 if bold else 0]
    return {"w": Wd, "h": Hd, "p": [[round(float(x), 1), round(float(y), 1)] for x, y in P], "r": [round(float(r), 1) for r in rad],
            "f": [fam_of.get(t, other) for t in tags], "lab": lab, "e": [[a, b, round(float(J[a, b]), 3)] for a, b in sorted(edges)]}


def ladder(mol, FAM):
    """The weight ladder: x = log molecular weight (lightest left), y = family lane (lanes in wheel order, each as tall as
    its molecule count), dots beeswarmed inside their lane so every molecule stays visible. Computed in a nominal
    1000 x 600 px space; molecules without a weight wait in a column at the far right. Deterministic."""
    import math, collections
    H0, GAP, R, D = 600.0, 8.0, 2.7, 5.7
    order = ["Fresh & aldehydic", "Citrus", "Green & herbal", "Floral", "Fruity", "Sweet & gourmand", "Spicy & warm",
             "Amber & musk", "Woody & earthy", "Sharp & other"]
    fidx = {n: k for k, (n, _, _) in enumerate(FAM)}
    N = len(mol)
    cnt = collections.Counter(m[11] for m in mol)
    free = H0 - GAP * (len(order) - 1)
    hs = [max(26.0, free * cnt[fidx[n]] / N) for n in order]
    k = free / sum(hs)
    hs = [h * k for h in hs]
    lanes, y = [], 0.0
    for n, h in zip(order, hs):
        lanes.append([fidx[n], round(y / H0, 4), round((y + h) / H0, 4)])
        y += h + GAP
    mws = [m[17] for m in mol if m[17] is not None]
    lmin, lmax = math.log(min(mws)), math.log(max(mws))
    X0, XW, NONE = 0.12, 0.80, (0.935, 0.985)
    xy = [None] * N
    for f, y0n, y1n in lanes:
        ids = [i for i in range(N) if mol[i][11] == f]
        yc, half = (y0n + y1n) / 2 * H0, (y1n - y0n) / 2 * H0 - R
        px = {}
        for i in ids:
            if mol[i][17] is not None:
                px[i] = (X0 + XW * (math.log(mol[i][17]) - lmin) / (lmax - lmin)) * 1000.0
        none = sorted([i for i in ids if mol[i][17] is None], key=lambda i: mol[i][0])
        for r_, i in enumerate(none):
            px[i] = (NONE[0] + (NONE[1] - NONE[0]) * (r_ + .5) / max(1, len(none))) * 1000.0
        cand = [0.0]
        for j in range(1, 400):
            off = j * 0.5 * D
            if off > half:
                break
            cand += [off, -off]
        placed = []
        for i in sorted(ids, key=lambda i: (px[i], mol[i][0])):
            win = placed[-80:]
            best = None
            for off in cand:
                if all((px[i] - qx) ** 2 + (yc + off - qy) ** 2 >= D * D for qx, qy in win):
                    best = off
                    break
            if best is None:                                   # lane saturated here: the position with the most room
                best = max(cand, key=lambda off: min(((px[i] - qx) ** 2 + (yc + off - qy) ** 2) for qx, qy in win) if win else 0)
            placed.append((px[i], yc + best))
            xy[i] = (round(px[i] / 1000.0, 4), round((yc + best) / H0, 4))
    return {"lanes": lanes, "x0": X0, "xw": XW, "none": list(NONE), "xy": xy}


def main() -> int:
    import numpy as np
    M, E, T = rd("molecules.tsv"), rd("evidence.tsv"), rd("tags.tsv")
    man = json.loads((REL / "manifest.json").read_text(encoding="utf-8"))
    tags = [r["tag"] for r in T]
    ti = {t: i for i, t in enumerate(tags)}
    mi = {r["molecule_id"]: i for i, r in enumerate(M)}
    # The descriptor -> tag table (corpus-level static field A3 of reports/molecule-card-v0.md): the card recomputes each
    # molecule's tags from its descriptor words with it, in the browser. Not part of release/v1.0 yet, so read from ontology/.
    surf = {}
    for line in (ROOT / "ontology" / "odor_terms.tsv").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or "\t" not in line:
            continue
        form, tag = (x.strip() for x in line.split("\t")[:2])
        if tag in ti:
            surf[form.lower()] = ti[tag]

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
    tm = term_map(X, tags, fam_of, len(SB.FAMILIES) - 1)

    def family(i):
        score = collections.Counter()
        for t, c in zip(tags, X[i]):
            if c and t in fam_of:
                score[fam_of[t]] += c * (0.6 if t in SB.GENERIC else 1)
        return score.most_common(1)[0][0] if score else len(SB.FAMILIES) - 1

    c3 = {}
    c3f = ROOT / "corpus" / "3d" / "conformers.json"
    if c3f.exists():                                  # corpus_3d_fetch.py (Hetzner): PubChem's computed conformers
        for ik, v in json.loads(c3f.read_text(encoding="utf-8")).items():
            if v.get("cid") or v.get("c3d"):
                c3[ik] = [v.get("cid"), v.get("c3d") or 0]
    print(f"3D: {sum(1 for v in c3.values() if v[1])} conformers, {sum(1 for v in c3.values() if v[0])} PubChem CIDs", flush=True)
    props = {}
    pf = ROOT / "corpus" / "props" / "pubchem-props.json"      # corpus_props_fetch.py (Hetzner): PubChem-computed
    if pf.exists():
        props = json.loads(pf.read_text(encoding="utf-8"))
    print(f"props: {len(props)} CIDs with formula / MW / XLogP3", flush=True)
    def props_of(i):
        r = M[i]
        cid = (r["pubchem_cids"].split(";")[0] if r["pubchem_cids"] else "") or str((c3.get(r["inchikey"]) or [""])[0] or "")
        v = props.get(cid) or {}
        return [v.get("f") or "", v.get("mw"), v.get("xlogp")]
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
                    ";".join(r["structure_basis"].split(";")), " ".join(docs)[:300], ";".join(descs)[:200]] + props_of(i))
        evid[i] = [[ti[e["tag"]], e["descriptor_span"], e["molecule_span"], e["quote"], e["antecedent"],
                    code(sty, e["source_type"]), e["source_id"], ";".join((e["documents"] or "").split(";")[:6]),
                    e["source_url"], code(how, e["how_decided"])] for e in sorted(es, key=lambda e: (e["tag"], e["evidence_id"]))]

    lad = ladder(mol, SB.FAMILIES)
    for i, xy_ in enumerate(lad["xy"]):
        mol[i] += list(xy_)
    lad_meta = {k_: v_ for k_, v_ in lad.items() if k_ != "xy"}
    c = man["counts"]
    data = {"tm": tm, "lad": lad_meta, "tags": [[r["tag"], int(r["molecules_v1_0"]), 1 if r["at_bar_30"] == "yes" else 0] for r in T],
            "fam": [[n, col] for n, col, _ in SB.FAMILIES], "m": mol, "sty": sty, "how": how,
            "counts": {"molecules": c["molecules"], "with_structure": c["molecules_with_structure"],
                       "name_only": c["molecules_name_only"], "hand": c["structure_hand_derived"],
                       "evidence": c["evidence_rows"], "at_bar": c["terms_at_bar"], "terms": c["terms_total"]},
            "surf": surf,
            "built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"), "head": (man.get("git_head") or "")[:7]}

    def js(o):
        return json.dumps(o, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")

    page = TEMPLATE.replace("/*DATA*/", js(data)).replace("/*EVID*/", js(evid)).replace("/*C3D*/", js(c3))
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size/1e6:.2f} MB)")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenScent corpus — every molecule of v1.0 (candidate)</title>
<meta name="color-scheme" content="light dark">
<script>try{var _t=localStorage.getItem("os-theme");if(_t==="dark"||_t==="light")document.documentElement.dataset.theme=_t}catch(e){}</script>
<meta name="description" content="Every molecule in the OpenScent v1.0 candidate: a CC0 structure–odour corpus built from US patents and US-government databases. Search, filter, read the quote behind every tag, and explore the scent map.">
<meta property="og:title" content="OpenScent corpus — every molecule of v1.0 (candidate)"><meta property="og:type" content="website">
<style>
:root{--paper:#f5f7f9;--card:#fff;--ink:#07111d;--mut:#687383;--faint:#718196;--line:#dce4ee;--line-strong:rgba(29,52,78,.3);
 --blue:#245cff;--blue-deep:#1647d9;--blue-pale:#eef3ff;--amber:#9a6a14;--amber-pale:#fdf6e9;--teal:#0f8f7f;--red:#bc4b47;
 --sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
 --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;--shadow:0 18px 50px rgba(28,60,98,.067);--page:1440px;color-scheme:light;--on:#fff;
 --card2:#fbfcfd;--hover:#f9fbfe;--hoverfill:rgba(7,17,29,.05);--ink2:#33414f;--tbg:rgba(255,255,255,.94);--track:#eef2f7;--low:#9cc9c2;
 --grad:linear-gradient(90deg,#22c1d6,#2b8de0,#5a52d5,#8a2fb0,#3f0d55);--dim:rgba(104,115,131,.16);--nowt:#aab6c3;--stripe:rgba(7,17,29,.035);--grid:rgba(29,52,78,.16);--band:rgba(36,92,255,.07);--bandline:rgba(36,92,255,.55);--bond:rgba(7,17,29,.35)}
:root[data-theme=dark]{--paper:#0b0e14;--card:#141925;--card2:#10151f;--hover:#19202e;--hoverfill:rgba(255,255,255,.07);--ink:#e6edf5;--ink2:#b9c5d3;--mut:#9aa7b8;--faint:#7f8ca0;--line:#232c3b;--line-strong:rgba(170,190,225,.26);--blue:#6f9bff;--blue-deep:#9db8ff;--blue-pale:#16233f;--amber:#e2ae4f;--amber-pale:#2a2212;--teal:#3cc9b4;--red:#ef7b77;--on:#07111d;--shadow:0 18px 50px rgba(0,0,0,.5);--tbg:rgba(11,14,20,.92);--track:#1d2735;--low:#2b6a62;color-scheme:dark;--grad:linear-gradient(90deg,#22c1d6,#4f8dff,#9a6bff,#d86bff,#ff7ac8);--dim:rgba(150,165,185,.2);--nowt:#5b6879;--stripe:rgba(255,255,255,.035);--grid:rgba(160,190,225,.18);--band:rgba(111,155,255,.12);--bandline:rgba(130,170,255,.65);--bond:rgba(0,0,0,.55)}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--paper:#0b0e14;--card:#141925;--card2:#10151f;--hover:#19202e;--hoverfill:rgba(255,255,255,.07);--ink:#e6edf5;--ink2:#b9c5d3;--mut:#9aa7b8;--faint:#7f8ca0;--line:#232c3b;--line-strong:rgba(170,190,225,.26);--blue:#6f9bff;--blue-deep:#9db8ff;--blue-pale:#16233f;--amber:#e2ae4f;--amber-pale:#2a2212;--teal:#3cc9b4;--red:#ef7b77;--on:#07111d;--shadow:0 18px 50px rgba(0,0,0,.5);--tbg:rgba(11,14,20,.92);--track:#1d2735;--low:#2b6a62;color-scheme:dark;--grad:linear-gradient(90deg,#22c1d6,#4f8dff,#9a6bff,#d86bff,#ff7ac8);--dim:rgba(150,165,185,.2);--nowt:#5b6879;--stripe:rgba(255,255,255,.035);--grid:rgba(160,190,225,.18);--band:rgba(111,155,255,.12);--bandline:rgba(130,170,255,.65);--bond:rgba(0,0,0,.55)}}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--blue)}
.topbar{position:sticky;top:0;z-index:6;border-bottom:1px solid var(--line-strong);background:var(--tbg);backdrop-filter:blur(6px)}
.topbar-in{max-width:var(--page);margin:0 auto;padding:10px 28px;min-height:64px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:12px}.glyph{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;background:var(--card);border:1px solid var(--line-strong)}.gk{stroke:var(--ink)}.gb{stroke:var(--blue)}
.wordmark b{display:block;font-size:17px;letter-spacing:-.01em}.wordmark span{font-family:var(--mono);font-size:10px;letter-spacing:.14em;color:var(--mut);text-transform:uppercase}
.nav{display:flex;gap:4px;flex-wrap:wrap}.nav button{font:600 12px var(--mono);letter-spacing:.02em;color:var(--mut);background:transparent;border:0;padding:6px 12px;border-radius:999px;cursor:pointer;white-space:nowrap}
.nav button:hover{background:var(--hoverfill);color:var(--ink)}.nav button.on{background:var(--blue);color:var(--on)}
.tr{display:flex;align-items:center;gap:14px}.themebtn{width:32px;height:32px;border-radius:50%;border:1px solid var(--line-strong);background:var(--card);color:var(--ink);font:15px/1 var(--sans);cursor:pointer;display:grid;place-items:center}.themebtn:hover{border-color:var(--blue);color:var(--blue)}.hl{font:600 12px var(--mono);letter-spacing:.02em;color:var(--blue-deep);text-decoration:none;white-space:nowrap}.hl:hover{text-decoration:underline}
.gl1{font:600 12px var(--mono);letter-spacing:.02em;color:var(--ink);text-decoration:none;border:1px solid var(--line-strong);border-radius:999px;padding:6px 12px;background:var(--card);white-space:nowrap}.gl1:hover{border-color:var(--blue);color:var(--blue)}
.badge{font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;padding:5px 10px;border:1px solid var(--line-strong);color:var(--mut);background:var(--card);white-space:nowrap}
.badge.amber{border-color:rgba(154,106,20,.5);color:var(--amber);background:var(--amber-pale)}
.wrap{max-width:var(--page);margin:0 auto;padding:0 28px 60px}
.lab{display:flex;align-items:center;gap:10px;color:var(--mut);font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.14em;margin-top:30px}
.lab:before{content:"";width:26px;height:1px;background:var(--blue)}
h1{font-size:clamp(26px,4vw,40px);line-height:1.1;letter-spacing:-.025em;margin:10px 0 10px;max-width:900px}
h1 small{font:500 12px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--amber);border:1px solid rgba(154,106,20,.5);background:var(--amber-pale);padding:3px 8px;vertical-align:middle;margin-left:8px}
.lede{max-width:860px;color:var(--ink2);margin:0 0 4px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);margin:22px 0;background:var(--card);border:1px solid var(--line-strong);box-shadow:var(--shadow)}
.stat{padding:15px 18px}.stat+.stat{border-left:1px solid var(--line)}
.stat .k{color:var(--mut);font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.1em}
.stat .v{font-family:var(--mono);font-size:22px;font-weight:500;margin-top:5px}.stat .v small{font-size:12px;color:var(--mut)}
.licbox{border:1px solid var(--line);border-left:3px solid var(--blue);background:var(--card);padding:12px 16px;margin-bottom:14px;font-size:13.5px;color:var(--ink2)}
.licbox b{color:var(--ink)}
.bar{position:sticky;top:var(--tb,64px);z-index:5;display:flex;align-items:center;gap:10px;background:var(--paper);padding:12px 0 14px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.bar input{flex:1;min-width:220px;font:14px var(--sans);padding:11px 14px;border:1px solid var(--line-strong);background:var(--card);color:var(--ink);border-radius:9px;outline:none}
.bar input:focus,.bar select:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(36,92,255,.14)}
.bar select{font:13px var(--mono);padding:10px 12px;border:1px solid var(--line-strong);border-radius:9px;background:var(--card);color:var(--ink);max-width:200px}
.btn{font:500 12px var(--mono);letter-spacing:.04em;padding:10px 14px;border:1px solid var(--line-strong);border-radius:9px;background:var(--card);color:var(--ink);cursor:pointer}.btn:hover{border-color:var(--blue);color:var(--blue)}
.count{font-family:var(--mono);font-size:11.5px;color:var(--mut);white-space:nowrap;margin-left:auto}
.active{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 0;min-height:4px}
.panel{background:var(--card);border:1px solid var(--line-strong);box-shadow:var(--shadow);margin-top:16px;border-top:3px solid var(--blue)}
table{width:100%;border-collapse:collapse}
#v-table .panel{overflow-x:auto}
th{font:500 10px var(--mono);text-transform:uppercase;letter-spacing:.09em;color:var(--mut);text-align:left;padding:10px 14px;border-bottom:1px solid var(--line-strong);background:var(--card2)}
td{font-size:13.5px;padding:10px 14px;border-top:1px solid var(--line);vertical-align:top}
tr.row{cursor:pointer}tr.row:hover td{background:var(--hover)}tr.row.open td{background:var(--blue-pale)}
td.num,th.num{font-family:var(--mono);text-align:right;white-space:nowrap}
th.s{cursor:pointer;user-select:none}th.s:hover{color:var(--blue)}th.s.on{color:var(--blue-deep)}th.s i{font-style:normal;margin-left:4px;color:var(--blue)}
td.fm{font-family:var(--mono);font-size:12px;white-space:nowrap}td.dash,.dash{color:var(--faint)}
.fine{font-size:12px;color:var(--mut);padding:10px 18px 12px;border-top:1px solid var(--line)}
.nm b{font-weight:600}.sub{color:var(--faint);font-size:11.5px;font-family:var(--mono);margin-top:1px;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tag{display:inline-block;font:10px var(--mono);letter-spacing:.06em;text-transform:uppercase;padding:2px 7px;margin:0 4px 4px 0;border:1px solid rgba(15,143,127,.4);color:var(--teal);background:rgba(15,143,127,.06);cursor:pointer}
.tag:hover{background:rgba(15,143,127,.16);border-color:var(--teal)}.tag.on{background:var(--teal);color:var(--on);border-color:var(--teal)}
.st{font:10px var(--mono);letter-spacing:.06em;text-transform:uppercase;padding:2px 7px;border:1px solid var(--line-strong);color:var(--mut);white-space:nowrap}
.st.d{border-color:rgba(15,143,127,.4);color:var(--teal)}.st.h{border-color:rgba(154,106,20,.5);color:var(--amber);background:var(--amber-pale)}.st.n{border-color:rgba(188,75,71,.5);color:var(--red)}
[hidden]{display:none!important}
.more{display:block;width:100%;padding:14px;border:0;border-top:1px solid var(--line);background:var(--card2);font:500 12px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--blue);cursor:pointer}.more:hover{background:var(--blue-pale)}
.empty{padding:40px 18px;text-align:center;color:var(--mut)}
.detail{padding:6px 18px 18px;background:var(--blue-pale);border-top:1px solid var(--line)}
.detail h3{margin:14px 0 4px;font-size:18px;letter-spacing:-.01em}
.kv{display:grid;grid-template-columns:130px 1fr;gap:4px 14px;font-size:12.5px;margin:8px 0 12px}.kv dt{color:var(--mut);font-family:var(--mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;padding-top:2px}
.kv dd{margin:0;font-family:var(--mono);font-size:12px;word-break:break-all}.kv dd.t{font-family:var(--sans);word-break:normal}
.evh{font:500 11px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--teal);margin:14px 0 6px}
.csh{font:500 10.5px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--mut);margin:12px 0 0;padding-bottom:4px;border-bottom:1px solid var(--line)}
.csh b{color:var(--teal);font-weight:600}.csh span{text-transform:none;letter-spacing:0;color:var(--faint)}
.src{display:block;font:10px var(--mono);color:var(--faint);letter-spacing:.03em;margin-top:1px;word-break:normal}
.ok{color:var(--teal)}.warn{color:var(--amber,#b7791f)}
.dtop{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:18px;align-items:start}
.v3d{background:var(--card);border:1px solid var(--line-strong);height:260px;margin:12px 0 4px;touch-action:none;cursor:grab}.v3d canvas{width:100%;height:100%;display:block}
.v3d.none{display:grid;place-items:center;cursor:default;font:11px var(--mono);color:var(--faint);letter-spacing:.06em;text-transform:uppercase;text-align:center;padding:0 14px}
.hint{font:10.5px var(--mono);color:var(--faint);letter-spacing:.04em}
.ev{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--teal);padding:9px 14px;margin-bottom:8px;font-size:13.5px}
.ev .ant{color:var(--faint);font-size:12.5px;margin-bottom:4px}
.ev mark.d{background:rgba(15,143,127,.2);color:inherit;padding:0 2px;border-bottom:2px solid var(--teal)}.ev mark.m{background:rgba(36,92,255,.14);color:inherit;padding:0 2px;border-bottom:2px solid var(--blue)}
.ev .meta{margin-top:6px;font:10.5px var(--mono);color:var(--faint);letter-spacing:.04em}.ev .meta a{margin-right:8px}
.mapwrap{position:relative;padding:0}#cv{display:block;width:100%;cursor:grab;touch-action:none;background:var(--card)}#cv.drag{cursor:grabbing}
.tip{position:absolute;pointer-events:none;background:var(--ink);color:var(--paper);font:12px var(--mono);padding:6px 9px;max-width:300px;z-index:3;display:none}
.zoom{position:absolute;right:12px;top:12px;display:flex;flex-direction:column;gap:6px}.zoom .btn{padding:6px 11px;background:var(--card)}
.legend{display:flex;gap:8px;flex-wrap:wrap;padding:12px 18px;border-top:1px solid var(--line)}
.lg{display:inline-flex;align-items:center;gap:7px;font:11px var(--mono);padding:4px 9px;border:1px solid var(--line-strong);background:var(--card);cursor:pointer;color:var(--ink)}.lg i{width:10px;height:10px;border-radius:50%;display:inline-block}.lg.off{opacity:.4}
.note{font-size:12.5px;color:var(--mut);padding:0 18px 14px}
.tm{display:grid;grid-template-columns:150px 1fr 60px;gap:12px;align-items:center;padding:7px 18px;border-top:1px solid var(--line);cursor:pointer}.tm:hover{background:var(--hover)}
.tm .n{font:12px var(--mono);text-transform:uppercase;letter-spacing:.06em}.tm .b{position:relative;height:12px;background:var(--track)}.tm .b i{display:block;height:100%;background:var(--teal)}.tm .b i.low{background:var(--low)}
.tm .b u{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--amber)}.tm .c{font:12px var(--mono);text-align:right}
.mixrow{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 10px}.mixl{font:11px var(--mono);color:var(--mut);text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}#mix{flex:1;min-width:150px;max-width:340px;accent-color:var(--blue)}
.cseg{display:inline-flex;border:1px solid var(--line-strong);margin-left:6px}.cseg button{font:500 11px var(--mono);padding:6px 10px;border:0;background:var(--card);cursor:pointer;color:var(--mut)}.cseg button+button{border-left:1px solid var(--line)}.cseg button.on{background:var(--blue);color:var(--on)}
.wtctl{padding:14px 18px 6px;border-bottom:1px solid var(--line);background:var(--card2)}.wthead{font-size:13px;color:var(--ink2);margin-bottom:8px;max-width:900px}
#wth{display:block;width:100%;height:56px}
.wtsl{position:relative;height:30px;margin:0 2px}.wtsl:before{content:"";position:absolute;left:0;right:0;top:13px;height:4px;border-radius:2px;background:var(--grad)}
.wtsl input{position:absolute;left:0;width:100%;top:6px;margin:0;height:18px;background:transparent;pointer-events:none;-webkit-appearance:none;appearance:none}
.wtsl input::-webkit-slider-runnable-track{background:transparent;height:18px}.wtsl input::-moz-range-track{background:transparent}
.wtsl input::-webkit-slider-thumb{-webkit-appearance:none;pointer-events:auto;width:18px;height:18px;border-radius:50%;background:var(--card);border:2px solid var(--ink);cursor:grab;box-shadow:0 1px 4px rgba(7,17,29,.25)}
.wtsl input::-moz-range-thumb{pointer-events:auto;width:14px;height:14px;border-radius:50%;background:var(--card);border:2px solid var(--ink);cursor:grab}
.wtrow{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:2px 0 10px}.wtrow .count{margin-left:0;flex:1;min-width:220px;white-space:normal}
.gl{display:inline-flex;align-items:center;gap:8px;font:11px var(--mono);color:var(--ink)}.grad{display:inline-block;width:200px;height:10px;border:1px solid var(--line-strong);background:var(--grad)}.gl2{font:11px var(--mono);color:var(--mut);margin-left:6px}
.tmwrap{overflow-x:auto}.tmsvg{display:block;width:100%;min-width:720px;height:auto;background:var(--card)}
.tmsvg text{font:11px var(--sans);fill:var(--ink);paint-order:stroke;stroke:var(--card);stroke-width:3.4px;stroke-linejoin:round;pointer-events:none}.tmsvg text.b{font-weight:600}.tmsvg circle.ring{stroke:var(--ink)}
.tmsvg .tn{cursor:pointer}.tmsvg .tn:hover circle{stroke:var(--blue);stroke-width:3}
footer{max-width:var(--page);margin:0 auto;padding:10px 28px 50px;color:var(--mut);font-size:12.5px}footer p{max-width:900px}
@media(max-width:760px){.nav{order:3;width:100%;overflow-x:auto;flex-wrap:nowrap}.nav button{padding:6px 10px}.tr{order:2;margin-left:auto}.hl,.wordmark span,.opt{display:none}.gl1{font-size:10.5px;padding:5px 9px}.wrap,.topbar-in,footer{padding-left:16px;padding-right:16px}.stats{grid-template-columns:repeat(2,1fr)}.stat:nth-child(3){border-left:0}.stat:nth-child(n+3){border-top:1px solid var(--line)}
 th.hide,td.hide{display:none}td,th{padding:9px 10px}.sub{max-width:38vw}.nm b{overflow-wrap:anywhere}.kv{grid-template-columns:1fr}.dtop{grid-template-columns:1fr}.tm{grid-template-columns:110px 1fr 46px}.bar{top:0;position:static}.count{margin-left:0}}
</style></head><body>
<header class="topbar"><div class="topbar-in">
 <div class="brand"><div class="glyph"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 9.2 13.8 11.7V16.7L9.5 19.2 5.2 16.7V11.7Z" class="gk" stroke-width="1.5"/><circle cx="9.5" cy="14.2" r="2.3" class="gb" stroke-width="1.3"/><path d="M13.8 11.7C15.9 10.6 14.7 8.4 16.7 7.2 18.7 6 17.7 3.8 19.9 2.8" class="gb" stroke-width="1.5"/></svg></div>
 <div class="wordmark"><b>OpenScent</b><span>Odour corpus · molecules</span></div></div>
 <nav class="nav" id="tabs"><button data-v="table" class="on">Table</button><button data-v="map">Scent map</button><button data-v="mw">Weight map</button><button data-v="terms">Term map</button></nav>
 <div class="tr"><a class="hl" href="https://github.com/VanPez/openscent" target="_blank" rel="noopener">GitHub ↗</a><a class="gl1" href="https://genesisl1.com" target="_blank" rel="noopener"><span class="opt">A </span>GenesisL1<span class="opt"> project</span> ↗</a><button class="themebtn" id="themebtn" aria-label="Switch to dark mode" title="Light / dark">☾</button></div>
</div></header>
<main class="wrap">
 <div class="lab">The corpus</div>
 <h1>Every molecule in OpenScent v1.0<small>candidate</small></h1>
 <p class="lede">A CC0 structure–odour corpus built only from US patents and US-government databases. Each odour tag below is a word quoted verbatim from its source, with the sentence one click away. Nothing is generated.</p>
 <div class="stats" id="stats"></div>
 <div class="licbox" id="lic"></div>
 <div class="bar" id="bar">
  <input id="q" type="search" placeholder="Search a name, InChIKey, patent number or odour word…" aria-label="Search">
  <select id="ftag" aria-label="Odour term"></select>
  <select id="fstr" aria-label="Structure"><option value="">any structure</option><option value="direct">structure read directly</option><option value="hand-derived">structure hand-derived</option><option value="none">no structure</option></select>
  <select id="fsrc" aria-label="Source"><option value="">any source</option><option value="0">patent text only</option><option value="1">government database only</option><option value="2">both</option></select>
  <button class="btn" id="reset">Reset</button><span class="count" id="count"></span>
 </div>
 <div class="active" id="active"></div>
 <section id="v-table"><div class="panel"><table><thead><tr id="thr"><th class="s" data-s="label">Molecule<i></i></th><th>Odour tags</th><th class="s hide" data-s="formula">Formula<i></i></th><th class="s num hide" data-s="mw">MW<i></i></th><th class="s num hide" data-s="xlogp">XLogP3<i></i></th><th class="s num hide" data-s="ev">Quotes<i></i></th><th class="hide">Structure</th></tr></thead><tbody id="tb"></tbody></table><button class="more" id="more" hidden></button><div class="empty" id="empty" hidden>No molecule matches these filters.</div><div class="fine">Formula, MW and XLogP3 are values computed by PubChem (NCBI) and read from its record for the molecule; a dash means PubChem has no record for this exact structure, or no value. Click a column head to sort.</div></div></section>
 <section id="v-map" hidden><div class="panel">
  <div class="wtctl" id="wtctl" hidden>
   <div class="wthead"><b>Lightest to heaviest.</b> Here the dots are placed by molecular weight, in rows by family. Drag the blend slider to melt them back into the scent map, drag the two weight handles to keep a band, or press Sweep.</div>
   <div class="mixrow"><span class="mixl">Scent map</span><input type="range" id="mix" min="0" max="1000" value="1000" aria-label="Blend between the scent map and the weight ladder"><span class="mixl">Weight ladder</span><span class="cseg" id="colseg"><button data-c="mw" class="on">Colour: weight</button><button data-c="fam">Colour: family</button></span></div>
   <canvas id="wth" height="56"></canvas>
   <div class="wtsl"><input type="range" id="wtlo" min="0" max="1000" value="0" aria-label="Lightest molecule shown"><input type="range" id="wthi" min="0" max="1000" value="1000" aria-label="Heaviest molecule shown"></div>
   <div class="wtrow"><span class="count" id="wtlab"></span><button class="btn" id="wtplay">▶ Sweep light → heavy</button><button class="btn" id="wtclear">Clear band</button></div>
  </div>
  <div class="mapwrap" id="mw"><canvas id="cv"></canvas><div class="tip" id="tip"></div><div class="zoom"><button class="btn" id="zi" aria-label="Zoom in">+</button><button class="btn" id="zo" aria-label="Zoom out">−</button><button class="btn" id="zr" aria-label="Reset view">⌂</button></div></div>
  <div class="legend" id="legend"></div>
  <div class="note" id="mapnote">Each dot is a molecule, placed by how its sources describe it (the pattern of odour tags; t-SNE). Molecules with the same pattern form a tight group; position inside a group means nothing. Drag to pan, scroll to zoom, click a dot to read its quotes. Colours are a display aid, not a classification. <b>Close on the map means described alike, not smelling alike.</b></div>
  <div id="mapdetail"></div></div></section>
 <section id="v-terms" hidden><div class="panel"><div class="note" style="padding-top:12px">The 67 odour terms, not the molecules. Dot area = molecules carrying the term; a dark ring = the term reaches the 30-molecule bar; lines join terms that often appear on the same molecules (same method as the scent map, so distances are approximate). Click a term to list its molecules.</div>
  <div class="tmwrap"><svg id="tsvg" class="tmsvg" role="img" aria-label="Map of the 67 odour terms"></svg></div><div class="legend" id="tlegend"></div>
  <div class="note" style="padding-top:14px;border-top:1px solid var(--line)"><b>The same terms by number of molecules.</b> The amber mark is the 30-molecule bar.</div><div id="terms"></div></div></section>
</main>
<footer><p id="foot"></p><p>CC0 1.0 for the data; code Apache-2.0. A molecule appearing here says nothing about live patent claims covering it. Odour words describe what the sources say about smell; they are not claims about health or effects. Rows set aside by the model screen were not read by a human, so absence here is a recall limit, not a judgement.</p></footer>
<script id="data" type="application/json">/*DATA*/</script>
<script id="evid" type="application/json">/*EVID*/</script>
<script id="c3d" type="application/json">/*C3D*/</script>
<script>
(function(){'use strict';
const D=JSON.parse(document.getElementById('data').textContent);let EV=null;
const ev=()=>EV||(EV=JSON.parse(document.getElementById('evid').textContent));
const TAGS=D.tags,FAM=D.fam,M=D.m,C=D.counts;const C3=JSON.parse(document.getElementById('c3d').textContent);const HAS3=Object.keys(C3).length>0;
const F={label:0,spell:1,smiles:2,ik:3,tags:4,nev:5,ndoc:6,str:7,cid:8,x:9,y:10,fam:11,src:12,basis:13,docs:14,descs:15,formula:16,mw:17,xlogp:18,lx:19,ly:20};
const STR=['direct','hand-derived','none'],STRL=['structure read directly','structure hand-derived','no structure'],STRC=['d','h','n'];
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt=n=>n.toLocaleString('en-US');
const root=document.documentElement,TH={mode:'light',dark:false,ink:'#07111d',blue:'#245cff',mut:'#687383',dim:'rgba(104,115,131,.16)',nowt:'#aab6c3',stripe:'rgba(7,17,29,.035)',grid:'rgba(29,52,78,.16)',band:'rgba(36,92,255,.07)',bandLine:'rgba(36,92,255,.55)',bond:'rgba(7,17,29,.35)'};
function refreshTheme(){const dark=root.dataset.theme==='dark'||(!root.dataset.theme&&window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches);TH.dark=dark;TH.mode=dark?'dark':'light';const cs=getComputedStyle(root),g=n=>cs.getPropertyValue(n).trim();
 TH.ink=g('--ink');TH.blue=g('--blue');TH.mut=g('--mut');TH.dim=g('--dim');TH.nowt=g('--nowt');TH.stripe=g('--stripe');TH.grid=g('--grid');TH.band=g('--band');TH.bandLine=g('--bandline');TH.bond=g('--bond');EC=dark?EC_D:EC_L;
 const b=$('themebtn');b.textContent=dark?'☀':'☾';b.setAttribute('aria-label',dark?'Switch to light mode':'Switch to dark mode');if(typeof draw==='function'&&cx)draw();if(st.view==='mw'&&typeof wtHist==='function')wtHist()}
const st={view:'table',q:'',tags:[],str:'',src:'',shown:80,open:-1,sel:-1,fams:new Set(),sk:'label',sd:1,cmode:'fam',wcol:'mw',mt:0,mix:1,mwlo:null,mwhi:null};
const H=M.map(m=>(m[F.label]+' '+m[F.spell]+' '+m[F.ik]+' '+m[F.tags].map(t=>TAGS[t][0]).join(' ')+' '+m[F.descs]+' '+m[F.docs]+' '+m[F.formula]).toLowerCase());
const order=M.map((_,i)=>i).sort((a,b)=>M[b][F.nev]-M[a][F.nev]||M[a][F.label].localeCompare(M[b][F.label]));
function match(i){const m=M[i];
 if(st.tags.length&&!st.tags.every(t=>m[F.tags].includes(t)))return false;
 if(st.str!==''&&STR[m[F.str]]!==st.str)return false;
 if(st.src!==''&&String(m[F.src])!==st.src)return false;
 if(st.mwlo!==null||st.mwhi!==null){const v=m[F.mw];if(v===null||(st.mwlo!==null&&v<st.mwlo-1e-9)||(st.mwhi!==null&&v>st.mwhi+1e-9))return false}
 if(st.q&&!st.q.split(/\s+/).every(w=>H[i].includes(w)))return false;return true}
let hits=[];
function labkey(l){l=l.toLowerCase();let i=l.search(/\p{L}{3}/u);if(i<0)i=Math.max(0,l.search(/\p{L}/u));return l.slice(i)+'\u0000'+l}
function sortVal(i){const m=M[i];return st.sk==='label'?labkey(m[F.label]):st.sk==='formula'?m[F.formula]:st.sk==='mw'?m[F.mw]:st.sk==='xlogp'?m[F.xlogp]:m[F.nev]}
function sortHits(){if(st.sk==='ev'&&st.sd===-1)return;const d=st.sd;hits.sort((a,b)=>{const x=sortVal(a),y=sortVal(b),nx=x===null||x===''||x===undefined,ny=y===null||y===''||y===undefined;
 if(nx||ny)return nx&&ny?0:nx?1:-1;return (x<y?-1:x>y?1:0)*d||M[b][F.nev]-M[a][F.nev]})}
function heads(){document.querySelectorAll('#thr th.s').forEach(t=>{const on=t.dataset.s===st.sk;t.classList.toggle('on',on);t.querySelector('i').textContent=on?(st.sd===1?'▲':'▼'):''})}
function refilter(){hits=order.filter(match);sortHits();heads();$('count').textContent=fmt(hits.length)+' of '+fmt(M.length)+' molecules';
 const a=$('active');a.innerHTML=st.tags.map(t=>'<span class="tag on" data-t="'+t+'">'+esc(TAGS[t][0])+' ✕</span>').join('')+((st.mwlo!==null||st.mwhi!==null)?'<span class="tag on" data-mw="1">MW '+fmtmw(st.mwlo===null?Math.exp(lmin):st.mwlo)+'–'+fmtmw(st.mwhi===null?Math.exp(lmax):st.mwhi)+' g/mol ✕</span>':'');
 $('ftag').value=st.tags.length===1?String(st.tags[0]):'';}
function chips(m){return m[F.tags].map(t=>'<span class="tag'+(st.tags.includes(t)?' on':'')+'" data-t="'+t+'">'+esc(TAGS[t][0])+'</span>').join('')}
function fmtF(f){return esc(f).replace(/(\d+)/g,'<sub>$1</sub>')}
function strb(m){const k=m[F.str];return '<span class="st '+STRC[k]+'">'+(k===0?'direct':k===1?'hand-derived':'no structure')+'</span>'}
function hl(q,d,mo){const R=[];const add=(s,c)=>{if(!s)return;const k=q.indexOf(s);if(k<0)return;if(R.some(r=>k<r[1]&&k+s.length>r[0]))return;R.push([k,k+s.length,c])};
 add(d,'d');add(mo,'m');R.sort((a,b)=>a[0]-b[0]);let o='',p=0;for(const r of R){o+=esc(q.slice(p,r[0]))+'<mark class="'+r[2]+'">'+esc(q.slice(r[0],r[1]))+'</mark>';p=r[1]}return o+esc(q.slice(p))}
function srcLink(e){const id=e[6];if(/^US\d/.test(id))return '<a href="https://patents.google.com/patent/'+encodeURIComponent(id)+'" target="_blank" rel="noopener">'+esc(id)+'</a>';
 return e[8]?'<a href="'+esc(e[8])+'" target="_blank" rel="noopener">'+esc(id||'source')+'</a>':esc(id)}
function v3dBox(i){const m=M[i],c3=C3[m[F.ik]];if(m[F.str]===2)return '';
 if(c3&&c3[1])return '<div class="v3dwrap"><div class="v3d"><canvas class="v3dc" data-i="'+i+'"></canvas></div><div class="hint">Drag to rotate · scroll to zoom · PubChem computed conformer (CID '+c3[0]+')</div></div>';
 return '<div class="v3dwrap"><div class="v3d none">'+(!HAS3?'3D not built into this page yet':c3&&c3[0]?'PubChem has no 3D conformer for this compound':'No PubChem record for this exact structure')+'</div></div>'}
/* Molecule card v0 (reports/molecule-card-v0.md): computed fields in the browser.
   SMILES -> molecular formula (Hill order) and average molecular mass. No library. Standard atomic weights (IUPAC 2007,
   the set PubChem's computed weights match). Handles the organic subset with implicit hydrogens, bracket atoms (H count,
   charge, isotope ignored for mass), branches, ring closures (incl. %nn), bond symbols, '.' components, aromatic lowercase. */
const AW={H:1.00794,He:4.002602,Li:6.941,Be:9.012182,B:10.811,C:12.0107,N:14.0067,O:15.9994,F:18.9984032,Ne:20.1797,Na:22.98976928,
Mg:24.305,Al:26.9815386,Si:28.0855,P:30.973762,S:32.065,Cl:35.453,Ar:39.948,K:39.0983,Ca:40.078,Sc:44.955912,Ti:47.867,V:50.9415,
Cr:51.9961,Mn:54.938045,Fe:55.845,Co:58.933195,Ni:58.6934,Cu:63.546,Zn:65.38,Ga:69.723,Ge:72.630,As:74.9216,Se:78.971,Br:79.904,
Kr:83.798,Rb:85.4678,Sr:87.62,Y:88.90585,Zr:91.224,Nb:92.90638,Mo:95.96,Ru:101.07,Rh:102.9055,Pd:106.42,Ag:107.8682,Cd:112.411,
In:114.818,Sn:118.71,Sb:121.76,Te:127.6,I:126.90447,Xe:131.293,Cs:132.9054519,Ba:137.327,La:138.90547,Ce:140.116,Nd:144.242,
W:183.84,Re:186.207,Os:190.23,Ir:192.217,Pt:195.084,Au:196.966569,Hg:200.59,Tl:204.3833,Pb:207.2,Bi:208.9804,U:238.02891};
const ISO={'2H':2.0141017778,'3H':3.0160492777,'13C':13.0033548378,'14C':14.0032419894,'15N':15.0001088982,'17O':16.999131757,'18O':17.9991596129};
const ORGV={B:[3],C:[4],N:[3,5],O:[2],P:[3,5],S:[2,4,6],F:[1],Cl:[1],Br:[1],I:[1]};
function smiChem(s){
 const A=[],stack=[],ring={};let prev=-1,bond=0,i=0,charge=0;
 const link=(a,b,o)=>{A[a].v+=o;A[b].v+=o};
 while(i<s.length){const ch=s[i];
  if(ch==='('){stack.push(prev);i++;continue}
  if(ch===')'){prev=stack.pop();i++;continue}
  if(ch==='.'){prev=-1;bond=0;i++;continue}
  if('-=#$:/\\'.indexOf(ch)>=0){bond=ch==='='?2:ch==='#'?3:ch==='$'?4:ch===':'?1.5:(ch==='-'?1:bond||0);if(ch==='/'||ch==='\\')bond=bond||0;i++;continue}
  if(/[0-9%]/.test(ch)){let n;if(ch==='%'){n=s.substr(i+1,2);i+=3}else{n=ch;i++}
   if(ring[n]){const r=ring[n],o=bond||r.b||(A[prev].ar&&A[r.a].ar?1.5:1);link(prev,r.a,o);delete ring[n]}else ring[n]={a:prev,b:bond};bond=0;continue}
  let a;
  if(ch==='['){const j=s.indexOf(']',i);if(j<0)return null;const t=s.slice(i+1,j);i=j+1;
   const m=t.match(/^(\d*)([A-Z][a-z]?|se|as|[bcnops]|\*)(@(?:@|TH[12]|AL[12]|SP[123]|TB\d{1,2}|OH\d{1,2})?)?(H\d*)?([+-]+\d*)?(:\d+)?$/);if(!m)return null;
   let el=m[2],ar=false;if(/^[a-z]/.test(el)){ar=true;el=el[0].toUpperCase()+el.slice(1)}
   const h=m[4]?(m[4].length>1?+m[4].slice(1):1):0;
   if(m[5]){const sg=m[5][0]==='+'?1:-1,rest=m[5].slice(1);charge+=sg*(/^\d+$/.test(rest)?+rest:m[5].length)}
   a={el,br:true,h,v:0,ar,iso:m[1]?m[1]+el:''}}
  else{const two=s.substr(i,2);let el;
   if(two==='Cl'||two==='Br'){el=two;i+=2}else if(/[BCNOPSFI]/.test(ch)){el=ch;i++}
   else if(/[bcnops]/.test(ch)){el=ch.toUpperCase();i++;a={el,br:false,v:0,ar:true}}
   else return null;
   a=a||{el,br:false,v:0,ar:false}}
  A.push(a);const k=A.length-1;
  if(prev>=0)link(prev,k,bond||(A[prev].ar&&a.ar?1.5:1));bond=0;prev=k}
 if(Object.keys(ring).length)return null;
 const cnt={};let dm=0;const add=(e,n)=>{if(n)cnt[e]=(cnt[e]||0)+n};
 for(const a of A){if(!(a.el in AW))return null;add(a.el,1);if(a.iso&&ISO[a.iso])dm+=ISO[a.iso]-AW[a.el];
  if(a.br){add('H',a.h);continue}
  const vs=ORGV[a.el];if(!vs)continue;let v=a.ar?Math.floor(a.v)+1:Math.round(a.v);
  const val=vs.find(x=>x>=v);if(val!==undefined)add('H',val-v)}
 const keys=Object.keys(cnt);const hill=('C' in cnt)?['C','H'].filter(e=>e in cnt).concat(keys.filter(e=>e!=='C'&&e!=='H').sort()):keys.sort();
 const f=hill.map(e=>e+(cnt[e]>1?cnt[e]:'')).join('')+(charge?(charge>0?'+':'-')+(Math.abs(charge)>1?Math.abs(charge):''):'');
 const mw=keys.reduce((s,e)=>s+AW[e]*cnt[e],0)+dm;
 return {f,mw}}
/* Checked 2026-10-21 against PubChem: the same formula for all 1,647 v1.0 molecules with a PubChem record; mass within PubChem's own precision for 1,643 (the other 4 are one-decimal rounding). */
function cardTags(E){const out={};for(const e of E){const w=(e[1]||'').toLowerCase(),t=D.surf[w];if(t===undefined)continue;const a=out[t]=out[t]||[];if(a.indexOf(w)<0)a.push(w)}return out}

function detail(i){const m=M[i],E=ev()[i]||[],c3=C3[m[F.ik]],cid=m[F.cid]||(c3&&c3[0])||'';
 const pc=cid?'https://pubchem.ncbi.nlm.nih.gov/compound/'+cid:(m[F.ik]?'https://pubchem.ncbi.nlm.nih.gov/#query='+m[F.ik]:'');
 const ch=m[F.smiles]?smiChem(m[F.smiles]):null,ct=cardTags(E),ctk=Object.keys(ct).map(Number);
 const same=ctk.length===m[F.tags].length&&ctk.every(t=>m[F.tags].includes(t)),pl=(n,w)=>n+' '+w+(n===1?'':'s');
 let h='<div class="detail"><h3>'+esc(m[F.label])+'</h3><div class="dtop"><div>';
 h+='<div class="csh"><b>Stored</b> · static fields <span>— what a token would carry (molecule card v0, a draft)</span></div><dl class="kv">';
 h+='<dt>Structure</dt><dd>'+(m[F.smiles]?esc(m[F.smiles])+'<span class="src">SMILES</span>':'<span class="dash t">none: known by its name only, so no token</span>')+'</dd>';
 h+='<dt>Names</dt><dd class="t">'+esc(m[F.label])+(m[F.spell]&&m[F.spell]!==m[F.label]?'<span class="src">as printed in the sources: '+esc(m[F.spell])+'</span>':'')+'</dd>';
 h+='<dt>Provenance</dt><dd class="t">'+STRL[m[F.str]]+(m[F.basis]?' ('+esc(m[F.basis].replace(/;/g,', '))+')':'')+(m[F.str]===1?'<span class="src">a hand-authorised reading; its reason is in corpus/structures/rewrites.json</span>':'')+(m[F.str]===2?'<span class="src">counted by its name text alone</span>':'')+'</dd>';
 h+='<dt>Evidence</dt><dd class="t">'+pl(E.length,'verbatim quote')+', below, each with its source</dd>';
 if(pc)h+='<dt>Links</dt><dd class="t"><a href="'+esc(pc)+'" target="_blank" rel="noopener">PubChem'+(cid?' '+esc(String(cid)):'')+' ↗</a></dd>';
 h+='</dl><div class="csh"><b>Computed</b> · derived fields <span>— never stored; recomputed from the stored ones</span></div><dl class="kv">';
 if(ch){h+='<dt>Formula</dt><dd class="t">'+fmtF(ch.f)+'<span class="src">in your browser, from the SMILES'+(m[F.formula]?(m[F.formula]===ch.f?' · <span class="ok">same as PubChem</span>':' · <span class="warn">PubChem gives '+esc(m[F.formula])+'</span>'):'')+'</span></dd>';
  h+='<dt>Mol. mass</dt><dd class="t">'+ch.mw.toFixed(2)+' g/mol<span class="src">in your browser, from the formula'+(m[F.mw]!==null&&m[F.mw]!==undefined&&m[F.mw]!==''?' · PubChem gives '+m[F.mw]:'')+'</span></dd>'}
 else if(m[F.smiles])h+='<dt>Formula</dt><dd class="t"><span class="dash">this SMILES is beyond the small parser</span></dd>';
 if(m[F.ik])h+='<dt>InChIKey</dt><dd>'+esc(m[F.ik])+'<span class="src">from the structure, by the release build (not in your browser yet)</span></dd>';
 h+='<dt>Odour tags</dt><dd class="t">'+(ctk.length?ctk.map(t=>esc(TAGS[t][0])+' <span class="dash">← '+esc(ct[t].join(', '))+'</span>').join(' · '):'<span class="dash">none</span>')+'<span class="src">in your browser, from the descriptor words and the tag table (ontology/odor_terms.tsv)'+(same?'':' · <span class="warn">differs from the release</span>')+'</span></dd>';
 h+='<dt>Counts</dt><dd class="t">'+pl(E.length,'quote')+' · '+pl(m[F.ndoc],'document')+' · '+pl(ctk.length,'tag')+'</dd>';
 if(m[F.formula])h+='<dt>XLogP3</dt><dd class="t">'+(m[F.xlogp]===null?'<span class="dash">not available</span>':m[F.xlogp])+'<span class="src">computed by PubChem, not recomputed here</span></dd>';
 h+='</dl></div>'+v3dBox(i)+'</div>';
 h+='<div class="csh"><b>Stored</b> · evidence <span>— the verbatim sentences, grouped by the tag their words map to</span></div>';
 const by={};E.forEach(e=>{(by[e[0]]=by[e[0]]||[]).push(e)});
 Object.keys(by).forEach(t=>{h+='<div class="evh">'+esc(TAGS[t][0])+' · '+by[t].length+'</div>';
  by[t].forEach(e=>{h+='<div class="ev">'+(e[4]?'<div class="ant">Preceding sentence: '+esc(e[4])+'</div>':'')+'“'+hl(e[3],e[1],e[2])+'”<div class="meta">'+srcLink(e)+(e[7]&&e[7].indexOf(';')>=0?'also in '+esc(e[7].split(';').slice(1,4).join(', '))+' · ':'')+esc(D.sty[e[5]])+' · '+esc(D.how[e[9]])+'</div></div>'})});
 return h+'</div>'}
function renderTable(){const tb=$('tb');const rows=hits.slice(0,st.shown);let h='';
 for(const i of rows){const m=M[i],sub=m[F.spell]&&m[F.spell]!==m[F.label]?m[F.spell]:'';
  h+='<tr class="row'+(st.open===i?' open':'')+'" data-i="'+i+'"><td class="nm"><b>'+esc(m[F.label])+'</b>'+(sub?'<div class="sub">'+esc(sub)+'</div>':'')+'</td><td>'+chips(m)+'</td><td class="fm hide'+(m[F.formula]?'':' dash')+'">'+(m[F.formula]?fmtF(m[F.formula]):'—')+'</td><td class="num hide'+(m[F.mw]===null?' dash':'')+'">'+(m[F.mw]===null?'—':m[F.mw].toFixed(2))+'</td><td class="num hide'+(m[F.xlogp]===null?' dash':'')+'">'+(m[F.xlogp]===null?'—':m[F.xlogp])+'</td><td class="num hide">'+m[F.nev]+'</td><td class="hide">'+strb(m)+'</td></tr>';
  if(st.open===i)h+='<tr><td colspan="7" style="padding:0">'+detail(i)+'</td></tr>'}
 tb.innerHTML=h;after(tb);$('empty').hidden=hits.length>0;const mo=$('more');mo.hidden=hits.length<=st.shown;mo.textContent='Show '+Math.min(80,hits.length-st.shown)+' more of '+fmt(hits.length-st.shown)+' remaining'}
/* built-in 3D viewer: no library, no network. Ball-and-stick, depth-sorted, CPK-style colours (same as the preview). */
const EC_L={1:["#f4f6f8",.22],6:["#3c4652",.34],7:["#2f5bea",.34],8:["#d6453d",.34],9:["#5fbf8a",.3],15:["#e08a2b",.42],16:["#e2b32b",.42],17:["#1f9e5a",.4],35:["#a1401d",.44],53:["#7a3fa0",.48]};
const EC_D=Object.assign({},EC_L,{6:["#a3b2c4",.34],7:["#5f86ff",.34]});let EC=EC_L;
const shade=(h,f)=>"#"+[1,3,5].map(i=>Math.round(parseInt(h.slice(i,i+2),16)*f).toString(16).padStart(2,"0")).join("");
function mol3d(cv,c){const ctx=cv.getContext("2d"),dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;cv.width=W*dpr;cv.height=H*dpr;ctx.scale(dpr,dpr);
 const n=c.xyz.length,cen=[0,1,2].map(k=>c.xyz.reduce((s,p)=>s+p[k],0)/n),P=c.xyz.map(p=>p.map((v,k)=>v-cen[k]));
 const R=Math.max(...P.map(p=>Math.hypot(p[0],p[1],p[2])))+.9;let yaw=.6,pitch=-.35,zoom=1,auto=true,drag=null;
 function draw(){ctx.clearRect(0,0,W,H);const s=Math.min(W,H)/(2*R)*zoom,cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
  const T=P.map(([x,y,z])=>{const x1=x*cy+z*sy,z1=-x*sy+z*cy;return [W/2+x1*s,H/2-(y*cp-z1*sp)*s,y*sp+z1*cp]});
  const items=c.b.map(([a,b,o])=>({z:(T[a][2]+T[b][2])/2-.05,a,b,o}));T.forEach((p,i)=>items.push({z:p[2],i}));items.sort((u,v)=>u.z-v.z);
  for(const it of items){if(it.i===undefined){const A=T[it.a],B=T[it.b],dx=B[0]-A[0],dy=B[1]-A[1],L=Math.hypot(dx,dy)||1,nx=-dy/L,ny=dx/L;
    const offs=it.o===2?[-2.4,2.4]:it.o===3?[-3.6,0,3.6]:[0];const ca=(EC[c.el[it.a]]||["#b36bd6"])[0],cb=(EC[c.el[it.b]]||["#b36bd6"])[0];
    for(const o of offs){const ax=A[0]+nx*o,ay=A[1]+ny*o,bx=B[0]+nx*o,by=B[1]+ny*o,mx=(ax+bx)/2,my=(ay+by)/2;
     ctx.lineCap="round";ctx.lineWidth=offs.length>1?2.6:4.2;ctx.strokeStyle=TH.bond;ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(bx,by);ctx.stroke();ctx.lineWidth-=1.6;
     ctx.strokeStyle=shade(ca==="#f4f6f8"?"#c9d0d8":ca,1);ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(mx,my);ctx.stroke();
     ctx.strokeStyle=shade(cb==="#f4f6f8"?"#c9d0d8":cb,1);ctx.beginPath();ctx.moveTo(mx,my);ctx.lineTo(bx,by);ctx.stroke()}
   }else{const [x,y]=T[it.i],[col,r]=EC[c.el[it.i]]||["#b36bd6",.38],rad=Math.max(2,r*s*.9);
    const g=ctx.createRadialGradient(x-rad*.35,y-rad*.4,rad*.08,x,y,rad);g.addColorStop(0,"#ffffff");g.addColorStop(.3,col);g.addColorStop(1,shade(col,.55));
    ctx.fillStyle=g;ctx.beginPath();ctx.arc(x,y,rad,0,7);ctx.fill();ctx.lineWidth=.6;ctx.strokeStyle="rgba(7,17,29,.3)";ctx.stroke()}}}
 (function frame(){if(!cv.isConnected)return;if(cv.offsetParent!==null){if(auto)yaw+=.005;draw()}requestAnimationFrame(frame)})();
 cv.addEventListener("pointerdown",e=>{drag=[e.clientX,e.clientY];auto=false;cv.setPointerCapture(e.pointerId);cv.parentNode.style.cursor="grabbing"});
 cv.addEventListener("pointermove",e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*.01;pitch=Math.max(-1.5,Math.min(1.5,pitch+(e.clientY-drag[1])*.01));drag=[e.clientX,e.clientY]});
 cv.addEventListener("pointerup",()=>{drag=null;cv.parentNode.style.cursor="grab"});
 cv.addEventListener("wheel",e=>{e.preventDefault();zoom=Math.max(.5,Math.min(3,zoom*Math.exp(-e.deltaY*.0015)))},{passive:false})}
function after(el){el.querySelectorAll('canvas.v3dc').forEach(c=>{if(c.offsetParent!==null&&!c.dataset.on){c.dataset.on=1;const v=C3[M[+c.dataset.i][F.ik]];if(v&&v[1])mol3d(c,v[1])}})}
/* ---------------- map */
const cv=$('cv'),cx=cv.getContext('2d');let W=800,Hh=520,dpr=1,V={k:1,tx:0,ty:0},hov=-1,hitset=new Set();
const PAD=24,sx=x=>PAD+x*(W-2*PAD)*V.k+V.tx,sy=y=>PAD+y*(Hh-2*PAD)*V.k+V.ty;
function fit(){const r=$('mw').getBoundingClientRect();W=Math.max(300,r.width);Hh=Math.round(Math.min(Math.max(380,W*.62),740));dpr=window.devicePixelRatio||1;cv.width=W*dpr;cv.height=Hh*dpr;cv.style.height=Hh+'px';cx.setTransform(dpr,0,0,dpr,0,0)}
let EE=0;const easeT=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
const X_=i=>M[i][F.x]+(M[i][F.lx]-M[i][F.x])*EE,Y_=i=>M[i][F.y]+(M[i][F.ly]-M[i][F.y])*EE;
function drawLadder(){const a=EE;if(a<.02)return;const L=D.lad;cx.save();cx.globalAlpha=a;
 L.lanes.forEach((l,k)=>{if(k%2){const y0=sy(l[1]),y1=sy(l[2]);cx.fillStyle=TH.stripe;cx.fillRect(sx(0),Math.min(y0,y1),sx(1)-sx(0),Math.abs(y1-y0))}});
 cx.font='10px ui-monospace,Menlo,monospace';cx.textAlign='center';
 [20,50,100,200,400,800].forEach(v=>{const x=sx(L.x0+L.xw*(Math.log(v)-lmin)/(lmax-lmin));cx.strokeStyle=TH.grid;cx.lineWidth=1;cx.setLineDash([2,4]);cx.beginPath();cx.moveTo(x,sy(0));cx.lineTo(x,sy(1));cx.stroke();cx.setLineDash([]);cx.fillStyle=TH.mut;cx.fillText(v,x,Hh-7)});
 cx.fillText('no weight',sx((L.none[0]+L.none[1])/2),Hh-7);cx.textAlign='left';cx.fillText('g/mol',8,Hh-7);
 if(st.mwlo!==null||st.mwhi!==null){const lo=st.mwlo===null?lmin:Math.log(st.mwlo),hi=st.mwhi===null?lmax:Math.log(st.mwhi),x0=sx(L.x0+L.xw*(lo-lmin)/(lmax-lmin)),x1=sx(L.x0+L.xw*(hi-lmin)/(lmax-lmin));
  cx.fillStyle=TH.band;cx.fillRect(x0,0,x1-x0,Hh);cx.strokeStyle=TH.bandLine;cx.setLineDash([4,3]);cx.beginPath();cx.moveTo(x0,0);cx.lineTo(x0,Hh);cx.moveTo(x1,0);cx.lineTo(x1,Hh);cx.stroke();cx.setLineDash([])}
 cx.textAlign='left';cx.font='600 10.5px ui-sans-serif,system-ui,sans-serif';
 L.lanes.forEach(l=>{const y=(sy(l[1])+sy(l[2]))/2;if(y<8||y>Hh-14)return;cx.fillStyle=FAM[l[0]][1];cx.fillText(FAM[l[0]][0],8,y+3.5)});
 cx.restore()}
function vis(i){return hitset.has(i)&&(st.cmode==='mw'||!st.fams.size||st.fams.has(M[i][F.fam]))}
function colOf(i){if(st.cmode==='mw'){const v=M[i][F.mw];return v===null?TH.nowt:ramp(v)}return FAM[M[i][F.fam]][1]}
function draw(){EE=easeT(st.mt);cx.clearRect(0,0,W,Hh);drawLadder();const r=Math.min(7,2.2*Math.sqrt(V.k));
 cx.fillStyle=TH.dim;for(let i=0;i<M.length;i++){if(vis(i))continue;cx.beginPath();cx.arc(sx(X_(i)),sy(Y_(i)),r*.8,0,6.283);cx.fill()}
 for(let i=0;i<M.length;i++){if(!vis(i))continue;cx.fillStyle=colOf(i);cx.globalAlpha=.86;cx.beginPath();cx.arc(sx(X_(i)),sy(Y_(i)),r,0,6.283);cx.fill()}
 cx.globalAlpha=1;const mark=(i,c)=>{if(i<0)return;const x=sx(X_(i)),y=sy(Y_(i));cx.lineWidth=2;cx.strokeStyle=c;cx.beginPath();cx.arc(x,y,r+4,0,6.283);cx.stroke()};
 mark(st.sel,TH.ink);mark(hov,TH.blue)}
function nearest(px,py){EE=easeT(st.mt);let b=-1,bd=100;for(let i=0;i<M.length;i++){if(!vis(i))continue;const dx=sx(X_(i))-px,dy=sy(Y_(i))-py,d=dx*dx+dy*dy;if(d<bd){bd=d;b=i}}return b}
function renderMap(){const wv=st.view==='mw',w=st.cmode==='mw';$('wtctl').hidden=!wv;fit();hitset=new Set(hits);if(wv){wtHist();wtLabel()}draw();
 $('legend').innerHTML=w?'<span class="gl">lightest <i class="grad"></i> heaviest</span><span class="gl2">colour range '+fmtmw(Math.exp(c0))+' to '+fmtmw(Math.exp(c1))+' g/mol, log scale · grey = no molecular weight ('+MW_NONE+' molecules)</span>':FAM.map((f,k)=>'<span class="lg'+(st.fams.size&&!st.fams.has(k)?' off':'')+'" data-f="'+k+'"><i style="background:'+f[1]+'"></i>'+esc(f[0])+'</span>').join('');
 $('mapnote').innerHTML=wv?'Left to right is lightest to heaviest on a log scale; the rows are the families, a display aid. Slide toward Scent map to blend the dots back to the odour layout, where molecules the sources describe alike sit together. Weight is the molecular weight PubChem computed for the compound: one number per molecule, not a volatility measure, and it says nothing about perfumery note position. <b>Molecules without a PubChem record have no weight and wait in the far-right column.</b>':'Each dot is a molecule, placed by how its sources describe it (the pattern of odour tags; t-SNE). Molecules with the same pattern form a tight group; position inside a group means nothing. Drag to pan, scroll to zoom, click a dot to read its quotes. Colours are a display aid, not a classification. <b>Close on the map means described alike, not smelling alike.</b>';
 $('mapdetail').innerHTML=st.sel>=0?detail(st.sel):'<div class="note" style="padding-top:6px">Click a dot to read the quotes behind it.</div>';after($('mapdetail'))}
let drag=null;
cv.addEventListener('pointerdown',e=>{cv.setPointerCapture(e.pointerId);drag={x:e.clientX,y:e.clientY,tx:V.tx,ty:V.ty,moved:false};cv.classList.add('drag')});
cv.addEventListener('pointermove',e=>{const r=cv.getBoundingClientRect(),px=e.clientX-r.left,py=e.clientY-r.top;
 if(drag){const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>4)drag.moved=true;if(drag.moved){V.tx=drag.tx+dx;V.ty=drag.ty+dy;draw()}return}
 const n=nearest(px,py),tip=$('tip');if(n!==hov){hov=n;draw()}
 if(n>=0){tip.style.display='block';tip.style.left=Math.min(px+14,W-200)+'px';tip.style.top=(py+14)+'px';tip.textContent=M[n][F.label]+' · '+(st.view==='mw'?(M[n][F.mw]===null?'no weight':fmtmw(M[n][F.mw])+' g/mol')+' · ':'')+M[n][F.tags].map(t=>TAGS[t][0]).join(', ')}else tip.style.display='none'});
cv.addEventListener('pointerup',e=>{const was=drag;drag=null;cv.classList.remove('drag');if(was&&!was.moved){const r=cv.getBoundingClientRect(),n=nearest(e.clientX-r.left,e.clientY-r.top);st.sel=n;draw();$('mapdetail').innerHTML=n>=0?detail(n):'';after($('mapdetail'));if(n>=0)$('mapdetail').scrollIntoView({behavior:'smooth',block:'nearest'})}});
cv.addEventListener('pointerleave',()=>{$('tip').style.display='none';if(hov!==-1){hov=-1;draw()}});
function zoomAt(f,px,py){const k=Math.max(1,Math.min(40,V.k*f)),r=k/V.k;V.tx=px-(px-V.tx)*r+PAD*(r-1);V.ty=py-(py-V.ty)*r+PAD*(r-1);V.k=k;if(k===1){V.tx=0;V.ty=0}draw()}
cv.addEventListener('wheel',e=>{e.preventDefault();const r=cv.getBoundingClientRect();zoomAt(e.deltaY<0?1.25:.8,e.clientX-r.left,e.clientY-r.top)},{passive:false});
$('zi').onclick=()=>zoomAt(1.5,W/2,Hh/2);$('zo').onclick=()=>zoomAt(1/1.5,W/2,Hh/2);$('zr').onclick=()=>{V={k:1,tx:0,ty:0};draw()};
$('legend').addEventListener('click',e=>{const f=e.target.closest('.lg');if(!f)return;const k=+f.dataset.f;st.fams.has(k)?st.fams.delete(k):st.fams.add(k);renderMap()});
/* ---------------- weight map */
const mwv=M.map(m=>m[F.mw]).filter(v=>v!==null).sort((a,b)=>a-b),MW_NONE=M.length-mwv.length;
const lmin=Math.log(mwv[0]),lmax=Math.log(mwv[mwv.length-1]),qf=p=>Math.log(mwv[Math.floor(p*(mwv.length-1))]),c0=qf(.02),c1=qf(.98);
const t2mw=t=>Math.exp(lmin+t*(lmax-lmin)),fmtmw=v=>v>=100?v.toFixed(0):v.toFixed(1);
const RAMPS={light:[[34,193,214],[43,141,224],[90,82,213],[138,47,176],[63,13,85]],dark:[[34,193,214],[79,141,255],[154,107,255],[216,107,255],[255,122,200]]};
function ramp(v){const t=Math.max(0,Math.min(1,(Math.log(v)-c0)/(c1-c0))),s=t*(RAMPS[TH.mode].length-1),i=Math.min(RAMPS[TH.mode].length-2,Math.floor(s)),f=s-i,R_=RAMPS[TH.mode],a=R_[i],b=R_[i+1];return 'rgb('+[0,1,2].map(k=>Math.round(a[k]+(b[k]-a[k])*f)).join(',')+')'}
let tw=null;function tweenTo(to){if(tw)cancelAnimationFrame(tw);const from=st.mt,t0=performance.now(),dur=800;const step=now=>{const p=Math.min(1,(now-t0)/dur);st.mt=from+(to-from)*p;draw();if(p<1)tw=requestAnimationFrame(step);else tw=null};tw=requestAnimationFrame(step)}
function tweenStop(){if(tw){cancelAnimationFrame(tw);tw=null}}
$('mix').oninput=e=>{tweenStop();st.mix=+e.target.value/1000;st.mt=st.mix;draw()};
$('colseg').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;st.wcol=b.dataset.c;st.cmode=st.wcol;document.querySelectorAll('#colseg button').forEach(x=>x.classList.toggle('on',x===b));renderMap()});
function wtBand(){return [+$('wtlo').value,+$('wthi').value]}
function wtLabel(){const [lo,hi]=wtBand(),a=t2mw(lo/1000),b=t2mw(hi/1000);let n=0;for(const v of mwv)if(v>=a-1e-9&&v<=b+1e-9)n++;
 $('wtlab').textContent=fmtmw(a)+' – '+fmtmw(b)+' g/mol · '+fmt(n)+' of '+fmt(mwv.length)+' molecules with a weight'}
function wtHist(){const c=$('wth'),w=c.parentElement.clientWidth-36;if(w<50)return;const dpr=window.devicePixelRatio||1,h=56;c.style.width=w+'px';c.width=w*dpr;c.height=h*dpr;const g=c.getContext('2d');g.setTransform(dpr,0,0,dpr,0,0);g.clearRect(0,0,w,h);
 const nb=60,cnt=new Array(nb).fill(0);for(const v of mwv)cnt[Math.min(nb-1,Math.floor((Math.log(v)-lmin)/(lmax-lmin)*nb))]++;const mx=Math.max(...cnt),[lo,hi]=wtBand();
 for(let b=0;b<nb;b++){const t=(b+.5)/nb,on=t*1000>=lo-8&&t*1000<=hi+8,bh=Math.sqrt(cnt[b]/mx)*(h-4);g.globalAlpha=on?.95:.22;g.fillStyle=ramp(t2mw(t));g.fillRect(2+b*(w-4)/nb,h-bh,Math.max(1,(w-4)/nb-1),bh)}g.globalAlpha=1}
function wtSet(lo,hi){lo=Math.max(0,Math.min(1000,lo));hi=Math.max(lo,Math.min(1000,hi));$('wtlo').value=lo;$('wthi').value=hi;st.mwlo=lo<=0?null:t2mw(lo/1000);st.mwhi=hi>=1000?null:t2mw(hi/1000);update()}
let sw=null;function wtStop(){if(sw){clearInterval(sw);sw=null}$('wtplay').textContent='▶ Sweep light → heavy'}
$('wtlo').oninput=()=>{wtStop();const [lo,hi]=wtBand();wtSet(Math.min(lo,hi),hi)};$('wthi').oninput=()=>{wtStop();const [lo,hi]=wtBand();wtSet(lo,Math.max(lo,hi))};
$('wtclear').onclick=()=>{wtStop();wtSet(0,1000)};
$('wtplay').onclick=()=>{if(sw){wtStop();return}const w=130;let lo=0;$('wtplay').textContent='⏸ Stop';wtSet(0,w);sw=setInterval(()=>{lo+=7;if(lo+w>=1000){wtStop();wtSet(0,1000);return}wtSet(lo,lo+w)},70)};  /* a finished sweep returns to all weights */
/* ---------------- term map */
function renderTermMap(){const T=D.tm;let h='';T.e.forEach(e=>{const a=T.p[e[0]],b=T.p[e[1]];h+='<line x1="'+a[0]+'" y1="'+a[1]+'" x2="'+b[0]+'" y2="'+b[1]+'" stroke="#8795a6" stroke-opacity=".34" stroke-width="'+(.5+9*e[2]).toFixed(2)+'" stroke-linecap="round"/>'});
 TAGS.forEach((t,i)=>{const p=T.p[i];h+='<g class="tn" data-t="'+i+'"><circle cx="'+p[0]+'" cy="'+p[1]+'" r="'+T.r[i]+'" fill="'+FAM[T.f[i]][1]+'" fill-opacity=".9" class="'+(t[2]?'ring':'')+'" stroke="none" stroke-width="'+(t[2]?2.2:0)+'"/><title>'+esc(t[0])+' · '+t[1]+' molecules'+(t[2]?' · at the bar':'')+' · click to list them</title></g>'});
 TAGS.forEach((t,i)=>{const p=T.p[i],l=T.lab[i];h+='<text class="'+(l[3]?'b':'')+'" x="'+(p[0]+l[0]).toFixed(1)+'" y="'+(p[1]+l[1]).toFixed(1)+'" text-anchor="'+l[2]+'" dominant-baseline="central">'+esc(t[0])+'</text>'});
 const sv=$('tsvg');sv.setAttribute('viewBox','0 0 '+T.w+' '+T.h);sv.innerHTML=h;
 $('tlegend').innerHTML=FAM.map(f=>'<span class="lg" style="cursor:default"><i style="background:'+f[1]+'"></i>'+esc(f[0])+'</span>').join('')}
function renderTerms(){renderTermMap();renderBars()}
/* ---------------- terms */
function renderBars(){const mx=Math.max(...TAGS.map(t=>t[1]));$('terms').innerHTML=TAGS.map((t,i)=>'<div class="tm" data-t="'+i+'"><span class="n">'+esc(t[0])+'</span><span class="b"><i class="'+(t[2]?'':'low')+'" style="width:'+Math.max(1,t[1]/mx*100)+'%"></i><u style="left:'+30/mx*100+'%"></u></span><span class="c">'+t[1]+'</span></div>').join('')}
/* ---------------- wiring */
function setView(v){st.view=v;st.cmode=v==='mw'?st.wcol:'fam';tweenStop();st.mt=0;
 /* the weight band and its sweep are a lens of the Weight map: leaving the map clears them, so no band filters another view unseen */
 if(v!=='mw'){wtStop();if(st.mwlo!==null||st.mwhi!==null){st.mwlo=st.mwhi=null;$('wtlo').value=0;$('wthi').value=1000;st.shown=80;refilter()}}document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('on',b.dataset.v===v));
 const sec={table:'v-table',map:'v-map',mw:'v-map',terms:'v-terms'};['v-table','v-map','v-terms'].forEach(x=>$(x).hidden=x!==sec[v]);$('bar').style.display=v==='terms'?'none':'flex';$('active').style.display=v==='terms'?'none':'flex';
 if(v==='map'||v==='mw')renderMap();if(v==='mw')tweenTo(st.mix);if(v==='table')renderTable();if(v==='terms')renderTerms()}
function update(){st.shown=80;refilter();if(st.view==='table')renderTable();if(st.view==='map'||st.view==='mw')renderMap()}
function toggleTag(t){const k=st.tags.indexOf(t);k>=0?st.tags.splice(k,1):st.tags.push(t);update()}
$('thr').addEventListener('click',e=>{const t=e.target.closest('th.s');if(!t)return;const k=t.dataset.s;if(st.sk===k)st.sd=-st.sd;else{st.sk=k;st.sd=(k==='label'||k==='formula')?1:-1}update()});
$('tabs').addEventListener('click',e=>{const b=e.target.closest('button');if(b)setView(b.dataset.v)});
$('q').addEventListener('input',e=>{st.q=e.target.value.trim().toLowerCase();update()});
$('ftag').innerHTML='<option value="">any odour term</option>'+TAGS.map((t,i)=>'<option value="'+i+'">'+esc(t[0])+' ('+t[1]+')</option>').join('');
$('ftag').onchange=e=>{st.tags=e.target.value===''?[]:[+e.target.value];update()};
$('fstr').onchange=e=>{st.str=e.target.value;update()};$('fsrc').onchange=e=>{st.src=e.target.value;update()};
$('reset').onclick=()=>{wtStop();st.q='';st.tags=[];st.str='';st.src='';st.fams.clear();st.open=-1;st.sel=-1;st.mwlo=st.mwhi=null;$('wtlo').value=0;$('wthi').value=1000;$('q').value='';$('fstr').value='';$('fsrc').value='';V={k:1,tx:0,ty:0};update()};
document.addEventListener('click',e=>{const t=e.target.closest('.tag');if(t&&t.dataset.mw){e.stopPropagation();wtStop();wtSet(0,1000);return}
 const tn=e.target.closest('.tn');if(tn){st.tags=[+tn.dataset.t];update();setView('table');window.scrollTo({top:0});return}
 if(t&&t.dataset.t!==undefined){e.stopPropagation();toggleTag(+t.dataset.t);return}
 const r=e.target.closest('tr.row');if(r){const i=+r.dataset.i;st.open=st.open===i?-1:i;renderTable()}
 const tm=e.target.closest('.tm');if(tm){st.tags=[+tm.dataset.t];update();setView('table');window.scrollTo({top:0})}});
$('more').onclick=()=>{st.shown+=80;renderTable()};
window.addEventListener('resize',()=>{if(st.view==='map'||st.view==='mw')renderMap()});
$('themebtn').onclick=()=>{const t=TH.dark?'light':'dark';root.dataset.theme=t;try{localStorage.setItem('os-theme',t)}catch(e){}refreshTheme()};
if(window.matchMedia)matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{if(!root.dataset.theme)refreshTheme()});
function setTb(){document.documentElement.style.setProperty('--tb',document.querySelector('.topbar').offsetHeight+'px')}setTb();window.addEventListener('resize',setTb);
$('stats').innerHTML=[['Molecules',fmt(C.molecules),'in release/v1.0'],['With a structure',fmt(C.with_structure),fmt(C.name_only)+' counted by name only'],['Terms at the bar',C.at_bar+' <small>of '+C.terms+'</small>','≥ 30 molecules'],['Quotes',fmt(C.evidence),'verbatim, each with its source']].map(s=>'<div class="stat"><div class="k">'+s[0]+'</div><div class="v">'+s[1]+'</div><div class="k" style="text-transform:none;letter-spacing:0;margin-top:2px">'+s[2]+'</div></div>').join('');
$('lic').innerHTML='<b>What you are looking at.</b> The v1.0 <i>candidate</i>: not frozen yet. '+fmt(C.hand)+' structures are hand-derived readings of OCR-damaged or obsolete names and '+fmt(C.name_only)+' molecules have no definite structure; both are marked. Database rows were extracted by rule from the odour clause; patent rows were each approved by a person.';
$('foot').textContent='Built '+D.built+' from release/v1.0 (git '+D.head+'). Every figure on this page is read from the release files.';
refreshTheme();refilter();renderTable();
})();
</script></body></html>
"""

if __name__ == "__main__":
    raise SystemExit(main())
