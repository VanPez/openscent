#!/usr/bin/env python3
"""Stage one adjudicated batch as proposals. TEMPLATE — edit D, then run.

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
batch=json.load(open('/tmp/batch.json'))
ANA="Anaphoric subject — no compound named here."; FAM="A family or formula class, not a definite compound."
GEN="A general or background statement; nothing attributed to a compound."; TRUNC="Truncated before the odour claim completes."
COMPO="Composition-level — the odour belongs to the product, not a compound."
D={
1:('R',[],"Defines the term 'exotic fruit'."),2:('R',[],"Reaction chemistry."),
3:('A',["3,3-Diethyl-4-oxa-tricyclo[5.2.1.0*2,6*]-decane"],"Named with its formula label, direct. Feeds animalic, which needs 2."),
4:('A',["isononyl acetate"],"Named, direct. 'isononyl' is a branched C9 and is a standard material name, though it is not a single defined isomer — your call."),
5:('A',["3-(4-methylcyclohex-3-enyl)butyraldehyde"],"Named with its common name (limonenal), direct. 'aidehydic' is an OCR slip for aldehydic."),
6:('R',[],FAM),7:('R',[],"'the pinanone of this invention' — a class, not a definite compound."),8:('R',[],ANA),
9:('R',[],"'2,5,5-trialkyl-' — alkyl unspecified. Family."),
10:('A',["menthyl acetate"],"Named, direct."),
11:('R',[],FAM),12:('R',[],COMPO),13:('R',[],FAM),
14:('R',[],"A use statement; no odour attributed to nor-dehydropatchoulol."),
15:('R',[],"A class defined by volatility."),16:('R',[],"Formulation table."),
17:('R',[],"Flavour of a composition containing the compound."),
18:('R',[],"Eucalyptus is a plant/oil, and the claim is psychological."),
19:('A',["1,1 diethoxy 2 pentyl 5 isobutyl 4 hexene"],"Named, isolated, direct. 'faintly' is intensity."),
20:('S',[],"TWO compounds, DIFFERENT descriptions — LILYFLORE has hydroxycitronellal/humic notes, HIVERNAL has lily of the valley. Trade names only."),
21:('R',[],ANA),
22:('A',["vanillin","methyl diantilis"],"TWO compounds sharing ONE description — 'ingredients exhibiting floral-spicy notes ... include vanillin and methyl diantilis'. iso-eugenol is the exemplar, not a subject."),
23:('A',["(1-ethylcyclohexyl) acetate"],"'is used to impart' form. Feeds hay, which needs 18. 'damascone' is a substance."),
24:('A',["Caryophyllene"],"Named, direct. The cedar-wood clause is a comparison."),
25:('R',[],"'a material' from a Diels-Alder reaction — not a definite compound."),
26:('A',["Thuj one"],"'Thujone has a menthol odor' — named, direct. The name is OCR-split ('Thuj one') and the Valencene clause belongs to the preceding entry."),
27:('R',[],"A cultural association, not an attribution."),
28:('R',[],"Blend effect — replacing part of a base accord."),
29:('S',[],"THREE compounds each with its OWN parenthetical description. Split, then each alone."),
30:('A',["geranonitrile"],"Named with its systematic name, direct. Truncated — check the tail."),
31:('A',["1,1,3,3-Tetramethyl-2,3,4,5- tetrahydro-1H-7,9-diaza- cyclopenta[a]naphthalene"],"Named with its formula label, direct. 'less interesting, weak' is judgement and intensity."),
32:('R',[],COMPO),
33:('A',["\"trans\" beta-cyclohomocitral enol propionate"],"Named, direct. Same claim as a row approved in batch 3, different patent. 'butyric/propionic acid' is a substance comparison."),
34:('R',[],"The essential oil — a mixture."),35:('R',[],TRUNC),
36:('A',["Thuj one"],"Same claim as row 26 in a second patent."),
37:('R',[],"The structural formula is OCR garbage."),38:('R',[],"'5' is a pointer."),
39:('R',[],"Same eucalyptus psychological claim as row 18."),
40:('R',[],"Negation — 'distinguish themselves by LACKING'."),
41:('R',[],"Concerns skin irritation; 'associated with animal notes' is not an attribution."),
42:('A',["3,3 dimethyl acetyl cyclohexane"],"Named, direct. Second-hand (cites a patent)."),
43:('R',[],"Formulation list."),
44:('A',["methyl-1-ethynycyclohexyl carbonate"],"Named, direct. Same claim as batch 3, different patent."),
45:('S',[],"TWO compounds, DIFFERENT descriptions — trans-sabinene oxide fresh/green, cis- woody/costus/camphor."),
46:('A',["Cineole"],"Named, direct. The eucalyptus-oil clause states where it occurs, not a comparison of odour."),
47:('R',[],TRUNC),48:('R',[],ANA+" Also truncated."),
49:('R',[],"'The pivalate' — which one is not stated."),
50:('R',[],"'The Formula V compounds' — family."),
51:('R',[],"'their odors are very DIFFERENT' undercuts the shared castoreum comparison, and castoreum is an animal material rather than a descriptor."),
52:('A',["isodamascone"],"Named with its formula label, direct."),
53:('A',["2,6-Dimethyl-5,6-dihydro-2H-thiopyran-3-carbaldehyde"],"Named, direct. 'onion' is not yet an ontology term."),
54:('R',[],"Concerns dosage limits."),55:('R',[],ANA),
56:('R',[],"Blend effect — adding linolal to a further fragrance."),
57:('R',[],"'a product having the fragrant odor of irone' — a comparison, and no compound is the subject."),
58:('R',[],"'The novel ... compounds of Formula III' — plural family."),
59:('A',["(+)-spathulenol"],"Named with stereodescriptor, direct for the ODOUR. The 'bitter herbal flavour' is taste and is not captured."),
60:('R',[],GEN),61:('R',[],"'Ketals of cyclododecanone' — which ketal is not stated."),
62:('R',[],GEN),
63:('S',[],"TWO compounds with separate descriptions — myrcene 'fresh hops', humulene 'a distinctive hop aroma'."),
64:('R',[],"No odour descriptor in this sentence; it gives structure and molecular weight."),
65:('S',[],"TWO compounds, DIFFERENT descriptions — phenyl ethanol rose/peach, benzyl alcohol fruity."),
66:('A',["benzyldimethyl carbinol"],"Named, direct. Second-hand (a reference citation) but the attribution is to the compound."),
67:('S',[],"THREE compounds, DIFFERENT descriptions — l-menthol mint, d-carvone caraway, d-nootkatone grapefruit. A clean three-way split."),
68:('R',[],COMPO),69:('R',[],FAM),
70:('R',[],"'The crude product mixture' — the mixture rule."),
71:('S',[],"TWO compounds, DIFFERENT descriptions — 'the l-isomer' peppermint, d-menthol wood/camphor. The first half is anaphoric and will likely reject."),
72:('R',[],"Formulation table."),73:('R',[],"Odour list with no compound named."),
74:('R',[],"'Compound ID' — pointer."),
75:('A',["acetyl, hexamethyl-1,2,3,4 tetrahydronaphthalene"],"Named, direct. 'musk-line' is an OCR slip for musk-like."),
76:('R',[],"Concerns adsorbent gels."),
77:('R',[],"'The racemic mixture' — the mixture rule."),
78:('A',["citral","Citralva","citronellyl nitrile","Citronitrile"],"FOUR compounds sharing ONE description — 'have a citrus odor'. Add all, approve once. Two are trade names."),
79:('R',[],TRUNC),80:('R',[],ANA+" Also a blend effect."),
81:('A',["caryophyllene acetate"],"Named, direct. Same claim as batch 2, different patent."),
82:('R',[],"'Individual Substance 12' — pointer."),
83:('A',["3-mercaptoheptyl acetate"],"Named, direct. 'relatively weak' is intensity."),
84:('A',["6-oxa-1,1,2,3,3,8-hexamethyl-2,3,5,6,7,8-hexahydrolH-benz [f] -indene"],"The systematic name is given in the same sentence as the musk attribution. Name is OCR-damaged."),
85:('R',[],ANA),86:('R',[],ANA),87:('R',[],COMPO),
88:('R',[],"Concerns aerosol smoke versus cigarettes."),
89:('R',[],"'The compounds according to the invention' — family."),
90:('A',["2-Isobutylcyclohexyl acetate"],"Named, direct. The raspberry clause is a comparison; the flavour clause is taste."),
91:('R',[],"Blend effect — what phenylethyl alcohol does with 5% of the crystalline material."),
92:('R',[],"A patent number as subject."),
93:('A',["(R)-citronellyl lactate"],"Named with stereodescriptor, direct. 'more natural than rosy alcohols' is a comparison."),
94:('A',["Pulegone"],"Named, direct."),
95:('A',["(1-vinylcyclohexyl) propanoate"],"'is used to impart' form. 'plum', 'chamomile' and 'raisin' are not yet ontology terms."),
96:('R',[],ANA),
97:('S',[],"TWO compounds, DIFFERENT descriptions — the DIMETHYL acetal is floral/sweet/earthy, the diethyl acetal differs. Note the dimethyl acetal IS definite (the alcohol is named), so that half should stand."),
98:('A',["2-methylperhydrocyclododeca[b]furan"],"Named, direct."),
99:('R',[],"Odour description with no compound named."),
100:('R',[],"PHANTOM RISK: 'dihydro-[i-santalol' is an OCR rendering of dihydro-beta-santalol, which is ALREADY in the corpus from US3673263A. Approving this would count one molecule twice under two spellings."),
}
forms=sorted(surf,key=len,reverse=True); rx=re.compile(r"\b("+"|".join(map(re.escape,forms))+r")\b", re.I)
EXCL={24:{'cedar','cedar wood'},46:{'eucalyptus'},90:{'fruity'} if False else set(),93:set(),59:{'herbal'},5:set()}
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
