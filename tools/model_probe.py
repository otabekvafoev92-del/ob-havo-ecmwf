"""Which further global models have open files we can read: ICON-EPS, ARPEGE, UKMO 10 km, ECMWF IFS 0.1°."""
import requests, datetime as dt, re
S = requests.Session(); S.headers['User-Agent'] = 'osmon-probe/1.0'
out = []
def P(*a): s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)
now = dt.datetime.utcnow(); run = (now - dt.timedelta(hours=8)).replace(minute=0, second=0, microsecond=0); run = run.replace(hour=0 if run.hour < 12 else 12)
d, h = run.strftime('%Y%m%d'), run.strftime('%H'); P('run', run)
def head(u):
    try: r = S.get(u, headers={'Range': 'bytes=0-200'}, timeout=30); return r.status_code, r.headers.get('content-range'), r.text[:200] if 'xml' in r.headers.get('content-type', '') or 'html' in r.headers.get('content-type', '') else ''
    except Exception as e: return 'ERR', str(e)[:100], ''
def lst(u):
    try: r = S.get(u, timeout=30); return r.status_code, r.text[:3000]
    except Exception as e: return 'ERR', str(e)[:100]
# ICON-EPS
c, t = lst(f'https://opendata.dwd.de/weather/nwp/icon-eps/grib/{h}/tot_prec/'); P('ICON-EPS tot_prec dir', c, re.findall(r'href="([^"]+)"', t)[:6])
c, t = lst(f'https://opendata.dwd.de/weather/nwp/icon-eps/grib/{h}/'); P('ICON-EPS dirs', c, re.findall(r'href="([^"]+)"', t)[:40])
# ARPEGE
for base in ['https://object.data.gouv.fr/meteofrance-pnt/pnt']:
    c, t = lst(f'{base}/{run:%Y-%m-%dT%H}:00:00Z/arpege/025/SP1/'); P('ARPEGE listing', c, t[:600])
    for rg in ['000H024H', '025H048H', '049H072H', '073H102H']:
        P('ARPEGE', rg, head(f'{base}/{run:%Y-%m-%dT%H}:00:00Z/arpege/025/SP1/arpege__025__SP1__{rg}__{run:%Y-%m-%dT%H}:00:00Z.grib2'))
# UKMO on AWS
c, t = lst('https://met-office-atmospheric-model-data.s3.eu-west-2.amazonaws.com/?list-type=2&delimiter=/&max-keys=50'); P('UKMO root', c, t[:1500])
c, t = lst(f'https://met-office-atmospheric-model-data.s3.eu-west-2.amazonaws.com/?list-type=2&prefix=global-deterministic-10km/{d}T{h}00Z/&max-keys=40'); P('UKMO run', c, re.findall(r'<Key>([^<]+)</Key>', t)[:40])
# ECMWF IFS 0.1
for p in [f'{d}/{h}z/ifs/0p1/oper/', f'{d}/{h}z/']:
    c, t = lst(f'https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com/?list-type=2&prefix={p}&delimiter=/&max-keys=60'); P('ECMWF', p, c, re.findall(r'<(?:Key|Prefix)>([^<]+)</(?:Key|Prefix)>', t)[:60])
open('probe.txt', 'w').write('\n'.join(out))
