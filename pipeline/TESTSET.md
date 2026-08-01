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
