"""The satellite in true colour, sharp (375 m VIIRS on NOAA-20/21, 250 m MODIS on Terra/Aqua; NASA GIBS): the passes of the
last two days over Uzbekistan as a video (each pass held, then eased into the next) and the latest clear pass as a Full HD
picture — in the Osmon look: navy header, borders, the towns in translucent grey labels.
Usage: python tools/sat_true.py out ru,uz  →  out/sattrue_{lang}.mp4, out/sattrue_{lang}.jpg, out/meta.json"""
import io, os, sys, json, math, pathlib, shutil, subprocess, tempfile, datetime as dt, concurrent.futures as cf
import numpy as np, requests
from PIL import Image
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
PASSES = [('MODIS_Terra_CorrectedReflectance_TrueColor', 'Terra · MODIS 250 м', 'Terra · MODIS 250 m', 10.5),
          ('VIIRS_NOAA21_CorrectedReflectance_TrueColor', 'NOAA-21 · VIIRS 375 м', 'NOAA-21 · VIIRS 375 m', 12.8),
          ('VIIRS_NOAA20_CorrectedReflectance_TrueColor', 'NOAA-20 · VIIRS 375 м', 'NOAA-20 · VIIRS 375 m', 13.3),
          ('MODIS_Aqua_CorrectedReflectance_TrueColor', 'Aqua · MODIS 250 м', 'Aqua · MODIS 250 m', 13.6)]
TX = {'ru': dict(title='Спутник · Узбекистан в истинных цветах', when='{d} · около {h}:00', tz='по Ташкенту', morning='утро', day='день',
                 leg='белое — облака и снег в горах · серое — дымка, пыль · бурое — пустыня · тёмное — вода', src='NASA GIBS · {s}', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']),
      'uz': dict(title='Sun’iy yo‘ldosh · O‘zbekiston haqiqiy ranglarda', when='{d} · taxminan {h}:00', tz='Toshkent vaqti', morning='ertalab', day='kunduzi',
                 leg='oq — bulut va tog‘dagi qor · kulrang — tuman, chang · jigarrang — cho‘l · to‘q — suv', src='NASA GIBS · {s}', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'])}


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


def coverage(a):
    """The share of the map (Uzbekistan's box) the pass really covers (no black swath gaps)."""
    return float((a.max(axis=2) > 12).mean())


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
    ax.text(0.006, 0.012, X['leg'], transform=ax.transAxes, fontsize=13, color='white', zorder=9, bbox=dict(boxstyle='round,pad=0.4', fc='#0b1220', ec='none', alpha=0.55))
    ax.text(0.994, 0.012, X['src'].format(s=meta[2 if lang != 'ru' else 1]) + ' · t.me/ObHavo_ECMWF_bot', transform=ax.transAxes, ha='right', fontsize=12, color='white', zorder=9,
            bbox=dict(boxstyle='round,pad=0.4', fc='#0b1220', ec='none', alpha=0.55))
    fig.patches.append(Rectangle((0, 0.906), 1, 0.094, transform=fig.transFigure, fc=PV.NAVY, ec='none', zorder=-1))
    fig.text(0.016, 0.953, 'OSMON', fontsize=22, fontweight='bold', color=PV.ORANGE, va='center')
    fig.text(0.093, 0.953, X['title'], fontsize=22, fontweight='bold', color='white', va='center')
    d = meta[0]; h = meta[3]
    fig.text(0.984, 0.968, f"{X['wd'][d.weekday()]} {d:%d.%m} · {X['morning'] if h < 12 else X['day']}", fontsize=24, fontweight='bold', color='#ffd29c', ha='right', va='center')
    fig.text(0.984, 0.928, f"{X['when'].format(d=f'{d:%d.%m}', h=int(round(h + 5 - LC / 15)))} {X['tz']}", fontsize=14, color='#a9bdd6', ha='right', va='center')
    fig.savefig(out, dpi=DPI, facecolor=fig.get_facecolor()); plt.close(fig)


CTX = {}


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); langs = (sys.argv[2] if len(sys.argv) > 2 else 'ru,uz').split(',')
    today = dt.datetime.utcnow().date(); days = [today - dt.timedelta(days=1), today]
    jobs = [(lay, d) for d in days for lay in PASSES]
    with cf.ThreadPoolExecutor(6) as ex: imgs = list(ex.map(lambda j: fetch(j[0][0], j[1]), jobs))
    shots = []
    for (lay, d), a in zip(jobs, imgs):
        if a is None: continue
        c = coverage(a); print(d, lay[0], 'coverage', round(c, 2), flush=True)
        if c >= 0.8: shots.append(((d, lay[1], lay[2], lay[3]), a))
    shots.sort(key=lambda s: (s[0][0], s[0][3]))
    if not shots: print('no clear passes'); return
    G = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']; GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']
    CTX['borders'] = [([np.asarray(r) for k, c in G.items() if k != 'UZ' for r in c['rings']], (1, 1, 1, 0.55), 1.0, 3),
                      ([np.asarray(r) for a in GA['adm1'] for r in a['r']], (1, 1, 1, 0.45), 0.7, 3.05), ([np.asarray(r) for r in G['UZ']['rings']], '#ffd29c', 2.2, 3.3)]
    tmp = pathlib.Path(tempfile.mkdtemp()); meta = []
    for lang in langs:
        files = []
        for k, (m, a) in enumerate(shots):
            f = tmp / f'{lang}_{k:02d}.png'; draw((lang, k, a, m, f)); files.append(f)
        # the picture: the latest clear pass
        Image.open(files[-1]).convert('RGB').save(out / f'sattrue_{lang}.jpg', quality=92)
        # the video: each pass held 2.5 s, eased into the next over 1 s (blended frames)
        fr = tmp / f'v_{lang}'; fr.mkdir(); n = 0; lst = []
        ims = [np.asarray(Image.open(f).convert('RGB'), np.float32) for f in files]
        for k, im in enumerate(ims):
            Image.fromarray(im.astype(np.uint8)).save(fr / f'{n:04d}.jpg', quality=93); lst.append((n, 2.5)); n += 1
            if k + 1 < len(ims):
                for q in range(1, 12):
                    a = q / 12; Image.fromarray(((1 - a) * im + a * ims[k + 1]).astype(np.uint8)).save(fr / f'{n:04d}.jpg', quality=93); lst.append((n, 1 / 12)); n += 1
        lst[-1] = (lst[-1][0], 3.5)
        (fr / 'list.txt').write_text(''.join(f"file '{i:04d}.jpg'\nduration {d_}\n" for i, d_ in lst) + f"file '{lst[-1][0]:04d}.jpg'\n")
        part = out / f'.sattrue_{lang}.part.mp4'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(fr / 'list.txt'), '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-map', '0:v', '-map', '1:a',
                        '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-crf', '19', '-maxrate', '4000k', '-bufsize', '8000k', '-preset', 'slow', '-c:a', 'aac', '-b:a', '48k', '-shortest', '-movflags', '+faststart', str(part)], check=True)
        part.replace(out / f'sattrue_{lang}.mp4'); print(out / f'sattrue_{lang}.mp4', (out / f'sattrue_{lang}.mp4').stat().st_size // 1024, 'KB', flush=True)
    json.dump(dict(made=dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), passes=[[m[0].isoformat(), m[2], m[3]] for m, _ in shots]), open(out / 'meta.json', 'w'))
    shutil.rmtree(tmp)


if __name__ == '__main__':
    main()
