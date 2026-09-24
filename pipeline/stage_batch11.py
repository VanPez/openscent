#!/usr/bin/env python3
"""Stage batch 11 — TARGETED tobacco+apple sweep (all 76 undecided rows with a tobacco/apple/appley form, no noise filter, no cap; drawn inline 2026-09-24 to /tmp/b11/batch.json). Copy of the fixed template.

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
batch=json.load(open('/tmp/b11/batch.json'))
ANA="Anaphoric subject — no compound named here."; FAM="A family or formula class, not a definite compound."
GEN="A general or background statement; nothing attributed to a compound."; TRUNC="Truncated before the odour claim completes."
COMPO="Composition-level — the odour belongs to the product, not a compound."
MIX="The mixture rule."; PTR="'the compound having the structure: ##STR##' — a pointer, nothing named."
SMK="Tobacco is the product being flavoured, not a smell of the compound."
D={
1:('R',[],"Other fragrances in combination; composition-level."),
2:('R',[],"'compound of formula (I)' — "+FAM),
3:('R',[],"BORDERLINE. 'the cooked apple note of the delta damascene' does attribute apple to one material, but 'delta damascene' is a misspelling that won't resolve, and the subject is the composition. Approving it would be the 3rd apple molecule."),
4:('R',[],COMPO),
5:('R',[],"'acetals of our invention' — "+FAM),
6:('A',['alpha-damascone'],"Named, direct — 'its fragrance character of green apple type'. 'fruity and floral' describe the compositions it's used in, so they're dropped. New to apple; no damascone of this name is approved."),
7:('R',[],MIX),8:('R',[],MIX),9:('R',[],MIX),
10:('R',[],FAM+" Tobacco product = usage."),
11:('R',[],MIX),12:('R',[],MIX),
13:('R',[],"BORDERLINE. 'This material … having a tobacco-honey odor' — "+ANA+" Passage scope would rescue it if the previous sentence names the compound."),
14:('R',[],"'the ketone of this invention' — "+ANA),
15:('R',[],"Same-document repeat: '2,5,5 trimethylacetyl cycloheptane' is already approved from US3869411A with tobacco."),
16:('R',[],"A formulation added to tobacco."),
17:('R',[],"'tricyclic ketones of formulae l-A and LB' — pointer, plural."),
18:('R',[],MIX+" Cigarette flavour."),
19:('R',[],"Truncated at a patent citation; earthy is offered as a use 'in foodstuffs … tobaccos'. When in doubt, reject."),
20:('R',[],"'enol ester (or mixture of esters)' — "+FAM),
21:('R',[],"'enol ester (or mixture of esters)' — "+FAM),
22:('R',[],MIX),23:('R',[],MIX),
24:('R',[],"Two compounds imparting flavour to tobacco compositions; "+SMK),
25:('A',['trans, trans-Δ-damascone'],"Named, direct — 'has a fine tobacco-rose, appley, berry note'. Relative stereochemistry is definite. New molecule. 'appley' is not in the ontology yet; mapping it would make this the 2nd apple molecule."),
26:('R',[],"No compound named."),
27:('R',[],"Fractions; nothing named."),28:('R',[],"Fractions; nothing named."),
29:('R',[],FAM+" Smoking flavour."),
30:('R',[],PTR),31:('R',[],PTR+" Detergent."),32:('R',[],PTR+" Detergent."),33:('R',[],PTR+" Cologne."),
34:('R',[],MIX+" Cigarette flavour."),
35:('R',[],PTR),36:('R',[],PTR+" Detergent."),37:('R',[],PTR+" Detergent."),38:('R',[],PTR+" Cologne."),
39:('R',[],PTR),40:('R',[],PTR+" Detergent."),41:('R',[],PTR+" Detergent."),42:('R',[],PTR+" Cologne."),
43:('R',[],PTR),44:('R',[],PTR+" Detergent."),45:('R',[],PTR+" Detergent."),46:('R',[],PTR+" Cologne."),
47:('R',[],FAM+" "+SMK),48:('R',[],FAM+" "+SMK),
49:('R',[],"Experimental cigarettes; composition."),
50:('R',[],FAM+" Smoking flavour."),
51:('R',[],PTR),52:('R',[],PTR+" Detergent."),53:('R',[],PTR+" Detergent."),54:('R',[],PTR+" Cologne."),
55:('R',[],PTR),56:('R',[],PTR),
57:('A',['1,1-Dimethyl-4-acetyl-tetralin'],"Named in the item heading, 'The odor of this compound' refers to it in the same sentence. Roses/tobacco/honey are sources named as smells; 'damascones' is a substance and is dropped. New molecule (the cyano sibling is already in, from this patent)."),
58:('A',['1,1,Dimethyl-indan-3-carboxylic acid methyl ester'],"Named in the heading, same pattern as #57. The comma after '1,1' is a typo for a hyphen, so linkage has to normalise it. New molecule."),
59:('R',[],"'1,226,730 having the structure' — pointer. Smoking flavour."),
60:('R',[],FAM+" Flavour."),61:('R',[],FAM+" Flavour."),62:('R',[],FAM+" Smoking flavour."),
63:('R',[],GEN),64:('R',[],FAM+" Flavour."),65:('R',[],GEN),
66:('R',[],"'oxyneopentyl alkanoate derivative(s)' — "+FAM),
67:('R',[],PTR+" Cigarette flavour."),
68:('R',[],"'1,226,730 having the structure' — pointer."),
69:('R',[],"'compounds of formula ##STR5##' — prior-art family."),
70:('R',[],"'1,226,730 having the structure' — pointer."),
71:('R',[],MIX+" Composition."),
72:('R',[],"'a diastereomer mixture' — the mixture rule."),
73:('R',[],PTR+" Garbled table."),
74:('R',[],"'compounds or isomer mixtures' — "+FAM),
75:('R',[],PTR+" Garbled table."),
76:('R',[],"'compounds of formula (I)' — "+FAM),
}
forms=sorted(surf,key=len,reverse=True); rx=re.compile(r"\b("+"|".join(map(re.escape,forms))+r")\b", re.I)
EXCL={6:{'fruity','floral'},25:set(),57:{'damascones','damascone'},58:{'acid'}}
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
