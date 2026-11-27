"""The chance of precipitation and the temperature over Uzbekistan for 15 days, in the look of the first Osmon video
(white map, blue patches of the chance of precipitation, Tashkent's bars under the map), made nicer: a branded header with
the time window, smooth motion between the windows, the chance and the temperature at twelve towns, the temperature line
over Tashkent's bars, an opening and a closing card with the bot's QR code.
Data: prob.npz and wx.npz of prob/fetch.py (all models: ECMWF IFS and AIFS, NOAA GFS and GEFS, DWD ICON; 3-hour windows
for the first 6 days, then 6-hour windows).
Usage: python tools/prob15_video.py prob.npz wx.npz out ru,uz  →  out/p15_{lang}.mp4"""
import sys, os, json, pathlib, shutil, subprocess, tempfile, datetime as dt, multiprocessing as mp
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import FancyBboxPatch, Rectangle
import matplotlib.patheffects as pe
from scipy.ndimage import zoom, gaussian_filter

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'prob'))
from render import load, probability, load_wx_npz  # noqa: E402

for f in (ROOT / 'prob' / 'fonts').glob('*.ttf'):
    try: matplotlib.font_manager.fontManager.addfont(str(f))
    except Exception: pass
_have = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
FONT = 'Inter' if 'Inter' in _have else 'DejaVu Sans'
plt.rcParams.update({'font.family': FONT})

W, H, DPI = 1920, 1080, 100
LEVELS = [10, 30, 50, 70, 90, 101]
RAIN = ['#d4e9f9', '#93c6ee', '#4a98e0', '#1c63c0', '#5b2fa8']  # the first video: light blues to dark blue, violet at 90–100 %
SNOW = ['#f1e3f5', '#dfb6ea', '#c486da', '#a055c2', '#6c2795']
MIX = ['#fde3ec', '#f6b9d2', '#e886b4', '#cc5593', '#96296e']  # wet snow, rain with snow: raspberry, between the blue rain and the violet snow
_PS = np.array([10, 20, 40, 60, 80, 95], float)  # the palettes' five colours sit in the middle of their bands; between them the colour flows
_ramp = lambda pal: np.array([matplotlib.colors.to_rgb(pal[0])] + [matplotlib.colors.to_rgb(c) for c in pal])
RR, MR, SR = _ramp(RAIN[:4] + ['#0f3a8c']), _ramp(MIX), _ramp(SNOW)  # the map's rain ends in deep blue (violet is the snow's)


def precip_rgba(P, sf, a_in=1.0):
    """The chance of precipitation as one smooth layer, no gaps and no steps: the colour flows with the chance (light → deep) and with
    the type — rain (blue), wet snow (raspberry), snow (violet) — by the snow share sf 0…1; the edge fades in from 6 % to 20 %."""
    col = lambda R: np.stack([np.interp(P, _PS, R[:, k]) for k in range(3)], -1)
    s = sf[..., None]; lo = np.clip(s * 2, 0, 1); hi = np.clip(s * 2 - 1, 0, 1)
    cr, cm, cs = col(RR), col(MR), col(SR)
    c = np.where(s < 0.5, cr * (1 - lo) + cm * lo, cm * (1 - hi) + cs * hi)
    al = np.clip((P - 6) / 14, 0, 1) ** 1.3 * (0.8 + 0.12 * np.clip((P - 20) / 60, 0, 1)) * a_in
    return np.dstack([c, al]).astype(np.float32)


# the temperature map's colours (like the professional weather maps): violet frost → blue → cyan around 0° → green → yellow → orange → red heat
TST = np.array([-40, -30, -24, -18, -12, -6, -2, 0, 2, 6, 10, 14, 18, 22, 26, 30, 35, 45], float)
TCL = np.array([matplotlib.colors.to_rgb(c) for c in ['#2b0a4e', '#5b2a86', '#7d4bb8', '#4c5fd0', '#2f86d8', '#38b3e0', '#7fd3ea', '#c8ecf2', '#d9f0c4', '#a7dc84',
                                                      '#6cc36a', '#c9dd52', '#f3dc4c', '#f9b23f', '#f27f33', '#df4a2b', '#b01d31', '#5c0b22']])


LANDC, SEAC = '#c9c6ad', '#3d6d96'  # the clouds' map: earth tones under white clouds, like a picture from space
TLV = np.arange(-50, 52, 2.0)  # 2° bands
TBC = None


def temp_rgb(T):
    return np.stack([np.interp(np.nan_to_num(T, nan=0), TST, TCL[:, k]) for k in range(3)], -1)


TBC = [tuple(c) for c in np.stack([np.interp((TLV[:-1] + TLV[1:]) / 2, TST, TCL[:, k]) for k in range(3)], -1)]


def grad_bar(fig, x, y, w, h, R):
    g = np.linspace(10, 100, 200); im = np.stack([np.interp(g, _PS, R[:, k]) for k in range(3)], -1)[None]
    bx = fig.add_axes([x, y, w, h]); bx.imshow(im, aspect='auto', interpolation='bilinear'); bx.axis('off')
    return bx


BAR_EMPTY = '#e7edf3'
INK, MUTED, FAINT, LINE = '#15202b', '#5b6876', '#98a3ae', '#dfe5ec'
NAVY, ORANGE, SEA = '#14233a', '#f08a24', '#e3eef8'
TEMP = '#e0601b'
TOWNS = [('Ташкент', 'Toshkent', 41.31, 69.28), ('Самарканд', 'Samarqand', 39.65, 66.96), ('Бухара', 'Buxoro', 39.77, 64.42), ('Нукус', 'Nukus', 42.46, 59.6),
         ('Ургенч', 'Urganch', 41.55, 60.63), ('Наманган', 'Namangan', 41.0, 71.67), ('Андижан', 'Andijon', 40.78, 72.34), ('Фергана', 'Farg‘ona', 40.39, 71.78),
         ('Карши', 'Qarshi', 38.86, 65.79), ('Термез', 'Termiz', 37.22, 67.28), ('Навои', 'Navoiy', 40.1, 65.38), ('Джизак', 'Jizzax', 40.12, 67.84)]
# where each town's label goes (offset in px from the dot, alignment), so the labels of the Fergana valley and of Bukhara–Navoi–Samarkand–Jizzakh do not cover each other
OFF = {'Ташкент': (-30, 6, 'right', 'center'), 'Самарканд': (26, -14, 'left', 'top'), 'Бухара': (-28, 0, 'right', 'center'), 'Нукус': (0, 28, 'center', 'bottom'),
       'Ургенч': (0, -28, 'center', 'top'), 'Наманган': (0, 30, 'center', 'bottom'), 'Андижан': (28, 6, 'left', 'center'), 'Фергана': (26, -14, 'left', 'top'),
       'Карши': (-26, -10, 'right', 'top'), 'Термез': (28, 0, 'left', 'center'), 'Навои': (-6, 28, 'right', 'bottom'), 'Джизак': (8, 28, 'left', 'bottom')}
TX = {'ru': dict(title='Вероятность осадков и температура · 15 дней', tz='по Ташкенту', day='день {i} из {n}', rain='дождь', snow='снег', mix='мокрый снег', wind='ветер', temp='температура', iso='изотермы через 5°', cloud='облачность', clear='ясно', overcast='сплошные тучи', title_c='Тучи и грозы · 15 дней', intro1_c='Тучи и грозы', title_t='Температура воздуха · 15 дней', chart_tt='{n}: температура по периодам, °C', chart_tc='{n}: облачность по периодам, %', intro1_t='Температура воздуха',
                 leg='Вероятность осадков (больше 0,2 мм) за период, %', models='Модели: ECMWF IFS и AIFS, NOAA GFS и GEFS, DWD ICON · {n} вариантов прогноза',
                 chart='Ташкент: вероятность осадков по периодам (столбики) и температура (линия)', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
                 intro1='Осадки и температура', intro2='на 15 дней по всему Узбекистану', end1='Погода в вашем районе и посёлке', end2='в Telegram-боте @ObHavo_ECMWF_bot'),
      'uz': dict(title='Yog‘ingarchilik ehtimoli va harorat · 15 kun', tz='Toshkent vaqti', day='{i}-kun / {n}', rain='yomg‘ir', snow='qor', mix='ho‘l qor', wind='shamol', temp='harorat', iso='har 5° izoterma', cloud='bulutlilik', clear='ochiq', overcast='qalin bulut', title_c='Bulut va momaqaldiroq · 15 kun', intro1_c='Bulut va momaqaldiroq', title_t='Havo harorati · 15 kun', chart_tt='{n}: davrlar bo‘yicha harorat, °C', chart_tc='{n}: davrlar bo‘yicha bulutlilik, %', intro1_t='Havo harorati',
                 leg='Davr ichida yog‘ingarchilik (0,2 mm dan ko‘p) ehtimoli, %', models='Modellar: ECMWF IFS va AIFS, NOAA GFS va GEFS, DWD ICON · {n} ta prognoz varianti',
                 chart='Toshkent: davrlar bo‘yicha yog‘in ehtimoli (ustunlar) va harorat (chiziq)', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'],
                 intro1='Yog‘ingarchilik va harorat', intro2='butun O‘zbekiston bo‘yicha 15 kunga', end1='Tumaningiz va qishlog‘ingiz ob-havosi', end2='Telegram-botda: @ObHavo_ECMWF_bot')}
MAP = (0.0, 0.205, 1.0, 0.701)  # the map: the full width, between the header and the legend
LAT0, LAT1 = 36.95, 45.95
COSL = np.cos(np.radians(41.4))
CTX = {}
FOG = None


def card(fig, x, y, w, h, fc, ec='none', r=10, lw=1.0, z=20, alpha=1.0):
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle=f'round,pad=0,rounding_size={r}', transform=None, facecolor=fc, edgecolor=ec, lw=lw, zorder=z, alpha=alpha))


def qr(url):
    try:
        import qrcode
        q = qrcode.QRCode(border=2); q.add_data(url); q.make(fit=True); return np.array(q.get_matrix(), bool)
    except Exception: return None


from matplotlib.path import Path as MPath
BOLT = MPath([(0.2, 1.0), (-0.55, -0.05), (-0.05, -0.05), (-0.35, -1.0), (0.6, 0.2), (0.08, 0.2), (0.55, 1.0), (0.2, 1.0)], closed=True)  # ⚡


def bolt(ax, x, y, size=520, z=9.6):
    ax.scatter([x], [y], marker=BOLT, s=size, c='#ffc21a', edgecolors='#5c3d00', linewidths=1.6, zorder=z)


def place(ax, items, fig):
    """Where each town's label goes: the first spot around its circle (preferred side first) that covers no temperature
    circle and no label already placed. items: [(lon, lat, text, fontsize, main, (dx, dy, ha, va) preferred)] → offsets."""
    ax.apply_aspect()
    k = fig.dpi / 72; circ = []
    for lo, la, txt, fs, main, pref in items:
        x, y = ax.transData.transform((lo, la)); circ.append((x, y, (31 if main else 25)))
    boxes, out = [], []
    for (lo, la, txt, fs, main, pref), (x, y, r) in zip(items, circ):
        w, h = len(txt) * fs * 0.6 * k + 14, fs * 1.5 * k + 8
        g = r + 8
        cands = [pref, (g, 0, 'left', 'center'), (-g, 0, 'right', 'center'), (0, g, 'center', 'bottom'), (0, -g, 'center', 'top'),
                 (g * 0.8, g * 0.8, 'left', 'bottom'), (-g * 0.8, g * 0.8, 'right', 'bottom'), (g * 0.8, -g * 0.8, 'left', 'top'), (-g * 0.8, -g * 0.8, 'right', 'top'),
                 (g + 30, 0, 'left', 'center'), (-g - 30, 0, 'right', 'center'), (0, g + 26, 'center', 'bottom'), (0, -g - 26, 'center', 'top')]
        best = None
        for dx, dy, ha, va in cands:
            bx0 = x + dx - (w if ha == 'right' else w / 2 if ha == 'center' else 0); by0 = y + dy - (h if va == 'top' else h / 2 if va == 'center' else 0)
            b = (bx0, by0, bx0 + w, by0 + h)
            hit = any(cx + cr > b[0] and cx - cr < b[2] and cy + cr > b[1] and cy - cr < b[3] for cx, cy, cr in circ) or \
                  any(not (b[2] < o[0] or b[0] > o[2] or b[3] < o[1] or b[1] > o[3]) for o in boxes)
            if not hit: best = (dx, dy, ha, va, b); break
        if best is None: dx, dy, ha, va = pref; best = (dx, dy, ha, va, (0, 0, 0, 0))
        boxes.append(best[4]); out.append(best[:4])
    return out


def relief_layer(x0, x1, la0, la1, w=1600, h=640):
    """Mountains, just noticeable: a soft hillshade (shadows grey, sunny slopes white) from the open terrain tiles (AWS Terrain Tiles,
    Mapzen terrarium); None when the tiles cannot be reached."""
    import io, math, concurrent.futures as cf_
    try:
        import requests
        from PIL import Image
        from matplotlib.colors import LightSource
    except Exception: return None
    z = int(np.clip(round(math.log2(360 / ((x1 - x0) / w * 256))), 4, 9)); n = 2 ** z
    tx = lambda lo: (lo + 180) / 360 * n; ty = lambda la: (1 - math.asinh(math.tan(math.radians(la))) / math.pi) / 2 * n
    X0, X1, Y0, Y1 = int(tx(x0)), int(tx(x1)), int(ty(la1)), int(ty(la0))
    if (X1 - X0 + 1) * (Y1 - Y0 + 1) > 400: return None
    def tile(xy):
        x, y = xy
        for _ in range(3):
            try:
                r = requests.get(f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x % n}/{y}.png', timeout=30)
                if r.ok:
                    a = np.asarray(Image.open(io.BytesIO(r.content)).convert('RGB'), float); return xy, a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
            except Exception: pass
        return xy, None
    big = np.zeros(((Y1 - Y0 + 1) * 256, (X1 - X0 + 1) * 256)); got = 0
    with cf_.ThreadPoolExecutor(16) as ex:
        for (x, y), e in ex.map(tile, [(x, y) for x in range(X0, X1 + 1) for y in range(Y0, Y1 + 1)]):
            if e is not None: big[(y - Y0) * 256:(y - Y0 + 1) * 256, (x - X0) * 256:(x - X0 + 1) * 256] = e; got += 1
    if not got: return None
    lon = np.linspace(x0, x1, w); lat = np.linspace(la1, la0, h)
    px = ((lon + 180) / 360 * n - X0) * 256; py = np.array([((1 - math.asinh(math.tan(math.radians(la))) / math.pi) / 2 * n - Y0) * 256 for la in lat])
    el = np.maximum(big[np.ix_(np.clip(py.astype(int), 0, big.shape[0] - 1), np.clip(px.astype(int), 0, big.shape[1] - 1))], 0)
    mpp = (x1 - x0) * 111e3 * math.cos(math.radians((la0 + la1) / 2)) / w
    hs = LightSource(azdeg=315, altdeg=40).hillshade(el, vert_exag=2.0, dx=mpp, dy=mpp) - math.sin(math.radians(40))
    out = np.zeros((h, w, 4), np.float32)
    shade = np.clip(-hs, 0, 1) * 0.22 + np.clip((el - 1500) / 3000, 0, 1) * 0.05  # the shaded slopes and the high mountains a little grey
    out[..., :3] = 0.35; out[..., 3] = np.clip(shade * 1.6, 0, 0.26)
    return out


def tcol(t):  # the colour of a temperature circle: violet in frost, blue when cold, green when cool, orange and red when warm
    stops = [(-15, '#4b2a8f'), (-5, '#2f5fc4'), (0, '#3f8fdd'), (6, '#2a9d8f'), (12, '#7cad3a'), (18, '#e3a21a'), (25, '#e0601b'), (32, '#c0262d')]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            a = np.clip((t - t0) / (t1 - t0), 0, 1); c0, c1 = np.array(matplotlib.colors.to_rgb(c0)), np.array(matplotlib.colors.to_rgb(c1)); return tuple(c0 + (c1 - c0) * a)
    return stops[-1][1]


def level(v, pal):
    return pal[int(np.clip(np.searchsorted(LEVELS, v, side='right') - 1, 0, 4))] if v >= LEVELS[0] else None


def draw(job):
    lang, i = job; C = CTX; V = C['videos'][lang]; fr = V['frames'][i]; X = TX[lang]
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI); fig.patch.set_facecolor('white')
    # the map
    ax = fig.add_axes(MAP); x0, x1 = C['lon_ext']; ax.set_xlim(x0, x1); ax.set_ylim(C['la0'], C['la1']); ax.set_aspect(1 / C['cosl']); ax.axis('off')
    CM = C.get('mode') == 'cloud'; SEA_ = SEAC if CM else SEA
    if C.get('land') is None and CM: ax.add_patch(Rectangle((x0, C['la0']), x1 - x0, C['la1'] - C['la0'], fc=LANDC, ec='none', zorder=0.1))  # (the axes are off: their own face is not drawn)
    if C.get('land') is not None:  # a continent: the sea as the background, the land on it
        ax.set_facecolor(SEA_ if C.get('globe') is None else 'white')
        if C.get('globe') is not None: ax.add_patch(matplotlib.patches.Polygon(C['globe'], closed=True, fc=SEA_, ec='#b9cfe3', lw=1.0, zorder=0.3))
        ax.add_collection(PolyCollection(C['land'], facecolors=LANDC if CM else '#fbfaf6', edgecolors='#b9cfe3', linewidths=0.5, zorder=0.4))
    for r in C['sea']: ax.fill(r[:, 0], r[:, 1], fc=SEA_, ec='#b9cfe3', lw=0.6, zorder=0.5)
    if C.get('relief') is not None:  # the mountains, just noticeable
        ax.imshow(C['relief'], extent=(x0, x1, C['la0'], C['la1']), origin='upper', interpolation='bilinear', aspect='auto', zorder=0.6)
        ax.set_xlim(x0, x1); ax.set_ylim(C['la0'], C['la1']); ax.set_aspect(1 / C['cosl'])
    P, T = fr['P'], fr['T']; a_in = fr.get('fade', 1.0); TM = C.get('mode') == 'temp'
    sf = np.clip((1.2 - T) / 2.6, 0, 1)  # the share of snow: rain above about +1°, wet snow around 0°, snow below about −1.5°
    LO, LA = C['LONu'], C['LATu']
    if TM:  # the temperature map, as on a forecaster's chart: 2° colour bands, the relief shaded through, labelled isotherms, the warmest and the coldest point
        Tf_ = np.where(np.isfinite(T), T, np.nan)
        ax.contourf(LO, LA, Tf_, levels=TLV, colors=TBC, alpha=0.93 * a_in, zorder=1.6, antialiased=True, extend='both')
        if C.get('relief') is not None:  # the mountains seen through the colour
            ax.imshow(C['relief'], extent=(x0, x1, C['la0'], C['la1']), origin='upper', interpolation='bilinear', aspect='auto', zorder=1.62, alpha=0.9)
        cs = ax.contour(LO, LA, Tf_, levels=[l for l in range(-50, 51, 5) if l != 0], colors=['#1d2733'], linewidths=0.55, alpha=0.38 * a_in, zorder=1.7)
        try: ax.clabel(cs, cs.levels, inline=True, fmt=lambda v: f'{v:+.0f}°'.replace('+0°', '0°'), fontsize=9, colors=['#1d2733'], inline_spacing=4)
        except Exception: pass
        ax.set_xlim(x0, x1); ax.set_ylim(C['la0'], C['la1']); ax.set_aspect(1 / C['cosl'])
        sx_, sy_ = x1 - x0, C['la1'] - C['la0']  # inside the visible map, away from its edges and the corner texts
        m_ = np.isfinite(Tf_) & ((LO > x0 + 0.06 * sx_) & (LO < x1 - 0.06 * sx_))[None, :] & ((LA > C['la0'] + 0.12 * sy_) & (LA < C['la1'] - 0.08 * sy_))[:, None]
        if m_.any():
            for fn, col, sym in ((np.nanargmax, '#c0262d', '▲'), (np.nanargmin, '#2350b5', '▼')):
                k_ = fn(np.where(m_, Tf_, np.nan)); yy, xx = np.unravel_index(k_, Tf_.shape)
                ax.annotate(f"{sym} {Tf_[yy, xx]:+.0f}°".replace('+0°', '0°'), (LO[xx], LA[yy]), ha='center', va='center', fontsize=12.5, fontweight='bold', color=col, zorder=7.5,
                            bbox=dict(boxstyle='round,pad=0.25,rounding_size=0.5', fc='white', ec=col, lw=1.4, alpha=0.9 * a_in))
    if CM and fr.get('Cl') is not None:  # the clouds' map: white clouds, thicker where the sky is more covered
        cl = np.zeros(fr['Cl'].shape + (4,), np.float32); cl[..., :3] = 1.0; cl[..., 3] = np.clip((fr['Cl'] - 0.08) / 0.85, 0, 1) ** 1.1 * 0.93 * a_in
        ax.imshow(cl, extent=(LO[0], LO[-1], LA[0], LA[-1]), origin='lower', interpolation='bicubic', aspect='auto', zorder=1.5)
        ax.set_xlim(x0, x1); ax.set_ylim(C['la0'], C['la1']); ax.set_aspect(1 / C['cosl'])
    elif fr.get('Cl') is not None and not TM:  # clouds: a soft grey veil under the rain, thicker where the sky is more covered
        cl = np.zeros(fr['Cl'].shape + (4,), np.float32); cl[..., :3] = (0.6, 0.64, 0.7); cl[..., 3] = np.clip((fr['Cl'] - 0.5) / 0.5, 0, 1) ** 1.3 * 0.32 * a_in
        ax.imshow(cl, extent=(LO[0], LO[-1], LA[0], LA[-1]), origin='lower', interpolation='bicubic', aspect='auto', zorder=1.5)
        ax.set_xlim(x0, x1); ax.set_ylim(C['la0'], C['la1']); ax.set_aspect(1 / C['cosl'])
    if P.max() >= 6 and not TM and not CM:  # (the clouds video shows the clouds and thunderstorms only)
        ax.imshow(precip_rgba(P, sf, a_in * (0.62 if CM else 1)), extent=(LO[0], LO[-1], LA[0], LA[-1]), origin='lower', interpolation='bicubic', aspect='auto', zorder=2)
        ax.set_xlim(x0, x1); ax.set_ylim(C['la0'], C['la1']); ax.set_aspect(1 / C['cosl'])
        if P.max() >= 50: ax.contour(LO, LA, P, levels=[50, 90], colors=['#ffffff'], linewidths=0.6, alpha=0.4 * a_in, zorder=2.05)
    if fr.get('wind') is not None:  # the wind: thin streams along it, longer and darker where it is stronger
        sg, al, lw = fr['wind']
        wc = (1, 1, 1) if TM or CM else (0.16, 0.24, 0.34); wk = 1.6 if TM else 1.0  # on the temperature colours: white streams
        if len(sg): ax.add_collection(LineCollection(sg, colors=[wc + (min(1, a_ * wk) * a_in,) for a_ in al], linewidths=lw, zorder=2.4, capstyle='round', joinstyle='round'))
    # 0° line: where rain turns to snow
    if not CM and np.nanmin(T) < 0 < np.nanmax(T):
        ax.contour(LO, LA, T, levels=[0], colors=['#3d7be0'], linewidths=1.3, linestyles=[(0, (5, 3))], alpha=0.75 * a_in, zorder=2.6)
    for rings, col, lw, z in C['borders']: ax.add_collection(LineCollection(rings, colors=col, linewidths=lw, zorder=z, capstyle='round', joinstyle='round'))
    if fr.get('Fg') is not None and not TM and fr['Fg'].max() >= 0.35:  # fog: a pale haze with fine horizontal lines, like on a weather chart
        fg = np.zeros(fr['Fg'].shape + (4,), np.float32); fg[..., :3] = (0.93, 0.9, 0.84); fg[..., 3] = np.clip((fr['Fg'] - 0.3) / 0.5, 0, 1) * 0.8 * a_in
        ax.imshow(fg, extent=(LO[0], LO[-1], LA[0], LA[-1]), origin='lower', interpolation='bicubic', aspect='auto', zorder=2.7)
        with matplotlib.rc_context({'hatch.color': '#a39a8a', 'hatch.linewidth': 1.0}):
            ax.contourf(LO, LA, fr['Fg'], levels=[0.5, 2], colors='none', hatches=['---'], zorder=2.75)
        ax.set_xlim(x0, x1); ax.set_ylim(C['la0'], C['la1']); ax.set_aspect(1 / C['cosl'])
    # thunderstorms: a lightning bolt where they are likely (rain likely and enough energy in the air)
    for bx_, by_ in ([] if TM else fr.get('storms', [])): bolt(ax, bx_, by_, 1500, 7.5)
    # the towns: dot, name, chance and temperature
    L = 0 if lang == 'ru' else 1
    cc_ = {}
    if CM and fr.get('Cl') is not None:  # the towns show the cloud cover
        cc_ = {tw[0]: float(fr['Cl'][np.abs(LA - tw[2]).argmin(), np.abs(LO - tw[3]).argmin()]) * 100 for tw in C['towns']}
    offs = place(ax, [(tw[3], tw[2],  (tw[L] if TM else f"{tw[L]} · {cc_.get(tw[0], 0):.0f}%" if CM else f"{tw[L]}  {p_:.0f}%") + (' · туман' if fg_ else ''), 17 if tw[0] == C['main'] else 13.5, tw[0] == C['main'], OFF.get(tw[0], (24, 0, 'left', 'center'))) for tw, (p_, t_, st_, fg_) in zip(C['towns'], fr['towns'])], fig)
    for tw, (p_, t_, st_, fg_), (dx, dy, ha, va) in zip(C['towns'], fr['towns'], offs):
        main = tw[0] == C['main']
        col = level(p_, SNOW if t_ <= 0.5 else RAIN)
        tt = f"{t_:+.0f}°".replace('+0°', '0°').replace('-0°', '0°')
        ax.annotate(tt, (tw[3], tw[2]), ha='center', va='center', fontsize=15 if main else 11.5, fontweight='bold', color='white', zorder=8.5,
                    bbox=dict(boxstyle='circle,pad=0.32' if not main else 'circle,pad=0.38', fc=tcol(t_), ec=ORANGE if main else 'white', lw=3 if main else 2))
        if st_ and not TM: bolt(ax, tw[3] + 0.36 * C['deg'], tw[2] + 0.32 * C['deg'], 1100 if main else 850, 9.7)
        fs = 17 if main else 13.5
        txt =  (tw[L] if TM else f"{tw[L]} · {cc_.get(tw[0], 0):.0f}%" if CM else f"{tw[L]}  {p_:.0f}%") + ((' · туман' if lang == 'ru' else ' · tuman') if fg_ else '')
        an = ax.annotate(txt, (tw[3], tw[2]), xytext=(dx, dy), textcoords='offset pixels', ha=ha, va=va, fontsize=fs, fontweight='bold' if main else 'semibold', color='#1f2933' if main else '#2f3a46', zorder=9,
                         bbox=dict(boxstyle='round,pad=0.3,rounding_size=0.7', fc='#f1f3f5', ec=ORANGE if main else 'none', lw=2.0 if main else 0, alpha=0.72))
    ax.text(0.995, 0.01, 't.me/ObHavo_ECMWF_bot', transform=ax.transAxes, ha='right', va='bottom', fontsize=11, color=FAINT, zorder=9)
    for lb_, lo_, la_ in C.get('names', []): ax.text(lo_, la_, lb_, fontsize=10, color='#8a96a3', ha='center', va='center', zorder=3.6, style='italic')
    # header
    fig.patches.append(Rectangle((0, 0.906), 1, 0.094, transform=fig.transFigure, fc=NAVY, ec='none', zorder=-1))
    fig.text(0.016, 0.953, 'OSMON', fontsize=22, fontweight='bold', color=ORANGE, va='center')
    fig.text(0.093, 0.953, (C['title'][lang] if C.get('title') else X['title']).replace(X['title'], X['title_t'] if TM else X['title_c'] if CM else X['title']), fontsize=22, fontweight='bold', color='white', va='center')
    fig.text(0.984, 0.968, fr['when'], fontsize=24, fontweight='bold', color='#ffd29c', ha='right', va='center')
    fig.text(0.984, 0.928, (C['tzl'][lang] if C.get('tzl') else X['tz']) + ' · ' + fr['day'], fontsize=14, color='#a9bdd6', ha='right', va='center')
    # progress over the 15 days
    fig.patches.append(Rectangle((0, 0.903), 1, 0.004, transform=fig.transFigure, fc='#2c3e57', ec='none', zorder=0))
    fig.patches.append(Rectangle((0, 0.903), fr['prog'], 0.004, transform=fig.transFigure, fc=ORANGE, ec='none', zorder=0.1))
    # legend
    if CM:  # the cloud cover, the precipitation under the clouds, the wind
        fig.text(0.016, 0.183, X['cloud'], fontsize=13, fontweight='bold', color=INK, va='center')
        g_ = np.linspace(0, 1, 200); cb_ = np.array(matplotlib.colors.to_rgb(LANDC)) * (1 - g_[:, None] ** 1.1 * 0.93) + g_[:, None] ** 1.1 * 0.93
        bx_ = fig.add_axes([0.11, 0.171, 0.24, 0.024]); bx_.imshow(cb_[None], aspect='auto', interpolation='bilinear'); bx_.axis('off')
        for v_, t_ in ((0.02, X['clear']), (0.98, X['overcast'])): fig.text(0.11 + 0.24 * v_, 0.183, t_, fontsize=9.5, fontweight='bold', color=INK, ha='left' if v_ < 0.5 else 'right', va='center')
        xb = 0.39
        fig.add_artist(matplotlib.lines.Line2D([xb, xb + 0.008, xb + 0.016, xb + 0.024], [0.178, 0.186, 0.181, 0.188], color='#2a3d57', lw=1.3, alpha=0.6, transform=fig.transFigure)); fig.text(xb + 0.03, 0.183, X['wind'], fontsize=12, color=MUTED, va='center')
        lg = fig.add_axes([xb + 0.075, 0.165, 0.02, 0.036]); lg.set_xlim(-1, 1); lg.set_ylim(-1.2, 1.2); lg.axis('off'); bolt(lg, 0, 0, 600)
        fig.text(xb + 0.097, 0.183, 'гроза' if lang == 'ru' else 'momaqaldiroq', fontsize=12, color=MUTED, va='center')
    elif TM:  # the temperature scale, the isotherms, the wind
        fig.text(0.016, 0.183, X['temp'], fontsize=13, fontweight='bold', color=INK, va='center')
        g_ = np.floor(np.linspace(-30, 39.99, 350) / 2) * 2 + 1; bx_ = fig.add_axes([0.11, 0.171, 0.42, 0.024]); bx_.imshow(temp_rgb(g_)[None], aspect='auto', interpolation='nearest', extent=(-30, 40, 0, 1)); bx_.axis('off')
        for v_ in range(-30, 41, 10): fig.text(0.11 + 0.42 * (v_ + 30) / 70 + (0.008 if v_ == -30 else -0.008 if v_ == 40 else 0), 0.183, f'{v_:+d}°'.replace('+0°', '0°'), fontsize=9.5, fontweight='bold', color='white' if v_ <= -20 or v_ >= 30 else INK, ha='center', va='center')
        fig.add_artist(matplotlib.lines.Line2D([0.548, 0.568], [0.183, 0.183], color='#9aa5b1', lw=1.2, transform=fig.transFigure)); fig.text(0.573, 0.183, X['iso'], fontsize=12, color=MUTED, va='center')
        fig.add_artist(matplotlib.lines.Line2D([0.675, 0.698], [0.183, 0.183], color='#3d7be0', lw=1.6, ls=(0, (4, 2.5)), transform=fig.transFigure)); fig.text(0.703, 0.183, '0°', fontsize=12, color=MUTED, va='center')
        if fr.get('wind') is not None:
            fig.add_artist(matplotlib.lines.Line2D([0.74, 0.748, 0.756, 0.764], [0.178, 0.186, 0.181, 0.188], color='#2a3d57', lw=1.3, alpha=0.6, transform=fig.transFigure)); fig.text(0.77, 0.183, X['wind'], fontsize=12, color=MUTED, va='center')
    else:
        xb = 0.016
        for R_, nm in ((RR, X['rain']), (MR, X['mix']), (SR, X['snow'])):  # the three types as smooth bars, 10 → 100 %
            fig.text(xb, 0.183, nm, fontsize=13, fontweight='bold', color=INK, va='center'); xb += 0.0068 * len(nm) + 0.009
            grad_bar(fig, xb, 0.171, 0.082, 0.024, R_)
            fig.text(xb + 0.004, 0.183, '10', fontsize=9.5, fontweight='bold', color=INK, va='center'); fig.text(xb + 0.078, 0.183, '100%', fontsize=9.5, fontweight='bold', color='white', va='center', ha='right')
            xb += 0.094
        if fr.get('wind') is not None:
            fig.add_artist(matplotlib.lines.Line2D([xb + 0.004, 0.012 + xb, 0.02 + xb, 0.028 + xb], [0.178, 0.186, 0.181, 0.188], color='#2a3d57', lw=1.3, alpha=0.6, transform=fig.transFigure))
            fig.text(xb + 0.033, 0.183, X['wind'], fontsize=12, color=MUTED, va='center')
        fig.add_artist(matplotlib.lines.Line2D([0.62, 0.645], [0.183, 0.183], color='#3d7be0', lw=1.6, ls=(0, (4, 2.5)), transform=fig.transFigure))
        fig.text(0.65, 0.183, '0°' + (' — дождь / снег' if lang == 'ru' else ' — yomg‘ir / qor'), fontsize=12, color=MUTED, va='center')
        fig.patches.append(FancyBboxPatch((0.74, 0.171), 0.036, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc='#b9bfc7', ec='none'))
        fig.text(0.781, 0.183, 'тучи' if lang == 'ru' else 'bulut', fontsize=12, color=MUTED, va='center')
        lg = fig.add_axes([0.826, 0.165, 0.02, 0.036]); lg.set_xlim(-1, 1); lg.set_ylim(-1.2, 1.2); lg.axis('off'); bolt(lg, 0, 0, 600)
        fig.text(0.848, 0.183, 'гроза' if lang == 'ru' else 'momaqaldiroq', fontsize=12, color=MUTED, va='center')
        if C.get('land') is None:
          with matplotlib.rc_context({'hatch.color': '#a39a8a', 'hatch.linewidth': 1.0}):
            fig.patches.append(FancyBboxPatch((0.918, 0.171), 0.024, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc='#efe8dc', ec='#cfc5b4', hatch='---', lw=0.6))
          fig.text(0.945, 0.183, 'туман' if lang == 'ru' else 'tuman', fontsize=12, color=MUTED, va='center')
    ax.text(0.005, 0.01, X['models'].format(n=C['members']), transform=ax.transAxes, ha='left', va='bottom', fontsize=10, color=FAINT, zorder=9)
    # Tashkent: bars of the chance, the temperature line
    mt = next((tw for tw in C['towns'] if tw[0] == C['main']), C['towns'][0])[0 if lang == 'ru' else 1]
    ctitle = X['chart_tt'].format(n=mt) if TM else X['chart_tc'].format(n=mt) if CM else (C['chart_t'][lang] if C.get('chart_t') else X['chart'])
    fig.text(0.016, 0.152, ctitle, fontsize=12, fontweight='bold', color=INK, va='center')
    bx = fig.add_axes([0.035, 0.035, 0.93, 0.1]); bx.set_facecolor('none')
    Xc, Wn, Pt, Tt = C['bx'], C['bw'], C['tp'], C['tt']
    if TM:  # the temperature video: the main town's temperature only — bars in the map's colours up to the line
        Pt = Tt; cols = [tuple(c_) for c_ in temp_rgb(np.asarray(Tt))]
    elif CM:  # the clouds video: the main town's cloud cover only, light (few clouds) → dark grey (overcast)
        Pt = C['tc']; cols = [(0.86 - 0.5 * c_ / 100, 0.88 - 0.48 * c_ / 100, 0.91 - 0.44 * c_ / 100) for c_ in Pt]
    else: cols = [(level(p_, SNOW if t_ <= 0.5 else RAIN) or BAR_EMPTY) for p_, t_ in zip(Pt, Tt)]
    if TM:
        tlo_, thi_ = np.nanmin(Tt), np.nanmax(Tt); pd_ = max(2, (thi_ - tlo_) * 0.2); base_ = tlo_ - pd_
        bx.bar(Xc, np.asarray(Tt) - base_, bottom=base_, width=Wn * 0.8, color=cols, zorder=2)
    else: bx.bar(Xc, np.maximum(Pt, 2), width=Wn * 0.8, color=cols, zorder=2)
    s = fr['s']; bx.axvspan(Xc[s] - Wn[s] / 2, Xc[s] + Wn[s] / 2, color=ORANGE, alpha=0.18, lw=0, zorder=1)
    bx.add_patch(Rectangle((Xc[s] - Wn[s] / 2, 0), Wn[s], 100, fill=False, ec=ORANGE, lw=2, zorder=5))
    if TM:
        bx.set_ylim(base_, thi_ + pd_); tk_ = [v for v in np.arange(np.ceil(base_ / 5) * 5, thi_ + pd_, 5)][::max(1, int((thi_ - base_) / 15) + 1)]
        bx.set_yticks(tk_); bx.set_yticklabels([f'{v:+.0f}°'.replace('+0°', '0°') for v in tk_], fontsize=10, color=FAINT)
    else: bx.set_ylim(0, 100); bx.set_yticks([0, 50, 100]); bx.set_yticklabels(['0', '50', '100%'], fontsize=10, color=FAINT)
    bx.set_xlim(Xc[0] - Wn[0], Xc[-1] + Wn[-1] / 2); bx.tick_params(length=0)
    if TM: bx.patches[-1].set_height(thi_ + pd_ - base_); bx.patches[-1].set_y(base_)  # the frame of the current period spans the axis
    for d0, lab in C['days']: bx.axvline(d0, color=LINE, lw=0.9, zorder=0)
    bx.set_xticks([d + 12 for d, _ in C['days']]); bx.set_xticklabels([lab[lang] for _, lab in C['days']], fontsize=10.5, color=MUTED, linespacing=1.05)
    for sp in bx.spines.values(): sp.set_visible(False)
    tx = bx.twinx(); tlo, thi = np.nanmin(Tt), np.nanmax(Tt); pad = max(2, (thi - tlo) * 0.2)
    if TM: tlo, thi, pad = base_ + pd_, thi_, pd_  # the line on the same scale as the bars
    if CM:  # the clouds video: the cover of the current period written over its bar, no temperature line
        bx.annotate(f"{Pt[s]:.0f}%", (Xc[s], min(Pt[s], 88)), xytext=(0, 6), textcoords='offset points', ha='center', fontsize=13, fontweight='bold', color=INK, zorder=8,
                    path_effects=[pe.withStroke(linewidth=3, foreground='white')])
    tx.plot(Xc, Tt, color=TEMP, lw=2.2, zorder=6, solid_capstyle='round', alpha=0 if CM else 1); tx.set_ylim(tlo - pad, thi + pad)
    if not CM: tx.plot([Xc[s]], [fr['tash_t']], 'o', ms=9, color=TEMP, mec='white', mew=2, zorder=7)
    if not CM: tx.annotate(f"{fr['tash_t']:+.0f}°".replace('+0°', '0°'), (Xc[s], fr['tash_t']), xytext=(10, 4), textcoords='offset points', ha='left', fontsize=13, fontweight='bold', color=TEMP, zorder=8,
                path_effects=[pe.withStroke(linewidth=3, foreground='white')])
    tx.set_yticks([]); [sp.set_visible(False) for sp in tx.spines.values()]
    # the opening and the closing cards
    if fr.get('card') == 'intro':
        a = fr['a']; fig.patches.append(Rectangle((0, 0.205), 1, 0.701, transform=fig.transFigure, fc='white', alpha=0.86 * a, ec='none', zorder=30))
        fig.text(0.5, 0.64, 'OSMON', fontsize=44, fontweight='bold', color=ORANGE, ha='center', va='center', alpha=a, zorder=31)
        fig.text(0.5, 0.56, X['intro1_t' if TM else 'intro1_c' if CM else 'intro1'], fontsize=40, fontweight='bold', color=INK, ha='center', va='center', alpha=a, zorder=31)
        fig.text(0.5, 0.49, (C.get('intro2') or {}).get(lang) or X['intro2'], fontsize=26, color=MUTED, ha='center', va='center', alpha=a, zorder=31)
    if fr.get('card') == 'end':
        fig.patches.append(Rectangle((0, 0.205), 1, 0.701, transform=fig.transFigure, fc='white', alpha=0.9, ec='none', zorder=30))
        fig.text(0.38, 0.70, 'OSMON', fontsize=44, fontweight='bold', color=ORANGE, ha='center', va='center', zorder=31)
        fig.text(0.38, 0.60, X['end1'], fontsize=30, fontweight='bold', color=INK, ha='center', va='center', zorder=31)
        fig.text(0.38, 0.53, X['end2'], fontsize=26, color=MUTED, ha='center', va='center', zorder=31)
        Q = C['qr']
        if Q is not None:
            qa = fig.add_axes([0.66, 0.36, 0.2 * H / W * 1.0, 0.44]); qa.imshow(~Q, cmap='gray', interpolation='nearest'); qa.axis('off'); qa.set_zorder(32)
    fig.savefig(pathlib.Path(V['dir']) / f'{i:04d}.png', dpi=DPI, facecolor='white')
    plt.close(fig)


def encode(lang):
    V = CTX['videos'][lang]; fd = pathlib.Path(V['dir'])
    lst = fd / 'list.txt'; lst.write_text(''.join(f"file '{i:04d}.png'\nduration {fr['d']}\n" for i, fr in enumerate(V['frames'])) + f"file '{len(V['frames']) - 1:04d}.png'\n")
    out = pathlib.Path(V['out']); tmp = out.with_name('.' + out.name + '.part.mp4')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-map', '0:v', '-map', '1:a',
                    '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-crf', '20', '-maxrate', '1600k', '-bufsize', '3200k',
                    '-preset', 'slow', '-tune', 'animation', '-c:a', 'aac', '-b:a', '48k', '-shortest', '-movflags', '+faststart', str(tmp)], check=True)
    tmp.replace(out); shutil.rmtree(fd)
    try:  # the weather's sound (prob/sound.py): rain, snow and thunder of the main town for the precipitation video, a calm pad for the temperature, soft air for the clouds
        import sound
        C = CTX; mi = next((k for k, tw in enumerate(C['towns']) if tw[0] == C['main']), 0); lv = []
        for fr in V['frames']:
            p_, t_, st_, _f = fr['towns'][mi]; l_ = sound.from_series([p_], [t_], [3.0])[0]; l_['storm'] = 1.0 if st_ else 0.0
            if fr.get('Cl') is not None: tw = C['towns'][mi]; l_['cloud'] = float(np.clip(fr['Cl'][np.abs(C['LATu'] - tw[2]).argmin(), np.abs(C['LONu'] - tw[3]).argmin()], 0, 1))
            lv += [l_] * max(1, int(round(fr['d'] / 0.1)))
        wav = str(out) + '.wav'; sound.track(lv, 0.1, wav, mode={'temp': 'temp', 'cloud': 'cloud'}.get(C.get('mode'), 'precip')); sound.mux(out, wav)
    except Exception as e: print('sound', e, flush=True)
    return f'{out} {out.stat().st_size // 1024} KB'


def wind_streams(seq, WX, lat_s, lon0, dg, ext, la0, la1, cosl, TF=None, TI=None, NP=None, TR=7):
    """Streams of the wind (GEFS 10 m, the window's mean, eased between windows): particles carried by the wind from frame to frame,
    each drawn as its last few positions — a soft moving line, longer and darker where the wind is stronger (like Ventusky).
    The particles move in longitude/latitude; on a continent's map they are projected for drawing."""
    from scipy.ndimage import map_coordinates
    rng = np.random.default_rng(7); Ug = np.nan_to_num(WX['U'][:, ::-1]); Vg = np.nan_to_num(WX['V'][:, ::-1])
    Ug = np.stack([gaussian_filter(u, 1.0) for u in Ug]); Vg = np.stack([gaussian_filter(v, 1.0) for v in Vg])
    wm = (ext[1] - ext[0]) * (1 if TF else 111320 * cosl)  # the map's width in metres
    dt_ = 26 * wm / 1920 / 10  # 10 m/s moves a particle ~26 px per frame
    NP = NP or (1500 if TF else 1000)
    def seed(n):
        x = rng.uniform(*ext, n); y = rng.uniform(la0, la1, n)
        return TI.transform(x, y) if TI else (x, y)
    def draw_xy(lo, la): return TF.transform(lo, la) if TF else (lo, la)
    lo, la = seed(NP); lo, la = np.asarray(lo, float), np.asarray(la, float)
    life = rng.integers(25, 70, NP); age = rng.integers(0, 25, NP)
    hx = [np.asarray(draw_xy(lo, la)).T]; out = []
    win_of = {}; cnt = {}
    for e in seq: win_of.setdefault(e[0], e[1]); cnt[e[0]] = cnt.get(e[0], 0) + 1
    for e in seq:
        n_, i, k = e[0], e[1], e[4]; j = win_of.get(n_ + 1, i); a = k / cnt[n_]
        U, V = (1 - a) * Ug[i] + a * Ug[j], (1 - a) * Vg[i] + a * Vg[j]
        fy, fx = (la - lat_s[0]) / dg, (lo - lon0) / dg
        u = map_coordinates(U, [fy, fx], order=1, mode='nearest'); v = map_coordinates(V, [fy, fx], order=1, mode='nearest')
        lo = lo + u * dt_ / (111320 * np.maximum(np.cos(np.radians(la)), 0.2)); la = la + v * dt_ / 110540; age += 1
        p = np.asarray(draw_xy(lo, la)).T
        # where the particles have gathered (a low draws them in), the extra ones go: the streams stay even
        cx_ = np.clip(((p[:, 0] - ext[0]) / (ext[1] - ext[0]) * 40).astype(int), 0, 39); cy_ = np.clip(((p[:, 1] - la0) / (la1 - la0) * 22).astype(int), 0, 21)
        cell = cx_ * 22 + cy_; cnt_ = np.bincount(cell, minlength=880); crowd = cnt_[cell] > 3.0 * NP / 880
        crowd &= rng.random(NP) < 0.35
        gone = (age > life) | crowd | (p[:, 0] < ext[0]) | (p[:, 0] > ext[1]) | (p[:, 1] < la0) | (p[:, 1] > la1) | ~np.isfinite(p).all(1)
        if gone.any():
            nl, na = seed(int(gone.sum())); lo[gone], la[gone] = nl, na; age[gone] = 0; life[gone] = rng.integers(25, 70, int(gone.sum()))
            p[gone] = np.asarray(draw_xy(lo[gone], la[gone])).T
        hx.append(p); hx = hx[-TR:]
        for h_ in hx[:-1]: h_[gone] = p[gone]  # a new particle starts without a tail
        H_ = np.stack(hx, 1); sp = np.hypot(u, v)
        jump = np.abs(np.diff(H_, axis=1)).max(axis=(1, 2)) > 0.06 * (ext[1] - ext[0])  # a particle that jumped (across the date line, the globe's edge): no long false line
        if jump.any():
            for h_ in hx: h_[jump] = p[jump]
            H_ = np.stack(hx, 1)
        fade = np.sin(np.pi * np.clip(age / life, 0, 1)) ** 0.7
        al = np.clip(sp / 12, 0.2, 1) * 0.34 * fade; lw = 0.55 + 0.75 * np.clip(sp / 15, 0, 1)
        m = (al > 0.02) & (np.abs(np.diff(H_, axis=1)).sum((1, 2)) > 0)
        out.append((H_[m].astype(np.float32), al[m], lw[m]))
    return out


def main(npz, wxp, outd, langs, only=None, view=None):
    """view (optional): the map of another country or place — lat (south, north), lc (centre longitude), towns [(ru, uz, lat, lon)], main (ru name),
    borders [(rings, colour, width, z)], names [(label, lon, lat)], title/tzl/chart_t {lang: text}, off (hours from UTC), stem (file name)."""
    view = view or {}; mode = view.get('mode') or os.environ.get('P15_MODE', 'prob')
    towns = view.get('towns', TOWNS); AR = (MAP[2] * W) / (MAP[3] * H); proj = view.get('proj'); TF = None; DEG = 1.0
    if proj:  # a continent: an equal-area map (Lambert azimuthal) around its centre — no stretching towards the poles
        from pyproj import Transformer
        TF = Transformer.from_crs('EPSG:4326', proj, always_xy=True); TI = Transformer.from_crs(proj, 'EPSG:4326', always_xy=True)
        b_ = view['bounds']; e_ = np.linspace(0, 1, 80)
        elo = np.r_[b_[0] + (b_[1] - b_[0]) * e_, b_[0] + (b_[1] - b_[0]) * e_, np.full(80, b_[0]), np.full(80, b_[1])]
        ela = np.r_[np.full(80, b_[2]), np.full(80, b_[3]), b_[2] + (b_[3] - b_[2]) * e_, b_[2] + (b_[3] - b_[2]) * e_]
        ex_, ey_ = TF.transform(elo, ela); x0_, x1_, y0_, y1_ = min(ex_), max(ex_), min(ey_), max(ey_)
        cx_, cy_ = (x0_ + x1_) / 2, (y0_ + y1_) / 2; w_, h_ = (x1_ - x0_) * 1.04, (y1_ - y0_) * 1.04
        if w_ / h_ > AR: h_ = w_ / AR
        else: w_ = h_ * AR
        ext = (cx_ - w_ / 2, cx_ + w_ / 2); la0, la1 = cy_ - h_ / 2, cy_ + h_ / 2; cosl = 1.0; span = w_; DEG = 111000.0
        gx_, gy_ = np.meshgrid(np.linspace(*ext, 90), np.linspace(la0, la1, 60)); glo_, gla_ = TI.transform(gx_, gy_)
        crop = (np.nanmin(glo_), np.nanmax(glo_), max(-89.5, np.nanmin(gla_)), min(89.5, np.nanmax(gla_)))
        towns = [(t[0], t[1]) + tuple(TF.transform(t[3], t[2])[::-1]) for t in towns]  # (ru, uz, y, x): the code below reads them as (lat, lon)
    else:
        la0, la1 = view.get('lat', (LAT0, LAT1)); cosl = np.cos(np.radians((la0 + la1) / 2))
        span = (la1 - la0) / cosl * AR; lc = view.get('lc', 64.8); ext = (lc - span / 2, lc + span / 2); crop = (ext[0], ext[1], la0, la1)
    D = load(npz); g = D['grid'].item(); lon = g['lon0'] + np.arange(g['W']) * g['d']; lat = g['lat0'] - np.arange(g['H']) * g['d']
    # only the map's box (+ a margin) is kept, before anything is computed: the whole grid would not fit in memory
    ci = np.flatnonzero((lon >= crop[0] - 2) & (lon <= crop[1] + 2)); ri = np.flatnonzero((lat >= crop[2] - 2) & (lat <= crop[3] + 2))
    for k, a_ in list(D.items()):
        if isinstance(a_, np.ndarray) and a_.ndim >= 2 and a_.shape[-2:] == (g['H'], g['W']): D[k] = a_[..., ri[0]:ri[-1] + 1, ci[0]:ci[-1] + 1]
    D['grid'] = np.array(dict(g, lon0=float(lon[ci[0]]), lat0=float(lat[ri[0]]), W=len(ci), H=len(ri)), dtype=object)
    lon, lat = lon[ci], lat[ri]
    P, models, members = probability(D); WX = load_wx_npz(D, wxp)
    lat_s, P = lat[::-1], P[:, ::-1]; Tm = WX['T'][:, ::-1]
    lon_raw0 = float(lon[0]); dg = g['d']
    PAD = 16 if not proj and (ext[0] < lon[0] + 0.5 or ext[1] > lon[-1] - 0.5) else 0  # the map wider than the data: the edge values carried on
    P = np.pad(P, ((0, 0), (0, 0), (PAD, PAD)), mode='edge'); Tm = np.pad(Tm, ((0, 0), (0, 0), (PAD, PAD)), mode='edge')
    lon = np.r_[lon[0] - g['d'] * np.arange(PAD, 0, -1), lon, lon[-1] + g['d'] * np.arange(1, PAD + 1)]
    UP, SIG = view.get('up', 4), view.get('sig', 1.6)  # a close-up: finer and smoother, so the model's grid does not show
    up = lambda a: gaussian_filter(zoom(np.nan_to_num(a, nan=np.nanmean(a)), UP, order=3), SIG)
    LONu = np.linspace(lon[0], lon[-1], len(lon) * UP); LATu = np.linspace(lat_s[0], lat_s[-1], len(lat_s) * UP)
    if proj:  # the fields drawn on a fine grid of the map itself: each point's own longitude and latitude looked up in the data
        from scipy.ndimage import map_coordinates
        nx = 720; ny = int(nx * (la1 - la0) / (ext[1] - ext[0])); LONu = np.linspace(*ext, nx); LATu = np.linspace(la0, la1, ny)
        PX, PY = np.meshgrid(LONu, LATu); plo, pla = TI.transform(PX, PY)
        fxy = [np.nan_to_num((pla - lat_s[0]) / dg, nan=-9), np.nan_to_num((plo - lon[0]) / dg, nan=-9)]
        inside = np.isfinite(plo) & np.isfinite(pla)  # the whole world's map: beyond the globe's edge there is nothing
        def up(a):
            r = gaussian_filter(map_coordinates(np.nan_to_num(a, nan=np.nanmean(a)), fxy, order=3, mode='nearest'), view.get('sig', 1.2)); r[~inside] = 0; return r
    at = lambda a, la, lo: float(a[np.abs(LATu - la).argmin(), np.abs(LONu - lo).argmin()])
    run = dt.datetime.fromisoformat(D['run'].replace('Z', '')[:19]); steps = [int(x) for x in D['steps']]; win = [int(x) for x in D['win']]
    now = dt.datetime.utcnow()
    keep = [i for i, s in enumerate(steps) if run + dt.timedelta(hours=s) > now + dt.timedelta(hours=1)]
    if only: keep = keep[:only]
    Pk = {i: np.clip(up(P[i]), 0, 100) for i in keep}; Tk = {i: up(Tm[i]) for i in keep}
    if proj and not inside.all():
        for i in keep: Tk[i][~inside] = np.nan
    Cm = WX['C'][:, ::-1] if WX.get('C') is not None else None; Km = WX['K'][:, ::-1] if WX.get('K') is not None else None
    if Cm is not None: Cm = np.pad(Cm, ((0, 0), (0, 0), (PAD, PAD)), mode='edge')
    if Km is not None: Km = np.pad(Km, ((0, 0), (0, 0), (PAD, PAD)), mode='edge')
    Ck = {i: np.clip(up(Cm[i]), 0, 1) if Cm is not None and np.isfinite(Cm[i]).any() else None for i in keep}
    Fk = {i: None for i in keep}
    if FOG and not proj and pathlib.Path(FOG).exists():  # fog from ECMWF (tools/fog_fetch.py): the step nearest the window's middle
        from scipy.interpolate import RegularGridInterpolator
        Z = np.load(FOG); vt = Z['vt']; LOg, LAg = np.meshgrid(lon, lat_s)
        for i in keep:
            tm = (run + dt.timedelta(hours=steps[i] - win[i] / 2) - dt.datetime(1970, 1, 1)).total_seconds() / 3600; j = int(np.abs(vt - tm).argmin())
            if abs(vt[j] - tm) > 6: continue
            f_ = RegularGridInterpolator((Z['lat'], Z['lon']), Z['fog'][j].astype(np.float32), bounds_error=False, fill_value=0)
            Fk[i] = np.clip(up(f_(np.stack([LAg, LOg], -1))), 0, 1)
    # the chance of a thunderstorm, 0…1: precipitation likely, enough convective energy (GEFS CAPE) and warm enough air
    Sk = {i: (np.clip((Pk[i] - 30) / 40, 0, 1) * np.clip((up(Km[i]) - 500) / 1000, 0, 1) * (Tk[i] >= 3)) if Km is not None and np.isfinite(Km[i]).any() else None for i in keep}
    off = view.get('off', 5); loc = lambda h: run + dt.timedelta(hours=h + off)
    tash = next(t for t in towns if t[0] == view.get('main', 'Ташкент'))
    # the chart under the map: hours from the first window's start
    h0 = steps[keep[0]] - win[keep[0]]
    bx = np.array([steps[i] - win[i] / 2 - h0 for i in keep], float); bw = np.array([win[i] for i in keep], float)
    tp = np.array([at(Pk[i], tash[2], tash[3]) for i in keep]); tt = np.array([at(Tk[i], tash[2], tash[3]) for i in keep])
    tcl = np.array([at(Ck[i], tash[2], tash[3]) * 100 if Ck.get(i) is not None else 0 for i in keep])
    days = []; t0 = loc(h0); d = (t0 + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0)
    if t0.hour == 0: d = t0
    while (d - t0).total_seconds() / 3600 < bx[-1]:
        hh = (d - t0).total_seconds() / 3600
        days.append((hh, {l: f"{TX[l]['wd'][d.weekday()]}\n{d:%d.%m}" for l in TX})); d += dt.timedelta(days=1)
    # the frames: a few in-between frames per window, the numbers of the window
    WAT = json.load(open(ROOT / 'prob' / 'geo_water.json'))
    sea = [np.asarray(r) for r in WAT['ocean']] + [np.asarray(l_['r']) for l_ in WAT['lakes']]
    borders = view.get('borders')
    if borders is None:
        G = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']; GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']
        UZ = [np.asarray(r) for r in G['UZ']['rings']]; NB = [np.asarray(r) for k, c in G.items() if k != 'UZ' for r in c['rings']]
        A1 = [np.asarray(r) for a in GA['adm1'] for r in a['r']]
        borders = [(NB, '#a3acb6', 1.0, 3), (A1, '#b7c0ca', 0.8, 3.05), (UZ, '#1c2633', 2.6, 3.3)]
    land = None
    if proj:  # rings in longitude/latitude → the map's metres; only those near the map
        near = lambda r: r[:, 0].max() >= crop[0] - 5 and r[:, 0].min() <= crop[1] + 5 and r[:, 1].max() >= crop[2] - 5 and r[:, 1].min() <= crop[3] + 5
        pr_ = lambda rs: [np.c_[TF.transform(r[:, 0], r[:, 1])] for r in rs if len(r) > 1 and near(r)]
        borders = [(pr_(rs), col, lw, z) for rs, col, lw, z in borders]
        GW_ = json.load(open(ROOT / 'prob' / 'geo_world.json'))['countries']
        land = pr_([np.asarray(r, float) for c in GW_.values() for r in c['rings']]); sea = []
        if view.get('globe'):  # the world: the globe's outline filled with the sea, white around it
            q = np.linspace(-90, 90, 181); o = np.linspace(-180, 180, 361)
            ol = np.r_[np.full(181, -179.999), o, np.full(181, 179.999), o[::-1]]; oa = np.r_[q, np.full(361, 90), q[::-1], np.full(361, -90)]
            globe = np.c_[TF.transform(ol, oa)]
    rl = relief_layer(ext[0], ext[1], la0, la1) if not proj and os.environ.get('P15_RELIEF', '1') == '1' else None
    print('relief', None if rl is None else rl.shape, flush=True)
    CTX.update(mode=mode, globe=globe if proj and view.get('globe') else None, relief=rl, land=land, deg=DEG, LONu=LONu, LATu=LATu, sea=sea, borders=borders, lon_ext=ext, la0=la0, la1=la1, cosl=cosl, towns=towns, main=tash[0], names=view.get('names', []),
               title=view.get('title'), intro2=view.get('intro2'), tzl=view.get('tzl'), chart_t=view.get('chart_t'),
               members=members, bx=bx, bw=bw, tp=tp, tt=tt, tc=tcl, days=days, qr=qr('https://t.me/ObHavo_ECMWF_bot'), videos={})
    seq = []
    for n_, i in enumerate(keep):  # one frame for every hour of the window (15:00, 16:00, …), the fields eased towards the next window
        nxt = keep[min(n_ + 1, len(keep) - 1)]; N = win[i]
        for k in range(N):
            a = k / N; mix = lambda D_: None if D_[i] is None or D_[nxt] is None else (1 - a) * D_[i] + a * D_[nxt]
            seq.append((n_, i, (1 - a) * Pk[i] + a * Pk[nxt], (1 - a) * Tk[i] + a * Tk[nxt], k, mix(Ck), mix(Sk), mix(Fk)))
    tot_h = (steps[keep[-1]] - h0)
    WIND = wind_streams(seq, WX, lat_s, lon_raw0, dg, ext, la0, la1, cosl, TF, TI if proj else None) if WX.get('U') is not None and os.environ.get('P15_WIND', '1') == '1' else [None] * len(seq)
    for lang in langs:
        X = TX[lang]; frames = []
        for n_, i, Pf, Tf, k, Cf, Sf, Ff in seq:
            t2 = loc(steps[i]); t1 = t2 - dt.timedelta(hours=win[i]); th = t1 + dt.timedelta(hours=k)
            when = f"{X['wd'][th.weekday()]} {th:%d.%m} · {th:%H}:00"
            dayn = max(1, (th.date() - loc(h0).date()).days + (0 if loc(h0).hour >= 12 else 1))  # day 1: the first full local day
            storms = []
            if Sf is not None and Sf.max() >= 0.35:  # one bolt per storm area (the strongest point within ~1.5°)
                from scipy.ndimage import maximum_filter
                mx = (maximum_filter(Sf, size=24) == Sf) & (Sf >= 0.35)
                for yy, xx in zip(*np.nonzero(mx)):
                    if not any(abs(LONu[xx] - tw[3]) < 0.7 * DEG and abs(LATu[yy] - tw[2]) < 0.5 * DEG for tw in towns): storms.append((float(LONu[xx]), float(LATu[yy])))
            frames.append(dict(wind=WIND[len(frames)], P=Pf, T=Tf, Cl=Cf, Fg=Ff, storms=storms[:14], s=n_, when=when, day=X['day'].format(i=min(dayn, 15), n=15), prog=(steps[i] - win[i] + k - h0) / tot_h, d=0.2,
                               towns=[(at(Pf, tw[2], tw[3]), at(Tf, tw[2], tw[3]), Sf is not None and at(Sf, tw[2], tw[3]) >= 0.35, Ff is not None and at(Ff, tw[2], tw[3]) >= 0.5) for tw in towns], tash_t=at(Tf, tash[2], tash[3])))
        frames[-1] = dict(frames[-1], d=1.2)
        intro = [dict(frames[0], card='intro', a=1.0, fade=0.0, d=1.6)] + [dict(frames[0], card='intro', a=float(a_), fade=float(1 - a_), d=0.07) for a_ in np.linspace(1, 0, 9)[1:]]
        end = [dict(frames[-1], card='end', d=4.0)]
        CTX['videos'][lang] = dict(frames=intro + frames + end, dir=tempfile.mkdtemp(), out=str(pathlib.Path(outd) / f"{view.get('stem', 'p15')}{ {'temp': '_t', 'cloud': '_c'}.get(mode, '')}_{lang}.mp4"))
    return CTX


if __name__ == '__main__':
    npz, wxp, outd = sys.argv[1:4]; langs = (sys.argv[4] if len(sys.argv) > 4 else 'ru,uz').split(',')
    FOG = sys.argv[5] if len(sys.argv) > 5 else None
    pathlib.Path(outd).mkdir(parents=True, exist_ok=True)
    main(npz, wxp, outd, langs)
    jobs = [(l, i) for l in langs for i in range(len(CTX['videos'][l]['frames']))]; print(len(jobs), 'frames', flush=True)
    with mp.get_context('fork').Pool(max(1, os.cpu_count() or 1)) as pool:
        for n_, _ in enumerate(pool.imap_unordered(draw, jobs, chunksize=4)):
            if n_ % 200 == 0: print('frames', n_, '/', len(jobs), flush=True)
        for r in pool.imap_unordered(encode, langs): print(r, flush=True)
