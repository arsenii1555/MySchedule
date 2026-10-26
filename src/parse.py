"""Розбір PDF-розкладів юрфаку ЛНУ в JSON.
python3 parse.py  -> data/parsed.json + data/flags.txt
"""
import pdfplumber, re, json, collections, sys

DAYS = {"ПОНЕДІЛОК": 1, "ВІВТОРОК": 2, "СЕРЕДА": 3, "ЧЕТВЕР": 4, "П'ЯТНИЦЯ": 5, "ПʼЯТНИЦЯ": 5, "П’ЯТНИЦЯ": 5, "СУБОТА": 6}
KINDS = r"(лекція|практичне|семінарське|семінар|лабораторне|консультація|практичне заняття)"
CX0, CX1 = 86, 558
FLAGS = []

def flag(*a): FLAGS.append(" ".join(str(x) for x in a))

def clus(vals, tol):
    vals = sorted(vals); out = []
    for v in vals:
        if out and v - out[-1][-1] <= tol: out[-1].append(v)
        else: out.append([v])
    return [sum(c) / len(c) for c in out]

def cover(segs, a, b):
    """частка відрізка [a,b], покрита segs"""
    if b - a <= 0: return 1
    segs = sorted((max(s, a), min(e, b)) for s, e in segs if e > a and s < b)
    tot, cur = 0, a
    for s, e in segs:
        s = max(s, cur)
        if e > s: tot += e - s; cur = e
    return tot / (b - a)

def norm(t):
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([.,)])", r"\1", t)
    t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r"(\w)\s+-\s+(\w)", r"\1-\2", t)
    for _ in range(4):
        t = re.sub(r"\b(\w)\.\s+(\w)\.", r"\1.\2.", t)
    t = re.sub(r"\b(\d{2,4})\s+(СП|Ю|Г|А|Б)\b", r"\1\2", t)
    t = t.replace(" .", ".")
    t = re.sub(r"(\w)\s*[’'ʼ]\s*(\w)", r"\1ʼ\2", t)
    t = re.sub(r"\s+:", ":", t)
    t = re.sub(r"\.-\s+", ".-", t)
    t = re.sub(r"(\w)-\s+(\w)", r"\1-\2", t)
    t = re.sub(r"\b(к\.ю\.н|д\.ю\.н)\s", r"\1. ", t)
    t = re.sub(r"\b(доц|проф|ас|викл|ст)\s(?=[А-ЯІЇЄҐ])", r"\1. ", t)
    t = re.sub(r"\b([А-ЯІЇЄҐ])\.\s([А-ЯІЇЄҐ])\b(?!\.)", r"\1.\2.", t)
    t = re.sub(r"\b([А-ЯІЇЄҐ])\.([А-ЯІЇЄҐ])(?=\s|$)", r"\1.\2.", t)
    return t

class Page:
    def __init__(self, p):
        self.p = p
        R = p.rects
        self.H = [r for r in R if r['height'] < 3 and r['width'] > 1.5]
        self.V = [r for r in R if r['width'] < 3 and r['height'] > 1.5]
        # злиті вертикальні лінії (пунктир -> суцільні відрізки)
        byx = collections.defaultdict(list)
        for r in self.V: byx[round((r['x0'] + r['x1']) / 2)].append(r)
        Vm = []
        for x, rs in byx.items():
            rs.sort(key=lambda r: r['top'])
            cur = None
            for r in rs:
                if cur and r['top'] - cur['bottom'] < 1.5: cur['bottom'] = max(cur['bottom'], r['bottom'])
                else:
                    if cur: Vm.append(cur)
                    cur = dict(x0=r['x0'], x1=r['x1'], width=r['width'], top=r['top'], bottom=r['bottom'])
            if cur: Vm.append(cur)
        self.Vm = Vm
        self.words = [w for w in p.extract_words(extra_attrs=["fontname", "upright"], x_tolerance=1.5) if w['upright']]
        rot = [c for c in p.chars if not c['upright'] and c['text'].strip() != '' or (not c['upright'] and c['text'] == ' ')]
        # rotated lines: cluster by x0
        cols = collections.defaultdict(list)
        for c in rot:
            cols[round(c['x0'] / 2.0)].append(c)
        lines = []
        for k in sorted(cols):
            cs = cols[k]
            # split column into separate runs by y gaps
            cs.sort(key=lambda c: -c['top'])
            runs = [[cs[0]]]
            for c in cs[1:]:
                if runs[-1][-1]['top'] - c['bottom'] > 6: runs.append([c])
                else: runs[-1].append(c)
            for r in runs:
                txt = ''.join(c['text'] for c in r)
                if not txt.strip(): continue
                bold = any('Bold' in c['fontname'] for c in r)
                lines.append(dict(x0=min(c['x0'] for c in r), x1=max(c['x1'] for c in r), top=min(c['top'] for c in r), bottom=max(c['bottom'] for c in r), text=txt, bold=bold,
                                  btext=''.join(c['text'] for c in r if 'Bold' in c['fontname'])))
        # merge rotated lines with near-identical x (same line split by chars)
        self.rot = lines

def parse_course(k, path):
    pdf = pdfplumber.open(path)
    lessons, streams = [], []
    gcols, groups, day = None, None, None
    last = {"day": None, "pair": None, "lessons": []}
    for pi, p in enumerate(pdf.pages):
        P = Page(p)
        # header with groups
        hdr = [w for w in P.words if w['text'].startswith('ЮРД')]
        if hdr:
            # group names: word "ЮРД", then "–", then code
            ws = sorted(P.words, key=lambda w: (round(w['top']), w['x0']))
            names = []
            top = hdr[0]['top']
            row = [w for w in ws if abs(w['top'] - top) < 3]
            row.sort(key=lambda w: w['x0'])
            starts = [i for i, w in enumerate(row) if w['text'].startswith('ЮРД')]
            for n, i in enumerate(starts):
                seg = row[i:(starts[n + 1] if n + 1 < len(starts) else len(row))]
                code = ''.join(w['text'] for w in seg).replace('ЮРД', '').replace('–', '').replace('-', '')
                names.append(("ЮРД-" + code, (seg[0]['x0'] + seg[-1]['x1']) / 2))
            # columns: header V lines spanning header
            hb = [r for r in P.H if r['x0'] < 70 and r['x1'] > 80]
            hy = sorted(r['top'] for r in hb)
            ytop = max([y for y in hy if y < top] or [top - 10]); ybot = min([y for y in hy if y > top] or [top + 15])
            vx = clus([r['x0'] for r in P.V if r['x0'] > CX0 + 5 and r['x1'] < CX1 - 5 and cover([(r['top'], r['bottom'])], ytop + 1, ybot - 1) > 0.6], 3)
            xs = [CX0] + vx + [CX1]
            gcols = [(xs[i], xs[i + 1]) for i in range(len(xs) - 1)]
            assert len(gcols) == len(names), (k, pi, names, gcols)
            groups = [n for n, _ in names]
            streams.append(groups)
            day = None
            content_top = ybot
        else:
            content_top = 0
        # row boundaries from pair column
        ys = clus([r['top'] for r in P.H if r['x0'] < 72 and r['x1'] > 80 and r['top'] >= content_top - 1], 3)
        # day labels (rotated, in day column)
        dl = [l for l in P.rot if l['x1'] < 66]
        dayspans = []
        for l in dl:
            t = l['text'].replace(' ', '').upper().replace("’", "'").replace("ʼ", "'")
            for nm, n in DAYS.items():
                if nm.replace("ʼ", "'") == t or nm == t:
                    dayspans.append((l['top'], l['bottom'], n))
        # day band boundaries: thick lines spanning day column
        dlines = clus([r['top'] for r in P.H if r['x0'] < 45 and r['x1'] > 60 and r['top'] >= content_top - 1], 4)
        def day_at(y):
            for i in range(len(dlines) - 1):
                if dlines[i] - 1 <= y <= dlines[i + 1] + 1:
                    for a, b, n in dayspans:
                        if dlines[i] - 2 <= (a + b) / 2 <= dlines[i + 1] + 2: return n
            return None
        pnum = [w for w in P.words if 64 < w['x0'] < 86 and re.fullmatch(r"\d\.", w['text'])]
        for ri in range(len(ys) - 1):
            y0, y1 = ys[ri], ys[ri + 1]
            if y1 - y0 < 6: continue
            nums = [int(w['text'][0]) for w in pnum if y0 <= (w['top'] + w['bottom']) / 2 <= y1]
            cont = False
            if not nums:
                if ri == 0 and last["pair"] and y1 - y0 > 15:
                    cont = True; pair = last["pair"]
                else: continue
            else: pair = nums[0]
            d = day_at((y0 + y1) / 2)
            if d is None:
                if last["day"]: d = last["day"]
                else:
                    flag(f"k{k} p{pi+1}: не визначено день для рядка y{y0:.0f}"); continue
            Ls = parse_row(k, pi + 1, P, y0, y1, d, pair, gcols, groups)
            if cont:
                prev = [L for L in last["lessons"] if L['d'] == d and L['p'] == pair]
                for L in Ls:
                    if L['w'] == "":
                        L['w'] = "z"
                for L in prev:
                    if L['w'] == "" and any(min(L['_cell'][1], M['_cell'][1]) - max(L['_cell'][0], M['_cell'][0]) > 5 for M in Ls):
                        L['w'] = "c"
                flag(f"k{k} p{pi+1}: рядок d{d} p{pair} продовжується з попередньої сторінки ({len(prev)}+{len(Ls)} занять)")
            lessons += Ls
            last["day"], last["pair"], last["lessons"] = d, pair, Ls
    return lessons, streams

def parse_row(k, pg, P, y0, y1, d, pair, gcols, groups):
    tag = f"k{k} p{pg} d{d} p{pair}"
    H = [r for r in P.H if r['x1'] > CX0 + 2 and r['x0'] < CX1 - 2 and y0 + 1.5 < r['top'] < y1 - 1.5]
    V = [r for r in P.Vm if CX0 + 3 < r['x0'] < CX1 - 3 and r['top'] < y1 - 1.5 and r['bottom'] > y0 + 1.5
         and not (r['top'] <= y0 + 1.5 and r['bottom'] < y0 + 6) and not (r['bottom'] >= y1 - 1.5 and r['top'] > y1 - 6)]
    xs = [CX0] + clus([r['x0'] + r['width'] / 2 for r in V], 2.5) + [CX1]
    yb = [y0] + clus([r['top'] + r['height'] / 2 for r in H] + [max(r['top'], y0) for r in V if r['top'] > y0 + 2] + [min(r['bottom'], y1) for r in V if r['bottom'] < y1 - 2], 2.5) + [y1]
    yb = [y for i, y in enumerate(yb) if i == 0 or y - yb[i - 1] > 1.2]
    nx, ny = len(xs) - 1, len(yb) - 1
    def vblock(i, j):  # boundary between col j and j+1 in row i
        X = xs[j + 1]; segs = [(r['top'], r['bottom']) for r in V if abs(r['x0'] + r['width'] / 2 - X) < 2.5]
        return cover(segs, yb[i], yb[i + 1]) > 0.5
    def hblock(i, xa, xb):  # boundary below row i over [xa,xb]
        Y = yb[i + 1]; segs = [(r['x0'], r['x1']) for r in H if abs(r['top'] + r['height'] / 2 - Y) < 2.5]
        return cover(segs, xa, xb) > 0.5
    strips = []  # (i, ja, jb)
    for i in range(ny):
        ja = 0
        for j in range(nx):
            if j == nx - 1 or vblock(i, j):
                strips.append((i, ja, j)); ja = j + 1
    par = list(range(len(strips)))
    def find(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    idx = {s: n for n, s in enumerate(strips)}
    for n, (i, ja, jb) in enumerate(strips):
        if i + 1 < ny and (i + 1, ja, jb) in idx and not hblock(i, xs[ja], xs[jb + 1]):
            par[find(n)] = find(idx[(i + 1, ja, jb)])
    cells = collections.defaultdict(list)
    for n, s in enumerate(strips): cells[find(n)].append(s)
    C = []
    for key, ss in cells.items():
        x0 = xs[min(s[1] for s in ss)]; x1 = xs[max(s[2] for s in ss) + 1]
        t0 = yb[min(s[0] for s in ss)]; t1 = yb[max(s[0] for s in ss) + 1]
        C.append(dict(x0=x0, x1=x1, top=t0, bottom=t1, up=[], rot=[]))
    def cell_of(x, y):
        for c in C:
            if c['x0'] - 0.5 <= x <= c['x1'] + 0.5 and c['top'] - 0.5 <= y <= c['bottom'] + 0.5: return c
    for w in P.words:
        cx, cy = (w['x0'] + w['x1']) / 2, (w['top'] + w['bottom']) / 2
        if cx < CX0 or not (y0 < cy < y1): continue
        c = cell_of(cx, cy)
        if c: c['up'].append(w)
    for l in P.rot:
        cx, cy = (l['x0'] + l['x1']) / 2, (l['top'] + l['bottom']) / 2
        if cx < CX0 or not (y0 < cy < y1): continue
        c = cell_of(cx, cy)
        if c: c['rot'].append(l)
    # cell texts
    for c in C:
        ws = sorted(c['up'], key=lambda w: (w['top'], w['x0']))
        lines = []
        for w in ws:
            if lines and abs(lines[-1][0]['top'] - w['top']) < 2.2: lines[-1].append(w)
            else: lines.append([w])
        txt, btxt = [], []
        for l in lines:
            l.sort(key=lambda w: w['x0'])
            txt.append(' '.join(w['text'] for w in l))
            btxt += [w['text'] for w in l if 'Bold' in w['fontname']]
        for l in sorted(c['rot'], key=lambda l: l['x0']):
            txt.append(l['text']);
            if l['bold']: btxt.append(l['btext'])
        c['lines'] = [norm(t) for t in txt]
        c['text'] = norm(' '.join(txt))
        c['bold'] = norm(' '.join(btxt))
    C = [c for c in C]
    # titles
    for c in C:
        c['title'] = None
        if not c['text']: continue
        m = re.match(r"^(?:(ВНД|ДВВС)\s+)?(.+?)\s*[–-]\s*" + KINDS + r"\b\s*(.*)$", c['text'])
        if m and c['bold']:
            c['title'] = dict(cat=m.group(1) or "", subj=m.group(2).strip(), kind=m.group(3), rest=m.group(4).strip())
        elif c['bold'] and re.fullmatch(r"(ВНД|ДВВС)", c['text'].strip()):
            c['title'] = dict(cat=c['text'].strip(), subj="", kind="", rest="")
        elif c['bold'] and c['text'] == c['bold']:
            c['title'] = dict(cat="", subj=c['text'], kind="", rest="")
    # parent for content-only cells
    out = []
    for c in C:
        if not c['text']: continue
        if c['title']:
            par_ = c
            content = c['title']['rest']
        else:
            cands = [t for t in C if t['title'] and t['bottom'] <= c['top'] + 1.5 and t['x0'] <= c['x0'] + 2 and t['x1'] >= c['x1'] - 2]
            if not cands:
                flag(f"{tag}: клітинка без назви предмета: «{c['text']}»"); continue
            par_ = max(cands, key=lambda t: t['bottom'])
            par_.setdefault('kids', []).append(c)
            content = c['text']
        c['par'] = par_; c['content'] = content
    lessons = []
    for c in C:
        if not c.get('par'): continue
        if c['title'] and c.get('kids') and not c['title']['rest']: continue  # title-only parent
        if c['title'] and c.get('kids') and c['title']['rest']:
            flag(f"{tag}: у назві є текст і є підклітинки: «{c['text']}»")
        t = c['par']['title']
        L = dict(_pg=pg, d=d, p=pair, s=t['subj'], k=t['kind'], cat=t['cat'], _cell=(c['x0'], c['x1'], c['top'], c['bottom']), _par=(c['par']['x0'], c['par']['x1'], c['par']['top'], c['par']['bottom']))
        rest = c['content']
        m = re.search(r"(\d{1,2}[:.]\d{2})\s*[–-]\s*(\d{1,2}[:.]\d{2})", rest)
        if m:
            L['time'] = [m.group(1).replace('.', ':').zfill(5), m.group(2).replace('.', ':').zfill(5)]; rest = (rest[:m.start()] + rest[m.end():]).strip()
        m = re.search(r"\b(\d)\s*груп[аи]\b", rest)
        if m: L['eg'] = [int(m.group(1))]; rest = (rest[:m.start()] + rest[m.end():]).strip()
        m = re.search(r"\b(Англійська|Німецька|Французька|Іспанська|Італійська|Польська) мова\b", rest)
        if m: L['lang'] = m.group(1); rest = (rest[:m.start()] + rest[m.end():]).strip()
        room = ""
        m = re.search(r"(?:^|\s)(\d{2,4}(?:СП|Ю|Г|А|Б)?|ВАК\s+\d{2,4}|НСК.*|online|онлайн)\s*$", rest)
        if m: room = m.group(1).strip(); rest = rest[:m.start()].strip()
        if room.startswith("ВАК"): rest = (rest + " ВАК").strip(); room = room[3:].strip()
        rest = rest.strip(' ,')
        if rest == "ВАК": rest = "вакансія"
        L['t'] = rest; L['r'] = room
        if t['subj'] and re.search(r"потік", t['subj']):
            mm = re.search(r"\(([IІ]{1,3}|\d)\s*потік\)", t['subj'])
            if mm: L['potok'] = mm.group(1); L['potok'] = L['potok'].replace("І", "I"); L['s'] = re.sub(r"\s*\(\s*([IІ]{1,3}|\d)\s*потік\s*\)", "", t['subj']).strip()
        lessons.append(L)
    # week halves: group lessons by parent region
    regs = collections.defaultdict(list)
    for L in lessons: regs[L['_par']].append(L)
    for par_, Ls in regs.items():
        xa = par_[0]; xb = par_[1]
        top = par_[2]; bot = max(L['_cell'][3] for L in Ls)
        above = top - y0 > 6; below = y1 - bot > 6
        # is there anything (cell) above/below in same x-range?
        w = "c" if below and not above else "z" if above and not below else "" if not above and not below else "?"
        if w == "?": flag(f"{tag}: неясно чис/знам для «{Ls[0]['s']}»")
        for L in Ls: L['w'] = w if w != "?" else ""
    # groups mapping
    for L in lessons:
        x0, x1 = L['_cell'][0], L['_cell'][1]
        full, part = [], []
        for (a, b), g in zip(gcols, groups):
            ov = max(0, min(b, x1) - max(a, x0)) / (b - a)
            if ov >= 0.85: full.append(g)
            elif ov > 0.08: part.append((g, ov, a, b))
        if L['cat'] or L['s'] in ("Іноземна мова",):
            L['g'] = list(groups)
            if L['s'] == "Іноземна мова":
                L['fl'] = {"Німецька": "de", "Французька": "fr", "Іспанська": "es", "Англійська": "en"}.get(L.pop('lang', None) or "", "en")
            elif L['cat'] == "ДВВС" and not L['s']:
                L['s'] = "ДВВС"; L['cat'] = ""
            else:
                L['el'] = L['s']
        elif full and not part:
            L['g'] = full
        elif not full and len(part) == 1 and 0.3 < part[0][1] < 0.7:
            g, ov, a, b = part[0]; L['g'] = [g]; L['sg'] = 1 if (x0 + x1) / 2 < (a + b) / 2 else 2
        else:
            L['g'] = full + [p[0] for p in part]
            flag(f"{tag}: неочевидні групи для «{L['s']} {L['t']}»: {full} + {[(p[0], round(p[1],2)) for p in part]}")
        if 'lang' in L: flag(f"{tag}: мова «{L['lang']}» поза іноземною: {L['s']}")
    return lessons

def postprocess(lessons, streams):
    # потоки вибіркових: лекція (I потік) отримує групи з практичних того ж потоку
    for st in streams:
        Ls = [L for L in lessons if L['g'] and L['g'][0] in st and L.get('el')]
        egs = collections.defaultdict(set)
        for L in Ls:
            if L.get('potok') and L.get('eg'): egs[(L['el'], L['potok'])] |= set(L['eg'])
        for L in Ls:
            if L.get('potok') and not L.get('eg'):
                s = egs.get((L['el'], L['potok']))
                if s: L['eg'] = sorted(s)
                else: flag(f"потік без груп: {L['el']} {L['potok']}")
    for L in lessons:
        for k in ('_cell', '_par'): L.pop(k, None)
        c = L.pop('cat', '')
        if L.get('el') and c: L['ct'] = c
        for k in ('w', 't', 'r'):
            if k in L and not L[k]: del L[k]
    return lessons

if __name__ == "__main__":
    out = {"courses": []}
    for k in (1, 2, 3, 4):
        L, S = parse_course(k, f"pdf/k{k}.pdf")
        L = postprocess(L, S)
        out["courses"].append({"n": k, "groups": [g for s in S for g in s], "streams": S, "L": L})
        print(k, len(S), "потоків", len(L), "занять")
    json.dump(out, open("data/parsed.json", "w"), ensure_ascii=False, indent=1)
    open("data/flags.txt", "w").write("\n".join(FLAGS))
    print(len(FLAGS), "позначок")
