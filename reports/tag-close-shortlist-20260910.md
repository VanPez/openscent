# Closing shortlist for the five near-bar tags — and a name-variant problem underneath

**Date:** 2026-09-10 · method: grep the undecided rows for each tag's own chemistry ·
**proposals, not decisions**

## The counts are not what `status.py` prints

`status.py` joins molecules on NAME TEXT — its own docstring calls the result an upper
bound. Squashing spaces, hyphens, brackets and the `l/1` `O/0` scanner confusions shows
the same molecule counted twice inside a single tag:

| tag | printed | duplicate spellings | real |
|---|---|---|---|
| musk | 67 | 4 | 63 |
| mint | 63 | 3 | 60 |
| woody | 111 | 3 | 108 |
| green | 149 | 2 | 147 |
| fatty | 49 | 2 | 47 |
| sweet | 213 | 2 | 211 |
| floral | 170 | 1 | 169 |
| lily | 56 | 1 | 55 |
| herbal | 42 | 1 | 41 |
| balsamic | 18 | 2 | 16 |
| jasmine | 13 | 1 | 12 |
| **amber** | **28** | **2** | **26** |
| **sandalwood** | **29** | **1** | **28** |

**The headline is safe — no tag at the bar falls below 30.** But the two nearest tags move
the wrong way: `sandalwood` needs **2**, not 1. `amber` needs **4**, not 2.

Examples: `4-acetyl-3,3,8,8-tetramethyl-as-hydrindacene` / `-ashydrindacene`;
`1,l,2,3,3-pentamethylhexahydro-4(5h)-indanone` / `1,1,2,3,3-...`.

25 duplicate spellings corpus-wide (22 in tags with >=20 molecules). `balsamic` and
`jasmine` also carry variants; neither is near the bar.

Caveat: the squash is aggressive (`i`->`1` especially). Every pair above reads as a true
duplicate on inspection, but the rule wants Ivan's eye before it goes anywhere near
`status.py`.

## Shortlist

### sandalwood — needs 2 — TWO CLEAN CANDIDATES, closes exactly

- **US3673263A** / **US3673266A** — `dihydro-B-santalol`
  > "The novel compound, dihydro-B-santalol, prepared by the process of this invention has
  > a powerful, long lasting highly desirable odor characterized as strong sandalwood."
- **US3662008A** / **US3679756A** — `B-santalol`
  > "...a process for preparing B-santalol, a component of sandalwood oil, having a
  > valuable sandalwood odor and useful in perfume compositions."

`B-` for beta is a rendering the corpus has already approved (US3673261A). Neither compound
is currently counted; `alpha-santalol` is.

**TRAP:** US3580953A's `dihydro-[i-santalol` and US3580954A's `dihydro-fi-santalol` are the
SAME molecule as `dihydro-B-santalol`. Approving more than one creates a phantom.

### camphoraceous — needs 2 — FOUR CANDIDATES, likely closes

| source | molecule | note |
|---|---|---|
| US3679756A | `8-oxoethyl epicamphene hydrate` | "useful as an odorant **per se**, having a sweet, camphor odor" — cleanest of the four |
| US12187979B2 | `1,5-dimethyl-bicyclo[3.2.1]octan-8-on O-methyl oxime` | **SPLIT** — two compounds, different profiles |
| US6034268A | `ocimenol` | **SPLIT** — "fresh-camphoraceous lime-like"; ocimenyl acetate differs |
| US20130303433A1 | `5-(but-3-en-2-yl)-1-methylcyclohex-3-enecarbaldehyde` | second-hand: "is described possessing" (cites another patent) |
| US12103935B2 | `ambroxide` | "camphor-like" — also serves animalic, see below |

### amber — needs 4 — NOTHING

The only candidate the scan surfaced, US3914314A's
`cis-3,4,4a,5,6,7,8,8apentamethyl-2( lH)-naphthalenone`, is an OCR variant of
`cis-3,4,4a,5,6,7,8,8a-octahydro-3,4a,5,5,8a-pentamethyl-2(1h)-naphthalenone`, **already
counted**. Approving it would inflate, not advance.

### animalic — needs 4 — ONE AND A HALF

- **US12103935B2** — `ambroxide`: "described to have a warm, slightly earthy, camphor-like,
  exotic-woody, **animal-like** note". Clean, and doubles for camphoraceous.
- **US3923699A** / US3929893A — `Cyclohexadecenone-S`: "is more animal-like than many other
  synthetic musk compounds" — comparative, borderline. `musk` is the clean read here.

### aldehydic — needs 7 — TWO

- **US20080161224A1** — `3-(4-methylcyclohex-3-enyl)butyraldehyde` (limonenal). Clean.
- **US12319647B2** — `2-(2,4,5-trimethylcyclohex-2-en-1-yl)acetaldehyde`, "is used to
  impart" — the form REVIEW-RULES explicitly keeps. Three rows, one molecule.

## Expected outcome of one sitting

**20 -> 22 tags** (sandalwood, camphoraceous). Amber, animalic and aldehydic do not close
from the existing queue, which is the sourcing question again — now with amber needing 4
rather than 2.
