#!/usr/bin/env python3
"""
fix_entities.py — decode HTML entities left in the corpus text by the fetch.

    python3 fix_entities.py            # report
    python3 fix_entities.py --write

WHAT IS WRONG
-------------
harvest.py strips HTML tags but never decodes entities, so the stored sentences carry
`&#34;` for a double quote and `&#39;` for an apostrophe. Found on 2026-09-05 when a
molecule span read

    5-[1&#39;-ethoxyethoxy]-4-methyl-3-decene

which is chemically correct — the prime marks a position on the substituent — but will not
resolve, and reads as damage to a human. 379 of 4,620 sentences are affected.

WHY SENTENCE AND SPANS MUST CHANGE TOGETHER
-------------------------------------------
The corpus's one invariant is that every molecule and descriptor is a VERBATIM substring
of its sentence. Decoding a span without its sentence breaks that; decoding a sentence
without its spans breaks it the other way. So this rewrites both in one pass and asserts
the invariant afterwards — a partial decode would leave the file in a state that looks
fine and fails the next integrity check for reasons nobody would connect to this script.

It also rewrites `char_offset` nowhere, deliberately: offsets index the ORIGINAL raw text,
which is unchanged on the harvest box. Decoding here does not move them.

WHAT IT DOES NOT FIX
--------------------
An apostrophe that OCR inserted into a word, e.g. `dime&#39;thyl` for `dimethyl`. Decoding
gives `dime'thyl`, still wrong. That is OCR damage, not encoding, and belongs to the
audit path. Such cases are listed rather than silently "fixed".
"""
from __future__ import annotations
import html, json, pathlib, re, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
REVIEW = ROOT / "corpus" / "rows" / "review.jsonl"
ENT = re.compile(r"&#\d+;|&[a-zA-Z]+;")
# an entity INSIDE a word is OCR noise, not encoding: dime&#39;thyl
INWORD = re.compile(r"[a-zA-Z]&#39;[a-zA-Z]")


def main() -> int:
    write = "--write" in sys.argv
    head, rows = None, []
    for l in REVIEW.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        if l.startswith('{"_comment"'):
            head = l; continue
        rows.append(json.loads(l))

    n_sent = n_mol = n_desc = 0
    suspect = []
    for r in rows:
        s = r.get("sentence") or ""
        if not ENT.search(s):
            continue
        if INWORD.search(s):
            for m in (r.get("molecules") or []):
                if INWORD.search(m):
                    suspect.append((r["source_id"], m))
        new = html.unescape(s)
        if new != s:
            r["sentence"] = new; n_sent += 1
        for field, counter in (("molecules", "mol"), ("descriptors", "desc")):
            vals = r.get(field) or []
            out = []
            for v in vals:
                d = html.unescape(v)
                if d != v:
                    if counter == "mol": n_mol += 1
                    else: n_desc += 1
                out.append(d)
            if vals:
                r[field] = out
        if r.get("molecule"):
            r["molecule"] = html.unescape(r["molecule"])

    print(f"sentences decoded   {n_sent}")
    print(f"molecule spans      {n_mol}")
    print(f"descriptor spans    {n_desc}")
    if suspect:
        print(f"\n! {len(suspect)} span(s) have an entity INSIDE a word — OCR noise, not")
        print("  encoding. Decoding leaves them wrong; they need the audit path:")
        for s, m in suspect:
            print(f"    {s:<16} {m}")

    # the invariant, checked after the rewrite
    bad = 0
    for r in rows:
        if r.get("decision") != "approve":
            continue
        for m in (r.get("molecules") or []):
            if m not in r["sentence"]:
                print(f"  NOT VERBATIM after decode: {r['source_id']} {m!r}"); bad += 1
        for d in (r.get("descriptors") or []):
            if d not in r["sentence"]:
                print(f"  DESC NOT VERBATIM: {r['source_id']} {d!r}"); bad += 1
    print(f"\nverbatim violations after decode: {bad}")
    if bad:
        print("REFUSING to write — the decode broke the invariant it was meant to preserve.")
        return 1
    if not write:
        print("\nDry run. Add --write to apply.")
        return 0

    bak = REVIEW.with_suffix(f".jsonl.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    bak.write_text(REVIEW.read_text(encoding="utf-8"), encoding="utf-8")
    with REVIEW.open("w", encoding="utf-8") as fh:
        if head:
            fh.write(head + "\n")
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"backup  -> {bak.name}\nwritten -> {REVIEW.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
