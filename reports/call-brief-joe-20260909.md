# Call brief — Joe, 2026-09-09

Numbers from `pipeline/status.py`, run this morning. Nothing here is remembered.

---

## What he actually said, and what he means

> *"Ich glaube du bist wirklich auf ein wichtiger Spur, aber ich habe irgendwie deine
> Fahne nicht mehr im Blick."*
> *"Mir ist einfach aufgefallen dass du ganz individuell schon ne ganze Datensatz gebaut
> hast, und bin mir nicht sicher ob M oder ich dich aktuell begleiten sollen, aber ich bin
> sehr gerne dabei falls du mein Input brauchst."*

**He is asking what his role is, not criticising your notes.** He has watched you build a
dataset alone for six weeks and can't tell whether he's still needed. The four-page paper
is his offered way back in.

So the call has one job: **tell him what you want from him specifically.** "Follow along
better" is not an answer he can act on.

---

## Correct this early

You told him on 31 August: *"I scraped the US and EU patent offices."*

**That is not what the project does, and the difference is the licensing claim.**

- **EP/WO patents are ruled out**, in `harvest.py`'s comments since day one — non-US
  patents do not carry the US no-copyright status CC0 rests on.
- What actually happens: **EPO OPS is the search API used to FIND US patents**; only US
  documents are fetched, from Google Patents.

One sentence fixes it. Leave it and it propagates — it is exactly the kind of thing that
gets repeated back by someone summarising your work to a third party.

---

## Where it stands, if he asks

```
5,346 US patent documents · 6,686 candidate rows
955 decided by hand (627 approve, 326 reject) · 5,731 to review
1,193 distinct molecules · 20 of 67 tags at >=30 molecules
648 molecules now carry computed chemical features
```

Target is 60-100 tags. **We are at 20, and honest about it.** Five tags are within seven
molecules: sandalwood 28, amber 28, camphoraceous 27, animalic 23, aldehydic 23.

Six weeks, 69 commits, first commit 31 July.

---

## The one-line pitch, if the conversation needs an anchor

Every structure-odour dataset of usable size is licence-encumbered — the standard one is
built on Leffingwell, which is CC-BY-NC and access-restricted. That blocks commercial use,
blocks tokens, and blocks anyone building on it. **OpenScent rebuilds it from sources that
carry no restriction, CC0, with the source sentence recorded on every single row.**

Not the biggest. The largest that anyone can legally use.

---

## What to ask him for

He built the publication toolchain and thinks about provenance, reproducibility, content
hashing and release audits. That is a genuine fit with a corpus whose entire pitch is
provenance — not a courtesy request.

1. **The paper.** He offered the template; take it. Four pages, scientific-paper format.
   Ask him to read a draft as someone who does not already know the project — he is
   currently the best-calibrated reader for exactly that, because he has lost the thread.
2. **The chemistry gap.** Say it plainly rather than apologising for it. Concretely:
   whether the 67-tag odour vocabulary is defensible to a chemist; whether descriptors
   like `camphoraceous` and `animalic` are used the way perfumers use them; whether the
   `sandal` -> `sandalwood` style mappings are sound.
3. **Reproducibility review.** His templates repo does content hashes and a privacy audit
   before release. OpenScent will need the same before the corpus is published. He has
   already solved that problem once.

---

## Do not undersell the method

*"I'm a total noob and sometimes even I don't know what I'm making"* — the chemistry gap is
real, the rest is not. The hard parts of six weeks were not chemistry:

- refusing to count a term attested by one patent twenty times (four counters were needed
  before the count meant anything);
- measuring yield on a 200-patent sample before spending seven hours fetching — which
  declined two whole CPC classes and doubled the corpus on a third;
- catching that a filter change had silently orphaned 84 hand-made decisions, and building
  the guard that refuses to write without a written reason;
- auditing your own corpus and finding 19.4% redundant documents, then working out that it
  does **not** move the headline and saying so.

That is measurement discipline, and it is rarer than chemistry. State the gap, ask him to
cover it, do not apologise for the rest.

---

## Open questions worth raising

1. **Does the model live in the OpenScent paper or in M's `GL1F.pdf`?** Asked in the main
   chat, no answer yet. Decides whether the paper is dataset-only.
2. **Authorship.** Mikhail proposed the project; you built it. Settle before submission.
3. **Where does it get published?** Joe's line — *"it gives the area in which you might be
   pointed towards as soon as you aim to publish"* — suggests he has a venue in mind. Ask.
