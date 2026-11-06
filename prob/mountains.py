"""Mountains of Uzbekistan: when fresh snow falls and which days are good for a trip (Chimgan, Amirsoy, Beldersay,
Urgut, Zomin). Daily forecast for 16 days from Open-Meteo (best mix of ECMWF, DWD ICON, NOAA GFS), corrected to each
spot's own height (the elevation parameter), with the snow cover from the hourly snow depth.
  out/mountains.json
Usage: python3 prob/mountains.py out"""
import datetime as dt, json, pathlib, sys, time
import requests

UA = {'User-Agent': 'osmon-weather/1.0 (Telegram @ObHavo_ECMWF_bot)'}
# id, names, region, lat, lon, height of the place people go to (m)
SPOTS = [
    ('chimgan', {'uz': 'Chimyon', 'ru': 'Чимган', 'tr': 'Çimgan'}, {'uz': 'Toshkent viloyati', 'ru': 'Ташкентская обл.', 'tr': 'Taşkent ili'}, 41.545, 70.010, 1700),
    ('amirsoy', {'uz': 'Amirsoy', 'ru': 'Амирсой', 'tr': 'Amirsoy'}, {'uz': 'Toshkent viloyati', 'ru': 'Ташкентская обл.', 'tr': 'Taşkent ili'}, 41.490, 69.995, 1900),
    ('beldersay', {'uz': 'Beldersoy', 'ru': 'Бельдерсай', 'tr': 'Beldersay'}, {'uz': 'Toshkent viloyati', 'ru': 'Ташкентская обл.', 'tr': 'Taşkent ili'}, 41.520, 70.070, 1800),
    ('urgut', {'uz': 'Urgut tog‘lari', 'ru': 'Ургут (горы)', 'tr': 'Urgut dağları'}, {'uz': 'Samarqand viloyati', 'ru': 'Самаркандская обл.', 'tr': 'Semerkant ili'}, 39.340, 67.270, 1600),
    ('zomin', {'uz': 'Zomin', 'ru': 'Зомин', 'tr': 'Zomin'}, {'uz': 'Jizzax viloyati', 'ru': 'Джизакская обл.', 'tr': 'Cizzak ili'}, 39.620, 68.430, 2000),
]
SNOW_CM = 2.0   # a day with at least this much fresh snow is a snow day


def get(params):
    for k in range(5):
        try:
            r = requests.get('https://api.open-meteo.com/v1/forecast', params=params, headers=UA, timeout=60)
            if r.status_code == 200: return r.json()
            print('open-meteo', r.status_code, r.text[:200], flush=True)
        except Exception as e: print('open-meteo', e, flush=True)
        time.sleep(5 * (k + 1))
    raise RuntimeError('open-meteo failed')


def good(d):
    """A good day to go up: dry, not stormy, mostly sunny, not bitterly cold. 2 = very good, 1 = good, 0 = no."""
    if d['pr'] >= 1 or d['sn'] >= 0.5 or d['gust'] > 12 or d['sun'] < 4 or d['tmax'] < -12: return 0
    return 2 if d['sun'] >= 6 and d['gust'] <= 8 else 1


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    r = get({'latitude': ','.join(str(s[3]) for s in SPOTS), 'longitude': ','.join(str(s[4]) for s in SPOTS), 'elevation': ','.join(str(s[5]) for s in SPOTS),
             'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,wind_gusts_10m_max,sunshine_duration',
             'hourly': 'snow_depth', 'forecast_days': 16, 'timezone': 'Asia/Tashkent', 'wind_speed_unit': 'ms'})
    r = r if isinstance(r, list) else [r]
    res = {'made': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), 'snow_cm': SNOW_CM, 'spots': []}
    for (sid, name, area, la, lo, el), x in zip(SPOTS, r):
        D, H = x['daily'], x.get('hourly', {})
        depth = {}
        for t, v in zip(H.get('time', []), H.get('snow_depth', [])):
            if v is not None: depth[t[:10]] = max(depth.get(t[:10], 0), v)
        f = lambda k, i, nd=1: None if D[k][i] is None else round(D[k][i], nd)
        days = []
        for i, d in enumerate(D['time']):
            if D['temperature_2m_max'][i] is None: continue
            row = {'d': d, 'code': D['weather_code'][i], 'tmin': f('temperature_2m_min', i, 0), 'tmax': f('temperature_2m_max', i, 0),
                   'pr': f('precipitation_sum', i) or 0, 'sn': f('snowfall_sum', i) or 0, 'gust': f('wind_gusts_10m_max', i, 0) or 0,
                   'sun': round((D['sunshine_duration'][i] or 0) / 3600, 1), 'depth': round(depth.get(d, 0) * 100)}
            row['good'] = good(row); days.append(row)
        res['spots'].append({'id': sid, 'name': name, 'area': area, 'lat': la, 'lon': lo, 'elev': el, 'days': days})
        snow = [f"{d['d'][5:]} {d['sn']}cm" for d in days if d['sn'] >= SNOW_CM]
        print(sid, 'snow:', snow or '—', '| good:', [d['d'][5:] for d in days if d['good']][:5], flush=True)
    json.dump(res, open(out / 'mountains.json', 'w'), ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__':
    main()
