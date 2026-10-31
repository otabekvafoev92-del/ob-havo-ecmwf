"""World boundary pack for the continent maps of the probability report.
Natural Earth (public domain): countries 10m and populated places 10m.
Usage: python3 tools/make_world_geo.py <natural-earth-geojson-dir> prob/geo_world.json"""
import json, sys, pathlib
from shapely.geometry import shape
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from names_current import fix_dict_place
src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])


def coords(geom, tol):
    g = geom.simplify(tol, preserve_topology=True)
    polys = [g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))
    return [[[round(x, 2), round(y, 2)] for x, y in p.exterior.coords] for p in polys if p.geom_type == 'Polygon' and not p.is_empty and p.area > 0.02]


countries = {}
for f in json.load(open(src / 'ne_10m_admin_0_countries.geojson'))['features']:
    p = f['properties']; iso = p.get('ISO_A2_EH') or p.get('ISO_A2')
    if not iso or iso == '-99' or p['NAME_EN'] == 'Baikonur': continue
    rings = coords(shape(f['geometry']), 0.08)
    c = countries.setdefault(iso, {'name': p['NAME_EN'], 'ru': p.get('NAME_RU'), 'tr': p.get('NAME_TR'), 'rings': [], 'cont': p.get('CONTINENT')})
    c['rings'] += rings
places = []
for f in json.load(open(src / 'ne_10m_populated_places.geojson'))['features']:
    p = f['properties']; iso = p.get('ISO_A2')
    cap = 2 if p.get('ADM0CAP') else 0; pop = int(p.get('POP_MAX') or 0)
    if not (cap == 2 or pop >= 1_000_000): continue
    places.append({'en': p.get('NAME_EN') or p['NAME'], 'ru': p.get('NAME_RU') or p['NAME'], 'tr': p.get('NAME_TR') or p.get('NAME_EN') or p['NAME'],
                   'lon': round(p['LONGITUDE'], 3), 'lat': round(p['LATITUDE'], 3), 'iso': iso, 'pop': pop, 'cap': cap, 'rank': p['SCALERANK']})
for x in places: fix_dict_place(x)
places.sort(key=lambda x: -x['pop'])
json.dump({'countries': countries, 'admin1': {}, 'places': places}, open(out, 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(countries), len(places), out.stat().st_size)
