#!/usr/bin/env python3
"""
OpenScent — boilerplate detector. Phase 0 quality gate.

    python3 boilerplate.py [min_docs]      # ON THE HARVEST BOX (needs corpus/raw/)

WHY THIS EXISTS
---------------
vocab.py counts documents, not occurrences, because a term repeated 124 times inside
one patent is one observation. That fix was necessary and INCOMPLETE: it does nothing
against the same sentence copied across many patents, which is exactly what patent
attorneys do.

Found 2026-08-05. `woodland`(124 docs), `spruce`(124) and `forest`(127) all traced to
one stock paragraph:

    "other pleasant scents include herbal and woodland scents derived from
     pine, spruce and other forest smells"

96% of `woodland`'s occurrences are that sentence. Three terms that looked as
well-supported as `rose` were one sentence, copy-pasted. Neither `woodland` nor
`spruce` appears in a single candidate sentence — that was the tell, and it was
noticed by eye rather than by measurement. Hence this file.

WHAT IT MEASURES
----------------
For each term, the share of its DOCUMENTS that carry one identical context window.

    boilerplate ratio = documents sharing the most common context
                        -----------------------------------------
                        documents containing the term at all

Documents, not occurrences, on both sides — a term repeating inside one patent must
not look like agreement between patents.

    ratio >= 0.50   one source sentence dominates      -> DROP, not a descriptor
    ratio >= 0.25   substantially boilerplate          -> read the context, decide
    ratio <  0.25   independently attested             -> keep

EFFECTIVE SUPPORT is the honest count: distinct contexts, not distinct documents.
A term needs independent attestations before it can be a tag, and 124 photocopies of
one paragraph is one attestation.

LIMIT, stated so nobody trusts this further than it goes: contexts are matched
EXACTLY after whitespace collapsing. A boilerplate paragraph that drifts between
patents — a word changed, a synonym swapped — splits into several contexts and this
under-reports it. Ratios here are a FLOOR on how much boilerplate a term carries.
"""
from __future__ import annotations
import collections, os, pathlib, re, sys

_here = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(os.environ.get("OPENSCENT_ROOT",
           _here.parent if _here.name == "pipeline" else _here / "openscent"))
RAW = ROOT / "corpus" / "raw"
ONT = ROOT / "ontology"

WIN = 55          # chars of context each side
CLASSIFIED = "harvested-terms-classified.tsv"


def load_terms(min_docs: int) -> dict[str, tuple[int, str]]:
    """term -> (docs_from_vocab, class). Prefers the classified export."""
    src = ONT / CLASSIFIED
    if not src.exists():
        src = ONT / "harvested-terms-corpus.tsv"
    out = {}
    for line in src.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        p = line.split("\t")
        if len(p) < 3:
            continue
        try:
            docs = int(p[2])
        except ValueError:
            continue
        if docs >= min_docs:
            out[p[0].strip().lower()] = (docs, p[3].strip() if len(p) > 3 else "")
    print(f"terms      {len(out)} at >={min_docs} docs   (from {src.name})")
    return out


def scan(terms):
    """context -> set of documents, per term. One pass over the corpus."""
    if not RAW.exists() or not any(RAW.glob("*.txt")):
        sys.exit(f"no corpus at {RAW} — run this on the box holding corpus/raw/")
    rx = re.compile(r"\b(" + "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)) + r")\b", re.I)
    ctx = collections.defaultdict(lambda: collections.defaultdict(set))
    files = sorted(RAW.glob("*.txt"))
    for i, f in enumerate(files, 1):
        if i % 500 == 0:
            print(f"  ...{i}/{len(files)}", flush=True)
        text = f.read_text(errors="ignore")
        for m in rx.finditer(text):
            t = m.group(1).lower()
            w = text[max(0, m.start() - WIN): m.end() + WIN]
            ctx[t][" ".join(w.split()).lower()].add(f.name)
    return ctx, len(files)


def main() -> int:
    min_docs = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    terms = load_terms(min_docs)
    ctx, nfiles = scan(terms)
    print(f"corpus     {nfiles} patents\n")

    rows = []
    for t, (vdocs, cls) in terms.items():
        buckets = ctx.get(t)
        if not buckets:
            rows.append((t, cls, vdocs, 0, 0, 0.0, ""))
            continue
        docs = len(set().union(*buckets.values()))
        top_ctx, top_docs = max(((c, len(d)) for c, d in buckets.items()), key=lambda x: x[1])
        rows.append((t, cls, vdocs, docs, len(buckets), top_docs / docs, top_ctx))

    rows.sort(key=lambda r: -r[5])
    dest = ONT / "boilerplate-report.tsv"
    with dest.open("w", encoding="utf-8") as fh:
        fh.write("# Share of a term's DOCUMENTS carrying one identical context window.\n")
        fh.write("# >=0.50 drop · >=0.25 inspect · <0.25 independently attested.\n")
        fh.write("# contexts = distinct context windows = EFFECTIVE independent support.\n")
        fh.write("# term\tclass\tvocab_docs\tdocs\tcontexts\tratio\ttop_context\n")
        for t, cls, vdocs, docs, nctx, ratio, top in rows:
            fh.write(f"{t}\t{cls}\t{vdocs}\t{docs}\t{nctx}\t{ratio:.3f}\t{top[:180]}\n")

    bad = [r for r in rows if r[5] >= 0.50]
    warn = [r for r in rows if 0.25 <= r[5] < 0.50]
    print(f"{'term':<18}{'cls':<5}{'docs':>6}{'ctxs':>7}{'ratio':>8}")
    print("-" * 44)
    for t, cls, vdocs, docs, nctx, ratio, top in (bad + warn)[:40]:
        print(f"{t:<18}{cls or '-':<5}{docs:>6}{nctx:>7}{ratio:>8.2f}")
    print(f"\nDROP     {len(bad):>3} terms at ratio >=0.50")
    print(f"INSPECT  {len(warn):>3} terms at 0.25-0.50")
    print(f"of which class D: drop {sum(1 for r in bad if r[1]=='D')}, "
          f"inspect {sum(1 for r in warn if r[1]=='D')}")
    print(f"-> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
