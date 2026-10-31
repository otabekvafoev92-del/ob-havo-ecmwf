"""Builds prob.npz from steps collected in the browser (combined probability already computed there
with the same equal-weight rule as prob/render.py).
Usage: python3 tools/prob_from_browser.py chunks.json key[,key2…] out.npz
Each step: "step^nIFS,nAIFS,nGEFS^hres,aifss,gfs^base64(gzip(P[N] + amt[N]))", steps joined by "~"."""
import json, sys, gzip, base64
import numpy as np
GRID = dict(lon0=20.0, lat0=82.0, d=0.25, W=681, H=197); N = GRID['W'] * GRID['H']
C = json.load(open(sys.argv[1])); keys = sys.argv[2].split(','); out = sys.argv[3]
rows = {}
for k in keys:
    for part in C[k].split('~'):
        s, n, d, data = part.split('^'); rows[int(s)] = (list(map(int, n.split(','))), list(map(int, d.split(','))), data)
steps = sorted(rows)
P = np.zeros((len(steps), GRID['H'], GRID['W']), np.uint8); amt = np.zeros_like(P)
nm = np.zeros((len(steps), 3), np.int16); dv = np.zeros((len(steps), 4), bool)
for i, s in enumerate(steps):
    n, d, data = rows[s]
    b = np.frombuffer(gzip.decompress(base64.b64decode(data)), np.uint8)
    P[i] = b[:N].reshape(GRID['H'], GRID['W']); amt[i] = b[N:2 * N].reshape(GRID['H'], GRID['W'])
    nm[i] = n; dv[i, :3] = d
np.savez_compressed(out, run='2026-10-29T00:00:00Z', steps=np.array(steps), grid=np.array(GRID, dtype=object), P=P, amt=amt,
                    ens_names=np.array(['ifs', 'aifs', 'gefs']), det_names=np.array(['hres', 'aifss', 'gfs', 'icon']), n_members=nm, det_avail=dv)
print('ok', steps[:3], '…', steps[-1], len(steps), nm[:2].tolist())
