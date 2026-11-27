"""Air quality over Uzbekistan for the next 24 hours, hour by hour, as a Full HD video in the Osmon look (the 15-day videos' map).
Data: Copernicus Atmosphere Monitoring Service (CAMS) global forecast (ECMWF), through the Open-Meteo air-quality API: US AQI,
PM2.5, PM10 and dust on a 0.4° grid and at the twelve towns. CAMS runs twice a day, so the grid is fetched at most every 6 hours
(kept in out/air.npz) and every hourly run only moves the 24-hour window.
Usage: python tools/air_video.py out ru,uz [previous_air.npz]  →  out/air24_{lang}.mp4, out/air.npz, out/meta.json"""
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
LATS = np.round(np.arange(35.25, 47.76, 0.75), 2); LONS = np.round(np.arange(50.25, 80.26, 0.75), 2)  # 0.75°: ~480 points, fetched in ~2 minutes (CAMS itself is 0.4°)
API = 'https://air-quality-api.open-meteo.com/v1/air-quality'
VARS = ['us_aqi', 'pm2_5', 'pm10', 'dust']
# the US AQI colours, softened: good, moderate, unhealthy for sensitive groups, unhealthy, very unhealthy, hazardous
AST = np.array([0, 35, 50, 75, 100, 150, 200, 300, 400], float)
ACL = np.array([matplotlib.colors.to_rgb(c) for c in ['#38b26a', '#7fc65a', '#c8d84a', '#f3d23f', '#f5a63a', '#ec6634', '#d6303c', '#8e3b9c', '#6b1532']])
CATS = [(0, 50, '#5cbf63'), (51, 100, '#f2d23f'), (101, 150, '#f5933a'), (151, 200, '#e0463b'), (201, 300, '#8e3b9c'), (301, 500, '#6b1532')]
TX = {'ru': dict(title='Качество воздуха · 24 часа', tz='по Ташкенту', src='CAMS (Copernicus, ECMWF) · индекс US AQI', cats=['хорошо', 'умеренно', 'вредно чувствит.', 'вредно', 'очень вредно', 'опасно'],
                 leg='индекс качества воздуха (AQI)', chart='{n}: индекс качества воздуха по часам', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], dust='пыль',
                 intro1='Качество воздуха', intro2='на 24 часа по всему Узбекистану', end1='Воздух в вашем городе', end2='в Telegram-боте @ObHavo_ECMWF_bot'),
      'uz': dict(title='Havo sifati · 24 soat', tz='Toshkent vaqti', src='CAMS (Copernicus, ECMWF) · US AQI indeksi', cats=['yaxshi', 'o‘rtacha', 'sezgirlarga zararli', 'zararli', 'juda zararli', 'xavfli'],
                 leg='havo sifati indeksi (AQI)', chart='{n}: soatma-soat havo sifati indeksi', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'], dust='chang',
                 intro1='Havo sifati', intro2='butun O‘zbekiston bo‘yicha 24 soatga', end1='Shahringizdagi havo', end2='Telegram-botda: @ObHavo_ECMWF_bot')}
CTX = {}


def acol(v):
    return np.stack([np.interp(np.nan_to_num(v, nan=0), AST, ACL[:, k]) for k in range(3)], -1)


def cat(v):
    return next((k for k, (a, b, _) in enumerate(CATS) if v <= b), len(CATS) - 1)


def fetch_points(lats, lons, hours=72):
    """The CAMS forecast at many points, ~100 a request (the API's rate limit respected); → {var: (points, hours)}, times."""
    out = {v: [] for v in VARS}; times = None
    B = 50
    for i in range(0, len(lats), B):
        r = None
        for tr in range(8):  # a slow answer or the rate limit: wait and ask again
            try:
                r = requests.get(API, params=dict(latitude=','.join(f'{x:.2f}' for x in lats[i:i + B]), longitude=','.join(f'{x:.2f}' for x in lons[i:i + B]),
                                                  hourly=','.join(VARS), forecast_hours=hours, past_hours=1, timezone='GMT', domains='cams_global'), timeout=240)
                if r.status_code == 200: break
                print('air api', r.status_code, r.text[:120], flush=True)
            except Exception as e: print('air api', e, flush=True)
            time.sleep(65 if r is not None and r.status_code == 429 else 20)
        if r is None or r.status_code != 200: raise RuntimeError('air api failed')
        J = r.json(); J = J if isinstance(J, list) else [J]
        for j in J:
            times = times or j['hourly']['time']
            for v in VARS: out[v].append([np.nan if x is None else x for x in j['hourly'][v]])
        time.sleep(3)
    return {v: np.array(a, np.float32) for v, a in out.items()}, times


def get_data(prev):
    if prev and pathlib.Path(prev).exists():
        z = np.load(prev, allow_pickle=True)
        same = z['g_us_aqi'].shape[:2] == (len(LATS), len(LONS))  # the grid of the last fetch is the same as now
        if same and time.time() - float(z['fetched']) < 6 * 3600: print('grid from the last fetch', flush=True); return {k: z[k] for k in z.files}
    gl, go = np.meshgrid(LATS, LONS, indexing='ij'); t0 = time.time()
    G, times = fetch_points(gl.ravel(), go.ravel())
    T, _ = fetch_points(np.array([t[2] for t in PV.TOWNS]), np.array([t[3] for t in PV.TOWNS]))
    D = {f'g_{v}': G[v].reshape(len(LATS), len(LONS), -1) for v in VARS}
    D.update({f't_{v}': T[v] for v in VARS}); D['times'] = np.array(times); D['fetched'] = np.array(time.time())
    print('fetched', len(gl.ravel()), 'points in', round(time.time() - t0), 's', flush=True)
    return D


def draw(job):
    lang, i = job; C = CTX; fr = C['frames'][lang][i]; X = TX[lang]
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI); fig.patch.set_facecolor('white')
    ax = fig.add_axes(MAP); ax.set_xlim(*EXT); ax.set_ylim(LA0, LA1); ax.set_aspect(1 / COSL); ax.axis('off')
    for r in C['sea']: ax.fill(r[:, 0], r[:, 1], fc=PV.SEA, ec='#b9cfe3', lw=0.6, zorder=0.5)
    if C['relief'] is not None: ax.imshow(C['relief'], extent=(EXT[0], EXT[1], LA0, LA1), origin='upper', interpolation='bilinear', aspect='auto', zorder=0.6)
    a_in = fr.get('fade', 1.0)
    img = np.dstack([acol(fr['A']), np.full(fr['A'].shape, 0.72 * a_in)]).astype(np.float32)
    ax.imshow(img, extent=(C['lon'][0], C['lon'][-1], C['lat'][0], C['lat'][-1]), origin='lower', interpolation='bicubic', aspect='auto', zorder=2)
    cs = ax.contour(C['lon'], C['lat'], fr['A'], levels=[50, 100, 150, 200, 300], colors=['#2b3440'], linewidths=0.6, alpha=0.35 * a_in, zorder=2.1)
    if fr['Du'].max() >= 150:  # a lot of dust: fine dots, like on a weather chart
        with matplotlib.rc_context({'hatch.color': '#8a6d3b', 'hatch.linewidth': 0.8}):
            ax.contourf(C['lon'], C['lat'], fr['Du'], levels=[150, 1e5], colors='none', hatches=['....'], zorder=2.2)
    ax.set_xlim(*EXT); ax.set_ylim(LA0, LA1); ax.set_aspect(1 / COSL)
    for rings, col, lw, z in C['borders']: ax.add_collection(LineCollection(rings, colors=col, linewidths=lw, zorder=z, capstyle='round', joinstyle='round'))
    L = 0 if lang == 'ru' else 1
    items = [(tw[3], tw[2], f"{tw[L]}  PM2.5 {pm:.0f}", 17 if tw[0] == 'Ташкент' else 13.5, tw[0] == 'Ташкент', PV.OFF.get(tw[0], (24, 0, 'left', 'center'))) for tw, (aq, pm, du) in zip(PV.TOWNS, fr['towns'])]
    offs = PV.place(ax, items, fig)
    for tw, (aq, pm, du), (dx, dy, ha, va), it in zip(PV.TOWNS, fr['towns'], offs, items):
        main = it[4]
        ax.annotate(f'{aq:.0f}', (tw[3], tw[2]), ha='center', va='center', fontsize=14 if main else 11, fontweight='bold', color='white' if cat(aq) != 1 else PV.INK, zorder=8.5,
                    bbox=dict(boxstyle='circle,pad=0.42' if main else 'circle,pad=0.36', fc=CATS[cat(aq)][2], ec=PV.ORANGE if main else 'white', lw=3 if main else 2))
        ax.annotate(it[2], (tw[3], tw[2]), xytext=(dx, dy), textcoords='offset pixels', ha=ha, va=va, fontsize=it[3], fontweight='bold' if main else 'semibold', color='#1f2933', zorder=9,
                    bbox=dict(boxstyle='round,pad=0.3,rounding_size=0.7', fc='#f1f3f5', ec=PV.ORANGE if main else 'none', lw=2.0 if main else 0, alpha=0.75))
    ax.text(0.005, 0.01, X['src'], transform=ax.transAxes, ha='left', va='bottom', fontsize=10, color=PV.FAINT, zorder=9)
    PV.brand(ax, 0.995, 0.01, 'Bot - @ObHavo_ECMWF_bot · Kanal - @osmon_obhavo', transform=ax.transAxes, ha='right', va='bottom', fontsize=11, color=PV.FAINT, zorder=9)
    # header
    fig.patches.append(Rectangle((0, 0.906), 1, 0.094, transform=fig.transFigure, fc=PV.NAVY, ec='none', zorder=-1))
    PV.mark(fig, 0.016 + 22 / 1920, 0.953, 44, ink='#ffffff', rings=(20, 32, 44))  # the channel's logo
    fig.text(0.016 + 50 / 1920, 0.953, 'osmon', fontsize=22, fontweight='bold', color='#ffffff', va='center')
    fig.text(0.12, 0.953, X['title'], fontsize=22, fontweight='bold', color='white', va='center')
    fig.text(0.984, 0.968, fr['when'], fontsize=24, fontweight='bold', color='#ffd29c', ha='right', va='center')
    fig.text(0.984, 0.928, X['tz'], fontsize=14, color='#a9bdd6', ha='right', va='center')
    fig.patches.append(Rectangle((0, 0.903), 1, 0.004, transform=fig.transFigure, fc='#2c3e57', ec='none', zorder=0))
    fig.patches.append(Rectangle((0, 0.903), fr['prog'], 0.004, transform=fig.transFigure, fc=PV.ORANGE, ec='none', zorder=0.1))
    # legend: the categories as coloured chips
    fig.text(0.016, 0.183, X['leg'] + ':', fontsize=13, fontweight='bold', color=PV.INK, va='center'); xb = 0.016 + 0.0068 * len(X['leg']) + 0.016
    for (a, b, col), nm in zip(CATS, X['cats']):
        fig.patches.append(FancyBboxPatch((xb, 0.171), 0.022, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc=col, ec='none'))
        fig.text(xb + 0.026, 0.183, f'{nm} {a}–{b}' if b < 500 else f'{nm} {a}+', fontsize=10.5, color=PV.MUTED, va='center'); xb += 0.032 + 0.0052 * (len(nm) + 8)
    with matplotlib.rc_context({'hatch.color': '#8a6d3b', 'hatch.linewidth': 0.8}):
        fig.patches.append(FancyBboxPatch((xb, 0.171), 0.022, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc='#f3ead8', ec='#cfc5b4', hatch='....', lw=0.6))
    fig.text(xb + 0.026, 0.183, X['dust'], fontsize=11, color=PV.MUTED, va='center')
    # the chart: Tashkent's index hour by hour
    fig.text(0.016, 0.152, X['chart'].format(n=PV.TOWNS[0][L]), fontsize=12, fontweight='bold', color=PV.INK, va='center')
    bx = fig.add_axes([0.035, 0.035, 0.93, 0.1]); bx.set_facecolor('none')
    Ht = C['tash']; xs = np.arange(len(Ht))
    bx.bar(xs, np.maximum(Ht, 2), width=0.78, color=[CATS[cat(v)][2] for v in Ht], zorder=2)
    s = fr['s']; bx.add_patch(Rectangle((s - 0.5, 0), 1, max(Ht.max() * 1.25, 60), fill=False, ec=PV.ORANGE, lw=2, zorder=5))
    bx.annotate(f'{fr["towns"][0][0]:.0f}', (s, Ht[s]), xytext=(0, 5), textcoords='offset points', ha='center', fontsize=13, fontweight='bold', color=PV.INK, zorder=8, path_effects=[pe.withStroke(linewidth=3, foreground='white')])
    bx.set_ylim(0, max(Ht.max() * 1.25, 60)); bx.set_xlim(-0.6, len(Ht) - 0.4)
    bx.set_xticks(xs[::2]); bx.set_xticklabels(C['hl'][::2], fontsize=10.5, color=PV.MUTED); bx.tick_params(length=0)
    bx.set_yticks([0, 50, 100, 150][:1 + int(bx.get_ylim()[1] // 50)]); bx.set_yticklabels([str(v) for v in [0, 50, 100, 150]][:1 + int(bx.get_ylim()[1] // 50)], fontsize=10, color=PV.FAINT)
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
    dst = pathlib.Path(out) / f'air24_{lang}.mp4'; tmp = dst.with_name('.' + dst.name + '.part.mp4')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(fd / 'list.txt'), '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-map', '0:v', '-map', '1:a',
                    '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-crf', '20', '-maxrate', '2500k', '-bufsize', '5000k', '-preset', 'slow', '-tune', 'animation',
                    '-c:a', 'aac', '-b:a', '48k', '-shortest', '-movflags', '+faststart', str(tmp)], check=True)
    tmp.replace(dst); shutil.rmtree(fd); return f'{dst} {dst.stat().st_size // 1024} KB'


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); langs = (sys.argv[2] if len(sys.argv) > 2 else 'ru,uz').split(',')
    D = get_data(sys.argv[3] if len(sys.argv) > 3 else None)
    np.savez_compressed(out / 'air.npz', **D)
    times = [dt.datetime.fromisoformat(str(t)) for t in D['times']]; now = dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    k0 = next((k for k, t in enumerate(times) if t >= now), 0); idx = list(range(k0, min(k0 + 25, len(times))))
    UP = 6; lat = np.linspace(LATS[0], LATS[-1], len(LATS) * UP); lon = np.linspace(LONS[0], LONS[-1], len(LONS) * UP)
    up = lambda a: gaussian_filter(zoom(np.nan_to_num(a, nan=np.nanmean(a) if np.isfinite(a).any() else 0), UP, order=3), 2.0)
    Ag = {k: np.clip(up(D['g_us_aqi'][..., k]), 0, 500) for k in idx}; Dg = {k: np.clip(up(D['g_dust'][..., k]), 0, None) for k in idx}
    tw = lambda v, k: [float(np.nan_to_num(x)) for x in D[f't_{v}'][:, k]]
    WAT = json.load(open(ROOT / 'prob' / 'geo_water.json')); G = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']; GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']
    borders = [([np.asarray(r) for k, c in G.items() if k != 'UZ' for r in c['rings']], '#a3acb6', 1.0, 3), ([np.asarray(r) for a in GA['adm1'] for r in a['r']], '#b7c0ca', 0.8, 3.05),
               ([np.asarray(r) for r in G['UZ']['rings']], '#1c2633', 2.6, 3.3)]
    loc = lambda t: t + dt.timedelta(hours=5)
    CTX.update(sea=[np.asarray(r) for r in WAT['ocean']] + [np.asarray(l_['r']) for l_ in WAT['lakes']], borders=borders, lat=lat, lon=lon,
               relief=PV.relief_layer(EXT[0], EXT[1], LA0, LA1), tash=np.array([float(np.nan_to_num(D['t_us_aqi'][0, k])) for k in idx]),
               hl=[f"{loc(times[k]):%H}:00" for k in idx], frames={}, dir={})
    N = 4  # in-between frames per hour
    for lang in langs:
        X = TX[lang]; F = []
        for n_, k in enumerate(idx):
            j = idx[min(n_ + 1, len(idx) - 1)]
            for q in range(N if n_ < len(idx) - 1 else 1):
                a = q / N; A = (1 - a) * Ag[k] + a * Ag[j]; Du = (1 - a) * Dg[k] + a * Dg[j]
                towns = [((1 - a) * x + a * y, (1 - a) * p + a * p2, d) for x, y, p, p2, d in zip(tw('us_aqi', k), tw('us_aqi', j), tw('pm2_5', k), tw('pm2_5', j), tw('dust', k))]
                t = loc(times[k])
                F.append(dict(A=A, Du=Du, towns=towns, s=n_, when=f"{X['wd'][t.weekday()]} {t:%d.%m} · {t:%H}:00", prog=(n_ + a) / max(1, len(idx) - 1), d=0.75 / N))
        F[-1] = dict(F[-1], d=1.5)
        intro = [dict(F[0], card='intro', a=1.0, fade=0.0, d=1.4)] + [dict(F[0], card='intro', a=float(a_), fade=float(1 - a_), d=0.07) for a_ in np.linspace(1, 0, 9)[1:]]
        CTX['frames'][lang] = intro + F + [dict(F[-1], card='end', d=3.0)]; CTX['dir'][lang] = tempfile.mkdtemp()
    jobs = [(l, i) for l in langs for i in range(len(CTX['frames'][l]))]
    with mp.get_context('fork').Pool(max(1, os.cpu_count() or 1)) as pool:
        list(pool.imap_unordered(draw, jobs, chunksize=4))
        for l in langs: print(pool.apply(encode, (l, str(out))), flush=True)
    json.dump(dict(made=dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), first=str(times[idx[0]]), last=str(times[idx[-1]]), fetched=float(D['fetched'])), open(out / 'meta.json', 'w'))


if __name__ == '__main__':
    main()
