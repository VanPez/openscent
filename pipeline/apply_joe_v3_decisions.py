#!/usr/bin/env python3
"""
apply_joe_v3_decisions.py — PROPOSED changes from the 2026-10-29 pass over Joe's v3 workbook and his notes.
NOT YET APPROVED: each block below waits for Ivan's decision; drop or edit an entry before --write.

    python3 pipeline/apply_joe_v3_decisions.py              # REPORT ONLY: shows each line it would touch
    python3 pipeline/apply_joe_v3_decisions.py --write      # timestamped backups first, then touches ONLY those lines
    python3 pipeline/apply_joe_v3_decisions.py --bauer      # also retire the 3 rows relayed from Bauer/Garbe/Surburg

Never with a review.html session open (it would overwrite review.jsonl).

What it does (conventions of apply_mixture_decisions.py, 2026-10-21):
  REJECT        review.jsonl: decision -> reject; molecules / molecule / descriptors emptied, old values in review_note
  DROP_DESC     review.jsonl: the named descriptors leave the row (they describe something else); old list in review_note
  DROP_MOL      review.jsonl: a word wrongly taken as a molecule leaves the row's molecules
  RETIRE        exclusions.jsonl: approved sentences that relay a reference work's wording (the 09-26 rule), which
                exclude_quotes.py missed because the splitter cut at "No." / "number" and left the work's name in the
                sentence before
  REWRITES      corpus/structures/rewrites.json: structures for name-only molecules (then run structures.py, --todo,
                --merge, status.py, release_build.py — the 10-21 order)

Rows are found by content, never by line number; each must match exactly the expected count or nothing is written.
"""
from __future__ import annotations
import json, pathlib, shutil, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROWS = ROOT / "corpus" / "rows"
REWRITES = ROOT / "corpus" / "structures" / "rewrites.json"
WHEN = "Ivan 2026-10-29"   # set to the date of the decision before --write

REJECT = [  # (source_id, molecules, descriptors (as stored), why)
    ("US10100267B1", ["3-(3-(tert-butyl)cyclohexyl)propanal"], ["aldehydic", "floral", "green"],
     "counterfactual composition statement ('the addition of ... instead of the invention's compound provided new fragrance "
     "...'), and 'less floral/green' is negated (REVIEW-RULES: attribution, negation)"),
    ("US10100267B1", ["3-(3-isopropylcyclohexyl)butanal"], ["orris", "floral", "powdery", "lily"],
     "counterfactual composition statement ('... instead of the invention's compound provided new fragrance ...'), and the "
     "lily of the valley note is 'devoid of' (REVIEW-RULES: attribution, negation)"),
    ("US10472591B2", ["(+−)-2-methyl-3-[4-(2-methyl-2-propanyl)-1-cyclohexen-1-yl]propanal"], ["lily of the valley", "lactonic", "peach"],
     "counterfactual ('When instead of the invention's compound were used ... the composition acquired ...'), and the "
     "lactonic white peach note is 'devoid of' (REVIEW-RULES: attribution, negation)"),
    ("US3993604A", ["trans-4-isopropenyl-cyclohexylmethanol"], ["aromatic"],
     "'aromatic' is from 'certain aromatic hydrocarbons', a chemical class named as a comparison, not a smell quality "
     "(REVIEW-RULES: descriptors)"),
    ("US20100130397A1", ["1-methyl-3-(2-methylpropyl)cyclohexan-1-ol"], ["flowery", "lily of the valley", "lilac", "herbal", "pine", "citrus"],
     "'The smell of a mixture of cis- and trans-...' (mixture rule)"),
    ("US4751214A", ["l-isomer"], ["peppermint"],
     "'the l-isomer' is an anaphor (REVIEW-RULES: attribution); the 10-03 veto stands. It is l-menthol, which the corpus "
     "already has with 'mint' and 'fresh' from other sentences, so nothing is lost"),
]
DROP_DESC = [  # (source_id, molecules, descriptors now, descriptors to drop, why)
    ("US3852219A", ["trans isomer of l-acetoxy-Lsec-butyl-L ethynylcyclohexane"], ["freshness", "minty", "woody"], ["freshness", "minty"],
     "the 'sentence' is two sentences glued at '... strength. l-Acetoxy-' (OCR 'l' for '1' hid the boundary); freshness and "
     "minty describe a cologne with 5% of the trans ALCOHOL, a different compound (spotted by Joe)"),
    ("US3870800A", ["ethyl 4-(methylthio)butyrate"], ["fruity", "ylang", "jasmin", "floral"], ["floral"],
     "'floral' is from 'this floral essential oil composition' — the blend, not the molecule (US3904556A's twin row has no 'floral')"),
    ("US3873574A", ["6-n-pentyl-alpha-pyrone"], ["green", "coconut", "tobacco", "woody"], ["woody"],
     "'woody' is from 'this woody, aphrodesia perfume formulation' — the blend, not the molecule"),
    ("US3644540A", ["1,1-dimethyl 5,7 diisopropyl-6-hydroxyindan"], ["Rose", "clean", "musk"], ["Rose"],
     "'Rose' is from the heading 'in a Rose perfume' — the blend, not the molecule"),
    ("US3705121A", ["1,2,3 ,4,6,7,8,9,10,11,12,13-dodecahydrocyclodeca[b] quinoxaline"], ["oily", "sweet", "nut"], ["oily"],
     "'oily' is from 'This oily material' — a physical state, not a smell"),
    ("US3754934A", ["l,2,3,4,6,7,8,9,10,11,12,13- dodecahydrocyclo-deca[blquinoxaline"], ["oily", "sweet"], ["oily"],
     "'oily' is from 'This oily material' — a physical state, not a smell"),
    ("US20150057206A1", ["1,1,3,3-Tetramethyl-2,3,4,5- tetrahydro-1H-7,9-diaza- cyclopenta[a]naphthalene"], ["musky", "woody", "clean"], ["clean"],
     "the sentence says 'not clean' (REVIEW-RULES: negation inverts)"),
    ("US6458987B1", ["(R)-citronellyl lactate"], ["flowery", "lily of the valley", "warm", "rosy"], ["rosy"],
     "'rosy' is from 'more natural than rosy alcohols' — a class of compounds named as a comparison"),
]
DROP_MOL = [  # (source_id, molecules now, molecule to drop, why)
    ("US20090270658A1", ["3,7-dimethyloctan-1-ol", "petal"], "petal",
     "'petal' is part of the odour phrase 'rose petal-like', not a molecule (spotted by Joe); the molecule, 3,7-dimethyloctan-1-ol, stays"),
]
RETIRE = [  # (source_id, molecule on the approved row, quoted work, where the work is named)
    ("US4289658A", "dihydrocyclol", "Arctander", "'Actander compound No.' ends the sentence before (OCR 'Actander')"),
    ("US4272412A", "2-chloro-4,6-dinitro-1,3-dimethyl-5-tertiary-butylbenzene", "Arctander", "'Actander compound No.' ends the sentence before"),
    ("US4400311A", "isopiperitenone", "Arctander", "'Arctander further states at Monograph No.' ends the sentence before"),
    ("US4449008A", "isopiperitenone", "Arctander", "'Arctander further states at Monograph No.' ends the sentence before"),
    ("US4451403A", "iso-pulegone", "Arctander", "'Arctander further states that Monograph No.' ends the sentence before"),
    ("US4482747A", "iso-pulegone", "Arctander", "'Arctander further states that Monograph No.' ends the sentence before"),
    ("US4493791A", "iso-pulegone", "Arctander", "'Arctander further states that Monograph No.' ends the sentence before"),
    ("US4501918A", "iso-pulegone", "Arctander", "'Arctander further states that Monograph No.' ends the sentence before"),
    ("US4486337A", "n-hexyl tiglate", "Arctander", "a numbered list from 'Perfume and Flavor Chemicals' ('No. 1682: n-hexyl tiglate--...')"),
    ("US20100130397A1", "p-tert-butylcyclohexanol", "Arctander", "'S. Arctander, Perfume and Flavor Chemicals ... describes ... 4-alkylcyclohexanols'; 'Under number 433'"),
    ("US20100130397A1", "4-Ethylcyclohexanol", "Arctander", "same passage; '(number 1201)'"),
    ("US20090162308A1", "p-methylacetophenone", "Arctander", "'(cf. S. Arctander, Perfume and Flavor Chemicals ... or K. Bauer, D. Garbe and H. Surburg, ...): p-methylacetophenone ...'"),
]
RETIRE_BAUER = [  # Bauer, Garbe, Surburg, Common Fragrance and Flavor Materials (Wiley-VCH) — not on the 09-26 list; --bauer only
    ("US20080064625A1", "3-phenylpropanol", "Bauer/Garbe/Surburg", "'(cf. Common Fragrance and Flavor Materials, 4th Edition, Wiley-VCH, Weinheim 2001): ...'"),
    ("US20080064625A1", "2-Methyl-5-phenylpentanol", "Bauer/Garbe/Surburg", "the next item of the same cf. list"),
    ("US20080064625A1", "3-Methyl-5-phenylpentanol", "Bauer/Garbe/Surburg", "the next item of the same cf. list"),
]
WORKS = {"Arctander": "Arctander, Perfume and Flavor Chemicals (1969)",
         "Bauer/Garbe/Surburg": "Bauer, Garbe, Surburg, Common Fragrance and Flavor Materials (Wiley-VCH)"}

# Strength as in rewrites.json: S = the patent text fixes the structure; M = probable, not certain.
REWRITE_NEW = [
    ("J27", "S", "dehydrorhodinol", "(5E)-3,7-dimethylocta-5,7-dien-1-ol",
     "US3455997A defines it: 'the trans alcohol (VI) (dehydrorhodinol)', and Example 6 names VI 'trans-3,7-dimethyl-5,7-octadien-1-ol' "
     "(hydrogenation gives 3,7-dimethyloctan-1-ol). PubChem CID 12920428 (same InChIKey). Proposed by Joe. C3 left flat"),
    ("J28", "S", "Epoxytamariscol", "2-(3,3-dimethyloxiran-2-yl)-3,7-dimethyloctahydro-1H-inden-2-ol",
     "US4659509A defines it: '3,7-dimethyl-2-(2-methyl-1,2-epoxypropyl)hexahydroindan-2-ol (hereinafter referred to as epoxytamariscol)'; "
     "OPSIN gives the same InChIKey for the patent's name and this one; PubChem CID 20206814 (connectivity). Proposed by Joe. Flat"),
    ("J29", "S", "ethyl tat-methyl, a-(2,3,3a,4,5,6,7,7a-octahydro-4,7-methanoinden 5 -ylidene) acetate",
     "ethyl 2-(octahydro-5H-4,7-methanoinden-5-ylidene)propanoate",
     "OCR of 'ethyl alpha-methyl, alpha-(...-ylidene) acetate': US3557188A lists the same ester cleanly ('ethyl a methyl, 0c "
     "(2,3,3a,4,5,6,7,7a-octahydro-4,7-methanoinden-5-ylidene) acetate') and its precursor 'ethyl a-methyl, a-(5-hydroxy-...-5-yl) acetate'. "
     "No PubChem record. Proposed by Joe (his workbook SMILES; the SMILES in his Telegram note has a cyclobutane and is not this compound). Flat"),
    ("J30", "S", "trans isomer of l-acetoxy-Lsec-butyl-L ethynylcyclohexane", "2-(butan-2-yl)-1-ethynylcyclohexyl acetate",
     "OCR of '1-acetoxy-2-sec-butyl-1-ethynylcyclohexane'; US3852219A's own compound list prints '1-Acetoxy-2-sec-butyl-1-ethynylcyclohexane (trans)'. "
     "PubChem CID 161936. Proposed by Joe. Flat: the patent does not say which C1 group 'trans' refers to"),
    ("J31", "S", "8-oxoethyl epicamphene hydrate", "3-(3-hydroxy-2,3-dimethylbicyclo[2.2.1]heptan-2-yl)propanal",
     "US3679756A names the Step (2) product 'exo-2-endo-3-dimethyl-endo-2-hydroxy-exo-3-(3'-oxopropyl)bicyclo[2.2.1]heptane' "
     "(claims and Example C); PubChem CID 130025287. Joe's proposal put the side chain on the carbinol carbon (C2) — the patent puts it on C3. "
     "Flat: the patent's exo/endo are not encoded (OPSIN cannot read them)"),
    ("J32", "S", "S-ethenyl-epi-camphene hydrate", "2,3-dimethyl-3-(prop-2-en-1-yl)bicyclo[2.2.1]heptan-2-ol",
     "'S' is OCR for '8' (the patent also prints '8-ethenyl-epi-camphene hydrate'); US3662008A names the Step (2) product "
     "'exo-2-methyl-endo-3-methyl-endo-2-hydroxy-exo-3-(1'-prop-2'-enyl)bicyclo[2.2.1]heptane' (claims and Example C). No PubChem record. "
     "Joe's proposal put the allyl group on C2 — the patent puts it on C3. Flat: exo/endo not encoded"),
    ("J33", "S", "nortetrapatchoulol", "10,11,11-trimethyltetracyclo[5.3.1.0^{2,4}.0^{5,10}]undecan-1-ol",
     "US20130287707A1 says US 3,991,123 describes nortetrapatchoulol, a tetracyclic norsesquiterpene alcohol with a three-membered ring, "
     "warm, sweet, woody and camphor-like; US3991123A's C14 alcohol is '10,11,11-trimethyl-tetracyclo-(5.3.1.0 2,4.0 5,10)undecan-1-ol' "
     "(MS 206; 'warm, woody, sweet and camphoraceous'). PubChem CID 54403738 carries that name (CAS 62731-84-4). Proposed by Joe. Flat"),
    ("J34", "S", "Dihydronorpatchoulinol", "2,2,8-trimethyltricyclo[5.3.1.0^{3,8}]undecan-3-ol",
     "US3996169A Example XVI makes it by sodium cyclization of 1,3,3-trimethyl-6-(3-chloropropyl)bicyclo[2.2.2]octan-2-one (the chain closes "
     "on the ketone carbon): MS 208 (C14H24O), three methyl singlets. That product is this name (Claude's derivation; same graph as Joe's "
     "proposal, which came from another route). PubChem CID 54256436. Flat"),
    ("J35", "S", "patchoulione", "octahydro-1,4,9,9-tetramethyl-3a,7-methanoazulen-5(4H)-one",
     "US3748284A: 'Buchi et al., 83 J.A.C.S. 927 (1961), shows ... patchoulione which is stated to be octahydro-1,4,9,9-tetramethyl-3a,7-"
     "methanoazulen-5(4H)-one' (US3991123A says the same). PubChem CID 12314005 (CAS 5986-56-1). The structure is the one the patent "
     "states, from the 1961 paper; Joe notes the 1961 patchouli skeleton was later disputed. Flat"),
    ("J36", "S", "3-methoxy-4-homoisotwistane", "3-methoxytricyclo[5.3.1.0^{3,8}]undecane",
     "US4169958A defines the parent: '4-homoisotwistane (tricyclo[5.3.1.0 3,8]undecane)'; C3 is a bridgehead, as the patent's chemistry "
     "needs (3-halogeno-4-homoisotwistane + alcohol, no base: bridgehead solvolysis). Assumes the trivial name's locant follows the "
     "von Baeyer numbering. No PubChem record. Proposed by Joe"),
    ("J37", "M", "3,7-Caryophyllane epoxide", "4,8-epoxy-4,8,11,11-tetramethylbicyclo[7.2.0]undecane",
     "US3978089A makes it by cyclizing caryophyll-6-en-3-ol 'with the formation of a 3,7-epoxy group'; in the patent's numbering (6,7 = the "
     "ring double bond of caryophyllene, 3 = the exocyclic one) that is an ether between the two methyl-bearing carbons, C4 and C8 of "
     "bicyclo[7.2.0]undecane. PubChem has the connectivity as '4,8-beta-epoxycaryophyllene' (CID 91749887). Claude's numbering argument; "
     "proposed by Joe. Probable, not certain. Flat"),
    ("J38", "M", "hexahydro-1,5,5-trimethyl-2H-2,4-a-methanonaphthalene-1(5H)-one",
     "3,5,5-trimethyl-3,4,6,7,8,8a-hexahydro-2H-2,4a-methanonaphthalen-1(5H)-one",
     "the printed name is impossible (a methyl and the ketone on C1; OPSIN: 'unphysical valency'). The same patents name 5,5-dimethyl and "
     "2,5,5-trimethyl homologues; CAS registered 5,5-dimethyl (77923-74-1), 2,5,5-trimethyl (77923-82-1) and 3,5,5-trimethyl (77923-83-2) "
     "in one block of numbers, which fits the 3,5,5 isomer being this patent's third compound (not proof). PubChem CID 44154114. Proposed by Joe (his 2,5,5 "
     "alternative is the patents' Example VIII compound, so not this one). Probable, not certain. Flat"),
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


def find(parsed, src, mols, n=1):
    hits = [i for i, r in enumerate(parsed)
            if r and r["source_id"] == src and r.get("decision") == "approve" and r.get("molecules") == mols]
    if len(hits) != n:
        sys.exit(f"expected {n} approved row(s) for {src} / {mols}, found {len(hits)} — refusing")
    return hits


def plan(bauer: bool):
    raw, parsed = load(ROWS / "review.jsonl")
    edits = {}
    for src, mols, desc, why in REJECT:
        for i in find(parsed, src, mols):
            if parsed[i]["descriptors"] != desc:
                sys.exit(f"{src} / {mols}: descriptors are {parsed[i]['descriptors']}, expected {desc} — refusing")
            r = dict(parsed[i])
            r.update(decision="reject", molecules=[], molecule="", descriptors=[],
                     review_note=f"{WHEN}: reject — {why}. Was approve with molecules={mols}, descriptors={desc}.")
            edits[i] = r
    for src, mols, desc, drop, why in DROP_DESC:
        hits = [i for i, r in enumerate(parsed) if r and r["source_id"] == src and r.get("decision") == "approve"
                and r.get("molecules") == mols and r.get("descriptors") == desc]
        if len(hits) != 1:
            sys.exit(f"expected 1 approved row for {src} / {mols} / {desc}, found {len(hits)} — refusing")
        i = hits[0]; r = dict(parsed[i])
        r.update(descriptors=[d for d in desc if d not in drop],
                 review_note=f"{WHEN}: descriptors {drop} dropped — {why}. Was descriptors={desc}.")
        edits[i] = r
    for src, mols, drop, why in DROP_MOL:
        i = find(parsed, src, mols)[0]; r = dict(parsed[i])
        new = [m for m in mols if m != drop]
        r.update(molecules=new, molecule=new[0], review_note=f"{WHEN}: {drop!r} removed from molecules — {why}. Was molecules={mols}.")
        edits[i] = r

    # exclusions: approved, not yet retired, found by source + molecule
    ex_raw, ex_parsed = load(ROWS / "exclusions.jsonl")
    have = {(e["source_id"], e["sentence"]) for e in ex_parsed if e}
    new_ex = []
    for src, mol, work, where in RETIRE + (RETIRE_BAUER if bauer else []):
        hits = [r for r in parsed if r and r["source_id"] == src and r.get("decision") == "approve" and mol in (r.get("molecules") or [])]
        if len(hits) != 1:
            sys.exit(f"expected 1 approved row for {src} / {mol!r} to retire, found {len(hits)} — refusing")
        key = (src, " ".join(hits[0]["sentence"].split()))
        if key in have:
            sys.exit(f"{src} / {mol!r} is already retired — refusing")
        new_ex.append({"source_id": src, "sentence": key[1], "reason": "third-party-quote", "quoted_work": WORKS[work],
                       "molecules": hits[0]["molecules"], "decided": WHEN,
                       "note": f"missed by exclude_quotes.py 2026-09-26: the work is named outside this sentence ({where})"})

    rw = json.loads(REWRITES.read_text(encoding="utf-8"))
    ids = {x["id"] for x in rw["rewrites"]}; raws = {" ".join(x["raw"].lower().split()) for x in rw["rewrites"]}
    for i_, s_, raw_, reading, why in REWRITE_NEW:
        if i_ in ids or " ".join(raw_.lower().split()) in raws:
            sys.exit(f"rewrite {i_} / {raw_!r} already present — refusing")
    return (raw, parsed, edits), (ex_raw, new_ex), rw


def main():
    write, bauer = "--write" in sys.argv, "--bauer" in sys.argv
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (raw, parsed, edits), (ex_raw, new_ex), rw = plan(bauer)
    print(f"== review.jsonl: {len(edits)} line(s)")
    for i in sorted(edits):
        r = edits[i]
        print(f"   line {i + 1}: {r['source_id']} decision={r['decision']} molecules={r['molecules']} descriptors={r['descriptors']}")
    print(f"== exclusions.jsonl: +{len(new_ex)} sentence(s)")
    for e in new_ex:
        print(f"   {e['source_id']:<17}{e['quoted_work'][:22]:<24}{', '.join(e['molecules'])[:60]}")
    print(f"== rewrites.json: +{len(REWRITE_NEW)} ({', '.join(x[0] + '/' + x[1] for x in REWRITE_NEW)})")
    if write:
        p = ROWS / "review.jsonl"; ser = style(raw, parsed, edits)
        shutil.copy2(p, p.with_name(f"review.jsonl.bak-{stamp}"))
        for i, r in edits.items():
            raw[i] = ser(r)
        p.write_text("\n".join(raw) + "\n", encoding="utf-8")
        p = ROWS / "exclusions.jsonl"
        shutil.copy2(p, p.with_name(f"exclusions.jsonl.bak-{stamp}"))
        p.write_text("\n".join(ex_raw + [json.dumps(e, ensure_ascii=False) for e in new_ex]) + "\n", encoding="utf-8")
        shutil.copy2(REWRITES, REWRITES.with_name(f"rewrites.json.bak-{stamp}"))
        rw["rewrites"] += [{"id": i_, "strength": s_, "raw": raw_, "reading": reading, "why": f"{why}. Approved by {WHEN}"}
                           for i_, s_, raw_, reading, why in REWRITE_NEW]
        REWRITES.write_text(json.dumps(rw, ensure_ascii=False, indent=1), encoding="utf-8")  # the file has no final newline
    print("WRITTEN (backups *.bak-" + stamp + ")" if write else "REPORT ONLY — nothing written (--write to apply)")


if __name__ == "__main__":
    main()
