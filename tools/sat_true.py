"""The satellite in true colour, sharp (375 m VIIRS on NOAA-20/21, 250 m MODIS on Terra/Aqua; NASA GIBS): the passes of the
last two days over Uzbekistan as a video (each pass held, then eased into the next) and the latest clear pass as a Full HD
picture — in the Osmon look: navy header, borders, the towns in translucent grey labels.
Usage: python tools/sat_true.py out ru,uz  →  out/sattrue_{lang}.mp4, out/sattrue_{lang}.jpg, out/meta.json"""
import io, os, sys, json, math, pathlib, shutil, subprocess, tempfile, datetime as dt, concurrent.futures as cf
import numpy as np, requests
from PIL import Image, ImageFilter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import prob15_video as PV

W, H, DPI = 1920, 1080, 100
MAP = (0, 0, 1, 0.906)
LA0, LA1, LC = 36.9, 46.0, 64.6
COSL = math.cos(math.radians((LA0 + LA1) / 2)); SPAN = (LA1 - LA0) / COSL * (MAP[2] * W) / (MAP[3] * H)
EXT = (LC - SPAN / 2, LC + SPAN / 2)
GIBS = 'https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi'
NORAD = {'Terra': 25994, 'NOAA-20': 43013, 'NOAA-21': 54234}
HALF = {'VIIRS': 1500.0, 'MODIS': 1160.0}  # half the swath, km
RULE = os.environ.get('SAT_RULE', 'near')  # which orbit the daily mosaic keeps where two orbits overlap
PASSES = [('MODIS_Terra_CorrectedReflectance_TrueColor', 'Terra · MODIS 250 м', 'Terra · MODIS 250 m', 10.5),
          ('VIIRS_NOAA21_CorrectedReflectance_TrueColor', 'NOAA-21 · VIIRS 375 м', 'NOAA-21 · VIIRS 375 m', 12.8),
          ('VIIRS_NOAA20_CorrectedReflectance_TrueColor', 'NOAA-20 · VIIRS 375 м', 'NOAA-20 · VIIRS 375 m', 13.3),
          ]  # (Aqua's MODIS is past its prime: striped swath edges, so it is left out)
TX = {'ru': dict(title='Спутник · Узбекистан в истинных цветах', title_live='Спутник · облака сейчас (Meteosat, ИК)', when='{d} · около {h}:00', tz='по Ташкенту', morning='утро', day='день',
                 leg='белое — облака и снег в горах · серое — дымка, пыль · бурое — пустыня · тёмное — вода', src='NASA GIBS · {s}', live='снимок {t} по Ташкенту', leg2='облака — Meteosat (каждые 30 мин, днём и ночью) · синее — осадки · земля — чистый снимок VIIRS', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']),
      'uz': dict(title='Sun’iy yo‘ldosh · O‘zbekiston haqiqiy ranglarda', title_live='Sun’iy yo‘ldosh · hozirgi bulutlar (Meteosat, IQ)', when='{d} · taxminan {h}:00', tz='Toshkent vaqti', morning='ertalab', day='kunduzi',
                 leg='oq — bulut va tog‘dagi qor · kulrang — tuman, chang · jigarrang — cho‘l · to‘q — suv', src='NASA GIBS · {s}', live='surat {t} Toshkent vaqti', leg2='bulut — Meteosat (har 30 daqiqa, kechayu kunduz) · ko‘k — yog‘in · yer — toza VIIRS surati', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'])}


def fetch(layer, day, px=3000):
    h = int(px * (LA1 - LA0) / (EXT[1] - EXT[0]))
    for _ in range(3):
        try:
            r = requests.get(GIBS, params=dict(SERVICE='WMS', REQUEST='GetMap', VERSION='1.3.0', LAYERS=layer, STYLES='', CRS='EPSG:4326', BBOX=f'{LA0},{EXT[0]},{LA1},{EXT[1]}',
                                               WIDTH=px, HEIGHT=h, FORMAT='image/jpeg', TIME=day.isoformat()), timeout=240)
            if r.ok and r.headers.get('content-type', '').startswith('image') and len(r.content) > 50000:
                a = np.asarray(Image.open(io.BytesIO(r.content)).convert('RGB'))
                return a
        except Exception as e: print('gibs', layer, day, e, flush=True)
    return None


_TLE = {}


def orbits(sat, day):
    """The satellite's daytime ground tracks over the region on that day: [(t0 seconds, lat[], lon[])], one per orbit (sgp4 on CelesTrak's elements)."""
    from skyfield.api import EarthSatellite, load, wgs84
    if sat not in _TLE:
        r = requests.get('https://celestrak.org/NORAD/elements/gp.php', params=dict(CATNR=NORAD[sat], FORMAT='TLE'), timeout=60).text.strip().splitlines()
        _TLE[sat] = [x.strip() for x in r[-3:]]
    ts = load.timescale(builtin=True); n, l1, l2 = _TLE[sat]; es = EarthSatellite(l1, l2, n, ts)
    sec = np.arange(0, 18 * 3600, 8.0); t = ts.utc(day.year, day.month, day.day, 0, 0, sec)
    sp = wgs84.subpoint_of(es.at(t)); la, lo = sp.latitude.degrees, sp.longitude.degrees
    solar = (sec / 3600 + lo / 15) % 24
    ok = (la > 15) & (la < 66) & (lo > EXT[0] - 35) & (lo < EXT[1] + 35) & (solar > 7) & (solar < 17)
    idx = np.where(ok)[0]; out = []
    if not len(idx): return out
    for g in np.split(idx, np.where(np.diff(idx) > 1)[0] + 1):
        if len(g) > 5: out.append((sec[g[0]], la[g], lo[g]))
    return out


def _gc(la1, lo1, la2, lo2):
    p1, p2 = np.radians(la1), np.radians(la2); dl = np.radians(lo2 - lo1)
    return 6371 * np.arccos(np.clip(np.sin(p1) * np.sin(p2) + np.cos(p1) * np.cos(p2) * np.cos(dl), -1, 1))


def assign(sat, kind, day, gla, glo, rule=None):
    """For each point of the grid: which orbit of the day the mosaic shows there (-1: none) and the orbits' cross-track distances."""
    ob = orbits(sat, day)
    if not ob: return np.full(gla.shape, -1), ob, None
    D = np.stack([np.min(_gc(gla[..., None], glo[..., None], la[None, None, ::2], lo[None, None, ::2]), axis=-1) for _, la, lo in ob])  # km
    rule = rule or RULE; cov = D < HALF[kind]; A = np.full(gla.shape, -1)
    order = range(len(ob)) if rule == 'late' else range(len(ob) - 1, -1, -1)
    if rule == 'near':
        A = np.where(cov.any(0), np.argmin(np.where(cov, D, 1e9), axis=0), -1)
    else:
        for k in order: A = np.where(cov[k], k, A)  # the later (or earlier) orbit painted over
    return A, ob, D


def seams(A):
    """The mask of the grid points where the shown orbit changes."""
    e = np.zeros(A.shape, bool)
    e[:, 1:] |= (A[:, 1:] != A[:, :-1]) & (A[:, 1:] >= 0) & (A[:, :-1] >= 0)
    e[1:, :] |= (A[1:, :] != A[:-1, :]) & (A[1:, :] >= 0) & (A[:-1, :] >= 0)
    return e


def coverage(a):
    """The share of the map (Uzbekistan's box) the pass really covers (no black swath gaps)."""
    return float((a.max(axis=2) > 8).mean())


def draw(job):
    lang, k, img, meta, out = job; X = TX[lang]
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI); fig.patch.set_facecolor('#0b1220')
    ax = fig.add_axes(MAP); ax.imshow(img, extent=(EXT[0], EXT[1], LA0, LA1), origin='upper', interpolation='lanczos', aspect='auto', zorder=0)
    ax.set_xlim(*EXT); ax.set_ylim(LA0, LA1); ax.set_aspect(1 / COSL); ax.axis('off')
    for rings, col, lw, z in CTX['borders']: ax.add_collection(LineCollection(rings, colors=col, linewidths=lw, zorder=z, capstyle='round', joinstyle='round'))
    L = 0 if lang == 'ru' else 1
    for tw in PV.TOWNS:
        ax.plot(tw[3], tw[2], 'o', ms=6, mfc='#ffffff', mec='#14233a', mew=1.5, zorder=8)
        ax.annotate(tw[L], (tw[3], tw[2]), xytext=(9, 6), textcoords='offset pixels', fontsize=14, fontweight='semibold', color='#14233a', zorder=9,
                    bbox=dict(boxstyle='round,pad=0.25,rounding_size=0.6', fc='#f1f3f5', ec='none', alpha=0.72))
    live = len(meta) > 5 and meta[5] is not None
    ax.text(0.006, 0.012, X['leg2' if live else 'leg'], transform=ax.transAxes, fontsize=13, color='white', zorder=9, bbox=dict(boxstyle='round,pad=0.4', fc='#0b1220', ec='none', alpha=0.55))
    PV.brand(ax, 0.994, 0.012, X['src'].format(s=meta[2 if lang != 'ru' else 1]) + ' · Bot - @ObHavo_ECMWF_bot · Kanal - @osmon_obhavo', transform=ax.transAxes, ha='right', fontsize=12, color='white', zorder=9,
            bbox=dict(boxstyle='round,pad=0.4', fc='#0b1220', ec='none', alpha=0.55))
    fig.patches.append(Rectangle((0, 0.906), 1, 0.094, transform=fig.transFigure, fc=PV.NAVY, ec='none', zorder=-1))
    PV.mark(fig, 0.016 + 22 / W, 0.953, 44, ink='#ffffff', rings=(20, 32, 44))  # the channel's logo
    fig.text(0.016 + 50 / W, 0.953, 'osmon', fontsize=22, fontweight='bold', color='white', va='center')
    d = meta[0]; h = meta[3]
    fig.text(0.093, 0.953, X['title_live' if live else 'title'], fontsize=22, fontweight='bold', color='white', va='center')
    if live:
        lt = meta[5]
        fig.text(0.984, 0.968, f"{X['wd'][lt.weekday()]} {lt:%d.%m} · {lt:%H:%M}", fontsize=24, fontweight='bold', color='#ffd29c', ha='right', va='center')
        fig.text(0.984, 0.928, X['live'].format(t=f'{lt:%H:%M}'), fontsize=14, color='#a9bdd6', ha='right', va='center')
        fig.savefig(out, dpi=DPI, facecolor=fig.get_facecolor()); plt.close(fig); return
    fig.text(0.984, 0.968, f"{X['wd'][d.weekday()]} {d:%d.%m} · {X['morning'] if h < 12 else X['day']}", fontsize=24, fontweight='bold', color='#ffd29c', ha='right', va='center')
    fig.text(0.984, 0.928, f"{X['when'].format(d=f'{d:%d.%m}', h=int(round(h + 5 - LC / 15)))} {X['tz']}", fontsize=14, color='#a9bdd6', ha='right', va='center')
    fig.savefig(out, dpi=DPI, facecolor=fig.get_facecolor()); plt.close(fig)


EUM = 'https://view.eumetsat.int/geoserver'


def eum_latest(layer):
    import re
    t = requests.get(f"{EUM}/{layer.replace(':', '/')}/wms", params=dict(service='WMS', request='GetCapabilities', version='1.3.0'), timeout=90).text
    return dt.datetime.fromisoformat(re.search(r'<Dimension[^>]*name="time"[^>]*default="([^"]+)"', t).group(1).replace('Z', '+00:00')).replace(tzinfo=None)


def eum(layer, t, fmt, w, h):
    for _ in range(3):
        try:
            r = requests.get(f'{EUM}/wms', params=dict(service='WMS', version='1.3.0', request='GetMap', layers=layer, styles='', crs='EPSG:4326', bbox=f'{LA0},{EXT[0]},{LA1},{EXT[1]}',
                                                       width=w, height=h, format=fmt, transparent='true', time=t.strftime('%Y-%m-%dT%H:%M:%SZ')), timeout=120)
            if r.ok and r.headers.get('content-type', '').startswith('image'): return Image.open(io.BytesIO(r.content)).convert('RGBA')
        except Exception as e: print('eum', layer, t, e, flush=True)
    return None


def clear_ground(today, n=10):
    """A cloud-free picture of the ground: the last n days of VIIRS, per point a darker-than-middle one (clouds are bright; the snow that stays, stays)."""
    days = [today - dt.timedelta(days=k) for k in range(n)]
    with cf.ThreadPoolExecutor(5) as ex: ims = [a for a in ex.map(lambda d: fetch('VIIRS_NOAA20_CorrectedReflectance_TrueColor', d), days) if a is not None]
    S_ = np.stack(ims).astype(np.float32); L = S_.mean(-1); L[S_.max(-1) < 8] = 1e9  # swath gaps never win
    k = np.argsort(L, axis=0)[min(2, len(ims) - 1)]  # the third darkest: shadows and dark gaps are left out too
    return np.take_along_axis(S_, k[None, ..., None].repeat(3, -1), 0)[0]


def live_frames(ground, hours=12):
    """Meteosat over the Indian Ocean every 30 minutes up to its latest picture: its clouds (cloud mask + infrared, day and night)
    and the rain (H SAF) laid on the clear ground — so the video goes on from the sharp passes to now."""
    _a = sys.argv; sys.argv = [_a[0], tempfile.mkdtemp(), tempfile.mkdtemp()]
    import sat_videos as SV
    sys.argv = _a
    end = eum_latest('msg_iodc:ir108'); endp = eum_latest('msg_iodc:h63'); end = end.replace(minute=end.minute - end.minute % 30)
    times = [end - dt.timedelta(minutes=30 * k) for k in range(hours * 2, -1, -1)]
    H_, W_ = ground.shape[:2]; w = 1600; h = int(w * H_ / W_)
    with cf.ThreadPoolExecutor(8) as ex:
        irs = list(ex.map(lambda t: eum('msg_iodc:ir108', t, 'image/jpeg', w, h), times))
        cms = list(ex.map(lambda t: eum('msg_iodc:clm', t, 'image/png', w // 2, h // 2), times))
        prs = list(ex.map(lambda t: eum('msg_iodc:h63', min(t, endp), 'image/png', w // 3, h // 3), times))
    M = SV.smooth_masks([SV.mask_of(c_, (w, h)) if c_ is not None else None for c_ in cms])
    gs = [np.median(np.asarray(ir.convert('L'), float)[m_ < 0.1]) / 255 for ir, m_ in zip(irs, M) if ir is not None and m_ is not None and (m_ < 0.1).sum() > 500]
    G0 = float(np.median(gs)) if gs else 0.4; out = []; lastp = None
    for t, ir, m_, pr in zip(times, irs, M, prs):
        if pr is not None: lastp = pr
        if ir is None or m_ is None: continue
        cl, sh = SV.clouds_real(ir, m_, G0)
        a = ground.copy()
        for lay in (sh, cl) + ((SV.rain_only(lastp.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(2))),) if lastp is not None else ()):
            L_ = np.asarray(lay.resize((W_, H_), Image.BICUBIC), np.float32) / 255; al = L_[..., 3:4] * (0.6 if lay is not sh and lay is not cl else 1)
            a = a * (1 - al) + L_[..., :3] * 255 * al
        out.append((t, a.astype(np.uint8)))
    print('live frames', len(out), times[0], end, flush=True)
    return out


CTX = {}


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); langs = (sys.argv[2] if len(sys.argv) > 2 else 'ru,uz').split(',')
    today = dt.datetime.utcnow().date(); days = [today - dt.timedelta(days=2), today - dt.timedelta(days=1), today]
    jobs = [(lay, d) for d in days for lay in PASSES]
    with cf.ThreadPoolExecutor(6) as ex: imgs = list(ex.map(lambda j: fetch(j[0][0], j[1]), jobs))
    shots = []
    for (lay, d), a in zip(jobs, imgs):
        if a is None: continue
        c = coverage(a); print(d, lay[0], 'coverage', round(c, 2), flush=True)
        if c >= 0.8: shots.append(((d, lay[1], lay[2], lay[3], lay[0]), a))
    shots.sort(key=lambda s: (s[0][0], s[0][3]))
    if not shots: print('no clear passes'); return
    G = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']; GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']
    CTX['borders'] = [([np.asarray(r) for k, c in G.items() if k != 'UZ' for r in c['rings']], (1, 1, 1, 0.55), 1.0, 3),
                      ([np.asarray(r) for a in GA['adm1'] for r in a['r']], (1, 1, 1, 0.45), 0.7, 3.05), ([np.asarray(r) for r in G['UZ']['rings']], '#ffd29c', 2.2, 3.3)]
    # the orbits: a daily mosaic is stitched of neighbouring orbits ~100 min apart, the clouds jump at the seam —
    # keep the passes where one orbit shows the whole of Uzbekistan, soften a seam that is left outside it
    from matplotlib.path import Path as MPath
    from scipy.ndimage import binary_dilation, gaussian_filter, zoom as nzoom
    F = 10; good = []
    for (m, a) in shots:
        h_, w_ = a.shape[:2]; gy, gx = np.mgrid[0:h_:F, 0:w_:F] + F / 2
        gla = LA1 - gy / h_ * (LA1 - LA0); glo = EXT[0] + gx / w_ * (EXT[1] - EXT[0])
        if 'uz' not in CTX:
            pts = np.c_[glo.ravel(), gla.ravel()]; uz = np.zeros(len(pts), bool)
            for r in G['UZ']['rings']: uz |= MPath(np.asarray(r)).contains_points(pts)
            CTX['uz'] = binary_dilation(uz.reshape(gla.shape), iterations=2)
        lay = m[4]; sat = 'Terra' if 'Terra' in lay else ('NOAA-21' if 'NOAA21' in lay else 'NOAA-20'); kind = 'MODIS' if 'MODIS' in lay else 'VIIRS'
        try:
            A, ob, D = assign(sat, kind, m[0], gla, glo)
        except Exception as e:
            print('orbit', sat, m[0], e, flush=True); good.append((m, a, 0.5)); continue
        U = CTX['uz']; inuz = A[U]; sm = seams(A)
        bad = float((sm & U).sum()) + 1000 * float((inuz < 0).mean() > 0.02)
        print(m[0], sat, 'orbits', len(ob), 'seam cells in UZ', int((sm & U).sum()), 'seam cells', int(sm.sum()), flush=True)
        if os.environ.get('SAT_DEBUG'):
            dbg = a.copy()
            for rule, col in (('late', (255, 0, 0)), ('early', (0, 255, 0)), ('near', (0, 200, 255))):
                A2 = assign(sat, kind, m[0], gla, glo, rule)[0]; e = nzoom(seams(A2).astype(np.uint8), F, order=0)[:h_, :w_] > 0
                e = binary_dilation(e, iterations=2); dbg[e] = col
            (out / 'debug').mkdir(exist_ok=True); Image.fromarray(dbg).resize((1500, int(1500 * h_ / w_))).save(out / 'debug' / f'{m[0]}_{sat}.jpg', quality=85)
        if sm.any():  # soften the seam: a blurred band ~25 km wide
            band = gaussian_filter(nzoom(binary_dilation(sm, iterations=1).astype(np.float32), F, order=1)[:h_, :w_], 6)
            band = np.clip(band / max(band.max(), 1e-6) * 1.6, 0, 1)[..., None]
            bl = np.stack([gaussian_filter(a[..., c].astype(np.float32), 5) for c in range(3)], -1)
            a = (a * (1 - band) + bl * band).astype(np.uint8)
        good.append((m, a, bad))
    clean = [(m, a) for m, a, b in good if b == 0]
    print('clean passes', len(clean), 'of', len(good), flush=True)
    shots = clean if len(clean) >= 2 else [(m, a) for m, a, b in sorted(good, key=lambda g: g[2])[:max(2, len(clean))]]
    shots.sort(key=lambda s: (s[0][0], s[0][3]))
    # the video goes on to now: Meteosat every 30 minutes after the last sharp pass
    LIVE = []
    try:
        ground = clear_ground(today)
        t_last = max(dt.datetime.combine(m[0], dt.time()) + dt.timedelta(hours=m[3] - LC / 15) for m, _ in shots)
        LIVE = [(t, a) for t, a in live_frames(ground) if t > t_last + dt.timedelta(minutes=20)]
    except Exception as e: print('live', e, flush=True)
    tmp = pathlib.Path(tempfile.mkdtemp()); PIC = {}
    for lang in langs:
        files = []; kinds = []
        for k, (m, a) in enumerate(shots):
            f = tmp / f'{lang}_{k:02d}.png'; draw((lang, k, a, m, f)); files.append(f); kinds.append('pass')
        # the picture: the latest day's VIIRS pass, the sharpest
        best = max((k for k, (m, _) in enumerate(shots) if 'VIIRS' in m[1]), key=lambda k: (shots[k][0][0], -k), default=len(files) - 1)
        for k, (t, a) in enumerate(LIVE):
            lt = t + dt.timedelta(hours=5); f = tmp / f'{lang}_L{k:02d}.png'
            draw((lang, k, a, (lt.date(), 'Meteosat · EUMETSAT', 'Meteosat · EUMETSAT', lt.hour, 'live', lt), f)); files.append(f); kinds.append('live')
        # the picture: by day the sharp true-colour pass; at night (or when the pass is old) the clouds now, Meteosat infrared
        bm = shots[best][0]; t_pass = dt.datetime.combine(bm[0], dt.time()) + dt.timedelta(hours=bm[3] - LC / 15)
        loc = dt.datetime.utcnow() + dt.timedelta(hours=5)
        night = loc.hour < 8 or loc.hour >= 17
        if LIVE and (night or LIVE[-1][0] - t_pass > dt.timedelta(hours=4)):
            Image.open(files[-1]).convert('RGB').save(out / f'sattrue_{lang}.jpg', quality=92)
            PIC.update(k='live', t=(LIVE[-1][0] + dt.timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M'))
        else:
            Image.open(files[best]).convert('RGB').save(out / f'sattrue_{lang}.jpg', quality=92)
            PIC.update(k='pass', d=bm[0].isoformat(), h=int(round(bm[3] + 5 - LC / 15)), s=bm[2])
        # the video: a sharp pass held 2.5 s and eased into the next over 1 s; the Meteosat half-hours run on, 0.5 s each, blended
        fr = tmp / f'v_{lang}'; fr.mkdir(); n = 0; lst = []
        prev = None
        for k, f in enumerate(files):
            im = np.asarray(Image.open(f).convert('RGB'), np.float32)
            if prev is not None:
                nb = 12 if kinds[k] == 'pass' or kinds[k - 1] == 'pass' else 6
                for q in range(1, nb):
                    w_ = q / nb; Image.fromarray(((1 - w_) * prev + w_ * im).astype(np.uint8)).save(fr / f'{n:04d}.jpg', quality=93); lst.append((n, 1 / 30 * (2.5 if nb == 12 else 1.5))); n += 1
            Image.fromarray(im.astype(np.uint8)).save(fr / f'{n:04d}.jpg', quality=93); lst.append((n, 2.5 if kinds[k] == 'pass' else 0.3)); n += 1
            prev = im
        lst[-1] = (lst[-1][0], 3.5)
        (fr / 'list.txt').write_text(''.join(f"file '{i:04d}.jpg'\nduration {d_}\n" for i, d_ in lst) + f"file '{lst[-1][0]:04d}.jpg'\n")
        part = out / f'.sattrue_{lang}.part.mp4'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(fr / 'list.txt'), '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-map', '0:v', '-map', '1:a',
                        '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-crf', '21', '-maxrate', '4000k', '-bufsize', '8000k', '-preset', 'slow', '-c:a', 'aac', '-b:a', '48k', '-shortest', '-movflags', '+faststart', str(part)], check=True)
        part.replace(out / f'sattrue_{lang}.mp4'); print(out / f'sattrue_{lang}.mp4', (out / f'sattrue_{lang}.mp4').stat().st_size // 1024, 'KB', flush=True)
    json.dump(dict(made=dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), passes=[[m[0].isoformat(), m[2], m[3]] for m, _ in shots], live=[LIVE[0][0].isoformat(), LIVE[-1][0].isoformat()] if LIVE else None, pic=PIC), open(out / 'meta.json', 'w'))
    shutil.rmtree(tmp)


if __name__ == '__main__':
    main()
