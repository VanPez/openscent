# Option 0 measured — the sandalwood queue is a passage-scope problem, not an ordering problem

**Date:** 2026-09-10 · sample seed `20260910` · **proposals, not decisions**

## Why this sample exists

`status.py` reported 49 productive rows and 0 of them aimed at `sandalwood`, which needs
ONE molecule. But `PRODUCTIVE()` requires a compound-like token **containing a digit**, and
sandalwood odorants are overwhelmingly trivially named (santalol, Ebanol, Javanol). 182
undecided rows carry a `sandal`/`sandalwood` surface form and NONE is flagged productive.

The proposal was to extend the predicate to trivial names. Standing rule: measure first.
25 of the 182 were drawn at random with a fixed seed and adjudicated against REVIEW-RULES.

## Result: 1 approve, 24 reject

| | |
|---|---|
| proposed approve | **1** (and its molecule name is OCR-damaged) |
| proposed reject | 24 |
| rate | 4%, Wilson 95% CI ~0.7-20% |
| extrapolated to 182 | ~7 approvals, wide — and see below, most would be re-rejected |

**Why the 24 fail — and this is the finding:**

| reason | n |
|---|---|
| anaphora (`It possesses`, `This compound`, `the carbinols 4a, b and c`) | 6 |
| composition-level (`the composition of Example VIII affords`) | 5 |
| no molecule named at all | 4 |
| family / derivatives / variable group (`alkyl`, `R2`, `general Formula (I)`) | 4 |
| mixture (`natural sandalwood oil`, `alpha,beta-santalol`) | 2 |
| scaffold | 1 |
| OCR damage | 1 |

**Extending the predicate would not have helped.** The rows it would surface are rejects for
a reason the predicate cannot see. Six of the 24 are anaphora where the molecule sits in the
PRECEDING sentence — the same finding as the HEADING removal (2026-08-03),
`organoleptic-colon` (2026-09-07) and `t09`. This is the fourth independent arrival at
passage scope.

The clearest example, US5326748A:

> It possesses a very strong sandalwood note, very woody, with a natural sandal character
> and a dry woody note reminiscent of the odor of cedarwood, accompanied by an amber
> undernote.

Rich, clean, unusable — the subject is one sentence away.

## The one approve, US3580953A (n=2822)

> ...a process for obtaining 3-endomethyl-3-exo(4-methyl 5' hydroxypentyl)norcamphor which is
> useful in synthesizing dihydro-[i-santalol, a compound having a valuable sandalwood odor.

`dihydro-[i-santalol` is OCR of *dihydro-beta-santalol*. The odour IS attributed to it. The
derivatives rule already contemplates recording a verbatim phrase OPSIN cannot parse and
normalising after review. Called approve on that precedent; it is the one call in the 25
that could go either way, and Ivan decides.

If it holds, `sandalwood` reaches 30 and crosses the bar.

## What this closes — and the correction

Option 0 as proposed (extend `PRODUCTIVE()` to trivial names) is **declined**. The rows it
surfaces are rejects for a reason the predicate cannot see: anaphora, composition-level,
families. That half of the finding stands.

**But the conclusion first drawn from it — that `sandalwood` cannot cross from the existing
queue — was wrong, and the sample is why.** 1 approve in 25 has a Wilson 95% CI of 0.7-20%;
the point estimate was led with and the interval was not. A `santalol` grep over the same
182 rows found four clean candidates the sample had not drawn, including two needing no OCR
argument at all:

> **US3673263A** — "The novel compound, dihydro-B-santalol, prepared by the process of this
> invention has a powerful, long lasting highly desirable odor characterized as strong
> sandalwood."

> **US3673266A** — "Dihydro-B-santalol, prepared by the process of this invention, has a
> highly desirable and useful odor characterized as strong sandalwood."

`B-` for beta is a rendering this corpus has ALREADY APPROVED — US3673261A sits in
sandalwood's 29 as `3-Normethyldihydro-B-santalol`. `dihydro-B-santalol` is neither santalol
already counted. It is sandalwood's 30th molecule, and n=2822 below is the wrong row to have
been arguing about.

## The method that actually worked

Not a better predicate. **When a tag is N molecules short, grep the undecided rows for that
tag's own chemistry and adjudicate those.** `santalol` -> 31 rows -> 4 candidates, in
seconds. The productive predicate is a queue-ordering heuristic and was never an instrument
for closing a specific tag.

## The 25, in full

**n=1346 · US12492356B2 · occ=2 · REJECT**  

> Symrise AG), which is described to exhibit a woody, tenacious sandalwood odor with a slight musk nuance and which is prepared based on a condensation of α-campholene aldehyde and propanal.

*anaphora — 'which' refers to a compound named in the preceding sentence. alpha-campholene aldehyde and propanal are STARTING MATERIALS ('prepared based on a condensation of')*

**n=1693 · US20090081140A1 · occ=2 · REJECT**  

> 5,189,013 in the main exhibit an at most weak sandalwood odor.

*fragment citing a patent number; no molecule named. 'at most weak' is diminution*

**n=1697 · US20090081140A1 · occ=2 · REJECT**  

> Furthermore, the intense, natural sandalwood note imparts excellent radiance and complexity to the present composition together with increased tenacity.

*composition-level ('imparts ... to the present composition'); no molecule named*

**n=2058 · US20160289595A1 · occ=1 · REJECT**  

> Since the Indian botanical species is now a protected species and is no more available on industrial scale, there is a real need for ingredients able to impart sandalwood notes as natural as possible and/or capable of improving the olfactive profile of the available natural oils.

*no molecule; a statement about supply of the botanical*

**n=2331 · US20220220051A1 · occ=1 · REJECT**  

> The compounds of general Formula (I) or of general Formula (VI) unexpectedly possess odorous properties, in particular a strong sandalwood note, some of which are good compared to those shown by the known derivatives of the prior art, for example Brahmanol.

*'compounds of general Formula (I)' is a scaffold. Brahmanol is prior-art comparison and a trade name*

**n=2384 · US20230365483A1 · occ=1 · REJECT**  

> It should be noted that also natural sandalwood oil note is the result of a number of different odorous notes reminiscent in turn of santalol, cedarwood oil or guaiac wood oil, or of sweet, balsamic, slightly ambery, spicy or animal notes or even of those milky notes reminiscent of freshly boiled milk.

*subject is 'natural sandalwood oil' — a mixture. santalol named only as comparison*

**n=2758 · US3481998A · occ=1 · REJECT**  

> Component: Percent by weight l-methyl-S-oxatricyclo[5.2.0.0*- ]nonane 1.00 Lemon 10.00 Bergamot 12.00 Lavender 30.00 Sandalwood 15.00 Patchouli 9.00 Labdanum 4.00 Musk Ambrette 15.00 Rosemary 1.00 This perfume composition exhibits a highly desirable and useful woody-lavender odor.

*formulation table: 'Sandalwood 15.00' is an INGREDIENT, not a descriptor. Odour is composition-level*

**n=2771 · US3499937A · occ=1 · REJECT**  

> (2) The polycyclic alcohol, 0 E 0, possesses a strong, sandalwood-type odor and it alone is responsible for the sandalwood-type odor and accompanying perfume value of the products obtained by hydrogenating bornylguaiacol.

*'The polycyclic alcohol, 0 E 0' — OCR damage where the name should be. bornylguaiacol is the precursor*

**n=2822 · US3580953A · occ=1 · APPROVE**  

> FIELD OF THE INVENTION This invention relates to a process for obtaining 3-endomethyl-3-exo(4-methyl 5' hydroxypentyl)norcamphor which is useful in synthesizing dihydro-[i-santalol, a compound having a valuable sandalwood odor.

*odour attributed to 'dihydro-[i-santalol' (OCR of dihydro-beta-santalol). Verbatim span is OCR-damaged; normalisation is post-review, per the derivatives rule. THE ONE CLOSE CALL*

**n=2998 · US3786075A · occ=1 · REJECT**  

> This compound has a complex odor which is reminiscent both of sandal wood and also of castoreum.

*'This compound' — anaphora, nothing named*

**n=2999 · US3786075A · occ=1 · REJECT**  

> All the compounds have a sandal wood, castoreum and amber note in their odors.

*'All the compounds' — anaphora/family*

**n=3211 · US3944621A · occ=2 · REJECT**  

> The π-tricyclene derivatives of our invention having a sweet, woody, oily and green sandalwood-like notes can be used to contribute sandalwood aromas.

*'The pi-tricyclene derivatives' — derivatives of X is a family*

**n=3306 · US4000050A · occ=1 · REJECT**  

> The use of the composition of Example VIII affords a distinct and definite "sandal cologne" aroma having a warm sandalwood-like character to the handkerchief perfume and to the cologne.

*composition-level, 'the composition of Example VIII'*

**n=3311 · US4000050A · occ=1 · REJECT**  

> The use of the composition of Example X affords a distinct and definite sandal cologne aroma having a warm sandalwood-like character to the handkerchief perfume and to the cologne.

*composition-level, 'the composition of Example X'*

**n=3319 · US4000050A · occ=1 · REJECT**  

> The cosmetic powder produced using column chromatography fractions 15-22 of Example I(B) has a sandalwood aroma with an oily nuttiness and acetophenone-like notes.

*odour belongs to a cosmetic powder from chromatography fractions; no molecule*

**n=3524 · US4149020A · occ=1 · REJECT**  

> The cosmetic powder produced using this material of Example IB also has a sandalwood aroma with woody, oily and santalol like nuances.

*composition-level, 'this material of Example IB'. santalol is a comparison*

**n=3553 · US4181631A · occ=1 · REJECT**  

> When blended with the aromatic oils, concentrates and chemicals used in the perfume arts, the novel α-hydroxyalkyl-4-t-alkylcyclohexanes of this invention impart natural sandalwood notes to such formulations.

*'alpha-hydroxyalkyl-4-t-alkylcyclohexanes' — alkyl is unspecified, a family. Also a blend effect ('when blended with')*

**n=3613 · US4229600A · occ=1 · REJECT**  

> Naturally, development of a synthetic perfume having an odor similar to α,β-santalol has been desired, and several products which are similar in odor to but quite distinct in structure from sandalwood oil have been offered on the market.

*comparison only ('an odor similar to'); alpha,beta-santalol is a mixture designation*

**n=3736 · US4318831A · occ=1 · REJECT**  

> Reduction of the esters, for example with alkali metals or alkaline earth metals in alcohols, or with mixed hydrides of metals of the first and third major groups, provided the carbinols 4a, b, and c, which have an intense sandalwood odor.

*'the carbinols 4a, b, and c' — anaphora to numbered structures, three compounds, no names*

**n=4045 · US4604488A · occ=1 · REJECT**  

> Description of the Prior Art It is known that hydrogenated catecholcamphene adducts obtained by the hydrogenation of an adduct of camphene with catechol have a sandal odor.

*'hydrogenated catecholcamphene adducts' — an adduct family, not a definite structure*

**n=4210 · US4891447A · occ=3 · REJECT**  

> 4,046,716, issued 1977) having the structure ##STR7## is reported as having a mild sandalwood odor.

*structure reference ##STR7##, no name*

**n=4308 · US5189013A · occ=1 · REJECT**  

> 4,173,585, but from a pure optically active starting product, possesses a weakly woody, resinous odor, with a very slight, sandalwood character.

*anaphoric fragment citing a patent number; no molecule*

**n=4353 · US5326748A · occ=1 · REJECT**  

> It possesses a very strong sandalwood note, very woody, with a natural sandal character and a dry woody note reminiscent of the odor of cedarwood, accompanied by an amber undernote.

*'It possesses' — anaphora. The molecule is in the PRECEDING sentence. Textbook passage-scope case*

**n=4398 · US5696075A · occ=1 · REJECT**  

> It is also indicated in this document that the compounds wherein R 2 and R 3 are both alkyl groups are preferred to their homologues which have one of these symbols representing hydrogen, since the sandalwood odor of the first is more powerful than that of the latter.

*R2/R3 variable groups — a family*

**n=4448 · US5929291A · occ=1 · REJECT**  

> The new cyclopropanated carbonyl compounds 1, 3, 4 as well as the new derivatives of the general formula IIb (with R 4 =Me) exhibit also useful olfactory properties, their odor belonging also to the amber/woody/ sandalwood family of odors.

*'compounds 1, 3, 4' and 'general formula IIb' — anaphora and family*
