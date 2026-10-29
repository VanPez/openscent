# OpenScent molecule card — v1 (draft, 2026-10-29)

**Status: a draft for the MolNFT v2 contract. Nothing is minted.** v1 applies Mike's review of v0 (2026-10-22). Every figure was
measured on `release/v1.0` as rebuilt on 2026-10-29: 1,682 molecules, **1,680 with a structure = 1,680 tokens**, 4,341 evidence
rows on those tokens. v0 is kept as `reports/molecule-card-v0.md`. The same card for one token as plain JSON, field title and
content only: `reports/molecule-card-v1-example.json` (Ethylvanillin), built by `pipeline/card_json.py`.

## What changed from v0

| # | Mike's point | v0 | v1 |
|---|---|---|---|
| 1 | one NFT per molecule | open question: per-token storage or a shared sentence store | **one token per molecule**; each token carries its own sentences; the shared store (v0 A6) is dropped |
| 2 | the scent is the main information and must be stored on chain | odour tags were *computed* from the descriptor words and the tag table | **scent stored** on the token (B6): the tags with the words that gave them |
| 3 | XLogP3 is fetched, not computed | listed as computed | **stored** (B7), PubChem's value |
| 4 | the 3D conformer is fetched, not computed | "computed in the browser, or a link to PubChem" | **stored** (B8), PubChem's conformer |

Points 3 and 4 correct a real mistake in v0: a value fetched from PubChem cannot be recomputed by the contract or the browser
(XLogP3 is NCBI's own algorithm; PubChem's conformer is one specific computed geometry), so by v0's own rule it is static.

## The rule (unchanged, now applied correctly)

Store what cannot be recomputed from the token itself; compute the rest. A value fetched from an outside source is stored, with its
source. The root static field is still the structure (SMILES).

## Fields

### A. Contract level (stored once)

| # | field | content |
|---|---|---|
| A1 | release | version, date, SHA-256 of the release files |
| A2 | licence | CC0 1.0 for the data; a suggested citation |
| A3 | descriptor -> tag table | maps a descriptor word to one of the 67 tags (`ontology/odor_terms.tsv`, 7.8 kB) |
| A4 | tag vocabulary | the 67 terms (B6 points into it) and the 30-molecule bar |
| A5 | source registry | source type -> licence basis and link pattern |

### B. Token level (one token per molecule, stored)

| # | field | content | example: Ethylvanillin |
|---|---|---|---|
| B1 | structure | SMILES; stereo only where the source states it | `CCOC1=C(C=CC(=C1)C=O)O` |
| B2 | names | the name as printed, and its other spellings | Ethylvanillin · ethyl vanillin · ETHYL VANILLIN |
| B3 | structure provenance | read from the name / PubChem record / hand-derived reading, and its strength | read directly + PubChem record · direct |
| B4 | evidence | per item: the verbatim sentence, the molecule as printed, the descriptor word(s), the source id, the scope, how it was decided | 4 items |
| **B6** | **scent** | the odour tags (indexes into A4) and, for each, the descriptor words that produced it, as of the release in A1 | sweet ← sweet · vanilla ← vanilla |
| **B7** | **XLogP3** | PubChem's value (NCBI XLogP3), or null when PubChem has none | 1.6 |
| **B8** | **3D conformer** | PubChem's computed conformer: element numbers, coordinates, bonds; null when PubChem has none | 22 atoms |
| B5 | external ids | PubChem CID (the source of B7 and B8) | 8467 |

### C. Computed (never stored)

| # | field | from | where |
|---|---|---|---|
| C1 | molecular formula | B1 | browser (done) or contract |
| C2 | molecular mass | C1 | browser (done) or contract |
| C3 | InChI / InChIKey | B1 | browser (RDKit.js) — see question 2 |
| C4 | connectivity key | C3 | either |
| C6 | 2D drawing | B1 | browser |
| C8' | tag check | B4 words × A3 | recomputes B6 as a check (the page does: it reproduces every stored tag) |
| C9 | counts | B4 | either |
| C10 | tags at the bar | B6 over all tokens | contract or browser |
| C11 | scent-map position | B6 over the release (t-SNE) | off-chain, once per release |

## Sizes per field, measured (1,680 tokens)

| content | size |
|---|---|
| SMILES | 38 kB |
| names as printed / other spellings | 45 kB / 51 kB |
| sentences, each token its own copy | **330 kB** (median 171 B, max 1,491 B per token) — a shared store would be 311 kB, so the copies cost only ~6% |
| evidence spans, tag and source id per row (4,341 rows) | 216 kB |
| scent (B6) | 3,237 molecule-tag pairs (median 1 tag per token): 3.2 kB as 1-byte indexes, 21 kB as text; the words are already in B4 |
| XLogP3 (B7) | 1,560 of 1,680 tokens have a value (range −5.2 to 10.5); 2 bytes each as a signed tenths integer ≈ 3 kB |
| 3D (B8) | 1,557 of 1,680 tokens have one; **1.38 MB as JSON** (median 921 B); **422 kB packed** (median 280 B: 1-byte element, three int16 coordinates in milli-ångström, 3-byte bonds); median 28 atoms, max 60 |

The 3D conformers are the largest field — more than everything else together. Packed binary is a third of JSON and loses nothing at
PubChem's precision (3 decimals; every coordinate fits an int16 at milli-ångström). Hydrogens are about half the atoms (median 12 heavy
atoms of 28); dropping them would make the field smaller but the geometry would no longer be PubChem's — not proposed.

## Open questions for the contract

1. ~~Per-token or shared sentence store~~ — answered: per token (point 1).
2. Store the InChIKey (27 bytes, 45 kB in all) so the contract can refuse a second token for the same molecule? With one token per
   molecule this matters more than in v0. **Proposed: yes**, although it is computable.
3. Encoding of B8 (JSON or packed binary) and of B6/B7 (indexes, integers) — cost per byte decides.
4. Field size limits, cost per byte, chunking (the largest 3D field is 2,004 bytes as JSON).
5. Corrections after minting: structures in this corpus have been corrected from the patent text more than once. A token's structure:
   immutable, versioned, or superseded by a new token? The same for B6 if the tag table changes in a later release.
6. Format of the licence field and the citation.
7. The 120 tokens without XLogP3 and the 123 without a 3D conformer: store null explicitly, or omit the field?

## Not on the card (unchanged)

Generated text of any kind; health or therapy claims; molecules without a structure (2 in v1.0); retired, rejected and undecided rows;
the licensed Olfatorium layer (CC BY 4.0) unless published as a separate, labelled layer.
