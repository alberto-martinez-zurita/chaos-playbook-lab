"""Paired analysis of the playbook effect (paper v1.1, §3.7 and Table 4).

Run i uses seed 2026 + i in both arms, so each (model, protocol, rate) cell yields matched pairs.
For each cell: runs that succeed only with the playbook (b) and only without it (c), and the exact
McNemar test on the discordant pairs. Holm correction over the 81 functioning-roster HTTP cells
with failure rate > 0. Read-only: it only reads experiments/*/*/*/rate_X.XX.csv.

Usage: python scripts/paired_analysis.py [--root experiments] [--out paired_analysis.json]
"""
import csv, glob, os, re, sys, json, math
sys.stdout.reconfigure(encoding='utf-8')
import argparse
ap = argparse.ArgumentParser(); ap.add_argument('--root', default='experiments'); ap.add_argument('--out', default='paired_analysis.json')
args = ap.parse_args(); root, out = args.root, args.out
from math import comb
def mcnemar_exact(b, c):
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k + 1)) / 2**n
    return min(1.0, 2 * p)
bad_seed = 0; unpaired = 0; res = {}
for f in sorted(glob.glob(os.path.join(root, '*', '*', '*', 'rate_*.csv'))):
    rel = os.path.relpath(f, root).replace('\\', '/'); model, alias, variant, fname = rel.split('/'); rate = fname[5:-4]
    if model.startswith('_') or not re.fullmatch(r'\d\.\d\d', rate): continue
    arms = {'nopb': {}, 'pb': {}}
    for r in csv.DictReader(open(f, encoding='utf-8')):
        arm = 'nopb' if '-nopb' in r['agent_type'] else 'pb'
        idx = int(r['experiment_id'].rsplit('-', 1)[-1])
        if int(r['seed']) != 2026 + (idx % 10**6): bad_seed += 1
        arms[arm][idx] = (int(r['seed']), r['outcome'] == 'success')
    keys = set(arms['nopb']) & set(arms['pb'])
    unpaired += len(set(arms['nopb']) ^ set(arms['pb']))
    unpaired += sum(1 for k in keys if arms['nopb'][k][0] != arms['pb'][k][0])
    b = sum(1 for k in keys if arms['pb'][k][1] and not arms['nopb'][k][1])   # only pb
    c = sum(1 for k in keys if arms['nopb'][k][1] and not arms['pb'][k][1])   # only nopb
    res[f'{model}|{variant}|{rate}'] = {'pairs': len(keys), 'only_pb': b, 'only_nopb': c, 'p_mcnemar': mcnemar_exact(b, c)}
print('rows whose seed differs from 2026+index (later seed-base batches, GLM/Gemma 26B MCP/A2A):', bad_seed, '| pairs with different seeds across arms:', unpaired)
# Holm over the functioning-roster HTTP cells (9 models x 9 non-zero rates)
FUNC = [('gemma4_e2b', 'http'), ('qwen35_4b', 'http'), ('gemma4_e4b', 'http'), ('nemotron_nano_4b', 'http_think'), ('gemma4_26b', 'http'),
        ('qwen35_9b', 'http'), ('qwen35_9b_distilled', 'http'), ('ministral_14b', 'http_think'), ('glm45', 'http_think')]
fam = sorted(((res[f'{m}|{v}|{r}']['p_mcnemar'], f'{m}|{v}|{r}') for m, v in FUNC for r in ['0.01', '0.02', '0.03', '0.05', '0.10', '0.15', '0.20', '0.25', '0.30']))
m = len(fam); sig = 0; holm = {}
for i, (p, k) in enumerate(fam):
    adj = min(1.0, max(holm.get(fam[i-1][1], 0) if i else 0, (m - i) * p)); holm[k] = adj
    sig += adj < 0.05
print(f'Holm family: {m} cells (functioning roster, HTTP, rates 1-30 %); significant after Holm: {sig}')
for r in ['0.10', '0.30']:
    print(f'-- rate {r}')
    for mm, v in FUNC:
        k = f'{mm}|{v}|{r}'; x = res[k]
        print(f'  {mm:22s} only_pb={x["only_pb"]:4d} only_nopb={x["only_nopb"]:3d} p={x["p_mcnemar"]:.2e} Holm={holm[k]:.2e}')
nonsig = [(k, round(holm[k], 3)) for _, k in fam if holm[k] >= 0.05]
print('not significant after Holm:', nonsig)
json.dump({'cells': res, 'holm_functional_http': holm}, open(out, 'w', encoding='utf-8'), indent=1)
