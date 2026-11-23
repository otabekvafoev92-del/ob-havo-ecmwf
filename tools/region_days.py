"""The weather of the regions of Uzbekistan by days, from ECMWF IFS: for each local day (Tashkent, UTC+5) the 18 UTC run of the
day before, its first 24 hours — the temperature every 3 hours (steps 0…24) and the precipitation over the 24 hours.
Each region: the mean over its area (the 0.25° grid refined ×4, cut by the region's border), the warmest and the coldest point,
the wettest point and the share of the area with ≥1 mm; next to it the 1991–2020 norm (ERA5) of the region's centre.
Usage: python tools/region_days.py 2026-11-02 2026-11-22 out/   →  out/region_days.json"""
import sys, json, pathlib, datetime as dt
import numpy as np
from scipy.ndimage import zoom
from matplotlib.path import Path as MPath

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'prob'))
import moisture as M

d0, d1 = (dt.date.fromisoformat(x) for x in sys.argv[1:3]); OUT = pathlib.Path(sys.argv[3] if len(sys.argv) > 3 else 'out'); OUT.mkdir(parents=True, exist_ok=True)
# the regions asked for (geo_admin ids) and the town whose norm stands for each
REG = [(10, 'Джизакская область', 'jizzakh'), (9, 'Сырдарьинская область', 'gulistan'), (6, 'Сурхандарьинская область', 'termez'), (5, 'Навоийская область', 'navoi'),
       (8, 'Ташкентская область', 'nurafshon'), (12, 'Кашкадарьинская область', 'karshi'), (7, 'Самаркандская область', 'samarkand'), (2, 'Ферганская область', 'fergana'),
       (13, 'г. Ташкент', 'tashkent'), (11, 'Бухарская область', 'bukhara'), (0, 'Андижанская область', 'andijan'), (1, 'Наманганская область', 'namangan')]
GA = {a['id']: a for a in json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']['adm1']}
NORM = json.load(open(ROOT / 'prob' / 'lfl_norm.json'))['places']
lat = np.arange(M.LAT0, M.LAT1 + 1e-6, M.RES); lon = np.arange(M.LON0, M.LON1 + 1e-6, M.RES)
UP = 4; up = lambda a: zoom(a, UP, order=1)
LATu = np.linspace(lat[0], lat[-1], len(lat) * UP); LONu = np.linspace(lon[0], lon[-1], len(lon) * UP)
pts = np.c_[np.repeat(LONu[None], len(LATu), 0).ravel(), np.repeat(LATu[:, None], len(LONu), 1).ravel()]
MASK = {}
for rid, *_ in REG:
    m = np.zeros(len(pts), bool)
    for r in GA[rid]['r']: m |= MPath(np.asarray(r)).contains_points(pts)
    MASK[rid] = m.reshape(len(LATu), len(LONu)); print(rid, GA[rid]['name']['ru'], int(MASK[rid].sum()), 'cells', flush=True)

days, out = [], {str(rid): [] for rid, *_ in REG}
d = d0
while d <= d1:
    run = dt.datetime(d.year, d.month, d.day, 18) - dt.timedelta(days=1); steps = list(range(0, 25, 3))
    F = M.fetch(run, [(s, 'hres') for s in steps])
    if len(F) < len(steps):  # fall back to the 12 UTC run, 6 hours further on
        run = run - dt.timedelta(hours=6); steps = list(range(6, 31, 3)); F = M.fetch(run, [(s, 'hres') for s in steps])
    ok = [s for s in steps if s in F]; print(d, 'run', run, len(ok), 'of', len(steps), 'steps', flush=True)
    if len(ok) < 6 or steps[-1] not in F: d += dt.timedelta(days=1); continue
    T = np.stack([up(F[s]['t2']) for s in ok]); P = up(np.maximum(F[steps[-1]]['tp'] - F[steps[0]]['tp'], 0))
    days.append(d.isoformat()); doy = d.timetuple().tm_yday - 1
    for rid, name, town in REG:
        m = MASK[rid]; t = T[:, m]; p = P[m]; n = NORM.get(town, {})
        out[str(rid)].append(dict(date=d.isoformat(), t_mean=round(float(t.mean()), 1), t_max=round(float(t.max(0).mean()), 1), t_min=round(float(t.min(0).mean()), 1),
                                  t_max_abs=round(float(t.max()), 1), t_min_abs=round(float(t.min()), 1), pr=round(float(p.mean()), 1), pr_max=round(float(p.max()), 1),
                                  wet=round(float((p >= 1).mean() * 100)), n_tm=n.get('tm', [None] * 366)[doy], n_tx=n.get('tx', [None] * 366)[doy],
                                  n_tn=n.get('tn', [None] * 366)[doy], n_pr=n.get('pr', [None] * 366)[doy], run=run.strftime('%Y-%m-%dT%HZ')))
    d += dt.timedelta(days=1)
json.dump(dict(source='ECMWF IFS HRES open data (0.25°), the 18 UTC run of the day before, hours 0–24; norm 1991–2020 ERA5 (Open-Meteo archive) of the region centre',
               days=days, regions=[dict(id=rid, name=name, norm_town=town, days=out[str(rid)]) for rid, name, town in REG]),
          open(OUT / 'region_days.json', 'w'), ensure_ascii=False, indent=1)
print('done', len(days), 'days')
