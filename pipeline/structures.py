#!/usr/bin/env python3
"""
structures.py — patent molecule NAMES -> STRUCTURES. Stage 1: OPSIN, offline, report-only.

    python3 pipeline/structures.py            # resolve, write corpus/structures/names-opsin.jsonl, report
    python3 pipeline/structures.py --report   # re-print the report from the file, no OPSIN run
    python3 pipeline/structures.py --todo     # write the PubChem work list (stage 2 runs on HETZNER)
    python3 pipeline/structures.py --merge    # fold Hetzner's PubChem answers in; report; write names.jsonl

WHY THIS EXISTS
---------------
A MolNFT needs a molecule, not a name (Mike, 2026-09-27). The ~990 patent molecules are
spans: "2,6,6-trimethyl-l-[ l-hydroxybutyl]-cyclohex- 2-ene", "Lilial", "l-carvone". This
turns each into a structure (SMILES + InChIKey) WITHOUT touching a single corpus row:
review.jsonl, passage-rows.jsonl and targeted-rows.jsonl are only READ, and the output is a
new file nothing else reads yet. Dry run in the sense DEVLOG asked for: nothing downstream
changes until Ivan has read the report.

THE GUARANTEE, AND THE TIERS THAT KEEP IT HONEST
------------------------------------------------
The failure mode this project fears is a valid-looking row bound to the WRONG structure
(DEVLOG 2026-07-31). So every structure carries the route that produced it, and routes are
never blended:

    verbatim      OPSIN parses the extracted span as written (whitespace collapsed, nothing else)
    formatting    resolves after Unicode / spacing repairs only — no letter or digit is replaced
    ocr           resolves after OCR repairs (l->1, O->0, rn->m, ...). Each one is listed in
                  `repairs`. Checked against other spellings of the same molecule (see below)
    rewrite       a hand-authorised rewrite (REWRITE below): Ivan said how the span is to be read
                  (an "X of Y" phrase written out, an OCR slip repaired, a trade name pinned to a
                  structure). The span in the corpus stays verbatim; the rewrite and its reason live here
    stereo_dropped  OPSIN could not read the stereo (alpha/beta locants) — structure is FLAT.
                  A less specific claim than the name, never a different one
    unresolved    OPSIN cannot read it: trivial/trade names -> stage 2 (PubChem, on Hetzner)

The repairs are normalisation of extracted text, not invention (REVIEW-RULES: "OPSIN will not
parse the phrase, so linkage has to rewrite it ... that is normalisation of extracted text").
The span in the corpus stays verbatim; the repaired string lives only in this file.

THE CHECK ON THE REPAIRS
------------------------
An OCR repair can in principle turn a wrong name into a different valid one, and OPSIN cannot
tell. So each repaired name is compared with every OTHER spelling of the same molecule that
resolved VERBATIM, grouped by the same squash name_variants.py uses. Agreement is reported,
disagreement is listed. The check only covers names that have a witness; the report says how
many do not.

A second kind of witness is the patent's own text (corpus/structures/text-witnesses.json, curated
by hand from the raw patents on Hetzner, 2026-10-03): a spelling of the same compound printed
elsewhere in the SAME patent. It is resolved by the same repair chain and lifts the name to
repaired+witness only if it gives the same structure ("text" in the report).

NAMES THAT ARE NOT A DEFINITE STRUCTURE
---------------------------------------
Some approved rows name two molecules or a choice ("(E/Z)-...", "8/9-methylene...", "A or B",
"alkyl ..."). REVIEW-RULES says a definite structure or no row. Such names are FLAGGED here,
never resolved around and never deleted — whether a row stays is Ivan's call.

THE TOOLS (downloaded 2026-10-03 with Ivan's OK, not committed — see .gitignore)
------------------------------------------------------------------------------
  OPSIN 2.9.0   https://github.com/dan2097/opsin/releases/download/2.9.0/opsin-cli-2.9.0-jar-with-dependencies.jar
                sha256 c2e29326c281f87b59a05d934d8589adac6e9d17b95b984931b3e739111b360f
                -> pipeline/tools/
  OpenJDK 21    brew install openjdk@21   (keg-only; found at /opt/homebrew/opt/openjdk@21)
OPSIN prints one line per input and a BLANK line for a name it cannot parse, so output stays
aligned with input; the runner asserts the line count anyway.

NO PUBCHEM TRAFFIC FROM THIS FILE. PubChem throttles Ivan's IP (2026-09-26); stage 2 is
pipeline/structures_pubchem.py, copied to Hetzner with scp.
"""
from __future__ import annotations
import collections, importlib.util, json, os, pathlib, re, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
JAR = HERE / "tools" / "opsin-cli-2.9.0-jar-with-dependencies.jar"
OUT_DIR = ROOT / "corpus" / "structures"
OUT = OUT_DIR / "names-opsin.jsonl"
TODO = OUT_DIR / "pubchem-todo.json"


def find_java() -> str:
    for c in (os.environ.get("JAVA"), "/opt/homebrew/opt/openjdk@21/bin/java", shutil.which("java")):
        if c and pathlib.Path(c).exists():
            r = subprocess.run([c, "-version"], capture_output=True, text=True)
            if r.returncode == 0:
                return c
    sys.exit("no working Java found (brew install openjdk@21, or set JAVA=)")


# ---------------------------------------------------------------- names, read-only from the rows

def _status():
    spec = importlib.util.spec_from_file_location("status", HERE / "status.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load_names() -> dict:
    """key (status.py's norm()) -> {raws: Counter, rows, sources, tags, scopes}. Exactly the set
    status.py counts as patent-side molecules: approved, not retired, with a mapped tag."""
    st = _status()
    surf, exk = st.load_tags(), st.excluded_keys()
    names = collections.defaultdict(lambda: {"raws": collections.Counter(), "rows": 0,
                                             "sources": set(), "tags": set(), "scopes": set()})

    def add(mol, src, tags, scope):
        n = names[st.norm(mol)]
        n["raws"][mol] += 1; n["rows"] += 1
        n["sources"].add(src); n["tags"].update(tags); n["scopes"].add(scope)

    def tagset(ds):
        return {surf[d.strip().lower()] for d in ds if d and surf.get(d.strip().lower())}

    for r in st.jsonl(st.REVIEW):
        if r.get("decision") != "approve":
            continue
        if (r.get("source_id"), " ".join((r.get("sentence") or "").split())) in exk:
            continue
        tags = tagset(r.get("tags") or r.get("descriptors") or [])
        for m in r.get("molecules") or []:
            if tags and m.strip():
                add(m.strip(), r["source_id"], tags, "sentence")
    for path, scope in ((st.PASSAGE, "passage"), (st.TARGETED, "targeted")):
        for r in st.jsonl(path):
            if r.get("review_decision") != "approve":
                continue
            tags = tagset(r.get("descriptors") or [])
            if tags and (r.get("molecule") or "").strip():
                add(r["molecule"].strip(), r["source_id"], tags, scope)
    return names


# ---------------------------------------------------------------- repairs

def _l_as_one(s: str) -> str:
    """A standalone l / I between name punctuation is the digit 1 ("-l-", "[ l-", "l,l-"). NOT at
    the start when followed by -letter ("l-carvone" is levo) and NOT "(l)" (levo)."""
    def rep(m):
        a, b = m.start(), m.end()
        if a == 0 and re.match(r"-[A-Za-z]", s[b:]):
            return m.group(0)
        if s[a - 1:a] == "(" and s[b:b + 1] == ")":
            return m.group(0)
        return "1"
    return re.sub(r"(?<![A-Za-z0-9])[lI](?![A-Za-z0-9])", rep, s)


def _ring_bracket(s: str) -> str:
    """bicyclo[3.l.O] -> bicyclo[3.1.0]: only inside the von Baeyer / spiro brackets, only when
    the contents are nothing but digits, dots, commas and the confusables l I O."""
    def rep(m):
        body = m.group(3)
        if not re.search(r"\d", body):
            return m.group(0)
        return m.group(1) + m.group(2) + re.sub(r"[lI]", "1", body).replace("O", "0") + m.group(4)
    return re.sub(r"((?:cyclo|spiro)\s*)([\[(])([0-9lIO.,\s]+)([\])])", rep, s)


# (id, what it does, function) — formatting repairs replace no letter or digit
FORMATTING = [
    ("U1", "Unicode primes/dashes/minus -> ASCII",
     lambda s: re.sub("[‐-―−]", "-", re.sub("[′’ʹ]", "'", s))),
    ("W1", "no whitespace next to - , ( [ ) ] '",
     lambda s: re.sub(r"\s+(?=[-,)\]'])", "", re.sub(r"(?<=[-,(\[])\s+", "", s))),
    ("W2", "digit<space>word -> digit-word (a lost hyphen)",
     lambda s: re.sub(r"(\d[a-z]?) (?=[a-z]{3,})", r"\1-", s)),
]
OCR = [
    ("L1", "standalone l/I -> 1 (locant)", _l_as_one),
    ("L2", "l/I/O -> 1/0 inside ring brackets", _ring_bracket),
    ("L3", "l next to a digit -> 1 (l0 -> 10)",
     lambda s: re.sub(r"(?<=\d)l(?![A-Za-z])", "1", re.sub(r"(?<![A-Za-z])l(?=\d)", "1", s))),
    ("L4", "digit 1 between letters -> l (bicyc1o)", lambda s: re.sub(r"(?<=[a-z])1(?=[a-z])", "l", s)),
    ("R1", "rn -> m in rnethyl/rnethoxy/rnethylen", lambda s: re.sub(r"rn(?=ethyl|ethoxy|ethylen)", "m", s)),
    ("H1", "( lH) -> (1H)", lambda s: re.sub(r"\(\s*[1lI]\s*[Hh]\s*\)", "(1H)", s)),
]


def repair(s: str, rules) -> tuple[str, list[str]]:
    used = []
    for rid, _, fn in rules:
        t = fn(s)
        if t != s:
            used.append(rid)
            s = t
    return s, used


# ---------------------------------------------------------------- OPSIN

def opsin(java: str, names: list[str], fmt: str, drop_stereo: bool = False) -> list[str]:
    """One JVM per call. Blank output line = failed. Returns a list aligned with `names`."""
    if not names:
        return []
    cmd = [java, "-Dfile.encoding=UTF-8", "-Dstdin.encoding=UTF-8", "-Dstdout.encoding=UTF-8",
           "-jar", str(JAR), "-o", fmt] + (["-s"] if drop_stereo else [])
    p = subprocess.run(cmd, input="\n".join(names) + "\n", capture_output=True, text=True,
                       encoding="utf-8", timeout=900)
    out = p.stdout.split("\n")[:-1]
    if len(out) != len(names):
        sys.exit(f"OPSIN returned {len(out)} lines for {len(names)} names — alignment lost, refusing to continue")
    return [o.strip() for o in out]


def resolve_batch(java, strings, drop_stereo=False):
    """unique strings -> {string: (smiles, inchikey)} for those that resolved."""
    uniq = sorted(set(strings))
    smi = opsin(java, uniq, "smi", drop_stereo)
    key = opsin(java, uniq, "stdinchikey", drop_stereo)
    return {s: (a, k) for s, a, k in zip(uniq, smi, key) if a and k}


# ---------------------------------------------------------------- authorised rewrites
#
# Ivan, 2026-10-03, on the flagged names. Keyed by span (case/space-insensitive). Value:
# (rewritten name for OPSIN, why, optional PubChem name to cross-check the result against).
# Nothing here changes a corpus span; a rewrite only decides which STRUCTURE the span stands for.
_THP = "3-methyl-3-[4-methyl-5-(oxan-2-yloxy)pentyl]bicyclo[2.2.1]heptan-2-one"
_THP_WHY = ("tetrahydropyranyl ether of the alcohol, written out; US3580954A's own route (alkylating 3-methylnorcamphor "
            "with 2-methyl-5-bromopentyl tetrahydropyranyl ether) confirms the structure. Three spellings in three "
            "patents = ONE compound (Ivan: unite). endo/exo is not expressed, so the structure is flat")
_ALC = "3-methyl-3-(5-hydroxy-4-methylpentyl)bicyclo[2.2.1]heptan-2-one"
_ALC_WHY = ("the free alcohol of the THP ether above: US3580954A / US3644505A / US3624106A make it by treating the "
            "tetrahydropyranyl ether with p-toluenesulfonic acid. Six OCR/spacing variants of one name; Ivan "
            "(2026-10-03) asked for them resolved the same way. Flat: endo/exo is not expressed")
REWRITE_RAW = {
    "acetate ester of 1,5-dimethylcyclooct-1-en-5-ol":
        ("1,5-dimethylcyclooct-1-en-5-yl acetate", 'REVIEW-RULES "X of Y": the acetate ester of an alcohol is X-yl acetate', None),
    "ethylester of 6-methyl-bicyclo[2.2.1]hept-2-en-5-carboxylic acid":
        ("ethyl 6-methylbicyclo[2.2.1]hept-2-ene-5-carboxylate", 'REVIEW-RULES "X of Y": the ethyl ester of an acid', None),
    "formate of 1,5-dimethylbicyclo[3,2,1]octan-8-ol":
        ("1,5-dimethylbicyclo[3.2.1]octan-8-yl formate",
         'REVIEW-RULES "X of Y": the formate of an alcohol is X-yl formate (the patent writes [3,2,1] throughout; same structure)', None),
    "tetrahydropyranyl ether of 3-endo-methyl-3-exo (4'-methyl-5'-hydroxypentyl)norcamphor": (_THP, _THP_WHY, None),
    "tetrahydropyranyl ether of 3-endo-methyl-3-exo(4'- methyl 5' hydroxypentyl)norcamphor": (_THP, _THP_WHY, None),
    "tetrahydropyranyl ether of 3-endomethyl-3-exo(4-methyl-5-hydroxypentyl)norcamphor": (_THP, _THP_WHY, None),
    "3 endo-methyl-3-exo(4'-methyl-5'-hydroxypentyl) norcamphor": (_ALC, _ALC_WHY, None),
    "3-endo-methyl 3 exo(4' methyl 5 hydroxy- 1O pentyl)norcamphor": (_ALC, _ALC_WHY, None),
    "3-endo-methyl-3 exo(4' methyl 5'-hydroxypentyl) norcamphor": (_ALC, _ALC_WHY, None),
    "3-endo-methyl-3-exo(4 methyl 5' hydroxypentyl) norcamphor": (_ALC, _ALC_WHY, None),
    "3-endo-methyl-3-exo(4'-methyl- 5'-hydroxypentyl)norcamphor": (_ALC, _ALC_WHY, None),
    "3-endo-Methyl3-exo( 4 '-methyl-5 '-hydroxypentyl )norcamphor": (_ALC, _ALC_WHY, None),
    "6-oxa-l,1,2,3,3-pentamethyl-2;t3,5,6,7,8-hexahydro-1H-benz[ f] -indene":
        ("6-oxa-1,1,2,3,3-pentamethyl-2,3,5,6,7,8-hexahydro-1H-benz[f]indene",
         "OCR repair (l->1, '2;t3'->'2,3'); the SAME patent prints this compound correctly in Example 15(b): "
         "6-oxa-1,1,2,3,3 pentamethyl 2,3,5,6,7,8 hexahydro-1H-benz[f]-indene; the structure is a benzo-fused "
         "tetrahydropyran, matching the claim's 'tricyclic isochroman'", None),
    "1-spiro(4.5)-7/6-decen-7-yl-4 penten-1-one":
        ("1-(spiro[4.5]dec-7-en-7-yl)pent-4-en-1-one",
         "the sentence names the trademark Spirogalbanone(R); '7/6' is a locant ambiguity in the patent's own "
         "spelling. The structure is pinned to the PubChem record for the trademark (cross-check below)",
         "Spirogalbanone"),
    "4,7 dihydro-Z-isopentyl- 2-methyl-l,3-dioxepin":
        ("4,7-dihydro-2-isopentyl-2-methyl-1,3-dioxepin",
         "OCR: 'Z-' is '2-' (both isopentyl and methyl sit on ring atom 2, the ketal carbon). The mechanical repair "
         "read 'Z' as a stereodescriptor and put the isopentyl on ring C4 — a valid but wrong structure. The corpus "
         "holds the correct compound under two verbatim spellings of other patents ('2-(3-methylbutyl)-2-methyl-4,7-"
         "dihydro-1,3-dioxepin', '4,7-dihydro-2-isopentyl-2-methyl-1,3-dioxepin'), same InChIKey; PubChem has it as "
         "CID 104471 and has no record for the earlier reading. Joe (2026-10-03) called the earlier reading wrong and "
         "proposed this one; Ivan asked for it to be applied (2026-10-03). The compound has no stereocentre, so nothing is "
         "lost by a flat structure", None),
    "l,l-diethoxy-3-pentyl-5-isobutyl-4-hexene":
        ("1,1-diethoxy-2-pentyl-5-isobutyl-4-hexene",
         "US3584010A contradicts itself: Example 10 starts from '2-pentyl-5-isobutyl-4-hexen-1-al' (ethanol + "
         "orthoformate, i.e. the diethyl acetal), and an acetal keeps the skeleton, so the pentyl stays on C2 — the same "
         "pattern as Examples 3-6 (2,5-dimethyl-4-hexen-1-al -> 1,1-diethoxy-2,5-dimethyl-4-hexene) — but the product "
         "is printed '3-pentyl'. The span stays verbatim; Ivan (2026-10-03) chose the 2-pentyl structure. PubChem has "
         "a record for this isomer (CID 154113870) and none for the 3-pentyl reading", None),
    "2,6,6-trimethyl-l-[ l-hydroxybutyl]-cyclohex- 2-ene":
        ("2,6,6-trimethyl-1-(1-hydroxybutyl)cyclohex-1-ene",
         "US3892809A makes and uses the 1-ene alcohol (Examples 5 and 11a: '2,6,6-trimethyl-1-[1-hydroxybutyl]-"
         "cyclohex-1-ene'); the only 2-ene alcohols it makes carry a second ring OH. The '2' in 'cyclohex- 2-ene' (odour "
         "sentence) is read as an OCR slip or typo for '1'. Claude's reading, chosen by Ivan (2026-10-03); the span "
         "itself says 2-ene and PubChem has both alcohols, so nothing outside the patent decides it", None),
    "6,7-dihydro-1,l,2, 3,3-pentamethyl-4(5H)-indanone":
        ("6,7-dihydro-1,1,2,3,3-pentamethyl-4(5H)-indanone",
         "OCR repair (l->1). The name is printed once in US3847993A (the summary), so there is no second spelling; "
         "the structure is pinned by the patent's own chemistry instead: the ketone is the product of the allylic "
         "oxidation of 4,5,6,7-tetrahydro-1,1,2,3,3-pentamethylindane, a name the patent prints clean in claim 7 and "
         "four examples, and the process claim puts the carbonyl on a carbon allylic to the ring double bond (C4 and "
         "C7 are equivalent here). Hand-authorised by Ivan (2026-10-03); same structure OPSIN gave the repaired name, "
         "Joe's SMILES and PubChem agree with it", None),
}
REWRITE = {" ".join(k.lower().split()): v for k, v in REWRITE_RAW.items()}

# More hand-authorised rewrites live in corpus/structures/rewrites.json (curated data, same meaning as REWRITE_RAW: a span
# stays verbatim, the rewrite only decides which structure it stands for; each carries its reason). Added 2026-10-03.
REWRITE_FILE = OUT_DIR / "rewrites.json"
if REWRITE_FILE.exists():
    for _w in json.loads(REWRITE_FILE.read_text(encoding="utf-8"))["rewrites"]:
        REWRITE[" ".join(_w["raw"].lower().split())] = (_w["reading"], _w["why"], None)

# Text witnesses (curated 2026-10-03, Ivan): for an OCR-repaired name, a spelling of the SAME compound printed elsewhere in
# the SAME patent's text. The spelling is resolved by the same repair chain as the name and the name is lifted from
# PROVISIONAL to repaired+witness only if it gives the same structure. Unlike REWRITE this confirms a reading, never changes it.
TEXT_WITNESS = OUT_DIR / "text-witnesses.json"


def load_text_witnesses() -> dict:
    if not TEXT_WITNESS.exists():
        return {}
    return {" ".join(w["raw"].split()): w for w in json.loads(TEXT_WITNESS.read_text(encoding="utf-8"))["witnesses"]}


# ---------------------------------------------------------------- flags

FLAGS = [
    ("E/Z mixture", re.compile(r"\(\s*[EZ]\s*/\s*[EZ]\s*\)", re.I)),
    ("choice (or)", re.compile(r"\bor\b", re.I)),
    ("two names (; / and)", re.compile(r";|\band\b", re.I)),
    ("locant choice (8/9-)", re.compile(r"\d\s*/\s*\d")),
    ("contradictory stereo", re.compile(r"\(\s*(\d+)[EZ]\s*,\s*\1[EZ]\s*\)")),
    ("family (alkyl)", re.compile(r"alkyl", re.I)),
    ("derivative phrase (X of Y)", re.compile(r"\b(ester|ether|acetal|formate|acetate|oxime)\b.*\bof\b|\w+ of \d", re.I)),
]


def flags_for(raw: str) -> list[str]:
    return [n for n, rx in FLAGS if rx.search(raw)]


def squash(s: str) -> str:
    """name_variants.py's squash — deliberately aggressive, only used to find witnesses."""
    s = re.sub(r"[\s\-,\[\]()'′\"]", "", s.lower())
    return s.translate(str.maketrans("li", "11")).replace("o", "0")


# ---------------------------------------------------------------- main

def run() -> None:
    java = find_java()
    names = load_names()
    raws = {r for v in names.values() for r in v["raws"]}
    print(f"{len(names)} distinct names ({len(raws)} spellings) from approved, non-retired rows")

    rec = {}                                     # raw -> result dict
    for r in raws:
        rec[r] = {"raw": r, "tier": "unresolved", "attempt": None, "repairs": [], "smiles": None, "inchikey": None}

    def settle(todo, make, tier, **kw):
        res = resolve_batch(java, [make(r)[0] for r in todo], **kw)
        left = []
        for r in todo:
            s, used = make(r)
            if s in res:
                rec[r].update(tier=tier, attempt=s, repairs=used, smiles=res[s][0], inchikey=res[s][1])
            else:
                left.append(r)
        return left

    collapse = lambda r: (" ".join(r.split()), [])
    fmt = lambda r: repair(" ".join(r.split()), FORMATTING)
    ocr = lambda r: repair(" ".join(r.split()), FORMATTING + OCR)

    left = settle(sorted(raws), collapse, "verbatim")
    print(f"  verbatim        {len(raws) - len(left):>5}")
    # A hand-authorised rewrite outranks the mechanical repairs: hold those names back from the formatting and OCR
    # passes, or an OCR reading that is valid but wrong would win (A5, 2026-10-03: "Z-" read as a stereodescriptor).
    held = [r for r in left if " ".join(r.lower().split()) in REWRITE]
    left = [r for r in left if r not in held]
    n = len(left); left = settle(left, fmt, "formatting"); print(f"  formatting      {n - len(left):>5}")
    n = len(left); left = settle(left, ocr, "ocr"); print(f"  ocr             {n - len(left):>5}")
    left += held
    def rewrite_of(r):
        v = REWRITE.get(" ".join(r.lower().split()))
        return (v[0], ["REWRITE"]) if v else (None, [])
    todo_rw = [r for r in left if rewrite_of(r)[0]]
    res = resolve_batch(java, [rewrite_of(r)[0] for r in todo_rw])
    n = len(left)
    for r in todo_rw:
        s_, _ = rewrite_of(r)
        if s_ in res:
            v = REWRITE[" ".join(r.lower().split())]
            rec[r].update(tier="rewrite", attempt=s_, repairs=["REWRITE"], smiles=res[s_][0], inchikey=res[s_][1],
                          rewrite_why=v[1], pubchem_check=v[2])
            left.remove(r)
    print(f"  rewrite         {n - len(left):>5}")
    n = len(left); left = settle(left, ocr, "stereo_dropped", drop_stereo=True); print(f"  stereo_dropped  {n - len(left):>5}")
    print(f"  unresolved      {len(left):>5}   (stage 2: PubChem name lookup, on Hetzner)")

    # one record per KEY. A key can have several spellings; the best tier wins, disagreement is flagged.
    order = ["verbatim", "formatting", "ocr", "rewrite", "stereo_dropped", "unresolved"]
    out = []
    for key, v in sorted(names.items()):
        rs = sorted((rec[r] for r in v["raws"]), key=lambda x: (order.index(x["tier"]), x["raw"]))
        best = dict(rs[0])
        fb = {x["inchikey"][:14] for x in rs if x["inchikey"]}
        best.update(key=key, spellings=sorted(v["raws"]), rows=v["rows"], n_sources=len(v["sources"]),
                    tags=sorted(v["tags"]), scopes=sorted(v["scopes"]),
                    flags=sorted({f for r in v["raws"] for f in flags_for(r)}),
                    spellings_disagree=len(fb) > 1)
        out.append(best)

    # witnesses for the repairs
    groups = collections.defaultdict(list)
    for o in out:
        groups[squash(o["raw"])].append(o)
    for o in out:
        o["witness"] = None
        if o["tier"] in ("formatting", "ocr") and o["inchikey"]:
            w = [g for g in groups[squash(o["raw"])] if g is not o and g["tier"] == "verbatim"]
            if w:
                o["witness"] = "agree" if all(g["inchikey"][:14] == o["inchikey"][:14] for g in w) else "DISAGREE"

    # text witnesses: a second spelling from the patent's own text, resolved the same way, must give the same structure
    twit = load_text_witnesses()
    todo_tw = [o for o in out if o["tier"] in ("formatting", "ocr") and o["inchikey"] and o["witness"] is None
               and " ".join(o["raw"].split()) in twit]
    if todo_tw:
        spell = {id(o): repair(" ".join(twit[" ".join(o["raw"].split())]["spelling"].split()), FORMATTING + OCR)[0] for o in todo_tw}
        got = resolve_batch(java, list(spell.values()))
        for o in todo_tw:
            w, s = twit[" ".join(o["raw"].split())], spell[id(o)]
            same = s in got and got[s][1][:14] == o["inchikey"][:14]
            o["text_witness"] = {"patent": w["patent"], "spelling": w["spelling"], "where": w["where"], "resolved": s if s in got else None}
            if s in got:
                o["witness"] = "text" if same else "DISAGREE"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(out)} lines)")
    report(out)


def report(out=None) -> None:
    if out is None:
        out = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines()]
    c = collections.Counter(o["tier"] for o in out)
    print("\n== BY TIER (distinct names; rows in brackets)")
    for t in ("verbatim", "formatting", "ocr", "rewrite", "stereo_dropped", "unresolved"):
        print(f"  {t:<15}{c[t]:>5}   [{sum(o['rows'] for o in out if o['tier'] == t)} rows]")
    res = [o for o in out if o["inchikey"]]
    print(f"\n== DISTINCT STRUCTURES among the {len(res)} resolved names")
    print(f"  full InChIKey (stereo kept)     {len({o['inchikey'] for o in res})}")
    print(f"  connectivity block (flat)       {len({o['inchikey'][:14] for o in res})}")
    w = collections.Counter(o["witness"] for o in out if o["tier"] in ("formatting", "ocr"))
    print("\n== REPAIR CHECK (repaired names vs another VERBATIM spelling of the same molecule)")
    print(f"  agree {w['agree']} · text-witnessed {w['text']} · DISAGREE {w['DISAGREE']} · no witness {w[None]}")
    for o in out:
        if o["witness"] == "DISAGREE":
            print(f"    DISAGREE  {o['raw']!r}  ->  {o['attempt']!r}")
    d = [o for o in out if o["spellings_disagree"]]
    print(f"\n== SPELLINGS OF ONE KEY THAT RESOLVE TO DIFFERENT STRUCTURES: {len(d)}")
    for o in d:
        print("   ", o["spellings"])
    fl = collections.defaultdict(list)
    for o in out:
        for f in o["flags"]:
            fl[f].append(o)
    print("\n== NOT A DEFINITE STRUCTURE? flagged for Ivan (REVIEW-RULES: a definite structure, or no row)")
    for f, os_ in sorted(fl.items()):
        print(f"  {f}: {len(os_)}")
        for o in os_[:6]:
            print(f"      {o['raw']!r}  [{o['tier']}]")


def todo() -> None:
    """The Hetzner work list. `todo` = names OPSIN could not read (and that are not flagged as
    non-definite). `check` = a seeded sample of names OPSIN DID resolve verbatim, sent through the
    same PubChem lookup so OPSIN's precision is measured against an independent resolver."""
    import random
    out = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines()]
    send = lambda o: repair(" ".join(o["spellings"][0].split()), FORMATTING)[0]
    t = [{"key": o["key"], "name": send(o)} for o in out if o["tier"] == "unresolved" and not o["flags"]]
    v = sorted((o for o in out if o["tier"] == "verbatim"), key=lambda o: o["key"])
    random.Random(20261003).shuffle(v)
    # Keep the sample STABLE across reruns: names PubChem has already answered come first, so a change
    # in the name set (a reject, a split) does not re-draw the sample and orphan the cached answers.
    cached = set(json.loads(PC_OUT.read_text(encoding="utf-8"))["names"]) if PC_OUT.exists() else set()
    v = [o for o in v if send(o) in cached] + [o for o in v if send(o) not in cached]
    c = [{"key": o["key"], "name": send(o)} for o in v[:80]]
    missing = pubchem_side_missing_cids()
    extra = [{"key": k, "name": v[2]} for k, v in sorted(REWRITE.items()) if v[2]]
    TODO.write_text(json.dumps({"todo": t, "check": c, "extra": extra, "cids": missing}, ensure_ascii=False, indent=0),
                    encoding="utf-8")
    skipped = sum(1 for o in out if o["tier"] == "unresolved" and o["flags"])
    print(f"{len(t)} names to resolve + {len(c)} verbatim names to cross-check + {len(missing)} CIDs lacking an InChIKey"
          f" -> {TODO.relative_to(ROOT)}"
          f"   ({skipped} unresolved + flagged left out)")


# ---------------------------------------------------------------- the PubChem half, for the join

SMILES_CACHE = ROOT / "corpus" / "raw-pubchem" / "smiles.json"
PC_OUT = OUT_DIR / "pubchem-names.json"
FINAL = OUT_DIR / "names.jsonl"


def _rows(name: str) -> list[dict]:
    p = ROOT / "corpus" / "rows" / f"{name}.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith('{"_comment"')]


def pubchem_side_rows() -> list[dict]:
    """The PubChem-half rows status.py counts: not excluded; physdesc rows only if not held."""
    rows = [r for r in _rows("pubchem-rows") if not r.get("excluded")]
    rows += [r for r in _rows("pubchem-physdesc-rows")
             if not (r.get("needs_review") and r.get("review_decision") != "approve")]
    return rows


def pubchem_side_missing_cids() -> list[int]:
    sm = json.loads(SMILES_CACHE.read_text(encoding="utf-8"))
    return sorted({r["molecule_cid"] for r in pubchem_side_rows()
                   if r.get("molecule_cid") and not sm.get(str(r["molecule_cid"]), {}).get("inchikey")})


# PubChem's name match is a synonym match, and a depositor's synonym can be wrong or generic. These
# were read against the PubChem title/IUPAC name on 2026-10-03 (Claude's reading — Ivan or Joe can
# overrule, and the reason is stored with the record). VETO: the structure is wrong for the span,
# so the name stays unresolved. CHECK: plausible but not confirmable from here (generic name or an
# unverifiable trade name) — kept, marked, and never merged with another name.
VETO = {
    "cyclohexal": "PubChem match is Cyclobarbital (a barbiturate), not a perfumery material",
    "l-isomer": "a fragment ('the l-isomer'), not a molecule name; PubChem match is lactic acid",
}
CHECK = {
    "terpineol": "generic: alpha-, beta-, gamma-terpineol and mixtures are all 'terpineol'; PubChem gave alpha",
    "cineole": "generic: 1,8- vs 1,4-cineole; PubChem gave 1,8-cineole",
    "pinoacetaldehyde": "PubChem gave the PROPanal (3 C); an acetaldehyde name suggests the 2-carbon chain",
    "nojigiku alcohol": "single depositor synonym -> 6-camphenol; not confirmable here",
    "methoxyelgenol": "trade name; one depositor synonym -> 7-methoxy-3,7-dimethyloctan-2-ol",
    "terranol": "trade name; one depositor synonym; not confirmable here",
}


def pick_pubchem(entry: dict, cids: dict):
    """One name's PubChem answer -> (cid, inchikey, smiles, why) or (None, ..., why).
    Accept only if EVERY record the name matched has the same connectivity block (a name that
    matches two different structures is ambiguous, not resolved). Among stereo variants of that
    one skeleton prefer the FLAT record — the span did not specify stereo — else the first."""
    if entry["status"] != "found":
        return None, None, None, entry["status"]
    recs = [(c, cids.get(str(c))) for c in entry["cids"]]
    recs = [(c, r) for c, r in recs if r and r.get("inchikey")]
    if not recs:
        return None, None, None, "no-properties"
    if len({r["inchikey"][:14] for _, r in recs}) > 1:
        return None, None, None, "ambiguous (matches different structures)"
    flat = [(c, r) for c, r in recs if r["inchikey"].endswith("-UHFFFAOYSA-N")]
    c, r = (flat or recs)[0]
    return c, r["inchikey"], r["smiles"], "flat-record" if flat else ("single-record" if len(recs) == 1 else "first-record")


def merge() -> None:
    if not PC_OUT.exists():
        sys.exit(f"{PC_OUT.relative_to(ROOT)} missing — run stage 2 on Hetzner and scp it back")
    pc = json.loads(PC_OUT.read_text(encoding="utf-8"))
    work = json.loads(TODO.read_text(encoding="utf-8"))
    out = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines()]
    by_key = {o["key"]: o for o in out}
    sent = {e["key"]: e["name"] for e in work["todo"]}
    chk = {e["key"]: e["name"] for e in work["check"]}

    # ---- the cross-check: OPSIN (verbatim) vs PubChem's name match, same names
    agree = dis = nf = amb = 0
    rows_dis = []
    for k, nm in chk.items():
        o = by_key[k]
        c, ik, smi, why = pick_pubchem(pc["names"].get(nm, {"status": "error", "cids": []}), pc["cids"])
        if ik is None:
            if why == "notfound":
                nf += 1
            else:
                amb += 1
            continue
        if ik[:14] == o["inchikey"][:14]:
            agree += 1
        else:
            dis += 1
            rows_dis.append((nm, o["smiles"], smi))
    n = agree + dis
    print("== OPSIN vs PubChem on the same names (verbatim-resolved sample)")
    print(f"  compared {n} · same structure {agree} · DIFFERENT {dis} · PubChem has no match {nf} · ambiguous/other {amb}")
    for nm, a, b in rows_dis:
        print(f"    DIFFERENT  {nm!r}\n        OPSIN   {a}\n        PubChem {b}")

    # ---- fold PubChem answers into the unresolved names
    got = collections.Counter()
    for k, nm in sent.items():
        o = by_key[k]
        c, ik, smi, why = pick_pubchem(pc["names"].get(nm, {"status": "error", "cids": []}), pc["cids"])
        got[why] += 1
        if ik and k in VETO:
            o["veto"] = VETO[k]
            got["VETOED"] += 1
        elif ik:
            o.update(tier="pubchem", smiles=smi, inchikey=ik, cid=c, pubchem_pick=why, attempt=nm)
            if k in CHECK:
                o["check_note"] = CHECK[k]
    print("\n== stage 2 on the unresolved names:", dict(got))

    # ---- rewrites that name a PubChem record to cross-check against
    for o in out:
        if o["tier"] == "rewrite" and o.get("pubchem_check"):
            c_, ik_, smi_, why_ = pick_pubchem(pc["names"].get(o["pubchem_check"], {"status": "error", "cids": []}), pc["cids"])
            o["rewrite_pubchem"] = ("no match" if ik_ is None else "agree" if ik_[:14] == o["inchikey"][:14] else "DIFFER")
            o["rewrite_pubchem_smiles"] = smi_
            print(f"\n== REWRITE CROSS-CHECK {o['raw']!r}\n   rewrite  {o['attempt']}  {o['smiles']}\n"
                  f"   PubChem  {o['pubchem_check']!r} -> {why_}  {smi_}   => {o['rewrite_pubchem']}")

    # ---- trust
    for o in out:
        t = o["tier"]
        o["trust"] = (
                      "REWRITE-CHECK" if t == "rewrite" and o.get("rewrite_pubchem") in ("DIFFER", "no match") else
                      "rewritten" if t == "rewrite" else"verbatim" if t == "verbatim" else
                      "PUBCHEM-CHECK" if t == "pubchem" and o.get("check_note") else
                      "pubchem" if t == "pubchem" else
                      "flat" if t == "stereo_dropped" else
                      "repaired+witness" if t in ("formatting", "ocr") and o.get("witness") in ("agree", "text") else
                      "PROVISIONAL" if t in ("formatting", "ocr") else "none")
    FINAL.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out), encoding="utf-8")
    print(f"wrote {FINAL.relative_to(ROOT)}")
    c = collections.Counter(o["trust"] for o in out)
    print("\n== FINAL, by trust (distinct names)")
    for t in ("verbatim", "pubchem", "repaired+witness", "rewritten", "flat", "PUBCHEM-CHECK", "REWRITE-CHECK", "PROVISIONAL", "none"):
        print(f"  {t:<17}{c[t]:>5}")
    print("  (PROVISIONAL = repaired without a second spelling to confirm it; PUBCHEM-CHECK = generic/trade name,"
          " see check_note; neither is ever merged with another name)")
    for o in out:
        if o["trust"] == "PUBCHEM-CHECK":
            print(f"      CHECK  {o['raw']!r}: {o['check_note']}")
        if o.get("veto"):
            print(f"      VETO   {o['raw']!r}: {o['veto']}")
    for o in out:
        if o["trust"] == "PROVISIONAL":
            print(f"      {o['raw']!r}\n          -> {o['attempt']!r}  {o['smiles']}")
    unresolved = [o for o in out if o["trust"] == "none"]
    print(f"\n== STILL WITHOUT A STRUCTURE: {len(unresolved)} names, {sum(o['rows'] for o in unresolved)} rows")
    for o in sorted(unresolved, key=lambda o: o["key"]):
        print(f"    {'[' + ','.join(o['flags']) + '] ' if o['flags'] else ''}{o['spellings'][0]!r}")
    print("\nstructure-based tag counts: python3 pipeline/status.py (it owns that definition since 2026-10-03)")


if __name__ == "__main__":
    if "--report" in sys.argv:
        report()
    elif "--todo" in sys.argv:
        todo()
    elif "--merge" in sys.argv:
        merge()
    else:
        run()
