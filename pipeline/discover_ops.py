#!/usr/bin/env python3
"""
discover_ops.py — walk a CPC class for US patent ids via EPO OPS. Replaces the Google walk.

    python3 discover_ops.py A23L27/00
    python3 discover_ops.py A23L27/00 C11D3/50 A61K8/00
    python3 discover_ops.py A23L27/00 --verify     # completeness cross-check, see below

Runs anywhere — OPS is an authenticated API, so unlike Google's /xhr/query it does not
care that the caller is a Hetzner box. The Mac-only constraint is gone.

DOES NOT TOUCH corpus/patent-ids.json. Writes corpus/patent-ids-<class>-ops.json;
merging stays a separate deliberate step via merge_ids.py.

HOW US IS SELECTED, AND WHY IT MUST BE DONE AT QUERY TIME
---------------------------------------------------------
`pn=US*` is rejected: OPS requires >=3 characters before a truncation and "US" is 2.
So the walk asks for US1*..US9* and USRE* separately, which is legal and splits the class
into naturally smaller queries.

The obvious alternative — pull a window unfiltered and keep the US ids — is WRONG, and
--verify proved it on 2026-08-19: prefix found 79 US ids in a window where the unfiltered
pull found 31. It misses more than half.

The reason is the family behaviour below. A US patent whose family also contains a WO or
EP publication surfaces under the SIBLING's number, so it never looks like a US document
at all. Client-side filtering cannot see it.

ONE PUBLICATION PER FAMILY — AND THAT IS THE RIGHT UNIT
-------------------------------------------------------
OPS search returns one representative publication per family. Asking for the grant
US10000723 returns US2015209688A1, its pre-grant publication (raw XML dumped to confirm:
one record, one document-id, family-id 53678132).

That is not a defect to work around. An application publication and the patent granted
from it are ONE disclosure — same party, same words — and the docs>=20 admission rule
counts documents as independent attestations. Counting both is one witness testifying
twice. Google Patents had no family concept, so the existing 2,588-patent corpus may
already contain that duplication; audit it before trusting any count derived from it.

Every id is therefore stored WITH its family id, in state["families"].

OVERLAP WITH THE EXISTING CORPUS IS NOT MEASURABLE YET
------------------------------------------------------
patent-ids.json holds grant numbers; OPS returns the family representative, often the
A-publication. So "new vs already held" compares different naming systems and OVERSTATES
newness. The count printed below is an upper bound, not a measurement, until the existing
corpus has family ids of its own.

THE 2,000 CEILING
-----------------
Measured, not assumed: a request returns at most 100 items and the highest reachable
offset is 2,000. Any query above that CANNOT be paged. ops.fetch_all raises rather than
returning a partial, and this walker responds by splitting the query by publication date
until every piece fits. The class total is 7,131 across all countries, so splitting is
not hypothetical.

The point is that a capped query is DETECTABLE here. Google's 1,000-cap returned a short
list indistinguishable from a complete one, and the first corpus walk finished at 998
looking healthy. total-result-count removes that whole class of silent error.

--verify
--------
Takes one date window, collects it two ways — by US prefix, and by pulling the window
unfiltered and keeping US client-side — then compares. If the prefix method is missing
ids, the nine-prefix assumption is wrong and the walk is quietly incomplete. Costs a few
extra requests once; a missing series digit would cost a silent hole in the corpus.
"""
from __future__ import annotations
import json, pathlib, random, sys, time

_here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_here))
import ops  # noqa: E402

ROOT = _here.parent
# US1*..US9* covers grants (US10…, US9…) and application publications (US2016…).
# USRE* was ADDED after --verify caught USRE44508E on 2026-08-19: reissues begin with
# letters, so no digit prefix can reach them. That is precisely the silent hole the
# check existed to find.
#
# Deliberately NOT included, and the reason matters more than the omission:
#   USD*  design patents — protect appearance, contain no description of an odour
#   USPP* plant patents  — a genuinely different corpus; some mention fragrance, but
#                          they describe cultivars, not compounds, and would not yield
#                          a molecule/descriptor row
#   USH*  statutory invention registrations — defunct programme, negligible volume
# Revisit if row yield ever comes up short; these are cheap to add.
PREFIXES = [f"US{d}" for d in range(1, 10)] + ["USRE"]
START, END = 2001, 2027

# CPC IS A TREE AND OPS MATCHES THE SYMBOL LITERALLY.
#
# cpc="A23L27/00"      ->  7,131   just that symbol
# cpc="A23L27/00/low"  -> 44,809   the symbol AND every subgroup under it
#
# Measured 2026-08-19. Two subgroups alone (A23L27/10 = 11,038 and /20 = 1,665) exceed
# the main group's entire count, which is how the literal matching was caught: documents
# live in the subgroups, not the bare main group. The first OPS walk finished in one
# minute with 589 US ids and looked perfectly healthy while covering ~1.3% of the class.
#
# cpc=A23L27* is refused outright — OPS allows classification truncation only at subclass
# level — so /low is the only way to reach the tree.
SCOPE = "/low"


def scoped(cpc: str) -> str:
    """Always search the subtree. There is no case where we want the bare symbol."""
    return f'cpc="{cpc}{SCOPE}"'


def collect(cql, label, out, indent="  "):
    """One query, split by date if it will not page. Appends ids to `out`."""
    try:
        total, recs = ops.fetch_all(cql)
        print(f"{indent}{label}: {total} -> {len(recs)} ids" + ("  (none)" if not total else ""))
        out += recs
        return True
    except ops.TooManyResults:
        print(f"{indent}{label}: OVER 2000 — splitting by date")
        return False


def walk_prefix(cpc, prefix, out):
    """All ids for one US series digit, narrowing by date only where needed."""
    base = f'{scoped(cpc)} and pn={prefix}*'
    if collect(base, prefix, out):
        return []
    failed = []
    lo = START
    while lo < END:
        hi = min(lo + 3, END)
        q = f'{base} and pd within "{lo} {hi - 1}"'
        if not collect(q, f"{prefix} {lo}-{hi - 1}", out, indent="    "):
            # Still too big for a 3-year window: go year by year.
            for y in range(lo, hi):
                q1 = f'{base} and pd within "{y} {y}"'
                if not collect(q1, f"{prefix} {y}", out, indent="      "):
                    print(f"      ! {prefix} {y} exceeds 2000 in a SINGLE YEAR and cannot")
                    print("        be split further by date. Narrow by CPC subgroup.")
                    failed.append([prefix, y])
        lo = hi
    return failed


def verify(cpc):
    """Is the nine-prefix method actually complete? Compare against an unfiltered pull."""
    win = '2013 2015'
    print(f"=== VERIFY {cpc}, pd within \"{win}\" ===")
    print(f"  pacing {ops.MIN_GAP}s between requests — this takes a few minutes.\n")
    by_prefix = []
    for p in PREFIXES:
        try:
            print(f"  {p}* ...", end="", flush=True)      # flush: 4.5s of silence
            _, recs = ops.fetch_all(f'{scoped(cpc)} and pn={p}* and pd within "{win}"')
            print(f" {len(recs)}")
            by_prefix += [r["id"] for r in recs]
        except ops.TooManyResults:
            print(f"\n  {p}: too large to verify in one window — skipping"); return
    unfiltered = []
    try:
        print("  unfiltered window (all countries, ~12 pages) ...", end="", flush=True)
        _, allrecs = ops.fetch_all(f'{scoped(cpc)} and pd within "{win}"')
        unfiltered = [r["id"] for r in allrecs if r["id"].startswith("US")]
        print(f" {len(allrecs)} total")
    except ops.TooManyResults as e:
        print(f"  cannot pull the window unfiltered ({e}) — pick a narrower one"); return
    a, b = set(by_prefix), set(unfiltered)
    print(f"\n  by prefix     : {len(a)}")
    print(f"  unfiltered+US : {len(b)}")
    print(f"  union         : {len(a | b)}")

    missed = b - a
    if missed:
        print(f"\n  ! {len(missed)} id(s) the PREFIX method missed: {sorted(missed)[:10]}")
        print("    Prefix list is incomplete — add the missing series.")
    extra = a - b
    if extra:
        print(f"\n  ! {len(extra)} id(s) the UNFILTERED method missed: {sorted(extra)[:10]}")
        print("    Expected zero. The likely cause is that OPS returns one representative")
        print("    publication per FAMILY, so a US patent with a WO/EP sibling surfaces")
        print("    under the sibling's number and never reads as US. If so, filtering US")
        print("    client-side undercounts badly and query-time pn=US.. is MANDATORY.")
    if not missed and not extra:
        print("\n  the two methods agree — either is safe.")
    print("\n  NB neither method is ground truth. This compares coverage; it does not")
    print("  prove completeness. Union is the best available estimate.")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        sys.exit("usage: discover_ops.py <CPC> [CPC...] [--verify]")
    try:
        ops.load_env(); ops.token()
    except ops.OPSError as e:
        print(e); return 1

    if "--verify" in sys.argv:
        verify(args[0]); return 0

    idfile = ROOT / "corpus" / "patent-ids.json"
    have = set(json.loads(idfile.read_text())) if idfile.exists() else set()
    print(f"already held: {len(have)} ids   ·   pacing {ops.MIN_GAP}s floor\n")

    for cpc in args:
        dest = ROOT / "corpus" / f"patent-ids-{cpc.replace('/', '_')}-ops.json"
        state = {"cpc": cpc, "scope": SCOPE, "source": "epo-ops",
                 "ids": [], "failed": [], "done_prefixes": []}
        if dest.exists():
            old = json.loads(dest.read_text())
            # A walk done with different scope semantics is not resumable — its
            # "done" prefixes were answering a narrower question. Resuming would
            # produce a file that is part subtree, part bare symbol, with nothing
            # recording which parts are which.
            if old.get("scope") != SCOPE:
                bak = dest.with_suffix(f".json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
                dest.rename(bak)
                print(f"! existing {dest.name} was walked with scope "
                      f"{old.get('scope', 'bare symbol')!r}, not {SCOPE!r}.")
                print(f"  It covers a fraction of the class. Moved to {bak.name};")
                print("  starting fresh.")
            else:
                state.update(old)
                print(f"resuming {cpc}: {len(state['ids'])} ids, "
                      f"{len(state['done_prefixes'])} prefixes done")
        print(f"=== {cpc} ===")
        t0 = time.time()
        for p in PREFIXES:
            if p in state["done_prefixes"]:
                continue
            if state["done_prefixes"]:
                pause = random.uniform(25, 50)   # rest between prefixes, not just requests
                print(f"  (resting {pause:.0f}s before {p})", flush=True)
                time.sleep(pause)
            got = []
            try:
                state["failed"] += walk_prefix(cpc, p, got)
            except (ops.QuotaExceeded, ops.RobotDetected) as e:
                print(f"\n{e}\nProgress saved — re-run to resume from {p}.")
                dest.write_text(json.dumps(state)); return 2
            fams = dict(state.get("families") or {})
            for r in got:
                if r["id"].startswith("US"):
                    fams[r["id"]] = r["family"]
            state["families"] = fams
            state["ids"] = sorted(fams)
            state["done_prefixes"].append(p)
            dest.write_text(json.dumps(state))       # save after EVERY prefix

        new = [i for i in state["ids"] if i not in have]
        fams = set((state.get("families") or {}).values())
        print(f"\n{cpc}: {len(state['ids'])} US ids in {len(fams)} families, "
              f"in {(time.time()-t0)/60:.0f} min")
        print(f"  {len(new)} not matching an id already in patent-ids.json — but that is an")
        print("  UPPER BOUND on newness, not a measurement: the corpus stores grant numbers")
        print("  and OPS returns family representatives, so the same disclosure can appear")
        print("  under two different numbers and read as new. Resolve with family ids.")
        if state["failed"]:
            print(f"! {len(state['failed'])} query/queries could not be split small enough:")
            print(f"  {state['failed']}")
            print("  These are GAPS. merge_ids.py will refuse the file until they clear.")
        print(f"quota used — hour {ops.QUOTA['hour_used']} · week {ops.QUOTA['week_used']} (bytes)")
        print(f"-> {dest}\n")
        print("NOT merged. Verify the numbers, then:")
        print(f"    python3 merge_ids.py {dest.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
