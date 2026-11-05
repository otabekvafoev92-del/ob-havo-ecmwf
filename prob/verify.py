"""Forecast accuracy check: every day the forecast for tomorrow (made 24–48 h ahead) is saved for the main cities,
and once the day is over it is compared with what happened (Open-Meteo: daily precipitation total and mean
temperature from the latest analysis and short-range data).
  out/verify/history.json   {"fc": {date: {city: [rain %, t mean]}}, "obs": {date: {city: [mm, t mean]}}}
  out/verify/index.json     30-day scores: overall, per city, per day
Usage: python3 prob/verify.py glob.npz wx.npz out [previous history.json]"""
import datetime as dt, json, pathlib, sys, time
import numpy as np, requests

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render as Rn
from regions import UZ_CITY

CITIES = ['Tashkent', 'Samarkand', 'Bukhara', 'Namangan', 'Andijan', 'Fergana', 'Qarshi', 'Nukus', 'Urgench', 'Termez', 'Jizzakh', 'Navoiy', 'Guliston', 'Kokand',
          'Almaty', 'Astana', 'Bishkek', 'Dushanbe', 'Ashgabat', 'Baku', 'Yerevan', 'Minsk', 'Chisinau', 'Moscow', 'Istanbul', 'Ankara']
RAIN_P, RAIN_MM, KEEP = 50, 1.0, 90


def places():
    out = {}
    for f in ('geo_prob.json', 'geo_world.json'):
        for p in json.load(open(HERE / f))['places']:
            if p['en'] in CITIES and p['en'] not in out:
                out[p['en']] = {'en': p['en'], 'lat': p['lat'], 'lon': p['lon'], 'iso': p['iso'],
                                'name': {'ru': p['ru'], 'uz': UZ_CITY.get(p['en']) or p['en'], 'tr': p.get('tr') or p['en']}}
    return [out[c] for c in CITIES if c in out]


def forecast(D, P, T, p, off):
    """Tomorrow (local) for one city: the highest rain chance of the day's windows and the mean temperature."""
    g = D['grid'].item() if hasattr(D['grid'], 'item') else D['grid']
    i = int(round((g['lat0'] - p['lat']) / g['d'])); j = int(round((p['lon'] - g['lon0']) / g['d'])) % P.shape[2]
    run = dt.datetime.fromisoformat(D['run'].replace('Z', '+00:00')).replace(tzinfo=None)
    tomorrow = (dt.datetime.utcnow() + dt.timedelta(hours=off)).date() + dt.timedelta(days=1)
    ix = [k for k, s in enumerate(D['steps']) if Rn.local_day(run, s, off, D['win'][k]) == tomorrow]
    if len(ix) < 2: return tomorrow, None
    pr = float(np.nanmax(P[ix, i, j]))
    tm = float(np.nanmean(T[ix, i, j])) if T is not None else None
    return tomorrow, [round(pr), None if tm is None or not np.isfinite(tm) else round(tm, 1)]


def observed(pl):
    r = None
    for k in range(4):
        try:
            r = requests.get('https://api.open-meteo.com/v1/forecast', params={'latitude': ','.join(str(p['lat']) for p in pl), 'longitude': ','.join(str(p['lon']) for p in pl),
                             'daily': 'precipitation_sum,temperature_2m_mean', 'past_days': 10, 'forecast_days': 1, 'timezone': 'auto'}, timeout=60)
            if r.status_code == 200: break
            print('open-meteo', r.status_code, r.text[:200], flush=True)
        except Exception as e: print('open-meteo', e, flush=True)
        time.sleep(10 * (k + 1))
    js = r.json(); js = js if isinstance(js, list) else [js]
    out = {}
    for p, x in zip(pl, js):
        for d, mm, t in zip(x['daily']['time'][:-1], x['daily']['precipitation_sum'][:-1], x['daily']['temperature_2m_mean'][:-1]):
            if mm is not None and t is not None: out.setdefault(d, {})[p['en']] = [round(mm, 1), round(t, 1)]
    return out


def score(pairs):
    """pairs: [(rain %, t, mm, t obs)] → accuracy of 'rain / no rain', mean temperature error, share within 2°."""
    if not pairs: return None
    hit = [(f >= RAIN_P) == (mm >= RAIN_MM) for f, _, mm, _ in pairs]
    te = [abs(t - to) for _, t, _, to in pairs if t is not None]
    return {'n': len(pairs), 'rain': round(100 * sum(hit) / len(hit)), 't_mae': round(float(np.mean(te)), 1) if te else None,
            't2': round(100 * sum(e <= 2 for e in te) / len(te)) if te else None}


def main():
    npz, wx, out = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3]) / 'verify'
    prev = pathlib.Path(sys.argv[4]) if len(sys.argv) > 4 else None
    out.mkdir(parents=True, exist_ok=True)
    H = {'fc': {}, 'obs': {}}
    if prev and prev.exists():
        try: H = json.load(open(prev))
        except Exception as e: print('history unreadable:', e)
    D = Rn.load(npz); P, _, _ = Rn.probability(D); W = Rn.load_wx_npz(D, wx) if pathlib.Path(wx).exists() else {}
    pl = places()
    # 1. tomorrow's forecast, only the first one made (so the lead time is a fair 24–48 h)
    for p in pl:
        off = 5 if p['iso'] == 'UZ' else round(p['lon'] / 15)
        day, f = forecast(D, P, W.get('T'), p, off)
        if f and p['en'] not in H['fc'].get(day.isoformat(), {}): H['fc'].setdefault(day.isoformat(), {})[p['en']] = f
    # 2. what happened on the past days
    try:
        for d, v in observed(pl).items(): H['obs'].setdefault(d, {}).update(v)
    except Exception as e: print('observations failed:', e)
    cut = (dt.date.today() - dt.timedelta(days=KEEP)).isoformat()
    H = {k: {d: v for d, v in H[k].items() if d >= cut} for k in ('fc', 'obs')}
    json.dump(H, open(out / 'history.json', 'w'), separators=(',', ':'))
    # 3. scores for the last 30 days
    since = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    pairs = {}
    for d, fc in H['fc'].items():
        if d < since: continue
        for c, (f, t) in fc.items():
            o = H['obs'].get(d, {}).get(c)
            if o: pairs.setdefault(c, []).append((d, f, t, o[0], o[1]))
    allp = [x[1:] for v in pairs.values() for x in v]
    days = {}
    for v in pairs.values():
        for x in v: days.setdefault(x[0], []).append(x[1:])
    idx = {'made': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), 'since': since, 'rule': {'rain_p': RAIN_P, 'rain_mm': RAIN_MM, 'lead': '24-48 h'},
           'overall': score(allp), 'uz': score([x[1:] for c, v in pairs.items() for x in v if c in CITIES[:14]]),
           'cities': [{'en': p['en'], 'iso': p['iso'], 'name': p['name'], **(score([x[1:] for x in pairs.get(p['en'], [])]) or {'n': 0})} for p in pl],
           'days': [{'date': d, **score(v)} for d, v in sorted(days.items())],
           'pending': sorted(d for d in H['fc'] if d not in H['obs'])}
    json.dump(idx, open(out / 'index.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    print('verify:', idx['overall'], 'days', len(idx['days']), 'pending', idx['pending'])


if __name__ == '__main__':
    main()
