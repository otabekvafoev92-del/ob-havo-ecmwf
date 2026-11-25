"""The chance of precipitation over Uzbekistan for the next ~15 days, by 6-hour windows, from all the models (ECMWF IFS and
AIFS, NOAA GFS and GEFS, DWD ICON; prob/fetch.py → prob.npz), drawn in the Osmon video style (tools/ecmwf_video.py):
white map with relief, dotted borders, the chance in each main town, under the map the chance in Tashkent window by window.
Usage: python tools/prob_video.py prob.npz out ru,uz   →  out/prob_{lang}.mp4  (the frame format: EV_FORMAT)"""
import sys, json, pathlib, tempfile, datetime as dt, multiprocessing as mp, os
import numpy as np
from scipy.ndimage import zoom

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'prob')); sys.path.insert(0, str(ROOT / 'tools'))
sys.argv, _args = sys.argv[:1] + ['/tmp/_ev_unused'], sys.argv  # ecmwf_video reads its own argv when imported
import ecmwf_video as EV
from render import load, probability
sys.argv = _args

NPZ = sys.argv[1]; OUT = pathlib.Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True); LANGS = (sys.argv[3] if len(sys.argv) > 3 else 'ru,uz').split(',')
TXT = {'ru': dict(title='Вероятность осадков · 15 дней', chart='Ташкент: вероятность осадков по 6-часовым периодам', badge='{d} · {h1}–{h2}',
                  line='Модели: {m}', src='Модели: ECMWF IFS и AIFS, NOAA GFS и GEFS, DWD ICON · равный вес каждой системы · Osmon'),
       'uz': dict(title='Yog‘ingarchilik ehtimoli · 15 kun', chart='Toshkent: 6 soatlik davrlar bo‘yicha yog‘in ehtimoli', badge='{d} · {h1}–{h2}',
                  line='Modellar: {m}', src='Modellar: ECMWF IFS va AIFS, NOAA GFS va GEFS, DWD ICON · har bir tizim teng vaznda · Osmon')}


def main():
    D = load(NPZ); P, models, members = probability(D)
    g = D['grid'].item() if hasattr(D['grid'], 'item') else D['grid']
    lon = g['lon0'] + np.arange(g['W']) * g['d']; lat = g['lat0'] - np.arange(g['H']) * g['d']
    ci = np.flatnonzero((lon >= EV.DOM[0]) & (lon <= EV.DOM[1])); ri = np.flatnonzero((lat >= EV.DOM[2]) & (lat <= EV.DOM[3]))
    LON, LAT = lon[ci], lat[ri][::-1]  # south to north
    cut = lambda a: a[np.ix_(ri, ci)][::-1].astype(np.float32)
    UP = 4; up = lambda a: np.clip(zoom(a, UP, order=1), 0, 100).astype(np.float32)
    hu, wu = up(np.zeros((len(LAT), len(LON)))).shape
    LATu, LONu = np.linspace(LAT[0], LAT[-1], hu), np.linspace(LON[0], LON[-1], wu)
    atu = lambda a, la, lo: float(a[np.abs(LATu - la).argmin(), np.abs(LONu - lo).argmin()])
    run = dt.datetime.fromisoformat(D['run'].replace('Z', '')[:19]); steps = [int(x) for x in D['steps']]; win = [int(x) for x in D['win']]
    keys = [up(cut(P[s])) for s in range(len(steps))]
    print('run', run, len(steps), 'windows, models', models, flush=True)
    # geography, as the forecast videos
    G = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']; GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']
    WAT = json.load(open(ROOT / 'prob' / 'geo_water.json')); sea = [np.asarray(r) for r in WAT['ocean']] + [np.asarray(l['r']) for l in WAT['lakes']]
    UZR = [np.asarray(r) for r in G['UZ']['rings']]; NB = [np.asarray(r) for k, c in G.items() if k != 'UZ' for r in c['rings']]
    ADM1 = [np.asarray(r) for a in GA['adm1'] for r in a['r']]
    E0 = EV.fit_ext(55.9, 73.25, 37.15, 45.6, 0.02)
    rel = {'uz': EV.relief(E0, UZR)}; relE = {'uz': E0}
    borders = [(NB, '#68717d', 1.8, EV.DOT, 0.9, 3), (ADM1, '#7c8794', 1.3, EV.DOT, 0.8, 3.1), (UZR, '#1f2d3d', 3.0, EV.DOT, 1.0, 3.3)]
    TASH = EV.TOWNS[0]
    loc = lambda s: run + dt.timedelta(hours=steps[s] + 5)
    lab, seen = [], set()  # one date per local day, every second day, so the labels do not overlap
    for s in range(len(steps)):
        d_ = loc(s).date(); lab.append(loc(s).strftime('%d.%m') if d_ not in seen and len(seen) % 2 == 0 and loc(s).hour <= 6 else ''); seen.add(d_)
    every = 1
    chart = dict(kind='prob', pct=[round(atu(k, TASH[2], TASH[3])) for k in keys], mx=[0] * len(keys), snow=[False] * len(keys), lab=lab, every=every)
    # fields: N in-between frames per window, blended
    fields, seq, N = [], [], 3
    for s in range(len(keys)):
        nxt = keys[min(s + 1, len(keys) - 1)]
        for k in range(N):
            a = k / N; fields.append(dict(P=(1 - a) * keys[s] + a * nxt)); seq.append((s, len(fields) - 1))
    videos = {}
    for lang in LANGS:
        X = TXT[lang]; L = 0 if lang == 'ru' else 1; frames = []
        for s, kk in seq:
            t2 = loc(s); t1 = t2 - dt.timedelta(hours=win[s])
            pts = []
            for tw in EV.TOWNS[:12]:
                v = atu(fields[kk]['P'], tw[2], tw[3]); col = EV.PROB[int(np.clip(np.searchsorted(EV.PROB_LV, v, side='right') - 1, 0, 4))] if v >= 10 else '#ffffff'
                pts.append((tw[3], tw[2], f'{v:.0f}%', col, None, tw[L], True))
            frames.append(dict(mode='prob', t=t2, k=kk, d=0.18 / N, ci=s, pts=pts, bc='#1f5fb3',
                               badge=X['badge'].format(d=t1.strftime('%d.%m'), h1=t1.strftime('%H:%M'), h2=t2.strftime('%H:%M') if t2.hour else '24:00'),
                               when=EV.TX[lang]['wd'][t1.weekday()] + ' · ' + ('по Ташкенту' if lang == 'ru' else 'Toshkent vaqti')))
        frames[-1]['d'] = 1.0
        intro = [dict(frames[0], intro=float(a_), d=0.08) for a_ in np.linspace(1, 0, 10)]; intro[0]['d'] = 0.6
        videos[f'prob_{lang}'] = dict(lang=lang, kind='prob', ext=E0, rel='uz', borders=borders, borders_c=borders, wind=False, frames=intro + frames,
                                      title=X['title'], line=X['line'].format(m=str(len(models)) + (' систем' if lang == 'ru' else ' tizim')), chart='tash', chart_t=X['chart'], src=X['src'],
                                      dir=tempfile.mkdtemp(), out=str(OUT / f'prob_{lang}.mp4'))
    EV.CTX.update(videos=videos, fields=fields, rel=rel, relE=relE, charts={'tash': chart}, acc={}, t2end={}, sea=sea, LATu=LATu, LONu=LONu,
                  ext=(LON[0] - 0.125, LON[-1] + 0.125, LAT[0] - 0.125, LAT[-1] + 0.125))
    jobs = [(vk, i) for vk, v in videos.items() for i in range(len(v['frames']))]
    print(len(jobs), 'frames', flush=True)
    with mp.get_context('fork').Pool(max(1, os.cpu_count() or 1)) as pool:
        for n_, _ in enumerate(pool.imap_unordered(EV.render, jobs, chunksize=4)):
            if n_ % 200 == 0: print('frames', n_, '/', len(jobs), flush=True)
        for r in pool.imap_unordered(EV.encode, list(videos)): print(r, flush=True)


if __name__ == '__main__':
    main()
