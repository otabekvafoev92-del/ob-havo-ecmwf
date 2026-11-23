"""The weather at one place by days: what the weather stations near it reported (WMO SYNOP, every 3 hours) and what ECMWF IFS
gave there (for each local day the 18 UTC run of the day before, hours 0–24).
Usage: python tools/point_days.py "Наманган" 41.0 71.67 2026-11-16 2026-11-22 out/  →  out/point_<start>_<end>.json"""
import sys, json, math, pathlib, datetime as dt, time
import numpy as np, requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'prob')); sys.path.insert(0, str(ROOT / 'tools'))
import moisture as M
import obs_video as OV

name, la0, lo0 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
d0, d1 = (dt.date.fromisoformat(x) for x in sys.argv[4:6]); OUT = pathlib.Path(sys.argv[6] if len(sys.argv) > 6 else 'out'); OUT.mkdir(parents=True, exist_ok=True)
lat = np.arange(M.LAT0, M.LAT1 + 1e-6, M.RES); lon = np.arange(M.LON0, M.LON1 + 1e-6, M.RES)
def at(a):  # bilinear at the place
    fy = (la0 - lat[0]) / M.RES; fx = (lo0 - lon[0]) / M.RES; y, x = int(fy), int(fx); wy, wx = fy - y, fx - x
    return float(a[y, x] * (1 - wy) * (1 - wx) + a[y + 1, x] * wy * (1 - wx) + a[y, x + 1] * (1 - wy) * wx + a[y + 1, x + 1] * wy * wx)
def rh(t, td): return 100 * math.exp(17.625 * td / (243.04 + td) - 17.625 * t / (243.04 + t))

# ECMWF at the place
ec = []
d = d0
while d <= d1:
    run = dt.datetime(d.year, d.month, d.day, 18) - dt.timedelta(days=1); steps = list(range(0, 25, 3))
    F = M.fetch(run, [(s, 'hres') for s in steps])
    if steps[-1] not in F: run -= dt.timedelta(hours=6); steps = list(range(6, 31, 3)); F = M.fetch(run, [(s, 'hres') for s in steps])
    terms = []
    for s in steps:
        if s not in F: continue
        f = F[s]; t = at(f['t2']); td = at(f['td2']) if 'td2' in f else None; u = at(f.get('u10', f['u'])); v = at(f.get('v10', f['v']))
        terms.append(dict(utc=(run + dt.timedelta(hours=s)).strftime('%Y-%m-%dT%H:%MZ'), local=(run + dt.timedelta(hours=s + 5)).strftime('%d.%m %H:%M'), t=round(t, 1),
                          rh=round(rh(t, td)) if td is not None else None, wind=round(math.hypot(u, v), 1), cloud=round(at(f['tcc']) * 100) if 'tcc' in f else None,
                          fog=bool(td is not None and rh(t, td) >= 95 and math.hypot(u, v) < 3)))
    pr = max(at(F[steps[-1]]['tp']) - at(F[steps[0]]['tp']), 0) if steps[-1] in F and steps[0] in F else None
    ec.append(dict(date=d.isoformat(), run=run.strftime('%Y-%m-%dT%HZ'), t_max=max(x['t'] for x in terms), t_min=min(x['t'] for x in terms), t_mean=round(sum(x['t'] for x in terms) / len(terms), 1),
                   pr=round(pr, 1) if pr is not None else None, wind_max=max(x['wind'] for x in terms), cloud_mean=round(sum(x['cloud'] or 0 for x in terms) / len(terms)),
                   fog_terms=[x['local'] for x in terms if x['fog']], terms=terms))
    print(d, 'ECMWF ok', flush=True); d += dt.timedelta(days=1)

# the weather stations within 40 km
st = OV.stations(); near = {k: v for k, v in st.items() if 111 * math.hypot(v['lat'] - la0, (v['lon'] - lo0) * math.cos(math.radians(la0))) <= 40}
print('stations', {k: v.get('name') for k, v in near.items()}, flush=True)
beg = dt.datetime(d0.year, d0.month, d0.day) - dt.timedelta(hours=6); end = dt.datetime(d1.year, d1.month, d1.day, 21)
txt = ''
for k in range(4):
    try:
        r = OV.S.get('https://www.ogimet.com/cgi-bin/getsynop', params=dict(block='38', begin=beg.strftime('%Y%m%d%H00'), end=end.strftime('%Y%m%d%H59')), timeout=180)
        if r.ok and 'AAXX' in r.text: txt = r.text; break
        print('ogimet', r.status_code, r.text[:200], flush=True)
    except requests.RequestException as e: print('ogimet', e, flush=True)
    time.sleep(30 * (k + 1))
VVT = lambda c: (c / 10 if c <= 50 else c - 50 if 56 <= c <= 80 else 30 + (c - 80) * 5 if 81 <= c <= 89 else {90: 0.05, 91: 0.05, 92: 0.2, 93: 0.5, 94: 1, 95: 2, 96: 4, 97: 10, 98: 20, 99: 50}.get(c))
obs = []
for line in txt.splitlines():
    p = line.split(',', 6)
    if len(p) < 7 or p[0] not in near: continue
    t = dt.datetime(int(p[1]), int(p[2]), int(p[3]), int(p[4]), int(p[5])); o = OV.decode(p[6]) or {}
    g = p[6].replace('=', ' ').split(); vis = None
    if len(g) > 3 and len(g[3]) == 5 and g[3][3:].isdigit(): vis = VVT(int(g[3][3:]))
    ww = o.get('ww'); kind = OV.wx(ww) if ww is not None else None
    obs.append(dict(station=p[0], name=near[p[0]].get('name'), utc=t.strftime('%Y-%m-%dT%H:%MZ'), local=(t + dt.timedelta(hours=5)).strftime('%d.%m %H:%M'), t=o.get('t'), td=o.get('td'),
                    rh=round(rh(o['t'], o['td'])) if o.get('t') is not None and o.get('td') is not None else None, wind=o.get('ws'), wind_dir=o.get('wd'), clouds_okta=o.get('n'),
                    ww=ww, kind=kind, rr=o.get('rr'), rr_hours={'1': 6, '2': 12, '3': 18, '4': 24, '5': 1, '6': 2, '7': 3, '8': 9, '9': 15}.get(o.get('rt')), vis_km=vis, raw=p[6].strip()))
obs.sort(key=lambda x: (x['station'], x['utc']))
json.dump(dict(place=name, lat=la0, lon=lo0, start=d0.isoformat(), end=d1.isoformat(), stations=near, ecmwf=ec, synop=obs,
               source='SYNOP via OGIMET (WMO block 38); ECMWF IFS HRES open data 0.25°, the 18 UTC run of the day before, hours 0–24'),
          open(OUT / f'point_{d0}_{d1}.json', 'w'), ensure_ascii=False, indent=1)
print('done', len(ec), 'days,', len(obs), 'reports')
