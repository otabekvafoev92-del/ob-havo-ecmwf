"""Renders precipitation-probability frames and MP4 videos for the CIS and Turkey.
Usage: python3 prob/render.py prob.npz out_dir [--regions cis,UZ,...] [--langs uz,ru,tr] [--fps 1.25]
Input (prob.npz, written by prob/fetch.py or tools/prob_from_browser.py):
  run (str ISO), steps (S,), grid lon0, lat0, d, W, H,
  ens_<name> (S,H,W) uint8 member counts with ≥0.2 mm, n_<name> (S,) members,
  det (S,H,W) uint8 bit flags of deterministic models with ≥0.2 mm, det_names, det_avail (S, ndet) bool,
  amt (S,H,W) uint8 ensemble-mean 6 h amount, q = round(ln(1+mm)·40)
"""
import json, sys, os, argparse, subprocess, datetime as dt, pathlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Polygon, Rectangle
from matplotlib.collections import PolyCollection, LineCollection
from pyproj import Proj
from scipy.ndimage import gaussian_filter

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from regions import REGIONS, ORDER, CIS, NAMES, UZ_CITY, OVERVIEW_TZ, T, CONT, CONT_ORDER

LEVELS = [10, 30, 50, 70, 90, 101]
COLORS = ['#c6e2f7', '#7fbdec', '#3b8de0', '#1658b8', '#0b2f73']        # rain
SNOW = ['#f1def4', '#e0b3ea', '#c682da', '#a052c2', '#6e2496']          # snow
CLOUD_LV, CLOUD_COL = [0.5, 0.8, 1.01], ['#e6e9ed', '#cdd2d8']           # cloud cover fraction (≥50 %, ≥80 %)
T_LV = list(range(-40, 44, 4))
T_COL = ['#3b0f70', '#4a2a9a', '#3e4fc0', '#3a72d8', '#4a94e6', '#69b3ee', '#93cdf2', '#bfe3f5', '#e3f2f2',   # −40…−4
         '#f2f0c8', '#f7e09a', '#f8c56c', '#f5a54a', '#ee8132', '#e05a24', '#c8381c', '#a51c1c', '#7f1018', '#5c0a14', '#40060d', '#2b040a']  # 0…+40
CL_LV, CL_COL = [10, 30, 50, 70, 90, 101], ['#eef1f4', '#d9dee4', '#bfc6cf', '#a3acb8', '#858f9c']
BAR_COLORS = ['#e9eef3'] + COLORS
SNOW_BAR = ['#f3eef5'] + SNOW
LABELS = ['10–30 %', '30–50 %', '50–70 %', '70–90 %', '90–100 %']
ENS_LABEL = {'ifs': 'ECMWF IFS ENS', 'aifs': 'ECMWF AIFS ENS', 'gefs': 'NOAA GEFS'}
DET_LABEL = {'hres': 'ECMWF IFS', 'aifss': 'ECMWF AIFS', 'gfs': 'NOAA GFS', 'icon': 'DWD ICON'}
INK, MUTED, BORDER = '#16202c', '#5b6876', '#9aa5b1'
def ISO_COL(v):  # isotherm colour: blue below zero, orange-red above
    if v < 0: return '#2b6cb0' if v > -15 else '#1e3a8a'
    if v == 0: return '#1d4ed8'
    return '#d97706' if v < 20 else '#c2410c'


def load(path):
    z = np.load(path, allow_pickle=True)
    D = {k: z[k] for k in z.files}
    D['run'] = str(D['run']); D['ens_names'] = [str(x) for x in D['ens_names']]; D['det_names'] = [str(x) for x in D['det_names']]
    if 'win' not in D:  # older files: windows were always 6 h
        st = [int(x) for x in D['steps']]; D['win'] = np.array([s - (st[i - 1] if i else 0) for i, s in enumerate(st)])
    return D


def hours_text(lang, h):
    h = int(h)
    if lang == 'ru': return f'{h} ' + ('час' if h % 10 == 1 and h % 100 != 11 else 'часа' if h % 10 in (2, 3, 4) and h % 100 not in (12, 13, 14) else 'часов')
    return f"{h} {'soat' if lang == 'uz' else 'saat'}"


def probability(D):
    """Equal weight per forecasting system: each ensemble, plus all deterministic models together."""
    if 'P' in D:  # already combined (browser demo)
        nm, dv = D['n_members'], D['det_avail']
        used = [ENS_LABEL[k] for i, k in enumerate(D['ens_names']) if nm[:, i].max() > 0] + [DET_LABEL[k] for i, k in enumerate(D['det_names']) if dv[:, i].any()]
        order = ['ECMWF IFS', 'ECMWF IFS ENS', 'ECMWF AIFS', 'ECMWF AIFS ENS', 'NOAA GFS', 'NOAA GEFS', 'DWD ICON']
        return D['P'].astype(np.float32), [m for m in order if m in used], int(nm.max(0).sum() + dv.any(0).sum())
    S, H, W = D['amt'].shape
    num = np.zeros((S, H, W), np.float32); den = np.zeros((S, 1, 1), np.float32)
    used = set(); members = 0
    for k in D['ens_names']:
        n = D['n_' + k].astype(np.float32)[:, None, None]
        ok = n > 0
        num += np.where(ok, D['ens_' + k] / np.maximum(n, 1), 0); den += ok
        if ok.any(): used.add(ENS_LABEL[k]); members = max(members, 0) + int(D['n_' + k].max())
    avail = D['det_avail'].astype(bool)  # (S, ndet)
    nd = avail.sum(1).astype(np.float32)
    if nd.max() > 0:
        bits = D['det']
        cnt = np.zeros((S, H, W), np.float32)
        for i, k in enumerate(D['det_names']):
            cnt += ((bits >> i) & 1) * avail[:, i][:, None, None]
            if avail[:, i].any(): used.add(DET_LABEL[k]); members += 1
        ok = (nd > 0)[:, None, None]
        num += np.where(ok, cnt / np.maximum(nd, 1)[:, None, None], 0); den += ok
    P = 100 * num / np.maximum(den, 1)
    order = ['ECMWF IFS', 'ECMWF IFS ENS', 'ECMWF AIFS', 'ECMWF AIFS ENS', 'NOAA GFS', 'NOAA GEFS', 'DWD ICON']
    return P, [m for m in order if m in used], members


def _unrle(s, n):
    import re
    out = np.zeros(n, np.uint8); p = 0
    for ch, num in re.findall(r'([A-Z])(\d*)', s):
        c = int(num) if num else 1; out[p:p + c] = ord(ch) - 65; p += c
    return out


def load_wx(D, data_dir):
    """Temperature (°C) and cloud density (0…1) for every 6-h window, on the probability grid.
    Source: the globe data built from charts.ecmwf.int (2 m temperature classes, simulated IR clouds)."""
    if not data_dir: return None
    import pathlib
    from PIL import Image
    data_dir = pathlib.Path(data_dir); F = json.load(open(data_dir / 'forecast.json'))
    grun = dt.datetime.fromisoformat(F['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    prun = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    gw, gh = F['global']['grid']['W'], F['global']['grid']['H']
    mids = np.array([(c['lo'] + c['hi']) / 2 for c in F['classes']['temp']], np.float32)
    TL = F['global']['layers']['temp']; tsteps = TL['steps']
    temps = {h: mids[_unrle(f, gw * gh)].reshape(gh, gw) for h, f in zip(tsteps, TL['frames']) if f}
    cl = F.get('clouds') or {}
    clouds = {}
    for h, f in zip(cl.get('steps', []), cl.get('g', [])):
        try: clouds[h] = np.asarray(Image.open(data_dir / f).convert('L'), np.float32) / 255
        except Exception: pass
    g = D['grid'].item() if hasattr(D['grid'], 'item') else D['grid']
    lon = g['lon0'] + np.arange(g['W']) * g['d']; lat = g['lat0'] - np.arange(g['H']) * g['d']
    LON, LAT = np.meshgrid(lon, lat)
    def sample(a, h):
        H, W = a.shape
        x = (((LON + 180) % 360) / 360) * W - 0.5; y = np.clip((90 - LAT) / 180 * H - 0.5, 0, H - 1.001)
        ix = np.floor(x).astype(int); iy = np.floor(y).astype(int); fx, fy = x - ix, y - iy
        ix0, ix1 = ix % W, (ix + 1) % W
        return (a[iy, ix0] * (1 - fx) + a[iy, ix1] * fx) * (1 - fy) + (a[iy + 1, ix0] * (1 - fx) + a[iy + 1, ix1] * fx) * fy
    S = len(D['steps']); T = np.full((S, g['H'], g['W']), np.nan, np.float32); C = np.full_like(T, np.nan)
    for i, st in enumerate(D['steps']):
        ends = [(prun + dt.timedelta(hours=int(st) - k) - grun).total_seconds() / 3600 for k in (6, 0)]
        ts = [sample(temps[int(h)], h) for h in ends if int(h) in temps]
        cs = [sample(clouds[int(h)], h) for h in ends if int(h) in clouds]
        if ts: T[i] = np.mean(ts, 0)
        if cs: C[i] = np.mean(cs, 0)
    return {'T': T, 'C': C}


def load_wx_npz(D, path):
    """wx.npz (prob/fetch.py or the browser collector): GEFS ensemble mean 2 m temperature (°C) and total cloud
    cover (%) every 6 h on a 0.5° grid; returns window means on the probability grid."""
    z = np.load(path, allow_pickle=True)
    g = D['grid'].item() if hasattr(D['grid'], 'item') else D['grid']; w = z['grid'].item()
    st = [int(x) for x in z['steps']]; Tw, Cw = z['T'].astype(np.float32), z['C'].astype(np.float32)
    lon = g['lon0'] + np.arange(g['W']) * g['d']; lat = g['lat0'] - np.arange(g['H']) * g['d']
    fx = (lon - w['lon0']) / w['d']; fy = (w['lat0'] - lat) / w['d']
    ix = np.clip(np.floor(fx).astype(int), 0, w['W'] - 2); iy = np.clip(np.floor(fy).astype(int), 0, w['H'] - 2)
    ax_, ay_ = (fx - ix)[None, :], (fy - iy)[:, None]
    def up(a): return (a[iy][:, ix] * (1 - ax_) + a[iy][:, ix + 1] * ax_) * (1 - ay_) + (a[iy + 1][:, ix] * (1 - ax_) + a[iy + 1][:, ix + 1] * ax_) * ay_
    S = len(D['steps']); T = np.full((S, g['H'], g['W']), np.nan, np.float32); C = np.full_like(T, np.nan)
    for i, s_ in enumerate(D['steps']):
        s_ = int(s_)
        w_ = int(D['win'][i]) if 'win' in D else 6
        a = [st.index(h) for h in (s_ - w_, s_) if h in st]
        if a: T[i] = up(np.nanmean([Tw[k] for k in a], 0))
        if s_ in st and np.isfinite(Cw[st.index(s_)]).any(): C[i] = up(Cw[st.index(s_)]) / 100  # GEFS cloud cover is already a 6-h mean
    return {'T': T, 'C': C}


class Geo:
    def __init__(self, path=None):
        g = json.load(open(path or HERE / 'geo_prob.json'))
        self.countries, self.admin1, self.places = g['countries'], g['admin1'], g['places']


def city_name(p, lang):
    if lang == 'ru': return p['ru']
    if lang == 'uz': return UZ_CITY.get(p['en'], p['en'])
    return p['tr'] or p['en']


def pick_cities(geo, region, n):
    if region in CONT:  # continent / world: capitals and the biggest cities, spread out
        lon0, lon1, lat0, lat1 = CONT[region][:4]; mains = set(CONT[region][7].values())
        cand = [p for p in geo.places if lon0 <= p['lon'] <= lon1 and lat0 <= p['lat'] <= lat1]
        cand.sort(key=lambda p: (p['en'] not in mains, -(p['pop'] + (3_000_000 if p['cap'] == 2 else 0))))
        out, gap = [], (lon1 - lon0) / 11
        for p in cand:
            if len(out) >= n: break
            if all(abs(p['lon'] - q['lon']) * max(0.4, np.cos(np.radians(p['lat']))) + abs(p['lat'] - q['lat']) > gap for q in out): out.append(p)
        return out
    iso = REGIONS[region][0]
    if iso is None:  # overview: capitals
        caps = [p for p in geo.places if p['cap'] == 2 and p['iso'] in CIS]
        seen, out = set(), []
        for p in caps:
            if p['iso'] not in seen: seen.add(p['iso']); out.append(p)
        for extra in ('Saint Petersburg', 'Novosibirsk', 'Yekaterinburg', 'Krasnoyarsk', 'Irkutsk', 'Khabarovsk', 'Yakutsk', 'Istanbul', 'Almaty'):
            out += [p for p in geo.places if p['en'] == extra][:1]
        return out
    cand = [p for p in geo.places if p['iso'] == iso]
    cand.sort(key=lambda p: (-p['cap'] if p['cap'] == 2 else 0, -p['pop']))
    out = []
    for p in cand:
        if len(out) >= n: break
        if all(abs(p['lon'] - q['lon']) * np.cos(np.radians(p['lat'])) + abs(p['lat'] - q['lat']) > (REGIONS[region][2] - REGIONS[region][1]) / 14 for q in out):
            out.append(p)
    return out


def tz_label(lang, region, off):
    named = {('uz', 'UZ'), ('uz', 'cis'), ('ru', 'RU'), ('ru', 'cis'), ('ru', 'BY'), ('tr', 'TR'), ('tr', 'cis')}
    if (lang, region) in named and off in T[lang]['tz']: return T[lang]['tz'][off]
    return T[lang]['utc'].format(o=off)


def window_text(lang, region, run, step, off, win=6):
    t1 = run + dt.timedelta(hours=int(step) - int(win) + off); t2 = run + dt.timedelta(hours=int(step) + off)
    f = lambda t: t.strftime('%d.%m')
    tz = tz_label(lang, region, off)
    if t1.date() == t2.date() or t2.hour == 0 and (t2 - t1).seconds == int(win) * 3600 and t1.date() == (t2 - dt.timedelta(minutes=1)).date():
        h2 = t2.hour if t2.hour else 24
        return T[lang]['window'].format(d1=f(t1), h1=f'{t1.hour:02d}', h2=f'{h2:02d}', tz=tz)
    return T[lang]['window2'].format(d1=f(t1), h1=f'{t1.hour:02d}', d2=f(t2), h2=f'{t2.hour:02d}', tz=tz)


class Region:
    def __init__(self, D, geo, region, P, amt):
        self.cont = region in CONT
        if self.cont:
            lon0, lon1, lat0, lat1, clon, clat, off, mains = CONT[region]; iso, cap = None, None
        else:
            iso, lon0, lon1, lat0, lat1, clon, off, cap = REGIONS[region]
        self.id, self.iso, self.off, self.cap = region, iso, off, cap
        g = D['grid'].item() if hasattr(D['grid'], 'item') else D['grid']
        glon0, glat0, d, W, H = g['lon0'], g['lat0'], g['d'], g['W'], g['H']
        m = 14 if self.cont and region != 'world' else 1.5  # azimuthal continent maps reach past their lon/lat box at the corners
        x0 = max(0, int((lon0 - m - glon0) / d)); x1 = min(W, int((lon1 + m - glon0) / d) + 2)
        y0 = max(0, int((glat0 - lat1 - m) / d)); y1 = min(H, int((glat0 - lat0 + m) / d) + 2)
        lons = glon0 + np.arange(x0, x1) * d; lats = glat0 - np.arange(y0, y1) * d
        self.LON, self.LAT = np.meshgrid(lons, lats)
        lat_1, lat_2 = lat0 + (lat1 - lat0) / 6, lat1 - (lat1 - lat0) / 6
        if region == 'world': self.proj = Proj(proj='robin', lon_0=clon, ellps='WGS84')
        elif self.cont: self.proj = Proj(proj='laea', lat_0=clat, lon_0=clon, ellps='WGS84')
        else: self.proj = Proj(proj='lcc', lat_1=lat_1, lat_2=lat_2, lat_0=(lat0 + lat1) / 2, lon_0=clon, ellps='WGS84')
        self.X, self.Y = self.proj(self.LON, self.LAT)
        sigma = 0.6 if self.cont else 0.8 if region in ('cis', 'RU') else 1.2
        self.P = np.stack([gaussian_filter(P[s, y0:y1, x0:x1], sigma) for s in range(P.shape[0])])
        self.A = np.expm1(amt[:, y0:y1, x0:x1] / 40.0)
        self.Araw = self.A
        self.Asm = np.stack([gaussian_filter(self.A[s], sigma) for s in range(P.shape[0])])
        wx = _CTX.get('wx')
        if wx is not None:
            self.T = np.stack([gaussian_filter(np.nan_to_num(wx['T'][s, y0:y1, x0:x1], nan=99), 1.5) for s in range(P.shape[0])])
            self.T[np.stack([np.isnan(wx['T'][s, y0:y1, x0:x1]) for s in range(P.shape[0])])] = np.nan
            self.C = np.stack([gaussian_filter(np.nan_to_num(wx['C'][s, y0:y1, x0:x1]), 1.0) for s in range(P.shape[0])])
        else:
            self.T = self.C = None
        # map extent: projected bounding box of the lon/lat box
        bl = np.linspace(lon0, lon1, 60); bb = np.linspace(lat0, lat1, 40)
        ex, ey = self.proj(np.r_[bl, np.full(40, lon1), bl[::-1], np.full(40, lon0)], np.r_[np.full(60, lat0), bb, np.full(60, lat1), bb[::-1]])
        self.ext = (ex.min(), ex.max(), ey.min(), ey.max())
        if region in ('cis', 'RU'):  # trim the empty corners of wide conic maps
            xs, ys = self.proj(np.r_[bl, bl], np.r_[np.full(60, lat0 + 2), np.full(60, lat1)])
            self.ext = (xs.min(), xs.max(), min(ys), max(ys))
        self.geo = geo
        self.cities = pick_cities(geo, region, 14 if region == 'world' else 12 if self.cont else 9 if region not in ('cis', 'RU', 'KZ') else 12)
        # pre-project boundaries
        self.cpoly = {}
        for c, info in geo.countries.items():
            rings = []
            for r in info['rings']:
                a = np.array(r)
                if a[:, 0].max() < lon0 - 25 or a[:, 0].min() > lon1 + 25 or a[:, 1].max() < lat0 - 15 or a[:, 1].min() > lat1 + 15: continue
                x, y = self.proj(a[:, 0], a[:, 1]); rings.append(np.c_[x, y])
            if rings: self.cpoly[c] = rings
        self.a1 = []
        if iso and iso in geo.admin1:
            for r in geo.admin1[iso]:
                a = np.array(r); x, y = self.proj(a[:, 0], a[:, 1]); self.a1.append(np.c_[x, y])
        self.cxy = [self.proj(p['lon'], p['lat']) for p in self.cities]
        # country mask on the data grid (for "share of the territory" in the daily comments)
        from matplotlib.path import Path as MPath
        self.mask = None
        rings = [] if self.cont else geo.countries.get(iso, {}).get('rings', []) if iso else [r for c in CIS for r in geo.countries.get(c, {}).get('rings', [])]
        if rings:
            pts = np.c_[self.LON.ravel(), self.LAT.ravel()]; m = np.zeros(len(pts), bool)
            for r in rings:
                a = np.array(r)
                if len(a) > 2: m |= MPath(a).contains_points(pts)
            self.mask = m.reshape(self.LON.shape)
        # time series at the main city
        self.Pfull = P[:, y0:y1, x0:x1]
        self.mains = {}
        for lang in ('uz', 'ru', 'tr'):
            want = mains[lang] if self.cont else cap if region != 'cis' else {'uz': 'Tashkent', 'ru': 'Moscow', 'tr': 'Istanbul'}[lang]
            self.mains[lang] = next((p for p in self.cities if p['en'] == want), self.cities[0] if self.cities else None)
        self.main = self.mains['uz']

    def series(self, p):
        g0, d = (self.LON[0, 0], self.LAT[0, 0]), self.LON[0, 1] - self.LON[0, 0]
        gx, gy = (p['lon'] - g0[0]) / d, (g0[1] - p['lat']) / d
        return np.array([bilinear(self.Pfull[s], gx, gy) for s in range(self.Pfull.shape[0])])

    def _xy(self, p):
        g0, d = (self.LON[0, 0], self.LAT[0, 0]), self.LON[0, 1] - self.LON[0, 0]
        return (p['lon'] - g0[0]) / d, (g0[1] - p['lat']) / d

    def cseries(self, p):
        if self.C is None: return None
        gx, gy = self._xy(p); return np.array([bilinear(self.C[s], gx, gy) for s in range(self.C.shape[0])])

    def aseries(self, p):
        gx, gy = self._xy(p); return np.array([bilinear(self.A[s], gx, gy) for s in range(self.A.shape[0])])

    def area_share(self, idx):
        """Share of the focus country where the 6-h probability exceeds 50 % at least once in these windows."""
        if self.mask is None or not self.mask.any(): return None
        m = np.max(self.Pfull[idx], 0) >= 50
        return float((m & self.mask).sum() / self.mask.sum())

    def tseries(self, p):
        if self.T is None: return None
        g0, d = (self.LON[0, 0], self.LAT[0, 0]), self.LON[0, 1] - self.LON[0, 0]
        gx, gy = (p['lon'] - g0[0]) / d, (g0[1] - p['lat']) / d
        return np.array([bilinear(self.T[s], gx, gy) for s in range(self.T.shape[0])])

    def value_at(self, s, p, field='P'):
        g = self.LON[0, 0], self.LAT[0, 0]
        d = self.LON[0, 1] - self.LON[0, 0]
        F = getattr(self, field)
        return bilinear(F[s], (p['lon'] - g[0]) / d, (g[1] - p['lat']) / d)


def bilinear(a, x, y):
    H, W = a.shape
    x = min(max(x, 0), W - 1.001); y = min(max(y, 0), H - 1.001)
    i, j = int(x), int(y); fx, fy = x - i, y - j
    return a[j, i] * (1 - fx) * (1 - fy) + a[j, i + 1] * fx * (1 - fy) + a[j + 1, i] * (1 - fx) * fy + a[j + 1, i + 1] * fx * fy


def local_day(run, step, off, win=6):
    """Local calendar day of a window (by its middle)."""
    return (run + dt.timedelta(hours=int(step) - int(win) / 2 + off)).date()


def fmt_t(v): return f'{v:+.0f}°'.replace('+0°', '0°').replace('-0°', '0°')


def daily_comments(R, D, lang, off, p=None, area=True):
    """One short comment per local day for a city (default: the region's main city; with the share of the country with rain)."""
    run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    L = T[lang]; p = p or R.mains[lang]
    if p is None: return {}
    P = R.series(p); Tm = R.tseries(p); Cm = R.cseries(p); A = R.aseries(p)
    days = {}
    for i, st in enumerate(D['steps']):
        days.setdefault(local_day(run, st, off, D['win'][i]), []).append(i)
    out = {}
    for d_, idx in days.items():
        pm = float(np.nanmax(P[idx])); mm = float(np.nansum(A[idx]))
        snow = Tm is not None and np.isfinite(Tm[idx]).any() and np.nanmin(Tm[idx]) <= 0.5 and pm >= 30
        t = ''
        if Tm is not None and np.isfinite(Tm[idx]).any():
            t = f"{fmt_t(np.nanmin(Tm[idx]))}…{fmt_t(np.nanmax(Tm[idx]))}"
        c = float(np.nanmean(Cm[idx])) if Cm is not None and np.isfinite(Cm[idx]).any() else None
        area_ = R.area_share(idx) if area else None
        out[d_.isoformat()] = make_comment(lang, city_name(p, lang), pm, mm, snow, t, c, area_, NAMES[R.id][lang])
    return out


def make_comment(lang, city, pm, mm, snow, t, c, area, region):
    sky = None
    if c is not None:
        sky = {'uz': ['ochiq havo', 'qisman bulutli', 'bulutli', 'qalin bulutli'], 'ru': ['ясно', 'переменная облачность', 'облачно', 'пасмурно'],
               'tr': ['açık', 'parçalı bulutlu', 'bulutlu', 'kapalı']}[lang][0 if c < 0.25 else 1 if c < 0.55 else 2 if c < 0.8 else 3]
    kind = {'uz': ('qor', 'yomg‘ir'), 'ru': ('снег', 'дождь'), 'tr': ('kar', 'yağmur')}[lang][0 if snow else 1]
    if pm < 20: rain = {'uz': 'yog‘in kutilmaydi', 'ru': 'без осадков', 'tr': 'yağış beklenmiyor'}[lang]
    elif pm < 50: rain = {'uz': f'{kind} ehtimoli past ({pm:.0f} %)', 'ru': f'{kind} маловероятен ({pm:.0f} %)', 'tr': f'{kind} olasılığı düşük (%{pm:.0f})'}[lang]
    elif pm < 75: rain = {'uz': f'{kind} bo‘lishi mumkin ({pm:.0f} %)', 'ru': f'возможен {kind} ({pm:.0f} %)', 'tr': f'{kind} olabilir (%{pm:.0f})'}[lang]
    else: rain = {'uz': f'{kind} kutiladi ({pm:.0f} %)', 'ru': f'ожидается {kind} ({pm:.0f} %)', 'tr': f'{kind} bekleniyor (%{pm:.0f})'}[lang]
    if pm >= 50 and mm >= 1: rain += {'uz': f', ~{mm:.0f} mm', 'ru': f', ~{mm:.0f} мм', 'tr': f', ~{mm:.0f} mm'}[lang]
    parts = [f'{city}: {t}' if t else city, rain] + ([sky] if sky else [])
    txt = ', '.join(parts)
    if area is not None and area >= 0.15:
        txt += {'uz': f'. {region} hududining {area*100:.0f} % qismida yog‘in ehtimoli 50 % dan yuqori',
                'ru': f'. На {area*100:.0f} % территории ({region}) вероятность осадков выше 50 %',
                'tr': f'. {region} alanının %{area*100:.0f} kadarında yağış olasılığı %50 üzerinde'}[lang]
    return txt + '.'


def _header(fig, R, D, s, lang, title):
    run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    step = int(D['steps'][s]); off = R.off if R.off is not None else OVERVIEW_TZ[lang]; L = T[lang]
    fig.text(0.04, 0.955, f"{title} · {NAMES[R.id][lang]}", fontsize=21, fontweight='bold', color=INK, va='center')
    fig.text(0.04, 0.915, window_text(lang, R.id, run, step, off, D['win'][s]), fontsize=19, color='#1a3e8c', fontweight='bold', va='center')
    fig.text(0.96, 0.955, 'Osmon · multimodel', fontsize=11, color=MUTED, ha='right', va='center')
    fig.text(0.96, 0.925, L['run'].format(run=run.strftime('%d.%m.%Y %H:%M')), fontsize=10.5, color=MUTED, ha='right', va='center')
    fig.text(0.96, 0.898, 'ECMWF (CC BY 4.0), NOAA, DWD · Natural Earth', fontsize=8, color='#9aa5b1', ha='right', va='center')
    return run, step, off


def _basemap(fig, R):
    ax = fig.add_axes([0.02, 0.27, 0.96, 0.62])
    x0, x1, y0, y1 = R.ext
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal', adjustable='box'); ax.axis('off')
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor='#f4f7fa', edgecolor='none', zorder=0))
    ax.add_collection(PolyCollection([r for rings in R.cpoly.values() for r in rings], facecolor='#ffffff', edgecolor='none', zorder=1))
    return ax


def _borders(ax, R):
    x0, x1, y0, y1 = R.ext
    if R.iso:
        ax.add_collection(PolyCollection([r for c, rings in R.cpoly.items() if c != R.iso for r in rings], facecolor=(1, 1, 1, 0.42), edgecolor='none', zorder=4))
        ax.add_collection(LineCollection(R.a1, colors='#8492a1', linewidths=0.45, zorder=5))
    ax.add_collection(LineCollection([r for c, rings in R.cpoly.items() if c != R.iso for r in rings], colors=BORDER, linewidths=0.6, zorder=5))
    focus = [] if R.cont else [R.iso] if R.iso else [c for c in CIS if c in R.cpoly]
    ax.add_collection(LineCollection([r for c in focus for r in R.cpoly.get(c, [])], colors=INK, linewidths=1.4 if R.iso else 0.9, zorder=6))
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor='none', edgecolor='#c4ccd5', linewidth=0.8, zorder=9))


def _cities(fig, ax, R, label):
    x0, x1, y0, y1 = R.ext
    fig.canvas.draw(); placed = []; axb = ax.get_window_extent()
    for p, (cx, cy) in sorted(zip(R.cities, R.cxy), key=lambda t: t[0] is not R.main):
        if not (x0 < cx < x1 and y0 < cy < y1): continue
        main = p is R.main; txt = label(p, main)
        fs = 15 if main else 10.5
        px, py = ax.transData.transform((cx, cy)); w, h = len(txt) * fs * 0.62 + 10, fs * 1.55 + 6
        spot = None
        for dx, dy, ha, va in ((8, 5, 'left', 'bottom'), (8, -5, 'left', 'top'), (-8, 5, 'right', 'bottom'), (-8, -5, 'right', 'top')):
            bx0 = px + (dx if ha == 'left' else dx - w); by0 = py + (dy if va == 'bottom' else dy - h); box_ = (bx0, by0, bx0 + w, by0 + h)
            inside = box_[0] > axb.x0 + 2 and box_[2] < axb.x1 - 2 and box_[1] > axb.y0 + 2 and box_[3] < axb.y1 - 2
            if inside and all(box_[2] < b[0] or box_[0] > b[2] or box_[3] < b[1] or box_[1] > b[3] for b in placed): spot = (dx, dy, ha, va, box_); break
        ax.plot(cx, cy, 'o', ms=6.5 if main else 4, mfc='white' if main else INK, mec=INK, mew=1.5, zorder=10)
        if spot is None: continue
        dx, dy, ha, va, box_ = spot; placed.append(box_)
        ax.annotate(txt, (cx, cy), xytext=(dx, dy), textcoords='offset points', fontsize=fs, ha=ha, va=va, fontweight='bold' if main else 'semibold', color=INK,
                    zorder=12 if main else 11, bbox=dict(boxstyle='round,pad=0.35' if main else 'round,pad=0.18', fc='white', ec=INK if main else 'none', lw=1.2, alpha=0.96 if main else 0.82))


def _swatches(fig, y, x, cols, labels, step=0.094, edge='#7a8794'):
    for i, (c, lab) in enumerate(zip(cols, labels)):
        fig.patches.append(Rectangle((x + i * step, y - 0.008), 0.022, 0.016, transform=fig.transFigure, facecolor=c, edgecolor=edge, lw=0.5))
        fig.text(x + 0.026 + i * step, y, lab, fontsize=9.6, color=INK, va='center')


def _timeline(fig, R, D, s, run, off, values, colors, ylim, yfmt, title, line=None):
    bx = fig.add_axes([0.06, 0.075, 0.88, 0.075])
    st_ = np.array([int(x) for x in D['steps']], float); wn = np.array([int(x) for x in D['win']], float)
    X = st_ - wn / 2  # middle of each window, hours from the run
    if values is not None: bx.bar(X, values, width=wn * 0.82, color=colors, zorder=2)
    bx.bar([X[s]], [ylim[1] - ylim[0]], bottom=ylim[0], width=wn[s] * 0.95, fill=False, edgecolor=INK, lw=1.6, zorder=3)
    bx.set_ylim(*ylim); bx.set_xlim(st_[0] - wn[0] - 1, st_[-1] + 1)
    bx.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(yfmt)); bx.tick_params(labelsize=8.5, colors=MUTED, length=0)
    ticks, labs = [], []
    t0 = run + dt.timedelta(hours=off); first = (t0 + dt.timedelta(days=1)).replace(hour=0, minute=0)
    if t0.hour == 0: first = t0
    k = first
    while (k - t0).total_seconds() / 3600 <= st_[-1]:
        ticks.append((k - t0).total_seconds() / 3600); labs.append(k.strftime('%d.%m')); k += dt.timedelta(days=1)
    bx.set_xticks(ticks); bx.set_xticklabels(labs, fontsize=8.5, color=MUTED)
    for tk in ticks: bx.axvline(tk, color='#e3e8ee', lw=0.8, zorder=1)
    for sp in ('top', 'right'): bx.spines[sp].set_visible(False)
    for sp in ('left', 'bottom'): bx.spines[sp].set_color('#c4ccd5')
    if line is not None and np.isfinite(line[0]).any():
        ys, col, fmt = line
        tx = bx if values is None else bx.twinx()
        tx.plot(X, ys, color=col, lw=1.5, zorder=4); tx.plot([X[s]], [ys[s]], 'o', ms=4.5, color=col, zorder=5)
        if tx is not bx:
            lo, hi = np.nanmin(ys), np.nanmax(ys); pad = max(2, (hi - lo) * 0.15); tx.set_ylim(lo - pad, hi + pad)
            tx.tick_params(length=0, labelsize=8.5, colors=col); tx.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(fmt))
            for sp in tx.spines.values(): sp.set_visible(False)
    bx.set_title(title, fontsize=10.5, color=INK, loc='left', pad=4)


def draw_frame(R, D, s, lang, models, members, path, product='prob', comment='', main=None):
    L = T[lang]; R.main = main if main is not None else R.mains[lang]
    fig = plt.figure(figsize=(12.8, 10.0), dpi=100); fig.patch.set_facecolor('white')
    title = {'prob': L['title'], 'temp': L['title_temp'], 'cloud': L['title_cloud']}[product]
    run, step, off = _header(fig, R, D, s, lang, title)
    ax = _basemap(fig, R)
    has_t = R.T is not None and np.isfinite(R.T[s]).any(); has_c = R.C is not None and np.isfinite(R.C[s]).any()
    if product == 'prob':
        if has_c: ax.contourf(R.X, R.Y, np.nan_to_num(R.C[s]), levels=CLOUD_LV, colors=CLOUD_COL, zorder=1.5, antialiased=True)
        snow = np.nan_to_num(R.T[s] <= 0.5).astype(bool) if has_t else np.zeros_like(R.P[s], bool)
        Pr, Ps = np.where(snow, 0, R.P[s]), np.where(snow, R.P[s], 0)
        ax.contourf(R.X, R.Y, Pr, levels=LEVELS, cmap=ListedColormap(COLORS), norm=BoundaryNorm(LEVELS, 5), zorder=2, antialiased=True)
        if Ps.max() >= LEVELS[0]: ax.contourf(R.X, R.Y, Ps, levels=LEVELS, cmap=ListedColormap(SNOW), norm=BoundaryNorm(LEVELS, 5), zorder=2.1, antialiased=True)
        if (R.Asm[s] >= 5).any(): ax.contour(R.X, R.Y, R.Asm[s], levels=[5], colors=['#5b1f8f'], linewidths=1.1, linestyles='--', zorder=3)
        if has_t:
            lv = [0] if R.id in ('cis', 'RU') or R.cont else list(range(-30, 45, 5))
            cs = ax.contour(R.X, R.Y, np.ma.masked_invalid(R.T[s]), levels=lv, colors=[ISO_COL(v) for v in lv], linewidths=[1.6 if v == 0 else 0.7 for v in lv], zorder=3.2, alpha=0.9)
            if R.id not in ('cis', 'RU') and not R.cont: ax.clabel(cs, fmt=fmt_t, fontsize=8, inline=True, inline_spacing=2)
    elif product == 'temp' and has_t:
        Tm = np.ma.masked_invalid(R.T[s])
        ax.contourf(R.X, R.Y, Tm, levels=T_LV, colors=T_COL[:len(T_LV) - 1], extend='both', zorder=2, antialiased=True, alpha=0.92)
        lv = list(range(-40, 45, 4))
        cs = ax.contour(R.X, R.Y, Tm, levels=lv, colors=['#1d4ed8' if v == 0 else '#4b5563' for v in lv], linewidths=[1.5 if v == 0 else 0.35 for v in lv], zorder=3, alpha=0.8)
        ax.clabel(cs, levels=[v for v in lv if v % 8 == 0], fmt=fmt_t, fontsize=8, inline=True)
    elif product == 'cloud' and has_c:
        ax.contourf(R.X, R.Y, np.nan_to_num(R.C[s]) * 100, levels=CL_LV, colors=CL_COL, zorder=2, antialiased=True)
        ax.contour(R.X, R.Y, R.P[s], levels=[50], colors=['#1658b8'], linewidths=1.2, linestyles='--', zorder=3)
    _borders(ax, R)
    def label(p, main):
        v = R.value_at(s, p); t = R.value_at(s, p, 'T') if has_t else np.nan
        if product == 'temp': return f"{city_name(p, lang)} {fmt_t(t)}" if np.isfinite(t) else city_name(p, lang)
        if product == 'cloud': return f"{city_name(p, lang)} {R.value_at(s, p, 'C') * 100:.0f} %" if has_c else city_name(p, lang)
        txt = f"{city_name(p, lang)} {int(round(max(0, min(100, v))))} %"
        if np.isfinite(t): txt += f" · {fmt_t(t)}" + (' ❄' if t <= 0.5 and v >= 30 else '')
        mm = R.value_at(s, p, 'Araw')
        if main and mm >= 0.5: txt += f" · ≈{mm:.0f} mm" if mm >= 1.5 else f" · ≈{mm:.1f} mm"
        return txt
    _cities(fig, ax, R, label)
    # legend
    if product == 'prob':
        fig.text(0.04, 0.25, L['legend'].format(h=hours_text(lang, D['win'][s])) + ':', fontsize=11.5, color=INK, va='center')
        for pal, name, y in ((COLORS, L['rain'], 0.226), (SNOW, L['snow'], 0.201)):
            fig.text(0.04, y, name, fontsize=10.5, color=INK, va='center', fontweight='bold'); _swatches(fig, y, 0.115, pal, LABELS)
        xr = 0.62
        for i, (c, lab) in enumerate(zip(CLOUD_COL, L['clouds'])):
            fig.patches.append(Rectangle((xr + i * 0.15, 0.243), 0.022, 0.016, transform=fig.transFigure, facecolor=c, edgecolor='#9aa5b1', lw=0.5))
            fig.text(xr + 0.027 + i * 0.15, 0.251, lab, fontsize=9.6, color=INK, va='center')
        fig.add_artist(matplotlib.lines.Line2D([xr, xr + 0.022], [0.226, 0.226], color='#d97706', lw=1.0, transform=fig.transFigure))
        fig.add_artist(matplotlib.lines.Line2D([xr + 0.024, xr + 0.046], [0.226, 0.226], color='#1d4ed8', lw=1.8, transform=fig.transFigure))
        fig.text(xr + 0.051, 0.226, L['iso'], fontsize=9.6, color=INK, va='center')
        fig.add_artist(matplotlib.lines.Line2D([xr, xr + 0.046], [0.201, 0.201], color='#5b1f8f', lw=1.3, ls='--', transform=fig.transFigure))
        fig.text(xr + 0.051, 0.201, L['heavy'].format(h=hours_text(lang, D['win'][s])), fontsize=9.6, color=INK, va='center')
        fig.text(0.04, 0.176, L['models'].format(m=', '.join(models)) + ' · ' + L['method'].format(n=members), fontsize=9, color=MUTED, va='center')
    elif product == 'temp':
        fig.text(0.04, 0.25, L['legend_temp'].format(h=hours_text(lang, D['win'][s])) + ':', fontsize=11.5, color=INK, va='center')
        cb = fig.add_axes([0.04, 0.218, 0.92, 0.018])
        cb.imshow([np.arange(len(T_COL) - 0)], cmap=ListedColormap(T_COL), aspect='auto', extent=(T_LV[0] - 4, T_LV[-1], 0, 1))
        cb.set_yticks([]); cb.set_xticks(list(range(-40, 41, 8))); cb.set_xticklabels([fmt_t(v) for v in range(-40, 41, 8)], fontsize=8.5, color=MUTED)
        for sp in cb.spines.values(): sp.set_visible(False)
        fig.text(0.04, 0.176, L['src_wx'], fontsize=9, color=MUTED, va='center')
    else:
        fig.text(0.04, 0.25, L['legend_cloud'] + ':', fontsize=11.5, color=INK, va='center')
        _swatches(fig, 0.222, 0.04, CL_COL, ['10–30 %', '30–50 %', '50–70 %', '70–90 %', '90–100 %'], edge='#9aa5b1')
        fig.add_artist(matplotlib.lines.Line2D([0.56, 0.6], [0.222, 0.222], color='#1658b8', lw=1.2, ls='--', transform=fig.transFigure))
        fig.text(0.605, 0.222, {'uz': 'yog‘in ehtimoli 50 % dan yuqori', 'ru': 'вероятность осадков выше 50 %', 'tr': 'yağış olasılığı %50 üzeri'}[lang], fontsize=9.6, color=INK, va='center')
        fig.text(0.04, 0.176, L['src_wx'], fontsize=9, color=MUTED, va='center')
    # timeline for the main city
    if R.main is not None:
        nm = city_name(R.main, lang)
        if product == 'prob':
            v = np.clip(R.series(R.main), 0, 100); cls = np.digitize(v, LEVELS[:-1]); ts = R.tseries(R.main)
            snowy = (ts <= 0.5) if ts is not None else np.zeros(len(v), bool)
            _timeline(fig, R, D, s, run, off, v, [(SNOW_BAR if sn else BAR_COLORS)[c] for c, sn in zip(cls, snowy)], (0, 100), lambda x, _: f'{x:.0f}',
                      L['bars'].format(city=nm) + ('  ·  ' + L['tline'] if ts is not None else ''), (ts, '#c2410c', lambda x, _: fmt_t(x)) if ts is not None else None)
        elif product == 'temp':
            ts = R.tseries(R.main)
            if ts is not None:
                lo, hi = np.nanmin(ts), np.nanmax(ts); pad = max(2, (hi - lo) * 0.15)
                cols = [T_COL[int(np.clip(np.digitize(t, T_LV) - 1, 0, len(T_COL) - 1))] if np.isfinite(t) else '#eee' for t in ts]
                _timeline(fig, R, D, s, run, off, None, None, (lo - pad, hi + pad), lambda x, _: fmt_t(x), L['bars_temp'].format(city=nm), (ts, '#c2410c', None))
        else:
            cs_ = R.cseries(R.main)
            if cs_ is not None:
                cv = np.nan_to_num(cs_) * 100
                _timeline(fig, R, D, s, run, off, cv, [CL_COL[int(np.clip(np.digitize(c, CL_LV[:-1]) - 1, 0, 4))] if c >= 10 else '#f3f5f7' for c in cv], (0, 100), lambda x, _: f'{x:.0f}', L['bars_cloud'].format(city=nm))
    if comment:
        fig.patches.append(Rectangle((0.04, 0.008), 0.92, 0.042, transform=fig.transFigure, facecolor='#f1f5fa', edgecolor='#d8e0e8', lw=0.8))
        fig.text(0.05, 0.029, comment, fontsize=11.2, color=INK, va='center', wrap=True)
    fig.savefig(path, dpi=_CTX.get('dpi', 100), facecolor='white')
    plt.close(fig)


def city_list(R, geo, lang):
    """The cities of the bot's city menu for a region: the main city first, then the labelled ones, then the biggest towns."""
    cities = [c for c in R.cities if not R.iso or c.get('iso') == R.iso]
    if R.iso:  # plus the biggest towns of the country that are not labelled on the map
        cities += sorted([c for c in geo.places if c['iso'] == R.iso and c not in cities], key=lambda c: -c['pop'])[:max(0, 14 - len(cities))]
    if R.mains[lang] in cities: cities.remove(R.mains[lang])
    return (([R.mains[lang]] if R.mains[lang] else []) + cities)[:15]


def _video(fdir, mp4, fps, width=None, crf=None):
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', str(fps), '-i', str(fdir / '%03d.png'),
                    '-vf', f"fps=25,scale={width or _CTX.get('width', 1152)}:-2,format=yuv420p", '-c:v', 'libx264', '-crf', str(crf or _CTX.get('crf', 24)), '-preset', 'medium', '-movflags', '+faststart', str(mp4)], check=True)


def _city_job(args):
    """The precipitation video of one region with the timeline and the comments of a chosen city."""
    region, lang, ci, sel, out, fps = args
    D, P, models, members, geo = _CTX['D'], _CTX['P'], _CTX['models'], _CTX['members'], _CTX['geo']
    R = Region(D, geo, region, P, D['amt'])
    run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    city = city_list(R, geo, lang)[ci]
    if city not in R.cities: R.cities.append(city); R.cxy.append(R.proj(city['lon'], city['lat']))
    off = R.off if R.off is not None else OVERVIEW_TZ[lang]
    com = daily_comments(R, D, lang, off, city, area=False)
    fdir = out / 'frames' / f'{region}_{lang}_c{ci:02d}'; fdir.mkdir(parents=True, exist_ok=True)
    for i, s in enumerate(sel):
        day = local_day(run, D['steps'][s], off, D['win'][s])
        draw_frame(R, D, s, lang, models, members, fdir / f'{i:03d}.png', 'prob', com.get(day.isoformat(), ''), main=city)
    mp4 = out / f'{region}_{lang}_c{ci:02d}.mp4'
    _video(fdir, mp4, fps, _CTX.get('city_width'), _CTX.get('city_crf'))  # smaller files: dozens of them
    print(region, lang, city_name(city, lang), 'city video ok', flush=True)
    return region, lang, ci, mp4.name


_CTX = {}
def _job(args):
    region, langs, sel, out, fps, products = args
    D, P, models, members, geo = _CTX['D'], _CTX['P'], _CTX['models'], _CTX['members'], _CTX['geo']
    R = Region(D, geo, region, P, D['amt'])
    run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    res = []
    for lang in langs:
        R.main = R.mains[lang]
        off = R.off if R.off is not None else OVERVIEW_TZ[lang]
        com = daily_comments(R, D, lang, off)
        for product in products:
            if product != 'prob' and (R.T is None if product == 'temp' else R.C is None): continue
            suf = '' if product == 'prob' else '_' + product
            fdir = out / 'frames' / f'{region}_{lang}{suf}'; fdir.mkdir(parents=True, exist_ok=True)
            for i, s in enumerate(sel):
                day = local_day(run, D['steps'][s], off, D['win'][s])
                draw_frame(R, D, s, lang, models, members, fdir / f'{i:03d}.png', product, com.get(day.isoformat(), ''))
            mp4 = out / f'{region}_{lang}{suf}.mp4'
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', str(fps), '-i', str(fdir / '%03d.png'),
                            '-vf', f"fps=25,scale={_CTX.get('width', 1152)}:-2,format=yuv420p", '-c:v', 'libx264', '-crf', str(_CTX.get('crf', 24)), '-preset', 'medium', '-movflags', '+faststart', str(mp4)], check=True)
            res.append({'region': region, 'lang': lang, 'product': product, 'video': mp4.name, 'frames': len(sel), 'name': NAMES[region][lang]})
            print(region, lang, product, 'ok', flush=True)
        res.append({'region': region, 'lang': lang, 'product': 'days', 'days': com, 'off': off, 'city': city_name(R.mains[lang], lang) if R.mains[lang] else ''})
        # the same daily comments for every labelled city of the country (the bot's city menu)
        cities = city_list(R, geo, lang)
        (out / 'cities').mkdir(exist_ok=True)
        json.dump({'region': region, 'lang': lang, 'off': off, 'cities': [{'name': city_name(c, lang), 'days': daily_comments(R, D, lang, off, c, area=False)} for c in cities]},
                  open(out / 'cities' / f'{region}_{lang}.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('npz'); ap.add_argument('out')
    ap.add_argument('--regions', default=','.join(ORDER)); ap.add_argument('--langs', default='uz,ru,tr')
    ap.add_argument('--fps', type=float, default=1.0); ap.add_argument('--steps', default=''); ap.add_argument('--jobs', type=int, default=os.cpu_count() or 2)
    ap.add_argument('--globe-data', default='', help='site/data with forecast.json + clouds/ (temperature and clouds from charts.ecmwf.int)')
    ap.add_argument('--max-step', type=int, default=0)
    ap.add_argument('--wx', default='', help='wx.npz: GEFS mean temperature and cloud cover (preferred over --globe-data)')
    ap.add_argument('--products', default='prob,temp,cloud')
    ap.add_argument('--geo', default='', help='boundary pack (default prob/geo_prob.json; continents: prob/geo_world.json)')
    ap.add_argument('--dpi', type=int, default=150, help='frame resolution: 150 → 1920×1500, sharp when zoomed in')
    ap.add_argument('--width', type=int, default=1920, help='video width in pixels')
    ap.add_argument('--crf', type=int, default=24, help='video quality (lower = sharper, bigger files)')
    ap.add_argument('--append', action='store_true', help='add these maps to an existing manifest.json instead of replacing it')
    ap.add_argument('--city-videos', default='', help='regions that also get one precipitation video per city, e.g. UZ,KZ')
    ap.add_argument('--city-langs', default='ru,uz', help='languages of the city videos')
    ap.add_argument('--city-width', type=int, default=1280); ap.add_argument('--city-crf', type=int, default=28)
    a = ap.parse_args()
    D = load(a.npz)
    P, models, members = probability(D)
    _CTX.update(D=D, P=P, models=models, members=members, dpi=a.dpi, width=a.width, crf=a.crf, city_width=a.city_width, city_crf=a.city_crf, geo=Geo(a.geo or None), wx=load_wx_npz(D, a.wx) if a.wx else load_wx(D, a.globe_data))
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    sel = list(range(len(D['steps']))) if not a.steps else [list(D['steps']).index(int(x)) for x in a.steps.split(',')]
    if a.max_step: sel = [i for i in sel if int(D['steps'][i]) <= a.max_step]
    tasks = [(r, a.langs.split(','), sel, out, a.fps, a.products.split(',')) for r in a.regions.split(',')]
    manifest = []
    import multiprocessing as mp
    if a.jobs > 1:
        with mp.get_context('fork').Pool(a.jobs) as pool:
            for res in pool.imap(_job, tasks): manifest += res
    else:
        for t in tasks: manifest += _job(t)
    # one precipitation video per city (the bot's city menu); the cities/*.json files learn their video names
    ctasks = []
    for r in [x for x in a.city_videos.split(',') if x and x in a.regions.split(',')]:
        for lang in [l for l in a.city_langs.split(',') if l in a.langs.split(',')]:
            n = len(json.load(open(out / 'cities' / f'{r}_{lang}.json'))['cities'])
            ctasks += [(r, lang, ci, sel, out, a.fps) for ci in range(n)]
    if ctasks:
        if a.jobs > 1:
            with mp.get_context('fork').Pool(a.jobs) as pool: done = list(pool.imap_unordered(_city_job, ctasks))
        else: done = [_city_job(t) for t in ctasks]
        for r, lang, ci, name in done:
            f = out / 'cities' / f'{r}_{lang}.json'; C = json.load(open(f)); C['cities'][ci]['video'] = name
            json.dump(C, open(f, 'w'), ensure_ascii=False, separators=(',', ':'))
    M = {'run': D['run'], 'models': models, 'members': members, 'fps': a.fps, 'steps': [int(D['steps'][i]) for i in sel], 'win': [int(D['win'][i]) for i in sel], 'items': manifest}
    if a.append and (out / 'manifest.json').exists():
        old = json.load(open(out / 'manifest.json')); done = {i['region'] for i in manifest}
        M['items'] = [i for i in old.get('items', []) if i['region'] not in done] + manifest
    json.dump(M, open(out / 'manifest.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
