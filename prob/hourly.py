"""Today and tomorrow, hour by hour: one Full HD video (1920 × 1080) per country and language.
The 3-hour model windows are interpolated to every hour; each hour stays on screen for one second (a calm,
"0.25×" pace). Every frame: the map (rain/snow, clouds, temperature at the cities), the chosen city's numbers,
when rain is likely today and tomorrow, what to wear, and a 48-hour strip.
  out/hr/<region>_<lang>.mp4 and out/hr/<region>_<lang>.json (timing and clothing texts for the bot)
Usage: python3 prob/hourly.py prob.npz wx.npz site/prob [--regions UZ,KZ,...] [--langs uz,ru]"""
import argparse, datetime as dt, json, os, pathlib, subprocess, sys, textwrap
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render as Rn
from render import plt, matplotlib, FancyBboxPatch, Rectangle
from regions import NAMES, T as TT

HOURS = 48
TX = {
    'ru': dict(title='Сегодня и завтра по часам', today='Сегодня', tomorrow='Завтра', now='Сейчас', rain='дождь', snow='снег', dry='без осадков', wind='ветер', ms='м/с',
               when='Осадки', none='Осадков не ожидается', likely='вероятны {a}–{b} ч (до {p} %)', wear='Что надеть', umbrella='зонт', boots='непромокаемая обувь', windbr='ветровка',
               c=['зимняя куртка, шапка, перчатки', 'тёплая куртка и шапка', 'куртка или пальто, шарф', 'лёгкая куртка или свитер', 'кофта, вечером лёгкая куртка', 'футболка и лёгкая одежда', 'лёгкая одежда, головной убор, вода'],
               strip='48 часов: вероятность осадков и температура', feel='ощущается как'),
    'uz': dict(title='Bugun va ertaga soatma-soat', today='Bugun', tomorrow='Ertaga', now='Hozir', rain='yomg‘ir', snow='qor', dry='yog‘insiz', wind='shamol', ms='m/s',
               when='Yog‘in', none='Yog‘in kutilmaydi', likely='{a}–{b} soatlarda ehtimoli bor ({p} % gacha)', wear='Nima kiyish kerak', umbrella='soyabon', boots='suv o‘tkazmaydigan poyabzal', windbr='shamoldan himoya kurtka',
               c=['qishki kurtka, telpak, qo‘lqop', 'issiq kurtka va telpak', 'kurtka yoki palto, sharf', 'yengil kurtka yoki sviter', 'kofta, kechqurun yengil kurtka', 'futbolka, yengil kiyim', 'yengil kiyim, bosh kiyim, suv'],
               strip='48 soat: yog‘in ehtimoli va harorat', feel='his qilinadi'),
    'tr': dict(title='Bugün ve yarın saat saat', today='Bugün', tomorrow='Yarın', now='Şimdi', rain='yağmur', snow='kar', dry='yağışsız', wind='rüzgâr', ms='m/s',
               when='Yağış', none='Yağış beklenmiyor', likely='{a}–{b} saatleri arasında olası (%{p} e kadar)', wear='Ne giymeli', umbrella='şemsiye', boots='su geçirmez ayakkabı', windbr='rüzgârlık',
               c=['kışlık mont, bere, eldiven', 'kalın mont ve bere', 'mont veya kaban, atkı', 'ince ceket veya kazak', 'hırka, akşam ince ceket', 'tişört ve hafif giysiler', 'hafif giysiler, şapka, su'],
               strip='48 saat: yağış olasılığı ve sıcaklık', feel='hissedilen'),
}


def wear(lang, tmin, tmax, pmax, snow, wmax):
    X = TX[lang]; t = (tmin + 2 * tmax) / 3
    k = 0 if t <= -10 else 1 if t <= 0 else 2 if t <= 8 else 3 if t <= 15 else 4 if t <= 22 else 5 if t <= 28 else 6
    out = [X['c'][k]]
    if pmax >= 40: out.append(X['boots'] if snow else X['umbrella'])
    if wmax >= 8: out.append(X['windbr'])
    return ', '.join(out)


def rain_spans(P, hours, lang, day0):
    """Hours of a local day with probability ≥ 40 % as 'a–b' spans."""
    X = TX[lang]; idx = [i for i, h in enumerate(hours) if h.date() == day0]
    if not idx: return None
    wet = [i for i in idx if P[i] >= 40]
    if not wet: return X['none']
    spans, a = [], wet[0]
    for i, j in zip(wet, wet[1:] + [None]):
        if j != i + 1: spans.append((a, i)); a = j
    a, b = max(spans, key=lambda s: P[s[0]:s[1] + 1].max())
    return X['likely'].format(a=hours[a].hour, b=(hours[b].hour + 1) % 24 or 24, p=int(P[a:b + 1].max()))


def to_hours(R, D, run, off):
    """Interpolate the region's fields from model windows to every hour of the next 48 h (from the next full hour)."""
    st = np.array([int(x) for x in D['steps']], float); wn = np.array([int(x) for x in D['win']], float)
    mid = st - wn / 2  # window middles, hours from the run
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    h0 = max(mid[0], np.ceil((now - run).total_seconds() / 3600))
    hrs = h0 + np.arange(HOURS)
    def lerp(F):
        out = []
        for h in hrs:
            j = int(np.clip(np.searchsorted(mid, h), 1, len(mid) - 1)); w = float(np.clip((h - mid[j - 1]) / (mid[j] - mid[j - 1]), 0, 1))
            out.append(F[j - 1] * (1 - w) + F[j] * w)
        return np.stack(out)
    for name in ('P', 'T', 'C', 'Asm', 'Wd', 'U', 'V', 'Pfull', 'A'):
        F = getattr(R, name, None)
        if F is not None: setattr(R, name, lerp(F))
    R.Araw = R.A
    loc = [run + dt.timedelta(hours=float(h) + off) for h in hrs]
    return hrs, loc


def frame(R, k, lang, path, loc, info, city):
    """Full HD 16:9, the same layout as the 15-day videos: map left, the city card right, 48 hours below."""
    X = TX[lang]; L = TT[lang]
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100); fig.patch.set_facecolor(Rn.BG)
    x = Rn._brand(fig, 0.022, 0.948)
    nm = fig.text(x + 0.012, 0.948, NAMES[R.id][lang], fontsize=18, fontfamily=Rn.DISPLAY, fontweight='bold', color=Rn.INK, va='center')
    bb = nm.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
    tx = fig.text(bb.x1 + 0.026, 0.948, X['title'].upper(), fontsize=8.6, fontweight='bold', color=Rn.SKY, va='center')
    tb = tx.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
    Rn._card(fig, tb.x0 - 0.01, 0.93, tb.width + 0.02, 0.036, fc=Rn.CARD2, ec=Rn.LINE, r=0.012)
    t = loc[k]; day = X['today'] if t.date() == loc[0].date() else X['tomorrow'] if t.date() == loc[0].date() + dt.timedelta(days=1) else ''
    tm = fig.text(0.985, 0.95, f"{t:%H}:00", fontsize=26, fontfamily=Rn.DISPLAY, fontweight='bold', color=Rn.ACCENT, ha='right', va='center')
    tb2 = tm.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
    fig.text(tb2.x0 - 0.014, 0.95, f"{day} · {L['wd'][t.weekday()]} {t:%d.%m}", fontsize=13, fontweight='bold', color=Rn.MUTED, ha='right', va='center')
    R.main = city; R.view = None
    ax = Rn._basemap(fig, R)
    has_t, has_c, has_w = Rn.draw_fields(ax, R, k, 'prob')
    Rn._borders(ax, R)
    def label(p, main):
        v = R.value_at(k, p); tt = R.value_at(k, p, 'T') if has_t else np.nan
        return f"{Rn.city_name(p, lang)} {Rn.fmt_t(tt)}" + (f" · {int(round(v))} %" if v >= 15 else '') if np.isfinite(tt) else Rn.city_name(p, lang)
    Rn._cities(fig, ax, R, label)
    PX, PW = Rn.PANEL; X0, X1 = PX + 0.016, PX + PW - 0.014
    Rn._card(fig, PX, 0.213, PW, 0.665)
    tt = R.value_at(k, city, 'T') if has_t else np.nan; v = max(0, min(100, R.value_at(k, city)))
    c = R.value_at(k, city, 'C') * 100 if has_c else np.nan; ws = R.value_at(k, city, 'Wd') if has_w else np.nan
    snow = np.isfinite(tt) and tt <= 0.5
    fig.text(X0, 0.845, Rn.city_name(city, lang), fontsize=13, fontweight='bold', color=Rn.INK, va='center')
    fig.text(X0, 0.785, Rn.fmt_t(tt) if np.isfinite(tt) else '—', fontsize=26, fontfamily=Rn.DISPLAY, fontweight='bold', color=Rn.INK, va='center')
    rows = [((X['snow'] if snow else X['rain']).capitalize(), f'{v:.0f} %')]
    if np.isfinite(c): rows.append((L['clouds'][0], f'{c:.0f} %'))
    if np.isfinite(ws): rows.append((X['wind'].capitalize(), f"{ws:.0f} {X['ms']}"))
    for i, (a_, b_) in enumerate(rows):
        y = 0.72 - i * 0.04
        fig.text(X0, y, a_, fontsize=10, color=Rn.MUTED, va='center'); fig.text(X1, y, b_, fontsize=12, fontweight='bold', color=Rn.INK, va='center', ha='right')
        fig.add_artist(matplotlib.lines.Line2D([X0, X1], [y - 0.02, y - 0.02], color=Rn.LINE, lw=0.6, transform=fig.transFigure))
    y = 0.575
    for lbl, d in ((X['today'], info['today']), (X['tomorrow'], info['tomorrow'])):
        if not d: continue
        fig.text(X0, y, f"{lbl}  {d['range']}", fontsize=11.5, fontweight='bold', color=Rn.INK, va='center'); y -= 0.034
        for line in textwrap.wrap(d['rain'] if d['rain'] == X['none'] else f"{X['when']}: {d['rain']}", 34)[:2]:
            fig.text(X0, y, line, fontsize=9.5, color=Rn.MUTED, va='center'); y -= 0.03
        for j, line in enumerate(textwrap.wrap(f"{X['wear']}: {d['wear']}", 34)[:3]):
            fig.text(X0, y, line, fontsize=9.5, color=Rn.ACCENT if j == 0 else Rn.MUTED, va='center'); y -= 0.03
        y -= 0.02
    # 48 hours
    Rn._card(fig, 0.012, 0.04, 0.976, 0.155)
    fig.text(0.024, 0.178, X['strip'], fontsize=9, color=Rn.MUTED, va='center')
    bx = fig.add_axes([0.045, 0.072, 0.915, 0.088]); bx.set_facecolor('none')
    P = np.clip(R.series(city), 0, 100); Ts = R.tseries(city)
    cols = [Rn._level_col(p, Rn.SNOW if (Ts is not None and Ts[i] <= 0.5) else Rn.COLORS) if p >= 10 else Rn.LOW_BAR for i, p in enumerate(P)]
    bx.bar(np.arange(HOURS), P, width=0.8, color=cols, zorder=2); bx.set_ylim(0, 100); bx.set_xlim(-0.6, HOURS - 0.4)
    bx.axvspan(k - 0.5, k + 0.5, color=Rn.ACCENT, alpha=0.25, lw=0); bx.axvline(k, color=Rn.ACCENT, lw=1.4, zorder=4)
    for m in [i for i, h in enumerate(loc) if h.hour == 0]: bx.axvline(m - 0.5, color=Rn.LINE, lw=1, zorder=1)
    ticks = [i for i, h in enumerate(loc) if h.hour % 3 == 0]
    bx.set_xticks(ticks); bx.set_xticklabels([f"{loc[i]:%H}" for i in ticks], fontsize=8, color=Rn.MUTED)
    bx.set_yticks([0, 50, 100]); bx.set_yticklabels(['0', '50', '100 %'], fontsize=7.5, color=Rn.FAINT); bx.tick_params(length=0)
    for sp in bx.spines.values(): sp.set_visible(False)
    if Ts is not None:
        tx2 = bx.twinx(); tx2.plot(np.arange(HOURS), Ts, color=Rn.ACCENT, lw=1.5); tx2.plot([k], [Ts[k]], 'o', ms=5, color=Rn.ACCENT, mec=Rn.BG)
        lo, hi = np.nanmin(Ts), np.nanmax(Ts); tx2.set_ylim(lo - 2, hi + 2); tx2.tick_params(length=0, labelsize=7.5, colors=Rn.ACCENT)
        tx2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x_, _: Rn.fmt_t(x_))); tx2.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
        for sp in tx2.spines.values(): sp.set_visible(False)
    fig.text(0.014, 0.018, 'ECMWF · NOAA · DWD', fontsize=6.6, color=Rn.FAINT, va='center')
    fig.text(0.986, 0.018, 't.me/ObHavo_ECMWF_bot', fontsize=6.6, color=Rn.FAINT, va='center', ha='right')
    fig.savefig(path, dpi=150, facecolor=Rn.BG); plt.close(fig)


REG = {}
def _frame(a):
    R, loc, info, city = REG[(a[0], a[1])]; frame(R, a[2], a[1], a[3], loc, info, city)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('npz'); ap.add_argument('wx'); ap.add_argument('out')
    ap.add_argument('--regions', default='UZ,KZ,KG,TJ,TM,AZ,AM,BY,MD,RU,TR'); ap.add_argument('--langs', default='uz,ru')
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 2)
    a = ap.parse_args()
    D = Rn.load(a.npz); P, _, _ = Rn.probability(D); Rn._CTX['wx'] = Rn.load_wx_npz(D, a.wx); geo = Rn.Geo(None)
    run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    out = pathlib.Path(a.out) / 'hr'; out.mkdir(parents=True, exist_ok=True)
    index = []
    for region in a.regions.split(','):
        R = Rn.Region(D, geo, region, P, D['amt']); off = R.off if R.off is not None else 5
        hrs, loc = to_hours(R, D, run, off)
        for lang in a.langs.split(','):
            if lang == 'tr' and region not in ('TR', 'AZ'): continue
            city = R.mains[lang]
            if city is None: continue
            Pc, Tc = np.clip(R.series(city), 0, 100), R.tseries(city); Wc = R.wseries(city) if getattr(R, 'Wd', None) is not None else np.zeros(HOURS)
            info = {}
            for key, dd in (('today', loc[0].date()), ('tomorrow', loc[0].date() + dt.timedelta(days=1))):
                idx = [i for i, h in enumerate(loc) if h.date() == dd]
                if not idx or Tc is None: info[key] = None; continue
                tmin, tmax, pmax = float(np.nanmin(Tc[idx])), float(np.nanmax(Tc[idx])), float(Pc[idx].max())
                snow = bool(np.nanmean(Tc[[i for i in idx if Pc[i] >= 30] or idx]) <= 0.5)
                info[key] = {'range': f"{Rn.fmt_t(tmin)}…{Rn.fmt_t(tmax)}", 'rain': rain_spans(Pc, loc, lang, dd), 'wear': wear(lang, tmin, tmax, pmax, snow, float(np.nanmax(Wc[idx]))),
                             'p': int(pmax), 'snow': snow}
            REG[(region, lang)] = (R, loc, info, city)
            fdir = out / f'frames_{region}_{lang}'; fdir.mkdir(exist_ok=True)
            jobs = [(region, lang, k, fdir / f'{k:03d}.png') for k in range(HOURS)]
            import multiprocessing as mp
            with mp.get_context('fork').Pool(a.jobs) as pool: list(pool.imap_unordered(_frame, jobs, chunksize=4))
            mp4 = out / f'{region}_{lang}.mp4'
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '1', '-i', str(fdir / '%03d.png'), '-vf', 'fps=25,format=yuv420p', '-c:v', 'libx264', '-crf', '27',
                            '-preset', 'medium', '-movflags', '+faststart', str(mp4)], check=True)
            import shutil; shutil.rmtree(fdir)
            json.dump({'region': region, 'lang': lang, 'city': Rn.city_name(city, lang), 'start': loc[0].strftime('%Y-%m-%dT%H:00'), 'info': info, 'video': f'hr/{mp4.name}'},
                      open(out / f'{region}_{lang}.json', 'w'), ensure_ascii=False)
            index.append({'region': region, 'lang': lang, 'video': f'hr/{mp4.name}'})
            print('hourly', region, lang, mp4.stat().st_size // 1024, 'KB', flush=True)
    json.dump({'run': D['run'], 'items': index}, open(out / 'index.json', 'w'))


if __name__ == '__main__':
    main()
