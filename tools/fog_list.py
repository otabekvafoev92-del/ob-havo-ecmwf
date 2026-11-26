"""Where fog is expected in Uzbekistan in the next 24 hours: every district centre (199), hour by hour, from the Open-Meteo forecast
(ECMWF IFS / ICON / GFS seamless): fog where the weather code is fog (45, 48) or the visibility is under 1 km.
Usage: python tools/fog_list.py out  →  out/fog.json {made, regions: [{ru, uz, districts: [{ru, uz, from, to, vis}]}]}"""
import sys, json, time, pathlib, datetime as dt, requests
ROOT = pathlib.Path(__file__).resolve().parent.parent
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
G = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']; A2 = G['adm2']; res = []
for i in range(0, len(A2), 100):
    ch = A2[i:i + 100]
    for t in range(6):
        try:
            r = requests.get('https://api.open-meteo.com/v1/forecast', params=dict(latitude=','.join(f"{d['c'][1]:.3f}" for d in ch), longitude=','.join(f"{d['c'][0]:.3f}" for d in ch),
                             hourly='weather_code,visibility', forecast_hours=24, timezone='Asia/Tashkent'), timeout=120)
            if r.status_code == 200: break
        except Exception as e: print('fog', e, flush=True)
        time.sleep(30)
    J = r.json(); res += J if isinstance(J, list) else [J]; time.sleep(3)
regs = {}
for d, j in zip(A2, res):
    h = j['hourly']; hrs = [k for k, (c, v) in enumerate(zip(h['weather_code'], h['visibility'])) if c in (45, 48) or (v is not None and v < 1000)]
    if not hrs: continue
    vis = min([h['visibility'][k] for k in hrs if h['visibility'][k] is not None] or [None]) if any(h['visibility'][k] is not None for k in hrs) else None
    regs.setdefault(d['p'], []).append(dict(ru=d['name']['ru'], uz=d['name']['uz'], frm=h['time'][hrs[0]], to=h['time'][hrs[-1]], vis=vis, lat=d['c'][1], lon=d['c'][0]))
R = [dict(ru=G['adm1'][p]['name']['ru'], uz=G['adm1'][p]['name']['uz'], districts=sorted(v, key=lambda x: x['frm'])) for p, v in sorted(regs.items())]
json.dump(dict(made=dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), regions=R), open(out / 'fog.json', 'w'), ensure_ascii=False)
print('fog districts', sum(len(r['districts']) for r in R), flush=True)
