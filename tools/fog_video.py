"""Fog over Uzbekistan for the next 24 hours, hour by hour, as a Full HD video in the Osmon look; and the list of the districts
with fog (out/fog.json, read by the bot). Data: the Open-Meteo forecast (ECMWF IFS, ICON, GFS — the best model for each place):
the visibility and the weather code on a 0.75° grid and at the 199 district centres. Fog: weather code 45/48 or visibility under
1 km; haze 1–2 km. The models are fetched at most every 3 hours (out/fog_raw.npz); every hourly run moves the 24-hour window.
Usage: python tools/fog_video.py out ru,uz [previous fog_raw.npz]  →  out/fog24_{lang}.mp4, out/fog.json, out/fog_raw.npz"""
import sys, os, json, time, math, pathlib, shutil, subprocess, tempfile, datetime as dt, multiprocessing as mp
import numpy as np, requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import FancyBboxPatch, Rectangle
import matplotlib.patheffects as pe
from scipy.ndimage import zoom, gaussian_filter

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import prob15_video as PV

W, H, DPI = PV.W, PV.H, PV.DPI
MAP = PV.MAP; LA0, LA1 = PV.LAT0, PV.LAT1; LC = 64.8
COSL = math.cos(math.radians((LA0 + LA1) / 2)); SPAN = (LA1 - LA0) / COSL * (MAP[2] * W) / (MAP[3] * H); EXT = (LC - SPAN / 2, LC + SPAN / 2)
LATS = np.round(np.arange(35.5, 47.6, 1.0), 2); LONS = np.round(np.arange(50.5, 80.6, 1.0), 2)  # 1° grid (fog is local: the 199 districts carry the detail)
API = 'https://api.open-meteo.com/v1/forecast'
GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']
FOGC = ['#e9eef3', '#c9d2dc', '#9aa8b8']  # haze, fog, thick fog
TX = {'ru': dict(title='Туман · 24 часа', tz='по Ташкенту', src='Open-Meteo: ECMWF, ICON, GFS · видимость', vis='видимость', fog='туман', clear='ясно',
                 leg=['дымка 1–2 км', 'туман 0,5–1 км', 'густой туман < 500 м'], chart='Районов Узбекистана в тумане по часам', km='км', m='м', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
                 intro1='Туман', intro2='на 24 часа по районам Узбекистана', end1='Туман в вашем районе', end2='в Telegram-боте @ObHavo_ECMWF_bot', nofog='тумана не ожидается'),
      'uz': dict(title='Tuman · 24 soat', tz='Toshkent vaqti', src='Open-Meteo: ECMWF, ICON, GFS · ko‘rinish', vis='ko‘rinish', fog='tuman', clear='ochiq',
                 leg=['g‘ubor 1–2 km', 'tuman 0,5–1 km', 'quyuq tuman < 500 m'], chart='O‘zbekistonda tumanli tumanlar soni (soatma-soat)', km='km', m='m', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'],
                 intro1='Tuman', intro2='O‘zbekiston tumanlari bo‘yicha 24 soatga', end1='Tumaningizdagi tuman', end2='Telegram-botda: @ObHavo_ECMWF_bot', nofog='tuman kutilmaydi')}
CTX = {}


def fetch(lats, lons, hours=30):
    out_v, out_c, times = [], [], None
    for i in range(0, len(lats), 100):
        r = None
        for _ in range(8):
            try:
                r = requests.get(API, params=dict(latitude=','.join(f'{x:.3f}' for x in lats[i:i + 100]), longitude=','.join(f'{x:.3f}' for x in lons[i:i + 100]),
                                                  hourly='visibility,weather_code', forecast_hours=hours, past_hours=1, timezone='GMT'), timeout=180)
                if r.status_code == 200: break
                print('fog api', r.status_code, r.text[:120], flush=True)
            except Exception as e: print('fog api', e, flush=True)
            time.sleep(61 if r is not None and r.status_code == 429 else 5)
        if r is None or r.status_code != 200: raise RuntimeError('fog api failed')
        J = r.json(); J = J if isinstance(J, list) else [J]
        for j in J:
            times = times or j['hourly']['time']
            out_v.append([np.nan if x is None else x for x in j['hourly']['visibility']]); out_c.append([0 if x is None else x for x in j['hourly']['weather_code']])
        time.sleep(0.5)
    return np.array(out_v, np.float32), np.array(out_c, np.int16), times


def get_data(prev):
    if prev and pathlib.Path(prev).exists():
        z = np.load(prev, allow_pickle=True)
        if z['gv'].shape[:2] == (len(LATS), len(LONS)) and time.time() - float(z['fetched']) < 2.5 * 3600: print('fog data from the last fetch', flush=True); return {k: z[k] for k in z.files}
    gl, go = np.meshgrid(LATS, LONS, indexing='ij')
    gv, gc, times = fetch(gl.ravel(), go.ravel())
    dv, dc, _ = fetch(np.array([d['c'][1] for d in GA['adm2']]), np.array([d['c'][0] for d in GA['adm2']]))
    tv, tc, _ = fetch(np.array([t[2] for t in PV.TOWNS]), np.array([t[3] for t in PV.TOWNS]))
    return dict(gv=gv.reshape(len(LATS), len(LONS), -1), gc=gc.reshape(len(LATS), len(LONS), -1), dv=dv, dc=dc, tv=tv, tc=tc, times=np.array(times), fetched=np.array(time.time()))


def fogness(v, c):
    """0 clear … 1 thick fog: the weather code fog (45, 48) or the visibility (haze from 2 km, fog under 1 km, thick under 500 m)."""
    f = np.clip((2000 - np.nan_to_num(v, nan=24000)) / 1800, 0, 1)
    return np.maximum(f, np.where(np.isin(c, (45, 48)), 0.75, 0))


def vis_text(v, c, X):
    if np.isin(c, (45, 48)) and (not np.isfinite(v) or v >= 1000): v = 600
    if not np.isfinite(v) or v >= 10000: return '10+'
    return f'{max(v, 100) / 1000:.1f}'.replace('.', ',')  # km, as the legend says


def draw(job):
    lang, i = job; C = CTX; fr = C['frames'][lang][i]; X = TX[lang]
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI); fig.patch.set_facecolor('white')
    ax = fig.add_axes(MAP); ax.set_xlim(*EXT); ax.set_ylim(LA0, LA1); ax.set_aspect(1 / COSL); ax.axis('off')
    for r in C['sea']: ax.fill(r[:, 0], r[:, 1], fc=PV.SEA, ec='#b9cfe3', lw=0.6, zorder=0.5)
    if C['relief'] is not None: ax.imshow(C['relief'], extent=(EXT[0], EXT[1], LA0, LA1), origin='upper', interpolation='bilinear', aspect='auto', zorder=0.6)
    a_in = fr.get('fade', 1.0); F = fr['F']
    img = np.zeros(F.shape + (4,), np.float32); img[..., :3] = np.clip(0.97 - 0.32 * F[..., None] * np.array([1.0, 0.95, 0.88]), 0, 1); img[..., 3] = np.clip(F * 1.1, 0, 0.88) * a_in
    ax.imshow(img, extent=(C['lon'][0], C['lon'][-1], C['lat'][0], C['lat'][-1]), origin='lower', interpolation='bicubic', aspect='auto', zorder=2)
    if F.max() >= 0.55: ax.contour(C['lon'], C['lat'], F, levels=[0.55], colors=['#6c7a8a'], linewidths=1.0, alpha=0.6 * a_in, zorder=2.1)
    ax.set_xlim(*EXT); ax.set_ylim(LA0, LA1); ax.set_aspect(1 / COSL)
    for rings, col, lw, z in C['borders']: ax.add_collection(LineCollection(rings, colors=col, linewidths=lw, zorder=z, capstyle='round', joinstyle='round'))
    L = 0 if lang == 'ru' else 1; Lk = 'ru' if lang == 'ru' else 'uz'
    for (lo, la, nm) in fr['dist']:  # the districts in fog (spread out, away from the towns): a grey dot and the name
        ax.plot(lo, la, 'o', ms=6, mfc='#56657a', mec='white', mew=1.2, zorder=7)
        ax.annotate(nm, (lo, la), xytext=(6, -4), textcoords='offset pixels', ha='left', va='top', fontsize=10.5, color='#34404e', zorder=7.2, path_effects=[pe.withStroke(linewidth=2.6, foreground='white')])
    items = [(tw[3], tw[2], f"{tw[L]}" + (f" · {X['fog']}" if f_ >= 0.55 else ''), 16 if tw[0] == 'Ташкент' else 13, tw[0] == 'Ташкент', PV.OFF.get(tw[0], (24, 0, 'left', 'center'))) for tw, (vt, f_) in zip(PV.TOWNS, fr['towns'])]
    offs = PV.place(ax, items, fig)
    for tw, (vt, f_), (dx, dy, ha, va), it in zip(PV.TOWNS, fr['towns'], offs, items):
        main = it[4]; col = FOGC[2] if f_ >= 0.85 else FOGC[1] if f_ >= 0.55 else '#7fbf7a' if f_ < 0.2 else '#c9c46a'
        ax.annotate(vt, (tw[3], tw[2]), ha='center', va='center', fontsize=12.5 if main else 10, fontweight='bold', color='white' if f_ >= 0.55 or f_ < 0.2 else PV.INK, zorder=8.5,
                    bbox=dict(boxstyle='circle,pad=0.4' if main else 'circle,pad=0.34', fc=col, ec=PV.ORANGE if main else 'white', lw=3 if main else 2))
        ax.annotate(it[2], (tw[3], tw[2]), xytext=(dx, dy), textcoords='offset pixels', ha=ha, va=va, fontsize=it[3], fontweight='bold' if main else 'semibold', color='#1f2933', zorder=9,
                    bbox=dict(boxstyle='round,pad=0.3,rounding_size=0.7', fc='#f1f3f5', ec=PV.ORANGE if main else 'none', lw=2.0 if main else 0, alpha=0.78))
    ax.text(0.005, 0.01, X['src'], transform=ax.transAxes, ha='left', va='bottom', fontsize=10, color=PV.FAINT, zorder=9)
    PV.brand(ax, 0.995, 0.01, 'Bot - @ObHavo_ECMWF_bot · Kanal - @osmon_obhavo', transform=ax.transAxes, ha='right', va='bottom', fontsize=11, color=PV.FAINT, zorder=9)
    fig.patches.append(Rectangle((0, 0.906), 1, 0.094, transform=fig.transFigure, fc=PV.NAVY, ec='none', zorder=-1))
    PV.mark(fig, 0.016 + 22 / 1920, 0.953, 44, ink='#ffffff', rings=(20, 32, 44))  # the channel's logo
    fig.text(0.016 + 50 / 1920, 0.953, 'osmon', fontsize=22, fontweight='bold', color='#ffffff', va='center')
    fig.text(0.12, 0.953, X['title'], fontsize=22, fontweight='bold', color='white', va='center')
    fig.text(0.984, 0.968, fr['when'], fontsize=24, fontweight='bold', color='#ffd29c', ha='right', va='center')
    fig.text(0.984, 0.928, X['tz'], fontsize=14, color='#a9bdd6', ha='right', va='center')
    fig.patches.append(Rectangle((0, 0.903), 1, 0.004, transform=fig.transFigure, fc='#2c3e57', ec='none', zorder=0))
    fig.patches.append(Rectangle((0, 0.903), fr['prog'], 0.004, transform=fig.transFigure, fc=PV.ORANGE, ec='none', zorder=0.1))
    xb = 0.016; fig.text(xb, 0.183, X['vis'] + ', ' + X['km'] + ':', fontsize=12.5, fontweight='bold', color=PV.INK, va='center'); xb += 0.09
    for col, nm in zip(FOGC, X['leg']):
        fig.patches.append(FancyBboxPatch((xb, 0.171), 0.024, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc=col, ec='#9aa5b1', lw=0.6))
        fig.text(xb + 0.029, 0.183, nm, fontsize=11.5, color=PV.MUTED, va='center'); xb += 0.04 + 0.0062 * len(nm)
    fig.text(0.984, 0.183, X['nofog'] if fr['n'] == 0 else f"{fr['n']} " + ('районов в тумане' if lang == 'ru' else 'tumanda tuman'), fontsize=13, fontweight='bold', color=PV.INK, ha='right', va='center')
    fig.text(0.016, 0.152, X['chart'], fontsize=12, fontweight='bold', color=PV.INK, va='center')
    bx = fig.add_axes([0.035, 0.035, 0.93, 0.1]); bx.set_facecolor('none')
    nn = C['count']; xs = np.arange(len(nn)); top = max(max(nn), 5)
    bx.bar(xs, np.maximum(nn, top * 0.02), width=0.78, color=[FOGC[2] if v >= 20 else FOGC[1] if v > 0 else '#e4e9ee' for v in nn], zorder=2)
    s = fr['s']; bx.add_patch(Rectangle((s - 0.5, 0), 1, top * 1.3, fill=False, ec=PV.ORANGE, lw=2, zorder=5))
    bx.annotate(str(nn[s]), (s, nn[s]), xytext=(0, 5), textcoords='offset points', ha='center', fontsize=13, fontweight='bold', color=PV.INK, zorder=8, path_effects=[pe.withStroke(linewidth=3, foreground='white')])
    bx.set_ylim(0, top * 1.35); bx.set_xlim(-0.6, len(nn) - 0.4); bx.set_yticks([]); bx.tick_params(length=0)
    bx.set_xticks(xs[::2]); bx.set_xticklabels(C['hl'][::2], fontsize=10.5, color=PV.MUTED)
    for sp in bx.spines.values(): sp.set_visible(False)
    if fr.get('card') == 'intro':
        a = fr['a']; fig.patches.append(Rectangle((0, 0.205), 1, 0.701, transform=fig.transFigure, fc='white', alpha=0.86 * a, ec='none', zorder=30))
        fig.text(0.5, 0.64, 'osmon', fontsize=44, fontweight='bold', color=PV.NAVY, ha='center', va='center', alpha=a, zorder=31)
        if a > 0.5: PV.mark(fig, 0.5, 0.78, 105, ink=PV.NAVY, rings=(20, 32, 44), zorder=31)
        fig.text(0.5, 0.56, X['intro1'], fontsize=40, fontweight='bold', color=PV.INK, ha='center', va='center', alpha=a, zorder=31)
        fig.text(0.5, 0.49, X['intro2'], fontsize=26, color=PV.MUTED, ha='center', va='center', alpha=a, zorder=31)
    if fr.get('card') == 'end':
        fig.patches.append(Rectangle((0, 0.205), 1, 0.701, transform=fig.transFigure, fc='white', alpha=0.9, ec='none', zorder=30))
        fig.text(0.5, 0.62, 'osmon', fontsize=44, fontweight='bold', color=PV.NAVY, ha='center', va='center', zorder=31)
        PV.mark(fig, 0.5, 0.76, 105, ink=PV.NAVY, rings=(20, 32, 44), zorder=31)
        fig.text(0.5, 0.54, X['end1'], fontsize=30, fontweight='bold', color=PV.INK, ha='center', va='center', zorder=31)
        fig.text(0.5, 0.47, X['end2'], fontsize=26, color=PV.MUTED, ha='center', va='center', zorder=31)
    fig.savefig(pathlib.Path(C['dir'][lang]) / f'{i:04d}.png', dpi=DPI, facecolor='white'); plt.close(fig)


def encode(lang, out):
    fd = pathlib.Path(CTX['dir'][lang]); F = CTX['frames'][lang]
    (fd / 'list.txt').write_text(''.join(f"file '{i:04d}.png'\nduration {fr['d']}\n" for i, fr in enumerate(F)) + f"file '{len(F) - 1:04d}.png'\n")
    dst = pathlib.Path(out) / f'fog24_{lang}.mp4'; tmp = dst.with_name('.' + dst.name + '.part.mp4')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(fd / 'list.txt'), '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-map', '0:v', '-map', '1:a',
                    '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-crf', '20', '-maxrate', '2500k', '-bufsize', '5000k', '-preset', 'slow', '-tune', 'animation',
                    '-c:a', 'aac', '-b:a', '48k', '-shortest', '-movflags', '+faststart', str(tmp)], check=True)
    tmp.replace(dst); shutil.rmtree(fd); return f'{dst} {dst.stat().st_size // 1024} KB'


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); langs = (sys.argv[2] if len(sys.argv) > 2 else 'ru,uz').split(',')
    D = get_data(sys.argv[3] if len(sys.argv) > 3 else None); np.savez_compressed(out / 'fog_raw.npz', **D)
    times = [dt.datetime.fromisoformat(str(t)) for t in D['times']]; now = dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    k0 = next((k for k, t in enumerate(times) if t >= now), 0); idx = list(range(k0, min(k0 + 25, len(times))))
    loc = lambda t: t + dt.timedelta(hours=5)
    # the list for the bot: the districts with fog in the window, from when to when, the lowest visibility
    A2 = GA['adm2']; regs = {}
    for j, d in enumerate(A2):
        hrs = [k for k in idx if fogness(D['dv'][j, k], D['dc'][j, k]) >= 0.55]
        if not hrs: continue
        vv = [float(D['dv'][j, k]) for k in hrs if np.isfinite(D['dv'][j, k])]
        regs.setdefault(d['p'], []).append(dict(ru=d['name']['ru'], uz=d['name']['uz'], frm=loc(times[hrs[0]]).strftime('%Y-%m-%dT%H:%M'), to=loc(times[hrs[-1]]).strftime('%Y-%m-%dT%H:%M'),
                                                vis=min(vv) if vv else None, lat=d['c'][1], lon=d['c'][0]))
    R = [dict(ru=GA['adm1'][p]['name']['ru'], uz=GA['adm1'][p]['name']['uz'], districts=sorted(v, key=lambda x: x['frm'])) for p, v in sorted(regs.items())]
    json.dump(dict(made=dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), video=True, regions=R), open(out / 'fog.json', 'w'), ensure_ascii=False)
    print('fog districts', sum(len(r['districts']) for r in R), flush=True)
    UP = 6; lat = np.linspace(LATS[0], LATS[-1], len(LATS) * UP); lon = np.linspace(LONS[0], LONS[-1], len(LONS) * UP)
    # the fog field: the grid, sharpened by the 199 district centres (fog is local: each district a soft spot ~25 km)
    LL, LA_ = np.meshgrid(lon, lat); dl = np.array([d['c'][0] for d in GA['adm2']]); da = np.array([d['c'][1] for d in GA['adm2']])
    ix = np.clip(np.searchsorted(lon, dl), 0, len(lon) - 1); iy = np.clip(np.searchsorted(lat, da), 0, len(lat) - 1)
    def field(k):
        g = zoom(fogness(D['gv'][..., k], D['gc'][..., k]), UP, order=1); spot = np.zeros_like(g)
        np.maximum.at(spot, (iy, ix), fogness(D['dv'][:, k], D['dc'][:, k]))
        spot = gaussian_filter(spot, 2.2); spot = spot / max(spot.max(), 1e-6) * fogness(D['dv'][:, k], D['dc'][:, k]).max() if spot.max() > 0 else spot
        return np.clip(np.maximum(gaussian_filter(g, 2.5), spot), 0, 1)
    Fg = {k: field(k) for k in idx}
    count = [int(sum(fogness(D['dv'][j, k], D['dc'][j, k]) >= 0.55 for j in range(len(A2)))) for k in idx]
    WAT = json.load(open(ROOT / 'prob' / 'geo_water.json')); G = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']
    CTX.update(sea=[np.asarray(r) for r in WAT['ocean']] + [np.asarray(l_['r']) for l_ in WAT['lakes']], lat=lat, lon=lon, relief=PV.relief_layer(EXT[0], EXT[1], LA0, LA1), count=count,
               borders=[([np.asarray(r) for k, c in G.items() if k != 'UZ' for r in c['rings']], '#a3acb6', 1.0, 3), ([np.asarray(r) for a in GA['adm1'] for r in a['r']], '#b7c0ca', 0.8, 3.05),
                        ([np.asarray(r) for r in G['UZ']['rings']], '#1c2633', 2.6, 3.3)], hl=[f"{loc(times[k]):%H}:00" for k in idx], frames={}, dir={})
    N = 4
    for lang in langs:
        X = TX[lang]; Lk = 'ru' if lang == 'ru' else 'uz'; F = []
        for n_, k in enumerate(idx):
            j2 = idx[min(n_ + 1, len(idx) - 1)]
            dist = []
            for j in np.argsort([-fogness(D['dv'][j, k], D['dc'][j, k]) for j in range(len(A2))]):
                if fogness(D['dv'][j, k], D['dc'][j, k]) < 0.55 or len(dist) >= 9: break
                lo_, la_ = A2[j]['c']
                if any(math.hypot((lo_ - x) * COSL, la_ - y) < 0.55 for x, y, _ in dist) or any(math.hypot((lo_ - t[3]) * COSL, la_ - t[2]) < 0.45 for t in PV.TOWNS): continue
                dist.append((lo_, la_, A2[j]['name'][Lk].replace(' р-н', '').replace(' tumani', '').replace('г. ', '')))
            towns = [(vis_text(D['tv'][t, k], D['tc'][t, k], X), float(fogness(D['tv'][t, k], D['tc'][t, k]))) for t in range(len(PV.TOWNS))]
            for q in range(N if n_ < len(idx) - 1 else 1):
                a = q / N; t = loc(times[k])
                F.append(dict(F=(1 - a) * Fg[k] + a * Fg[j2], dist=dist, towns=towns, n=count[n_], s=n_, when=f"{X['wd'][t.weekday()]} {t:%d.%m} · {t:%H}:00", prog=(n_ + a) / max(1, len(idx) - 1), d=0.75 / N))
        F[-1] = dict(F[-1], d=1.5)
        intro = [dict(F[0], card='intro', a=1.0, fade=0.0, d=1.4)] + [dict(F[0], card='intro', a=float(a_), fade=float(1 - a_), d=0.07) for a_ in np.linspace(1, 0, 9)[1:]]
        CTX['frames'][lang] = intro + F + [dict(F[-1], card='end', d=3.0)]; CTX['dir'][lang] = tempfile.mkdtemp()
    jobs = [(l, i) for l in langs for i in range(len(CTX['frames'][l]))]
    with mp.get_context('fork').Pool(max(1, os.cpu_count() or 1)) as pool:
        list(pool.imap_unordered(draw, jobs, chunksize=4))
        for l in langs: print(pool.apply(encode, (l, str(out))), flush=True)


if __name__ == '__main__':
    main()
