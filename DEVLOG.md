# OpenScent — work log

Newest first. Times UTC.

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
