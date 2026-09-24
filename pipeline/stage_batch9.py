#!/usr/bin/env python3
"""Stage batch 9 (hedione_pool.py 100 --noise2-first --seed 20260925 --out /tmp/b9/batch.json, 2026-09-24). Copy of the fixed template.

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
batch=json.load(open('/tmp/b9/batch.json'))
ANA="Anaphoric subject — no compound named here."; FAM="A family or formula class, not a definite compound."
GEN="A general or background statement; nothing attributed to a compound."; TRUNC="Truncated before the odour claim completes."
COMPO="Composition-level — the odour belongs to the product, not a compound."
D={
1:('R',[],FAM),
2:('R',[],"Composition-level ('Said fragrance')."),
3:('R',[],"'aldehyde V' — pointer."),
4:('R',[],'Blend effect.'),
5:('R',[],"'a mixture of 4 isomers' — the mixture rule."),
6:('R',[],"'the lower aliphatic ethers of cedrol' — which ether? A family."),
7:('R',[],FAM),
8:('A', ['cyclohexylmethanol'], "The same Arctander quote approved in batch 8, second patent (spelled 'slightly' here). A true row; adds no molecule. 'Patchouli' and 'Flower' (book title) dropped."),
9:('R',[],"'the latter' — ANA"),
10:('R',[],"'the latter ester' — ANA"),
11:('R',[],"Taste; 'Compounds I (a,b,c)' — pointers."),
12:('R',[],"A class ('cyclic dioxanes having ambery notes') illustrated by trade names with pointers; Karanal is sold as an isomer mix. When in doubt, reject."),
13:('R',[],FAM),
14:('R',[],'Flavour, no compound.'),
15:('R',[],'An extract.'),
16:('R',[],"'an acetal' — which? No compound named."),
17:('R',[],"'The solid' — ANA"),
18:('R',[],"A general statement about a class ('Alcohols such as…')."),
19:('R',[],FAM),
20:('R',[],"Taste; 'the (S) one' — anaphora."),
21:('R',[],"'the particular isomer' — ANA"),
22:('R',[],GEN),
23:('R',[],GEN),
24:('R',[],"'The major peak' — not a compound."),
25:('R',[],FAM),
26:('A', ['acetaldehyde ethyl linalyl acetal'], "Named, direct ('By comparison' refers to the compound compared, not the odour). 'linalool' is a substance — dropped. New molecule."),
27:('R',[],FAM),
28:('R',[],FAM),
29:('R',[],'Truncated; subject is a patent number.'),
30:('R',[],GEN),
31:('R',[],"'Those isomers' — "+FAM),
32:('R',[],"'the former' — ANA"),
33:('R',[],GEN),
34:('R',[],"'Material 1' — pointer."),
35:('R',[],GEN),
36:('R',[],"'the resulting product' — flavour product."),
37:('R',[],"'a solid acetyl derivative' — no compound named."),
38:('R',[],'Lilial/Lyral again (second patent). You rejected this split whole in batch 8 — following that.'),
39:('R',[],"Composition-level; 'dioxaspiro compound' is a family."),
40:('R',[],'Truncated citation; no compound named.'),
41:('R',[],"'4' — pointer."),
42:('R',[],GEN),
43:('R',[],"'IX) This' — pointer."),
44:('R',[],FAM),
45:('R',[],"'dehydrorhodinol (VI)' — rhodinol is itself a trade blend, so the dehydro- of it is not one definite compound. When in doubt, reject."),
46:('R',[],GEN),
47:('R',[],'Truncated; subject is a patent number.'),
48:('R',[],GEN),
49:('R',[],GEN),
50:('R',[],"'this decatrienoate' — anaphora, and a comparison."),
51:('R',[],"'ethylene glycol monoaryl ethers' — "+FAM),
52:('R',[],'Truncated; subject is a patent number.'),
53:('R',[],'Composition-level.'),
54:('R',[],'Product-level (cigarettes).'),
55:('A', ['ethylene glycol monophenyl ether'], "Named single compound (2-phenoxyethanol), odour attributed to it. 'acid' is from 'Citric acid' — dropped. PubChem already holds 2-phenoxyethanol ('aromatic'); the weak name join will count this separately."),
56:('A', ['cinnamonitrile'], "Named, direct. 'cinnamaldehyde' is a substance comparison; 'green' carries the row. New molecule."),
57:('A', ['coumarin'], "Named, direct — 'having a hay like bittersweet odour'. PubChem has coumarin (hay, vanilla); patents did not."),
58:('R',[],'Composition-level.'),
59:('R',[],FAM),
60:('R',[],'Not an odour sentence.'),
61:('R',[],'Cigarette smoke.'),
62:('A', ['alpha-ionylideneethane'], 'Named, direct. New molecule.'),
63:('R',[],"'ketonic acylated product' — a reaction product."),
64:('R',[],GEN),
65:('A', ['4,5 -decamethyleneoxazole'], 'Named (with a stray OCR space) plus a formula label, direct. New molecule. Check it resolves.'),
66:('R',[],"'mixture J' — the mixture rule."),
67:('R',[],FAM),
68:('R',[],GEN),
69:('R',[],GEN),
70:('R',[],"'The (-)-S methylester' of what? — anaphora; and the R half is 'the (+)-R isomer'."),
71:('R',[],"'a mixture of 5 stereoisomers' — the mixture rule."),
72:('R',[],'Both lactates are ALREADY approved from this same patent; a split here would add nothing, and splits are the weak proposal.'),
73:('R',[],'Truncated; subject is a patent number.'),
74:('R',[],"'nerol compound A' — pointer, and a >90% blend."),
75:('A', ['menthol'], "Named, direct — 'its strong minty odor'. Already in the corpus; a further attestation."),
76:('R',[],FAM),
77:('R',[],GEN),
78:('R',[],'No compound named.'),
79:('R',[],GEN),
80:('R',[],'Product-level (pellets).'),
81:('R',[],"'The beta,gamma-isomer' — ANA"),
82:('A', ['cis-rose oxide'], "Named, direct; geranium and peppermint are plants named as smells. The trans half has no descriptor ('somewhat intense'), so no split — approve the cis half alone. New molecule."),
83:('R',[],GEN),
84:('A', ['Nojigiku alcohol'], "Trivial name for one natural compound, direct. 'floral perfume' is usage. New molecule. Borderline: check it resolves."),
85:('R',[],'Truncated; subject is a patent number.'),
86:('R',[],"'The resultant mixture' — the mixture rule."),
87:('A', ['S-ethenyl-epi-camphene hydrate'], "Named, 'useful as an odorant per se, having…' — direct. New molecule."),
88:('R',[],FAM),
89:('R',[],"'The derivatives' — "+FAM),
90:('A', ['menthol'], "Named, direct — 'menthol has a strong minty odor'. Already in; a further attestation."),
91:('R',[],"'isomethone' is a misspelling (isomenthone) — the name as written does not resolve. When in doubt, reject."),
92:('R',[],'Cigarette smoke.'),
93:('R',[],FAM),
94:('R',[],"'The material' — ANA"),
95:('R',[],"Negation — 'none … exhibit'."),
96:('R',[],'Cigarette smoke.'),
97:('R',[],'\'the "cis" isomer\' — '+ANA),
98:('R',[],'Composition-level, mixtures.'),
99:('A', ['iso-pulegone'], "Named (Arctander, quoted). 'not as sweet as pulegone' is negation — 'sweet' dropped. New molecule."),
100:('R',[],"'they' — anaphora, and a comparison."),
}
forms=sorted(surf,key=len,reverse=True); rx=re.compile(r"\b("+"|".join(map(re.escape,forms))+r")\b", re.I)
EXCL={8:{'patchouli','flower'},26:{'linalool'},55:{'acid'},56:{'cinnamaldehyde'},84:{'perfume'},99:{'sweet','pulegone'},82:{'rose'},57:{'bittersweet'},62:set(),65:set(),75:{'menthol'},87:set(),90:{'menthol'}}
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
