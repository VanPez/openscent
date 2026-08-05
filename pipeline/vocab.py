#!/usr/bin/env python3
"""
OpenScent — odour vocabulary harvester. Phase 0 groundwork.

    python3 vocab.py corpus       # ON THE HARVEST BOX: all of corpus/raw/ (2,588 patents)
    python3 vocab.py candidates   # anywhere: corpus/extracted/candidates.json only

Method, unchanged from hand-run 04 so the numbers stay comparable: take the words that
immediately precede an odour head noun, strip a generic English/patent stop list, count.
The vocabulary is DERIVED FROM THE CORPUS. Nothing is hand-supplied, which is the whole
point — a hand-written list would smuggle in GoodScents/Leffingwell vocabulary through
the author's memory, and be unauditable.

Hand-run 04 ran this over 60 patents: 1,035 distinct terms, only 14 occurring >=30 times.
Mike's Phase 0 target is 60-100 tags at >=30 molecules each, which that corpus size could
never reach. 2,588 patents is the first time the target is testable.

Output: ontology/harvested-terms-<scope>.tsv — term, count, class.
Class is carried over from ontology/harvested-terms-v0.tsv where a human already judged
it, and left EMPTY otherwise. Filling those in is human work, not the script's.

    D = plausible odour descriptor      -> ontology candidate
    H = hedonic (pleasant/unpleasant)   -> not a descriptor, separate axis
    T = note-tier / positional          -> NOT per-compound assertable (hand-run 04)
    M = malodour context                -> signals a document to exclude
    X = noise                           -> stop list needs extending
"""
from __future__ import annotations
import json, os, pathlib, re, sys, collections

_here = pathlib.Path(__file__).resolve().parent
ROOT  = pathlib.Path(os.environ.get("OPENSCENT_ROOT",
            _here.parent if _here.name == "pipeline" else _here / "openscent"))
RAW   = ROOT / "corpus" / "raw"
ONT   = ROOT / "ontology"

# The head nouns an odour word attaches to. Same set as the extraction filter's ODOUR,
# plus 'aroma'/'scent'/'smell' which appear in descriptive prose but not in that regex.
HEAD = r"(?:odou?rs?|smells?|aromas?|scents?|notes?|characters?|nuances?|impressions?|tonalit(?:y|ies))"

# A descriptor run before the head noun: up to four hyphen/comma-separated words.
# Leading \b is belt-and-braces; this pattern is already anchored by the fixed-width
# word units, and adding it changed nothing in the output (verified, 1,376 terms before
# and after).
#
# NOTE, so it isn't rediscovered: mid-word fragments like `ven in low concentrations` and
# `ol possesses unexpected` came from a THROWAWAY phrase-harvesting experiment, not from
# this file. That experiment used an unanchored `([a-z][a-z\-\s,]{2,60}?)` whose 60-char
# cap forced the engine to start mid-word whenever the head noun sat further away. It was
# abandoned — see the DEVLOG: multiword descriptors belong in the human-written
# odor_terms.tsv, not in a frequency heuristic.
PRE  = re.compile(r"\b((?:[a-z][a-z-]{2,}[,\s]+){1,4})" + HEAD + r"\b", re.I)
# "odour of X, Y and Z" / "notes of X" — the other common shape.
POST = re.compile(HEAD + r"\s+(?:of|like|reminiscent of|recalling)\s+\b([a-z][a-z,\s-]{3,60})", re.I)

STOP = set("""
the a an and or of to in for with without at on by from as is are was were be been being
this that these those it its their his her our your my which who whom whose what when where
have has had having do does did doing will would shall should can could may might must
one two three four five six seven eight nine ten first second third
very more most much many some any all each every both either neither other another
such same different various several certain particular specific general
present invention compound compounds composition compositions mixture mixtures product products
example examples embodiment embodiments claim claims formula formulae accordingly therefore thus
said above below herein wherein whereby further furthermore moreover however although though
also than then there here about into onto upon over under between among during while
new novel known preferred preferably suitable suitably useful used using use provides provide
according relates relating comprises comprising consisting containing contains including includes
obtained prepared produced formed made following described disclosed shown given
amount amounts weight percent parts ratio range ranges total least less more high higher low lower
good better best strong stronger weak long longer short shorter fine
perfume perfumes perfumery fragrance fragrances flavour flavor flavours flavors
material materials substance substances ingredient ingredients agent agents
its it's has have does not non nor no yes may can

# --- extended 2026-08-05, written FROM the >=30 output of the full 2,588-patent run ---
# Not from memory: every entry below was observed ranking above real descriptors. Two
# passes took the >=30 count from 592 to 436 and the unjudged share from 512 to 379.
#
# Intensity and quality modifiers are stopped DELIBERATELY. "strong floral" tells you how
# much; "floral" tells you what. Only the second is a descriptor, and conflating them is
# how an ontology fills up with words that carry no perceptual information.
odor odors odour odours aroma aromas scent scents smell smells smelling odorant odorants
note notes accords organoleptic olfactory olfactive retronasal sensory perceptible perceived
desired desirable improved improve improving enhance enhanced enhancing modify modifying
modified alter altering change changing reduce reducing reduction eliminate release releasing
produce producing providing provide creating create combined added addition additional
include includes including selected showing collecting evaluated evaluation sample samples
method methods means term terms name names article articles structure structures component
components individual respective typical typically especially significantly significant
highly largely slightly initial original existing intrinsic inherent secondary residual
potency distinct unique excellent essential possessing possess thereof control controlled
just but like even only own they well after time off clear main type types
consumer consumers human use used using
detergent detergents fabric fabrics laundry cosmetic cosmetics hair skin food foods
liquid liquids solid solids gas gases oil oils solvent solvents alcohols aldehyde aldehydes
air surface surfaces freshening
natural taste way impart imparts imparting characteristic characteristics chemical similar
complex volatile slight intense intensity strong stronger strongest powerful pronounced
mild faint weak heavy light long-lasting lasting persistent tenacity body overall
perfuming perfume perfumes perfumed fragrance fragrances fragranced flavour flavor
flavours flavors substantivity diffusive diffusion
""".split())

def harvest(texts) -> collections.Counter:
    c = collections.Counter()
    for t in texts:
        for m in PRE.finditer(t):
            for w in re.split(r"[,\s]+", m.group(1)):
                w = w.strip("-").lower()
                if len(w) > 2 and w not in STOP and not w.isdigit():
                    c[w] += 1
        for m in POST.finditer(t):
            for w in re.split(r"[,\s]+|\band\b", m.group(1)):
                w = (w or "").strip("- ").lower()
                if len(w) > 2 and w not in STOP and not w.isdigit():
                    c[w] += 1
    return c

def prior_classes() -> dict:
    """Carry over the human judgements already made in hand-run 04."""
    out = {}
    f = ONT / "harvested-terms-v0.tsv"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            p = line.split("\t")
            if len(p) == 3:
                out[p[0].strip().lower()] = p[2].strip()
    return out

def main() -> int:
    scope = sys.argv[1] if len(sys.argv) > 1 else "candidates"
    if scope == "corpus":
        if not RAW.exists():
            sys.exit(f"no corpus at {RAW} — run this on the box holding corpus/raw/")
        files = sorted(RAW.glob("*.txt"))
        texts = (f.read_text(encoding="utf-8") for f in files)
        label = f"{len(files)} patents"
    else:
        cf = ROOT / "corpus" / "extracted" / "candidates.json"
        rows = json.loads(cf.read_text(encoding="utf-8"))
        texts = (r["sentence"] for r in rows)
        label = f"{len(rows)} candidate sentences"

    counts = harvest(texts)
    prior = prior_classes()
    ONT.mkdir(parents=True, exist_ok=True)
    dest = ONT / f"harvested-terms-{scope}.tsv"

    ge30 = [t for t, n in counts.items() if n >= 30]
    with dest.open("w", encoding="utf-8") as fh:
        fh.write(f"# Odour vocabulary harvested from {label}.\n")
        fh.write("# Method: words immediately preceding an odour head noun, minus a generic\n")
        fh.write("#         English/patent stop list. Corpus-derived, NOT hand-supplied.\n")
        fh.write(f"# {len(counts)} distinct terms; {len(ge30)} occur >=30 times.\n")
        fh.write("# class: D descriptor · H hedonic · T tier · M malodour · X noise · (empty = unjudged)\n")
        fh.write("# Classes for terms seen in hand-run 04 are carried over. New terms are BLANK\n")
        fh.write("# on purpose — judging them is human work.\n#\n# term\tn\tclass\n")
        for t, n in counts.most_common():
            fh.write(f"{t}\t{n}\t{prior.get(t,'')}\n")

    print(f"scope     {scope} ({label})")
    print(f"distinct  {len(counts)}")
    print(f">=30      {len(ge30)}     <- Phase 0 needs 60-100 tags at >=30 molecules each")
    print(f"carried   {sum(1 for t in counts if t in prior)} terms already judged in hand-run 04")
    print(f"unjudged  {sum(1 for t in counts if t not in prior)}")
    print(f"-> {dest}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
