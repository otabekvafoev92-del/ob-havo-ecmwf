"""Where the rain and snow come from (Uzbekistan, Kazakhstan): back-trajectories of the air that brings them.
For each big city with a likely rain or snow day in the next three days, the air arriving at the wettest time is
followed back 48 hours along the ECMWF wind at about 3 km (0.65 × 850 hPa + 0.35 × 500 hPa, the "steering" level
that carries the clouds). The path tells the direction and the moisture source (the Caspian, the Mediterranean...).
  out/hr/<region>_traj.json             every path, with a short text in ru/uz/tr
  out/hr/<region>_traj_<lang>.png       the map of the paths (Full HD)
Wind: ECMWF IFS open data (AWS mirror): the analyses of the last two days' runs, then the current run's forecast.
Usage: python3 prob/trajectory.py prob.npz out [--regions UZ,KZ] [--langs ru,uz]"""
import argparse, concurrent.futures as cf, datetime as dt, json, pathlib, sys, time
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ECM = 'https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com'
LON0, LON1, LAT0, LAT1, RES = 0.0, 120.0, 15.0, 70.0, 0.5   # the area the paths may cross
BACK = 48                                                   # hours back
SEAS = [  # name ru/uz/tr, lon0, lon1, lat0, lat1 (checked only where no country is)
    ({'ru': 'Каспийского моря', 'uz': 'Kaspiy dengizi', 'tr': 'Hazar Denizi'}, 46.0, 55.5, 36.4, 47.5),
    ({'ru': 'Аральского моря', 'uz': 'Orol dengizi', 'tr': 'Aral Gölü'}, 58.0, 61.8, 43.4, 46.9),
    ({'ru': 'Чёрного моря', 'uz': 'Qora dengiz', 'tr': 'Karadeniz'}, 27.0, 42.0, 40.8, 47.0),
    ({'ru': 'Средиземного моря', 'uz': 'O‘rta yer dengizi', 'tr': 'Akdeniz'}, -6.0, 36.5, 30.0, 46.0),
    ({'ru': 'Персидского залива', 'uz': 'Fors ko‘rfazi', 'tr': 'Basra Körfezi'}, 47.5, 57.0, 23.5, 30.6),
    ({'ru': 'Аравийского моря', 'uz': 'Arabiston dengizi', 'tr': 'Umman Denizi'}, 50.0, 78.0, 5.0, 25.5),
    ({'ru': 'Красного моря', 'uz': 'Qizil dengiz', 'tr': 'Kızıldeniz'}, 32.0, 44.0, 12.0, 30.0),
    ({'ru': 'озера Балхаш', 'uz': 'Balxash ko‘li', 'tr': 'Balkaş Gölü'}, 73.0, 79.5, 44.8, 47.3),
]
UZN = {'TM': 'Turkmaniston', 'IR': 'Eron', 'AF': 'Afg‘oniston', 'KZ': 'Qozog‘iston', 'RU': 'Rossiya', 'CN': 'Xitoy', 'KG': 'Qirg‘iziston', 'TJ': 'Tojikiston',
       'AZ': 'Ozarbayjon', 'TR': 'Turkiya', 'GE': 'Gruziya', 'AM': 'Armaniston', 'IQ': 'Iroq', 'SY': 'Suriya', 'PK': 'Pokiston', 'IN': 'Hindiston', 'MN': 'Mo‘g‘uliston',
       'SA': 'Saudiya Arabistoni', 'UA': 'Ukraina', 'EG': 'Misr', 'UZ': 'O‘zbekiston', 'BY': 'Belarus', 'KW': 'Quvayt', 'JO': 'Iordaniya', 'IL': 'Isroil', 'GR': 'Gretsiya'}
DIR = {'ru': ['с севера', 'с северо-востока', 'с востока', 'с юго-востока', 'с юга', 'с юго-запада', 'с запада', 'с северо-запада'],
       'uz': ['shimoldan', 'shimoli-sharqdan', 'sharqdan', 'janubi-sharqdan', 'janubdan', 'janubi-g‘arbdan', 'g‘arbdan', 'shimoli-g‘arbdan'],
       'tr': ['kuzeyden', 'kuzeydoğudan', 'doğudan', 'güneydoğudan', 'güneyden', 'güneybatıdan', 'batıdan', 'kuzeybatıdan']}
TX = {'ru': dict(title='Откуда придут осадки', rain='дождь', snow='снег', come='{w} придёт {d}', via='путь воздуха: {c}', src='влага — с {s} ({h} назад)', h='{n} ч', d1='сутки', d2='двое суток',
                 sub='Путь воздуха, который принесёт осадки, за 2 суток до их начала', ago='{n} ч назад', none='В ближайшие дни осадков не ожидается', start='осадки начинаются'),
      'uz': dict(title='Yog‘in qayerdan keladi', rain='yomg‘ir', snow='qor', come='{w} {d} keladi', via='havo yo‘li: {c}', src='namlik — {s}dan ({h} oldin)', h='{n} soat', d1='bir kun', d2='ikki kun',
                 sub='Yog‘in olib keladigan havoning boshlanishidan 2 kun oldingi yo‘li', ago='{n} soat oldin', none='Yaqin kunlarda yog‘in kutilmaydi', start='yog‘in boshlanadi'),
      'tr': dict(title='Yağış nereden gelecek', rain='yağmur', snow='kar', come='{w} {d} gelecek', via='havanın yolu: {c}', src='nem {s} kaynaklı ({h} önce)', h='{n} saat', d1='bir gün', d2='iki gün',
                 sub='Yağışı getirecek havanın, başlamadan önceki 2 günlük yolu', ago='{n} saat önce', none='Önümüzdeki günlerde yağış beklenmiyor', start='yağış başlıyor')}
S = None


def get(url, rng=None):
    import requests
    global S
    S = S or requests.Session()
    for a in range(6):
        try:
            r = S.get(url, headers={'Range': f'bytes={rng[0]}-{rng[1]}'} if rng else {}, timeout=60)
            if r.status_code in (200, 206): return r.content
            if r.status_code in (403, 404): return None
        except Exception: pass
        time.sleep(2 * (a + 1))
    return None


def crop(buf):
    import eccodes
    h = eccodes.codes_new_from_message(buf)
    v = eccodes.codes_get_values(h).reshape(eccodes.codes_get(h, 'Nj'), eccodes.codes_get(h, 'Ni')); eccodes.codes_release(h)
    # global 0.25° from 90°N, 180°W → the area at 0.5°
    lat = 90 - np.arange(v.shape[0]) * 0.25; lon = -180 + np.arange(v.shape[1]) * 0.25
    r = np.flatnonzero((lat <= LAT1) & (lat >= LAT0))[::2]; c = np.flatnonzero((lon >= LON0) & (lon <= LON1))[::2]
    return v[np.ix_(r, c)][::-1].astype(np.float32)  # rows south → north


def fetch_winds(run):
    """{hours from run: (U, V)} on the area grid: past runs' analyses (−48…−6 h), then the forecast (0…+96 h)."""
    want = []  # (hour from run, run time, step)
    for back in range(BACK, 0, -6): want.append((-back, run - dt.timedelta(hours=back), 0))
    for st in range(0, 97, 6): want.append((st, run, st))
    jobs = []
    for hr, r, st in want:
        d, hh = r.strftime('%Y%m%d'), r.strftime('%H')
        stream = 'oper' if hh in ('00', '12') else 'scda'  # the 06/18 runs are the short "scda" stream
        base = f'{ECM}/{d}/{hh}z/ifs/0p25/{stream}/{d}{hh}0000-{st}h-{stream}-fc'
        idx = get(base + '.index')
        if not idx: print('traj: missing', base, flush=True); continue
        for line in idx.decode().strip().split('\n'):
            x = json.loads(line)
            if x.get('levtype') == 'pl' and x.get('levelist') in ('850', '500') and x.get('param') in ('u', 'v'):
                jobs.append((hr, x['levelist'], x['param'], base + '.grib2', (x['_offset'], x['_offset'] + x['_length'] - 1)))
    F = {}
    with cf.ThreadPoolExecutor(12) as pool:
        for (hr, lev, par, url, rng), buf in zip(jobs, pool.map(lambda j: get(j[3], j[4]), jobs)):
            if buf: F[(hr, lev, par)] = crop(buf)
    W = {}
    for hr in sorted({k[0] for k in F}):
        try: W[hr] = tuple(0.65 * F[(hr, '850', p)] + 0.35 * F[(hr, '500', p)] for p in ('u', 'v'))
        except KeyError: pass
    print('traj: wind at', len(W), 'times', flush=True)
    return W


def follow(W, lon, lat, t_end):
    """The air arriving at (lon, lat) at t_end (hours from run), followed back BACK hours (1 h steps, midpoint rule).
    Returns [[lon, lat, hours before arrival], ...] every 3 h."""
    ts = np.array(sorted(W)); ny, nx = W[ts[0]][0].shape
    def wind(lo, la, t):
        if t < ts[0] or t > ts[-1] or not (LON0 <= lo <= LON1 - RES and LAT0 <= la <= LAT1 - RES): return None
        j = int(np.clip(np.searchsorted(ts, t), 1, len(ts) - 1)); a = (t - ts[j - 1]) / (ts[j] - ts[j - 1])
        fx, fy = (lo - LON0) / RES, (la - LAT0) / RES; x0, y0 = int(fx), int(fy); dx, dy = fx - x0, fy - y0
        out = []
        for c in range(2):
            v = 0.0
            for tt, wt in ((ts[j - 1], 1 - a), (ts[j], a)):
                f = W[tt][c]; v += wt * ((1 - dy) * ((1 - dx) * f[y0, x0] + dx * f[y0, x0 + 1]) + dy * ((1 - dx) * f[y0 + 1, x0] + dx * f[y0 + 1, x0 + 1]))
            out.append(v)
        return out
    def move(lo, la, u, v, sec):  # metres → degrees
        return lo + u * sec / (111320 * np.cos(np.radians(la))), la + v * sec / 110540
    path = [[round(lon, 2), round(lat, 2), 0]]; lo, la, t = lon, lat, t_end
    for k in range(1, BACK + 1):
        w1 = wind(lo, la, t)
        if w1 is None: break
        mlo, mla = move(lo, la, w1[0], w1[1], -1800)
        w2 = wind(mlo, mla, t - 0.5)
        if w2 is None: break
        lo, la = move(lo, la, w2[0], w2[1], -3600); t -= 1
        if k % 3 == 0: path.append([round(lo, 2), round(la, 2), k])
    return path


def country_at(lon, lat, polys):
    from matplotlib.path import Path
    for iso, rings in polys.items():
        for r in rings:
            if r[1][0] <= lon <= r[1][1] and r[1][2] <= lat <= r[1][3] and r[0].contains_point((lon, lat)): return iso
    return None


def describe(path, home, polys, names):
    """Direction (from where the last 12 hours came), the countries on the way, and the moisture source (a sea)."""
    if len(path) < 3: return None
    a = path[min(4, len(path) - 1)]; b = path[0]  # 12 h before arrival → arrival
    ang = (np.degrees(np.arctan2(a[0] - b[0], a[1] - b[1])) + 360) % 360  # where the air came from
    di = int(((ang + 22.5) % 360) // 45)
    via, src = [], None
    for lo, la, h in path[1:]:
        iso = country_at(lo, la, polys)
        if iso and iso != home and iso not in via: via.append(iso)
        if iso is None and src is None:
            for nm, x0, x1, y0, y1 in SEAS:
                if x0 <= lo <= x1 and y0 <= la <= y1: src = (nm, h); break
    return di, via[:3], src


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('npz'); ap.add_argument('out'); ap.add_argument('--regions', default='UZ,KZ'); ap.add_argument('--langs', default='ru,uz')
    ap.add_argument('--winds', help='a saved wind file (tests)')
    a = ap.parse_args()
    import render as Rn
    D = Rn.load(a.npz); P, _, _ = Rn.probability(D); geo = Rn.Geo(None)
    run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    W = dict(np.load(a.winds, allow_pickle=True)['W'].item()) if a.winds else fetch_winds(run)
    if len(W) < 6: print('traj: not enough wind', flush=True); return
    from matplotlib.path import Path
    G = json.load(open(HERE / 'geo_world.json'))['countries']
    polys = {}
    for iso, c in G.items():
        rr = []
        for r in c['rings']:
            ar = np.asarray(r)
            if ar[:, 0].max() < LON0 - 10 or ar[:, 0].min() > LON1 + 10 or ar[:, 1].max() < LAT0 - 10: continue
            rr.append((Path(ar), (ar[:, 0].min(), ar[:, 0].max(), ar[:, 1].min(), ar[:, 1].max())))
        if rr: polys[iso] = rr
    cname = lambda iso, lang: (UZN.get(iso, G.get(iso, {}).get('name', iso)) if lang == 'uz' else G.get(iso, {}).get(lang) or G.get(iso, {}).get('name', iso))
    out = pathlib.Path(a.out) / 'hr'; out.mkdir(parents=True, exist_ok=True)
    st = np.array([int(x) for x in D['steps']], float); wn = np.array([int(x) for x in D['win']], float); mid = st - wn / 2
    for region in a.regions.split(','):
        R = Rn.Region(D, geo, region, P, D['amt']); off = 5
        items = []
        for p in R.cities[:14]:
            Pc = np.clip(R.series(p), 0, 100); Tc = R.tseries(p)
            for k in range(3):  # today, tomorrow, the day after (local)
                now_l = min(dt.datetime.now(dt.timezone.utc).replace(tzinfo=None), run + dt.timedelta(hours=12)) + dt.timedelta(hours=off)  # (an old test run: its own days)
                d = now_l.date() + dt.timedelta(days=k)
                idx = [i for i in range(len(mid)) if (run + dt.timedelta(hours=float(mid[i]) + off)).date() == d and mid[i] <= 96]
                if not idx: continue
                i = max(idx, key=lambda i: Pc[i])
                if Pc[i] < 40: continue
                path = follow(W, p['lon'], p['lat'], float(mid[i]))
                if len(path) < 6: continue
                dsc = describe(path, region, polys, G)
                if not dsc: continue
                di, via, src = dsc; snow = Tc is not None and float(Tc[i]) <= 0.5
                text = {}
                for lang in ('ru', 'uz', 'tr'):
                    X = TX[lang]; parts = [X['come'].format(w=(X['snow'] if snow else X['rain']).capitalize(), d=DIR[lang][di])]
                    if via: parts.append(X['via'].format(c=' → '.join(cname(c, lang) for c in reversed(via))))
                    if src: parts.append(X['src'].format(s=src[0][lang], h=X['d2'] if src[1] >= 42 else X['d1'] if 20 <= src[1] <= 30 else X['h'].format(n=src[1])))
                    text[lang] = ', '.join(parts)
                items.append({'city': {l: Rn.city_name(p, l) for l in ('ru', 'uz', 'tr')}, 'lat': p['lat'], 'lon': p['lon'], 'day': d.isoformat(), 'k': k,
                              't': (run + dt.timedelta(hours=float(mid[i]) + off)).strftime('%Y-%m-%dT%H:00'), 'p': int(round(Pc[i])), 'snow': bool(snow),
                              'dir': di, 'via': via, 'src': src[0] if src else None, 'path': path, 'text': text})
        json.dump({'region': region, 'run': D['run'], 'items': items}, open(out / f'{region}_traj.json', 'w'), ensure_ascii=False, separators=(',', ':'))
        for lang in a.langs.split(','):
            try: picture(R, region, items, lang, out / f'{region}_traj_{lang}.png', run, polys)
            except Exception as e: print('traj picture failed', region, lang, e, flush=True)
            if items:
                try: picture(R, region, items, lang, None, run, polys, anim=out / f'{region}_traj_{lang}.mp4')
                except Exception as e: print('traj animation failed', region, lang, e, flush=True)
        print('traj', region, len(items), 'paths', flush=True)


def picture(R, region, items, lang, path, run, polys, anim=None):
    import render as Rn
    from render import plt, matplotlib
    from regions import NAMES, T as TT
    from hourly import NAVY, PAPER, LAND
    X = TX[lang]; L = TT[lang]
    G = json.load(open(HERE / 'geo_world.json'))['countries']
    fig = plt.figure(figsize=(12.8, 7.2), dpi=150); fig.patch.set_facecolor('#dfe9f2')
    fig.patches.append(matplotlib.patches.Rectangle((0, 0.93), 1, 0.07, transform=fig.transFigure, facecolor=NAVY, edgecolor='none', zorder=-6))
    ink0 = Rn.INK; Rn.INK = '#ffffff'
    try: x = Rn._brand(fig, 0.016, 0.965, size=11)
    finally: Rn.INK = ink0
    fig.text(x + 0.014, 0.965, f"{NAMES[region][lang]} · {X['title']}", fontsize=14, fontfamily=Rn.DISPLAY, fontweight='bold', color='#ffffff', va='center')
    fig.text(0.984, 0.965, X['sub'], fontsize=10, color='#c9d6e5', ha='right', va='center')
    ax = fig.add_axes([0, 0.06, 1, 0.87]); ax.set_facecolor('#dfe9f2'); ax.set_xticks([]); ax.set_yticks([])
    for s_ in ax.spines.values(): s_.set_visible(False)
    # the view: the paths and the country, in plain lon/lat with the latitude squeeze
    pts = np.array([[q[0], q[1]] for it in items for q in it['path']]).reshape(-1, 2)
    cr = np.concatenate([np.asarray(r) for r in G.get(region, {}).get('rings', [])])
    allp = np.vstack([pts, cr]) if len(pts) else cr
    x0, x1, y0, y1 = allp[:, 0].min() - 2, allp[:, 0].max() + 2, allp[:, 1].min() - 1.5, allp[:, 1].max() + 1.5
    k = np.cos(np.radians((y0 + y1) / 2)); asp = 12.8 / (7.2 * 0.87)
    if (x1 - x0) * k / (y1 - y0) < asp: c = (x0 + x1) / 2; w = (y1 - y0) * asp / k; x0, x1 = c - w / 2, c + w / 2
    else: c = (y0 + y1) / 2; h = (x1 - x0) * k / asp; y0, y1 = c - h / 2, c + h / 2
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect(1 / k)
    PC, LC = matplotlib.collections.PolyCollection, matplotlib.collections.LineCollection
    near = lambda r: np.asarray(r)[:, 0].max() > x0 - 5 and np.asarray(r)[:, 0].min() < x1 + 5 and np.asarray(r)[:, 1].max() > y0 - 5 and np.asarray(r)[:, 1].min() < y1 + 5
    for iso, c_ in G.items():
        rr = [np.asarray(r) for r in c_['rings'] if near(r)]
        if rr: ax.add_collection(PC(rr, facecolor='#ffffff' if iso == region else LAND, edgecolor='#ffffff' if iso != region else NAVY, linewidths=1.6 if iso == region else 0.8, zorder=1 if iso != region else 1.5))
    for iso, c_ in G.items():  # country names (not our own), faint
        if iso == region: continue
        rr = [np.asarray(r) for r in c_['rings']]
        if not rr: continue
        big = max(rr, key=len); cx_, cy_ = big[:, 0].mean(), big[:, 1].mean()
        if x0 + 1 < cx_ < x1 - 1 and y0 + 0.8 < cy_ < y1 - 0.8 and len(big) > 30:
            ax.text(cx_, cy_, (UZN.get(iso) if lang == 'uz' else c_.get(lang)) or c_.get('name', iso), fontsize=8, color='#8a9bb0', ha='center', va='center', zorder=1.8)
    for nm, sx0, sx1, sy0, sy1 in SEAS:  # sea names
        cx_, cy_ = (sx0 + sx1) / 2, (sy0 + sy1) / 2
        if x0 < cx_ < x1 and y0 < cy_ < y1 and country_at(cx_, cy_, polys) is None:
            nom = {'Каспийского моря': 'Каспийское море', 'Аральского моря': 'Аральское море', 'Чёрного моря': 'Чёрное море', 'Средиземного моря': 'Средиземное море', 'Персидского залива': 'Персидский залив',
                   'Аравийского моря': 'Аравийское море', 'Красного моря': 'Красное море', 'озера Балхаш': 'оз. Балхаш'}
            ax.text(cx_, cy_, nom.get(nm[lang], nm[lang]), fontsize=8.5, style='italic', color='#6d8aa6', ha='center', va='center', zorder=2)
    cols = ['#3a78b5', '#e0895a', '#8a63b8', '#2f9e8f', '#c75b7a', '#6b8e23']
    if not items:
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, X['none'], fontsize=18, color=NAVY, ha='center', va='center', fontweight='bold', zorder=9)
    seen = set()
    show = sorted(items, key=lambda it: (it['k'], -it['p']))
    show = [it for it in show if not (it['city']['ru'] in seen or seen.add(it['city']['ru']))][:6]
    if anim: return _animate(fig, ax, show, cols, lang, X, L, (x0, x1, y0, y1), anim)
    for j, it in enumerate(show):
        c = cols[j % len(cols)]; pth = np.array(it['path'])
        ax.plot(pth[:, 0], pth[:, 1], color=c, lw=2.6, alpha=0.9, zorder=5, solid_capstyle='round')
        for q in pth[4::4]:  # a dot every 12 h, labelled every 24 h
            ax.plot(q[0], q[1], 'o', ms=4.5, mfc='#ffffff', mec=c, mew=1.6, zorder=6)
            if int(q[2]) % 24 == 0: ax.text(q[0], q[1] + 0.45, X['ago'].format(n=int(q[2])), fontsize=7.5, color=c, ha='center', va='bottom', fontweight='bold', zorder=7)
        # arrows along the way, pointing to the city
        for m in (len(pth) // 3, 2 * len(pth) // 3):
            if 1 <= m < len(pth): ax.annotate('', xy=pth[m - 1, :2], xytext=pth[m, :2], arrowprops=dict(arrowstyle='-|>', color=c, lw=2, mutation_scale=16), zorder=6)
        ax.plot(it['lon'], it['lat'], 'o', ms=8, mfc=c, mec='#ffffff', mew=2, zorder=8)
        d = dt.date.fromisoformat(it['day'])
        right = it['lon'] > x0 + 0.72 * (x1 - x0)  # near the right edge: the label goes to the left of the city
        ax.text(it['lon'] + (-0.35 if right else 0.35), it['lat'] - 0.35, f"{it['city'][lang]} · {L['wd'][d.weekday()]} {d:%d.%m} · {'❄' if it['snow'] else '☂'} {it['p']}%", fontsize=9, fontweight='bold', color=NAVY, zorder=9, ha='right' if right else 'left', va='top',
                bbox=dict(boxstyle='round,pad=0.25,rounding_size=0.5', fc='#ffffffee', ec=c, lw=1.2))
    fig.text(0.016, 0.03, 'ECMWF IFS · ~3 км / km', fontsize=8.5, color='#5b6b80', va='center')
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor()); plt.close(fig)


def _animate(fig, ax, show, cols, lang, X, L, view, mp4):
    """The air moving: each path grows from 48 h before the rain to the city (a comet with a fading tail), the clock
    counting down, then the rain starts at the cities. 16 frames a second, about 9 s, with the sound of wind and rain."""
    import subprocess, shutil, tempfile
    from render import plt
    from hourly import NAVY
    x0, x1, y0, y1 = view
    fdir = pathlib.Path(tempfile.mkdtemp())
    P = []
    for j, it in enumerate(show):  # every path, densified to 0.5 h, oldest first
        pth = np.array(it['path'], float)[::-1]; hs = np.arange(pth[0, 2], -0.01, -0.5)
        P.append((it, cols[j % len(cols)], np.interp(-hs, -pth[:, 2], pth[:, 0]), np.interp(-hs, -pth[:, 2], pth[:, 1]), hs))
    for it, c, *_ in P:  # the cities and their labels stay all the time
        ax.plot(it['lon'], it['lat'], 'o', ms=8, mfc=c, mec='#ffffff', mew=2, zorder=8)
        d = dt.date.fromisoformat(it['day']); right = it['lon'] > x0 + 0.72 * (x1 - x0)
        ax.text(it['lon'] + (-0.35 if right else 0.35), it['lat'] - 0.35, f"{it['city'][lang]} · {L['wd'][d.weekday()]} {d:%d.%m} · {'❄' if it['snow'] else '☂'} {it['p']}%", fontsize=9, fontweight='bold', color=NAVY, zorder=9,
                ha='right' if right else 'left', va='top', bbox=dict(boxstyle='round,pad=0.25,rounding_size=0.5', fc='#ffffffee', ec=c, lw=1.2))
    clock = ax.text(x0 + (x1 - x0) * 0.02, y1 - (y1 - y0) * 0.05, '', fontsize=22, fontweight='bold', color=NAVY, va='top', zorder=10,
                    bbox=dict(boxstyle='round,pad=0.35,rounding_size=0.8', fc='#ffffffee', ec='#c9d3de', lw=1))
    taus = list(np.arange(48, -0.01, -0.5)) + [0.0] * 40; dyn = []; lv = []
    for f, tau in enumerate(taus):
        for a in dyn: a.remove()
        dyn = []
        for it, c, xs, ys, hs in P:
            m = hs >= tau - 1e-6
            if m.sum() < 1: continue
            xx, yy = xs[m], ys[m]
            dyn += ax.plot(xx, yy, color=c, lw=2.4, alpha=0.55, zorder=5, solid_capstyle='round')
            tail = slice(max(0, len(xx) - 8), len(xx))  # the bright head of the comet
            dyn += ax.plot(xx[tail], yy[tail], color=c, lw=4.2, alpha=0.95, zorder=5.5, solid_capstyle='round')
            dyn += ax.plot(xx[-1], yy[-1], 'o', ms=10, mfc=c, mec='#ffffff', mew=2.2, zorder=7)
            if tau <= 0.01:  # arrived: the rain (or snow) at the city, pulsing
                k = (f - taus.index(0.0)) % 16 / 16
                dyn += ax.plot(it['lon'], it['lat'], 'o', ms=14 + 22 * k, mfc='none', mec=c, mew=2.5 * (1 - k), alpha=1 - k, zorder=7.5)
        clock.set_text(X['ago'].format(n=int(round(tau))) if tau > 0.01 else ('❄ ' if any(it['snow'] for it, *_ in P) else '☂ ') + X['start'])
        fig.savefig(fdir / f'{f:03d}.png', dpi=100, facecolor=fig.get_facecolor())
        lv.append({'rain': 0.0 if tau > 0.01 else 0.55, 'snow': tau <= 0.01 and any(it['snow'] for it, *_ in P), 'wind': 0.45 + 0.35 * (1 - tau / 48), 'storm': 0.0})
    plt.close(fig)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '16', '-i', str(fdir / '%03d.png'), '-vf', 'format=yuv420p', '-c:v', 'libx264', '-crf', '23', '-preset', 'medium',
                    '-tune', 'animation', '-movflags', '+faststart', str(mp4)], check=True)
    try:
        import sound as S_
        S_.mux(mp4, S_.track(lv, 1 / 16, str(mp4) + '.wav', mode='all'))
    except Exception as e: print('traj sound failed', e, flush=True)
    shutil.rmtree(fdir)


if __name__ == '__main__':
    main()
