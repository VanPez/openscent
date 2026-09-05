# Paste this into a new chat

---

We're continuing **OpenScent** — a CC0 odour corpus (molecule → odour-descriptor rows)
mined from US patents + PubChem. Proposed by Mikhail Fedorov of GenesisL1. Target:
60–100 tags with ≥30 molecules each.

Repo: `~/Documents/GenesisL1/openscent/`

**Before you say anything about the state of the project, do these three things:**

1. `python3 pipeline/status.py` — this owns the headline number. **Quote no figure that
   did not come out of it.** On 2026-09-05 the count was done by hand three times in ten
   minutes and gave 20, then 11, then 15 tags; only the first was right. Don't recompute
   it yourself, and don't trust a number you remember.
2. Read the **RESUME HERE** block at the top of `DEVLOG.md` — current state, what's
   settled, what's deferred, and the open decision.
3. Read `REVIEW-RULES.md` if any reviewing or proposing is involved.

`DEVLOG.md` is oldest-first; the newest entry is at the bottom. The scripts in
`pipeline/` carry long docstrings explaining why they do the odd thing they do — read the
docstring before changing a script, since most of them encode a bug that already
happened once.

## Where we are

The productive review queue is **empty** — every candidate carrying both a name-like span
and a descriptor has been seen by a human. 962 decisions, 20 of 67 tags at the bar (12 on
20 August). `amber` is 2 molecules short. The 3,658 undecided rows carry no descriptor or
no name-like span and will not add molecules.

## The open decision — this is what the session is for

New material is needed. Three options, ordered by what they cost to *learn* from:

1. **Sample `C11D 3/50` for yield** — ~20 min, ~1,240 US patents. Detergent perfumery,
   which is where amber/musk descriptors live, i.e. aimed at the tags nearest the bar.
   Yield never measured. *This is the recommended first move: it buys information rather
   than spending hours on a guess.*
2. **Re-extract the 5,346 patents at a looser filter** — free, no network, weaker
   candidates, unknown keep rate.
3. **Fetch A23L27/00** — ~7 h, already walked and deduped, sampled at 0.17 → ~280 rows.

I haven't chosen. Start by running `status.py`, then let's decide.

## Standing rules for this project

- **Measure yield before fetching anything.** Always. That discipline earned the August
  corpus doubling and correctly declined A23L27/00.
- **Extract, never generate.** Every molecule and descriptor must be a verbatim substring
  of its sentence. `status.py` re-checks this.
- **Propose-only.** You label candidates, I decide. Blind accuracy is 67%, not 99.3% —
  the high figure was anchoring. Auto-reject stays off.
- **Ask before deleting anything** — files, rows, data.
- Never hardcode keys; they live in `.env` / `config.json`.
- Non-US patents are ruled out — the CC0 claim rests on US no-copyright status.
- Say "log" and write the DEVLOG entry before we stop for the day.
