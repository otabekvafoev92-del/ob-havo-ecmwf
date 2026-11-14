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
import cv2
from scipy.ndimage import zoom, gaussian_filter

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
NAVY, ORANGE, INK, MUTED, PAPER = '#08111f', '#e8742c', '#eef3f8', '#93a4b8', '#0d1829'  # the dark look of the world weather maps
# precipitation in steps (mm in 3 hours): one palette everywhere in Osmon
PR_LV = [0.2, 1, 3, 6, 12, 99]
RAIN = ['#9be59a', '#3fca5a', '#f2e33a', '#f59a2c', '#e53935']  # radar colours
SNOW = ['#f3e9ff', '#e2c4ff', '#cf94f5', '#b55ee6', '#8e2fc9']
TCOL = lambda t: OV.tcol(t)
TOWNS = [('Ташкент', 'Toshkent', 41.31, 69.28), ('Самарканд', 'Samarqand', 39.65, 66.96), ('Бухара', 'Buxoro', 39.77, 64.42), ('Нукус', 'Nukus', 42.46, 59.6),
         ('Ургенч', 'Urganch', 41.55, 60.63), ('Наманган', 'Namangan', 41.0, 71.67), ('Андижан', 'Andijon', 40.78, 72.34), ('Фергана', 'Farg‘ona', 40.39, 71.78),
         ('Карши', 'Qarshi', 38.86, 65.79), ('Термез', 'Termiz', 37.22, 67.28), ('Навои', 'Navoiy', 40.1, 65.38), ('Джизак', 'Jizzax', 40.12, 67.84),
         ('Гулистан', 'Guliston', 40.49, 68.78), ('Нурафшон', 'Nurafshon', 41.04, 69.36)]
TX = {'ru': dict(fact='ФАКТ · метеостанции', fc='ПРОГНОЗ ECMWF', t12='Погода: 6 часов факт + 12 часов прогноз', t3='Погода: 6 часов факт + 3 дня прогноз',
                 at='{d} · {h} по Ташкенту', plus='+{h} ч', rain='дождь, мм за 3 ч', snow='снег', town='Города', src='Факт: метеостанции Узбекистана (ВМО SYNOP) · Прогноз: ECMWF IFS · Osmon',
                 wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], mon=['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'],
                 dry='Без осадков по всей стране', wet='Больше всего осадков: {t} — {mm} мм', wet3='За 3 дня больше всего осадков: {t} — {mm} мм', none3='3 дня без заметных осадков',
                 wind='штрихи — ветер у земли · белые линии — давление', tot='Осадки за 3 дня, мм', fog='туман', obs_ring='осадки или явление на станции', total='ИТОГ · 3 дня'),
      'uz': dict(fact='FAKT · meteostansiyalar', fc='ECMWF PROGNOZI', t12='Ob-havo: 6 soat fakt + 12 soat prognoz', t3='Ob-havo: 6 soat fakt + 3 kun prognoz',
                 at='{d} · Toshkent vaqti {h}', plus='+{h} soat', rain='yomg‘ir, 3 soatda mm', snow='qor', town='Shaharlar', src='Fakt: O‘zbekiston meteostansiyalari (JMT SYNOP) · Prognoz: ECMWF IFS · Osmon',
                 wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'], mon=['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'],
                 dry='Butun mamlakatda yog‘in yo‘q', wet='Eng ko‘p yog‘in: {t} — {mm} mm', wet3='3 kunda eng ko‘p yog‘in: {t} — {mm} mm', none3='3 kun sezilarli yog‘insiz',
                 wind='chiziqchalar — yer yonidagi shamol · oq chiziqlar — bosim', tot='3 kunlik yog‘in, mm', fog='tuman', obs_ring='stansiyada yog‘in yoki hodisa', total='JAMI · 3 kun')}
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
    base = np.dstack([np.interp(el, [0, 300, 1200, 2500, 4200], c) for c in ([0.20, 0.22, 0.27, 0.40, 0.88], [0.21, 0.23, 0.26, 0.38, 0.9], [0.19, 0.19, 0.22, 0.36, 0.94])])
    img = np.clip(base * (0.42 + 0.9 * hs[..., None]), 0, 1)
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
        mx = lambda k, alt: cut(F[a].get(k, F[a][alt])) * (1 - w) + cut(F[b].get(k, F[b][alt])) * w
        return mix('t2'), pr, mix('tcc'), mix('msl'), mx('u10', 'u'), mx('v10', 'v')
    def at(a, la, lo): return float(a[np.abs(LAT - la).argmin(), np.abs(LON - lo).argmin()])
    # motion: the fields upsampled ×4, the optical flow between two forecast hours moves the clouds and the rain between them
    UP = 4; up = lambda a: zoom(a, UP, order=1)
    hu, wu = up(np.zeros((len(LAT), len(LON)))).shape
    LATu, LONu = np.linspace(LAT[0], LAT[-1], hu), np.linspace(LON[0], LON[-1], wu)
    def atu(a, la, lo): return float(a[np.abs(LATu - la).argmin(), np.abs(LONu - lo).argmin()])
    GX, GY = np.meshgrid(np.arange(wu, dtype=np.float32), np.arange(hu, dtype=np.float32))
    def warp(a, fl, s):  # a sampled at x − s·flow
        return cv2.remap(a.astype(np.float32), GX - s * fl[..., 0], GY - s * fl[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    def flow(a, b):
        u8 = lambda x: np.clip(x * 255, 0, 255).astype(np.uint8)
        return cv2.calcOpticalFlowFarneback(u8(a), u8(b), None, 0.5, 4, 31, 5, 7, 1.5, cv2.OPTFLOW_FARNEBACK_GAUSSIAN)
    sig = lambda pr, tc: 0.65 * tc + 0.35 * np.clip(pr / 6, 0, 1)
    rng = np.random.default_rng(7); NOISE = sum(gaussian_filter(rng.random((hu, wu)), s_) * w_ for s_, w_ in ((3, 1), (7, 1.6), (16, 2.2)))
    NOISE = (NOISE - NOISE.min()) / (NOISE.max() - NOISE.min())
    def sequence(fts, kind):  # the forecast frames: N in-between frames per interval, clouds and rain carried along the flow
        N, dur = (8, 0.5) if kind == '12h' else (6, 0.4); stp = 1 if kind == '12h' else 3
        keys = [tuple(up(x) for x in field(t)) for t in fts]; nz = NOISE.copy(); out = []
        # the wind: particles carried by the 10 m wind, each with a short fading trail
        pr_rng = np.random.default_rng(3); NP, TR = 950, 7
        spawn = lambda n: np.c_[pr_rng.uniform(V[0], V[1], n), pr_rng.uniform(V[2], V[3], n)]
        P = spawn(NP); age = pr_rng.integers(0, 50, NP); life = pr_rng.integers(35, 70, NP); hist = [P.copy() for _ in range(TR)]
        def step(u, v):
            nonlocal P, age, hist
            iy = np.clip(np.searchsorted(LATu, P[:, 1]), 0, hu - 1); ix = np.clip(np.searchsorted(LONu, P[:, 0]), 0, wu - 1)
            K = 0.0055; P = P + np.c_[u[iy, ix] * K / np.cos(np.radians(P[:, 1])), v[iy, ix] * K]; age += 1
            dead = (age > life) | (P[:, 0] < V[0]) | (P[:, 0] > V[1]) | (P[:, 1] < V[2]) | (P[:, 1] > V[3])
            if dead.any():
                P[dead] = spawn(int(dead.sum())); age[dead] = 0
                for h_ in hist: h_[dead] = P[dead]
            hist = hist[1:] + [P.copy()]
            return np.stack(hist)
        for i, t in enumerate(fts):
            t2a, pra, tca, msa, ua, va = keys[i]
            if i == len(fts) - 1:
                for k in range(N):  # the last hour: the wind keeps blowing while it holds
                    out.append(dict(mode='fc', t=t, t2=t2a, pr=pra, tcc=tca, msl=msa, nz=nz, tr=step(ua, va), d=(1.0 if k == N - 1 else 0.6 / N)))
                break
            t2b, prb, tcb, msb, ub, vb = keys[i + 1]; fl = flow(gaussian_filter(sig(pra, tca), 2), gaussian_filter(sig(prb, tcb), 2))
            for k in range(N):
                s = k / N
                pr_ = (1 - s) * warp(pra, fl, s) + s * warp(prb, fl, s - 1); tc_ = (1 - s) * warp(tca, fl, s) + s * warp(tcb, fl, s - 1)
                out.append(dict(mode='fc', t=t + dt.timedelta(hours=round(s * stp)), t2=(1 - s) * t2a + s * t2b, pr=pr_, tcc=tc_, msl=(1 - s) * msa + s * msb, nz=nz,
                                tr=step((1 - s) * ua + s * ub, (1 - s) * va + s * vb), d=dur / N))
                nz = warp(nz, fl, 1 / N)
        return out
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
    from matplotlib.path import Path as MPath  # Uzbekistan bright, the neighbours dimmed
    gx_, gy_ = np.meshgrid(np.linspace(V[0], V[1], REL.shape[1]), np.linspace(V[3], V[2], REL.shape[0])); pts_ = np.c_[gx_.ravel(), gy_.ravel()]
    ins = np.zeros(len(pts_), bool)
    for r in G['UZ']['rings']: ins |= MPath(np.asarray(r)).contains_points(pts_)
    REL = np.where(ins.reshape(REL.shape[:2])[..., None], REL, (REL * 0.55).astype(np.uint8)); UZR = [np.asarray(r) for r in G['UZ']['rings']]
    WAT = json.load(open(ROOT / 'prob' / 'geo_water.json')); sea = [np.asarray(r) for r in WAT['ocean']] + [np.asarray(l['r']) for l in WAT['lakes']]
    meta = {'run': run.strftime('%Y-%m-%dT%HZ'), 'made': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), 'obs': [t.strftime('%H:%MZ') for t in terms]}
    for kind in ('12h', '3d'):
        fts = [now + dt.timedelta(hours=h) for h in (range(1, 13) if kind == '12h' else range(3, 73, 3))]
        fts = [t for t in fts if (t - run).total_seconds() / 3600 <= steps[-1]]
        # what it means: the wettest town over the period
        tot = {}
        for t in fts[::(3 if kind == '12h' else 1)]:
            pr = field(t)[1]
            for tw in TOWNS: tot[tw] = tot.get(tw, 0) + at(pr, tw[2], tw[3])
        wet = max(tot.items(), key=lambda kv: kv[1])
        seq = sequence(fts, kind); print(kind, len(seq), 'forecast frames', flush=True)
        acc3 = up(sum(field(tt)[1] for tt in fts)); t2end = up(field(fts[-1])[0])
        for lang in LANGS:
            X = TX[lang]; fd = pathlib.Path(tempfile.mkdtemp()); n_ = 0
            line = (X['wet3' if kind == '3d' else 'wet'].format(t=wet[0][0 if lang == 'ru' else 1], mm=round(wet[1])) if wet[1] >= 1 else X['none3' if kind == '3d' else 'dry'])
            frames = [dict(mode='obs', t=t, d=1.2) for t in terms] + seq + ([dict(mode='total', t=None, d=3.0)] if kind == '3d' else [])
            for fr in frames:
                t, mode = fr['t'], fr['mode']
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
                ax.add_collection(PCOL(sea, facecolors='#0b2036', edgecolors='#2a5079', linewidths=0.8, zorder=0.5))
                if mode == 'fc' or mode == 'total':
                    if mode == 'fc': t2, pr, tcc = fr['t2'], fr['pr'], fr['tcc']; acc = pr
                    else: acc, t2 = acc3, t2end
                    # clouds: white where thin, grey where thick, a texture that drifts with the wind; precipitation in steps on top
                    if mode == 'fc':
                        th = np.clip((tcc - 0.7) / 0.3, 0, 1)[..., None]; cl = np.zeros(tcc.shape + (4,))
                        cl[..., :3] = (1 - th) * np.array([0.95, 0.96, 0.98]) + th * np.array([0.74, 0.77, 0.82])
                        cl[..., 3] = np.clip((tcc - 0.15) / 0.6, 0, 1) * (0.4 + 0.55 * np.clip(fr['nz'] * 1.6 - 0.3, 0, 1)) * 0.88
                        ax.imshow(cl, extent=ext, origin='lower', aspect='auto', interpolation='bicubic', zorder=1)
                    lv = PR_LV if mode == 'fc' else [1, 5, 10, 20, 40, 999]
                    snow = t2 <= 0.5
                    for mask, cols in ((~snow, RAIN), (snow, SNOW)):
                        a = np.where(mask, acc, np.nan)
                        if np.nanmax(np.nan_to_num(a)) >= lv[0]:
                            ax.contourf(LONu, LATu, a, levels=lv, colors=cols, alpha=0.88, zorder=2, antialiased=True)
                    if mode == 'fc':
                        ms = gaussian_filter(fr['msl'], 4); lo_, hi_ = int(np.floor(ms.min() / 4) * 4), int(np.ceil(ms.max() / 4) * 4)
                        if hi_ > lo_: ax.contour(LONu, LATu, ms, levels=range(lo_, hi_ + 1, 4), colors='#ffffff', linewidths=1.1, alpha=0.38, zorder=2.6)
                        tr = fr['tr']; segs = np.stack([tr[:-1], tr[1:]], axis=2).reshape(-1, 2, 2)  # (TR−1)·NP segments, old to new
                        al = np.repeat(np.linspace(0.05, 0.6, tr.shape[0] - 1), tr.shape[1])
                        ax.add_collection(LC(segs, colors=np.c_[np.ones((len(al), 3)), al], linewidths=1.2, zorder=2.8, capstyle='round'))
                ax.add_collection(LC([np.asarray(r) for c in G.values() for r in c['rings']], colors='#c9d3df', linewidths=1.2, alpha=0.6, zorder=3))
                ax.add_collection(LC(UZR, colors='#ffffff', linewidths=2.6, zorder=3.3))
                if GA:
                    ax.add_collection(LC([np.asarray(r) for a in GA['adm1'] for r in a['r']], colors='#ffffff', linewidths=1.0, alpha=0.3, zorder=3))
                # axes: a grid of latitude and longitude every 2°, the degrees along the left and the bottom edge
                for g in range(56, 74, 2): ax.axvline(g, color='#ffffff', lw=0.7, alpha=0.13, ls=(0, (4, 4)), zorder=3.2)
                for g in range(37, 46, 1 if False else 2): ax.axhline(g, color='#ffffff', lw=0.7, alpha=0.13, ls=(0, (4, 4)), zorder=3.2)
                for g in range(58, 74, 2):
                    ax.text(g, V[2] + 0.08, f"{g}°{'в.д.' if lang == 'ru' else 'E'}", ha='center', va='bottom', fontsize=13, color='#cfd8e3', zorder=6.5,
                            bbox=dict(boxstyle='round,pad=0.15', fc='#08111fb0', ec='none'))
                for g in range(39, 46, 2):
                    ax.text(V[0] + 0.08, g, f"{g}°{'с.ш.' if lang == 'ru' else 'N'}", ha='left', va='center', fontsize=13, color='#cfd8e3', zorder=6.5,
                            bbox=dict(boxstyle='round,pad=0.15', fc='#08111fb0', ec='none'))
                # values: the stations (fact) or the towns (forecast)
                pts = []
                if mode == 'obs':
                    for w, o in obs[t].items():
                        s_ = st[w]; k = OV.wx(o.get('ww'))
                        pts.append((s_['lon'], s_['lat'], o['t'], k, s_['main']))
                elif mode == 'fc':
                    for tw in TOWNS: pts.append((tw[3], tw[2], atu(t2, tw[2], tw[3]), (1 if atu(t2, tw[2], tw[3]) <= 0.5 else 0) if atu(pr, tw[2], tw[3]) >= 0.3 else None, True))
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
                    ax.text(tw[3], tw[2] - 0.42, tw[0 if lang == 'ru' else 1], ha='center', va='top', fontsize=15, fontweight='bold', color='#ffffff', zorder=6,
                            bbox=dict(boxstyle='round,pad=0.2', fc='#08111fcc', ec='none'))
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
                elif mode == 'fc':
                    fig.text(0.05, y0 - 0.1, X['wind'], fontsize=18, color=MUTED, va='top')
                # towns panel: now (this frame) for the 8 biggest towns
                y1 = y0 - 0.135; fig.text(0.05, y1, X['town'], fontsize=24, color=INK, fontweight='bold', va='center')
                vals = []
                for tw in TOWNS[:8]:
                    if mode == 'obs':
                        near = min(obs[t].items(), key=lambda kv: (st[kv[0]]['lat'] - tw[2]) ** 2 + (st[kv[0]]['lon'] - tw[3]) ** 2)
                        d2 = (st[near[0]]['lat'] - tw[2]) ** 2 + (st[near[0]]['lon'] - tw[3]) ** 2
                        vals.append((tw, near[1]['t'] if d2 < 0.09 else None))
                    elif mode == 'fc': vals.append((tw, atu(t2, tw[2], tw[3])))
                    else: vals.append((tw, tot.get(tw, 0)))
                for i, (tw, v) in enumerate(vals):
                    cx = 0.05 + (i % 2) * 0.46; cy = y1 - 0.042 - (i // 2) * 0.039
                    fig.text(cx, cy, tw[0 if lang == 'ru' else 1], fontsize=24, color=INK, va='center')
                    fig.text(cx + 0.4, cy, '—' if v is None else (f"{v:.0f} мм" if lang == 'ru' else f"{v:.0f} mm") if mode == 'total' else f"{v:+.0f}°", fontsize=26, color=INK, fontweight='bold', va='center', ha='right')
                # what it means
                fig.patches.append(plt.Rectangle((0, 0.075), 1, 0.06, transform=fig.transFigure, fc='#16243a', ec='none'))
                fig.text(0.05, 0.105, line, fontsize=25, color='#ffb066', fontweight='bold', va='center')
                fig.text(0.05, 0.04, X['src'], fontsize=15, color=MUTED, va='center')
                fig.savefig(fd / f'{n_:03d}.png', facecolor=PAPER); plt.close(fig); n_ += 1
            # timing: the facts slower, the forecast smooth
            per = [fr['d'] for fr in frames]
            lst = fd / 'list.txt'; lst.write_text(''.join(f"file '{i:03d}.png'\nduration {d}\n" for i, d in enumerate(per)) + f"file '{len(per) - 1:03d}.png'\n")
            out = OUT / f'{kind}_{lang}.mp4'; tmp = OUT / f'.{kind}_{lang}.part.mp4'
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-map', '0:v', '-map', '1:a', '-vf',
                            'framerate=fps=30:interp_start=0:interp_end=255:scene=100,format=yuv420p', '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast',
                            '-c:a', 'aac', '-b:a', '48k', '-shortest', '-movflags', '+faststart', str(tmp)], check=True)
            tmp.replace(out); shutil.rmtree(fd); print(out, out.stat().st_size // 1024, 'KB', flush=True)
        meta[kind] = {'until': fts[-1].strftime('%Y-%m-%dT%HZ') if fts else None, 'wettest': [wet[0][0], round(wet[1], 1)]}
    json.dump(meta, open(OUT / 'meta.json', 'w'), ensure_ascii=False)


if __name__ == '__main__':
    main()
