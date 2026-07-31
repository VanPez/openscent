# OpenScent

**A permissively-licensed odour corpus, and an on-chain model trained on it.**

Every published structure–odour dataset of any size is encumbered. The standard QSOR training set is
assembled from GoodScents and Leffingwell; the Leffingwell corpus is CC-BY-NC and its files are now
access-restricted behind a non-commercial condition. That licence blocks commercial use, blocks tradeable
tokens, and — more importantly — blocks anyone else from building on the work.

OpenScent builds the corpus from scratch out of sources that carry no such restriction, publishes it CC0
with per-row provenance, and uses it to train a structure–odour model that runs verifiably on GenesisL1.

Three artifacts, one build:

| | What | Status |
|---|---|---|
| **Corpus** | molecule → odour-tag assertions, each backed by a verbatim quote from a public-domain source | design |
| **Model** | one-vs-rest GBDT per tag (GL1F), inference by `eth_call`, no state change | not started |
| **Paper** | first permissively-licensed odour corpus; verifiable SMILES→prediction path | not started |

Proposed by Mikhail Fedorov (GenesisL1) 2026-07-31. Built by vanpe.

---

## The rule everything depends on

> **Extract, never generate.** A model may only return text that appears verbatim in a source document.
> It never writes an odour word that isn't already there.

An LLM asked to *describe* a molecule's smell answers from training data that includes GoodScents and
Leffingwell — so the output is contaminated even when the input is public domain, and the contamination is
unauditable. This is not hypothetical: it is exactly how the descriptors in the sister project
(`../aroma-index`) turned out to be model-generated with no traceable provenance.

So the pipeline separates three jobs: a model **locates** character spans, deterministic code **verifies**
they are verbatim, and a human-written lookup table **maps** span text to a tag. The model supplies
coordinates, never vocabulary.

See `reports/phase0-1-pipeline.md` for the full design, the provenance schema, and the USPTO mining plan.

---

## Sources

| Source | Licence basis | Role |
|---|---|---|
| USPTO patent full text | US Government work — no copyright | modern aroma chemicals, incl. captives documented nowhere else |
| Parry, Piesse, Askinson (pre-1930) | expired copyright | historical naturals and classical materials |
| Keller & Vosshall 2016 | CC0 | 480 molecules, calibrated human ratings |
| PubChem / EU / FEMA GRAS | public domain / identifiers | CID·CAS·SMILES backbone |

**Nothing GoodScents- or Leffingwell-derived touches any phase.** Licence is recorded per row, not per
dataset, so a challenge to one source removes those rows rather than the corpus.

## Layout

```
openscent/
  corpus/
    raw/         source documents as retrieved (patents, OCR text)
    extracted/   verified verbatim spans + provenance, pre-tagging
    staging/     intermediate batches
  ontology/      the tag vocabulary + odor_terms.tsv (surface form -> tag)
  pipeline/      extraction, verification, name->structure resolution
  reports/       design docs and findings
  notebooks/     exploration
```

## Status

Nothing built yet. Next step is the 20-patent hand-run described at the end of
`reports/phase0-1-pipeline.md` — it calibrates linkage accuracy and yield before any infrastructure gets
written.

## Related

- `../aroma-index` — the curated index and pilot mint (99 curated + 218 licence-clean sourced molecules).
  Separate project, shares the licence discipline. Its `reports/license-scan.md` is the evidence base for
  why OpenScent exists.
- `../INFRA.md` — validator and L1 tooling reference.
