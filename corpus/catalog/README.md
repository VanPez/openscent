# Materials catalogue

`materials.tsv` lists common commercial perfumery compounds, one row per PubChem CID, **whether
or not the OpenScent corpus holds a description of their odour**. It is built by
`pipeline/catalog.py` and is a companion to the corpus, not part of it: `status.py` does not
read it, and the corpus rows keep their own provenance and licence.

## Why it exists

The compounds were selected as materials sold to perfumers by two retail suppliers in 2026.
208 distinct single compounds resolved to a PubChem CID. Of these, a number have an odour
description in an admissible source the corpus holds (US patents, US-government data); the rest
do not. Those are listed anyway, marked `no admissible description found`, so the gap is visible
and measurable rather than silent.

## Columns and their sources

| columns | source | status |
|---|---|---|
| `common_name` | the first name the material is sold under, cleaned of supplier codes and dilutions (e.g. "Aldehyde C12 Lauric", "Iso E Super") | name (fact) |
| `cid`, `pubchem_title`, `iupac_name`, `formula`, `mw`, `exact_mass`, `xlogp3`, `tpsa`, `hbd`, `hba`, `rotatable_bonds`, `smiles`, `inchikey`, `inchi` | computed by PubChem (NCBI) | US-government work, public domain |
| `cas` | CAS Registry Numbers, as stated by the suppliers and checksum-validated | identifiers (facts) |
| `commercial_names` | names the material is sold under, kept only if PubChem lists the name as a synonym or the supplier marked it with the maker's code | names only, used nominatively |
| `vapour_pressure`, `boiling_point`, `logp_measured` (+ `_source`) | PubChem experimental properties, **only** where the depositing source is a US-government database (HSDB, CAMEO, NIOSH, EPA, NTP, FDA…); copied verbatim with the source named | public domain; values from other depositors are dropped |
| `descriptor_status`, `corpus_tags`, `status_note` | the OpenScent corpus | CC0 |

No supplier's odour descriptions, prices or catalogue text are included, and the catalogue does
not say which supplier sells what.

## Trademarks

Names such as Iso E Super®, Cashmeran®, Hedione®, Helional®, Ambroxan® and others are trademarks of
their respective owners (among them IFF, Givaudan, Firmenich/DSM-Firmenich, Symrise and Kao).
They are used here only to identify the materials.
