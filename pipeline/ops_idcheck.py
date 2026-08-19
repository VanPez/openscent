#!/usr/bin/env python3
"""
ops_idcheck.py — do OPS ids match the form the corpus already uses?

    python3 ops_idcheck.py

WHY THIS MUST BE ANSWERED BEFORE THE WALK
-----------------------------------------
The verify run returned ids shaped like US2013071455A1 — four year digits then SIX — while
the corpus stores US20160376521A1, four then SEVEN. The smoke run, though, returned
US20260223902A1, which is the long form. Two shapes from one API.

An id in the wrong shape does not fail loudly. It merges cleanly into patent-ids.json,
the fetch requests a page that does not exist, and the result is a 404 that reads exactly
like a patent we simply could not get. The corpus ends up short by an unknown amount with
nothing anywhere recording why. That is the same class of silent hole as the capped
Google window, and it is worth ten requests to close.

METHOD
------
Take ids the corpus ALREADY holds, ask OPS for each by publication number, and print what
comes back beside what we asked for. The mapping is then observed, not inferred.
"""
from __future__ import annotations
import json, pathlib, re, sys

_here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_here))
import ops  # noqa: E402

ROOT = _here.parent


def normalise(pub: str) -> str:
    """OPS docdb id -> USPTO publication number, as the corpus writes it.

    US application publications are YEAR + a 7-digit serial. OPS sometimes emits the
    serial without its leading zero. Grants (US8…, US9…, US10…) and reissues are left
    alone — they have no fixed width to restore.
    """
    m = re.match(r"^US(\d{4})(\d+)([A-Z]\d?)$", pub)
    if not m:
        return pub
    year, serial, kind = m.groups()
    if not (1976 <= int(year) <= 2100):      # not a year: this is a grant number
        return pub
    if len(serial) < 7:
        serial = serial.rjust(7, "0")
    return f"US{year}{serial}{kind}"


def main() -> int:
    try:
        ops.load_env(); ops.token()
    except ops.OPSError as e:
        print(e); return 1

    idfile = ROOT / "corpus" / "patent-ids.json"
    if not idfile.exists():
        print(f"{idfile} not found"); return 1
    have = json.loads(idfile.read_text())

    apps = [i for i in have if re.match(r"^US\d{4}0", i)][:5]
    grants = [i for i in have if re.match(r"^US\d{7,8}[A-Z]", i)][:5]
    sample = apps + grants
    if not sample:
        print("no recognisable ids in patent-ids.json"); return 1

    print(f"corpus holds {len(have)} ids. Asking OPS for {len(sample)} of them.\n")
    print(f"{'asked for':<20} {'OPS returned':<20} {'normalised':<20} match")
    print("-" * 72)
    bad = 0
    for want in sample:
        stem = re.sub(r"[A-Z]\d?$", "", want)       # drop kind code for the query
        try:
            _, recs, _ = ops.search(f"pn={stem}", 1, 5)
        except ops.OPSError as e:
            print(f"{want:<20} ERROR {str(e).splitlines()[0]}")
            continue
        got = next((r["id"] for r in recs if r["id"].startswith("US")), "(none)")
        norm = normalise(got) if got != "(none)" else "(none)"
        ok = "yes" if norm == want else "NO"
        if ok == "NO":
            bad += 1
        print(f"{want:<20} {got:<20} {norm:<20} {ok}")

    print("-" * 72)
    if bad:
        print(f"{bad} of {len(sample)} do not round-trip. normalise() is not yet correct —")
        print("do NOT merge a walk until it is, or the corpus gains ids that cannot be fetched.")
    else:
        print("all sampled ids round-trip. normalise() can be applied to walk output.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
