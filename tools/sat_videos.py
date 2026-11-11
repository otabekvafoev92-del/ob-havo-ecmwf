"""Satellite videos for the bot, remade about every 30 minutes (workflow sat.yml):
  clouds — the last 6 hours of Meteosat IODC infrared (EUMETSAT) with the H SAF rain estimate on top;
  rain   — only where it rains or snows now (H SAF), on a white map: where precipitation falls and how it moves.
For Uzbekistan, Kazakhstan, Kyrgyzstan, in Russian and Uzbek → out/{R}_{kind}_{lang}.mp4 and out/meta.json."""
import io, json, re, shutil, subprocess, sys, time, datetime as dt, pathlib, tempfile, concurrent.futures as cf
import numpy as np, requests
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection as LC, PolyCollection as PCOL
from PIL import Image, ImageFilter, ImageEnhance

HERE = pathlib.Path(__file__).resolve().parent.parent / 'prob'
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
VIEW = {'UZ': (55, 74, 36.5, 46), 'KZ': (46, 88, 40, 56), 'KG': (68, 81, 38.5, 44)}
TZ = {'UZ': 5, 'KZ': 5, 'KG': 6}
W = 'https://view.eumetsat.int/geoserver'
TX = {'ru': dict(clouds='Спутник · тучи и осадки', rain='Спутник · где идут осадки', at='снимок {t}', tz={'UZ': 'по Ташкенту', 'KZ': 'по Астане', 'KG': 'по Бишкеку'},
                 lc='белое — тучи (ярче и объёмнее — плотнее и выше) · синее/фиолетовое — осадки (H SAF)', lr='голубое — слабые · синее — умеренные · фиолетовое — сильные осадки (оценка со спутника H SAF)',
                 fc='прогноз на {t}', fcn='по движению облаков', g=['тонкие облака', 'плотные облака', 'слабые осадки', 'умеренные', 'сильные']),
      'uz': dict(clouds='Sun’iy yo‘ldosh · bulut va yog‘in', rain='Sun’iy yo‘ldosh · yog‘in qayerda', at='surat {t}', tz={'UZ': 'Toshkent vaqti', 'KZ': 'Ostona vaqti', 'KG': 'Bishkek vaqti'},
                 lc='oq — bulut (qancha yorqin — shuncha qalin) · ko‘k/binafsha — yog‘in (H SAF)', lr='havorang — kuchsiz · ko‘k — o‘rtacha · binafsha — kuchli yog‘in (H SAF)',
                 fc='prognoz: {t}', fcn='bulut harakati bo‘yicha', g=['yupqa bulut', 'qalin bulut', 'kuchsiz yog‘in', 'o‘rtacha', 'kuchli'])}
S = requests.Session()
CACHE = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else 'satcache'); CACHE.mkdir(parents=True, exist_ok=True)  # pictures and frames of earlier runs: only the new ones are made


def cached(name, make):
    f = CACHE / name
    if f.exists(): return Image.open(f).convert('RGBA')
    im = make()
    if im is not None: im.save(f)
    return im


def latest(layer):
    t = S.get(f"{W}/{layer.replace(':', '/')}/wms", params=dict(service='WMS', request='GetCapabilities', version='1.3.0'), timeout=90).text
    return dt.datetime.fromisoformat(re.search(r'<Dimension[^>]*name="time"[^>]*default="([^"]+)"', t).group(1).replace('Z', '+00:00'))


def get(layer, t, fmt, V, w, h):
    for _ in range(3):
        try:
            r = requests.get(f'{W}/wms', params=dict(service='WMS', version='1.3.0', request='GetMap', layers=layer, styles='', crs='EPSG:4326', bbox=f'{V[2]},{V[0]},{V[3]},{V[1]}',
                                                     width=w, height=h, format=fmt, transparent='true', time=t.strftime('%Y-%m-%dT%H:%M:%SZ')), timeout=120)
            if r.ok and r.headers.get('content-type', '').startswith('image'): return Image.open(io.BytesIO(r.content)).convert('RGBA')
        except Exception as e: print('retry', layer, t, e, flush=True)
    return None


def clouds_only(ir):
    """Only the clouds of the infrared picture: the ground (warm → darker grey, and cold steppe or snow → middle grey) taken away.
    Cloud tops are colder than the ground, so they are the brightest; a soft ramp from the clear ground's brightness up keeps thin clouds faint."""
    b = np.asarray(ir.convert('L'), float) / 255
    g = np.percentile(b, 35)  # most of the picture is clear ground: its brightness
    lo = max(0.42, g + 0.08); a = np.clip((b - lo) / 0.22, 0, 1); edge = np.clip((b - lo) / 0.03, 0, 1)
    c = 0.78 - 0.46 * a  # light grey (thin) → dark grey (thick, high); the clear sky stays white
    return Image.fromarray((np.dstack([c, c, c * 1.03, edge * (0.45 + 0.5 * a)]) * 255).astype(np.uint8), 'RGBA').filter(ImageFilter.GaussianBlur(0.8))


def mask_of(cm, size):
    """The EUMETSAT cloud mask as 0..1: white = cloud; green land, blue sea = clear (soft edges)."""
    m = np.asarray(cm.resize(size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.5)), float) / 255
    return np.clip((np.minimum(np.minimum(m[..., 0], m[..., 1]), m[..., 2]) * m[..., 3] - 0.55) / 0.35, 0, 1)


def smooth_masks(ms):
    """Every 15-minute slot gets a mask: a missing one from the nearest slot (before or after — never a different method, which made
    the clouds jump), then each blended with its neighbours (¼ ½ ¼) so small clouds fade in and out instead of popping."""
    have = [i for i, m in enumerate(ms) if m is not None]
    if not have: return ms
    full = [ms[min(have, key=lambda j: (abs(j - i), j))] for i in range(len(ms))]
    return [0.25 * full[max(i - 1, 0)] + 0.5 * full[i] + 0.25 * full[min(i + 1, len(full) - 1)] for i in range(len(full))]


def clouds_real(ir, m, g):
    """Clouds that look like clouds: white, thin ones see-through, thick ones bright with soft relief (lit from the north-west, the texture
    of the infrared picture) and a faint shadow on the ground. Where they are — the EUMETSAT cloud mask m; how thick/high — the infrared."""
    from matplotlib.colors import LightSource
    from scipy.ndimage import gaussian_filter, shift
    b = np.asarray(ir.convert('L'), float) / 255
    a = np.clip((b - g) / 0.35, 0, 1) * m  # 0 thin/low … 1 thick/high
    Hc = gaussian_filter(a, 1.6)
    hs = LightSource(azdeg=315, altdeg=40).hillshade(Hc * 60, vert_exag=1)
    base = 0.94 + 0.06 * np.clip(a * 1.4, 0, 1)
    base = base * (1 - 0.16 * np.clip(1 - gaussian_filter(m, 2.5) / np.maximum(m, 0.05), 0, 1))  # a slightly darker rim: the edge of each cloud is seen
    c = np.clip(base * (0.80 + 0.32 * hs), 0, 1)
    rgb = np.dstack([c * 0.985, c * 0.99, c])  # a touch of blue in the shade
    al = np.clip(m * (0.72 + 0.28 * np.clip(a * 1.5, 0, 1) ** 0.7), 0, 0.98)
    sh = gaussian_filter(shift(al, (6, 6), order=0, mode='nearest'), 4) * 0.42 * (1 - al)  # shadow, south-east of the cloud
    return (Image.fromarray((np.dstack([rgb, al]) * 255).astype(np.uint8), 'RGBA'),
            Image.fromarray((np.dstack([np.full(sh.shape + (3,), 0.25), sh]) * 255).astype(np.uint8), 'RGBA'))


MOUNTS = {'ru': [((75.6, 42.0), 'Тянь-Шань'), ((72.6, 38.7), 'Памир'), ((68.3, 39.1), 'Гиссар'), ((57.6, 38.3), 'Копетдаг'), ((80.5, 45.3), 'Джунгарский Алатау'), ((86.5, 49.2), 'Алтай')],
          'uz': [((75.6, 42.0), 'Tyan-Shan'), ((72.6, 38.7), 'Pomir'), ((68.3, 39.1), 'Hisor'), ((57.6, 38.3), 'Kopetdog‘'), ((80.5, 45.3), 'Jung‘or Olatovi'), ((86.5, 49.2), 'Oltoy')]}
RAINC = [(0.62, 0.84, 1.0), (0.24, 0.56, 0.93), (0.36, 0.22, 0.75)]
LAND = (0.667, 0.725, 0.549)  # #aab98c


def nowcast(ir, m, pr, ir0, m0, steps=12):
    """3 hours ahead by the motion of the clouds: the shift between the picture an hour ago and the last one (optical flow),
    the last clouds and rain carried on along it, 15 minutes a step."""
    import cv2
    from scipy.ndimage import gaussian_filter
    f = lambda i_, m_: (np.clip(np.asarray(i_.convert('L'), float) / 255 * 0.5 + m_ * 0.5, 0, 1) * 255).astype(np.uint8)
    fl = cv2.calcOpticalFlowFarneback(f(ir0, m0), f(ir, m), None, 0.5, 4, 31, 4, 7, 1.5, 0)
    u, v = (gaussian_filter(fl[..., k], 20) / 4 for k in (0, 1))  # per 15 minutes, smooth
    hh, ww = m.shape; X, Y = np.meshgrid(np.arange(ww, dtype=np.float32), np.arange(hh, dtype=np.float32))
    a_ir = np.ascontiguousarray(np.asarray(ir.convert('RGB'))); a_pr = np.ascontiguousarray(np.asarray(pr)) if pr is not None else None; out = []
    for k in range(1, steps + 1):
        mx, my = (X - k * u).astype(np.float32), (Y - k * v).astype(np.float32)
        rm = lambda a: cv2.remap(a, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        out.append((Image.fromarray(rm(a_ir)), rm(m.astype(np.float32)), Image.fromarray(rm(a_pr), 'RGBA') if a_pr is not None else None))
    return out


def legend(fig, X):
    """The colours as small tiles: thin and thick clouds, weak / moderate / heavy rain."""
    from matplotlib.patches import FancyBboxPatch
    tiles = [tuple(np.array(LAND) * 0.28 + 0.72), (0.97, 0.975, 0.985)] + [tuple(np.array(LAND) * 0.38 + np.array(c) * 0.62) for c in RAINC]
    x = 0.012; y = 0.022
    for col, name in zip(tiles, X['g']):
        fig.patches.append(FancyBboxPatch((x, y), 0.016, 0.026, boxstyle='round,pad=0.002,rounding_size=0.004', transform=fig.transFigure, fc=col, ec='#2b3a4e', lw=0.8))
        fig.text(x + 0.021, y + 0.004, name, fontsize=11, color='#1d2a3a', fontweight='bold', bbox=dict(boxstyle='round,pad=0.2', fc='#ffffffcc', ec='none'))
        x += 0.021 + 0.0075 * len(name) + 0.018


def relief(R):
    """The light relief of the mountains (made by the forecast build for the site: prob/hr/live/{R}/relief.png and its bounds)."""
    try:
        site = 'https://otabekvafoev92-del.github.io/ob-havo-ecmwf/prob/hr/live/' + R
        m = requests.get(site + '/meta.json', timeout=60).json(); r = requests.get(site + '/relief.png', timeout=60)
        return (Image.open(io.BytesIO(r.content)).convert('RGBA'), m['bounds']) if r.ok and m.get('relief') else None
    except Exception as e: print('relief', R, e, flush=True); return None


def clouds_mask(ir, m, g):
    """Clouds from the EUMETSAT cloud mask (day and night, it also finds the low clouds and fog that look like the ground in infrared):
    where it says cloud — grey; the infrared only sets the shade: warm low cloud light and faint grey, cold high thick cloud dark grey.
    g — the clear ground's brightness, one value for the whole video (so the shade does not jump between frames)."""
    b = np.asarray(ir.convert('L'), float) / 255
    a = np.clip((b - g) / 0.35, 0, 1)
    c = 0.80 - 0.48 * a
    return Image.fromarray((np.dstack([c, c, c * 1.03, m * (0.42 + 0.53 * a)]) * 255).astype(np.uint8), 'RGBA')


def rain_only(pr):
    """The H SAF colours redrawn in one family: light blue (weak) → blue → violet (strong), soft edges."""
    a = np.asarray(pr, float) / 255; al = a[..., 3]
    # the H SAF palette goes from yellow (weak) through green/cyan to blue/magenta (strong): its "coolness" ranks the intensity
    k = np.clip((a[..., 2] - a[..., 0] + 0.6) / 1.4, 0, 1)
    cols = np.array([[0.62, 0.84, 1.0], [0.24, 0.56, 0.93], [0.36, 0.22, 0.75]])
    c = np.where((k < 0.5)[..., None], cols[0] + (cols[1] - cols[0]) * (k / 0.5)[..., None], cols[1] + (cols[2] - cols[1]) * ((k - 0.5) / 0.5)[..., None])
    out = np.dstack([c, np.where(al > 0.1, 0.92, 0)])
    return Image.fromarray((out * 255).astype(np.uint8), 'RGBA')


def main():
    end, endp = latest('msg_iodc:ir108'), latest('msg_iodc:h63'); print('latest', end, endp, flush=True)
    G = json.load(open(HERE / 'geo_world.json'))['countries']; WAT = json.load(open(HERE / 'geo_water.json'))
    places = json.load(open(HERE / 'geo_prob.json'))['places']
    times = [end - dt.timedelta(minutes=15 * k) for k in range(24, -1, -1)]  # 6 hours
    import os
    only = os.environ.get('SAT_ONLY')
    for R, V in VIEW.items():
        if only and R != only: continue
        GA = json.load(open(HERE / 'geo_admin.json')).get(R, {})
        w = 1280; h = int(round(w * (V[3] - V[2]) / ((V[1] - V[0]) * np.cos(np.radians((V[2] + V[3]) / 2)))))
        with cf.ThreadPoolExecutor(8) as pool:  # all the pictures of the country at once
            irs = list(pool.map(lambda t: cached(f"{R}_ir_{t:%Y%m%d%H%M}.png", lambda: get('msg_iodc:ir108', t, 'image/jpeg', V, w, h)), times))
            cms = list(pool.map(lambda t: cached(f"{R}_cm_{t:%Y%m%d%H%M}.png", lambda: get('msg_iodc:clm', t, 'image/png', V, w // 2, h // 2)), times))
            prs = list(pool.map(lambda t: cached(f"{R}_pr_{min(t, endp):%Y%m%d%H%M}.png", lambda: get('msg_iodc:h63', min(t, endp), 'image/png', V, w // 3, h // 3)), times))
        M = smooth_masks([mask_of(c_, (w, h)) if c_ is not None else None for c_ in cms])
        gs = [np.median(np.asarray(ir.convert('L'), float)[m_ < 0.1]) / 255 for ir, m_ in zip(irs, M) if ir is not None and m_ is not None and (m_ < 0.1).sum() > 500]
        G0 = float(np.median(gs)) if gs else 0.4
        last = None; P = []
        for p in prs:  # a missing rain picture: the last one (no flicker); the 3–5 km blocks smoothed
            if p is not None: last = p.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(3))
            P.append(last)
        REL = relief(R); LAB = []
        for p in sorted([p for p in places if p.get('iso') == R and p.get('pop', 0) > (300000 if R == 'KZ' else 150000)], key=lambda p: -p.get('pop', 0)):
            if all(abs(p['lon'] - q['lon']) > 0.9 or abs(p['lat'] - q['lat']) > 0.35 for q in LAB): LAB.append(p)  # a smaller town next to a bigger one: no label
        FC = []  # 3 hours ahead by the motion of the clouds (the last picture and the one an hour before it)
        ok = [i for i in range(len(times)) if irs[i] is not None and M[i] is not None]
        if len(ok) > 5:
            try: FC = nowcast(irs[ok[-1]], M[ok[-1]], P[-1], irs[ok[-5]], M[ok[-5]])
            except Exception as e: print('nowcast', e, flush=True)
        seq = [(t, ir, pr, cm, False) for t, ir, pr, cm in zip(times, irs, P, M)] + [(end + dt.timedelta(minutes=15 * (k + 1)), a, c, b, True) for k, (a, b, c) in enumerate(FC)]
        sea = [np.asarray(r) for r in WAT['ocean']] + [np.asarray(l['r']) for l in WAT['lakes']]
        for kind in ('clouds',):  # one video: clouds (grey) and rain (blue) together
            for lang, X in TX.items():
                if only and lang != 'ru': continue
                fd = pathlib.Path(tempfile.mkdtemp()); n = 0
                for t, ir, pr, cm, fut in seq:
                    if ir is None and kind == 'clouds': continue
                    fr_ = CACHE / f"v6_{R}_{kind}_{lang}_{t:%Y%m%d%H%M}_{'p' if pr is not None else 'n'}{'m' if cm is not None else ''}.png"  # a frame drawn before: reused
                    if fr_.exists() and kind != 'clouds' and not fut: shutil.copy(fr_, fd / f'{n:03d}.png'); n += 1; continue  # clouds: drawn again each time (each mask is blended with its neighbours)
                    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(V[0], V[1]); ax.set_ylim(V[2], V[3]); ax.axis('off')
                    dark = False  # a white map: clear sky white, clouds grey → dark grey (the infrared ground looked like clouds)
                    fig.patch.set_facecolor('#ffffff'); ax.add_collection(PCOL(sea, facecolors='#7eaacb' if kind == 'clouds' else '#d6e8f2', edgecolors='#7fa9c6', linewidths=0.6, zorder=0.3))
                    if kind == 'clouds':  # a soft land colour and the mountains, so that the white clouds stand out like on a real photo from space
                        ax.set_facecolor('#aab98c'); fig.patch.set_facecolor('#aab98c')
                        if REL: ax.imshow(REL[0], extent=tuple(REL[1]), aspect='auto', zorder=0.2, alpha=1.0)
                        if cm is not None:
                            cl_, sh_ = clouds_real(ir, cm, G0)
                            ax.imshow(sh_, extent=(V[0], V[1], V[2], V[3]), aspect='auto', zorder=0.5); ax.imshow(cl_, extent=(V[0], V[1], V[2], V[3]), aspect='auto', zorder=0.6)
                        else: ax.imshow(clouds_only(ir), extent=(V[0], V[1], V[2], V[3]), aspect='auto', zorder=0.6)
                    if pr is not None: ax.imshow(rain_only(pr), extent=(V[0], V[1], V[2], V[3]), aspect='auto', alpha=0.62 if kind == 'clouds' else 0.9, zorder=0.8)
                    lc = '#ffffff' if dark else '#2b3a4e'
                    ax.add_collection(LC([np.asarray(r) for c in G.values() for r in c['rings']], colors=lc, linewidths=1.1, alpha=0.85))
                    if GA:
                        ax.add_collection(LC([np.asarray(r) for a in GA.get('adm2', []) for r in a['r']], colors=lc, linewidths=0.4, alpha=0.35, zorder=1))
                        ax.add_collection(LC([np.asarray(r) for a in GA['adm1'] for r in a['r']], colors='#ffffff', linewidths=2.6, alpha=0.55, zorder=1))  # regions: a light halo …
                        ax.add_collection(LC([np.asarray(r) for a in GA['adm1'] for r in a['r']], colors=lc, linewidths=1.3, alpha=0.9, zorder=1.1))  # … and a clear line
                    for p in LAB:
                        if True:
                            ax.plot(p['lon'], p['lat'], 'o', ms=4, color='#ffd27a' if dark else '#2b3a4e')
                            ax.text(p['lon'] + 0.1, p['lat'] + 0.07, p.get(lang) or p.get('ru', ''), color=lc, fontsize=11, fontweight='bold')
                    for (mx_, my_), nm in MOUNTS.get(lang, MOUNTS['ru']):
                        if V[0] + 0.5 < mx_ < V[1] - 1 and V[2] + 0.4 < my_ < V[3] - 0.6:
                            ax.text(mx_, my_, nm, fontsize=12, style='italic', color='#5b4632', ha='center', zorder=3, alpha=0.9)
                    loc = t + dt.timedelta(hours=TZ[R])
                    if fut:  # the forecast part: an orange label, so that it is not taken for a snapshot
                        fig.text(0.012, 0.955, f"{X[kind].split(' · ')[0]} · {X['fc'].format(t=loc.strftime('%H:%M'))} {X['tz'][R]} · {X['fcn']}", fontsize=16, fontweight='bold', color='#ffffff',
                                 bbox=dict(boxstyle='round,pad=0.4', fc='#c0562bdd', ec='none'))
                    else:
                        fig.text(0.012, 0.955, f"{X[kind]} · {X['at'].format(t=loc.strftime('%H:%M'))} {X['tz'][R]}", fontsize=16, fontweight='bold', color='#ffffff',
                                 bbox=dict(boxstyle='round,pad=0.4', fc='#1d2a3acc', ec='none'))
                    if kind == 'clouds': legend(fig, X)
                    else: fig.text(0.012, 0.025, X['lr'], fontsize=11, color='#ffffff', bbox=dict(boxstyle='round,pad=0.3', fc='#1d2a3aaa', ec='none'))
                    fig.savefig(fd / f'{n:03d}.png', facecolor=fig.get_facecolor()); plt.close(fig); shutil.copy(fd / f'{n:03d}.png', fr_); n += 1
                mp4 = OUT / f'{R}_{kind}_{lang}.mp4'
                subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '3', '-i', str(fd / '%03d.png'), '-vf',
                                'tpad=stop_mode=clone:stop_duration=1,framerate=fps=24:interp_start=0:interp_end=255:scene=100,scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p',
                                '-c:v', 'libx264', '-crf', '21', '-movflags', '+faststart', str(mp4)], check=True)
                print(mp4.name, n, 'frames', mp4.stat().st_size // 1024, 'KB', flush=True)
    old = time.time() - 8 * 3600  # the cache keeps 8 hours
    for f in CACHE.iterdir():
        if f.stat().st_mtime < old: f.unlink()
    json.dump({'made': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'last': end.strftime('%Y-%m-%dT%H:%M:%SZ'), 'rain': endp.strftime('%Y-%m-%dT%H:%M:%SZ')},
              open(OUT / 'meta.json', 'w'))


if __name__ == '__main__':
    main()
