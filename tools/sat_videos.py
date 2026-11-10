"""Satellite videos for the bot, remade about every 30 minutes (workflow sat.yml):
  clouds — the last 6 hours of Meteosat IODC infrared (EUMETSAT) with the H SAF rain estimate on top;
  rain   — only where it rains or snows now (H SAF), on a white map: where precipitation falls and how it moves.
For Uzbekistan, Kazakhstan, Kyrgyzstan, in Russian and Uzbek → out/{R}_{kind}_{lang}.mp4 and out/meta.json."""
import io, json, re, subprocess, sys, datetime as dt, pathlib, tempfile, concurrent.futures as cf
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
                 lc='белое — тучи (чем белее, тем выше) · цветное — осадки (оценка H SAF)', lr='голубое — слабые · синее — умеренные · фиолетовое — сильные осадки (оценка со спутника H SAF)'),
      'uz': dict(clouds='Sun’iy yo‘ldosh · bulut va yog‘in', rain='Sun’iy yo‘ldosh · yog‘in qayerda', at='surat {t}', tz={'UZ': 'Toshkent vaqti', 'KZ': 'Ostona vaqti', 'KG': 'Bishkek vaqti'},
                 lc='oq — bulut (qancha oq — shuncha baland) · rangli — yog‘in (H SAF)', lr='havorang — kuchsiz · ko‘k — o‘rtacha · binafsha — kuchli yog‘in (H SAF)')}
S = requests.Session()


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
    for R, V in VIEW.items():
        GA = json.load(open(HERE / 'geo_admin.json')).get(R, {})
        w = 1280; h = int(round(w * (V[3] - V[2]) / ((V[1] - V[0]) * np.cos(np.radians((V[2] + V[3]) / 2)))))
        with cf.ThreadPoolExecutor(8) as pool:  # all the pictures of the country at once
            irs = list(pool.map(lambda t: get('msg_iodc:ir108', t, 'image/jpeg', V, w, h), times))
            prs = list(pool.map(lambda t: get('msg_iodc:h63', min(t, endp), 'image/png', V, w // 3, h // 3), times))
        last = None; P = []
        for p in prs:  # a missing rain picture: the last one (no flicker); the 3–5 km blocks smoothed
            if p is not None: last = p.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(3))
            P.append(last)
        sea = [np.asarray(r) for r in WAT['ocean']] + [np.asarray(l['r']) for l in WAT['lakes']]
        for kind in ('clouds', 'rain'):
            for lang, X in TX.items():
                fd = pathlib.Path(tempfile.mkdtemp()); n = 0
                for t, ir, pr in zip(times, irs, P):
                    if ir is None and kind == 'clouds': continue
                    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(V[0], V[1]); ax.set_ylim(V[2], V[3]); ax.axis('off')
                    dark = kind == 'clouds'
                    if dark: ax.imshow(ImageEnhance.Contrast(ir.convert('RGB')).enhance(1.35), extent=(V[0], V[1], V[2], V[3]), aspect='auto')
                    else:
                        fig.patch.set_facecolor('#ffffff'); ax.add_collection(PCOL(sea, facecolors='#d6e8f2', edgecolors='#7fa9c6', linewidths=0.6))
                    if pr is not None: ax.imshow(pr if dark else rain_only(pr), extent=(V[0], V[1], V[2], V[3]), aspect='auto', alpha=0.9)
                    lc = '#ffffff' if dark else '#2b3a4e'
                    ax.add_collection(LC([np.asarray(r) for c in G.values() for r in c['rings']], colors=lc, linewidths=1.1, alpha=0.85))
                    if GA:
                        ax.add_collection(LC([np.asarray(r) for a in GA.get('adm2', []) for r in a['r']], colors=lc, linewidths=0.3, alpha=0.3))
                        ax.add_collection(LC([np.asarray(r) for a in GA['adm1'] for r in a['r']], colors=lc, linewidths=0.7, alpha=0.6))
                    for p in places:
                        if p.get('iso') == R and p.get('pop', 0) > (300000 if R == 'KZ' else 150000):
                            ax.plot(p['lon'], p['lat'], 'o', ms=4, color='#ffd27a' if dark else '#2b3a4e')
                            ax.text(p['lon'] + 0.1, p['lat'] + 0.07, p.get(lang) or p.get('ru', ''), color=lc, fontsize=11, fontweight='bold')
                    loc = t + dt.timedelta(hours=TZ[R])
                    fig.text(0.012, 0.955, f"{X[kind]} · {X['at'].format(t=loc.strftime('%H:%M'))} {X['tz'][R]}", fontsize=16, fontweight='bold', color='#ffffff',
                             bbox=dict(boxstyle='round,pad=0.4', fc='#1d2a3acc', ec='none'))
                    fig.text(0.012, 0.025, X['lc' if dark else 'lr'], fontsize=11, color='#ffffff', bbox=dict(boxstyle='round,pad=0.3', fc='#1d2a3aaa', ec='none'))
                    fig.savefig(fd / f'{n:03d}.png', facecolor=fig.get_facecolor()); plt.close(fig); n += 1
                mp4 = OUT / f'{R}_{kind}_{lang}.mp4'
                subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '3', '-i', str(fd / '%03d.png'), '-vf',
                                'tpad=stop_mode=clone:stop_duration=3,framerate=fps=24:interp_start=0:interp_end=255:scene=100,scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p',
                                '-c:v', 'libx264', '-crf', '21', '-movflags', '+faststart', str(mp4)], check=True)
                print(mp4.name, n, 'frames', mp4.stat().st_size // 1024, 'KB', flush=True)
    json.dump({'made': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'last': end.strftime('%Y-%m-%dT%H:%M:%SZ'), 'rain': endp.strftime('%Y-%m-%dT%H:%M:%SZ')},
              open(OUT / 'meta.json', 'w'))


if __name__ == '__main__':
    main()
