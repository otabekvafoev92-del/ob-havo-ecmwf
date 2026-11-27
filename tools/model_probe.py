"""UKMO precipitation files and ICON-EPS steps."""
import requests, datetime as dt, re
S = requests.Session(); S.headers['User-Agent'] = 'osmon-probe/1.0'; out = []
def P(*a): s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)
B = 'https://met-office-atmospheric-model-data.s3.eu-west-2.amazonaws.com'
r = S.get(f'{B}/?list-type=2&prefix=global-deterministic-10km/&delimiter=/&max-keys=1000', timeout=30); runs = re.findall(r'<Prefix>(global-deterministic-10km/[^<]+/)</Prefix>', r.text); P('runs', runs[-4:])
import datetime as _d
run = 'global-deterministic-10km/' + (_d.datetime.utcnow() - _d.timedelta(hours=14)).replace(hour=0 if (_d.datetime.utcnow() - _d.timedelta(hours=14)).hour < 12 else 12).strftime('%Y%m%dT%H00Z') + '/'; P('run', run); keys = []; tok = ''
while True:
    r = S.get(f'{B}/?list-type=2&prefix={run}&max-keys=1000' + (f'&continuation-token={requests.utils.quote(tok)}' if tok else ''), timeout=60)
    keys += [(re.search(r'<Key>([^<]+)</Key>', c).group(1), re.search(r'<Size>(\d+)</Size>', c).group(1)) for c in re.findall(r'<Contents>(.*?)</Contents>', r.text)]
    if not keys: P('raw', r.status_code, r.text[:500])
    m = re.search(r'<NextContinuationToken>([^<]+)</NextContinuationToken>', r.text)
    if not m: break
    tok = m.group(1)
P('nkeys', len(keys))
names = sorted({re.sub(r'^.*-PT\d+H\d+M-', '', k) for k, _ in keys}); P('vars', names)
pr = [(k, s) for k, s in keys if 'precip' in k.lower()]; P('precip files', len(pr)); [P(k, s) for k, s in pr[:6] + pr[-4:]]
steps = sorted({re.search(r'-PT(\d+)H', k).group(1) for k, _ in pr}); P('steps', steps)
r = S.get(f'https://opendata.dwd.de/weather/nwp/icon-eps/grib/00/tot_prec/', timeout=60); st = re.findall(r'_(\d{3})_tot_prec', r.text); P('icon-eps steps', sorted(set(st)))
r = S.get('https://opendata.dwd.de/weather/nwp/icon-eps/grib/00/clat/', timeout=60); P('clat', re.findall(r'href="([^"]+)"', r.text))
open('probe.txt', 'w').write('\n'.join(out))
