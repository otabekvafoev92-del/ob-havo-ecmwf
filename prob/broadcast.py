"""Professional weather briefing for YouTube and Telegram channels: one 16:9 Full HD video per language with
an intro, the world, the CIS and Turkey, Uzbekistan, a city table and an outro. Every map segment animates the
forecast while a side panel explains to viewers what matters (rain, snow, heat, cold, warnings).
Also writes the YouTube title, description with chapters and tags, and a thumbnail.
  out/yt/briefing_<lang>.mp4, briefing_<lang>.txt, thumb_<lang>.jpg, index.json
Usage: python3 prob/broadcast.py prob.npz glob.npz wx.npz site/prob [--langs ru,uz]"""
import argparse, datetime as dt, json, os, pathlib, subprocess, sys, textwrap
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render as Rn
from render import plt, matplotlib, FancyBboxPatch, Rectangle
from regions import NAMES

W_IN, H_IN = 19.2, 10.8  # 1920 × 1080 at 100 dpi
BOT, SITE = '@ObHavo_ECMWF_bot', 'otabekvafoev92-del.github.io/ob-havo-ecmwf'
TX = {
    'ru': dict(title='Прогноз погоды на 15 дней', sub='Мир · СНГ и Турция · Узбекистан', run='Расчёт моделей {run} UTC', models='Мультимодельный ансамбль ECMWF · NOAA · DWD',
               world='Мир', cis='СНГ и Турция', uz='Узбекистан', cities='Города Узбекистана', main='Главное', prob='Вероятность осадков', today='Сегодня', tomorrow='Завтра',
               warm='Самое тепло', cold='Самое холодно', rain='Дожди', snow='Снег', dry='Сухо и без осадков', warn='Предупреждения', none_warn='Сильных осадков не ожидается',
               share='Осадки пройдут на {p} % территории страны', next='Ближайшие дни, {city}', rainw='дождь', snoww='снег', noprec='без осадков', mm='мм',
               outro='Подписывайтесь', outro2='Прогноз для вашего города, видео и предупреждения — в Telegram', site='Сайт', days3='в ближайшие 3 дня',
               chapters=['Вступление', 'Мир', 'СНГ и Турция', 'Узбекистан', 'Города', 'Подписка'],
               ytitle='Прогноз погоды на 15 дней · {d} · мир, СНГ, Узбекистан | Osmon',
               ydesc='Мультимодельный прогноз погоды на 15 дней: вероятность дождя и снега, температура, сильные осадки.\nМодели: {m}.\n\n{bul}\n\n⏱ Главы:\n{ch}\n\n🤖 Бот с прогнозом для вашего города и предупреждениями: https://t.me/ObHavo_ECMWF_bot\n\n#погода #прогнозпогоды #Узбекистан #Ташкент #ECMWF',
               tags='погода, прогноз погоды, прогноз на 15 дней, Узбекистан, Ташкент, Казахстан, СНГ, ECMWF, осадки, дождь, снег, Osmon'),
    'uz': dict(title='15 kunlik ob-havo prognozi', sub='Dunyo · MDH va Turkiya · O‘zbekiston', run='Modellar hisobi {run} UTC', models='ECMWF · NOAA · DWD multimodel ansambli',
               world='Dunyo', cis='MDH va Turkiya', uz='O‘zbekiston', cities='O‘zbekiston shaharlari', main='Asosiysi', prob='Yog‘in ehtimoli', today='Bugun', tomorrow='Ertaga',
               warm='Eng issiq', cold='Eng sovuq', rain='Yomg‘ir', snow='Qor', dry='Quruq, yog‘insiz', warn='Ogohlantirishlar', none_warn='Kuchli yog‘in kutilmaydi',
               share='Yog‘in mamlakat hududining {p} % qismida', next='Yaqin kunlar, {city}', rainw='yomg‘ir', snoww='qor', noprec='yog‘insiz', mm='mm',
               outro='Obuna bo‘ling', outro2='Shahringiz prognozi, videolar va ogohlantirishlar — Telegramda', site='Sayt', days3='yaqin 3 kunda',
               chapters=['Kirish', 'Dunyo', 'MDH va Turkiya', 'O‘zbekiston', 'Shaharlar', 'Obuna'],
               ytitle='15 kunlik ob-havo prognozi · {d} · dunyo, MDH, O‘zbekiston | Osmon',
               ydesc='15 kunlik multimodel ob-havo prognozi: yomg‘ir va qor ehtimoli, harorat, kuchli yog‘in.\nModellar: {m}.\n\n{bul}\n\n⏱ Bo‘limlar:\n{ch}\n\n🤖 Shahringiz prognozi va ogohlantirishlar: https://t.me/ObHavo_ECMWF_bot\n\n#obhavo #obhavoprognozi #Ozbekiston #Toshkent #ECMWF',
               tags='ob-havo, ob havo, ob-havo prognozi, 15 kunlik prognoz, O‘zbekiston, Toshkent, ECMWF, yomg‘ir, qor, Osmon'),
}
FPS = {'world': 3, 'cis': 3, 'uz': 4}


def days_of(R, D, run, off, p, n=3):
    """Per local day for a place: (date, tmin, tmax, max probability %, mm, snow)."""
    steps, win = [int(x) for x in D['steps']], [int(x) for x in D['win']]
    P, A, Ts = R.series(p), R.aseries(p), R.tseries(p)
    first = (run + dt.timedelta(hours=12 + off)).date(); out = {}
    for i, (s, w) in enumerate(zip(steps, win)):
        d = Rn.local_day(run, s, off, w)
        if first <= d < first + dt.timedelta(days=n): out.setdefault(d, []).append(i)
    res = []
    for d, idx in sorted(out.items()):
        t = Ts[idx] if Ts is not None else np.array([np.nan])
        wet = [i for i in idx if P[i] >= 30]
        snow = Ts is not None and wet and float(np.nanmean(Ts[wet])) <= 0.5
        res.append((d, float(np.nanmin(t)), float(np.nanmax(t)), float(np.nanmax(P[idx])), float(np.nansum(A[idx])), bool(snow)))
    return res


def highlights(R, D, run, off, lang, n=3):
    """Bullets for viewers: warmest, coldest, where it rains or snows (next n days)."""
    X = TX[lang]; rows = []
    for p in R.cities:
        dd = days_of(R, D, run, off, p, n)
        if dd: rows.append((p, max(x[2] for x in dd), min(x[1] for x in dd), max(x[3] for x in dd), any(x[5] and x[3] >= 50 for x in dd)))
    rows = [r for r in rows if np.isfinite(r[1]) and -70 < r[2] <= r[1] < 60]
    nm = lambda p: Rn.city_name(p, lang)
    out = []
    if rows:
        hot = sorted(rows, key=lambda r: -r[1])[:3]; cold = sorted(rows, key=lambda r: r[2])[:3]
        out.append(f"{X['warm']}: " + ', '.join(f"{nm(r[0])} {Rn.fmt_t(r[1])}" for r in hot))
        out.append(f"{X['cold']}: " + ', '.join(f"{nm(r[0])} {Rn.fmt_t(r[2])}" for r in cold))
        wet = sorted([r for r in rows if r[3] >= 55 and not r[4]], key=lambda r: -r[3])[:4]
        snow = sorted([r for r in rows if r[4]], key=lambda r: -r[3])[:4]
        if wet: out.append(f"{X['rain']}: " + ', '.join(f"{nm(r[0])} {r[3]:.0f} %" for r in wet))
        if snow: out.append(f"{X['snow']}: " + ', '.join(f"{nm(r[0])} {r[3]:.0f} %" for r in snow))
        if not wet and not snow: out.append(X['dry'])
    return out


def _brand(fig, y=0.955, x=0.025, size=20):
    k = fig.get_figheight() / fig.get_figwidth(); r = 0.011
    for a0, a1, col in ((200, 20, Rn.ACCENT), (20, 200, Rn.SKY)):
        w = matplotlib.patches.Wedge((x, y), r, a0, a1, width=r * 0.45, facecolor=col, edgecolor='none')
        w.set_transform(matplotlib.transforms.Affine2D().scale(1, 1 / k).translate(0, y - y / k) + fig.transFigure); fig.patches.append(w)
    fig.text(x + 0.018, y, 'osmon', fontsize=size, fontfamily=Rn.DISPLAY, fontweight='bold', color=Rn.INK, va='center')
    t = fig.text(x + 0.018, y, 'osmon', fontsize=size, fontfamily=Rn.DISPLAY, fontweight='bold', color='none', va='center')
    bb = t.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
    fig.text(bb.x1, y, '.', fontsize=size, fontfamily=Rn.DISPLAY, fontweight='bold', color=Rn.ACCENT, va='center')


def _when(lang, run, step, off, win):
    return Rn._when(lang, run, step, off, win)


def map_frame(R, D, s, lang, path, seg, bullets, frames, k, warn=None):
    X = TX[lang]; L = Rn.T[lang]
    run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    off = R.off if R.off is not None else Rn.OVERVIEW_TZ[lang]
    fig = plt.figure(figsize=(W_IN, H_IN), dpi=100); fig.patch.set_facecolor(Rn.BG)
    _brand(fig)
    fig.text(0.13, 0.955, f"{seg}  ·  {X['prob']}", fontsize=19, fontweight='bold', color=Rn.INK, va='center')
    fig.text(0.975, 0.955, _when(lang, run, D['steps'][s], off, D['win'][s]), fontsize=21, fontweight='bold', color=Rn.ACCENT, va='center', ha='right')
    R.main = R.mains[lang]; R.view = None
    ax = Rn._basemap(fig, R, [0.018, 0.095, 0.655, 0.81])
    has_t, has_c, has_w = Rn.draw_fields(ax, R, s, 'prob')
    Rn._borders(ax, R)
    def label(p, main):
        v = R.value_at(s, p); t = R.value_at(s, p, 'T') if has_t else np.nan
        txt = f"{Rn.city_name(p, lang)} {int(round(max(0, min(100, v))))} %"
        return txt + (f" · {Rn.fmt_t(t)}" if np.isfinite(t) else '')
    Rn._cities(fig, ax, R, label)
    # side panel: what viewers should know
    Rn._card(fig, 0.69, 0.095, 0.29, 0.81)
    fig.text(0.705, 0.875, X['main'].upper(), fontsize=13, fontweight='bold', color=Rn.SKY, va='center')
    fig.text(0.705, 0.845, X['days3'], fontsize=12, color=Rn.MUTED, va='center')
    y = 0.8
    for b in bullets:
        head, _, rest = b.partition(': ')
        fig.text(0.705, y, head, fontsize=14, fontweight='bold', color=Rn.INK, va='top'); y -= 0.034
        if rest:
            for line in textwrap.wrap(rest, 34)[:3]:
                fig.text(0.705, y, line, fontsize=14, color=Rn.MUTED, va='top'); y -= 0.03
        y -= 0.018
    if warn is not None:
        y -= 0.005
        fig.text(0.705, y, ('⚠ ' + X['warn']) if warn else X['none_warn'], fontsize=14, fontweight='bold', color=Rn.HEAVY if warn else Rn.MUTED, va='top'); y -= 0.034
        for w in warn[:4]:
            fig.text(0.705, y, w, fontsize=12.5, color=Rn.INK, va='top'); y -= 0.028
    # legend
    fig.text(0.705, 0.175, L['rain'], fontsize=12, fontweight='bold', color=Rn.INK, va='center')
    Rn._chips(fig, 0.75, 0.175, Rn.COLORS, ['10', '30', '50', '70', '90'], w=0.042, h=0.026, gap=0.003)
    fig.text(0.705, 0.135, L['snow'], fontsize=12, fontweight='bold', color=Rn.INK, va='center')
    Rn._chips(fig, 0.75, 0.135, Rn.SNOW, ['10', '30', '50', '70', '90'], w=0.042, h=0.026, gap=0.003)
    # progress through the segment
    Rn._card(fig, 0.018, 0.022, 0.962, 0.05, fc=Rn.CARD2, ec='none', r=0.01)
    fig.patches.append(FancyBboxPatch((0.03, 0.04), 0.4 * (k + 1) / frames, 0.014, boxstyle='round,pad=0,rounding_size=0.007', transform=fig.transFigure,
                                      facecolor=Rn.ACCENT, edgecolor='none', mutation_aspect=W_IN / H_IN))
    fig.text(0.45, 0.047, X['models'], fontsize=12, color=Rn.MUTED, va='center')
    fig.text(0.97, 0.047, f't.me/{BOT[1:]}', fontsize=13, fontweight='bold', color=Rn.SKY, va='center', ha='right')
    fig.savefig(path, dpi=100, facecolor=Rn.BG); plt.close(fig)


def card_frame(path, lang, kind, D, extra=None):
    X = TX[lang]; D = D or REG['uz'][1]; run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00'))
    fig = plt.figure(figsize=(W_IN, H_IN), dpi=100); fig.patch.set_facecolor(Rn.BG)
    if kind in ('intro', 'thumb'):
        _brand(fig, 0.86, 0.08, 30)
        today = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=5)).date()
        fig.text(0.08, 0.62, X['title'], fontsize=58 if kind == 'intro' else 70, fontfamily=Rn.DISPLAY, fontweight='bold', color=Rn.INK, va='center')
        fig.text(0.08, 0.5, today.strftime('%d.%m.%Y'), fontsize=44, fontweight='bold', color=Rn.ACCENT, va='center')
        fig.text(0.08, 0.4, X['sub'], fontsize=30, color=Rn.MUTED, va='center')
        if kind == 'intro':
            fig.text(0.08, 0.16, X['models'] + '  ·  ' + X['run'].format(run=run.strftime('%d.%m %H:%M')), fontsize=18, color=Rn.FAINT, va='center')
        for i, c in enumerate(Rn.COLORS + Rn.SNOW[::-1]):
            fig.patches.append(Rectangle((0.08 + i * 0.084, 0.27), 0.08, 0.018, transform=fig.transFigure, facecolor=c, edgecolor='none'))
    elif kind == 'outro':
        _brand(fig, 0.8, 0.08, 30)
        fig.text(0.08, 0.6, X['outro'], fontsize=60, fontfamily=Rn.DISPLAY, fontweight='bold', color=Rn.INK, va='center')
        fig.text(0.08, 0.48, X['outro2'], fontsize=28, color=Rn.MUTED, va='center')
        fig.text(0.08, 0.34, f't.me/{BOT[1:]}', fontsize=42, fontweight='bold', color=Rn.SKY, va='center')
        fig.text(0.08, 0.24, X['models'], fontsize=22, color=Rn.MUTED, va='center')
    elif kind == 'cities':
        _brand(fig)
        fig.text(0.13, 0.955, X['cities'], fontsize=19, fontweight='bold', color=Rn.INK, va='center')
        rows = extra or []
        x0, cw = 0.04, [0.2, 0.37, 0.37]
        fig.text(x0 + cw[0], 0.86, X['today'], fontsize=20, fontweight='bold', color=Rn.ACCENT, va='center')
        fig.text(x0 + cw[0] + cw[1], 0.86, X['tomorrow'], fontsize=20, fontweight='bold', color=Rn.ACCENT, va='center')
        for i, (name, dd) in enumerate(rows[:10]):
            y = 0.79 - i * 0.075
            Rn._card(fig, 0.03, y - 0.03, 0.94, 0.06, fc=Rn.CARD if i % 2 == 0 else Rn.BG, ec='none', r=0.008)
            fig.text(x0, y, name, fontsize=20, fontweight='bold', color=Rn.INK, va='center')
            for j, d in enumerate(dd[:2]):
                _, tmin, tmax, pm, mm, snow = d
                x = x0 + cw[0] + j * cw[1]
                pal = Rn.SNOW if snow else Rn.COLORS
                col = Rn._level_col(pm, pal) if pm >= 10 else Rn.LOW_TXT
                fig.patches.append(Rectangle((x, y - 0.012), 0.06 * min(pm, 100) / 100 + 0.002, 0.024, transform=fig.transFigure, facecolor=col, edgecolor='none'))
                fig.text(x + 0.07, y, f"{Rn.fmt_t(tmin)}…{Rn.fmt_t(tmax)}", fontsize=19, fontweight='bold', color=Rn.INK, va='center')
                w = X['noprec'] if pm < 20 else f"{X['snoww'] if snow else X['rainw']} {pm:.0f} %" + (f", ~{mm:.0f} {X['mm']}" if mm >= 1 else '')
                fig.text(x + 0.17, y, w, fontsize=17, color=Rn.MUTED, va='center')
    fig.savefig(path, dpi=100 if kind != 'thumb' else 66.67, facecolor=Rn.BG); plt.close(fig)


REG = {}
def _job(a):
    if a[0] == 'map':
        R, D = REG[a[1]]; map_frame(R, D, *a[2:])
    else: card_frame(*a[1:])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('prob'); ap.add_argument('glob'); ap.add_argument('wx'); ap.add_argument('out')
    ap.add_argument('--langs', default='ru,uz'); ap.add_argument('--jobs', type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    out = pathlib.Path(a.out) / 'yt'; out.mkdir(parents=True, exist_ok=True)
    Dc = Rn.load(a.prob); Pc, models, _ = Rn.probability(Dc)
    Dg = Rn.load(a.glob); Pg, _, _ = Rn.probability(Dg)
    run = dt.datetime.fromisoformat(Dc['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    Rn._CTX['wx'] = Rn.load_wx_npz(Dg, a.wx); Rw = Rn.Region(Dg, Rn.Geo(HERE / 'geo_world.json'), 'world', Pg, Dg['amt'])
    Rn._CTX['wx'] = Rn.load_wx_npz(Dc, a.wx); geo = Rn.Geo(None)
    Rc = Rn.Region(Dc, geo, 'cis', Pc, Dc['amt']); Ru = Rn.Region(Dc, geo, 'UZ', Pc, Dc['amt'])
    warns = []
    for rg in ('UZ', 'KZ', 'KG', 'TJ', 'TM', 'AZ', 'AM', 'BY', 'MD', 'RU', 'TR'):
        try: warns += Rn.find_alerts(Ru if rg == 'UZ' else Rn.Region(Dc, geo, rg, Pc, Dc['amt']), Dc, run)
        except Exception as e: print(rg, e)
    sel = lambda D, h: [i for i, s in enumerate(D['steps']) if int(s) <= h]
    REG.update(world=(Rw, Dg), cis=(Rc, Dc), uz=(Ru, Dc))  # shared with the forked workers, not pickled per frame
    segs = [('world', Rw, Dg, sel(Dg, 120)), ('cis', Rc, Dc, sel(Dc, 168)), ('uz', Ru, Dc, list(range(len(Dc['steps']))))]
    index = {'run': Dc['run'], 'items': []}
    for lang in a.langs.split(','):
        X = TX[lang]; fdir = out / f'frames_{lang}'; fdir.mkdir(exist_ok=True)
        offw = Rn.OVERVIEW_TZ[lang]
        bul = {'world': highlights(Rw, Dg, run, offw, lang), 'cis': highlights(Rc, Dc, run, Rc.off if Rc.off is not None else offw, lang), 'uz': []}
        # Uzbekistan: share of the country with rain and the next days in Tashkent
        idx3 = [i for i, s in enumerate(Dc['steps']) if int(s) <= 72]; sh = Ru.area_share(idx3)
        tas = days_of(Ru, Dc, run, 5, Ru.mains[lang], 5)
        bul['uz'] = ([X['share'].format(p=round(sh * 100)) + ': ' + X['days3']] if sh else []) + [
            f"{Rn.T[lang]['wd'][d.weekday()]} {d:%d.%m}: {Rn.fmt_t(lo)}…{Rn.fmt_t(hi)}, " + (X['noprec'] if pm < 20 else f"{X['snoww'] if sn else X['rainw']} {pm:.0f} %") for d, lo, hi, pm, mm, sn in tas]
        wl = [f"{w['name'][lang]} {Rn.T[lang]['wd'][dt.date.fromisoformat(w['date']).weekday()]}: ~{w['mm']:.0f} {X['mm']} ({X['snoww'] if w['snow'] else X['rainw']})" for w in warns]
        jobs, order = [], []
        def add(kind, args):
            name = fdir / f'{len(order):03d}_{kind}.png'; order.append((name, kind))
            jobs.append((kind, *[name if isinstance(x, str) and x == '@' else x for x in args]))
        add('card', ['@', lang, 'intro', None])
        for key, R, D, ss in segs:
            title = {'world': X['world'], 'cis': X['cis'], 'uz': X['uz']}[key]
            for k, s in enumerate(ss):
                add('map', [key, s, lang, '@', title, bul[key], len(ss), k, wl if key == 'cis' else None])
        main_cities = [Ru.mains[lang]] + [p for p in Ru.cities if p is not Ru.mains[lang]][:9]
        add('card', ['@', lang, 'cities', None, [(Rn.city_name(p, lang), days_of(Ru, Dc, run, 5, p, 2)) for p in main_cities]])
        add('card', ['@', lang, 'outro', None])
        card_frame(out / f'thumb_{lang}.jpg', lang, 'thumb', Dc)
        import multiprocessing as mp
        with mp.get_context('fork').Pool(a.jobs) as pool: list(pool.imap_unordered(_job, jobs, chunksize=4))
        # one segment per scene, each with its own pace, then joined
        parts, chapters, t = [], [], 0.0
        groups = [('intro', 1, 3.0)] + [(k, len(ss), len(ss) / FPS[k]) for k, _, _, ss in segs] + [('cities', 1, 8.0), ('outro', 1, 5.0)]
        i0 = 0
        for gi, (g, n, dur) in enumerate(groups):
            lst = fdir / f'list_{gi}.txt'
            with open(lst, 'w') as f:
                for j in range(i0, i0 + n): f.write(f"file '{order[j][0].resolve()}'\nduration {dur / n:.4f}\n")
                f.write(f"file '{order[i0 + n - 1][0].resolve()}'\n")
            seg = fdir / f'seg_{gi}.mp4'
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-crf', '24', '-preset', 'medium', str(seg)], check=True)
            parts.append(seg); chapters.append((t, X['chapters'][gi])); t += dur; i0 += n
        with open(fdir / 'all.txt', 'w') as f:
            for p in parts: f.write(f"file '{p.resolve()}'\n")
        mp4 = out / f'briefing_{lang}.mp4'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(fdir / 'all.txt'), '-c', 'copy', '-movflags', '+faststart', str(mp4)], check=True)
        ch = '\n'.join(f"{int(tt // 60)}:{int(tt % 60):02d} {nm}" for tt, nm in chapters)
        today = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=5)).strftime('%d.%m.%Y')
        allb = [f"• {X['world']}. " + '; '.join(bul['world'])[:300], f"• {X['cis']}. " + '; '.join(bul['cis'])[:300], f"• {X['uz']}. " + '; '.join(bul['uz'])[:400]]
        if wl: allb.append(f"• {X['warn']}: " + '; '.join(wl[:6]))
        txt = f"{X['ytitle'].format(d=today)}\n\n{X['ydesc'].format(m=', '.join(models), bul=chr(10).join(allb), ch=ch, site=SITE)}\n\nTags: {X['tags']}\n"
        open(out / f'briefing_{lang}.txt', 'w').write(txt)
        index['items'].append({'lang': lang, 'video': f'yt/briefing_{lang}.mp4', 'thumb': f'yt/thumb_{lang}.jpg', 'text': f'yt/briefing_{lang}.txt', 'title': X['ytitle'].format(d=today), 'duration': round(t, 1)})
        import shutil; shutil.rmtree(fdir)
        print('briefing', lang, f'{t:.0f} s', mp4.stat().st_size // 1048576, 'MB', flush=True)
    json.dump(index, open(out / 'index.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
