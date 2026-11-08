"""Regions (oblasts) and districts of Uzbekistan, Kazakhstan and Kyrgyzstan for the maps → prob/geo_admin.json.

Run once by hand (needs shapely), the result is kept in the repository:
    python prob/build_admin.py <folder with geoBoundaries-*-ADM1/ADM2_simplified.geojson> prob/geo_admin.json
Borders: geoBoundaries (gbOpen, CC BY 4.0), https://www.geoboundaries.org
"""
import json, re, sys
from pathlib import Path
from shapely.geometry import shape, mapping, Point
from shapely.ops import unary_union

ISO3 = {'UZ': 'UZB', 'KZ': 'KAZ', 'KG': 'KGZ'}
# region names in Russian, Uzbek and Turkish (the borders come with English names)
ADM1 = {
    'Andijan Region': ('Андижанская обл.', 'Andijon viloyati', 'Andican'), 'Namangan Region': ('Наманганская обл.', 'Namangan viloyati', 'Namangan'),
    'Fergana Region': ('Ферганская обл.', 'Farg‘ona viloyati', 'Fergana'), 'Republic of Karakalpakstan': ('Каракалпакстан', 'Qoraqalpog‘iston', 'Karakalpakistan'),
    'Xorazm Region': ('Хорезмская обл.', 'Xorazm viloyati', 'Harezm'), 'Navoiy Region': ('Навоийская обл.', 'Navoiy viloyati', 'Navoi'),
    'Surxondaryo Region': ('Сурхандарьинская обл.', 'Surxondaryo viloyati', 'Surhanderya'), 'Samarqand Region': ('Самаркандская обл.', 'Samarqand viloyati', 'Semerkant'),
    'Tashkent Region': ('Ташкентская обл.', 'Toshkent viloyati', 'Taşkent bölgesi'), 'Sirdaryo Region': ('Сырдарьинская обл.', 'Sirdaryo viloyati', 'Sirderya'),
    'Jizzakh Region': ('Джизакская обл.', 'Jizzax viloyati', 'Cizzak'), 'Bukhara Region': ('Бухарская обл.', 'Buxoro viloyati', 'Buhara'),
    'Qashqadaryo Region': ('Кашкадарьинская обл.', 'Qashqadaryo viloyati', 'Kaşkaderya'), 'Tashkent': ('Ташкент', 'Toshkent shahri', 'Taşkent'),
    'Pavlodar Region': ('Павлодарская обл.', 'Pavlodar viloyati', 'Pavlodar'), 'Jambyl Region': ('Жамбылская обл.', 'Jambil viloyati', 'Cambıl'),
    'Kostanay Region': ('Костанайская обл.', 'Qo‘stanay viloyati', 'Kostanay'), 'Mangystau Region': ('Мангистауская обл.', 'Mang‘istov viloyati', 'Mangıstav'),
    'Karaganda Region': ('Карагандинская обл.', 'Qarag‘anda viloyati', 'Karağandı'), 'Kyzylorda Region': ('Кызылординская обл.', 'Qizil O‘rda viloyati', 'Kızılorda'),
    'East Kazakhstan Region': ('Восточно-Казахстанская обл.', 'Sharqiy Qozog‘iston', 'Doğu Kazakistan'), 'Aktobe Region': ('Актюбинская обл.', 'Aqto‘be viloyati', 'Aktöbe'),
    'Atyrau Region': ('Атырауская обл.', 'Atirau viloyati', 'Atırav'), 'South Kazakhstan Region': ('Туркестанская обл.', 'Turkiston viloyati', 'Türkistan'),
    'Akmola Region': ('Акмолинская обл.', 'Aqmola viloyati', 'Akmola'), 'Almaty Region': ('Алматинская обл.', 'Olmaota viloyati', 'Almatı bölgesi'),
    'North Kazakhstan Region': ('Северо-Казахстанская обл.', 'Shimoliy Qozog‘iston', 'Kuzey Kazakistan'), 'Almaty': ('Алматы', 'Olmaota shahri', 'Almatı'),
    'West Kazakhstan Region': ('Западно-Казахстанская обл.', 'G‘arbiy Qozog‘iston', 'Batı Kazakistan'), 'Astana': ('Астана', 'Ostona', 'Astana'),
    'Batken Region': ('Баткенская обл.', 'Botken viloyati', 'Batken'), 'Osh Region': ('Ошская обл.', 'O‘sh viloyati', 'Oş'),
    'Talas Region': ('Таласская обл.', 'Talas viloyati', 'Talas'), 'Jalal-Abad Region': ('Джалал-Абадская обл.', 'Jalolobod viloyati', 'Celalabad'),
    'Issyk-Kul Region': ('Иссык-Кульская обл.', 'Issiqko‘l viloyati', 'Issık Göl'), 'Chuy Region': ('Чуйская обл.', 'Chuy viloyati', 'Çuy'),
    'Naryn Region': ('Нарынская обл.', 'Norin viloyati', 'Narın'),
}
# district names: the borders give a Russian name in Latin letters; Russian gets it back in Cyrillic
LAT2CYR = [('shch', 'щ'), ('sch', 'щ'), ('gh', 'г'), ('`', 'ь'), ('yo', 'ё'), ('zh', 'ж'), ('kh', 'х'), ('ts', 'ц'), ('ch', 'ч'), ('sh', 'ш'), ('yu', 'ю'), ('ya', 'я'), ('ye', 'е'),
           ('iy', 'ий'), ('yy', 'ый'), ('a', 'а'), ('b', 'б'), ('v', 'в'), ('g', 'г'), ('d', 'д'), ('e', 'е'), ('z', 'з'), ('i', 'и'), ('y', 'ы'), ('k', 'к'),
           ('l', 'л'), ('m', 'м'), ('n', 'н'), ('o', 'о'), ('p', 'п'), ('r', 'р'), ('s', 'с'), ('t', 'т'), ('u', 'у'), ('f', 'ф'), ('h', 'х'), ('c', 'к'),
           ('j', 'дж'), ('q', 'к'), ('x', 'х'), ('w', 'в'), ("'", 'ь')]


def cyr(name):
    out, i, low = '', 0, name.lower()
    while i < len(name):
        if low[i] == 'y' and i and low[i - 1] in 'aeiou' and not low.startswith(('ya', 'yu', 'ye', 'yo'), i):
            out += 'й'; i += 1; continue  # Alay → Алай, Chuy → Чуй
        for a, b in LAT2CYR:
            if low.startswith(a, i):
                out += (b[0].upper() + b[1:]) if name[i].isupper() else b; i += len(a); break
        else:
            out += name[i]; i += 1
    return out


def dname(en):
    """A district: 'Karshi city' → город, 'Aksuskiy' → район (in Russian and Uzbek)."""
    en = en.replace('а', 'a').strip()  # a Cyrillic 'а' slipped into one name
    city = bool(re.search(r'\bcity\b|^City of ', en, re.I)) or '(' in en
    base = re.sub(r'^City of\s*|\s*\bcity\b|\s*\(.*?\)', '', en, flags=re.I).strip()
    ru = cyr(base)
    if city: return {'ru': f'г. {ru}', 'uz': f'{base} shahri', 'tr': base, 'en': en}
    return {'ru': f'{ru} р-н', 'uz': f'{base} tumani', 'tr': base, 'en': en}


def rings(geom, tol, nd=3):
    g = geom.simplify(tol, preserve_topology=True)
    polys = [g] if g.geom_type == 'Polygon' else list(g.geoms) if hasattr(g, 'geoms') else []
    out = []
    for p in polys:
        if p.area < tol * tol * 4: continue  # specks
        out.append([[round(x, nd), round(y, nd)] for x, y in p.exterior.coords])
    return out


def main(src, dst):
    src = Path(src); res = {}
    for iso, i3 in ISO3.items():
        A1 = json.load(open(src / f'{i3}_ADM1.geojson'))['features']; A2 = json.load(open(src / f'{i3}_ADM2.geojson'))['features']
        tol1, tol2 = (0.02, 0.012) if iso == 'KZ' else (0.01, 0.006)
        adm1 = []
        for k, f in enumerate(A1):
            en = f['properties']['shapeName']; ru, uz, tr = ADM1.get(en, (en, en, en)); g = shape(f['geometry'])
            adm1.append({'id': k, 'name': {'ru': ru, 'uz': uz, 'tr': tr, 'en': en}, 'c': [round(g.representative_point().x, 3), round(g.representative_point().y, 3)],
                         'r': rings(g, tol1), '_g': g})
        adm2 = []
        for f in A2:
            g = shape(f['geometry']); pt = g.representative_point()
            par = next((a['id'] for a in adm1 if a['_g'].contains(pt)), None)
            if par is None:  # on a border: the region it overlaps most
                par = max(adm1, key=lambda a: a['_g'].intersection(g).area)['id']
            adm2.append({'name': dname(f['properties']['shapeName']), 'p': par, 'c': [round(pt.x, 3), round(pt.y, 3)], 'r': rings(g, tol2)})
        for a in adm1: a.pop('_g')
        res[iso] = {'adm1': adm1, 'adm2': adm2}
        print(iso, len(adm1), 'regions', len(adm2), 'districts', sum(len(r) for a in adm2 for r in a['r']), 'points')
    res['_source'] = 'geoBoundaries gbOpen (CC BY 4.0), www.geoboundaries.org'
    json.dump(res, open(dst, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(dst, Path(dst).stat().st_size // 1024, 'KB')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
