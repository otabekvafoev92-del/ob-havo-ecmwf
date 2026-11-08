"""The weather by regions (oblasts) and districts of Uzbekistan, Kazakhstan and Kyrgyzstan, for today and tomorrow.
Called by prob/hourly.py with the region's hourly fields (the same numbers as the hourly video and the interactive map):
  out/hr/<region>_admin.json         every region and district: lowest/highest temperature, chance of rain or snow, wind
  out/hr/<region>_geo.json           the region and district borders with their names (the interactive map draws them)
  out/hr/<region>_adm_<lang>_<k>.png the map of the regions for today (k=0) and tomorrow (k=1), Full HD
Borders: geoBoundaries (CC BY 4.0)."""
import datetime as dt, json, pathlib
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
COUNTRIES = ('UZ', 'KZ', 'KG')
TX = {'ru': dict(title='Погода по регионам', today='Сегодня', tomorrow='Завтра', leg='Вероятность осадков за день: синий — дождь, сиреневый — снег', low='без осадков'),
      'uz': dict(title='Viloyatlar bo‘yicha ob-havo', today='Bugun', tomorrow='Ertaga', leg='Kunlik yog‘in ehtimoli: ko‘k — yomg‘ir, binafsha — qor', low='yog‘insiz'),
      'tr': dict(title='Bölgelere göre hava', today='Bugün', tomorrow='Yarın', leg='Günlük yağış olasılığı: mavi — yağmur, mor — kar', low='yağışsız')}
SHORT = {'ru': [(' обл.', ''), ('Восточно-Казахстанская', 'Вост.-Казахстанская'), ('Западно-Казахстанская', 'Зап.-Казахстанская'), ('Северо-Казахстанская', 'Сев.-Казахстанская')],
         'uz': [(' viloyati', ''), (' shahri', '')], 'tr': [(' bölgesi', '')]}


def load(region):
    g = json.load(open(HERE / 'geo_admin.json'))
    return g.get(region)


def cells_of(rings, LON, LAT):
    """The grid points inside a unit (any of its rings); a small unit with no point gets the nearest one."""
    from matplotlib.path import Path
    pts = np.c_[LON.ravel(), LAT.ravel()]; m = np.zeros(len(pts), bool)
    for r in rings:
        a = np.asarray(r); bb = (pts[:, 0] >= a[:, 0].min()) & (pts[:, 0] <= a[:, 0].max()) & (pts[:, 1] >= a[:, 1].min()) & (pts[:, 1] <= a[:, 1].max())
        if bb.any(): m[np.flatnonzero(bb)[Path(a).contains_points(pts[bb])]] = True
    return np.flatnonzero(m)


def stats(R, loc, win_day, Pw, idx, c):
    """Per day (today, tomorrow): [tmin, tmax, chance %, snow 0/1, wind max] over the unit's grid points."""
    if not len(idx):  # nothing inside (a city district): the nearest point to its centre
        d = (R.LON - c[0]) ** 2 + (R.LAT - c[1]) ** 2; idx = np.array([int(np.argmin(d))])
    T = R.T.reshape(R.T.shape[0], -1)[:, idx] if getattr(R, 'T', None) is not None else None
    W = R.Wd.reshape(R.Wd.shape[0], -1)[:, idx] if getattr(R, 'Wd', None) is not None else None
    P = np.clip(R.P.reshape(R.P.shape[0], -1)[:, idx], 0, 100)
    out = []
    for k in range(2):
        dd = loc[0].date() + dt.timedelta(days=k); h = [i for i, t in enumerate(loc) if t.date() == dd]
        if not h: out.append(None); continue
        tmin = float(np.nanmean(np.nanmin(T[h], 0))) if T is not None else None
        tmax = float(np.nanmean(np.nanmax(T[h], 0))) if T is not None else None
        # the day's chance: the model windows of that day (the rule of the daily texts), the wetter quarter of the unit
        wd = [i for i, d_ in enumerate(win_day) if d_ == dd]
        Pd = Pw.reshape(Pw.shape[0], -1)[wd][:, idx] if wd else P[h]
        p = float(np.nanmax(np.nanpercentile(Pd, 75, axis=1)))
        wet = [i for i in h if np.nanpercentile(P[i], 75) >= 30] or h
        snow = int(T is not None and float(np.nanmean(T[wet])) <= 0.5)
        w = float(np.nanmax(np.nanmean(W[h], 1))) if W is not None else 0.0
        out.append([round(tmin, 1) if tmin is not None else None, round(tmax, 1) if tmax is not None else None, int(round(p)), snow, round(w, 1)])
    return out


def build(R, region, loc, win_day, Pw, out, langs, run):
    """Everything for one country; Pw = the precipitation chance on the model windows (before the hours)."""
    G = load(region)
    if not G: return None
    LON, LAT = R.LON, R.LAT
    res = {'region': region, 'run': run.strftime('%Y-%m-%dT%H:00Z'), 'days': [(loc[0].date() + dt.timedelta(days=k)).isoformat() for k in range(2)], 'adm1': [], 'adm2': []}
    for a in G['adm1']:
        res['adm1'].append({'id': a['id'], 'name': a['name'], 'c': a['c'], 'v': stats(R, loc, win_day, Pw, cells_of(a['r'], LON, LAT), a['c'])})
    for a in G['adm2']:
        res['adm2'].append({'p': a['p'], 'name': a['name'], 'c': a['c'], 'v': stats(R, loc, win_day, Pw, cells_of(a['r'], LON, LAT), a['c'])})
    json.dump(res, open(out / f'{region}_admin.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    json.dump({'adm1': [{'id': a['id'], 'name': a['name'], 'c': a['c'], 'r': a['r']} for a in G['adm1']],
               'adm2': [{'p': a['p'], 'name': a['name'], 'c': a['c'], 'r': a['r']} for a in G['adm2']]},
              open(out / f'{region}_geo.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    for lang in langs:
        for k in range(2):
            try: picture(R, G, res, region, lang, k, loc, out / f'{region}_adm_{lang}_{k}.png')
            except Exception as e: print('admin picture failed', region, lang, k, e, flush=True)
    print('admin', region, len(res['adm1']), 'regions', len(res['adm2']), 'districts', flush=True)
    return res


def picture(R, G, res, region, lang, k, loc, path):
    import render as Rn
    from render import plt, matplotlib
    from regions import NAMES, T as TT
    from hourly import NAVY, PAPER, LAND, RAIN_C, SNOW_C
    X = TX.get(lang, TX['ru']); L = TT[lang]
    fig = plt.figure(figsize=(12.8, 7.2), dpi=150); fig.patch.set_facecolor(PAPER)
    fig.patches.append(matplotlib.patches.Rectangle((0, 0.93), 1, 0.07, transform=fig.transFigure, facecolor=NAVY, edgecolor='none', zorder=-6))
    ink0 = Rn.INK; Rn.INK = '#ffffff'
    try: x = Rn._brand(fig, 0.016, 0.965, size=11)
    finally: Rn.INK = ink0
    fig.text(x + 0.014, 0.965, f"{NAMES[region][lang]} · {X['title']}", fontsize=14, fontfamily=Rn.DISPLAY, fontweight='bold', color='#ffffff', va='center')
    d = loc[0].date() + dt.timedelta(days=k)
    fig.text(0.984, 0.965, f"{X['today'] if k == 0 else X['tomorrow']} · {L['wd'][d.weekday()]} {d:%d.%m}", fontsize=15, fontfamily=Rn.DISPLAY, fontweight='bold', color='#f0b88a', ha='right', va='center')
    box = [0.006, 0.075, 0.988, 0.85]; ax = fig.add_axes(box); ax.axis('off')
    P_ = lambda r: np.c_[R.proj(np.asarray(r)[:, 0], np.asarray(r)[:, 1])]
    rings = R.cpoly.get(region, [])
    xs = np.concatenate([r[:, 0] for r in rings]); ys = np.concatenate([r[:, 1] for r in rings])
    e0, e1, f0, f1 = xs.min(), xs.max(), ys.min(), ys.max(); px, py = (e1 - e0) * 0.02, (f1 - f0) * 0.03
    e0, e1, f0, f1 = e0 - px, e1 + px, f0 - py, f1 + py; asp = box[2] * 12.8 / (box[3] * 7.2)
    if (e1 - e0) / (f1 - f0) < asp: c_ = (e0 + e1) / 2; w_ = (f1 - f0) * asp; e0, e1 = c_ - w_ / 2, c_ + w_ / 2
    else: c_ = (f0 + f1) / 2; h_ = (e1 - e0) / asp; f0, f1 = c_ - h_ / 2, c_ + h_ / 2
    ax.set_xlim(e0, e1); ax.set_ylim(f0, f1); ax.set_aspect('equal', adjustable='box')
    PC, LC = matplotlib.collections.PolyCollection, matplotlib.collections.LineCollection
    ax.add_collection(PC([r for c__, rr in R.cpoly.items() if c__ != region for r in rr], facecolor=LAND, edgecolor='#ffffff', linewidths=1.2, zorder=1))
    # each region coloured by its chance of rain (blue) or snow (lilac); dry regions stay white
    def col(v):
        if not v or v[2] < 30: return '#ffffff'
        cs = SNOW_C if v[3] else RAIN_C; return cs[min(3, (v[2] - 30) // 20)]
    by1 = {a['id']: a for a in res['adm1']}
    for a in G['adm1']:
        v = by1[a['id']]['v'][k]
        ax.add_collection(PC([P_(r) for r in a['r']], facecolor=col(v), edgecolor='none', zorder=2))
    ax.add_collection(LC([P_(r) for a in G['adm2'] for r in a['r']], colors='#a3b3c4', linewidths=0.55, alpha=0.85, zorder=3))  # districts, clearly visible
    ax.add_collection(LC([P_(r) for a in G['adm1'] for r in a['r']], colors='#8a9bb0', linewidths=1.0, zorder=3.5))  # regions
    ax.add_collection(LC(rings, colors=NAVY, linewidths=1.8, zorder=4))
    # a label per region: the name, the temperatures, the chance — moved apart where they would overlap
    fig.canvas.draw(); rnd = fig.canvas.get_renderer(); placed = []
    labs = sorted(res['adm1'], key=lambda a: -len(a['name']['ru']))
    for a in labs:
        v = a['v'][k]
        if not v: continue
        nm = a['name'].get(lang) or a['name']['ru']
        for s0, s1 in SHORT.get(lang, []): nm = nm.replace(s0, s1)
        t = f"{Rn.fmt_t(v[0])}…{Rn.fmt_t(v[1])}" if v[0] is not None else ''
        pr = (f"{'❄' if v[3] else '☂'} {v[2]}%") if v[2] >= 20 else X['low']
        cx, cy = R.proj(*a['c'])
        for dy in (0, 1, -1, 2, -2, 3, -3):
            y_ = cy + dy * (f1 - f0) * 0.035
            tx = ax.text(cx, y_, f"{nm}\n{t}  {pr}", fontsize=7.6 if region == 'KZ' else 8.2, ha='center', va='center', color=NAVY, fontweight='bold', linespacing=1.25, zorder=8,
                         bbox=dict(boxstyle='round,pad=0.28,rounding_size=0.6', fc='#ffffffe6', ec='#c9d3de', lw=0.6))
            bb = tx.get_window_extent(rnd).expanded(1.04, 1.1)
            if not any(bb.overlaps(o) for o in placed): placed.append(bb); break
            tx.remove()
    # the legend under the map
    lx = 0.016
    for cs, lab in ((RAIN_C, ''), (SNOW_C, '')):
        for j, c in enumerate(cs):
            fig.patches.append(matplotlib.patches.FancyBboxPatch((lx + j * 0.022, 0.028), 0.02, 0.018, boxstyle='round,pad=0,rounding_size=0.004', transform=fig.transFigure, facecolor=c, edgecolor='none'))
        lx += 0.1
    fig.text(lx, 0.037, f"30 · 50 · 70 · 90 %   {X['leg']}", fontsize=9, color='#5b6b80', va='center')
    fig.text(0.984, 0.037, 'ECMWF · NOAA · DWD · geoBoundaries', fontsize=8, color='#8a9bb0', ha='right', va='center')
    fig.savefig(path, dpi=150, facecolor=PAPER); plt.close(fig)
