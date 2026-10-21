#!/usr/bin/env python3
"""
apply_mixture_decisions.py — Ivan's 2026-10-21 decisions on mixtures left in the v1.0 candidate.

    python3 pipeline/apply_mixture_decisions.py            # REPORT ONLY: shows each row it would touch
    python3 pipeline/apply_mixture_decisions.py --write    # timestamped backups first, then touches ONLY those lines

The mixture rule (REVIEW-RULES): if the odour is attributed to a mixture, there is no row. The 10-03 flagger in
structures.py caught names written "E/Z" or "A or B" (apply_flag_decisions.py); three patent mixtures written another
way, "(E,Z)-7,8-", "4(3)-", "6,7,8-", were still approved, and four government-data records are mixtures too. Each patent
below states the mixture in its own text (read on Hetzner, 2026-10-21). Effects were measured on a scratch copy first.

  reject (patent rows, review.jsonl)   decision -> reject; molecules / molecule / descriptors emptied, old values kept in
                                       review_note (the 10-03 convention)
  split  (review.jsonl)                one span that fused two names becomes the two names (each verbatim in the sentence)
  retire (pubchem-rows.jsonl)          excluded = true, excluded_category = "mixture" (triage_pubchem.py's convention)
  retire (pubchem-physdesc-rows.jsonl) needs_review = true, review_decision = "reject" (the 09-24 Dowtherm A convention)

Rows are found by their content, never by line number; each must match exactly the expected count or nothing is written.
Every file is written in its own JSON style, proven first by round-tripping an untouched row.
"""
from __future__ import annotations
import json, pathlib, shutil, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROWS = ROOT / "corpus" / "rows"
WHEN = "Ivan 2026-10-21"

REJECT = [  # (source_id, span, expected rows, why)
    ("US20050137120A1", "(E,Z)-7,8-cyclohexadecenone", 2,
     "a mixture: the patent's table names it 'Mixture of (E,Z)-7- and (E,Z)-8-Cyclohexadecen-1-one' (mixture rule)"),
    ("US20140349901A1", "4(3)-(4-hydroxy-4-methylpentyl)-3-cyclohexene-1-carbonitrile", 3,
     "a mixture: the patent says the name 'denotes a mixture of both isomers' (4- and 3-) (mixture rule)"),
    ("US20140349901A1", "4(3)-(4-Hydroxy-4-methylpentyl)-3-cyclohexene-1-carbonitrile", 1,
     "a mixture: the patent says the name 'denotes a mixture of both isomers' (4- and 3-) (mixture rule)"),
    ("US20130165532A1", "6,7,8-Decene-1ol", 1,
     "a mixture: Example I is '6,7,8-Decene-1-ol (Mixture of 6-Decene-1-ol, 7-Decene-1-ol, and 8-Decene-1-ol)' (mixture rule)"),
]
SPLIT = [  # (source_id, fused span, replacement names, why)
    ("US6720295B2", "4-cyclopentyl-2-methyl-2-butanol, 3-cyclopentyl-1,1-dimethylpropyl acetate",
     ["4-cyclopentyl-2-methyl-2-butanol", "3-cyclopentyl-1,1-dimethylpropyl acetate"],
     "one span fused two of the three compounds the sentence describes; split into the two names (not a mixture)"),
]
PUBCHEM_RETIRE = [  # (cid, expected rows, reason)
    (56846457, 1, "mixture record: xylidine, six isomers in one PubChem record"),
    (24670, 1, "mixture record: Dowtherm A, biphenyl + diphenyl ether (its NIOSH Physical Description row was rejected 09-24)"),
    (73422990, 1, "mixture record: dichloropropane-dichloropropene mixture"),
]
PHYSDESC_RETIRE = [  # (cid, expected rows, note)
    (56846457, 3, "mixture record name (xylidines, six isomers) — rejected, Ivan 2026-10-21."),
    (34692, 1, "mixture record name (nitroanilines; the record lumps several compounds) — rejected, Ivan 2026-10-21."),
]


def load(path):
    raw = path.read_text(encoding="utf-8").splitlines()
    parsed = [json.loads(l) if l.strip() and not l.startswith('{"_comment"') else None for l in raw]
    return raw, parsed


def style(raw, parsed, touched):
    probe = next(i for i, r in enumerate(parsed) if r and i not in touched)
    for kw in ({"separators": (",", ":")}, {}):
        if json.dumps(parsed[probe], ensure_ascii=False, **kw) == raw[probe]:
            return lambda r, kw=kw: json.dumps(r, ensure_ascii=False, **kw)
    sys.exit(f"cannot reproduce the JSON style of an untouched row (line {probe + 1}) — refusing to write")


def plan():
    out = {}
    raw, parsed = load(ROWS / "review.jsonl")
    edits = {}
    for src, span, n, why in REJECT:
        hits = [i for i, r in enumerate(parsed)
                if r and r["source_id"] == src and r.get("decision") == "approve" and r.get("molecules") == [span]]
        if len(hits) != n:
            sys.exit(f"expected {n} approved row(s) for {src} / {span!r}, found {len(hits)} — refusing")
        for i in hits:
            r = dict(parsed[i])
            r.update(decision="reject", molecules=[], molecule="", descriptors=[],
                     review_note=(f"{WHEN}: reject — {why}. Was approve with molecules={parsed[i]['molecules']}, "
                                  f"descriptors={parsed[i]['descriptors']}."))
            edits[i] = r
    for src, span, new, why in SPLIT:
        hits = [i for i, r in enumerate(parsed)
                if r and r["source_id"] == src and r.get("decision") == "approve" and span in (r.get("molecules") or [])]
        if len(hits) != 1:
            sys.exit(f"expected 1 approved row for {src} / {span!r}, found {len(hits)} — refusing")
        i = hits[0]; r = dict(parsed[i])
        mols = [m for x in r["molecules"] for m in (new if x == span else [x])]
        for m in mols:
            if m not in r["sentence"]:
                sys.exit(f"{m!r} is not a verbatim substring of the sentence — refusing")
        r.update(molecules=mols, molecule=mols[0], review_note=f"{WHEN}: {why}. Was molecules={parsed[i]['molecules']}.")
        edits[i] = r
    out["review.jsonl"] = (raw, parsed, edits)

    raw, parsed = load(ROWS / "pubchem-rows.jsonl")
    edits = {}
    for cid, n, why in PUBCHEM_RETIRE:
        hits = [i for i, r in enumerate(parsed) if r and r.get("molecule_cid") == cid and not r.get("excluded")]
        if len(hits) != n:
            sys.exit(f"expected {n} live pubchem row(s) for CID {cid}, found {len(hits)} — refusing")
        for i in hits:
            r = dict(parsed[i]); r.update(excluded=True, excluded_category="mixture", excluded_reason=why,
                                          excluded_on="2026-10-21")
            edits[i] = r
    out["pubchem-rows.jsonl"] = (raw, parsed, edits)

    raw, parsed = load(ROWS / "pubchem-physdesc-rows.jsonl")
    edits = {}
    for cid, n, note in PHYSDESC_RETIRE:
        hits = [i for i, r in enumerate(parsed)
                if r and r.get("molecule_cid") == cid and r.get("review_decision") != "reject"]
        if len(hits) != n:
            sys.exit(f"expected {n} live physdesc row(s) for CID {cid}, found {len(hits)} — refusing")
        for i in hits:
            r = dict(parsed[i]); r.update(needs_review=True, review_decision="reject",
                                          review_reason="mixture record name", review_note=note)
            edits[i] = r
    out["pubchem-physdesc-rows.jsonl"] = (raw, parsed, edits)
    return out


def main():
    write = "--write" in sys.argv
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for name, (raw, parsed, edits) in plan().items():
        ser = style(raw, parsed, edits)
        print(f"== {name}: {len(edits)} line(s)")
        for i in sorted(edits):
            r = edits[i]
            print(f"   line {i + 1}: " + (f"decision={r.get('decision')} molecules={r.get('molecules')}" if name == "review.jsonl"
                  else f"CID {r['molecule_cid']} {r.get('molecule_name')!r} tag={r.get('tag')} "
                       f"excluded={r.get('excluded')} review_decision={r.get('review_decision')}"))
        if write:
            p = ROWS / name
            shutil.copy2(p, p.with_name(f"{name}.bak-{stamp}"))
            for i, r in edits.items():
                raw[i] = ser(r)
            p.write_text("\n".join(raw) + "\n", encoding="utf-8")
    print("WRITTEN (backups *.bak-" + stamp + ")" if write else "REPORT ONLY — nothing written (--write to apply)")


if __name__ == "__main__":
    main()
