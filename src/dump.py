import pdfplumber, sys, collections
# usage: dump.py k pg  -> structured dump of one page
k, pg = sys.argv[1], int(sys.argv[2])
pdf = pdfplumber.open(f"pdf/k{k}.pdf"); p = pdf.pages[pg - 1]
R = p.rects
H = [r for r in R if r['height'] < 3 and r['width'] > 3]
V = [r for r in R if r['width'] < 3 and r['height'] > 3]
# pair-number column: find "1." "2." texts near x 65-85
words = p.extract_words(extra_attrs=["fontname", "upright", "size"], keep_blank_chars=False, x_tolerance=1.5)
up = [w for w in words if w['upright']]
pn = [w for w in up if 64 < w['x0'] < 86 and w['text'].rstrip('.').isdigit() and w['text'].endswith('.')]
# row boundaries: H lines covering x 70..80
bnd = sorted(set(round(r['top'], 1) for r in H if r['x0'] < 70 and r['x1'] > 80))
# merge close
B = []
for y in bnd:
    if not B or y - B[-1] > 3: B.append(y)
CX0, CX1 = 86, 558
def inrow(y0, y1, w): return w['top'] >= y0 - 1 and w['bottom'] <= y1 + 1
def phr(ws):
    # group into lines then phrases
    ws = sorted(ws, key=lambda w: (round(w['top']), w['x0']))
    lines = collections.OrderedDict()
    for w in ws:
        key = None
        for kk in lines:
            if abs(kk - w['top']) < 2.2: key = kk; break
        if key is None: key = w['top']; lines[key] = []
        lines[key].append(w)
    out = []
    for y, l in sorted(lines.items()):
        l.sort(key=lambda w: w['x0'])
        ph = [[l[0]]]
        for w in l[1:]:
            if w['x0'] - ph[-1][-1]['x1'] > 7: ph.append([w])
            else: ph[-1].append(w)
        segs = []
        for pp in ph:
            t = ''
            for w in pp:
                b = 'Bold' in w['fontname']
                t += ('*' + w['text'] + '*' if b else w['text']) + ' '
            segs.append(f"[{pp[0]['x0']:.0f}-{pp[-1]['x1']:.0f}] {t.strip().replace('* *', ' ')}")
        out.append(f"   y{y:.0f}: " + '  ||  '.join(segs))
    return out
# rotated chars
rot = [c for c in p.chars if not c['upright']]
print(f"== k{k} p{pg}  rows={len(B)-1}")
hdr = [w for w in up if w['top'] < (B[0] if B else 200) and 'ЮРД' in w['text'] or (w['top'] < (B[0] if B else 200) and w['text'] in ('–',))]
for i in range(len(B) - 1):
    y0, y1 = B[i], B[i + 1]
    num = [w['text'] for w in pn if y0 <= w['top'] <= y1]
    if y1 - y0 < 4: continue
    print(f"-- ROW {i} y{y0:.0f}-{y1:.0f} pair={num}")
    hs = [r for r in H if r['x0'] >= CX0 - 2 and y0 + 2 < r['top'] < y1 - 2]
    g = collections.defaultdict(list)
    for r in hs: g[round(r['top'])].append((r['x0'], r['x1']))
    for y in sorted(g):
        xs = sorted(g[y]); print(f"   H@{y}: " + ' '.join(f"{a:.0f}-{b:.0f}" for a, b in xs))
    vs = [r for r in V if r['x0'] > CX0 + 3 and r['x1'] < CX1 - 3 and r['top'] < y1 - 2 and r['bottom'] > y0 + 2]
    vv = collections.defaultdict(list)
    for r in vs: vv[round(r['x0'])].append((max(r['top'], y0), min(r['bottom'], y1)))
    if vv: print("   V: " + ' '.join(f"x{x}[{min(a for a,b in s):.0f}-{max(b for a,b in s):.0f}]" for x, s in sorted(vv.items())))
    ws = [w for w in up if inrow(y0, y1, w) and w['x0'] > CX0 - 1]
    for l in phr(ws): print(l)
    rc = [c for c in rot if y0 <= c['top'] <= y1 and c['x0'] > CX0 - 1]
    if rc:
        cols = collections.defaultdict(list)
        for c in rc: cols[round(c['x0'] / 2.5)].append(c)
        for kx in sorted(cols):
            cs = sorted(cols[kx], key=lambda c: -c['top'])
            print(f"   ROT x{cs[0]['x0']:.0f}: " + ''.join(c['text'] for c in cs))
