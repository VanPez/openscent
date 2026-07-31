# Hand-run 01 — first contact with patent text

**Date:** 2026-07-31 (late) · **Sample size: 2 patents.** Not a calibration run — a smoke test.
Conclusions below are provisional and n=2 was deliberately chosen to span extremes.

## What was tested

Can patent full text be retrieved without a USPTO API key, and does it contain linkable
(structure → odour) assertions?

Both patents fetched fine from Google Patents as plain text, ~96 KB each, **no API key required**.
Retrieval is not the bottleneck.

---

## Patent A — US3929677A (IFF, 1975) · the Iso E Super family

**Result: rich odour data, but not cleanly linkable.**

Verbatim spans found:

> "PERFUME PROPERTIES Fruity, woody, pineapple-like."
> "This isomer useful in carrying out our invention has a characteristic intense fruity-amber note."
> "clear liquids with intense and persistent unique amber and fruity-amber odors"
> "Peak 1 has a slight buttery note with a strong woody amber character. Peak 2 is weak, low keyed
> with a green vegetable character."

**Two problems, both anticipated in the design doc and both real:**

1. **OCR noise.** The 1975 scan is dirty: `"fruityamber"`, `"iso mer"` split across a line break, and one
   passage garbled into `"amberwillbofskyt Banish and Davis, like fragrance compositions"`. A strict
   verbatim-span rule will reject spans that a human would accept. Either the rule needs a normalisation
   step (collapse whitespace, repair hyphenation) applied *identically* to source and span before
   comparison, or pre-2000 patents need a different tolerance. **The normalisation must be deterministic
   and versioned, or the audit trail breaks.**

2. **Linkage is worse than "Example 3".** The odour is attributed to *isomer mixtures* and to *GC peaks* —
   "Peak 1", "Peak 2", "the specific isomer of our invention". Attaching "woody amber" to one SMILES here
   is not a parsing problem, it is a chemistry judgement about which isomer the perfumer smelled. Many
   rows from old compound patents will be **legitimately unresolvable**, not just hard.

---

## Patent B — US11332693B2 (2022) · woody-ambery composition

**Result: clean text, wrong patent type — but an unexpected and better source.**

Modern text is pristine: no OCR artifacts at all. The problem is that this is a *formulation* patent
(composition claims), not a compound patent. It describes blends and trade-named ingredients, not novel
structures. So the naive plan — "mine patents for Example N → odour" — finds nothing here.

**But it yields something the design doc didn't anticipate.** Formulation patents name commercial
captives *together with their IUPAC name and an odour description*:

> "KARANAL® 2-(2,4-dimethylcyclohex-3-en-1-yl)-5-methyl-5-(1-methylpropyl)-1,3-dioxane, commercially
> available under the trade name KARANAL® is a perfume ingredient that is valued for the dry, radiant,
> woody ambery notes that it brings to fragrance formulations"
>
> "KARANAL® can be broadly categorized as a perfume ingredient exhibiting a warm, ambery, woody odour.
> However, among the ambery, woody class of perfume ingredients KARANAL® has quite unique odour
> qualities. More specifically, it has an unusual characteristic dry, mineral effect, which has also been
> expressed as a sharp, radiant, burning effect."

That is a **trade name + IUPAC name + odour description** triple, in clean text, resolvable to a structure
by OPSIN with no ambiguity. And it describes exactly the class of molecule that has no free descriptor
anywhere — commercial captives.

This may be the more productive vein. Compound patents describe *new* molecules once; formulation patents
describe *established captives* repeatedly, in clean modern text, because they must explain what they are
substituting for.

---

## Revised targeting

| Source type | Text quality | Linkage | Verdict |
|---|---|---|---|
| Pre-2000 compound patents (C11B 9/00) | OCR noise | isomer mixtures, GC peaks — often unresolvable | hard; salvage selectively |
| Post-2001 compound patents (C11B 9/00) | clean | Example N → IUPAC name | **untested — the obvious next test** |
| Formulation patents (A61Q 13/00) | clean | trade name + IUPAC name inline | **unexpectedly good for captives** |

The design doc dismissed A61Q 13/00 as "mostly mixtures". That was wrong, or at least incomplete.

## Next

1. Test a **post-2001 C11B 9/00 compound patent** — the untested cell, and the one the whole plan assumes.
2. Register a **USPTO Open Data Portal API key** (free, data.uspto.gov) — needed for any systematic search.
   Requires an account, so it's Ivan's to create.
3. Decide the normalisation rule for OCR'd text before writing the verifier, not after.
4. Only then the full 20-patent run.

## Caveat

Two patents, chosen to be maximally different. Nothing here is a rate or a yield estimate. The single
firm conclusion is that **retrieval works and the text contains what we hoped** — and that the linkage
problem is real, differently shaped than expected, and needs the sampling to be targeted rather than broad.
