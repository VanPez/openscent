# OpenScent — work log

**Entries are OLDEST FIRST — scroll to the bottom for the latest.** Times UTC.

---

## RESUME HERE — state as of 2026-08-01

**One blocker, and it is not technical.** The 2,588-patent fetch has never run. Everything downstream
waits on it. `corpus/patent-ids.json` holds the IDs and is deliberately not gitignored — discovery is
rate-limited and cannot casually be re-run.

```bash
scp ~/Documents/GenesisL1/openscent/corpus/patent-ids.json $OPENSCENT_HOST:/opt/openscent/corpus/
ssh $OPENSCENT_HOST
screen -S openscent bash -c 'python3 /opt/harvest.py fetch 2>&1 | tee /opt/openscent-fetch.log'
```
~2.5 h unattended. Ctrl+C kills the screen session as well as the process — reopen a new one to restart.

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
