"""The mountains of Uzbekistan as a video on the map: day by day for 10 days, where fresh snow falls (violet) and where it
rains (blue) over the mountains in relief, and at the six places people go to (Chimgan, Amirsoy, Beldersay, the Kamchik pass,
Urgut, Zomin) a card: the day's temperature, the fresh snow or the rain, and whether it is a good day to go — under the map
the 10 days of each place as a strip (green good days, violet snow, blue rain, the best day after the snow framed).
Data: the places — prob/mountains.py (Open-Meteo, corrected to the place's height); the map — ECMWF IFS HRES (prob/moisture.py).
Usage: python tools/mtn_video.py mountains.json prob.npz out ru,uz  →  out/mtn_{lang}.mp4"""
import sys, os, json, math, pathlib, tempfile, datetime as dt, multiprocessing as mp
import numpy as np
from scipy.ndimage import zoom, gaussian_filter

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'prob'))
import prob15_video as PV
from prob15_video import plt, matplotlib, LineCollection, Rectangle, FancyBboxPatch, pe

W, H, DPI = PV.W, PV.H, PV.DPI
MAP = (0.0, 0.30, 1.0, 0.606)  # the map; the 10-day strips of the places below it
LA0, LA1, LC = 38.75, 42.35, 69.6
COSL = math.cos(math.radians((LA0 + LA1) / 2))
SPAN = (LA1 - LA0) / COSL * (MAP[2] * W) / (MAP[3] * H)
EXT = (LC - SPAN / 2, LC + SPAN / 2)
SNOW_LV, SNOW_C = [1, 3, 6, 12, 25, 500], ['#efe6ff', '#d9c4fb', '#bb9cf2', '#9b72e2', '#7444c4']
RAIN_LV, RAIN_C = [1, 3, 8, 15, 30, 500], ['#d6ebfa', '#a3cdf1', '#62a6e6', '#2f7ad0', '#1c55a8']
GOOD = {2: '#bfe7c6', 1: '#e3f4e5', 0: '#ffffff'}
TX = {'ru': dict(title='Горы Узбекистана · снег и дни для поездки', day='день {i} из {n}', snow='снег, см', rain='дождь, мм', good='хороший день', great='отличный день',
                 best='лучший день после снега', cm='см', mm='мм', m='м', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], tz='по Ташкенту',
                 v_snow='снег', v_rain='дождь', v_great='✓ отлично', v_good='✓ можно ехать', v_no='не лучший день', fresh='свежий снег на карте за сутки',
                 src='Места: Open-Meteo (ECMWF, DWD, NOAA) с поправкой на высоту · карта: ECMWF IFS · Osmon', intro1='Горы Узбекистана', intro2='снег и лучшие дни для поездки на 10 дней',
                 end1='Чимган, Амирсой, Бельдерсай, Камчик, Ургут, Зомин', end2='каждый день в Telegram-боте @ObHavo_ECMWF_bot'),
      'uz': dict(title='O‘zbekiston tog‘lari · qor va sayohat kunlari', day='{i}-kun / {n}', snow='qor, sm', rain='yomg‘ir, mm', good='yaxshi kun', great='a’lo kun',
                 best='qordan keyingi eng yaxshi kun', cm='sm', mm='mm', m='m', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'], tz='Toshkent vaqti',
                 v_snow='qor', v_rain='yomg‘ir', v_great='✓ a’lo', v_good='✓ borsa bo‘ladi', v_no='yaxshi kun emas', fresh='xaritada bir sutkadagi yangi qor',
                 src='Joylar: Open-Meteo (ECMWF, DWD, NOAA), balandlikka tuzatilgan · xarita: ECMWF IFS · Osmon', intro1='O‘zbekiston tog‘lari', intro2='10 kunga qor va sayohat uchun eng yaxshi kunlar',
                 end1='Chimyon, Amirsoy, Beldersoy, Qamchiq, Urgut, Zomin', end2='har kuni Telegram-botda: @ObHavo_ECMWF_bot')}
CTX = {}


def best_after_snow(days):
    """The first good day after the last snow day (the framed one)."""
    out = set(); last = None
    for i, d in enumerate(days):
        if d['sn'] >= 2: last = i
        elif last is not None and d['good'] and (not out or max(out) < last): out.add(i)
    return out


def draw(job):
    lang, i = job; C = CTX; V = C['videos'][lang]; fr = V['frames'][i]; X = TX[lang]
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI); fig.patch.set_facecolor('white')
    ax = fig.add_axes(MAP); ax.set_xlim(*EXT); ax.set_ylim(LA0, LA1); ax.set_aspect(1 / COSL); ax.axis('off')
    if C['relief'] is not None: ax.imshow(C['relief'], extent=(EXT[0], EXT[1], LA0, LA1), origin='upper', interpolation='bilinear', aspect='auto', zorder=0.6)
    ax.set_xlim(*EXT); ax.set_ylim(LA0, LA1); ax.set_aspect(1 / COSL)
    for r in C['sea']: ax.fill(r[:, 0], r[:, 1], fc=PV.SEA, ec='#b9cfe3', lw=0.6, zorder=0.5)
    a_in = fr.get('fade', 1.0); LO, LA = C['LO'], C['LA']
    if fr['rain'] is not None and fr['rain'].max() >= RAIN_LV[0]:
        ax.contourf(LO, LA, fr['rain'], levels=RAIN_LV, colors=RAIN_C, alpha=0.78 * a_in, zorder=2, antialiased=True)
    if fr['snow'] is not None and fr['snow'].max() >= SNOW_LV[0]:
        ax.contourf(LO, LA, fr['snow'], levels=SNOW_LV, colors=SNOW_C, alpha=0.85 * a_in, zorder=2.1, antialiased=True)
        ax.contour(LO, LA, fr['snow'], levels=[3], colors=['#7444c4'], linewidths=0.8, alpha=0.6 * a_in, zorder=2.15)
    ax.set_xlim(*EXT); ax.set_ylim(LA0, LA1); ax.set_aspect(1 / COSL)
    for rings, col, lw, z in C['borders']: ax.add_collection(LineCollection(rings, colors=col, linewidths=lw, zorder=z, capstyle='round', joinstyle='round'))
    for nm, lo, la in C['towns']: ax.plot(lo, la, 'o', ms=4, color='#6b7785', zorder=5); ax.text(lo, la - 0.07, nm, fontsize=11, color='#6b7785', ha='center', va='top', zorder=5)
    # the six places: a peak mark and a card
    L = 0 if lang == 'ru' else 1; k = fr['k']; items = []
    for s in C['spots']:
        d = s['days'][k]
        if d['sn'] >= 1: v, vc = f"{X['v_snow']} {d['sn']:.0f} {X['cm']}", '#7444c4'
        elif d['rn'] >= 1 or d['pr'] >= 1: v, vc = f"{X['v_rain']} {max(d['rn'], d['pr']):.0f} {X['mm']}", '#1c63c0'
        elif d['good'] == 2: v, vc = X['v_great'], '#1f8a4c'
        elif d['good'] == 1: v, vc = X['v_good'], '#3f9b5f'
        else: v, vc = X['v_no'], '#8a96a3'
        items.append((s, d, v, vc))
    for s, d, v, vc in items:  # a card in its own slot around the mountains, a thin line to the peak
        best = k in s['best']; dx, dy = s['off']
        ax.plot(s['lon'], s['lat'], marker='^', ms=16, color='#2b3a4a', mec='white', mew=2, zorder=8)
        txt = f"{s['name'][lang]} · {s['elev']} {X['m']}\n{PV_deg(d['tmin'])}…{PV_deg(d['tmax'])}   {v}" + (f"\n★ {X['best']}" if best else '')
        fc = (SNOW_C[1] if d['sn'] >= 1 else RAIN_C[0] if max(d['rn'], d['pr']) >= 1 else GOOD.get(d['good'], '#ffffff'))
        ax.annotate(txt, (s['lon'], s['lat']), xytext=(dx, dy), textcoords='offset pixels', ha='center', va='center', fontsize=14, fontweight='bold', color='#1f2933', zorder=9, linespacing=1.35,
                    bbox=dict(boxstyle='round,pad=0.5,rounding_size=0.8', fc=fc, ec=PV.ORANGE if best else '#9aa6b2', lw=3.2 if best else 1.0, alpha=0.95),
                    arrowprops=dict(arrowstyle='-', color='#5b6876', lw=1.2, shrinkA=0, shrinkB=9))
    ax.text(0.995, 0.01, 'Bot - @ObHavo_ECMWF_bot · Kanal - @osmon_obhavo', transform=ax.transAxes, ha='right', va='bottom', fontsize=11, color=PV.FAINT, zorder=9)
    ax.text(0.005, 0.01, X['src'], transform=ax.transAxes, ha='left', va='bottom', fontsize=10, color=PV.FAINT, zorder=9)
    # header
    fig.patches.append(Rectangle((0, 0.906), 1, 0.094, transform=fig.transFigure, fc=PV.NAVY, ec='none', zorder=-1))
    fig.text(0.016, 0.953, 'OSMON', fontsize=22, fontweight='bold', color=PV.ORANGE, va='center')
    fig.text(0.093, 0.953, X['title'], fontsize=22, fontweight='bold', color='white', va='center')
    fig.text(0.984, 0.968, fr['when'], fontsize=24, fontweight='bold', color='#ffd29c', ha='right', va='center')
    fig.text(0.984, 0.928, X['tz'] + ' · ' + X['day'].format(i=k + 1, n=C['n']), fontsize=14, color='#a9bdd6', ha='right', va='center')
    fig.patches.append(Rectangle((0, 0.903), 1, 0.004, transform=fig.transFigure, fc='#2c3e57', ec='none', zorder=0))
    fig.patches.append(Rectangle((0, 0.903), fr['prog'], 0.004, transform=fig.transFigure, fc=PV.ORANGE, ec='none', zorder=0.1))
    # legend
    y = 0.283; xx = 0.016
    def chips(x, lab, cols, labs):
        fig.text(x, y, lab, fontsize=12.5, fontweight='bold', color=PV.INK, va='center'); x += 0.006 * len(lab) + 0.012
        for c, l in zip(cols, labs):
            fig.patches.append(FancyBboxPatch((x, y - 0.011), 0.032, 0.022, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc=c, ec='none'))
            fig.text(x + 0.016, y, l, fontsize=10, fontweight='bold', color=PV.INK, ha='center', va='center'); x += 0.035
        return x + 0.015
    xx = chips(xx, X['snow'], SNOW_C, ['1', '3', '6', '12', '25+'])
    xx = chips(xx, X['rain'], RAIN_C, ['1', '3', '8', '15', '30+'])
    for c, lab, ec in ((GOOD[2], X['great'], 'none'), (GOOD[1], X['good'], 'none'), ('#ffffff', X['best'], PV.ORANGE)):
        fig.patches.append(FancyBboxPatch((xx, y - 0.011), 0.03, 0.022, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc=c, ec=ec, lw=2))
        fig.text(xx + 0.035, y, lab, fontsize=12, color=PV.MUTED, va='center'); xx += 0.035 + 0.0062 * len(lab) + 0.02
    # the strips: each place × the days
    n = C['n']; x0, x1 = 0.165, 0.985; cw = (x1 - x0) / n; top = 0.238; rh = 0.037
    for j in range(n):
        d0 = C['dates'][j]
        fig.text(x0 + cw * (j + 0.5), top + 0.003, f"{X['wd'][d0.weekday()]} {d0:%d.%m}", fontsize=11.5, fontweight='bold' if j == k else 'normal', color=PV.ORANGE if j == k else PV.MUTED, ha='center', va='bottom')
    for r_, s in enumerate(C['spots']):
        yy = top - (r_ + 1) * rh
        fig.text(0.016, yy + rh / 2, f"{s['name'][lang]} · {s['elev']} {X['m']}", fontsize=12.5, fontweight='bold', color=PV.INK, va='center')
        for j, d in enumerate(s['days'][:n]):
            c = SNOW_C[min(4, int(np.searchsorted(SNOW_LV, d['sn'], side='right')) - 1)] if d['sn'] >= 1 else RAIN_C[min(4, int(np.searchsorted(RAIN_LV, max(d['rn'], d['pr']), side='right')) - 1)] if max(d['rn'], d['pr']) >= 1 else GOOD.get(d['good'], '#ffffff')
            show = j <= k  # the strip fills in as the days go by
            fig.patches.append(FancyBboxPatch((x0 + cw * j + 0.002, yy + 0.003), cw - 0.004, rh - 0.006, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure,
                                              fc=c if show else '#f3f5f7', ec=PV.ORANGE if (j in s['best'] and show) else ('#d5dbe1' if c == '#ffffff' else 'none'), lw=2.2 if j in s['best'] else 0.6))
            if show:
                t = f"{d['sn']:.0f} {X['cm']}" if d['sn'] >= 1 else f"{max(d['rn'], d['pr']):.0f} {X['mm']}" if max(d['rn'], d['pr']) >= 1 else f"{PV_deg(d['tmax'])}"
                fig.text(x0 + cw * (j + 0.5), yy + rh / 2, t, fontsize=10.5, fontweight='bold', color='white' if (d['sn'] >= 12 or max(d['rn'], d['pr']) >= 15) else PV.INK, ha='center', va='center')
    fig.patches.append(Rectangle((x0 + cw * k, top - len(C['spots']) * rh), cw, len(C['spots']) * rh, transform=fig.transFigure, fill=False, ec=PV.NAVY, lw=2.2))
    if fr.get('card') == 'intro':
        a = fr['a']; fig.patches.append(Rectangle((0, MAP[1]), 1, MAP[3], transform=fig.transFigure, fc='white', alpha=0.86 * a, ec='none', zorder=30))
        fig.text(0.5, 0.70, 'OSMON', fontsize=44, fontweight='bold', color=PV.ORANGE, ha='center', va='center', alpha=a, zorder=31)
        fig.text(0.5, 0.62, X['intro1'], fontsize=40, fontweight='bold', color=PV.INK, ha='center', va='center', alpha=a, zorder=31)
        fig.text(0.5, 0.55, X['intro2'], fontsize=26, color=PV.MUTED, ha='center', va='center', alpha=a, zorder=31)
    if fr.get('card') == 'end':
        fig.patches.append(Rectangle((0, MAP[1]), 1, MAP[3], transform=fig.transFigure, fc='white', alpha=0.9, ec='none', zorder=30))
        fig.text(0.38, 0.72, 'OSMON', fontsize=44, fontweight='bold', color=PV.ORANGE, ha='center', va='center', zorder=31)
        fig.text(0.38, 0.64, X['end1'], fontsize=28, fontweight='bold', color=PV.INK, ha='center', va='center', zorder=31)
        fig.text(0.38, 0.57, X['end2'], fontsize=24, color=PV.MUTED, ha='center', va='center', zorder=31)
        PV.qr2(fig, y=0.46, h=0.28)
    fig.savefig(pathlib.Path(V['dir']) / f'{i:04d}.png', dpi=DPI, facecolor='white'); plt.close(fig)


def PV_deg(v):
    v = int(round(v)); return f'{v:+d}°' if v else '0°'


def grid_days(npz, dates):
    """Daily fresh snow (cm ≈ mm of water where it is freezing) and rain (mm) on the map's grid from ECMWF HRES; None without data."""
    try:
        import moisture as M, render as Rn
        D = Rn.load(npz); run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None); run = run.replace(hour=0 if run.hour < 12 else 12)
        F = M.fetch(run, [s for s in M.STEPS15 if s[0] <= 246])
    except Exception as e:
        print('no ECMWF fields', e, flush=True); return None
    lon = M.LON0 + np.arange(F[min(F)]['msl'].shape[1]) * M.RES; lat = M.LAT0 + np.arange(F[min(F)]['msl'].shape[0]) * M.RES
    ci = np.flatnonzero((lon >= EXT[0] - 1) & (lon <= EXT[1] + 1)); ri = np.flatnonzero((lat >= LA0 - 1) & (lat <= LA1 + 1))
    UP = 5; LO = np.linspace(lon[ci[0]], lon[ci[-1]], len(ci) * UP); LA = np.linspace(lat[ri[0]], lat[ri[-1]], len(ri) * UP)
    up = lambda a: gaussian_filter(zoom(a[np.ix_(ri, ci)], UP, order=3), 2.5)
    ks = sorted(F); out = []
    for d0 in dates:
        a = (dt.datetime.combine(d0, dt.time()) - dt.timedelta(hours=5) - run).total_seconds() / 3600; b = a + 24
        s0 = min(ks, key=lambda s: abs(s - a)); s1 = min(ks, key=lambda s: abs(s - b))
        if s1 <= s0 or abs(s0 - a) > 6 or abs(s1 - b) > 6: out.append((None, None)); continue
        tp = np.clip(F[s1]['tp'] - F[s0]['tp'], 0, None); t2 = np.mean([F[s]['t2'] for s in ks if s0 <= s <= s1], axis=0)
        sf = np.clip((1.0 - t2) / 2.0, 0, 1)  # the snow share: all snow below −1 °C, all rain above +1 °C
        out.append((np.clip(up(tp * sf), 0, None), np.clip(up(tp * (1 - sf)), 0, None)))
    return out, LO, LA


def main():
    mj, npz, outd = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3]); langs = (sys.argv[4] if len(sys.argv) > 4 else 'ru,uz').split(','); outd.mkdir(parents=True, exist_ok=True)
    J = json.load(open(mj)); n = 10
    today = (dt.datetime.utcnow() + dt.timedelta(hours=5)).date()
    spots = []
    OFFS = {'chimgan': (-150, 95), 'amirsoy': (-360, -20), 'beldersay': (330, 75), 'kamchik': (340, -30), 'urgut': (-330, 10), 'zomin': (300, -60)}  # card slots (px) around the peaks
    for s in J['spots']:
        days = [d for d in s['days'] if dt.date.fromisoformat(d['d']) >= today][:n]
        spots.append(dict(s, days=days, best=best_after_snow(days), off=OFFS.get(s['id'], (0, 120))))
    n = min(len(s['days']) for s in spots); dates = [dt.date.fromisoformat(d['d']) for d in spots[0]['days'][:n]]
    G = grid_days(npz, dates) if npz and pathlib.Path(npz).exists() else None
    if G: grids, LO, LA = G
    else: grids, LO, LA = [(None, None)] * n, None, None
    GW = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']; GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']
    WAT = json.load(open(ROOT / 'prob' / 'geo_water.json'))
    rel = PV.relief_layer(EXT[0], EXT[1], LA0, LA1, 1800, 700)
    if rel is not None: rel[..., 3] = np.clip(rel[..., 3] * 2.0, 0, 0.5)  # the mountains are the point here: shaded more
    towns = [('Ташкент' if True else '', 69.28, 41.31), ('Самарканд', 66.96, 39.65), ('Джизак', 67.84, 40.12), ('Наманган', 71.67, 41.0), ('Фергана', 71.78, 40.39), ('Андижан', 72.34, 40.78)]
    CTX.update(relief=rel, LO=LO, LA=LA, spots=spots, n=n, dates=dates, qr=PV.qr('https://t.me/ObHavo_ECMWF_bot'), videos={},
               sea=[np.asarray(r) for r in WAT['ocean']] + [np.asarray(l_['r']) for l_ in WAT['lakes']],
               borders=[([np.asarray(r) for k, c in GW.items() if k != 'UZ' for r in c['rings']], '#8d97a3', 1.0, 3), ([np.asarray(r) for a in GA['adm1'] for r in a['r']], '#aab4bf', 0.8, 3.05),
                        ([np.asarray(r) for r in GW['UZ']['rings']], '#1c2633', 2.4, 3.3)])
    TW = {'ru': [t[0] for t in towns], 'uz': ['Toshkent', 'Samarqand', 'Jizzax', 'Namangan', 'Farg‘ona', 'Andijon']}
    for lang in langs:
        X = TX[lang]; frames = []; CTX['towns'] = None
        for k in range(n):
            sn, rn = grids[k]; nx_sn, nx_rn = grids[min(k + 1, n - 1)]
            for q in range(14):  # the day held, then eased into the next
                a = 0 if q < 10 else (q - 9) / 5
                mix = lambda A, B: None if A is None else (A if B is None else (1 - a) * A + a * B)
                frames.append(dict(k=k, snow=mix(sn, nx_sn), rain=mix(rn, nx_rn), when=f"{X['wd'][dates[k].weekday()]} {dates[k]:%d.%m}", prog=(k + q / 14) / n, d=0.2))
        frames[-1] = dict(frames[-1], d=1.5)
        intro = [dict(frames[0], card='intro', a=1.0, fade=0.0, d=1.6)] + [dict(frames[0], card='intro', a=float(a_), fade=float(1 - a_), d=0.07) for a_ in np.linspace(1, 0, 9)[1:]]
        CTX['videos'][lang] = dict(frames=intro + frames + [dict(frames[-1], card='end', d=4.0)], dir=tempfile.mkdtemp(), out=str(outd / f'mtn_{lang}.mp4'), towns=[(nm, lo, la) for nm, (_, lo, la) in zip(TW[lang], towns)])
    PV.CTX.update(videos=CTX['videos'])
    jobs = [(l, i) for l in langs for i in range(len(CTX['videos'][l]['frames']))]; print(len(jobs), 'frames', flush=True)
    with mp.get_context('fork').Pool(max(1, os.cpu_count() or 1)) as pool:
        list(pool.imap_unordered(draw_l, jobs, chunksize=4))
        for r in pool.imap_unordered(PV.encode, langs): print(r, flush=True)


def draw_l(job):
    CTX['towns'] = CTX['videos'][job[0]]['towns']; return draw(job)


if __name__ == '__main__':
    main()
