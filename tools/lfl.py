"""Weather against last year for the mini-app page lfl.html (workflow lfl.yml, daily): for each city — daily max/min/mean temperature,
precipitation and snowfall from 1 January of last year to today (fact: ERA5 archive, the last days from the ECMWF model's analysis),
and the next 15 days (ECMWF forecast). Written to out/lfl.json; the page compares like-for-like (the same weekday 364 days back)
or date to date (the same calendar day last year)."""
import json, sys, time, datetime as dt, pathlib
import requests

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'lfl'); OUT.mkdir(parents=True, exist_ok=True)
# id, ru, uz, lat, lon, country
P = [('tashkent', 'Ташкент', 'Toshkent', 41.31, 69.28, 'UZ'), ('nurafshon', 'Ташкентская обл. (Нурафшон)', 'Toshkent viloyati (Nurafshon)', 41.04, 69.36, 'UZ'),
     ('samarkand', 'Самарканд', 'Samarqand', 39.65, 66.96, 'UZ'), ('bukhara', 'Бухара', 'Buxoro', 39.77, 64.42, 'UZ'),
     ('andijan', 'Андижан', 'Andijon', 40.78, 72.34, 'UZ'), ('fergana', 'Фергана', 'Farg‘ona', 40.39, 71.78, 'UZ'),
     ('namangan', 'Наманган', 'Namangan', 41.0, 71.67, 'UZ'), ('karshi', 'Карши', 'Qarshi', 38.86, 65.79, 'UZ'),
     ('termez', 'Термез', 'Termiz', 37.22, 67.28, 'UZ'), ('jizzakh', 'Джизак', 'Jizzax', 40.12, 67.84, 'UZ'),
     ('gulistan', 'Гулистан', 'Guliston', 40.49, 68.78, 'UZ'), ('navoi', 'Навои', 'Navoiy', 40.1, 65.38, 'UZ'),
     ('urgench', 'Ургенч', 'Urganch', 41.55, 60.63, 'UZ'), ('nukus', 'Нукус', 'Nukus', 42.46, 59.6, 'UZ')]
V = ['temperature_2m_max', 'temperature_2m_min', 'temperature_2m_mean', 'precipitation_sum', 'snowfall_sum']
K = ['tx', 'tn', 'tm', 'pr', 'sn']
S = requests.Session()


def call(url, **q):
    q.update(latitude=','.join(str(p[3]) for p in P), longitude=','.join(str(p[4]) for p in P), daily=','.join(V), timezone='auto')
    for k in range(6):
        try: r = S.get(url, params=q, timeout=180)
        except requests.RequestException as e: print('retry', url, e, flush=True); time.sleep(20 * (k + 1)); continue  # a timeout now and then
        if r.ok:
            j = r.json(); return j if isinstance(j, list) else [j]
        print('retry', url, r.status_code, r.text[:200], flush=True); time.sleep(20 * (k + 1))
    raise RuntimeError('Open-Meteo did not answer: ' + url)


def main():
    today = dt.date.today(); y0 = dt.date(today.year - 1, 1, 1)
    arc = call('https://archive-api.open-meteo.com/v1/archive', start_date=y0.isoformat(), end_date=(today - dt.timedelta(days=2)).isoformat())
    try: fc = call('https://api.open-meteo.com/v1/forecast', past_days=14, forecast_days=16, models='ecmwf_ifs025')
    except Exception as e:
        print('ecmwf model failed, best match', e, flush=True); fc = call('https://api.open-meteo.com/v1/forecast', past_days=14, forecast_days=16)
    days = [(y0 + dt.timedelta(days=i)).isoformat() for i in range((today - y0).days + 16)]
    out = {'made': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'start': y0.isoformat(), 'today': today.isoformat(), 'places': []}
    for p, a, f in zip(P, arc, fc):
        ser = {k: [None] * len(days) for k in K}; src = [None] * len(days)
        for blk, tag in ((a, 'a'), (f, 'f')):  # the archive first; the model fills the days the archive does not have yet (and the forecast)
            d = blk['daily']
            for i, day in enumerate(d['time']):
                j = (dt.date.fromisoformat(day) - y0).days
                if not 0 <= j < len(days): continue
                if tag == 'f' and src[j] == 'a' and d[V[0]][i] is not None and ser['tx'][j] is not None: continue
                if d[V[0]][i] is None: continue
                for k, v in zip(K, V):
                    x = d[v][i]; ser[k][j] = None if x is None else round(x, 1)
                src[j] = tag
        out['places'].append({'id': p[0], 'ru': p[1], 'uz': p[2], 'iso': p[5], 'tz': a.get('timezone'), **ser})
    json.dump(out, open(OUT / 'lfl.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    print('lfl.json', len(days), 'days', (OUT / 'lfl.json').stat().st_size // 1024, 'KB')


if __name__ == '__main__':
    main()
