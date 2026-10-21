# OpenScent molecule card — v0 (draft, 2026-10-21)

**Status: a draft for discussion with Mike before the MolNFT v2 contract. Nothing is built yet.** Every figure here was
measured on `release/v1.0` on 2026-10-21: 1,695 molecules, 1,678 with a structure, 4,399 evidence rows.

## The rule

Store only facts that cannot be recomputed (**static**). Everything that can be derived from them is **computed**, by the
contract or in the user's browser (Mike's principle: write the formula, compute the mass).

The root static field is the **structure (SMILES)**, not the formula: a formula does not identify a molecule (C10H18O is
linalool, geraniol, alpha-terpineol and 1,8-cineole alike), while the formula, mass, InChIKey and the rest all follow from
the SMILES.

Two corpus rules shape the card:

- **Extract, never generate.** There is no written description. The text on a card is the verbatim source sentences, each
  with its source and licence basis. No summaries, no health or therapy claims.
- **A token needs a structure.** The 17 molecules known only by name get no card on chain.

## Three levels

| level | what | stored |
|---|---|---|
| A. corpus | facts shared by every card | once per release / contract |
| B. molecule | facts about one molecule | once per token |
| C. computed | anything derivable from A and B | never stored; computed by the contract or the browser (or off-chain per release, said so) |

## Fields

### A. Corpus level (static, stored once)

| # | field | content | from |
|---|---|---|---|
| A1 | release | version, date, SHA-256 of the release files | `release/v1.0/manifest.json`, `SHA256SUMS` |
| A2 | licence | CC0 1.0 for the data; a suggested citation | release README |
| A3 | descriptor -> tag table | the only place a descriptor word becomes an odour tag (7.8 kB) | `ontology/odor_terms.tsv` |
| A4 | tag vocabulary | the 67 terms and the 30-molecule bar | `release/v1.0/tags.tsv` |
| A5 | source registry | source type -> licence basis and link pattern (patent number -> Google Patents; HSDB / CAMEO / NIOSH / OSHA -> the PubChem record) | `evidence.tsv` columns |
| A6 | sentence store (optional) | each verbatim sentence stored once, with its source; cards point to it | `evidence.tsv` `quote` (2,353 distinct sentences, 318 kB) |

### B. Molecule level (static, one token)

| # | field | content | example: Ethylvanillin |
|---|---|---|---|
| B1 | structure | SMILES as resolved; stereo only where the source states it | `CCOC1=C(C=CC(=C1)C=O)O` |
| B2 | names | the name as printed, and its other spellings | Ethylvanillin · ethyl vanillin · ETHYL VANILLIN |
| B3 | structure provenance | how the structure was obtained (read directly from the name, a PubChem record, or a hand-derived reading with its reason) and its strength | read directly + PubChem record · direct |
| B4 | evidence | per item: the sentence (or a reference into A6), the molecule as printed, the descriptor word(s) as printed, the source id, the scope (sentence / passage), how it was decided (human-approved / rule-extracted) | 4 items: US20150267144A1 (2), HSDB, CAMEO |
| B5 | external ids | PubChem CID(s): a link, not a fact about the molecule; optional | 8467 |

### C. Computed (never stored)

| # | field | computed from | where | example |
|---|---|---|---|---|
| C1 | molecular formula | B1 | browser (or contract, if it parses SMILES) | C9H10O3 |
| C2 | molecular mass | C1 | contract (simple sum) or browser | 166.17 |
| C3 | InChI / InChIKey | B1 | browser (RDKit.js with InChI) | CBOQJANXLMLOSS-UHFFFAOYSA-N |
| C4 | connectivity key | C3 (first block) | either | CBOQJANXLMLOSS |
| C5 | logP | B1 | browser (RDKit's Crippen logP; PubChem's XLogP3, 1.6 here, is a different method) | — |
| C6 | 2D drawing | B1 | browser | — |
| C7 | 3D model | B1 | browser (RDKit conformer), or a link to PubChem's computed conformer | — |
| C8 | odour tags | descriptor words in B4 x table A3 | contract or browser | sweet · vanilla |
| C9 | counts | B4 | contract or browser | 4 quotes, 4 documents, 2 tags; sources: patent, HSDB, CAMEO |
| C10 | tags at the bar | C8 over all tokens | contract or browser | — |
| C11 | scent-map position | C8 over the whole release (t-SNE) | off-chain, once per release; not reproducible in a contract | — |

## Example card (Ethylvanillin)

```
STATIC
  structure   CCOC1=C(C=CC(=C1)C=O)O
  names       Ethylvanillin | ethyl vanillin | ETHYL VANILLIN
  provenance  read directly from the name; matches PubChem CID 8467 — direct
  evidence    1. US20150267144A1 (patent, human-approved): "...the incorporation of ethyl vanillin or vanillin in a melamine
                 formaldehyde slurry produces a microcapsule ..."   molecule: "ethyl vanillin"   words: "sweet", "vanilla"
              2. HSDB (rule-extracted): "Finer and more intense vanilla"   words: "vanilla"
              3. CAMEO (rule-extracted): "Ethyl vanillin appears as colorless crystals. More intense vanilla odor and taste
                 than vanillin. (NTP, 1992)"   molecule: "Ethyl vanillin"   words: "vanilla"
  links       PubChem 8467
COMPUTED
  formula C9H10O3 · mass 166.17 · InChIKey CBOQJANXLMLOSS-UHFFFAOYSA-N · tags sweet, vanilla · 4 quotes from 4 documents
```

## Sizes (static text, measured)

| content | size |
|---|---|
| SMILES, 1,678 molecules | 38 kB |
| names as printed | 45 kB; other spellings 51 kB |
| distinct sentences (2,353) | 318 kB |
| molecule and descriptor spans plus tags, 4,399 evidence rows | 179 kB |
| descriptor -> tag table | 7.8 kB |

About 0.6 MB of text in all, most of it the sentences. One sentence often supports several molecules (2,353 distinct
sentences behind 4,399 evidence rows), so a shared sentence store (A6) avoids storing the same text twice; per-token storage
would repeat it. The median card carries 242 bytes of sentence text.

## Not on the card

- Generated text of any kind (descriptions, summaries, notes).
- Health or therapy claims.
- The 17 molecules without a structure.
- Retired, rejected and undecided rows.
- The licensed Olfatorium layer (CC BY 4.0, not CC0): if it is ever published, as a separate, labelled layer.

## Open questions for the contract

1. Per-token storage, or a corpus-level sentence store (A6) that cards reference?
2. Should the token store the InChIKey (27 bytes) so the contract can refuse duplicates, even though it is computable?
3. Which computed fields belong in the contract (mass from formula is a simple sum; formula from SMILES needs a parser) and
   which in the browser?
4. Field size limits, cost per byte, chunking.
5. Corrections after minting: structures in this corpus have been corrected from the patent text more than once (rewrites with
   reasons). Is a token's structure immutable, versioned, or superseded by a new token?
6. Format of the licence field and the citation.

## Built so far (2026-10-21)

The corpus page (`docs/corpus.html`, built by `pipeline/corpus_page_build.py`) shows this card for every molecule: a
**Stored** block (structure, names, provenance, evidence, links) and a **Computed** block. Computed in the browser, with no
library: the formula and mass from the SMILES (a small parser; checked against PubChem: the same formula for all 1,647
molecules with a PubChem record, the mass within PubChem's own precision for 1,643, the other 4 being one-decimal rounding)
and the odour tags from the descriptor words with the tag table (it reproduces all 4,399 evidence tags). The InChIKey is
still computed by the release build, and XLogP3 and the 3D model are PubChem's; the card says so on each line.

The tag table (A3) is read from `ontology/odor_terms.tsv`, which is not in `release/v1.0`: as corpus-level static data it
should join the release at the freeze.

## Next (web2 first)

A card view on the corpus page: each field labelled static or computed, the computed ones calculated in the browser. Open
choice: RDKit.js from a CDN (full chemistry; the page stops being a single offline file) or a small script for formula and
mass only (enough for v0).
