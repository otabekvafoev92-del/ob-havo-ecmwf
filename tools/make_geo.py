"""Builds site/assets/geo.json from Natural Earth (public domain):
countries (50m), admin-1 regions (10m), urban areas (10m), populated places (10m).
Usage: python3 tools/make_geo.py <natural-earth-geojson-dir> site/assets/geo.json
Download the inputs from https://github.com/nvkelso/natural-earth-vector/tree/master/geojson
"""
import json, sys, math, pathlib

src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
CA = (44, 96, 28, 56)  # Central Asia box: lon0, lon1, lat0, lat1 — kept in more detail

def in_ca(pts):
    return any(CA[0] <= x <= CA[1] and CA[2] <= y <= CA[3] for x, y in pts)

def dp(pts, tol):
    """Douglas–Peucker simplification (iterative)."""
    if len(pts) < 3: return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]; bx, by = pts[b]
        dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy) or 1e-12
        best, bi = -1, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / L if L > 1e-12 else math.hypot(px - ax, py - ay)
            if d > best: best, bi = d, i
        if best > tol:
            keep[bi] = True; stack += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]

def enc(pts):
    """Delta-encoded integers at 0.01°."""
    out, px, py = [], 0, 0
    for x, y in pts:
        X, Y = round(x * 100), round(y * 100)
        out += [X - px, Y - py]; px, py = X, Y
    return out

def rings(geom):
    if geom is None: return []
    t, c = geom['type'], geom['coordinates']
    if t == 'Polygon': return c
    if t == 'MultiPolygon': return [r for p in c for r in p]
    if t == 'LineString': return [c]
    if t == 'MultiLineString': return c
    return []

def layer(fname, tol_world, tol_ca, min_pts=2, min_extent=0.0):
    d = json.load(open(src / fname))
    lines = []
    for f in d['features']:
        for r in rings(f['geometry']):
            pts = [(p[0], p[1]) for p in r]
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            if max(xs) - min(xs) < min_extent and max(ys) - min(ys) < min_extent: continue
            s = dp(pts, tol_ca if in_ca(pts) else tol_world)
            if len(s) >= min_pts: lines.append(enc(s))
    return lines

geo = {
    'countries': layer('ne_50m_admin_0_countries.geojson', 0.04, 0.01),
    'admin1': layer('ne_10m_admin_1_states_provinces.geojson', 0.06, 0.012, min_extent=0.05),
    'urban': layer('ne_10m_urban_areas.geojson', 0.01, 0.004, min_pts=3, min_extent=0.02),
}
pp = json.load(open(src / 'ne_10m_populated_places.geojson'))
places = []
for f in pp['features']:
    p = f['properties']
    lon, lat = p['LONGITUDE'], p['LATITUDE']
    ca = CA[0] <= lon <= CA[1] and CA[2] <= lat <= CA[3]
    if not ca and p['SCALERANK'] > 6: continue
    cap = 2 if p.get('ADM0CAP') else (1 if p.get('FEATURECLA', '').startswith('Admin-1') else 0)
    places.append([round(lon, 3), round(lat, 3), p.get('NAME_EN') or p['NAME'], p.get('NAME_RU') or p['NAME'],
                   p['SCALERANK'], int(p.get('POP_MAX') or 0), p.get('ISO_A2') or '', cap])
# Natural Earth still has some outdated names
RENAME = {'Nur-Sultan': ('Astana', 'Астана'), 'Almaty': ('Almaty', 'Алматы')}
for x in places:
    if x[2] in RENAME: x[2], x[3] = RENAME[x[2]]
places.sort(key=lambda x: (x[4], -x[5]))
geo['places'] = places
txt = json.dumps(geo, separators=(',', ':'), ensure_ascii=False)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(txt)
print({k: len(v) for k, v in geo.items()}, round(len(txt) / 1e6, 2), 'MB')
