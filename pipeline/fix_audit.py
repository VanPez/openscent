#!/usr/bin/env python3
"""
fix_audit.py — apply the 2026-09-04 audit corrections. Proposes; never decides alone.

    python3 fix_audit.py                  # report only
    python3 fix_audit.py --trim           # apply the SPAN trims (safe: no decision changes)
    python3 fix_audit.py --flip           # apply the decision reversals (asks first)

TWO KINDS OF CORRECTION, AND THEY ARE NOT EQUALLY SAFE
------------------------------------------------------
**Trims** clean a molecule span that carries the patent's own label or an alternative name:
`8-drimanol (1a)` -> `8-drimanol`, `3,7-dimethyloctan-1-ol (tetrahydrogeraniol)` -> the
systematic half. The decision stands, the row survives, only the string improves. Every
result is re-checked as a verbatim substring of the stored sentence before it is written,
so a trim can only ever narrow to text that is really there.

**Flips** reverse a decision a human made. Fifteen rows, found by a blind comparison in
which Claude and Ivan could not see each other's answers and agreed only 67% of the time
(see DEVLOG 2026-09-04). Claude being on the other side of a disagreement is NOT authority
to overwrite a human judgement — 33% of the time in that test, one of us was wrong, and it
was not always Ivan. So --flip prints every sentence in full and requires typing the count
back. If a flip looks wrong, do not run it; fix that row in the UI instead.

WHY THESE FIFTEEN
-----------------
  composition/tobacco/food (5)  the odour belongs to a soup, a cigarette or a strawberry
                                aroma, not to the compound
  OCR damage (5)                Z or I standing in for a digit, `[2.2.21`, `cyclohexanI`
  names two compounds (2)       "the 7 and 8-acetyl..." is two substances at once
  unspecified substituent (3)   alkyl / alkoxy — a family, not a molecule

Backs up before writing, always.
"""
from __future__ import annotations
import json, pathlib, re, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
REVIEW = ROOT / "corpus" / "rows" / "review.jsonl"

FLIP_WHY = {
    "US3863013A": "odour imparted to the SOUP, not the compound",
    "US3875307A": "OCR (`cyclohexanI-one`) / odour belongs to the tobacco",
    "US3903900A": "odour belongs to the TOBACCO, not the compound",
    "US3907718A": "OCR (`Z-methyl`) and the note is imparted to a strawberry aroma",
    "US2969397A": "OCR: `Z-methyl` should be `2-methyl`",
    "US3510510A": "OCR: `Z-hydroxy` should be `2-hydroxy`",
    "US3668255A": "OCR: `IO-trimethyl` should be `10-trimethyl`",
    "US3914322A": "OCR `[2.2.21-0ct` / `7 and 8-acetyl` names two compounds",
    "US3929676A": "`7 and 8-acetyl` names two compounds at once",
    "US10077414B2": "`7-alkoxy` — unspecified substituent",
    "US20110118170A1": "`4-alkyl` — unspecified substituent",
}
COMP = re.compile(r"the tobacco to have|enhances the natural tobacco|to the soup\b"
                  r"|to the strawberry aroma", re.I)
TWO = re.compile(r"\b7 and 8-\w+", re.I)
HARD = re.compile(r"(?<![A-Za-z])[ZS]-(?:methyl|hydroxy|butyl|sec)|\bIO-\b|\[2\.2\.21"
                  r"|0ct-|cyclohexanI|\balkyl\b|\balkoxy\b", re.I)

# span cleaners, tried in order; each result must stay verbatim in the sentence
LABEL = re.compile(r"\s*\(\s*(?:[IVXivx]{1,4}|\d{1,2}[a-z]?|[a-z])\s*\)\s*$")   # (V) (1a) (r)
ALTNAME = re.compile(r"\s*\((?:[A-Za-z][\w\-,'’ ]{4,})\)\s*$")                   # (tetrahydrogeraniol)
MARKUSH = re.compile(r"\s*\([^()]*(?:R\s*=|Δ)[^()]*\)\s*$")                      # (R=R 1 =H, Δ 3,5 )
LEADNAME = re.compile(r"^[A-Za-z][\w\-]*,\s+")                                   # "Methionol, 3-(...)"
# ...but a STEREODESCRIPTOR before a comma is part of the name, not a common name.
# `trans, E-1-crotonoyl-2,2,6-trimethylcyclohexane` -> stripping "trans," would silently
# discard which diastereomer was smelled, which is the difference between two compounds
# that can smell nothing alike. Caught in review before it was applied.
STEREO = re.compile(r"^(?:cis|trans|rel|meso|syn|anti|endo|exo|[EZRS]|alpha|beta|gamma|"
                    r"delta|ortho|meta|para|sec|tert|iso|neo|n|d|l|dl)\b", re.I)


def bal(s):
    return s.count("(") == s.count(")") and s.count("[") == s.count("]")


def clean(m, sentence):
    """Return (new, why) or (None, None). Never invents text."""
    for pat, why in ((LABEL, "dropped the patent's formula label"),
                     (MARKUSH, "dropped the Markush annotation"),
                     (ALTNAME, "dropped the parenthetical alternative name"),
                     (LEADNAME, "dropped the leading common name")):
        if pat is LEADNAME and STEREO.match(m):
            continue                       # that comma-word is stereochemistry, keep it
        c = pat.sub("", m).strip()
        if c and c != m and bal(c) and c in sentence and len(re.findall(r"[A-Za-z]", c)) >= 4:
            return c, why
    if m.startswith("(") and m.endswith(")") and bal(m[1:-1]):
        c = m[1:-1].strip()
        if c in sentence:
            return c, "removed the enclosing brackets"
    if not bal(m):
        c = m.rstrip(")").rstrip()
        if bal(c) and c in sentence and len(re.findall(r"[A-Za-z]", c)) >= 4:
            return c, "dropped a stray closing bracket"
    return None, None


def main() -> int:
    do_trim = "--trim" in sys.argv
    do_flip = "--flip" in sys.argv
    head, rows = None, []
    for l in REVIEW.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        if l.startswith('{"_comment"'):
            head = l; continue
        rows.append(json.loads(l))

    flips, trims = [], []
    for r in rows:
        if r.get("decision") != "approve":
            continue
        mols = r.get("molecules") or []
        s = r["sentence"]
        if COMP.search(s) or TWO.search(s) or any(HARD.search(m) for m in mols):
            flips.append(r); continue
        for m in mols:
            c, why = clean(m, s)
            if c:
                trims.append((r, m, c, why))

    print(f"=== {len(flips)} DECISION REVERSALS (approve -> reject) ===")
    for r in flips:
        print(f"\n  {r['source_id']}   {(r.get('molecules') or [''])[0][:60]}")
        print(f"    why: {FLIP_WHY.get(r['source_id'], 'audit')}")
        print(f"    {r['sentence'][:150]}")
    print(f"\n\n=== {len(trims)} SPAN TRIMS (decision unchanged) ===")
    for r, old, new, why in trims:
        print(f"  {r['source_id']:<17} {old[:52]}\n  {'':<17} -> {new[:52]}   ({why})")

    if not (do_trim or do_flip):
        print("\nReport only.")
        print("  --trim   apply the span trims (safe, no decision changes)")
        print("  --flip   reverse the 15 decisions (will ask for confirmation)")
        return 0

    if do_flip:
        print(f"\n{len(flips)} decisions will be REVERSED. These are human judgements, and")
        print("the blind test that found them agreed only 67% of the time — Claude is not")
        print("automatically the correct party. Read them above first.")
        ans = input(f"Type the number {len(flips)} to confirm, anything else to abort: ").strip()
        if ans != str(len(flips)):
            print("aborted, nothing written")
            return 1

    bak = REVIEW.with_suffix(f".jsonl.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    bak.write_text(REVIEW.read_text(encoding="utf-8"), encoding="utf-8")

    n_f = n_t = 0
    if do_flip:
        ids = {id(r) for r in flips}
        for r in rows:
            if id(r) in ids:
                r["decision"] = "reject"
                r["molecules"] = []
                r["molecule"] = ""
                r["descriptors"] = []
                r["audit_flip"] = FLIP_WHY.get(r["source_id"], "audit 2026-09-04")
                n_f += 1
    if do_trim:
        for r, old, new, why in trims:
            ms = r.get("molecules") or []
            if old in ms and new in r["sentence"]:
                ms[ms.index(old)] = new
                r["molecules"] = ms
                r["molecule"] = ms[0]
                n_t += 1

    with REVIEW.open("w", encoding="utf-8") as fh:
        if head:
            fh.write(head + "\n")
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nbackup  -> {bak.name}")
    print(f"flipped {n_f} · trimmed {n_t} -> {REVIEW.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
