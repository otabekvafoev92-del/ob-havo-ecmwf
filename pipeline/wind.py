"""Real wind for the globe: ECMWF IFS (open data) u/v at 10 m, 850, 500 and 250 hPa, every 6 h to +240 h.
Writes site/data/wind/<level>.jpg atlases (u and v as grey: 128 + value/scale) and site/data/wind.json.
Only the needed GRIB messages are downloaded (byte ranges from the .index files).
Usage: python3 pipeline/wind.py site/data 2026-10-29T00:00:00Z"""
import json, sys, time, pathlib, concurrent.futures as cf
import numpy as np, requests, eccodes
from PIL import Image

ECM = 'https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com'
LEVELS = [  # id, levtype, level, scale (m/s per grey step), height (m) used on the globe
    ('10m', 'sfc', None, 0.5, 0), ('850', 'pl', '850', 0.5, 1500), ('500', 'pl', '500', 1.0, 5500), ('250', 'pl', '250', 1.0, 10400)]
TW, TH, COLS = 360, 181, 5  # 1° tiles, 5 steps per atlas row (u and v side by side)
S = requests.Session()


def get(url, rng=None):
    for a in range(8):
        try:
            r = S.get(url, headers={'Range': f'bytes={rng[0]}-{rng[1]}'} if rng else {}, timeout=60)
            if r.status_code in (200, 206): return r.content
            if r.status_code == 404: return None
        except requests.RequestException:
            pass
        time.sleep(2 * (a + 1))
    return None


def to1deg(buf):
    h = eccodes.codes_new_from_message(buf)
    v = eccodes.codes_get_values(h).reshape(eccodes.codes_get(h, 'Nj'), eccodes.codes_get(h, 'Ni')); eccodes.codes_release(h)
    # 0.25° grid from 90°N and 180°W → 1°: every 4th row, mean of 4 neighbouring columns
    rows = v[::4]  # 721 → 181 rows (90°N … 90°S)
    return rows.reshape(181, 360, 4).mean(2).astype(np.float32)


def main():
    out, run = pathlib.Path(sys.argv[1]), sys.argv[2]
    d, hh = run[:10].replace('-', ''), run[11:13]
    steps = list(range(0, 241, 6))
    (out / 'wind').mkdir(parents=True, exist_ok=True)
    jobs = []
    for i, s in enumerate(steps):
        base = f'{ECM}/{d}/{hh}z/ifs/0p25/oper/{d}{hh}0000-{s}h-oper-fc'
        idx = get(base + '.index')
        if not idx: print('missing', s); continue
        for line in idx.decode().strip().split('\n'):
            x = json.loads(line)
            for lid, lt, lev, *_ in LEVELS:
                if lt == 'sfc' and x.get('param') in ('10u', '10v') or lt == 'pl' and x.get('levtype') == 'pl' and x.get('levelist') == lev and x.get('param') in ('u', 'v'):
                    comp = x['param'][-1]
                    jobs.append((i, lid, comp, base + '.grib2', (x['_offset'], x['_offset'] + x['_length'] - 1)))
    fields = {}
    with cf.ThreadPoolExecutor(12) as pool:
        for (i, lid, comp, url, rng), buf in zip(jobs, pool.map(lambda j: get(j[3], j[4]), jobs)):
            if buf: fields[(i, lid, comp)] = to1deg(buf)
    rows = (len(steps) + COLS - 1) // COLS
    meta = {'run': run, 'steps': steps, 'tile': {'W': TW, 'H': TH, 'cols': COLS}, 'levels': []}
    for lid, lt, lev, scale, height in LEVELS:
        atlas = np.full((rows * TH, COLS * 2 * TW), 128, np.uint8)
        for i in range(len(steps)):
            for c, comp in enumerate('uv'):
                f = fields.get((i, lid, comp))
                if f is None: f = fields.get((max(0, i - 1), lid, comp))
                if f is None: continue
                y0, x0 = (i // COLS) * TH, ((i % COLS) * 2 + c) * TW
                atlas[y0:y0 + TH, x0:x0 + TW] = np.clip(np.round(128 + f / scale), 0, 255)
        Image.fromarray(atlas, 'L').save(out / 'wind' / f'{lid}.jpg', quality=90)
        meta['levels'].append({'id': lid, 'file': f'wind/{lid}.jpg', 'scale': scale, 'h': height})
    json.dump(meta, open(out / 'wind.json', 'w'))
    print('wind ok', len(fields), 'fields')


if __name__ == '__main__':
    main()
