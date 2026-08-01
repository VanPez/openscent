# Hand-run 04 — vocabulary harvest and the tier question, settled

**Date:** 2026-08-01 · 60 US patents (C11B 9/00 + A61Q 13/00), 4.64 M characters, 0 fetch failures.

Phase 0 says the ontology comes from *"term frequency over the PD corpus"*. This is that, run for the
first time on real text. Raw output in `ontology/harvested-terms-v0.tsv`.

## Method

Extract every word immediately preceding an odour-head noun (`odour|note|character|aroma|nuance`),
strip a generic English + patent-boilerplate stop list, count. **No vocabulary was supplied** — every
term below came out of the patents.

## Result: the vocabulary is real, the corpus is too small

**1,035 distinct candidate terms. Only 14 occur ≥30 times.**

Mike's Phase 0 target is *60–100 tags, ≥30 molecules each*. At 60 patents we have 14 terms clearing that
bar — and terms-per-corpus grows sub-linearly. Reaching ~80 terms at ≥30 occurrences plausibly needs
**500–1,000 patents**, not 60. That is entirely feasible (the C11B 9/00 US pool alone is 5,660) but it is
a concrete scale requirement that the plan didn't quantify. Phase 0 cannot be completed on a small corpus.

**What did emerge is recognisably perfumery**, which validates the approach:

> floral · muguet · green · fruity · spicy · fatty · woody · fresh · citrus · smoke · sweet · radiant ·
> musk · aromatic · ambery · tobacco · blossom-type · flowery · aldehydic · musky · transparent

`radiant` and `transparent` are notable — those are working perfumer's words, not textbook categories.
They wouldn't appear in a vocabulary someone wrote from first principles.

## Three problems quantified

**Roughly half of the top 60 is still noise** (`profile`, `imparting`, `embodiment`, `accord`, `way`,
`maintains`). The stop list needs another pass. Cheap to fix, but it means the raw counts overstate.

**Hedonic terms are not descriptors.** `unpleasant` (127) and `pleasant` (72) rank 2nd and 6th. They say
whether a smell is liked, not what it smells of. They belong on a separate axis, or nowhere.

**Malodour contamination is large and now measurable.** `toilet` 25, `sweat` 23, `mask` 22, `cooking` 16,
`masking` 12, `urine` 11, `faecal` 12. A61Q 13/00 includes deodorants and malodour counteractants, whose
patents describe smells they are trying to *destroy*. Hand-run 03 flagged this from three sentences; the
frequency data shows it is a substantial share of the class. **Deodorant/malodour subclasses must be
excluded at the query stage**, not filtered later — otherwise the ontology fills with bad smells.

## The tier question: settled, negatively

`base` (89), `top` (80), `middle` (53), `heart` (32), `head` (14), `bottom` (13) all rank high — which
raised a real possibility: if patents assert *"compound X is a top note"*, then note tiers become citable
evidence rather than Ivan's unverifiable judgement.

Tested directly across all 60 patents:

- **Direct per-compound tier assertions ("X is a base note"): 0**
- Tier-with-examples enumerations: 2, and both generic — *"Heart note such as floral characters"*,
  *"base note such as musks"*

Patents use tier language to describe **accord architecture**, never to classify an individual molecule.

**So tiers are not recoverable from the patent corpus.** That is now the second independent line of
evidence, after the fitted rule reproducing the existing 99 at only 56% leave-one-out. The note tier is a
judgement, it cannot be sourced or computed, and if it is published it must be labelled as the
maintainer's classification. Worth telling Mike — it answers one of the three open questions from the
proposal without needing his input.

## Next

1. Extend the stop list; re-harvest. Cheap.
2. Exclude deodorant/malodour subclasses at query time.
3. Scale the harvest to 500–1,000 patents to make Phase 0 completable — that is the real prerequisite,
   and it is a compute/time cost rather than an unsolved problem.
4. Only then draft the 60–100 tag ontology and the `surface form → tag` mapping table.
