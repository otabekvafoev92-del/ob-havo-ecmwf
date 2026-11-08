"""The moisture coming in: a broadcast-style video of the next three days for Uzbekistan and Kazakhstan.
Every frame (30 minutes apart, smoothly interpolated from ECMWF's 3-hourly forecast):
  - the water vapour in the whole air column (TCWV, kg/m²): dry air light, moist air deep blue-green
  - the wind at about 3 km (700 hPa) as flowing streaks, the way the moisture travels
  - the precipitation (mm in 3 h) in radar colours where it falls
  - sea-level pressure isobars every 4 hPa with the highs (H/В/Y) and lows (L/Н/P)
  - countries, our regions, the main cities, the local time, legends, sound (wind, then rain)
  out/hr/<region>_moist_<lang>.mp4  (Full HD, about 14 s)
Data: ECMWF IFS open data (AWS mirror), the current run, steps 0…72 h.
Usage: python3 prob/moisture.py prob.npz out [--regions UZ,KZ] [--langs ru,uz] [--fields saved.npz]"""
import argparse, concurrent.futures as cf, datetime as dt, json, pathlib, shutil, subprocess, sys, tempfile
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import trajectory as TJ
from trajectory import ECM, get  # the same mirror and downloader

STEPS = list(range(0, 73, 3))
LON0, LON1, LAT0, LAT1, RES = 20.0, 100.0, 20.0, 60.0, 0.25
VIEW = {'UZ': (42.0, 80.0, 30.0, 49.0), 'KZ': (40.0, 92.0, 33.0, 57.5)}
TX = {'ru': dict(title='Откуда идёт дождь', tv_rain='дождь', tv_snow='снег', tv_flow='поток влаги', tv_cloud='облака', sub='стрелки — поток влажного воздуха · синее — дождь · сиреневое — снег', tcwv='Влажность воздуха', dry='сухо', wet='очень влажно', pr='Дождь / снег', prl='слабый', prh='ливень',
                 hi='В', lo='Н', hiw='антициклон · ясно', low='циклон · непогода', tz='по Ташкенту', src='влага: {s}', leg='путь влаги к городу',
                 c_intro='Оранжевые стрелки — куда ветер несёт влажный воздух. Синее — дождь, сиреневое — снег.', c_go='Влажный воздух от: {s} идёт к городу {c}', c_rain='Сейчас дождь: {c}', c_snow='Сейчас снег: {c}',
                 c_dry='Над страной сухо — дождя нет', c_wet='Влажный воздух над страной — возможны осадки', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']),
      'uz': dict(title='Yomg‘ir qayerdan keladi', tv_rain='yomg‘ir', tv_snow='qor', tv_flow='namlik oqimi', tv_cloud='bulutlar', sub='strelkalar — nam havo oqimi · ko‘k — yomg‘ir · binafsha — qor', tcwv='Havo namligi', dry='quruq', wet='juda nam', pr='Yomg‘ir / qor', prl='kuchsiz', prh='jala',
                 hi='Y', lo='P', hiw='antisiklon · ochiq havo', low='siklon · yomon havo', tz='Toshkent vaqti', src='namlik: {s}', leg='namlikning shaharga yo‘li',
                 c_intro='To‘q sariq strelkalar — shamol nam havoni qayerga olib ketmoqda. Ko‘k — yomg‘ir, binafsha — qor.', c_go='Nam havo ({s}) {c} shahriga kelmoqda', c_rain='Hozir yomg‘ir: {c}', c_snow='Hozir qor: {c}',
                 c_dry='Mamlakat ustida quruq — yomg‘ir yo‘q', c_wet='Mamlakat ustida nam havo — yog‘in bo‘lishi mumkin', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya']),
      'tr': dict(title='Yağmur nereden geliyor', tv_rain='yağmur', tv_snow='kar', tv_flow='nem akışı', tv_cloud='bulutlar', sub='oklar — nemli hava akışı · mavi — yağmur · mor — kar', tcwv='Havanın nemi', dry='kuru', wet='çok nemli', pr='Yağmur / kar', prl='hafif', prh='sağanak',
                 hi='Y', lo='A', hiw='antisiklon · açık', low='siklon · kötü hava', tz='TSİ', src='nem: {s}', leg='nemin şehre yolu',
                 c_intro='Turuncu oklar rüzgârın nemli havayı nereye taşıdığını gösterir. Mavi — yağmur, mor — kar.', c_go='Nemli hava ({s}) {c} şehrine geliyor', c_rain='Şu an yağmur: {c}', c_snow='Şu an kar: {c}',
                 c_dry='Ülke üzerinde hava kuru — yağmur yok', c_wet='Ülke üzerinde nemli hava — yağış olabilir', wd=['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'])}
# water vapour on a dark map: the dry air dark slate, the moist air glowing teal-green (the moisture stands out like on satellite water-vapour images)
TCWV_STOPS = [(0, '#1f2530'), (6, '#2a3340'), (12, '#2f4450'), (18, '#2e5a60'), (25, '#2d7470'), (32, '#3a927f'), (40, '#5fb08f'), (50, '#9ccf9f'), (70, '#e3f2c0')]  # dark dry air → glowing moist air
# precipitation, radar-like colours
PR_LV = [0.3, 1, 2, 4, 7, 12, 20, 40]
PR_COL = ['#8fd0ff', '#4aa8f5', '#2b6fe0', '#f2d94e', '#f29c38', '#e0503a', '#c23aa0']  # blue (light rain) → yellow → red → magenta: apart from the green-teal moisture


def fetch(run):
    """{step: dict(tcwv, msl hPa, tp mm (accumulated from 0), u, v)} on the area grid (rows south → north)."""
    d, hh = run.strftime('%Y%m%d'), run.strftime('%H')
    jobs = []
    for st in STEPS:
        idx = None
        for stream in (('oper', 'scda') if hh in ('00', '12') else ('scda', 'oper')):
            base = f'{ECM}/{d}/{hh}z/ifs/0p25/{stream}/{d}{hh}0000-{st}h-{stream}-fc'
            idx = get(base + '.index')
            if idx: break
        if not idx: print('moist: missing step', st, flush=True); continue
        for line in idx.decode().strip().split('\n'):
            x = json.loads(line); p = x.get('param')
            key = p if x.get('levtype') == 'sfc' and p in ('tcwv', 'msl', 'tp', 'tcc', '2t') else p if x.get('levtype') == 'pl' and x.get('levelist') == '700' and p in ('u', 'v') else None
            if key: jobs.append((st, key, base + '.grib2', (x['_offset'], x['_offset'] + x['_length'] - 1)))
    F = {}
    import eccodes
    def crop(buf):
        h = eccodes.codes_new_from_message(buf)
        v = eccodes.codes_get_values(h).reshape(eccodes.codes_get(h, 'Nj'), eccodes.codes_get(h, 'Ni')); eccodes.codes_release(h)
        lat = 90 - np.arange(v.shape[0]) * 0.25; lon = -180 + np.arange(v.shape[1]) * 0.25
        r = np.flatnonzero((lat <= LAT1 + 1e-6) & (lat >= LAT0 - 1e-6)); c = np.flatnonzero((lon >= LON0 - 1e-6) & (lon <= LON1 + 1e-6))
        return v[np.ix_(r, c)][::-1].astype(np.float32)
    with cf.ThreadPoolExecutor(12) as pool:
        for (st, key, url, rng), buf in zip(jobs, pool.map(lambda j: get(j[2], j[3]), jobs)):
            if buf: F.setdefault(st, {})[key] = crop(buf)
    out = {}
    for st, f in F.items():
        if all(k in f for k in ('tcwv', 'msl', 'u', 'v')):
            out[st] = {'tcwv': f['tcwv'], 'msl': f['msl'] / 100.0, 'tp': f.get('tp', np.zeros_like(f['tcwv'])) * 1000.0, 'u': f['u'], 'v': f['v'],
                       'tcc': f.get('tcc', np.clip((f['tcwv'] - 10) / 25, 0, 1)), 't2': f['2t'] - 273.15 if '2t' in f else np.full_like(f['tcwv'], 10.0)}
    print('moist: fields at', len(out), 'steps', flush=True)
    return out


def interp(F, h):
    """The fields at hour h (linear between the 3-hourly steps); precipitation as mm in the 3 h around h."""
    ks = sorted(F); j = int(np.clip(np.searchsorted(ks, h), 1, len(ks) - 1)); a = float(np.clip((h - ks[j - 1]) / (ks[j] - ks[j - 1]), 0, 1))
    A, B = F[ks[j - 1]], F[ks[j]]
    out = {k: A[k] * (1 - a) + B[k] * a for k in ('tcwv', 'msl', 'u', 'v', 'tcc', 't2') if k in A and k in B}
    rate = lambda i: np.clip(F[ks[i]]['tp'] - F[ks[i - 1]]['tp'], 0, None) if i >= 1 else np.zeros_like(A['tp'])  # mm in the 3 h before step i
    out['pr'] = rate(j) * (1 - abs(a - 0.5)) + (rate(j - 1) if a < 0.5 else rate(min(j + 1, len(ks) - 1))) * abs(a - 0.5)
    return out


_RELIEF = {}
def tv_base(x0, x1, y0, y1, n=1600):
    """A TV-weather base map in plain lon/lat: blue seas, land tinted by height (green lowlands, sand, brown mountains,
    white peaks) with soft hill shading, from the site's world height map."""
    key = (x0, x1, y0, y1, n)
    if key in _RELIEF: return _RELIEF[key]
    from PIL import Image
    from scipy.ndimage import map_coordinates, gaussian_filter
    import matplotlib.colors as mc
    v = np.asarray(Image.open(HERE.parent / 'site' / 'assets' / 'dem-world.png').convert('L'), float)
    H, Wd = v.shape; m = int(n * (y1 - y0) / (x1 - x0) / np.cos(np.radians((y0 + y1) / 2)))
    LO, LA = np.meshgrid(np.linspace(x0, x1, n), np.linspace(y1, y0, m))
    raw = map_coordinates(v, [(90 - LA) / 180 * H - 0.5, ((LO + 180) % 360) / 360 * Wd - 0.5], order=1, mode='nearest')
    land = raw >= 64; z = np.where(land, ((raw - 64) / 191) ** 2 * 8848, 0.0); z = gaussian_filter(z, 1.2)
    stops = [(0, '#c9dcae'), (400, '#dfe2b4'), (900, '#e9dcb0'), (1600, '#d9c39a'), (2600, '#bfa283'), (3600, '#a88d79'), (4600, '#e9e6e2'), (6000, '#ffffff')]
    zs = np.array([a for a, _ in stops]); cs = np.array([mc.to_rgb(c) for _, c in stops])
    rgb = np.stack([np.interp(z, zs, cs[:, k]) for k in range(3)], -1)
    gy, gx = np.gradient(z, 3000.0); az, alt = np.radians(315), np.radians(45)
    slope = np.arctan(np.hypot(gx, gy) * 6); asp = np.arctan2(-gx, gy)
    sh = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - asp)
    rgb = np.clip(rgb * (0.72 + 0.4 * sh[..., None]), 0, 1)
    sea = np.array(mc.to_rgb('#9cc6e4')); deep = np.array(mc.to_rgb('#7fb1da'))
    coast = gaussian_filter(land.astype(float), 3)
    water = sea * (0.6 + 0.4 * coast[..., None]) + deep * (0.4 - 0.4 * coast[..., None])
    out = np.where(land[..., None], rgb, water)
    _RELIEF[key] = out
    return out


def video_tv(F, region, lang, mp4, run, off=5, paths=()):
    """The TV-weather version: a light relief map, white clouds, blue rain and lilac snow, a few big soft arrows of the
    moisture flow, the highs and lows, the cities with their temperature and weather, one plain sentence at the bottom.
    Slow: one hour of weather each 0.17 s (30-minute frames at 6 per second), about 26 s."""
    import render as Rn
    from render import plt, matplotlib
    from scipy.ndimage import gaussian_filter, maximum_filter, minimum_filter
    from regions import NAMES
    from hourly import NAVY
    import matplotlib.patheffects as pe
    X = TX.get(lang, TX['ru'])
    x0, x1, y0, y1 = VIEW[region]
    k = np.cos(np.radians((y0 + y1) / 2)); span = (x1 - x0) * k / (12.8 / 7.2); cy = (y0 + y1) / 2; y0v, y1v = cy - span / 2, cy + span / 2
    lon = LON0 + np.arange(next(iter(F.values()))['tcwv'].shape[1]) * RES; lat = LAT0 + np.arange(next(iter(F.values()))['tcwv'].shape[0]) * RES
    ci = np.flatnonzero((lon >= x0 - 1) & (lon <= x1 + 1)); ri = np.flatnonzero((lat >= y0v - 1) & (lat <= y1v + 1))
    LON, LAT = np.meshgrid(lon[ci], lat[ri]); ext = (lon[ci[0]] - RES / 2, lon[ci[-1]] + RES / 2, lat[ri[0]] - RES / 2, lat[ri[-1]] + RES / 2)
    G = json.load(open(HERE / 'geo_world.json'))['countries']; GA = json.load(open(HERE / 'geo_admin.json')).get(region, {})
    fig = plt.figure(figsize=(12.8, 7.2), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(x0, x1); ax.set_ylim(y0v, y1v); ax.set_aspect(1 / k); ax.axis('off')
    ax.imshow(tv_base(x0, x1, y0v, y1v), extent=(x0, x1, y0v, y1v), origin='upper', zorder=0, aspect='auto', interpolation='bilinear')
    LC = matplotlib.collections.LineCollection
    near = lambda r: np.asarray(r)[:, 0].max() > x0 - 3 and np.asarray(r)[:, 0].min() < x1 + 3 and np.asarray(r)[:, 1].max() > y0v - 3 and np.asarray(r)[:, 1].min() < y1v + 3
    ax.add_collection(LC([np.asarray(r) for c in G.values() for r in c['rings'] if near(r)], colors='#6f7d8c', linewidths=0.7, alpha=0.7, zorder=4))
    own = [np.asarray(r) for r in G.get(region, {}).get('rings', [])]
    if GA: ax.add_collection(LC([np.asarray(r) for a in GA['adm1'] for r in a['r']], colors='#7f8c99', linewidths=0.4, alpha=0.5, zorder=4))
    ax.add_collection(LC(own, colors='#ffffff', linewidths=4.5, alpha=0.8, zorder=4.4)); ax.add_collection(LC(own, colors=NAVY, linewidths=1.8, zorder=4.5))
    pl = sorted([p for p in json.load(open(HERE / 'geo_prob.json'))['places'] if p.get('iso') == region and x0 + 0.8 < p['lon'] < x1 - 0.8], key=lambda p: -p.get('pop', 0))[:7]
    # the frame: a title badge, the clock, and a TV "lower third" bar with the sentence and a small key
    fig.text(0.016, 0.952, f" {NAMES[region][lang]} · {X['title']} ", fontsize=18, fontfamily=Rn.DISPLAY, fontweight='bold', color='#ffffff', va='center', zorder=20,
             bbox=dict(boxstyle='round,pad=0.45,rounding_size=0.5', fc=NAVY, ec='none'))
    clock = fig.text(0.984, 0.952, '', fontsize=16, fontfamily=Rn.DISPLAY, fontweight='bold', color=NAVY, ha='right', va='center', zorder=20,
                     bbox=dict(boxstyle='round,pad=0.45,rounding_size=0.5', fc='#ffffffee', ec='none'))
    fig.patches.append(matplotlib.patches.Rectangle((0, 0), 1, 0.105, transform=fig.transFigure, facecolor=NAVY, edgecolor='none', alpha=0.94, zorder=19))
    fig.patches.append(matplotlib.patches.Rectangle((0, 0.105), 1, 0.006, transform=fig.transFigure, facecolor='#f0b88a', edgecolor='none', zorder=19))
    cap = fig.text(0.02, 0.052, '', fontsize=17, fontweight='bold', color='#ffffff', va='center', zorder=21)
    kx = 0.70
    for sym, col, lab in (('■', '#3d8be0', X['tv_rain']), ('■', '#b9a3ec', X['tv_snow']), ('➜', '#ffb15c', X['tv_flow'])):
        t_ = fig.text(kx, 0.052, f"{sym} {lab}", fontsize=11, color='#ffffff', va='center', zorder=21); t_.set_color('#ffffff')
        fig.text(kx, 0.052, sym, fontsize=11, color=col, va='center', zorder=22)
        kx += 0.035 + 0.0085 * len(lab)
    fig.text(0.984, 0.016, 'ECMWF · osmon', fontsize=7.5, color='#9fb0c2', ha='right', zorder=21)
    halo = [pe.withStroke(linewidth=3, foreground='#ffffff')]
    dyn = []; fdir = pathlib.Path(tempfile.mkdtemp()); hours = list(np.arange(0, 72.01, 0.5)); levels = []
    from matplotlib.path import Path
    pts_ = np.c_[LON.ravel(), LAT.ravel()]; land = np.zeros(len(pts_), bool)
    for r in own: land |= Path(r).contains_points(pts_)
    land = land.reshape(LON.shape)
    cgx = [int(round((p['lon'] - lon[ci[0]]) / RES)) for p in pl]; cgy = [int(round((p['lat'] - lat[ri[0]]) / RES)) for p in pl]
    seeds = np.c_[np.repeat(np.linspace(x0 + 1, x1 - 1, 9), 6), np.tile(np.linspace(y0v + 1, y1v - 1, 6), 9)]  # fixed starts: the arrows change smoothly
    # where the city tags and the source labels go: placed once (they do not move), never over each other
    fig.canvas.draw(); rnd = fig.canvas.get_renderer(); boxes = []
    def place(x, y, txt, fs, cands):
        for dx, dy, ha, va in cands:
            t_ = ax.text(x + dx, y + dy, txt, fontsize=fs, fontweight='bold', ha=ha, va=va, bbox=dict(boxstyle='round,pad=0.3', fc='w', ec='none'))
            bb = t_.get_window_extent(rnd).expanded(1.06, 1.15); t_.remove()
            if bb.y0 > 0.12 * fig.bbox.height and bb.y1 < 0.9 * fig.bbox.height and bb.x0 > 4 and bb.x1 < fig.bbox.width - 4 and not any(bb.overlaps(o) for o in boxes):
                boxes.append(bb); return (x + dx, y + dy, ha, va)
        return None
    tagpos = [place(p['lon'], p['lat'], f"☂ {Rn.city_name(p, lang)}  +00°", 10, [(0.3, 0.25, 'left', 'bottom'), (0.3, -0.25, 'left', 'top'), (-0.3, 0.25, 'right', 'bottom'), (-0.3, -0.25, 'right', 'top')]) for p in pl]
    srcpos = []
    for pa in paths:
        q = np.array(pa['path']); inside = [i for i in range(len(q)) if x0 + 1.5 < q[i, 0] < x1 - 1.5 and y0v + span * 0.2 < q[i, 1] < y1v - span * 0.12]
        lab = None
        if inside:
            i = max(inside); off_map = i < len(q) - 1
            txt = (lambda t: t[:1].upper() + t[1:])(X['src'].format(s=pa['src'][lang])) + (' ↙' if off_map and q[-1, 0] < q[i, 0] else ' ↘' if off_map else '')
            pos = place(q[i, 0], q[i, 1], txt, 11, [(0, 0, 'center', 'center'), (0, 1.0, 'center', 'center'), (0, -1.0, 'center', 'center'), (1.5, 0, 'left', 'center'), (-1.5, 0, 'right', 'center')])
            if pos: lab = (pos, txt)
        srcpos.append(lab)
    for f, h in enumerate(hours):
        for a in dyn:
            try: a.remove()
            except Exception: pass
        dyn = []
        Q = interp(F, h); sub = lambda A_: A_[np.ix_(ri, ci)]
        P = gaussian_filter(sub(Q['pr']), 1.0); C = gaussian_filter(sub(Q['tcc']), 1.5); T2 = sub(Q['t2']); M = gaussian_filter(sub(Q['msl']), 2.5)
        Wv = gaussian_filter(sub(Q['tcwv']), 1.2); U, V = gaussian_filter(sub(Q['u']), 2), gaussian_filter(sub(Q['v']), 2)
        # clouds: soft white, thicker where the sky is closed
        cl = np.zeros(C.shape + (4,)); cl[..., :3] = 1.0; cl[..., 3] = np.clip((C - 0.25) / 0.75, 0, 1) ** 1.3 * 0.62
        dyn.append(ax.imshow(cl, extent=ext, origin='lower', zorder=2, aspect='auto', interpolation='bilinear'))
        # rain blue, snow lilac (where it is at or below freezing), stronger = deeper
        for mask, col in ((T2 > 0.5, '#3d8be0'), (T2 <= 0.5, '#b9a3ec')):
            A_ = np.where(mask, P, 0)
            if A_.max() >= 0.3:
                rgba = np.zeros(A_.shape + (4,)); rgba[..., :3] = matplotlib.colors.to_rgb(col)
                rgba[..., 3] = np.clip((A_ - 0.2) / 3.0, 0, 1) ** 0.6 * 0.85
                dyn.append(ax.imshow(rgba, extent=ext, origin='lower', zorder=2.5, aspect='auto', interpolation='bilinear'))
        # the moisture flow: a few big soft arrows where moist air moves (water vapour × wind), thicker where it carries more
        for ln_, hd_ in flow_arrows(U, V, Wv, LON, LAT, (x0, x1, y0v + span * 0.12, y1v)):
            dyn += ax.plot(ln_[:, 0], ln_[:, 1], color='#ff9a3c', lw=hd_, alpha=0.75, solid_capstyle='round', zorder=3.5)
            ar = matplotlib.patches.FancyArrowPatch(ln_[-3], ln_[-1], arrowstyle='-|>', mutation_scale=12 + 2.5 * hd_, color='#ff9a3c', alpha=0.9, zorder=3.6, lw=0)
            ax.add_patch(ar); dyn.append(ar)
        # highs and lows, big, with a word
        mx, mn = maximum_filter(M, size=31) == M, minimum_filter(M, size=31) == M
        for mask, lab, word, col in ((mx, X['hi'], X['hiw'], '#1f5fbf'), (mn, X['lo'], X['low'], '#c8382c')):
            for (yy, xx) in zip(*np.nonzero(mask)):
                if 4 < yy < M.shape[0] - 4 and 4 < xx < M.shape[1] - 4 and abs(M[yy, xx] - np.median(M)) > 3 and y0v + 2 < LAT[yy, xx] < y1v - 2:
                    dyn.append(ax.text(LON[yy, xx], LAT[yy, xx], lab, fontsize=30, fontweight='bold', color=col, ha='center', va='center', zorder=7, path_effects=halo))
                    dyn.append(ax.text(LON[yy, xx], LAT[yy, xx] - 1.15, word, fontsize=10, fontweight='bold', color=col, ha='center', va='center', zorder=7, path_effects=halo))
        # the cities: a white tag with the weather and the temperature
        wet_c = []
        for p, gx_, gy_ in zip(pl, cgx, cgy):
            if not (0 <= gy_ < P.shape[0] and 0 <= gx_ < P.shape[1]): continue
            pr, tt, cc = P[gy_, gx_], T2[gy_, gx_], C[gy_, gx_]
            sym = ('❄' if tt <= 0.5 else '☂') if pr >= 0.6 else '☁' if cc >= 0.65 else '☀'
            scol = '#3d8be0' if sym == '☂' else '#8a6fd6' if sym == '❄' else '#7d8b99' if sym == '☁' else '#f0a020'
            if pr >= 0.6: wet_c.append((Rn.city_name(p, lang), sym == '❄'))
            dyn += ax.plot(p['lon'], p['lat'], 'o', ms=5, mfc=NAVY, mec='#ffffff', mew=1.2, zorder=8)
            tp = tagpos[pl.index(p)]
            if tp:
                tx_, ty_, ha_, va_ = tp
                tg_ = ax.text(tx_, ty_, f"{sym} {Rn.city_name(p, lang)}  {'+' if tt > 0.5 else ''}{tt:.0f}°", fontsize=10, fontweight='bold', color=NAVY, zorder=9, ha=ha_, va=va_,
                              bbox=dict(boxstyle='round,pad=0.3,rounding_size=0.5', fc='#ffffffee', ec=scol if sym in '☂❄' else 'none', lw=1.6))
                dyn.append(tg_)
        # the moisture source labels (from the air's path), where the path comes into the picture
        for lab in srcpos:
            if lab:
                (sx_, sy_, ha_, va_), txt = lab
                dyn.append(ax.text(sx_, sy_, txt, fontsize=11, fontweight='bold', color='#1d2a3a', ha=ha_, va=va_, zorder=9.5, bbox=dict(boxstyle='round,pad=0.35,rounding_size=0.5', fc='#ffb15c', ec='#ffffff', lw=1.2)))
        # one plain sentence
        flying = [pa for pa in paths if 0 <= pa['h'] - h <= np.array(pa['path'])[-1, 2]]
        if f < 24: msg = X['c_intro']
        elif wet_c: msg = (X['c_snow'] if all(s_ for _, s_ in wet_c) else X['c_rain']).format(c=', '.join(n for n, _ in wet_c[:3]))
        elif flying: msg = X['c_go'].format(s=flying[0]['src'][lang], c=next((Rn.city_name(p, lang) for p in pl if p.get('ru') == flying[0]['city']), flying[0]['city']))
        else: msg = X['c_wet'] if (land.any() and float(np.mean(Wv[land] >= 25)) > 0.4) else X['c_dry']
        cap.set_text(msg)
        t = run + dt.timedelta(hours=float(h) + off); clock.set_text(f"{X['wd'][t.weekday()]} {t:%d.%m} · {t:%H}:{t:%M} {X['tz']}")
        fig.savefig(fdir / f'{f:03d}.png', dpi=150)
        wet = float(np.mean(P[land] >= 1)) if land.any() else 0.0
        levels.append({'rain': min(1.0, wet * 2.5), 'snow': False, 'wind': float(np.clip(np.nanmean(np.hypot(U, V)) / 22, 0.15, 0.7)), 'storm': 0.0})
    plt.close(fig)
    for e in range(18): shutil.copy(fdir / f'{len(hours) - 1:03d}.png', fdir / f'{len(hours) + e:03d}.png'); levels.append(levels[-1])
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '6', '-i', str(fdir / '%03d.png'), '-vf', 'framerate=fps=24:interp_start=0:interp_end=255:scene=100,scale=1920:-2:flags=lanczos,format=yuv420p',
                    '-c:v', 'libx264', '-crf', '22', '-preset', 'medium', '-movflags', '+faststart', str(mp4)], check=True)
    try:
        import sound as S_
        S_.mux(mp4, S_.track(levels, 1 / 6, str(mp4) + '.wav', mode='all'))
    except Exception as e: print('moist sound failed', e, flush=True)
    Rn.fit_size(mp4)
    shutil.rmtree(fdir)


STORY = {
  'ru': dict(title='Откуда придёт дождь', sub='прогноз на 3 дня', s1_sea='Влага поднимается над водой: {s}', s1_land='Влажный воздух приходит из страны: {s}', s2='Ветер несёт эти облака к городу {c}',
             s3='{d} — {w} в городе {c}', rain='дождь', snow='снег', none='В ближайшие 3 дня дождя не ожидается', sum='Итог: откуда придут осадки', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']),
  'uz': dict(title='Yomg‘ir qayerdan keladi', sub='3 kunlik prognoz', s1_sea='Namlik suv ustida ko‘tariladi: {s}', s1_land='Nam havo shu davlatdan keladi: {s}', s2='Shamol bu bulutlarni {c} shahriga olib keladi',
             s3='{d} — {c} shahrida {w}', rain='yomg‘ir', snow='qor', none='Yaqin 3 kunda yomg‘ir kutilmaydi', sum='Xulosa: yog‘in qayerdan keladi', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya']),
  'tr': dict(title='Yağmur nereden gelecek', sub='3 günlük tahmin', s1_sea='Nem suyun üzerinde yükseliyor: {s}', s1_land='Nemli hava şu ülkeden geliyor: {s}', s2='Rüzgâr bu bulutları {c} şehrine taşıyor',
             s3='{d} — {c} şehrinde {w}', rain='yağmur', snow='kar', none='Önümüzdeki 3 günde yağmur beklenmiyor', sum='Özet: yağış nereden gelecek', wd=['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'])}


def video(F, region, lang, mp4, run, off=5, paths=()):
    """The plainest version: a story in three steps per city, on a calm light map, no weather fields at all.
    1) where the moisture rises (a pulsing drop at the sea or the country it comes from), 2) a thick arrow grows
    along the real path of the air (ECMWF) while a cloud travels on it, 3) the rain (or snow) falls on the city, with
    the day. A big plain sentence explains each step; at the end, a summary. About 3 s per step, sound of wind and rain."""
    import render as Rn
    from render import plt, matplotlib
    from regions import NAMES
    from hourly import NAVY
    import matplotlib.patheffects as pe
    X = STORY.get(lang, STORY['ru'])
    G, POLYS = TJ.load_polys()
    own = [np.asarray(r) for r in G.get(region, {}).get('rings', [])]
    # the view: our country and every path's start, in 16:9
    pts = np.vstack(own + [np.array(p['path'])[:, :2] for p in paths]) if paths else np.vstack(own)
    x0, x1, y0, y1 = pts[:, 0].min() - 2.5, pts[:, 0].max() + 2.5, pts[:, 1].min() - 2, pts[:, 1].max() + 2
    k = np.cos(np.radians((y0 + y1) / 2)); asp = 12.8 / (7.2 * 0.84)
    if (x1 - x0) * k / (y1 - y0) < asp: c = (x0 + x1) / 2; w = (y1 - y0) * asp / k; x0, x1 = c - w / 2, c + w / 2
    else: c = (y0 + y1) / 2; h_ = (x1 - x0) * k / asp; y0, y1 = c - h_ / 2, c + h_ / 2
    fig = plt.figure(figsize=(12.8, 7.2), dpi=150); fig.patch.set_facecolor(NAVY)
    ax = fig.add_axes([0, 0.16, 1, 0.84]); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect(1 / k); ax.axis('off')
    # a soft relief map (height-tinted land, blue seas), slightly washed out so the story drawn on it stands out
    base = tv_base(x0, x1, y0, y1, n=1400); base = base * 0.82 + 0.18
    ax.imshow(base, extent=(x0, x1, y0, y1), origin='upper', zorder=0, aspect='auto', interpolation='bilinear')
    PC, LC = matplotlib.collections.PolyCollection, matplotlib.collections.LineCollection
    near = lambda r: np.asarray(r)[:, 0].max() > x0 - 3 and np.asarray(r)[:, 0].min() < x1 + 3 and np.asarray(r)[:, 1].max() > y0 - 3 and np.asarray(r)[:, 1].min() < y1 + 3
    ax.add_collection(LC([np.asarray(r) for iso, c_ in G.items() if iso != region for r in c_['rings'] if near(r)], colors='#8f9aa5', linewidths=0.7, alpha=0.6, zorder=1))
    ax.add_collection(PC(own, facecolor='#ffffff55', edgecolor='none', zorder=1.8))
    ax.add_collection(LC(own, colors='#ffffff', linewidths=6, alpha=0.9, zorder=2)); ax.add_collection(LC(own, colors=NAVY, linewidths=2.2, zorder=2.1))
    for iso, c_ in G.items():  # country names, faint
        if iso == region or not c_['rings']: continue
        big = max((np.asarray(r) for r in c_['rings']), key=len); cx_, cy_ = big[:, 0].mean(), big[:, 1].mean()
        if x0 + 1.5 < cx_ < x1 - 1.5 and y0 + 1 < cy_ < y1 - 1 and len(big) > 30:
            ax.text(cx_, cy_, (TJ.UZN.get(iso) if lang == 'uz' else c_.get(lang)) or c_.get('name', iso), fontsize=10, color='#5f6c78', ha='center', va='center', zorder=1.5, alpha=0.8, path_effects=[pe.withStroke(linewidth=2.5, foreground='#ffffffaa')])
    ax.text(*np.array(own[0]).mean(0), NAMES[region][lang].upper(), fontsize=15, color=NAVY, alpha=0.45, fontweight='bold', ha='center', va='center', zorder=2.2)
    # the frame: title, a big sentence bar at the bottom with the step number
    fig.text(0.02, 0.955, f" {X['title']} ", fontsize=22, fontfamily=Rn.DISPLAY, fontweight='bold', color='#ffffff', va='center', zorder=20, bbox=dict(boxstyle='round,pad=0.4,rounding_size=0.5', fc=NAVY, ec='none'))
    fig.text(0.024, 0.885, X['sub'], fontsize=13, fontweight='bold', color=NAVY, va='center', zorder=20, path_effects=[pe.withStroke(linewidth=3, foreground='#ffffff')])
    fig.patches.append(matplotlib.patches.Rectangle((0, 0), 1, 0.16, transform=fig.transFigure, facecolor=NAVY, edgecolor='none', zorder=19))
    step = fig.text(0.03, 0.08, '', fontsize=30, fontfamily=Rn.DISPLAY, fontweight='bold', color='#f0b88a', va='center', zorder=21)
    dots = [fig.text(0.03 + 0.022 * i, 0.03, '●', fontsize=11, color='#4a5b70', va='center', zorder=21) for i in range(3)]
    def set_step(i):  # the number and the three dots of the story's steps
        step.set_text(str(i) if i else '')
        for j_, d_ in enumerate(dots): d_.set_color('#f0b88a' if i and j_ < i else '#4a5b70')
    sent = fig.text(0.1, 0.08, '', fontsize=21, fontweight='bold', color='#ffffff', va='center', zorder=21)
    fig.text(0.985, 0.02, 'ECMWF · osmon', fontsize=8, color='#9fb0c2', ha='right', zorder=21)
    halo = [pe.withStroke(linewidth=3.5, foreground='#ffffff')]
    def drop(x, y, s, a=1.0):  # a teardrop shape
        t = np.linspace(0, 2 * np.pi, 60); r = s * (1 - np.sin(t)) / 2
        xs, ys = x + r * np.cos(t) * 0.75 / k, y + r * np.sin(t) * 0.75 + s * 0.35
        return ax.fill(xs, ys, color='#2f7fd8', alpha=a, zorder=8, ec='#ffffff', lw=2)
    def cloud(x, y, s, a=1.0):
        out = []
        for dx, dy, r in ((-0.55, 0, 0.42), (0, 0.22, 0.55), (0.55, 0, 0.42), (0, -0.1, 0.45)):
            out.append(matplotlib.patches.Ellipse((x + dx * s / k, y + dy * s), 2 * r * s / k, 2 * r * s, fc='#ffffff', ec='#7d8b99', lw=1.6, alpha=a, zorder=8.5))
        for o in out: ax.add_patch(o)
        return out
    frames = []; fdir = pathlib.Path(tempfile.mkdtemp()); n = [0]; lv = []
    def shot(snd):
        fig.savefig(fdir / f'{n[0]:04d}.png', dpi=150, facecolor=fig.get_facecolor()); n[0] += 1; lv.append(snd)
    FPS, S = 12, 1.0 * (x1 - x0) / 40  # S: the size of the drawings relative to the map
    keep = []  # what stays on the map after each city's story
    sent.set_text(X['sub'].capitalize()); set_step(0)
    for _ in range(24): shot({'wind': 0.15})
    if not paths:
        sent.set_text(X['none'] + ' ☀'); [shot({'wind': 0.15}) for _ in range(48)]
    cols = ['#2f7fd8', '#e0703a', '#7a5bd0']
    for j, pa in enumerate(paths):
        q = np.array(pa['path'])[::-1]  # oldest first
        inside = [i for i in range(len(q)) if x0 + 0.5 < q[i, 0] < x1 - 0.5 and y0 + 0.5 < q[i, 1] < y1 - 0.5]
        if not inside: continue
        q = q[inside[0]:]; dense = np.vstack([np.linspace(q[i], q[i + 1], 6, endpoint=False) for i in range(len(q) - 1)] + [q[-1:]])[:, :2]
        is_sea = pa['src']['ru'] in TJ.SEA_NOM.values() or 'залив' in pa['src']['ru'] or 'море' in pa['src']['ru']
        t_arr = run + dt.timedelta(hours=pa['h'] + off); snow = pa.get('snow', False)
        city = next((Rn.city_name(p, lang) for p in json.load(open(HERE / 'geo_prob.json'))['places'] if p.get('ru') == pa['city']), pa['city'])
        dyn = []
        def clear():
            for a in dyn:
                try: a.remove()
                except Exception: pass
            dyn.clear()
        # 1) the source: the sea it crossed, else the country where the path starts on the map (where the drop is)
        sx, sy = dense[0]
        if not is_sea:
            iso = TJ.country_at(sx, sy, POLYS)
            if iso and iso != region: pa = {**pa, 'src': {l: TJ.cname(iso, l, G) for l in ('ru', 'uz', 'tr')}}
        set_step(1); sent.set_text((X['s1_sea'] if is_sea else X['s1_land']).format(s=pa['src'][lang]))
        lab = ax.text(sx, sy - 1.3 * S, pa['src'][lang], fontsize=13, fontweight='bold', color=NAVY, ha='center', va='top', zorder=9, path_effects=halo)
        for f in range(36):
            clear(); pulse = 1 + 0.15 * np.sin(f / 3)
            rr = (f % 18) / 18; dyn += ax.plot(sx, sy + 0.4 * S, 'o', ms=20 + 50 * rr, mfc='none', mec='#2f7fd8', mew=3 * (1 - rr), alpha=1 - rr, zorder=7.5)
            dyn += drop(sx, sy, 1.1 * S * pulse)
            shot({'wind': 0.2})
        # 2) the arrow grows along the path, a cloud rides on its head
        set_step(2); sent.set_text(X['s2'].format(c=city))
        for f in range(48):
            clear(); m = max(2, int(len(dense) * (f + 1) / 48)); seg = dense[:m]
            dyn += ax.plot(seg[:, 0], seg[:, 1], color=cols[j % 3], lw=9, alpha=0.9, solid_capstyle='round', zorder=6, path_effects=[pe.withStroke(linewidth=13, foreground='#ffffff')])
            if m >= 3:
                ar = matplotlib.patches.FancyArrowPatch(seg[-3], seg[-1], arrowstyle='-|>', mutation_scale=45, color=cols[j % 3], zorder=6.5, lw=0); ax.add_patch(ar); dyn.append(ar)
            dyn += drop(sx, sy, 1.0 * S, 0.6); dyn += cloud(seg[-1, 0], seg[-1, 1] + 0.9 * S, 0.9 * S)
            shot({'wind': 0.25 + 0.4 * f / 48})
        # 3) the rain (or snow) at the city, with the day
        set_step(3); sent.set_text(X['s3'].format(d=f"{X['wd'][t_arr.weekday()]} {t_arr:%d.%m}", w=X['snow'] if snow else X['rain'], c=city))
        cx, cy = pa['lon'], pa['lat']; rng = np.random.default_rng(j)
        tag = ax.text(cx, cy - 1.0 * S, f"{city} · {X['wd'][t_arr.weekday()]} {t_arr:%d.%m}", fontsize=13, fontweight='bold', color=NAVY, ha='center', va='top', zorder=9.5,
                      bbox=dict(boxstyle='round,pad=0.35,rounding_size=0.6', fc='#ffffff', ec=cols[j % 3], lw=2))
        drops = np.c_[rng.uniform(-1.1, 1.1, 26) * S / k, rng.uniform(0, 1.6, 26) * S]
        for f in range(40):
            clear()
            dyn += ax.plot(dense[:, 0], dense[:, 1], color=cols[j % 3], lw=9, alpha=0.9, solid_capstyle='round', zorder=6, path_effects=[pe.withStroke(linewidth=13, foreground='#ffffff')])
            dyn += cloud(cx, cy + 1.9 * S, 1.0 * S)
            yy = (drops[:, 1] - f * 0.12 * S) % (1.6 * S)
            if snow: dyn += ax.plot(cx + drops[:, 0], cy + yy, '*', ms=9, color='#8a6fd6', zorder=8)
            else: dyn.append(ax.add_collection(LC([[(cx + dx, cy + y_), (cx + dx - 0.05 * S / k, cy + y_ - 0.35 * S)] for dx, y_ in zip(drops[:, 0], yy)], colors='#2f7fd8', linewidths=2.2, zorder=8)))
            dyn += ax.plot(cx, cy, 'o', ms=10, mfc=NAVY, mec='#ffffff', mew=2, zorder=9)
            shot({'rain': 0.0 if snow else 0.6, 'snow': snow, 'wind': 0.3})
        clear(); lab.remove(); tag.remove()
        keep += ax.plot(dense[:, 0], dense[:, 1], color=cols[j % 3], lw=5, alpha=0.45, solid_capstyle='round', zorder=5)
        keep.append(ax.text(cx, cy - 0.9 * S, f"{'❄' if snow else '☂'} {city} · {X['wd'][t_arr.weekday()]} {t_arr:%d.%m}", fontsize=11, fontweight='bold', color=NAVY, ha='center', va='top', zorder=9,
                            bbox=dict(boxstyle='round,pad=0.3,rounding_size=0.5', fc='#ffffffee', ec=cols[j % 3], lw=1.5)))
        keep.append(ax.text(sx, sy - 0.6 * S, pa['src'][lang], fontsize=11, fontweight='bold', color=cols[j % 3], ha='center', va='top', zorder=9, path_effects=halo))
        keep += ax.plot(sx, sy, 'o', ms=9, mfc=cols[j % 3], mec='#ffffff', mew=2, zorder=8)
    if paths:  # the summary: every path at once
        set_step(0); sent.set_text(X['sum'])
        for _ in range(48): shot({'wind': 0.15})
    plt.close(fig)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', str(FPS), '-i', str(fdir / '%04d.png'), '-vf', 'scale=1920:-2:flags=lanczos,format=yuv420p', '-c:v', 'libx264', '-crf', '21',
                    '-preset', 'medium', '-movflags', '+faststart', str(mp4)], check=True)
    try:
        import sound as S_
        S_.mux(mp4, S_.track([{'rain': 0, 'snow': False, 'wind': 0.2, 'storm': 0, **l} for l in lv], 1 / FPS, str(mp4) + '.wav', mode='all'))
    except Exception as e: print('moist sound failed', e, flush=True)
    Rn.fit_size(mp4)
    shutil.rmtree(fdir)


def flow_arrows(U, V, Wv, LON, LAT, box, n=5):
    """A few big arrows of the moisture flow, the way TV weather draws them: start at the strongest streams of moist air
    (water vapour × wind), follow the wind 6° back and 9° forward while the air stays moist. [(line, width), ...]"""
    x0, x1, y0, y1 = box
    ivt = Wv * np.hypot(U, V); res = LON[0, 1] - LON[0, 0]
    def at(F, x, y):
        fx, fy = (x - LON[0, 0]) / res, (y - LAT[0, 0]) / res
        if not (0 <= fx < F.shape[1] - 1 and 0 <= fy < F.shape[0] - 1): return np.nan
        i, j = int(fy), int(fx); a, b = fy - i, fx - j
        return (1 - a) * ((1 - b) * F[i, j] + b * F[i, j + 1]) + a * ((1 - b) * F[i + 1, j] + b * F[i + 1, j + 1])
    moist = Wv >= 20
    if moist.sum() < 20: return []
    thr = np.percentile(ivt[moist], 70)
    cand = [(ivt[i, j], LON[i, j], LAT[i, j]) for i in range(0, ivt.shape[0], 4) for j in range(0, ivt.shape[1], 4)
            if moist[i, j] and ivt[i, j] >= thr and x0 + 1 < LON[i, j] < x1 - 1 and y0 + 1 < LAT[i, j] < y1 - 1]
    cand.sort(reverse=True); seeds = []
    for q, x, y in cand:
        if all(np.hypot(x - a, y - b) > 4.0 for _, a, b in seeds): seeds.append((q, x, y))
        if len(seeds) >= n: break
    if not seeds: return []
    top = seeds[0][0]; out = []
    for q, x, y in seeds:
        def walk(sign, length):
            pts, cx, cy, L = [], x, y, 0.0
            while L < length:
                u, v = at(U, cx, cy), at(V, cx, cy); w = at(Wv, cx, cy)
                if not np.isfinite(u) or not np.isfinite(w) or w < 14: break
                sp = np.hypot(u, v * 1.0) + 1e-6; dx, dy = sign * 0.3 * u / sp, sign * 0.3 * v / sp
                cx, cy = cx + dx / np.cos(np.radians(cy)) * 0.8, cy + dy; L += 0.3
                if not (x0 < cx < x1 and y0 < cy < y1): break
                pts.append((cx, cy))
            return pts
        line = np.array(walk(-1, 6)[::-1] + [(x, y)] + walk(1, 9))
        if len(line) >= 8: out.append((line, 2.5 + 7 * q / top))
    return out


def moisture_paths(F, W, region, n=3):
    """For the biggest cities with rain in the next 72 h: the hour of their heaviest rain, the air's path 48 h back
    and its moisture source (the last sea it crossed, else the country it came from)."""
    G, polys = TJ.load_polys()
    pl = sorted([p for p in json.load(open(HERE / 'geo_prob.json'))['places'] if p.get('iso') == region], key=lambda p: -p.get('pop', 0))[:8]
    out = []
    for p in pl:
        gx, gy = int(round((p['lon'] - LON0) / RES)), int(round((p['lat'] - LAT0) / RES))
        best = max(((interp(F, h)['pr'][gy, gx], h) for h in range(3, 73, 3)), default=(0, 0))
        if best[0] < 1.0: continue
        path = TJ.follow(W, p['lon'], p['lat'], float(best[1]))
        if len(path) < 8: continue
        d = TJ.describe(path, region, polys, G)
        if not d: continue
        di, via, src = d
        if src: name = {'ru': TJ.SEA_NOM.get(src[0]['ru'], src[0]['ru']), 'uz': src[0]['uz'], 'tr': src[0]['tr']}
        elif via: name = {l: TJ.cname(via[-1], l, G) for l in ('ru', 'uz', 'tr')}
        else: continue
        if any(abs(o['path'][-1][0] - path[-1][0]) < 2.5 and abs(o['path'][-1][1] - path[-1][1]) < 2 for o in out): continue  # the same stream twice: once
        t2 = interp(F, best[1]).get('t2'); snow = bool(t2 is not None and t2[gy, gx] <= 0.5)
        out.append({'city': p.get('ru', p.get('en')), 'lon': p['lon'], 'lat': p['lat'], 'h': float(best[1]), 'path': path, 'src': name, 'snow': snow})
        if len(out) >= n: break
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('npz'); ap.add_argument('out'); ap.add_argument('--regions', default='UZ,KZ'); ap.add_argument('--langs', default='ru,uz')
    ap.add_argument('--fields', help='saved fields (tests)'); ap.add_argument('--winds', help='saved steering winds (tests)')
    a = ap.parse_args()
    import render as Rn
    D = Rn.load(a.npz); run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    F = dict(np.load(a.fields, allow_pickle=True)['F'].item()) if a.fields else fetch(run)
    if len(F) < 6: print('moist: not enough fields', flush=True); return
    out = pathlib.Path(a.out) / 'hr'; out.mkdir(parents=True, exist_ok=True)
    try: W = dict(np.load(a.winds, allow_pickle=True)['W'].item()) if a.winds else TJ.fetch_winds(run)
    except Exception as e: print('moist: no winds for the paths', e, flush=True); W = {}
    for region in a.regions.split(','):
        paths = []
        try: paths = moisture_paths(F, W, region) if len(W) >= 6 else []
        except Exception as e: print('moist paths failed', region, e, flush=True)
        print('moist paths', region, [(p['city'], p['h'], p['src']['ru']) for p in paths], flush=True)
        for lang in a.langs.split(','):
            try: video(F, region, lang, out / f'{region}_moist_{lang}.mp4', run, paths=paths); print('moist', region, lang, 'ok', flush=True)
            except Exception as e:
                import traceback; traceback.print_exc(); print('moist failed', region, lang, e, flush=True)


if __name__ == '__main__':
    main()
