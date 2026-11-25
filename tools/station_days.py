"""What the weather stations of Uzbekistan reported, day by day (local days, Tashkent UTC+5): yesterday and today so far.
For each station: the warmest and coldest term, precipitation (the 12-hour amounts reported at 08:00 and 20:00), fog and the
worst visibility, rain, snow, thunder, dust, the strongest wind; and what that weather meant for going out and shopping
(impact: 0 good, 1 so-so, 2 bad, with the reasons). Stations are grouped by region for the bot.
Usage: python tools/station_days.py out/  →  out/stations_days.json"""
import sys, json, math, pathlib, datetime as dt
import numpy as np
from matplotlib.path import Path as MPath

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import obs_video as OV

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'obs'); OUT.mkdir(parents=True, exist_ok=True)
LOC = dt.timedelta(hours=5)
NAMES = {'Jaslyk': ('Жаслык', 'Jasliq'), 'Karakapalkija': ('Каракалпакия', 'Qoraqalpog‘iston'), 'Ak-Bajtal': ('Акбайтал', 'Oqboytal'), 'Buzaubaj': ('Бузаубай', 'Buzaubay'),
         'Mashikuduk': ('Машикудук', 'Mashikuduq'), 'Nurata': ('Нурата', 'Nurota'), 'Tamdy-Bulak': ('Тамдыбулак', 'Tomdibuloq'), 'Olgaing': ('Ойгаинг', 'Oygaing'), 'Pskem': ('Пскем', 'Piskom'),
         'Gurlen': ('Гурлен', 'Gurlan'), 'Ayakagitma': ('Аякагитма', 'Ayoqog‘itma'), 'Dzangeldy': ('Джангельды', 'Jongeldi'), 'Karakul': ('Каракуль', 'Qorako‘l'), 'Bahmal': ('Бахмал', 'Baxmal'),
         'Zapadny Arnasay': ('Западный Арнасай', 'G‘arbiy Arnasoy'), "Syr-Dar'Ja": ('Сырдарья', 'Sirdaryo'), 'Akrabat': ('Акрабат', 'Akrabot'), 'Guzar': ('Гузар', 'G‘uzor'),
         'Minchukur': ('Минчукур', 'Minchuqur'), 'Baysun': ('Байсун', 'Boysun'), 'Shirabad': ('Шерабад', 'Sherobod'), 'Shurchi': ('Шурчи', 'Sho‘rchi'), 'Каган': ('Каган (Бухара)', 'Kogon (Buxoro)')}
VV = lambda c: (c / 10 if c <= 50 else c - 50 if 56 <= c <= 80 else 30 + (c - 80) * 5 if 81 <= c <= 89 else {90: 0.05, 91: 0.05, 92: 0.2, 93: 0.5, 94: 1, 95: 2, 96: 4, 97: 10, 98: 20, 99: 50}.get(c))
KIND = {0: 'rain', 1: 'snow', 3: 'fog', 4: 'thunder', 5: 'dust'}


def impact(d):
    """0 good, 1 so-so, 2 bad for going out and shopping, with the reasons (keys the bot translates)."""
    bad, soso = [], []
    fogm = [h for h in d['fog_hours'] if 6 <= h <= 11]
    if d['vis_min'] is not None and d['vis_min'] < 1 and fogm: bad.append('fog_morning')
    elif d['fog_hours']: soso.append('fog')
    if d['snow']: bad.append('snow')
    if (d['pr'] or 0) >= 5: bad.append('rain_heavy')
    elif (d['pr'] or 0) >= 0.5 or d['rain']: soso.append('rain')
    if d['thunder']: soso.append('thunder')
    if d['dust']: (bad if (d['vis_min'] or 10) < 2 else soso).append('dust')
    if d['t_max'] is not None:
        if d['t_max'] <= 0: bad.append('frost')
        elif d['t_max'] <= 5: soso.append('cold')
        if d['t_max'] >= 40: bad.append('heat')
        elif d['t_max'] >= 35: soso.append('hot')
    if (d['wind_max'] or 0) >= 15: bad.append('storm')
    elif (d['wind_max'] or 0) >= 10: soso.append('wind')
    return (2 if bad else 1 if soso else 0), bad + soso


def main():
    st = OV.stations(); now = dt.datetime.utcnow()
    today = (now + LOC).date(); days = [today - dt.timedelta(days=1), today]
    txt = OV.synops(hours=int((now + LOC - dt.datetime.combine(days[0], dt.time())).total_seconds() // 3600) + 4)
    rep = {}
    for line in txt.splitlines():
        p = line.split(',', 6)
        if len(p) < 7 or p[0] not in st: continue
        t = dt.datetime(int(p[1]), int(p[2]), int(p[3]), int(p[4]), int(p[5])); o = OV.decode(p[6]) or {}
        g = p[6].replace('=', ' ').split(); o['vis'] = VV(int(g[3][3:])) if len(g) > 3 and len(g[3]) == 5 and g[3][3:].isdigit() else None
        rep[(p[0], t)] = o
    GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']['adm1']
    regof = lambda s: next((a['id'] for a in GA if any(MPath(np.asarray(r)).contains_point((s['lon'], s['lat'])) for r in a['r'])), None)
    out = {}
    for w, s in st.items():
        dd = {}
        for day in days:
            lo = dt.datetime.combine(day, dt.time()) - LOC; hi = lo + dt.timedelta(days=1)
            ts = sorted((t, o) for (k, t), o in rep.items() if k == w and lo < t <= hi)
            if not ts: continue
            T = [o['t'] for _, o in ts if o.get('t') is not None]
            kinds = [OV.wx(o.get('ww')) for _, o in ts]
            pr = [o['rr'] for _, o in ts if o.get('rr') is not None and o.get('rt') == '2']  # the 12-hour amounts: 08:00 and 20:00 local
            fog = [(t + LOC).hour for (t, o), k in zip(ts, kinds) if k == 3 and (o.get('ww') or 0) >= 40 or (o.get('vis') is not None and o['vis'] < 1)]
            d = dict(terms=len(ts), last=(ts[-1][0] + LOC).strftime('%H:%M'), t_max=max(T) if T else None, t_min=min(T) if T else None,
                     pr=round(sum(pr), 1) if pr else (0.0 if any(o.get('rr') == 0 for _, o in ts) else None),
                     rain=any(k in (0, 4) for k in kinds), snow=any(k == 1 for k in kinds), thunder=any(k == 4 for k in kinds), dust=any(k == 5 for k in kinds),
                     fog_hours=sorted(set(fog)), vis_min=min([o['vis'] for _, o in ts if o.get('vis') is not None], default=None),
                     wind_max=max([o['ws'] for _, o in ts if o.get('ws') is not None], default=None),
                     clouds=round(sum(o['n'] for _, o in ts if o.get('n') is not None) / max(1, sum(1 for _, o in ts if o.get('n') is not None)), 1))
            d['impact'], d['why'] = impact(d)
            dd[day.isoformat()] = d
        ru, uz = NAMES.get(s['ru'], (s['ru'], s['uz']))
        if dd: out[w] = dict(ru=ru, uz=uz, lat=s['lat'], lon=s['lon'], main=s['main'], region=regof(s), days=dd)
    regions = {}
    for w, s in out.items():
        if s['region'] is not None: regions.setdefault(str(s['region']), []).append(w)
    if '38457' in out: regions['13'] = ['38457']  # Tashkent city: its airport station
    for k in regions: regions[k].sort(key=lambda w: (not out[w]['main'], out[w]['ru']))
    json.dump(dict(made=now.strftime('%Y-%m-%dT%H:%MZ'), days=[d.isoformat() for d in days], stations=out, regions=regions,
                   source='WMO SYNOP of the stations of Uzbekistan (OGIMET), every 3 hours'), open(OUT / 'stations_days.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    print('stations', len(out), 'regions', {k: len(v) for k, v in regions.items()})


if __name__ == '__main__':
    main()
