"""Point forecasts for the Telegram bot (location or a searched town anywhere in the world):
the 15-day multimodel windows on the 0.5° world grid, cut into 10° × 10° tiles of 21 × 21 points.
  out/pt/index.json            run, steps, windows, tile layout
  out/pt/<top>_<left>.bin      uint8 [window][var][21][21], var = P (% × 2.5), T ((°C + 60) × 2), C (fraction × 250),
                               W (wind m/s × 5), A (ensemble-mean amount, round(ln(1 + mm) × 40)); 255 = no data
  out/places.json              towns for the bot's text search: [ru, uz, en, tr, iso, lat, lon, pop]
  out/pt25/...                 the same at 0.25° from the regional file (prob.npz: 20°E…190°E, 25°N…82°N), 5° × 5° tiles of 21 × 21 points:
                               the very numbers of the country videos, city texts and hourly forecasts, so every panel agrees
Usage: python3 prob/points.py glob.npz wx.npz site/prob [prob.npz]"""
import json, pathlib, sys
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render as Rn
from regions import UZ_CITY

TILE, N = 10, 21


def main():
    npz, wx, out = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
    D = Rn.load(npz); P, models, members = Rn.probability(D)
    W = Rn.load_wx_npz(D, wx) if wx and pathlib.Path(wx).exists() else {}
    g = D['grid'].item() if hasattr(D['grid'], 'item') else D['grid']
    assert abs(g['lon0'] + 180) < 1e-6 and abs(g['lat0'] - 90) < 1e-6 and abs(g['d'] - 0.5) < 1e-6, g
    S, H, Wd = P.shape
    def enc(a, f, lo=0):
        if a is None: return np.full((S, H, Wd), 255, np.uint8)
        v = np.round((np.asarray(a, np.float32) + lo) * f)
        return np.where(np.isfinite(v), np.clip(v, 0, 254), 255).astype(np.uint8)
    wind = np.hypot(W['U'], W['V']) if W.get('U') is not None else None
    cube = np.stack([enc(P, 2.5), enc(W.get('T'), 2, 60), enc(W.get('C'), 250), enc(wind, 5), np.asarray(D['amt'], np.uint8)], 1)  # S, 5, H, W
    pt = out / 'pt'; pt.mkdir(parents=True, exist_ok=True)
    n = 0
    boxes = []  # land only: tiles that touch a country
    for f in ('geo_prob.json', 'geo_world.json'):
        for c in json.load(open(HERE / f))['countries'].values():
            for r in c['rings']:
                a_ = np.array(r); boxes.append((a_[:, 0].min(), a_[:, 0].max(), a_[:, 1].min(), a_[:, 1].max()))
    land = lambda l, t: any(b[0] <= l + TILE and b[1] >= l and b[2] <= t and b[3] >= t - TILE for b in boxes)
    for top in range(80, -60, -TILE):
        rows = [int(round((90 - top) / 0.5)) + i for i in range(N)]
        for left in range(-180, 180, TILE):
            if not land(left, top): continue
            cols = [(int(round((left + 180) / 0.5)) + i) % Wd for i in range(N)]
            cube[:, :, rows][:, :, :, cols].tofile(pt / f'{top}_{left}.bin'); n += 1
    json.dump({'run': D['run'], 'steps': [int(s) for s in D['steps']], 'win': [int(x) for x in D['win']], 'tile': TILE, 'n': N, 'd': 0.5,
               'vars': ['P', 'T', 'C', 'W', 'A'], 'models': models, 'built': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%dT%H:%M:00Z')}, open(pt / 'index.json', 'w'))
    # towns for the text search (both boundary packs, without duplicates)
    seen, places = set(), []
    for f in ('geo_prob.json', 'geo_world.json'):
        for p in json.load(open(HERE / f))['places']:
            k = (p['en'], p['iso'])
            if k in seen: continue
            seen.add(k)
            places.append([p['ru'], UZ_CITY.get(p['en'], ''), p['en'], p.get('tr') or '', p['iso'], round(p['lat'], 3), round(p['lon'], 3), int(p['pop']), int(p.get('cap') or 0)])
    places.sort(key=lambda r: -r[7])
    json.dump(places, open(out / 'places.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    print('points:', n, 'tiles,', len(places), 'places')
    if len(sys.argv) > 4 and pathlib.Path(sys.argv[4]).exists(): regional(sys.argv[4], wx, out)


def regional(npz, wx, out, tile=5):
    """0.25° tiles over the regional grid (CIS and Turkey): the bot and the site use them first, the 0.5° world tiles elsewhere."""
    D = Rn.load(npz); P, models, _ = Rn.probability(D)
    W = Rn.load_wx_npz(D, wx) if wx and pathlib.Path(wx).exists() else {}
    g = D['grid'].item() if hasattr(D['grid'], 'item') else D['grid']; d = g['d']; S, H, Wd = P.shape
    def enc(a, f, lo=0):
        if a is None: return np.full((S, H, Wd), 255, np.uint8)
        v = np.round((np.asarray(a, np.float32) + lo) * f)
        return np.where(np.isfinite(v), np.clip(v, 0, 254), 255).astype(np.uint8)
    gf = Rn.gaussian_filter  # the same smoothing as the maps and city texts (render.Region), so the numbers are identical
    sm = lambda a, sg: None if a is None else np.stack([gf(np.nan_to_num(a[s]), sg) for s in range(S)])
    T = None
    if W.get('T') is not None:
        T = np.stack([gf(np.nan_to_num(W['T'][s], nan=99), 1.5) for s in range(S)]); T[np.isnan(W['T'])] = np.nan
    wind = np.hypot(sm(W['U'], 1.0), sm(W['V'], 1.0)) if W.get('U') is not None else None
    cube = np.stack([enc(P, 2.5), enc(T, 2, 60), enc(sm(W.get('C'), 1.0), 250), enc(wind, 5), np.asarray(D['amt'], np.uint8)], 1)
    boxes = []
    for c in json.load(open(HERE / 'geo_prob.json'))['countries'].values():
        for r in c['rings']:
            a_ = np.array(r); boxes.append((a_[:, 0].min(), a_[:, 0].max(), a_[:, 1].min(), a_[:, 1].max()))
    land = lambda l, t: any(b[0] <= l + tile and b[1] >= l and b[2] <= t and b[3] >= t - tile for b in boxes)
    pt = out / 'pt25'; pt.mkdir(parents=True, exist_ok=True); n = 0
    lon0, lat0 = g['lon0'], g['lat0']; lon1, lat1 = lon0 + (Wd - 1) * d, lat0 - (H - 1) * d
    top0 = int(np.floor(lat0 / tile) * tile)
    for top in range(top0, int(lat1) - 1, -tile):
        if top - tile < lat1 or top > lat0: continue
        for left in range(int(np.ceil(lon0 / tile) * tile), int(lon1) - tile + 1, tile):
            if not land(left, top): continue
            r0, c0 = int(round((lat0 - top) / d)), int(round((left - lon0) / d))
            cube[:, :, r0:r0 + N, c0:c0 + N].tofile(pt / f'{top}_{left}.bin'); n += 1
    json.dump({'run': D['run'], 'steps': [int(s) for s in D['steps']], 'win': [int(x) for x in D['win']], 'tile': tile, 'n': N, 'd': d,
               'box': [lon0, lon1, lat1, lat0], 'vars': ['P', 'T', 'C', 'W', 'A'], 'models': models,
               'built': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%dT%H:%M:00Z')}, open(pt / 'index.json', 'w'))
    print('points 0.25°:', n, 'tiles')


if __name__ == '__main__':
    main()
