#!/usr/bin/env python3
"""
status.py — the ONE answer to "where are we". Read this before quoting any number.

    python3 pipeline/status.py

WHY THIS FILE EXISTS
--------------------
On 2026-09-05, asked the same question three times in ten minutes, I gave three
different answers:

    20 of 67 tags, 561 molecules     (from a summary, unverified)
    11 of 67 tags, 569 molecules     (ad-hoc script, odor_terms.tsv columns REVERSED)
    15 of 67 tags, 544 molecules     (columns fixed, pubchem-rows.jsonl not read)

Only the first was right, and only by luck — I could not reproduce it, so I could not
defend it. Each wrong version looked exactly as authoritative as the right one: same
confident formatting, same "AT THE BAR" header, no hint that anything was off.

This is the failure attest.py's docstring already warned about, one layer up:

    Two counters that disagree about what they are counting cannot be compared,
    so this one does not get its own definition.

attest.py obeys that for terms. Nothing obeyed it for the headline number, so the
headline number was recomputed by hand every time it was asked for. Now it is not.

THE TWO MISTAKES, SO THEY ARE NOT REPEATED
------------------------------------------
1. odor_terms.tsv is `surface_form <TAB> tag`, surface FIRST. Reversed, `flowery` and
   `floral` stay separate, `muguet` never folds into `lily`, and the count collapses.
   This module does not parse it — it imports rows_pubchem.load_tags(), which also
   asserts one-tag-per-form.

2. The corpus has TWO row sources and the bar counts their UNION:

       corpus/rows/review.jsonl        patent rows, `decision == approve` only
       corpus/rows/pubchem-rows.jsonl  HSDB rows, no review gate

   Patents alone give 15 tags, PubChem alone 6, together 20 — the union is not close
   to either part, so reading one file is not an approximation of the answer, it is a
   different answer.

NAME MATCHING BETWEEN THE SOURCES
---------------------------------
PubChem stores `BENZENE`, the patents store `benzene`. Counted raw, one molecule
becomes two and every tag inflates. Names are casefolded and whitespace-collapsed
before the union.

This is a WEAK join and is labelled as such: it matches on name text, not structure.
`linalool` and `(+)-linalool` stay separate here. Fixing that needs InChIKeys for both
sides, which the patent rows do not have — so treat the combined figure as an upper
bound on distinct molecules, and the per-tag counts as slightly conservative (a tag
splitting one molecule across two spellings counts it twice only if both spellings
were approved, which review should have caught).
"""
from __future__ import annotations
import collections, importlib.util, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REVIEW = ROOT / "corpus" / "rows" / "review.jsonl"
PUBCHEM = ROOT / "corpus" / "rows" / "pubchem-rows.jsonl"
BAR = 30
N_TAGS = 67


def load_tags() -> dict[str, str]:
    """rows_pubchem.py's loader, imported not copied — see the docstring."""
    spec = importlib.util.spec_from_file_location("rows_pubchem", ROOT / "pipeline" / "rows_pubchem.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.load_tags()


def norm(s: str) -> str:
    return " ".join(s.lower().split())


def jsonl(p: pathlib.Path):
    if not p.exists():
        sys.exit(f"missing {p} — status is not computable without both row sources")
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith('{"_comment"'):
            yield json.loads(line)


def main() -> int:
    surf = load_tags()
    patents = collections.defaultdict(set)
    pubchem = collections.defaultdict(set)
    decisions = collections.Counter()
    unmapped = collections.Counter()
    violations = []

    for r in jsonl(REVIEW):
        decisions[r.get("decision") or "undecided"] += 1
        if r.get("decision") != "approve":
            continue
        sent = r.get("sentence") or ""
        mols = [m.strip() for m in (r.get("molecules") or []) if m.strip()]
        for m in mols:
            if m not in sent:
                violations.append((r.get("source_id"), m))
        for d in (r.get("tags") or r.get("descriptors") or []):
            d = d.strip()
            if d and d not in sent:
                violations.append((r.get("source_id"), d))
            tag = surf.get(d.lower())
            if tag is None:
                if d:
                    unmapped[d.lower()] += 1
                continue
            patents[tag].update(norm(m) for m in mols)

    excluded = collections.Counter()
    for r in jsonl(PUBCHEM):
        # triage_pubchem.py marks rather than deletes, so rows retired on provenance or
        # attribution grounds are still IN the file. Counting them would inflate every
        # figure this module exists to make trustworthy.
        if r.get("excluded"):
            excluded[r.get("excluded_category") or "?"] += 1
            continue
        t = (r.get("tag") or "").strip()
        m = norm(r.get("molecule_name") or "")
        if t and m:
            pubchem[t].add(m)

    combined = collections.defaultdict(set)
    for d in (patents, pubchem):
        for t, s in d.items():
            combined[t].update(s)

    def bar(d):
        return sorted(t for t, s in d.items() if len(s) >= BAR)

    print(f"decisions   {dict(decisions)}")
    print(f"            {decisions['approve']} approvals of {sum(decisions.values())} rows")
    if excluded:
        print(f"excluded    {sum(excluded.values())} pubchem rows retired  {dict(excluded)}")
    print()
    for name, d in (("patents", patents), ("pubchem", pubchem), ("COMBINED", combined)):
        mols = {m for s in d.values() for m in s}
        print(f"{name:<10}{len(bar(d)):>3} of {N_TAGS} at the bar   {len(mols):>5} molecules")

    at = bar(combined)
    print(f"\nAT THE BAR ({len(at)}):\n  {', '.join(at)}")

    near = sorted(((len(s), t) for t, s in combined.items() if BAR - 10 <= len(s) < BAR), reverse=True)
    if near:
        print("\nwithin reach:")
        for n, t in near:
            print(f"  {t:<14}{n:>4}   needs {BAR - n}")

    left = N_TAGS - len(at)
    need = sum(BAR - len(combined.get(t, ())) for t in surf.values() if len(combined.get(t, ())) < BAR)
    print(f"\n{left} tags below the bar; {need} molecule-tag pairs to fill them all")

    if violations:
        print(f"\n!! {len(violations)} VERBATIM VIOLATIONS — a span is not a substring of its sentence")
        for sid, s in violations[:10]:
            print(f"     {sid:<16}{s!r}")
        return 1
    print("\nverbatim invariant: clean")

    if unmapped:
        print(f"\nunmapped descriptors: {len(unmapped)} distinct, {sum(unmapped.values())} uses")
        print("  (approved text with no odor_terms.tsv entry — candidates, not errors)")
        print("  " + ", ".join(w for w, _ in unmapped.most_common(12)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
