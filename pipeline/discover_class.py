#!/usr/bin/env python3
"""
discover_class.py — walk a CPC class and collect its US patent ids. Discovery only.

    OPENSCENT_DELAY_MIN=6 OPENSCENT_DELAY_MAX=12 python3 discover_class.py A23L27/00

RUN FROM THE MAC. Google refuses /xhr/query from Hetzner.

DOES NOT TOUCH corpus/patent-ids.json. Results go to corpus/patent-ids-<class>.json, and
merging is a separate deliberate step (merge_ids.py). The fetch silently falls back to
re-running discovery if patent-ids.json goes missing, which is how the 503 storm started
on 2026-08-01 — so that file is never written by anything except an explicit merge.

WHY A23L 27/00
--------------
Probed 2026-08-18: 1,081 sampled, 1,021 of them NOT already held — 94% new. Food-flavour
patents are a genuinely separate pool from perfume patents, because a flavour house rarely
files under a perfume classification. Estimated ~4,400 new patents, which would take the
corpus from 2,588 to ~7,000.

RESUMABLE, AND HONEST ABOUT GAPS
--------------------------------
Every window is saved as it completes, so a 503 halfway through costs minutes, not the
whole walk. Windows that fail are RECORDED, not skipped silently — the summary lists them
and they can be re-run alone. A discovery walk that quietly dropped three windows would
produce a corpus with a hole in it that nothing downstream could detect.

THE 1,000 CAP
-------------
Google caps a result set at ~1,000 (10 pages x 100). A window at the cap has lost results
and there is no way to tell how many. Such windows are automatically split in half and
re-walked, recursively, until each part comes in under the cap. The first corpus run hit
exactly 998 and looked complete, which is what taught us to check.
"""
from __future__ import annotations
import json, os, pathlib, sys, time

_here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_here))
from harvest import search_window, ROOT, DELAY   # noqa: E402

CAP = 1000
START = int(os.environ.get("OPENSCENT_START_YEAR", 2001))
END = int(os.environ.get("OPENSCENT_END_YEAR", 2027))
STEP = int(os.environ.get("OPENSCENT_STEP", 3))


def walk(cpc, lo, hi, failed, depth=0):
    """One window, split recursively if it hits the cap."""
    pad = "  " * (depth + 1)
    ids = search_window(cpc, lo, hi)
    if not ids:
        print(f"{pad}{lo}-{hi}: NO DATA (empty window or rate limited)")
        failed.append([lo, hi])
        return []
    if len(ids) >= CAP and (hi - lo) > 1:
        print(f"{pad}{lo}-{hi}: {len(ids)} — AT THE CAP, splitting")
        mid = lo + (hi - lo) // 2
        return walk(cpc, lo, mid, failed, depth + 1) + walk(cpc, mid, hi, failed, depth + 1)
    if len(ids) >= CAP:
        # A single year at the cap cannot be split further by date.
        print(f"{pad}{lo}-{hi}: {len(ids)} — AT THE CAP and cannot split further. "
              f"RESULTS LOST for this year; narrow by subclass instead.")
        failed.append([lo, hi])
    else:
        print(f"{pad}{lo}-{hi}: {len(ids)}")
    return ids


def main() -> int:
    classes = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not classes:
        sys.exit("usage: discover_class.py <CPC> [CPC...]   e.g. A23L27/00")
    idfile = ROOT / "corpus" / "patent-ids.json"
    have = set(json.loads(idfile.read_text())) if idfile.exists() else set()
    print(f"already held: {len(have)}   ·   delay {DELAY[0]:.0f}-{DELAY[1]:.0f}s "
          f"·   walking {START}-{END} in {STEP}y windows\n")

    for cpc in classes:
        dest = ROOT / "corpus" / f"patent-ids-{cpc.replace('/', '_')}.json"
        state = {"cpc": cpc, "ids": [], "failed_windows": [], "done_windows": []}
        if dest.exists():                      # resume
            state.update(json.loads(dest.read_text()))
            print(f"resuming {cpc}: {len(state['ids'])} ids, "
                  f"{len(state['done_windows'])} windows already walked")
        done = {tuple(w) for w in state["done_windows"]}
        print(f"=== {cpc} ===")
        t0 = time.time()
        for lo in range(START, END, STEP):
            hi = min(lo + STEP, END)
            if (lo, hi) in done:
                continue
            failed = []
            ids = walk(cpc, lo, hi, failed)
            state["ids"] = sorted(set(state["ids"]) | set(ids))
            state["failed_windows"] += failed
            state["done_windows"].append([lo, hi])
            dest.write_text(json.dumps(state))   # save after EVERY window
        new = [i for i in state["ids"] if i not in have]
        mins = (time.time() - t0) / 60
        print(f"\n{cpc}: {len(state['ids'])} ids total, {len(new)} new "
              f"({len(state['ids']) - len(new)} already held) in {mins:.0f} min")
        if state["failed_windows"]:
            print(f"! {len(state['failed_windows'])} window(s) returned nothing: "
                  f"{state['failed_windows']}")
            print("  Re-run the same command after a cooldown — completed windows are")
            print("  skipped, so it will only retry these.")
        print(f"-> {dest}\n")
        print("NOT merged into patent-ids.json. When the walk is clean:")
        print(f"    python3 merge_ids.py {dest.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
