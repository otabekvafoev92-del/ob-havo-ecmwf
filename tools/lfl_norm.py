"""The climate norm 1991–2020 for the "weather against last year" report: for each region centre (tools/lfl.py) the mean daily
temperature (mean, max, min) and precipitation of each day of the year over 30 years (ERA5 through the Open-Meteo archive), smoothed
(temperature ±7 days, precipitation ±15 days). Run once (workflow lfl-norm.yml); written to prob/lfl_norm.json."""
import json, sys, time, pathlib
import numpy as np, requests

import ast
_src = (pathlib.Path(__file__).resolve().parent / 'lfl.py').read_text()  # the places of tools/lfl.py (read, not imported: it writes files when run)
P = next(ast.literal_eval(n.value) for n in ast.parse(_src).body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'P')

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'prob/lfl_norm.json')
V = ['temperature_2m_mean', 'temperature_2m_max', 'temperature_2m_min', 'precipitation_sum']; K = ['tm', 'tx', 'tn', 'pr']


def smooth(a, w):  # a circular running mean over the 366 days
    k = np.ones(2 * w + 1) / (2 * w + 1); b = np.concatenate([a[-w:], a, a[:w]]); return np.convolve(b, k, 'valid')


def get(p):
    for n in range(6):
        try:
            r = requests.get('https://archive-api.open-meteo.com/v1/archive', params=dict(latitude=p[3], longitude=p[4], start_date='1991-01-01', end_date='2020-12-31',
                             daily=','.join(V), timezone='Asia/Tashkent'), timeout=300)
            if r.ok: return r.json()['daily']
            print('retry', p[0], r.status_code, r.text[:150], flush=True)
        except requests.RequestException as e: print('retry', p[0], e, flush=True)
        time.sleep(60 * (n + 1))
    raise RuntimeError('no data for ' + p[0])


out = {'period': '1991-2020', 'source': 'ERA5 (Open-Meteo archive)', 'places': {}}
for p in P:
    d = get(p); doy = np.array([int(t[5:7]) * 100 + int(t[8:10]) for t in d['time']])
    days = sorted(set(doy)); idx = {x: i for i, x in enumerate(days)}  # 366 month-day keys, 29 Feb included
    rec = {}
    for k, v in zip(K, V):
        x = np.array([np.nan if y is None else y for y in d[v]], float); m = np.full(len(days), np.nan)
        for md in days: m[idx[md]] = np.nanmean(x[doy == md])
        rec[k] = [round(float(y), 2) for y in smooth(m, 15 if k == 'pr' else 7)]
    rec['md'] = days
    out['places'][p[0]] = rec; print(p[0], 'ok', flush=True); time.sleep(5)
OUT.parent.mkdir(parents=True, exist_ok=True); json.dump(out, open(OUT, 'w'), separators=(',', ':')); print(OUT, OUT.stat().st_size // 1024, 'KB')
