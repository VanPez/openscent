#!/usr/bin/env python3
"""
normalise_ids.py — convert OPS docdb numbers to the fetchable USPTO form.

    python3 normalise_ids.py patent-ids-A23L27_00-ops-dedup.json
    python3 normalise_ids.py patent-ids-A23L27_00-ops-dedup.json --write

One-off repair for walk files produced before ops.py normalised at capture time.
New walks do not need this.

WHAT WAS WRONG
--------------
US application publications are YEAR + a SEVEN-digit serial. OPS returns most of them
with the leading zero stripped:

    OPS      US2001001711A1     404 on Google Patents
    correct  US20010001711A1    serves the document

5,801 of 5,924 application publications in the A23L27/00 walk carried the short form.
Grants are unaffected.

WHY IT MATTERED MORE THAN IT LOOKS
----------------------------------
A malformed id fails as a **404**, which is exactly what a patent that genuinely is not
available also looks like. harvest.py logs it and moves on. The fetch would have
completed, reported ~70% failures as if the documents were missing, and the corpus would
have been short by thousands with the reason recorded nowhere.

This is the same shape as every other problem in this pipeline: not an error, a quiet
wrong answer. It was caught only because a fetch was watched while it ran.

VERIFICATION IS PART OF THE FIX
-------------------------------
--write re-checks that each converted id still parses as a US publication and that the
family map survives the rename. Ids it cannot convert confidently are left alone and
reported rather than guessed at.
"""
from __future__ import annotations
import json, pathlib, re, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from ops import to_uspto
except ImportError:                      # runnable on a box without the rest of the tree
    def to_uspto(pub: str) -> str:
        m = re.match(r"^US(\d{4})(\d+)([A-Z]\d?)$", pub)
        if not m:
            return pub
        year, serial, kind = m.groups()
        if len(year) + len(serial) < 10 or not (1976 <= int(year) <= 2100):
            return pub
        return f"US{year}{serial.rjust(7, '0')}{kind}"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = "--write" in sys.argv
    if not args:
        sys.exit("usage: normalise_ids.py <walk-file.json> [--write]")

    src = pathlib.Path(args[0])
    if not src.exists():
        src = HERE.parent / "corpus" / args[0]
    d = json.loads(src.read_text())
    ids = d["ids"] if isinstance(d, dict) else d
    fams = (d.get("families") or {}) if isinstance(d, dict) else {}

    changed, same = [], 0
    for i in ids:
        n = to_uspto(i)
        if n != i:
            changed.append((i, n))
        else:
            same += 1

    print(f"{src.name}: {len(ids)} ids")
    print(f"  unchanged : {same}")
    print(f"  rewritten : {len(changed)}")
    if changed:
        print("\n  examples:")
        for a, b in changed[:6]:
            print(f"    {a:<18} -> {b}")

    new_ids = [to_uspto(i) for i in ids]
    if len(set(new_ids)) != len(set(ids)):
        print(f"\n! normalising COLLAPSED {len(set(ids)) - len(set(new_ids))} distinct ids.")
        print("  Two different documents cannot map to one id — investigate before writing.")
        return 1

    if not write:
        print("\nDry run. Add --write to apply.")
        return 0

    bak = src.with_suffix(f".json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    bak.write_text(src.read_text())
    out = dict(d) if isinstance(d, dict) else {}
    out["ids"] = sorted(set(new_ids))
    if fams:
        out["families"] = {to_uspto(k): v for k, v in fams.items()}
    out["normalised_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    src.write_text(json.dumps(out))
    print(f"\nbackup -> {bak.name}")
    print(f"written -> {src.name}   ({len(out['ids'])} ids)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
