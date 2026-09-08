# OpenScent — manuscript source

**Not a manuscript. The material for one, format-agnostic.**

Assembled 2026-09-08 after Joe asked for the work to be documented in a GenesisL1
community publication template.

**TARGET, confirmed by Joe 2026-09-08: the SCIENTIFIC PAPER template (two-column) from
`JoMfN/genesisl1-community-publication-templates`, condensed to FOUR PAGES**, processed in
Overleaf. "4p" is four pages, not a format name — *"if you have 18 pages and want to sober
it up to 4"*. He is explicit that it is guidance, not obligation: *"only a template and
only to guide you in making this study ready to publish it anywhere."*

**So this file is the quarry, not the draft.** Four pages two-column is roughly
3,000–3,500 words including figures and tables; everything below would run eight to ten.
The manuscript is made by CUTTING this, and §11 records what survives.

**Every figure here came from `pipeline/status.py` or a named script on 2026-09-08.**
Do not copy a number out of this file into a manuscript without re-running it — the whole
project exists because numbers copied forward are numbers unverified (DEVLOG 2026-09-05).

---

## 1. The claim, in one paragraph

Every structure–odour dataset of usable size is licence-encumbered. The standard QSOR
training set is assembled from GoodScents and Leffingwell; the Leffingwell corpus is
CC-BY-NC with access restrictions. That blocks commercial use, blocks tradeable tokens,
and blocks anyone from building on the work. OpenScent rebuilds a molecule→odour corpus
from sources that carry no such restriction — US patent full text (US Government work, no
copyright) and PubChem's HSDB odour annotations (public domain) — publishes it CC0 with
per-row provenance, and uses it to train a structure–odour model that runs verifiably
on GenesisL1.

**This is the "engagement introduction" Joe asked for.** The hook is not "we made a
dataset". It is: *the field's shared training data cannot legally be built on, and that
is fixable by construction rather than by negotiation.*

---

## 2. Where it stands (2026-09-08, from `status.py`)

```
5,346 patent documents · 2,426 distinct documents represented in the review queue
6,686 candidate rows · 955 decided (627 approve, 326 reject, 2 skip) · 5,731 undecided
1,018 live PubChem rows from 651 distinct CIDs

patents    15 of 67 tags at the bar     541 molecules
pubchem     6 of 67                     653 molecules
COMBINED   20 of 67 tags at >=30 molecules · 1,193 distinct molecules

ontology: 67 tags, 119 surface forms
verbatim invariant: clean
```

Target (Mikhail Fedorov's, at proposal): 60–100 tags at ≥30 molecules each. **We are at
20.** Five tags are within seven molecules: sandalwood 28, amber 28, camphoraceous 27,
animalic 23, aldehydic 23.

Project span: first commit 2026-07-31, 69 commits, ~6 weeks.

---

## 3. Method — what actually distinguishes this

Four rules do the work. Each is stated as a rule, then as the failure it prevents.

### 3.1 Extract, never generate

Every molecule name and every descriptor must be a **verbatim substring of the sentence it
came from**. `status.py` re-asserts this on every run and refuses to report if violated.

*Why:* a generated or paraphrased row is indistinguishable from an extracted one once it is
in the corpus. The invariant is what makes per-row provenance meaningful rather than
decorative.

*Consequence:* normalisation is versioned (`norm/2`) and applied identically to source text
and to extracted spans, because a comparison between differently-normalised strings is not
a verbatim check.

### 3.2 Measure yield before fetching

Sampling a CPC class costs ~20 minutes. It has changed the decision three times:

| class | sampled yield | decision |
|---|---|---|
| C11B 9/00 `/low` | 1.02 candidates/patent | fetched — **doubled the corpus**, 2,588 → 5,346 |
| A23L 27/00 | 0.17 | declined — saved ~7 h for ~280 rows |
| C11D 3/50 | 0.36 (0.29× the corpus) | declined 2026-09-07 |

The C11B 9/00 result came from noticing that the class the corpus was *already built from*
had only ever been harvested at the bare CPC symbol; the `/low` subtree was four-fifths
unseen.

**And yield alone is insufficient.** C11D 3/50 was chosen because detergent perfumery is
where amber and musk descriptors live. Counting where its descriptors actually landed:
~70% fell on tags already past the bar, and **sandalwood and animalic — the tags it was
chosen for — did not appear at all**. A class can be twice as rich as a declined one and
still buy nothing.

### 3.3 Propose-only review, with written rules

A human decides every row. Machine proposals are advisory; auto-reject is off.

Blind accuracy of the proposals, measured 2026-09-04 by withholding them on 30 rows:
**67%**. An earlier 99.3% figure was agreement-after-anchoring and is not accuracy.

`REVIEW-RULES.md` was written 2026-08-25 after a blind evaluation disagreed on 14 of 98
rows — and the disagreements were not noise. They were two unwritten rules applied in
opposite directions. Written rules are the only defence against a corpus that means
slightly different things in different weeks.

The rules that took the most argument:

- **The mixture rule.** If an odour is attributed to a mixture there is no row — including
  a mixture of stereoisomers of one compound. Enantiomers can smell different (carvone is
  the textbook case), so a 50:50 mixture's odour is not either one's odour.
- **Substance vs source.** "Reminiscent of nitromusk" gives nothing; "reminiscent of
  peonies" gives `peony`. A compound named as a comparison is a reference point; a plant
  or food named as a smell is a descriptor.
- **Negation and comparison invert.** "Devoid of the lactonic note" asserts the opposite
  of what capturing it would record.

### 3.4 Count independent attestations, not occurrences

Vocabulary admission requires `docs >= 20` **and** `attestations >= 30`, where an
attestation is a *distinct sentence*.

Four successive counters were needed to get this right, each fixing the last one's blind
spot: occurrences (a term repeated 124× in one patent scored 124), documents (a sentence
copied across 124 patents scored 124), boilerplate (scored the term, not the passage), and
finally the passage-level counter in `attest.py`.

---

## 4. Results

### 4.1 The corpus

1,193 distinct molecules, 20 tags at ≥30 molecules, CC0, per-row provenance. Not
Leffingwell's ~3,500 — but the largest that can be used commercially, which is the point.

### 4.2 The feature table (2026-09-08)

`reports/openscent-pubchem.csv` — 648 molecules × 40 numeric columns: 22 RDKit descriptors
computed offline from PubChem structures, 15 binary tag columns, `n_tags`,
`primary_tag_id`. Zero missing cells.

**Structure predicts odour on it.** 5-fold stratified CV, AUC:

| tag | n | AUC | | tag | n | AUC |
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

**Three caveats that must travel with that table:**

1. `chlorine` 0.94 is trivial — halogen count gives it away. A pipeline check, not a result.
2. `citrus`, `rose`, `woody`, `spicy` have 10–12 positives. Five-fold AUC is unstable there.
3. `aromatic` 0.85 has a semantic confound: the odour tag and the chemical property are
   different concepts that correlate.

`fatty` 0.925 and `mint` 0.874 are the honest results.

---

## 5. Negative results — the most publishable part

A method paper's value is often what it rules out. These are measured, not argued.

- **Note tiers (top/heart/base) are neither sourceable nor computable.** Across 60 patents:
  **zero** per-compound tier assertions. Patents use those terms for accord architecture,
  never to classify a molecule. A fitted rule reproduces curated tiers at 56% under
  leave-one-out — barely above chance on three classes.
- **Vocabulary is not the binding constraint; molecules are.** 29 further descriptor
  candidates passed an independence test and were still refused: the best reaches 8
  molecules against a bar of 30. Admitting them converts 20-of-67 into 20-of-95 — same
  numerator, worse denominator.
- **The pre-1930 literature is redundant, not merely awkward.** Of 30 classic Parry-era
  synthetics, 27 already have a PubChem odour row; the misses are naming artefacts
  (*heliotropin* is *piperonal*, which is present). Dropped for redundancy, not licensing.
- **Deodorant subclasses poison the vocabulary.** A61Q 13/00 includes patents describing
  smells they intend to destroy; malodour terms otherwise dominate the harvest.
- **Sentence scope is the binding extraction constraint.** Three independent findings point
  at it: the HEADING rule's removal (2026-08-03), 345 sentences that carry descriptors while
  the molecule sits in the *previous* sentence (2026-09-07), and the single standing recall
  failure in the test set. A passage-scope extractor does not exist yet.

---

## 6. Corpus quality: what an audit found

Reported because a corpus paper that does not audit itself is not credible.

- **19.4% of documents are redundant** (835 groups, 1,035 documents) — the same disclosure
  published twice, application and grant. Detected by text containment, not by family id.
  **Upper bound**: the detector's boilerplate threshold caps detectable group size at 5 and
  lets 1970s-80s house template through; 702 pairs is the defensible floor.
- **This does not inflate the molecule counts.** `status.py` counts distinct molecules in
  sets, and a second copy of a disclosure contains the same molecules. Collapsing duplicates
  correctly costs 10 molecules and no tags.
- **It does threaten the vocabulary**, because `docs >= 20` treats documents as independent
  attestations. **Not yet re-measured.** Stated as an open exposure rather than resolved.
- **56 sentences appear more than once within a single document** — patents restate a
  sentence in summary and again in examples.

---

## 7. Limitations, stated plainly

- 20 of 67 tags, against a 60–100 target. The corpus is roughly a third of the way.
- The patent half has no structures yet — OPSIN name→structure linkage is not run, so the
  feature table covers PubChem only (648 of 1,193 molecules).
- The molecule join between the two sources matches on **name text**, not structure.
  `linalool` and `(+)-linalool` remain separate. InChIKeys now exist for the PubChem side
  only.
- HSDB is a *safety* database: industrial compounds sit beside aroma chemicals, which is why
  `chlorine` is a tag.
- Proposal accuracy is 67%, and errors skew toward rejecting good rows rather than accepting
  bad ones — a recall problem, not a precision one.
- Whole-queue filter precision is ~0.2. The 0.82 figure that appears in older notes is
  precision *within the productive subset* and must never be quoted as the filter's.

---

## 8. Reproducibility

- Every row carries source id, the verbatim sentence, and a licence basis. A challenge to
  one source removes those rows, not the corpus.
- `status.py` is the single place any headline number is computed. It exists because the
  same question asked three times in ten minutes gave 20, 11 and 15 tags.
- Features are computed offline by RDKit from published structures — never fetched as
  precomputed descriptors, so the table does not depend on a remote service's version.
- Code and data: `github.com/VanPez/openscent`, CC0 for data, Apache-2.0 for code.

---

## 9. Figures worth making

1. **Pipeline schematic** — sources → filter → human review → ontology → rows → features.
   The four rules annotated where they apply.
2. **Tags at the bar over time** — 12 (20 Aug) → 20 (8 Sept), with the corpus doubling
   marked. Honest about the plateau.
3. **Yield-before-fetch table** — the three sampled classes and their decisions. This is the
   method's clearest single illustration.
4. **AUC by tag** with positive counts on the same axis, so the small-n caveat is visible
   rather than written underneath.

---

## 10. Still open

1. ~~Which format~~ — **answered: scientific paper, four pages.**
2. **Does this coordinate with M's `GL1F.pdf`?** He is drafting one for ledger submission.
   If OpenScent is the dataset in that story, the two documents should reference each other
   rather than overlap. **Ask before writing the results section**, since it decides whether
   the model belongs here or there.
3. **Authorship and attribution** — Mikhail Fedorov proposed the project; Ivan built it.
   Needs settling before submission anywhere.

---

## 11. The four-page cut

A budget, not a wish. Two-column, ~3,300 words total including captions.

| § | Content | Words | Source above |
|---|---|---|---|
| Abstract | structured; the licensing claim, the corpus size, the AUC result, the honest limit | 200 | §1, §2, §4 |
| 1. Introduction | encumbered training data blocks commercial use, tokens, and downstream work; fixable by construction | 450 | §1 |
| 2. Method | the four rules, one paragraph each, each stated as the failure it prevents | 900 | §3 |
| 3. Results | corpus figures; feature table; AUC with n visible | 600 | §4 |
| 4. What we ruled out | tiers unsourceable; vocabulary not the constraint; pre-1930 redundant; sentence scope binding | 500 | §5 |
| 5. Limitations | 20 of 67; name-text join; 19.4% redundancy and why it does not move the headline; 0.2 precision | 400 | §6, §7 |
| 6. Availability | CC0 data, Apache-2.0 code, per-row provenance, one place computes the numbers | 150 | §8 |
| Figures | pipeline schematic; AUC-with-n | — | §9 |

**Cut entirely:** the four-counter history (one sentence in §2), the duplicate-audit method
detail (two sentences in §5), the deodorant-subclass finding, the yield table's third row,
and figures 2 and 3 from §9.

**Do not cut:** the licensing argument, the verbatim invariant, measure-yield-before-fetch,
the negative results, and the small-n caveat under the AUC table. Those five are the paper.
