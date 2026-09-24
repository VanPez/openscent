#!/usr/bin/env python3
"""pubchem_physdesc.py — rows from PubChem `Physical Description`, US Government sources only.

    python3 pipeline/pubchem_physdesc.py            # measure: counts only, writes nothing
    python3 pipeline/pubchem_physdesc.py --write    # write corpus/rows/pubchem-physdesc-rows.jsonl
    python3 pipeline/pubchem_physdesc.py --flagged  # print the rows held for Ivan's decision

OFFLINE. Reads the pages pubchem_probe.py cached on 2026-09-10
(corpus/raw-pubchem/probe-physical-description-p*.json). Fetches nothing.

WHICH SOURCES, AND WHY ONLY THESE (DEVLOG 2026-09-10 night, 2026-09-24 evening)
------------------------------------------------------------------------------
  CAMEO Chemicals (NOAA/EPA)   US Gov. Its terms reserve ONLY DuPont clothing data, CAS
                               numbers/synonyms/formulas, NFPA ratings and AEGLs — not the
                               physical description. Its text cites (USCG …) / (NTP …) /
                               (EPA …); a citation to anything else is FLAGGED.
  OSHA                         US Gov (DOL: public domain; "some content may be others'").
  NIOSH Pocket Guide           US Gov (CDC).
  REFUSED: JECFA (CC BY-NC-SA 3.0 IGO), Haz-Map (all rights reserved), ICSC (international),
           HMDB (no odour rows), EPA CDR (not odour prose), EU Food Improvement Agents.
The source is checked PER ANNOTATION on `SourceName`, never per heading.

THE ODOUR-CLAUSE GATE — the thing the probe did not have
--------------------------------------------------------
Physical Description is mostly colour and state: "Yellow-GREEN gas with a pungent odor".
A tag is emitted only from the ODOUR CLAUSE: for each `odor/odour/smell` token, the text
back to the nearest clause opener (with / has / having / ; / . / start) and forward to the
token itself. "green" in the colour phrase is outside it. Extract, never generate: every
span is asserted to be a substring of the quote at its offset.

HELD FOR REVIEW (propose-only; status.py does not count these until decided)
----------------------------------------------------------------------------
  negation in the clause       "no", "not", "without", "odorless", "devoid"
  `acid` span                  usually a compound name or a comparison ("acetic acid-like")
  mixture/solution/class name  SOLUTION, MIXTURE, N.O.S., "class of", "and its salts"…
  non-Gov citation in CAMEO    anything in brackets that is not USCG/NTP/EPA/NIOSH/OSHA
A held row carries `needs_review: true` and `review_reason`. Ivan decides; a decided row
gets `review_decision: approve|reject`. Nothing is deleted.

MOLECULE NAMES
--------------
status.py joins on NAME text. If a CID is already in pubchem-rows.jsonl its existing name is
reused, so the same compound is not counted twice under HSDB's and CAMEO's spellings. A new
CID takes the first source's name (CAMEO > OSHA > NIOSH) for every row.
"""
from __future__ import annotations
import collections, glob, json, os, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "corpus" / "rows" / "pubchem-physdesc-rows.jsonl"
SOURCES = {  # SourceName -> short label, in name-priority order
    "CAMEO Chemicals": "CAMEO",
    "Occupational Safety and Health Administration (OSHA)": "OSHA",
    "The National Institute for Occupational Safety and Health (NIOSH)": "NIOSH",
}
ODOR = re.compile(r"\b(odou?rs?|smells?)\b", re.I)
OPENER = re.compile(r"(\bwith\b|\bhas\b|\bhaving\b|;|\.\s|^)", re.I)
NEG = re.compile(r"\b(no|not|without|odou?rless|devoid)\b", re.I)
MIXNAME = re.compile(r"solution|mixture|n\.o\.s|\bclass\b|and its salts|compounds?\b|preparations?|"
                     r"formulation|\d+\s*%|\bor\b", re.I)   # RECORD NAME only; not commas — locants carry them
CITE = re.compile(r"\(([^()]*\b(19|20)\d\d)\)")
COLOURAFTER = re.compile(r"[\s-]*(colou?r|colou?red|tint|tinted|hue|crystals|liquid|solid|powder|lust(er|re)|sheen)\b", re.I)
MIXTEXT = re.compile(r"solution|mixture|\d+\s*%|isomers|slurry|dispersion|emulsion", re.I)   # first sentence of the quote
GOVCITE = re.compile(r"\b(USCG|NTP|EPA|NIOSH|OSHA|NOAA|DOT|CDC|NLM|HSDB)\b")


def load_tags():
    spec = __import__("importlib.util").util.spec_from_file_location("st", ROOT / "pipeline" / "status.py")
    st = __import__("importlib.util").util.module_from_spec(spec); spec.loader.exec_module(st)
    return st.load_tags()


def annotations():
    for f in sorted(glob.glob(str(ROOT / "corpus" / "raw-pubchem" / "probe-physical-description-p*.json"))):
        for a in json.load(open(f, encoding="utf-8"))["Annotations"]["Annotation"]:
            if a.get("SourceName") in SOURCES:
                yield a


def clauses(text):
    """(start, end) of each odour clause: last opener before an odour token, up to the token."""
    for m in ODOR.finditer(text):
        head = text[:m.start()]
        opens = [o.end() for o in OPENER.finditer(head)]
        yield (opens[-1] if opens else 0), m.end()


def build():
    tags = load_tags()
    rx = re.compile(r"\b(" + "|".join(map(re.escape, sorted(tags, key=len, reverse=True))) + r")\b", re.I)
    old_names = {}
    for l in open(ROOT / "corpus" / "rows" / "pubchem-rows.jsonl", encoding="utf-8"):
        if l.strip():
            r = json.loads(l); old_names.setdefault(r["molecule_cid"], r["molecule_name"])
    anns = sorted(annotations(), key=lambda a: list(SOURCES).index(a["SourceName"]))
    new_names, rows, skipped = {}, [], collections.Counter()
    for a in anns:
        cids = (a.get("LinkedRecords") or {}).get("CID") or []
        if len(cids) != 1:
            skipped["no or several CIDs"] += 1; continue
        cid = cids[0]
        text = " ".join(s.get("String", "") for d in a.get("Data", [])
                        for s in d.get("Value", {}).get("StringWithMarkup", []))
        seen = {}
        for c0, c1 in clauses(text):
            clause = text[c0:c1]
            for m in rx.finditer(clause):
                if COLOURAFTER.match(clause, m.end()):     # "an amber color and an odor" — a colour, not a smell
                    continue
                tag = tags[m.group(1).lower()]
                if tag not in seen:
                    seen[tag] = (c0 + m.start(), m.group(1), clause)
        if not seen:
            skipped["no tag in an odour clause"] += 1; continue
        name = old_names.get(cid) or new_names.setdefault(cid, a.get("Name"))
        cites = [c.group(1) for c in CITE.finditer(text)]
        for tag, (off, span, clause) in seen.items():
            assert text[off:off + len(span)] == span, (cid, span)       # EXTRACT, NEVER GENERATE
            why = []
            if NEG.search(clause): why.append("negation in odour clause")
            if tag == "acid": why.append("`acid` span — name or comparison?")
            if MIXNAME.search(a.get("Name") or "") or MIXTEXT.search(text.split(". ")[0]):
                why.append("mixture/solution/class record name")
            if a["SourceName"] == "CAMEO Chemicals" and any(not GOVCITE.search(c) for c in cites):
                why.append("non-Government citation: " + "; ".join(c for c in cites if not GOVCITE.search(c)))
            rows.append({
                "molecule_cid": cid, "molecule_name": name, "tag": tag, "span": span,
                "span_offset": off, "quote": text, "odour_clause": clause,
                "source": a["SourceName"], "source_label": SOURCES[a["SourceName"]],
                "source_record_name": a.get("Name"), "source_url": a.get("URL"),
                "license_url": a.get("LicenseURL"), "citations": cites,
                "cid_new_to_pubchem_rows": cid not in old_names,
                "needs_review": bool(why), "review_reason": "; ".join(why) or None,
                "extractor": "pubchem_physdesc/v1",
            })
    return rows, skipped, set(old_names)


def main(argv):
    rows, skipped, old = build()
    ok = [r for r in rows if not r["needs_review"]]
    held = [r for r in rows if r["needs_review"]]
    print(f"rows {len(rows)}   clean {len(ok)}   held for review {len(held)}")
    print(f"skipped {dict(skipped)}")
    cids = {r['molecule_cid'] for r in ok}
    print(f"clean CIDs {len(cids)}, new to pubchem-rows {len(cids - old)}")
    print("by source (clean):", dict(collections.Counter(r['source_label'] for r in ok)))
    print("tags (clean):", collections.Counter(r['tag'] for r in ok).most_common())
    print("held reasons:", collections.Counter(x for r in held for x in r['review_reason'].split('; ') if not x.startswith('non-Gov')).most_common(),
          "+ non-Gov citation", sum('non-Gov' in r['review_reason'] for r in held))
    if "--flagged" in argv:
        for r in held:
            print(f"\n[{r['source_label']}] {r['molecule_name']} -> {r['tag']} ({r['span']!r})  {r['review_reason']}\n   {r['quote'][:300]}")
    if "--write" in argv:
        # Carry Ivan's decisions forward — a re-run must never erase a review.
        key = lambda r: (r["molecule_cid"], r["tag"], r["source_url"])
        prev = {}
        if OUT.exists():
            for l in open(OUT, encoding="utf-8"):
                if l.strip():
                    r = json.loads(l)
                    if r.get("review_decision"):
                        prev[key(r)] = (r["review_decision"], r.get("review_note"))
        for r in rows:
            if key(r) in prev:
                r["review_decision"], r["review_note"] = prev[key(r)]
        tmp = OUT.with_suffix(".jsonl.tmp")
        tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        os.replace(tmp, OUT)
        print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
