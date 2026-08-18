#!/usr/bin/env python3
"""
merge_ids.py — fold a discovery result into corpus/patent-ids.json. Deliberate step.

    python3 merge_ids.py patent-ids-A23L27_00.json          # show what would change
    python3 merge_ids.py patent-ids-A23L27_00.json --write  # actually do it

WHY THIS IS SEPARATE FROM DISCOVERY
-----------------------------------
patent-ids.json is the corpus definition. harvest.py's fetch silently falls back to
re-running discovery if it is missing or wrong, which is how the 503 storm started on
2026-08-01. So nothing writes to it as a side effect: a walk produces its own file, a
human looks at the numbers, and only then does it merge.

Refuses to merge a walk that has unresolved failed windows unless --force is given.
Merging an incomplete walk bakes a gap into the corpus that nothing downstream can see —
the ids simply are not there, and no later stage can tell the difference between "this
patent has no odour data" and "we never fetched this patent".

Always writes a timestamped backup before touching anything.
"""
from __future__ import annotations
import json, pathlib, shutil, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = "--write" in sys.argv
    force = "--force" in sys.argv
    if not args:
        sys.exit(__doc__.strip().splitlines()[2].strip())

    target = CORPUS / "patent-ids.json"
    have = json.loads(target.read_text()) if target.exists() else []
    merged = set(have)
    print(f"current corpus: {len(have)} ids\n")

    for name in args:
        src = CORPUS / name if not pathlib.Path(name).is_absolute() else pathlib.Path(name)
        d = json.loads(src.read_text())
        ids = d["ids"] if isinstance(d, dict) else d
        failed = d.get("failed_windows", []) if isinstance(d, dict) else []
        new = [i for i in ids if i not in merged]
        print(f"{src.name}: {len(ids)} ids, {len(new)} new")
        if failed:
            print(f"  ! {len(failed)} window(s) failed in this walk: {failed}")
            if not force:
                print("  REFUSING to merge an incomplete walk. Re-run the discovery to")
                print("  retry those windows, or pass --force if you accept the gap.")
                return 1
            print("  --force given: merging anyway, gap and all.")
        merged |= set(ids)

    print(f"\nresult: {len(have)} -> {len(merged)} ids  (+{len(merged) - len(have)})")
    if not write:
        print("\nDry run. Add --write to apply.")
        return 0

    if target.exists():
        bak = target.with_suffix(f".json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(target, bak)
        print(f"backup -> {bak.name}")
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sorted(merged), indent=0))
    tmp.replace(target)                      # atomic
    print(f"written -> {target}")
    print("\nNext: copy it to the harvest box and fetch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
