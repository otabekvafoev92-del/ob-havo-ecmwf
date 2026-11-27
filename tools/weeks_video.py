"""The weather by ISO weeks over Uzbekistan, in the look of the 15-day video (tools/prob15_video.py): for the past week
(what fell, analysis) and the next weeks (ECMWF EC46 extended-range ensemble mean, up to ~6 weeks): how much precipitation
falls as a share of the normal for that week (%), and the mean temperature of the week at the towns (in circles, with the
difference from the normal). Under the map: Tashkent week by week.
Data: Open-Meteo (CC BY 4.0), the same grid as prob/outlook.py.
Usage: python tools/weeks_video.py out ru,uz [--cache weeks.json]  →  out/weeks_{lang}.mp4, out/weeks.json"""
import sys, os, json, pathlib, tempfile, datetime as dt, multiprocessing as mp
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'prob')); sys.path.insert(0, str(ROOT / 'tools'))
import prob15_video as PV  # the look: colours, towns, header, encoding
from prob15_video import plt, matplotlib, ListedColormap, BoundaryNorm, LineCollection, Rectangle, FancyBboxPatch, pe
from scipy.interpolate import RegularGridInterpolator
from scipy.ndimage import gaussian_filter

LONS = np.round(np.arange(55.5, 73.51, 0.75), 2); LATS = np.round(np.arange(36.75, 46.01, 0.75), 2)
PCT_LV = [0, 25, 50, 80, 120, 150, 200, 300, 2000]
PCT_COL = ['#a0632c', '#cf9a5c', '#ead2a8', '#ffffff', '#cfe6f7', '#93c6ee', '#4a98e0', '#1c58b0']
TX = {'ru': dict(title='Погода по неделям', week='Неделя {n}', dtitle='Неделя по дням', dleg='Дождь, мм', sleg='Снег, см', clouds='тучи', dchart='Ташкент: дождь (мм) и снег (см) по дням, температура днём и ночью', past='прошедшая неделя · факт', fc='прогноз ECMWF EC46', leg='Осадки за неделю, % от нормы',
                 less='меньше нормы', norm='около нормы', more='больше нормы', circ='в кружке — средняя температура недели, °C', chart='Ташкент: осадки по неделям (% от нормы) и средняя температура',
                 dtn='{d:+.0f}° к норме', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], intro1='Погода по неделям', intro2='осадки к норме и температура на 6 недель',
                 end1='Погода в вашем районе и посёлке', end2='в Telegram-боте @ObHavo_ECMWF_bot', src='Данные: Open-Meteo (ECMWF EC46, анализ моделей)'),
      'uz': dict(title='Haftalar bo‘yicha ob-havo', week='Hafta {n}', dtitle='Hafta kunma-kun', dleg='Yomg‘ir, mm', sleg='Qor, sm', clouds='bulut', dchart='Toshkent: kunlar bo‘yicha yomg‘ir (mm) va qor (sm), kunduzgi va tungi harorat', past='o‘tgan hafta · fakt', fc='ECMWF EC46 prognozi', leg='Haftalik yog‘in, me’yorga nisbatan %',
                 less='me’yordan kam', norm='me’yor atrofida', more='me’yordan ko‘p', circ='doirada — haftaning o‘rtacha harorati, °C', chart='Toshkent: haftalar bo‘yicha yog‘in (me’yorga %) va o‘rtacha harorat',
                 dtn='me’yorga {d:+.0f}°', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'], intro1='Haftalar bo‘yicha ob-havo', intro2='6 haftaga yog‘in (me’yorga) va harorat',
                 end1='Tumaningiz va qishlog‘ingiz ob-havosi', end2='Telegram-botda: @ObHavo_ECMWF_bot', src='Ma’lumotlar: Open-Meteo (ECMWF EC46, modellar tahlili)')}
W, H = PV.W, PV.H
CTX = {}


def fetch():
    import outlook as OL
    pts = [(la, lo) for la in LATS for lo in LONS]
    import time, requests
    def get(url, params):  # Open-Meteo counts each point as a call (600 a minute): wait out the minute when it says so
        for k in range(8):
            try:
                r = requests.get(url, params=params, headers=OL.UA, timeout=90)
                if r.status_code == 200: return r.json()
                print('open-meteo', r.status_code, r.text[:120], flush=True)
            except Exception as e: print('open-meteo', e, flush=True)
            time.sleep(65)
        raise RuntimeError('open-meteo failed')
    sea = []
    for i in range(0, len(pts), 100):
        ch = pts[i:i + 100]
        r = get('https://seasonal-api.open-meteo.com/v1/seasonal', {'latitude': ','.join(str(p[0]) for p in ch), 'longitude': ','.join(str(p[1]) for p in ch),
                'models': 'ecmwf_seasonal_ensemble_mean_seamless', 'weekly': 'temperature_2m_mean,temperature_2m_anomaly,precipitation_mean,precipitation_anomaly',
                'daily': 'temperature_2m_mean,precipitation_sum,snowfall_sum,cloud_cover_mean,temperature_2m_max,temperature_2m_min', 'timezone': 'Asia/Tashkent'})
        sea += r if isinstance(r, list) else [r]; time.sleep(12)
    # the past ISO week (Monday–Sunday before this week): the daily analysis of the last 14 days
    past = []
    for i in range(0, len(pts), 100):
        ch = pts[i:i + 100]; time.sleep(12)
        r = get('https://api.open-meteo.com/v1/forecast', {'latitude': ','.join(str(p[0]) for p in ch), 'longitude': ','.join(str(p[1]) for p in ch),
                   'daily': 'precipitation_sum,temperature_2m_mean', 'past_days': 14, 'forecast_days': 1, 'timezone': 'Asia/Tashkent'})
        past += r if isinstance(r, list) else [r]
    s0 = sea[0]; wk = s0.get('weekly', {}); wu = s0.get('weekly_units', {})
    f = OL.per_day(wu.get('precipitation_mean'), 7)
    G = lambda key, i: [None if x.get('weekly', {}).get(key) is None or x['weekly'][key][i] is None else float(x['weekly'][key][i]) for x in sea]
    weeks = []
    # the past 7 days: totals; the normal of that week from the climate (the analysis has no anomaly): taken from the first forecast week's normal
    today_ = (dt.datetime.utcnow() + dt.timedelta(hours=5)).date(); d0 = today_ - dt.timedelta(days=today_.weekday() + 7)
    days_ = [dt.date.fromisoformat(t) for t in past[0]['daily']['time']]; ix = [k for k, d in enumerate(days_) if d0 <= d <= d0 + dt.timedelta(days=6)]
    pr = [float(np.nansum([x['daily']['precipitation_sum'][k] for k in ix if x['daily']['precipitation_sum'][k] is not None])) for x in past]
    tm = [float(np.nanmean([x['daily']['temperature_2m_mean'][k] for k in ix if x['daily']['temperature_2m_mean'][k] is not None] or [np.nan])) for x in past]
    weeks.append(dict(kind='past', start=d0.isoformat(), pr=pr, t=tm, pa=None, ta=None))
    today = (dt.datetime.utcnow() + dt.timedelta(hours=5)).date()
    for i, t in enumerate(wk.get('time', [])):
        s = dt.date.fromisoformat(t[:10])
        if s + dt.timedelta(days=6) < today: continue
        prm, pa, tmn, ta = G('precipitation_mean', i), G('precipitation_anomaly', i), G('temperature_2m_mean', i), G('temperature_2m_anomaly', i)
        if all(v is None for v in prm): continue
        weeks.append(dict(kind='fc', start=s.isoformat(), pr=[None if v is None else v * f for v in prm], pa=[None if v is None else v * f for v in pa], t=tmn, ta=ta))
    dd = s0.get('daily', {}); days = []  # each day of the coming weeks (EC46 ensemble mean): the week-by-day videos
    for i, t in enumerate(dd.get('time', [])):
        d_ = dt.date.fromisoformat(t[:10])
        if d_ < today: continue
        g_ = lambda key: [None if x.get('daily', {}).get(key) is None or x['daily'][key][i] is None else float(x['daily'][key][i]) for x in sea]
        days.append(dict(d=d_.isoformat(), pr=g_('precipitation_sum'), t=g_('temperature_2m_mean'), sn=g_('snowfall_sum'), cc=g_('cloud_cover_mean'), tx=g_('temperature_2m_max'), tn=g_('temperature_2m_min')))
    for w in weeks:  # each week's snow (cm) and mean cloud cover (%) from its days, where the days are known
        s_ = dt.date.fromisoformat(w['start']); dd_ = [x for x in days if s_ <= dt.date.fromisoformat(x['d']) <= s_ + dt.timedelta(days=6)]
        if dd_:
            w['sn'] = [float(np.nansum([x['sn'][i] or 0 for x in dd_])) for i in range(len(pts))]
            w['cc'] = [float(np.nanmean([x['cc'][i] if x['cc'][i] is not None else np.nan for x in dd_])) for i in range(len(pts))]
    return dict(made=dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), lats=LATS.tolist(), lons=LONS.tolist(), weeks=weeks[:7], days=days[:49])


def wk(s):  # the ISO week and its year, as on a calendar: «49-2026» (ISO 8601: the week of its Thursday; 2026 has 53 weeks, as it starts on a Thursday)
    y, n, _ = (s + dt.timedelta(days=3)).isocalendar(); return f'{n}-{y}'


def amounts(mm, sn, lang):  # « · 12 мм · снег 5 см»: how much falls (rain in mm, snow in cm)
    out = ''
    if mm is not None and np.isfinite(mm) and mm >= 0.5: out += f" · {mm:.0f} {'мм' if lang == 'ru' else 'mm'}"
    if sn is not None and np.isfinite(sn) and sn >= 0.5: out += f" · {'снег' if lang == 'ru' else 'qor'} {sn:.0f} {'см' if lang == 'ru' else 'sm'}"
    return out


def cloud_veil(ax, C, cc, a_in=1.0):  # the cloud cover (%) as a soft grey veil, thicker where the sky is more covered
    v = np.zeros(cc.shape + (4,), np.float32); v[..., :3] = (0.58, 0.62, 0.68); v[..., 3] = np.clip((cc - 45) / 55, 0, 1) ** 1.2 * 0.3 * a_in
    ax.imshow(v, extent=(C['LONu'][0], C['LONu'][-1], C['LATu'][0], C['LATu'][-1]), origin='lower', interpolation='bicubic', aspect='auto', zorder=2.5)
    ax.set_xlim(*C['lon_ext']); ax.set_ylim(LAT_A, LAT_B); ax.set_aspect(1 / PV.COSL)


def deg(v):
    v = int(round(v)); return f'{v:+d}°' if v else '0°'


def grids(D):
    """Each week: % of the normal precipitation, mean temperature and its difference from the normal, on the map's fine grid."""
    nl, no = len(LATS), len(LONS); out = []
    LONu = np.linspace(48, 82, 340); LATu = np.linspace(LAT_A, LAT_B, 120)
    LO, LA = np.meshgrid(LONu, LATu)
    def up(v):
        A = np.array([np.nan if x is None else x for x in v], float).reshape(nl, no)
        if np.isnan(A).all(): return np.full(LO.shape, np.nan)
        A = np.where(np.isnan(A), np.nanmean(A), A)
        f = RegularGridInterpolator((LATS, LONS), A, bounds_error=False, fill_value=None)
        return gaussian_filter(f(np.stack([np.clip(LA, LATS[0], LATS[-1]), np.clip(LO, LONS[0], LONS[-1])], -1)), 2.0)
    # the normal of each forecast week = mean − anomaly; the past week borrows the normal of the first forecast week
    norm0 = None
    for w in D['weeks']:
        if w['kind'] == 'fc': norm0 = [None if a is None or b is None else a - b for a, b in zip(w['pr'], w['pa'])]; break
    for w in D['weeks']:
        pr = up(w['pr']); nm = up([None if a is None or b is None else a - b for a, b in zip(w['pr'], w['pa'])] if w['pa'] else norm0 or w['pr'])
        pct = np.where(nm >= 1.0, 100 * pr / np.maximum(nm, 1e-3), np.where(pr >= 2, 200, 100))  # deserts with ~0 mm normal: around the normal unless it rains
        out.append(dict(pct=np.clip(pct, 0, 1000), t=up(w['t']), ta=up(w['ta']) if w['ta'] else None, pr=pr, nm=nm, sn=up(w['sn']) if w.get('sn') else None, cc=up(w['cc']) if w.get('cc') else None))
    return out, LONu, LATu


LAT_A, LAT_B = PV.LAT0, PV.LAT1


def draw(job):
    lang, i = job; C = CTX; V = C['videos'][lang]; fr = V['frames'][i]; X = TX[lang]
    fig = plt.figure(figsize=(W / PV.DPI, H / PV.DPI), dpi=PV.DPI); fig.patch.set_facecolor('white')
    ax = fig.add_axes(PV.MAP); x0, x1 = C['lon_ext']; ax.set_xlim(x0, x1); ax.set_ylim(LAT_A, LAT_B); ax.set_aspect(1 / PV.COSL); ax.axis('off')
    for r in C['sea']: ax.fill(r[:, 0], r[:, 1], fc=PV.SEA, ec='#b9cfe3', lw=0.6, zorder=0.5)
    a_in = fr.get('fade', 1.0)
    ax.contourf(C['LONu'], C['LATu'], fr['pct'], levels=PCT_LV, cmap=ListedColormap(PCT_COL), norm=BoundaryNorm(PCT_LV, len(PCT_COL)), zorder=2, alpha=0.9 * a_in, antialiased=True)
    ax.contour(C['LONu'], C['LATu'], fr['pct'], levels=[80, 120], colors=['#c9a77a', '#8fb6dc'], linewidths=0.8, alpha=0.8 * a_in, zorder=2.05)
    if fr.get('cc') is not None: cloud_veil(ax, C, fr['cc'], a_in)
    for rings, col, lw, z in C['borders']: ax.add_collection(LineCollection(rings, colors=col, linewidths=lw, zorder=z, capstyle='round', joinstyle='round'))
    L = 0 if lang == 'ru' else 1
    labs = [f"{tw[L]}  {p_:.0f}%" + ('' if d_ is None or not np.isfinite(d_) else f" ({deg(d_)})") + amounts(m_, s_, lang) for tw, (p_, t_, d_, m_, s_) in zip(PV.TOWNS, fr['towns'])]
    offs = PV.place(ax, [(tw[3], tw[2], lb, 17 if tw[0] == 'Ташкент' else 13.5, tw[0] == 'Ташкент', PV.OFF[tw[0]]) for tw, lb in zip(PV.TOWNS, labs)], fig)
    for tw, (p_, t_, d_, m_, s_), (dx, dy, ha, va), lab_ in zip(PV.TOWNS, fr['towns'], offs, labs):
        main = tw[0] == 'Ташкент'
        tt = deg(t_)
        ax.annotate(tt, (tw[3], tw[2]), ha='center', va='center', fontsize=15 if main else 11.5, fontweight='bold', color='white', zorder=8.5,
                    bbox=dict(boxstyle='circle,pad=0.38' if main else 'circle,pad=0.32', fc=PV.tcol(t_), ec=PV.ORANGE if main else 'white', lw=3 if main else 2))
        ec = '#a0632c' if p_ < 80 else '#1c63c0' if p_ > 120 else '#c9d2db'
        sub = '' if d_ is None or not np.isfinite(d_) else f" ({deg(d_)})"
        ax.annotate(lab_, (tw[3], tw[2]), xytext=(dx, dy), textcoords='offset pixels', ha=ha, va=va, fontsize=17 if main else 13.5,
                    fontweight='bold' if main else 'semibold', color='#1f2933' if main else '#2f3a46', zorder=9,
                    bbox=dict(boxstyle='round,pad=0.3,rounding_size=0.7', fc='#eef1f4', ec=PV.ORANGE if main else 'none', lw=2.0 if main else 0, alpha=0.62))
    PV.brand(ax, 0.995, 0.01, 'Bot - @ObHavo_ECMWF_bot · Kanal - @osmon_obhavo', transform=ax.transAxes, ha='right', va='bottom', fontsize=11, color=PV.FAINT, zorder=9)
    # header
    fig.patches.append(Rectangle((0, 0.906), 1, 0.094, transform=fig.transFigure, fc=PV.NAVY, ec='none', zorder=-1))
    fig.text(0.016, 0.953, 'OSMON', fontsize=22, fontweight='bold', color=PV.ORANGE, va='center')
    fig.text(0.093, 0.953, X['title'], fontsize=22, fontweight='bold', color='white', va='center')
    fig.text(0.984, 0.968, fr['when'], fontsize=24, fontweight='bold', color='#ffd29c', ha='right', va='center')
    fig.text(0.984, 0.928, fr['sub'], fontsize=14, color='#a9bdd6', ha='right', va='center')
    fig.patches.append(Rectangle((0, 0.903), 1, 0.004, transform=fig.transFigure, fc='#2c3e57', ec='none', zorder=0))
    fig.patches.append(Rectangle((0, 0.903), fr['prog'], 0.004, transform=fig.transFigure, fc=PV.ORANGE, ec='none', zorder=0.1))
    # legend
    fig.text(0.016, 0.183, X['leg'], fontsize=11.5, fontweight='bold', color=PV.INK, va='center')
    labs = ['<25', '25–50', '50–80', '80–120', '120–150', '150–200', '200–300', '>300']
    for k, (c, lab) in enumerate(zip(PCT_COL, labs)):
        xx = 0.215 + k * 0.047
        fig.patches.append(FancyBboxPatch((xx, 0.171), 0.044, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc=c, ec='#c9d2db' if c == '#ffffff' else 'none'))
        fig.text(xx + 0.022, 0.183, lab, fontsize=10.5, fontweight='bold', color='white' if k in (0, 6, 7) else PV.INK, ha='center', va='center')
    fig.text(0.984, 0.183, X['circ'], fontsize=12, color=PV.MUTED, ha='right', va='center')
    ax.text(0.005, 0.01, X['src'], transform=ax.transAxes, ha='left', va='bottom', fontsize=10, color=PV.FAINT, zorder=9)
    # Tashkent week by week
    fig.text(0.016, 0.152, X['chart'], fontsize=12, fontweight='bold', color=PV.INK, va='center')
    bx = fig.add_axes([0.035, 0.035, 0.93, 0.1]); bx.set_facecolor('none')
    n = len(C['tp']); xs = np.arange(n); tp = np.array(C['tp']); tt = np.array(C['tt'])
    cols = [PCT_COL[int(np.clip(np.searchsorted(PCT_LV, v, side='right') - 1, 0, 7))] for v in tp]
    bx.bar(xs, np.minimum(tp, 300), width=0.62, color=cols, edgecolor='#c9d2db', lw=0.8, zorder=2)
    bx.axhline(100, color=PV.MUTED, lw=1, ls=(0, (4, 3)), zorder=1.5)
    for x_, v in zip(xs, tp): bx.text(x_, min(v, 300) + 8, f'{v:.0f}%', ha='center', va='bottom', fontsize=11, fontweight='bold', color=PV.INK, zorder=4)
    s = fr['s']; bx.axvspan(s - 0.45, s + 0.45, color=PV.ORANGE, alpha=0.15, lw=0, zorder=1)
    bx.add_patch(Rectangle((s - 0.45, 0), 0.9, 340, fill=False, ec=PV.ORANGE, lw=2, zorder=5))
    bx.set_ylim(0, 380); bx.set_xlim(-0.6, n - 0.4); bx.set_yticks([100]); bx.set_yticklabels(['100%'], fontsize=10, color=PV.FAINT); bx.tick_params(length=0)
    bx.set_xticks(xs); bx.set_xticklabels(C['wlab'][lang], fontsize=11, color=PV.MUTED)
    for sp in bx.spines.values(): sp.set_visible(False)
    tx = bx.twinx(); lo, hi = np.nanmin(tt), np.nanmax(tt); pad = max(2, (hi - lo) * 0.3)
    tx.plot(xs, tt, color=PV.TEMP, lw=2.4, marker='o', ms=7, mfc='white', mew=2, zorder=6); tx.set_ylim(lo - pad - 1.3 * (hi - lo + 2 * pad), hi + pad)  # the line in the upper part, over the bars
    for x_, v in zip(xs, tt): tx.annotate(deg(v), (x_, v), xytext=(16, 0), textcoords='offset points', fontsize=12, fontweight='bold', color=PV.TEMP, va='center',
                                          path_effects=[pe.withStroke(linewidth=3, foreground='white')], zorder=7)
    tx.set_yticks([]); [sp.set_visible(False) for sp in tx.spines.values()]
    if fr.get('card') == 'intro':
        a = fr['a']; fig.patches.append(Rectangle((0, 0.205), 1, 0.701, transform=fig.transFigure, fc='white', alpha=0.86 * a, ec='none', zorder=30))
        fig.text(0.5, 0.64, 'OSMON', fontsize=44, fontweight='bold', color=PV.ORANGE, ha='center', va='center', alpha=a, zorder=31)
        fig.text(0.5, 0.56, X['intro1'], fontsize=40, fontweight='bold', color=PV.INK, ha='center', va='center', alpha=a, zorder=31)
        fig.text(0.5, 0.49, X['intro2'], fontsize=26, color=PV.MUTED, ha='center', va='center', alpha=a, zorder=31)
    if fr.get('card') == 'end':
        fig.patches.append(Rectangle((0, 0.205), 1, 0.701, transform=fig.transFigure, fc='white', alpha=0.9, ec='none', zorder=30))
        fig.text(0.38, 0.70, 'OSMON', fontsize=44, fontweight='bold', color=PV.ORANGE, ha='center', va='center', zorder=31)
        fig.text(0.38, 0.60, X['end1'], fontsize=30, fontweight='bold', color=PV.INK, ha='center', va='center', zorder=31)
        fig.text(0.38, 0.53, X['end2'], fontsize=26, color=PV.MUTED, ha='center', va='center', zorder=31)
        PV.qr2(fig)
    fig.savefig(pathlib.Path(V['dir']) / f'{i:04d}.png', dpi=PV.DPI, facecolor='white'); plt.close(fig)


def setup(D, outd, langs):
    G_, LONu, LATu = grids(D)
    at = lambda a, la, lo: float(a[np.abs(LATu - la).argmin(), np.abs(LONu - lo).argmin()]) if a is not None else None
    G = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']; GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']
    WAT = json.load(open(ROOT / 'prob' / 'geo_water.json'))
    sea = [np.asarray(r) for r in WAT['ocean']] + [np.asarray(l_['r']) for l_ in WAT['lakes']]
    UZ = [np.asarray(r) for r in G['UZ']['rings']]; NB = [np.asarray(r) for k, c in G.items() if k != 'UZ' for r in c['rings']]
    A1 = [np.asarray(r) for a in GA['adm1'] for r in a['r']]
    span = (LAT_B - LAT_A) / PV.COSL * (PV.MAP[2] * W) / (PV.MAP[3] * H); lc = 64.8
    tash = PV.TOWNS[0]; starts = [dt.date.fromisoformat(w['start']) for w in D['weeks']]
    wlab = {l: [(f"{TX[l]['week'].format(n=wk(s))}\n{s:%d.%m}–{s + dt.timedelta(days=6):%d.%m}") for s in starts] for l in TX}
    CTX.update(LONu=LONu, LATu=LATu, sea=sea, borders=[(NB, '#a3acb6', 1.0, 3), (A1, '#b7c0ca', 0.8, 3.05), (UZ, '#1c2633', 2.6, 3.3)], lon_ext=(lc - span / 2, lc + span / 2),
               tp=[at(g['pct'], tash[2], tash[3]) for g in G_], tt=[at(g['t'], tash[2], tash[3]) for g in G_], wlab=wlab, qr=PV.qr('https://t.me/ObHavo_ECMWF_bot'), videos={})
    n = len(G_)
    for lang in langs:
        X = TX[lang]; frames = []
        for k, (w, g, s) in enumerate(zip(D['weeks'], G_, starts)):
            e = s + dt.timedelta(days=6); iso = (s + dt.timedelta(days=3)).isocalendar()  # the ISO week of the week's middle day
            when = f"{X['week'].format(n=wk(s))} · {s:%d.%m}–{e:%d.%m}"
            sub = X['past'] if w['kind'] == 'past' else X['fc']
            towns = lambda gg: [(at(gg['pct'], tw[2], tw[3]), at(gg['t'], tw[2], tw[3]), at(gg['ta'], tw[2], tw[3]) if gg['ta'] is not None else None,
                                 at(gg['pr'], tw[2], tw[3]) if gg.get('pr') is not None else None, at(gg['sn'], tw[2], tw[3]) if gg.get('sn') is not None else None) for tw in PV.TOWNS]
            frames.append(dict(pct=g['pct'], cc=g.get('cc'), s=k, when=when, sub=sub, prog=(k + 1) / n, towns=towns(g), d=3.0))
            if k + 1 < n:  # the move to the next week: the map blends, the numbers follow
                g2 = G_[k + 1]
                for a in np.linspace(0, 1, 9)[1:-1]:
                    gm = dict(pct=(1 - a) * g['pct'] + a * g2['pct'], t=(1 - a) * g['t'] + a * g2['t'], ta=None if g['ta'] is None or g2['ta'] is None else (1 - a) * g['ta'] + a * g2['ta'],
                              pr=(1 - a) * g['pr'] + a * g2['pr'], sn=None if g.get('sn') is None or g2.get('sn') is None else (1 - a) * g['sn'] + a * g2['sn'], cc=None if g.get('cc') is None or g2.get('cc') is None else (1 - a) * g['cc'] + a * g2['cc'])
                    frames.append(dict(frames[-1] if a < 0.5 else dict(pct=None), pct=gm['pct'], cc=gm['cc'], towns=towns(gm), d=0.06, s=k if a < 0.5 else k + 1,
                                       when=when if a < 0.5 else None, sub=sub, prog=(k + 1 + a) / n))
        for j, f_ in enumerate(frames):  # fill the header of the second half of each move from the next week
            if f_.get('when') is None: nx = next(f2 for f2 in frames[j:] if f2.get('when') is not None and f2['d'] >= 1); f_.update(when=nx['when'], sub=nx['sub'])
        frames[-1] = dict(frames[-1], d=3.5)
        intro = [dict(frames[0], card='intro', a=1.0, fade=0.0, d=1.6)] + [dict(frames[0], card='intro', a=float(a_), fade=float(1 - a_), d=0.07) for a_ in np.linspace(1, 0, 9)[1:]]
        CTX['videos'][lang] = dict(frames=intro + frames + [dict(frames[-1], card='end', d=4.0)], dir=tempfile.mkdtemp(), out=str(pathlib.Path(outd) / f'weeks_{lang}.mp4'))


SN_LV = [0.5, 2, 5, 10, 20, 500]
SN_COL = ['#f1e3f5', '#dfb6ea', '#c486da', '#a055c2', '#6c2795']
MM_LV = [0.5, 1, 3, 5, 10, 20, 500]
MM_COL = ['#d4e9f9', '#93c6ee', '#4a98e0', '#1c63c0', '#173f97', '#5b2fa8']


def draw_day(job):
    """One frame of a week-by-day video: the day's precipitation (mm) on the map, the day's mean temperature at the towns."""
    lang, i = job; C = CTX; V = C['dvideos'][lang]; fr = V['frames'][i]; X = TX[lang]
    fig = plt.figure(figsize=(W / PV.DPI, H / PV.DPI), dpi=PV.DPI); fig.patch.set_facecolor('white')
    ax = fig.add_axes(PV.MAP); x0, x1 = C['lon_ext']; ax.set_xlim(x0, x1); ax.set_ylim(LAT_A, LAT_B); ax.set_aspect(1 / PV.COSL); ax.axis('off')
    for r in C['sea']: ax.fill(r[:, 0], r[:, 1], fc=PV.SEA, ec='#b9cfe3', lw=0.6, zorder=0.5)
    if np.nanmax(fr['mm']) >= MM_LV[0]:
        ax.contourf(C['LONu'], C['LATu'], fr['mm'], levels=MM_LV, colors=MM_COL, zorder=2, alpha=0.9, antialiased=True)
    if fr.get('sn') is not None and np.nanmax(fr['sn']) >= SN_LV[0]:  # the snow (cm) in violet over the rain
        ax.contourf(C['LONu'], C['LATu'], fr['sn'], levels=SN_LV, colors=SN_COL, zorder=2.1, alpha=0.9, antialiased=True)
    if fr.get('cc') is not None: cloud_veil(ax, C, fr['cc'])
    for rings, col, lw, z in C['borders']: ax.add_collection(LineCollection(rings, colors=col, linewidths=lw, zorder=z, capstyle='round', joinstyle='round'))
    L = 0 if lang == 'ru' else 1
    labs = [tw[L] + amounts(m_, s_, lang) + (f" · {deg(x_)}/{deg(n_)}" if x_ is not None and n_ is not None else '') for tw, (m_, t_, s_, x_, n_) in zip(PV.TOWNS, fr['towns'])]
    offs = PV.place(ax, [(tw[3], tw[2], lb, 17 if tw[0] == 'Ташкент' else 13.5, tw[0] == 'Ташкент', PV.OFF[tw[0]]) for tw, lb in zip(PV.TOWNS, labs)], fig)
    for tw, (m_, t_, s_, x_, n_), (dx, dy, ha, va), lb in zip(PV.TOWNS, fr['towns'], offs, labs):
        main = tw[0] == 'Ташкент'
        ax.annotate(deg(t_), (tw[3], tw[2]), ha='center', va='center', fontsize=15 if main else 11.5, fontweight='bold', color='white', zorder=8.5,
                    bbox=dict(boxstyle='circle,pad=0.38' if main else 'circle,pad=0.32', fc=PV.tcol(t_), ec=PV.ORANGE if main else 'white', lw=3 if main else 2))
        ax.annotate(lb, (tw[3], tw[2]), xytext=(dx, dy), textcoords='offset pixels', ha=ha, va=va, fontsize=17 if main else 13.5, fontweight='bold' if main else 'semibold', color='#1f2933', zorder=9,
                    bbox=dict(boxstyle='round,pad=0.3,rounding_size=0.7', fc='#eef1f4', ec=PV.ORANGE if main else 'none', lw=2.0 if main else 0, alpha=0.7))
    PV.brand(ax, 0.995, 0.01, 'Bot - @ObHavo_ECMWF_bot · Kanal - @osmon_obhavo', transform=ax.transAxes, ha='right', va='bottom', fontsize=11, color=PV.FAINT, zorder=9)
    ax.text(0.005, 0.01, X['src'], transform=ax.transAxes, ha='left', va='bottom', fontsize=10, color=PV.FAINT, zorder=9)
    fig.patches.append(Rectangle((0, 0.906), 1, 0.094, transform=fig.transFigure, fc=PV.NAVY, ec='none', zorder=-1))
    fig.text(0.016, 0.953, 'OSMON', fontsize=22, fontweight='bold', color=PV.ORANGE, va='center')
    fig.text(0.093, 0.953, f"{X['dtitle']} · {V['wname']}", fontsize=22, fontweight='bold', color='white', va='center')
    fig.text(0.984, 0.968, fr['when'], fontsize=24, fontweight='bold', color='#ffd29c', ha='right', va='center')
    fig.text(0.984, 0.928, X['fc'], fontsize=14, color='#a9bdd6', ha='right', va='center')
    fig.patches.append(Rectangle((0, 0.903), 1, 0.004, transform=fig.transFigure, fc='#2c3e57', ec='none', zorder=0))
    fig.patches.append(Rectangle((0, 0.903), fr['prog'], 0.004, transform=fig.transFigure, fc=PV.ORANGE, ec='none', zorder=0.1))
    fig.text(0.016, 0.183, X['dleg'], fontsize=12, fontweight='bold', color=PV.INK, va='center')
    xs_ = 0.14 + 6 * 0.05 + 0.01; fig.text(xs_, 0.183, X['sleg'], fontsize=12, fontweight='bold', color=PV.INK, va='center')
    for k, (c, lab) in enumerate(zip(SN_COL, ['0,5–2', '2–5', '5–10', '10–20', '>20'])):
        xx = xs_ + 0.07 + k * 0.045
        fig.patches.append(FancyBboxPatch((xx, 0.171), 0.042, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc=c, ec='none'))
        fig.text(xx + 0.021, 0.183, lab, fontsize=10.5, fontweight='bold', color='white' if k >= 2 else PV.INK, ha='center', va='center')
    fig.patches.append(FancyBboxPatch((0.86, 0.171), 0.022, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc='#b9bfc7', ec='none'))
    fig.text(0.886, 0.183, X['clouds'], fontsize=12, color=PV.MUTED, va='center')
    for k, (c, lab) in enumerate(zip(MM_COL, ['0,5–1', '1–3', '3–5', '5–10', '10–20', '>20'])):
        xx = 0.14 + k * 0.05
        fig.patches.append(FancyBboxPatch((xx, 0.171), 0.047, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc=c, ec='none'))
        fig.text(xx + 0.0235, 0.183, lab, fontsize=10.5, fontweight='bold', color='white' if k >= 2 else PV.INK, ha='center', va='center')
    fig.text(0.016, 0.152, X['dchart'], fontsize=12, fontweight='bold', color=PV.INK, va='center')
    bx = fig.add_axes([0.035, 0.035, 0.93, 0.1]); bx.set_facecolor('none')
    tp, tt, ts = np.array(V['tp']), np.array(V['tt']), np.array(V['ts']); xs = np.arange(len(tp)); top = max((tp + ts).max(), 2)
    bx.bar(xs, np.maximum(tp, 0.15), width=0.62, color='#4a98e0', zorder=2)
    bx.bar(xs, ts, bottom=tp, width=0.62, color='#a055c2', zorder=2)
    for x_, v, sv, cv in zip(xs, tp, ts, V['tc']):
        t_ = ' · '.join([x for x in [f"{v:.0f} {'мм' if lang == 'ru' else 'mm'}" if v >= 0.5 else '', f"{'снег' if lang == 'ru' else 'qor'} {sv:.0f} {'см' if lang == 'ru' else 'sm'}" if sv >= 0.5 else ''] if x]) or '—'
        bx.text(x_, v + sv + top * 0.04, t_ + (f"\n☁ {cv:.0f}%" if cv is not None and False else ''), ha='center', va='bottom', fontsize=10.5, fontweight='bold', color=PV.INK, zorder=4)
    s = fr['s']; bx.add_patch(Rectangle((s - 0.45, 0), 0.9, top * 1.5, fill=False, ec=PV.ORANGE, lw=2, zorder=5))
    bx.set_ylim(0, top * 2.4); bx.set_xlim(-0.6, len(tp) - 0.4); bx.set_yticks([]); bx.tick_params(length=0)
    bx.set_xticks(xs); bx.set_xticklabels(V['dlab'], fontsize=11, color=PV.MUTED)
    for sp in bx.spines.values(): sp.set_visible(False)
    tx = bx.twinx(); lo, hi = np.nanmin(tt), np.nanmax(tt); pad = max(2, (hi - lo) * 0.3)
    TX_ = np.array([v if v is not None else np.nan for v in V['tx']]); TN_ = np.array([v if v is not None else np.nan for v in V['tn']])
    if np.isfinite(TX_).any(): lo, hi = np.nanmin(TN_), np.nanmax(TX_); pad = max(2, (hi - lo) * 0.3)
    tx.set_ylim(lo - pad - 1.3 * (hi - lo + 2 * pad), hi + pad)
    if np.isfinite(TX_).any():  # by day (orange) and at night (blue)
        tx.plot(xs, TX_, color=PV.TEMP, lw=2.4, marker='o', ms=7, mfc='white', mew=2, zorder=6); tx.plot(xs, TN_, color='#3f7fd6', lw=2.0, marker='o', ms=6, mfc='white', mew=2, zorder=6)
        for x_, a_, b_ in zip(xs, TX_, TN_):
            tx.annotate(deg(a_), (x_, a_), xytext=(14, 2), textcoords='offset points', fontsize=11.5, fontweight='bold', color=PV.TEMP, va='center', path_effects=[pe.withStroke(linewidth=3, foreground='white')], zorder=7)
            tx.annotate(deg(b_), (x_, b_), xytext=(14, -2), textcoords='offset points', fontsize=11, fontweight='bold', color='#3f7fd6', va='center', path_effects=[pe.withStroke(linewidth=3, foreground='white')], zorder=7)
    else:
        tx.plot(xs, tt, color=PV.TEMP, lw=2.4, marker='o', ms=7, mfc='white', mew=2, zorder=6)
    tx.set_yticks([]); [sp.set_visible(False) for sp in tx.spines.values()]
    fig.savefig(pathlib.Path(V['dir']) / f'{i:04d}.png', dpi=PV.DPI, facecolor='white'); plt.close(fig)


def setup_days(D, outd, langs):
    """One video per coming ISO week: its seven days one after another (the bot sends it when that week is chosen)."""
    if not D.get('days'): return []
    tash = PV.TOWNS[0]; nl, no = len(LATS), len(LONS); LO, LA = np.meshgrid(CTX['LONu'], CTX['LATu'])
    def up(v):
        A = np.array([np.nan if x is None else x for x in v], float).reshape(nl, no)
        if np.isnan(A).all(): return np.zeros(LO.shape)
        A = np.where(np.isnan(A), np.nanmean(A), A); f = RegularGridInterpolator((LATS, LONS), A, bounds_error=False, fill_value=None)
        return gaussian_filter(f(np.stack([np.clip(LA, LATS[0], LATS[-1]), np.clip(LO, LONS[0], LONS[-1])], -1)), 2.0)
    at = lambda a, la, lo: float(a[np.abs(CTX['LATu'] - la).argmin(), np.abs(CTX['LONu'] - lo).argmin()])
    byd = {dt.date.fromisoformat(x['d']): x for x in D['days']}; mon = min(byd); mon -= dt.timedelta(days=mon.weekday()); jobs = []; CTX['dvideos'] = {}
    while mon in byd or mon + dt.timedelta(days=6) in byd:
        ds = [mon + dt.timedelta(days=k) for k in range(7) if mon + dt.timedelta(days=k) in byd]
        if len(ds) >= 4:
            gf = lambda d, k_: up(byd[d][k_]) if byd[d].get(k_) else None
            G_ = [(up(byd[d]['pr']), up(byd[d]['t']), gf(d, 'sn'), gf(d, 'cc'), gf(d, 'tx'), gf(d, 'tn')) for d in ds]; key = wk(mon)
            for lang in langs:
                X = TX[lang]; frames = []
                mix = lambda A, B, a: None if A is None or B is None else (1 - a) * A + a * B
                tv = lambda f, tw: at(f, tw[2], tw[3]) if f is not None else None
                for k, (d, g) in enumerate(zip(ds, G_)):
                    def fr_(g, **kw):
                        mm, t, sn, cc, tx, tn = g; rain = np.clip(mm - (sn if sn is not None else 0) / 0.7, 0, None)  # snow (cm) ≈ 0.7 × its water (mm)
                        return dict(mm=rain, sn=None if sn is None else np.clip(sn, 0, None), cc=cc, towns=[(tv(rain, tw), tv(t, tw), tv(sn, tw), tv(tx, tw), tv(tn, tw)) for tw in PV.TOWNS], **kw)
                    frames.append(fr_(g, s=k, when=f"{X['wd'][d.weekday()]} {d:%d.%m}", prog=(k + 1) / len(ds), d=1.8))
                    if k + 1 < len(ds):
                        g2 = G_[k + 1]
                        for a in np.linspace(0, 1, 7)[1:-1]: frames.append(dict(frames[-1], **{kk: vv for kk, vv in fr_(tuple(mix(A, B, a) for A, B in zip(g, g2))).items()}, d=0.06))
                frames[-1] = dict(frames[-1], d=3.0)
                vid = f'{lang}_{key}'
                CTX['dvideos'][vid] = dict(frames=frames, dir=tempfile.mkdtemp(), out=str(pathlib.Path(outd) / f'wk_{key}_{lang}.mp4'), wname=f"{X['week'].format(n=key)} · {ds[0]:%d.%m}–{mon + dt.timedelta(days=6):%d.%m}",
                                           tp=[max(0.0, at(g[0], tash[2], tash[3]) - (at(g[2], tash[2], tash[3]) / 0.7 if g[2] is not None else 0)) for g in G_], tt=[at(g[1], tash[2], tash[3]) for g in G_],
                                           ts=[at(g[2], tash[2], tash[3]) if g[2] is not None else 0 for g in G_], tx=[at(g[4], tash[2], tash[3]) if g[4] is not None else None for g in G_],
                                           tn=[at(g[5], tash[2], tash[3]) if g[5] is not None else None for g in G_], tc=[at(g[3], tash[2], tash[3]) if g[3] is not None else None for g in G_], dlab=[f"{X['wd'][d.weekday()]}\n{d:%d.%m}" for d in ds])
                jobs += [(vid, i) for i in range(len(frames))]
        mon += dt.timedelta(days=7)
    return jobs


def draw_day_job(job):
    vid, i = job; lang = vid.split('_')[0]; CTX['dvideos'][lang] = CTX['dvideos'][vid]; draw_day((lang, i))


if __name__ == '__main__':
    outd = pathlib.Path(sys.argv[1]); langs = (sys.argv[2] if len(sys.argv) > 2 else 'ru,uz').split(','); outd.mkdir(parents=True, exist_ok=True)
    cache = sys.argv[sys.argv.index('--cache') + 1] if '--cache' in sys.argv else None
    D = json.load(open(cache)) if cache and pathlib.Path(cache).exists() else fetch()
    json.dump(D, open(outd / 'weeks.json', 'w'), separators=(',', ':'))
    print('weeks', [(w['kind'], w['start']) for w in D['weeks']], flush=True)
    setup(D, outd, langs)
    PV.CTX.update(videos=CTX['videos'])  # PV.encode reads its own CTX
    jobs = [(l, i) for l in langs for i in range(len(CTX['videos'][l]['frames']))]; print(len(jobs), 'frames', flush=True)
    with mp.get_context('fork').Pool(max(1, os.cpu_count() or 1)) as pool:
        list(pool.imap_unordered(draw, jobs, chunksize=4))
        for r in pool.imap_unordered(PV.encode, langs): print(r, flush=True)
    # the week-by-day videos (each coming ISO week)
    dj = setup_days(D, outd, langs)
    PV.CTX.update(videos=CTX['dvideos'])
    with mp.get_context('fork').Pool(max(1, os.cpu_count() or 1)) as pool:
        list(pool.imap_unordered(draw_day_job, dj, chunksize=4))
        for r in pool.imap_unordered(PV.encode, sorted({v for v, _ in dj})): print(r, flush=True)
