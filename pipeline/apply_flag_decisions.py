#!/usr/bin/env python3
"""
apply_flag_decisions.py — Ivan's 2026-10-03 decisions on the names structures.py flagged as "not a
definite structure", written into corpus/rows/review.jsonl.

    python3 pipeline/apply_flag_decisions.py            # REPORT ONLY: shows the 11 rows, runs status.py on a copy
    python3 pipeline/apply_flag_decisions.py --write    # timestamped backup first, then touches ONLY those lines

WHY A SCRIPT, AND WHY REPORT-ONLY BY DEFAULT
--------------------------------------------
review.html holds every row in memory and an export discards what was written underneath it
(DEVLOG, 2026-09-10). So `--write` must only be run when no review.html session is open. The
decisions came from Ivan in chat, with the rule in front of him (REVIEW-RULES: a definite structure,
or no row; the mixture rule), so this applies HIS decisions — it proposes nothing.

WHAT IT DOES
------------
 reject (10) the row's decision becomes `reject`, and molecules / molecule / descriptors are emptied
             exactly as review.html does on a reject (all 1,158 existing rejects have both empty).
             The old values are kept in `review_note`, so nothing is lost.
 merge  (1)  #18 US4010207A: "2-benzyl-2-ethyl-hex-3-enal; and 2-prenyl non-2-enal" is two compounds
             sharing ONE description -> "add both, approve once": molecules becomes the two names,
             each a verbatim substring of the sentence. The row stays approved.

Rows are found by (source_id, molecules == [span]), and the match must be exactly one approved row.
Every other line of the file stays BYTE-IDENTICAL — only the matched lines are replaced.
"""
from __future__ import annotations
import importlib.util, io, json, pathlib, shutil, sys, time, contextlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
REVIEW = ROOT / "corpus" / "rows" / "review.jsonl"
WHEN = "Ivan 2026-10-03"

REJECT = [  # (source_id, span, why)
    ("US20150038386A1", "(E/Z)-2,4,7-trimethylocta-2,6-dien-1-ol", "E/Z label = a mixture of isomers (mixture rule)"),
    ("US10450532B2", "(E/Z)-9-hydroxy-5,9-dimethyldec-4-enal", "E/Z label = a mixture of isomers (mixture rule)"),
    ("US20100189672A1", "6,6-dimethoxy-2,5,5-trimethyl-2-hexene or 4,7-dimethyl-6-octen-3-one",
     "two prior-art compounds named as a comparison, 'A or B'"),
    ("US12441954B2", "oxacyclohexadec-(12 or 13)-en-2-one", "'various isomers' of a 12-/13-ene: a mixture"),
    ("US20110142783A1", "[(4E,4Z)-5-methoxy-3-methyl-4-pentenyl]-benzene", "contradictory stereo (4E,4Z): a mixture / not definite"),
    ("US5994291A", "(E)-(R)-2-alkyl-4-(2,2,3-trimethylcyclopent-3-en-1-yl)-2-buten-1-ol", "family ('alkyl'), not a molecule"),
    ("US20110195038A1", "2-[perhydro-trialkyl-2-naphthalenylidene]-1-propanol", "family ('trialkyl'), not a molecule"),
    ("US4069828A", "C 1 -C 6 alkyl-2-methyl-3,4-pentadienoate", "family ('C1-C6 alkyl'), not a molecule"),
    ("US20020055453A1", "8/9-methylenecyclohexadecanone", "8- or 9-: a mixture of positional isomers"),
    ("US2867668A", "ethyl ether of allo-ocimenol",
     "identified 2026-10-03: the patent itself defines allo-ocimenol as 'the mixture of the two isomers I and II', "
     "so the ethyl ether is the ether of a mixture (mixture rule; 'X of Y' picks out no single substance)"),
]
MERGE = [  # (source_id, old span, new molecules, why)
    ("US4010207A", "2-benzyl-2-ethyl-hex-3-enal; and 2-prenyl non-2-enal",
     ["2-benzyl-2-ethyl-hex-3-enal", "2-prenyl non-2-enal"],
     "two compounds sharing ONE description: add both, approve once (REVIEW-RULES, Splits)"),
]


def plan():
    raw = REVIEW.read_text(encoding="utf-8").split("\n")
    parsed = []
    for i, line in enumerate(raw):
        parsed.append(json.loads(line) if line.strip() and not line.startswith('{"_comment"') else None)
    edits = {}      # line index -> new line
    notes = []

    def find(src, span):
        hits = [i for i, r in enumerate(parsed)
                if r and r["source_id"] == src and r.get("decision") == "approve" and r.get("molecules") == [span]]
        if len(hits) != 1:
            sys.exit(f"expected exactly 1 approved row for {src} / {span!r}, found {len(hits)} — refusing")
        return hits[0]

    for src, span, why in REJECT:
        i = find(src, span)
        r = dict(parsed[i])
        note = (f"{WHEN}: reject — {why}. Was approve with molecules={r['molecules']}, descriptors={r['descriptors']} "
                f"(flagged by structures.py as not a definite structure).")
        r.update(decision="reject", molecules=[], molecule="", descriptors=[], review_note=note)
        edits[i] = r
        notes.append(("reject", src, span, r))
    for src, span, new, why in MERGE:
        i = find(src, span)
        r = dict(parsed[i])
        sent = r["sentence"]
        for m in new:
            if m not in sent:
                sys.exit(f"{m!r} is not a verbatim substring of the sentence — refusing")
        r.update(molecules=new, molecule=new[0],
                 review_note=f"{WHEN}: {why}. Was one span {span!r}.")
        edits[i] = r
        notes.append(("merge", src, span, r))
    # serialise in the file's own style: compact, ensure_ascii off — and PROVE the style by round-tripping
    # an untouched row before trusting it for the touched ones.
    probe = next(i for i, r in enumerate(parsed) if r and i not in edits)
    ser = lambda r: json.dumps(r, ensure_ascii=False, separators=(",", ":"))
    if ser(parsed[probe]) != raw[probe]:
        sys.exit("cannot reproduce the file's JSON style on an untouched row — refusing to write")
    for i, r in edits.items():
        raw[i] = ser(r)
    return raw, notes


def status_on(text: str, label: str) -> None:
    """Run status.py's own main() against a copy — numbers come from status.py, never from memory."""
    import tempfile
    spec = importlib.util.spec_from_file_location("status_copy", HERE / "status.py")
    st = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(st)
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        f.write(text)
    st.REVIEW = pathlib.Path(f.name)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        st.main()
    out = buf.getvalue().splitlines()
    keep = [l for l in out if l.startswith(("decisions", "patents", "COMBINED", "AT THE BAR", "verbatim invariant"))]
    print(f"--- status.py {label}")
    for l in keep:
        print("   ", l)
    at = [l for l in out if l.startswith("  ") and "within reach" not in l][:0]
    return out


def main() -> int:
    raw, notes = plan()
    new_text = "\n".join(raw)
    print(f"{len(notes)} rows to change (10 reject + 1 merge); every other line byte-identical\n")
    for kind, src, span, r in notes:
        print(f"  {kind:<7}{src:<18}{span[:70]!r}\n          -> decision={r['decision']} molecules={r['molecules']}")
    before = status_on(REVIEW.read_text(encoding="utf-8"), "BEFORE")
    after = status_on(new_text, "AFTER (on a copy)")
    b = [l for l in before if l.startswith("AT THE BAR")]
    a = [l for l in after if l.startswith("AT THE BAR")]
    gone = set(before) ^ set(after)
    print("\n--- lines that differ between the two status.py runs")
    for l in sorted(gone):
        print("   ", l)
    if "--write" not in sys.argv:
        print("\nREPORT ONLY — nothing written. Re-run with --write once no review.html session is open.")
        return 0
    bak = REVIEW.with_name(REVIEW.name + time.strftime(".bak-%Y%m%d-%H%M%S"))
    shutil.copy2(REVIEW, bak)
    REVIEW.write_text(new_text, encoding="utf-8")
    print(f"\nWROTE {REVIEW.relative_to(ROOT)}   backup: {bak.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
