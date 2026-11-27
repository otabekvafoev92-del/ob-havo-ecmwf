"""On demand (the bot's «🎬 15 days» for a place): two videos in the look of the 15-day video (tools/prob15_video.py),
hour by hour, the chance of precipitation and the temperature —
  1) the whole country of the place (any country of the world), its biggest towns;
  2) the place itself, cut out close: its region and districts (Uzbekistan, Kazakhstan, Kyrgyzstan) or the towns around,
and sends them to the Telegram chat that asked.
Data: prob.npz (0.25°, Eurasia 20–190° E, 25–82° N) or glob.npz (0.5°, the world), wx.npz, fog.npz (optional).
Usage: python tools/place15.py DATA_DIR OUT --lang ru --lat 41.31 --lon 69.28 --name Ташкент [--iso UZ] [--chat ID]"""
import sys, os, json, math, pathlib, argparse, multiprocessing as mp
import numpy as np
from matplotlib.path import Path as MPath

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'prob'))
import prob15_video as PV
from uz_names import uz_name

GW = json.load(open(ROOT / 'prob' / 'geo_world.json')); GP = json.load(open(ROOT / 'prob' / 'geo_prob.json'))
GC = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']; GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))
TZC = {'UZ': 5, 'KZ': 5, 'KG': 6, 'TJ': 5, 'TM': 5, 'AZ': 4, 'AM': 4, 'GE': 4, 'TR': 3, 'BY': 3, 'MD': 2, 'UA': 2, 'AF': 4.5, 'IR': 3.5, 'CN': 8, 'IN': 5.5, 'RU': 3}
TZN = {'UZ': {'ru': 'по Ташкенту', 'uz': 'Toshkent vaqti'}}
AR = (PV.MAP[2] * PV.W) / (PV.MAP[3] * PV.H)  # the map's width : height
# the continents of the bot: the box to show and the centre of the equal-area map (Lambert azimuthal)
CONT = {'EU': dict(b=(-24, 45, 34, 71), c=(10, 52), ru='Европа', uz='Yevropa', tz=1), 'AS': dict(b=(32, 146, -8, 68), c=(90, 38), ru='Азия', uz='Osiyo', tz=5, main=('Ташкент', 'Toshkent', 41.31, 69.28)),
        'AF': dict(b=(-19, 52, -36, 38), c=(17, 2), ru='Африка', uz='Afrika', tz=2), 'NA': dict(b=(-168, -52, 8, 72), c=(-100, 45), ru='Северная Америка', uz='Shimoliy Amerika', tz=-6),
        'world': dict(b=(-180, 180, -58, 82), c=(0, 0), ru='Весь мир', uz='Butun dunyo', tz=5, proj='+proj=eqearth +lon_0=0 +datum=WGS84 +units=m', main=('Ташкент', 'Toshkent', 41.31, 69.28)),
        'SA': dict(b=(-82, -34, -56, 13), c=(-60, -20), ru='Южная Америка', uz='Janubiy Amerika', tz=-4), 'OC': dict(b=(112, 179, -47, -9), c=(142, -28), ru='Австралия и Океания', uz='Avstraliya va Okeaniya', tz=10)}


def rings_of(iso):
    c = GC.get(iso) or GW['countries'].get(iso)
    return [np.asarray(r, float) for r in (c['rings'] if c else [])]


def country_at(lat, lon):
    for iso, c in list(GC.items()) + list(GW['countries'].items()):
        if any(MPath(np.asarray(r)).contains_point((lon, lat)) for r in c['rings']): return iso
    return None


def cname(iso, lang):
    c = GW['countries'].get(iso) or GC.get(iso) or {}
    return c.get('ru') or c.get('name') or iso if lang == 'ru' else c.get('name') or iso


def towns_of(iso, box=None, n=12):
    seen, out = set(), []
    for p in sorted(GP['places'] + GW['places'], key=lambda p: (-(p.get('cap') or 0) // 2, -p.get('pop', 0))):
        if p.get('iso') != iso or p['en'] in seen: continue
        if box and not (box[0] < p['lon'] < box[1] and box[2] < p['lat'] < box[3]): continue
        seen.add(p['en']); out.append((p.get('ru') or p['en'], uz_name(p), p['lat'], p['lon']))
        if len(out) >= n: break
    return out


def spread(towns, min_deg):
    """Keep the towns at least min_deg apart (the first, the biggest or the chosen one, always stays)."""
    out = []
    for t in towns:
        if all(math.hypot((t[3] - o[3]) * math.cos(math.radians(t[2])), t[2] - o[2]) >= min_deg for o in out): out.append(t)
    return out


def fit(lo0, lo1, la0, la1, pad=0.08):
    """The map's latitude range and centre longitude that show the box whole at the map's width : height."""
    cl = math.cos(math.radians((la0 + la1) / 2)); w, h = (lo1 - lo0) * cl, la1 - la0
    w, h = w * (1 + 2 * pad), h * (1 + 2 * pad)
    if w / h > AR: h = w / AR
    mid = (la0 + la1) / 2
    return (max(-85, mid - h / 2), min(85, mid + h / 2)), (lo0 + lo1) / 2


def borders(iso, adm2=False):
    # the neighbours: the detailed Central Asia pack where it has the country, the world pack elsewhere (one line per border)
    nb = [np.asarray(r, float) for k, c in GC.items() if k != iso for r in c['rings']] + [np.asarray(r, float) for k, c in GW['countries'].items() if k != iso and k not in GC for r in c['rings']]
    out = [(nb, '#a3acb6', 1.0, 3)]
    if iso in GA:
        out.append(([np.asarray(r) for a in GA[iso]['adm1'] for r in a['r']], '#3b4652' if adm2 else '#b7c0ca', 1.8 if adm2 else 0.8, 3.05))
        if adm2: out.append(([np.asarray(r) for d in GA[iso]['adm2'] for r in d['r']], '#c3cbd3', 0.6, 3.02))
    elif iso in GP['admin1']: out.append(([np.asarray(r) for r in GP['admin1'][iso]], '#b7c0ca', 0.8, 3.05))
    if not (adm2 and iso in GA): out.append((rings_of(iso), '#1c2633', 2.6, 3.3))  # close up: the regions' own lines are the border (one line, not two)
    return out


def render(data, out, lang, view):
    npz = data / ('prob.npz' if view['src'] == 'prob' else 'glob.npz')
    PV.FOG = str(data / 'fog.npz') if (data / 'fog.npz').exists() else None
    PV.main(str(npz), str(data / 'wx.npz'), str(out), [lang], only=int(os.environ.get('P15_ONLY', 0)) or None, view=view)
    jobs = [(lang, i) for i in range(len(PV.CTX['videos'][lang]['frames']))]
    with mp.get_context('fork').Pool(max(1, os.cpu_count() or 1)) as pool:
        list(pool.imap_unordered(PV.draw, jobs, chunksize=4))
        r = pool.apply(PV.encode, (lang,))
    print(r, flush=True)
    return out / f"{view['stem']}{ {'temp': '_t', 'cloud': '_c'}.get(os.environ.get('P15_MODE', ''), '')}_{lang}.mp4"


def src_for(la, lo):
    return 'prob' if 22 <= lo[0] and lo[1] <= 188 and 27 <= la[0] and la[1] <= 80 else 'glob'


def continent(data, out, code, lang):
    """The 15-day hourly video of a continent: the world data (0.5°), so the precipitation fills the whole map; an equal-area map."""
    C = CONT[code]; X = PV.TX[lang]; b = C['b']
    CN = {'EU': ('Europe',), 'AS': ('Asia',), 'AF': ('Africa',), 'NA': ('North America',), 'SA': ('South America',), 'OC': ('Oceania',)}.get(code)  # the continent's own towns only
    inc = lambda p: CN is None or (GW['countries'].get(p.get('iso'), {}).get('cont') in CN)
    big = sorted([p for p in GW['places'] if b[0] < p['lon'] < b[1] and b[2] < p['lat'] < b[3] and inc(p)], key=lambda p: (-(p.get('cap') or 0), -p.get('pop', 0)))
    towns = spread(([C['main']] if C.get('main') else []) + [(p.get('ru') or p['en'], uz_name(p), p['lat'], p['lon']) for p in big], (b[3] - b[2]) / 9)[:14 if not C.get('main') else 18]
    nb = [np.asarray(r, float) for c in GW['countries'].values() for r in c['rings']]
    view = dict(proj=C.get('proj') or f"+proj=laea +lat_0={C['c'][1]} +lon_0={C['c'][0]} +datum=WGS84 +units=m", bounds=b, globe=code == 'world', towns=towns, main=towns[0][0], borders=[(nb, '#7d8995', 0.7, 3)],
                off=C['tz'], stem=f'country_{code}', src='glob', intro2={lang: {'ru': f"на 15 дней: {C['ru']}", 'uz': f"15 kunga: {C['uz']}"}[lang]}, sig=1.3, title={lang: f"{C[lang]} · {X['title']}"}, tzl={lang: ({'ru': 'по Ташкенту', 'uz': 'Toshkent vaqti'} if code == 'world' else {'ru': f"UTC{C['tz']:+d}", 'uz': f"UTC{C['tz']:+d}"})[lang]},
                chart_t={lang: X['chart'].replace('Ташкент', towns[0][0]).replace('Toshkent', towns[0][1])})
    PV.FOG = None
    f = render(data, out, lang, view); print('continent', code, f, flush=True); return f


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('data'); ap.add_argument('out'); ap.add_argument('--lang', default='ru')
    ap.add_argument('--lat', type=float); ap.add_argument('--lon', type=float); ap.add_argument('--name', default=''); ap.add_argument('--iso', default='')
    ap.add_argument('--chat', default=''); ap.add_argument('--only', default=''); ap.add_argument('--cont', default='')
    a = ap.parse_args(); data, out = pathlib.Path(a.data), pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True); lang = a.lang
    if a.cont: return continent(data, out, a.cont, lang)
    iso = a.iso or (country_at(a.lat, a.lon) if a.lat is not None else 'UZ') or 'UZ'
    X = PV.TX[lang]; cn = cname(iso, lang); off = TZC.get(iso, round((a.lon if a.lon is not None else 64) / 15))
    tz = TZN.get(iso, {}).get(lang) or ({'ru': 'местное время', 'uz': 'mahalliy vaqt'}[lang])
    files = []
    # 1) the country
    R = rings_of(iso)
    if a.only in ('', 'country') and R:
        big = max(R, key=lambda r: len(r)); keep = [r for r in R if len(r) >= 0.15 * len(big)]  # far small islands do not stretch the map
        P_ = np.concatenate(keep); lo0, lo1, la0, la1 = P_[:, 0].min(), P_[:, 0].max(), P_[:, 1].min(), P_[:, 1].max()
        lat, lc = fit(lo0, lo1, la0, la1)
        cl = math.cos(math.radians(sum(lat) / 2)); span = (lat[1] - lat[0]) / cl * AR
        towns = spread(towns_of(iso, (lo0, lo1, la0, la1), 24), (lat[1] - lat[0]) / 14)[:12]
        if iso == 'UZ': towns = PV.TOWNS
        if towns:
            view = dict(lat=lat, lc=lc, towns=towns, main=towns[0][0], borders=borders(iso), off=off, intro2={lang: {'ru': f'на 15 дней: {cn}', 'uz': f'15 kunga: {cn}'}[lang]}, stem=f'country_{iso}', src=src_for(lat, (lc - span / 2, lc + span / 2)),
                        title={lang: f"{cn} · {X['title']}"}, tzl={lang: tz}, chart_t={lang: X['chart'].replace('Ташкент', towns[0][0 if lang == 'ru' else 1]).replace('Toshkent', towns[0][1])})
            files.append(('country', render(data, out, lang, view)))
    # 2) the place, close: its region and districts
    if a.only in ('', 'place') and a.lat is not None:
        h = 1.3; lat = (a.lat - h / 2, a.lat + h / 2); cl = math.cos(math.radians(a.lat)); span = h / cl * AR; lc = a.lon
        box = (lc - span / 2 + 0.15, lc + span / 2 - 0.15, lat[0] + 0.1, lat[1] - 0.1)
        nm = a.name or 'Место'
        me = (nm, nm, a.lat, a.lon); near = []
        if iso in GA:  # the districts' centres around
            for d in GA[iso]['adm2']:
                lo_, la_ = d['c']; n_ = d['name']
                if box[0] < lo_ < box[1] and box[2] < la_ < box[3]: near.append((n_['ru'], n_.get('uz') or n_['ru'], la_, lo_))
        near += [t for t in towns_of(iso, box, 30)]
        near.sort(key=lambda t: math.hypot((t[3] - a.lon) * cl, t[2] - a.lat))  # the nearest first
        towns = spread([me] + near, 0.11)[:10]
        view = dict(lat=lat, lc=lc, up=6, sig=5.0, towns=towns, main=nm, intro2={lang: {'ru': f'на 15 дней: {nm}', 'uz': f'15 kunga: {nm}'}[lang]}, borders=borders(iso, adm2=True), off=off, stem='place', src=src_for(lat, (lc - span / 2, lc + span / 2)),
                    title={lang: f"{nm} · {X['title']}"}, tzl={lang: tz}, chart_t={lang: X['chart'].replace('Ташкент', nm).replace('Toshkent', nm)})
        files.append(('place', render(data, out, lang, view)))
    json.dump([[k, str(f)] for k, f in files], open(out / 'files.json', 'w'))
    tok = os.environ.get('TELEGRAM_BOT_TOKEN')
    if a.chat and tok:
        import requests
        cap = {'country': {'ru': f'🎬 {cn}: вероятность осадков и температура на 15 дней по часам', 'uz': f'🎬 {cn}: 15 kunga soatma-soat yog‘in ehtimoli va harorat'},
               'place': {'ru': f'📍 {a.name}: вероятность осадков и температура на 15 дней по часам', 'uz': f'📍 {a.name}: 15 kunga soatma-soat yog‘in ehtimoli va harorat'}}
        for k, f in files:
            with open(f, 'rb') as fh:
                r = requests.post(f'https://api.telegram.org/bot{tok}/sendVideo', data=dict(chat_id=a.chat, caption=cap[k][lang], supports_streaming='true', width=1920, height=1080),
                                  files=dict(video=(f.name, fh, 'video/mp4')), timeout=300)
            print('telegram', k, r.status_code, r.text[:200], flush=True)


if __name__ == '__main__':
    main()
