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
STEPS15 = [(st, 'hres') for st in list(range(0, 144, 3)) + list(range(144, 241, 6))] + [(st, 'ens') for st in range(246, 361, 6)]
FPS = 3  # 0.5× of the first version (6 frames a second)
# the names of the big waters on the map (lon, lat), and the size of the letters
_WN = [((50.6, 42.6), ('Каспийское\nморе', 'Kaspiy\ndengizi', 'Hazar\nDenizi'), 10), ((59.6, 45.4), ('Аральское\nморе', 'Orol\ndengizi', 'Aral\nGölü'), 8.5),
       ((74.6, 46.2), ('Балхаш', 'Balxash', 'Balkaş'), 8.5), ((77.3, 42.4), ('Иссык-Куль', 'Issiqko‘l', 'Issık Göl'), 8), ((51.5, 27.3), ('Персидский\nзалив', 'Fors\nko‘rfazi', 'Basra\nKörfezi'), 9),
       ((62.0, 21.0), ('Аравийское море', 'Arab dengizi', 'Umman Denizi'), 10), ((34.5, 43.2), ('Чёрное море', 'Qora dengiz', 'Karadeniz'), 10),
       ((62.4, 39.9), ('Амударья', 'Amudaryo', 'Amu Derya'), 7.5), ((66.6, 44.3), ('Сырдарья', 'Sirdaryo', 'Siri Derya'), 7.5), ((88.0, 52.0), ('Обь', 'Ob', 'Obi'), 7.5)]
MOUNT_NAMES = {l: [(p_, n_[i]) for p_, n_ in [((80.0, 42.9), ('Т я н ь - Ш а н ь', 'T y a n - S h a n', 'T i y e n - Ş a n')), ((73.4, 38.4), ('П а м и р', 'P o m i r', 'P a m i r')),
                                              ((57.5, 38.4), ('Копетдаг', 'Kopetdog‘', 'Kopet Dağ')), ((69.0, 34.6), ('Гиндукуш', 'Hindukush', 'Hindukuş')), ((84.0, 36.2), ('Куньлунь', 'Kunlun', 'Kunlun'))]]
               for i, l in enumerate(('ru', 'uz', 'tr'))}
WATER_NAMES = {l: [(p_, n_[i], f_) for p_, n_, f_ in _WN] for i, l in enumerate(('ru', 'uz', 'tr'))}
LON0, LON1, LAT0, LAT1, RES = 20.0, 100.0, 20.0, 60.0, 0.25
VIEW = {'UZ': (42.0, 80.0, 30.0, 49.0), 'KZ': (40.0, 92.0, 33.0, 57.5), 'KG': (62.0, 86.0, 36.0, 46.0)}
TZ = {'UZ': (5, {'ru': 'по Ташкенту', 'uz': 'Toshkent vaqti', 'tr': 'Taşkent saati'}), 'KZ': (5, {'ru': 'по Астане', 'uz': 'Ostona vaqti', 'tr': 'Astana saati'}),
      'KG': (6, {'ru': 'по Бишкеку', 'uz': 'Bishkek vaqti', 'tr': 'Bişkek saati'})}
TX = {'ru': dict(rainbar='синие столбики — где в стране дождь', title='Откуда идёт дождь', sub='серое с чёрным пунктиром — тучи · синее — дождь · фиолетовое — снег · красное — циклон · линии — ветер (темнее — сильнее)', tcwv='Влажность воздуха', cl='Тучи', rn='Дождь', sn='Снег', snh='сильный', fronts='▲▲ холодный фронт   ●● тёплый фронт', wd_t='Порывы ветра', ms='м/с', wsub=' · жёлтое — сильный ветер', dry='сухо', wet='очень влажно', pr='Дождь / снег', prl='слабый', prh='ливень',
                 hi='В', lo='Н', hiw='антициклон: ясно, сухо', low='циклон: тучи, дождь, ветер', tz='по Ташкенту', src='влага: {s}', leg='путь влаги к городу',
                 c_intro='Серое — тучи, синее — дождь, фиолетовое — снег. Линии показывают, куда дует ветер.', c_go='Влажный воздух от: {s} идёт к городу {c}', c_rain='Сейчас дождь: {c}', c_snow='Сейчас снег: {c}',
                 c_dry='Над страной сухо — дождя нет', c_wet='Влажный воздух над страной — возможны осадки', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']),
      'uz': dict(rainbar='ko‘k ustunlar — mamlakatda yomg‘ir', title='Yomg‘ir qayerdan keladi', sub='kulrang, qora punktir — bulut · ko‘k — yomg‘ir · binafsha — qor · qizil — siklon · chiziqlar — shamol', tcwv='Havo namligi', cl='Bulut', rn='Yomg‘ir', sn='Qor', snh='kuchli', fronts='▲▲ sovuq front   ●● iliq front', wd_t='Shamol zarbasi', ms='m/s', wsub=' · sariq — kuchli shamol', dry='quruq', wet='juda nam', pr='Yomg‘ir / qor', prl='kuchsiz', prh='jala',
                 hi='Y', lo='P', hiw='antisiklon: ochiq, quruq', low='siklon: bulut, yomg‘ir, shamol', tz='Toshkent vaqti', src='namlik: {s}', leg='namlikning shaharga yo‘li',
                 c_intro='Kulrang — bulut, ko‘k — yomg‘ir, binafsha — qor. Chiziqlar shamol yo‘nalishini ko‘rsatadi.', c_go='Nam havo ({s}) {c} shahriga kelmoqda', c_rain='Hozir yomg‘ir: {c}', c_snow='Hozir qor: {c}',
                 c_dry='Mamlakat ustida quruq — yomg‘ir yo‘q', c_wet='Mamlakat ustida nam havo — yog‘in bo‘lishi mumkin', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya']),
      'tr': dict(rainbar='mavi sütunlar — ülkede yağmur', title='Yağmur nereden geliyor', sub='gri, siyah kesikli — bulut · mavi — yağmur · mor — kar · kırmızı — siklon · çizgiler — rüzgâr', tcwv='Havanın nemi', cl='Bulut', rn='Yağmur', sn='Kar', snh='yoğun', fronts='▲▲ soğuk cephe   ●● sıcak cephe', wd_t='Rüzgâr hamlesi', ms='m/s', wsub=' · sarı — kuvvetli rüzgâr', dry='kuru', wet='çok nemli', pr='Yağmur / kar', prl='hafif', prh='sağanak',
                 hi='Y', lo='A', hiw='antisiklon: açık, kuru', low='siklon: bulut, yağmur, rüzgâr', tz='TSİ', src='nem: {s}', leg='nemin şehre yolu',
                 c_intro='Gri bulut, mavi yağmur, mor kar. Çizgiler rüzgârın yönünü gösterir.', c_go='Nemli hava ({s}) {c} şehrine geliyor', c_rain='Şu an yağmur: {c}', c_snow='Şu an kar: {c}',
                 c_dry='Ülke üzerinde hava kuru — yağmur yok', c_wet='Ülke üzerinde nemli hava — yağış olabilir', wd=['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'])}
# water vapour on a dark map: the dry air dark slate, the moist air glowing teal-green (the moisture stands out like on satellite water-vapour images)
TCWV_STOPS = [(0, '#ffffff'), (8, '#fbfcfb'), (14, '#eef6f1'), (20, '#d8eee2'), (27, '#b5e0cb'), (35, '#86cbb0'), (45, '#52ad94'), (58, '#2e8a7c'), (70, '#1f6b66')]  # white dry air → deep green moist air
# precipitation, radar-like colours
PR_LV = [0.3, 1, 2, 4, 7, 12, 20, 40]
PR_COL = ['#8fd0ff', '#4aa8f5', '#2b6fe0', '#f2d94e', '#f29c38', '#e0503a', '#c23aa0']  # (the TV version)
RAIN_COL = ['#a9dbff', '#6cbcf7', '#3d95ec', '#2272d8', '#1756b5', '#0f3f8c', '#0a2b66']  # light rain → downpour, all blue
WIND_COL = ['#fff27a', '#ffd93a', '#f5b700']  # gusts 15–20, 20–25, 25+ m/s: yellow
WIND_LV = [15, 20, 25, 80]
SNOW_COL = ['#eadcff', '#d3bcfa', '#b897f0', '#9b72e2', '#8052cc', '#6639ae', '#4c2788']  # light snow → heavy snow, all violet  # blue (light rain) → yellow → red → magenta: apart from the green-teal moisture


def fetch(run, steps=None):
    """{step: dict(tcwv, msl hPa, tp mm (accumulated from 0), u, v, …)} on the area grid (rows south → north).
    steps: [(hour, 'hres'|'ens')]; 'ens' takes the control member of the ensemble (it reaches 15 days)."""
    d, hh = run.strftime('%Y%m%d'), run.strftime('%H')
    jobs = []
    for st, kind in (steps or [(s_, 'hres') for s_ in STEPS]):
        idx = None
        if kind == 'ens':
            base = f'{ECM}/{d}/{hh}z/ifs/0p25/enfo/{d}{hh}0000-{st}h-enfo-ef'; idx = get(base + '.index')
        else:
            for stream in (('oper', 'scda') if hh in ('00', '12') else ('scda', 'oper')):
                base = f'{ECM}/{d}/{hh}z/ifs/0p25/{stream}/{d}{hh}0000-{st}h-{stream}-fc'
                idx = get(base + '.index')
                if idx: break
        if not idx: print('moist: missing step', st, flush=True); continue
        for line in idx.decode().strip().split('\n'):
            x = json.loads(line); p = x.get('param')
            if kind == 'ens' and x.get('type') != 'cf': continue
            lt, lv = x.get('levtype'), x.get('levelist')
            key = (p if lt == 'sfc' and p in ('tcwv', 'msl', 'tp', 'tcc', '2t', '10u', '10v', '10fg', 'fg10', 'i10fg', 'sp') else p if lt == 'pl' and lv == '700' and p in ('u', 'v')
                   else p + '850' if lt == 'pl' and lv == '850' and p in ('t', 'r') else None)
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
        if all(k in f for k in ('msl', 'u', 'v')):
            if 'tcwv' not in f: f['tcwv'] = f['tcc'] * 40 if 'tcc' in f else np.full_like(f['msl'], 15.0)
            out[st] = {'tcwv': f['tcwv'], 'msl': f['msl'] / 100.0, 'tp': f.get('tp', np.zeros_like(f['tcwv'])) * 1000.0, 'u': f['u'], 'v': f['v'],
                       'tcc': f.get('tcc', np.clip((f['tcwv'] - 10) / 25, 0, 1)), 't2': f['2t'] - 273.15 if '2t' in f else np.full_like(f['tcwv'], 10.0)}
            if '10u' in f and '10v' in f: out[st]['ws'] = np.hypot(f['10u'], f['10v']); out[st]['u10'] = f['10u']; out[st]['v10'] = f['10v']
            g_ = next((f[k] for k in ('10fg', 'fg10', 'i10fg') if k in f), None)
            if g_ is not None: out[st]['gust'] = g_
            elif 'ws' in out[st]: out[st]['gust'] = out[st]['ws'] * 1.6  # no gusts in the data: the usual gust factor
            for k_ in ('t850', 'r850', 'sp'):  # the fronts (850 hPa) and the height of the ground (surface pressure)
                if k_ in f: out[st][k_] = f[k_] / 100.0 if k_ == 'sp' else f[k_]
    print('moist: fields at', len(out), 'steps, last', max(out) if out else None, 'h', flush=True)
    return out


def ground_height(F):
    """The height of the ground (m) from the surface and sea-level pressure of the first step (hypsometric formula)."""
    f = F[min(F)]
    if 'sp' not in f: return None
    T = f['t2'] + 273.15 + 0.0065 * 500  # the air between the ground and sea level, roughly
    return np.clip(29.27 * T * np.log(np.maximum(f['msl'], 1) / np.maximum(f['sp'], 1)), -50, 7500)


def fronts(T850, R850, U, V, lon, lat, smooth=3.0):
    """Cold and warm fronts at 850 hPa (MetPy): where the gradient of the equivalent potential temperature θe
    changes fastest (the zero of the thermal front parameter) and is strong. A front is cold where the wind blows
    from the cold side, warm where it blows from the warm side. Returns [(xy array, 'cold'|'warm'), ...]."""
    import metpy.calc as mc
    from metpy.units import units
    from scipy.ndimage import gaussian_filter
    from contourpy import contour_generator
    Tk = T850 * units.kelvin if T850.mean() > 100 else (T850 + 273.15) * units.kelvin
    td = mc.dewpoint_from_relative_humidity(Tk, np.clip(R850, 1, 100) * units.percent)
    th = gaussian_filter(np.asarray(mc.equivalent_potential_temperature(850 * units.hPa, Tk, td).m), smooth)
    dy = 111.0 * (lat[1] - lat[0]); dx = 111.0 * (lon[1] - lon[0]) * np.cos(np.radians(lat))[:, None]  # km between the grid points
    gy, gx = np.gradient(th, axis=0) / dy, np.gradient(th, axis=1) / dx
    mag = np.hypot(gx, gy) + 1e-9
    my, mx = np.gradient(mag, axis=0) / dy, np.gradient(mag, axis=1) / dx
    tfp = -(mx * gx + my * gy) / mag
    strong = gaussian_filter(mag, 1) > 0.03  # K per km: a real front (≥ 3 K over 100 km)
    adv = -(U * gx + V * gy)  # > 0: warm air coming
    out = []
    for line in contour_generator(lon, lat, np.where(strong, tfp, np.nan)).lines(0.0):
        if len(line) < 6: continue
        j = np.clip(((line[:, 1] - lat[0]) / (lat[1] - lat[0])).astype(int), 0, len(lat) - 1); i = np.clip(((line[:, 0] - lon[0]) / (lon[1] - lon[0])).astype(int), 0, len(lon) - 1)
        if np.hypot(*np.diff(line, axis=0).T).sum() < 4: continue  # shorter than ~400 km: noise
        out.append((line, 'warm' if np.median(adv[j, i]) > 0 else 'cold'))
    return out


def interp(F, h):
    """The fields at hour h (linear between the 3-hourly steps); precipitation as mm in the 3 h around h."""
    ks = sorted(F); j = int(np.clip(np.searchsorted(ks, h), 1, len(ks) - 1)); a = float(np.clip((h - ks[j - 1]) / (ks[j] - ks[j - 1]), 0, 1))
    A, B = F[ks[j - 1]], F[ks[j]]
    out = {k: A[k] * (1 - a) + B[k] * a for k in ('tcwv', 'msl', 'u', 'v', 'tcc', 't2', 'ws', 'gust', 'u10', 'v10', 't850', 'r850') if k in A and k in B}
    rate = lambda i: np.clip(F[ks[i]]['tp'] - F[ks[i - 1]]['tp'], 0, None) * 3 / (ks[i] - ks[i - 1]) if i >= 1 else np.zeros_like(A['tp'])  # mm per 3 h before step i
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
        wet_c = []; snow_c = []
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
        levels.append({'rain': min(1.0, wet * 2.5), 'snow': bool(land.any() and (P[land & SN] >= 1).sum() > (P[land & ~SN] >= 1).sum()), 'wind': float(np.clip(np.nanmean(np.hypot(U, V)) / 22, 0.15, 0.7)), 'storm': 0.0})
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


def video(F, region, lang, mp4, run, off=5, paths=(), H=72):
    import render as Rn
    from render import plt, matplotlib
    from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm, ListedColormap
    from scipy.ndimage import gaussian_filter, maximum_filter, minimum_filter
    from regions import NAMES
    from hourly import NAVY
    from metpy.plots import ColdFront, WarmFront
    X = TX.get(lang, TX['ru']); off = TZ.get(region, (off,))[0]
    x0, x1, y0, y1 = VIEW[region]
    lon = LON0 + np.arange(next(iter(F.values()))['tcwv'].shape[1]) * RES; lat = LAT0 + np.arange(next(iter(F.values()))['tcwv'].shape[0]) * RES
    ci = np.flatnonzero((lon >= x0 - 1) & (lon <= x1 + 1)); ri = np.flatnonzero((lat >= y0 - 1) & (lat <= y1 + 1))
    LON, LAT = np.meshgrid(lon[ci], lat[ri])
    k = np.cos(np.radians((y0 + y1) / 2))
    cmap = LinearSegmentedColormap.from_list('tcwv', [(v / 70, c) for v, c in TCWV_STOPS])
    prc, prn = ListedColormap(PR_COL), BoundaryNorm(PR_LV, len(PR_COL))
    G = json.load(open(HERE / 'geo_world.json'))['countries']; GA = json.load(open(HERE / 'geo_admin.json')).get(region, {})
    fig = plt.figure(figsize=(12.8, 7.2), dpi=150); fig.patch.set_facecolor('#ffffff')
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect(1 / k); ax.axis('off')
    # the map width fills the frame; the height follows the latitude squeeze
    fx = 12.8 / 7.2; span = (x1 - x0) * k / fx; cy = (y0 + y1) / 2; ax.set_ylim(cy - span / 2, cy + span / 2); y0v, y1v = cy - span / 2, cy + span / 2
    PCOL, LC = matplotlib.collections.PolyCollection, matplotlib.collections.LineCollection
    near = lambda r: np.asarray(r)[:, 0].max() > x0 - 3 and np.asarray(r)[:, 0].min() < x1 + 3 and np.asarray(r)[:, 1].max() > y0v - 3 and np.asarray(r)[:, 1].min() < y1v + 3
    borders = [np.asarray(r) for c in G.values() for r in c['rings'] if near(r)]
    ax.add_collection(LC(borders, colors='#7d8b99', linewidths=0.7, alpha=0.8, zorder=4))
    own = [np.asarray(r) for r in G.get(region, {}).get('rings', [])]
    if GA: ax.add_collection(LC([np.asarray(r) for a in GA['adm1'] for r in a['r']], colors='#8e9aa6', linewidths=0.45, alpha=0.55, zorder=4))
    ax.add_collection(LC(own, colors='#1d2a3a', linewidths=1.7, zorder=4.5))
    WAT = json.load(open(HERE / 'geo_water.json')); WFILL, WEDGE, WTXT = '#cfe3ef', '#4d8fb8', '#2f6f99'
    seas = [np.asarray(r) for r in WAT['ocean'] if near(r)] + [np.asarray(l['r']) for l in WAT['lakes'] if near(l['r'])]
    ax.add_collection(PCOL(seas, facecolors=WFILL, edgecolors='none', zorder=0.6))  # the water under the clouds and the rain
    ax.add_collection(LC(seas, colors=WEDGE, linewidths=0.9, alpha=0.9, zorder=4.15))  # its shore always clear on top
    riv = [(np.asarray(r['c']), r['w']) for r in WAT['rivers'] if near(r['c'])]
    ax.add_collection(LC([c for c, w in riv], colors=WEDGE, linewidths=[0.5 + 0.55 * w for c, w in riv], alpha=0.95, zorder=4.2, capstyle='round'))
    wl = matplotlib.patheffects.withStroke(linewidth=2.6, foreground='#ffffffcc')
    for (wx, wy), nm_, fs_ in WATER_NAMES.get(lang, WATER_NAMES['ru']):
        if x0 + 1 < wx < x1 - 1 and y0v + (y1v - y0v) * 0.2 < wy < y1v - (y1v - y0v) * 0.125:
            ax.text(wx, wy, nm_, fontsize=fs_, color=WTXT, style='italic', fontweight='bold', ha='center', va='center', zorder=4.3, path_effects=[wl], linespacing=0.9)
    # the mountains: hill shading from the height of the ground (lit from the north-west), a light brown tint up high
    E = ground_height(F)
    if E is not None:
        from scipy.ndimage import zoom
        from matplotlib.colors import LightSource
        Er = zoom(gaussian_filter(np.clip(E[np.ix_(ri, ci)], 0, None), 0.6), 4, order=3)
        hs = np.flipud(LightSource(azdeg=315, altdeg=35).hillshade(np.flipud(Er), vert_exag=6, dx=RES / 4 * 111e3 * k, dy=RES / 4 * 111e3))
        hi_ = np.clip((Er - 300) / 900, 0, 1)
        rel = np.zeros(Er.shape + (4,)); rel[..., :3] = np.where((hs < 0.6)[..., None], (0.22, 0.18, 0.14), (1.0, 1.0, 1.0))
        rel[..., 3] = np.clip(np.where(hs < 0.62, (0.62 - hs) * 1.3, (hs - 0.62) * 0.9), 0, 0.6) * hi_
        tint = np.zeros(Er.shape + (4,)); tint[..., :3] = (0.62, 0.52, 0.40); tint[..., 3] = np.clip((Er - 1200) / 2800, 0, 1) * 0.38
        ext = (lon[ci[0]] - RES / 2, lon[ci[-1]] + RES / 2, lat[ri[0]] - RES / 2, lat[ri[-1]] + RES / 2)
        ax.imshow(tint, extent=ext, origin='lower', zorder=0.7, aspect='auto', interpolation='bilinear')
        ax.imshow(rel, extent=ext, origin='lower', zorder=0.75, aspect='auto', interpolation='bilinear')
        for (mx_, my_), nm_ in MOUNT_NAMES.get(lang, MOUNT_NAMES['ru']):
            if x0 + 1 < mx_ < x1 - 1 and y0v + (y1v - y0v) * 0.2 < my_ < y1v - (y1v - y0v) * 0.125:
                ax.text(mx_, my_, nm_, fontsize=9, color='#7a5a36', style='italic', fontweight='bold', ha='center', va='center', zorder=4.3, path_effects=[wl], rotation=8)
    # the main cities of the country
    allp = sorted([p for p in json.load(open(HERE / 'geo_prob.json'))['places'] if p.get('iso') == region and x0 < p['lon'] < x1], key=lambda p: -p.get('pop', 0))
    pl = allp[:6]
    if GA:  # and the biggest city of every region (oblast), so each region has its town on the map
        from matplotlib.path import Path as MPath_
        for a_ in GA['adm1']:
            best_ = next((p for p in allp if any(MPath_(np.asarray(r)).contains_point((p['lon'], p['lat'])) for r in a_['r'])), None)
            if best_ is not None and best_ not in pl: pl.append(best_)
    pl = pl[:16]
    for p in pl: ax.plot(p['lon'], p['lat'], 'o', ms=4.5, mfc=NAVY, mec='#ffffff', mew=1, zorder=8)
    fig.canvas.draw(); rnd = fig.canvas.get_renderer(); taken = []
    def place(x, y, txt, fs, cands, keep=True, ey=2.4):
        for dx, dy, ha, va in cands:
            t_ = ax.text(x + dx, y + dy, txt, fontsize=fs, fontweight='bold', ha=ha, va=va); bb = t_.get_window_extent(rnd).expanded(1.04, ey); t_.remove()
            if bb.y0 > 0.2 * fig.bbox.height and bb.y1 < 0.86 * fig.bbox.height and 4 < bb.x0 and bb.x1 < fig.bbox.width - 4 and not any(bb.overlaps(o) for o in taken):
                if keep: taken.append(bb)
                return (x + dx, y + dy, ha, va)
        return None
    tagpos = [place(p['lon'], p['lat'], '☂ ' + Rn.city_name(p, lang) + '', 9, [(0.22, 0.12, 'left', 'bottom'), (0.22, -0.12, 'left', 'top'), (-0.22, 0.12, 'right', 'bottom'), (-0.22, -0.12, 'right', 'top')]) for p in pl]
    tagfs = [9] * len(pl)
    for j_, p in enumerate(pl):  # a city that did not fit: a smaller tag below or above
        if tagpos[j_] is None:
            tagpos[j_] = place(p['lon'], p['lat'], '☂ ' + Rn.city_name(p, lang) + '', 7.5, [(0, -0.18, 'center', 'top'), (0, 0.18, 'center', 'bottom'), (0.2, 0, 'left', 'center'), (-0.2, 0, 'right', 'center')]); tagfs[j_] = 7.5
    halo = [matplotlib.patheffects.withStroke(linewidth=2.6, foreground='#ffffff')]
    if GA:  # the names of the regions (oblasts), quiet grey, where they fit between the towns
        for a_ in GA['adm1']:
            nm_ = (a_['name'].get(lang) or a_['name']['ru']).replace(' обл.', '').replace(' viloyati', '')
            if not (x0 < a_['c'][0] < x1) or a_['name']['ru'] in ('Ташкент', 'Алматы', 'Астана', 'Бишкек', 'Ош'): continue  # a city that is a region: its town tag says it
            cands_ = [(dx_, dy_, 'center', 'center') for dy_ in (0, -0.3, 0.3, -0.6, 0.6) for dx_ in (0, 0.5, -0.5)]
            pos_ = place(a_['c'][0], a_['c'][1], nm_, 7.5, cands_, ey=1.1)
            if pos_: ax.text(pos_[0], pos_[1], nm_, fontsize=7.5, color='#5f6b78', fontweight='bold', ha='center', va='center', zorder=4.35, alpha=0.9,
                             path_effects=[matplotlib.patheffects.withStroke(linewidth=2.4, foreground='#ffffffcc')])
    matplotlib.rcParams['hatch.color'] = '#d9a400'; matplotlib.rcParams['hatch.linewidth'] = 0.8
    # the title band, the clock, the legends (drawn once)
    band = dict(boxstyle='round,pad=0.5,rounding_size=0.6', fc='#1d2a3acc', ec='none')
    fig.text(0.018, 0.955, f"{NAMES[region][lang]} · {X['title']}", fontsize=17, fontfamily=Rn.DISPLAY, fontweight='bold', color='#ffffff', va='center', bbox=band, zorder=20)
    fig.text(0.018, 0.893, X['sub'] + X['wsub'], fontsize=9.5, color='#e3ebf3', va='center', zorder=20, bbox=dict(boxstyle='round,pad=0.35,rounding_size=0.4', fc='#1d2a3aaa', ec='none'))
    fig.patches.append(matplotlib.patches.FancyBboxPatch((0.008, 0.012), 0.53, 0.115, boxstyle='round,pad=0,rounding_size=0.008', transform=fig.transFigure, facecolor='#1d2a3acc', edgecolor='none', zorder=19))
    clock = fig.text(0.982, 0.955, '', fontsize=17, fontfamily=Rn.DISPLAY, fontweight='bold', color='#f0b88a', ha='right', va='center', bbox=band, zorder=20)
    def swatch(x, w, cols, title, lo=None, hi=None):
        fig.text(x, 0.088, title, fontsize=11, color='#ffffff', fontweight='bold', zorder=21, va='center')
        for i_, c_ in enumerate(cols):
            fig.patches.append(matplotlib.patches.Rectangle((x + w * i_ / len(cols), 0.045), w / len(cols), 0.022, transform=fig.transFigure, facecolor=c_, edgecolor='none', zorder=20.5))
        if lo: fig.text(x, 0.028, lo, fontsize=8.5, color='#c9d6e5', zorder=21, va='center')
        if hi: fig.text(x + w, 0.028, hi, fontsize=8.5, color='#c9d6e5', ha='right', zorder=21, va='center')
    swatch(0.02, 0.075, ['#c4c9cf', '#9aa2ab', '#7a838e'], '☁ ' + X['cl'])
    fig.lines.append(matplotlib.lines.Line2D([0.022, 0.093], [0.056, 0.056], transform=fig.transFigure, color='#111111', lw=1.6, ls=(0, (4, 3)), zorder=21))
    swatch(0.115, 0.125, RAIN_COL, X['rn'], X['prl'], X['prh'])
    swatch(0.26, 0.125, SNOW_COL, '❄ ' + X['sn'], X['prl'], X['snh'])
    swatch(0.405, 0.12, WIND_COL, X['wd_t'], '15', '25+ ' + X['ms'])
    fig.text(0.982, 0.012, 'ECMWF IFS · osmon', fontsize=7, color='#9fb0c2', ha='right', va='bottom', zorder=21)
    from matplotlib.path import Path as MPath
    pts0 = np.c_[LON.ravel(), LAT.ravel()]; land = np.zeros(len(pts0), bool)
    for r in own: land |= MPath(r).contains_points(pts0)
    land = land.reshape(LON.shape)
    fig.patches.append(matplotlib.patches.FancyBboxPatch((0.548, 0.012), 0.444, 0.115, boxstyle='round,pad=0,rounding_size=0.008', transform=fig.transFigure, facecolor='#1d2a3acc', edgecolor='none', zorder=19))
    tax = fig.add_axes([0.565, 0.045, 0.41, 0.05]); tax.set_zorder(21); tax.set_xlim(0, H); tax.set_ylim(0, 1); tax.axis('off')
    bs = 3 if H <= 72 else 12  # the rain bars: every 3 h, every 12 h in the long video
    share = [float(np.mean(gaussian_filter(interp(F, hh)['pr'][np.ix_(ri, ci)], 0.8)[land] >= 1)) if land.any() else 0 for hh in range(0, H + 1, bs)]
    tax.bar(np.arange(0, H + 1, bs), [max(0.04, min(1, v * 2.2)) for v in share], width=bs * 0.85, color='#6cbcf7', alpha=0.6, align='center', zorder=1)
    t0 = run + dt.timedelta(hours=off)
    for dd in range(H // 24 + 2):  # midnights and the day names
        hh = (dt.datetime.combine(t0.date() + dt.timedelta(days=dd), dt.time()) - t0).total_seconds() / 3600
        if 0 < hh < H: tax.axvline(hh, color='#9fb0c2', lw=0.8 if H <= 72 else 0.5, alpha=0.7, zorder=2)
        mid = min(H - 1, max(1, hh + 12))
        if 0 <= hh + 12 <= H:
            d_ = t0.date() + dt.timedelta(days=dd); fig.text(0.565 + 0.41 * mid / H, 0.108 if H <= 72 else 0.106, f"{X['wd'][d_.weekday()]} {d_:%d.%m}" if H <= 72 else f"{d_:%d}", fontsize=9 if H <= 72 else 8, fontweight='bold', color='#e3ebf3', ha='center', va='center', zorder=21)
    fig.text(0.565, 0.026, X['rainbar'], fontsize=8, color='#9fb0c2', va='center', zorder=21)
    prog = tax.add_patch(matplotlib.patches.Rectangle((0, 0), 0.01, 1, color='#f0b88a', alpha=0.5, zorder=0.5)); head = tax.axvline(0, color='#f0b88a', lw=2.5, zorder=3)
    knob = tax.plot([0], [0.5], 'o', ms=9, mfc='#f0b88a', mec='#ffffff', mew=1.5, zorder=4, clip_on=False)[0]
    # flowing streaks: particles carried by the 700 hPa wind, each with a fading tail
    rng = np.random.default_rng(3); N = 480; TAIL = 10
    def seed(n): return np.c_[rng.uniform(x0, x1, n), rng.uniform(y0v, y1v, n)]
    pts = seed(N); age = rng.integers(0, 60, N); hist = np.repeat(pts[None], TAIL, 0)
    TAIL = 12; hist = np.repeat(pts[None], TAIL, 0)
    FLOW = LinearSegmentedColormap.from_list('flow', ['#a9bdd1', '#7095bb', '#40699b', '#2a4f80'])
    fades = np.linspace(0.03, 0.6, TAIL - 1) ** 1.6
    lines = [LC([], linewidths=0.7, zorder=6, capstyle='round') for a in fades]
    heads = ax.scatter([], [], s=[], c=[], zorder=6.05, linewidths=0)
    for l in lines: ax.add_collection(l)
    img = ax.imshow(np.zeros(LON.shape + (4,)), extent=(lon[ci[0]] - RES / 2, lon[ci[-1]] + RES / 2, lat[ri[0]] - RES / 2, lat[ri[-1]] + RES / 2), origin='lower',
                    interpolation='bilinear', zorder=1.8, aspect='auto')  # the clouds: grey, the thicker the darker
    # where the moisture comes from: for the big cities that will get rain, the air's path 2 days back
    # (prob/trajectory.py), drawn dashed with its source; a bright drop travels along it in time with the video
    SRC = '#f08a24'
    placed = []; pa_art = []
    for pa in paths:
        q = np.array(pa['path'])
        _before = set(map(id, ax.get_children()))
        ax.plot(q[:, 0], q[:, 1], color=SRC, lw=1.8, ls=(0, (5, 3)), alpha=0.9, zorder=6.5, path_effects=[matplotlib.patheffects.withStroke(linewidth=3.5, foreground='#ffffffaa')])
        for m in (len(q) // 3, 2 * len(q) // 3):
            if 1 <= m < len(q): ax.annotate('', xy=q[m - 1, :2], xytext=q[m, :2], arrowprops=dict(arrowstyle='-|>', color=SRC, lw=1.8, mutation_scale=15), zorder=6.6)
        # the source: at the start of the path, or (when it is off the map) where the path comes into the picture
        mx, my = (x1 - x0) * 0.06, (y1v - y0v) * 0.08
        inside = [i for i in range(len(q)) if x0 + mx < q[i, 0] < x1 - mx and y0v + (y1v - y0v) * 0.2 < q[i, 1] < y1v - my * 1.6]  # above the legend panel
        if inside:
            i = max(inside); sx, sy = q[i, 0], q[i, 1]; off_map = i < len(q) - 1
            ax.plot(sx, sy, 'o', ms=7, mfc=SRC, mec='#ffffff', mew=1.5, zorder=7)
            ly = sy + (y1v - y0v) * 0.03
            while any(abs(ly - p_[1]) < (y1v - y0v) * 0.045 and abs(sx - p_[0]) < (x1 - x0) * 0.2 for p_ in placed): ly += (y1v - y0v) * 0.05  # not over another label
            placed.append((sx, ly))
            ax.text(sx, ly, (lambda t: t[:1].upper() + t[1:])(X['src'].format(s=pa['src'][lang])) + (' ↙' if off_map and q[-1, 0] < sx else ' ↘' if off_map else ''), fontsize=9.5, fontweight='bold',
                    color='#1d2a3a', ha='center', va='bottom', zorder=9, bbox=dict(boxstyle='round,pad=0.3,rounding_size=0.5', fc=SRC, ec='none'))
        pa_art.append([c_ for c_ in ax.get_children() if id(c_) not in _before])
        if H > 72:
            for c_ in pa_art[-1]: c_.set_visible(False)
            placed.pop() if placed and inside else None  # labels of paths at other times may share a place
    if any('t850' in f_ for f_ in F.values()):  # the fronts: one line each, in their colours
        for yy_, txt_, col_ in ((0.852, X['fronts'].split('   ')[0], '#8fb8ff'), (0.814, X['fronts'].split('   ')[1], '#ff9a8a')):
            fig.text(0.982, yy_, txt_, fontsize=9.5, fontweight='bold', color=col_, ha='right', va='center', zorder=21,
                     bbox=dict(boxstyle='round,pad=0.3,rounding_size=0.4', fc='#1d2a3aaa', ec='none'))
    if paths:
        fig.text(0.982, 0.893, '- - ▶  ' + X['leg'], fontsize=9.5, fontweight='bold', color=SRC, ha='right', va='center', zorder=21,
                 bbox=dict(boxstyle='round,pad=0.35,rounding_size=0.4', fc='#1d2a3aaa', ec='none'))
    cap = fig.text(0.5, 0.168, '', fontsize=15, fontweight='bold', color='#ffffff', ha='center', va='center', zorder=22,
                   bbox=dict(boxstyle='round,pad=0.55,rounding_size=0.7', fc='#1d2a3ae6', ec='#ffb15c', lw=1.4))
    cgx = [int(round((p['lon'] - lon[ci[0]]) / RES)) for p in pl]; cgy = [int(round((p['lat'] - lat[ri[0]]) / RES)) for p in pl]
    night = ax.imshow(np.zeros(LON.shape + (4,)), extent=(lon[ci[0]] - RES / 2, lon[ci[-1]] + RES / 2, lat[ri[0]] - RES / 2, lat[ri[-1]] + RES / 2), origin='lower', zorder=5.5, aspect='auto', interpolation='bilinear')
    def sun_elev(t):  # degrees above the horizon at every grid point (t in UTC)
        n_ = t.timetuple().tm_yday; dec = np.radians(23.44) * np.sin(2 * np.pi * (284 + n_) / 365)
        ha = np.radians(((t.hour + t.minute / 60 + LON / 15) - 12) * 15); la_ = np.radians(LAT)
        return np.degrees(np.arcsin(np.sin(la_) * np.sin(dec) + np.cos(la_) * np.cos(dec) * np.cos(ha)))
    wet_prev = set(); rings = {}
    dyn = []
    # the frames: every 30 min over 3 days; in the long video every hour to day 6, then every 2 h (the data are 6-hourly there)
    hours = list(np.arange(0, H + 0.01, 0.5)) if H <= 72 else list(np.arange(0, 144, 1.0)) + list(np.arange(144, H + 0.01, 2.0))
    fdir = pathlib.Path(tempfile.mkdtemp()); levels = []
    for f, h in enumerate(hours):
        for a in dyn: a.remove()
        dyn = []
        Q = interp(F, h); T = Q['tcwv'][np.ix_(ri, ci)]; P = gaussian_filter(Q['pr'][np.ix_(ri, ci)], 0.8); M = gaussian_filter(Q['msl'][np.ix_(ri, ci)], 2.0)
        C = gaussian_filter(Q['tcc'][np.ix_(ri, ci)], 1.2); cl = np.zeros(LON.shape + (4,)); cl[..., :3] = (0.33, 0.37, 0.42); cl[..., 3] = np.clip((C - 0.3) / 0.65, 0, 1) ** 1.1 * 0.58
        img.set_data(cl); ax.set_aspect(1 / k)
        if 't850' in Q and 'r850' in Q:  # the atmospheric fronts at 850 hPa: cold ▲ (blue), warm ● (red)
            try:
                for xy, kind in fronts(Q['t850'][np.ix_(ri, ci)], Q['r850'][np.ix_(ri, ci)], Q['u'][np.ix_(ri, ci)], Q['v'][np.ix_(ri, ci)], lon[ci], lat[ri]):
                    col_ = '#1f5fd1' if kind == 'cold' else '#d6402b'
                    pe = (ColdFront if kind == 'cold' else WarmFront)(size=5, spacing=1.6, color=col_)
                    dyn += ax.plot(xy[:, 0], xy[:, 1], color=col_, lw=2.2, zorder=4.6, path_effects=[pe])
            except Exception as e:
                if f == 0: print('fronts failed', e, flush=True)
        if C.max() > 0.55:  # the edge of the cloud masses: a black dashed line, so their movement is easy to follow
            dyn.append(ax.contour(LON, LAT, gaussian_filter(C, 1.5), levels=[0.55], colors='#111111', linewidths=1.3, linestyles=[(0, (4, 3))], alpha=0.75, zorder=3.3))
            if C.max() > 0.9: dyn.append(ax.contour(LON, LAT, gaussian_filter(C, 1.5), levels=[0.9], colors='#111111', linewidths=0.8, linestyles=[(0, (2, 3))], alpha=0.5, zorder=3.3))
        T2 = gaussian_filter(Q['t2'][np.ix_(ri, ci)], 1.0); SN = T2 <= 0.5
        GU = gaussian_filter(Q['gust'][np.ix_(ri, ci)], 1.0) if 'gust' in Q else gaussian_filter(np.hypot(Q['u'], Q['v'])[np.ix_(ri, ci)], 1.0) * 0.9
        if GU.max() >= WIND_LV[0]:
            dyn.append(ax.contourf(LON, LAT, GU, levels=WIND_LV, colors=WIND_COL, alpha=0.32, zorder=1.9, antialiased=True))
            dyn.append(ax.contour(LON, LAT, GU, levels=[WIND_LV[0]], colors='#c99400', linewidths=1.0, zorder=1.96))
        if P.max() >= PR_LV[0]:
            if (~SN).any(): dyn.append(ax.contourf(LON, LAT, np.where(SN, 0, P), levels=PR_LV, colors=RAIN_COL, alpha=0.88, zorder=2, antialiased=True))
            if SN.any() and P[SN].max() >= PR_LV[0]: dyn.append(ax.contourf(LON, LAT, np.where(SN, P, 0), levels=PR_LV, colors=SNOW_COL, alpha=0.92, zorder=2.05, antialiased=True))
        lv = np.arange(np.floor(M.min() / 4) * 4, M.max() + 4, 4)
        cs = ax.contour(LON, LAT, M, levels=lv, colors='#4b5d70', linewidths=0.6, alpha=0.35, zorder=3); dyn.append(cs)
        A = M - np.median(M)  # the cyclone (low pressure) in red, the anticyclone in blue: deeper = stronger colour
        lo_ = min(A.min() - 1, -10.5)  # the levels must rise even when the low is shallow
        if A.min() < -3: dyn.append(ax.contourf(LON, LAT, A, levels=[lo_, -10, -6, -3], colors=['#ec7a68', '#f3a395', '#f9cdc5'], alpha=0.22, zorder=1.5))
        if A.min() < -3: dyn.append(ax.contour(LON, LAT, A, levels=[-3], colors='#d6402b', linewidths=1.6, linestyles='--', alpha=0.8, zorder=3.2))
        if A.max() > 3: dyn.append(ax.contourf(LON, LAT, A, levels=[3, 6, 10, max(A.max() + 1, 10.5)], colors=['#bcd6f5', '#8fb8ec', '#5f97e0'], alpha=0.3, zorder=1.5))
        mx, mn = maximum_filter(M, size=25) == M, minimum_filter(M, size=25) == M
        for mask, lab, col in ((mx, X['hi'], '#2f6fd0'), (mn, X['lo'], '#d6402b')):
            for (yy, xx) in zip(*np.nonzero(mask)):
                if 3 < yy < M.shape[0] - 3 and 3 < xx < M.shape[1] - 3 and abs(M[yy, xx] - np.median(M)) > 3 and \
                        y0v + (y1v - y0v) * 0.24 < LAT[yy, xx] < y1v - (y1v - y0v) * 0.2 and x0 + (x1 - x0) * 0.04 < LON[yy, xx] < x1 - (x1 - x0) * 0.06:  # not under the panels
                    dyn.append(ax.text(LON[yy, xx], LAT[yy, xx], lab, fontsize=20, fontweight='bold', color=col, ha='center', va='center', zorder=7,
                                       path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground='#ffffff')]))
                    dyn.append(ax.text(LON[yy, xx], LAT[yy, xx] - 1.0, X['hiw'] if lab == X['hi'] else X['low'], fontsize=9.5, fontweight='bold', color='#ffffff', ha='center', va='center', zorder=7,
                                       bbox=dict(boxstyle='round,pad=0.3,rounding_size=0.5', fc=col, ec='none')))
        if H > 72:
            for pa, arts in zip(paths, pa_art):
                on = -9 <= pa['h'] - h <= 60
                for c_ in arts: c_.set_visible(on)
        for pa in paths:  # the drop of moisture on its way: where the air is now (hours before it reaches the city)
            q = np.array(pa['path']); back = pa['h'] - h
            if 0 <= back <= q[-1, 2]:
                px, py = np.interp(back, q[:, 2], q[:, 0]), np.interp(back, q[:, 2], q[:, 1])
                dyn += ax.plot(px, py, 'o', ms=16, mfc=SRC, mec='none', alpha=0.28, zorder=7.4)
                dyn += ax.plot(px, py, 'o', ms=8, mfc=SRC, mec='#ffffff', mew=1.6, zorder=7.5)
            elif -6 <= back < 0:  # it arrived: a ring at the city
                kk = (-back) / 6; dyn += ax.plot(pa['lon'], pa['lat'], 'o', ms=10 + 26 * kk, mfc='none', mec=SRC, mew=2.4 * (1 - kk), alpha=1 - kk, zorder=7.5)
        # move the streaks (sped up so the motion is visible: ~1.1 h of travel per frame)
        U, V = Q['u'][np.ix_(ri, ci)], Q['v'][np.ix_(ri, ci)]
        gx = np.clip(((pts[:, 0] - lon[ci[0]]) / RES).astype(int), 0, len(ci) - 1); gy = np.clip(((pts[:, 1] - lat[ri[0]]) / RES).astype(int), 0, len(ri) - 1)
        u, v = U[gy, gx], V[gy, gx]; sec = 0.8 * 3600
        pts = pts + np.c_[u * sec / (111320 * np.cos(np.radians(pts[:, 1]))), v * sec / 110540]
        age += 1; dead = (age > 60) | (pts[:, 0] < x0) | (pts[:, 0] > x1) | (pts[:, 1] < y0v) | (pts[:, 1] > y1v)
        if dead.any(): pts[dead] = seed(dead.sum()); age[dead] = 0; hist[:, dead] = pts[dead]
        hist = np.roll(hist, -1, 0); hist[-1] = pts
        spd = np.hypot(u, v)
        for i, l in enumerate(lines):
            seg = np.stack([hist[i], hist[i + 1]], 1); ok = ~dead & (np.hypot(*(seg[:, 1] - seg[:, 0]).T) < 3)
            sp_ = np.clip(spd[ok] / 25, 0, 1); col = FLOW(sp_); col[:, 3] = fades[i] * (0.55 + 0.45 * sp_)
            l.set_segments(seg[ok]); l.set_linewidths((0.35 + 0.9 * sp_) * (0.5 + 0.5 * i / (TAIL - 2))); l.set_color(col)
        sp_ = np.clip(spd / 25, 0, 1); hc = FLOW(sp_); hc[:, 3] = np.where(dead, 0, 0.55 + 0.4 * sp_)
        heads.set_offsets(pts); heads.set_sizes(1.2 + 4 * sp_); heads.set_color(hc)
        # the cities: their tags (☂ in blue while it rains there), a widening ring when the rain starts
        wet_c = []; snow_c = []
        for j_, (p, gx_, gy_) in enumerate(zip(pl, cgx, cgy)):
            wet = 0 <= gy_ < P.shape[0] and 0 <= gx_ < P.shape[1] and P[gy_, gx_] >= 0.8
            snowy = wet and bool(SN[gy_, gx_])
            nm = Rn.city_name(p, lang)
            if wet:
                wet_c.append(nm); snow_c.append(nm) if snowy else None
                if nm not in wet_prev: rings[nm] = f
            if nm in rings and f - rings[nm] < 10:
                kk = (f - rings[nm]) / 10; dyn += ax.plot(p['lon'], p['lat'], 'o', ms=8 + 40 * kk, mfc='none', mec='#1f6fd1', mew=3 * (1 - kk), alpha=1 - kk, zorder=8.2)
            tp = tagpos[j_]
            if tp:
                yy_, xx_ = np.clip(gy_, 0, GU.shape[0] - 1), np.clip(gx_, 0, GU.shape[1] - 1); g_ = int(round(float(GU[yy_, xx_])))
                uu_, vv_ = (Q['u10'], Q['v10']) if 'u10' in Q else (Q['u'], Q['v'])
                ang = np.degrees(np.arctan2(vv_[ri[yy_], ci[xx_]], uu_[ri[yy_], ci[xx_]]))  # where the wind blows to
                arw = '→↗↑↖←↙↓↘'[int(((ang + 22.5) % 360) // 45)]
                dyn.append(ax.annotate(('❄ ' if snowy else '☂ ' if wet else '') + nm, (tp[0], tp[1]), fontsize=tagfs[j_], fontweight='bold', color='#6639ae' if snowy else '#1f6fd1' if wet else NAVY, ha=tp[2], va=tp[3], zorder=8.5, path_effects=halo))
                dyn.append(ax.annotate(f'{arw} {g_} ' + X['ms'], (0.12, 0) if tp[2] != 'right' else (0.88, 0), xycoords=dyn[-1], va='top', ha='left' if tp[2] != 'right' else 'right', fontsize=tagfs[j_] - 0.5,
                                       fontweight='bold', color='#b07800' if g_ >= 15 else '#5b6b7c', zorder=8.5, path_effects=halo))
        wet_prev = set(wet_c)
        tnow = run + dt.timedelta(hours=float(h))
        el = sun_elev(tnow); nd = np.zeros(LON.shape + (4,)); nd[..., 0] = 0.12; nd[..., 1] = 0.18; nd[..., 2] = 0.32; nd[..., 3] = np.clip((2 - el) / 10, 0, 1) * 0.16
        night.set_data(nd)
        prog.set_width(max(0.01, float(h)))
        head.set_xdata([h, h]); knob.set_xdata([h])
        flying = [pa for pa in paths if 0 <= pa['h'] - h <= np.array(pa['path'])[-1, 2]]
        if f < 5 * FPS: msg = X['c_intro']
        elif snow_c and len(snow_c) * 2 >= len(wet_c): msg = X['c_snow'].format(c=', '.join(snow_c[:3]))
        elif wet_c: msg = X['c_rain'].format(c=', '.join([c_ for c_ in wet_c if c_ not in snow_c][:3] or wet_c[:3]))
        elif flying: msg = X['c_go'].format(s=flying[0]['src'][lang], c=next((Rn.city_name(p, lang) for p in pl if p.get('ru') == flying[0]['city']), flying[0]['city']))
        else: msg = X['c_wet'] if (land.any() and float(np.mean(T[land] >= 25)) > 0.4) else X['c_dry']
        cap.set_text(msg)
        t = run + dt.timedelta(hours=float(h) + off)
        clock.set_text(f"{X['wd'][t.weekday()]} {t:%d.%m} · {t:%H}:{t:%M} · {TZ.get(region, (5, {}))[1].get(lang, X['tz'])}")
        fig.savefig(fdir / f'{f:03d}.png', dpi=150, facecolor=fig.get_facecolor())
        # the sound: the wind of the region, the rain when it falls on the country
        wet = float(np.mean(P[land] >= 1)) if land.any() else 0.0
        levels.append({'rain': min(1.0, wet * 2.5), 'snow': bool(land.any() and (P[land & SN] >= 1).sum() > (P[land & ~SN] >= 1).sum()), 'wind': float(np.clip(np.mean(spd) / 22, 0.15, 0.9)), 'storm': 0.0})
    plt.close(fig)
    for e in range(4 * FPS): shutil.copy(fdir / f'{len(hours) - 1:03d}.png', fdir / f'{len(hours) + e:03d}.png'); levels.append(levels[-1])  # hold the last frame
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', str(FPS), '-i', str(fdir / '%03d.png'), '-vf', 'framerate=fps=12:interp_start=0:interp_end=255:scene=100,scale=1920:-2:flags=lanczos,format=yuv420p', '-c:v', 'libx264', '-crf', '19', '-tune', 'animation',
                    '-preset', 'slow', '-movflags', '+faststart', str(mp4)], check=True)
    try:
        import sound as S_
        S_.mux(mp4, S_.track(levels, 1 / FPS, str(mp4) + '.wav', mode='all'))
    except Exception as e: print('moist sound failed', e, flush=True)
    Rn.fit_size(mp4, 19e6)  # Telegram takes a video by link up to 20 MB
    shutil.rmtree(fdir)


def extend_winds(W, F):
    """The steering winds past the trajectory data (+96 h): the 700 hPa wind of the moisture fields, put on the paths' grid
    (outside our area the last known wind stays)."""
    if not W: return W
    W = dict(W); last = max(W); U0, V0 = W[last]
    r0, c0 = int(round((LAT0 - TJ.LAT0) / TJ.RES)), int(round((LON0 - TJ.LON0) / TJ.RES)); stp = int(round(TJ.RES / RES))
    for st in sorted(F):
        if st <= last: continue
        U, V = U0.copy(), V0.copy(); u, v = F[st]['u'][::stp, ::stp], F[st]['v'][::stp, ::stp]
        h_, w_ = min(u.shape[0], U.shape[0] - r0), min(u.shape[1], U.shape[1] - c0)
        U[r0:r0 + h_, c0:c0 + w_] = u[:h_, :w_]; V[r0:r0 + h_, c0:c0 + w_] = v[:h_, :w_]; W[st] = (U, V)
    return W


def moisture_paths(F, W, region, n=3, H=72):
    """For the biggest cities with rain: the hour of their heaviest rain, the air's path 48 h back
    and its moisture source (the last sea it crossed, else the country it came from).
    Over 3 days: one path a city (at most n). Over 15 days: the rain events of every 3-day block (up to 2 a block)."""
    G, polys = TJ.load_polys()
    pl = sorted([p for p in json.load(open(HERE / 'geo_prob.json'))['places'] if p.get('iso') == region], key=lambda p: -p.get('pop', 0))[:8]
    blocks = [(3, 73)] if H <= 72 else [(b, min(b + 72, H + 1)) for b in range(3, H, 72)]
    per = n if H <= 72 else 2
    out = []
    for b0, b1 in blocks:
      got = []
      for p in pl:
        gx, gy = int(round((p['lon'] - LON0) / RES)), int(round((p['lat'] - LAT0) / RES))
        best = max(((interp(F, h)['pr'][gy, gx], h) for h in range(b0, b1, 3)), default=(0, 0))
        if best[0] < 1.0: continue
        path = TJ.follow(W, p['lon'], p['lat'], float(best[1]))
        if len(path) < 8: continue
        d = TJ.describe(path, region, polys, G)
        if not d: continue
        di, via, src = d
        if src: name = {'ru': TJ.SEA_NOM.get(src[0]['ru'], src[0]['ru']), 'uz': src[0]['uz'], 'tr': src[0]['tr']}
        elif via: name = {l: TJ.cname(via[-1], l, G) for l in ('ru', 'uz', 'tr')}
        else: continue
        if any(abs(o['path'][-1][0] - path[-1][0]) < 2.5 and abs(o['path'][-1][1] - path[-1][1]) < 2 for o in got) or any(o['src']['ru'] == name['ru'] for o in got): continue  # the same stream (or source) twice: once
        t2 = interp(F, best[1]).get('t2'); snow = bool(t2 is not None and t2[gy, gx] <= 0.5)
        got.append({'city': p.get('ru', p.get('en')), 'lon': p['lon'], 'lat': p['lat'], 'h': float(best[1]), 'path': path, 'src': name, 'snow': snow})
        if len(got) >= per: break
      out += got
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('npz'); ap.add_argument('out'); ap.add_argument('--regions', default='UZ,KZ'); ap.add_argument('--langs', default='ru,uz')
    ap.add_argument('--days', type=int, default=3); ap.add_argument('--fields', help='saved fields (tests)'); ap.add_argument('--winds', help='saved steering winds (tests)')
    a = ap.parse_args()
    import render as Rn
    D = Rn.load(a.npz); run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    if a.days > 3: run = run.replace(hour=0 if run.hour < 12 else 12)  # only the 00 and 12 UTC runs go 15 days ahead
    F = dict(np.load(a.fields, allow_pickle=True)['F'].item()) if a.fields else fetch(run, STEPS15 if a.days > 3 else None)
    if len(F) < 6: print('moist: not enough fields', flush=True); return
    out = pathlib.Path(a.out) / 'hr'; out.mkdir(parents=True, exist_ok=True)
    try: W = dict(np.load(a.winds, allow_pickle=True)['W'].item()) if a.winds else TJ.fetch_winds(run)
    except Exception as e: print('moist: no winds for the paths', e, flush=True); W = {}
    for region in a.regions.split(','):
        paths = []
        try: paths = moisture_paths(F, extend_winds(W, F) if a.days > 3 else W, region, H=72 if a.days <= 3 else min(a.days * 24, max(F))) if len(W) >= 6 else []
        except Exception as e: print('moist paths failed', region, e, flush=True)
        print('moist paths', region, [(p['city'], p['h'], p['src']['ru']) for p in paths], flush=True)
        for lang in a.langs.split(','):
            H = min(a.days * 24, max(F)) if a.days > 3 else 72
            name = f'{region}_moist_{lang}.mp4' if a.days <= 3 else f'{region}_moist15_{lang}.mp4'
            try: video(F, region, lang, out / name, run, paths=paths, H=int(H)); print('moist', region, lang, a.days, 'days ok', flush=True)
            except Exception as e:
                import traceback; traceback.print_exc(); print('moist failed', region, lang, e, flush=True)


if __name__ == '__main__':
    main()
