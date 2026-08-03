# The extraction test set — what it proves, and what it does not

`pipeline/testset.jsonl` · 29 labelled sentences · scored by `pipeline/score.py`

## ⚠️ Read this before quoting any score

The v2 filter scores **precision 1.00, recall 1.00** on this set.

**That number does not mean the filter is accurate.** Every rule in the v2 filter was written
*while looking at these 29 sentences*, and edited until they all passed. Scoring a model on the data
you tuned it against measures memorisation, not generalisation. A perfect score here was inevitable
the moment I started fixing disagreements, and it would be dishonest to report it as evidence the
extraction works.

What the progression actually shows is the *cost of each fix*, which is the useful part:

| version | precision | recall | F1 | what changed |
|---|---|---|---|---|
| v1 | 0.73 | 0.73 | 0.73 | first scored measurement |
| v2 | 1.00 | 0.82 | 0.90 | +4 exclusions, bare `note(s)` as odour head, heading path |
| v2 + `valued for` | 1.00 | 1.00 | 1.00 | commercial-register verbs; **and one label corrected** |
| v3 `NAMED` | 1.00 | 0.90 | 0.95 | rewrote the compound-name gate — see below |
| v3 + t10 relabel | 1.00 | 1.00 | 1.00 | **the label moved, not the filter** — read the t10 section |

**v3 exists because the gate was measured against real data for the first time.** Over the 3,379
candidates from the full 2,588-patent run, the most common token satisfying "this sentence names a
compound" was **`floral`** (624×), then `natural` 278, `material` 250, `chemical` 134, `herbal` 111 — the
pattern `[a-z]+al\b` matches an odour descriptor exactly as well as it matches *lilial*. Simultaneously it
**missed** real names: `[a-z]+ol\b` fails on the plural *alkoxynonenols*, and `-yne` was absent entirely,
so *1,3-undecadien-5-yne* did not match. Some rows were accepted for the wrong reason.

**This set could not have caught that.** It contains essentially one no-compound-name case (`t11`), and
"feedstock" happens not to end in `-al`. The blind spot documented above for recall applies equally to
over-acceptance.

## What this set IS good for

1. **Regression detection.** Any future filter change that re-breaks a known case fails loudly.
2. **Encoding failure modes as executable knowledge.** "Odour Value is a metric, not a descriptor"
   is now a test, not a sentence in a report nobody re-reads.
3. **Making filter changes arguable with evidence** rather than by assertion.

## What it is NOT good for

1. **Estimating real-world accuracy.** For that, score against patents that were never used for tuning.
2. **Measuring recall honestly.** This is the deeper problem: **every sentence here was surfaced by an
   earlier version of the filter.** The set physically cannot contain a sentence the filter has always
   missed, because nobody ever saw it. Recall against this set is an upper bound on optimism, not an
   estimate. The true recall is unknown and is probably materially lower.
3. **Anything statistical.** n=29, from ~12 patents, over-representing the handful I read closely.

## Two labels have now been moved — and the second one is a scope decision, not a fix

### t10 — anaphora (2026-08-01)

`t10` — *"In the latter case, the material was described as having an aldehydic, flowery-lily of the
valley, fatty type of odour"* — was labelled **keep**. The v3 `NAMED` gate rejects it: no compound name.

**Relabelled keep → drop.** Superficially this is `t11` again, but the cause is different and the
difference is the whole point:

| | can it ever resolve to a structure? |
|---|---|
| `t11` "this **feedstock**…" | **No.** A feedstock is a process input, often a mixture. No context helps. |
| `t10` "the **material**… in the **latter case**" | **Probably yes** — but only from a sentence this filter cannot see. |

So `t10` is not a question about the regex. It is a question about **the unit of extraction**: a sentence,
or a sentence plus its context? Labelling it *keep* asserts the filter ought to catch it, which requires
**anaphora resolution** — a real feature, not a rule tweak — and until that exists the score would be
penalising the filter for something it was never built to do, which makes the number meaningless.

**The cost is measured, not waved away:** of the 987 sentences v3 newly rejects from the full 2,588-patent
run, **85 (9%) look anaphoric** (*"the compound"*, *"the material"*, *"in the latter case"*). That is the
recall this decision forfeits. Revisit if the corpus comes up short — the fix is a context window around
each candidate, and the patents are already cached, so it costs no re-fetching.

**And note the trap this creates.** With `t10` relabelled, the set scores 1.00/1.00 again. That is not
evidence the filter improved — it is the same overfitting warned about at the top of this file, arriving
one layer deeper. A test set you relabel when it disagrees with you will always agree with you eventually.
The defence is the same as before: write down which one moved, and get a held-out set.

## One label was wrong, and that matters

`t11` — *"This feedstock itself possesses an odour in the direction of grapefruit and rhubarb"* — was
originally labelled **keep**. The filter rejected it for having no compound name, and the filter was
right: "feedstock" cannot resolve to a structure, so the row could never become a corpus entry.

**Relabelled keep → drop.** Recorded here rather than quietly changed, because the temptation in this
kind of work is to bend the filter until it agrees with the labels. Sometimes the label is what's wrong,
and the only defence against fooling yourself is writing down which one you changed and why.

## How to make this honest

The fix is a **held-out set**: label ~50 sentences from patents not used in any tuning, score once,
never tune against them. That requires the 2,588-patent fetch to have run, so it is blocked on the
same download everything else is waiting for.

Until then, treat the current filter as *"encodes every failure mode we have actually observed"* —
which is genuinely worth something — and not as *"is 100% accurate"*, which is not a claim being made.

## Running it

```
python3 pipeline/score.py        # summary + disagreements
python3 pipeline/score.py -v     # also list agreements
```

Score before and after any change to `ODOUR`, `DESCR`, `NAMED`, `HEADING` or `EXCLUDE` in `harvest.py`.
