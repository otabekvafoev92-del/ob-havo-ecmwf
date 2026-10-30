"""Current (2026) names for places and countries where Natural Earth is outdated or wrong.
Used by tools/make_geo.py and tools/make_prob_geo.py; `python3 tools/names_current.py` patches the built files in place.
Key: Natural Earth English name -> (English, Russian, Turkish or None to keep)."""
import json, pathlib, sys

PLACES = {
    'Nur-Sultan': ('Astana', 'Астана', 'Astana'),
    'Almaty': ('Almaty', 'Алматы', 'Almatı'),
    # Kazakhstan
    'Kapchagay': ('Konaev', 'Конаев', 'Konayev'),            # renamed 2022
    'Jezkazgan': ('Zhezkazgan', 'Жезказган', None),
    'Rudniy': ('Rudny', 'Рудный', 'Rudnıy'),
    'Petropavl': ('Petropavl', 'Петропавловск', 'Petropavl'),
    'Oskemen': ('Oskemen', 'Усть-Каменогорск', 'Öskemen'),
    'Komsomolets': ('Karabalyk', 'Карабалык', None),
    'Chundzha': ('Shonzhy', 'Шонжы', None),
    'Bulayev': ('Bulayevo', 'Булаево', None),
    'Osakarov': ('Osakarovka', 'Осакаровка', None),
    'Bayganin': ('Karauylkeldy', 'Караулкельды', None),
    'Kashyr': ('Kashyr', 'Кашыр', None),
    # Kyrgyzstan / Tajikistan / Turkmenistan
    'Bokhtar': ('Bokhtar', 'Бохтар', 'Bohtar'),              # formerly Kurgan-Tyube
    'Khujand': ('Khujand', 'Худжанд', 'Hucend'),
    'Konibodom': ('Konibodom', 'Канибадам', 'Konibodom'),
    'Kuybyshevsk': ('Abdurahmoni Jomi', 'Абдурахмони Джоми', None),
    'Leninobod': ('Leninobod', 'Ленинобод', None),
    'Abadan Etrap': ('Abadan', 'Абадан', None),
    'Serdar': ('Serdar', 'Сердар', None),
    # Azerbaijan / Armenia
    'Stepanakert': ('Khankendi', 'Ханкенди', 'Hankendi'),    # Azerbaijani name in use since 2023
    'Gədəbəy': ('Gadabay', 'Гедабек', 'Gedebey'),
    'Lankaran': ('Lankaran', 'Ленкорань', 'Lenkeran'),
    'Nakhchivan': ('Nakhchivan', 'Нахчыван', 'Nahçıvan'),
    # Russia (errors in Natural Earth)
    'Buynaksk': ('Buynaksk', 'Буйнакск', None),
    'Çistay': ('Chistopol', 'Чистополь', None),
    'Dombarovsky': ('Dombarovsky', 'Домбаровский', None),
    # Ukraine
    'Odessa': ('Odesa', 'Одесса', 'Odesa'),
    # Iran / Afghanistan
    'Shahrud': ('Shahrud', 'Шахруд', None),
    'Arak': ('Arak', 'Арак', None),
    'Ahwaz': ('Ahvaz', 'Ахваз', None),
    'Zarghun Shar': ('Sharana', 'Шарана', None),
    # China: drop administrative suffixes, fix wrong Russian names
    'Kashgar City': ('Kashgar', 'Кашгар', None), 'Jiayuguan City': ('Jiayuguan', 'Цзяюйгуань', None),
    'Jingmen City': ('Jingmen', 'Цзинмэнь', None), 'Xiantao City': ('Xiantao', 'Сяньтао', None),
    'Altay City': ('Altay', 'Алтай', None), 'Yarkant County': ('Yarkant', 'Яркенд', None),
    'Kuqa County': ('Kuqa', 'Куча', None), 'Qiemo Town': ('Qiemo', 'Черчен', None), 'Nagchu Town': ('Nagqu', 'Нагчу', None),
    'Yining City': ('Yining', 'Инин (Кульджа)', None), 'Jilin City': ('Jilin', 'Гирин', None),
    'Wanzhou': ('Wanzhou', 'Ваньчжоу', None), 'Lianshan': ('Lianshan', 'Ляньшань', None),
    # Mongolia
    'Öndörkhaan': ('Chinggis', 'Чингис', None),              # renamed 2013
}
# fix wrong country codes of single places
PLACE_ISO = {'Kapan': 'AM'}
COUNTRIES = {  # ISO -> (English, Russian)
    'TR': ('Türkiye', 'Турция'), 'CZ': ('Czechia', 'Чехия'), 'TL': ('Timor-Leste', 'Тимор-Лесте'),
    'CI': ("Côte d'Ivoire", 'Кот-д’Ивуар'), 'CV': ('Cabo Verde', 'Кабо-Верде'), 'SZ': ('Eswatini', 'Эсватини'),
    'MK': ('North Macedonia', 'Северная Македония'), 'MM': ('Myanmar', 'Мьянма'),
    'TM': ('Turkmenistan', 'Туркменистан'), 'KG': ('Kyrgyzstan', 'Кыргызстан'), 'MD': ('Moldova', 'Молдова'),
    'BY': ('Belarus', 'Беларусь'), 'KZ': ('Kazakhstan', 'Казахстан'), 'UZ': ('Uzbekistan', 'Узбекистан'),
}


def fix_list_place(x):  # [lon, lat, en, ru, rank, pop, iso, cap]
    if x[2] in PLACE_ISO: x[6] = PLACE_ISO[x[2]]
    if x[2] in PLACES: en, ru, _ = PLACES[x[2]]; x[2], x[3] = en, ru


def fix_dict_place(x):  # {'en', 'ru', 'tr', 'iso', ...}
    if x['en'] in PLACE_ISO: x['iso'] = PLACE_ISO[x['en']]
    if x['en'] in PLACES:
        en, ru, tr = PLACES[x['en']]; x['en'], x['ru'] = en, ru
        if tr: x['tr'] = tr


def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    p = root / 'site/assets/geo.json'; g = json.loads(p.read_text())
    for x in g['places']: fix_list_place(x)
    for c in g.get('cty', []):
        if c[0] in COUNTRIES: c[1], c[2] = COUNTRIES[c[0]]
    p.write_text(json.dumps(g, separators=(',', ':'), ensure_ascii=False))
    q = root / 'prob/geo_prob.json'; h = json.loads(q.read_text())
    for x in h['places']: fix_dict_place(x)
    q.write_text(json.dumps(h, separators=(',', ':'), ensure_ascii=False))
    print('names updated')


if __name__ == '__main__':
    main()
