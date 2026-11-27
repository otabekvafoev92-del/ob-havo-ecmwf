"""Open-Meteo: which global models give data over Uzbekistan, and the Canadian GEPS file layout (out.txt on the probe branch)."""
import requests, re, json, datetime as dt
out = []
M = 'cma_grapes_global,jma_gsm,meteofrance_arpege_world,gem_global,bom_access_global,kma_gdps,ecmwf_ifs025,gfs_global,icon_global,ukmo_global_deterministic_10km,ecmwf_aifs025_single,ncep_aigfs025'
r = requests.get('https://api.open-meteo.com/v1/forecast', params={'latitude': 41.31, 'longitude': 69.28, 'daily': 'precipitation_sum,temperature_2m_max', 'forecast_days': 7, 'models': M}, timeout=60)
out.append(f'OM {r.status_code}')
j = r.json(); d = j.get('daily', {})
for k, v in d.items():
    if k != 'time': out.append(f'{k}: {v}')
if 'reason' in j: out.append(j['reason'])
today = dt.datetime.utcnow().strftime('%Y%m%d')
for h in ['00', '12']:
    for step in ['024']:
        u = f'https://dd.weather.gc.ca/{today}/WXO-DD/ensemble/geps/grib2/raw/{h}/{step}/'
        t = requests.get(u, timeout=40); out.append(f'GEPS {u} {t.status_code} ' + ' '.join(re.findall(r'href="([^"?/]+\.grib2)"', t.text)[:40]))
t = requests.get(f'https://dd.weather.gc.ca/{today}/WXO-DD/', timeout=40); out.append('DD root ' + ' '.join(re.findall(r'href="([^"?]+/)"', t.text)[:60]))
t = requests.get('https://noaa-nws-graphcastgfs-pds.s3.amazonaws.com/?list-type=2&max-keys=1000&delimiter=/', timeout=40)
out.append('AIGFS last ' + ' '.join(re.findall(r'<Prefix>([^<]+)<', t.text)[-6:]))
open('out.txt', 'w').write('\n'.join(out) + '\n')
