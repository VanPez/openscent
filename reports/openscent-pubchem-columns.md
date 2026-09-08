# openscent-pubchem.csv — columns

648 rows, one per PubChem CID. All values numeric.

`cid` is an identifier, NOT a feature — exclude it in the GL1F dataset tab.

## descriptors (RDKit, computed from the structure)

- `mw`
- `heavy_atoms`
- `n_carbon`
- `n_oxygen`
- `n_nitrogen`
- `n_sulfur`
- `n_halogen`
- `heteroatoms`
- `logp`
- `molar_refractivity`
- `tpsa`
- `labute_asa`
- `h_donors`
- `h_acceptors`
- `rot_bonds`
- `rings`
- `aromatic_rings`
- `aliphatic_rings`
- `saturated_rings`
- `fraction_csp3`
- `valence_electrons`
- `bertz_complexity`

## labels

`tag_<name>` — 1 if the molecule carries that odour tag. 15 tags with >= 10 molecules:

- `tag_pungent` — 187 molecules
- `tag_sweet` — 151 molecules
- `tag_aromatic` — 140 molecules
- `tag_fruity` — 85 molecules
- `tag_floral` — 39 molecules
- `tag_acid` — 31 molecules
- `tag_musty` — 28 molecules
- `tag_mint` — 24 molecules
- `tag_chlorine` — 18 molecules
- `tag_fatty` — 16 molecules
- `tag_green` — 12 molecules
- `tag_rose` — 12 molecules
- `tag_citrus` — 11 molecules
- `tag_spicy` — 11 molecules
- `tag_woody` — 10 molecules

`n_tags` — how many tags this molecule carries (mean 1.41, max 9).

`primary_tag_id` — single-class codification for multiclass tasks. The MOST SPECIFIC (rarest) tag the molecule carries; 0 if it carries none of the kept tags:

- 1 = woody (10 molecules)
- 2 = citrus (11 molecules)
- 3 = spicy (11 molecules)
- 4 = green (12 molecules)
- 5 = rose (12 molecules)
- 6 = fatty (16 molecules)
- 7 = chlorine (18 molecules)
- 8 = mint (24 molecules)
- 9 = musty (28 molecules)
- 10 = acid (31 molecules)
- 11 = floral (39 molecules)
- 12 = fruity (85 molecules)
- 13 = aromatic (140 molecules)
- 14 = sweet (151 molecules)
- 15 = pungent (187 molecules)

## provenance

Odour tags: HSDB records via PubChem, public domain. Structures: PubChem PUG REST. Descriptors: RDKit, offline. Nothing here is generated — every tag traces to a quoted HSDB span in corpus/rows/pubchem-rows.jsonl.

These are SAFETY records, not a perfume catalogue: `tag_chlorine` is real, and `n_halogen` will predict it almost perfectly.
