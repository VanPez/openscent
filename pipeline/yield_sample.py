#!/usr/bin/env python3
"""
yield_sample.py — is a class worth fetching? Measure on a sample before paying for it.

    python3 yield_sample.py --ids patent-ids-A23L27_00-ops-dedup.json --n 200

RUN ON HETZNER. Needs harvest.py beside it and the id file readable.

WHY SAMPLE INSTEAD OF JUST FETCHING
-----------------------------------
The A23L27/00 walk found 9,346 distinct disclosures. Fetching all of them is roughly
15-20 hours of requests and a day of somebody's bandwidth, and it is the one step in this
project that cannot be undone cheaply or re-run casually.

The class was chosen because it is LARGE and mostly NEW. Neither says it is USEFUL. A
food-flavour patent can be a genuine odour disclosure or a process document about
extraction equipment that never characterises a smell. The perfume classes yield about
1.2 candidates per patent; if this subtree yields 0.1, then 9,000 fetches buy a few
hundred candidates and the day is better spent elsewhere.

That is a measurement, and it costs 200 fetches to make.

IT ALSO TESTS THE RATE, WHICH IS THE SECOND UNKNOWN
---------------------------------------------------
Discovery moved to EPO OPS, but fetching is still Google Patents — the source that
produced two unexplained multi-hour cooldowns. The corpus so far is 2,588 documents;
this would be 3.6x that. 200 sequential fetches is a cheap probe of whether the current
pace is tolerated, and cheap to abandon if it is not.

ISOLATION
---------
Runs against its own OPENSCENT_ROOT so sample documents never mix into corpus/raw/.
Mixing them would make the yield unmeasurable (extract() runs over everything in raw/)
and would quietly add unreviewed documents to the corpus proper.

NEVER invokes `harvest.py fetch`. That CLI path re-runs DISCOVERY when patent-ids.json
is absent, which is how the 503 storm started on 2026-08-01. fetch() is called directly
with an explicit list.
"""
from __future__ import annotations
import argparse, json, os, pathlib, random, re, sys, time

HERE = pathlib.Path(__file__).resolve().parent


def era(pid: str):
    """Rough publication era, for stratifying and for reporting yield by age."""
    m = re.match(r"^US(\d+)([A-Z])", pid)
    if not m:
        return "?"
    digits = m.group(1)
    if len(digits) >= 10:                     # application publication: YYYY + serial
        return digits[:4]
    n = int(digits)
    for lo, yr in [(11000000, "2021+"), (9000000, "2015-2020"), (7000000, "2006-2014"),
                   (5000000, "1991-2005"), (3930000, "1976-1990")]:
        if n >= lo:
            return yr
    return "pre-1976"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True, help="walk output json (use the -dedup one)")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--root", default="/opt/openscent-sample")
    ap.add_argument("--seed", type=int, default=20260819)
    ap.add_argument("--include-pre1976", action="store_true")
    a = ap.parse_args()

    # must be set BEFORE importing harvest — ROOT is bound at import time
    os.environ["OPENSCENT_ROOT"] = a.root
    sys.path.insert(0, str(HERE))
    import harvest  # noqa: E402

    src = pathlib.Path(a.ids)
    if not src.exists():
        src = HERE.parent / "corpus" / a.ids
    d = json.loads(src.read_text())
    ids = d["ids"] if isinstance(d, dict) else d

    dropped = []
    if not a.include_pre1976:
        keep = [i for i in ids if era(i) != "pre-1976"]
        dropped = [i for i in ids if era(i) == "pre-1976"]
        ids = keep

    print(f"{src.name}: {len(ids)} candidates for sampling")
    if dropped:
        print(f"  ({len(dropped)} pre-1976 grants excluded — scanned images, and 1911 OCR")
        print("   will not carry modern descriptor vocabulary. --include-pre1976 to keep.)")

    # Stratify by era so the estimate is not dominated by whichever decade happens to be
    # largest. Yield very plausibly differs by age: older patents are terser and use
    # different descriptive conventions.
    buckets: dict[str, list[str]] = {}
    for i in ids:
        buckets.setdefault(era(i), []).append(i)
    rng = random.Random(a.seed)
    per = max(1, a.n // len(buckets))
    sample = []
    for k in sorted(buckets):
        pool = buckets[k]
        take = min(per, len(pool))
        sample += rng.sample(pool, take)
    rng.shuffle(sample)                       # do not fetch in era order
    print(f"\nsampling {len(sample)} across {len(buckets)} eras "
          f"(~{per} each, seed {a.seed} so this is reproducible)")
    for k in sorted(buckets):
        print(f"   {k:<10} pool {len(buckets[k]):5d}")

    # PREFLIGHT — one id before the batch.
    #
    # The first run of this script spent minutes in exponential-backoff retry storms
    # because every id 404'd: OPS returns application numbers with the leading zero
    # stripped (US2001001711A1) and Google needs the padded form (US20010001711A1).
    # harvest.py treats a 404 as "this patent is unavailable" and continues, so a fully
    # broken run looks like a class with terrible availability and completes normally.
    #
    # One request distinguishes "wrong id format" from "genuinely missing document"
    # before the other 199 are attempted.
    import urllib.request, urllib.error  # noqa: E402
    probe = sample[0]
    print(f"\npreflight: {probe}", end=" ", flush=True)
    try:
        req = urllib.request.Request(f"https://patents.google.com/patent/{probe}/en",
                                     headers={"User-Agent": harvest.UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            ok = len(r.read()) > 5000
        print("ok" if ok else "returned a near-empty page")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}")
        if e.code == 404:
            print("\nSTOPPING. A 404 on the first id means the ID FORMAT is wrong, not")
            print("that the patent is missing — and harvest.py cannot tell those apart.")
            print("US application publications need a 7-digit serial:")
            print("    OPS gives   US2001001711A1")
            print("    Google wants US20010001711A1")
            print("\nFix the id file first:")
            print("    python3 normalise_ids.py <your-ids.json> --write")
        return 1

    root = pathlib.Path(a.root)
    (root / "corpus").mkdir(parents=True, exist_ok=True)
    print(f"\nfetching into {root}/corpus/raw  ·  delay {harvest.DELAY[0]}-{harvest.DELAY[1]}s")
    print(f"expect roughly {len(sample) * sum(harvest.DELAY) / 2 / 60:.0f} min\n")

    t0 = time.time()
    harvest.fetch(sample)                     # explicit list — never the CLI path
    mins = (time.time() - t0) / 60

    cached = sorted(harvest.RAW.glob("*.txt"))
    print(f"\nfetched in {mins:.0f} min · {len(cached)} of {len(sample)} produced usable text")
    short = len(sample) - len(cached)
    if short:
        print(f"  {short} were skipped as too short (<500 chars) or failed — this is")
        print("  itself a yield signal, not just noise.")

    print("\nextracting …")
    harvest.extract()
    cf = harvest.OUT / "candidates.json"
    rows = json.loads(cf.read_text()) if cf.exists() else []

    print("\n" + "=" * 66)
    print(f"documents fetched   {len(cached)}")
    print(f"candidates          {len(rows)}")
    if cached:
        rate = len(rows) / len(cached)
        print(f"CANDIDATES/PATENT   {rate:.2f}")

        # Compare against the corpus we already have, computed rather than quoted.
        main_raw = HERE.parent / "corpus" / "raw"
        main_cand = HERE.parent / "corpus" / "extracted" / "candidates.json"
        if main_cand.exists() and main_raw.exists():
            base_docs = len(list(main_raw.glob("*.txt")))
            base_rows = len(json.loads(main_cand.read_text()))
            if base_docs:
                base = base_rows / base_docs
                print(f"existing corpus     {base:.2f}  ({base_rows} / {base_docs})")
                print(f"ratio               {rate / base:.2f}x" if base else "")
        print()
        print(f"projected for the full {len(ids):,}: ~{int(rate * len(ids)):,} candidates")
        print(f"at ~0.2 precision that is ~{int(rate * len(ids) * 0.2):,} usable rows,")
        print(f"and ~{len(ids) * sum(harvest.DELAY) / 2 / 3600:.0f} h of fetching.")
        print("\nPrecision 0.2 is the WHOLE-QUEUE figure. Do not substitute 0.87 —")
        print("that is precision within the productive subset and would triple this.")
    print("=" * 66)
    print(f"\nSample documents are in {root} and are NOT part of the corpus.")
    print("Delete that directory when the decision is made, or keep it as evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
