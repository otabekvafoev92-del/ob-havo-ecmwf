"""Where the moist air comes from, the clouds, the precipitation and the weather (fronts, highs and lows), hour by hour for
15 days over Uzbekistan, in the look of the 15-day chance-of-precipitation video (tools/prob15_video.py): white map,
navy header with the hour, the towns with the temperature in a circle and the weather at each, Tashkent's chart below.
Data: ECMWF IFS open data (prob/moisture.py: HRES to 10 days, then one ensemble member to 15 days), the moisture paths
48 h back from the towns' heaviest rain (prob/trajectory.py).
Usage: python tools/moist15_video.py prob.npz out ru,uz [--fields saved.npz]  →  out/moist15_{lang}.mp4"""
import sys, os, json, pathlib, tempfile, datetime as dt, multiprocessing as mp
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'prob')); sys.path.insert(0, str(ROOT / 'tools'))
import prob15_video as PV
from prob15_video import plt, matplotlib, ListedColormap, BoundaryNorm, LineCollection, Rectangle, FancyBboxPatch, pe
from scipy.ndimage import zoom, gaussian_filter, maximum_filter, minimum_filter

W, H = PV.W, PV.H
LAT_A, LAT_B = PV.LAT0, PV.LAT1
TCWV_LV = [0, 10, 15, 20, 26, 33, 41, 80]
TCWV_COL = ['#ffffff', '#f3f8f4', '#e2f1e8', '#c6e7d6', '#a2d7bf', '#76c1a5', '#4ba48b']  # dry white → moist green
PR_LV = [0.3, 1, 2, 4, 7, 12, 200]
RAIN = ['#b9e0fb', '#7cc2f2', '#3f96e6', '#1f6fd0', '#1550a8', '#0d3580']
SNOW = ['#eadcff', '#d3bcfa', '#b897f0', '#9b72e2', '#7a4bc8', '#5a2da0']
COLD, WARM = '#2f63d6', '#d8432b'
TX = {'ru': dict(title='Откуда идёт влага · тучи и осадки · 15 дней', tz='по Ташкенту', day='день {i} из {n}', moist='Влажный воздух', dry='сухо', wet='влажно', cl='тучи',
                 rain='дождь', snow='снег', mm='мм за 3 ч', cold='холодный фронт', warm='тёплый фронт', hi='В', lo='Н', hil='антициклон: ясно', lol='циклон: тучи, осадки',
                 path='путь влаги к городу', src='Влага: {s}', wind='тонкие линии — ветер на высоте ~3 км (куда течёт влага)', chart='Ташкент: осадки (мм за 3 ч, столбики) и температура (линия)',
                 w_dry='сухо', w_cl='облачно', w_fog='туман', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], intro1='Откуда идёт влага', intro2='тучи, осадки и фронты на 15 дней по часам',
                 end1='Погода в вашем районе и посёлке', end2='в Telegram-боте @ObHavo_ECMWF_bot', models='ECMWF IFS (до 10 дней), далее ансамбль ECMWF · Osmon'),
      'uz': dict(title='Namlik qayerdan keladi · bulut va yog‘in · 15 kun', tz='Toshkent vaqti', day='{i}-kun / {n}', moist='Nam havo', dry='quruq', wet='nam', cl='bulut',
                 rain='yomg‘ir', snow='qor', mm='mm / 3 soat', cold='sovuq front', warm='iliq front', hi='Y', lo='P', hil='antisiklon: ochiq', lol='siklon: bulut, yog‘in',
                 path='namlikning shaharga yo‘li', src='Namlik: {s}', wind='ingichka chiziqlar — ~3 km balandlikdagi shamol (namlik oqimi)', chart='Toshkent: yog‘in (mm / 3 soat, ustunlar) va harorat (chiziq)',
                 w_dry='quruq', w_cl='bulutli', w_fog='tuman', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'], intro1='Namlik qayerdan keladi', intro2='15 kunga soatma-soat bulut, yog‘in va frontlar',
                 end1='Tumaningiz va qishlog‘ingiz ob-havosi', end2='Telegram-botda: @ObHavo_ECMWF_bot', models='ECMWF IFS (10 kungacha), keyin ECMWF ansambli · Osmon')}
CTX = {}


def level(v, lv, pal):
    return pal[int(np.clip(np.searchsorted(lv, v, side='right') - 1, 0, len(pal) - 1))] if v >= lv[0] else None


def draw(job):
    lang, i = job; C = CTX; V = C['videos'][lang]; fr = V['frames'][i]; X = TX[lang]
    fig = plt.figure(figsize=(W / PV.DPI, H / PV.DPI), dpi=PV.DPI); fig.patch.set_facecolor('white')
    ax = fig.add_axes(PV.MAP); x0, x1 = C['lon_ext']; ax.set_xlim(x0, x1); ax.set_ylim(LAT_A, LAT_B); ax.set_aspect(1 / PV.COSL); ax.axis('off')
    LO, LA = C['LONu'], C['LATu']; f = {k: v.astype(np.float32) for k, v in C['fields'][fr['k']].items()}; a_in = fr.get('fade', 1.0)
    ext_ = (LO[0], LO[-1], LA[0], LA[-1])
    # the water vapour as a smooth wash: dry air white, moist air green
    ax.imshow(C['wv_cmap'](np.clip((f['tcwv'] - 8) / 37, 0, 1)), extent=ext_, origin='lower', interpolation='bicubic', aspect='auto', zorder=0.3, alpha=a_in)
    for r in C['sea']: ax.fill(r[:, 0], r[:, 1], fc=PV.SEA, ec='#b9cfe3', lw=0.6, zorder=0.5, alpha=0.8)
    # clouds: a soft grey veil, thicker where the cloud is thicker
    cl = np.zeros(f['tcc'].shape + (4,), np.float32); cl[..., :3] = (0.56, 0.6, 0.66); cl[..., 3] = np.clip((f['tcc'] - 0.35) / 0.65, 0, 1) ** 1.3 * 0.42 * a_in
    ax.imshow(cl, extent=ext_, origin='lower', interpolation='bicubic', aspect='auto', zorder=1.2)
    snow = f['t2'] <= 0.5; Pr, Ps = np.where(snow, 0, f['pr']), np.where(snow, f['pr'], 0)
    for P_, pal, z in ((Pr, RAIN, 2), (Ps, SNOW, 2.1)):
        if P_.max() >= PR_LV[0]:
            ax.contourf(LO, LA, P_, levels=PR_LV, colors=pal, alpha=0.9 * a_in, zorder=z, antialiased=True)
            ax.contour(LO, LA, P_, levels=PR_LV[:1], colors=[pal[2]], linewidths=0.8, alpha=0.7 * a_in, zorder=z + 0.01)
    ax.set_xlim(x0, x1); ax.set_ylim(LAT_A, LAT_B); ax.set_aspect(1 / PV.COSL)
    # the wind at ~3 km as flowing streaks: each particle drifts with the wind and leaves a fading trail
    tr = C['trails'][fr['p']].astype(np.float32); TRn = tr.shape[0]
    seg = np.stack([tr[:-1], tr[1:]], axis=2)  # (TR-1, N, 2 points, 2)
    ok = (np.abs(seg[:, :, 1] - seg[:, :, 0]).max(-1) < 0.8)
    sp_ = np.hypot(*(seg[:, :, 1] - seg[:, :, 0]).T).T  # degrees per half hour
    alph = (np.arange(1, TRn) / (TRn - 1))[:, None] ** 1.6 * np.clip((sp_ - 0.03) / 0.22, 0, 1) * 0.42 * a_in
    rgba = np.zeros(alph.shape + (4,), np.float32); rgba[..., :3] = matplotlib.colors.to_rgb('#3d5a6c'); rgba[..., 3] = alph
    ax.add_collection(LineCollection(seg[ok], colors=rgba[ok], linewidths=0.9, zorder=2.4, capstyle='round'))
    # fronts with their symbols on the side the front moves to
    for line, kind in C['fronts'].get(fr['fk'], []):
        col = COLD if kind == 'cold' else WARM
        ax.plot(line[:, 0], line[:, 1], color=col, lw=2.8, zorder=3.4, alpha=a_in, solid_capstyle='round', solid_joinstyle='round')
        for poly in front_symbols(line, kind): ax.fill(poly[:, 0], poly[:, 1], color=col, ec='none', zorder=3.45, alpha=a_in)
    # highs and lows
    for x_, y_, hi in fr['hl']:
        ax.text(x_, y_, X['hi'] if hi else X['lo'], fontsize=30, fontweight='bold', color=COLD if hi else WARM, ha='center', va='center', zorder=3.6, alpha=0.45 * a_in)  # semi-transparent: the weather under it shows through
    for rings, col, lw, z in C['borders']: ax.add_collection(LineCollection(rings, colors=col, linewidths=lw, zorder=z, capstyle='round', joinstyle='round'))
    # the moisture's path to a town (from its source, ~2 days back)
    used = []  # the source labels: never on top of each other, never on the map's bottom edge
    for p in fr['paths']:
        xy = np.asarray(p['path'])[:, :2]
        ax.plot(xy[:, 0], xy[:, 1], color=PV.ORANGE, lw=2.6, ls=(0, (6, 3)), zorder=3.8, alpha=p['a'])
        dv = xy[min(2, len(xy) - 1)] - xy[0]; dv = dv / (np.hypot(*dv) + 1e-9)  # the arrow head at the town
        ax.annotate('', xy=xy[0], xytext=xy[0] + 0.45 * dv, arrowprops=dict(arrowstyle='-|>', color=PV.ORANGE, lw=2.6, mutation_scale=24), zorder=3.85, alpha=p['a'])
        sx, sy = float(np.clip(xy[-1, 0], x0 + 1.8, x1 - 1.8)), float(np.clip(xy[-1, 1], LAT_A + 1.0, LAT_B - 0.6))
        while any(abs(sx - ux) < 3.2 and abs(sy - uy) < 0.45 for ux, uy in used): sy += 0.5
        used.append((sx, sy))
        ax.text(sx, sy, X['src'].format(s=p['src'][lang]), fontsize=14, fontweight='bold', color='white', ha='center', va='center', zorder=9.5, alpha=p['a'],
                bbox=dict(boxstyle='round,pad=0.35,rounding_size=0.6', fc=PV.ORANGE, ec='none', alpha=0.95 * p['a']))
    L = 0 if lang == 'ru' else 1
    def wx_(pr_, sn_, cl_, fog_):
        if pr_ >= 0.3: return f"{X['snow'] if sn_ else X['rain']} {pr_:.1f}".replace('.', ',') + (' мм' if lang == 'ru' else ' mm')
        return X['w_fog'] if fog_ else X['w_cl'] if cl_ >= 0.7 else None
    labs = [tw[L] + (f" · {wx_(*v[1:])}" if wx_(*v[1:]) else '') for tw, v in zip(PV.TOWNS, fr['towns'])]
    offs = PV.place(ax, [(tw[3], tw[2], lb, 17 if tw[0] == 'Ташкент' else 13.5, tw[0] == 'Ташкент', PV.OFF[tw[0]]) for tw, lb in zip(PV.TOWNS, labs)], fig)
    for tw, (t_, pr_, sn_, cl_, fog_), (dx, dy, ha, va), lb in zip(PV.TOWNS, fr['towns'], offs, labs):
        main = tw[0] == 'Ташкент'
        ax.annotate(PV_deg(t_), (tw[3], tw[2]), ha='center', va='center', fontsize=15 if main else 11.5, fontweight='bold', color='white', zorder=8.5,
                    bbox=dict(boxstyle='circle,pad=0.38' if main else 'circle,pad=0.32', fc=PV.tcol(t_), ec=PV.ORANGE if main else 'white', lw=3 if main else 2))
        ax.annotate(lb, (tw[3], tw[2]), xytext=(dx, dy), textcoords='offset pixels', ha=ha, va=va, fontsize=17 if main else 13.5,
                    fontweight='bold' if main else 'semibold', color='#1f2933' if main else '#2f3a46', zorder=9, bbox=dict(boxstyle='round,pad=0.3,rounding_size=0.7', fc='#eef1f4', ec=PV.ORANGE if main else 'none', lw=2.0 if main else 0, alpha=0.62))
    ax.text(0.995, 0.01, 't.me/ObHavo_ECMWF_bot', transform=ax.transAxes, ha='right', va='bottom', fontsize=11, color=PV.FAINT, zorder=9)
    # header
    fig.patches.append(Rectangle((0, 0.906), 1, 0.094, transform=fig.transFigure, fc=PV.NAVY, ec='none', zorder=-1))
    fig.text(0.016, 0.953, 'OSMON', fontsize=22, fontweight='bold', color=PV.ORANGE, va='center')
    fig.text(0.093, 0.953, X['title'], fontsize=21, fontweight='bold', color='white', va='center')
    fig.text(0.984, 0.968, fr['when'], fontsize=24, fontweight='bold', color='#ffd29c', ha='right', va='center')
    fig.text(0.984, 0.928, X['tz'] + ' · ' + fr['day'], fontsize=14, color='#a9bdd6', ha='right', va='center')
    fig.patches.append(Rectangle((0, 0.903), 1, 0.004, transform=fig.transFigure, fc='#2c3e57', ec='none', zorder=0))
    fig.patches.append(Rectangle((0, 0.903), fr['prog'], 0.004, transform=fig.transFigure, fc=PV.ORANGE, ec='none', zorder=0.1))
    # legend: two rows
    def chips(x, y, cols, labs, w=0.04, dark_from=3):
        for k, (c, lab) in enumerate(zip(cols, labs)):
            fig.patches.append(FancyBboxPatch((x + k * (w + 0.003), y - 0.012), w, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc=c, ec='#d5dbe1' if k == 0 else 'none'))
            if lab: fig.text(x + k * (w + 0.003) + w / 2, y, lab, fontsize=9.5, fontweight='bold', color='white' if k >= dark_from else PV.INK, ha='center', va='center')
        return x + len(cols) * (w + 0.003)
    y1, y2 = 0.186, 0.156
    fig.text(0.016, y1, X['moist'], fontsize=13, fontweight='bold', color=PV.INK, va='center')
    e = chips(0.105, y1, TCWV_COL[1:], ['', '', '', '', '', ''], w=0.026)
    fig.text(0.105, y1 - 0.02, X['dry'], fontsize=9.5, color=PV.MUTED, va='center'); fig.text(e - 0.003, y1 - 0.02, X['wet'], fontsize=9.5, color=PV.MUTED, va='center', ha='right')
    fig.patches.append(FancyBboxPatch((e + 0.015, y1 - 0.012), 0.04, 0.024, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, fc='#c9cfd6', ec='none'))
    fig.text(e + 0.06, y1, X['cl'], fontsize=12, color=PV.MUTED, va='center')
    fig.text(0.40, y1, X['rain'], fontsize=13, fontweight='bold', color=PV.INK, va='center'); e2 = chips(0.435, y1, RAIN, ['0,3', '1', '2', '4', '7', '12+'], w=0.03, dark_from=2)
    fig.text(e2 + 0.01, y1, X['snow'], fontsize=13, fontweight='bold', color=PV.INK, va='center'); e3 = chips(e2 + 0.04, y1, SNOW, ['0,3', '1', '2', '4', '7', '12+'], w=0.03, dark_from=3)
    fig.text(e3 + 0.006, y1, X['mm'], fontsize=11, color=PV.MUTED, va='center')
    xx = 0.016
    for kind, lab in (('cold', X['cold']), ('warm', X['warm'])):
        col = COLD if kind == 'cold' else WARM
        fig.add_artist(matplotlib.lines.Line2D([xx, xx + 0.03], [y2, y2], color=col, lw=2.6, transform=fig.transFigure))
        fig.add_artist(matplotlib.lines.Line2D([xx + 0.015], [y2], marker='^' if kind == 'cold' else 'o', ms=8, color=col, mec='white', transform=fig.transFigure))
        t = fig.text(xx + 0.036, y2, lab, fontsize=12, color=PV.MUTED, va='center'); xx += 0.036 + 0.0058 * len(lab) + 0.02
    for hi, lab in ((True, X['hil']), (False, X['lol'])):
        fig.text(xx, y2, X['hi'] if hi else X['lo'], fontsize=17, fontweight='bold', color=COLD if hi else WARM, va='center'); fig.text(xx + 0.014, y2, lab, fontsize=12, color=PV.MUTED, va='center'); xx += 0.014 + 0.0058 * len(lab) + 0.02
    fig.add_artist(matplotlib.lines.Line2D([xx, xx + 0.03], [y2, y2], color=PV.ORANGE, lw=2.6, ls=(0, (5, 2.5)), transform=fig.transFigure))
    fig.text(xx + 0.036, y2, X['path'], fontsize=12, color=PV.MUTED, va='center')
    fig.text(0.984, y2, X['wind'], fontsize=11, color=PV.FAINT, ha='right', va='center')
    # Tashkent's chart
    fig.text(0.016, 0.126, X['chart'], fontsize=12, fontweight='bold', color=PV.INK, va='center')
    ax.text(0.005, 0.01, X['models'], transform=ax.transAxes, ha='left', va='bottom', fontsize=10, color=PV.FAINT, zorder=9)
    bx = fig.add_axes([0.035, 0.03, 0.93, 0.082]); bx.set_facecolor('none')
    hx, pmm, tt, sn = C['ch_h'], C['ch_pr'], C['ch_t'], C['ch_sn']
    cols = [(level(p_, PR_LV, SNOW if s_ else RAIN) or '#e7edf3') for p_, s_ in zip(pmm, sn)]
    top = max(4.0, float(np.nanmax(pmm)) * 1.15)
    bx.bar(hx, np.maximum(pmm, top * 0.015), width=2.4, color=cols, zorder=2)
    h = fr['h']; bx.axvline(h, color=PV.ORANGE, lw=2, zorder=5); bx.axvspan(h - 1.5, h + 1.5, color=PV.ORANGE, alpha=0.18, lw=0, zorder=1)
    bx.set_ylim(0, top); bx.set_xlim(hx[0] - 3, hx[-1] + 3)
    bx.set_yticks([0, round(top / 2), round(top)]); bx.set_yticklabels(['0', f'{round(top / 2)}', f"{round(top)} {'мм' if lang == 'ru' else 'mm'}"], fontsize=10, color=PV.FAINT); bx.tick_params(length=0)
    for d0, lab in C['days']: bx.axvline(d0, color=PV.LINE, lw=0.9, zorder=0)
    bx.set_xticks([d + 12 for d, _ in C['days']]); bx.set_xticklabels([lab[lang] for _, lab in C['days']], fontsize=10.5, color=PV.MUTED, linespacing=1.05)
    for sp in bx.spines.values(): sp.set_visible(False)
    tx = bx.twinx(); lo, hi_ = np.nanmin(tt), np.nanmax(tt); pad = max(2, (hi_ - lo) * 0.2)
    tx.plot(C['ch_th'], tt, color=PV.TEMP, lw=2.2, zorder=6); tx.set_ylim(lo - pad, hi_ + pad)
    tx.plot([h], [fr['tash_t']], 'o', ms=9, color=PV.TEMP, mec='white', mew=2, zorder=7)
    tx.annotate(PV_deg(fr['tash_t']), (h, fr['tash_t']), xytext=(10, 4), textcoords='offset points', ha='left', fontsize=13, fontweight='bold', color=PV.TEMP, zorder=8,
                path_effects=[pe.withStroke(linewidth=3, foreground='white')])
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
        if C['qr'] is not None:
            qa = fig.add_axes([0.66, 0.36, 0.2 * H / W, 0.44]); qa.imshow(~C['qr'], cmap='gray', interpolation='nearest'); qa.axis('off')
    fig.savefig(pathlib.Path(V['dir']) / f'{i:04d}.png', dpi=PV.DPI, facecolor='white'); plt.close(fig)


def front_symbols(line, kind, every=1.1, size=0.22):
    """Triangles (cold) or half-discs (warm) along a front, in lon/lat, drawn on one side of the line."""
    xy = np.c_[line[:, 0] * PV.COSL, line[:, 1]]  # an even scale in both directions
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]; out = []
    for s in np.arange(every / 2, d[-1] - size, every):
        j = int(np.clip(np.searchsorted(d, s) - 1, 0, len(xy) - 2)); a = (s - d[j]) / max(d[j + 1] - d[j], 1e-9)
        p = xy[j] + a * (xy[j + 1] - xy[j]); t = xy[j + 1] - xy[j]; t = t / (np.hypot(*t) + 1e-9); n = np.array([-t[1], t[0]])
        if kind == 'cold': pts = np.array([p - t * size, p + t * size, p + n * size * 1.25])
        else: th = np.linspace(0, np.pi, 14); pts = np.array([p + size * (np.cos(q) * t + np.sin(q) * n) for q in th])
        out.append(np.c_[pts[:, 0] / PV.COSL, pts[:, 1]])
    return out


def PV_deg(v):
    v = int(round(v)); return f'{v:+d}°' if v else '0°'


def setup(F, run, paths, outd, langs, now=None, only=None):
    import moisture as M
    now = now or dt.datetime.utcnow()
    lon = M.LON0 + np.arange(F[min(F)]['msl'].shape[1]) * M.RES; lat = M.LAT0 + np.arange(F[min(F)]['msl'].shape[0]) * M.RES
    span = (LAT_B - LAT_A) / PV.COSL * (PV.MAP[2] * W) / (PV.MAP[3] * H); lc = 64.8; ext = (lc - span / 2, lc + span / 2)
    ci = np.flatnonzero((lon >= ext[0] - 1) & (lon <= ext[1] + 1)); ri = np.flatnonzero((lat >= LAT_A - 1) & (lat <= LAT_B + 1))
    UP = 2; LONu = np.linspace(lon[ci[0]], lon[ci[-1]], len(ci) * UP); LATu = np.linspace(lat[ri[0]], lat[ri[-1]], len(ri) * UP)
    cut = lambda a: a[np.ix_(ri, ci)]
    up = lambda a, s=1.0: gaussian_filter(zoom(cut(a), UP, order=1), s)
    at = lambda a, la, lo: float(a[np.abs(LATu - la).argmin(), np.abs(LONu - lo).argmin()])
    l0 = int(np.ceil((now - run).total_seconds() / 3600)) + 1; hmax = max(F)
    hours = list(range(max(l0, min(F) + 1), hmax + 1))
    if only: hours = hours[:only]
    # the fronts and the highs and lows at the model's own steps (the frames take the nearest)
    import warnings; warnings.filterwarnings('ignore')
    fronts = {}
    for st in sorted(F):
        if st < hours[0] - 6 or st > hours[-1] + 6 or 't850' not in F[st] or 'r850' not in F[st]: continue
        try:
            fr_ = M.fronts(cut(F[st]['t850']), cut(F[st]['r850']), cut(F[st]['u']), cut(F[st]['v']), lon[ci], lat[ri])
            fronts[st] = [(l_, k_) for l_, k_ in fr_ if (l_[:, 0] > ext[0]).any() and (l_[:, 0] < ext[1]).any() and (l_[:, 1] > LAT_A).any() and (l_[:, 1] < LAT_B).any()]
        except Exception as e: print('fronts', st, e, flush=True); fronts[st] = []
    def centres(msl):
        Mg = gaussian_filter(msl, 3); out = []
        for mask, hi in ((maximum_filter(Mg, size=40) == Mg, True), (minimum_filter(Mg, size=40) == Mg, False)):
            for y_, x_ in zip(*np.nonzero(mask)):
                if 4 < y_ < len(LATu) - 4 and 4 < x_ < len(LONu) - 4 and ext[0] + 0.8 < LONu[x_] < ext[1] - 0.8 and LAT_A + 0.4 < LATu[y_] < LAT_B - 0.4:
                    loc_ = Mg[max(0, y_ - 30):y_ + 30, max(0, x_ - 30):x_ + 30]
                    if (hi and Mg[y_, x_] - loc_.min() >= 3) or (not hi and loc_.max() - Mg[y_, x_] >= 3): out.append((float(LONu[x_]), float(LATu[y_]), hi))
        return out
    fields, frames0, trails = [], [], []
    rng = np.random.default_rng(7); NP, TRn = 1000, 12
    spawn = lambda n: np.c_[rng.uniform(ext[0], ext[1], n), rng.uniform(LAT_A - 0.3, LAT_B + 0.3, n)]
    P = spawn(NP); age = rng.integers(0, 60, NP); life = rng.integers(45, 90, NP); hist = [P.copy() for _ in range(TRn)]
    times = [h + s for h in hours for s in (0.0, 0.5)][:-1]
    for h in times:  # a frame every half hour: the fields eased in time, the particles moved by the wind of that half hour
        f = M.interp(F, h)
        g = dict(tcwv=up(f['tcwv'], 1.5), tcc=np.clip(up(f['tcc'], 1.5), 0, 1), pr=np.clip(up(f['pr'], 1.2), 0, None), t2=up(f['t2']), u=up(f['u']), v=up(f['v']), msl=up(f['msl']))
        iy = np.clip(np.searchsorted(LATu, P[:, 1]), 0, len(LATu) - 1); ix = np.clip(np.searchsorted(LONu, P[:, 0]), 0, len(LONu) - 1)
        P = P + np.c_[g['u'][iy, ix] * 1800 / (111e3 * np.cos(np.radians(P[:, 1]))), g['v'][iy, ix] * 1800 / 111e3]; age += 1
        dead = (age > life) | (P[:, 0] < ext[0] - 0.5) | (P[:, 0] > ext[1] + 0.5) | (P[:, 1] < LAT_A - 0.5) | (P[:, 1] > LAT_B + 0.5)
        if dead.any():
            P[dead] = spawn(int(dead.sum())); age[dead] = 0
            for q in hist: q[dead] = P[dead]
        hist = hist[1:] + [P.copy()]; trails.append(np.stack(hist).astype(np.float16))
        fog = None
        if 'td2' in F[min(F)]:
            ks = sorted(F); k_ = min(ks, key=lambda s: abs(s - h)); fog = up(F[k_]['td2'])
        fields.append({k: v.astype(np.float16) for k, v in g.items() if k != 'msl'})
        frames0.append(dict(h=h, k=len(fields) - 1, p=len(trails) - 1, fk=min(fronts, key=lambda s: abs(s - h)) if fronts else None, hl=centres(g['msl']) if h == int(h) else None, fog=fog,
                            g=dict(t2=g['t2'], pr=g['pr'], tcc=g['tcc'])))
    for j, fr in enumerate(frames0):  # the highs and lows of the half hours: those of the hour before
        if fr['hl'] is None: fr['hl'] = frames0[j - 1]['hl']
    hours = [fr['h'] for fr in frames0 if fr['h'] == int(fr['h'])]
    # Tashkent's chart: mm in 3 h at each 3rd hour, the temperature every hour
    tash = PV.TOWNS[0]
    ch_h = [h for h in hours if h % 3 == 0]
    byh = {fr['h']: fr['g'] for fr in frames0}
    ch_pr = [at(byh[h]['pr'], tash[2], tash[3]) for h in ch_h]
    ch_sn = [at(byh[h]['t2'], tash[2], tash[3]) <= 0.5 for h in ch_h]
    ch_t = [at(byh[h]['t2'], tash[2], tash[3]) for h in hours]
    loc = lambda h: run + dt.timedelta(hours=h + 5)
    days = []; t0 = loc(0); d = (loc(hours[0])).replace(hour=0, minute=0, second=0) + dt.timedelta(days=1)
    while (d - t0).total_seconds() / 3600 < hours[-1]:
        days.append(((d - t0).total_seconds() / 3600, {l: f"{TX[l]['wd'][d.weekday()]}\n{d:%d.%m}" for l in TX})); d += dt.timedelta(days=1)
    G = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']; GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']
    WAT = json.load(open(ROOT / 'prob' / 'geo_water.json'))
    from matplotlib.colors import LinearSegmentedColormap
    CTX.update(LONu=LONu, LATu=LATu, fields=fields, trails=trails, fronts=fronts, lon_ext=ext,
               wv_cmap=LinearSegmentedColormap.from_list('wv', ['#ffffff', '#f4f9f5', '#e3f2e9', '#c9e9d8', '#a6d9c1', '#7cc4a8', '#52a88e', '#3a8f7a']),
               sea=[np.asarray(r) for r in WAT['ocean']] + [np.asarray(l_['r']) for l_ in WAT['lakes']],
               borders=[([np.asarray(r) for k, c in G.items() if k != 'UZ' for r in c['rings']], '#a3acb6', 1.0, 3), ([np.asarray(r) for a in GA['adm1'] for r in a['r']], '#b7c0ca', 0.8, 3.05),
                        ([np.asarray(r) for r in G['UZ']['rings']], '#1c2633', 2.6, 3.3)],
               ch_h=ch_h, ch_pr=ch_pr, ch_sn=ch_sn, ch_t=ch_t, ch_th=hours, days=days, qr=PV.qr('https://t.me/ObHavo_ECMWF_bot'), videos={})
    d1 = loc(hours[0]).date() + dt.timedelta(days=0 if loc(hours[0]).hour < 12 else 1)
    for lang in langs:
        X = TX[lang]; frames = []
        for fr in frames0:
            g = fr['g']; h = fr['h']; t = loc(h)
            towns = []
            for tw in PV.TOWNS:
                t_ = at(g['t2'], tw[2], tw[3]); fog = fr['fog'] is not None and t_ - at(fr['fog'], tw[2], tw[3]) <= 1.0 and at(g['pr'], tw[2], tw[3]) < 0.3
                towns.append((t_, at(g['pr'], tw[2], tw[3]), t_ <= 0.5, at(g['tcc'], tw[2], tw[3]), fog))
            ps = [dict(p, a=float(np.clip(1 - (abs(h - p['h']) - 18) / 12, 0, 1))) for p in paths if abs(h - p['h']) <= 30]
            frames.append(dict(fr, when=f"{X['wd'][t.weekday()]} {t:%d.%m} · {t:%H}:00", day=X['day'].format(i=int(np.clip((t.date() - d1).days + 1, 1, 15)), n=15),
                               prog=(h - hours[0]) / max(1, hours[-1] - hours[0]), d=0.2, towns=towns, tash_t=at(g['t2'], tash[2], tash[3]), paths=[p for p in ps if p['a'] > 0]))
        frames[-1] = dict(frames[-1], d=1.2)
        intro = [dict(frames[0], card='intro', a=1.0, fade=0.0, d=1.6)] + [dict(frames[0], card='intro', a=float(a_), fade=float(1 - a_), d=0.07) for a_ in np.linspace(1, 0, 9)[1:]]
        CTX['videos'][lang] = dict(frames=intro + frames + [dict(frames[-1], card='end', d=4.0)], dir=tempfile.mkdtemp(), out=str(pathlib.Path(outd) / f'moist15_{lang}.mp4'))
    return CTX


def main():
    import moisture as M, trajectory as TJ, render as Rn
    npz, outd = sys.argv[1], pathlib.Path(sys.argv[2]); langs = (sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith('--') else 'ru,uz').split(',')
    outd.mkdir(parents=True, exist_ok=True)
    D = Rn.load(npz); run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None); run = run.replace(hour=0 if run.hour < 12 else 12)
    if '--fields' in sys.argv:
        Z = np.load(sys.argv[sys.argv.index('--fields') + 1], allow_pickle=True)
        F = {k: {q: np.asarray(v, np.float32) for q, v in f.items()} for k, f in Z['F'].item().items()}; Wd = dict(Z['W'].item()) if 'W' in Z.files else {}
    else:
        F = M.fetch(run, M.STEPS15)
        try: Wd = TJ.fetch_winds(run)
        except Exception as e: print('no winds', e, flush=True); Wd = {}
    paths = []
    try: paths = M.moisture_paths(F, M.extend_winds(Wd, F), 'UZ', H=min(360, max(F))) if len(Wd) >= 6 else []
    except Exception as e: print('paths failed', e, flush=True)
    paths = [dict(p, path=[list(map(float, q[:2])) for q in p['path']]) for p in paths]
    print('paths', [(p['city'], p['h'], p['src']['ru']) for p in paths], flush=True)
    setup(F, run, paths, outd, langs)
    PV.CTX.update(videos=CTX['videos'])
    jobs = [(l, i) for l in langs for i in range(len(CTX['videos'][l]['frames']))]; print(len(jobs), 'frames', flush=True)
    with mp.get_context('fork').Pool(max(1, os.cpu_count() or 1)) as pool:
        for n_, _ in enumerate(pool.imap_unordered(draw, jobs, chunksize=4)):
            if n_ % 200 == 0: print('frames', n_, '/', len(jobs), flush=True)
        for r in pool.imap_unordered(PV.encode, langs): print(r, flush=True)


if __name__ == '__main__':
    main()
