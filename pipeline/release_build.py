#!/usr/bin/env python3
"""
release_build.py — the v1.0 release export: the CC0 corpus as flat, self-describing files.

    python3 pipeline/release_build.py                 # writes release/v1.0/ (refuses if it exists)
    python3 pipeline/release_build.py --out DIR [--force]

Offline. Reads the same files status.py reads and counts the same way (it imports
status.py's own loaders and re-applies its row rules); it then RUNS status.py and refuses to
write anything unless the molecule total and the list of terms at the bar are identical. So the
release cannot drift from the one counter the project quotes.

WHAT IS IN v1.0 (Ivan, 2026-10-19): the CC0 corpus only. NOT in it: the Olfatorium layer
(licensed/, CC BY 4.0 with permission), the 30 retired quoted-reference rows, anything
undecided or rejected.

Files written to the output directory
  molecules.tsv   one line per distinct molecule (full InChIKey, stereo kept; a molecule
                  whose name has no definite structure is identified by its name text and is
                  marked mintable=no)
  evidence.tsv    one line per approved (molecule span, descriptor span) pair: the verbatim
                  quote, source, scope and how the row was decided
  tags.tsv        the 67 vocabulary terms with their molecule counts and surface forms
  README.md       what the files are, definitions, licence, limits
  manifest.json   counts, status.py's headline lines, hashes of every input, git head
  SHA256SUMS      checksums of everything above

Nothing is generated: every span is a verbatim substring of its quote (status.py asserts it);
the only derived columns are the structure fields, which come from names.jsonl (OPSIN, PubChem,
hand-authorised rewrites with reasons) or from the PubChem record of the compound identifier.
"""
from __future__ import annotations
import argparse, collections, csv, datetime, hashlib, importlib.util, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("status_mod", ROOT / "pipeline" / "status.py")
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

N_TAGS, BAR = S.N_TAGS, S.BAR
PATENT_LICENCE = "US patent document (government work)"

# structures.py trust class -> (basis code, direct?)  "direct" = read from the name or the PubChem record as
# extracted; hand-derived = a rewrite / OCR repair / stereo-free reading (see README, 'Structures').
BASIS = {"verbatim": ("opsin-verbatim", True), "pubchem": ("pubchem-name", True),
         "repaired+witness": ("ocr-repair-witnessed", False), "rewritten": ("rewritten", False),
         "flat": ("flat-stereo", False)}


def clean(v) -> str:
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()


def sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "release" / "v1.0"))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    if out.exists() and any(out.iterdir()) and not a.force:
        sys.exit(f"{out} exists and is not empty — pass --force to overwrite (nothing was changed)")

    surf = S.load_tags()
    exkeys = S.excluded_keys()
    ident = S.load_identity()
    if not ident:
        sys.exit("corpus/structures/names.jsonl missing — run pipeline/structures.py first")
    pat_ik, known, pc_ik = ident

    names = {}
    for line in S.STRUCT.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            names[r["key"]] = r
    cid_rec = {}                                    # CID -> PubChem record (smiles, names)
    if S.SMILES_CACHE.exists():
        for cid, v in json.loads(S.SMILES_CACHE.read_text(encoding="utf-8")).items():
            cid_rec[int(cid)] = v
    if S.STRUCT_PC.exists():
        for cid, v in json.loads(S.STRUCT_PC.read_text(encoding="utf-8")).get("cids", {}).items():
            cid_rec.setdefault(int(cid), v)

    ev = []                                         # evidence records (name-keyed until identities are settled)
    unmapped = collections.Counter()

    def add(**kw):
        ev.append(kw)

    # ---- patent sentence rows (review.jsonl), approved and not retired
    for r in S.jsonl(S.REVIEW):
        if r.get("decision") != "approve":
            continue
        sent = r.get("sentence") or ""
        if (r.get("source_id"), " ".join(sent.split())) in exkeys:
            continue
        mols = [m.strip() for m in (r.get("molecules") or []) if m.strip()]
        for d in (r.get("tags") or r.get("descriptors") or []):
            d = d.strip()
            tag = surf.get(d.lower())
            if tag is None:
                if d:
                    unmapped[d.lower()] += 1
                continue
            for m in mols:
                add(side="patent", name=S.norm(m), mol=m, desc=d, tag=tag, quote=sent, antecedent="",
                    scope="sentence", stype="patent-sentence", source_id=r.get("source_id"),
                    docs=";".join(r.get("sources") or [r.get("source_id")]), url="", licence=PATENT_LICENCE,
                    how="human-approved", offset=r.get("char_offset"))

    # ---- database rows (HSDB; CAMEO/OSHA/NIOSH), counted exactly as status.py counts them
    for r in S.jsonl(S.PUBCHEM):
        if r.get("excluded"):
            continue
        t, m = (r.get("tag") or "").strip(), S.norm(r.get("molecule_name") or "")
        if t and m:
            how = ("rule-extracted; negation cue in quote, triaged before publication (triage_pubchem.py)"
                   if r.get("needs_review") else "rule-extracted; span verified against the stored quote")
            add(side="pubchem", name=m, mol=r.get("molecule_name"), desc=r.get("span"), tag=t, quote=r.get("quote"),
                antecedent="", scope="sentence", stype="hsdb", source_id="HSDB", docs="", url=r.get("source_url"),
                licence=r.get("license_url") or "", how=how, offset=r.get("span_offset"), cid=r.get("molecule_cid"))
    if S.PHYSDESC.exists():
        for r in S.jsonl(S.PHYSDESC):
            held = bool(r.get("needs_review"))
            if held and r.get("review_decision") != "approve":
                continue
            t, m = (r.get("tag") or "").strip(), S.norm(r.get("molecule_name") or "")
            if t and m:
                how = ("rule-extracted; held row approved by a human" if held
                       else "rule-extracted; span verified against the stored quote")
                add(side="pubchem", name=m, mol=r.get("molecule_name"), desc=r.get("span"), tag=t,
                    quote=r.get("quote"), antecedent="", scope="sentence",
                    stype=(r.get("source_label") or "physdesc").lower(), source_id=r.get("source_label") or "",
                    docs="", url=r.get("source_url"), licence=r.get("license_url") or "", how=how,
                    offset=r.get("span_offset"), cid=r.get("molecule_cid"))

    # ---- passage rows (narrow scope) and targeted rows, approved only
    if S.PASSAGE.exists():
        for r in S.jsonl(S.PASSAGE):
            if r.get("review_decision") != "approve":
                continue
            mol = (r.get("molecule") or "").strip()
            for d in (r.get("descriptors") or []):
                tag = surf.get(d.lower())
                if tag and mol:
                    add(side="patent", name=S.norm(mol), mol=mol, desc=d, tag=tag, quote=r.get("sentence"),
                        antecedent=r.get("antecedent") or "", scope="passage", stype="patent-passage",
                        source_id=r.get("source_id"), docs=r.get("source_id"), url="", licence=PATENT_LICENCE,
                        how="human-approved (human-resolved reference)", offset="")
    if S.TARGETED.exists():
        for r in S.jsonl(S.TARGETED):
            if r.get("review_decision") != "approve":
                continue
            mol = (r.get("molecule") or "").strip()
            for d in (r.get("descriptors") or []):
                tag = surf.get(d.lower())
                if tag and mol:
                    add(side="patent", name=S.norm(mol), mol=mol, desc=d, tag=tag, quote=r.get("sentence"),
                        antecedent="", scope="sentence", stype="patent-targeted", source_id=r.get("source_id"),
                        docs=r.get("source_id"), url="", licence=PATENT_LICENCE,
                        how="human-approved (found by targeted search)", offset="")

    # ---- identities, exactly status.py's rule
    name2cid = collections.defaultdict(set)
    for e in ev:
        if e["side"] == "pubchem" and e.get("cid"):
            name2cid[e["name"]].add(e["cid"])

    def identity(e):
        if e["side"] == "pubchem":
            iks = {pc_ik[c] for c in name2cid.get(e["name"], ()) if c in pc_ik}
            return min(iks) if iks else None
        return pat_ik.get(e["name"])

    mols = {}
    for e in ev:
        ik = identity(e)
        mid = ik if ik else "name:" + e["name"]
        e["mid"], e["ik"] = mid, ik
        m = mols.setdefault(mid, {"ik": ik, "spans": collections.Counter(), "tags": set(), "types": set(),
                                  "docs": set(), "n": 0, "cids": set(), "keys": set()})
        m["spans"][clean(e["mol"])] += 1
        m["tags"].add(e["tag"])
        m["types"].add(e["stype"])
        m["docs"].update(x for x in e["docs"].split(";") if x) if e["docs"] else m["docs"].add(e["url"])
        m["n"] += 1
        m["keys"].add(e["name"])
        if e.get("cid"):
            m["cids"].add(e["cid"])

    # ---- the self-check: refuse to write unless status.py agrees
    tagsets = collections.defaultdict(set)
    for e in ev:
        tagsets[e["tag"]].add(e["mid"])
    at_bar = sorted(t for t, s in tagsets.items() if len(s) >= BAR)
    res = subprocess.run([sys.executable, str(ROOT / "pipeline" / "status.py")], capture_output=True, text=True, check=True)
    m_tot = re.search(r"^COMBINED\s+(\d+) of (\d+)\s+(\d+) molecules", res.stdout, re.M)
    m_bar = re.search(r"AT THE BAR \((\d+)\):\n\s+(.+)", res.stdout)
    if not (m_tot and m_bar):
        sys.exit("could not read status.py's COMBINED line / at-the-bar list — export not written")
    want_tot, want_bar = int(m_tot.group(3)), sorted(x.strip() for x in m_bar.group(2).split(","))
    if len(mols) != want_tot or at_bar != want_bar:
        sys.exit(f"MISMATCH with status.py: export has {len(mols)} molecules and {len(at_bar)} terms at the bar; "
                 f"status.py says {want_tot} and {len(want_bar)}. Nothing written.")
    print(f"self-check OK: {len(mols)} molecules, {len(at_bar)} of {N_TAGS} terms at the bar — identical to status.py")

    # ---- molecule rows
    def structure_of(mid, m):
        """-> (smiles, basis list, strength, note)"""
        bases, smiles = [], None
        if m["ik"]:
            for c in sorted(m["cids"]):
                rec = cid_rec.get(c)
                if rec and rec.get("inchikey") == m["ik"]:
                    bases.append(("pubchem-cid", True))
                    smiles = smiles or rec.get("smiles")
            for k in sorted(m["keys"]):
                n = names.get(k)
                if n and n.get("trust") in BASIS and n.get("inchikey") == m["ik"]:
                    bases.append(BASIS[n["trust"]])
                    smiles = smiles or n.get("smiles")
            strength = "direct" if any(d for _, d in bases) else "hand-derived"
            return smiles or "", sorted({b for b, _ in bases}), strength, ""
        notes = sorted({("unresolved" if names[k]["trust"] == "none" else "held: " + names[k]["trust"])
                        for k in m["keys"] if k in names})
        return "", [], "none", "no definite structure (" + ("/".join(notes) or "not in names.jsonl") + "); counted by name text"

    mrows = []
    for mid, m in mols.items():
        smiles, bases, strength, note = structure_of(mid, m)
        label = ""
        for c in sorted(m["cids"]):
            rec = cid_rec.get(c) or {}
            label = rec.get("common_name") or rec.get("title") or rec.get("iupac_name") or ""
            if label:
                break
        spans = [s for s, _ in m["spans"].most_common()]
        if not label:                                # patent-side: the best-trusted spelling, then the commonest, then the longest
            rank = {"verbatim": 0, "pubchem": 1, "repaired+witness": 2, "flat": 3, "rewritten": 4}
            label = sorted(spans, key=lambda s: (rank.get((names.get(S.norm(s)) or {}).get("trust"), 9),
                                                 -m["spans"][s], -len(s), s))[0]
        mrows.append({
            "molecule_id": mid, "inchikey": m["ik"] or "", "connectivity_key": (m["ik"] or "")[:14], "label": label,
            "smiles": smiles, "structure_basis": ";".join(bases), "structure_strength": strength,
            "mintable": "yes" if m["ik"] else "no", "tags": ";".join(sorted(m["tags"])), "n_tags": len(m["tags"]),
            "n_evidence": m["n"], "n_documents": len(m["docs"]), "source_types": ";".join(sorted(m["types"])),
            "name_spellings": " | ".join(spans), "pubchem_cids": ";".join(str(c) for c in sorted(m["cids"])),
            "note": note})
    mrows.sort(key=lambda r: r["molecule_id"])

    erows = []
    for e in ev:
        eid = hashlib.sha1("|".join(clean(x) for x in (e["stype"], e["source_id"], e["quote"], e["mol"], e["desc"],
                                                       e["tag"])).encode()).hexdigest()[:12]
        erows.append({"evidence_id": eid, "molecule_id": e["mid"], "inchikey": e["ik"] or "", "tag": e["tag"],
                      "descriptor_span": clean(e["desc"]), "molecule_span": clean(e["mol"]), "quote": clean(e["quote"]),
                      "antecedent": clean(e["antecedent"]), "scope": e["scope"], "source_type": e["stype"],
                      "source_id": clean(e["source_id"]), "documents": e["docs"], "source_url": clean(e["url"]),
                      "licence_basis": clean(e["licence"]), "how_decided": e["how"]})
    erows.sort(key=lambda r: (r["molecule_id"], r["tag"], r["evidence_id"]))
    seen = collections.Counter()
    for r in erows:                                  # identical assertions from two source records: keep both, make the id unique
        seen[r["evidence_id"]] += 1
        if seen[r["evidence_id"]] > 1:
            r["evidence_id"] += f"-{seen[r['evidence_id']]}"
    if len({r["evidence_id"] for r in erows}) != len(erows):
        sys.exit("evidence_id is not unique — nothing written")

    forms = collections.defaultdict(list)
    for f, t in surf.items():
        forms[t].append(f)
    trows = [{"tag": t, "molecules_v1_0": len(tagsets.get(t, ())), "at_bar_30": "yes" if len(tagsets.get(t, ())) >= BAR else "no",
              "surface_forms": ";".join(sorted(forms[t]))} for t in sorted(forms, key=lambda t: (-len(tagsets.get(t, ())), t))]
    if len(trows) != N_TAGS:
        sys.exit(f"vocabulary has {len(trows)} terms, expected {N_TAGS}")

    # ---- write
    out.mkdir(parents=True, exist_ok=True)

    def write_tsv(name, rows):
        with (out / name).open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
            w.writeheader()
            w.writerows(rows)

    write_tsv("molecules.tsv", mrows)
    write_tsv("evidence.tsv", erows)
    write_tsv("tags.tsv", trows)

    n_ik = sum(1 for r in mrows if r["mintable"] == "yes")
    n_conn = len({r["connectivity_key"] for r in mrows if r["connectivity_key"]})
    n_direct = sum(1 for r in mrows if r["structure_strength"] == "direct")
    n_hand = sum(1 for r in mrows if r["structure_strength"] == "hand-derived")
    n_none = len(mrows) - n_ik
    by_type = collections.Counter(r["source_type"] for r in erows)
    counts = {"molecules": len(mrows), "molecules_with_structure": n_ik, "molecules_connectivity_only": n_conn,
              "structure_direct": n_direct, "structure_hand_derived": n_hand, "molecules_name_only": n_none,
              "evidence_rows": len(erows), "evidence_by_source_type": dict(sorted(by_type.items())),
              "terms_at_bar": len(at_bar), "terms_total": N_TAGS, "unmapped_descriptor_pairs_skipped": sum(unmapped.values())}
    print(json.dumps(counts, indent=1))

    (out / "README.md").write_text(README.format(
        molecules=len(mrows), with_structure=n_ik, name_only=n_none, direct=n_direct, hand=n_hand, conn=n_conn,
        evidence=len(erows), at_bar=len(at_bar), n_tags=N_TAGS, bar=BAR, at_bar_list=", ".join(at_bar),
        types="; ".join(f"{k} {v}" for k, v in sorted(by_type.items()))), encoding="utf-8")

    inputs = {}
    for p in (S.REVIEW, S.PUBCHEM, S.PHYSDESC, S.PASSAGE, S.TARGETED, S.EXCLUSIONS, S.STRUCT, S.STRUCT_PC, S.SMILES_CACHE,
              ROOT / "corpus" / "structures" / "rewrites.json", ROOT / "ontology" / "odor_terms.tsv"):
        if p.exists():
            inputs[str(p.relative_to(ROOT))] = sha256(p)

    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            return None
    head = git("rev-parse", "HEAD")
    dirty = git("status", "--porcelain", "--untracked-files=no")
    manifest = {"version": "1.0-candidate", "built_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "git_head": head, "tracked_files_modified_at_build": (len(dirty.splitlines()) if dirty is not None else None),
                "scope": "CC0 corpus only; the licensed layer, retired rows, rejected and undecided rows are not included",
                "counts": counts, "terms_at_bar": at_bar,
                "status_py_headline": {"COMBINED": m_tot.group(0), "at_the_bar": m_bar.group(0)},
                "inputs_sha256": inputs}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    sums = [f"{sha256(out / n)}  {n}" for n in ("molecules.tsv", "evidence.tsv", "tags.tsv", "README.md", "manifest.json")]
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


README = """# OpenScent v1.0 (candidate) — the corpus as flat files

**CC0 1.0.** A structure–odour corpus built only from public-domain sources: United States patent text and
United States government databases (HSDB, CAMEO Chemicals, OSHA, NIOSH) read through PubChem. Every molecule
name and every descriptor in `evidence.tsv` is a verbatim substring of its `quote`; nothing is generated.

| file | one line per | lines |
|---|---|---|
| `molecules.tsv` | distinct molecule | {molecules} |
| `evidence.tsv` | approved (molecule span, descriptor span) pair, with its quote and source | {evidence} |
| `tags.tsv` | vocabulary term | {n_tags} |
| `manifest.json` | — | counts, `status.py` headline lines, SHA-256 of every input, git head |
| `SHA256SUMS` | — | checksums of the files above |

## Counts (generated by `pipeline/release_build.py`, checked equal to `pipeline/status.py` before writing)

- **{molecules} molecules.** {with_structure} have a structure (`mintable = yes`), {conn} distinct by connectivity
  (enantiomers merged). {name_only} have no definite structure and are identified by name text (`mintable = no`).
- **{at_bar} of {n_tags} vocabulary terms** reach {bar} molecules: {at_bar_list}.
- Evidence rows by source type: {types}.

## Definitions

- **A molecule is a distinct full InChIKey, stereochemistry kept** (enantiomers can smell different). It is not a
  name spelling: patent-side names were resolved to structures (OPSIN offline, PubChem name lookup, and
  hand-authorised rewrites that each carry a stored reason in `corpus/structures/rewrites.json`); database rows are
  identified through their PubChem compound identifier. Two names are merged only when the structure is trusted.
- **`molecule_id`** is the InChIKey, or `name:<text>` for the molecules without a definite structure.
- **`structure_basis`**: `pubchem-cid` (PubChem record of the row's compound identifier), `opsin-verbatim` (OPSIN
  read the span as extracted), `pubchem-name` (PubChem name match), `ocr-repair-witnessed`, `rewritten`
  (hand-authorised reading), `flat-stereo` (stereo descriptors not readable, so no stereochemistry).
  **`structure_strength`**: `direct` when at least one basis is `pubchem-cid`, `opsin-verbatim` or `pubchem-name`;
  `hand-derived` when it rests only on the other three; `none` otherwise. Counting only `direct` structures changes
  the number of terms at the bar (see the paper's Limitations).
- **`tag`** is one of the {n_tags} vocabulary terms; `descriptor_span` is the verbatim word that was mapped to it by
  the human-written table `ontology/odor_terms.tsv` (listed per term in `tags.tsv`). Descriptor words with no entry
  in that table are not in this release.
- **`how_decided`**: patent rows were decided one by one by a human against `REVIEW-RULES.md`; passage rows carry a
  human-resolved reference (`antecedent` holds the preceding sentence). **Database rows (HSDB, CAMEO, OSHA, NIOSH)
  were extracted by rule from the odour clause, each span checked against the stored quote; they were not decided
  one by one by a human.** Rows the rules flagged were held and decided by a human before counting, or triaged
  before publication, as the column says.
- `scope`: `sentence` (one sentence) or `passage` (the narrow, human-resolved two-sentence form).
- `documents`: every patent document that carries the same sentence (a sentence repeated across documents is one
  assertion, listed once).

## Limits you should know before using it

- The {name_only} molecules without a structure cannot be used for structure work; they are kept because their
  descriptor evidence is valid and counted by `status.py`.
- {hand} molecules have a hand-derived structure only (a rewrite, an OCR repair or a stereo-free reading). The
  readings are in `corpus/structures/`; question them first if a structure looks wrong.
- Patent text carries OCR errors; spans are verbatim, so `molecule_span` can be misspelt while the molecule is right.
- The review queue was screened by a model after batch adjudication; rows it screened out were **left undecided, not
  rejected, and have not been read by a human**. Their absence is a recall limit, not a judgement.
- CC0 waives copyright, not patents: a molecule appearing here says nothing about live patent claims.
- Not in this release: the separately licensed Olfatorium descriptor layer (`licensed/`), 30 retired patent rows that
  relayed copyrighted reference works, and every rejected or undecided row.

Source code: Apache-2.0, https://github.com/VanPez/openscent
"""

if __name__ == "__main__":
    raise SystemExit(main())
