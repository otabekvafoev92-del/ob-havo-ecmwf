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
               when='Осадки', none='Осадков не ожидается', low='Осадки маловероятны ({p} %)', likely='вероятны {a}–{b} ч (до {p} %)', wear='Что надеть', umbrella='зонт', boots='непромокаемая обувь', windbr='ветровка',
               c=['зимняя куртка, шапка, перчатки', 'тёплая куртка и шапка', 'куртка или пальто, шарф', 'лёгкая куртка или свитер', 'кофта, вечером лёгкая куртка', 'футболка и лёгкая одежда', 'лёгкая одежда, головной убор, вода'],
               strip='48 часов: вероятность осадков и температура', feel='ощущается как'),
    'uz': dict(title='Bugun va ertaga soatma-soat', today='Bugun', tomorrow='Ertaga', now='Hozir', rain='yomg‘ir', snow='qor', dry='yog‘insiz', wind='shamol', ms='m/s',
               when='Yog‘in', none='Yog‘in kutilmaydi', low='Yog‘in ehtimoli past ({p} %)', likely='{a}–{b} soatlarda ehtimoli bor ({p} % gacha)', wear='Nima kiyish kerak', umbrella='soyabon', boots='suv o‘tkazmaydigan poyabzal', windbr='shamoldan himoya kurtka',
               c=['qishki kurtka, telpak, qo‘lqop', 'issiq kurtka va telpak', 'kurtka yoki palto, sharf', 'yengil kurtka yoki sviter', 'kofta, kechqurun yengil kurtka', 'futbolka, yengil kiyim', 'yengil kiyim, bosh kiyim, suv'],
               strip='48 soat: yog‘in ehtimoli va harorat', feel='his qilinadi'),
    'tr': dict(title='Bugün ve yarın saat saat', today='Bugün', tomorrow='Yarın', now='Şimdi', rain='yağmur', snow='kar', dry='yağışsız', wind='rüzgâr', ms='m/s',
               when='Yağış', none='Yağış beklenmiyor', low='Yağış olasılığı düşük (%{p})', likely='{a}–{b} saatleri arasında olası (%{p} e kadar)', wear='Ne giymeli', umbrella='şemsiye', boots='su geçirmez ayakkabı', windbr='rüzgârlık',
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


def rain_spans(P, hours, lang, day0, pday=None):
    """Hours of a local day with probability ≥ 40 % as 'a–b' spans. pday: the day's chance from the model windows,
    the same number as the 15-day text and the city list (below 20 % "no precipitation", as there)."""
    X = TX[lang]; idx = [i for i, h in enumerate(hours) if h.date() == day0]
    if not idx: return None
    wet = [i for i in idx if P[i] >= 40]
    pd_ = int(round(pday)) if pday is not None else int(P[idx].max())
    if not wet: return X['none'] if pd_ < 20 else X['low'].format(p=pd_)
    spans, a = [], wet[0]
    for i, j in zip(wet, wet[1:] + [None]):
        if j != i + 1: spans.append((a, i)); a = j
    a, b = max(spans, key=lambda s: P[s[0]:s[1] + 1].max())
    return X['likely'].format(a=hours[a].hour, b=(hours[b].hour + 1) % 24 or 24, p=max(int(P[a:b + 1].max()), pd_))


def to_hours(R, D, run, off):
    """Interpolate the region's fields from model windows to every hour of local today and tomorrow (00:00 → 23:00),
    so the video always covers whole days, whenever it was built."""
    st = np.array([int(x) for x in D['steps']], float); wn = np.array([int(x) for x in D['win']], float)
    mid = st - wn / 2  # window middles, hours from the run
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    midnight = (now + dt.timedelta(hours=off)).replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(hours=off)  # local 00:00 in UTC
    h0 = max(np.floor(mid[0]), np.round((midnight - run).total_seconds() / 3600))
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


NAVY, PAPER, LAND, ICE = '#2b3a4e', '#f3f5f7', '#e6e9ed', '#ffffff'
RAIN_C = ['#bcdcf2', '#8cc0e6', '#5a9fd6', '#3a78b5']   # 30–50–70–90 %: soft blues
SNOW_C = ['#e4d4f0', '#ccb0e3', '#ad8bd0', '#8a63b8']   # the same steps for snow: soft lilac
P_LV = [30, 50, 70, 90, 101]
LEG = {'ru': ('Вероятность осадков', 'синий — дождь, сиреневый — снег; пунктир — температура'), 'uz': ('Yog‘in ehtimoli', 'ko‘k — yomg‘ir, binafsha — qor; punktir — harorat'), 'tr': ('Yağış olasılığı', 'mavi — yağmur, mor — kar; kesikli — sıcaklık')}


def _kind(p, c, t):
    """The weather of one place and hour as an icon: sun, part cloud, cloud, rain, snow."""
    if p >= 50: return 'snow' if t <= 0.5 else 'rain'
    if c >= 0.75: return 'cloud'
    if c >= 0.3 or p >= 30: return 'part'
    return 'sun'


def icon(fig, cx, cy, h, kind):
    """A small flat weather icon in figure coordinates (h = its height as a fraction of the frame)."""
    w = h * 9 / 16; tf = fig.transFigure; add = fig.patches.append
    E = lambda x, y, r, fc, z=10: add(matplotlib.patches.Ellipse((cx + x * w, cy + y * h), 2 * r * w, 2 * r * h, transform=tf, fc=fc, ec='none', zorder=z))
    if kind in ('sun', 'part'):
        sx, sy = (-0.12, 0.12) if kind == 'part' else (0, 0)
        for i in range(8):
            a_ = i * np.pi / 4
            fig.add_artist(matplotlib.lines.Line2D([cx + (sx + 0.30 * np.cos(a_)) * w, cx + (sx + 0.42 * np.cos(a_)) * w], [cy + (sy + 0.30 * np.sin(a_)) * h, cy + (sy + 0.42 * np.sin(a_)) * h],
                                                   color='#f4b740', lw=1.6, solid_capstyle='round', transform=tf, zorder=9))
        E(sx, sy, 0.22, '#f6c453', 9.5)
    if kind in ('part', 'cloud', 'rain', 'snow'):
        cc = '#9fb0c3' if kind in ('rain', 'snow') else '#b9c6d4'; dy = 0.08 if kind in ('rain', 'snow') else -0.05
        for x, y, r in ((-0.14, dy, 0.18), (0.06, dy + 0.08, 0.24), (0.24, dy - 0.02, 0.16)): E(x, y, r, cc, 11)
        add(matplotlib.patches.FancyBboxPatch((cx - 0.30 * w, cy + (dy - 0.17) * h), 0.6 * w, 0.17 * h, boxstyle='round,pad=0,rounding_size=0.004', transform=tf, fc=cc, ec='none', zorder=11))
    if kind == 'rain':
        for x in (-0.16, 0.02, 0.20):
            fig.add_artist(matplotlib.lines.Line2D([cx + x * w, cx + (x - 0.05) * w], [cy - 0.16 * h, cy - 0.34 * h], color='#4f8cc4', lw=1.6, solid_capstyle='round', transform=tf, zorder=12))
    if kind == 'snow':
        for x, y in ((-0.16, -0.22), (0.04, -0.30), (0.22, -0.22)): E(x, y, 0.045, '#9a78c2', 12)


def frame(R, k, lang, path, loc, info, city):
    """Full HD 16:9, soft and plain: a dark title band with the hour, the country alone in colour (rain and snow only
    where they are likely, ≥ 30 %), a white pill with the temperature and an icon at every city, the chosen city on the
    right, and 48 hours along the bottom."""
    X = TX[lang]; L = TT[lang]
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100); fig.patch.set_facecolor(PAPER)
    # a thin title band: brand, country, the hour
    fig.patches.append(matplotlib.patches.Rectangle((0, 0.93), 1, 0.07, transform=fig.transFigure, facecolor=NAVY, edgecolor='none', zorder=-6))
    ink0 = Rn.INK; Rn.INK = '#ffffff'
    try: x = Rn._brand(fig, 0.016, 0.965, size=11)
    finally: Rn.INK = ink0
    fig.text(x + 0.014, 0.965, NAMES[R.id][lang], fontsize=14, fontfamily=Rn.DISPLAY, fontweight='bold', color='#ffffff', va='center')
    t = loc[k]; day = X['today'] if t.date() == loc[0].date() else X['tomorrow'] if t.date() == loc[0].date() + dt.timedelta(days=1) else ''
    tm = fig.text(0.984, 0.965, f"{t:%H}:00", fontsize=19, fontfamily=Rn.DISPLAY, fontweight='bold', color='#f0b88a', ha='right', va='center')
    tb2 = tm.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
    fig.text(tb2.x0 - 0.012, 0.965, f"{day} · {L['wd'][t.weekday()]} {t:%d.%m} · {Rn.VIEW_TZ_LABEL.get(lang, '')}", fontsize=11, fontweight='bold', color='#c9d6e5', ha='right', va='center')
    # the map
    box = [0.004, 0.15, 0.81, 0.775]  # the map takes most of the frame
    ax = fig.add_axes(box); ax.axis('off')
    rings = R.cpoly.get(R.id, []) or [r for rr in R.cpoly.values() for r in rr]
    xs = np.concatenate([r[:, 0] for r in rings]); ys = np.concatenate([r[:, 1] for r in rings])
    e0, e1, f0, f1 = xs.min(), xs.max(), ys.min(), ys.max(); px, py = (e1 - e0) * 0.015, (f1 - f0) * 0.03
    e0, e1, f0, f1 = e0 - px, e1 + px, f0 - py, f1 + py; asp = box[2] * 12.8 / (box[3] * 7.2)
    if (e1 - e0) / (f1 - f0) < asp: c_ = (e0 + e1) / 2; w_ = (f1 - f0) * asp; e0, e1 = c_ - w_ / 2, c_ + w_ / 2
    else: c_ = (f0 + f1) / 2; h_ = (e1 - e0) / asp; f0, f1 = c_ - h_ / 2, c_ + h_ / 2
    ax.set_xlim(e0, e1); ax.set_ylim(f0, f1); ax.set_aspect('equal', adjustable='box')
    PC, LC = matplotlib.collections.PolyCollection, matplotlib.collections.LineCollection
    ax.add_collection(PC([r for c__, rr in R.cpoly.items() if c__ != R.id for r in rr], facecolor=LAND, edgecolor='#ffffff', linewidths=1.2, zorder=1))
    ax.add_collection(PC(rings, facecolor=ICE, edgecolor='none', zorder=1.5))
    U = Rn._up(R, np.clip(R.P[k], 0, 100)); TU = Rn._up(R, R.T[k]) if getattr(R, 'T', None) is not None else None
    verts = np.concatenate(rings); codes = np.concatenate([[1] + [2] * (len(r) - 2) + [79] for r in rings])
    for F, cols in ((np.where(TU > 0.5, U, 0) if TU is not None else U, RAIN_C), (np.where(TU <= 0.5, U, 0) if TU is not None else None, SNOW_C)):
        if F is None or F.max() < P_LV[0]: continue
        out_ = ax.contourf(R.XU, R.YU, F, levels=P_LV, colors=cols, alpha=0.35, zorder=1.2)  # the neighbours: faint
        cs = ax.contourf(R.XU, R.YU, F, levels=P_LV, colors=cols, zorder=2)
        edge = ax.contour(R.XU, R.YU, F, levels=P_LV[:-1], colors=[cols[-1]], linewidths=[0.9, 0.9, 1.1, 1.3], alpha=0.75, zorder=2.2)  # the edges of the rain/snow areas
        clip = matplotlib.patches.PathPatch(matplotlib.path.Path(verts, codes), transform=ax.transData, facecolor='none', edgecolor='none'); ax.add_patch(clip); cs.set_clip_path(clip); edge.set_clip_path(clip)
    if TU is not None and np.isfinite(TU).any():  # isotherms every 5°, labelled, inside the country
        lo_, hi_ = np.nanmin(TU), np.nanmax(TU); lv_ = [v for v in range(-40, 50, 5) if lo_ < v < hi_]
        if lv_:
            iso = ax.contour(R.XU, R.YU, TU, levels=lv_, colors='#e0895a', linewidths=0.9, linestyles='--', alpha=0.85, zorder=2.6)
            clip2 = matplotlib.patches.PathPatch(matplotlib.path.Path(verts, codes), transform=ax.transData, facecolor='none', edgecolor='none'); ax.add_patch(clip2); iso.set_clip_path(clip2)
            lab = ax.clabel(iso, fmt=lambda v: Rn.fmt_t(v), fontsize=8, inline=True, inline_spacing=4)
            for t_ in lab:
                t_.set_color('#c8784a'); t_.set_fontweight('bold')
                if not matplotlib.path.Path(verts, codes).contains_point(t_.get_position()): t_.set_visible(False)
    ax.add_collection(LC(R.a1, colors='#c9d3de', linewidths=0.7, zorder=3))
    ax.add_collection(LC(rings, colors=NAVY, linewidths=6, alpha=0.06, zorder=3.5))
    ax.add_collection(LC(rings, colors=NAVY, linewidths=1.8, zorder=4))
    # the cities: a white pill with the temperature, the name under it, an icon at the left
    fig.canvas.draw(); rnd = fig.canvas.get_renderer(); placed = []; axb = ax.get_window_extent()
    cities = [city] + [p for p in R.cities if p is not city]
    dots = [ax.transData.transform(R.proj(p['lon'], p['lat'])) for p in cities]
    for j, p in enumerate(cities):
        cx, cy = R.proj(p['lon'], p['lat']); ax.plot(cx, cy, 'o', ms=6 if j == 0 else 4.5, mfc=NAVY, mec='#ffffff', mew=1.4, zorder=6)
    for j, p in enumerate(cities):
        cx, cy = R.proj(p['lon'], p['lat']); main = j == 0
        tt = R.value_at(k, p, 'T'); pp = R.value_at(k, p); cc = R.value_at(k, p, 'C') if getattr(R, 'C', None) is not None else 0.5
        if not np.isfinite(tt): continue
        for (ox, oy, ha, va) in ((0, 8, 'center', 'bottom'), (10, 0, 'left', 'center'), (-10, 0, 'right', 'center'), (0, -8, 'center', 'top'),
                                 (10, 9, 'left', 'bottom'), (-10, 9, 'right', 'bottom'), (10, -9, 'left', 'top'), (-10, -9, 'right', 'top')):
            pill = ax.annotate(f"{Rn.city_name(p, lang)}  {Rn.fmt_t(tt)}", (cx, cy), xytext=(ox, oy), textcoords='offset points', ha=ha, va=va, fontsize=13 if main else 10.5, fontweight='bold', color=NAVY, zorder=7,
                               bbox=dict(boxstyle='round,pad=0.32,rounding_size=0.9', fc='#ffffff', ec=('#e0895a' if main else '#cfd7e0'), lw=1.8 if main else 1.0, alpha=0.96))
            name = None
            pb = pill.get_window_extent(rnd); bb = pb.padded(4)
            ok = axb.contains(bb.x0, bb.y0) and axb.contains(bb.x1, bb.y1) and not any(bb.overlaps(o) for o in placed) and not any(bb.contains(*d) for i_, d in enumerate(dots) if i_ != j)
            if ok: placed.append(bb); break
            pill.remove()
        else:  # no free place: a small pill above the dot, no name
            ax.annotate(Rn.fmt_t(tt), (cx, cy), xytext=(0, 7), textcoords='offset points', ha='center', va='bottom', fontsize=9.5, fontweight='bold', color=NAVY, zorder=7,
                        bbox=dict(boxstyle='round,pad=0.25,rounding_size=0.8', fc='#ffffff', ec='#d5dce4', lw=0.8))
    # what the colours mean: a small key in the corner of the map (its own axes, above the map)
    lg = fig.add_axes([0.012, 0.16, 0.25, 0.062], zorder=20); lg.set_xlim(0, 1); lg.set_ylim(0, 1); lg.axis('off')
    lg.add_patch(matplotlib.patches.FancyBboxPatch((0, 0), 1, 1, boxstyle='round,pad=0,rounding_size=0.08', fc='#ffffff', ec='#dde3ea', lw=0.8, transform=lg.transAxes, mutation_aspect=0.3))
    lg.text(0.04, 0.8, LEG[lang][0], fontsize=7.6, fontweight='bold', color=NAVY, va='center')
    for i_, (c1, c2, lv) in enumerate(zip(RAIN_C, SNOW_C, ('30', '50', '70', '90 %'))):
        x_ = 0.04 + i_ * 0.19
        lg.add_patch(matplotlib.patches.Rectangle((x_, 0.4), 0.06, 0.22, fc=c1, ec='none')); lg.add_patch(matplotlib.patches.Rectangle((x_ + 0.06, 0.4), 0.04, 0.22, fc=c2, ec='none'))
        lg.text(x_ + 0.115, 0.51, lv, fontsize=7.2, color=NAVY, va='center')
    lg.text(0.04, 0.17, LEG[lang][1], fontsize=6.8, color=Rn.MUTED, va='center')
    # the chosen city
    PX, PW = 0.82, 0.172; X0, X1 = PX + 0.014, PX + PW - 0.014
    Rn._card(fig, PX, 0.15, PW, 0.77, fc='#ffffff', ec='#dde3ea', r=0.012)
    tt = R.value_at(k, city, 'T'); v = max(0, min(100, R.value_at(k, city)))
    c = R.value_at(k, city, 'C') if getattr(R, 'C', None) is not None else np.nan; ws = R.value_at(k, city, 'Wd') if getattr(R, 'Wd', None) is not None else np.nan
    snow = np.isfinite(tt) and tt <= 0.5
    fig.text(X0, 0.88, Rn.city_name(city, lang), fontsize=12.5, fontweight='bold', color=Rn.MUTED, va='center')
    icon(fig, X0 + 0.022, 0.81, 0.07, _kind(v, c if np.isfinite(c) else 0.5, tt if np.isfinite(tt) else 10))
    fig.text(X0 + 0.052, 0.81, Rn.fmt_t(tt) if np.isfinite(tt) else '—', fontsize=30, fontfamily=Rn.DISPLAY, fontweight='bold', color=NAVY, va='center')
    rows = [((X['snow'] if snow else X['rain']).capitalize(), f'{v:.0f} %')]
    if np.isfinite(c): rows.append((L['clouds'][0], f'{c * 100:.0f} %'))
    if np.isfinite(ws): rows.append((X['wind'].capitalize(), f"{ws:.0f} {X['ms']}"))
    for i, (a_, b_) in enumerate(rows):
        y = 0.73 - i * 0.045
        fig.text(X0, y, a_, fontsize=10.5, color=Rn.MUTED, va='center'); fig.text(X1, y, b_, fontsize=12.5, fontweight='bold', color=NAVY, va='center', ha='right')
        fig.add_artist(matplotlib.lines.Line2D([X0, X1], [y - 0.022, y - 0.022], color='#e8edf2', lw=0.8, transform=fig.transFigure))
    # today and tomorrow in two short lines each: the range and the chance of rain or snow (the details are in the bot's text)
    y = 0.565
    for lbl, d in ((X['today'], info['today']), (X['tomorrow'], info['tomorrow'])):
        if not d: continue
        fig.text(X0, y, lbl, fontsize=11.5, fontweight='bold', color=NAVY, va='center'); y -= 0.04
        fig.text(X0, y, d['range'], fontsize=17, fontfamily=Rn.DISPLAY, fontweight='bold', color=NAVY, va='center'); y -= 0.04
        pr = int(d.get('p', 0)); kind_ = X['snow'] if d.get('snow') else X['rain']
        fig.text(X0, y, f"{kind_.capitalize()} {pr} %" if pr >= 20 else X['dry'].capitalize(), fontsize=10.5, color='#4f8cc4' if pr >= 20 else Rn.MUTED, va='center'); y -= 0.07
    # 48 hours
    Rn._card(fig, 0.004, 0.022, 0.988, 0.12, fc='#ffffff', ec='#dde3ea', r=0.012)
    fig.text(0.016, 0.126, X['strip'], fontsize=8, color=Rn.MUTED, va='center')
    bx = fig.add_axes([0.04, 0.045, 0.925, 0.07]); bx.set_facecolor('none')
    P = np.clip(R.series(city), 0, 100)[:HOURS]; Ts = R.tseries(city); Ts = Ts[:HOURS] if Ts is not None else None
    cols = [(SNOW_C if (Ts is not None and Ts[i] <= 0.5) else RAIN_C)[int(np.clip(np.digitize(p, P_LV) - 1, 0, 3))] if p >= 20 else '#edf1f5' for i, p in enumerate(P)]
    bx.bar(np.arange(HOURS), np.maximum(P, 4), width=0.72, color=cols, zorder=2); bx.set_ylim(0, 100); bx.set_xlim(-0.6, HOURS - 0.4)
    bx.axvspan(k - 0.5, k + 0.5, color='#f0b88a', alpha=0.28, lw=0, zorder=1)
    for m in [i for i, h in enumerate(loc[:HOURS]) if h.hour == 0]:
        bx.axvline(m - 0.5, color='#dfe5ec', lw=1, zorder=1)
        bx.text(m - 0.2, 96, f"{L['wd'][loc[m].weekday()]} {loc[m]:%d.%m}", fontsize=7.5, color=Rn.MUTED, va='top')
    ticks = [i for i, h in enumerate(loc[:HOURS]) if h.hour % 3 == 0]
    bx.set_xticks(ticks); bx.set_xticklabels([f"{loc[i]:%H}" for i in ticks], fontsize=8, color=Rn.MUTED)
    bx.set_yticks([]); bx.tick_params(length=0)
    for sp in bx.spines.values(): sp.set_visible(False)
    if Ts is not None:
        tx2 = bx.twinx(); xs_ = np.arange(HOURS)
        tx2.plot(xs_, Ts, color='#e0895a', lw=1.8, solid_capstyle='round'); tx2.plot([k], [Ts[k]], 'o', ms=6, color='#e0895a', mec='#ffffff', mew=1.5)
        lo, hi = np.nanmin(Ts), np.nanmax(Ts); tx2.set_ylim(lo - (hi - lo) * 0.25 - 1, hi + (hi - lo) * 0.45 + 1)
        tx2.annotate(Rn.fmt_t(Ts[k]), (k, Ts[k]), xytext=(0, 8), textcoords='offset points', ha='center', fontsize=9, fontweight='bold', color='#c8784a')
        tx2.set_yticks([])
        for sp in tx2.spines.values(): sp.set_visible(False)
    fig.text(0.014, 0.012, 'ECMWF · NOAA · DWD', fontsize=6.6, color=Rn.FAINT, va='center')
    fig.text(0.986, 0.012, 't.me/ObHavo_ECMWF_bot', fontsize=6.6, color=Rn.FAINT, va='center', ha='right')
    fig.savefig(path, dpi=150, facecolor=PAPER); plt.close(fig)


def export_live(R, region, loc, out, run, off, suffix='live', times=None):
    """The data of the interactive map (site/live.html, opened from the bot): the region's 48 hours on its own grid
    (precipitation chance, temperature, clouds, wind, as bytes), the outlines and the cities.
      out/hr/<region>_live.bin  [hour][var P,T,C,W][row][col] uint8 (255 = no data)
      out/hr/<region>_live.json the grid, the hours, outlines, cities"""
    g = json.load(open(HERE / 'geo_prob.json'))
    rings = g['countries'].get(region, {}).get('rings') or [r for c in g['countries'].values() for r in c['rings']][:0]
    if not rings: return
    a_ = np.concatenate([np.array(r) for r in rings])
    lo0, lo1, la0, la1 = a_[:, 0].min() - 0.75, a_[:, 0].max() + 0.75, a_[:, 1].min() - 0.75, a_[:, 1].max() + 0.75
    LON, LAT = R.LON[0], R.LAT[:, 0]
    cols = np.flatnonzero((LON >= lo0) & (LON <= lo1)); rows = np.flatnonzero((LAT >= la0) & (LAT <= la1))
    if not len(cols) or not len(rows): return
    st = max(1, int(np.ceil(np.sqrt(len(cols) * len(rows) / 15000))))  # big countries (Russia) on a coarser grid
    cols, rows = cols[::st], rows[::st]
    NH = len(times) if times is not None else HOURS
    sub = lambda F: None if F is None else np.asarray(F)[:NH][:, rows][:, :, cols]
    def enc(F, f, lo=0.0):
        if F is None: return np.full((NH, len(rows), len(cols)), 255, np.uint8)
        v = np.round((F + lo) * f); return np.where(np.isfinite(v), np.clip(v, 0, 254), 255).astype(np.uint8)
    cube = np.stack([enc(np.clip(sub(R.P), 0, 100), 2.5), enc(sub(R.T), 2, 60), enc(sub(R.C), 250), enc(sub(getattr(R, 'Wd', None)), 5)], 1)
    cube.tofile(out / f'{region}_{suffix}.bin')
    near = lambda r: any(lo0 - 3 <= x <= lo1 + 3 and la0 - 3 <= y <= la1 + 3 for x, y in r[::max(1, len(r) // 30)])
    rnd = lambda r: [[round(x, 3), round(y, 3)] for x, y in r]
    meta = {'region': region, 'run': run.strftime('%Y-%m-%dT%H:00Z'), 'start': (times[0] if times is not None else loc[0].strftime('%Y-%m-%dT%H:00')), 'off': off, 'hours': NH,
            **({'times': times} if times is not None else {}),
            'lon': [float(LON[cols[0]]), float(LON[cols[-1]])], 'lat': [float(LAT[rows[0]]), float(LAT[rows[-1]])], 'nx': len(cols), 'ny': len(rows),
            'vars': ['P', 'T', 'C', 'W'], 'scale': [[2.5, 0], [2, 60], [250, 0], [5, 0]],
            'country': [rnd(r) for r in rings], 'neighbours': [rnd(r) for c, v in g['countries'].items() if c != region for r in v['rings'] if near(r)],
            'admin': [rnd(r) for r in g['admin1'].get(region, [])],
            'cities': [{'ru': Rn.city_name(p, 'ru'), 'uz': Rn.city_name(p, 'uz'), 'tr': Rn.city_name(p, 'tr'), 'lat': p['lat'], 'lon': p['lon']} for p in R.cities],
            'main': {l: Rn.city_name(R.mains[l], 'ru') for l in ('uz', 'ru', 'tr') if R.mains.get(l) is not None}}
    json.dump(meta, open(out / f'{region}_{suffix}.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    print(suffix, region, len(rows), 'x', len(cols), 'step', st, flush=True)


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
        groups = {}
        for lang in a.langs.split(','):
            if lang == 'tr' and region not in ('TR', 'AZ'): continue
            groups.setdefault(Rn.VIEW_TZ.get(lang, 5), []).append(lang)
        first = True
        for vo, langs_g in groups.items():
            R = Rn.Region(D, geo, region, P, D['amt']); off = vo  # the viewer's time: Tashkent for Russian and Uzbek, Türkiye for Turkish
            # the day's chance from the model windows (before they become hours): the same rule as the daily texts
            win_day = [Rn.local_day(run, st, off, D['win'][i]) for i, st in enumerate(D['steps'])]
            pw = {lang: R.series(R.mains[lang]) for lang in a.langs.split(',') if R.mains.get(lang) is not None}
            if first:
              try:  # the 15 days for the interactive map: the model windows themselves, each with its local start time
                tw = [(run + dt.timedelta(hours=int(st) - int(D['win'][i]) + off)).strftime('%Y-%m-%dT%H:00') for i, st in enumerate(D['steps'])]
                export_live(R, region, None, out, run, off, 'live15', tw)
              except Exception as e: print('live15 export failed:', region, e, flush=True)
            hrs, loc = to_hours(R, D, run, off)
            if first:
                try: export_live(R, region, loc, out, run, off)
                except Exception as e: print('live export failed:', region, e, flush=True)
            first = False
            for lang in langs_g:
                city = R.mains[lang]
                if city is None: continue
                Pc, Tc = np.clip(R.series(city), 0, 100), R.tseries(city); Wc = R.wseries(city) if getattr(R, 'Wd', None) is not None else np.zeros(HOURS)
                info = {}
                for key, dd in (('today', loc[0].date()), ('tomorrow', loc[0].date() + dt.timedelta(days=1))):
                    idx = [i for i, h in enumerate(loc) if h.date() == dd]
                    if not idx or Tc is None: info[key] = None; continue
                    tmin, tmax = float(np.nanmin(Tc[idx])), float(np.nanmax(Tc[idx]))
                    wd_ = [i for i, d_ in enumerate(win_day) if d_ == dd]
                    pmax = float(np.nanmax(pw[lang][wd_])) if lang in pw and wd_ else float(Pc[idx].max())
                    snow = bool(np.nanmean(Tc[[i for i in idx if Pc[i] >= 30] or idx]) <= 0.5)
                    info[key] = {'range': f"{Rn.fmt_t(tmin)}…{Rn.fmt_t(tmax)}", 'rain': rain_spans(Pc, loc, lang, dd, pmax), 'wear': wear(lang, tmin, tmax, pmax, snow, float(np.nanmax(Wc[idx]))),
                                 'p': int(round(pmax)), 'snow': snow}
                REG[(region, lang)] = (R, loc, info, city)
                fdir = out / f'frames_{region}_{lang}'; fdir.mkdir(exist_ok=True)
                jobs = [(region, lang, k, fdir / f'{k:03d}.png') for k in range(HOURS)]
                import multiprocessing as mp
                with mp.get_context('fork').Pool(a.jobs) as pool: list(pool.imap_unordered(_frame, jobs, chunksize=4))
                mp4 = out / f'{region}_{lang}.mp4'
                subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '1', '-i', str(fdir / '%03d.png'), '-vf', 'framerate=fps=25:interp_start=140:interp_end=255:scene=100,format=yuv420p', '-c:v', 'libx264', '-crf', '21', '-tune', 'animation',
                                '-preset', 'medium', '-movflags', '+faststart', str(mp4)], check=True)
                try:  # the weather heard hour by hour: rain, snow, wind (and a real video in Telegram, not a silent GIF)
                    import sound as S_
                    S_.mux(mp4, S_.track(S_.from_series(Pc[:HOURS], Tc[:HOURS] if Tc is not None else None, Wc[:HOURS]), 1.0, str(mp4) + '.wav'))
                except Exception as e: print('sound failed:', mp4, e, flush=True)
                import shutil; shutil.rmtree(fdir)
                json.dump({'region': region, 'lang': lang, 'off': off, 'city': Rn.city_name(city, lang), 'start': loc[0].strftime('%Y-%m-%dT%H:00'), 'info': info, 'video': f'hr/{mp4.name}'},
                          open(out / f'{region}_{lang}.json', 'w'), ensure_ascii=False)
                index.append({'region': region, 'lang': lang, 'video': f'hr/{mp4.name}'})
                print('hourly', region, lang, mp4.stat().st_size // 1024, 'KB', flush=True)
    json.dump({'run': D['run'], 'items': index}, open(out / 'index.json', 'w'))


if __name__ == '__main__':
    main()
