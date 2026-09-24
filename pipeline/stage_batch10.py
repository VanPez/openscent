#!/usr/bin/env python3
"""Stage batch 10 (hedione_pool.py 100 --noise2-first --seed 20260926 --out /tmp/b10/batch.json, 2026-09-24). Copy of the fixed template.

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
batch=json.load(open('/tmp/b10/batch.json'))
ANA="Anaphoric subject — no compound named here."; FAM="A family or formula class, not a definite compound."
GEN="A general or background statement; nothing attributed to a compound."; TRUNC="Truncated before the odour claim completes."
COMPO="Composition-level — the odour belongs to the product, not a compound."
D={
1:('R',[],'The notes belong to wines.'),
2:('R',[],"'Said prior art analogue' — "+ANA),
3:('R',[],FAM),
4:('R',[],'A beverage.'),
5:('R',[],'Composition-level.'),
6:('R',[],'Truncated; subject is a patent number.'),
7:('R',[],'No compound named.'),
8:('A', ['α-Campholene aldehyde'], 'Named, direct. New molecule.'),
9:('R',[],FAM),
10:('R',[],'\'The "trans" isomer\' — '+ANA),
11:('A', ['Linalool'], "Named, direct. 'Lilly-of-the-Valley' is misspelt and won't map; 'spice' carries spicy. New on the patent side (PubChem has linalool)."),
12:('R',[],"'isolongifolenyl esters' — which acyl? A family."),
13:('R',[],"'Said prior art analogue' — "+ANA),
14:('R',[],FAM),
15:('R',[],'Blend effect.'),
16:('R',[],"Truncated; 'having the structure 1' — pointer."),
17:('R',[],"'I' — pointer."),
18:('R',[],"'an important trace constituent' — nothing named."),
19:('R',[],"The odour is the (S) form's, and '(S)-benzylisobutylcarbinol' is not a contiguous span — recording the bare name would attribute it to the racemate. When in doubt, reject."),
20:('R',[],'Composition-level.'),
21:('A', ['n-hexyl tiglate'], "Named (Arctander entry), direct. 'pleasant' is judgement; berries/plums are foods named as smells. New molecule."),
22:('R',[],FAM),
23:('R',[],'Composition-level.'),
24:('R',[],"'mixture C' — the mixture rule."),
25:('R',[],"'(in B)' — pointer."),
26:('R',[],"'Formula XVIII' — pointer."),
27:('R',[],'No compound named.'),
28:('R',[],'A perfume oil — composition.'),
29:('R',[],'Cigarette smoke; truncated.'),
30:('A', ['Linalool acetate'], "Named, direct. Borderline: 'linalool acetate' is a common misnomer for linalyl acetate — check it resolves; PubChem holds 'linalyl acetate', and the name join will count this separately."),
31:('R',[],GEN),
32:('R',[],"'Their' — "+ANA),
33:('R',[],'Blend effect.'),
34:('R',[],"'neutral odor' — no descriptor."),
35:('R',[],GEN),
36:('R',[],"'The two compounds mentioned' — "+ANA),
37:('R',[],FAM),
38:('A', ['ortho-isobutyl-alpha-methyl hydrocinnamaldehyde'], "'Pure X … exhibits an iris, powdery and woody note' — named, direct. The para isomer is a comparison. New molecule."),
39:('R',[],"A stereo-enriched blend 'containing at least a predetermined amount' — the mixture rule."),
40:('R',[],"'Said prior art analogue' — "+ANA),
41:('R',[],GEN),
42:('R',[],'Fragrance mixtures, general.'),
43:('A', ['Lilial'], "Trade name, direct — 'widely valued for its muguet odour note'. You approved Lilial in batch 9; a further attestation."),
44:('A', ['Lilial'], 'Same sentence as #43, another patent. Further attestation only.'),
45:('A', ['hydroxycitronellal'], "Named, direct. Aroma clause 'sweet-floral aroma'; the taste clause repeats the same words. Already in; attestation."),
46:('A', ['Trans-sabinene hydrate'], "Named, direct. 'cooling' is not a smell. New molecule."),
47:('R',[],GEN),
48:('R',[],"'The propene tetramer oxime mixture' — the mixture rule."),
49:('A', ['Caryophyllene'], "Named, direct. 'dry' dropped; 'clove' kept. Already in (2 patents)."),
50:('A', ['phenyl ethyl alcohol'], "'the rose-like odor phenyl ethyl alcohol' — the odour is attributed to the named compound. The '(17)' is a reference. New spelling of a common molecule — check for a phantom under another spelling."),
51:('R',[],FAM),
52:('R',[],FAM),
53:('R',[],'Odour threshold only — no descriptor.'),
54:('R',[],"'The isomerizate' — a reaction mixture."),
55:('R',[],'No compound named.'),
56:('R',[],"'Ortho- and para-… caproates' — two isomers under one plural, each itself a cis/trans set. A family."),
57:('R',[],"'an acetal' — no compound named."),
58:('R',[],FAM),
59:('R',[],GEN),
60:('R',[],FAM),
61:('R',[],"'the cis product' / 'the trans-isomer' — anaphora."),
62:('R',[],"'certain ethers of cyclododecanol' — "+FAM),
63:('R',[],FAM),
64:('R',[],GEN),
65:('R',[],"'Linolal' — I can't place this as one defined compound; the profile is also a class list. When in doubt, reject."),
66:('A', ['damascenone'], "Named, direct — its odour 'in the family of the floral-rose odors'. New by this name (β-damascenone is already in; possible phantom — your call)."),
67:('R',[],"'Lower fatty acid esters of nojigiku alcohol' — which acid? A family."),
68:('R',[],'Composition-level; a class.'),
69:('R',[],FAM),
70:('S', [], 'FOUR compounds, DIFFERENT descriptions, all named: methyl cedryl ether (woody-amber), methyl cedryl ketone (musk-woody), cedrene epoxide (woody-amber-camphor), cedryl acetate (woody-vetiver). All halves live, as in your Lilial/Lyral call.'),
71:('R',[],'Truncated; subject is a citation.'),
72:('R',[],'(S)-citronellyl lactate is already approved from this same patent — a same-document repeat adds nothing.'),
73:('R',[],'Composition-level.'),
74:('R',[],GEN),
75:('R',[],'Exaltone is the trade name of cyclopentadecanone, already in the corpus by its systematic name — the rule: trade names are not separate molecules.'),
76:('R',[],'No compound named.'),
77:('R',[],FAM),
78:('R',[],"'a compound obtained by…' — no compound named."),
79:('R',[],"'musk' is a material, and the odour is shared with it."),
80:('R',[],"Flavour; 'the added bicyclooctane derivative' — family."),
81:('R',[],"'the cis product' / 'the trans-isomer' — anaphora."),
82:('R',[],FAM),
83:('R',[],'No compound named.'),
84:('R',[],FAM),
85:('R',[],FAM),
86:('R',[],'Blend effect.'),
87:('R',[],'Truncated; subject is a patent number.'),
88:('R',[],"'The C alcohols' — "+FAM),
89:('R',[],"'A mixture of the (E)-isomer and the (Z)-isomer' — the mixture rule."),
90:('R',[],"'The derivative' — "+ANA),
91:('R',[],"'The 2(3)-dihydrofarnesals I' — plural, in compositions."),
92:('A', ['allyl caproate'], "Named, direct — 'allyl caproate has a fruity note'. 'spicy' is nutmeg oil's — dropped. New molecule."),
93:('R',[],FAM),
94:('R',[],"'the pure alcohol' — "+ANA),
95:('R',[],'A flavour mixture.'),
96:('R',[],"'The odour' — whose? Nothing named."),
97:('R',[],'A comparison between trade materials; no odour attributed to either.'),
98:('R',[],"'Alcohol (IIA)' / '(IIB)' — pointers."),
99:('R',[],'Reaction products; truncated citation.'),
100:('R',[],'No compound named.'),
}
forms=sorted(surf,key=len,reverse=True); rx=re.compile(r"\b("+"|".join(map(re.escape,forms))+r")\b", re.I)
EXCL={11:set(),21:{'pleasant'},30:set(),38:{'cyclamen'} and set(),45:set(),46:{'cooling','mint'},49:{'dry'},50:set(),66:set(),92:{'spicy','nutmeg'},8:{'aldehyde'},43:set(),44:set()}
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
