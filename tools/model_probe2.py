"""Which more forecast models the runners can reach (written to out.txt on the probe branch):
Canada GEM / GEPS (MSC Datamart), NOAA GraphCast-GFS (AWS), ECMWF AIFS ENS (open data), Open-Meteo's other global models."""
import requests, re, datetime as dt

out = []
def log(*a):
    s = ' '.join(str(x) for x in a); print(s); out.append(s)

def get(url, **kw):
    try:
        r = requests.get(url, timeout=40, **kw); return r.status_code, r.text[:3000]
    except Exception as e:
        return 'ERR', str(e)[:150]

today = dt.datetime.utcnow().strftime('%Y%m%d')
yday = (dt.datetime.utcnow() - dt.timedelta(days=1)).strftime('%Y%m%d')
# Canada: GEM global 15 km and GEPS ensemble (MSC Datamart, open licence)
for u in ['https://dd.weather.gc.ca/model_gem_global/15km/grib2/lat_lon/00/',
          'https://dd.weather.gc.ca/ensemble/geps/grib2/raw/00/',
          f'https://dd.weather.gc.ca/{today}/WXO-DD/model_gem_global/15km/grib2/lat_lon/00/',
          f'https://dd.weather.gc.ca/{today}/WXO-DD/ensemble/geps/grib2/raw/00/']:
    c, t = get(u); log('CMC', u, c, re.findall(r'href="([^"?]+)"', t)[:6] if c == 200 else t[:120])
# NOAA GraphCast-GFS on AWS (open data)
for b in ['noaa-nws-graphcastgfs-pds', 'noaa-nws-aigfs-pds', 'noaa-oar-mlwp-data']:
    c, t = get(f'https://{b}.s3.amazonaws.com/?list-type=2&max-keys=8&delimiter=/'); log('AWS', b, c, re.findall(r'<(?:Key|Prefix)>([^<]+)<', t)[:8])
for d in [today, yday]:
    c, t = get(f'https://noaa-nws-graphcastgfs-pds.s3.amazonaws.com/?list-type=2&max-keys=10&prefix=graphcastgfs.{d}/'); log('GraphCast', d, c, re.findall(r'<Key>([^<]+)<', t)[:6])
# ECMWF AIFS ENS (open data, 0.25°)
for d in [today, yday]:
    c, t = get(f'https://data.ecmwf.int/forecasts/{d}/00z/aifs-ens/0p25/enfo/'); log('AIFS-ENS', d, c, re.findall(r'href="[^"]*/([^/"]+)"', t)[:6])
# Open-Meteo: other global models for one point (Tashkent)
for m in ['cma_grapes_global', 'jma_gsm', 'meteofrance_arpege_world', 'gem_global', 'bom_access_global', 'kma_gdps', 'ukmo_global_deterministic_10km', 'ecmwf_aifs025_single']:
    c, t = get('https://api.open-meteo.com/v1/forecast', params={'latitude': 41.31, 'longitude': 69.28, 'hourly': 'precipitation,temperature_2m', 'models': m, 'forecast_days': 10})
    n = len(re.findall(r'-?\d+\.\d', t)) if c == 200 else 0
    log('Open-Meteo', m, c, n, t[:100] if c != 200 else '')
open('out.txt', 'w').write('\n'.join(out) + '\n')
