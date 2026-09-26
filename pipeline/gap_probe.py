#!/usr/bin/env python3
"""gap_probe.py — do our own patents describe the Hekserij gap compounds in sentences we never kept?

MEASURE BEFORE FETCHING. This fetches nothing and writes nothing into the corpus.

WHERE THE GAP LIST COMES FROM
-----------------------------
hekserij_link.py (2026-09-25): 107 Hekserij products (~103 distinct compounds) that are
single compounds with a PubChem CID, but that neither our PubChem rows nor any approved
patent/passage molecule name covers. A gap can only become a row through an ADMISSIBLE
source; the shop's text is all-rights-reserved. The obvious admissible source is the
5,346 US patents we already hold: they may describe these compounds in sentences the
extractor dropped (named() did not fire on a trade/common name, the claim spans two
sentences, etc.).

THREE STEPS, TWO MACHINES (the passage_probe.py split — the raw text lives on Hetzner)
-----------------------------------------------------------------------------------
  MAC      python3 pipeline/gap_probe.py --names
             -> corpus/hekserij/gap-names.json   (compound -> search names)
  HETZNER  scp pipeline/gap_probe.py corpus/hekserij/gap-names.json <hetzner>:/opt/openscent/...
           OPENSCENT_ROOT=/opt/openscent python3 pipeline/gap_probe.py --scan gap-names.json --dump gap-hits.jsonl
  MAC      scp <hetzner>:/opt/openscent/gap-hits.jsonl corpus/staging/
           python3 pipeline/gap_probe.py --analyse corpus/staging/gap-hits.jsonl

SEARCH NAMES, AND WHY THEY ARE FILTERED
---------------------------------------
For each compound: the Hekserij name without supplier/dilution, the INCI name, and the
first 15 PubChem synonyms (PubChem ranks them; deeper ones are where the δ-for-γ kind of
pollution lives — see hekserij_link.BAD_SYNONYM). Dropped: CAS-like strings, names under
6 letters, and generic words (PERFUME, PARFUM, FRAGRANCE…) — on 2026-09-25 an unfiltered
substring count gave "Ambrocenide" 818 hits because its INCI is PERFUME.
Matching is case-insensitive with non-alphanumeric boundaries, not \b: chemical names
start with digits and brackets.

WHAT COUNTS AS A HIT
--------------------
A sentence 25-600 chars that carries an odour word (harvest.ODOUR), a descriptive verb
(harvest.DESCR / DESCR_COLON), passes harvest.EXCLUDE, and contains a search name.
Each hit is labelled:
  comparison   the name follows a comparison cue within 60 chars ("reminiscent of",
               "similar to", "like that of", "than", "instead of", "replace", "compared")
               — a reference point, which REVIEW-RULES says is not a row
  extracted    harvest.decide() accepts it — it is (or was) in review.jsonl already
The analysis joins hits to review.jsonl on (source_id, sentence) to report decisions.
"""
from __future__ import annotations
import collections, csv, importlib.util, json, os, pathlib, re, sys

ROOT = pathlib.Path(os.environ.get("OPENSCENT_ROOT", pathlib.Path(__file__).resolve().parent.parent))
HEK = ROOT / "corpus" / "hekserij"
GENERIC = {"perfume", "parfum", "fragrance", "flavor", "flavour", "aroma chemical", "dipropylene glycol"}
COMPARE = re.compile(r"(reminiscent of|similar to|like that of|resembl\w*|than|instead of|"
                     r"replac\w*|compared|in place of|substitute for|such as)\W[^.;]{0,60}$", re.I)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "pipeline" / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def make_names():
    cache = json.loads((HEK / "pubchem-cache.json").read_text(encoding="utf-8"))
    link = _load("hekserij_link")
    rows = list(csv.DictReader(open(HEK / "hekserij-gaps.tsv", encoding="utf-8"), delimiter="\t"))
    out = {}
    for r in rows:
        if r["status"] != "gap" or r["cas"] in out:
            continue
        base = re.sub(r"\((IFF|Giv|Fir|Sym|DRT|nat|org)\)|\d+%\s*in\s*\w+|\*ADR\*", "", r["name"], flags=re.I).strip()
        bad = link.BAD_SYNONYM.get(r["cas"], set())
        cands = [base, r["inci"]] + cache["syn"].get(r["cid"], [])[:15]
        names = []
        for n in cands:
            n = (n or "").strip()
            if not n or n.lower() in bad or n.lower() in GENERIC:
                continue
            if re.fullmatch(r"[\d\-]+", n) or sum(ch.isalpha() for ch in n) < 6:
                continue
            if ":" in n or re.match(r"(DTX|FEMA|UNII|EINECS|NSC|CHEBI|SCHEMBL|AKOS|MFCD)", n, re.I):
                continue                                   # database identifiers, not names
            if n.lower() not in {x.lower() for x in names}:
                names.append(n)
        if names:
            out[r["cas"]] = {"product": r["name"], "cid": r["cid"], "names": names}
    p = HEK / "gap-names.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} gap compounds, {sum(len(v['names']) for v in out.values())} search names -> {p.relative_to(ROOT)}")


def scan(names_path, dump_path):
    H = _load("harvest")
    G = json.loads(pathlib.Path(names_path).read_text(encoding="utf-8"))
    alias = {}
    for cas, v in G.items():
        for n in v["names"]:
            alias.setdefault(n.lower(), cas)
    alts = sorted(alias, key=len, reverse=True)
    rx = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(map(re.escape, alts)) + r")(?![A-Za-z0-9])", re.I)
    docs = sorted(H.RAW.glob("*.txt"))
    if not docs:
        sys.exit(f"no documents in {H.RAW} — run this on Hetzner")
    n_hits = 0
    with open(dump_path, "w", encoding="utf-8") as fh:
        for k, path in enumerate(docs, 1):
            if k % 500 == 0:
                print(f"  ...{k}/{len(docs)}  hits so far {n_hits}")
            text = H.norm(path.read_text(encoding="utf-8", errors="ignore"))
            for s in H.SENT.split(text):
                if not (25 < len(s) < 600) or not H.ODOUR.search(s):
                    continue
                if not (H.DESCR.search(s) or H.DESCR_COLON.search(s)):
                    continue
                if any(r.search(s) for r, _ in H.EXCLUDE):
                    continue
                found = {}
                for m in rx.finditer(s):
                    cas = alias[m.group(0).lower()]
                    cmp_ = bool(COMPARE.search(s[:m.start()]))
                    # a compound counts as NOT-comparison if any of its mentions is not one
                    found[cas] = found.get(cas, True) and cmp_
                    found.setdefault("_span_" + cas, m.group(0))
                for cas, cmp_ in list(found.items()):
                    if cas.startswith("_span_"):
                        continue
                    fh.write(json.dumps({"source_id": path.stem, "cas": cas, "span": found["_span_" + cas],
                                         "comparison": cmp_, "extracted": H.decide(s)[0], "sentence": s},
                                        ensure_ascii=False) + "\n")
                    n_hits += 1
    print(f"{len(docs)} documents, {n_hits} hits -> {dump_path}")


def analyse(dump_path):
    st = _load("status")
    surf = st.load_tags()
    tagrx = re.compile(r"\b(" + "|".join(sorted(map(re.escape, surf), key=len, reverse=True)) + r")\b", re.I)
    G = json.loads((HEK / "gap-names.json").read_text(encoding="utf-8"))
    rev = {}
    for r in st.jsonl(st.REVIEW):
        rev[(r["source_id"], re.sub(r"\s+", " ", r.get("sentence", "")).strip())] = r.get("decision") or "undecided"
    hits = [json.loads(l) for l in open(dump_path, encoding="utf-8")]
    per = collections.defaultdict(lambda: {"sent": 0, "docs": set(), "noncmp": 0, "noncmp_docs": set(),
                                            "in_review": collections.Counter(), "tags": collections.Counter(), "ex": None})
    for h in hits:
        p = per[h["cas"]]
        p["sent"] += 1; p["docs"].add(h["source_id"])
        key = (h["source_id"], re.sub(r"\s+", " ", h["sentence"]).strip())
        if key in rev:
            p["in_review"][rev[key]] += 1
        if not h["comparison"]:
            p["noncmp"] += 1; p["noncmp_docs"].add(h["source_id"])
            for m in tagrx.finditer(h["sentence"]):
                p["tags"][surf[m.group(0).lower()]] += 1
            if p["ex"] is None:
                p["ex"] = h["sentence"][:220]
    # near-bar: combined counts as status.py computes them
    out = []
    for cas, v in G.items():
        p = per.get(cas)
        out.append({"cas": cas, "product": v["product"], "sentences": p["sent"] if p else 0,
                    "documents": len(p["docs"]) if p else 0,
                    "non_comparison_sentences": p["noncmp"] if p else 0,
                    "non_comparison_documents": len(p["noncmp_docs"]) if p else 0,
                    "already_in_review": dict(p["in_review"]) if p else {},
                    "tags_in_non_comparison": ", ".join(f"{t} {n}" for t, n in p["tags"].most_common(8)) if p else "",
                    "example": p["ex"] if p and p["ex"] else ""})
    out.sort(key=lambda r: (-r["non_comparison_documents"], -r["sentences"]))
    path = HEK / "gap-probe.tsv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]), delimiter="\t"); w.writeheader()
        for r in out:
            w.writerow({**r, "already_in_review": json.dumps(r["already_in_review"])})
    hit = [r for r in out if r["sentences"]]
    nc = [r for r in out if r["non_comparison_sentences"]]
    print(f"{len(out)} gap compounds · {len(hit)} mentioned in an odour sentence · "
          f"{len(nc)} in at least one NON-comparison odour sentence")
    unrev = sum(r["non_comparison_sentences"] - sum(r["already_in_review"].values()) for r in nc)
    print(f"non-comparison sentences not in review.jsonl (upper bound on new candidates): {max(unrev, 0)}")
    print("\ntop 25 by documents with a non-comparison mention:")
    for r in out[:25]:
        print(f"  {r['product'][:34]:<35}{r['non_comparison_documents']:>4} docs  {r['non_comparison_sentences']:>4} sents"
              f"  review {r['already_in_review']}  | {r['tags_in_non_comparison'][:60]}")
    print(f"\nwritten -> {path.relative_to(ROOT)}\nA CEILING, not a yield: read examples before believing any count.")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--names" in a:
        make_names()
    elif "--scan" in a:
        scan(a[a.index("--scan") + 1], a[a.index("--dump") + 1] if "--dump" in a else "gap-hits.jsonl")
    elif "--analyse" in a:
        analyse(a[a.index("--analyse") + 1])
    else:
        print(__doc__)
