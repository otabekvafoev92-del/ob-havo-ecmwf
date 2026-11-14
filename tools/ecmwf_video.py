"""Videos for phones (1080×1920): what the weather stations of Uzbekistan reported over the last 6 hours (WMO SYNOP), then the
ECMWF forecast — "12h" (hourly) and "3d" (every 3 hours to 72 h) — and one video per region, cut out whole with its districts (12 h).

The look: a white map in 3D — tilted like a view from a plane, the mountains in relief (elevation tiles), a haze towards the horizon;
borders drawn as dots; clouds and rain moving along the optical flow between the forecast hours; the wind as drifting particles;
isobars; under the map the dynamics of the rain (how much of the territory gets rain, hour by hour, the current hour marked).
Out: out/{12h|3d}_{lang}.mp4, out/reg/{id}_{lang}.mp4, out/meta.json.  Usage: python tools/ecmwf_video.py out ru,uz"""
import io, json, math, os, sys, shutil, subprocess, tempfile, datetime as dt, pathlib, concurrent.futures as cf, multiprocessing as mp
import numpy as np, requests
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection as LC, PolyCollection as PCOL
from matplotlib.colors import LightSource
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch
from matplotlib import font_manager as fm
from PIL import Image
import cv2
from scipy.ndimage import zoom, gaussian_filter

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'prob')); sys.path.insert(0, str(ROOT / 'tools'))
import moisture as M  # ECMWF open data: fields of a run (Google's mirror)
import obs_video as OV  # the stations and their SYNOP reports

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'ev'); OUT.mkdir(parents=True, exist_ok=True)
LANGS = (sys.argv[2] if len(sys.argv) > 2 else 'ru,uz').split(',')
W, H = 1080, 1920
HEAD, CHART = 210, 400            # px: the header on top, the rain dynamics at the bottom
HD = H - HEAD - CHART              # the 3D map between them
WS, HS = 1512, 1834                # the map drawn 1.4× and scaled down (sharp lines)
TOPIN, BOTOUT = 0, 0               # seen from straight above (a tilt would be TOPIN>0)
SLOW = 4.0                         # the speed: 0.25× (every frame held 4× longer)
DOM = (54.0, 76.5, 34.5, 48.5)     # the data grid (all the regions fit)
if any('inter' in x.lower() for x in fm.findSystemFonts()): plt.rcParams['font.family'] = 'Inter'
NAVY, ORANGE, INK, MUTED = '#0f1d30', '#e8742c', '#1f2d3d', '#5d6b7c'
PR_LV = [0.2, 1, 3, 6, 12, 99]
RAIN = ['#9be59a', '#3fca5a', '#f2e33a', '#f59a2c', '#e53935']  # radar colours
SNOW = ['#f3e9ff', '#e2c4ff', '#cf94f5', '#b55ee6', '#8e2fc9']
TCOL = lambda t: OV.tcol(t)
DOT = (0, (0.1, 2.0))  # dotted borders (with round caps the dashes become dots)
TOWNS = [('Ташкент', 'Toshkent', 41.31, 69.28), ('Самарканд', 'Samarqand', 39.65, 66.96), ('Бухара', 'Buxoro', 39.77, 64.42), ('Нукус', 'Nukus', 42.46, 59.6),
         ('Ургенч', 'Urganch', 41.55, 60.63), ('Наманган', 'Namangan', 41.0, 71.67), ('Андижан', 'Andijon', 40.78, 72.34), ('Фергана', 'Farg‘ona', 40.39, 71.78),
         ('Карши', 'Qarshi', 38.86, 65.79), ('Термез', 'Termiz', 37.22, 67.28), ('Навои', 'Navoiy', 40.1, 65.38), ('Джизак', 'Jizzax', 40.12, 67.84),
         ('Гулистан', 'Guliston', 40.49, 68.78), ('Нурафшон', 'Nurafshon', 41.04, 69.36)]
TX = {'ru': dict(fact='ФАКТ · метеостанции', fc='ПРОГНОЗ ECMWF', t12='Погода: 6 ч факт + 12 ч прогноз', t3='Погода: 6 ч факт + 3 дня прогноз',
                 at='{d} · {h} по Ташкенту', plus='+{h} ч', rain='мм за 3 ч', snow='снег', src='Факт: метеостанции Узбекистана (ВМО SYNOP) · Прогноз: ECMWF IFS · Osmon',
                 wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], mon=['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'],
                 dry='Без осадков по всей стране', wet='Больше всего осадков: {t} — {mm} мм', wet3='За 3 дня больше всего: {t} — {mm} мм', none3='3 дня без заметных осадков',
                 reg_t='прогноз на 12 часов', reg_wet='Больше всего за 12 ч: {t} — {mm} мм', reg_dry='Ближайшие 12 часов без заметных осадков',
                 chart='Динамика дождей: где идут осадки, % территории', chart_r='Динамика дождей в области, % территории', upto='до {mm} мм', none_='без осадков',
                 tot='Осадки за 3 дня, мм', total='ИТОГ · 3 дня', lat='с.ш.', lon='в.д.', fog='туман', day_mm='мм за сутки',
                 t7='Погода по дням: 7 дней', d7='день {i} из {n}', chart7='Осадки по дням: где пройдут, % территории', wet7='Самый дождливый день: {d} — до {mm} мм', dry7='Неделя без заметных осадков', nightc='в кружке — днём, рядом — ночью'),
      'uz': dict(fact='FAKT · meteostansiyalar', fc='ECMWF PROGNOZI', t12='Ob-havo: 6 soat fakt + 12 soat prognoz', t3='Ob-havo: 6 soat fakt + 3 kun prognoz',
                 at='{d} · Toshkent vaqti {h}', plus='+{h} soat', rain='3 soatda mm', snow='qor', src='Fakt: O‘zbekiston meteostansiyalari (JMT SYNOP) · Prognoz: ECMWF IFS · Osmon',
                 wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'], mon=['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'],
                 dry='Butun mamlakatda yog‘in yo‘q', wet='Eng ko‘p yog‘in: {t} — {mm} mm', wet3='3 kunda eng ko‘p: {t} — {mm} mm', none3='3 kun sezilarli yog‘insiz',
                 reg_t='12 soatlik prognoz', reg_wet='12 soatda eng ko‘p: {t} — {mm} mm', reg_dry='Yaqin 12 soatda sezilarli yog‘in yo‘q',
                 chart='Yog‘in dinamikasi: yog‘in yog‘ayotgan hudud, %', chart_r='Viloyatda yog‘in dinamikasi, % hudud', upto='{mm} mm gacha', none_='yog‘insiz',
                 tot='3 kunlik yog‘in, mm', total='JAMI · 3 kun', lat='N', lon='E', fog='tuman', day_mm='sutkada mm',
                 t7='Kunlar bo‘yicha ob-havo: 7 kun', d7='{i}-kun / {n}', chart7='Kunlar bo‘yicha yog‘in: hudud, %', wet7='Eng yog‘inli kun: {d} — {mm} mm gacha', dry7='Hafta sezilarli yog‘insiz', nightc='doirada — kunduz, yonida — tun')}
S = requests.Session(); S.headers['User-Agent'] = 'Osmon weather (github.com/otabekvafoev92-del/ob-havo-ecmwf)'
CTX = {}  # filled by main before the workers fork: they read it, nothing is copied


# ---------- geometry: the extent of a map and the 3D tilt ----------
def fit_ext(lo0, lo1, la0, la1, pad=0.06):
    """The smallest extent around a box with the proportions of the flat map (true scale at its middle latitude)."""
    cy = (la0 + la1) / 2; cx = (lo0 + lo1) / 2; cf_ = math.cos(math.radians(cy))
    w = (lo1 - lo0) * cf_ * (1 + pad); h = (la1 - la0) * (1 + pad); r = WS / HS
    if w / h < r: w = h * r
    else: h = w / r
    return (cx - w / cf_ / 2, cx + w / cf_ / 2, cy - h / 2, cy + h / 2)


HM = cv2.getPerspectiveTransform(np.float32([[0, 0], [WS, 0], [WS, HS], [0, HS]]), np.float32([[TOPIN, 0], [W - TOPIN, 0], [W + BOTOUT, HD], [-BOTOUT, HD]]))


def proj(E, lon, lat):
    """lon/lat → pixels of the frame (x right, y down), through the tilt."""
    p = np.float32([[[(lon - E[0]) / (E[1] - E[0]) * WS, (E[3] - lat) / (E[3] - E[2]) * HS]]])
    q = cv2.perspectiveTransform(p, HM)[0, 0]
    return float(q[0]), float(q[1] + HEAD)


# ---------- the relief ----------
_TILES = {}


def relief(E, mask_in=None, mask_hi=None):
    """The flat map (WS×HS): white lowlands, the mountains shaded in relief, snow on the peaks; outside mask_in grey, outside mask_hi greyer."""
    span = E[1] - E[0]; z = int(np.clip(round(math.log2(360 / (span / WS * 256))), 6, 10)); n = 2 ** z
    tx = lambda lon: (lon + 180) / 360 * n
    ty = lambda lat: (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    x0, x1 = int(tx(E[0])), int(tx(E[1])); y0, y1 = int(ty(E[3])), int(ty(E[2]))
    def tile(xy):
        x, y = xy
        if (z, x, y) in _TILES: return xy, _TILES[(z, x, y)]
        for k in range(3):
            try:
                r = S.get(f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png', timeout=60)
                if r.ok:
                    a = np.asarray(Image.open(io.BytesIO(r.content)).convert('RGB'), float); e = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
                    _TILES[(z, x, y)] = e; return xy, e
            except requests.RequestException: pass
        return xy, np.zeros((256, 256))
    big = np.zeros(((y1 - y0 + 1) * 256, (x1 - x0 + 1) * 256))
    with cf.ThreadPoolExecutor(16) as p:
        for (x, y), e in p.map(tile, [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]):
            big[(y - y0) * 256:(y - y0 + 1) * 256, (x - x0) * 256:(x - x0 + 1) * 256] = e
    lon = np.linspace(E[0], E[1], WS); lat = np.linspace(E[3], E[2], HS)
    px = ((lon + 180) / 360 * n - x0) * 256; py = np.array([((1 - math.asinh(math.tan(math.radians(la))) / math.pi) / 2 * n - y0) * 256 for la in lat])
    el = np.maximum(big[np.ix_(np.clip(py.astype(int), 0, big.shape[0] - 1), np.clip(px.astype(int), 0, big.shape[1] - 1))], 0)
    mpp = span * 111e3 * math.cos(math.radians((E[2] + E[3]) / 2)) / WS
    hs = LightSource(azdeg=315, altdeg=35).hillshade(el, vert_exag=3.0, dx=mpp, dy=mpp)
    base = np.dstack([np.interp(el, [0, 400, 1200, 2400, 3600, 4500], c) for c in
                      ([0.995, 0.975, 0.93, 0.86, 0.9, 1.0], [0.99, 0.965, 0.91, 0.83, 0.9, 1.0], [0.975, 0.94, 0.87, 0.8, 0.92, 1.0])])
    img = np.clip(base * (1 + 1.1 * (hs[..., None] - math.sin(math.radians(35)))), 0, 1)  # flat ground stays white, slopes light and shade
    gx, gy = np.meshgrid(lon, lat); pts = np.c_[gx.ravel(), gy.ravel()]; top = None
    for rings, f in ((mask_in, 0.86), (mask_hi, 0.93)):
        if rings is None: continue
        ins = np.zeros(len(pts), bool)
        for r in rings: ins |= MPath(r).contains_points(pts)
        ins = ins.reshape(el.shape); out = ~ins; g = img.mean(axis=2, keepdims=True); top = ins
        img = np.where(out[..., None], (0.55 * img + 0.45 * g) * f, img)
    if False and top is not None:  # (off) 3D from above: the cut-out lies raised over the map and casts a soft shadow to the south-east
        sh = gaussian_filter(np.roll(np.roll(top.astype(float), 14, 0), 10, 1), 7) * (~top)
        img = img * (1 - 0.38 * sh[..., None])
        edge = gaussian_filter(top.astype(float), 1.5); rim = np.clip((edge - 0.5) * -2, 0, 1) * top  # a light rim just inside the edge
        img = np.clip(img + 0.05 * rim[..., None], 0, 1)
    return (img * 255).astype(np.uint8)


# ---------- one frame ----------
def render(job):
    """job = (video key, frame index): draws the frame of that video into its folder."""
    vk, i = job; V = CTX['videos'][vk]; fr = V['frames'][i]; X = TX[V['lang']]; mode = fr['mode']
    E0 = fr.get('E', V['ext']); relk = fr.get('relk', V['rel']); ctry = fr.get('country', False)  # a region video opens on the whole country
    zf = fr.get('zf', 1.0); cx_, cy_ = (E0[0] + E0[1]) / 2, (E0[2] + E0[3]) / 2  # a slow camera zoom
    E = (cx_ - (E0[1] - E0[0]) / 2 / zf, cx_ + (E0[1] - E0[0]) / 2 / zf, cy_ - (E0[3] - E0[2]) / 2 / zf, cy_ + (E0[3] - E0[2]) / 2 / zf)
    # 1) the flat map
    f1 = plt.figure(figsize=(WS / 100, HS / 100), dpi=100); ax = f1.add_axes([0, 0, 1, 1]); ax.set_xlim(E[0], E[1]); ax.set_ylim(E[2], E[3]); ax.axis('off')
    ax.imshow(CTX['rel'][relk], extent=CTX['relE'][relk], aspect='auto', zorder=0, interpolation='antialiased')
    ax.add_collection(PCOL(CTX['sea'], facecolors='#bcd9ef', edgecolors='#86afd2', linewidths=0.9, zorder=0.5))
    clip = None
    if V.get('clip') is not None and not ctry:
        clip = PathPatch(MPath.make_compound_path(*[MPath(r) for r in V['clip']]), transform=ax.transData, fc='none', ec='none'); ax.add_patch(clip)
    LATu, LONu, ext = CTX['LATu'], CTX['LONu'], CTX['ext']
    if mode in ('fc', 'total', 'day'):
        F = CTX['fields'][fr['k']] if mode != 'total' else None
        if mode != 'total':
            tcc, nz = F['tcc'], F['nz']; th = np.clip((tcc - 0.7) / 0.3, 0, 1)[..., None]; cl = np.zeros(tcc.shape + (4,))
            cl[..., :3] = (1 - th) * np.array([0.78, 0.81, 0.85]) + th * np.array([0.5, 0.53, 0.58])
            cl[..., 3] = np.clip((tcc - 0.15) / 0.6, 0, 1) * (0.3 + 0.5 * np.clip(nz * 1.6 - 0.3, 0, 1)) * 0.62
            im = ax.imshow(cl, extent=ext, origin='lower', aspect='auto', interpolation='bicubic', zorder=1)
            if clip is not None: im.set_clip_path(clip)
            fg = F.get('fog')
            if fg is not None and fg.max() > 0.05:  # fog: a milky veil, thicker in the valleys where the air is saturated and calm
                fl_ = np.zeros(fg.shape + (4,)); fl_[..., :3] = (0.9, 0.91, 0.93)
                fl_[..., 3] = np.clip(fg, 0, 1) * (0.55 + 0.35 * np.clip(1.4 - nz * 1.6, 0, 1)) * 0.85
                im2 = ax.imshow(fl_, extent=ext, origin='lower', aspect='auto', interpolation='bicubic', zorder=1.5)
                if clip is not None: im2.set_clip_path(clip)
        acc, t2 = (F['pr'], F['t2']) if mode != 'total' else (CTX['acc'][V['kind']], CTX['t2end'][V['kind']])
        lv = PR_LV if mode == 'fc' else [1, 3, 5, 10, 20, 999] if mode == 'day' else [1, 5, 10, 20, 40, 999]
        for msk, cols in ((t2 > 0.5, RAIN), (t2 <= 0.5, SNOW)):
            a = np.where(msk, acc, np.nan)
            if np.nanmax(np.nan_to_num(a)) >= lv[0]:
                cs = ax.contourf(LONu, LATu, a, levels=lv, colors=cols, alpha=0.9, zorder=2, antialiased=True)
                if clip is not None: cs.set_clip_path(clip)
        if mode in ('fc', 'day'):
            ms = gaussian_filter(F['msl'], 4); lo_, hi_ = int(np.floor(ms.min() / 4) * 4), int(np.ceil(ms.max() / 4) * 4)
            if hi_ > lo_: ax.contour(LONu, LATu, ms, levels=range(lo_, hi_ + 1, 4), colors='#3b4a5c', linewidths=1.2, alpha=0.4, zorder=2.6)
            if (V.get('wind') or ctry) and 'tr' in F:
                tr = F['tr']; segs = np.stack([tr[:-1], tr[1:]], axis=2).reshape(-1, 2, 2); al = np.repeat(np.linspace(0.05, 0.6, tr.shape[0] - 1), tr.shape[1])
                ax.add_collection(LC(segs, colors=np.c_[np.tile([0.12, 0.21, 0.31], (len(al), 1)), al], linewidths=1.5, zorder=2.8, capstyle='round'))
    for g in range(30, 80, 2 if (E[1] - E[0]) > 6 else 1): ax.axvline(g, color='#1f2d3d', lw=0.8, alpha=0.12, zorder=2.9)
    for g in range(30, 52, 2 if (E[1] - E[0]) > 6 else 1): ax.axhline(g, color='#1f2d3d', lw=0.8, alpha=0.12, zorder=2.9)
    for segs, col, lw, ls, al, z in (V['borders_c'] if ctry else V['borders']):
        ax.add_collection(LC(segs, colors=col, linewidths=lw, linestyles=ls, alpha=al, zorder=z, capstyle='round'))
    f1.canvas.draw(); flat = np.asarray(f1.canvas.buffer_rgba())[..., :3].copy(); plt.close(f1)
    # 2) the tilt, a haze towards the horizon, the sky behind
    warp = (cv2.warpPerspective(flat, HM, (W, HD), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)) if TOPIN else cv2.resize(flat, (W, HD), interpolation=cv2.INTER_AREA)).astype(float) / 255
    msk = cv2.warpPerspective(np.ones((HS, WS), np.float32), HM, (W, HD), flags=cv2.INTER_LINEAR)[..., None]
    yy = np.linspace(0, 1, HD)[:, None, None]; sky = (1 - yy) * np.array([0.84, 0.89, 0.94]) + yy * np.array([0.97, 0.98, 0.99])
    if TOPIN: haze = np.clip(1 - yy / 0.45, 0, 1) * 0.42; warp = warp * (1 - haze) + sky * haze
    canvas = np.ones((H, W, 3)); canvas[HEAD:HEAD + HD] = sky * (1 - msk) + warp * msk
    # 3) the frame: the values on the map, the header, the dynamics
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100); a0 = fig.add_axes([0, 0, 1, 1]); a0.set_xlim(0, W); a0.set_ylim(H, 0); a0.axis('off')
    a0.imshow(canvas, extent=(0, W, H, 0), interpolation='nearest', zorder=0)
    for g in range(int(math.ceil(E[0])), int(E[1]) + 1, 2 if (E[1] - E[0]) > 6 else 1):  # the axes: degrees along the near edge and the left side
        x, y = proj(E, g, E[2])
        if 30 < x < W - 30: a0.text(x, y - 10, f"{g}°{X['lon']}", ha='center', va='bottom', fontsize=12, color='#33475e', zorder=7, bbox=dict(boxstyle='round,pad=0.12', fc='#ffffffcc', ec='none'))
    for g in range(int(math.ceil(E[2])), int(E[3]) + 1, 2 if (E[1] - E[0]) > 6 else 1):
        x, y = proj(E, E[0], g)
        if HEAD + 40 < y < HEAD + HD - 40: a0.text(max(x, 0) + 6, y, f"{g}°{X['lat']}", ha='left', va='center', fontsize=12, color='#33475e', zorder=7, bbox=dict(boxstyle='round,pad=0.12', fc='#ffffffcc', ec='none'))
    for p in sorted(fr.get('pts', []), key=lambda q: -proj(E, q[0], q[1])[1]):  # far first
        lon, lat, txt, col, ring, lab, big = p
        x, y = proj(E, lon, lat)
        if not (0 < x < W and HEAD + 10 < y < HEAD + HD): continue
        k = (0.7 + 0.3 * (y - HEAD) / HD) if TOPIN else 1.0; sz = (1500 if big else 800) * k * k
        if ring: a0.scatter(x, y, s=sz * 1.55, facecolors='none', edgecolors=ring, linewidths=4.5 * k, zorder=8)
        a0.scatter(x, y, s=sz, c=[col], edgecolors='#ffffff', linewidths=2.2, zorder=9)
        a0.text(x, y, txt, ha='center', va='center', fontsize=(18 if big else 13) * k, fontweight='bold', color='#1f2d3d', zorder=10)
        if lab: a0.text(x, y + (30 if big else 22) * k, lab, ha='center', va='top', fontsize=(15 if big else 11) * k, fontweight='bold' if big else 'normal', color='#1f2d3d', zorder=10,
                        bbox=dict(boxstyle='round,pad=0.15', fc='#ffffffdd', ec='none'))
    if fr.get('intro') is not None:  # the opening: the title over a dark veil that lifts off the map
        al = fr['intro']; a0.add_patch(plt.Rectangle((0, 0), W, H, fc=NAVY, ec='none', alpha=0.93 * al, zorder=10.5))
        sc = 1 + 0.25 * al
        a0.text(W / 2, H * 0.40, 'OSMON', ha='center', va='center', fontsize=64 * sc, fontweight='bold', color='#f08a24', alpha=min(1, al * 1.4), zorder=10.6)
        a0.text(W / 2, H * 0.47, V['title'], ha='center', va='center', fontsize=30, fontweight='bold', color='#ffffff', alpha=min(1, al * 1.4), zorder=10.6, wrap=True)
        if fr.get('when'): a0.text(W / 2, H * 0.515, fr['when'], ha='center', va='center', fontsize=24, color='#dfe6ee', alpha=min(1, al * 1.4), zorder=10.6)
    # header
    a0.add_patch(plt.Rectangle((0, 0), W, HEAD, fc=NAVY, ec='none', zorder=11))
    a0.text(50, 46, 'OSMON', color='#f08a24', fontsize=24, fontweight='bold', va='center', zorder=12)
    a0.text(50, 100, V['title'], color='#ffffff', fontsize=29, fontweight='bold', va='center', zorder=12)
    a0.text(50, 162, fr['badge'], color='#ffffff', fontsize=23, fontweight='bold', va='center', zorder=12, bbox=dict(boxstyle='round,pad=0.35', fc=fr['bc'], ec='none'))
    if fr.get('when'): a0.text(W - 50, 162, fr['when'], color='#dfe6ee', fontsize=22, va='center', ha='right', zorder=12)
    # the dynamics of the rain
    y0 = H - CHART; a0.add_patch(plt.Rectangle((0, y0), W, CHART, fc='#ffffff', ec='none', zorder=11))
    a0.plot([0, W], [y0, y0], color='#e3e8ee', lw=2, zorder=12)
    a0.text(50, y0 + 34, V['line'], fontsize=20, color='#a1520c', fontweight='bold', va='center', zorder=12)
    a0.text(50, y0 + 76, V['chart_t'], fontsize=17, color=INK, fontweight='bold', va='center', zorder=12)
    ch = CTX['charts'][V['chart']]; n = len(ch['pct']); cur = fr.get('ci')
    cx0, cx1, cyb, cyt = 60, W - 40, y0 + 290, y0 + 150; bw = (cx1 - cx0) / max(n, 1)
    a0.plot([cx0, cx1], [cyb, cyb], color='#c9d1da', lw=1.5, zorder=12)
    for j, (pc, mx) in enumerate(zip(ch['pct'], ch['mx'])):
        hgt = max(pc, 0.8 if mx >= 0.2 else 0) / 100 * (cyb - cyt); ci = int(np.clip(np.searchsorted(PR_LV, mx, side='right') - 1, 0, 4))
        col = (SNOW if ch['snow'][j] else RAIN)[ci] if mx >= 0.2 else '#dfe4ea'
        on = cur is not None and j <= cur; xx = cx0 + j * bw
        a0.add_patch(plt.Rectangle((xx + bw * 0.14, cyb - max(hgt, 3)), bw * 0.72, max(hgt, 3), fc=col, ec='none', alpha=1.0 if (on or cur is None) else 0.35, zorder=12))
        if j % ch['every'] == 0: a0.text(xx + bw / 2, cyb + 10, ch['lab'][j], ha='center', va='top', fontsize=12, color=MUTED, zorder=12)
    if cur is not None:
        xx = cx0 + (cur + 0.5) * bw; a0.plot([xx, xx], [cyt - 6, cyb], color=INK, lw=2, zorder=13)
        pc, mx = ch['pct'][cur], ch['mx'][cur]
        a0.text(min(max(xx, 150), W - 150), cyt - 12, (f"{pc:.0f}% · " + X['upto'].format(mm=f'{mx:.0f}' if mx >= 1 else f'{mx:.1f}')) if mx >= 0.2 else X['none_'],
                ha='center', va='bottom', fontsize=15, fontweight='bold', color=INK, zorder=13, bbox=dict(boxstyle='round,pad=0.25', fc='#ffffff', ec='#c9d1da'))
    # legend and source
    lx = 40; a0.text(lx, H - 52, X['rain'] if mode not in ('total', 'day') else X['tot'] if mode == 'total' else X['day_mm'], fontsize=13, color=MUTED, va='center', zorder=12); lx += 112 if V['lang'] == 'ru' else 118
    for c, l_ in zip(RAIN, ['0.2', '1', '3', '6', '12+'] if mode not in ('total', 'day') else ['1', '5', '10', '20', '40+'] if mode == 'total' else ['1', '3', '5', '10', '20+']):
        a0.add_patch(plt.Rectangle((lx, H - 62), 40, 20, fc=c, ec='none', zorder=12)); a0.text(lx + 45, H - 52, l_, fontsize=12, color=MUTED, va='center', zorder=12); lx += 92
    a0.add_patch(plt.Rectangle((lx + 110, H - 62), 40, 20, fc='#e3e6ea', ec='#b9c0c8', hatch='---', lw=0.8, zorder=12)); a0.text(lx + 155, H - 52, X['fog'], fontsize=12, color=MUTED, va='center', zorder=12)
    a0.add_patch(plt.Rectangle((lx, H - 62), 40, 20, fc=SNOW[2], ec='none', zorder=12)); a0.text(lx + 45, H - 52, X['snow'], fontsize=12, color=MUTED, va='center', zorder=12)
    a0.text(50, H - 18, X['src'], fontsize=11, color='#7d8c9e', va='center', zorder=12)
    fig.savefig(pathlib.Path(V['dir']) / f'{i:04d}.png'); plt.close(fig)
    return vk


def encode(vk):
    V = CTX['videos'][vk]; fd = pathlib.Path(V['dir']); per = [fr['d'] * (1.5 if fr.get('intro') is not None else SLOW) for fr in V['frames']]
    lst = fd / 'list.txt'; lst.write_text(''.join(f"file '{i:04d}.png'\nduration {d}\n" for i, d in enumerate(per)) + f"file '{len(per) - 1:04d}.png'\n")
    out = pathlib.Path(V['out']); tmp = out.with_name('.' + out.name + '.part.mp4')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-map', '0:v', '-map', '1:a', '-vf',
                    'framerate=fps=30:interp_start=0:interp_end=255:scene=100,format=yuv420p', '-c:v', 'libx264', '-crf', '19', '-maxrate', '1700k', '-bufsize', '3400k', '-preset', 'slow', '-tune', 'animation', '-profile:v', 'high', '-level', '4.2',  # under 20 MB: Telegram takes a video by link only up to that
                   
                    '-c:a', 'aac', '-b:a', '48k', '-shortest', '-movflags', '+faststart', str(tmp)], check=True)
    tmp.replace(out); shutil.rmtree(fd); return f"{out} {out.stat().st_size // 1024} KB"


def latest_run():
    now = dt.datetime.utcnow()
    for h in range(4, 40):
        t = now - dt.timedelta(hours=h)
        if t.hour % 6: continue
        run = t.replace(minute=0, second=0, microsecond=0); d, hh = run.strftime('%Y%m%d'), run.strftime('%H')
        for stream in (('oper', 'scda') if hh in ('00', '12') else ('scda', 'oper')):
            if M.get(f'{M.ECM}/{d}/{hh}z/ifs/0p25/{stream}/{d}{hh}0000-90h-{stream}-fc.index'): return run
    raise RuntimeError('no run')


def main():
    run = latest_run(); print('run', run, flush=True)
    now = dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    lead0 = int((now - run).total_seconds() // 3600)
    need = sorted(set(s for s in range(0, 91, 3) if lead0 - 3 <= s <= lead0 + 75))
    F = M.fetch(run, [(s, 'hres') for s in need])
    lat = np.arange(M.LAT0, M.LAT1 + 1e-6, M.RES); lon = np.arange(M.LON0, M.LON1 + 1e-6, M.RES)
    ri = np.flatnonzero((lat >= DOM[2]) & (lat <= DOM[3])); ci = np.flatnonzero((lon >= DOM[0]) & (lon <= DOM[1]))
    LAT, LON = lat[ri], lon[ci]; ext = (LON[0] - M.RES / 2, LON[-1] + M.RES / 2, LAT[0] - M.RES / 2, LAT[-1] + M.RES / 2)
    cut = lambda a: a[np.ix_(ri, ci)].astype(np.float32)
    steps = sorted(F)
    def field(t):  # temperature, precipitation of the 3 hours ending at t (mm), cloud cover, pressure, wind at 10 m — interpolated in time
        L = (t - run).total_seconds() / 3600
        a = max([s for s in steps if s <= L], default=steps[0]); b = min([s for s in steps if s >= L], default=steps[-1]); w = 0 if b == a else (L - a) / (b - a)
        mix = lambda k, alt=None: cut(F[a].get(k, F[a].get(alt))) * (1 - w) + cut(F[b].get(k, F[b].get(alt))) * w
        b3 = min([s for s in steps if s >= L], default=steps[-1]); a3 = max([s for s in steps if s <= b3 - 3], default=steps[0])
        pr = np.maximum(cut(F[b3]['tp']) - cut(F[a3]['tp']), 0) * (3 / max(3, b3 - a3))
        t2 = mix('t2'); u, v = mix('u10', 'u'), mix('v10', 'v')
        return t2, pr, mix('tcc'), mix('msl'), u, v, fogidx(t2, mix('td2') if all('td2' in F[x] for x in (a, b)) else t2 - 10, u, v)
    def fogidx(t, td, u, v):  # how likely fog is: the air saturated (dew point at the temperature) and the wind calm
        rh = np.exp(17.625 * td / (243.04 + td) - 17.625 * t / (243.04 + t))
        return (np.clip((rh - 0.93) / 0.05, 0, 1) * np.clip((4.5 - np.hypot(u, v)) / 3, 0, 1)).astype(np.float32)
    UP = 4; up = lambda a: zoom(a, UP, order=1).astype(np.float32)
    hu, wu = up(np.zeros((len(LAT), len(LON)))).shape
    LATu, LONu = np.linspace(LAT[0], LAT[-1], hu), np.linspace(LON[0], LON[-1], wu)
    atu = lambda a, la, lo: float(a[np.abs(LATu - la).argmin(), np.abs(LONu - lo).argmin()])
    GX, GY = np.meshgrid(np.arange(wu, dtype=np.float32), np.arange(hu, dtype=np.float32))
    warp = lambda a, fl, s: cv2.remap(a.astype(np.float32), GX - s * fl[..., 0], GY - s * fl[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    def flow(a, b):
        u8 = lambda x: np.clip(x * 255, 0, 255).astype(np.uint8)
        return cv2.calcOpticalFlowFarneback(u8(a), u8(b), None, 0.5, 4, 31, 5, 7, 1.5, cv2.OPTFLOW_FARNEBACK_GAUSSIAN)
    sig = lambda pr, tc: 0.65 * tc + 0.35 * np.clip(pr / 6, 0, 1)
    rng = np.random.default_rng(7); NOISE = sum(gaussian_filter(rng.random((hu, wu)), s_) * w_ for s_, w_ in ((3, 1), (7, 1.6), (16, 2.2)))
    NOISE = ((NOISE - NOISE.min()) / (NOISE.max() - NOISE.min())).astype(np.float32)
    # the geography
    G = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']  # Natural Earth 1:10m: the Fergana valley, Sokh and Shakhimardan exact
    GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']
    WAT = json.load(open(ROOT / 'prob' / 'geo_water.json')); sea = [np.asarray(r) for r in WAT['ocean']] + [np.asarray(l['r']) for l in WAT['lakes']]
    UZR = [np.asarray(r) for r in G['UZ']['rings']]; NB = [np.asarray(r) for k, c in G.items() if k != 'UZ' for r in c['rings']]
    ADM1 = [np.asarray(r) for a in GA['adm1'] for r in a['r']]
    def inside(rings):
        m = np.zeros(hu * wu, bool); pts = np.c_[np.repeat(LONu[None], hu, 0).ravel(), np.repeat(LATu[:, None], wu, 1).ravel()]
        for r in rings: m |= MPath(r).contains_points(pts)
        return m.reshape(hu, wu)
    MUZ = inside(UZR)
    # the stations: the last 6 hours
    st = OV.stations(); obs = {}
    for line in OV.synops(hours=9).splitlines():
        p = line.split(',', 6)
        if len(p) < 7 or p[0] not in st: continue
        t = dt.datetime(int(p[1]), int(p[2]), int(p[3]), int(p[4]), int(p[5])); o = OV.decode(p[6])
        if o and 't' in o: obs.setdefault(t, {})[p[0]] = o
    terms = [t for t in sorted(obs) if t.hour % 3 == 0 and len(obs[t]) >= 8 and t >= now - dt.timedelta(hours=7)][-3:]
    print('obs terms', terms, flush=True)
    # the forecast frames: N in-between frames per interval, the clouds and the rain carried along the flow, the wind as particles
    fields = []
    E0 = fit_ext(55.9, 73.25, 37.15, 45.6, 0.02)  # the whole country, from the Ustyurt to the Fergana valley
    def sequence(fts, kind):
        N, dur = (6, 0.5) if kind == '12h' else (4, 0.42); stp = 1 if kind == '12h' else 3
        keys = [tuple(up(x) for x in field(t)) for t in fts]; nz = NOISE.copy(); out = []
        pr_rng = np.random.default_rng(3); NP, TR = 1500, 7
        spawn = lambda n: np.c_[pr_rng.uniform(E0[0], E0[1], n), pr_rng.uniform(E0[2], E0[3], n)]
        P = spawn(NP); age = pr_rng.integers(0, 40, NP); life = pr_rng.integers(25, 50, NP); hist = [P.copy() for _ in range(TR)]
        def step(u, v):
            nonlocal P, age, hist
            iy = np.clip(np.searchsorted(LATu, P[:, 1]), 0, hu - 1); ix = np.clip(np.searchsorted(LONu, P[:, 0]), 0, wu - 1)
            K = 0.008 if kind == '12h' else 0.011
            P = P + np.c_[u[iy, ix] * K / np.cos(np.radians(P[:, 1])), v[iy, ix] * K]; age += 1
            dead = (age > life) | (P[:, 0] < E0[0]) | (P[:, 0] > E0[1]) | (P[:, 1] < E0[2]) | (P[:, 1] > E0[3])
            if dead.any():
                P[dead] = spawn(int(dead.sum())); age[dead] = 0
                for h_ in hist: h_[dead] = P[dead]
            hist = hist[1:] + [P.copy()]
            return np.stack(hist).astype(np.float32)
        for i, t in enumerate(fts):
            t2a, pra, tca, msa, ua, va, fga = keys[i]
            if i == len(fts) - 1:
                for k in range(N):
                    fields.append(dict(t2=t2a, pr=pra, tcc=tca, msl=msa, fog=fga, nz=nz, tr=step(ua, va)))
                    out.append(dict(t=t, k=len(fields) - 1, ci=i, d=(1.2 if k == N - 1 else 0.5 / N)))
                break
            t2b, prb, tcb, msb, ub, vb, fgb = keys[i + 1]; fl = flow(gaussian_filter(sig(pra, tca), 2), gaussian_filter(sig(prb, tcb), 2))
            for k in range(N):
                s = k / N
                fields.append(dict(t2=(1 - s) * t2a + s * t2b, pr=(1 - s) * warp(pra, fl, s) + s * warp(prb, fl, s - 1), tcc=(1 - s) * warp(tca, fl, s) + s * warp(tcb, fl, s - 1),
                                   msl=(1 - s) * msa + s * msb, fog=(1 - s) * warp(fga, fl, s) + s * warp(fgb, fl, s - 1), nz=nz, tr=step((1 - s) * ua + s * ub, (1 - s) * va + s * vb)))
                out.append(dict(t=t + dt.timedelta(hours=round(s * stp)), k=len(fields) - 1, ci=i + (1 if s >= 0.5 else 0), d=dur / N))
                nz = warp(nz, fl, 1 / N)
        return out, keys
    def chart(keys, fts, mask, kind):
        pct, mx, sn, lab = [], [], [], []
        for (t2, pr, *_), t in zip(keys, fts):
            v = pr[mask]; pct.append(float((v >= 0.2).mean() * 100) if v.size else 0); mx.append(float(v.max()) if v.size else 0)
            sn.append(bool(v.size and (t2[mask][v >= 0.2] <= 0.5).mean() > 0.5) if (v >= 0.2).any() else False)
            loc = t + dt.timedelta(hours=5); lab.append(loc.strftime('%H') if kind == '12h' else (loc.strftime('%d.%m') if loc.hour < 3 else loc.strftime('%H')))
        return dict(pct=pct, mx=mx, snow=sn, lab=lab, every=(2 if kind == '12h' else 4))
    meta = {'run': run.strftime('%Y-%m-%dT%HZ'), 'made': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), 'obs': [t.strftime('%H:%MZ') for t in terms]}
    rel = {'uz': relief(E0, UZR)}; relE = {'uz': E0}; print('relief', flush=True)
    borders_uz = [(NB, '#68717d', 1.8, DOT, 0.9, 3), (ADM1, '#7c8794', 1.3, DOT, 0.8, 3.1), (UZR, '#1f2d3d', 3.0, DOT, 1.0, 3.3)]
    videos, charts, acc, t2end = {}, {}, {}, {}
    KINDS = os.environ.get('EV_KINDS', '12h,3d,7d').split(','); REGS = os.environ.get('EV_REGIONS')
    when = lambda t, X: X['at'].format(d=f"{X['wd'][(t + dt.timedelta(hours=5)).weekday()]} {(t + dt.timedelta(hours=5)).day} {X['mon'][(t + dt.timedelta(hours=5)).month - 1]}", h=(t + dt.timedelta(hours=5)).strftime('%H:%M'))
    for kind in ('12h', '3d'):
        fts = [now + dt.timedelta(hours=h) for h in (range(1, 13) if kind == '12h' else range(3, 73, 3))]
        fts = [t for t in fts if (t - run).total_seconds() / 3600 <= steps[-1]]
        seq, keys = sequence(fts, kind); print(kind, len(seq), 'forecast frames', flush=True)
        charts[kind] = chart(keys, fts, MUZ, kind)
        acc[kind] = sum(k[1] for k in keys[::(3 if kind == '12h' else 1)]); t2end[kind] = keys[-1][0]
        tot = {tw: atu(acc[kind], tw[2], tw[3]) for tw in TOWNS}; wet = max(tot.items(), key=lambda kv: kv[1]); meta[kind] = {'until': fts[-1].strftime('%Y-%m-%dT%HZ'), 'wettest': [wet[0][0], round(wet[1], 1)]}
        if kind == '12h': seq12, keys12, fts12 = seq, keys, fts
        if kind not in KINDS: continue
        for lang in LANGS:
            X = TX[lang]; L = 0 if lang == 'ru' else 1; frames = []
            for t in terms:
                pts = [(st[w]['lon'], st[w]['lat'], f"{o['t']:+.0f}" if round(o['t']) != 0 else '0', TCOL(o['t']),
                        OV.KC[OV.KI[OV.wx(o.get('ww'))]] if OV.wx(o.get('ww')) is not None else None, None, st[w]['main']) for w, o in obs[t].items()]
                frames.append(dict(mode='obs', t=t, d=1.3, pts=pts, badge=X['fact'], bc='#2e8b57', when=when(t, X), ci=None))
            for fr in seq:
                Fd = fields[fr['k']]; h_ = int((fr['t'] - now).total_seconds() // 3600); pts = []
                for tw in TOWNS[:12]:
                    v = atu(Fd['t2'], tw[2], tw[3]); mm = atu(Fd['pr'], tw[2], tw[3])
                    pts.append((tw[3], tw[2], f"{v:+.0f}" if round(v) != 0 else '0', TCOL(v), ('#7b4fd0' if v <= 0.5 else '#2f7fd1') if mm >= 0.3 else None, tw[L], True))
                frames.append(dict(mode='fc', t=fr['t'], k=fr['k'], d=fr['d'], ci=fr['ci'], pts=pts, badge=X['fc'] + (' · ' + X['plus'].format(h=h_) if h_ > 0 else ''), bc=ORANGE, when=when(fr['t'], X)))
            if kind == '3d':
                frames.append(dict(mode='total', t=None, d=3.0, ci=None, badge=X['total'], bc=ORANGE, when=None,
                                   pts=[(tw[3], tw[2], f"{tot[tw]:.0f}", '#ffffff', None, tw[L], True) for tw in TOWNS[:12]]))
            line = (X['wet3' if kind == '3d' else 'wet'].format(t=wet[0][L], mm=round(wet[1])) if wet[1] >= 1 else X['none3' if kind == '3d' else 'dry'])
            vk = f'{kind}_{lang}'
            videos[vk] = dict(lang=lang, kind=kind, ext=E0, rel='uz', borders=borders_uz, borders_c=borders_uz, wind=True, frames=frames, title=X['t12' if kind == '12h' else 't3'], line=line,
                              chart=kind, chart_t=X['chart'], dir=tempfile.mkdtemp(), out=str(OUT / f'{vk}.mp4'))
    # by days: 7 days from the last 00/12 UTC run (it reaches 10 days; the 06/18 runs only 90 hours)
    if '7d' in KINDS:
        run7 = run if run.hour in (0, 12) else run - dt.timedelta(hours=6)
        l7 = int((now - run7).total_seconds() // 3600)
        F7 = M.fetch(run7, [(s_, 'hres') for s_ in range(0, 175, 6) if s_ >= l7 - 24])
        st7 = sorted(F7); print('7d: run', run7, len(st7), 'steps', flush=True)
        loc0 = (now + dt.timedelta(hours=5)).replace(hour=0)
        days, keys7 = [], []
        for dd in range(7):
            a_ = loc0 + dt.timedelta(days=dd) - dt.timedelta(hours=5); b_ = a_ + dt.timedelta(days=1)
            La, Lb = max((a_ - run7).total_seconds() / 3600, l7), (b_ - run7).total_seconds() / 3600
            sa = max([x for x in st7 if x <= La], default=None); sb = min([x for x in st7 if x >= Lb], default=None)
            if sa is None or sb is None: break
            inn = [x for x in st7 if sa <= x <= sb]
            t2s = np.stack([cut(F7[x]['t2']) for x in inn])
            fgs = np.stack([fogidx(cut(F7[x]['t2']), cut(F7[x]['td2']) if 'td2' in F7[x] else cut(F7[x]['t2']) - 10, cut(F7[x].get('u10', F7[x]['u'])), cut(F7[x].get('v10', F7[x]['v']))) for x in inn])
            keys7.append(dict(t2=up(t2s.max(0)), tmin=up(t2s.min(0)), pr=up(np.maximum(cut(F7[sb]['tp']) - cut(F7[sa]['tp']), 0)), tcc=up(np.mean([cut(F7[x]['tcc']) for x in inn], 0)),
                              msl=up(np.mean([cut(F7[x]['msl']) for x in inn], 0)), fog=up(fgs.max(0)), nz=NOISE))
            days.append(loc0 + dt.timedelta(days=dd))
        if days:
            pct, mx, sn, lab = [], [], [], []
            for k_, d_ in zip(keys7, days):
                v_ = k_['pr'][MUZ]; pct.append(float((v_ >= 1).mean() * 100)); mx.append(float(v_.max())); sn.append(bool((k_['t2'][MUZ][v_ >= 1] <= 0.5).mean() > 0.5) if (v_ >= 1).any() else False)
                lab.append(f"{d_.day}.{d_.month:02d}")
            charts['7d'] = dict(pct=pct, mx=mx, snow=sn, lab=lab, every=1)
            wetd = int(np.argmax(mx)); meta['7d'] = {'days': [d_.strftime('%Y-%m-%d') for d_ in days], 'wettest_day': days[wetd].strftime('%Y-%m-%d'), 'mm': round(mx[wetd], 1)}
            for lang in LANGS:
                X = TX[lang]; L = 0 if lang == 'ru' else 1; frames = []
                for dd, (k_, d_) in enumerate(zip(keys7, days)):
                    fields.append(k_); kk = len(fields) - 1
                    pts = [(tw[3], tw[2], f"{atu(k_['t2'], tw[2], tw[3]):+.0f}", TCOL(atu(k_['t2'], tw[2], tw[3])),
                            ('#7b4fd0' if atu(k_['t2'], tw[2], tw[3]) <= 0.5 else '#2f7fd1') if atu(k_['pr'], tw[2], tw[3]) >= 1 else ('#8a96a3' if atu(k_['fog'], tw[2], tw[3]) > 0.5 else None),
                            f"{tw[L]} {atu(k_['tmin'], tw[2], tw[3]):+.0f}°", True) for tw in TOWNS[:12]]
                    dl = f"{X['wd'][d_.weekday()]} {d_.day} {X['mon'][d_.month - 1]}"
                    for j in range(5):
                        frames.append(dict(mode='day', t=d_, k=kk, d=(0.9 if j == 4 else 0.35), ci=dd, pts=pts, badge=f"{X['fc']} · {dl}", bc=ORANGE, when=X['d7'].format(i=dd + 1, n=len(days))))
                frames[-1]['d'] = 2.0
                dlw = days[wetd]; line = X['wet7'].format(d=f"{X['wd'][dlw.weekday()]} {dlw.day} {X['mon'][dlw.month - 1]}", mm=round(mx[wetd])) if mx[wetd] >= 1 else X['dry7']
                videos[f'7d_{lang}'] = dict(lang=lang, kind='7d', ext=E0, rel='uz', borders=borders_uz, borders_c=borders_uz, wind=False, frames=frames, title=X['t7'], line=line + ' · ' + X['nightc'] if len(line) < 34 else line,
                                            chart='7d', chart_t=X['chart7'], dir=tempfile.mkdtemp(), out=str(OUT / f'7d_{lang}.mp4'))
    # the regions: each one cut out whole, its districts, 12 hours
    (OUT / 'reg').mkdir(exist_ok=True); meta['regions'] = {}
    short = lambda n: n.replace(' р-н', '').replace(' tumani', '').replace(' шахри', '').replace(' shahri', '')
    for a in GA['adm1']:
        rid = a['id']; meta['regions'][str(rid)] = a['name']
        if REGS is not None and str(rid) not in REGS.split(','): continue
        rings = [np.asarray(r) for r in a['r']]; allp = np.vstack(rings)
        Er = fit_ext(allp[:, 0].min(), allp[:, 0].max(), allp[:, 1].min(), allp[:, 1].max(), 0.1)
        rel[f'r{rid}'] = relief(Er, UZR, rings); relE[f'r{rid}'] = Er
        mask = inside(rings); charts[f'r{rid}'] = chart(keys12, fts12, mask if mask.any() else MUZ, '12h')
        dis = [d for d in GA['adm2'] if d['p'] == rid]; DIS = [np.asarray(r) for d in dis for r in d['r']]
        tot = {}
        for d in dis: tot[d['name']['ru']] = (d, sum(atu(k[1], d['c'][1], d['c'][0]) for k in keys12[::3]))
        wet = max(tot.values(), key=lambda v: v[1]) if tot else (None, 0)
        bord = [(NB, '#68717d', 1.6, DOT, 0.9, 3), (ADM1, '#9aa3ad', 1.2, DOT, 0.8, 3), (DIS, '#9aa3ad', 1.1, DOT, 0.9, 3.1),
                (UZR, '#1f2d3d', 2.6, DOT, 1.0, 3.2), (rings, '#5b2a86', 3.4, (0, (6, 3, 1, 3)), 1.0, 3.4)]
        for lang in LANGS:
            X = TX[lang]; frames = []; big = len(dis) <= 16
            for fr in seq12[:12:2]:  # the whole country for a moment
                Fd = fields[fr['k']]
                pts = [(tw[3], tw[2], f"{atu(Fd['t2'], tw[2], tw[3]):+.0f}", TCOL(atu(Fd['t2'], tw[2], tw[3])), None, tw[0 if lang == 'ru' else 1], True) for tw in TOWNS[:12]]
                frames.append(dict(mode='fc', t=fr['t'], k=fr['k'], d=0.25, ci=fr['ci'], pts=pts, country=True, E=E0, relk='uz', badge=X['fc'], bc=ORANGE, when=when(fr['t'], X)))
            nzm = 16
            for j in range(1, nzm + 1):  # the camera flies down to the region
                f_ = (1 - math.cos(math.pi * j / nzm)) / 2; cxa, cya = (E0[0] + E0[1]) / 2, (E0[2] + E0[3]) / 2; cxb, cyb = (Er[0] + Er[1]) / 2, (Er[2] + Er[3]) / 2
                hw = ((E0[1] - E0[0]) / 2) ** (1 - f_) * ((Er[1] - Er[0]) / 2) ** f_; hh = ((E0[3] - E0[2]) / 2) ** (1 - f_) * ((Er[3] - Er[2]) / 2) ** f_
                cx_, cy_ = cxa + (cxb - cxa) * f_, cya + (cyb - cya) * f_; fr = seq12[min(12, len(seq12) - 1)]
                frames.append(dict(mode='fc', t=fr['t'], k=fr['k'], d=0.07, ci=fr['ci'], pts=[], country=True, E=(cx_ - hw, cx_ + hw, cy_ - hh, cy_ + hh), relk='uz' if f_ < 0.75 else f'r{rid}',
                                   badge=X['fc'], bc=ORANGE, when=when(fr['t'], X), zf=1.0))
            for fr in seq12[::2]:
                Fd = fields[fr['k']]; h_ = int((fr['t'] - now).total_seconds() // 3600); pts = []
                for d in dis:
                    x, y = d['c']; v = atu(Fd['t2'], y, x); mm = atu(Fd['pr'], y, x)
                    pts.append((x, y, f"{v:+.0f}" if round(v) != 0 else '0', TCOL(v), ('#7b4fd0' if v <= 0.5 else '#2f7fd1') if mm >= 0.3 else None, short(d['name'][lang]), big))
                frames.append(dict(mode='fc', t=fr['t'], k=fr['k'], d=fr['d'] * 2, ci=fr['ci'], pts=pts, badge=X['fc'] + (' · ' + X['plus'].format(h=h_) if h_ > 0 else ''), bc=ORANGE, when=when(fr['t'], X)))
            frames[-1]['d'] = 1.5
            line = X['reg_wet'].format(t=short(wet[0]['name'][lang]), mm=f"{wet[1]:.1f}".rstrip('0').rstrip('.')) if wet[1] >= 0.3 else X['reg_dry']
            videos[f'reg/{rid}_{lang}'] = dict(lang=lang, kind='12h', ext=Er, rel=f'r{rid}', borders=bord, borders_c=borders_uz + [(rings, '#5b2a86', 3.4, (0, (6, 3, 1, 3)), 1.0, 3.4)], wind=False, clip=rings, frames=frames,
                                               title=f"{a['name'][lang]} · {X['reg_t']}", line=line, chart=f'r{rid}', chart_t=X['chart_r'], dir=tempfile.mkdtemp(), out=str(OUT / 'reg' / f'{rid}_{lang}.mp4'))
    # the points for the bot: every town and every district, hour by hour for 12 hours (the caption under the video)
    def series(lo_, la_):
        return dict(t=[round(atu(k[0], la_, lo_), 1) for k in keys12], pr=[round(atu(k[1], la_, lo_) / 3, 2) for k in keys12], fog=[round(atu(k[6], la_, lo_), 2) for k in keys12])
    regof = lambda lo_, la_: next((a_['id'] for a_ in GA['adm1'] if any(MPath(np.asarray(r)).contains_point((lo_, la_)) for r in a_['r'])), None)
    pts_json = dict(run=meta['run'], made=meta['made'], hours=[(t + dt.timedelta(hours=5)).strftime('%H') for t in fts12],
                    towns=[dict(ru=tw[0], uz=tw[1], rid=regof(tw[3], tw[2]), **series(tw[3], tw[2])) for tw in TOWNS],
                    districts={str(a_['id']): [dict(ru=short(d['name']['ru']), uz=short(d['name']['uz']), c=[round(d['c'][0], 3), round(d['c'][1], 3)], **series(d['c'][0], d['c'][1])) for d in GA['adm2'] if d['p'] == a_['id']] for a_ in GA['adm1']})
    json.dump(pts_json, open(OUT / 'points.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    for v in videos.values():  # the camera: a slow zoom over the forecast; an opening of 0.8 s
        fs = v['frames']; nf = len(fs)
        for j, f_ in enumerate(fs):
            if 'zf' not in f_: f_['zf'] = 1 + 0.07 * j / max(1, nf - 1) if f_['mode'] != 'total' and not f_.get('country') and v['ext'] is not E0 else 1.0  # the country fills the width: no zoom, nothing cut
        intro = [dict(fs[0], intro=float(a_), d=0.08, zf=1.0) for a_ in np.linspace(1, 0, 10)]
        intro[0]['d'] = 0.6; v['frames'] = intro + fs
    print('relief done:', len(rel), 'maps;', sum(len(v['frames']) for v in videos.values()), 'frames to draw', flush=True)
    # draw everything in parallel (the forked workers share CTX), then encode
    CTX.update(videos=videos, fields=fields, rel=rel, relE=relE, charts=charts, acc=acc, t2end=t2end, sea=sea, LATu=LATu, LONu=LONu, ext=ext)
    jobs = [(vk, i) for vk, v in videos.items() for i in range(len(v['frames']))]
    with mp.get_context('fork').Pool(max(1, os.cpu_count() or 1)) as pool:
        for n_, _ in enumerate(pool.imap_unordered(render, jobs, chunksize=4)):
            if n_ % 200 == 0: print('frames', n_, '/', len(jobs), flush=True)
        for r in pool.imap_unordered(encode, list(videos)): print(r, flush=True)
    json.dump(meta, open(OUT / 'meta.json', 'w'), ensure_ascii=False)


if __name__ == '__main__':
    main()
