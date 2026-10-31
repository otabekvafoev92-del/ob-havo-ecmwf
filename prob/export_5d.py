"""Packs the 15-day multimodel forecast for the 3D globe's "5D" layer: one small RGB PNG per 6-hour window.
(no alpha channel: browsers would premultiply it away)
  R = precipitation probability (0–100 % → 0–250)   G = temperature ((°C + 60) × 2, −60…+67 °C)   B = cloud cover (0–1 → 0–250)
The globe raises the probability into relief, colours it rain/snow by temperature, floats clouds above and
blends between windows in time — lon, lat, height, time and colour: "5D".
Usage: python3 prob/export_5d.py prob.npz wx.npz site/prob/d5"""
import json, pathlib, sys
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import render as Rn


def main():
    npz, wx, out = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
    D = Rn.load(npz); P, models, members = Rn.probability(D)
    W = Rn.load_wx_npz(D, wx) if wx and pathlib.Path(wx).exists() else {'T': None, 'C': None}
    g = D['grid'].item() if hasattr(D['grid'], 'item') else D['grid']
    steps = [int(s) for s in D['steps']]
    for i, s in enumerate(steps):
        p = gaussian_filter(np.nan_to_num(P[i]).astype(np.float32), 0.8)
        T = W['T'][i] if W['T'] is not None else np.full_like(p, 10)
        C = W['C'][i] if W['C'] is not None else np.zeros_like(p)
        T = np.where(np.isfinite(T), T, 10); C = np.where(np.isfinite(C), C, 0)
        rgba = np.stack([np.clip(p * 2.5, 0, 250), np.clip((T + 60) * 2, 0, 255), np.clip(gaussian_filter(C, 0.8) * 250, 0, 250)], -1)
        Image.fromarray(np.round(rgba).astype(np.uint8), 'RGB').save(out / f's{s:03d}.png', optimize=True)
    json.dump({'run': D['run'], 'steps': steps, 'lon0': float(g['lon0']), 'lat0': float(g['lat0']), 'd': float(g['d']), 'W': int(g['W']), 'H': int(g['H']),
               'win': [int(x) for x in D['win']], 'models': models, 'members': members}, open(out / 'index.json', 'w'))
    print('5D', len(steps), 'windows →', out)


if __name__ == '__main__':
    main()
