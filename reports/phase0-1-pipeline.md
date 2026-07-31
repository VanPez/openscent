# CC0 odour corpus — Phase 0/1 design sketch

Working design for the corpus half of Mike's build plan (2026-07-31). Covers the extraction rule, the
provenance schema, and what a USPTO mining pass actually involves. Not a commitment — a sketch to argue with.

The corpus is the load-bearing contribution. The model demonstrates it; the paper describes it; but if the
corpus isn't clean, nothing downstream is worth minting. And it goes on-chain immutably, so the licence
audit has to close *before* the mint, not after.

---

## 0. The ordering is not what the plan says

Mike's plan lists ONTOLOGY as Phase 0 and CORPUS as Phase 1, with "Phase 0 gates everything". But the
ontology is defined as *"own vocabulary, term frequency over the PD corpus"* — which requires the corpus
to already exist. These interleave:

```
1a. COLLECT      raw documents + raw text spans, no tagging yet
0.  ONTOLOGY     term-frequency over 1a -> candidate tags -> human prunes to 60-100
1b. TAG          map spans -> ontology terms, deterministically
```

This matters practically: **1a is the long pole** (OCR, patent mining, linkage) and can start immediately,
because it doesn't depend on the vocabulary. Don't block on ontology design.

---

## 1. The extraction rule — "extract, never generate"

The paper's central claim is licence purity. The threat to it is subtle and is the same trap that produced
the unverifiable descriptors in `rows2.json`: **an LLM asked to "describe this molecule's odour" answers
from training data that includes GoodScents and Leffingwell.** The input being public domain does not make
the output clean, and there is no provenance to audit.

So the rule:

> **A model may only return text that appears verbatim in the source document. It never writes an odour
> word that isn't already there.**

Operationally, in three separated steps:

| Step | Does what | Who does it | Auditable? |
|---|---|---|---|
| **Locate** | finds character spans in the source that describe odour | LLM or regex | yes — span offsets |
| **Verify** | asserts `span == source_text[start:end]`, rejects on mismatch | deterministic code | yes — hard assert |
| **Map** | span text → ontology tag | **static lookup table, human-written** | yes — table is published |

The LLM decides *where the odour language is*. A table you wrote decides *what it means*. Contamination
cannot enter through the model because the model never supplies vocabulary — only coordinates.

The mapping table (`odor_terms.tsv`: `surface_form → tag`) becomes a published artifact in its own right.
`"powerful woody-ambery"` → `woody`, `amber`. `"dry cedarwood character"` → `woody`, `dry`. When someone
challenges a row, you show them the sentence and the table line. That is a defensible audit trail; "an LLM
said so" is not.

**Enforcement, not intention.** The verify step must be a hard failure in the pipeline, not a review habit:

```python
assert span in source_text, f"REJECT {row_id}: span not verbatim in source"
```

Anything that fails is dropped, logged, and counted. A published rejection rate is evidence the rule was
actually enforced.

---

## 2. Provenance schema

One row = one (molecule, tag) assertion backed by one piece of evidence. Not one row per molecule — a
molecule with five tags from three documents is fifteen rows. Aggregation happens at build time, so the
evidence survives.

```json
{
  "molecule": {
    "cid": 638014,
    "canonical_smiles": "CC1=C(C(CCC1)(C)C)/C=C/C(=O)C",
    "inchikey": "PSQYTAPXSHCGMF-BQYQJAHWSA-N",
    "resolved_by": "opsin|pubchem-name|manual",
    "resolved_from": "beta-ionone"
  },
  "tag": "woody",
  "evidence": {
    "verbatim_span": "warm woody, dry, and fruity odor",
    "char_offset": [18422, 18454],
    "sentence": "The compound of Example 3 has a warm woody, dry, and fruity odor reminiscent of cedar.",
    "mapping_rule": "odor_terms.tsv:v1#L214"
  },
  "source": {
    "id": "US4482465A",
    "type": "patent|book|dataset",
    "ref": "US Patent 4,482,465, col. 6 ln. 12",
    "licence": "public-domain-usgov|public-domain-expired|CC0",
    "retrieved": "2026-08-01",
    "url": "https://data.uspto.gov/..."
  },
  "extraction": { "method": "llm-span", "extractor_version": "0.1.0", "verified_verbatim": true }
}
```

Non-obvious choices, and why:

- **`licence` is per-row, not per-dataset.** The corpus mixes US-government works, expired copyright, and
  CC0. If one source is later challenged, you delete those rows rather than the corpus.
- **`char_offset` + `sentence`** make every claim independently checkable against the source document.
- **`resolved_by`** records how a name became a structure — the single biggest error source (see §3).
- **`mapping_rule`** pins the exact table line, so re-running an old build reproduces old tags even after
  the table evolves.
- **No confidence score.** A score invites "probably fine" rows. Either the span is verbatim and the
  mapping is in the table, or the row doesn't exist.

---

## 3. What a USPTO mining pass actually involves

**Access.** USPTO Open Data Portal, [data.uspto.gov](https://data.uspto.gov/apis/bulk-data/search) — free
bulk search and download API, requires a free API key. (The legacy developer hub was decommissioned in June
2026; older tutorials point at dead endpoints.)

**Where the fragrance chemistry lives.** Target CPC class **C11B 9/00** — *essential oils; perfumes* —
which covers the odorant compounds themselves. Useful quirk: the CPC definition for C11B 9/0003–9/0096
requires **all exemplified compounds to be classified**, so the class is applied at compound level rather
than just to the invention as a whole. **A61Q 13/00** (*formulations or additives for perfume preparations*)
is secondary — it's mostly mixtures and consumer products, where odour claims describe blends, not molecules.

**The actual work is linkage, not scraping.** A fragrance patent typically describes dozens of compounds,
and the odour sentence almost never names the molecule:

> "The compound of **Example 3** possesses a powerful woody-ambery odour with a dry cedarwood character."

To make that a data row you must resolve *Example 3* → a structure. Three routes, in order of reliability:

1. **IUPAC name in the examples section → structure.** Use **OPSIN** (open-source name-to-structure, from
   Cambridge). This is the workhorse and it's accurate on well-formed nomenclature.
2. **Trade name or CAS number → PubChem lookup.** Good for known captives.
3. **Structure only in an image.** Skip — OCSR (optical chemical structure recognition) is a research
   problem and not worth the error rate here.

Realistically: parse the *Examples* section, build a local map of `example_number → name/CAS`, resolve
names with OPSIN, then attach odour spans found in the same example block. Reject anything where the
example number is ambiguous. Expect to discard a large fraction — that's correct behaviour, not failure.

**Why this is worth the trouble.** The 37 molecules in the current pilot with *no* free odour source are
exactly the modern captives — Iso E Super, Hedione, Norlimbanol, Cashmeran, the musks. Those have no free
descriptors precisely *because* they're recent commercial materials. Which means they were patented, and
their patents describe their odour in detail. **Patent mining is the only route to the specific molecules
that are otherwise undocumentable.**

**Known biases to declare in the paper, not discover later:**

- Patent odour language is *applicant-supplied advocacy*. Everything is "powerful", "elegant", "outstanding
  substantivity". Useful for descriptors, useless for intensity or hedonics.
- Coverage skews to what was worth patenting — synthetics, not naturals.
- Patent families duplicate the same text across jurisdictions; de-duplicate on family, not document.
- A patent describes what the applicant *claims*, sometimes for a compound that never reached market.

---

## 4. Suggested first move — a 20-patent proof

Before building anything: take **20 patents** covering molecules whose odour you already know
(β-ionone, Iso E Super, Hedione, Ambroxan, a few musks), and run the whole pipeline by hand.

It answers the only questions that matter before committing months:

- What fraction of example blocks resolve to a structure at all?
- Does OPSIN handle the nomenclature these patents actually use?
- How many distinct odour surface-forms appear, and do 60–100 tags plausibly cover them?
- Does the verbatim-span rule survive contact with real patent prose, or is the language too indirect?
- Do the extracted descriptors agree with what you know these molecules smell like?

That last one is the real test, and it's the one thing here that only Ivan can judge.

If 20 patents yield clean rows for even 10 molecules, the method works and scale is an engineering problem.
If they don't, better to know now than after the OCR pipeline is built.

---

## Open questions for Mike

1. **Do note tiers belong in a CC0 scientific corpus at all?** Ours are a judgement, not a measurement — a
   rule fitted to the existing 99 reproduces them at only 56% under leave-one-out. Defensible as a labelled
   opinion, wrong as implied data.
2. **Is he doing the 8-byte node read optimisation?** It changes the gas economics of a per-tag model mint,
   which changes how many tags the ontology can afford.
3. **Feature commitment: (a) vectors via MolNFT or (b) Morgan in Solidity?** (a) is achievable now; only
   (b) makes "verifiable SMILES→prediction" literally true. Worth starting on (a) provided the paper
   doesn't claim (b).
