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

THE HEADLINE IS NOW BY STRUCTURE (2026-10-03, Ivan's decision, "option A")
--------------------------------------------------------------------------
The paragraph above was right and was waiting for its fix. structures.py now gives the
patent-side names a structure (corpus/structures/names.jsonl), and the PubChem side has had
InChIKeys since smiles.json. So the headline counts DISTINCT STRUCTURES (full InChIKey,
stereo kept — enantiomers can smell different, REVIEW-RULES), and the old name-text count is
printed BESIDE it, not instead of it. A third column, connectivity only (first InChIKey
block), is the lower bound that merges enantiomers.

What changed when it was first run: 27 of 67 tags by name text became 26 by structure —
`apple` had 34 names but 26 distinct structures (six OCR spellings of one compound, plus
three duplicate pairs). That is the 09-05 lesson once more: a count is only as good as its
definition of "one molecule".

Rules that keep the structure count honest:
  * a name is MERGED with another only when structures.py trusts its structure
    (verbatim / pubchem / repaired+witness / rewritten / flat). PROVISIONAL, PUBCHEM-CHECK,
    REWRITE-CHECK and unresolved names stay as separate names — an unconfirmed structure must
    never be the reason two molecules become one.
  * a PubChem row is identified by its CID's InChIKey, not by its (shouting) name.
  * names.jsonl is GENERATED. If a patent-side name has no record in it (rows changed since
    structures.py last ran) it counts as its own name and a warning says how many.
  * no names.jsonl at all: the headline falls back to name text, loudly.

Only this file's headline changed. gaps.py, gap_probe.py, hekserij_link.py and hedione_pool.py
still count name text for their own purposes; they use this module's helpers, not its output.
"""
from __future__ import annotations
import collections, importlib.util, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REVIEW = ROOT / "corpus" / "rows" / "review.jsonl"
PUBCHEM = ROOT / "corpus" / "rows" / "pubchem-rows.jsonl"
PHYSDESC = ROOT / "corpus" / "rows" / "pubchem-physdesc-rows.jsonl"
PASSAGE = ROOT / "corpus" / "rows" / "passage-rows.jsonl"   # passage scope, adopted 2026-09-24
EXCLUSIONS = ROOT / "corpus" / "rows" / "exclusions.jsonl"  # retired approved rows, 2026-09-26
TARGETED = ROOT / "corpus" / "rows" / "targeted-rows.jsonl"  # sentence rows found by gap search, 2026-09-26
STRUCT = ROOT / "corpus" / "structures" / "names.jsonl"          # structures.py --merge (2026-10-03)
STRUCT_PC = ROOT / "corpus" / "structures" / "pubchem-names.json"  # Hetzner stage 2: also holds CID InChIKeys
SMILES_CACHE = ROOT / "corpus" / "raw-pubchem" / "smiles.json"
# structures.py trust classes whose structure is safe to MERGE two names on.
MERGE_TRUST = {"verbatim", "pubchem", "repaired+witness", "rewritten", "flat"}
BAR = 30
N_TAGS = 67


def load_identity():
    """-> (patent: name_key -> InChIKey for trusted names, patent_known: every name_key in names.jsonl,
    pubchem: CID -> InChIKey) or None when names.jsonl is absent."""
    if not STRUCT.exists():
        return None
    pat, known = {}, set()
    for line in STRUCT.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        known.add(r["key"])
        if r.get("trust") in MERGE_TRUST and r.get("inchikey"):
            pat[r["key"]] = r["inchikey"]
    pc = {}
    if SMILES_CACHE.exists():
        for cid, v in json.loads(SMILES_CACHE.read_text(encoding="utf-8")).items():
            if v.get("inchikey"):
                pc[int(cid)] = v["inchikey"]
    if STRUCT_PC.exists():
        for cid, v in json.loads(STRUCT_PC.read_text(encoding="utf-8")).get("cids", {}).items():
            if v.get("inchikey"):
                pc.setdefault(int(cid), v["inchikey"])
    return pat, known, pc


def load_tags() -> dict[str, str]:
    """rows_pubchem.py's loader, imported not copied — see the docstring."""
    spec = importlib.util.spec_from_file_location("rows_pubchem", ROOT / "pipeline" / "rows_pubchem.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.load_tags()


def norm(s: str) -> str:
    return " ".join(s.lower().split())


def productive_predicate():
    """review.html's PRODUCTIVE(), READ OUT OF review.html — never reimplemented here.

    WHY THIS FUNCTION IS UGLY ON PURPOSE
    ------------------------------------
    On 2026-09-09 the RESUME block still said "0 PRODUCTIVE rows remain". It had said so
    since 2026-09-05, and it was wrong then (53) and very wrong by then (483). That one
    stale figure produced "the constraint is now material, not review time" and with it
    the C11D 3/50 walk, two sampling probes and two days of sourcing analysis.

    It went stale because NOTHING RECOMPUTED IT. status.py exists precisely so the
    headline cannot be remembered rather than measured — and it reported tags and
    molecules, not queue productivity, so the one number that decided what to work on
    next was outside its scope. Adding it here closes that.

    The predicate itself lives in review.html and stays there: it is what the reviewer
    actually sees, and a Python copy would drift from it exactly as this project's other
    duplicated definitions have (harvest.py on Hetzner; VOCAB below). So the regexes and
    the vocabulary array are PARSED OUT of the JavaScript. That is uglier than a copy and
    it is the point: if review.html changes, this follows, and if it cannot be parsed
    this refuses to guess.
    """
    html = (ROOT / "pipeline" / "review.html").read_text(encoding="utf-8")

    m = re.search(r"var\s+_NAME\s*=\s*/(.+?)/([a-z]*);", html)
    v = re.search(r"var\s+VOCAB\s*=\s*(\[.*?\]);", html, re.S)
    if not m or not v:
        return None, None, "could not parse _NAME or VOCAB out of review.html"

    flags = re.I if "i" in m.group(2) else 0
    name_rx = re.compile(m.group(1), flags)
    vocab = json.loads(v.group(1))
    tag_rx = re.compile(r"\b(" + "|".join(re.escape(w) for w in vocab) + r")\b", re.I)

    def productive(s: str) -> bool:
        return bool(s) and bool(name_rx.search(s)) and bool(tag_rx.search(s))

    return productive, vocab, None


def excluded_keys() -> set:
    """(source_id, whitespace-normalised sentence) of approved rows RETIRED without touching
    review.jsonl — Ivan's decisions stay his; the retirement is a separate, reasoned record.
    First use 2026-09-26: sentences relaying a copyrighted reference work's descriptor wording
    (Arctander, Fenaroli, Good Scents) — see pipeline/exclude_quotes.py."""
    if not EXCLUSIONS.exists():
        return set()
    return {(r["source_id"], " ".join(r["sentence"].split())) for r in jsonl(EXCLUSIONS)}


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
    name2cid = collections.defaultdict(set)     # PubChem-side name text -> CIDs, for the structure join
    decisions = collections.Counter()
    unmapped = collections.Counter()
    violations = []
    exkeys = excluded_keys()
    retired = 0

    for r in jsonl(REVIEW):
        decisions[r.get("decision") or "undecided"] += 1
        if r.get("decision") != "approve":
            continue
        sent = r.get("sentence") or ""
        if (r.get("source_id"), " ".join(sent.split())) in exkeys:
            retired += 1
            continue
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
            if r.get("molecule_cid"):
                name2cid[m].add(r["molecule_cid"])

    # Physical Description rows (pubchem_physdesc.py, 2026-09-24): CAMEO/OSHA/NIOSH only.
    # A row held for review counts ONLY once Ivan has approved it — propose-only.
    held = 0
    if PHYSDESC.exists():
        for r in jsonl(PHYSDESC):
            if r.get("needs_review") and r.get("review_decision") != "approve":
                held += r.get("review_decision") is None
                continue
            q, s = r.get("quote") or "", r.get("span") or ""
            if s not in q:
                violations.append((r.get("source_url"), s))
            t = (r.get("tag") or "").strip()
            m = norm(r.get("molecule_name") or "")
            if t and m:
                pubchem[t].add(m)
                if r.get("molecule_cid"):
                    name2cid[m].add(r["molecule_cid"])

    # Passage-scope rows (passage_rows.py, adopted 2026-09-24, narrow form). A RESOLVED
    # REFERENCE, not a sentence-scope claim: molecule verbatim in the antecedent, anaphor and
    # descriptors verbatim in the odour sentence. Counted ONLY when Ivan has approved it, and
    # left out entirely with --sentence-scope, which gives the pre-09-24 guarantee back.
    passage = collections.defaultdict(set)
    p_held = p_rows = 0
    sentence_scope = "--sentence-scope" in sys.argv
    if PASSAGE.exists() and not sentence_scope:
        for r in jsonl(PASSAGE):
            if r.get("review_decision") != "approve":
                p_held += r.get("review_decision") is None
                continue
            p_rows += 1
            ante, sent, mol = r.get("antecedent") or "", r.get("sentence") or "", (r.get("molecule") or "").strip()
            if mol not in ante:
                violations.append((r.get("source_id"), mol))
            if (r.get("anaphor") or "") not in sent:
                violations.append((r.get("source_id"), r.get("anaphor")))
            for d in (r.get("descriptors") or []):
                if d not in sent:
                    violations.append((r.get("source_id"), d))
                tag = surf.get(d.lower())
                if tag and mol:
                    passage[tag].add(norm(mol))

    # Targeted rows (targeted_rows.py, 2026-09-26): ordinary SENTENCE-scope claims, found by
    # searching for a missing compound rather than by the extractor — kept out of review.jsonl
    # so merge_review.py never reports them as orphans. Counted only once Ivan has approved.
    targeted = collections.defaultdict(set)
    t_held = t_rows = 0
    if TARGETED.exists():
        for r in jsonl(TARGETED):
            if r.get("review_decision") != "approve":
                t_held += r.get("review_decision") is None
                continue
            t_rows += 1
            sent, mol = r.get("sentence") or "", (r.get("molecule") or "").strip()
            for v in [mol] + list(r.get("descriptors") or []):
                if v not in sent:
                    violations.append((r.get("source_id"), v))
            for d in (r.get("descriptors") or []):
                tag = surf.get(d.lower())
                if tag and mol:
                    targeted[tag].add(norm(mol))

    combined = collections.defaultdict(set)         # NAME TEXT — the pre-2026-10-03 definition
    for d in (patents, pubchem, passage, targeted):
        for t, s in d.items():
            combined[t].update(s)

    # ---- the same sets, re-identified by STRUCTURE. Only the identity of a molecule changes.
    ident = load_identity()
    stale = 0
    if ident:
        pat_ik, known, pc_ik = ident
        stale = len({m for d in (patents, passage, targeted) for s_ in d.values() for m in s_} - known)

        def ik_of(name, source):
            if source == "pubchem":
                iks = {pc_ik[c] for c in name2cid.get(name, ()) if c in pc_ik}
                return min(iks) if iks else None
            return pat_ik.get(name)

        def remap(d, source, level):
            out = collections.defaultdict(set)
            for t, s_ in d.items():
                for m in s_:
                    k = ik_of(m, source)
                    out[t].add(("ik:" + (k if level == "full" else k[:14])) if k else "name:" + m)
            return out

        def views(level):
            v = {"patents": remap(patents, "patent", level), "pubchem": remap(pubchem, "pubchem", level),
                 "passage": remap(passage, "patent", level), "targeted": remap(targeted, "patent", level)}
            c = collections.defaultdict(set)
            for d in v.values():
                for t, s_ in d.items():
                    c[t].update(s_)
            v["COMBINED"] = c
            return v
        full, flat = views("full"), views("flat")
        name_view = {"patents": patents, "pubchem": pubchem, "passage": passage, "targeted": targeted,
                     "COMBINED": combined}
    else:
        full = flat = None

    def bar(d):
        return sorted(t for t, s in d.items() if len(s) >= BAR)

    headline = full["COMBINED"] if full else combined      # what every figure below the table uses
    name_combined = combined
    combined = headline

    print(f"decisions   {dict(decisions)}")
    print(f"            {decisions['approve']} approvals of {sum(decisions.values())} rows")
    if excluded:
        print(f"excluded    {sum(excluded.values())} pubchem rows retired  {dict(excluded)}")
    if retired:
        print(f"retired     {retired} approved patent rows (corpus/rows/exclusions.jsonl: quoted copyrighted reference works)")
    if held:
        print(f"held        {held} Physical Description rows awaiting Ivan's decision (not counted)")
    if sentence_scope:
        print("scope       SENTENCE ONLY — passage-rows.jsonl left out (--sentence-scope)")
    elif p_held:
        print(f"held        {p_held} passage rows awaiting Ivan's decision (not counted)")
    if t_held:
        print(f"held        {t_held} targeted rows awaiting Ivan's decision (not counted)")
    print()
    if not full:
        print(f"!! {STRUCT.relative_to(ROOT)} missing — the headline below is NAME TEXT, the old and weaker definition.")
        print("   Run pipeline/structures.py (needs Java + OPSIN) and --merge.\n")
        for name, d in (("patents", patents), ("pubchem", pubchem), ("passage", passage), ("targeted", targeted),
                        ("COMBINED", combined)):
            if name == "passage" and sentence_scope:
                continue
            mols = {m for s_ in d.values() for m in s_}
            print(f"{name:<10}{len(bar(d)):>3} of {N_TAGS} at the bar   {len(mols):>5} molecules")
    else:
        print(f"{'':<10}{'BY STRUCTURE (headline)':<30}{'connectivity only':<26}{'name text (old)'}")
        print(f"{'':<10}{'full InChIKey, stereo kept':<30}{'enantiomers merged':<26}{'one spelling = one name'}")
        for name in ("patents", "pubchem", "passage", "targeted", "COMBINED"):
            if name == "passage" and sentence_scope:
                continue
            cells = []
            for v, unit in ((full, "molecules"), (flat, "molecules"), (name_view, "names")):
                d = v[name]
                mols = {m for s_ in d.values() for m in s_}
                cells.append(f"{len(bar(d)):>3} of {N_TAGS}  {len(mols):>5} {unit}")
            print(f"{name:<10}{cells[0]:<30}{cells[1]:<26}{cells[2]}")
        if stale:
            print(f"\n!! {stale} patent-side name(s) have no record in names.jsonl — rows changed since structures.py last ran."
                  "\n   They count as their own molecule until it is re-run (python3 pipeline/structures.py; --merge).")
        multi = sum(1 for c in name2cid.values() if len({pc_ik.get(x) for x in c if x in pc_ik}) > 1)
        if multi:
            print(f"\nnote        {multi} PubChem-side name(s) map to CIDs with different structures; the lowest InChIKey is used")

    at = bar(combined)
    print(f"\nAT THE BAR ({len(at)}):\n  {', '.join(at)}")
    if full:
        by_name = set(bar(name_combined))
        lost, gained = sorted(by_name - set(at)), sorted(set(at) - by_name)
        if lost or gained:
            print(f"  (by name text the list would differ: also {lost or '-'}; not {gained or '-'})")
        fl = set(bar(flat["COMBINED"]))
        if fl != set(at):
            print(f"  (connectivity only: {sorted(set(at) - fl) or '-'} drop, {sorted(fl - set(at)) or '-'} added)")

    near = sorted(((len(s_), t) for t, s_ in combined.items() if BAR - 10 <= len(s_) < BAR), reverse=True)
    if near:
        print("\nwithin reach:")
        for n, t in near:
            by = f"   (name text {len(name_combined.get(t, ()))})" if full and len(name_combined.get(t, ())) != n else ""
            print(f"  {t:<14}{n:>4}   needs {BAR - n}{by}")

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

    # ---- QUEUE PRODUCTIVITY. The number that told us to stop reviewing, wrongly. ----
    productive, vocab, err = productive_predicate()
    print()
    if err:
        print(f"!! productive rows NOT COMPUTED — {err}")
        print("   Fix that rather than assuming the queue is empty. That assumption")
        print("   cost two days on 2026-09-05.")
    else:
        und = [r for r in jsonl(REVIEW) if not r.get("decision")]
        prod = [r for r in und if productive(r.get("sentence") or "")]
        print(f"review queue: {len(und)} undecided, {len(prod)} PRODUCTIVE "
              f"(review.html's own rule)")
        if prod:
            # Which SHORT tags those rows would feed. A productive row aimed at a tag
            # already past the bar adds a molecule but not a tag.
            pats = [(re.compile(r"\b" + re.escape(f) + r"\b", re.I), t)
                    for f, t in surf.items()]
            hits: collections.Counter = collections.Counter()
            for r in prod:
                s = r.get("sentence") or ""
                for rx, t in pats:
                    if rx.search(s):
                        hits[t] += 1
            short = [(t, len(combined.get(t, ())), n) for t, n in hits.most_common()
                     if len(combined.get(t, ())) < BAR][:6]
            if short:
                print("  aimed at tags below the bar:")
                for t, have, n in short:
                    print(f"     {t:<16}{have:>4} have, needs {BAR-have:<3} "
                          f"{n:>4} rows waiting")
            print(f"  at 0.82 productive-subset precision that is ~{int(len(prod)*0.82)} "
                  f"approvals — REVIEW BEFORE FETCHING ANYTHING.")

        # VOCAB drift. review.html hardcodes its vocabulary; odor_terms.tsv is the real
        # one. Forms missing from VOCAB are invisible to productive-ordering, so the
        # count above is a floor.
        missing = sorted(set(surf) - {w.lower() for w in vocab})
        if missing:
            print(f"  ! review.html's VOCAB has {len(vocab)} forms; odor_terms.tsv has "
                  f"{len(surf)}. {len(missing)} not in VOCAB, so the count above is a "
                  f"FLOOR:")
            print("    " + ", ".join(missing[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
