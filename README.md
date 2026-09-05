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
| **Corpus** | molecule → odour-tag assertions, each backed by a verbatim quote from a public-domain source | **collection done, tagging not started** |
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
(aroma-index) turned out to be model-generated with no traceable provenance.

So the pipeline separates three jobs: a model **locates** character spans, deterministic code **verifies**
they are verbatim, and a human-written lookup table **maps** span text to a tag. The model supplies
coordinates, never vocabulary.

Verification is a hard `assert`, not a review habit — see `named()` and the verbatim check in
`pipeline/harvest.py`. It has caught two real defects so far, both of which a reading pass had waved
through.

See `reports/phase0-1-pipeline.md` for the full design and the provenance schema.

---

## Where it actually stands (2026-08-03)

**Patent corpus collected.** 2,588 US patents (CPC C11B 9/00 + A61Q 13/00, priority 2001+), fetched
clean: zero failures, zero short-document rejects, 173 MB. Extraction over 992,396 sentences yields
**4,068 candidate assertions** across ~1,100 patents.

**Second source built.** PubChem's `Odor` annotations — 2,358 records → **1,453 usable CIDs**. Its value
is that PubChem returns the compound ID directly, so the patent pipeline's most dangerous failure (an
accurate odour description bound to the *wrong* molecule) cannot occur there. See
`reports/pubchem-source.md`.

**Measured accuracy: precision 0.16, recall 1.00.** 50 sentences from patents never used for tuning,
drawn blind, labelled by hand, scored once (`pipeline/heldout.py`). The same filter scores 1.00/1.00 on
its own tuning set — that figure is memorisation and should never be quoted. Recall is a floor rather than
an estimate: 25 rejected sentences were sampled and none should have been kept, which is consistent with
few misses but does not prove it.

**What 0.16 means in practice.** The filter is a deliberately wide sieve; precision is the *review cost*,
not a correctness claim. ~650 of the 4,068 candidates are expected to survive human review — inside the
original 600–1,000 molecule projection — but a human reads 4,068 sentences to get there. Two failure modes
account for it: definitional claim language (15 of 21 false positives) and descriptor-only headings, which
structurally cannot name a molecule and so can never yield a row at sentence scope.

**Then, in order:** ontology derivation over the full corpus → OPSIN name→structure linkage →
copyright-notice scan → tagging.

### Measured findings worth knowing

- **Yield is lower than assumed.** ≈0.2 clean assertions per patent at the v0 filter, against the 1–3
  guessed from hand-picked examples. Projects to a **600–1,000 molecule** corpus — not Leffingwell's
  3,500, but the largest anyone can use commercially, which is the point.
- **Note tiers are neither sourceable nor computable.** Across 60 patents there are **zero** per-compound
  tier assertions; patents use top/heart/base for accord architecture, never to classify a molecule. A
  fitted rule reproduces curated tiers at 56% under leave-one-out. The sister project replaced them with
  an honestly-named `volatility_band`.
- **Phase 0 needs scale.** 60 patents give 1,035 distinct terms but only 14 occurring ≥30 times. A
  60–100 tag ontology at ≥30 molecules per tag needs 500–1,000 patents; the corpus now has 2,588.
- **Deodorant subclasses must be excluded at query time.** A61Q 13/00 includes patents describing smells
  they intend to destroy — malodour terms otherwise dominate the harvested vocabulary.

---

## Sources

| Source | Licence basis | Role | Status |
|---|---|---|---|
| USPTO patent full text | US Government work — no copyright | modern aroma chemicals, incl. captives documented nowhere else | **collected, 2,588 docs** |
| PubChem `Odor` (HSDB) | US Government work — public domain | common molecules, CID given so linkage is exact | **collected, 1,453 CIDs** |
| PubChem / FEMA GRAS | public domain / identifiers | CID·CAS·SMILES backbone; FEMA number as a selection layer | in use |
| Keller & Vosshall 2016 | CC0 | 480 molecules, calibrated human ratings | not yet ingested |
| Parry, Piesse (pre-1930) | expired copyright | historical materials | **checked and dropped** — see below |

**Nothing GoodScents- or Leffingwell-derived touches any phase.** Licence is recorded per row, not per
dataset, so a challenge to one source removes those rows rather than the corpus.

**On the pre-1930 literature:** dropped for redundancy, not licensing. Of 30 classic Parry-era synthetics,
**27 already have a PubChem odour row**, and the misses are naming artefacts (*heliotropin* is *piperonal*,
which is present). The scans are also poor — archive.org reports 24% of words below OCR confidence 30 —
and Piesse describes plant *materials* that never resolve to a structure. Full reasoning in the appendix of
`reports/pubchem-source.md`. Worth revisiting only if the ontology turns out vocabulary-starved.

---

## Layout

```
openscent/
  corpus/
    patent-ids.json   2,588 discovered ids — expensive to rebuild, deliberately committed
    raw/              source documents as retrieved (gitignored: 173 MB)
    raw-pubchem/      PubChem annotation pages, committed so rows are checkable offline
    extracted/        candidate assertions + provenance, pre-tagging
  ontology/           the tag vocabulary + odor_terms.tsv (surface form -> tag)
  pipeline/           harvest.py · pubchem.py · score.py · heldout.py + test sets
  reports/            design docs, hand-run findings, source analyses
  DEVLOG.md           work log, newest at the bottom. START HERE.
```

## Running it

```bash
python3 pipeline/harvest.py status     # what is cached, what remains
python3 pipeline/harvest.py extract    # offline, re-runnable as the filter changes
python3 pipeline/score.py              # filter vs the (overfit) tuning set
python3 pipeline/pubchem.py fetch      # second source; polite, cached, resumable
python3 pipeline/heldout.py sample     # draw the blind evaluation set
```

`fetch` and `extract` are deliberately separate: the filter is not finished, and improving a regex must
never require re-downloading 2,588 documents.

The harvest host is referred to as `$OPENSCENT_HOST` throughout; set it in your shell.

## Related

- **aroma-index** — the curated index and pilot mint (99 curated + 218 licence-clean sourced molecules).
  Separate project, shares the licence discipline. Its `reports/license-scan.md` is the evidence base for
  why OpenScent exists.

## Licence

Two licences, split by what the file is:

| | Licence | Covers |
|---|---|---|
| **Data** | [CC0 1.0](LICENSE) | `corpus/`, `ontology/`, and every dataset derived from them |
| **Code** | [Apache-2.0](LICENSE-CODE) | `pipeline/` and all other source |

CC0 on the data is the whole point — no non-commercial clause, no share-alike, nothing
that blocks a commercial or tradeable derivative. Apache-2.0 on the code because CC0
addresses copyright but is silent on patents and warranty, which is what a company's
legal review actually asks about code.

Licence basis is recorded **per row, not per file**, so any row can be audited back to a
source that carries no copyright restriction (US patent full text; PubChem/HSDB). Rows
that cannot clear that bar are marked `excluded` with a reason and kept in place rather
than deleted — see `pipeline/triage_pubchem.py`.

**CC0 waives copyright, not patents.** This corpus is built from patent text. A molecule
appearing here says nothing about whether making, using or selling it infringes a live
claim. That question is separate and stays with the user.
