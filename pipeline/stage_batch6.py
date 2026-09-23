#!/usr/bin/env python3
"""Stage batch 6 (TARGETED, pipeline/target_pool.py draw, 2026-09-23). Copy of the stage_batch.py template.

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

ROW MATCHING is on (source_id, first 110 chars of whitespace-normalised sentence),
NOT on row index — propose.py keys on index and a split shifts every index behind
it. Already-decided rows are skipped and reported, never overwritten.

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
idx={}
for i,r in enumerate(rows): idx.setdefault((r['source_id'], re.sub(r'\s+',' ',r.get('sentence','')).strip()), i)
batch=json.load(open('/tmp/batch.json'))
ANA="Anaphoric subject — no compound named here."; FAM="A family or formula class, not a definite compound."
GEN="A general or background statement; nothing attributed to a compound."; TRUNC="Truncated before the odour claim completes."
COMPO="Composition-level — the odour belongs to the product, not a compound."
PH="PHANTOM RISK — a spelling variant of a compound already in the corpus; approving counts one molecule twice. Same precedent as batch 4's dihydro-[i-santalol."
D={
1:('R',[],FAM),
2:('A',["Terpineol"],"Named, direct. 'apple blossom' is a flower, not the apple tag — dropped. Borderline: bare 'terpineol' is a trade material of mixed isomers, like isononyl acetate (which you approved)."),
3:('R',[],"'mixture B' — the mixture rule."),4:('R',[],"'mixture B' — the mixture rule."),
5:('A',["2-(2,4,5-trimethylcyclohex-2-en-1-yl)acetaldehyde"],"'is used to impart' form — named, direct. Feeds aldehydic."),
6:('A',["2-(2,4,5-trimethylcyclohex-2-en-1-yl)acetaldehyde"],"Same claim as row 5, same patent, differs by one comma. A true row but adds no molecule — reject if you treat same-document repeats as one."),
7:('R',[],"'mixture of the trans isomers' — the mixture rule."),8:('R',[],GEN),
9:('R',[],"A cis/trans mixture — the mixture rule."),10:('R',[],GEN),
11:('A',["β-damascenone"],"Several compounds sharing ONE description; only β-damascenone is a clean span ('α-, β-, δ-damascones' is a list, not a name). apple is inside the odour clause. Feeds apple. Borderline: your call."),
12:('R',[],"A class of trade materials, and no odour attributed to one of them."),
13:('A',["Dihydroverbetryle"],"Trade name with its formula label, direct. 'geranonitrile' is a substance comparison. Feeds aldehydic. Check the trade name resolves."),
14:('R',[],"'Formula XV' — pointer."),15:('R',[],"'The (E)-isomer of the racemic form' — "+ANA),
16:('R',[],"'All' — "+ANA),17:('R',[],GEN),18:('R',[],COMPO),19:('R',[],"'The derivative' — "+ANA),
20:('A',["Indoflor"],"Trade name for a single defined compound, direct. Feeds animalic, which needs 1. Civet is an animal material; the 'animalic' span carries the tag."),
21:('A',["2-methyl-4H-3,1-benzoxathiin"],"Named, direct. 'indole' and 'cresol' are substances, dropped; 'animal-like' carries animalic."),
22:('R',[],"'certain types of ketal products' — family."),23:('R',[],TRUNC+" The subject is before the CAS number."),
24:('R',[],TRUNC+" Spectral data; the compound is named in an earlier sentence."),
25:('R',[],PH+" The same compound was approved in batch 4 from this patent as '3-endo-methyl 3 exo(4' methyl 5 hydroxy- 1O pentyl)norcamphor'."),
26:('R',[],TRUNC+" Same as row 24, second patent."),
27:('A',["allyl beta-phenylpropionate"],"Named, direct. Same molecule and spelling as batch 5 #57, second patent — a real attestation, no new molecule."),
28:('R',[],PH+" 'Allyl betaphenylpropionate' vs 'allyl beta-phenylpropionate'."),
29:('R',[],PH+" 'allyl lbeta-phenylpropionate' — OCR."),
30:('A',["trans-5-cyclohexyl-3-methyl-2-penten-1-oic acid nitrile"],"Named, direct. 'soft' is intensity. Feeds aldehydic."),
31:('R',[],"Blend effect — a mellowing effect upon aldehydes."),32:('R',[],COMPO),
33:('R',[],"'alcohol 9' — pointer."),34:('R',[],GEN),
35:('A',["3-methyl-2-hexenoic acid","7-octenoic acid"],"TWO compounds sharing ONE description — 'have a very strong animal note'. Feeds animalic. E/Z of the hexenoic acid is unstated, as with most trivially-named rows."),
36:('R',[],"Blend effect — compounded into mixed perfumes."),
37:('R',[],"'the pentadecenolides mentioned above' — family, and a comparison."),
38:('R',[],"'Compounds (II)' — pointer, and negation by comparison ('less animal')."),
39:('R',[],"Blend effect, and 'or a mixture thereof'."),
40:('R',[],FAM),41:('A',["3-methyl-cis-4-hexenyl acetate"],"Named, direct. 'pears or apples' is inside the odour clause. Feeds apple."),
42:('R',[],GEN),
}
EXCL={30:{'acid','soft'},35:{'acid'},11:{'floral','fruity'},2:{'apple','apple blossom'},21:{'indole','cresol','indole-like','cresol-like'},13:{'geranonitrile'}}
forms=sorted(surf,key=len,reverse=True); rx=re.compile(r"\b("+"|".join(map(re.escape,forms))+r")\b", re.I)
bo=[];inb=[];bad=[];skip=[]
for i,r in enumerate(batch,1):
    dec,mols,why=D[i]
    k=(r['source_id'], re.sub(r'\s+',' ',r['sentence']).strip())
    if k not in idx: bad.append((i,'not found')); continue
    n=idx[k]; row=rows[n]; s=row['sentence']
    if row.get('decision'): skip.append(i); continue
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
