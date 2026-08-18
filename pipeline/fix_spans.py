#!/usr/bin/env python3
"""
fix_spans.py — repair molecule spans that were mis-selected during review.

    python3 fix_spans.py                 # propose only, changes nothing
    python3 fix_spans.py --write         # apply the proposals it is confident about

WHY THIS IS SAFE TO DO AFTER THE FACT
-------------------------------------
Every row carries its full sentence, so a span can be re-derived from the source rather
than from memory. That is the point of storing the quote: the review captures WHERE the
evidence is, and the exact boundaries can be corrected later without re-reading anything.

WHAT GOES WRONG DURING REVIEW
-----------------------------
The highlighter splits long chemical names across several spans, because locants and
brackets break its token pattern. Clicking one highlight then yields a fragment:

    too little   E/Z)-9-hydroxy-5,9-dimethyldec-4-enal    <- lost the leading "("
    too much     (XI) (=7-methoxy-3,7-dimethyl-3-decanol) <- kept the formula label
    nonsense     3-(                                      <- a mis-click

The first two matter because the string is fed to OPSIN, and a name with unbalanced
brackets or a "(XI) (=" prefix will not resolve. Verified 2026-08-18: 8 of 195 molecule
strings, 4%.

METHOD, AND WHY "BALANCE THE BRACKETS" IS NOT THE GOAL
-----------------------------------------------------
The first version of this script simply grew the span until the brackets matched. It
produced, from a real row:

    4-(2,2,C-3,T-6-tetramethyl-R-1-cyclohexyl)-3-buten-2-one, trademark and origin: Firmenich SA)

Balanced, verbatim, and not a molecule. The unmatched ")" belonged to the patent's citation
parenthesis, so closing it dragged in the sentence. Bracket balance is a SYMPTOM of a bad
span, not the thing being repaired; the thing being repaired is the name's boundary.

So the operations are tried worst-case-first, cheapest damage first:

  1. add up to two adjacent BRACKET characters on the left    — keeps the whole name
  2. trim unmatched brackets and whatever sits outside them   — drops citation punctuation
  3. give up

Step 2 is what "((2-methoxy-2-methylheptane)" and "alpha (1-(...)-4-penten-1-one" need:
the leading "(" is the patent opening a parenthetical, not part of the compound.

Every candidate is then checked to be a VERBATIM substring of the stored sentence, and to
retain enough of a name to be one — extract-never-generate applies to a repair exactly as
it applies to the original selection.

A fragment like "3-(" carries no information about which name was meant, so it is reported
and left alone. PROPOSING IS THE DEFAULT. A script that silently rewrote molecule
identities would be a worse bug than the one it fixes.
"""
from __future__ import annotations
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "corpus" / "rows" / "review.jsonl"

# "(XI) (=", "(1a)", "3b)" and friends, when they lead the span
LABEL = re.compile(r'^\s*\(?\s*(?:[IVXLC]{1,6}|\d{1,3}[a-z]?)\s*\)\s*\(?\s*=?\s*')
MAXEXPAND = 60


def balanced(s):
    return s.count('(') == s.count(')') and s.count('[') == s.count(']')


def unmatched(s):
    """Positions of brackets with no partner. (openers, closers)"""
    stack, closers = [], []
    pairs = {')': '(', ']': '['}
    for n, c in enumerate(s):
        if c in '([':
            stack.append(n)
        elif c in ')]':
            if stack and s[stack[-1]] == pairs[c]:
                stack.pop()
            else:
                closers.append(n)
    return stack, closers


def plausible(s):
    """Enough of a name left to be one. '3-' and '(' are not molecules."""
    return len(re.findall(r'[A-Za-z]', s)) >= 4


def repair(span, sentence):
    stripped = LABEL.sub('', span).strip()
    if stripped and stripped != span and balanced(stripped) and stripped in sentence:
        return stripped, "stripped formula label"
    if balanced(span):
        return None, None
    i = sentence.find(span)
    if i < 0:
        return None, "span not in sentence (!)"

    # 1. the name is intact, the selection just clipped a bracket off the front
    for grow in (1, 2):
        if i - grow < 0:
            break
        if not all(c in '([' for c in sentence[i - grow:i]):
            break
        cand = sentence[i - grow:i + len(span)]
        if balanced(cand):
            return cand, f"restored {grow} clipped opening bracket(s)"

    # 2. the selection swallowed the patent's own punctuation — cut it away
    opens, closes = unmatched(span)
    cand = span
    if closes:                      # everything from the first orphan ')' is not the name
        cut = span[closes[0]:]
        # ...unless real name is being discarded. "...cyclopropyl]methanol" trimmed to
        # "...cyclopropyl" is not a repair, it is a different compound. When the patent
        # itself omits a bracket (US10407378B2 does, in one sentence but not the next),
        # no verbatim span can be balanced, and truncating to force it is falsification.
        if len(re.findall(r'[A-Za-z]', cut)) >= 4:
            return None, "source text has an unbalanced bracket — span is right, patent is wrong"
        cand = cand[:closes[0]]
    o2, _ = unmatched(cand)
    if o2:                          # everything up to the last orphan '(' is not the name
        cand = cand[o2[-1] + 1:]
    cand = cand.strip(" ,;:-")
    if cand and balanced(cand) and plausible(cand) and cand in sentence:
        return cand, "trimmed the patent's own parenthesis"

    return None, "cannot repair without guessing"


def main() -> int:
    write = "--write" in sys.argv
    rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith('{"_comment"')]
    head = next((l for l in SRC.read_text(encoding="utf-8").splitlines()
                 if l.startswith('{"_comment"')), None)

    fixed = manual = 0
    for r in rows:
        if r.get("decision") != "approve":
            continue
        out = []
        mols = r.get("molecules") or []
        for m in mols:
            if balanced(m) and not LABEL.match(m):
                out.append(m)
                continue
            # A broken span contained inside a good span on the SAME row is a stray
            # second click, not a name to reconstruct. US20100130397A1 carried '3-('
            # alongside the full '1-methyl-3-(2-methylpropyl)cyclohexan-1-ol'. Dropping
            # it loses nothing; trying to expand it would invent a second molecule.
            if any(o != m and m.strip('-( ') and m.strip('-( ') in o for o in mols):
                print(f"DROP {r['source_id']}\n     {m!r} — stray click, already covered "
                      f"by a fuller span on this row\n")
                fixed += 1
                continue
            new, why = repair(m, r["sentence"])
            if new and new in r["sentence"]:
                print(f"FIX  {r['source_id']}\n     was: {m}\n     now: {new}\n     ({why})\n")
                out.append(new)
                fixed += 1
            else:
                print(f"MANUAL  {r['source_id']}\n        {m!r} — {why}\n"
                      f"        sentence: {r['sentence'][:150]}...\n")
                out.append(m)
                manual += 1
        r["molecules"] = out
        r["molecule"] = out[0] if out else ""

    print("=" * 60)
    print(f"repaired automatically : {fixed}")
    print(f"need a human           : {manual}")
    if not write:
        print("\nProposal only. Re-run with --write to apply.")
        return 0

    bak = SRC.with_suffix(f".jsonl.bak-{__import__('time').strftime('%Y%m%d-%H%M%S')}")
    bak.write_text(SRC.read_text(encoding="utf-8"), encoding="utf-8")
    with SRC.open("w", encoding="utf-8") as fh:
        if head:
            fh.write(head + "\n")
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nbackup -> {bak.name}\nwritten -> {SRC.name}")
    print("Re-verify with the integrity check before trusting it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
