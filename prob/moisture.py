"""The moisture coming in: a broadcast-style video of the next three days for Uzbekistan and Kazakhstan.
Every frame (30 minutes apart, smoothly interpolated from ECMWF's 3-hourly forecast):
  - the water vapour in the whole air column (TCWV, kg/m²): dry air light, moist air deep blue-green
  - the wind at about 3 km (700 hPa) as flowing streaks, the way the moisture travels
  - the precipitation (mm in 3 h) in radar colours where it falls
  - sea-level pressure isobars every 4 hPa with the highs (H/В/Y) and lows (L/Н/P)
  - countries, our regions, the main cities, the local time, legends, sound (wind, then rain)
  out/hr/<region>_moist_<lang>.mp4  (Full HD, about 14 s)
Data: ECMWF IFS open data (AWS mirror), the current run, steps 0…72 h.
Usage: python3 prob/moisture.py prob.npz out [--regions UZ,KZ] [--langs ru,uz] [--fields saved.npz]"""
import argparse, concurrent.futures as cf, datetime as dt, json, pathlib, shutil, subprocess, sys, tempfile
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from trajectory import ECM, get  # the same mirror and downloader

STEPS = list(range(0, 73, 3))
LON0, LON1, LAT0, LAT1, RES = 20.0, 100.0, 20.0, 60.0, 0.25
VIEW = {'UZ': (44.0, 80.0, 30.0, 49.0), 'KZ': (40.0, 92.0, 33.0, 57.5)}
TX = {'ru': dict(title='Поступление влаги', sub='водяной пар в атмосфере · ветер на высоте ~3 км · осадки · давление', tcwv='Водяной пар, кг/м²', pr='Осадки, мм за 3 ч',
                 hi='В', lo='Н', tz='по Ташкенту', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']),
      'uz': dict(title='Namlik kelishi', sub='atmosferadagi suv bug‘i · ~3 km balandlikdagi shamol · yog‘in · bosim', tcwv='Suv bug‘i, kg/m²', pr='Yog‘in, 3 soatda mm',
                 hi='Y', lo='P', tz='Toshkent vaqti', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya']),
      'tr': dict(title='Nem girişi', sub='atmosferdeki su buharı · ~3 km rüzgâr · yağış · basınç', tcwv='Su buharı, kg/m²', pr='Yağış, 3 saatte mm',
                 hi='Y', lo='A', tz='TSİ', wd=['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'])}
# water vapour on a dark map: the dry air dark slate, the moist air glowing teal-green (the moisture stands out like on satellite water-vapour images)
TCWV_STOPS = [(0, '#1f2530'), (6, '#2a3340'), (12, '#2f4450'), (18, '#2e5a60'), (25, '#2d7470'), (32, '#3a927f'), (40, '#5fb08f'), (50, '#9ccf9f'), (70, '#e3f2c0')]  # dark dry air → glowing moist air
# precipitation, radar-like colours
PR_LV = [0.3, 1, 2, 4, 7, 12, 20, 40]
PR_COL = ['#8fd0ff', '#4aa8f5', '#2b6fe0', '#f2d94e', '#f29c38', '#e0503a', '#c23aa0']  # blue (light rain) → yellow → red → magenta: apart from the green-teal moisture


def fetch(run):
    """{step: dict(tcwv, msl hPa, tp mm (accumulated from 0), u, v)} on the area grid (rows south → north)."""
    d, hh = run.strftime('%Y%m%d'), run.strftime('%H')
    jobs = []
    for st in STEPS:
        idx = None
        for stream in (('oper', 'scda') if hh in ('00', '12') else ('scda', 'oper')):
            base = f'{ECM}/{d}/{hh}z/ifs/0p25/{stream}/{d}{hh}0000-{st}h-{stream}-fc'
            idx = get(base + '.index')
            if idx: break
        if not idx: print('moist: missing step', st, flush=True); continue
        for line in idx.decode().strip().split('\n'):
            x = json.loads(line); p = x.get('param')
            key = p if x.get('levtype') == 'sfc' and p in ('tcwv', 'msl', 'tp') else p if x.get('levtype') == 'pl' and x.get('levelist') == '700' and p in ('u', 'v') else None
            if key: jobs.append((st, key, base + '.grib2', (x['_offset'], x['_offset'] + x['_length'] - 1)))
    F = {}
    import eccodes
    def crop(buf):
        h = eccodes.codes_new_from_message(buf)
        v = eccodes.codes_get_values(h).reshape(eccodes.codes_get(h, 'Nj'), eccodes.codes_get(h, 'Ni')); eccodes.codes_release(h)
        lat = 90 - np.arange(v.shape[0]) * 0.25; lon = -180 + np.arange(v.shape[1]) * 0.25
        r = np.flatnonzero((lat <= LAT1 + 1e-6) & (lat >= LAT0 - 1e-6)); c = np.flatnonzero((lon >= LON0 - 1e-6) & (lon <= LON1 + 1e-6))
        return v[np.ix_(r, c)][::-1].astype(np.float32)
    with cf.ThreadPoolExecutor(12) as pool:
        for (st, key, url, rng), buf in zip(jobs, pool.map(lambda j: get(j[2], j[3]), jobs)):
            if buf: F.setdefault(st, {})[key] = crop(buf)
    out = {}
    for st, f in F.items():
        if all(k in f for k in ('tcwv', 'msl', 'u', 'v')):
            out[st] = {'tcwv': f['tcwv'], 'msl': f['msl'] / 100.0, 'tp': f.get('tp', np.zeros_like(f['tcwv'])) * 1000.0, 'u': f['u'], 'v': f['v']}
    print('moist: fields at', len(out), 'steps', flush=True)
    return out


def interp(F, h):
    """The fields at hour h (linear between the 3-hourly steps); precipitation as mm in the 3 h around h."""
    ks = sorted(F); j = int(np.clip(np.searchsorted(ks, h), 1, len(ks) - 1)); a = float(np.clip((h - ks[j - 1]) / (ks[j] - ks[j - 1]), 0, 1))
    A, B = F[ks[j - 1]], F[ks[j]]
    out = {k: A[k] * (1 - a) + B[k] * a for k in ('tcwv', 'msl', 'u', 'v')}
    rate = lambda i: np.clip(F[ks[i]]['tp'] - F[ks[i - 1]]['tp'], 0, None) if i >= 1 else np.zeros_like(A['tp'])  # mm in the 3 h before step i
    out['pr'] = rate(j) * (1 - abs(a - 0.5)) + (rate(j - 1) if a < 0.5 else rate(min(j + 1, len(ks) - 1))) * abs(a - 0.5)
    return out


def video(F, region, lang, mp4, run, off=5):
    import render as Rn
    from render import plt, matplotlib
    from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm, ListedColormap
    from scipy.ndimage import gaussian_filter, maximum_filter, minimum_filter
    from regions import NAMES
    from hourly import NAVY
    X = TX.get(lang, TX['ru'])
    x0, x1, y0, y1 = VIEW[region]
    lon = LON0 + np.arange(next(iter(F.values()))['tcwv'].shape[1]) * RES; lat = LAT0 + np.arange(next(iter(F.values()))['tcwv'].shape[0]) * RES
    ci = np.flatnonzero((lon >= x0 - 1) & (lon <= x1 + 1)); ri = np.flatnonzero((lat >= y0 - 1) & (lat <= y1 + 1))
    LON, LAT = np.meshgrid(lon[ci], lat[ri])
    k = np.cos(np.radians((y0 + y1) / 2))
    cmap = LinearSegmentedColormap.from_list('tcwv', [(v / 70, c) for v, c in TCWV_STOPS])
    prc, prn = ListedColormap(PR_COL), BoundaryNorm(PR_LV, len(PR_COL))
    G = json.load(open(HERE / 'geo_world.json'))['countries']; GA = json.load(open(HERE / 'geo_admin.json')).get(region, {})
    fig = plt.figure(figsize=(12.8, 7.2), dpi=150); fig.patch.set_facecolor(NAVY)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect(1 / k); ax.axis('off')
    # the map width fills the frame; the height follows the latitude squeeze
    fx = 12.8 / 7.2; span = (x1 - x0) * k / fx; cy = (y0 + y1) / 2; ax.set_ylim(cy - span / 2, cy + span / 2); y0v, y1v = cy - span / 2, cy + span / 2
    PCOL, LC = matplotlib.collections.PolyCollection, matplotlib.collections.LineCollection
    near = lambda r: np.asarray(r)[:, 0].max() > x0 - 3 and np.asarray(r)[:, 0].min() < x1 + 3 and np.asarray(r)[:, 1].max() > y0v - 3 and np.asarray(r)[:, 1].min() < y1v + 3
    borders = [np.asarray(r) for c in G.values() for r in c['rings'] if near(r)]
    ax.add_collection(LC(borders, colors='#ffffff', linewidths=0.7, alpha=0.75, zorder=4))
    own = [np.asarray(r) for r in G.get(region, {}).get('rings', [])]
    if GA: ax.add_collection(LC([np.asarray(r) for a in GA['adm1'] for r in a['r']], colors='#ffffff', linewidths=0.45, alpha=0.45, zorder=4))
    ax.add_collection(LC(own, colors='#ffffff', linewidths=1.6, zorder=4.5))
    # the main cities of the country
    pl = sorted([p for p in json.load(open(HERE / 'geo_prob.json'))['places'] if p.get('iso') == region and x0 < p['lon'] < x1], key=lambda p: -p.get('pop', 0))[:8]
    for p in pl:
        ax.plot(p['lon'], p['lat'], 'o', ms=4, mfc='#ffffff', mec=NAVY, mew=0.8, zorder=8)
        ax.text(p['lon'] + 0.25, p['lat'] + 0.2, Rn.city_name(p, lang), fontsize=8.5, fontweight='bold', color='#ffffff', zorder=8,
                path_effects=[matplotlib.patheffects.withStroke(linewidth=2.2, foreground='#1d2a3a')])
    # the title band, the clock, the legends (drawn once)
    band = dict(boxstyle='round,pad=0.5,rounding_size=0.6', fc='#1d2a3acc', ec='none')
    fig.text(0.018, 0.955, f"{NAMES[region][lang]} · {X['title']}", fontsize=17, fontfamily=Rn.DISPLAY, fontweight='bold', color='#ffffff', va='center', bbox=band, zorder=20)
    fig.text(0.018, 0.893, X['sub'], fontsize=9.5, color='#e3ebf3', va='center', zorder=20, bbox=dict(boxstyle='round,pad=0.35,rounding_size=0.4', fc='#1d2a3aaa', ec='none'))
    fig.patches.append(matplotlib.patches.FancyBboxPatch((0.008, 0.012), 0.53, 0.115, boxstyle='round,pad=0,rounding_size=0.008', transform=fig.transFigure, facecolor='#1d2a3acc', edgecolor='none', zorder=19))
    clock = fig.text(0.982, 0.955, '', fontsize=17, fontfamily=Rn.DISPLAY, fontweight='bold', color='#f0b88a', ha='right', va='center', bbox=band, zorder=20)
    cax = fig.add_axes([0.018, 0.045, 0.26, 0.016]); cax.set_zorder(21); cb = matplotlib.colorbar.ColorbarBase(cax, cmap=cmap, norm=matplotlib.colors.Normalize(0, 70), orientation='horizontal')
    cb.set_ticks([0, 10, 20, 30, 40, 50, 60, 70]); cax.tick_params(labelsize=7.5, colors='#ffffff', length=2); cb.outline.set_visible(False)
    fig.text(0.018, 0.085, X['tcwv'], fontsize=8.5, color='#ffffff', fontweight='bold', zorder=21)
    pax = fig.add_axes([0.30, 0.045, 0.22, 0.016]); pax.set_zorder(21); pb = matplotlib.colorbar.ColorbarBase(pax, cmap=prc, norm=prn, orientation='horizontal', boundaries=PR_LV, ticks=PR_LV[:-1])
    pax.tick_params(labelsize=7.5, colors='#ffffff', length=2); pb.outline.set_visible(False); pax.set_xticklabels(['0.3', '1', '2', '4', '7', '12', '20'])
    fig.text(0.30, 0.085, X['pr'], fontsize=8.5, color='#ffffff', fontweight='bold', zorder=21)
    fig.text(0.982, 0.03, 'ECMWF IFS · osmon', fontsize=8, color='#c9d6e5', ha='right')
    # flowing streaks: particles carried by the 700 hPa wind, each with a fading tail
    rng = np.random.default_rng(3); N = 1700; TAIL = 10
    def seed(n): return np.c_[rng.uniform(x0, x1, n), rng.uniform(y0v, y1v, n)]
    pts = seed(N); age = rng.integers(0, 60, N); hist = np.repeat(pts[None], TAIL, 0)
    lines = [LC([], colors='#ffffff', linewidths=0.8, alpha=a, zorder=6) for a in np.linspace(0.04, 0.6, TAIL - 1) ** 1.3]
    for l in lines: ax.add_collection(l)
    img = ax.imshow(np.zeros((len(ri), len(ci))), extent=(lon[ci[0]] - RES / 2, lon[ci[-1]] + RES / 2, lat[ri[0]] - RES / 2, lat[ri[-1]] + RES / 2), origin='lower', cmap=cmap, vmin=0, vmax=70,
                    interpolation='bilinear', zorder=1, aspect='auto')
    dyn = []
    fdir = pathlib.Path(tempfile.mkdtemp()); hours = list(np.arange(0, 72.01, 0.5)); levels = []
    land = None
    for f, h in enumerate(hours):
        for a in dyn: a.remove()
        dyn = []
        Q = interp(F, h); T = Q['tcwv'][np.ix_(ri, ci)]; P = gaussian_filter(Q['pr'][np.ix_(ri, ci)], 0.8); M = gaussian_filter(Q['msl'][np.ix_(ri, ci)], 2.0)
        img.set_data(gaussian_filter(T, 0.6)); img.set_extent(img.get_extent()); ax.set_aspect(1 / k)
        if P.max() >= PR_LV[0]:
            dyn.append(ax.contourf(LON, LAT, P, levels=PR_LV, cmap=prc, norm=prn, alpha=0.85, zorder=2, antialiased=True))
        lv = np.arange(np.floor(M.min() / 4) * 4, M.max() + 4, 4)
        cs = ax.contour(LON, LAT, M, levels=lv, colors='#d9e3ee', linewidths=0.7, alpha=0.5, zorder=3); dyn.append(cs)
        for t_ in ax.clabel(cs, fmt='%d', fontsize=6.5, inline=True, inline_spacing=2): t_.set_color('#ffffff'); t_.set_alpha(0.7)  # (they go with the contours)
        mx, mn = maximum_filter(M, size=25) == M, minimum_filter(M, size=25) == M
        for mask, lab, col in ((mx, X['hi'], '#7fb2e5'), (mn, X['lo'], '#f08a7a')):
            for (yy, xx) in zip(*np.nonzero(mask)):
                if 3 < yy < M.shape[0] - 3 and 3 < xx < M.shape[1] - 3 and abs(M[yy, xx] - np.median(M)) > 3:
                    dyn.append(ax.text(LON[yy, xx], LAT[yy, xx], lab, fontsize=20, fontweight='bold', color=col, ha='center', va='center', zorder=7,
                                       path_effects=[matplotlib.patheffects.withStroke(linewidth=2.5, foreground='#1d2a3a')]))
                    dyn.append(ax.text(LON[yy, xx], LAT[yy, xx] - 0.9, f'{M[yy, xx]:.0f}', fontsize=7.5, color='#ffffff', ha='center', va='center', zorder=7))
        # move the streaks (sped up so the motion is visible: ~1.6 h of travel per frame)
        U, V = Q['u'][np.ix_(ri, ci)], Q['v'][np.ix_(ri, ci)]
        gx = np.clip(((pts[:, 0] - lon[ci[0]]) / RES).astype(int), 0, len(ci) - 1); gy = np.clip(((pts[:, 1] - lat[ri[0]]) / RES).astype(int), 0, len(ri) - 1)
        u, v = U[gy, gx], V[gy, gx]; sec = 1.1 * 3600
        pts = pts + np.c_[u * sec / (111320 * np.cos(np.radians(pts[:, 1]))), v * sec / 110540]
        age += 1; dead = (age > 60) | (pts[:, 0] < x0) | (pts[:, 0] > x1) | (pts[:, 1] < y0v) | (pts[:, 1] > y1v)
        if dead.any(): pts[dead] = seed(dead.sum()); age[dead] = 0; hist[:, dead] = pts[dead]
        hist = np.roll(hist, -1, 0); hist[-1] = pts
        spd = np.hypot(u, v)
        for i, l in enumerate(lines):
            seg = np.stack([hist[i], hist[i + 1]], 1); ok = ~dead & (np.hypot(*(seg[:, 1] - seg[:, 0]).T) < 3)
            l.set_segments(seg[ok]); l.set_linewidths(0.4 + 1.0 * np.clip(spd[ok] / 25, 0, 1))
        t = run + dt.timedelta(hours=float(h) + off)
        clock.set_text(f"{X['wd'][t.weekday()]} {t:%d.%m} · {t:%H}:{t:%M} · {X['tz']}")
        fig.savefig(fdir / f'{f:03d}.png', dpi=150, facecolor=fig.get_facecolor())
        # the sound: the wind of the region, the rain when it falls on the country
        if land is None:
            from matplotlib.path import Path
            pts_ = np.c_[LON.ravel(), LAT.ravel()]; m = np.zeros(len(pts_), bool)
            for r in own: m |= Path(r).contains_points(pts_)
            land = m.reshape(LON.shape)
        wet = float(np.mean(P[land] >= 1)) if land.any() else 0.0
        levels.append({'rain': min(1.0, wet * 2.5), 'snow': False, 'wind': float(np.clip(np.mean(spd) / 22, 0.15, 0.9)), 'storm': 0.0})
    plt.close(fig)
    for e in range(24): shutil.copy(fdir / f'{len(hours) - 1:03d}.png', fdir / f'{len(hours) + e:03d}.png'); levels.append(levels[-1])  # hold the last frame
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '12', '-i', str(fdir / '%03d.png'), '-vf', 'scale=1920:-2:flags=lanczos,format=yuv420p', '-c:v', 'libx264', '-crf', '21',
                    '-preset', 'medium', '-movflags', '+faststart', str(mp4)], check=True)
    try:
        import sound as S_
        S_.mux(mp4, S_.track(levels, 1 / 12, str(mp4) + '.wav', mode='all'))
    except Exception as e: print('moist sound failed', e, flush=True)
    Rn.fit_size(mp4)
    shutil.rmtree(fdir)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('npz'); ap.add_argument('out'); ap.add_argument('--regions', default='UZ,KZ'); ap.add_argument('--langs', default='ru,uz')
    ap.add_argument('--fields', help='saved fields (tests)')
    a = ap.parse_args()
    import render as Rn
    D = Rn.load(a.npz); run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    F = dict(np.load(a.fields, allow_pickle=True)['F'].item()) if a.fields else fetch(run)
    if len(F) < 6: print('moist: not enough fields', flush=True); return
    out = pathlib.Path(a.out) / 'hr'; out.mkdir(parents=True, exist_ok=True)
    for region in a.regions.split(','):
        for lang in a.langs.split(','):
            try: video(F, region, lang, out / f'{region}_moist_{lang}.mp4', run); print('moist', region, lang, 'ok', flush=True)
            except Exception as e:
                import traceback; traceback.print_exc(); print('moist failed', region, lang, e, flush=True)


if __name__ == '__main__':
    main()
