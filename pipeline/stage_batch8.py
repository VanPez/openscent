#!/usr/bin/env python3
"""Stage batch 8 (hedione_pool.py 100 --noise2-first --seed 20260924 --out /tmp/b8/batch.json, 2026-09-24). Copy of the fixed template.

Pattern established over batches 1-4 (2026-09-23). Copy this file, fill in D,
run it, then `python3 pipeline/propose.py apply`.

  D[i] = (decision, [molecule spans], "why")
     decision is 'A' approve / 'R' reject / 'S' split
     i is the 1-based position in the batch JSON, NOT a review.jsonl row index
     molecule spans are hand-specified and MUST be verbatim substrings
     descriptors are AUTO-EXTRACTED from the ontology, so verbatim by construction

  EXCL[i] = {"term", ...} drops ontology terms that appear only in a COMPARISON
     clause ("reminiscent of cedar") or belong to a flavour rather than an odour.

THE GUARANTEE: every span is substring-checked against its own sentence and the
script REFUSES TO WRITE if any check fails. It has never had to. Do not weaken it.

ROW MATCHING is on (source_id, FULL whitespace-normalised sentence), NOT on row
index — propose.py keys on index and a split shifts every index behind it.
Bug 4 (fixed 2026-09-24): this used to key on the first 110 chars, which collides
(68 keys / 151 rows); it put a batch-5 proposal on the wrong row and skipped two
batch-6 rows. The full sentence still repeats across split copies (34 keys, all
parent/split_of pairs), so a key maps to a LIST: the match is the one undecided
row; none undecided = skipped and reported; more than one = REFUSE.
Already-decided rows are never overwritten.

INPUT  /tmp/batch.json   (from pipeline/hedione_pool.py)
OUTPUT pipeline/propose-batch.jsonl + propose-in.jsonl
"""
import json, re, importlib.util, pathlib, collections
ROOT=pathlib.Path('.').resolve()
spec=importlib.util.spec_from_file_location("status", ROOT/"pipeline/status.py")
st=importlib.util.module_from_spec(spec); spec.loader.exec_module(st)
surf=st.load_tags()
rows=[]
for l in open('corpus/rows/review.jsonl',encoding='utf-8'):
    l=l.strip()
    if not l or l.startswith('{"_comment"'): continue
    rows.append(json.loads(l))
def key(r): return (r['source_id'], re.sub(r'\s+',' ',r.get('sentence','')).strip())   # FULL sentence — bug 4
idx=collections.defaultdict(list)
for i,r in enumerate(rows): idx[key(r)].append(i)   # a list: split copies share their parent's sentence
batch=json.load(open('/tmp/b8/batch.json'))
ANA="Anaphoric subject — no compound named here."; FAM="A family or formula class, not a definite compound."
GEN="A general or background statement; nothing attributed to a compound."; TRUNC="Truncated before the odour claim completes."
COMPO="Composition-level — the odour belongs to the product, not a compound."
D={
1:('A', ['Myrcene'], "Named, direct: 'The odor of Myrcene is…'. Myrcene is in the corpus only with 'fresh hops' (US20220064566A1), so this adds tags."),
2:('R',[],"'diastereomer mixture' — the mixture rule, and 'the propionate' is anaphoric."),
3:('R',[],"Composition-level, and 'dioxaspiro compound' is a family."),
4:('R',[],"'The unsaturated nitrile (VIII)' / '(IX)' — pointers."),
5:('R',[],'A flavour blend, no compound.'),
6:('R',[],"'The cis-isomer I'a' — pointer."),
7:('R',[],"'a perfume and perfume base comprising…' — the smell is the base's; the name is also OCR-garbled."),
8:('R',[],"'Peak 3' — pointer."),
9:('A', ['ethyl ether of allo-ocimenol'], "'the X of Y' derivative that picks out one compound (ethylate the OH) — whole phrase recorded per the derivative rule. New molecule."),
10:('A', ['Bis (cyclohexyl) disulfide'], "Named, direct. Aroma clause only: 'sweet', 'nutty', 'minty', 'bitter', 'musty' belong to the TASTE clause and are dropped. New molecule."),
11:('R',[],GEN),
12:('R',[],"'substituted phenols' — "+FAM),
13:('R',[],"'The macrocyclic lactones' — "+FAM),
14:('R',[],"'Material 2' — pointer."),
15:('R',[],FAM),
16:('A', ['cyclohexylmethanol'], "Named, direct (Arctander, quoted). 'Patchouli' is a remote comparison — dropped. New molecule."),
17:('R',[],"'Formula (1)' — pointer."),
18:('A', ['citronellyl lactate'], "Named, direct. 'less natural than the (R)-citronellyl lactate' is a comparison — dropped. New molecule (the (R)- form is already in from this patent). Borderline: unspecified stereo, like most trivial names."),
19:('R',[],'Truncated; subject is a numeral.'),
20:('R',[],"Trade name with no odour attributed — 'unique odour qualities'."),
21:('R',[],'An extract, not a compound.'),
22:('R',[],"'mixture J' — the mixture rule."),
23:('R',[],FAM),
24:('R',[],FAM),
25:('R',[],FAM),
26:('R',[],'Composition-level.'),
27:('R',[],'Flavour of coffee, not a compound.'),
28:('R',[],FAM),
29:('R',[],GEN),
30:('R',[],GEN),
31:('R',[],"'a new class of substituted indanones' — "+FAM),
32:('R',[],"'The pure Ia' — pointer."),
33:('R',[],"'the ethyl- and isopropylester of last mentioned acid' — anaphora."),
34:('R',[],'Truncated; subject is a patent number.'),
35:('R',[],'Truncated; subject is a patent number.'),
36:('R',[],"'(Mixture)', a formula label, and a comparison."),
37:('R',[],GEN),
38:('R',[],'A process claim.'),
39:('R',[],"'mixture C' — the mixture rule."),
40:('R',[],GEN),
41:('R',[],'Composition-level.'),
42:('R',[],"'A mixture of geometrical and optical isomers' — the mixture rule."),
43:('A', ['Caryophyllene'], "Named, direct. 'cedar wood' is a wood named as a smell (source, not substance). Already in the corpus as woody (US3965189A) — a second attestation, few or no new tags."),
44:('A', ['trithioacetone'], "Named, direct — 'notes which it possesses'. Same patent already gave trithioacetone 'green'; this adds 'leafy' at most."),
45:('R',[],"'Structure IV' — pointer."),
46:('R',[],'Truncated; subject is a patent number.'),
47:('R',[],FAM),
48:('R',[],"'Formula XVI' — pointer."),
49:('R',[],"'Fraction 6' — a fraction, not a compound."),
50:('R',[],'Composition-level.'),
51:('R',[],"'Fractions of the propionate' — anaphora, and fractions."),
52:('R',[],'Truncated; subject is a patent number.'),
53:('R',[],FAM),
54:('R',[],"'alcohol 23 as a mixture of two diastereoisomers' — pointer and mixture."),
55:('R',[],GEN),
56:('R',[],'Product-level (pellets).'),
57:('R',[],'An essential oil.'),
58:('R',[],"'a novel tetracyclic oxide' — no definite compound."),
59:('R',[],"'it' — anaphora, and a comparison."),
60:('R',[],GEN),
61:('R',[],'Product-level (towel).'),
62:('R',[],GEN),
63:('R',[],FAM),
64:('R',[],"'neutral odor' — no descriptor."),
65:('A', ['Thujone'], "Named, direct. 'menthol' is a substance comparison — dropped. Borderline: bare 'thujone' is usually an α/β blend, the loose reading you used for Terpineol. New molecule by name."),
66:('R',[],"'Both acetals' — anaphora."),
67:('R',[],"'Alcohol (IIA)' / '(IIB)' — pointers."),
68:('R',[],'Truncated; subject is a patent number.'),
69:('R',[],"OCR-garbled, 'materials of this nature'."),
70:('R',[],'Blend effect on a geranium top note.'),
71:('R',[],'A flavour containing the carbonate — composition-level.'),
72:('R',[],GEN),
73:('R',[],'No compound named.'),
74:('R',[],"'I' — pointer."),
75:('R',[],GEN),
76:('R',[],'No compound named.'),
77:('R',[],"'The octenyl acetate' — octenyl without a locant is not one compound."),
78:('S', [], "TWO trade names, DIFFERENT descriptions: Lilial — lily of the valley, watery; Lyral — floral, lily of the valley ('hydroxycitronellal' is a substance, drop it). Both halves are named subjects, so this split has two live halves (unlike the pointer splits you rejected)."),
79:('R',[],"'the former/latter compound' — anaphora."),
80:('R',[],"'Octan-B-One Oxime' is OCR (octan-3-one?) — the name as written does not resolve. When in doubt, reject."),
81:('R',[],GEN),
82:('A', ['Calone'], "Trade name for one defined compound, direct. 'oysters' is a food named as a smell. New molecule. Check the trade name resolves."),
83:('R',[],GEN),
84:('R',[],"'Thiols' — "+FAM),
85:('R',[],GEN),
86:('R',[],'Peppermint oil fractions; OCR-garbled.'),
87:('A', ['pentyl butanoate'], "Named, direct: 'known for resembling the smell of a pear or apricot'. 'sweet'/'fruity' are in the usage clause about fragrances, dropped. New molecule."),
88:('R',[],'Truncated; subject is a patent number.'),
89:('R',[],"'isomeric ester mixture' — the mixture rule, and a comparison."),
90:('R',[],"'bicyclic-cyclobutanones' — "+FAM),
91:('R',[],"OCR-garbled; 'They'."),
92:('R',[],"Taste, and 'the (S) one' — anaphora."),
93:('R',[],"'The derivative' — anaphora."),
94:('R',[],"Magnolan is sold as an isomer mixture; 'having a floral note' names the class. When in doubt, reject."),
95:('R',[],"'Tetraalkylperhydroindanone' — "+FAM),
96:('R',[],'Blend effect on compositions.'),
97:('R',[],"'The cyclohexene derivatives' — "+FAM),
98:('R',[],"'compounds 3 and 4' — pointers."),
99:('R',[],"Trade name compared to an oil; negation ('less pronounced')."),
100:('R',[],'Product-level (aerosol).'),
}
forms=sorted(surf,key=len,reverse=True); rx=re.compile(r"\b("+"|".join(map(re.escape,forms))+r")\b", re.I)
EXCL={10:{'sweet','nutty','minty','mint','bitter','musty'},16:{'patchouli','flower'},18:{'natural','powerful'},65:{'menthol'},87:{'sweet','fruity'},1:set(),9:{'perfume'},43:set(),44:set(),82:set()}
bo=[];inb=[];bad=[];skip=[]
for i,r in enumerate(batch,1):
    dec,mols,why=D[i]
    k=key(r)
    if k not in idx: bad.append((i,'not found')); continue
    open_=[n for n in idx[k] if not rows[n].get('decision')]
    if not open_: skip.append(i); continue
    if len(open_)>1: bad.append((i,f"AMBIGUOUS: {len(open_)} undecided rows share this sentence {open_}")); continue
    n=open_[0]; row=rows[n]; s=row['sentence']
    descs=[]
    if dec=='A':
        seen=set()
        for m in rx.finditer(s):
            w=m.group(0)
            if w.lower() in EXCL.get(i,set()) or w.lower() in seen: continue
            seen.add(w.lower()); descs.append(w)
    for v in mols+descs:
        if v not in s: bad.append((i,f"NOT VERBATIM {v!r}"))
    bo.append({"n":n,"source_id":row['source_id'],"char_offset":row.get('char_offset'),"sentence":s})
    inb.append({"n":n,"decision":{'A':'approve','R':'reject','S':'split'}[dec],"molecules":mols,"descriptors":descs,
        "why":why+("  [descriptors = every ontology form present; trim comparisons]" if dec=='A' else "")})
if bad:
    print("REFUSING:"); [print("  ",b) for b in bad[:20]]; raise SystemExit(1)
pathlib.Path('pipeline/propose-batch.jsonl').write_text("\n".join(json.dumps(b,ensure_ascii=False) for b in bo)+"\n",encoding='utf-8')
pathlib.Path('pipeline/propose-in.jsonl').write_text("\n".join(json.dumps(b,ensure_ascii=False) for b in inb)+"\n",encoding='utf-8')
print("skipped:",skip); print(f"{len(inb)} staged: {dict(collections.Counter(x['decision'] for x in inb))}")
