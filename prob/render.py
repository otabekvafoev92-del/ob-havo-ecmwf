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

import matplotlib.font_manager as _fm
from matplotlib.patches import FancyBboxPatch
import textwrap
# Osmon video style: the site's night palette, Golos Text / Unbounded (SIL OFL, prob/fonts), portrait layout:
# header, map, a card for the chosen city, legend chips and the 15-day timeline
for _f in sorted((HERE / 'fonts').glob('*.ttf')): _fm.fontManager.addfont(str(_f))
matplotlib.rcParams.update({'font.family': 'Golos Text', 'font.size': 10})
DISPLAY = 'Unbounded'

BG, CARD, CARD2, LINE = '#0b111b', '#121c2b', '#182435', '#233247'
INK, MUTED, FAINT = '#eef3f9', '#8fa0b6', '#5d6e85'
ACCENT, SKY = '#ffad5c', '#6cc4ff'
SEA, LAND = '#0d1624', '#1a2638'
BORDER, FOCUS = '#34465f', '#f2f6fb'
LEVELS = [10, 30, 50, 70, 90, 101]
COLORS = ['#1d5f80', '#1f8cbd', '#33b5e0', '#7ad9f5', '#d2f6ff']        # rain: brighter = more likely (night map)
SNOW = ['#5d3f86', '#8a55c0', '#b476e6', '#d8a8f8', '#f6e6ff']          # snow
CLOUD_LV, CLOUD_COL = [0.5, 0.8, 1.01], [(1, 1, 1, 0.07), (1, 1, 1, 0.15)]  # cloud cover fraction (≥50 %, ≥80 %)
T_LV = list(range(-40, 44, 4))
_T_ANCH = [(-40, '#2a1858'), (-24, '#2e4fb5'), (-12, '#2f8fd0'), (-4, '#7fd0e6'), (0, '#d9f3ee'), (6, '#f3e9a6'), (14, '#f7c46b'),
           (22, '#f3904f'), (30, '#d8524a'), (40, '#7a1530')]
def _tcol(v):
    for (a0, c0), (a1, c1) in zip(_T_ANCH, _T_ANCH[1:]):
        if v <= a1:
            k = max(0, (v - a0) / (a1 - a0)); h0, h1 = matplotlib.colors.to_rgb(c0), matplotlib.colors.to_rgb(c1)
            return matplotlib.colors.to_hex([x0 + (x1 - x0) * k for x0, x1 in zip(h0, h1)])
    return _T_ANCH[-1][1]
T_COL = [_tcol(v + 2) for v in T_LV[:-1]] + [_T_ANCH[-1][1]]
CL_LV, CL_COL = [10, 30, 50, 70, 90, 101], ['#253247', '#33445c', '#475a74', '#687c96', '#97a8be']
LOW_BAR = '#22304a'
BAR_COLORS = [LOW_BAR] + COLORS
SNOW_BAR = [LOW_BAR] + SNOW
LABELS = ['10–30 %', '30–50 %', '50–70 %', '70–90 %', '90–100 %']
ENS_LABEL = {'ifs': 'ECMWF IFS ENS', 'aifs': 'ECMWF AIFS ENS', 'gefs': 'NOAA GEFS'}
DET_LABEL = {'hres': 'ECMWF IFS', 'aifss': 'ECMWF AIFS', 'gfs': 'NOAA GFS', 'icon': 'DWD ICON'}
HEAVY = '#ffd166'
W_LV = [0, 2, 4, 6, 8, 10, 12, 15, 20, 25, 60]
W_COL = ['#16263a', '#1b3d52', '#1d5d66', '#2a7f6c', '#64a35a', '#c9bd45', '#eea13a', '#e86a3a', '#cf3a52', '#8e1f63']
S2 = {  # words of the city card and the legend
    'uz': {'chance': 'yog‘in ehtimoli', 't': 'Harorat', 'c': 'Bulutlilik', 'a': 'Yog‘in', 'p': 'Yog‘in ehtimoli', 'scale': 'Yog‘in ehtimoli, %', 'iso0': '0° chizig‘i',
           'heavy': '≥ 5 mm', 'deg': 'havo harorati', 'cl': 'bulutlilik', 'p50': 'yog‘in ehtimoli > 50 %',
           'wt': 'Shamol (10 m)', 'ws': 'm/s', 'w': 'Shamol', 'wsub': 'shamol tezligi', 'wleg': 'Shamol tezligi, m/s · NOAA GEFS ansambli o‘rtachasi', 'wbars': '{city}: shamol, m/s',
           'dirs': ['shimoliy', 'shim.-sharqiy', 'sharqiy', 'jan.-sharqiy', 'janubiy', 'jan.-g‘arbiy', 'g‘arbiy', 'shim.-g‘arbiy']},
    'ru': {'chance': 'вероятность осадков', 't': 'Температура', 'c': 'Облачность', 'a': 'Осадки', 'p': 'Вероятность осадков', 'scale': 'Вероятность осадков, %', 'iso0': 'линия 0°',
           'heavy': '≥ 5 мм', 'deg': 'температура воздуха', 'cl': 'облачность', 'p50': 'вероятность осадков > 50 %',
           'wt': 'Ветер (10 м)', 'ws': 'м/с', 'w': 'Ветер', 'wsub': 'скорость ветра', 'wleg': 'Скорость ветра, м/с · среднее ансамбля NOAA GEFS', 'wbars': '{city}: ветер, м/с',
           'dirs': ['северный', 'северо-восточный', 'восточный', 'юго-восточный', 'южный', 'юго-западный', 'западный', 'северо-западный']},
    'tr': {'chance': 'yağış olasılığı', 't': 'Sıcaklık', 'c': 'Bulutluluk', 'a': 'Yağış', 'p': 'Yağış olasılığı', 'scale': 'Yağış olasılığı, %', 'iso0': '0° çizgisi',
           'heavy': '≥ 5 mm', 'deg': 'hava sıcaklığı', 'cl': 'bulutluluk', 'p50': 'yağış olasılığı > %50',
           'wt': 'Rüzgâr (10 m)', 'ws': 'm/s', 'w': 'Rüzgâr', 'wsub': 'rüzgâr hızı', 'wleg': 'Rüzgâr hızı, m/s · NOAA GEFS topluluk ortalaması', 'wbars': '{city}: rüzgâr, m/s',
           'dirs': ['kuzey', 'kuzeydoğu', 'doğu', 'güneydoğu', 'güney', 'güneybatı', 'batı', 'kuzeybatı']},
}
def ISO_COL(v):  # isotherms on the night map: sky blue for 0°, cool below, warm above
    if v == 0: return SKY
    return '#7f9cff' if v < 0 else '#f0a868'


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
    Uw = z['U'].astype(np.float32) if 'U' in z.files else None; Vw = z['V'].astype(np.float32) if 'V' in z.files else None
    S = len(D['steps']); T = np.full((S, g['H'], g['W']), np.nan, np.float32); C = np.full_like(T, np.nan)
    U = np.full_like(T, np.nan) if Uw is not None else None; V = np.full_like(T, np.nan) if Vw is not None else None
    for i, s_ in enumerate(D['steps']):
        s_ = int(s_)
        w_ = int(D['win'][i]) if 'win' in D else 6
        a = [st.index(h) for h in (s_ - w_, s_) if h in st]
        if a: T[i] = up(np.nanmean([Tw[k] for k in a], 0))
        if a and U is not None: U[i] = up(np.nanmean([Uw[k] for k in a], 0)); V[i] = up(np.nanmean([Vw[k] for k in a], 0))
        if s_ in st and np.isfinite(Cw[st.index(s_)]).any(): C[i] = up(Cw[st.index(s_)]) / 100  # GEFS cloud cover is already a 6-h mean
    return {'T': T, 'C': C, 'U': U, 'V': V}


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
        self.upk = 3 if (not self.cont and region not in ('cis', 'RU')) else 1
        self.XU, self.YU = (_up(self, self.X), _up(self, self.Y))
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
            self.U = self.V = self.Wd = None
            if wx.get('U') is not None and np.isfinite(wx['U']).any():
                self.U = np.stack([gaussian_filter(np.nan_to_num(wx['U'][s, y0:y1, x0:x1]), 1.0) for s in range(P.shape[0])])
                self.V = np.stack([gaussian_filter(np.nan_to_num(wx['V'][s, y0:y1, x0:x1]), 1.0) for s in range(P.shape[0])])
                self.Wd = np.hypot(self.U, self.V)
        else:
            self.T = self.C = self.U = self.V = self.Wd = None
        # map extent: projected bounding box of the lon/lat box
        bl = np.linspace(lon0, lon1, 60); bb = np.linspace(lat0, lat1, 40)
        ex, ey = self.proj(np.r_[bl, np.full(40, lon1), bl[::-1], np.full(40, lon0)], np.r_[np.full(60, lat0), bb, np.full(60, lat1), bb[::-1]])
        self.ext = (ex.min(), ex.max(), ey.min(), ey.max())
        if region in ('cis', 'RU'):  # trim the empty corners of wide conic maps
            xs, ys = self.proj(np.r_[bl, bl], np.r_[np.full(60, lat0 + 2), np.full(60, lat1)])
            self.ext = (xs.min(), xs.max(), min(ys), max(ys))
        self.geo = geo
        self.relief = relief(self.proj, self.ext)
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

    def wseries(self, p):
        if self.Wd is None: return None
        gx, gy = self._xy(p); return np.array([bilinear(self.Wd[s], gx, gy) for s in range(self.Wd.shape[0])])

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


_DEM = None
def relief(proj, ext, n=760):
    """Shaded relief (RGBA) of the map window in the map projection, from the website's world height map."""
    global _DEM
    try:
        if _DEM is None:
            from PIL import Image
            v = np.asarray(Image.open(HERE.parent / 'site' / 'assets' / 'dem-world.png').convert('L'), float)
            _DEM = np.where(v >= 64, ((v - 64) / 191) ** 2 * 8848, 0.0)
        from scipy.ndimage import map_coordinates
        x0, x1, y0, y1 = ext; m = int(n * (y1 - y0) / (x1 - x0))
        X, Y = np.meshgrid(np.linspace(x0, x1, n), np.linspace(y1, y0, m))
        lon, lat = proj(X, Y, inverse=True)
        H, W = _DEM.shape
        z = map_coordinates(_DEM, [(90 - lat) / 180 * H - 0.5, ((lon + 180) % 360) / 360 * W - 0.5], order=1, mode='nearest')
        z = gaussian_filter(z, 1.0)
        px = (x1 - x0) / n
        gy, gx = np.gradient(z, px)
        az, alt = np.radians(315), np.radians(40)
        slope = np.arctan(np.hypot(gx, gy) * 30.0); aspect = np.arctan2(-gx, gy)
        shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
        out = np.zeros((m, n, 4))
        light = np.clip((shade - 0.70) * 2.5, 0, 1); dark = np.clip((0.66 - shade) * 1.8, 0, 1)
        out[..., :3] = np.where(light[..., None] > 0, [0.80, 0.88, 1.0], [0.0, 0.02, 0.06])
        hi = np.clip(z / 4500, 0, 1)
        out[..., 3] = np.clip(light * 0.28 + dark * 0.55 + hi * 0.06, 0, 0.6) * (z > 1)
        return out
    except Exception as e:
        print('relief:', e); return None


def _up(R, F):
    """Finer grid for smooth contour edges on country maps."""
    k = getattr(R, 'upk', 1)
    if k == 1: return F
    from scipy.ndimage import zoom
    return zoom(F, k, order=1)


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


def _card(fig, x, y, w, h, fc=CARD, ec=LINE, r=0.012, z=-5):  # under the axes
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle=f'round,pad=0,rounding_size={r}', transform=fig.transFigure, facecolor=fc, edgecolor=ec, lw=0.8, zorder=z,
                                      mutation_aspect=fig.get_figwidth() / fig.get_figheight()))


def _when(lang, run, step, off, win):
    """('Сб 31.10 · 17:00–20:00', tz) — the forecast window in local time."""
    t1 = run + dt.timedelta(hours=int(step) - int(win) + off); t2 = run + dt.timedelta(hours=int(step) + off)
    wd = lambda t: T[lang]['wd'][t.weekday()]
    end = t2 - dt.timedelta(minutes=1)
    if t1.date() == end.date():
        return f"{wd(t1)} {t1:%d.%m} · {t1.hour:02d}:00–{(t2.hour or 24):02d}:00"
    return f"{wd(t1)} {t1:%d.%m} {t1.hour:02d}:00 – {wd(t2)} {t2:%d.%m} {t2.hour:02d}:00"


def _header(fig, R, D, s, lang, title):
    run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    step = int(D['steps'][s]); off = R.off if R.off is not None else OVERVIEW_TZ[lang]
    # brand: a ring (the site's mark) and the word
    k = fig.get_figheight() / fig.get_figwidth()
    for a0, a1, col in ((200, 20, ACCENT), (20, 200, SKY)):  # two-tone ring, as on the website
        fig.patches.append(matplotlib.patches.Wedge((0.047, 0.966), 0.0125, a0, a1, width=0.0055, transform=fig.transFigure, facecolor=col, edgecolor='none'))
    fig.patches[-1].set_transform(matplotlib.transforms.Affine2D().scale(1, 1 / k) + matplotlib.transforms.Affine2D().translate(0, 0.966 - 0.966 / k) + fig.transFigure)
    fig.patches[-2].set_transform(fig.patches[-1].get_transform())
    fig.text(0.068, 0.966, 'osmon', fontsize=15, fontfamily=DISPLAY, fontweight='bold', color=INK, va='center')
    fig.text(0.192, 0.966, '.', fontsize=15, fontfamily=DISPLAY, fontweight='bold', color=ACCENT, va='center')
    tx = fig.text(0.96, 0.966, title.upper(), fontsize=8.4, fontweight='bold', color=SKY, ha='right', va='center')
    bb = tx.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
    _card(fig, bb.x0 - 0.018, 0.951, bb.width + 0.036, 0.03, fc=CARD2, ec=LINE, r=0.015)
    fig.text(0.035, 0.921, NAMES[R.id][lang], fontsize=19, fontfamily=DISPLAY, fontweight='bold', color=INK, va='center')
    t = fig.text(0.035, 0.887, _when(lang, run, step, off, D['win'][s]), fontsize=13.5, fontweight='bold', color=ACCENT, va='center')
    fig.text(0.975, 0.887, tz_label(lang, R.id, off), fontsize=9, color=MUTED, ha='right', va='center')
    return run, step, off


def zoom_view(R, p, z):
    """Map window of 1/z of the region around a place (kept inside the region)."""
    x0, x1, y0, y1 = R.ext
    if z <= 1.001 or p is None: return R.ext
    cx, cy = R.proj(p['lon'], p['lat']); w, h = (x1 - x0) / z, (y1 - y0) / z
    cx = min(max(cx, x0 + w / 2), x1 - w / 2); cy = min(max(cy, y0 + h / 2), y1 - h / 2)
    return (cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2)


MAP_BOX = [0.025, 0.415, 0.95, 0.46]
def _basemap(fig, R):
    _card(fig, MAP_BOX[0] - 0.006, MAP_BOX[1] - 0.005, MAP_BOX[2] + 0.012, MAP_BOX[3] + 0.01, fc=SEA, ec=LINE)
    ax = fig.add_axes(MAP_BOX)
    x0, x1, y0, y1 = getattr(R, 'view', None) or R.ext
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal', adjustable='box'); ax.axis('off')
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=SEA, edgecolor='none', zorder=0))
    ax.add_collection(PolyCollection([r for rings in R.cpoly.values() for r in rings], facecolor=LAND, edgecolor='none', zorder=1))
    if getattr(R, 'relief', None) is not None:
        ax.imshow(R.relief, extent=R.ext, origin='upper', interpolation='bilinear', zorder=2.6)
    return ax


def _borders(ax, R):
    x0, x1, y0, y1 = getattr(R, 'view', None) or R.ext
    if R.iso:  # neighbours dimmed, provinces of the country drawn faintly
        ax.add_collection(PolyCollection([r for c, rings in R.cpoly.items() if c != R.iso for r in rings], facecolor=(0.04, 0.07, 0.11, 0.45), edgecolor='none', zorder=4))
        ax.add_collection(LineCollection(R.a1, colors='#3d5068', linewidths=0.4, zorder=5))
    ax.add_collection(LineCollection([r for c, rings in R.cpoly.items() if c != R.iso for r in rings], colors=BORDER, linewidths=0.55, zorder=5))
    focus = [] if R.cont else [R.iso] if R.iso else [c for c in CIS if c in R.cpoly]
    rings = [r for c in focus for r in R.cpoly.get(c, [])]
    ax.add_collection(LineCollection(rings, colors=SKY, linewidths=4.5 if R.iso else 3, alpha=0.18, zorder=5.5))  # soft glow
    ax.add_collection(LineCollection(rings, colors=FOCUS, linewidths=1.3 if R.iso else 0.8, zorder=6))
    ax.text(0.99, 0.015, 't.me/ObHavo_ECMWF_bot', transform=ax.transAxes, fontsize=7, color=FAINT, ha='right', va='bottom', zorder=13)


def _cities(fig, ax, R, label, extra=()):
    x0, x1, y0, y1 = getattr(R, 'view', None) or R.ext
    fig.canvas.draw(); placed = []; axb = ax.get_window_extent()
    pts = list(zip(R.cities, R.cxy)) + list(extra)
    for p, (cx, cy) in sorted(pts, key=lambda t: t[0] is not R.main):
        if not (x0 < cx < x1 and y0 < cy < y1): continue
        main = p is R.main; txt = label(p, main)
        fs = 11.5 if main else 8.4
        px, py = ax.transData.transform((cx, cy)); dpi_k = fig.dpi / 72
        w, h = (len(txt) * fs * 0.58 + 12) * dpi_k, (fs * 1.6 + 6) * dpi_k
        spot = None
        for dx, dy, ha, va in ((7, 4, 'left', 'bottom'), (7, -4, 'left', 'top'), (-7, 4, 'right', 'bottom'), (-7, -4, 'right', 'top')):
            ox, oy = dx * dpi_k, dy * dpi_k
            bx0 = px + (ox if ha == 'left' else ox - w); by0 = py + (oy if va == 'bottom' else oy - h); box_ = (bx0, by0, bx0 + w, by0 + h)
            inside = box_[0] > axb.x0 + 2 and box_[2] < axb.x1 - 2 and box_[1] > axb.y0 + 2 and box_[3] < axb.y1 - 2
            if inside and all(box_[2] < b[0] or box_[0] > b[2] or box_[3] < b[1] or box_[1] > b[3] for b in placed): spot = (dx, dy, ha, va, box_); break
        if main:
            ax.plot(cx, cy, 'o', ms=13, mfc='none', mec=ACCENT, mew=1.2, alpha=0.6, zorder=10)
            ax.plot(cx, cy, 'o', ms=6.5, mfc=ACCENT, mec=BG, mew=1.5, zorder=10)
        else:
            ax.plot(cx, cy, 'o', ms=3.6, mfc=INK, mec=BG, mew=0.8, zorder=10)
        if spot is None: continue
        dx, dy, ha, va, box_ = spot; placed.append(box_)
        ax.annotate(txt, (cx, cy), xytext=(dx, dy), textcoords='offset points', fontsize=fs, ha=ha, va=va, fontweight='bold' if main else 'medium',
                    color='#2a1600' if main else INK, zorder=12 if main else 11,
                    bbox=dict(boxstyle='round,pad=0.38,rounding_size=0.7' if main else 'round,pad=0.25,rounding_size=0.5', fc=ACCENT if main else BG, ec='none', alpha=1 if main else 0.72))


def _chips(fig, x, y, cols, labels, w=0.052, h=0.019, gap=0.004, dark_from=3):
    for i, (c, lab) in enumerate(zip(cols, labels)):
        _card(fig, x + i * (w + gap), y - h / 2, w, h, fc=c, ec='none', r=0.006)
        fig.text(x + i * (w + gap) + w / 2, y, lab, fontsize=7.6, fontweight='bold', ha='center', va='center',
                 color=BG if i >= dark_from else INK)


def _timeline(fig, R, D, s, run, off, values, colors, ylim, yfmt, title, line=None, lang='ru'):
    _card(fig, 0.025, 0.042, 0.95, 0.143)
    fig.text(0.045, 0.168, title, fontsize=9, color=MUTED, va='center')
    bx = fig.add_axes([0.075, 0.068, 0.87, 0.082]); bx.set_facecolor('none')
    st_ = np.array([int(x) for x in D['steps']], float); wn = np.array([int(x) for x in D['win']], float)
    X = st_ - wn / 2  # middle of each window, hours from the run
    bx.axvspan(X[s] - wn[s] / 2, X[s] + wn[s] / 2, color=ACCENT, alpha=0.16, lw=0, zorder=1)
    bx.axvline(X[s], color=ACCENT, lw=1.3, zorder=4)
    if values is not None: bx.bar(X, values, width=wn * 0.72, color=colors, zorder=2)
    bx.set_ylim(*ylim); bx.set_xlim(st_[0] - wn[0] - 1, st_[-1] + 1)
    bx.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(yfmt)); bx.tick_params(labelsize=7.5, colors=FAINT, length=0)
    bx.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
    ticks, labs = [], []
    t0 = run + dt.timedelta(hours=off); first = (t0 + dt.timedelta(days=1)).replace(hour=0, minute=0)
    if t0.hour == 0: first = t0
    k = first
    while (k - t0).total_seconds() / 3600 <= st_[-1]:
        ticks.append((k - t0).total_seconds() / 3600); labs.append(f"{T[lang]['wd'][k.weekday()]}\n{k:%d}"); k += dt.timedelta(days=1)
    bx.set_xticks([t + 12 for t in ticks]); bx.set_xticklabels(labs, fontsize=7, color=MUTED, linespacing=1.1)
    for tk in ticks: bx.axvline(tk, color=LINE, lw=0.7, zorder=0)
    bx.grid(axis='y', color=LINE, lw=0.5, zorder=0)
    for sp in bx.spines.values(): sp.set_visible(False)
    if line is not None and np.isfinite(line[0]).any():
        ys, col, fmt = line
        tx = bx if values is None else bx.twinx()
        tx.plot(X, ys, color=col, lw=1.3, alpha=0.9, zorder=5, solid_capstyle='round'); tx.plot([X[s]], [ys[s]], 'o', ms=5, color=col, mec=BG, mew=1.2, zorder=6)
        if tx is not bx:
            lo, hi = np.nanmin(ys), np.nanmax(ys); pad = max(2, (hi - lo) * 0.15); tx.set_ylim(lo - pad, hi + pad)
            tx.tick_params(length=0, labelsize=7.5, colors=col); tx.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(fmt))
            tx.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
            for sp in tx.spines.values(): sp.set_visible(False)


def _level_col(v, pal):
    if not np.isfinite(v) or v < LEVELS[0]: return '#b9c6d6'
    return pal[int(np.clip(np.digitize(v, LEVELS[:-1]) - 1, 0, 4))]


def draw_frame(R, D, s, lang, models, members, path, product='prob', comment='', main=None, zoom=1.0, dpi=None):
    L = T[lang]; W2 = S2[lang]; R.main = main if main is not None else R.mains[lang]
    R.view = zoom_view(R, R.main, zoom) if zoom > 1.001 else None
    fig = plt.figure(figsize=(7.2, 9.0), dpi=100); fig.patch.set_facecolor(BG)
    title = {'prob': L['title'], 'temp': L['title_temp'], 'cloud': L['title_cloud'], 'wind': W2['wt']}[product]
    run, step, off = _header(fig, R, D, s, lang, title)
    ax = _basemap(fig, R)
    has_w = getattr(R, 'Wd', None) is not None
    has_t = R.T is not None and np.isfinite(R.T[s]).any(); has_c = R.C is not None and np.isfinite(R.C[s]).any()
    near = R.id in ('cis', 'RU') or R.cont
    U = lambda F: _up(R, F); XU, YU = R.XU, R.YU
    if product == 'prob':
        if has_c: ax.contourf(XU, YU, U(np.nan_to_num(R.C[s])), levels=CLOUD_LV, colors=CLOUD_COL, zorder=1.5, antialiased=True)
        snow = np.nan_to_num(R.T[s] <= 0.5).astype(bool) if has_t else np.zeros_like(R.P[s], bool)
        Pr, Ps = np.where(snow, 0, R.P[s]), np.where(snow, R.P[s], 0)
        ax.contourf(XU, YU, U(Pr), levels=LEVELS, cmap=ListedColormap(COLORS), norm=BoundaryNorm(LEVELS, 5), zorder=2, antialiased=True, alpha=0.92)
        if Ps.max() >= LEVELS[0]: ax.contourf(XU, YU, U(Ps), levels=LEVELS, cmap=ListedColormap(SNOW), norm=BoundaryNorm(LEVELS, 5), zorder=2.1, antialiased=True, alpha=0.92)
        if (R.Asm[s] >= 5).any(): ax.contour(XU, YU, U(R.Asm[s]), levels=[5], colors=[HEAVY], linewidths=1.1, linestyles='dashed', zorder=3)
        if has_t:
            lv = [0] if near else list(range(-30, 45, 5))
            cs = ax.contour(XU, YU, np.ma.masked_invalid(U(R.T[s])), levels=lv, colors=[ISO_COL(v) for v in lv], linewidths=[1.6 if v == 0 else 0.6 for v in lv], zorder=3.2,
                            alpha=0.85, linestyles=['solid' if v == 0 else 'dotted' for v in lv])
            if not near: ax.clabel(cs, fmt=fmt_t, fontsize=7, inline=True, inline_spacing=2)
    elif product == 'temp' and has_t:
        Tm = np.ma.masked_invalid(U(R.T[s]))
        ax.contourf(XU, YU, Tm, levels=T_LV, colors=T_COL[:len(T_LV) - 1], extend='both', zorder=2, antialiased=True, alpha=0.88)
        lv = list(range(-40, 45, 4))
        cs = ax.contour(XU, YU, Tm, levels=lv, colors=[SKY if v == 0 else BG for v in lv], linewidths=[1.6 if v == 0 else 0.3 for v in lv], zorder=3, alpha=0.7)
        ax.clabel(cs, levels=[v for v in lv if v % 8 == 0], fmt=fmt_t, fontsize=7, inline=True, colors=BG)
    elif product == 'wind' and has_w:
        ax.contourf(XU, YU, U(R.Wd[s]), levels=W_LV, colors=W_COL, zorder=2, antialiased=True, alpha=0.9)
        ax.contour(XU, YU, U(R.Wd[s]), levels=[10, 15, 20], colors=['#f6f0d8'], linewidths=[0.5, 0.7, 0.9], alpha=0.5, zorder=3)  # strong-wind outlines
    elif product == 'cloud' and has_c:
        ax.contourf(XU, YU, U(np.nan_to_num(R.C[s]) * 100), levels=CL_LV, colors=CL_COL, zorder=2, antialiased=True, alpha=0.95)
        ax.contour(XU, YU, U(R.P[s]), levels=[50], colors=[SKY], linewidths=1.2, linestyles='dashed', zorder=3)
    _borders(ax, R)
    def label(p, main):
        v = R.value_at(s, p); t = R.value_at(s, p, 'T') if has_t else np.nan
        if product == 'temp': return f"{city_name(p, lang)} {fmt_t(t)}" if np.isfinite(t) else city_name(p, lang)
        if product == 'cloud': return f"{city_name(p, lang)} {R.value_at(s, p, 'C') * 100:.0f} %" if has_c else city_name(p, lang)
        if product == 'wind': return f"{city_name(p, lang)} {R.value_at(s, p, 'Wd'):.0f} {W2['ws']}" if has_w else city_name(p, lang)
        txt = f"{city_name(p, lang)} {int(round(max(0, min(100, v))))} %"
        if np.isfinite(t): txt += f" · {fmt_t(t)}" + (' ❄' if t <= 0.5 and v >= 30 else '')
        return txt
    extra = []
    if R.view is not None:  # zoomed in: the towns around the chosen city get labels too
        vx0, vx1, vy0, vy1 = R.view; have = {id(p) for p in R.cities}
        for p in sorted(R.geo.places, key=lambda q: -q['pop']):
            if id(p) in have or len(extra) >= 10: continue
            x, y = R.proj(p['lon'], p['lat'])
            if vx0 < x < vx1 and vy0 < y < vy1: extra.append((p, (x, y)))
    _cities(fig, ax, R, label, extra)
    # the chosen city: one card with the numbers of this window
    _card(fig, 0.025, 0.25, 0.95, 0.152)
    if R.main is not None:
        p = R.main; v = max(0, min(100, R.value_at(s, p))); t = R.value_at(s, p, 'T') if has_t else np.nan
        c = R.value_at(s, p, 'C') * 100 if has_c else np.nan; mm = R.value_at(s, p, 'Araw')
        snowy = np.isfinite(t) and t <= 0.5
        fig.text(0.05, 0.378, city_name(p, lang), fontsize=12.5, fontweight='bold', color=INK, va='center')
        if product == 'temp' and np.isfinite(t): big, bigc, sub = fmt_t(t), _tcol(t), W2['deg']
        elif product == 'cloud' and np.isfinite(c): big, bigc, sub = f'{c:.0f} %', '#d5deea', W2['cl']
        elif product == 'wind' and has_w:
            ws = R.value_at(s, p, 'Wd'); u_, v_ = R.value_at(s, p, 'U'), R.value_at(s, p, 'V')
            frm = (np.degrees(np.arctan2(-u_, -v_)) + 360) % 360
            big, bigc, sub = f"{ws:.0f} {W2['ws']}", W_COL[int(np.clip(np.digitize(ws, W_LV) - 1, 4, 9))], f"{W2['wsub']} · {W2['dirs'][int(round(frm / 45)) % 8]}"
        else: big, bigc, sub = f'{v:.0f} %', _level_col(v, SNOW if snowy else COLORS), W2['chance']
        fig.text(0.05, 0.33, big, fontsize=29, fontfamily=DISPLAY, fontweight='bold', color=bigc, va='center')
        fig.text(0.05, 0.288, sub, fontsize=8.5, color=MUTED, va='center')
        stats = []
        if product != 'prob': stats.append((W2['p'], f'{v:.0f} %'))
        if product != 'temp' and np.isfinite(t): stats.append((W2['t'], fmt_t(t)))
        if product != 'cloud' and np.isfinite(c): stats.append((W2['c'], f'{c:.0f} %'))
        if product == 'prob' and mm >= 0.1: stats.append((W2['a'], f'≈ {mm:.1f} mm' if mm < 1.5 else f'≈ {mm:.0f} mm'))
        for i, (k, val) in enumerate(stats[:3]):
            y = 0.372 - i * 0.034
            fig.text(0.47, y, k, fontsize=9.5, color=MUTED, va='center')
            fig.text(0.95, y, val, fontsize=11, fontweight='bold', color=INK, va='center', ha='right')
            if i < len(stats[:3]) - 1: fig.add_artist(matplotlib.lines.Line2D([0.47, 0.95], [y - 0.017, y - 0.017], color=LINE, lw=0.6, transform=fig.transFigure))
    if comment:
        fig.text(0.05, 0.262, textwrap.shorten(comment, 130, placeholder='…'), fontsize=8.6, color='#c9d4e2', va='center', style='italic')
    # legend
    if product == 'prob':
        fig.text(0.035, 0.226, f"{W2['scale']} · {hours_text(lang, D['win'][s])}", fontsize=8.2, color=MUTED, va='center')
        fig.text(0.035, 0.2, L['rain'], fontsize=8.5, fontweight='bold', color=INK, va='center')
        _chips(fig, 0.105, 0.2, COLORS, ['10', '30', '50', '70', '90'], w=0.05, h=0.018, gap=0.003)
        fig.text(0.39, 0.2, L['snow'], fontsize=8.5, fontweight='bold', color=INK, va='center')
        _chips(fig, 0.45, 0.2, SNOW, ['10', '30', '50', '70', '90'], w=0.05, h=0.018, gap=0.003)
        xk = 0.735
        fig.add_artist(matplotlib.lines.Line2D([xk, xk + 0.04], [0.226, 0.226], color=SKY, lw=1.6, transform=fig.transFigure))
        fig.text(xk + 0.048, 0.226, W2['iso0'], fontsize=8, color=MUTED, va='center')
        fig.add_artist(matplotlib.lines.Line2D([xk, xk + 0.04], [0.2, 0.2], color=HEAVY, lw=1.3, ls=(0, (3, 2)), transform=fig.transFigure))
        fig.text(xk + 0.048, 0.2, W2['heavy'], fontsize=8, color=MUTED, va='center')
    elif product == 'temp':
        fig.text(0.035, 0.226, L['legend_temp'].format(h=hours_text(lang, D['win'][s])), fontsize=8.2, color=MUTED, va='center')
        cb = fig.add_axes([0.035, 0.204, 0.93, 0.011])
        cb.imshow([np.arange(len(T_COL))], cmap=ListedColormap(T_COL), aspect='auto', extent=(T_LV[0] - 4, T_LV[-1], 0, 1))
        cb.set_yticks([]); cb.set_xticks(list(range(-40, 41, 8))); cb.set_xticklabels([fmt_t(v) for v in range(-40, 41, 8)], fontsize=7, color=MUTED)
        cb.tick_params(length=0, pad=2)
        for sp in cb.spines.values(): sp.set_visible(False)
    elif product == 'wind':
        fig.text(0.035, 0.226, W2['wleg'], fontsize=8.2, color=MUTED, va='center')
        _chips(fig, 0.035, 0.2, W_COL[1:], [str(v) for v in W_LV[1:-1]], w=0.098, h=0.018, gap=0.0035, dark_from=4)
    else:
        fig.text(0.035, 0.226, L['legend_cloud'], fontsize=8.2, color=MUTED, va='center')
        _chips(fig, 0.035, 0.2, CL_COL, ['10', '30', '50', '70', '90'], w=0.05, h=0.018, gap=0.003, dark_from=4)
        fig.add_artist(matplotlib.lines.Line2D([0.33, 0.37], [0.2, 0.2], color=SKY, lw=1.2, ls=(0, (3, 2)), transform=fig.transFigure))
        fig.text(0.378, 0.2, W2['p50'], fontsize=8, color=MUTED, va='center')
    # timeline of the chosen city
    if R.main is not None:
        nm = city_name(R.main, lang)
        if product == 'prob':
            v = np.clip(R.series(R.main), 0, 100); cls = np.digitize(v, LEVELS[:-1]); ts = R.tseries(R.main)
            snowy = (ts <= 0.5) if ts is not None else np.zeros(len(v), bool)
            _timeline(fig, R, D, s, run, off, v, [(SNOW_BAR if sn else BAR_COLORS)[c] for c, sn in zip(cls, snowy)], (0, 100), lambda x, _: f'{x:.0f}',
                      L['bars'].format(city=nm) + ('  ·  ' + W2['t'].lower() if ts is not None else ''), (ts, ACCENT, lambda x, _: fmt_t(x)) if ts is not None else None, lang=lang)
        elif product == 'temp':
            ts = R.tseries(R.main)
            if ts is not None:
                lo, hi = np.nanmin(ts), np.nanmax(ts); pad = max(2, (hi - lo) * 0.15)
                _timeline(fig, R, D, s, run, off, None, None, (lo - pad, hi + pad), lambda x, _: fmt_t(x), L['bars_temp'].format(city=nm), (ts, ACCENT, None), lang=lang)
        elif product == 'wind':
            ws_ = R.wseries(R.main)
            if ws_ is not None:
                _timeline(fig, R, D, s, run, off, ws_, [W_COL[int(np.clip(np.digitize(w, W_LV) - 1, 0, 9))] if w >= 2 else LOW_BAR for w in ws_], (0, max(8, float(np.nanmax(ws_)) * 1.15)),
                          lambda x, _: f'{x:.0f}', W2['wbars'].format(city=nm), lang=lang)
        else:
            cs_ = R.cseries(R.main)
            if cs_ is not None:
                cv = np.nan_to_num(cs_) * 100
                _timeline(fig, R, D, s, run, off, cv, [CL_COL[int(np.clip(np.digitize(c, CL_LV[:-1]) - 1, 0, 4))] if c >= 10 else LOW_BAR for c in cv], (0, 100), lambda x, _: f'{x:.0f}',
                          L['bars_cloud'].format(city=nm), lang=lang)
    src = (L['models'].format(m=', '.join(models)) + ' · ' + L['method'].format(n=members)) if product == 'prob' else W2['wleg'] if product == 'wind' else L['src_wx']
    fig.text(0.035, 0.026, textwrap.shorten(src, 150, placeholder='…'), fontsize=6.2, color=FAINT, va='center')
    fig.text(0.035, 0.012, L['run'].format(run=run.strftime('%d.%m.%Y %H:%M')) + ' · ECMWF (CC BY 4.0), NOAA, DWD · Natural Earth', fontsize=6.2, color=FAINT, va='center')
    fig.savefig(path, dpi=dpi or _CTX.get('dpi', 100), facecolor=BG)
    plt.close(fig)


def city_list(R, geo, lang):
    """The cities of the bot's city menu for a region: the main city first, then the labelled ones, then the biggest towns."""
    cities = [c for c in R.cities if not R.iso or c.get('iso') == R.iso]
    if R.iso:  # plus the biggest towns of the country that are not labelled on the map
        cities += sorted([c for c in geo.places if c['iso'] == R.iso and c not in cities], key=lambda c: -c['pop'])[:max(0, 14 - len(cities))]
    if R.mains[lang] in cities: cities.remove(R.mains[lang])
    return (([R.mains[lang]] if R.mains[lang] else []) + cities)[:15]


def _video(fdir, mp4, fps, width=None, crf=None, intro=None):
    w = width or _CTX.get('width', 1440); vf = f"fps=25,scale={w}:-2:flags=lanczos,format=yuv420p"
    enc = ['-c:v', 'libx264', '-crf', str(crf or _CTX.get('crf', 24)), '-preset', 'medium', '-movflags', '+faststart', str(mp4)]
    if intro is None:
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', str(fps), '-i', str(fdir / '%03d.png'), '-vf', vf] + enc, check=True)
    else:  # the zoom-in, then the forecast frames
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', str(INTRO), '-i', str(intro / '%03d.png'), '-framerate', str(fps), '-i', str(fdir / '%03d.png'),
                        '-filter_complex', f'[0]{vf}[a];[1]{vf}[b];[a][b]concat=n=2:v=1[v]', '-map', '[v]'] + enc, check=True)


def _city_job(args):
    """The precipitation video of one region around a chosen city: a short zoom-in from the whole country, then the
    15 days with the map closer to the city, its numbers, timeline and daily comments."""
    region, lang, ci, sel, out, fps = args
    D, P, models, members, geo = _CTX['D'], _CTX['P'], _CTX['models'], _CTX['members'], _CTX['geo']
    R = Region(D, geo, region, P, D['amt'])
    run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    city = city_list(R, geo, lang)[ci]
    if city not in R.cities: R.cities.append(city); R.cxy.append(R.proj(city['lon'], city['lat']))
    off = R.off if R.off is not None else OVERVIEW_TZ[lang]
    com = daily_comments(R, D, lang, off, city, area=False)
    Z = max(1.6, (R.ext[1] - R.ext[0]) / 9e5)  # about 900 km across around the city
    dpi = _CTX.get('city_dpi', 150)
    fdir = out / 'frames' / f'{region}_{lang}_c{ci:02d}'; fdir.mkdir(parents=True, exist_ok=True)
    idir = out / 'frames' / f'{region}_{lang}_c{ci:02d}_in'; idir.mkdir(parents=True, exist_ok=True)
    day0 = local_day(run, D['steps'][sel[0]], off, D['win'][sel[0]])
    for i in range(INTRO):
        k = i / (INTRO - 1); k = k * k * (3 - 2 * k)  # ease in and out
        draw_frame(R, D, sel[0], lang, models, members, idir / f'{i:03d}.png', 'prob', com.get(day0.isoformat(), ''), main=city, zoom=Z ** k, dpi=dpi)
    for i, s in enumerate(sel):
        day = local_day(run, D['steps'][s], off, D['win'][s])
        draw_frame(R, D, s, lang, models, members, fdir / f'{i:03d}.png', 'prob', com.get(day.isoformat(), ''), main=city, zoom=Z, dpi=dpi)
    mp4 = out / f'{region}_{lang}_c{ci:02d}.mp4'
    _video(fdir, mp4, fps, _CTX.get('city_width'), _CTX.get('city_crf'), intro=idir)
    print(region, lang, city_name(city, lang), 'city video ok', flush=True)
    return region, lang, ci, mp4.name


INTRO = 9  # frames of the zoom-in (played at 9 frames per second)
def find_alerts(R, D, run, days=3):
    """Heavy precipitation in the next days at the cities of a country (for the bot's warnings):
    a local day with ≥ 15 mm of rain (≥ 8 mm of snow, water equivalent) in the ensemble mean and ≥ 60 % chance."""
    if R.cont or R.id in ('cis',) or not R.iso: return []
    off = R.off if R.off is not None else 5
    steps, win = [int(x) for x in D['steps']], [int(x) for x in D['win']]
    first = (run + dt.timedelta(hours=12 + off)).date()  # data reach the bot about half a day after the model run
    out = []
    for p in city_list(R, R.geo, 'ru'):
        P, A, Ts = R.series(p), R.aseries(p), R.tseries(p)
        by = {}
        for i, (st, w) in enumerate(zip(steps, win)):
            d = local_day(run, st, off, w)
            if first <= d < first + dt.timedelta(days=days): by.setdefault(d, []).append(i)
        for d, idx in sorted(by.items()):
            mm = float(np.nansum(A[idx])); pm = float(np.nanmax(P[idx]))
            wet = [i for i in idx if P[i] >= 30] or idx
            snow = Ts is not None and float(np.nanmean(Ts[wet])) <= 0.5
            lim = 8 if snow else 15
            if mm >= lim and pm >= 60:
                peak = max(idx, key=lambda i: A[i])
                h2 = (run + dt.timedelta(hours=steps[peak] + off)); h1 = h2 - dt.timedelta(hours=win[peak])
                out.append({'region': R.id, 'en': p['en'], 'name': {l: city_name(p, l) for l in ('uz', 'ru', 'tr')}, 'date': d.isoformat(),
                            'mm': round(mm, 1), 'p': int(round(pm)), 'snow': bool(snow), 'level': 2 if mm >= 2 * lim else 1, 'peak': f'{h1:%H}–{h2:%H}'})
    return out


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
            if product != 'prob' and (R.T is None if product == 'temp' else getattr(R, 'Wd', None) is None if product == 'wind' else R.C is None): continue
            suf = '' if product == 'prob' else '_' + product
            fdir = out / 'frames' / f'{region}_{lang}{suf}'; fdir.mkdir(parents=True, exist_ok=True)
            for i, s in enumerate(sel):
                day = local_day(run, D['steps'][s], off, D['win'][s])
                draw_frame(R, D, s, lang, models, members, fdir / f'{i:03d}.png', product, com.get(day.isoformat(), ''))
            mp4 = out / f'{region}_{lang}{suf}.mp4'
            _video(fdir, mp4, fps)
            res.append({'region': region, 'lang': lang, 'product': product, 'video': mp4.name, 'frames': len(sel), 'name': NAMES[region][lang]})
            print(region, lang, product, 'ok', flush=True)
        res.append({'region': region, 'lang': lang, 'product': 'days', 'days': com, 'off': off, 'city': city_name(R.mains[lang], lang) if R.mains[lang] else ''})
        # the same daily comments for every labelled city of the country (the bot's city menu)
        cities = city_list(R, geo, lang)
        (out / 'cities').mkdir(exist_ok=True)
        json.dump({'region': region, 'lang': lang, 'off': off, 'cities': [{'name': city_name(c, lang), 'days': daily_comments(R, D, lang, off, c, area=False)} for c in cities]},
                  open(out / 'cities' / f'{region}_{lang}.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    try: res.append({'product': 'alerts', 'alerts': find_alerts(R, D, run)})
    except Exception as e: print(region, 'alerts:', e, flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('npz'); ap.add_argument('out')
    ap.add_argument('--regions', default=','.join(ORDER)); ap.add_argument('--langs', default='uz,ru,tr')
    ap.add_argument('--fps', type=float, default=1.0); ap.add_argument('--steps', default=''); ap.add_argument('--jobs', type=int, default=os.cpu_count() or 2)
    ap.add_argument('--globe-data', default='', help='site/data with forecast.json + clouds/ (temperature and clouds from charts.ecmwf.int)')
    ap.add_argument('--max-step', type=int, default=0)
    ap.add_argument('--wx', default='', help='wx.npz: GEFS mean temperature and cloud cover (preferred over --globe-data)')
    ap.add_argument('--products', default='prob,temp,cloud,wind')
    ap.add_argument('--geo', default='', help='boundary pack (default prob/geo_prob.json; continents: prob/geo_world.json)')
    ap.add_argument('--dpi', type=int, default=200, help='frame resolution: 200 → 1440×1800 (portrait 4:5), sharp when zoomed in')
    ap.add_argument('--width', type=int, default=1440, help='video width in pixels')
    ap.add_argument('--crf', type=int, default=24, help='video quality (lower = sharper, bigger files)')
    ap.add_argument('--append', action='store_true', help='add these maps to an existing manifest.json instead of replacing it')
    ap.add_argument('--city-videos', default='', help='regions that also get one precipitation video per city, e.g. UZ,KZ')
    ap.add_argument('--city-langs', default='ru,uz', help='languages of the city videos')
    ap.add_argument('--city-width', type=int, default=1080); ap.add_argument('--city-crf', type=int, default=27); ap.add_argument('--city-dpi', type=int, default=150)
    a = ap.parse_args()
    D = load(a.npz)
    P, models, members = probability(D)
    _CTX.update(D=D, P=P, models=models, members=members, dpi=a.dpi, width=a.width, crf=a.crf, city_width=a.city_width, city_crf=a.city_crf, city_dpi=a.city_dpi, geo=Geo(a.geo or None), wx=load_wx_npz(D, a.wx) if a.wx else load_wx(D, a.globe_data))
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
    alerts = [a for i in manifest if i.get('product') == 'alerts' for a in i['alerts']]
    manifest = [i for i in manifest if i.get('product') != 'alerts']
    if a.append and (out / 'alerts.json').exists(): alerts = [x for x in json.load(open(out / 'alerts.json')).get('items', []) if x['region'] not in a.regions.split(',')] + alerts
    json.dump({'run': D['run'], 'items': alerts}, open(out / 'alerts.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    print('alerts:', len(alerts), flush=True)
    M = {'run': D['run'], 'models': models, 'members': members, 'fps': a.fps, 'steps': [int(D['steps'][i]) for i in sel], 'win': [int(D['win'][i]) for i in sel], 'items': manifest}
    if a.append and (out / 'manifest.json').exists():
        old = json.load(open(out / 'manifest.json')); done = {i['region'] for i in manifest}
        M['items'] = [i for i in old.get('items', []) if i['region'] not in done] + manifest
    json.dump(M, open(out / 'manifest.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
