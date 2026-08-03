# PubChem as a second source — what it fixes, and the one thing it doesn't

**Date:** 2026-08-01 · Script: `pipeline/pubchem.py` · Output: `corpus/extracted/pubchem-candidates.json`

Built while the 2,588-patent fetch ran. Deliberately independent of it: different endpoint, different
host, runs on the Mac, cannot interfere with the Hetzner job.

## What it fixes: linkage, entirely

The patent pipeline's most dangerous failure is not a missed sentence, it is **"Example 3" resolving to
the wrong structure** — an accurate odour description bound to the wrong molecule, which looks exactly
like a valid row. That's why OPSIN is a gated stage.

PubChem returns `LinkedRecords.CID` with every annotation. The molecule is stated, not inferred.
**There is no linkage stage for this source and therefore no linkage error.** Rows where PubChem gives
more than one CID are dropped rather than guessed (`cid_ambiguous`), because a two-CID annotation is
precisely the ambiguity we refuse to resolve silently.

## What it does not fix: the statement's provenance

`../aroma-index/reports/license-scan.md` records the `Odor` heading as ✅ public domain, on the grounds
that 2,356 of 2,358 annotations come from HSDB, a US National Library of Medicine work. That reasoning
is correct **about the database** and incomplete **about the sentences in it**.

The first record this endpoint returns:

```
SourceName: Hazardous Substances Data Bank (HSDB)
LicenseURL: https://www.nlm.nih.gov/web_policies.html
Value:      "HAS ODOR OF HYDROGEN SULFIDE IN MOIST AIR"
Reference:  Budavari, S. (ed.). The Merck Index — An Encyclopedia of Chemicals,
            Drugs, and Biologicals. Merck and Co., Inc., 1996., p. 1511
```

HSDB is a US Government work. *The Merck Index* is a copyrighted book. HSDB summarising Merck does not
make Merck's content public domain, and a PD wrapper around a copyrighted assertion is the same
laundering pattern the project exists to avoid — it is `quotes_source` from hand-run 02 arriving through
a different door.

**This does not rule the source out.** A short factual statement of what a chemical smells like is thin
copyright ground, and much of HSDB is original summary. It does mean the licence claim cannot be made at
the *heading* level. So every row carries:

| field | meaning |
|---|---|
| `references` | the cited works, verbatim, never dropped |
| `quotes_source` | true if the annotation cites anything at all |
| `reference_may_be_copyrighted` | heuristic: a known publisher appears in the citation |
| `reference_flag_hits` | which publisher strings matched, so the call is checkable |
| `source_name` / `license_url` | per row, never assumed from the heading |

`reference_may_be_copyrighted` is **a prompt for review, not a legal finding.** The publisher list is
over-broad on purpose — a false flag costs a human glance, a missed one costs the licence claim — and
false negatives are still possible, because a citation can name a copyrighted work in a form the list
doesn't contain.

## The FEMA layer, and why it's only a layer

The `Odor` heading is a **toxicology** field, and taken whole its vocabulary runs to *pungent*, *acrid*,
*rotten eggs* — nickel carbonyl, dioxane and nitrogen trifluoride all carry odour annotations. The FEMA
join (heading `FEMA Number`, ~2,389 CIDs per the scan) is a cheap, objective selection criterion that
separates established flavour ingredients from industrial chemicals: `fema_listed` is true where the CID
carries a FEMA number.

**Correction (see the Parry check below): "toxicological, not perfumery" is true of the corpus as a whole
and false of the aroma subset**, which is the part anyone would actually use. Sampled from the FEMA-listed
rows: *"Sweet rose odor"* (geraniol), *"Heliotrope odor"* (piperonal), *"Odor similar to that of bergamot
oil and French lavender"* (linalool), *"warm, woody, floral … with balsamic and sweet tone"* (ionone).
That is perfumery register. The vocabulary problem is real at the corpus level and dissolves once
`fema_listed` is applied — which is the argument for having built the join.

**The field is named for what it records, not what it implies**, and it is deliberately not called
`food_grade`: a FEMA number is an industry association's GRAS designation, not a safety certification
and not a curated list of perfumery materials. Acetone is FEMA 3326.

**It is also asymmetric, which is the part that matters.** Presence suggests an aroma molecule; absence
implies nothing at all. Flavour and fragrance are largely the same chemistry — most of what we call
flavour is retronasal olfaction, so vanillin, limonene and linalool are both at once — but the fragrance
side extends well beyond anything edible. Iso E Super, Hedione and the musks will never carry a FEMA
number and are no less odorants for it. **Never filter on this field.** It is metadata for ranking
review effort, not a gate.

**Only the number is taken.** FEMA's flavor-library prose is proprietary and is never fetched. A FEMA
number is an identifier — a fact — and "has a FEMA number" is an objective criterion, not an authored
compilation, which is the same reasoning the licence scan used to call this list clean.

Note from the raw data: some FEMA records (e.g. ACACIA GUM) carry no CID at all, because they are
materials rather than single compounds. Those simply don't join.

## Exclusions

Three, each because the field is toxicological rather than descriptive:

- `absence-of-odour` — *Odorless*, *none*. A true statement, not a descriptor.
- `threshold/metric` — detection thresholds and ppm values. Same class of error as *odour value* in the
  patent filter.
- `no-data placeholder` — *not available*, *not reported*.

## Results — run 2026-08-01

**2,358 odour annotations, matching the licence scan's count exactly.** The endpoint has not drifted.

```
rows 3135 → excluded 903 (odourless / thresholds / placeholders)
          → dropped   150 (more than one CID — refused rather than guessed)
          → kept     2082  across 1453 distinct CIDs
```

1,148 kept rows (55%) cite a possibly-copyrighted work, overwhelmingly Merck Index / Budavari.

## The citation is not the risk — the span length is. I had this wrong first time.

The first version of this report treated a flagged citation as disqualifying and reported the usable
set as *"~800 CIDs with unflagged provenance, 83 of them food-grade."* **That was over-cautious and the
data contradicts it.** Recorded rather than quietly edited, per the TESTSET.md precedent.

Copyright protects **expression, not facts**. A statement of what a chemical smells like is a fact;
"fragrant and penetrating odor" is additionally a **short phrase**, and where there are only a few ways
to express an idea, expression merges with the idea and there is nothing left to protect. HSDB citing
Merck is a peer-reviewed government database following scientific attribution norms — it is not
reproduction of Merck's prose. *Cites a copyrighted work* and *copies protected expression* are
different propositions, and conflating them would have discarded 1,148 good rows.

Measured over the flagged rows:

| words in span | flagged rows | share |
|---|---|---|
| ≤ 5 | 1004 | 87% |
| ≤ 10 | 1109 | 97% |
| ≤ 20 | 1146 | 100% |

Median 3 words. Mean 3.5. Maximum 22.

**Where it does become real** is the tail, because length brings creativity with it:

```
20w  BENZYL ACETATE — "Powerful but thin, sweet floral fresh, fresh and light, fruity
     odor reminiscent of Jasmin, Gardenia, Muguet, Lily and other flowers"
     cited to: Merck Index 1996, p.189
```

That is not a fact statement, it is authored prose in the register of Arctander. Somebody wrote it.

So rows carry `word_count` and `expression_risk`, which is `review` only when a flagged citation
coincides with a span over 10 words:

```
kept rows            2082   (1453 CIDs)
expression_risk low  2043
needs hand review      39   (27 of them FEMA-listed)
FEMA-listed rows      521   ( 277 CIDs)
```

**39 rows to read by hand**, not 1,148 to discard. Not legal advice — a triage field, and the threshold
is a judgement that should be argued with rather than trusted.

## What this is worth

Usable: **1,453 CIDs**, of which 277 are FEMA-listed established flavour ingredients, with 39 rows parked
for review. Zero linkage risk and a machine-readable licence pointer per row.

The remaining honest caveat is coverage, not vocabulary and not licensing: this source is strong on
century-old commodity aroma chemicals and silent on anything modern. Best used as (a) a **cross-check**
on patent-derived rows for the same CID — two independent sources agreeing is real evidence — and (b)
coverage of common molecules the patent literature has no reason to describe, because nobody patents
vanillin.

**Patents remain the main event**, and this source does nothing for the 37 captives.

---

## Appendix — why Parry and Piesse were checked and dropped (2026-08-01)

The obvious third source is the pre-1929 perfumery literature: Piesse, *The Art of Perfumery* (1857) and
Parry, *The Chemistry of Essential Oils and Artificial Perfumes* (vol. 1, London 1918). Both are
unambiguously public domain — archive.org gives Parry vol. 1 as `chemistryofessen01parruoft`,
`possible-copyright-status: NOT_IN_COPYRIGHT`, full text as a 1.6 MB `djvu.txt`, no key, no barrier.

**Dropped for redundancy, measured rather than assumed.** Of 30 classic Parry-era synthetics — the
molecules vol. 2 is actually about — **27 already have a PubChem odour row**, and the three misses are
naming artefacts (HELIOTROPIN is the period name for PIPERONAL, which is present). Parry was writing
about precisely the compounds that are now century-old commodity chemicals, i.e. the population a
toxicology database covers thoroughly. He sits entirely inside PubChem's coverage.

Two further strikes, either sufficient on its own:

- **OCR quality is measurably poor, and archive.org publishes the numbers.** For that scan (ABBYY
  FineReader 8.0 on 1918 print): **24% of words at confidence ≤30, only 7% above 80.** Materially worse
  than the pre-2000 patent scans that handrun-01 already found problematic. A verbatim span that is
  verbatim *of a mis-OCR'd word* satisfies the assert and is still worthless.
- **Linkage regresses.** Piesse describes materials — rose otto, patchouli, civet — which do not resolve
  to a CID at all. Parry's period names (*heliotropine*, *musk xylol*) need a hand-written synonym table,
  reintroducing exactly the linkage risk PubChem eliminates.

**What would revive it:** only a vocabulary-starved ontology. 1918 perfumery prose is richer per sentence
than anything in HSDB, so if Phase 0 cannot reach 60–100 tags at ≥30 molecules each from patents alone,
Parry vol. 2 is the place to look for *terms* — never for coverage, and never for linkable rows.

It does nothing for the 37 captives. Nothing published in 1918 could.

It does **not** address the 37 captives. Those are recent commercial materials; they are in the patents or
nowhere.
