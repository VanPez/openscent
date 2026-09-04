# Review rules — what makes a row

A row asserts: **this molecule smells of these descriptors**, and both must be verbatim in
one sentence. Everything below follows from that.

These were tacit until 2026-08-25, when a blind evaluation of Claude against Ivan's 300
decisions disagreed on 14 of 98 — and the disagreements were not noise. They were two
rules neither of us had written down, applied in opposite directions. Written rules are
the only defence against a corpus that means slightly different things in different weeks.

---

## The molecule

**A definite structure, or no row.**

The compound must be identifiable well enough for OPSIN to resolve it to a structure. A
name with an unspecified group is a family, not a molecule.

| | |
|---|---|
| REJECT | `7-alkoxy-3,7-dimethyloctan-2-ol` — alkoxy could be anything |
| REJECT | `alkyl 3-methoxy-3-methyl-1-butanol esters` |
| REJECT | `acetal of 2,4,7-decatrienal` — which acetal? |
| REJECT | "compounds having a X basic structure" — a scaffold |
| REJECT | "certain 3-isopropyl-1-methylcyclopentyl derivatives" |
| KEEP | `(1R,6S)-allyl 2,2,6-trimethylcyclohexanecarboxylate` — stereodescriptors are SPECIFIC |
| KEEP | `(1S*,2R*)-...` — relative stereochemistry is still definite |

Note the asymmetry: `(R)-` narrows a structure, `R-` as a variable group leaves it open.
Same letter, opposite effect.

**Trade names are not separate molecules.** Lilial™ and 3-(4-tert-butylphenyl)-2-
methylpropanal are one compound; recording both double-counts it. Prefer the systematic
name — it resolves.

---

## The mixture rule

**If the odour is attributed to a mixture, there is no row. Including a mixture of
stereoisomers of one compound.**

| | |
|---|---|
| REJECT | "the mixture of X and Y was described as having…" |
| REJECT | "a mixture of cis- and trans-X is described as…" |
| REJECT | "the mixture of (4R)- and (4S)-forms of X shows…" |
| REJECT | "the isomeric mixture of Structure 45 and 46…" |
| REJECT | "X **(E/Z of ~4:1)** was described as having…" — a ratio in brackets is still a blend |
| KEEP | "X, **and mixtures thereof**, exhibit…" — X is described in its own right |
| KEEP | "(Z)-enriched X has an expressive rose odour" — enriched is not mixed |

**The bracketed-ratio form is the one that looks like an exception and is not.**
`Ethyl nona-3,8-dienoate (E/Z of ~4:1)` reads as a compound with an analytical footnote,
the way "(97% pure)" would. It isn't: E and Z are two different substances, and the
sentence reports the smell of a jar containing 80% of one and 20% of the other. Settled
2026-08-29 after the grammatical difference was raised — the SUBJECT being the compound
rather than "the mixture of" does not change what was in the jar.

Note what rejecting it usually costs: nothing. A patent careful enough to state a ratio
almost always characterises the pure isomers separately elsewhere, and those rows are
strictly better. In the case that settled this, `(E)-` and `(Z)-non-3-enoate` each had
their own sentence two lines further down.

Settled 2026-08-25 in Ivan's favour. Claude argued a mixture of enantiomers of one
compound is still that compound; the counter-argument won: **enantiomers can smell
different** (carvone is the textbook case), so a 50:50 mixture's odour is not either one's
odour. The rule is about what the evidence supports, not about chemical identity.

The test: **could this odour belong to one component rather than the whole?** If yes,
the sentence does not tell you which.

---

## The attribution

The odour must belong to the MOLECULE, not to something the molecule is in or near.

| | |
|---|---|
| REJECT | "the composition/perfume oil has a … note" — composition-level |
| REJECT | "if X had been used instead, the composition would have acquired…" — counterfactual |
| REJECT | "this floral note is…" / "said ingredient" / "compound (7)" — anaphora, nothing named |
| REJECT | "starting materials: X and acetic anhydride" — reagents |
| REJECT | "towels washed with X exhibit a strong Florhydral note" — a precursor releasing something else |
| KEEP | "X is used to impart a fruity note" — the note originates in X |

"Imparts to a composition" is the hard case. Ask whether the descriptor originates in this
compound or emerges from the blend. "Blends well with", "emphasises", "harmonises",
"contributes to the top note" are blend effects. "Is used to impart a fruity note" is not.

---

## Descriptors

**A descriptor names a smell quality. Not a substance, not an intensity, not a judgement.**

| | |
|---|---|
| NOT a descriptor | `nitromusk`, `acetophenone`, `isoeugenol`, `damascone`, `Lilial`, `ionone`, `citronellol` — substances used as comparisons |
| NOT a descriptor | `weak`, `faint`, `strong`, `powerful`, `diffusive`, `long-lasting` — intensity |
| NOT a descriptor | `top note`, `bottom note`, `dry down` — position |
| NOT a descriptor | `beneficial`, `pleasant`, `elegant`, `attractive`, `feminine` — judgement |
| IS a descriptor | `rose`, `sandalwood`, `lily of the valley`, `linden`, `coconut` — flowers, woods, foods |

The line is substance vs source. **A compound named as a comparison is a reference point;
a plant or food named as a smell is a descriptor.** "Reminiscent of nitromusk" gives
nothing; "reminiscent of peonies" gives `peony` — but only when the sentence attributes
the smell, not merely the comparison.

Watch for the same word in two senses: "a hybrid **rose** that lacks fragrance" is a
plant, not an odour.

**Negation and comparison invert.** "less pyrazinic", "devoid of character", "without the
lactonic note" — capturing these asserts the opposite of the sentence.

---

## Splits

One sentence, two compounds, DIFFERENT descriptions → **P** to split, then do each alone.
"X is floral whereas Y is fruity". Two compounds sharing ONE description → add both, approve
once.

---

## When in doubt

Reject. A missing row costs one row. A wrong row is indistinguishable from a right one
once it is in the corpus, and it is the thing the whole extract-never-generate rule exists
to prevent.

---

## Derivatives named as "the X of Y"

A patent often describes a compound without naming it directly, as a modification of one it
has just named. Whether that is a row depends on whether the phrase picks out **exactly one
substance**.

| | |
|---|---|
| KEEP | "the **acetate ester** of 1,5-dimethylcyclooct-1-en-5-ol" — acetylate the OH; one compound |
| KEEP | "the **propionate**/**formate** ester of X" — same |
| KEEP | "the corresponding **alcohol**/**aldehyde**" when only one such exists |
| REJECT | "the **acetal** of 2,4,7-decatrienal" — acetal with WHICH alcohol? a family |
| REJECT | "the **ester** of X" — which acid? |
| REJECT | "**derivatives** of X", "**substituted** X" |

The test: can you draw it without choosing anything? If a second decision is needed to
know what the substance is, it is a family.

**Record the whole phrase**, verbatim — `acetate ester of 1,5-dimethylcyclooct-1-en-5-ol`,
not the parent alcohol on its own. The parent is mentioned only to locate the derivative;
attributing the odour to it would name the wrong molecule. OPSIN will not parse the phrase,
so linkage has to rewrite it (`…-5-yl acetate`), but that is normalisation of extracted
text, not invention, and it happens after review.
