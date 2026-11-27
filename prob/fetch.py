"""Downloads 6-hour precipitation from several global models and counts, for every 6-hour window,
how many ensemble members / models give at least 0.2 mm. Output: prob.npz for prob/render.py.

Sources (all open data, only the precipitation field is downloaded thanks to byte ranges):
  ECMWF IFS ENS (50+1), ECMWF AIFS ENS (50+1), ECMWF IFS HRES, ECMWF AIFS Single
      https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com  (ECMWF open data, CC BY 4.0)
  NOAA GEFS (31), NOAA GFS     https://noaa-gefs-pds.s3.amazonaws.com, https://noaa-gfs-bdp-pds.s3.amazonaws.com
  DWD ICON (global, icosahedral → regridded)  https://opendata.dwd.de/weather/nwp/icon/grib/
  DWD ICON-EPS (40 members, up to 72 h)       https://opendata.dwd.de/weather/nwp/icon-eps/grib/
  ECMWF IFS HRES at 0.1° (9 km) where published
  UK Met Office global 10 km (to 168 h)       https://met-office-atmospheric-model-data.s3.eu-west-2.amazonaws.com
Usage: python3 prob/fetch.py out.npz [--run 2026-10-29T00] [--max-step 360]
"""
import argparse, bz2, datetime as dt, io, json, re, sys, time, concurrent.futures as cf
import numpy as np, requests
import eccodes

GRID = dict(lon0=20.0, lat0=82.0, d=0.25, W=681, H=229)  # 20°E…190°E, 82°N…25°N (south edge beyond the maps so the 5D layer is not cut)
N = GRID['W'] * GRID['H']
# the whole world at 0.5° for the globe's probability layer (same downloads, just a second regridding)
GLOBAL = dict(lon0=-180.0, lat0=90.0, d=0.5, W=720, H=361)
THR = 0.2  # mm per 6 h
# ECMWF open data mirrors (the same files); the Google Cloud copy is used first, AWS is the fallback
ECM = 'https://storage.googleapis.com/ecmwf-open-data'
ECM_ALT = 'https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com'
GEFS = 'https://noaa-gefs-pds.s3.amazonaws.com'
GFS = 'https://noaa-gfs-bdp-pds.s3.amazonaws.com'
DWD = 'https://opendata.dwd.de/weather/nwp/icon/grib'
S = requests.Session()
S.headers['User-Agent'] = 'osmon-prob/1.0 (open-data weather maps)'


def log(*a): print(dt.datetime.utcnow().strftime('%H:%M:%S'), *a, flush=True)


def get(url, rng=None, tries=6):
    for a in range(tries):
        if a == tries // 2 and url.startswith(ECM): url = ECM_ALT + url[len(ECM):]
        try:
            r = S.get(url, headers={'Range': f'bytes={rng[0]}-{rng[1]}'} if rng else {}, timeout=60)
            if r.status_code in (200, 206): return r.content
            if r.status_code == 404: return None
        except requests.RequestException as e:
            log('net', e)
        time.sleep(2 * (a + 1))
    return None


def decode(buf):
    h = eccodes.codes_new_from_message(buf)
    try:
        Ni, Nj = eccodes.codes_get(h, 'Ni'), eccodes.codes_get(h, 'Nj')
        lo1 = eccodes.codes_get(h, 'longitudeOfFirstGridPointInDegrees'); la1 = eccodes.codes_get(h, 'latitudeOfFirstGridPointInDegrees')
        di = eccodes.codes_get(h, 'iDirectionIncrementInDegrees'); dj = eccodes.codes_get(h, 'jDirectionIncrementInDegrees')
        v = eccodes.codes_get_values(h).astype(np.float32).reshape(Nj, Ni)
    finally:
        eccodes.codes_release(h)
    return dict(Ni=Ni, Nj=Nj, lo1=lo1, la1=la1, di=di, dj=dj, v=v)


_maps = {}
def regrid(g, grid=None):
    grid = grid or GRID
    key = (g['Ni'], g['lo1'], g['la1'], tuple(sorted(grid.items())))
    if key not in _maps:
        lon = grid['lon0'] + np.arange(grid['W']) * grid['d']; lat = grid['lat0'] - np.arange(grid['H']) * grid['d']
        fx = ((lon - g['lo1']) % 360) / g['di']; fy = (g['la1'] - lat) / g['dj']
        ix = np.floor(fx).astype(int); iy = np.floor(fy).astype(int)
        _maps[key] = (ix, (ix + 1) % g['Ni'], fx - ix, iy, np.minimum(iy + 1, g['Nj'] - 1), fy - iy)
    ix, ix1, ax, iy, iy1, ay = _maps[key]
    v = g['v']
    a = v[iy][:, ix] * (1 - ax) + v[iy][:, ix1] * ax
    b = v[iy1][:, ix] * (1 - ax) + v[iy1][:, ix1] * ax
    return (a * (1 - ay[:, None]) + b * ay[:, None]).astype(np.float32)


def ecmwf_jobs(run, model, stream, typ, step, scale, res='0p25'):
    d, h = run.strftime('%Y%m%d'), run.strftime('%H')
    base = f'{ECM}/{d}/{h}z/{model}/{res}/{stream}/{d}{h}0000-{step}h-{stream}-{typ}'
    idx = get(base + '.index')
    if not idx: return []
    out = []
    for line in idx.decode().strip().split('\n'):
        x = json.loads(line)
        if x.get('param') != 'tp': continue
        mem = 0 if x.get('type') in ('cf', 'fc') else int(x.get('number', 0))
        out.append(dict(url=base + '.grib2', rng=(x['_offset'], x['_offset'] + x['_length'] - 1), member=mem, scale=scale, start=0))
    return out


def ncep_job(url, step, member, win=6):
    """NOAA files hold precipitation in buckets that restart every 6 h (0-3, 0-6, 6-9, 6-12 …).
    Take the bucket that ends at `step`, preferring one that starts exactly at step − win."""
    idx = get(url + '.idx')
    if not idx: return []
    L = idx.decode().strip().split('\n'); best = None
    for i, l in enumerate(L):
        m = re.search(r':APCP:surface:(\d+)-(\d+) hour acc', l)
        if not m or int(m.group(2)) != step or i + 1 >= len(L): continue
        a = int(m.group(1))
        if best is None or a == step - win or (best[0] != step - win and a < best[0]):
            best = (a, dict(url=url, rng=(int(l.split(':')[1]), int(L[i + 1].split(':')[1]) - 1), member=member, scale=1, start=a))
    return [best[1]] if best else []


class Icon:
    """ICON global (deterministic) on its icosahedral grid → nearest cell for every target point."""
    def __init__(self, run, grids):
        self.run = run; self.idx = None; self.grids = grids
        try:
            from scipy.spatial import cKDTree
            h = run.strftime('%H'); tag = run.strftime('%Y%m%d%H')
            def field(var, name):
                raw = get(f'{DWD}/{h}/{var}/icon_global_icosahedral_time-invariant_{tag}_{name}.grib2.bz2')
                return eccodes.codes_get_values(eccodes.codes_new_from_message(bz2.decompress(raw)))
            clat, clon = np.radians(field('clat', 'CLAT')), np.radians(field('clon', 'CLON'))
            xyz = np.c_[np.cos(clat) * np.cos(clon), np.cos(clat) * np.sin(clon), np.sin(clat)]
            tree = cKDTree(xyz); self.idx = []
            for G_ in self.grids:
                lon = np.radians(G_['lon0'] + np.arange(G_['W']) * G_['d']); lat = np.radians(G_['lat0'] - np.arange(G_['H']) * G_['d'])
                LON, LAT = np.meshgrid(lon, lat)
                q = np.c_[(np.cos(LAT) * np.cos(LON)).ravel(), (np.cos(LAT) * np.sin(LON)).ravel(), np.sin(LAT).ravel()]
                self.idx.append(tree.query(q)[1])
            log('icon grid ok', len(clat))
        except Exception as e:
            log('icon disabled:', e)
        self.prev = None

    def amount(self, step, win=6):
        if self.idx is None or step > 180: return None
        h = self.run.strftime('%H'); tag = self.run.strftime('%Y%m%d%H')
        raw = get(f'{DWD}/{h}/tot_prec/icon_global_icosahedral_single-level_{tag}_{step:03d}_TOT_PREC.grib2.bz2')
        if not raw: return None
        v = eccodes.codes_get_values(eccodes.codes_new_from_message(bz2.decompress(raw)))
        cur = [v[ix].reshape(G_['H'], G_['W']).astype(np.float32) for ix, G_ in zip(self.idx, self.grids)]
        p = self.prev; self.prev = (step, cur)
        if step == win: return cur
        if p is None or p[0] != step - win: return None
        return [np.maximum(c - q, 0) for c, q in zip(cur, p[1])]


class IconEps:
    """DWD ICON-EPS (40 members, ~40 km icosahedral): every file holds all members' precipitation since the start; up to 72 h every 3 h or less."""
    BASE = 'https://opendata.dwd.de/weather/nwp/icon-eps/grib'
    def __init__(self, run, grids):
        self.run = run; self.idx = None; self.grids = grids; self.prev = {}
        try:
            from scipy.spatial import cKDTree
            h = run.strftime('%H'); tag = run.strftime('%Y%m%d%H')
            def field(var):
                raw = get(f'{self.BASE}/{h}/{var}/icon-eps_global_icosahedral_time-invariant_{tag}_{var}.grib2.bz2')
                return eccodes.codes_get_values(eccodes.codes_new_from_message(bz2.decompress(raw)))
            clat, clon = np.radians(field('clat')), np.radians(field('clon'))
            tree = cKDTree(np.c_[np.cos(clat) * np.cos(clon), np.cos(clat) * np.sin(clon), np.sin(clat)]); self.idx = []
            for G_ in grids:
                lon = np.radians(G_['lon0'] + np.arange(G_['W']) * G_['d']); lat = np.radians(G_['lat0'] - np.arange(G_['H']) * G_['d'])
                LON, LAT = np.meshgrid(lon, lat)
                self.idx.append(tree.query(np.c_[(np.cos(LAT) * np.cos(LON)).ravel(), (np.cos(LAT) * np.sin(LON)).ravel(), np.sin(LAT).ravel()])[1])
            log('icon-eps grid ok', len(clat))
        except Exception as e:
            log('icon-eps disabled:', e); self.idx = None

    def fields(self, step):
        """{member: [array per grid]} of the precipitation since the start, or None"""
        if self.idx is None or step > 180: return None
        if step in self.prev: return self.prev[step]
        h = self.run.strftime('%H'); tag = self.run.strftime('%Y%m%d%H')
        raw = get(f'{self.BASE}/{h}/tot_prec/icon-eps_global_icosahedral_single-level_{tag}_{step:03d}_tot_prec.grib2.bz2')
        if not raw: return None
        import tempfile, os
        out = {}
        with tempfile.NamedTemporaryFile(suffix='.grib2', delete=False) as f: f.write(bz2.decompress(raw)); fn = f.name
        try:
            with open(fn, 'rb') as fh:
                while True:
                    g = eccodes.codes_grib_new_from_file(fh)
                    if g is None: break
                    try:
                        m = eccodes.codes_get(g, 'perturbationNumber') if eccodes.codes_is_defined(g, 'perturbationNumber') else len(out) + 1
                        v = eccodes.codes_get_values(g)
                        out[int(m)] = [v[ix].reshape(G_['H'], G_['W']).astype(np.float32) for ix, G_ in zip(self.idx, self.grids)]
                    finally: eccodes.codes_release(g)
        finally: os.unlink(fn)
        self.prev = {k: v for k, v in self.prev.items() if k >= step - 12}; self.prev[step] = out
        return out

    def amounts(self, step, win):
        """the members' precipitation in (step − win, step], or None when the model has no output at one of the ends"""
        cur = self.fields(step)
        if not cur: return None
        if step == win: return list(cur.values())
        old = self.fields(step - win)
        if not old: return None
        return [[np.maximum(c - o, 0) for c, o in zip(cur[m], old[m])] for m in cur if m in old]


UKMO = 'https://met-office-atmospheric-model-data.s3.eu-west-2.amazonaws.com/global-deterministic-10km'


def ukmo_amount(run, step, win, grids):
    """UK Met Office global 10 km: the precipitation of the window (step − win, step] from its own 3- or 6-hour accumulation file (NetCDF)"""
    if step > 168 or win not in (3, 6): return None
    try:
        import netCDF4
    except Exception:
        return None
    vt = run + dt.timedelta(hours=step)
    url = f"{UKMO}/{run:%Y%m%dT%H00Z}/{vt:%Y%m%dT%H00Z}-PT{step:04d}H00M-precipitation_accumulation-PT{win:02d}H.nc"
    raw = get(url, tries=3)
    if not raw: return None
    try:
        ds = netCDF4.Dataset('mem', memory=raw)
        var = next(v for v in ds.variables.values() if v.ndim >= 2 and v.dimensions[-1].startswith(('lon', 'x', 'grid_longitude')))
        lat = np.asarray(ds.variables[var.dimensions[-2]][:], float); lon = np.asarray(ds.variables[var.dimensions[-1]][:], float)
        v = np.asarray(var[:], np.float32).reshape(len(lat), len(lon))
        un = (getattr(var, 'units', '') or '').strip()
        if un in ('m', 'metre', 'meters'): v = v * 1000
        elif un in ('kg m-2 s-1', 'mm s-1'): v = v * win * 3600
        v = np.nan_to_num(v, nan=0.0)
        if lat[0] < lat[-1]: lat = lat[::-1]; v = v[::-1]
        g = dict(Ni=len(lon), Nj=len(lat), lo1=float(lon[0]) % 360, la1=float(lat[0]), di=float(abs(lon[1] - lon[0])), dj=float(abs(lat[1] - lat[0])), v=v)
        return [regrid(g, G_) for G_ in grids]
    except Exception as e:
        log('ukmo', step, e); return None


def pick_run(want=None):
    if want: return dt.datetime.strptime(want, '%Y-%m-%dT%H')
    now = dt.datetime.utcnow()
    for k in range(0, 6):
        run = (now - dt.timedelta(hours=12 * k)).replace(minute=0, second=0, microsecond=0)
        run = run.replace(hour=0 if run.hour < 12 else 12)
        d, h = run.strftime('%Y%m%d'), run.strftime('%H')
        ok = all(get(u, (0, 10)) for u in [
            f'{ECM}/{d}/{h}z/ifs/0p25/enfo/{d}{h}0000-360h-enfo-ef.index',
            f'{ECM}/{d}/{h}z/aifs-ens/0p25/enfo/{d}{h}0000-360h-enfo-pf.index',
            f'{GEFS}/gefs.{d}/{h}/atmos/pgrb2ap5/gep30.t{h}z.pgrb2a.0p50.f360.idx'])
        if ok: return run
        log('run not complete:', run)
    raise SystemExit('no complete run')


def main():
    global GRID
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--run'); ap.add_argument('--max-step', type=int, default=360)
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--step3-until', type=int, default=144, help='3-hour windows up to this lead time (0 = 6-hour windows only)')
    ap.add_argument('--glob', default='glob.npz', help='also save the same probabilities for the whole world at 0.5° (globe layer); empty to skip')
    ap.add_argument('--wx', default='wx.npz', help='also save GEFS ensemble-mean 2 m temperature and cloud cover here')
    a = ap.parse_args()
    run = pick_run(a.run); log('run', run)
    d, h = run.strftime('%Y%m%d'), run.strftime('%H')
    # 3-hour windows while the models give 3-hourly output (ECMWF IFS ENS/HRES, GEFS, GFS, ICON: up to 144 h), then 6-hour windows
    steps = [x for x in range(3, min(a.step3_until, a.max_step) + 1, 3)] + [x for x in range(6, a.max_step + 1, 6) if x > a.step3_until]
    wins = [s - (steps[i - 1] if i else 0) for i, s in enumerate(steps)]
    ENS = ['ifs', 'aifs', 'gefs', 'iconeps']; DET = ['hres', 'aifss', 'gfs', 'icon', 'ukmo']
    GRIDS = [GRID] + ([GLOBAL] if a.glob else [])  # regional maps (0.25°) and, for the globe, the whole world (0.5°)
    Z = lambda G_, dt_=np.uint8: np.zeros((len(steps), G_['H'], G_['W']), dt_)
    cnt = [{k: Z(G_) for k in ENS} for G_ in GRIDS]; det = [Z(G_) for G_ in GRIDS]; amt = [Z(G_) for G_ in GRIDS]
    nmem = {k: np.zeros(len(steps), np.int16) for k in ENS}; avail = np.zeros((len(steps), len(DET)), bool)
    prev = {}
    icon = Icon(run, GRIDS); ieps = IconEps(run, GRIDS)
    pool = cf.ThreadPoolExecutor(a.workers)
    for si, s in enumerate(steps):
        win = wins[si]; jobs = []
        for j in ecmwf_jobs(run, 'ifs', 'enfo', 'ef', s, 1000): jobs.append(('ifs', j))
        for typ in ('cf', 'pf'):
            for j in ecmwf_jobs(run, 'aifs-ens', 'enfo', typ, s, 1): jobs.append(('aifs', j))
        # IFS HRES at 9 km (0.1°) where it is published, else 0.25°
        hj = ecmwf_jobs(run, 'ifs', 'oper', 'fc-sfc', s, 1000, res='0p1') or ecmwf_jobs(run, 'ifs', 'oper', 'fc', s, 1000)
        for j in hj: jobs.append(('hres', j))
        for j in ecmwf_jobs(run, 'aifs-single', 'oper', 'fc', s, 1): jobs.append(('aifss', j))
        urls = [(m, f'{GEFS}/gefs.{d}/{h}/atmos/pgrb2ap5/{"gec00" if m == 0 else f"gep{m:02d}"}.t{h}z.pgrb2a.0p50.f{s:03d}') for m in range(31)]
        for m, j in zip([u[0] for u in urls], pool.map(lambda u: ncep_job(u[1], s, u[0], win), urls)):
            for x in j: jobs.append(('gefs', x))
        for j in ncep_job(f'{GFS}/gfs.{d}/{h}/atmos/gfs.t{h}z.pgrb2.0p25.f{s:03d}', s, 0, win): jobs.append(('gfs', j))

        def work(item):
            sys_, j = item
            buf = get(j['url'], j['rng'])
            if not buf: return sys_, j, None
            g = decode(buf)
            return sys_, j, [regrid(g, G_) * j['scale'] for G_ in GRIDS]
        sums = [{k: np.zeros((G_['H'], G_['W']), np.float32) for k in ENS} for G_ in GRIDS]
        for sys_, j, f in pool.map(work, jobs):
            if f is None: continue
            # every field is an accumulation from j['start'] to s; the window is (s − win, s]
            key = (sys_, j['member']); p = prev.get(key); prev[key] = (j['start'], s, f)
            if j['start'] == s - win: amount = f
            elif p is not None and p[0] == j['start'] and p[1] == s - win: amount = [np.maximum(x - y, 0) for x, y in zip(f, p[2])]
            else: continue  # this model has no output at s − win (e.g. AIFS is 6-hourly): leave it out of this window
            if sys_ in ENS:
                nmem[sys_][si] += 1
                for gi in range(len(GRIDS)): cnt[gi][sys_][si] += (amount[gi] >= THR); sums[gi][sys_] += amount[gi]
            else:
                b = DET.index(sys_); avail[si, b] = True
                for gi in range(len(GRIDS)): det[gi][si] |= ((amount[gi] >= THR) << b).astype(np.uint8)
        ia = icon.amount(s, win)
        if ia is not None:
            b = DET.index('icon'); avail[si, b] = True
            for gi in range(len(GRIDS)): det[gi][si] |= ((ia[gi] >= THR) << b).astype(np.uint8)
        ua = ukmo_amount(run, s, win, GRIDS)
        if ua is not None:
            b = DET.index('ukmo'); avail[si, b] = True
            for gi in range(len(GRIDS)): det[gi][si] |= ((ua[gi] >= THR) << b).astype(np.uint8)
        ea = ieps.amounts(s, win) if s <= 72 else None  # ICON-EPS: 3-hourly output only up to 72 h
        if ea:
            nmem['iconeps'][si] = len(ea)
            for amount in ea:
                for gi in range(len(GRIDS)): cnt[gi]['iconeps'][si] += (amount[gi] >= THR); sums[gi]['iconeps'] += amount[gi]
        have = [k for k in ENS if nmem[k][si]]
        for gi in range(len(GRIDS)):
            mean = sum(sums[gi][k] / nmem[k][si] for k in have) / max(1, len(have))
            amt[gi][si] = np.clip(np.round(np.log1p(mean) * 40), 0, 255).astype(np.uint8)
        log(f'+{s}h ({win} h)', {k: int(nmem[k][si]) for k in ENS}, dict(zip(DET, avail[si].tolist())))
    for gi, (G_, out) in enumerate(zip(GRIDS, [a.out, a.glob])):
        np.savez_compressed(out, run=run.strftime('%Y-%m-%dT%H:00:00Z'), steps=np.array(steps), win=np.array(wins), grid=np.array(G_, dtype=object),
                            ens_names=np.array(ENS), det_names=np.array(DET), det=det[gi], det_avail=avail, amt=amt[gi],
                            **{f'ens_{k}': cnt[gi][k] for k in ENS}, **{f'n_{k}': nmem[k] for k in ENS})
        log('saved', out)
    if a.wx:
        # GEFS ensemble mean: 2 m temperature, total cloud cover, 10 m wind and CAPE every 6 h (for snow, clouds and temperature maps)
        WG = dict(GLOBAL)  # GEFS mean temperature / cloud for the whole world at 0.5° (the maps interpolate their own box from it)
        wsteps = sorted({0} | set(steps)); Tw = np.full((len(wsteps), WG['H'], WG['W']), np.nan, np.float32); Cw = Tw.copy(); Uw = Tw.copy(); Vw = Tw.copy(); Kw = Tw.copy()
        keep = GRID; GRID = WG; _maps.clear()
        for i, s in enumerate(wsteps):
            url = f'{GEFS}/gefs.{d}/{h}/atmos/pgrb2ap5/geavg.t{h}z.pgrb2a.0p50.f{s:03d}'
            idx = get(url + '.idx')
            if not idx: continue
            L = idx.decode().strip().split('\n')
            for key, arr, conv in ((':TMP:2 m above ground:', Tw, lambda v: v - 273.15), (':TCDC:entire atmosphere:', Cw, lambda v: v),
                                   (':UGRD:10 m above ground:', Uw, lambda v: v), (':VGRD:10 m above ground:', Vw, lambda v: v),
                                   (':CAPE:180-0 mb above ground:', Kw, lambda v: v)):  # convective energy: thunderstorms
                j = next((k for k, l in enumerate(L) if key in l), None)
                if j is None or j + 1 >= len(L): continue
                buf = get(url, (int(L[j].split(':')[1]), int(L[j + 1].split(':')[1]) - 1))
                if buf: arr[i] = conv(regrid(decode(buf)))
        GRID = keep
        np.savez_compressed(a.wx, run=run.strftime('%Y-%m-%dT%H:00:00Z'), steps=np.array(wsteps), grid=np.array(WG, dtype=object), T=Tw.astype(np.float16), C=Cw.astype(np.float16), U=Uw.astype(np.float16), V=Vw.astype(np.float16), K=np.clip(Kw, 0, 60000).astype(np.float16))
        log('saved', a.wx)


if __name__ == '__main__':
    main()
