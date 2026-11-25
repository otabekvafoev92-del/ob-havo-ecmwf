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
TX = {'ru': dict(title='Вероятность осадков и температура · 15 дней', tz='по Ташкенту', day='день {i} из {n}', rain='дождь', snow='снег',
                 leg='Вероятность осадков (больше 0,2 мм) за период, %', models='Модели: ECMWF IFS и AIFS, NOAA GFS и GEFS, DWD ICON · {n} вариантов прогноза',
                 chart='Ташкент: вероятность осадков по периодам (столбики) и температура (линия)', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
                 intro1='Осадки и температура', intro2='на 15 дней по всему Узбекистану', end1='Погода в вашем районе и посёлке', end2='в Telegram-боте @ObHavo_ECMWF_bot'),
      'uz': dict(title='Yog‘ingarchilik ehtimoli va harorat · 15 kun', tz='Toshkent vaqti', day='{i}-kun / {n}', rain='yomg‘ir', snow='qor',
                 leg='Davr ichida yog‘ingarchilik (0,2 mm dan ko‘p) ehtimoli, %', models='Modellar: ECMWF IFS va AIFS, NOAA GFS va GEFS, DWD ICON · {n} ta prognoz varianti',
                 chart='Toshkent: davrlar bo‘yicha yog‘in ehtimoli (ustunlar) va harorat (chiziq)', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'],
                 intro1='Yog‘ingarchilik va harorat', intro2='butun O‘zbekiston bo‘yicha 15 kunga', end1='Tumaningiz va qishlog‘ingiz ob-havosi', end2='Telegram-botda: @ObHavo_ECMWF_bot')}
MAP = (0.0, 0.272, 1.0, 0.640)  # the map: the full width, between the header and the legend
LAT0, LAT1 = 36.95, 45.95
COSL = np.cos(np.radians(41.4))
CTX = {}


def card(fig, x, y, w, h, fc, ec='none', r=10, lw=1.0, z=20, alpha=1.0):
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle=f'round,pad=0,rounding_size={r}', transform=None, facecolor=fc, edgecolor=ec, lw=lw, zorder=z, alpha=alpha))


def qr(url):
    try:
        import qrcode
        q = qrcode.QRCode(border=2); q.add_data(url); q.make(fit=True); return np.array(q.get_matrix(), bool)
    except Exception: return None


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
    ax = fig.add_axes(MAP); x0, x1 = C['lon_ext']; ax.set_xlim(x0, x1); ax.set_ylim(LAT0, LAT1); ax.set_aspect(1 / COSL); ax.axis('off')
    for r in C['sea']: ax.fill(r[:, 0], r[:, 1], fc=SEA, ec='#b9cfe3', lw=0.6, zorder=0.5)
    P, T = fr['P'], fr['T']; a_in = fr.get('fade', 1.0)
    snow = T <= 0.5
    Pr, Ps = np.where(snow, 0, P), np.where(snow, P, 0)
    LO, LA = C['LONu'], C['LATu']
    if Pr.max() >= LEVELS[0]:
        ax.contourf(LO, LA, Pr, levels=LEVELS, cmap=ListedColormap(RAIN), norm=BoundaryNorm(LEVELS, 5), zorder=2, alpha=0.92 * a_in, antialiased=True)
        ax.contour(LO, LA, Pr, levels=LEVELS[1:-1], colors=['#ffffff'], linewidths=0.5, alpha=0.55 * a_in, zorder=2.05)
    if Ps.max() >= LEVELS[0]:
        ax.contourf(LO, LA, Ps, levels=LEVELS, cmap=ListedColormap(SNOW), norm=BoundaryNorm(LEVELS, 5), zorder=2.1, alpha=0.92 * a_in, antialiased=True)
    # 0° line: where rain turns to snow
    if np.nanmin(T) < 0 < np.nanmax(T):
        ax.contour(LO, LA, T, levels=[0], colors=['#3d7be0'], linewidths=1.3, linestyles=[(0, (5, 3))], alpha=0.75 * a_in, zorder=2.6)
    for rings, col, lw, z in C['borders']: ax.add_collection(LineCollection(rings, colors=col, linewidths=lw, zorder=z, capstyle='round', joinstyle='round'))
    # the towns: dot, name, chance and temperature
    L = 0 if lang == 'ru' else 1
    for tw, (p_, t_) in zip(TOWNS, fr['towns']):
        main = tw[0] == 'Ташкент'; dx, dy, ha, va = OFF[tw[0]]
        col = level(p_, SNOW if t_ <= 0.5 else RAIN)
        tt = f"{t_:+.0f}°".replace('+0°', '0°').replace('-0°', '0°')
        ax.annotate(tt, (tw[3], tw[2]), ha='center', va='center', fontsize=15 if main else 11.5, fontweight='bold', color='white', zorder=8.5,
                    bbox=dict(boxstyle='circle,pad=0.32' if not main else 'circle,pad=0.38', fc=tcol(t_), ec=ORANGE if main else 'white', lw=3 if main else 2))
        fs = 17 if main else 13.5
        txt = f"{tw[L]}  {p_:.0f}%"
        an = ax.annotate(txt, (tw[3], tw[2]), xytext=(dx, dy), textcoords='offset pixels', ha=ha, va=va, fontsize=fs, fontweight='bold' if main else 'semibold', color=INK, zorder=9,
                         bbox=dict(boxstyle='round,pad=0.32,rounding_size=0.7', fc='white', ec=ORANGE if main else (col or '#c9d2db'), lw=2.2 if main else 1.4, alpha=0.93))
    ax.text(0.995, 0.01, 't.me/ObHavo_ECMWF_bot', transform=ax.transAxes, ha='right', va='bottom', fontsize=11, color=FAINT, zorder=9)
    # header
    fig.patches.append(Rectangle((0, 0.906), 1, 0.094, transform=fig.transFigure, fc=NAVY, ec='none', zorder=-1))
    fig.text(0.016, 0.953, 'OSMON', fontsize=22, fontweight='bold', color=ORANGE, va='center')
    fig.text(0.093, 0.953, X['title'], fontsize=22, fontweight='bold', color='white', va='center')
    fig.text(0.984, 0.968, fr['when'], fontsize=24, fontweight='bold', color='#ffd29c', ha='right', va='center')
    fig.text(0.984, 0.928, X['tz'] + ' · ' + fr['day'], fontsize=14, color='#a9bdd6', ha='right', va='center')
    # progress over the 15 days
    fig.patches.append(Rectangle((0, 0.903), 1, 0.004, transform=fig.transFigure, fc='#2c3e57', ec='none', zorder=0))
    fig.patches.append(Rectangle((0, 0.903), fr['prog'], 0.004, transform=fig.transFigure, fc=ORANGE, ec='none', zorder=0.1))
    # legend
    fig.text(0.016, 0.247, X['leg'], fontsize=13, color=MUTED, va='center')
    for j, (pal, nm) in enumerate(((RAIN, X['rain']), (SNOW, X['snow']))):
        y = 0.214 - j * 0.0; xb = 0.016 + j * 0.30
        fig.text(xb, y, nm, fontsize=13, fontweight='bold', color=INK, va='center')
        for k, (c, lab) in enumerate(zip(pal, ['10–30', '30–50', '50–70', '70–90', '90–100'])):
            xx = xb + 0.052 + k * 0.047
            fig.patches.append(FancyBboxPatch((xx, y - 0.012), 0.043, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc=c, ec='none'))
            fig.text(xx + 0.0215, y, lab, fontsize=10.5, fontweight='bold', color='white' if k >= 2 else INK, ha='center', va='center')
    fig.add_artist(matplotlib.lines.Line2D([0.62, 0.645], [0.214, 0.214], color='#3d7be0', lw=1.6, ls=(0, (4, 2.5)), transform=fig.transFigure))
    fig.text(0.65, 0.214, '0°' + (' — граница дождя и снега' if lang == 'ru' else ' — yomg‘ir va qor chegarasi'), fontsize=12, color=MUTED, va='center')
    fig.text(0.984, 0.247, X['models'].format(n=C['members']), fontsize=11, color=FAINT, ha='right', va='center')
    # Tashkent: bars of the chance, the temperature line
    fig.text(0.016, 0.178, X['chart'], fontsize=13, fontweight='bold', color=INK, va='center')
    bx = fig.add_axes([0.035, 0.05, 0.93, 0.105]); bx.set_facecolor('none')
    Xc, Wn, Pt, Tt = C['bx'], C['bw'], C['tp'], C['tt']
    cols = [(level(p_, SNOW if t_ <= 0.5 else RAIN) or BAR_EMPTY) for p_, t_ in zip(Pt, Tt)]
    bx.bar(Xc, np.maximum(Pt, 2), width=Wn * 0.8, color=cols, zorder=2)
    s = fr['s']; bx.axvspan(Xc[s] - Wn[s] / 2, Xc[s] + Wn[s] / 2, color=ORANGE, alpha=0.18, lw=0, zorder=1)
    bx.add_patch(Rectangle((Xc[s] - Wn[s] / 2, 0), Wn[s], 100, fill=False, ec=ORANGE, lw=2, zorder=5))
    bx.set_ylim(0, 100); bx.set_xlim(Xc[0] - Wn[0], Xc[-1] + Wn[-1] / 2)
    bx.set_yticks([0, 50, 100]); bx.set_yticklabels(['0', '50', '100%'], fontsize=10, color=FAINT); bx.tick_params(length=0)
    for d0, lab in C['days']: bx.axvline(d0, color=LINE, lw=0.9, zorder=0)
    bx.set_xticks([d + 12 for d, _ in C['days']]); bx.set_xticklabels([lab[lang] for _, lab in C['days']], fontsize=10.5, color=MUTED, linespacing=1.05)
    for sp in bx.spines.values(): sp.set_visible(False)
    tx = bx.twinx(); tlo, thi = np.nanmin(Tt), np.nanmax(Tt); pad = max(2, (thi - tlo) * 0.2)
    tx.plot(Xc, Tt, color=TEMP, lw=2.2, zorder=6, solid_capstyle='round'); tx.set_ylim(tlo - pad, thi + pad)
    tx.plot([Xc[s]], [fr['tash_t']], 'o', ms=9, color=TEMP, mec='white', mew=2, zorder=7)
    tx.annotate(f"{fr['tash_t']:+.0f}°".replace('+0°', '0°'), (Xc[s], fr['tash_t']), xytext=(10, 4), textcoords='offset points', ha='left', fontsize=13, fontweight='bold', color=TEMP, zorder=8,
                path_effects=[pe.withStroke(linewidth=3, foreground='white')])
    tx.set_yticks([]); [sp.set_visible(False) for sp in tx.spines.values()]
    # the opening and the closing cards
    if fr.get('card') == 'intro':
        a = fr['a']; fig.patches.append(Rectangle((0, 0.272), 1, 0.634, transform=fig.transFigure, fc='white', alpha=0.86 * a, ec='none', zorder=30))
        fig.text(0.5, 0.64, 'OSMON', fontsize=44, fontweight='bold', color=ORANGE, ha='center', va='center', alpha=a, zorder=31)
        fig.text(0.5, 0.56, X['intro1'], fontsize=40, fontweight='bold', color=INK, ha='center', va='center', alpha=a, zorder=31)
        fig.text(0.5, 0.49, X['intro2'], fontsize=26, color=MUTED, ha='center', va='center', alpha=a, zorder=31)
    if fr.get('card') == 'end':
        fig.patches.append(Rectangle((0, 0.272), 1, 0.634, transform=fig.transFigure, fc='white', alpha=0.9, ec='none', zorder=30))
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
                    '-vf', 'framerate=fps=30:interp_start=0:interp_end=255:scene=100,format=yuv420p', '-c:v', 'libx264', '-crf', '20', '-maxrate', '1900k', '-bufsize', '3800k',
                    '-preset', 'slow', '-tune', 'animation', '-c:a', 'aac', '-b:a', '48k', '-shortest', '-movflags', '+faststart', str(tmp)], check=True)
    tmp.replace(out); shutil.rmtree(fd); return f'{out} {out.stat().st_size // 1024} KB'


def main(npz, wxp, outd, langs, only=None):
    D = load(npz); P, models, members = probability(D); WX = load_wx_npz(D, wxp)
    g = D['grid'].item(); lon = g['lon0'] + np.arange(g['W']) * g['d']; lat = g['lat0'] - np.arange(g['H']) * g['d']
    lat_s, P = lat[::-1], P[:, ::-1]; Tm = WX['T'][:, ::-1]
    PAD = 16  # the map is wider than the data (50–80° E): the edge values carried on, so no patch ends in a straight line
    P = np.pad(P, ((0, 0), (0, 0), (PAD, PAD)), mode='edge'); Tm = np.pad(Tm, ((0, 0), (0, 0), (PAD, PAD)), mode='edge')
    lon = np.r_[lon[0] - g['d'] * np.arange(PAD, 0, -1), lon, lon[-1] + g['d'] * np.arange(1, PAD + 1)]
    UP = 4; up = lambda a: gaussian_filter(zoom(np.nan_to_num(a, nan=np.nanmean(a)), UP, order=1), 1.6)
    LONu = np.linspace(lon[0], lon[-1], len(lon) * UP); LATu = np.linspace(lat_s[0], lat_s[-1], len(lat_s) * UP)
    at = lambda a, la, lo: float(a[np.abs(LATu - la).argmin(), np.abs(LONu - lo).argmin()])
    run = dt.datetime.fromisoformat(D['run'].replace('Z', '')[:19]); steps = [int(x) for x in D['steps']]; win = [int(x) for x in D['win']]
    now = dt.datetime.utcnow()
    keep = [i for i, s in enumerate(steps) if run + dt.timedelta(hours=s) > now + dt.timedelta(hours=1)]
    if only: keep = keep[:only]
    Pk = {i: np.clip(up(P[i]), 0, 100) for i in keep}; Tk = {i: up(Tm[i]) for i in keep}
    loc = lambda h: run + dt.timedelta(hours=h + 5)
    tash = TOWNS[0]
    # the chart under the map: hours from the first window's start
    h0 = steps[keep[0]] - win[keep[0]]
    bx = np.array([steps[i] - win[i] / 2 - h0 for i in keep], float); bw = np.array([win[i] for i in keep], float)
    tp = np.array([at(Pk[i], tash[2], tash[3]) for i in keep]); tt = np.array([at(Tk[i], tash[2], tash[3]) for i in keep])
    days = []; t0 = loc(h0); d = (t0 + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0)
    if t0.hour == 0: d = t0
    while (d - t0).total_seconds() / 3600 < bx[-1]:
        hh = (d - t0).total_seconds() / 3600
        days.append((hh, {l: f"{TX[l]['wd'][d.weekday()]}\n{d:%d.%m}" for l in TX})); d += dt.timedelta(days=1)
    # the frames: a few in-between frames per window, the numbers of the window
    G = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']; GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']
    WAT = json.load(open(ROOT / 'prob' / 'geo_water.json'))
    sea = [np.asarray(r) for r in WAT['ocean']] + [np.asarray(l_['r']) for l_ in WAT['lakes']]
    UZ = [np.asarray(r) for r in G['UZ']['rings']]; NB = [np.asarray(r) for k, c in G.items() if k != 'UZ' for r in c['rings']]
    A1 = [np.asarray(r) for a in GA['adm1'] for r in a['r']]
    span = (LAT1 - LAT0) / COSL * (MAP[2] * W) / (MAP[3] * H); lc = 64.8
    CTX.update(LONu=LONu, LATu=LATu, sea=sea, borders=[(NB, '#a3acb6', 1.0, 3), (A1, '#b7c0ca', 0.8, 3.05), (UZ, '#1c2633', 2.6, 3.3)], lon_ext=(lc - span / 2, lc + span / 2),
               members=members, bx=bx, bw=bw, tp=tp, tt=tt, days=days, qr=qr('https://t.me/ObHavo_ECMWF_bot'), videos={})
    seq = []
    for n_, i in enumerate(keep):  # one frame for every hour of the window (15:00, 16:00, …), the fields eased towards the next window
        nxt = keep[min(n_ + 1, len(keep) - 1)]; N = win[i]
        for k in range(N):
            a = k / N; seq.append((n_, i, (1 - a) * Pk[i] + a * Pk[nxt], (1 - a) * Tk[i] + a * Tk[nxt], k))
    tot_h = (steps[keep[-1]] - h0)
    for lang in langs:
        X = TX[lang]; frames = []
        for n_, i, Pf, Tf, k in seq:
            t2 = loc(steps[i]); t1 = t2 - dt.timedelta(hours=win[i]); th = t1 + dt.timedelta(hours=k)
            when = f"{X['wd'][th.weekday()]} {th:%d.%m} · {th:%H}:00"
            dayn = max(1, (th.date() - loc(h0).date()).days + (0 if loc(h0).hour >= 12 else 1))  # day 1: the first full local day
            frames.append(dict(P=Pf, T=Tf, s=n_, when=when, day=X['day'].format(i=min(dayn, 15), n=15), prog=(steps[i] - win[i] + k - h0) / tot_h, d=0.2,
                               towns=[(at(Pf, tw[2], tw[3]), at(Tf, tw[2], tw[3])) for tw in TOWNS], tash_t=at(Tf, tash[2], tash[3])))
        frames[-1] = dict(frames[-1], d=1.2)
        intro = [dict(frames[0], card='intro', a=1.0, fade=0.0, d=1.6)] + [dict(frames[0], card='intro', a=float(a_), fade=float(1 - a_), d=0.07) for a_ in np.linspace(1, 0, 9)[1:]]
        end = [dict(frames[-1], card='end', d=4.0)]
        CTX['videos'][lang] = dict(frames=intro + frames + end, dir=tempfile.mkdtemp(), out=str(pathlib.Path(outd) / f'p15_{lang}.mp4'))
    return CTX


if __name__ == '__main__':
    npz, wxp, outd = sys.argv[1:4]; langs = (sys.argv[4] if len(sys.argv) > 4 else 'ru,uz').split(',')
    pathlib.Path(outd).mkdir(parents=True, exist_ok=True)
    main(npz, wxp, outd, langs)
    jobs = [(l, i) for l in langs for i in range(len(CTX['videos'][l]['frames']))]; print(len(jobs), 'frames', flush=True)
    with mp.get_context('fork').Pool(max(1, os.cpu_count() or 1)) as pool:
        for n_, _ in enumerate(pool.imap_unordered(draw, jobs, chunksize=4)):
            if n_ % 200 == 0: print('frames', n_, '/', len(jobs), flush=True)
        for r in pool.imap_unordered(encode, langs): print(r, flush=True)
