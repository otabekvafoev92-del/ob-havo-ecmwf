"""Point forecasts for the Telegram bot (location or a searched town anywhere in the world):
the 15-day multimodel windows on the 0.5° world grid, cut into 10° × 10° tiles of 21 × 21 points.
  out/pt/index.json            run, steps, windows, tile layout
  out/pt/<top>_<left>.bin      uint8 [window][var][21][21], var = P (% × 2.5), T ((°C + 60) × 2), C (fraction × 250),
                               W (wind m/s × 5), A (ensemble-mean amount, round(ln(1 + mm) × 40)); 255 = no data
  out/places.json              towns for the bot's text search: [ru, uz, en, tr, iso, lat, lon, pop]
Usage: python3 prob/points.py glob.npz wx.npz site/prob"""
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
               'vars': ['P', 'T', 'C', 'W', 'A'], 'models': models}, open(pt / 'index.json', 'w'))
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


if __name__ == '__main__':
    main()
