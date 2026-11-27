"""Dangerous weather for 15 days over Uzbekistan, day by day, as a Full HD video in the Osmon look.
Data: ECMWF ENS ensemble probabilities (open data, CC BY 4.0) for each 24-hour window — gusts over 15 and 25 m/s, precipitation
over 5, 10 and 20 mm; with the temperature (2 m, min and max of the day) and the convective energy (CAPE) of wx.npz (GEFS mean)
for frost below −10°, heat over +35°, heavy snow (precipitation over 10 mm in the cold) and thunderstorms.
Usage: python tools/risk_video.py DATA_DIR out ru,uz  (DATA_DIR: prob.npz and wx.npz of the last site run)  →  out/risk_{lang}.mp4, out/meta.json"""
import sys, os, json, math, pathlib, shutil, subprocess, tempfile, datetime as dt, multiprocessing as mp, concurrent.futures as cf
import numpy as np, requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import FancyBboxPatch, Rectangle
import matplotlib.patheffects as pe
from scipy.ndimage import zoom, gaussian_filter, maximum_filter

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'prob'))
import prob15_video as PV

W, H, DPI = PV.W, PV.H, PV.DPI
MAP = PV.MAP; LA0, LA1 = PV.LAT0, PV.LAT1; LC = 64.8
COSL = math.cos(math.radians((LA0 + LA1) / 2)); SPAN = (LA1 - LA0) / COSL * (MAP[2] * W) / (MAP[3] * H); EXT = (LC - SPAN / 2, LC + SPAN / 2)
GRID = dict(lon0=44.0, lat0=48.5, d=0.25, W=161, H=55)  # 44–84° E, 35–48.5° N
ECM = 'https://storage.googleapis.com/ecmwf-open-data'
PARAMS = ['10fgg15', '10fgg25', 'tpg5', 'tpg10', 'tpg20']
# the risks: key, colour, threshold of the probability shown (%)
RISK = [('rain', '#1f6fd1'), ('snow', '#8b4fd6'), ('wind', '#f08a24'), ('storm', '#d93a3a'), ('frost', '#2bb3d9'), ('heat', '#e0302a')]
TX = {'ru': dict(title='Опасная погода · 15 дней', tz='прогноз ансамбля ECMWF', src='ECMWF ENS (вероятности ансамбля) · NOAA GEFS · Bot - @ObHavo_ECMWF_bot · Kanal - @osmon_obhavo',
                 names=dict(rain='ливень >20 мм', snow='снегопад >10 мм', wind='порывы >15 м/с', storm='гроза', frost='мороз < −10°', heat='жара > +35°'),
                 short=dict(rain='ливень', snow='снегопад', wind='ветер', storm='гроза', frost='мороз', heat='жара', calm='спокойно'),
                 leg='вероятность, %', chart='{n}: самый вероятный риск дня, %', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], hur='ураганные порывы >25 м/с',
                 intro1='Опасная погода', intro2='ветер, ливни, снег, мороз, жара и грозы на 15 дней', end1='Предупреждения для вашего места', end2='в Telegram-боте @ObHavo_ECMWF_bot'),
      'uz': dict(title='Xavfli ob-havo · 15 kun', tz='ECMWF ansambl prognozi', src='ECMWF ENS (ansambl ehtimollari) · NOAA GEFS · Bot - @ObHavo_ECMWF_bot · Kanal - @osmon_obhavo',
                 names=dict(rain='jala >20 mm', snow='qor >10 mm', wind='shamol >15 m/s', storm='momaqaldiroq', frost='sovuq < −10°', heat='jazirama > +35°'),
                 short=dict(rain='jala', snow='qor', wind='shamol', storm='momaqaldiroq', frost='sovuq', heat='jazirama', calm='tinch'),
                 leg='ehtimol, %', chart='{n}: kunning eng ehtimolli xavfi, %', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'], hur='dovul >25 m/s',
                 intro1='Xavfli ob-havo', intro2='15 kunga shamol, jala, qor, sovuq, jazirama va momaqaldiroq', end1='Joyingiz uchun ogohlantirishlar', end2='Telegram-botda: @ObHavo_ECMWF_bot')}
CTX = {}


def get(url, rng=None):
    for _ in range(5):
        try:
            r = requests.get(url, headers={'Range': f'bytes={rng[0]}-{rng[1]}'} if rng else {}, timeout=120)
            if r.status_code in (200, 206): return r.content
            if r.status_code == 404: return None
        except Exception as e: print('get', url, e, flush=True)
    return None


def ep_fields(run):
    """The ensemble probabilities of each 24-hour window: {(param, start_h): field on GRID, %}."""
    import fetch as FE  # decode + regrid of prob/fetch.py
    d, h = run.strftime('%Y%m%d'), run.strftime('%H'); jobs = {}
    for step in range(24, 361, 24):
        base = f'{ECM}/{d}/{h}z/ifs/0p25/enfo/{d}{h}0000-{step}h-enfo-ep'
        idx = get(base + '.index')
        if not idx: continue
        for line in idx.decode().strip().split('\n'):
            x = json.loads(line)
            if x.get('param') not in PARAMS: continue
            a, b = (int(v) for v in str(x.get('step')).split('-')) if '-' in str(x.get('step')) else (None, None)
            if a is None or b - a != 24 or a % 24: continue
            jobs.setdefault((x['param'], a), (base + '.grib2', (x['_offset'], x['_offset'] + x['_length'] - 1)))
    print('ep windows', len(jobs), flush=True)
    def one(k):
        url, rng = jobs[k]; buf = get(url, rng)
        return k, (FE.regrid(FE.decode(buf), GRID) if buf else None)
    out = {}
    with cf.ThreadPoolExecutor(12) as ex:
        for k, f in ex.map(one, list(jobs)):
            if f is not None: out[k] = np.clip(f, 0, 100)
    return out


def wx_days(path, run, days):
    """Daily min / max temperature and the max CAPE (GEFS mean, 6-hourly) on GRID for each UTC day from the run."""
    z = np.load(path, allow_pickle=True); g = z['grid'].item(); st = [int(s) for s in z['steps']]
    lon = g['lon0'] + np.arange(g['W']) * g['d']; lat = g['lat0'] - np.arange(g['H']) * g['d']
    lo = GRID['lon0'] + np.arange(GRID['W']) * GRID['d']; la = GRID['lat0'] - np.arange(GRID['H']) * GRID['d']
    ix = np.clip(np.searchsorted(lon, lo), 0, len(lon) - 1); iy = np.clip(np.argmin(np.abs(lat[:, None] - la[None, :]), 0), 0, len(lat) - 1)
    pick = lambda a: a[np.ix_(iy, ix)]
    wrun = dt.datetime.fromisoformat(str(z['run']).replace('Z', '')[:19]) if 'run' in z.files else run
    off = int(round((run - wrun).total_seconds() / 3600))
    T, K = z['T'].astype(np.float32), (z['K'].astype(np.float32) if 'K' in z.files else None); out = []
    for k in range(days):
        hs = [i for i, s in enumerate(st) if 24 * k + off < s <= 24 * k + 24 + off]
        if not hs: out.append(None); continue
        Ts = np.stack([pick(T[i]) for i in hs]); out.append(dict(tmin=np.nanmin(Ts, 0), tmax=np.nanmax(Ts, 0), cape=np.nanmax(np.stack([pick(K[i]) for i in hs]), 0) if K is not None else None, tmean=np.nanmean(Ts, 0)))
    return out


def risks(ep, wx, k):
    """The six risks of day k as probabilities 0…100 (temperature ones: 0 or 85 — the ensemble mean crosses the line or not)."""
    z = np.zeros((GRID['H'], GRID['W']), np.float32); g = lambda p: ep.get((p, 24 * k), z)
    w = wx[k] if k < len(wx) and wx[k] is not None else None
    cold = np.clip((0.5 - w['tmean']) / 2, 0, 1) if w is not None else np.zeros_like(z)
    R = dict(rain=g('tpg20') * (1 - cold), snow=g('tpg10') * cold, wind=g('10fgg15'), hur=g('10fgg25'))
    R['storm'] = (g('tpg5') * np.clip((w['cape'] - 400) / 800, 0, 1) * (w['tmax'] > 8)) if w is not None and w['cape'] is not None else z
    R['frost'] = (np.clip((-10 - w['tmin']) / 3, 0, 1) * 85) if w is not None else z
    R['heat'] = (np.clip((w['tmax'] - 35) / 3, 0, 1) * 85) if w is not None else z
    return R


def draw(job):
    lang, i = job; C = CTX; fr = C['frames'][lang][i]; X = TX[lang]
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI); fig.patch.set_facecolor('white')
    ax = fig.add_axes(MAP); ax.set_xlim(*EXT); ax.set_ylim(LA0, LA1); ax.set_aspect(1 / COSL); ax.axis('off')
    for r in C['sea']: ax.fill(r[:, 0], r[:, 1], fc=PV.SEA, ec='#b9cfe3', lw=0.6, zorder=0.5)
    if C['relief'] is not None: ax.imshow(C['relief'], extent=(EXT[0], EXT[1], LA0, LA1), origin='upper', interpolation='bilinear', aspect='auto', zorder=0.6)
    a_in = fr.get('fade', 1.0); R = fr['R']; LO, LA = C['lon'], C['lat']
    for z_, (key, col) in enumerate(RISK):  # each risk: its colour, stronger where it is more likely (from 20 %)
        if key == 'storm': continue
        a = np.clip((R[key] - 15) / 55, 0, 1) ** 0.9 * (0.62 if key in ('frost', 'heat') else 0.72) * a_in
        if a.max() < 0.02: continue
        img = np.zeros(a.shape + (4,), np.float32); img[..., :3] = matplotlib.colors.to_rgb(col); img[..., 3] = a
        ax.imshow(img, extent=(LO[0], LO[-1], LA[0], LA[-1]), origin='lower', interpolation='bicubic', aspect='auto', zorder=2 + z_ * 0.01)
        ax.contour(LO, LA, R[key], levels=[50], colors=[col], linewidths=1.4, alpha=0.9 * a_in, zorder=2.2)
    if R['hur'].max() >= 10:  # hurricane gusts: a dark hatched area
        with matplotlib.rc_context({'hatch.color': '#8a2b10', 'hatch.linewidth': 1.0}):
            ax.contourf(LO, LA, R['hur'], levels=[10, 101], colors='none', hatches=['////'], zorder=2.3)
    ax.set_xlim(*EXT); ax.set_ylim(LA0, LA1); ax.set_aspect(1 / COSL)
    for bx_, by_ in fr['storms']: PV.bolt(ax, bx_, by_, 1400, 7.5)
    for rings, col, lw, z in C['borders']: ax.add_collection(LineCollection(rings, colors=col, linewidths=lw, zorder=z, capstyle='round', joinstyle='round'))
    L = 0 if lang == 'ru' else 1
    labs = [f"{tw[L]} · {X['short'][k_]} {p_:.0f}%" if k_ != 'calm' else f"{tw[L]} · {X['short']['calm']}" for tw, (k_, p_) in zip(PV.TOWNS, fr['towns'])]
    offs = PV.place(ax, [(tw[3], tw[2], lb, 16 if tw[0] == 'Ташкент' else 13, tw[0] == 'Ташкент', PV.OFF.get(tw[0], (24, 0, 'left', 'center'))) for tw, lb in zip(PV.TOWNS, labs)], fig)
    for tw, (k_, p_), (dx, dy, ha, va), lb in zip(PV.TOWNS, fr['towns'], offs, labs):
        main = tw[0] == 'Ташкент'; col = dict(RISK).get(k_, '#5cbf63') if p_ >= 30 else '#5cbf63'
        ax.plot(tw[3], tw[2], 'o', ms=15 if main else 11, mfc=col, mec=PV.ORANGE if main else 'white', mew=3 if main else 2, zorder=8.5)
        ax.annotate(lb, (tw[3], tw[2]), xytext=(dx, dy), textcoords='offset pixels', ha=ha, va=va, fontsize=16 if main else 13, fontweight='bold' if main else 'semibold', color='#1f2933', zorder=9,
                    bbox=dict(boxstyle='round,pad=0.3,rounding_size=0.7', fc='#f1f3f5', ec=PV.ORANGE if main else 'none', lw=2.0 if main else 0, alpha=0.78))
    PV.brand(ax, 0.005, 0.01, X['src'], transform=ax.transAxes, ha='left', va='bottom', fontsize=10, color=PV.FAINT, zorder=9)
    fig.patches.append(Rectangle((0, 0.906), 1, 0.094, transform=fig.transFigure, fc=PV.NAVY, ec='none', zorder=-1))
    fig.text(0.016, 0.953, 'OSMON', fontsize=22, fontweight='bold', color=PV.ORANGE, va='center')
    fig.text(0.093, 0.953, X['title'], fontsize=22, fontweight='bold', color='white', va='center')
    fig.text(0.984, 0.968, fr['when'], fontsize=24, fontweight='bold', color='#ffd29c', ha='right', va='center')
    fig.text(0.984, 0.928, X['tz'], fontsize=14, color='#a9bdd6', ha='right', va='center')
    fig.patches.append(Rectangle((0, 0.903), 1, 0.004, transform=fig.transFigure, fc='#2c3e57', ec='none', zorder=0))
    fig.patches.append(Rectangle((0, 0.903), fr['prog'], 0.004, transform=fig.transFigure, fc=PV.ORANGE, ec='none', zorder=0.1))
    xb = 0.016
    for key, col in RISK:  # the legend: one chip per risk
        if key == 'storm':
            lg = fig.add_axes([xb, 0.166, 0.016, 0.034]); lg.set_xlim(-1, 1); lg.set_ylim(-1.2, 1.2); lg.axis('off'); PV.bolt(lg, 0, 0, 560)
        else: fig.patches.append(FancyBboxPatch((xb, 0.171), 0.02, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc=col, ec='none', alpha=0.8))
        nm = X['names'][key]; fig.text(xb + 0.024, 0.183, nm, fontsize=11.5, color=PV.INK, va='center'); xb += 0.032 + 0.0061 * len(nm)
    with matplotlib.rc_context({'hatch.color': '#8a2b10', 'hatch.linewidth': 1.0}):
        fig.patches.append(FancyBboxPatch((xb, 0.171), 0.02, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc='#fbe6d8', ec='#8a2b10', hatch='////', lw=0.6))
    fig.text(xb + 0.024, 0.183, X['hur'], fontsize=11.5, color=PV.INK, va='center')
    fig.text(0.016, 0.152, X['chart'].format(n=PV.TOWNS[0][L]), fontsize=12, fontweight='bold', color=PV.INK, va='center')
    bx = fig.add_axes([0.035, 0.035, 0.93, 0.1]); bx.set_facecolor('none')
    tk = C['tash']; xs = np.arange(len(tk))
    bx.bar(xs, [max(p, 2) for _, p in tk], width=0.7, color=[dict(RISK).get(k, '#cfd8e3') if p >= 20 else '#dfe5ec' for k, p in tk], zorder=2)
    for x_, (k, p) in zip(xs, tk):
        if p >= 20: bx.text(x_, p + 4, f"{p:.0f}%", ha='center', va='bottom', fontsize=10.5, fontweight='bold', color=PV.INK)
        else: bx.text(x_, 6, X['short']['calm'], ha='center', va='bottom', fontsize=9.5, color=PV.FAINT, rotation=0)
    s = fr['s']; bx.add_patch(Rectangle((s - 0.48, 0), 0.96, 118, fill=False, ec=PV.ORANGE, lw=2, zorder=5))
    bx.set_ylim(0, 125); bx.set_xlim(-0.6, len(tk) - 0.4); bx.set_yticks([]); bx.tick_params(length=0)
    bx.set_xticks(xs); bx.set_xticklabels(C['dl'][lang], fontsize=10, color=PV.MUTED)
    for sp in bx.spines.values(): sp.set_visible(False)
    if fr.get('card') == 'intro':
        a = fr['a']; fig.patches.append(Rectangle((0, 0.205), 1, 0.701, transform=fig.transFigure, fc='white', alpha=0.86 * a, ec='none', zorder=30))
        fig.text(0.5, 0.64, 'OSMON', fontsize=44, fontweight='bold', color=PV.ORANGE, ha='center', va='center', alpha=a, zorder=31)
        fig.text(0.5, 0.56, X['intro1'], fontsize=40, fontweight='bold', color=PV.INK, ha='center', va='center', alpha=a, zorder=31)
        fig.text(0.5, 0.49, X['intro2'], fontsize=26, color=PV.MUTED, ha='center', va='center', alpha=a, zorder=31)
    if fr.get('card') == 'end':
        fig.patches.append(Rectangle((0, 0.205), 1, 0.701, transform=fig.transFigure, fc='white', alpha=0.9, ec='none', zorder=30))
        fig.text(0.5, 0.62, 'OSMON', fontsize=44, fontweight='bold', color=PV.ORANGE, ha='center', va='center', zorder=31)
        fig.text(0.5, 0.54, X['end1'], fontsize=30, fontweight='bold', color=PV.INK, ha='center', va='center', zorder=31)
        fig.text(0.5, 0.47, X['end2'], fontsize=26, color=PV.MUTED, ha='center', va='center', zorder=31)
    fig.savefig(pathlib.Path(C['dir'][lang]) / f'{i:04d}.png', dpi=DPI, facecolor='white'); plt.close(fig)


def encode(lang, out):
    fd = pathlib.Path(CTX['dir'][lang]); F = CTX['frames'][lang]
    (fd / 'list.txt').write_text(''.join(f"file '{i:04d}.png'\nduration {fr['d']}\n" for i, fr in enumerate(F)) + f"file '{len(F) - 1:04d}.png'\n")
    dst = pathlib.Path(out) / f'risk_{lang}.mp4'; tmp = dst.with_name('.' + dst.name + '.part.mp4')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(fd / 'list.txt'), '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-map', '0:v', '-map', '1:a',
                    '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-crf', '20', '-maxrate', '2500k', '-bufsize', '5000k', '-preset', 'slow', '-tune', 'animation',
                    '-c:a', 'aac', '-b:a', '48k', '-shortest', '-movflags', '+faststart', str(tmp)], check=True)
    tmp.replace(dst); shutil.rmtree(fd)
    try:  # thunder and wind in the sound when the main town has them (prob/sound.py)
        import sound
        lv = []
        for fr in F:
            k_, p_ = fr['towns'][0]; lv += [dict(rain=p_ / 100 if k_ in ('rain', 'storm') else 0, snow=k_ == 'snow', wind=p_ / 100 if k_ == 'wind' else 0.1, storm=1.0 if k_ == 'storm' and p_ >= 30 else 0)] * max(1, int(round(fr['d'] / 0.1)))
        wav = str(dst) + '.wav'; sound.track(lv, 0.1, wav, mode='all'); sound.mux(dst, wav)
    except Exception as e: print('sound', e, flush=True)
    return f'{dst} {dst.stat().st_size // 1024} KB'


def main():
    data, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True); langs = (sys.argv[3] if len(sys.argv) > 3 else 'ru,uz').split(',')
    z = np.load(data / 'prob.npz', allow_pickle=True); run = dt.datetime.fromisoformat(str(z['run']).replace('Z', '')[:19])
    run = run.replace(hour=0 if run.hour < 12 else 12)
    ep = ep_fields(run)
    if not ep: run -= dt.timedelta(hours=12); ep = ep_fields(run)
    nd = max([a for _, a in ep] + [0]) // 24 + 1; wx = wx_days(data / 'wx.npz', run, nd)
    UP = 4; up = lambda a: gaussian_filter(zoom(np.nan_to_num(a), UP, order=1), 2.0)
    lat = (GRID['lat0'] - np.arange(GRID['H']) * GRID['d'])[::-1]; lon = GRID['lon0'] + np.arange(GRID['W']) * GRID['d']
    lat_u = np.linspace(lat[0], lat[-1], len(lat) * UP); lon_u = np.linspace(lon[0], lon[-1], len(lon) * UP)
    at = lambda a, la, lo: float(a[np.abs(lat_u - la).argmin(), np.abs(lon_u - lo).argmin()])
    days = []
    for k in range(nd):
        R = {key: up(v[::-1]) for key, v in risks(ep, wx, k).items()}
        towns = []
        for tw in PV.TOWNS:
            best = max(((key, at(R[key], tw[2], tw[3])) for key, _ in RISK), key=lambda q: q[1]); towns.append(best if best[1] >= 20 else ('calm', best[1]))
        st = (maximum_filter(R['storm'], size=20) == R['storm']) & (R['storm'] >= 30)
        storms = [(float(lon_u[x]), float(lat_u[y])) for y, x in zip(*np.nonzero(st))][:12]
        date_ = (run + dt.timedelta(days=k)).date()
        if date_ < (dt.datetime.utcnow() + dt.timedelta(hours=5)).date(): continue  # the days already gone are left out
        days.append(dict(R=R, towns=towns, storms=storms, date=date_))
    WAT = json.load(open(ROOT / 'prob' / 'geo_water.json')); G = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']; GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']
    CTX.update(sea=[np.asarray(r) for r in WAT['ocean']] + [np.asarray(l_['r']) for l_ in WAT['lakes']], lon=lon_u, lat=lat_u, relief=PV.relief_layer(EXT[0], EXT[1], LA0, LA1),
               borders=[([np.asarray(r) for k, c in G.items() if k != 'UZ' for r in c['rings']], '#a3acb6', 1.0, 3), ([np.asarray(r) for a in GA['adm1'] for r in a['r']], '#b7c0ca', 0.8, 3.05),
                        ([np.asarray(r) for r in G['UZ']['rings']], '#1c2633', 2.6, 3.3)],
               tash=[(d['towns'][0][0], d['towns'][0][1] if d['towns'][0][0] != 'calm' else 0) for d in days],
               dl={l: [f"{TX[l]['wd'][d['date'].weekday()]}\n{d['date']:%d.%m}" for d in days] for l in TX}, frames={}, dir={})
    for lang in langs:
        X = TX[lang]; F = []
        for k, d in enumerate(days):
            F.append(dict(R=d['R'], towns=d['towns'], storms=d['storms'], s=k, when=f"{X['wd'][d['date'].weekday()]} {d['date']:%d.%m}", prog=(k + 1) / len(days), d=1.7))
            if k + 1 < len(days):
                R2 = days[k + 1]['R']
                for a in np.linspace(0, 1, 7)[1:-1]: F.append(dict(F[-1], R={key: (1 - a) * d['R'][key] + a * R2[key] for key in d['R']}, storms=[], d=0.06))
        F[-1] = dict(F[-1], d=3.0)
        intro = [dict(F[0], card='intro', a=1.0, fade=0.0, d=1.4)] + [dict(F[0], card='intro', a=float(a_), fade=float(1 - a_), d=0.07) for a_ in np.linspace(1, 0, 9)[1:]]
        CTX['frames'][lang] = intro + F + [dict(F[-1], card='end', d=3.0)]; CTX['dir'][lang] = tempfile.mkdtemp()
    jobs = [(l, i) for l in langs for i in range(len(CTX['frames'][l]))]
    with mp.get_context('fork').Pool(max(1, os.cpu_count() or 1)) as pool:
        list(pool.imap_unordered(draw, jobs, chunksize=4))
        for l in langs: print(pool.apply(encode, (l, str(out))), flush=True)
    # the bot's text: the main risks of each town and day (for «⚠️ Опасная погода»)
    json.dump(dict(made=dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), run=run.isoformat(), days=[dict(d=d['date'].isoformat(), towns={tw[0]: [k_, round(p_)] for tw, (k_, p_) in zip(PV.TOWNS, d['towns'])}) for d in days]),
              open(out / 'meta.json', 'w'), ensure_ascii=False)


if __name__ == '__main__':
    main()
