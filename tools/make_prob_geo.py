"""Boundary pack for the precipitation-probability maps (CIS + Turkey).
Natural Earth (public domain): countries 10m, admin-1 10m, populated places 10m.
Usage: python3 tools/make_prob_geo.py <natural-earth-geojson-dir> prob/geo_prob.json"""
import json, sys, pathlib
from shapely.geometry import shape, box
from shapely.ops import unary_union
src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
BOX = box(15, 25, 195, 85)
FOCUS = ['UZ', 'KZ', 'KG', 'TJ', 'TM', 'AZ', 'AM', 'BY', 'MD', 'RU', 'TR']

def coords(geom, tol):
    g = geom.simplify(tol, preserve_topology=True)
    polys = [g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))
    res = []
    for p in polys:
        if p.geom_type != 'Polygon' or p.is_empty: continue
        res.append([[round(x, 3), round(y, 3)] for x, y in p.exterior.coords])
    return res

def shift(geom):
    # Chukotka crosses 180°: move western-hemisphere parts east so the map is continuous
    from shapely.affinity import translate
    parts = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
    return unary_union([translate(p, 360) if p.bounds[2] < -150 else p for p in parts])

countries = {}
for f in json.load(open(src / 'ne_10m_admin_0_countries.geojson'))['features']:
    p = f['properties']; iso = p.get('ISO_A2_EH') or p.get('ISO_A2')
    if p['NAME_EN'] in ('Baikonur',): continue  # leased area, would draw a border inside Kazakhstan
    g = shift(shape(f['geometry']))
    if not g.intersects(BOX): continue
    g = g.intersection(BOX)
    rings = coords(g, 0.02 if iso in FOCUS else 0.05)
    if iso in countries:  # e.g. Baikonur is a separate feature with ISO KZ
        countries[iso]['rings'] += rings
        if g.area > countries[iso]['area']: countries[iso].update(name=p['NAME_EN'], ru=p.get('NAME_RU'), tr=p.get('NAME_TR'), area=g.area)
    else:
        countries[iso] = {'name': p['NAME_EN'], 'ru': p.get('NAME_RU'), 'tr': p.get('NAME_TR'), 'rings': rings, 'area': g.area}
admin1 = {}
for f in json.load(open(src / 'ne_10m_admin_1_states_provinces.geojson'))['features']:
    p = f['properties']; iso = p.get('iso_a2')
    if iso not in FOCUS: continue
    g = shift(shape(f['geometry']))
    admin1.setdefault(iso, []).extend(coords(g, 0.03 if iso != 'RU' else 0.06))
places = []
for f in json.load(open(src / 'ne_10m_populated_places.geojson'))['features']:
    p = f['properties']; iso = p.get('ISO_A2')
    if iso not in FOCUS: continue
    lon, lat = p['LONGITUDE'], p['LATITUDE']
    if lon < -150: lon += 360
    cap = 2 if p.get('ADM0CAP') else (1 if (p.get('FEATURECLA') or '').startswith('Admin-1 capital') else 0)
    places.append({'en': p.get('NAME_EN') or p['NAME'], 'ru': p.get('NAME_RU') or p['NAME'], 'tr': p.get('NAME_TR') or p.get('NAME_EN') or p['NAME'],
                   'lon': round(lon, 3), 'lat': round(lat, 3), 'iso': iso, 'pop': int(p.get('POP_MAX') or 0), 'cap': cap, 'rank': p['SCALERANK']})
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from names_current import fix_dict_place
for x in places: fix_dict_place(x)
places.sort(key=lambda x: -x['pop'])
json.dump({'countries': countries, 'admin1': admin1, 'places': places}, open(out, 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(countries), {k: len(v) for k, v in admin1.items()}, len(places), out.stat().st_size)
