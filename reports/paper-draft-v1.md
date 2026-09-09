# OpenScent: a CC0 structure–odour corpus built by construction rather than by permission

**Draft v1, 2026-09-09.** Written to the four-page scientific-paper budget in
`manuscript-source.md` §11. Markdown, sectioned for the GenesisL1 scientific-paper
template — LaTeX fitting happens in Overleaf.

**Scope decision, provisional:** this is a *dataset and method* paper. Modelling is
represented by one baseline in §4 and otherwise left to GL1F. If M wants the model here,
§4 expands and §5 contracts. Not yet confirmed with him.

~3,300 words including tables.

---

## Structured abstract

**Background.** Machine learning on odour depends on datasets that pair molecular
structures with odour descriptors. The descriptor-labelled sets in common use derive from
GoodScents and Leffingwell; the Leffingwell corpus carries a CC-BY-NC licence with access
restrictions. A non-commercial clause forecloses commercial application, tokenised
derivatives, and independent redistribution — not because the science is disputed, but
because the licence travels with the data.

**Objective.** Build a molecule→odour-descriptor corpus from sources whose licence status
permits unrestricted reuse, and release it CC0 with per-row provenance.

**Method.** Odour assertions are extracted verbatim from two public-domain sources: US
patent full text (US Government work, not subject to copyright) and PubChem's HSDB odour
annotations. Every molecule name and every descriptor must appear as a literal substring of
the sentence it was taken from; this invariant is re-asserted on every run. A human decides
every row against written rules; machine proposals are advisory and never auto-accepted.
Vocabulary admission requires independent attestation across documents, counted at passage
level rather than by occurrence.

**Results.** 5,346 patent documents and 1,018 HSDB rows yield 1,193 distinct molecules
across a 67-term vocabulary, with 20 terms reaching 30 or more molecules. A 648-molecule
subset carrying computed structural descriptors supports supervised prediction of odour
labels — AUC 0.93 for *fatty* and 0.87 for *mint* under five-fold cross-validation —
confirming that the labels carry structure-dependent signal rather than noise.

**Conclusions.** A permissively-licensed odour corpus can be built by construction. It is
smaller than the encumbered alternatives and is reported as such. The method's transferable
content is a set of measurement disciplines and four negative results that constrain what
patent text can be asked to supply.

---

## 1. Introduction

Quantitative structure–odour relationship (QSOR) work needs training data that maps
molecular structures to odour descriptors. In practice the field draws on two commercial
flavour-and-fragrance databases, GoodScents and Leffingwell, or on datasets assembled from
them. The Leffingwell corpus is distributed under CC-BY-NC with access restrictions.

The consequence is not scientific. It is that a non-commercial clause blocks commercial
application, blocks tradeable or tokenised derivatives, and blocks a third party from
redistributing a corrected or extended version. Work built on such data cannot be built on
in turn.

Permissively-licensed alternatives exist but are of a different kind and a different size.
Keller and Vosshall (2016) released psychophysical ratings for 480 molecules under CC0 —
panel ratings on a fixed set of semantic scales, not curated descriptor assignments. It is
a valuable resource and it does not substitute for a descriptor-labelled corpus.

This paper reports an attempt to obtain the missing artefact by construction: to rebuild a
molecule→odour-descriptor corpus from sources that carry no restriction in the first place,
so that the licence question is settled before any row exists rather than negotiated
afterwards.

Two source classes qualify. **US patent full text** is a US Government work and not subject
to copyright; it is also where modern aroma chemicals are described, including captive
molecules documented nowhere else. **PubChem's HSDB annotations** are public domain and
carry a compound identifier, so the link from an odour claim to a structure is exact rather
than inferred from a name.

The corpus that results is smaller than the encumbered alternatives. We report the size
plainly, and argue that a corpus anyone may use commercially and extend is worth more per
row than a larger one that no one may.

---

## 2. Method

Four rules do most of the work. Each is stated below as a rule and as the failure it exists
to prevent, because in each case the failure occurred first.

### 2.1 Extract, never generate

Every molecule name and every descriptor recorded in a row must be a **verbatim substring
of the sentence it came from**. A status tool re-asserts this invariant across the corpus on
every run and refuses to report figures if it is violated.

*The failure it prevents:* a paraphrased or model-generated row is indistinguishable from an
extracted one once it is in the file. Per-row provenance is meaningful only if the recorded
span can be located in the cited source.

A consequence is that text normalisation must be versioned and applied identically to source
text and to extracted spans. A comparison between differently-normalised strings is not a
verbatim check. We discovered this concretely: HTML character entities left undecoded in the
source (`&#39;`) while decoded in the extracted rows silently broke the join between 84
human decisions and the text they were made against.

### 2.2 Measure yield before fetching

Before harvesting a patent classification, a 200-document sample is fetched and the
extraction yield measured. The sample costs roughly twenty minutes. It has changed the
decision three times:

| CPC class | sampled yield (candidates/patent) | decision |
|---|---|---|
| C11B 9/00 (subtree) | 1.02 | fetched — corpus 2,588 → 5,346 documents |
| A23L 27/00 | 0.17 | declined — saved ~7 h fetching for ~280 rows |
| C11D 3/50 | 0.36 | declined |

The C11B 9/00 result came from noticing that the class the corpus had been built from was
only ever harvested at the bare classification symbol; four fifths of its subtree had never
been seen.

**Yield alone is insufficient, and this is the sharper finding.** C11D 3/50 (detergent
perfumery) was sampled because it is where amber and musk descriptors are expected. It
yielded 0.36 candidates per patent — twice the declined food class. But counting *where its
descriptors landed* showed that roughly 70% fell on vocabulary terms already well past the
threshold, and that **sandalwood and animalic, the two terms the class was chosen for, did
not appear at all**. A source can be substantially richer than a rejected one and still
supply nothing that is needed. We now measure both yield and target coverage before
fetching.

### 2.3 Propose-only review against written rules

A human decides every row. Machine proposals are advisory; automatic rejection is disabled.
Blind proposal accuracy, measured by withholding proposals on 30 rows, is **67%** — an
earlier figure of 99.3% was agreement measured after the reviewer had seen the proposal, and
is not accuracy. Errors skew toward rejecting valid rows rather than accepting invalid ones.

The decision rules were written down after a blind evaluation disagreed on 14 of 98 rows and
the disagreements proved not to be noise: they were two unwritten rules applied in opposite
directions on different days. Three rules took the most argument:

- **Mixtures do not yield rows**, including mixtures of stereoisomers of a single compound.
  Enantiomers can smell different — carvone is the standard example — so the odour of a
  50:50 mixture is not the odour of either component.
- **Substance versus source.** A compound named as a comparison ("reminiscent of nitromusk")
  is a reference point and yields nothing; a plant or food named as a smell ("reminiscent of
  peonies") is a descriptor.
- **Negation and comparison invert the claim.** Recording a descriptor from "devoid of the
  lactonic note" asserts the opposite of the source.

### 2.4 Count independent attestations, not occurrences

A vocabulary term is admitted only if it appears in at least 20 distinct documents and
accumulates at least 30 attestations, where an attestation is a **distinct sentence**.

Four successive counters were required, each correcting the previous one's blind spot: raw
occurrences (a term repeated 124 times within one document scored 124), document counts (a
sentence copied across 124 documents scored 124), a per-term boilerplate ratio (which scored
the term rather than the passage carrying it), and finally passage-level counting.

The resulting vocabulary is 67 terms with 119 surface forms. The mapping from surface form
to term is a human-written table: it is the only place where extracted text becomes a
category, and it is auditable line by line.

---

## 3. The corpus

| | |
|---|---|
| Patent documents harvested | 5,346 |
| Documents represented in the review queue | 2,426 |
| Candidate rows | 6,686 |
| Decided by hand | 955 (627 accept, 326 reject, 2 defer) |
| HSDB rows | 1,018 across 651 compound identifiers |
| **Distinct molecules** | **1,193** |
| **Vocabulary terms at ≥30 molecules** | **20 of 67** |

Terms at threshold: *acid, aromatic, citrus, earthy, fatty, floral, fresh, fruity, green,
herbal, lily, mint, musk, musty, powdery, pungent, rose, spicy, sweet, woody.* Five further
terms are within seven molecules (*sandalwood* 28, *amber* 28, *camphoraceous* 27,
*animalic* 23, *aldehydic* 23).

The design target was 60–100 terms at 30 molecules each. **The corpus reaches 20.** The
binding constraint is molecules per term, not vocabulary size (§5.2).

Each row records the source document, the verbatim sentence, the extracted spans, and a
licence basis. Licence is recorded **per row, not per dataset**, so a successful challenge
to one source removes those rows rather than invalidating the corpus.

---

## 4. Structural signal

To test whether the labels carry structure-dependent information, the 651 HSDB compounds
were resolved to structures via their PubChem identifiers, and 22 interpretable descriptors
computed offline with RDKit (molecular weight, log *P*, topological polar surface area,
hydrogen-bond donors and acceptors, rotatable bonds, ring counts, fraction sp³, element
counts, Labute surface area, Bertz complexity). Three compounds failed structure parsing
(hypervalent halogen oxidisers) leaving 648.

Descriptors are computed rather than retrieved. Requesting precomputed properties from a
remote service would make the feature table depend on that service's version of a
descriptor, which is neither reproducible nor auditable.

Gradient-boosted trees, five-fold stratified cross-validation, one binary task per label:

| label | positives | AUC | | label | positives | AUC |
|---|---|---|---|---|---|---|
| chlorine | 18 | 0.943 | | pungent | 186 | 0.751 |
| fatty | 16 | 0.925 | | woody | 10 | 0.739 |
| mint | 24 | 0.874 | | musty | 28 | 0.692 |
| rose | 12 | 0.873 | | spicy | 11 | 0.657 |
| citrus | 11 | 0.862 | | acid | 31 | 0.633 |
| aromatic | 140 | 0.851 | | sweet | 149 | 0.619 |
| fruity | 85 | 0.843 | | | | |
| floral | 39 | 0.820 | | | | |
| green | 12 | 0.799 | | | | |

**Three qualifications belong with this table and should not be separated from it.**
*Chlorine* at 0.943 is trivial — halogen count determines it, and the result serves as a
pipeline check rather than a finding. Labels with 10–12 positives (*citrus*, *rose*,
*woody*, *spicy*) produce unstable cross-validated estimates at this sample size. And
*aromatic* carries a semantic confound: the odour term and the structural property are
distinct concepts that correlate, so part of that score is unearned.

*Fatty* (0.925) and *mint* (0.874) are the substantive results. Chain length and lipophilicity
genuinely track fattiness; mint labels concentrate in a narrow structural family.

The purpose here is negative-control rather than performance: a corpus of *incorrect* labels,
however carefully assembled, would score near 0.5 and would look identical in a spreadsheet.

---

## 5. What the sources cannot supply

Four results that constrain the method. Each is measured.

**5.1 Note tiers are not present in patent text.** Perfumery classifies materials as top,
heart or base notes. Across 60 patents there are **zero** per-compound tier assertions:
patents use those terms to describe accord architecture, never to classify an individual
molecule. A rule fitted to curated tier assignments reproduces them at 56% under
leave-one-out — barely above chance across three classes. Tiers are neither sourceable from
this literature nor recoverable by inference, and were replaced downstream by an honestly
named volatility band.

**5.2 Vocabulary is not the binding constraint; molecules are.** Twenty-nine further
descriptor candidates passed an independence test and were nonetheless refused: the
best-supported reached 8 molecules against a threshold of 30. Admitting them would convert
20-of-67 into 20-of-95 — an unchanged numerator and a worse denominator. Evidence is
retained so the decision is not re-litigated.

**5.3 The pre-1930 literature is redundant rather than merely inconvenient.** Of 30 classic
Parry-era synthetics, 27 already have a PubChem odour row; the apparent misses are naming
artefacts (*heliotropin* is *piperonal*, which is present). Expired-copyright sources were
dropped for redundancy, not for licensing.

**5.4 Sentence scope is the binding extraction constraint.** Three independent observations
converge on it: a heading-matching rule removed for producing rows that name no molecule;
345 sentences carrying descriptors whose compound is named in the *preceding* sentence; and
the single standing recall failure in the evaluation set. Extraction at passage scope, with
a context window, is the identified next step and is not yet built.

---

## 6. Limitations

**Coverage.** 20 of 67 vocabulary terms reach threshold, against a design target of 60–100.

**Structures for one source only.** The patent-derived half has no computed structures yet;
name-to-structure resolution is pending, so §4 covers 648 of 1,193 molecules.

**A weak join between sources.** Molecules are matched across the two sources by name text,
not by structure. `linalool` and `(+)-linalool` remain distinct entries. Structure keys now
exist for the HSDB side only.

**Source character.** HSDB is a hazardous-substances database. Industrial compounds appear
alongside aroma chemicals — which is why *chlorine* is a vocabulary term at all.

**Filter precision.** Whole-queue precision of the candidate filter is approximately 0.2.
A figure of 0.82 appears in earlier project notes and is precision *within the productive
subset*; it must not be read as the filter's precision.

**Corpus redundancy.** A text-containment audit identifies 835 groups covering 1,035
documents — 19.4% — as the same disclosure published more than once, typically an
application and its granted patent. This is an upper bound: the detector's boilerplate
threshold caps detectable group size and admits era-specific house template as evidence, so
702 pairs is the defensible floor. Redundancy does **not** inflate the molecule counts,
which are computed over sets — a second copy of a disclosure contains the same molecules.
It does bear on the document-count criterion for vocabulary admission (§2.4), and that
recount has not been performed.

---

## 7. Availability

Corpus and ontology are released under CC0; the code under Apache-2.0. Every row carries its
source identifier, the verbatim sentence, and a licence basis. All headline figures are
computed by a single tool, so that a number quoted anywhere can be regenerated rather than
remembered.

Repository: `github.com/VanPez/openscent`.

**CC0 waives copyright, not patents.** The corpus is built from patent text; the presence of
a molecule in it says nothing about live patent claims on that molecule or its use.

---

## Figures to produce

1. **Pipeline schematic** — sources → candidate filter → human review → vocabulary → rows →
   features, with the four method rules annotated at the stage each governs.
2. **AUC by label with positive counts on a secondary axis**, so the small-sample caveat is
   visible in the figure rather than only in the caption.

---

## Notes for the co-authors (delete before submission)

- **§4 is provisional.** If the model belongs in GL1F, this section reduces to a pointer and
  the freed space goes to §2 and §5.
- **Authorship and order** unsettled. Mikhail Fedorov proposed the project.
- **Every number re-derived 2026-09-09.** Re-run before submission; several figures moved
  within the last week.
- **Two claims to check with a chemist**, per the call brief: whether the 67-term vocabulary
  is defensible, and whether surface-form mappings such as `sandal` → *sandalwood* are sound.
