"""Cut a forecast .npz (prob/fetch.py: prob.npz, wx.npz) to a box around Uzbekistan, so it is small enough for a branch.
Usage: python tools/crop_npz.py in.npz out.npz [lon0 lon1 lat0 lat1]"""
import sys, numpy as np
src, dst = sys.argv[1], sys.argv[2]; X0, X1, Y0, Y1 = (float(x) for x in (sys.argv[3:7] or (50, 80, 32, 49)))
z = np.load(src, allow_pickle=True); D = {k: z[k] for k in z.files}
g = D['grid'].item(); H, W, d = g['H'], g['W'], g['d']
lon = g['lon0'] + np.arange(W) * d; lat = g['lat0'] - np.arange(H) * d
ci = np.flatnonzero((lon >= X0) & (lon <= X1)); ri = np.flatnonzero((lat >= Y0) & (lat <= Y1))
for k, a in D.items():
    if isinstance(a, np.ndarray) and a.ndim >= 2 and a.shape[-2:] == (H, W): D[k] = a[..., ri[0]:ri[-1] + 1, ci[0]:ci[-1] + 1]
g = dict(g, lon0=float(lon[ci[0]]), lat0=float(lat[ri[0]]), W=len(ci), H=len(ri)); D['grid'] = np.array(g, dtype=object)
np.savez_compressed(dst, **D); print(dst, {k: getattr(v, 'shape', None) for k, v in D.items()})
