"""A sample of the «🛰 Online» view as a video: the last 3 hours of Meteosat IODC infrared (EUMETSAT WMS)
with the H SAF rain estimate and the borders, for one country. Used to show what the mini app shows."""
import io, json, re, subprocess, sys, datetime as dt, pathlib, tempfile
import numpy as np, requests
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection as LC
from PIL import Image
HERE = pathlib.Path(__file__).resolve().parent.parent / 'prob'
reg, out = sys.argv[1], sys.argv[2]
V = {'UZ': (55, 74, 36.5, 46), 'KZ': (46, 88, 40, 56), 'KG': (68, 81, 38.5, 44)}[reg]
W = 'https://view.eumetsat.int/geoserver'
def latest(layer):
    t = requests.get(f"{W}/{layer.replace(':', '/')}/wms", params=dict(service='WMS', request='GetCapabilities', version='1.3.0'), timeout=60).text
    return dt.datetime.fromisoformat(re.search(r'<Dimension[^>]*name="time"[^>]*default="([^"]+)"', t).group(1).replace('Z', '+00:00'))
def get(layer, t, fmt, w=1280, h=720):
    for _ in range(3):
        try: return get1(layer, t, fmt, w, h)
        except Exception as e: print('retry', layer, t, e, flush=True)
    return None
def get1(layer, t, fmt, w, h):
    r = requests.get(f'{W}/wms', params=dict(service='WMS', version='1.3.0', request='GetMap', layers=layer, styles='', crs='EPSG:4326', bbox=f'{V[2]},{V[0]},{V[3]},{V[1]}',
                                             width=w, height=h, format=fmt, transparent='true', time=t.strftime('%Y-%m-%dT%H:%M:%SZ')), timeout=150)
    return Image.open(io.BytesIO(r.content)).convert('RGBA') if r.ok and r.headers.get('content-type', '').startswith('image') else None
end, endp = latest('msg_iodc:ir108'), latest('msg_iodc:h63'); print('latest', end, endp, 'now', dt.datetime.utcnow())
G = json.load(open(HERE / 'geo_world.json'))['countries']; GA = json.load(open(HERE / 'geo_admin.json')).get(reg, {})
fd = pathlib.Path(tempfile.mkdtemp()); n = 0
for k in range(12, -1, -1):
    t = end - dt.timedelta(minutes=15 * k); ir = get('msg_iodc:ir108', t, 'image/jpeg'); pr = get('msg_iodc:h63', min(t, endp), 'image/png')
    if ir is None: continue
    fig = plt.figure(figsize=(16, 9), dpi=120); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(V[0], V[1]); ax.set_ylim(V[2], V[3]); ax.axis('off')
    ax.imshow(ir, extent=(V[0], V[1], V[2], V[3]), aspect='auto')
    if pr is not None: ax.imshow(pr, extent=(V[0], V[1], V[2], V[3]), aspect='auto', alpha=0.9)
    ax.add_collection(LC([np.asarray(r) for c in G.values() for r in c['rings']], colors='#ffffff', linewidths=1.0, alpha=0.85))
    if GA:
        ax.add_collection(LC([np.asarray(r) for a in GA.get('adm2', []) for r in a['r']], colors='#ffffff', linewidths=0.3, alpha=0.35))
        ax.add_collection(LC([np.asarray(r) for a in GA['adm1'] for r in a['r']], colors='#ffffff', linewidths=0.7, alpha=0.6))
    for p in json.load(open(HERE / 'geo_prob.json'))['places']:
        if p.get('iso') == reg and p.get('pop', 0) > 150000:
            ax.plot(p['lon'], p['lat'], 'o', ms=4, color='#ffd27a'); ax.text(p['lon'] + 0.12, p['lat'] + 0.08, p.get('ru', ''), color='#ffffff', fontsize=11, fontweight='bold')
    loc = t + dt.timedelta(hours=5); ago = int((dt.datetime.now(dt.timezone.utc) - t).total_seconds() // 60)
    fig.text(0.015, 0.95, f'🛰 Онлайн · Meteosat (EUMETSAT) · {loc:%H:%M} по Ташкенту · {ago} мин назад', fontsize=18, fontweight='bold', color='#ffffff',
             bbox=dict(boxstyle='round,pad=0.4', fc='#1d2a3acc', ec='none'))
    fig.text(0.015, 0.03, 'белое — тучи (чем белее, тем выше) · цветное — осадки по оценке со спутника (H SAF)', fontsize=12, color='#ffffff', bbox=dict(boxstyle='round,pad=0.3', fc='#1d2a3aaa', ec='none'))
    fig.savefig(fd / f'{n:03d}.png'); plt.close(fig); n += 1
print('frames', n)
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '2', '-i', str(fd / '%03d.png'), '-vf', 'framerate=fps=12:interp_start=0:interp_end=255:scene=100,format=yuv420p', '-c:v', 'libx264', '-crf', '22', out], check=True)
