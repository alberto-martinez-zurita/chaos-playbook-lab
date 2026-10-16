"""Check the numbers quoted in the paper (v1.1) against the released CSVs.

Recomputes per-cell metrics from experiments/<model>/<alias>/<variant>/rate_X.XX.csv (active cells
only; directories starting with "_" and retired/backup files are ignored) and compares them with the
values quoted in paper/00-abstract.md … 06-conclusions.md. Read-only.

Usage: python scripts/check_paper_numbers.py [--root experiments] [--csv paper_number_checks.csv]
Exit code 0 if every check passes, 1 otherwise.
"""
import argparse, csv, glob, math, os, random, re, statistics as stt, sys

ap = argparse.ArgumentParser()
ap.add_argument('--root', default='experiments')
ap.add_argument('--csv', default='paper_number_checks.csv')
args = ap.parse_args()
RATES = (0, .01, .02, .03, .05, .1, .15, .2, .25, .3)

# ---------- per-cell metrics ----------
cells = {}; runs = 0; excluded_runs = 0
for f in sorted(glob.glob(os.path.join(args.root, '*', '*', '*', 'rate_*.csv'))):
    model, alias, variant, fname = os.path.relpath(f, args.root).replace('\\', '/').split('/')
    rate = fname[5:-4]
    if model.startswith('_') or not re.fullmatch(r'\d\.\d\d', rate):
        continue
    with open(f, encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            runs += 1; excluded_runs += model == 'gpt_oss_20b'
            arm = 'nopb' if '-nopb' in r['agent_type'] else 'pb'
            c = cells.setdefault((model, variant, rate, arm), {'n': 0, 's': 0, 'dur': 0.0, 'tok': 0, 'calls': 0})
            c['n'] += 1; c['s'] += r['outcome'] == 'success'
            c['dur'] += float(r['duration_ms'] or 0)
            c['tok'] += int(r['prompt_tokens'] or 0) + int(r['completion_tokens'] or 0)
            c['calls'] += int(r['llm_calls'] or 0)

def C(m, v, r, a): return cells[(m, v, f'{r:.2f}', a)]
def sr(m, v, r, a): c = C(m, v, r, a); return round(100 * c['s'] / c['n'], 2)
def d(m, v, r): return round(sr(m, v, r, 'pb') - sr(m, v, r, 'nopb'), 2)
def wilson_hw(c):
    n = c['n']; p = c['s'] / n; z = 1.96; den = 1 + z*z/n
    return 100 * z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
def diff_ci(c1, c2):
    p1, p2 = c1['s']/c1['n'], c2['s']/c2['n']
    return 100 * 1.96 * math.sqrt(p1*(1-p1)/c1['n'] + p2*(1-p2)/c2['n'])

rows = []
def chk(sec, claim, text, calc, tol=0.051):
    if isinstance(text, (int, float)) and isinstance(calc, (int, float)) and not isinstance(text, bool):
        ok = abs(text - calc) <= tol
    else:
        ok = text == calc
    rows.append((sec, claim, text, calc, 'OK' if ok else 'DIFFERS'))

HTTP = {'qwen3.5 0.8 B': ('qwen35_0_8b', 'http'), 'qwen3.5 2 B': ('qwen35_2b', 'http'), 'Gemma 4 E2B': ('gemma4_e2b', 'http'),
        'Gemma 4 E4B': ('gemma4_e4b', 'http'), 'qwen3.5 4 B': ('qwen35_4b', 'http'), 'Nemotron Nano 4 B': ('nemotron_nano_4b', 'http_think'),
        'qwen3.5 9 B': ('qwen35_9b', 'http'), 'qwen3.5 9 B (distilled)': ('qwen35_9b_distilled', 'http'), 'Ministral 14 B': ('ministral_14b', 'http_think'),
        'Gemma 4 26 B (MoE)': ('gemma4_26b', 'http'), 'GLM 4.5 (think)': ('glm45', 'http_think')}
FUNC = [k for k in HTTP if k not in ('qwen3.5 0.8 B', 'qwen3.5 2 B')]
ACTIVE_B = {'Gemma 4 E2B': 2.3, 'qwen3.5 4 B': 4, 'Gemma 4 E4B': 4.5, 'Nemotron Nano 4 B': 4, 'Gemma 4 26 B (MoE)': 4,
            'qwen3.5 9 B': 9, 'qwen3.5 9 B (distilled)': 9, 'Ministral 14 B': 14, 'GLM 4.5 (think)': 32}

# ---------- dataset size (§1.3, §3.4) ----------
chk('§3.4', 'total runs', 128800, runs, 0); chk('§3.4', 'active runs', 128000, runs - excluded_runs, 0)
chk('§3.4', 'cells (model × variant × rate × arm)', 416, len(cells), 0)

# ---------- §4.1 table at 20 % ----------
t41 = {'qwen3.5 0.8 B': (0.0, 0.0), 'qwen3.5 2 B': (4.0, 31.5), 'Gemma 4 E2B': (19.0, 71.5), 'Gemma 4 E4B': (69.0, 98.5), 'qwen3.5 4 B': (71.5, 97.0),
       'Nemotron Nano 4 B': (43.5, 90.5), 'qwen3.5 9 B': (53.0, 89.5), 'qwen3.5 9 B (distilled)': (59.5, 98.0), 'Ministral 14 B': (41.0, 98.0),
       'Gemma 4 26 B (MoE)': (55.0, 97.5), 'GLM 4.5 (think)': (71.7, 98.3)}
for k, (n, p) in t41.items():
    chk('§4.1 table', f'{k} nopb@20', n, sr(*HTTP[k], .2, 'nopb')); chk('§4.1 table', f'{k} pb@20', p, sr(*HTTP[k], .2, 'pb'))
up = [sr(*HTTP[k], .2, 'pb') for k in ['qwen3.5 9 B', 'qwen3.5 9 B (distilled)', 'Ministral 14 B', 'Gemma 4 26 B (MoE)', 'GLM 4.5 (think)']]
chk('§4.1', 'upper-roster pb@20 within [89, 99]', True, 89 <= min(up) and max(up) <= 99)
chk('§4.1', 'no negative Δ in any cell', True, all(cells[(m, v, r, 'pb')]['s'] / cells[(m, v, r, 'pb')]['n'] >= cells[(m, v, r, 'nopb')]['s'] / cells[(m, v, r, 'nopb')]['n'] for (m, v, r, a) in cells if a == 'pb'))

# ---------- §4.2 ----------
t10 = {'Gemma 4 E2B': 50.5, 'qwen3.5 4 B': 13.5, 'Gemma 4 E4B': 14.0, 'Nemotron Nano 4 B': 31.0, 'qwen3.5 9 B': 24.0,
       'qwen3.5 9 B (distilled)': 18.0, 'Ministral 14 B': 34.0, 'Gemma 4 26 B (MoE)': 27.0, 'GLM 4.5 (think)': 14.3}
for k, x in t10.items(): chk('§4.2 table 10 %', f'Δ {k}', x, d(*HTTP[k], .1), 0.06)
t30 = {'qwen3.5 4 B': 36.5, 'Gemma 4 E4B': 41.0, 'Nemotron Nano 4 B': 52.5, 'qwen3.5 9 B': 50.0, 'qwen3.5 9 B (distilled)': 43.5,
       'Ministral 14 B': 67.0, 'Gemma 4 26 B (MoE)': 55.0, 'GLM 4.5 (think)': 40.0}
for k, x in t30.items(): chk('§4.2 table 30 %', f'Δ {k}', x, d(*HTTP[k], .3), 0.06)
chk('§4.2', 'Δ Gemma 4 E2B @30', 41.5, d(*HTTP['Gemma 4 E2B'], .3))
chk('§4.2', 'largest Δ@30 (functioning roster)', 'Ministral 14 B', max(FUNC, key=lambda k: d(*HTTP[k], .3)))
chk('§4.2', 'largest Δ@10 (functioning roster)', 'Gemma 4 E2B', max(FUNC, key=lambda k: d(*HTTP[k], .1)))
chk('§4.2', 'Δ@30 > Δ@10 for all functioning models except Gemma 4 E2B', ['Gemma 4 E2B'], [k for k in FUNC if d(*HTTP[k], .3) <= d(*HTTP[k], .1)])
for k, x in [('GLM 4.5 (think)', (.1, 'nopb', 85.2)), ('GLM 4.5 (think)', (.1, 'pb', 99.5)), ('qwen3.5 4 B', (.1, 'nopb', 85.5)),
             ('Gemma 4 E4B', (.1, 'nopb', 86.0)), ('GLM 4.5 (think)', (.3, 'nopb', 57.0)), ('qwen3.5 4 B', (.3, 'nopb', 57.5))]:
    chk('§4.2(a)', f'{k} {x[1]}@{int(x[0]*100)}', x[2], sr(*HTTP[k], x[0], x[1]))

def quad_t(r):
    xs = [math.log(ACTIVE_B[k]) for k in FUNC]; ys = [d(*HTTP[k], r) for k in FUNC]; n = len(xs)
    X = [[1, x, x*x] for x in xs]
    XtX = [[sum(X[i][a]*X[i][b] for i in range(n)) for b in range(3)] for a in range(3)]
    Xty = [sum(X[i][a]*ys[i] for i in range(n)) for a in range(3)]
    def inv3(m):
        a, b, c = m[0]; d_, e, f = m[1]; g, h, i = m[2]
        det = a*(e*i-f*h) - b*(d_*i-f*g) + c*(d_*h-e*g)
        return [[(e*i-f*h)/det, (c*h-b*i)/det, (b*f-c*e)/det], [(f*g-d_*i)/det, (a*i-c*g)/det, (c*d_-a*f)/det], [(d_*h-e*g)/det, (b*g-a*h)/det, (a*e-b*d_)/det]]
    Inv = inv3(XtX); beta = [sum(Inv[a][b]*Xty[b] for b in range(3)) for a in range(3)]
    res = [ys[i] - sum(beta[a]*X[i][a] for a in range(3)) for i in range(n)]
    s2 = sum(e*e for e in res) / (n - 3)
    return beta, beta[2] / math.sqrt(s2*Inv[2][2])
b30, t30_ = quad_t(.3); b10, t10_ = quad_t(.1)
chk('§5.5 viii', 'quadratic t at 30 % ≈ −1.1', -1.1, round(t30_, 1), 0.05)
chk('§5.5 viii', 'quadratic t at 10 % ≈ +0.9', 0.9, round(t10_, 1), 0.05)
chk('§5.5 viii', 'fitted peak at 30 % near 10 B', 10, round(math.exp(-b30[1]/(2*b30[2]))), 1)

# ---------- §4.3 ----------
gapB = max(abs(sr('qwen35_4b', 'http', r, 'nopb') - sr('gemma4_e4b', 'http', r, 'nopb')) for r in RATES)
chk('§4.3 B / §5.2', 'qwen 4B vs E4B nopb within 3 pp at every rate', True, gapB <= 3)
nem = [min(sr('qwen35_4b', 'http', r, 'nopb'), sr('gemma4_e4b', 'http', r, 'nopb')) - sr('nemotron_nano_4b', 'http_think', r, 'nopb') for r in RATES]
chk('§4.3 B / §5.2', 'Nemotron 12–26 pp below the non-reasoning pair', True, 12 <= min(nem) and max(nem) <= 26)
chk('§4.3 B', 'Nemotron pb@30', 86.5, sr('nemotron_nano_4b', 'http_think', .3, 'pb')); chk('§4.3 B', 'Nemotron nopb@0 ≈ 85', 85, sr('nemotron_nano_4b', 'http_think', 0, 'nopb'), 0.6)
chk('§4.3 B', 'qwen 4B and E4B pb@30 ≥ 94', True, min(sr('qwen35_4b', 'http', .3, 'pb'), sr('gemma4_e4b', 'http', .3, 'pb')) >= 94)
chk('§4.3 C', 'panel C pb@30 ≥ 86', True, all(sr(*HTTP[k], .3, 'pb') >= 86 for k in ['qwen3.5 9 B', 'qwen3.5 9 B (distilled)', 'Ministral 14 B', 'Gemma 4 26 B (MoE)']))
chk('§4.3 D', 'GLM pb@30', 97.0, sr('glm45', 'http_think', .3, 'pb'))
chk('§4.3 D', 'Wilson half-width GLM nopb@30 ≈ 4.0', 4.0, round(wilson_hw(C('glm45', 'http_think', .3, 'nopb')), 1), 0.2)
chk('§4.3 D', 'Wilson half-width qwen 4B nopb@30 ≈ 6.8', 6.8, round(wilson_hw(C('qwen35_4b', 'http', .3, 'nopb')), 1), 0.2)

# ---------- §4.4 / §4.5 ----------
diffs = {r: sr('glm45', 'http_think', r, 'nopb') - sr('glm45', 'http_nothink', r, 'nopb') for r in RATES}
rmax = max(diffs, key=lambda r: abs(diffs[r]))
chk('§4.4', 'max |think−nothink| HTTP nopb', '5.5@0.15', f'{abs(diffs[rmax]):.1f}@{rmax}')
chk('§4.4', '±5.6 on HTTP think−nothink @30', 5.6, round(diff_ci(C('glm45', 'http_think', .3, 'nopb'), C('glm45', 'http_nothink', .3, 'nopb')), 1), 0.2)
for v, a, x in [('http_think', 'nopb', 57.0), ('http_nothink', 'nopb', 55.0), ('mcp_nothink', 'nopb', 56.7), ('mcp_think', 'nopb', 39.2),
                ('a2a_nothink', 'nopb', 65.2), ('a2a_think', 'nopb', 51.5), ('http_think', 'pb', 97.0), ('http_nothink', 'pb', 91.3),
                ('a2a_think', 'pb', 99.5), ('a2a_nothink', 'pb', 98.8), ('mcp_think', 'pb', 88.3), ('mcp_nothink', 'pb', 99.2)]:
    chk('§4.4', f'GLM {v} {a}@30', x, sr('glm45', v, .3, a))
for m, v, a, x in [('ministral_14b', 'mcp_think', 'pb', 79.5), ('ministral_14b', 'http_think', 'pb', 94.5), ('ministral_14b', 'a2a_think', 'pb', 93.5),
                   ('ministral_14b', 'a2a_think', 'nopb', 87.5), ('ministral_14b', 'http_think', 'nopb', 27.5), ('gemma4_26b', 'a2a', 'nopb', 86.5), ('gemma4_26b', 'http', 'nopb', 38.5)]:
    chk('§4.5', f'{m} {v} {a}@30', x, sr(m, v, .3, a))
gaps = [sr('ministral_14b', o, .3, 'pb') - sr('ministral_14b', 'mcp_think', .3, 'pb') for o in ('http_think', 'a2a_think')] + \
       [sr('glm45', o, .3, 'pb') - sr('glm45', 'mcp_think', .3, 'pb') for o in ('http_think', 'a2a_think')]
chk('§4.9 (3)', 'MCP-under-reasoning pb gap at 30 % about 9–15 pp', True, 8.5 <= min(gaps) and max(gaps) <= 15)

# ---------- §4.6 ----------
V, D = ('qwen35_9b', 'http'), ('qwen35_9b_distilled', 'http')
for r, (a, b, ci) in {0: (99.0, 100.0, 1.4), .05: (86.5, 90.0, 6.3), .1: (73.0, 82.0, 8.0), .2: (53.0, 59.5, 9.7), .3: (36.5, 49.5, 9.6)}.items():
    chk('§4.6 table', f'vanilla nopb@{r}', a, sr(*V, r, 'nopb')); chk('§4.6 table', f'distilled nopb@{r}', b, sr(*D, r, 'nopb'))
    chk('§4.6 table', f'CI half-width @{r}', ci, round(diff_ci(C(*V, r, 'nopb'), C(*D, r, 'nopb')), 1), 0.15)
chk('§4.6', 'distilled > vanilla on nopb at 10/10 rates', 10, sum(sr(*D, r, 'nopb') > sr(*V, r, 'nopb') for r in RATES), 0)

# ---------- §4.7 ----------
HT = dict(HTTP); HT['GLM 4.5 (nothink)'] = ('glm45', 'http_nothink')
T = {'qwen3.5 4 B': (3224, 3663, 5.2, 5.4, 23.3, 18.6), 'Gemma 4 E4B': (2941, 3846, 5.0, 5.4, 19.8, 20.3), 'Nemotron Nano 4 B': (2709, 3702, 5.5, 6.1, 12.4, 12.6),
     'qwen3.5 9 B': (2597, 3644, 4.8, 5.4, 23.5, 26.7), 'Ministral 14 B': (1581, 2664, 4.5, 5.4, 15.4, 19.6), 'Gemma 4 26 B (MoE)': (1750, 2791, 4.7, 5.4, 14.8, 21.2),
     'GLM 4.5 (nothink)': (1680, 2472, 5.0, 5.4, 14.5, 13.4)}
dc = []
for k, (tn, tp, cn, cp, sn, sp) in T.items():
    a_, b_ = C(*HT[k], .1, 'nopb'), C(*HT[k], .1, 'pb')
    for lab, txt, val, tol in [('tokens nopb', tn, a_['tok']/a_['n'], 1), ('tokens pb', tp, b_['tok']/b_['n'], 1), ('calls nopb', cn, round(a_['calls']/a_['n'], 1), .06),
                               ('calls pb', cp, round(b_['calls']/b_['n'], 1), .06), ('time nopb (s)', sn, a_['dur']/a_['n']/1000, .06), ('time pb (s)', sp, b_['dur']/b_['n']/1000, .06)]:
        chk('§4.7 table', f'{k} {lab}', txt, round(val, 2), tol)
    dc.append(b_['calls']/b_['n'] - a_['calls']/a_['n'])
chk('§4.7', 'mean extra LLM calls', 0.57, round(stt.mean(dc), 2), 0.006)

# ---------- §4.9 / abstract: median and bootstrap ----------
for r, med, lo, hi in [(.1, 24.0, 14.0, 34.0), (.3, 43.5, 40.0, 55.0)]:
    xs = [d(*HTTP[k], r) for k in FUNC]
    chk('§4.9 / abstract', f'median Δ@{r} (n = {len(xs)})', med, stt.median(xs))
    random.seed(0); boots = sorted(stt.median(random.choices(xs, k=len(xs))) for _ in range(10000))
    chk('§4.9 / abstract', f'bootstrap 95 % CI Δ@{r} (percentile, 10,000 resamples)', f'[{lo}, {hi}]', f'[{boots[249]}, {boots[9749]}]')
chk('§4.9 (4)', 'qwen 2B Δ@0', 100, d('qwen35_2b', 'http', 0))
chk('abstract', 'qwen 0.8B fails at 0 % in both arms', True, sr('qwen35_0_8b', 'http', 0, 'nopb') == 0 == sr('qwen35_0_8b', 'http', 0, 'pb'))

# ---------- §5.6 / §6.4 ----------
n30 = [sr(*HTTP[k], .3, 'nopb') for k in FUNC]; p30 = sorted(sr(*HTTP[k], .3, 'pb') for k in FUNC)
chk('§6.4', 'functioning nopb@30 range 14.5–57.5 %', '14.5-57.5', f'{min(n30)}-{max(n30)}')
chk('§6.4', 'functioning pb@30 range 56–97 %', '56-97', f'{round(p30[0])}-{round(p30[-1])}')
chk('§6.4', 'functioning pb@30 without the smallest model 86–97 %', '86-97', f'{math.floor(p30[1])}-{round(p30[-1])}')
mid = [sr(*HTTP[k], .3, 'pb') for k in ['qwen3.5 4 B', 'Gemma 4 E4B', 'Nemotron Nano 4 B', 'Gemma 4 26 B (MoE)', 'qwen3.5 9 B', 'qwen3.5 9 B (distilled)', 'Ministral 14 B']]
chk('§5.6', 'mid-range pb@30 between 86 and 96 %', True, 86 <= min(mid) and max(mid) <= 96)

with open(args.csv, 'w', newline='', encoding='utf-8') as fh:
    w = csv.writer(fh, delimiter=';'); w.writerow(['section', 'claim', 'paper', 'recomputed', 'status']); w.writerows(rows)
bad = [r for r in rows if r[4] != 'OK']
print(f'{len(rows)} checks, {len(bad)} differ. Details: {args.csv}')
for r in bad: print('  DIFFERS:', ' | '.join(map(str, r)))
sys.exit(1 if bad else 0)
