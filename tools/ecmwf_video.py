"""Videos for phones (1080×1920, the Osmon 2.0 clarity standard): what the weather stations of Uzbekistan reported over the last
6 hours (WMO SYNOP), then the ECMWF forecast — "12h" (hourly, interpolated between the 3-hourly steps) and "3d" (every 3 hours to 72 h).
The map: sharp relief (elevation tiles ~1 km), borders drawn at full size, precipitation in steps (rain blue, snow violet),
temperatures in the towns; under it the legend, the towns, and one line saying what it means.
Out: out/{12h|3d}_{lang}.mp4 and out/meta.json.  Usage: python tools/ecmwf_video.py out ru,uz"""
import io, json, math, sys, shutil, subprocess, tempfile, datetime as dt, pathlib, concurrent.futures as cf
import numpy as np, requests
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection as LC, PolyCollection as PCOL
from matplotlib.colors import ListedColormap, BoundaryNorm, LightSource
from matplotlib import font_manager as fm
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'prob')); sys.path.insert(0, str(ROOT / 'tools'))
import moisture as M  # ECMWF open data: fields of a run (Google's mirror)
import obs_video as OV  # the stations and their SYNOP reports

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'ev'); OUT.mkdir(parents=True, exist_ok=True)
LANGS = (sys.argv[2] if len(sys.argv) > 2 else 'ru,uz').split(',')
W, H = 1080, 1920
V = (55.8, 73.4, 36.9, 45.8)  # Uzbekistan
MAP_H = int(round(W * (V[3] - V[2]) / ((V[1] - V[0]) * math.cos(math.radians(41.3)))))  # true proportions
if any('inter' in x.lower() for x in fm.findSystemFonts()): plt.rcParams['font.family'] = 'Inter'
NAVY, ORANGE, INK, MUTED, PAPER = '#1f2d3d', '#c0562b', '#1f2d3d', '#5d6b7c', '#f5f7f9'
# precipitation in steps (mm in 3 hours): one palette everywhere in Osmon
PR_LV = [0.2, 1, 3, 6, 12, 99]
RAIN = ['#b9dcf7', '#7cbcf0', '#3f8fdd', '#1f5fb3', '#173f84']
SNOW = ['#e1d4f7', '#c2a6ef', '#9a70e0', '#7346c2', '#4f2a95']
TCOL = lambda t: OV.tcol(t)
TOWNS = [('Ташкент', 'Toshkent', 41.31, 69.28), ('Самарканд', 'Samarqand', 39.65, 66.96), ('Бухара', 'Buxoro', 39.77, 64.42), ('Нукус', 'Nukus', 42.46, 59.6),
         ('Ургенч', 'Urganch', 41.55, 60.63), ('Наманган', 'Namangan', 41.0, 71.67), ('Андижан', 'Andijon', 40.78, 72.34), ('Фергана', 'Farg‘ona', 40.39, 71.78),
         ('Карши', 'Qarshi', 38.86, 65.79), ('Термез', 'Termiz', 37.22, 67.28), ('Навои', 'Navoiy', 40.1, 65.38), ('Джизак', 'Jizzax', 40.12, 67.84),
         ('Гулистан', 'Guliston', 40.49, 68.78), ('Нурафшон', 'Nurafshon', 41.04, 69.36)]
TX = {'ru': dict(fact='ФАКТ · метеостанции', fc='ПРОГНОЗ ECMWF', t12='Погода: 6 часов факт + 12 часов прогноз', t3='Погода: 6 часов факт + 3 дня прогноз',
                 at='{d} · {h} по Ташкенту', plus='+{h} ч', rain='дождь, мм за 3 ч', snow='снег', town='Города', src='Факт: метеостанции Узбекистана (ВМО SYNOP) · Прогноз: ECMWF IFS · Osmon',
                 wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], mon=['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'],
                 dry='Без осадков по всей стране', wet='Больше всего осадков: {t} — {mm} мм', wet3='За 3 дня больше всего осадков: {t} — {mm} мм', none3='3 дня без заметных осадков',
                 tot='Осадки за 3 дня, мм', fog='туман', obs_ring='осадки или явление на станции', total='ИТОГ · 3 дня'),
      'uz': dict(fact='FAKT · meteostansiyalar', fc='ECMWF PROGNOZI', t12='Ob-havo: 6 soat fakt + 12 soat prognoz', t3='Ob-havo: 6 soat fakt + 3 kun prognoz',
                 at='{d} · Toshkent vaqti {h}', plus='+{h} soat', rain='yomg‘ir, 3 soatda mm', snow='qor', town='Shaharlar', src='Fakt: O‘zbekiston meteostansiyalari (JMT SYNOP) · Prognoz: ECMWF IFS · Osmon',
                 wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'], mon=['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'],
                 dry='Butun mamlakatda yog‘in yo‘q', wet='Eng ko‘p yog‘in: {t} — {mm} mm', wet3='3 kunda eng ko‘p yog‘in: {t} — {mm} mm', none3='3 kun sezilarli yog‘insiz',
                 tot='3 kunlik yog‘in, mm', fog='tuman', obs_ring='stansiyada yog‘in yoki hodisa', total='JAMI · 3 kun')}
S = requests.Session(); S.headers['User-Agent'] = 'Osmon weather (github.com/otabekvafoev92-del/ob-havo-ecmwf)'


def relief():
    """A sharp hill shade of the map from elevation tiles (Mapzen terrarium on AWS, ~1 km at zoom 7), on a lon/lat grid."""
    z = 7; n = 2 ** z
    tx = lambda lon: (lon + 180) / 360 * n
    ty = lambda lat: (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    x0, x1 = int(tx(V[0])), int(tx(V[1])); y0, y1 = int(ty(V[3])), int(ty(V[2]))
    def tile(xy):
        x, y = xy
        for k in range(3):
            try:
                r = S.get(f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png', timeout=60)
                if r.ok: a = np.asarray(Image.open(io.BytesIO(r.content)).convert('RGB'), float); return xy, a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
            except requests.RequestException: pass
        return xy, np.zeros((256, 256))
    big = np.zeros(((y1 - y0 + 1) * 256, (x1 - x0 + 1) * 256))
    with cf.ThreadPoolExecutor(12) as p:
        for (x, y), e in p.map(tile, [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]):
            big[(y - y0) * 256:(y - y0 + 1) * 256, (x - x0) * 256:(x - x0 + 1) * 256] = e
    # onto a lon/lat grid at the output size
    nx, ny = W * 2, MAP_H * 2
    lon = np.linspace(V[0], V[1], nx); lat = np.linspace(V[3], V[2], ny)
    px = ((lon + 180) / 360 * n - x0) * 256; py = np.array([((1 - math.asinh(math.tan(math.radians(la))) / math.pi) / 2 * n - y0) * 256 for la in lat])
    ix = np.clip(px.astype(int), 0, big.shape[1] - 1); iy = np.clip(py.astype(int), 0, big.shape[0] - 1)
    el = np.maximum(big[np.ix_(iy, ix)], 0)
    hs = LightSource(azdeg=315, altdeg=40).hillshade(el, vert_exag=0.012, dx=1, dy=1)
    # land in soft greens/sands by height, shaded
    base = np.dstack([np.interp(el, [0, 300, 1200, 2500, 4500], c) for c in ([0.93, 0.92, 0.88, 0.86, 0.97], [0.93, 0.92, 0.87, 0.84, 0.97], [0.86, 0.86, 0.82, 0.82, 0.98])])
    img = np.clip(base * (0.62 + 0.45 * hs[..., None]), 0, 1)
    return (img * 255).astype(np.uint8)


def latest_run():
    now = dt.datetime.utcnow()
    for h in range(4, 40):
        t = now - dt.timedelta(hours=h)
        if t.hour % 6: continue
        run = t.replace(minute=0, second=0, microsecond=0); d, hh = run.strftime('%Y%m%d'), run.strftime('%H')
        for stream in (('oper', 'scda') if hh in ('00', '12') else ('scda', 'oper')):
            if M.get(f'{M.ECM}/{d}/{hh}z/ifs/0p25/{stream}/{d}{hh}0000-90h-{stream}-fc.index'): return run
    raise RuntimeError('no run')


def main():
    run = latest_run(); print('run', run, flush=True)
    now = dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    lead0 = int((now - run).total_seconds() // 3600)  # the step of "now"
    need = sorted(set(s for s in range(0, 91, 3) if lead0 - 3 <= s <= lead0 + 75))
    F = M.fetch(run, [(s, 'hres') for s in need])
    lat = np.arange(M.LAT0, M.LAT1 + 1e-6, M.RES); lon = np.arange(M.LON0, M.LON1 + 1e-6, M.RES)
    ri = np.flatnonzero((lat >= V[2] - 1) & (lat <= V[3] + 1)); ci = np.flatnonzero((lon >= V[0] - 1) & (lon <= V[1] + 1))
    LAT, LON = lat[ri], lon[ci]; ext = (LON[0] - M.RES / 2, LON[-1] + M.RES / 2, LAT[0] - M.RES / 2, LAT[-1] + M.RES / 2)
    cut = lambda a: a[np.ix_(ri, ci)]
    steps = sorted(F)
    def field(t):  # temperature, precipitation of the 3 hours ending at t (mm), cloud cover — interpolated in time
        L = (t - run).total_seconds() / 3600
        a = max([s for s in steps if s <= L], default=steps[0]); b = min([s for s in steps if s >= L], default=steps[-1]); w = 0 if b == a else (L - a) / (b - a)
        mix = lambda k: cut(F[a][k]) * (1 - w) + cut(F[b][k]) * w
        b3 = min([s for s in steps if s >= L], default=steps[-1]); a3 = max([s for s in steps if s <= b3 - 3], default=steps[0])
        pr = np.maximum(cut(F[b3]['tp']) - cut(F[a3]['tp']), 0) * (3 / max(3, b3 - a3))
        return mix('t2'), pr, mix('tcc')
    def at(a, la, lo): return float(a[np.abs(LAT - la).argmin(), np.abs(LON - lo).argmin()])
    # the stations: the last 6 hours (the 3-hourly terms)
    st = OV.stations(); obs = {}
    for line in OV.synops(hours=9).splitlines():
        p = line.split(',', 6)
        if len(p) < 7 or p[0] not in st: continue
        t = dt.datetime(int(p[1]), int(p[2]), int(p[3]), int(p[4]), int(p[5])); o = OV.decode(p[6])
        if o and 't' in o: obs.setdefault(t, {})[p[0]] = o
    terms = [t for t in sorted(obs) if t.hour % 3 == 0 and len(obs[t]) >= 8 and t >= now - dt.timedelta(hours=7)][-3:]
    print('obs terms', terms, flush=True)
    REL = relief(); print('relief', REL.shape, flush=True)
    G = json.load(open(ROOT / 'prob' / 'geo_world.json'))['countries']; GA = json.load(open(ROOT / 'prob' / 'geo_admin.json')).get('UZ', {})
    WAT = json.load(open(ROOT / 'prob' / 'geo_water.json')); sea = [np.asarray(r) for r in WAT['ocean']] + [np.asarray(l['r']) for l in WAT['lakes']]
    meta = {'run': run.strftime('%Y-%m-%dT%HZ'), 'made': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), 'obs': [t.strftime('%H:%MZ') for t in terms]}
    for kind in ('12h', '3d'):
        fts = [now + dt.timedelta(hours=h) for h in (range(1, 13) if kind == '12h' else range(3, 73, 3))]
        fts = [t for t in fts if (t - run).total_seconds() / 3600 <= steps[-1]]
        # what it means: the wettest town over the period
        tot = {}
        for t in fts[::(3 if kind == '12h' else 1)]:
            _, pr, _ = field(t)
            for tw in TOWNS: tot[tw] = tot.get(tw, 0) + at(pr, tw[2], tw[3])
        wet = max(tot.items(), key=lambda kv: kv[1])
        for lang in LANGS:
            X = TX[lang]; fd = pathlib.Path(tempfile.mkdtemp()); n_ = 0
            line = (X['wet3' if kind == '3d' else 'wet'].format(t=wet[0][0 if lang == 'ru' else 1], mm=round(wet[1])) if wet[1] >= 1 else X['none3' if kind == '3d' else 'dry'])
            frames = [(t, 'obs') for t in terms] + [(t, 'fc') for t in fts] + ([(None, 'total')] if kind == '3d' else [])
            for t, mode in frames:
                fig = plt.figure(figsize=(W / 100, H / 100), dpi=100); fig.patch.set_facecolor(PAPER)
                # header
                fig.patches.append(plt.Rectangle((0, 1 - 250 / H), 1, 250 / H, transform=fig.transFigure, fc=NAVY, ec='none'))
                fig.text(0.05, 1 - 70 / H, 'OSMON', color='#f08a24', fontsize=26, fontweight='bold', va='center')
                fig.text(0.05, 1 - 128 / H, X['t12' if kind == '12h' else 't3'], color='#ffffff', fontsize=31, fontweight='bold', va='center')
                if t is not None:
                    loc = t + dt.timedelta(hours=5)
                    badge, bc = (X['fact'], '#2e8b57') if mode == 'obs' else (X['fc'] + (' · ' + X['plus'].format(h=int((t - now).total_seconds() // 3600)) if t > now else ''), ORANGE)
                    fig.text(0.05, 1 - 196 / H, badge, color='#ffffff', fontsize=26, fontweight='bold', va='center', bbox=dict(boxstyle='round,pad=0.35', fc=bc, ec='none'))
                    fig.text(0.95, 1 - 196 / H, X['at'].format(d=f"{X['wd'][loc.weekday()]} {loc.day} {X['mon'][loc.month - 1]}", h=loc.strftime('%H:%M')), color='#dfe6ee', fontsize=24, va='center', ha='right')
                else:
                    fig.text(0.05, 1 - 196 / H, X['total'], color='#ffffff', fontsize=26, fontweight='bold', va='center', bbox=dict(boxstyle='round,pad=0.35', fc=ORANGE, ec='none'))
                # the map
                top = 270; ax = fig.add_axes([0, 1 - (top + MAP_H) / H, 1, MAP_H / H]); ax.set_xlim(V[0], V[1]); ax.set_ylim(V[2], V[3]); ax.axis('off')
                ax.imshow(REL, extent=(V[0], V[1], V[2], V[3]), aspect='auto', zorder=0, interpolation='lanczos')
                ax.add_collection(PCOL(sea, facecolors='#bcd8ec', edgecolors='#7fa9c6', linewidths=0.8, zorder=0.5))
                if mode == 'fc' or mode == 'total':
                    if mode == 'fc': t2, pr, tcc = field(t); acc = pr
                    else:
                        acc = sum(field(tt)[1] for tt in fts); t2 = field(fts[-1])[0]
                    # clouds: a soft white veil, precipitation in steps on top
                    if mode == 'fc':
                        cl = np.zeros(tcc.shape + (4,)); cl[..., :3] = 1; cl[..., 3] = np.clip((tcc - 0.3) / 0.7, 0, 1) * 0.45
                        ax.imshow(cl, extent=ext, origin='lower', aspect='auto', interpolation='bicubic', zorder=1)
                    lv = PR_LV if mode == 'fc' else [1, 5, 10, 20, 40, 999]
                    snow = t2 <= 0.5
                    for mask, cols in ((~snow, RAIN), (snow, SNOW)):
                        a = np.where(mask, acc, np.nan)
                        if np.nanmax(np.nan_to_num(a)) >= lv[0]:
                            ax.contourf(LON, LAT, a, levels=lv, colors=cols, alpha=0.85, zorder=2, antialiased=True)
                ax.add_collection(LC([np.asarray(r) for c in G.values() for r in c['rings']], colors='#2b3a4e', linewidths=2.2, zorder=3))
                if GA:
                    ax.add_collection(LC([np.asarray(r) for a in GA['adm1'] for r in a['r']], colors='#ffffff', linewidths=3.2, alpha=0.55, zorder=3))
                    ax.add_collection(LC([np.asarray(r) for a in GA['adm1'] for r in a['r']], colors='#55657a', linewidths=1.3, zorder=3.1))
                # values: the stations (fact) or the towns (forecast)
                pts = []
                if mode == 'obs':
                    for w, o in obs[t].items():
                        s_ = st[w]; k = OV.wx(o.get('ww'))
                        pts.append((s_['lon'], s_['lat'], o['t'], k, s_['main']))
                elif mode == 'fc':
                    for tw in TOWNS: pts.append((tw[3], tw[2], at(t2, tw[2], tw[3]), (1 if at(t2, tw[2], tw[3]) <= 0.5 else 0) if at(pr, tw[2], tw[3]) >= 0.3 else None, True))
                for x, y, v, k, big in sorted(pts, key=lambda q: q[4]):
                    if not (V[0] < x < V[1] and V[2] < y < V[3]): continue
                    if k is not None and OV.KC[OV.KI[k]]: ax.scatter(x, y, s=(2300 if big else 1300), facecolors='none', edgecolors=OV.KC[OV.KI[k]], linewidths=5, zorder=4)
                    ax.scatter(x, y, s=(1500 if big else 700), c=[TCOL(v)], edgecolors='#ffffff', linewidths=2.2, zorder=5)
                    ax.text(x, y, f"{v:+.0f}" if round(v) != 0 else '0', ha='center', va='center', fontsize=(19 if big else 13), fontweight='bold', color='#1f2d3d' if -8 < v < 30 else '#ffffff', zorder=6)
                if mode == 'total':
                    for tw in TOWNS:
                        mm = tot.get(tw, 0); ax.text(tw[3], tw[2], f"{mm:.0f}", ha='center', va='center', fontsize=18, fontweight='bold', color='#173f84', zorder=6,
                                                      bbox=dict(boxstyle='round,pad=0.3', fc='#ffffffdd', ec='#173f84', lw=1.5))
                for tw in TOWNS[:12]:
                    ax.text(tw[3], tw[2] - 0.42, tw[0 if lang == 'ru' else 1], ha='center', va='top', fontsize=15, fontweight='bold', color='#1f2d3d', zorder=6,
                            bbox=dict(boxstyle='round,pad=0.15', fc='#ffffffcc', ec='none'))
                # legend tiles
                y0 = 1 - (top + MAP_H + 40) / H
                fig.text(0.05, y0, X['rain'] if mode != 'total' else X['tot'], fontsize=21, color=INK, fontweight='bold', va='center')
                labs = ['0.2', '1', '3', '6', '12+'] if mode != 'total' else ['1', '5', '10', '20', '40+']
                for i, (c, l_) in enumerate(zip(RAIN, labs)):
                    x0 = 0.05 + i * 0.12; fig.patches.append(plt.Rectangle((x0, y0 - 0.045), 0.1, 0.02, transform=fig.transFigure, fc=c, ec='none')); fig.text(x0, y0 - 0.06, l_, fontsize=18, color=MUTED, va='top')
                fig.patches.append(plt.Rectangle((0.69, y0 - 0.045), 0.1, 0.02, transform=fig.transFigure, fc=SNOW[2], ec='none')); fig.text(0.69, y0 - 0.06, X['snow'], fontsize=18, color=MUTED, va='top')
                if mode == 'obs':
                    from matplotlib.patches import Circle
                    fig.patches.append(Circle((0.07, y0 - 0.112), 0.012, transform=fig.transFigure, fc='none', ec='#2f7fd1', lw=4))
                    fig.text(0.1, y0 - 0.1, X['obs_ring'], fontsize=18, color=MUTED, va='top')
                # towns panel: now (this frame) for the 8 biggest towns
                y1 = y0 - 0.15; fig.text(0.05, y1, X['town'], fontsize=24, color=INK, fontweight='bold', va='center')
                vals = []
                for tw in TOWNS[:8]:
                    if mode == 'obs':
                        near = min(obs[t].items(), key=lambda kv: (st[kv[0]]['lat'] - tw[2]) ** 2 + (st[kv[0]]['lon'] - tw[3]) ** 2)
                        d2 = (st[near[0]]['lat'] - tw[2]) ** 2 + (st[near[0]]['lon'] - tw[3]) ** 2
                        vals.append((tw, near[1]['t'] if d2 < 0.09 else None))
                    elif mode == 'fc': vals.append((tw, at(t2, tw[2], tw[3])))
                    else: vals.append((tw, tot.get(tw, 0)))
                for i, (tw, v) in enumerate(vals):
                    cx = 0.05 + (i % 2) * 0.46; cy = y1 - 0.045 - (i // 2) * 0.045
                    fig.text(cx, cy, tw[0 if lang == 'ru' else 1], fontsize=24, color=INK, va='center')
                    fig.text(cx + 0.4, cy, '—' if v is None else (f"{v:.0f} мм" if lang == 'ru' else f"{v:.0f} mm") if mode == 'total' else f"{v:+.0f}°", fontsize=26, color=INK, fontweight='bold', va='center', ha='right')
                # what it means
                fig.patches.append(plt.Rectangle((0, 0.075), 1, 0.06, transform=fig.transFigure, fc='#fff4e8', ec='none'))
                fig.text(0.05, 0.105, line, fontsize=25, color='#a1520c', fontweight='bold', va='center')
                fig.text(0.05, 0.04, X['src'], fontsize=15, color=MUTED, va='center')
                fig.savefig(fd / f'{n_:03d}.png', facecolor=PAPER); plt.close(fig); n_ += 1
            # timing: the facts slower, the forecast smooth
            per = [1.2 if m == 'obs' else (0.45 if kind == '12h' else 0.35) if m == 'fc' else 3.0 for _, m in frames]
            lst = fd / 'list.txt'; lst.write_text(''.join(f"file '{i:03d}.png'\nduration {d}\n" for i, d in enumerate(per)) + f"file '{len(per) - 1:03d}.png'\n")
            out = OUT / f'{kind}_{lang}.mp4'; tmp = OUT / f'.{kind}_{lang}.part.mp4'
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-vf',
                            'framerate=fps=30:interp_start=0:interp_end=255:scene=100,format=yuv420p', '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast',
                            '-movflags', '+faststart', str(tmp)], check=True)
            tmp.replace(out); shutil.rmtree(fd); print(out, out.stat().st_size // 1024, 'KB', flush=True)
        meta[kind] = {'until': fts[-1].strftime('%Y-%m-%dT%HZ') if fts else None, 'wettest': [wet[0][0], round(wet[1], 1)]}
    json.dump(meta, open(OUT / 'meta.json', 'w'), ensure_ascii=False)


if __name__ == '__main__':
    main()
