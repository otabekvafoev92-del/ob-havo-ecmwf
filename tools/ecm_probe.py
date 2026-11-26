"""Which ECMWF open data exist (params of the ensemble, the probability product 'ep', the 9 km data)."""
import json, sys, collections, datetime as dt, requests
out = []
d = (dt.datetime.utcnow() - dt.timedelta(days=1)).strftime('%Y%m%d')
B = 'https://storage.googleapis.com/ecmwf-open-data'
def idx(u):
    r = requests.get(u, timeout=60); c = collections.Counter()
    if not r.ok: return f'{r.status_code}'
    for l in r.text.splitlines():
        try: j = json.loads(l)
        except Exception: continue
        c[(j.get('type'), j.get('param'), j.get('levtype'))] += 1
    return sorted(c.items())
for u in [f'{B}/{d}/00z/ifs/0p25/enfo/{d}000000-24h-enfo-ef.index', f'{B}/{d}/00z/ifs/0p25/enfo/{d}000000-240h-enfo-ep.index', f'{B}/{d}/00z/ifs/0p25/enfo/{d}000000-24h-enfo-ep.index',
          f'{B}/{d}/00z/ifs/0p25/oper/{d}000000-24h-oper-fc.index']:
    out.append(f'{u}\n{idx(u)}\n')
# the 9 km (0p1?) folders
for res in ['0p1', '0p125', '0p08', '9km']:
    for st in ['oper', 'enfo']:
        u = f'{B}/{d}/00z/ifs/{res}/{st}/'
        r = requests.get(f'{B}?prefix={d}/00z/ifs/{res}/{st}/&max-keys=5', timeout=60) if False else None
r = requests.get('https://storage.googleapis.com/storage/v1/b/ecmwf-open-data/o', params=dict(prefix=f'{d}/00z/', delimiter='/'), timeout=60)
out.append('prefixes 00z: ' + json.dumps(r.json().get('prefixes', [])))
r = requests.get('https://storage.googleapis.com/storage/v1/b/ecmwf-open-data/o', params=dict(prefix=f'{d}/00z/ifs/', delimiter='/'), timeout=60)
out.append('ifs: ' + json.dumps(r.json().get('prefixes', [])))
open('probe.txt', 'w').write('\n'.join(map(str, out))); print('\n'.join(map(str, out)))
