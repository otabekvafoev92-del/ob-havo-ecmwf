"""Video "the weather now": what the weather stations of Uzbekistan reported over the last 24 hours (SYNOP, every 3 hours, WMO data
through OGIMET), then the ECMWF forecast for the next 6 hours at the same places (hourly). For each language: out/obs_{lang}.mp4,
and out/obs.json (the last observation and the forecast of the main towns, for the bot).
NOAA ISD / GHCN stopped receiving the stations of Uzbekistan on 24 August 2025, so the reports are taken from the WMO exchange directly.
Usage: python tools/obs_video.py out ru,uz"""
import csv, io, json, re, sys, time, subprocess, tempfile, shutil, datetime as dt, pathlib
import numpy as np, requests
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection as LC, PolyCollection as PCOL
from matplotlib.colors import LinearSegmentedColormap
from matplotlib import font_manager as fm
from PIL import Image

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'obs'); OUT.mkdir(parents=True, exist_ok=True)
LANGS = (sys.argv[2] if len(sys.argv) > 2 else 'ru,uz').split(',')
HERE = pathlib.Path(__file__).resolve().parent.parent / 'prob'
V = (55.8, 73.4, 36.9, 45.8)  # Uzbekistan
W, H = 1920, 1080
if any('inter' in x.lower() for x in fm.findSystemFonts()): plt.rcParams['font.family'] = 'Inter'
S = requests.Session(); S.headers['User-Agent'] = 'Osmon weather bot (github.com/otabekvafoev92-del/ob-havo-ecmwf)'
TEMP = LinearSegmentedColormap.from_list('t', [(0, '#5b2a86'), (0.2, '#2f6fd0'), (0.4, '#7fb5e8'), (0.5, '#e8eef2'), (0.62, '#f6d36b'), (0.78, '#f08a24'), (1, '#c0262b')])
tcol = lambda t: TEMP(np.clip((t + 20) / 60, 0, 1))  # −20 … +40 °C
TX = {'ru': dict(fact='Факт · метеостанции', fc='Прогноз ECMWF', at='{t} по Ташкенту', plus='+{h} ч', src='Факт: сводки SYNOP метеостанций Узбекистана (ВМО) · прогноз: ECMWF IFS',
                 lg=[('дождь', '#2f7fd1'), ('снег', '#7b4fd0'), ('гроза', '#e0643a'), ('туман, дымка', '#8a96a3'), ('пыль', '#b7791f')], wind='ветер, м/с', now='Сейчас', in6='Через 6 ч',
                 ww='сводка {t}'),
      'uz': dict(fact='Fakt · meteostansiyalar', fc='ECMWF prognozi', at='Toshkent vaqti {t}', plus='+{h} soat', src='Fakt: O‘zbekiston meteostansiyalari SYNOP xabarlari (JMT) · prognoz: ECMWF IFS',
                 lg=[('yomg‘ir', '#2f7fd1'), ('qor', '#7b4fd0'), ('momaqaldiroq', '#e0643a'), ('tuman', '#8a96a3'), ('chang', '#b7791f')], wind='shamol, m/s', now='Hozir', in6='6 soatdan keyin',
                 ww='{t} xabari')}
MAIN = ['TASHKENT', 'SAMARKAND', 'BUKHARA', 'NUKUS', 'URGENCH', 'NAMANGAN', 'ANDIZHAN', 'FERGANA', 'KARSHI', 'TERMEZ', 'NAVOI', 'DZIZAK']


def stations():
    """The stations of Uzbekistan (NOAA's list: WMO number, place) with a name in Russian / Uzbek from our places nearby."""
    t = S.get('https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv', timeout=120).text
    pl = json.load(open(HERE / 'geo_prob.json'))['places']; out = {}
    for r in csv.DictReader(io.StringIO(t)):
        if r['CTRY'] != 'UZ' or not r['LAT'] or r['USAF'][:2] != '38': continue
        wmo = r['USAF'][:5]; la, lo = float(r['LAT']), float(r['LON'])
        if wmo in out: continue
        near = min(pl, key=lambda p: (p['lat'] - la) ** 2 + ((p['lon'] - lo) * 0.76) ** 2)
        close = ((near['lat'] - la) ** 2 + ((near['lon'] - lo) * 0.76) ** 2) ** 0.5 < 0.25
        nm = r['STATION NAME'].split('/')[0].split(' AIRPORT')[0].strip().title()
        out[wmo] = dict(wmo=wmo, lat=la, lon=lo, en=r['STATION NAME'], ru=near.get('ru') if close else nm, uz=near.get('uz') if close else nm,
                        main=any(m in r['STATION NAME'] for m in MAIN), icao=r['ICAO'])
    return out


def synops(hours=27):
    """The SYNOP reports of WMO block 38 for the last hours (OGIMET)."""
    end = dt.datetime.utcnow(); beg = end - dt.timedelta(hours=hours)
    for k in range(4):
        try:
            r = S.get('https://www.ogimet.com/cgi-bin/getsynop', params=dict(block='38', begin=beg.strftime('%Y%m%d%H00'), end=end.strftime('%Y%m%d%H59')), timeout=120)
            if r.ok and 'AAXX' in r.text: return r.text
            print('ogimet', r.status_code, r.text[:200], flush=True)
        except requests.RequestException as e: print('ogimet', e, flush=True)
        time.sleep(30 * (k + 1))
    raise RuntimeError('no SYNOP reports')


def decode(rep):
    """The main groups of a SYNOP report (section 1 and the precipitation of section 3)."""
    g = rep.replace('=', ' ').split()
    if len(g) < 5 or g[0] != 'AAXX': return None
    iw = g[1][-1]; s1 = []; s3 = []; cur = s1
    for x in g[3:]:
        if x in ('333', '555', '222', '444'): cur = s3 if x == '333' else []; continue
        if x.startswith('222') and len(x) == 5: cur = []; continue
        cur.append(x)
    if len(s1) < 2: return None
    o = {}
    ir = s1[0][0]
    n, dd, ff = s1[1][0], s1[1][1:3], s1[1][3:5]
    o['n'] = int(n) if n.isdigit() and n != '9' else None
    if dd.isdigit() and ff.isdigit():
        f = int(ff); f = f * 0.514 if iw in '34' else f; o['wd'] = int(dd) * 10; o['ws'] = round(f, 1)
    for x in s1[2:]:
        if len(x) != 5 or '/' in x[:2]: continue
        k = x[0]
        try:
            if k in '12' and x[1] in '01' and x[2:].isdigit(): v = int(x[2:]) / 10 * (-1 if x[1] == '1' else 1); o['t' if k == '1' else 'td'] = v
            elif k == '6' and x[1:4].isdigit(): o['rr'] = (0.0 if int(x[1:4]) == 990 else (int(x[1:4]) - 990) / 10) if int(x[1:4]) >= 990 else float(int(x[1:4])); o['rt'] = x[4]
            elif k == '7' and x[1:3].isdigit(): o['ww'] = int(x[1:3])
            elif k == '4' and x[1:].isdigit(): v = int(x[1:]) / 10; o['p'] = v + 1000 if v < 100 else v
        except ValueError: pass
    if ir == '3': o.setdefault('rr', 0.0)
    for x in s3:
        if len(x) == 5 and x[0] == '6' and x[1:4].isdigit() and 'rr' not in o: v = int(x[1:4]); o['rr'] = (0.0 if v == 990 else (v - 990) / 10) if v >= 990 else float(v); o['rt'] = x[4]
    return o


def wx(ww):  # the kind of weather from the present weather code
    if ww is None: return None
    if 95 <= ww <= 99 or ww in (17, 29): return 4  # thunder
    if 70 <= ww <= 79 or 83 <= ww <= 88 or ww in (22, 23, 26): return 1  # snow
    if 50 <= ww <= 69 or 80 <= ww <= 82 or ww in (20, 21, 24, 25): return 0  # rain, drizzle
    if 40 <= ww <= 49 or ww in (10, 11, 12, 4, 5): return 3  # fog, mist, haze
    if 6 <= ww <= 9 or 30 <= ww <= 35: return 5  # dust, sand
    return None


def wmo_kind(c):  # the same from the forecast's weather code (WMO 4677 in Open-Meteo: 0–99)
    if c is None: return None
    if c >= 95: return 4
    if c in (71, 73, 75, 77, 85, 86): return 1
    if c in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82): return 0
    if c in (45, 48): return 3
    return None


def forecast(st):
    """ECMWF hourly at the stations for the next 7 hours."""
    L = list(st.values()); out = {}
    for k in range(0, len(L), 50):
        part = L[k:k + 50]
        q = dict(latitude=','.join(str(s['lat']) for s in part), longitude=','.join(str(s['lon']) for s in part), hourly='temperature_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m,cloud_cover',
                 wind_speed_unit='ms', forecast_hours=8, timezone='UTC', models='ecmwf_ifs025')
        for n in range(4):
            try:
                r = S.get('https://api.open-meteo.com/v1/forecast', params=q, timeout=120)
                if r.ok: j = r.json(); j = j if isinstance(j, list) else [j]; break
            except requests.RequestException as e: print('forecast', e, flush=True)
            time.sleep(20 * (n + 1))
        else: raise RuntimeError('no forecast')
        for s, f in zip(part, j): out[s['wmo']] = f['hourly']
    return out


KC = ['#2f7fd1', '#7b4fd0', None, '#8a96a3', '#e0643a', '#b7791f']  # rain, snow, —, fog, thunder, dust
KI = {0: 0, 1: 1, 3: 3, 4: 4, 5: 5}


def main():
    st = stations(); print(len(st), 'stations', flush=True)
    obs = {}  # time → {wmo: decoded}
    for line in synops().splitlines():
        p = line.split(',', 6)
        if len(p) < 7 or p[0] not in st: continue
        t = dt.datetime(int(p[1]), int(p[2]), int(p[3]), int(p[4]), int(p[5]))
        o = decode(p[6])
        if o and 't' in o: obs.setdefault(t, {})[p[0]] = o
    times = sorted(t for t in obs if len(obs[t]) >= 8 and t.hour % 3 == 0)[-9:]  # the last 24 hours, the main 3-hourly terms
    if not times: raise RuntimeError('no observations')
    last = times[-1]; print('obs', [f"{t:%d %H}z:{len(obs[t])}" for t in times], flush=True)
    F = forecast(st); fts = [last + dt.timedelta(hours=h) for h in range(1, 7)]
    def fc_at(w, t):
        h = F.get(w)
        if not h: return None
        k = f"{t:%Y-%m-%dT%H:%M}"
        if k not in h['time']: return None
        i = h['time'].index(k)
        return dict(t=h['temperature_2m'][i], wd=h['wind_direction_10m'][i], ws=h['wind_speed_10m'][i], k=wmo_kind(h['weather_code'][i]), n=(h['cloud_cover'][i] or 0) / 12.5)
    frames = [(t, {w: dict(t=o['t'], wd=o.get('wd'), ws=o.get('ws'), k=wx(o.get('ww')), n=o.get('n')) for w, o in obs[t].items()}, False) for t in times]
    frames += [(t, {w: v for w in st if (v := fc_at(w, t))}, True) for t in fts]
    # the map
    G = json.load(open(HERE / 'geo_world.json'))['countries']; GA = json.load(open(HERE / 'geo_admin.json')).get('UZ', {}); WAT = json.load(open(HERE / 'geo_water.json'))
    sea = [np.asarray(r) for r in WAT['ocean']] + [np.asarray(l['r']) for l in WAT['lakes']]
    rel = None
    try:
        site = 'https://otabekvafoev92-del.github.io/ob-havo-ecmwf/prob/hr/live/UZ'; m = S.get(site + '/meta.json', timeout=60).json()
        rel = (Image.open(io.BytesIO(S.get(site + '/relief.png', timeout=60).content)).convert('RGBA'), m['bounds'])
    except Exception as e: print('relief', e, flush=True)
    summary = {'made': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'), 'obs_time': last.strftime('%Y-%m-%dT%H:%MZ'), 'towns': []}
    for w, s in st.items():
        if s['main'] and w in obs[last]:
            f6 = fc_at(w, fts[-1]); o = obs[last][w]
            summary['towns'].append(dict(wmo=w, ru=s['ru'], uz=s['uz'], t=o['t'], ww=o.get('ww'), ws=o.get('ws'), t6=f6['t'] if f6 else None, k6=f6['k'] if f6 else None))
    json.dump(summary, open(OUT / 'obs.json', 'w'), ensure_ascii=False)
    for lang in LANGS:
        X = TX[lang]; fd = pathlib.Path(tempfile.mkdtemp())
        for n_, (t, D, fut) in enumerate(frames):
            fig = plt.figure(figsize=(W / 100, H / 100), dpi=100); fig.patch.set_facecolor('#ffffff')
            ax = fig.add_axes([0, 0, 0.74, 1]); ax.set_xlim(V[0], V[1]); ax.set_ylim(V[2], V[3]); ax.axis('off'); ax.set_facecolor('#eef1e6')
            ax.add_patch(plt.Rectangle((V[0], V[2]), V[1] - V[0], V[3] - V[2], color='#eef1e6', zorder=0))
            if rel: ax.imshow(rel[0], extent=tuple(rel[1]), aspect='auto', zorder=0.2, alpha=0.9)
            ax.add_collection(PCOL(sea, facecolors='#cfe3f0', edgecolors='#8fb4cf', linewidths=0.6, zorder=0.3))
            ax.add_collection(LC([np.asarray(r) for c in G.values() for r in c['rings']], colors='#3d4a5c', linewidths=1.3, zorder=1))
            if GA:
                ax.add_collection(LC([np.asarray(r) for a in GA['adm1'] for r in a['r']], colors='#ffffff', linewidths=2.4, alpha=0.6, zorder=1))
                ax.add_collection(LC([np.asarray(r) for a in GA['adm1'] for r in a['r']], colors='#5b6b80', linewidths=0.9, alpha=0.8, zorder=1.1))
            for w, v in sorted(D.items(), key=lambda kv: st[kv[0]]['main']):
                s = st[w]; x, y = s['lon'], s['lat']
                if not (V[0] < x < V[1] and V[2] < y < V[3]) or v.get('t') is None: continue
                k = v.get('k'); big = s['main']
                if k is not None and KC[KI[k]]: ax.scatter(x, y, s=(1500 if big else 900), facecolors='none', edgecolors=KC[KI[k]], linewidths=4, alpha=0.9, zorder=3)
                ax.scatter(x, y, s=(900 if big else 520), c=[tcol(v['t'])], edgecolors='#ffffff', linewidths=1.6, zorder=4)
                ax.text(x, y, f"{v['t']:+.0f}".replace('+0', '0').replace('-0', '0') if abs(v['t']) < 0.5 else f"{v['t']:+.0f}", ha='center', va='center', fontsize=(13 if big else 10), fontweight='bold', color='#1f2d3d' if -8 < v['t'] < 30 else '#ffffff', zorder=5)
                if v.get('ws') and v['ws'] >= 2 and v.get('wd') is not None:
                    a = np.radians(v['wd']); L_ = 0.12 + min(0.5, v['ws'] / 25); dx, dy = -np.sin(a) * L_ / 0.76, -np.cos(a) * L_
                    ax.annotate('', xy=(x + dx * 1.9, y + dy * 1.9), xytext=(x + dx * 0.75, y + dy * 0.75), arrowprops=dict(arrowstyle='-|>', color='#1f2d3d', lw=1.6, mutation_scale=12), zorder=4.5)
                if big: ax.text(x, y - 0.32, s[lang], ha='center', va='top', fontsize=11, color='#1f2d3d', fontweight='bold', zorder=5,
                                bbox=dict(boxstyle='round,pad=0.15', fc='#ffffffcc', ec='none'))
            loc = t + dt.timedelta(hours=5)
            col = '#c0562b' if fut else '#1f2d3d'
            fig.text(0.012, 0.955, f"{X['fc'] if fut else X['fact']} · {X['at'].format(t=loc.strftime('%d.%m %H:%M'))}" + (f" · {X['plus'].format(h=int((t - last).total_seconds() // 3600))}" if fut else ''),
                     fontsize=22, fontweight='bold', color='#ffffff', bbox=dict(boxstyle='round,pad=0.45', fc=col, ec='none'))
            # the side panel: the main towns, now and in 6 hours
            px = fig.add_axes([0.745, 0, 0.255, 1]); px.axis('off'); px.set_xlim(0, 1); px.set_ylim(0, 1)
            px.add_patch(plt.Rectangle((0, 0), 1, 1, color='#f5f7f9')); px.text(0.06, 0.95, X['now'], fontsize=15, fontweight='bold', color='#1f2d3d'); px.text(0.66, 0.95, X['in6'], fontsize=13, fontweight='bold', color='#c0562b')
            for i, tw in enumerate(sorted(summary['towns'], key=lambda z: MAIN.index(next((m for m in MAIN if m in st[z['wmo']]['en']), MAIN[-1])))[:12]):
                y = 0.88 - i * 0.068; px.text(0.06, y, tw[lang], fontsize=13, color='#1f2d3d', va='center')
                px.text(0.56, y, f"{tw['t']:+.0f}°", fontsize=15, fontweight='bold', color='#1f2d3d', va='center', ha='right')
                if tw['t6'] is not None: px.text(0.9, y, f"{tw['t6']:+.0f}°", fontsize=15, fontweight='bold', color='#c0562b', va='center', ha='right')
            for i, (nm, c) in enumerate(X['lg']):
                y = 0.115 - (i % 3) * 0.035; xx = 0.06 + (i // 3) * 0.48
                px.scatter(xx + 0.02, y, s=110, facecolors='none', edgecolors=c, linewidths=3); px.text(xx + 0.06, y, nm, fontsize=10.5, color='#1f2d3d', va='center')
            fig.text(0.012, 0.012, X['src'], fontsize=10, color='#6b7a8c')
            fig.savefig(fd / f'{n_:03d}.png', facecolor='#ffffff'); plt.close(fig)
        mp4 = OUT / f'obs_{lang}.mp4'; tmp = OUT / f'.obs_{lang}.part.mp4'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', '1.2', '-i', str(fd / '%03d.png'), '-vf',
                        'tpad=stop_mode=clone:stop_duration=1.5,framerate=fps=30:interp_start=0:interp_end=255:scene=100,scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p',
                        '-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast', '-movflags', '+faststart', str(tmp)], check=True)
        tmp.replace(mp4); shutil.rmtree(fd); print(mp4, mp4.stat().st_size // 1024, 'KB', flush=True)


if __name__ == '__main__':
    main()
