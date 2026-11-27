"""UKMO accumulation files per step, and one file's variables."""
import subprocess, sys, re, requests
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'netCDF4', 'numpy'], check=True)
import site, importlib; site.addsitedir(site.getusersitepackages()); importlib.invalidate_caches()
import netCDF4, numpy as np
S = requests.Session(); out = []
def P(*a): s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)
B = 'https://met-office-atmospheric-model-data.s3.eu-west-2.amazonaws.com'; run = 'global-deterministic-10km/20261126T1200Z/'
keys, tok = [], ''
while True:
    r = S.get(f'{B}/?list-type=2&prefix={run}&max-keys=1000' + (f'&continuation-token={requests.utils.quote(tok)}' if tok else ''), timeout=60)
    keys += re.findall(r'<Key>([^<]+)</Key>', r.text); m = re.search(r'<NextContinuationToken>([^<]+)</NextContinuationToken>', r.text)
    if not m: break
    tok = m.group(1)
for a in ('PT01H', 'PT03H', 'PT06H'):
    st = sorted({int(re.search(r'-PT(\d+)H00M-', k).group(1)) for k in keys if f'precipitation_accumulation-{a}' in k}); P(a, st)
k = next(k for k in keys if 'precipitation_accumulation-PT03H' in k)
raw = S.get(f'{B}/{k}', timeout=120).content; ds = netCDF4.Dataset('m', memory=raw)
for n, v in ds.variables.items(): P(n, v.dimensions, v.shape, getattr(v, 'units', ''), getattr(v, 'standard_name', ''))
lat = ds.variables['latitude'][:] if 'latitude' in ds.variables else None
if lat is not None: P('lat', float(lat[0]), float(lat[-1]), 'lon', float(ds.variables['longitude'][0]), float(ds.variables['longitude'][-1]))
open('probe.txt', 'w').write('\n'.join(out))
