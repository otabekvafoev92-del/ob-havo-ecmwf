"""A live weather animation for a province's capital, 48 hours hour by hour (Full HD, ~24 s):
left — the city from above: its boundary and its buildings (OpenStreetMap), with the weather moving over it (rain, snow, fog, cloud shade);
right — the city's skyline under its sky: the sun and the moon on their way, clouds drifting with the wind, rain or snow falling, lightning, fog;
below — the 48 hours: temperature, precipitation, the moment shown.
Data: Open-Meteo (hourly forecast), OpenStreetMap (Nominatim boundary, Overpass buildings).
Usage: python tools/city_live.py out <k> uz,ru  →  out/city<k>_<lang>.mp4   (k: index in CITIES)"""
import sys, json, math, pathlib, shutil, subprocess, tempfile, time, datetime as dt
import numpy as np, requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.patches import Rectangle, Circle, Polygon as MPoly

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'prob'))
import prob15_video as PV  # noqa: E402
from brand import brand, mark  # noqa: E402

W, H, DPI = 1920, 1080, 100
NAVY, AMBER, INK, MUTED = '#0B2545', '#FFB020', '#15202b', '#5b6876'
SIGN = 'Bot - @ObHavo_ECMWF_bot · Kanal - @osmon_obhavo'
UA = {'User-Agent': 'osmon-weather/1.0 (https://t.me/ObHavo_ECMWF_bot)'}
CITIES = [('Toshkent', 'Ташкент', 41.311, 69.279, 'Tashkent', 3500), ('Nurafshon', 'Нурафшан', 41.04, 69.36, 'Nurafshon', 2000),
          ('Andijon', 'Андижан', 40.783, 72.344, 'Andijan', 2500), ('Farg‘ona', 'Фергана', 40.384, 71.784, 'Fergana', 2500),
          ('Qo‘qon', 'Коканд', 40.528, 70.943, 'Kokand', 2500), ('Namangan', 'Наманган', 40.998, 71.673, 'Namangan', 2500),
          ('Guliston', 'Гулистан', 40.49, 68.785, 'Gulistan', 2000), ('Jizzax', 'Джизак', 40.116, 67.842, 'Jizzakh', 2200),
          ('Samarqand', 'Самарканд', 39.655, 66.976, 'Samarkand', 3000), ('Qarshi', 'Карши', 38.861, 65.79, 'Karshi', 2500),
          ('Termiz', 'Термез', 37.224, 67.278, 'Termez', 2500), ('Buxoro', 'Бухара', 39.768, 64.421, 'Bukhara', 2500),
          ('Navoiy', 'Навои', 40.103, 65.374, 'Navoiy', 2200), ('Urganch', 'Ургенч', 41.55, 60.631, 'Urgench', 2200),
          ('Nukus', 'Нукус', 42.461, 59.611, 'Nukus', 2500)]
X = {'uz': dict(title='Shahar ob-havosi jonli · 48 soat', now='hozir', feels='his qilinadi', wind='shamol', ms='m/s', prec='yog‘in', mm='mm', hum='namlik',
                wx={0: 'ochiq', 1: 'asosan ochiq', 2: 'qisman bulutli', 3: 'bulutli', 45: 'tuman', 48: 'qirovli tuman', 51: 'mayda yomg‘ir', 53: 'mayda yomg‘ir', 55: 'mayda yomg‘ir',
                    61: 'yomg‘ir', 63: 'yomg‘ir', 65: 'kuchli yomg‘ir', 66: 'muzli yomg‘ir', 67: 'muzli yomg‘ir', 71: 'qor', 73: 'qor', 75: 'kuchli qor', 77: 'qor donalari',
                    80: 'jala', 81: 'jala', 82: 'kuchli jala', 85: 'qor', 86: 'kuchli qor', 95: 'momaqaldiroq', 96: 'do‘lli momaqaldiroq', 99: 'do‘lli momaqaldiroq'},
                wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'], src='Open-Meteo · OpenStreetMap', dirs=['shim.', 'shim.-sharq', 'sharq', 'jan.-sharq', 'janub', 'jan.-g‘arb', 'g‘arb', 'shim.-g‘arb']),
     'ru': dict(title='Погода в городе вживую · 48 часов', now='сейчас', feels='ощущается', wind='ветер', ms='м/с', prec='осадки', mm='мм', hum='влажность',
                wx={0: 'ясно', 1: 'малооблачно', 2: 'переменная облачность', 3: 'пасмурно', 45: 'туман', 48: 'туман с изморозью', 51: 'морось', 53: 'морось', 55: 'морось',
                    61: 'дождь', 63: 'дождь', 65: 'сильный дождь', 66: 'ледяной дождь', 67: 'ледяной дождь', 71: 'снег', 73: 'снег', 75: 'сильный снег', 77: 'снежная крупа',
                    80: 'ливень', 81: 'ливень', 82: 'сильный ливень', 85: 'снегопад', 86: 'сильный снегопад', 95: 'гроза', 96: 'гроза с градом', 99: 'гроза с градом'},
                wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], src='Open-Meteo · OpenStreetMap', dirs=['северный', 'северо-восточный', 'восточный', 'юго-восточный', 'южный', 'юго-западный', 'западный', 'северо-западный'])}
FPH = 4  # frames per hour (12 fps → a third of a second an hour; ~16 s for 48 hours)


def get_json(url, params, tries=5, post=None):
    for k in range(tries):
        try:
            r = (requests.post(url, data=post, headers=UA, timeout=180) if post else requests.get(url, params=params, headers=UA, timeout=120))
            if r.ok: return r.json()
            print('http', url, r.status_code, r.text[:120], flush=True)
            if r.status_code == 429: time.sleep(60); continue
        except Exception as e: print('net', url, e, flush=True)
        time.sleep(4 * (k + 1))
    return None


def city_shape(c):
    """The city's boundary (Nominatim) and its buildings within the view (Overpass), in local km."""
    la0, lo0, R = c[2], c[3], c[5] / 1000
    kx = 111.32 * math.cos(math.radians(la0)); ky = 110.57
    to = lambda lon, lat: ((np.asarray(lon) - lo0) * kx, (np.asarray(lat) - la0) * ky)
    rings = []
    j = get_json('https://nominatim.openstreetmap.org/search', dict(q=f'{c[4]}, Uzbekistan', format='json', polygon_geojson=1, limit=3))
    for it in (j or []):
        g = it.get('geojson') or {}
        if g.get('type') in ('Polygon', 'MultiPolygon') and it.get('class') in ('boundary', 'place'):
            polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
            for poly in polys:
                a = np.asarray(poly[0]); x, y = to(a[:, 0], a[:, 1]); rings.append(np.c_[x, y])
            break
    # the map itself, drawn by us from OpenStreetMap: buildings, streets by class, rivers and canals, water, parks and green
    rr = int(R * 1000 * 1.25)
    q = (f'[out:json][timeout:150];(way["building"](around:{rr},{la0},{lo0});way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|unclassified|living_street"](around:{rr},{la0},{lo0});'
         f'way["waterway"~"river|canal|stream"](around:{rr},{la0},{lo0});way["natural"="water"](around:{rr},{la0},{lo0});way["leisure"~"park|garden|stadium"](around:{rr},{la0},{lo0});'
         f'way["landuse"~"grass|forest|cemetery|recreation_ground"](around:{rr},{la0},{lo0}););out geom;')
    M = dict(b=[], water=[], green=[], river=[], roads={})
    for url in ('https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter'):
        j = get_json(url, None, tries=2, post={'data': q})
        if j:
            for el in j.get('elements', []):
                gm = el.get('geometry'); tg = el.get('tags', {})
                if not gm or len(gm) < 2: continue
                x, y = to([p['lon'] for p in gm], [p['lat'] for p in gm]); a = np.c_[x, y]
                if 'building' in tg and len(gm) >= 3: M['b'].append(a)
                elif 'highway' in tg: M['roads'].setdefault(tg['highway'], []).append(a)
                elif tg.get('waterway'): M['river'].append(a)
                elif tg.get('natural') == 'water' and len(gm) >= 3: M['water'].append(a)
                elif len(gm) >= 3: M['green'].append(a)
            break
    print(c[0], 'boundary rings', len(rings), 'buildings', len(M['b']), 'roads', sum(len(v) for v in M['roads'].values()), flush=True)
    return rings, M, R


def weather(c):
    j = get_json('https://api.open-meteo.com/v1/forecast', dict(latitude=c[2], longitude=c[3], timezone='Asia/Tashkent', forecast_days=3,
                 hourly='temperature_2m,apparent_temperature,precipitation,snowfall,weather_code,cloud_cover,visibility,wind_speed_10m,wind_direction_10m,relative_humidity_2m,is_day',
                 daily='sunrise,sunset', wind_speed_unit='ms'))
    hh = j['hourly']; now = dt.datetime.utcnow() + dt.timedelta(hours=5)
    t = [dt.datetime.fromisoformat(x) for x in hh['time']]; i0 = max(0, next((i for i, x in enumerate(t) if x >= now.replace(minute=0, second=0, microsecond=0)), 0))
    sl = slice(i0, i0 + 49)
    A = {k: np.array([v if v is not None else np.nan for v in hh[k][sl]], float) for k in hh if k != 'time'}
    A['t'] = t[sl]; A['sun'] = {d: (dt.datetime.fromisoformat(a), dt.datetime.fromisoformat(b)) for d, a, b in zip(j['daily']['time'], j['daily']['sunrise'], j['daily']['sunset'])}
    return A


def lerp(a, i, f): return a[min(i, len(a) - 1)] * (1 - f) + a[min(i + 1, len(a) - 1)] * f


def sky_rgb(day_frac, cloud):
    """Sky colours (top, bottom) for the sun's height (−1 night … 1 noon) and cloud cover (0..1)."""
    night = (np.array([10, 18, 38]), np.array([28, 40, 70])); dusk = (np.array([40, 60, 110]), np.array([245, 150, 90])); day = (np.array([60, 130, 210]), np.array([170, 210, 245]))
    if day_frac <= -0.15: top, bot = night
    elif day_frac < 0.15:
        f = (day_frac + 0.15) / 0.3; top = night[0] * (1 - f) + dusk[0] * f; bot = night[1] * (1 - f) + dusk[1] * f
    else:
        f = min(1, (day_frac - 0.15) / 0.35); top = dusk[0] * (1 - f) + day[0] * f; bot = dusk[1] * (1 - f) + day[1] * f
    grey = np.array([150, 160, 172]) * (0.35 + 0.65 * max(0, day_frac + 0.2)) if day_frac > -0.2 else np.array([40, 46, 58])
    k = 0.75 * cloud
    return (top * (1 - k) + grey * k) / 255, (bot * (1 - k) + grey * k) / 255


RNG = np.random.default_rng(7)
SKY = dict(bld=None, clouds=RNG.random((14, 3)), drops=RNG.random((420, 2)), flakes=RNG.random((260, 2)), stars=RNG.random((140, 2)))


def skyline(n=46):
    """A generic city skyline (towers, blocks, a dome and a minaret) — the same every frame."""
    rng = np.random.default_rng(11); x = 0.0; out = []
    while x < 1.0:
        w = rng.uniform(0.018, 0.05); h = rng.choice([rng.uniform(0.08, 0.2), rng.uniform(0.2, 0.42)], p=[0.75, 0.25]); out.append(('b', x, w, h, rng.random())); x += w + rng.uniform(0.0, 0.006)
    out.append(('dome', 0.33, 0.07, 0.17, 0)); out.append(('min', 0.395, 0.012, 0.33, 0)); out.append(('tower', 0.72, 0.012, 0.55, 0))
    return out


def draw_scene(ax, A, i, f, k, lang):
    """The right panel: the sky over the city at hour i + f."""
    t = A['t'][min(i, len(A['t']) - 1)] + dt.timedelta(hours=f)
    sr, ss = A['sun'].get(t.date().isoformat(), (t.replace(hour=7), t.replace(hour=17)))
    hr = t.hour + t.minute / 60; a, b = sr.hour + sr.minute / 60, ss.hour + ss.minute / 60
    day_frac = math.sin(math.pi * (hr - a) / (b - a)) if a <= hr <= b else -0.6 if (hr < a - 1 or hr > b + 1) else -0.3
    cl = lerp(A['cloud_cover'], i, f) / 100; pr = lerp(A['precipitation'], i, f); sn = lerp(A['snowfall'], i, f); vis = lerp(A['visibility'], i, f)
    ws = lerp(A['wind_speed_10m'], i, f); wdir = A['wind_direction_10m'][min(i, len(A['t']) - 1)]; code = int(A['weather_code'][min(i, len(A['t']) - 1)])
    top, bot = sky_rgb(day_frac, cl)
    g = np.linspace(0, 1, 256)[:, None, None]; ax.imshow(top * (1 - g) + bot * g, extent=(0, 1, 0, 1), aspect='auto', zorder=0, origin='upper')
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    if day_frac < -0.1 and cl < 0.7:
        st = SKY['stars']; ax.scatter(st[:, 0], 0.35 + st[:, 1] * 0.65, s=2 + 4 * st[:, 0] % 3, c='white', alpha=(1 - cl) * 0.8, zorder=1, lw=0)
    # the sun (by day) or the moon (by night) along an arc
    if a <= hr <= b:
        p = (hr - a) / (b - a); sx, sy = 0.08 + 0.84 * p, 0.42 + 0.48 * math.sin(math.pi * p)
        ax.add_patch(Circle((sx, sy), 0.07, fc=AMBER, ec='none', alpha=0.25 * (1 - cl), zorder=1)); ax.add_patch(Circle((sx, sy), 0.04, fc='#ffd166', ec='none', alpha=1 - 0.8 * cl, zorder=2))
    else:
        p = ((hr - b) % 24) / ((a + 24 - b) % 24 or 12); mx, my = 0.1 + 0.8 * p, 0.5 + 0.35 * math.sin(math.pi * p)
        ax.add_patch(Circle((mx, my), 0.03, fc='#f5f0d0', ec='none', alpha=1 - 0.8 * cl, zorder=2))
    # clouds drifting with the wind
    drift = (k / (FPH * 48)) * (0.3 + ws / 8) * (1 if 180 < wdir < 360 or wdir < 0 else -1)
    shade = 0.92 if day_frac > 0 else 0.4
    ncl = int(round(3 + cl * 11))
    for j, (cx, cy, cs) in enumerate(SKY['clouds'][:ncl]):
        x = (cx + drift * (0.6 + cs)) % 1.3 - 0.15; y = 0.62 + cy * 0.33; s = 0.05 + cs * 0.06
        col = np.clip(np.array([shade, shade, shade + 0.02]) - 0.35 * min(1, pr / 2), 0, 1)
        for dx, dy, r in ((-1, 0, 1), (0, 0.5, 1.3), (1, 0, 1.05), (0.4, -0.3, 0.9), (-0.5, -0.3, 0.9)):
            ax.add_patch(Circle((x + dx * s * 0.9, y + dy * s * 0.6), s * r * 0.75, fc=col, ec='none', alpha=0.88, zorder=3))
    # the city
    for kind, x0, w, h, r in sorted(SKY['bld'], key=lambda b: b[0] != 'b'):
        lit = day_frac < 0
        col = '#1d2b3f' if not lit else '#0d1626'
        if kind == 'b':
            ax.add_patch(Rectangle((x0, 0.18), w, h, fc=col, ec='none', zorder=5))
            if lit:
                rng = np.random.default_rng(int(x0 * 1e4)); wx = rng.random((int(h * 40), max(1, int(w * 60)))) > 0.55
                yy, xx = np.nonzero(wx); ax.scatter(x0 + (xx + 0.5) / max(1, wx.shape[1]) * w, 0.18 + (yy + 0.5) / max(1, wx.shape[0]) * h, s=3, marker='s', c='#ffd98a', alpha=0.85, lw=0, zorder=6)
        elif kind == 'dome':  # a domed hall: a wide base, a drum, the blue dome, a golden finial
            ax.add_patch(Rectangle((x0 - w * 0.75, 0.18), w * 1.5, h * 0.45, fc='#2c3e57' if not lit else '#16233a', ec='none', zorder=5.5))
            ax.add_patch(Rectangle((x0 - w * 0.42, 0.18 + h * 0.45), w * 0.84, h * 0.18, fc='#2c3e57' if not lit else '#16233a', ec='none', zorder=5.5))
            from matplotlib.patches import Ellipse
            ax.add_patch(Ellipse((x0, 0.18 + h * 0.63), w * 0.84, h * 0.62, fc='#2a8fbd' if not lit else '#1d4f6e', ec='none', zorder=5.4))
            ax.plot([x0, x0], [0.18 + h * 0.93, 0.18 + h * 1.05], color='#e9c46a', lw=2, zorder=5.6)
        elif kind == 'min':
            ax.add_patch(Rectangle((x0, 0.18), w, h, fc='#2c3e57' if not lit else '#16233a', ec='none', zorder=5.5))
            ax.add_patch(Rectangle((x0 - w * 0.4, 0.18 + h * 0.86), w * 1.8, h * 0.05, fc='#2c3e57' if not lit else '#16233a', ec='none', zorder=5.5))
            ax.add_patch(Circle((x0 + w / 2, 0.18 + h * 0.97), w * 0.7, fc='#2a8fbd' if not lit else '#1d4f6e', ec='none', zorder=5.5))
        elif kind == 'tower':
            ax.add_patch(MPoly([[x0 - 0.012, 0.18], [x0 + 0.024, 0.18], [x0 + 0.010, 0.18 + h], [x0 + 0.002, 0.18 + h]], closed=True, fc=col, ec='none', zorder=5))
            ax.add_patch(Circle((x0 + 0.006, 0.18 + h * 0.72), 0.014, fc=col, ec='none', zorder=5))
    ax.add_patch(Rectangle((0, 0), 1, 0.18, fc='#2b3a4d' if day_frac > 0 else '#141d2b', ec='none', zorder=5))
    if sn >= 0.05 or (code in (71, 73, 75, 77, 85, 86)):
        ax.add_patch(Rectangle((0, 0.16), 1, 0.03, fc='white', ec='none', alpha=min(0.9, 0.3 + sn), zorder=6))
    # rain or snow
    slant = 0.02 + ws / 300
    if pr >= 0.05 and not (sn >= 0.05 or code in (71, 73, 75, 77, 85, 86)):
        n = int(min(420, 60 + pr * 140)); d = SKY['drops'][:n]
        y = (d[:, 1] - k * 0.09) % 1.0; x = (d[:, 0] + y * slant) % 1
        segs = np.stack([np.c_[x, y * 0.82 + 0.18], np.c_[x - slant * 0.6, y * 0.82 + 0.18 - 0.035]], 1)
        ax.add_collection(LineCollection(segs, colors='#cfe3ff', linewidths=1.3, alpha=0.75, zorder=7))
    elif sn >= 0.05 or code in (71, 73, 75, 77, 85, 86):
        n = int(min(260, 50 + sn * 120)); d = SKY['flakes'][:n]
        y = (d[:, 1] - k * 0.012) % 1.0; x = (d[:, 0] + 0.02 * np.sin(k * 0.2 + d[:, 1] * 9) + y * slant) % 1
        ax.scatter(x, y * 0.82 + 0.18, s=12, c='white', alpha=0.9, lw=0, zorder=7)
    if code >= 95 and (k % 23) in (0, 1):  # lightning
        ax.add_patch(Rectangle((0, 0), 1, 1, fc='white', alpha=0.45, zorder=8)); bx = 0.3 + 0.4 * ((k // 23) % 3) / 2
        ax.plot([bx, bx - 0.03, bx + 0.02, bx - 0.02], [0.9, 0.7, 0.6, 0.35], color='#fff6c2', lw=3, zorder=9)
    if vis < 2000:  # fog
        ax.add_patch(Rectangle((0, 0), 1, 1, fc='#d6dde5', alpha=min(0.75, (2000 - vis) / 2000 * 0.8), zorder=8))
    return t, day_frac, pr, sn, code, cl, vis, ws, wdir


_CITY = {}


def city_img(rings, blds, R, night):
    """The city from above drawn once (thousands of buildings), by day or by night, as a picture the frames reuse."""
    if night in _CITY: return _CITY[night]
    import io
    from PIL import Image
    M = blds
    fig = plt.figure(figsize=(11, 11), dpi=100); ax = fig.add_axes([0, 0, 1, 1]); ax.set_facecolor('#101827' if night else '#f2efe9')
    ax.set_xlim(-R, R); ax.set_ylim(-R, R); ax.axis('off')
    if M['green']: ax.add_collection(PolyCollection(M['green'], facecolors='#1d3b2f' if night else '#cfe8c4', edgecolors='none', zorder=1))
    if M['water']: ax.add_collection(PolyCollection(M['water'], facecolors='#173a5c' if night else '#a8d0f0', edgecolors='none', zorder=2))
    if M['river']: ax.add_collection(LineCollection(M['river'], colors='#2a5d8a' if night else '#8cc0ea', linewidths=2.2, zorder=2))
    if M['b']: ax.add_collection(PolyCollection(M['b'], facecolors='#e9c46a' if night else '#d9d2c6', edgecolors='none' if night else '#c4bbac', linewidths=0.2, alpha=0.55 if night else 1, zorder=3))
    W_ = {'motorway': 4.5, 'trunk': 4.2, 'primary': 3.6, 'secondary': 3.0, 'tertiary': 2.4, 'residential': 1.4, 'unclassified': 1.4, 'living_street': 1.1}
    for cls in ('living_street', 'residential', 'unclassified', 'tertiary', 'secondary', 'primary', 'trunk', 'motorway'):
        L_ = M['roads'].get(cls)
        if not L_: continue
        w = W_[cls]; main = cls in ('motorway', 'trunk', 'primary', 'secondary')
        ax.add_collection(LineCollection(L_, colors='#0a101b' if night else '#c9c2b6', linewidths=w + 1.2, capstyle='round', zorder=4))
        ax.add_collection(LineCollection(L_, colors=('#c79a3a' if main else '#3a4658') if night else ('#ffd88a' if main else '#ffffff'), linewidths=w, capstyle='round', zorder=4.1))
    for r in rings: ax.plot(r[:, 0], r[:, 1], color='#FFB020', lw=2.5, zorder=5)
    buf = io.BytesIO(); fig.savefig(buf, format='png', facecolor=ax.get_facecolor()); plt.close(fig)
    _CITY[night] = np.asarray(Image.open(buf).convert('RGB')); return _CITY[night]


def boundary_inset(fig, ax, rings, R):
    """A small map in the corner: the whole city within its boundary, the square shown big beside it."""
    if not rings: return
    allp = np.concatenate(rings); x0, y0 = allp.min(0); x1, y1 = allp.max(0); sp = max(x1 - x0, y1 - y0) * 0.55; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bb = ax.get_position(); ins = fig.add_axes([bb.x0 + 0.006, bb.y1 - 0.20, 0.10, 0.10 * W / H * 0.95])
    ins.set_facecolor('#0B2545'); ins.patch.set_alpha(0.75); ins.set_xlim(cx - sp, cx + sp); ins.set_ylim(cy - sp, cy + sp); ins.set_aspect(1); ins.set_xticks([]); ins.set_yticks([])
    for s_ in ins.spines.values(): s_.set_color('#FFB020'); s_.set_linewidth(1)
    for r in rings: ins.fill(r[:, 0], r[:, 1], fc='#FFB020', alpha=0.25); ins.plot(r[:, 0], r[:, 1], color='#FFB020', lw=1.5)
    ins.add_patch(Rectangle((-R, -R * 0.94), 2 * R, 1.88 * R, fc='none', ec='white', lw=1.5))


def draw_city(ax, rings, blds, R, A, i, f, k, day_frac):
    ax.imshow(city_img(rings, blds, R, day_frac <= 0), extent=(-R, R, -R * 0.94, R * 0.94), aspect='auto', zorder=1)
    ax.set_xlim(-R, R); ax.set_ylim(-R * 0.94, R * 0.94); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    pr = lerp(A['precipitation'], i, f); sn = lerp(A['snowfall'], i, f); cl = lerp(A['cloud_cover'], i, f) / 100; vis = lerp(A['visibility'], i, f)
    ax.add_patch(Rectangle((-R, -R), 2 * R, 2 * R, fc='#0b1525', alpha=0.25 * cl, zorder=4))  # cloud shade
    if pr >= 0.05:
        rng = np.random.default_rng(3); n = int(min(500, 80 + pr * 150)); p = rng.random((n, 2))
        if sn >= 0.05: ax.scatter((p[:, 0] * 2 - 1) * R, ((p[:, 1] - k * 0.01) % 1 * 2 - 1) * R * 0.82, s=10, c='white', lw=0, alpha=0.9, zorder=5)
        else:
            y = ((p[:, 1] - k * 0.05) % 1 * 2 - 1) * R * 0.82; x = (p[:, 0] * 2 - 1) * R
            ax.add_collection(LineCollection(np.stack([np.c_[x, y], np.c_[x - R * 0.01, y - R * 0.03]], 1), colors='#3d7fe0', linewidths=1.2, alpha=0.7, zorder=5))
    if vis < 2000: ax.add_patch(Rectangle((-R, -R), 2 * R, 2 * R, fc='#d6dde5', alpha=min(0.7, (2000 - vis) / 2000 * 0.75), zorder=6))
    ax.plot([R * 0.62, R * 0.92], [-R * 0.74] * 2, color='#5b6876', lw=3, zorder=7); ax.text(R * 0.77, -R * 0.70, f'{R * 0.3:.1f} km', ha='center', fontsize=12, color='#5b6876', zorder=7)


MAPCAP = {'uz': '{n} · xarita: OpenStreetMap', 'ru': '{n} · карта: OpenStreetMap'}
TITLE = {'uz': 'Shahar ob-havosi jonli · 48 soat', 'ru': 'Погода в городе вживую · 48 часов'}


def render(c, lang, out, shape):
    """The scene is drawn in a browser canvas (tools/city_scene.html: sky, sun and moon, clouds, the skyline, rain, snow, fog, the map card with a slow camera move)
    and captured frame by frame with Playwright; 30 fps, 48 hours in ~19 s."""
    import base64, io
    from playwright.sync_api import sync_playwright
    rings, M, R = shape; L = X[lang]; A = weather(c); n = len(A['t']) - 1
    tmp = pathlib.Path(tempfile.mkdtemp())
    def png(night):
        from PIL import Image
        b = io.BytesIO(); Image.fromarray(city_img(rings, M, R, night)).save(b, 'JPEG', quality=88); return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
    hours = [dict(t=A['t'][i].strftime('%Y-%m-%dT%H:%M:00Z'), T=float(np.nan_to_num(A['temperature_2m'][i])), F=float(np.nan_to_num(A['apparent_temperature'][i])),
                  p=float(np.nan_to_num(A['precipitation'][i])), s=float(np.nan_to_num(A['snowfall'][i])), code=int(np.nan_to_num(A['weather_code'][i])),
                  cl=float(np.nan_to_num(A['cloud_cover'][i])), vis=float(np.nan_to_num(A['visibility'][i], nan=20000)), ws=float(np.nan_to_num(A['wind_speed_10m'][i])),
                  wd=float(np.nan_to_num(A['wind_direction_10m'][i])), rh=float(np.nan_to_num(A['relative_humidity_2m'][i]))) for i in range(n + 1)]
    sun = {d: [a.hour + a.minute / 60, b.hour + b.minute / 60] for d, (a, b) in A['sun'].items()}
    name = c[0] if lang == 'uz' else c[1]
    data = dict(hours=hours, sun=sun, name=name, tower=c[0] == 'Toshkent', fph=15,
                lab=dict(title=TITLE[lang], src=L['src'], wd=L['wd'], wx={str(k): v for k, v in L['wx'].items()}, feels=L['feels'], wind=L['wind'], ms=L['ms'], hum=L['hum'],
                         mapcap=MAPCAP[lang].format(n=name)), map=dict(day=png(False), night=png(True)))
    N = n * 15
    with sync_playwright() as pw:
        br = pw.chromium.launch(); pg = br.new_page(viewport={'width': W, 'height': H})
        pg.goto((ROOT / 'tools' / 'city_scene.html').as_uri()); pg.wait_for_timeout(1500)
        pg.evaluate('d => { d.lab.wx = Object.fromEntries(Object.entries(d.lab.wx).map(([k, v]) => [+k, v])); return window.init(d); }', data)
        for k in range(N):
            pg.evaluate(f'window.frame({k})'); pg.screenshot(path=str(tmp / f'{k:04d}.jpg'), type='jpeg', quality=88)
        br.close()
    part = out.with_name('.' + out.name + '.part.mp4')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '30', '-i', str(tmp / '%04d.jpg'), '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-map', '0:v', '-map', '1:a',
                    '-vf', 'format=yuv420p', '-c:v', 'libx264', '-crf', '21', '-preset', 'medium', '-c:a', 'aac', '-b:a', '48k', '-shortest', '-movflags', '+faststart', str(part)], check=True)
    part.replace(out); shutil.rmtree(tmp); print(out, out.stat().st_size // 1024, 'KB', flush=True)


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); ks = [int(x) for x in sys.argv[2].split(',')]; langs = (sys.argv[3] if len(sys.argv) > 3 else 'uz,ru').split(',')
    for k in ks:
        c = CITIES[k]; shape = city_shape(c)
        for lang in langs: render(c, lang, out / f'city{k}_{lang}.mp4', shape)


if __name__ == '__main__':
    main()
