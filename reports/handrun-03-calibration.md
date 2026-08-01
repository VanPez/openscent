# Hand-run 03 — sampled calibration, 25 patents

**Date:** 2026-08-01 · **First real yield measurement.** Sampled, not hand-picked.

## Method

Discovery via the Google Patents JSON search endpoint (no key, no account — see below). Query:
US-only, CPC **C11B 9/00**, priority ≥ 2001, phrase `"odour of"`. Took the first 25 distinct results,
fetched each patent's description section in-browser, split into sentences, and applied a v0 filter:

- must contain odour vocabulary (`odour|smell|fragrance note|olfactive`)
- must **not** match claim/definitional boilerplate
- must contain a description verb (`has|possesses|exhibits|described as|reminiscent…`)
- must name a compound or an Example number

## Result

| | |
|---|---|
| patents fetched | **25** (0 failures) |
| sentences scanned | 13,758 |
| sentences containing odour vocabulary | 663 |
| survived the v0 filter | **21** |
| genuinely usable on inspection | **~5** |

**≈ 0.2 clean assertions per patent.** Considerably lower than the "1–3 per patent" I guessed after
hand-run 02 — that estimate came from hand-picked patents and was optimistic.

### The good rows (verbatim)

> "2-ethyl-5,5-dimethyl-cyclohexanol exhibits a minty, fresh tobacco leaf, cresol, horse and/or
> animalistic odour" — US20210395639A1
> "ethyl 4-methylvalerate possesses a very attractive fruity odour that is not at all expected in
> patchouli" — US20180187123A1
> "3-(4-isobutyl-2-methylphenyl)propanal … possesses muguet odour characteristics" — USRE49502E1
> "Dihydrocinnamyl alcohol (3-phenylpropanol) possesses a fruity cinnamon odour" — US20080064625A1

Each is a compound name resolvable by OPSIN plus a verbatim descriptor span. Exactly the target shape.

Note the last one is **prefaced by a citation to *Common Fragrance and Flavor Materials*, 4th ed.,
Wiley-VCH** — Problem 4 observed in the wild. The patent is public domain; the sentence is quoting a
copyrighted book. `quotes_source` is not a hypothetical field.

### The false positives are now nameable — and mostly fixable

1. **"Odour Value" intensity metrics** — *"Lilial™ has an odour value of only 32,978"*. A number, not a
   descriptor. 3 of 21.
2. **Malodour test protocols** — *"Sweat Odour Test"*, *"Toilet Odour Test"*, *"Cooking Odour Test"*.
   These are experimental procedures for masking bad smells. 3 of 21.
3. **Definitional boilerplate that slipped the filter** — *"The odoriferous aldehyde is an aldehyde that a
   person skilled in the perfumery art would select…"*. 2 of 21.
4. **Composition/proportion claims** — *"If the proportion … exceeds 75 wt. %, a mixture … has a weaker
   odour"*. 2–3 of 21.
5. **Synthesis prose** — distillation yields that happen to contain a compound name. 1 of 21.

Categories 1 and 2 alone are ~6 of the 13 false positives and are trivially excludable by pattern
(`odour value`, `odour test`, `malodour`). Precision should reach 50–60% with an afternoon of tuning.

## What this means for scale

Precision is the *review* cost; **recall** sets the yield, and the v0 filter is strict — 663 → 21 means
real assertions were certainly discarded (anything phrased "It smells woody" fails the compound-name test).
So **0.2/patent is a lower bound**, not an estimate.

Rough projection, deliberately conservative:

- 5,660 US C11B 9/00 patents × ~0.2 = **~1,100 assertions**
- heavy duplication across patents → perhaps **400–700 distinct molecules**
- plus A61Q 13/00 formulation patents (1,976 US since 2010), which hand-run 01 showed are the better
  vein for **captives** specifically

Combined with the 218 already-sourced molecules in `../aroma-index/data/sourced/`, a corpus in the
**600–1,000 molecule** range with full per-row provenance looks realistic. That is not Leffingwell's 3,500.
It would, however, be the largest odour dataset anyone can use commercially — which is the entire point.

## Infrastructure note: the API key is unnecessary

USPTO's Open Data Portal requires an account, MFA, and pushed toward **ID.me identity verification**
(passport + video call). Not needed. Google Patents exposes a JSON search endpoint —
`patents.google.com/xhr/query?url=<urlencoded query>` — supporting `cpc=`, `country=`, `after=priority:`
and phrase queries, with no key. Combined with the full-text pages, the whole Phase 1 pipeline runs
credential-free.

Caveats: undocumented internal endpoint, may change or rate-limit; Google's terms discourage heavy
automated querying, so cache aggressively and stay moderate; and **filter `country=US`** — an unfiltered
query returns JP/CN/EP documents, which do not carry the US no-copyright status the licence claim rests on.

## Next

1. Tune the filter — add the `odour value` / `odour test` exclusions, loosen the compound-name requirement
   to recover recall, re-run on the same 25 and measure precision/recall against a hand-labelled set.
2. Harvest surface forms from the true positives to seed `ontology/odor_terms.tsv`. Phase 0 can begin from
   real data rather than guesswork.
3. Run the same calibration over **A61Q 13/00** to get the captives yield separately.
