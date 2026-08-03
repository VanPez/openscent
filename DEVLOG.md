# OpenScent — work log

**Entries are OLDEST FIRST — scroll to the bottom for the latest.** Times UTC.

---

## RESUME HERE — state as of 2026-08-01 (evening)

**The corpus is IN.** 2,588 patents cached on Hetzner (`/opt/openscent/corpus/raw/`, 173 MB, zero
failures). `extract` with the v3 filter gives **3,191 candidates** across 1,027 patents;
`corpus/extracted/candidates.json` is on the Mac.

> `$OPENSCENT_HOST` is the harvest box (`user@ip`). Set it in your shell — it is deliberately not
> committed, so this repo can go public unchanged:
> ```bash
> export OPENSCENT_HOST=user@your.host.ip
> ```

**Next: finish the candidate review.** Open `pipeline/review.html` in a browser, load a previously
exported `rows.jsonl` to resume (or `corpus/extracted/candidates.json` to start). A / R / S / left-arrow.
**Export before closing the tab — nothing is stored.**

2,205 candidates. Reviewing all of them gives exact precision *and* builds the corpus; two rounds of
50-sentence sampling could do neither (see the 2026-08-03 evening entry).

**Then:** ontology re-harvest over the full 2,588 (Phase 0 was blocked on corpus size — 60 patents gave
1,035 terms but only 14 occurring ≥30 times; it needed 500–1,000 and now has 2,588, so Mike's
"60–100 tags at ≥30 molecules each" target is finally testable) → OPSIN linkage → copyright-notice scan
→ only then is `odor_terms` mintable (`reports/phase0-1-pipeline.md` §2a).

**Not chasing Mike on gas/NFT questions** — they only bind once minting is close, which is several stages
away. See the 2026-08-02 entry.

**Do not run discovery again.** `corpus/patent-ids.json` (2,588 ids) must be present on the server at
`/opt/openscent/corpus/` before `fetch` runs; if it is missing, harvest.py silently falls back to
`/xhr/query` discovery, which Google refuses from Hetzner — that caused the 503 storm. *Known footgun:
`fetch` should refuse to run discovery unless asked explicitly. Not fixed yet.*

**Second source, independent of all the above:** `pipeline/pubchem.py`, run from the Mac. 1,453 usable
CIDs, linkage free (PubChem returns the CID), 39 rows flagged for expression review. See
`reports/pubchem-source.md`. Parry/Piesse checked and dropped — 27 of 30 already covered.

**Infrastructure constraint, learned the hard way:** Google Patents refuses Umbrel's IP outright and
refuses Hetzner for `/xhr/query` (though Hetzner serves patent *pages* fine). Search runs only from the
Mac; the bulk fetch runs on Hetzner. Do not spoof the User-Agent to get around a 503 — a project whose
entire selling point is clean provenance cannot have circumvention in its collection history.

**Read before touching the filter:** `pipeline/TESTSET.md`. The 1.00/1.00 score is overfitting, not
accuracy, and the set has a structural recall blind spot. Score `pipeline/score.py` before and after any
change to `ODOUR` / `DESCR` / `NAMED` / `HEADING` / `EXCLUDE` in `harvest.py`.

**Then, in order:** linkage via OPSIN → held-out accuracy on patents never used for tuning →
copyright-notice scan → only then is `odor_terms` mintable (`reports/phase0-1-pipeline.md` §2a).

**Sister project** `../aroma-index/` ships its pilot mint *without* descriptors and should not wait for
any of this. Its own open items are at the top of `../aroma-index/DEVLOG.md`.

---

## 2026-07-31 — Project created

Split out of `aroma-index` after Mike proposed a much larger build: a CC0 odour corpus assembled from
public-domain sources, an on-chain GL1F QSOR model trained on it, and a paper. Different scope, different
artifact, own folder.

**Why it exists.** Yesterday's licence scan (`../aroma-index/reports/license-scan.md`) established that no
permissively-licensed odour dataset exists at scale — every large expert-labelled set is NC, proprietary,
or a copyrighted book, and Leffingwell's files are now access-restricted behind a non-commercial condition.
The conclusion at the time was "free descriptors don't exist at scale." Mike's counter: they do, they're
just in **patents**, and nobody has mined them. US patent text carries no copyright, and a fragrance patent
must describe the smell because the smell is the invention.

That also solves the specific dead end from the pilot: the 37 molecules with no free descriptor source are
the modern captives — Iso E Super, Hedione, Norlimbanol, Cashmeran, the musks — which have no free
descriptors *precisely because* they are recent commercial materials, and were therefore patented.

**Design decisions taken up front:**

- **Extract, never generate.** The contamination vector is an LLM writing odour words from training data
  that includes GoodScents/Leffingwell. Mitigation: models return only verbatim spans, verified by a hard
  assert; a human-written lookup table does span→tag mapping. Rejection rate published as evidence the rule
  was enforced. This is a direct lesson from the sister project, where descriptors turned out to be
  model-generated with no traceable provenance.
- **Provenance per row, not per dataset** — one row = one (molecule, tag) assertion + one verbatim quote +
  one source + its licence. A challenge to one source deletes rows, not the corpus.
- **Phase ordering corrected.** Mike's plan gates everything on the ontology, but the ontology is defined
  as term-frequency *over the corpus*, which doesn't exist yet. Actual order: collect raw spans → derive
  vocabulary → tag. Collection is the long pole and can start without the vocabulary settled.

**Corrected myself on patent reliability.** I initially flagged patent odour descriptions as biased
advocacy. Ivan pushed back: the manufacturer knows the molecule and the smell is the commercial point, so
they have no reason to misdescribe it. He's right — the descriptions are chemically honest. The residual
bias is *emphasis* ("outstanding substantivity") and *selection* (what was worth patenting), not
fabrication. The hand-run remains worthwhile for a different reason: it tests **linkage**, not truthfulness.
The dangerous failure is resolving "Example 3" to the wrong structure, which yields an accurate description
bound to the wrong molecule and looks like a valid row.

**Open questions put to Mike:** whether note tiers belong in a CC0 scientific corpus at all (ours are a
judgement — a fitted rule reproduces them at 56% leave-one-out); whether he'll ship the 8-byte node read
gas optimisation (changes per-tag mint economics, hence affordable ontology size); and feature commitment
via MolNFT vectors vs Morgan fingerprints in Solidity.

**Next:** the 20-patent hand-run. Nothing gets built before it.

---

## 2026-07-31 (late) — Hand-run 01: two patents, retrieval works, targeting was wrong

Smoke test, n=2, deliberately spanning extremes. Written up in `reports/handrun-01-findings.md`.

- **Retrieval is free and unblocked.** Google Patents serves full text as plain text, no API key. ~96 KB per patent. (The USPTO bulk API still needs a key — Ivan's to register, since it requires an account.)
- **US3929677A (IFF 1975, Iso E Super family)** — rich odour text, *"PERFUME PROPERTIES Fruity, woody, pineapple-like"*, but two real problems: OCR noise on the old scan (`fruityamber`, `iso mer`, one passage garbled outright), and odour attributed to **isomer mixtures and GC peaks** rather than single structures. Some rows from old compound patents will be legitimately unresolvable — a chemistry judgement, not a parsing bug.
- **US11332693B2 (2022, woody-ambery composition)** — pristine text, but a *formulation* patent, so no novel structures. **Unexpected finding:** it names commercial captives with their IUPAC name *and* an odour description inline — KARANAL® with full nomenclature and *"dry, radiant, woody ambery"*, *"unusual characteristic dry, mineral effect… sharp, radiant, burning"*. That is a directly linkable triple, in clean text, for exactly the captives no free source describes.
- **The design doc dismissed A61Q 13/00 formulation patents as "mostly mixtures". That was wrong** — they may be the better vein for captives, because they must describe what they substitute for.
- **Untested and load-bearing:** post-2001 C11B 9/00 *compound* patents — clean text *and* novel structures. The plan assumes this cell works; nobody has checked it.
- **Decide before writing the verifier:** the text-normalisation rule for OCR'd sources (whitespace, hyphenation) must be deterministic and versioned, applied identically to source and span, or the verbatim audit trail breaks.

---

## 2026-08-01 — Hand-runs 02–04: yield measured, vocabulary harvested, two blockers dissolved

Three runs in one morning. Reports in `reports/handrun-01-findings.md` (02 appended) and
`handrun-03-calibration.md`, `handrun-04-vocabulary.md`.

### The USPTO API key turned out to be unnecessary

USPTO's Open Data Portal wanted an account, MFA, and then pushed into **ID.me identity verification** —
passport plus a video call, 31-minute queue. For a patent *search* key. Abandoned it, because
**Google Patents exposes an undocumented JSON search endpoint** that answers the same query:

```
patents.google.com/xhr/query?url=<urlencoded>   e.g. cpc=C11B9/00&country=US&after=priority:20010101
```

No key, no account, no identity check. Combined with the full-text pages, **the entire Phase 1 pipeline
runs credential-free.** Also avoids handing a third party a passport scan, which matters given the
pseudonymity decision.

Pool sizes measured: **C11B 9/00 US all years — 5,660**; +`odor` since 2010 — 2,088; A61Q 13/00 US since
2010 — 1,976; exact phrase `"odour of"` — 243.

Caveats: undocumented endpoint, may change or rate-limit, Google's terms discourage heavy automation —
cache, stay moderate. And **always filter `country=US`**: unfiltered queries return JP/CN/EP documents,
which do not carry the US no-copyright status the whole licence claim rests on.

### Hand-run 02 — the load-bearing cell works, but yields less than assumed

US9109187B2 (Firmenich 2015, oud odorants). Modern text is pristine — the pre/post-2001 split is real.
Genuine rows exist: *"3-(n-propyl)phenol … has a leather-like, phenolic and ink-like odor"*. Two new
problems though:

- **Problem 3 — claim-language noise.** ~14 odour mentions, ~2 descriptive. The rest is legal boilerplate.
  Distinguishing descriptive from definitional use is harder than finding odour words, and is where an
  LLM earns its place (locating, never generating).
- **Problem 4 — patents describe *other people's* compounds, citing literature.** Good news: established
  molecules are covered too, not just novel ones. Caveat: the description may originate in a copyrighted
  paper the patent quotes. Add `quotes_source` to the schema so it's visible rather than laundered.

### Hand-run 03 — first real yield number

25 sampled patents → 13,758 sentences → 663 containing odour vocabulary → 21 passing a v0 filter →
**~5 genuinely usable. ≈0.2 clean assertions per patent**, well below the 1–3 guessed from hand-picked
patents. Precision is the review cost; **recall sets yield and the v0 filter is strict, so 0.2 is a floor.**

False positives are now nameable and mostly cheap to fix: *odour value* intensity metrics, malodour test
protocols (*Sweat/Toilet/Cooking Odour Test*), definitional boilerplate, composition claims, synthesis prose.

Conservative projection: 5,660 × 0.2 ≈ 1,100 assertions → **400–700 distinct molecules** after duplication,
plus formulation patents for captives, plus the 218 already sourced → a **600–1,000 molecule** corpus.
Not Leffingwell's 3,500 — but the largest anyone can use commercially, which is the point.

### Hand-run 04 — Phase 0 started from real text, and the tier question closed

60 patents, 4.64 M characters, 0 failures. Harvested every word preceding an odour-head noun.
**1,035 distinct terms; only 14 occur ≥30 times.** Raw output in `ontology/harvested-terms-v0.tsv`.

- The vocabulary is recognisably perfumery: floral · muguet · green · fruity · spicy · fatty · woody ·
  fresh · citrus · sweet · musk · ambery · tobacco · aldehydic — plus **radiant** and **transparent**,
  working perfumer's words that nobody would invent from first principles. Validates the method.
- **Mike's Phase 0 target (60–100 tags at ≥30 molecules each) needs 500–1,000 patents, not 60.** Concrete
  scale requirement the plan never quantified. Feasible, but Phase 0 cannot complete on a small corpus.
- **Malodour contamination is large and now measured**: toilet 25, sweat 23, mask 22, cooking 16, urine 11,
  faecal 12. A61Q 13/00 includes deodorants — patents describing smells they intend to destroy. Exclude
  those subclasses *at query time* or the ontology fills with bad smells.
- Hedonic terms rank absurdly high (*unpleasant* 127, *pleasant* 72) and are not descriptors. Separate axis.

**The tier question, settled negatively.** `base` 89, `top` 80, `middle` 53, `heart` 32 ranked high, raising
a real possibility: if patents assert *"compound X is a top note"*, tiers become citable rather than
judgement. Tested across all 60 patents: **0 direct per-compound tier assertions.** The only two hits were
generic (*"heart note such as floral characters"*). Patents use tier language for accord architecture,
never to classify a molecule.

So tiers are **not sourceable and not computable** — second independent line of evidence after the fitted
rule reproducing the curated 99 at 56% leave-one-out. This answers one of the three open questions to Mike
without needing his reply. Sister project's response: a separate, honestly-named `volatility_band`
(declared MW convention, 67% agreement with the curated tier) — see `../aroma-index/data/VOLATILITY_BAND.md`.

### Next

1. Extend the stop list; exclude deodorant/malodour subclasses at query time; re-harvest.
2. Tune the extraction filter (`odour value` / `odour test` exclusions; loosen the compound-name test to
   recover recall) and measure against a hand-labelled set.
3. Scale the harvest to 500–1,000 patents — the real prerequisite for Phase 0, a time cost rather than an
   unsolved problem.
4. Then draft the 60–100 tag ontology and the `surface form → tag` mapping table.

---

## 2026-08-01 (later) — Test set, and the mint decision reverses

### The extraction filter is now measured rather than argued about

`pipeline/testset.jsonl` — 29 real sentences from 12 named patents, each labelled with a reason.
`pipeline/score.py` imports `harvest.py` dynamically and mirrors its accept path, so the thing being
scored is the thing that runs. Write-up in `pipeline/TESTSET.md`.

| version | precision | recall | F1 |
|---|---|---|---|
| v1 | 0.73 | 0.73 | 0.73 |
| v2 | 1.00 | 0.82 | 0.90 |
| v2 + `valued for` | 1.00 | 1.00 | 1.00 |

**The 1.00/1.00 is overfitting and is not a quality claim.** Every v2 rule was written while looking at
these 29 sentences and edited until they passed; a perfect score became inevitable the moment I started
fixing disagreements. Worse, the set has a structural recall blind spot — **every sentence in it was
surfaced by an earlier version of the filter**, so it cannot contain a case the filter has always missed.
Recall against it is an upper bound on optimism. The honest fix is a held-out set of ~50 sentences from
patents never used for tuning, scored once — blocked on the fetch.

What the exercise genuinely bought: two real gaps found by measurement rather than intuition (bare
`note(s)` as an odour head noun, which had been silently missing the KARANAL captive case — exactly what
the formulation-patent source exists to capture; and commercial-register verbs like *valued for* /
*prized for*, which patents use about established materials), plus four exclusions each traceable to a
scored false positive.

**One of my labels was wrong, not the filter.** `t11` — *"This feedstock itself possesses an odour…"* —
was labelled keep; the filter rejected it for having no compound name and was right, since "feedstock"
can never resolve to a structure. Relabelled keep→drop and recorded in TESTSET.md rather than quietly
changed. The failure mode in this kind of work is bending the filter until it agrees with the labels;
the only defence is writing down which one you moved.

### Patent-sourced descriptors are mintable — and the old ones still aren't

Ivan's question: if the descriptors come from public-domain patents, can they go on the token after all?
**Yes**, and it resolves a tension left open this morning. Full reasoning in
`reports/phase0-1-pipeline.md` §2a.

The mint strip was **never a licensing decision** — it was provenance. The `rows2.json` descriptors are
model-generated with no traceable source and 37 of 95 have no corroboration and never will. Patent-extracted
descriptors invert every term: named source document, char offset, verbatim span, checkable by a stranger.

**`descriptors` stays dead.** Reviving the name would blur the exact distinction the project exists to
draw. The replacement is `odor_terms` + `odor_evidence`, which cannot be separated from each other. The
difference is what the token asserts: *"this smells woody"* (unbacked, permanent) versus *"US11332693B2
says this smells woody, here is the sentence"* (checkable in thirty seconds, true regardless of whether
the perception is). No other on-chain molecular record carries a public-domain citation per perceptual claim.

It is also the answer to the 37 — captives lack free descriptors *because* they are recent commercial
materials, which is why they were patented.

**Two caveats recorded as schema fields, not as good intentions:** `quotes_source` (patents quote
copyrighted literature — one test-set sentence quotes Wiley-VCH; the row is usable, but the provenance
chain must be visible rather than laundered) and `copyright_notice_present` (USPTO rules permit a
copyright notice on portions of a specification — rare, but "US patents are public domain" is a
generalisation, so scan rather than assume).

**Not actionable yet, and the pilot mint should not wait for it.** Preconditions in order: the
2,588-patent fetch → linkage via OPSIN → held-out accuracy → copyright-notice scan.

---

## 2026-08-01 (evening) — The fetch finally launched, and PubChem turns out to be weaker than the scan said

### The fetch: three failures, none of them the code

Wasted an afternoon on an operational sequence, worth recording because each failure was avoidable:

1. **Pasting a multi-line block containing `ssh` into one terminal.** Everything after the `ssh` line was
   consumed by the remote shell, so commands intended for the Mac ran on Hetzner and vice versa.
2. **The `scp` of `patent-ids.json` had silently failed** (target directory didn't exist). harvest.py's
   fallback is to run *discovery* — which hits `/xhr/query`, the one endpoint Google refuses from
   Hetzner. Result: a 503 storm, a partially-written `patent-ids.json` on the server (which a later run
   would have silently reused), and a temporary throttle that reached the Mac too.
3. **`screen` looked frozen.** It wasn't — Python block-buffers stdout into a pipe, so `| tee` swallowed
   ~8 KB of progress. `python3 -u` fixes it. Diagnosis was `ls corpus/raw | wc -l` twice, 15 s apart.

**Design lesson, not just an ops lesson:** a fallback that quietly does something expensive and blockable
when an input is missing is a footgun. `fetch` should refuse to run discovery unless asked explicitly.
Not changed yet — noted so it doesn't get rediscovered.

Cooling off for an hour, re-verifying with a two-request smoke test, and launching in a fresh screen
worked. ~3 s/patent, no failures in the first several hundred.

### PubChem: linkage solved, licence weaker than advertised

Built `pipeline/pubchem.py` while the fetch ran — deliberately a different host and endpoint so it cannot
interfere. Two PUG View headings, no key: `Odor` and `FEMA Number`. Write-up in `reports/pubchem-source.md`.

**Fetch matched the scan exactly: 2,358 odour annotations.** Endpoint has not drifted.

```
rows 3135 → excluded 903 (odourless / thresholds / placeholders)
          → dropped   150 (more than one CID — refused rather than guessed)
          → kept     2082  across 1453 distinct CIDs
```

**What it fixes: linkage, completely.** PubChem returns `LinkedRecords.CID`, so the patent pipeline's
worst failure mode — "Example 3" resolving to the wrong structure, yielding an accurate description bound
to the wrong molecule — cannot occur. No OPSIN stage for this source.

**What it does not fix, and this is the finding.** The licence scan marks the `Odor` heading ✅ public
domain because 2,356 of 2,358 annotations come from HSDB, an NLM work. That is true of the *database* and
not of the *sentences*. HSDB summarises prior literature, and the very first record cites
**The Merck Index (Merck & Co., 1996)** — a copyrighted book behind a PD wrapper. Same `quotes_source`
problem as hand-run 02, different door.

Every row now carries `references`, `quotes_source`, `reference_may_be_copyrighted` (heuristic publisher
match) and `reference_flag_hits` (which strings matched, so the call is checkable). Then:

1,148 kept rows (55%) cite a possibly-copyrighted work, mostly Merck Index / Budavari.

**I then over-corrected, and Ivan called it.** My first take treated a flagged citation as disqualifying
and put the usable set at 83 food-grade molecules. Ivan pushed back — *does a Merck cite really make it
unusable?* — and the data says no. Copyright protects **expression, not facts**; flagged spans run to a
**median of 3 words** and 87% are ≤5. "Fragrant and penetrating odor" is a short phrase stating a fact,
with no protectable expression in it. HSDB citing Merck is scientific attribution, not reproduction.
*Cites a copyrighted work* ≠ *copies protected expression*, and conflating them would have thrown away
1,148 good rows.

**The real discriminator is span length, because length brings creativity.** The tail is where it bites:

```
20w  BENZYL ACETATE — "Powerful but thin, sweet floral fresh, fresh and light, fruity odor
     reminiscent of Jasmin, Gardenia, Muguet, Lily and other flowers"   [Merck Index p.189]
```

That is authored prose in Arctander's register, not a fact statement. So rows now carry `word_count` and
`expression_risk`, set to `review` only where a flagged citation meets a span over 10 words:

```
kept rows            2082   (1453 CIDs)
expression_risk low  2043
needs hand review      39   (27 FEMA-listed)
FEMA-listed rows      521   ( 277 CIDs)
```

**39 rows to read, not 1,148 to discard.** Usable set is 1,453 CIDs / 277 FEMA-listed — an order of
magnitude better than my first number. Second time this project has caught me being conservative in a way
that destroys data; the discipline of writing down *which* thing moved (per TESTSET.md) is what surfaced it.

**Patents remain the main event.** PubChem's value is (a) cross-checking patent rows for the same CID and
(b) common molecules nobody patents. It does nothing for the 37 captives.

### Parry / Piesse: checked, dropped, and the reason is redundancy not licensing

Ivan asked whether the pre-1929 perfumery literature was worth mining, then answered his own question —
*wouldn't it already be on PubChem?* It is. Of 30 classic Parry-era synthetics, **27 already have a
PubChem odour row**, and the misses are naming artefacts (HELIOTROPIN = PIPERONAL, which is present).
Parry wrote about exactly the compounds that are now century-old commodities — the population a
toxicology database covers thoroughly. Appendix in `reports/pubchem-source.md`.

Licensing was never the obstacle: archive.org serves Parry vol. 1 (1918) as
`possible-copyright-status: NOT_IN_COPYRIGHT`, 1.6 MB of plain text, no key. Two other strikes: **24% of
words at OCR confidence ≤30** (archive.org publishes the histogram — worse than the pre-2000 patent scans
handrun-01 already struggled with), and linkage *regresses*, since Piesse describes materials that never
resolve to a CID and Parry's period names need a hand-written synonym table.

Revisit only if Phase 0 turns out vocabulary-starved — 1918 prose is richer per sentence than HSDB, so it
is a source of *terms*, never of coverage.

### And I was too harsh on PubChem's vocabulary

The Parry check incidentally disproved my own "toxicological, not perfumery" line. Sampled from the
FEMA-listed rows: *"Sweet rose odor"*, *"Heliotrope odor"*, *"Odor similar to that of bergamot oil and
French lavender"*, *"warm, woody, floral … with balsamic and sweet tone"*. That is perfumery register.
The complaint is true of the corpus as a whole — nickel carbonyl and dioxane are in there — and false of
the aroma subset, which is the part anyone would use. `fema_listed` separates the two cleanly, which is
the argument for having built the join. Corrected in the report rather than left standing.

**Second time today a claim of mine survived only until it was measured** (the other being the Merck
citation). Both were conservative errors, and conservative errors in this project destroy data rather
than compromise it — which makes them feel safe and cost more than they look.

---

## 2026-08-01 (night) — Corpus landed; the compound-name gate turned out to be measuring nothing

### The fetch completed clean

**2,588 of 2,588, 173 MB, zero failures, zero too-short rejects.** Better than the hand-runs predicted.
~67 KB per patent against handrun-01's ~96 KB estimate — post-2001 text is tighter than the 1975 scan.

First `extract` on the full corpus: 992,396 sentences → 27,308 containing odour vocabulary → 2,973
excluded → **3,379 candidates**.

### `NAMED` was broken in both directions and neither the test set nor I could see it

I first called 3,379 "6.7× the projection". **That comparison was wrong** — it measured *candidates*
against a projection of *usable rows*. Corrected: handrun-03's v0 produced 0.84 candidates/patent of
which ~24% were usable (0.20/patent). v3 now gives 1.23 candidates/patent → **~765 usable at the same
survival rate**, which sits inside the original 600–1,000 molecule projection. Nothing was broken. The
24% survival is itself an assumption resting on five hand-read sentences, and is the next thing to
measure rather than trust.

But checking the number surfaced something real. The most common token satisfying "this sentence names a
compound" across the 3,379 candidates:

```
floral 624 · natural 278 · material 250 · chemical 134 · herbal 111 · animal 41
(genuine: acetate 94 · lilial 65 · propanal 51 · menthol 48 · damascone 42)
```

**The gate that proves a molecule is named was being satisfied by the words that describe the smell.**
`[a-z]+al\b` matches *floral* exactly as well as *lilial*.

And it failed the other way at the same time: `[a-z]+ol\b` misses the plural *alkoxynonenols*; `-yne` was
absent, so *1,3-undecadien-5-yne* never matched. Several rows were accepted **for the wrong reason** —
right answer, broken reasoning — which is worse than a wrong answer because it looks fine.

**v3** replaces it with four independent signals (explicit `Example N` / `Formula (I)`, systematic-name
locants, ®/™ trade names, chemical suffixes minus a published stoplist). One bug in my own v3, found by
inspecting what it newly rejected rather than by reasoning: patents write *"compounds of Formula (I)"*
with parentheses, and my rule demanded a bare numeral — it missed every parenthesised reference. That fix
alone recovered 164 rows.

Full-corpus re-run: **3,191 candidates.** Net movement small, but ~987 out and ~799 in — roughly a
quarter of the set changed identity. No re-fetching; this is exactly what the fetch/extract split bought.

### t10 relabelled, and the score is now actively misleading

v3 dropped test-set recall to 0.90 on `t10`: *"In the latter case, the material was described as having
an aldehydic, flowery-lily of the valley, fatty type of odour."*

Same principle as `t11` (a row needs a resolvable molecule), different cause. `t11`'s "feedstock" can
**never** resolve. `t10`'s "the material" **probably can** — from a sentence the filter cannot see. So it
is not a regex question but a **scope** question: is the unit of extraction a sentence, or a sentence plus
context? Labelling it *keep* asserts the filter should do anaphora resolution, which is a feature.

**Relabelled keep → drop**, cost measured: of the 987 sentences v3 rejects, **85 (9%) look anaphoric**.
That is the recall forfeited, and it is recoverable later — the patents are cached, so a context window
costs no re-fetching.

Score returns to 1.00/1.00, **and that is now worse than meaningless**: I moved a label until the set
agreed with the filter. A test set you relabel on disagreement will always agree with you eventually.
Written into TESTSET.md next to the number rather than left for someone to discover.

### Held-out set: built, and two honesty problems with it stated up front

`pipeline/heldout.py`. Two rules it enforces mechanically:

1. **It samples rejected sentences too.** A set drawn only from `candidates.json` cannot contain a
   sentence the filter has always missed — the exact flaw in the current test set. Stratified 25/25
   across accept/reject, reweighted by true stratum sizes at scoring time (only ~12% of odour-bearing
   sentences are accepted, so a uniform 50 would carry ~6 accepted rows and say nothing about precision).
2. **Blind labelling.** `sample` writes sentences with no decision attached and the filter's answers to a
   separate key file. Fixed seed, so the draw cannot be quietly re-rolled.

**Known contamination, recorded rather than hidden:** handrun-03 sampled 25 patents and handrun-04 sampled
60, and **neither list was written down**. Those runs produced the EXCLUDE rules and stop lists, so up to
~85 unidentifiable patents may survive the exclusion list. Weaker contamination than the test set's
(aggregate statistics, not per-sentence tuning) but real, and it qualifies any number this set produces.
**Lesson for future runs: record the sampled IDs.**

If a rule is later changed because of what this set reveals, the set is burned and a new one must be drawn.
That has to be a DEVLOG entry, not a quiet re-score.

---

## 2026-08-02 — Read the main GenesisL1 chat back to 30 Jul. Nothing blocks us; several things clarify.

Context gathering, not project work. Recorded so it isn't re-derived, and because two items correct
things written elsewhere in this repo.

**MolNFTs are transferable — settled by evidence rather than by assertion.** Joe had suggested they are
one-address / not built for exchange, which would have reopened the whole NC-licence question. The chat
closes it: yesterday's poll reads *"to distribute **transferrable** molnft to community… 2. Send Molnft
pdbbank to community members. This will be just an **ownership transfer**"* (8 of 9 voted for that).
The entire thread presumes transferability. **`../aroma-index/reports/license-scan.md` stands unchanged**
and NC sources stay ruled out. Ivan's call to keep assuming Mike's original statement was correct.

Worth noting the distinction that made this moot for us anyway: even if the tokens were non-transferable,
NC data still could not enter a **CC0** corpus. CC0 promises downstream users no restrictions; NC imposes
them. The tradeability question only ever affected aroma-index's display layer, never the corpus licence.

**GL1F is not a model — correction to `../GLOSSARY.md`, now fixed.** Mike: *"GL1F is not a model, it is a
studio with runtime, 4 clients and canonical format identical for each client."* A `.gl1f` holds weights
plus a features register; deploy on-chain or run locally. Determinism is claimed as absolute, with one
known client bug making rare models diverge from the EVM runtime, to be fixed alongside a GL1F paper Mike
is writing. **He has his own paper in flight** — ours should not collide with it.

**A dataset NFT service is coming, and it is the intended home for this corpus.** *"Provenance score is
absolute as long as you use dataset from upcoming dataset NFT service. Verifiable dataset as input and
training data towards model whose output is byte to byte identical via any execution path."* No date.
This is Mike's Phase 2, so we may not need to build corpus publication ourselves.

**DOI issuance is planned but blocked upstream.** Joe asked about the legal backbone for assigning DOIs;
Mike: *"this is for us to issue doi and this is planned but first should solve software task and to solve
it we need ipfs sidecar first."* **Zenodo remains our route**, as the build plan already assumed. No
change for us.

**One genuine risk, raised by Joe and unanswered:** publishing on L1 first may compromise later journal
publication, since results normally cannot be published twice. Most journals accept preprints, some do
not. Cheap to check now, expensive after the fact. Parked, not dismissed.

**Precedent and possible funding.** `app.molnft.org` has already minted PDB and AlphaFold structures, so
this class of dataset is not novel to the chain. ~99k L1 of unspent mint budget was returned to the
community pool this week, alongside ~$3k/week in Base LP fees. A governance proposal is therefore an
available route if this ever needs funding.

**Deliberately NOT chasing Mike.** The two open asks — the 8-byte node read gas optimisation and the
MolNFT-vectors-vs-Morgan-fingerprints commitment — only bind once minting is close, and we are several
stages away (held-out accuracy → OPSIN linkage → ontology). He spent the week on the explorer,
CoinGecko/CMC submissions, the bridge and spam. Joe's read, which matches the evidence: don't wait on
Mike, show him something finished.

---

## 2026-08-03 — **precision 0.16.** The first honest number, and it is not the one we were quoting

### The result

50 sentences from patents never used for tuning, drawn blind, labelled by Ivan without sight of the
filter's answers, scored once.

```
precision 0.16    recall 1.00    F1 0.28      <- HELD OUT

accept stratum 25: kept  4, dropped 21
reject stratum 25: kept  0                     <- no detected misses
```

**Against 1.00/1.00 on the tuning set.** That gap is the entire value of the exercise, and it is the
number to quote from here on. Everything scored against `testset.jsonl` was measuring memorisation.

**Recall 1.00 is weaker evidence than it looks.** It means zero misses in 25 sentences sampled from the
31,409 the filter rejected. A true keep-rate of 1% among rejects would produce an expected 0.25 hits in a
sample that size, so this is "no evidence of misses", not proof of none. Precision is the solid number
here; recall is a floor with wide error bars.

### It does not break the plan — it prices it

Hand-run 03 projected ~24% of candidates would survive human review. Measured: **16%**. Same order.
Applied to 4,068 candidates that is **~650 usable assertions**, inside the original 600–1,000 molecule
projection. Precision was always specified as the *review cost*, not a correctness claim.

What changed is that the cost is now measured rather than assumed: **to obtain ~650 rows a human reads
4,068 sentences.** That is the real finding, and it makes the case for one round of tightening before
anyone starts reviewing.

### Two failure modes, both diagnosable from the 21 false positives

**1. Claim language dominates — 15 of 21.** Definitional patent prose that mentions odour without
describing any particular molecule's smell. The EXCLUDE list catches some of these shapes and evidently
not enough. This is hand-run 02's "Problem 3" reappearing at scale.

**2. The HEADING path cannot produce a valid row, and the reason is structural — not a tuning issue.**
Four false positives arrived via `kept (heading)`, including the two cases the rule exists to catch:

```
"Odor characteristics: scallion, pickle."
"Odor characteristics: pickle, oshinko."
```

Both correctly dropped, because **a descriptor-only heading by definition names no molecule.** Under
sentence-level scope the rule can never yield a row; it can only work with a context window reaching the
preceding line. So this morning's discovery that extract() had been silently missing the heading path was
real, but fixing it added ~877 rows that are, on this evidence, mostly waste. The bug was worth finding;
the rule it restored is not worth keeping in its current form.

Note the irony: `t10` was relabelled yesterday precisely because anaphora is out of scope. The heading
path is the same problem wearing a different hat, and it survived because the test set rewarded it.

### The four keeps — what a row actually looks like

```
"Menthone has a typical strong minty smell and flavour ... isomenthone is minty, cam..."
"In particular, 6-(2-ethoxyethyl)-1,3,4-trimethylcyclohex-1-ene is used to impart a fruity note..."
"In particular, 3-methoxy-2,3-dimethyl-pentane is used to impart an ethereal, sweet, mouldy, hay..."
"However, in addition to its too high volatility, l-menthol has several other drawbacks..."
```

Named structure, explicit descriptor, one sentence, no context required.

### This set is now spent

Per the rule written into `heldout.py` and TESTSET.md: changing a filter rule because of what this set
revealed **burns the set**. A fresh 50 must be drawn and labelled again.

Plan is **one consolidated round, not iterative tuning** — kill or context-window the heading path,
extend the claim-language exclusions from the 15 worked examples, then re-draw and label once. Recall
1.00 says there is slack to spend on tightening. Two labelling sessions, not five.

`pipeline/label.html` exists now — a blind, single-file labelling UI, keyboard-driven. It turned a
40-minute JSON-editing chore into something repeatable, which is what makes a second round affordable.

FEMA is used as a *selection layer only*: the number joins on CID to give `fema_listed` (renamed from
`food_grade`, which overclaimed — a FEMA number is an industry GRAS designation, not a safety
certification, and acetone is FEMA 3326). The flag is **asymmetric**: presence suggests an aroma
molecule, absence implies nothing, since fragrance-only materials like Iso E Super and the musks are
never FEMA-listed. Metadata for ranking review effort, never a filter. It separates
perfumery-relevant rows from toxicological noise. FEMA's own library prose is proprietary and is never
fetched. 2,394 CIDs carry a FEMA number.

### The verbatim assert earned its keep

`extract` crashed on ANID 1392 (NICKEL CARBONYL, *`LIKE "BRICK DUST"`*). The data was fine — **the check
was wrong**: it compared a JSON-*decoded* string against JSON-*encoded* file text, so any value containing
a quote, backslash or newline failed while being perfectly verbatim. 3 of 3,135 strings affected. Fixed by
re-encoding before comparison; 0 fail now.

More useful: chasing it exposed a **real** hole. The extractor was calling `.strip()` before storing,
which would silently make stored text differ from source in the one field that must be exact. Removed.
As it happens 0 strings had surrounding whitespace, so nothing was corrupted — luck, not design.

This is the second time a hard assert has caught something a review pass would have waved through. The
pattern holds: **enforce, don't intend.**

---

## 2026-08-03 (evening) — Round 2: 0.20 / 0.25. The measurement, not the filter, is the problem

```
round 1 (v3)   precision 0.16   recall 1.00   accept 25: kept 4   reject 25: 0 misses
round 2 (v4)   precision 0.20   recall 0.25   accept 25: kept 5   reject 25: 1 miss
```

**Neither difference is real.** Precision moved by one sentence out of 25; Wilson 95% intervals are
[0.06, 0.35] and [0.09, 0.39], almost entirely overlapping. Recall looks catastrophic and is worse than
meaningless — it is driven by a single sentence in a stratum weighted 1,306x against the accept stratum's
87x:

```
0 misses in 25 rejects -> recall 1.00
1 miss                 -> recall 0.25
2 misses               -> recall 0.14
```

Two rounds of the same filter family produced opposite-looking recall because one sentence fell
differently. **That is a design fault in the evaluation, and it is mine.** 25 samples from 32,657 rejects
with rare positives was never going to estimate recall. It should have been obvious when the stratum
weights were written down.

So v4 is neither vindicated nor refuted. 80 minutes of labelling bought failure-mode diagnosis — which was
worth having — and no usable score.

### The one hard finding: the 320-character cap is throwing away real rows

`h44`, rejected on **length**, 667 characters, and correctly labelled keep:

> "Dimethylester (Product of Example II.1): Time elapsed Odor impression <1 min. gob odor, fruity
> (banana) 10 min. gob-sulfurous odor, fruity (banana) 1 h gob odor, fruity (banana) 24 h fruity
> (banana) Diethylester (Product of Exa..."

Patent odour *tables* run long and are dense with exactly the assertions we want. The cap was set to keep
sentence-splitting sane, and it is silently discarding the highest-density source in the corpus. Not fixed
yet — deliberately, since it changes the review pool mid-review.

### Decision: stop sampling, review everything

The full review of 2,205 candidates gives **exact** precision with no sampling error, and produces the
corpus rather than another estimate. Sampled evaluation has told us what it can.

Recall stays unmeasured. Measuring it needs a different design — sampling *near-miss* rejects rather than
uniform ones, e.g. sentences that pass every test but one. Worth doing after the review, not before.

### `pipeline/review.html`

Single-file review UI, same shape as label.html. Loads candidates.json, approve/reject/skip, and on
approval captures molecule + descriptors **selected out of the sentence**. The rule is enforced rather
than trusted: the molecule field refuses to save text that is not a verbatim substring, and descriptors
can only be words present in the sentence. Rejections are kept in the export — they are the precision
measurement.

Descriptor highlighting uses 96 terms: the 26 class-D terms hand-run 04 harvested from the corpus, plus
conventional perfumery words. Only 1,312 of 2,205 candidates contain one, which is itself a signal about
how thin the ontology vocabulary still is.

**Noted while reviewing, not acted on:** `C 1-4 alkyl` (a substituent *range* in a Markush claim) trips
NAMED_LOCANT, which reads `\d-\d` as systematic nomenclature. Only ~6% of the queue looks Markush, so it
is not worth pre-filtering, but it is a real defect in the rule.
