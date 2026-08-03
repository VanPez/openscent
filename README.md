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

## Where it actually stands (2026-08-02)

**Patent corpus collected.** 2,588 US patents (CPC C11B 9/00 + A61Q 13/00, priority 2001+), fetched
clean: zero failures, zero short-document rejects, 173 MB. Extraction over 992,396 sentences yields
**3,191 candidate assertions** across 1,027 patents.

**Second source built.** PubChem's `Odor` annotations — 2,358 records → **1,453 usable CIDs**. Its value
is that PubChem returns the compound ID directly, so the patent pipeline's most dangerous failure (an
accurate odour description bound to the *wrong* molecule) cannot occur there. See
`reports/pubchem-source.md`.

**The accuracy number does not exist yet, and that is the current blocker.** The extraction filter scores
1.00/1.00 on `pipeline/testset.jsonl`, and that figure is worthless: every rule was written while looking
at those 29 sentences, and when the filter disagreed with a label, the label moved. `pipeline/TESTSET.md`
says so directly. `pipeline/heldout.py` draws a blind, stratified set from patents never used for tuning —
including sentences the filter *rejected*, so recall can be measured rather than assumed. Until that is
labelled and scored once, every downstream number is provisional.

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
