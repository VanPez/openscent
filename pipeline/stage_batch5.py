#!/usr/bin/env python3
"""Stage batch 5 (seed 20260928, 2026-09-23). Copy of the stage_batch.py template.

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
for i,r in enumerate(rows): idx.setdefault((r['source_id'], re.sub(r'\s+',' ',r.get('sentence','')).strip()[:110]), i)
batch=json.load(open('/tmp/batch.json'))
ANA="Anaphoric subject — no compound named here."; FAM="A family or formula class, not a definite compound."
GEN="A general or background statement; nothing attributed to a compound."; TRUNC="Truncated before the odour claim completes."
COMPO="Composition-level — the odour belongs to the product, not a compound."
D={
1:('R',[],FAM+" Also imparts to formulations."),
2:('R',[],"'the ketone(s) produced according to the process' — not a definite compound; imparts to formulations."),
3:('A',["Perillyl acetate"],"Named, direct. 'amild' is OCR for 'a mild' — intensity."),
4:('R',[],GEN),5:('R',[],COMPO),6:('R',[],ANA),
7:('R',[],"Menthol and menthyl acetate CONTRIBUTE TO peppermint's smell — a statement about the oil, not an attribution to either compound."),
8:('A',["menthol"],"'the strong mint odor typically associated with menthol' — attribution to a named compound inside a background clause. 'strong' is intensity. Borderline: your call."),
9:('R',[],"Absolutes — natural extracts, the mixture rule."),
10:('A',["(S)-dihydrocitronellyl lactate"],"Named with stereodescriptor, direct. Sibling of the (S)-citronellyl lactate row."),
11:('A',["(-)-thujone"],"'odor attributed to the (-)-thujone content of these oils' — the sentence assigns the odour's origin to the compound. 'warmherbaceous' is OCR-fused and will not map. Borderline: your call."),
12:('R',[],TRUNC+" The name is cut to '1 ]heptane'."),
13:('R',[],"'norbornyl oxyacetaldehyde' leaves attachment and exo/endo open; also imparts to formulations."),
14:('R',[],FAM),15:('R',[],TRUNC),16:('R',[],FAM),17:('R',[],"'this acetal' — "+ANA),18:('R',[],ANA),
19:('R',[],"The patchouli odour belongs to an UNNAMED minor peak, not to patchouli alcohol."),
20:('R',[],FAM),21:('R',[],"Blend effect — linolal boosting notes in compositions."),22:('R',[],COMPO),
23:('R',[],"'hydrogenated catecholcamphene adducts' — a product mixture."),24:('R',[],ANA),25:('R',[],FAM),26:('R',[],"Same form as row 2."),
27:('R',[],ANA),28:('R',[],COMPO),29:('R',[],"'enolone ether isomers of campholenic acids' — a family of isomers."),30:('R',[],ANA),
31:('R',[],GEN),32:('R',[],ANA),33:('R',[],FAM),34:('R',[],GEN),
35:('R',[],"Orange terpenes is a mixture; no descriptor for d-limonene."),
36:('R',[],"'The trans isomer' — "+ANA),37:('R',[],ANA),38:('R',[],ANA),39:('R',[],"'The novel acetal' — "+ANA),
40:('R',[],GEN),41:('R',[],GEN),42:('R',[],GEN),43:('R',[],"'The obtained mixture' — the mixture rule."),
44:('A',["ethyl vanillin","vanillin"],"TWO compounds sharing ONE description — either one deposits 'to provide the vanilla sweet note'. The note originates in the compound. Borderline: your call."),
45:('A',["menthol"],"'the mint odour of menthol' — named, direct."),
46:('A',["Ethyl Linalool"],"Named, direct. A defined compound under a common name."),
47:('R',[],ANA),48:('R',[],COMPO),49:('R',[],"Washed linen, and 'spiro-ketone (I)' is a pointer."),
50:('S',[],"TWO compounds, DIFFERENT descriptions — patchoulione rooty/earthy, 'the Example II material' amber. The second half is a pointer and will reject; patchoulione is a trivial name, check it resolves."),
51:('R',[],GEN),52:('R',[],FAM),53:('R',[],"Compound numbers — pointers."),
54:('A',["(Oxybis(methylene))dicyclohexane"],"Named, direct. 'salicylate' is a substance, dropped."),
55:('R',[],ANA),56:('R',[],"'this product' — "+ANA),
57:('A',["allyl beta-phenylpropionate"],"'imparts an apple-apple cider note' — the note originates in the compound. Feeds apple, which needs 9."),
58:('A',["trithioacetone"],"Named in apposition, direct. 'geranium' names the target perfume type, dropped."),
59:('R',[],COMPO),60:('R',[],"'para-acyloxycyclohexyl alkylcarboxylate' — acyl and alkyl open. Family."),
61:('R',[],"'Armoise NNO+' is a trade product of undisclosed composition; the odour is a comparison to an oil."),
62:('R',[],GEN),63:('R',[],FAM+" Mixtures, and imparts to formulations."),64:('R',[],"'Formula (1)' — family/pointer."),
65:('R',[],"Compound numbers — pointers."),66:('R',[],FAM),
67:('R',[],"'The flavor containing' — composition-level, and taste."),
68:('R',[],"'(E)/(Z) isomeric mixture' — the mixture rule."),69:('R',[],FAM),70:('R',[],GEN),
71:('R',[],"'the acetate' — "+ANA+" And a 92:8 syn/anti blend."),
72:('R',[],"'cyclohexadecenone' leaves the double-bond position open; stated as an aim, not an attribution."),
73:('R',[],ANA),74:('R',[],GEN),75:('R',[],FAM),76:('R',[],ANA),77:('R',[],FAM),78:('R',[],"'The ketone' — "+ANA),
79:('R',[],FAM+" 'patchouli alcohol' is the comparison, not the subject."),80:('R',[],FAM),
81:('R',[],ANA+" A natural material."),82:('R',[],"A patent number as subject, and negated-by-degree ('at most weak')."),
83:('R',[],GEN),84:('R',[],"'an acetal' — not a definite compound."),85:('R',[],FAM),86:('R',[],"'The trans isomer' — "+ANA),
87:('R',[],COMPO),88:('R',[],FAM),89:('R',[],"'The dihydroindane so produced' — "+ANA),90:('R',[],GEN),91:('R',[],FAM),
92:('R',[],FAM),93:('R',[],COMPO),94:('R',[],"A 1:1 damascol:beta-cyclohomocitral mixture in a detergent."),
95:('R',[],FAM),96:('R',[],TRUNC),97:('R',[],"A patent's process as subject."),98:('R',[],ANA),
99:('R',[],"'This ketone' — "+ANA),100:('R',[],FAM),
}
EXCL={54:{'salicylate'},58:{'geranium'},8:{'menthol'},45:{'menthol','cooling'},44:{'dry'}}
forms=sorted(surf,key=len,reverse=True); rx=re.compile(r"\b("+"|".join(map(re.escape,forms))+r")\b", re.I)
bo=[];inb=[];bad=[];skip=[]
for i,r in enumerate(batch,1):
    dec,mols,why=D[i]
    k=(r['source_id'], re.sub(r'\s+',' ',r['sentence']).strip()[:110])
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
