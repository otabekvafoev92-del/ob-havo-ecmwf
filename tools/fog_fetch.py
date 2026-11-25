"""Fog over Uzbekistan from ECMWF (prob/moisture.py fetch: HRES to 10 days, one ensemble member to 15 days): where the air
at 2 m is near saturation (temperature − dew point ≤ ~1.5 °C), the wind is light and it is not raining, as 0…1.
Usage: python tools/fog_fetch.py prob.npz fog.npz  (the run: the 00/12 UTC run of prob.npz)"""
import sys, pathlib, datetime as dt
import numpy as np
from scipy.ndimage import gaussian_filter
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'prob'))
import moisture as M, render as Rn

D = Rn.load(sys.argv[1]); run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None); run = run.replace(hour=0 if run.hour < 12 else 12)
F = M.fetch(run, M.STEPS15)
lon = M.LON0 + np.arange(F[min(F)]['msl'].shape[1]) * M.RES; lat = M.LAT0 + np.arange(F[min(F)]['msl'].shape[0]) * M.RES
ci = np.flatnonzero((lon >= 45) & (lon <= 85)); ri = np.flatnonzero((lat >= 32) & (lat <= 50))
ks = sorted(F); fog, vt = [], []
for j, s in enumerate(ks):
    f = F[s]
    if 'td2' not in f: continue
    sp = f['t2'] - f['td2']; ws = f.get('ws', np.zeros_like(sp))
    rate = np.clip(f['tp'] - F[ks[j - 1]]['tp'], 0, None) / max(1, s - ks[j - 1]) if j else np.zeros_like(sp)  # mm per hour
    g = np.clip((1.8 - sp) / 1.3, 0, 1) * np.clip((4.5 - ws) / 3.0, 0, 1) * np.clip((0.3 - rate) / 0.3, 0, 1)
    fog.append(gaussian_filter(g, 1.0)[np.ix_(ri, ci)].astype(np.float16)); vt.append((run + dt.timedelta(hours=s) - dt.datetime(1970, 1, 1)).total_seconds() / 3600)
np.savez_compressed(sys.argv[2], fog=np.array(fog), vt=np.array(vt), lon=lon[ci], lat=lat[ri])
print('fog steps', len(fog), 'max', float(np.max(fog)) if fog else None)
