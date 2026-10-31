"""Builds the probability files from the browser run (tools/collect_chunks.py output):
  PG → glob.npz (world, 0.5°), PR → prob.npz (CIS + Turkey, 0.25°), WX → wx.npz (GEFS mean T / cloud, 1° world).
Usage: python3 tools/world_from_browser.py chunks.json RUN(e.g. 2026-10-30T12:00:00Z) outdir"""
import json, sys, gzip, base64, pathlib
import numpy as np
C = json.load(open(sys.argv[1])); RUN = sys.argv[2]; out = pathlib.Path(sys.argv[3])
GRIDS = {'PG': ('glob.npz', dict(lon0=-180.0, lat0=90.0, d=0.5, W=720, H=361)), 'PR': ('prob.npz', dict(lon0=20.0, lat0=82.0, d=0.25, W=681, H=229))}
for key, (name, G) in GRIDS.items():
    N = G['W'] * G['H']; rows = {}
    for part in C[key].split('~'):
        s, n, d, data = part.split('^'); rows[int(s)] = (list(map(int, n.split(','))), list(map(int, d.split(','))), data)
    steps = sorted(rows)
    P = np.zeros((len(steps), G['H'], G['W']), np.uint8); amt = np.zeros_like(P)
    nm = np.zeros((len(steps), 3), np.int16); dv = np.zeros((len(steps), 4), bool)
    for i, s in enumerate(steps):
        n, d, data = rows[s]
        b = np.frombuffer(gzip.decompress(base64.b64decode(data)), np.uint8)
        P[i] = b[:N].reshape(G['H'], G['W']); amt[i] = b[N:2 * N].reshape(G['H'], G['W']); nm[i] = n; dv[i, :3] = d
    np.savez_compressed(out / name, run=RUN, steps=np.array(steps), win=np.full(len(steps), 6), grid=np.array(G, dtype=object), P=P, amt=amt,
                        ens_names=np.array(['ifs', 'aifs', 'gefs']), det_names=np.array(['hres', 'aifss', 'gfs', 'icon']), n_members=nm, det_avail=dv)
    print(name, len(steps), steps[0], steps[-1], nm.min(0).tolist(), nm.max(0).tolist())
WG = dict(lon0=-180.0, lat0=90.0, d=1.0, W=360, H=181); NW = WG['W'] * WG['H']
wrows = {}
for part in C['WX'].split('~'):
    s, data = part.split('^'); wrows[int(s)] = data
ws = sorted(wrows)
T = np.full((len(ws), WG['H'], WG['W']), np.nan, np.float32); Cl = T.copy()
for i, s in enumerate(ws):
    b = np.frombuffer(gzip.decompress(base64.b64decode(wrows[s])), np.uint8).astype(np.float32)
    t, c = b[:NW], b[NW:2 * NW]
    T[i] = np.where(t < 255, t / 2 - 60, np.nan).reshape(WG['H'], WG['W']); Cl[i] = np.where(c < 255, c / 2.5, np.nan).reshape(WG['H'], WG['W'])
np.savez_compressed(out / 'wx.npz', run=RUN, steps=np.array(ws), grid=np.array(WG, dtype=object), T=T.astype(np.float16), C=Cl.astype(np.float16))
print('wx', len(ws))
