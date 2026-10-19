# Licensed layer — NOT part of the OpenScent corpus

**Licence: CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/ — attribution required.** This folder is outside
`corpus/` and is not covered by the repository's CC0 data licence. The CC0 corpus, the v1.0 release and the MolNFT tokens
contain nothing from here.

## What it is

Descriptor **words** (not sentences) that a rights holder allowed OpenScent to use, each mapped by a person to one of the 67
corpus tags. Files are named after the source.

| file | source | permission | rows |
|---|---|---|---|
| `olfatorium-rows.jsonl` | Olfatorium, https://olfatorium.com/ | written permission of the owner, 2026-10-13: the short descriptor words from descriptions Olfatorium wrote themselves, under CC BY 4.0, credited with a link, in a separate labelled layer | 144 (136 approved, 8 rejected and kept so they are not proposed again) |

## How to credit

> Descriptor words from Olfatorium (https://olfatorium.com/), used under CC BY 4.0 with the owner's permission.

Every row carries `attribution`, `licence`, `licence_basis` and the product page it comes from (`source_url`).

## What a row contains, and what it does not

The word (`span`, Spanish, as written on the page), the tag it maps to (`tag`, with `mapping_confidence` and
`mapping_note`), the PubChem CID and CAS of the molecule, and a locator: the field, the offsets and a SHA-256 of the sentence
it sits in. **The shop's sentences are not here**: the permission covers descriptor words. Anyone with the product page can
check a row from the locator; the extraction scripts are `pipeline/olfatorium_fetch.py` and
`pipeline/olfatorium_candidates.py`.

## Rules

- `pipeline/status.py` reports these rows as a separate source. Its default output is the v1.0 figures (the layer is NOT in
  COMBINED; an add-on row shows the total with it); `--with-licensed` counts the layer into COMBINED; `--no-licensed`
  ignores it.
- Never copy these rows into `corpus/`. If a rights holder later releases words under CC0, that is a new decision.
- Other sources (for example De Hekserij) are NOT in this layer: their current descriptors were declined.
