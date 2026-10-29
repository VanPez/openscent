#!/usr/bin/env python3
"""
attribution_check.py — flag APPROVED sentence rows whose descriptors may not belong to the row's molecule.
READ-ONLY: reads corpus/rows/review.jsonl (and exclusions via status.py), writes nothing in corpus/.

    python3 pipeline/attribution_check.py                 # counts per check
    python3 pipeline/attribution_check.py --tsv out.tsv   # every flagged row, one per line, for reading

WHY (2026-10-29)
----------------
Joe, reading source passages himself, saw descriptors of one molecule attached to another: a compound added at
5% to a cologne gave "freshness ... more minty", and that "minty" sat on a DIFFERENT compound's row because the
sentence splitter had glued two sentences together (US3852219A: "...than body and strength. l-Acetoxy-2-sec-butyl-..."
— the OCR'd "l" for "1" after the full stop hid the sentence boundary). This script looks for that, and for the
other ways a descriptor can land on the wrong thing, which a read of 63 flagged rows on 2026-10-29 also found.

THE CHECKS (each one is a reason to READ the row, not a verdict)
-----------------------------------------------------------------
  GLUED        the sentence has an internal full stop followed by more text (not an abbreviation), and a
               descriptor sits in a segment that does not contain the row's molecule.
  NEGATED      a descriptor follows "devoid of", "without", "lacking", "less", "not", "no" within a few words —
               REVIEW-RULES: negation inverts.
  COUNTERFACT  "instead of", "had been used", "would have", "replaced by" — REVIEW-RULES: counterfactual.
  COMPOSITION  a descriptor is the first word of "<word> formulation/composition/perfume/cologne/oil composition"
               — the word names the BLEND ("this floral essential oil composition"), not the molecule.
  PHYSICAL     "oily material", "oily liquid", "waxy solid" ... — a physical state, not a smell.
  CLASS        a descriptor directly followed by "hydrocarbon(s)", "compound(s)", "ester(s)" ... — a chemical class
               used as a comparison ("certain aromatic hydrocarbons"), not a smell quality.
  NEARER       (low priority) a descriptor is closer to ANOTHER known molecule named in the sentence than to the
               row's own. In a sample of 25 such rows on 2026-10-29, 23 were correct ("X is A, whereas Y is B").

Rows retired by exclusions.jsonl are skipped (they do not ship).
"""
from __future__ import annotations
import argparse, collections, csv, importlib.util, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("st", ROOT / "pipeline" / "status.py")
st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)

ABBREV = re.compile(r"(?:\be\.g|\bi\.e|\bNo|\bNos|\bPat|\bU\.S|\bal|\bca|\bapprox|\bFig|\bFigs|\bcf|\bvol|\bVol|\bp|\bpp|"
                    r"\bEx|\bEd|\bCo|\bInc|\bLtd|\bCorp|\bDr|\bMr|\bSt|\bresp|\bwt|\bmin|\bhr|\bmm|\bml|\bg|\bb\.p|\bm\.p|"
                    r"\bvs|\bJ|\bChem|\bSoc|\bAm|\bAcad|\bSci|\bOrg|\bAgric|\bFood|\bOd|\b[A-Z])\.$")
NEG = re.compile(r"\b(devoid of|without|lacking|lacks|lack of|less|not|no|free of|absence of)\b", re.I)
CFACT = re.compile(r"\binstead of\b|\bhad been used\b|\bwould have\b|\breplaced by\b|\bif [^,.]{0,60}\bwere used\b", re.I)
BLEND = re.compile(r"^[\s,-]*(essential oil |perfume |fragrance |)(formulation|composition|perfume|cologne|base|accord|blend)s?\b", re.I)
PHYS = re.compile(r"^[\s-]*(material|liquid|solid|oil\b|substance|residue|crystals)", re.I)
CLASS = re.compile(r"^[\s-]*(hydrocarbon|compound|ester|aldehyde|ketone|alcohol|amine|derivative)s?\b", re.I)


def segments(s: str) -> list[tuple[int, int]]:
    """Split a 'sentence' at internal full stops that are not abbreviations or decimals."""
    cuts = [0]
    for m in re.finditer(r"\.\s+(?=\S)", s):
        before = s[max(0, m.start() - 12):m.start() + 1]
        if ABBREV.search(before) or re.search(r"\d\.$", s[:m.start() + 1]) and re.match(r"\d", s[m.end():]):
            continue
        cuts.append(m.end())
    cuts.append(len(s))
    return [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)]


def find_all(needle: str, hay: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(re.escape(needle), hay, re.I)] if needle else []


def desc_hits(d: str, s: str) -> list[tuple[int, int]]:
    """Where descriptor d sits in s. Descriptors are stored as words; match the word or its first 5 letters
    as a word start ('mint' finds 'minty', 'fresh' finds 'freshness')."""
    h = find_all(d, s)
    if h:
        return h
    stem = d[:5] if len(d) > 5 else d
    return [(m.start(), m.end()) for m in re.finditer(r"\b" + re.escape(stem) + r"\w*", s, re.I)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tsv", help="write every flagged row here")
    a = ap.parse_args(argv)

    ex = st.excluded_keys()
    rows = list(st.jsonl(st.REVIEW))
    appr = [r for r in rows if r.get("decision") == "approve"
            and (r["source_id"], " ".join((r.get("sentence") or "").split())) not in ex]

    known = set()
    for r in rows:
        known.update(m for m in (r.get("molecules") or []) if len(m) >= 6)
    for l in open(ROOT / "corpus" / "structures" / "names.jsonl", encoding="utf-8"):
        known.update(x for x in json.loads(l).get("spellings", []) if len(x) >= 6)
    descwords = {d.lower() for r in rows for d in (r.get("descriptors") or [])}
    known = sorted((k for k in known if k.lower() not in descwords), key=len, reverse=True)
    known_rx = re.compile("|".join(re.escape(k) for k in known), re.I)

    flagged, count = [], collections.Counter()
    for r in appr:
        s = r.get("sentence") or ""
        mols = r.get("molecules") or []
        mpos = [p for m in mols for p in find_all(m, s)]
        dpos = {d: desc_hits(d, s) for d in (r.get("descriptors") or [])}
        why = []

        segs = segments(s)
        if len(segs) > 1 and mpos:
            seg_of = lambda x: next(i for i, (p, q) in enumerate(segs) if p <= x < q or (i == len(segs) - 1 and x == q))
            mseg = {seg_of(p) for p, _ in mpos}
            off = [d for d, hs in dpos.items() if hs and all(seg_of(p) not in mseg for p, _ in hs)]
            if off:
                why.append("GLUED:" + ",".join(off))
        for d, hs in dpos.items():
            for p, q in hs:
                pre = s[max(0, p - 30):p]
                if NEG.search(pre) and not re.search(r"[,;]", pre[NEG.search(pre).end():]):
                    why.append("NEGATED:" + d); break
        if CFACT.search(s):
            why.append("COUNTERFACT")
        for d, hs in dpos.items():
            for p, q in hs:
                tail = s[q:q + 40]
                if BLEND.search(tail):
                    why.append("COMPOSITION:" + d); break
                if PHYS.search(tail) and d.lower() in ("oily", "waxy", "fatty", "powdery", "resinous"):
                    why.append("PHYSICAL:" + d); break
                if CLASS.search(tail):
                    why.append("CLASS:" + d); break
        others = [m for m in known_rx.finditer(s)
                  if not any(m.start() < y and m.end() > x for x, y in mpos)
                  and not any(m.group(0).lower() in x.lower() for x in mols)]
        if others and mpos:
            near = []
            for d, hs in dpos.items():
                for p, _ in hs:
                    do = min(abs(p - (x + y) / 2) for x, y in mpos)
                    dt = min(abs(p - (o.start() + o.end()) / 2) for o in others)
                    if dt < do:
                        near.append(d); break
            if near:
                why.append("NEARER:" + ",".join(near))
        if why:
            for w in why:
                count[w.split(":")[0]] += 1
            flagged.append((r, why))

    print(f"{len(appr)} approved sentence rows read (retired rows skipped)")
    for k in ("GLUED", "NEGATED", "COUNTERFACT", "COMPOSITION", "PHYSICAL", "CLASS", "NEARER"):
        print(f"  {count[k]:5}  {k}")
    hi = [f for f in flagged if any(not w.startswith("NEARER") for w in f[1])]
    print(f"{len(flagged)} rows flagged; {len(hi)} by a check other than NEARER")
    if a.tsv:
        with open(a.tsv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["checks", "source_id", "queue_order", "molecules", "descriptors", "sentence"])
            for r, why in sorted(flagged, key=lambda f: (all(x.startswith("NEARER") for x in f[1]), f[0]["source_id"])):
                w.writerow([" ".join(why), r["source_id"], r.get("queue_order"), " | ".join(r.get("molecules") or []),
                            ", ".join(r.get("descriptors") or []), " ".join((r.get("sentence") or "").split())])
        print(f"written -> {a.tsv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
