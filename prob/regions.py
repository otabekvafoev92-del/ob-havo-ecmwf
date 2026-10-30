"""Map areas, time zones and labels for the precipitation-probability product (CIS + Turkey)."""

# id: (ISO focus or None, lon0, lon1, lat0, lat1, central lon, utc offset, capital English name)
REGIONS = {
    'cis': (None, 22, 188, 34, 80, 90, None, None),
    'UZ': ('UZ', 55.0, 74.5, 36.5, 46.2, 64.5, 5, 'Tashkent'),
    'KZ': ('KZ', 45.5, 88.5, 39.5, 56.5, 67.0, 5, 'Astana'),
    'KG': ('KG', 68.5, 81.5, 38.8, 44.0, 75.0, 6, 'Bishkek'),
    'TJ': ('TJ', 66.5, 75.8, 36.2, 41.4, 71.0, 5, 'Dushanbe'),
    'TM': ('TM', 51.5, 67.5, 34.8, 43.3, 59.5, 5, 'Ashgabat'),
    'AZ': ('AZ', 43.8, 51.5, 37.6, 42.4, 47.8, 4, 'Baku'),
    'AM': ('AM', 42.6, 47.2, 38.5, 41.6, 45.0, 4, 'Yerevan'),
    'BY': ('BY', 22.5, 33.5, 50.7, 56.9, 28.0, 3, 'Minsk'),
    'MD': ('MD', 26.2, 30.6, 45.2, 48.7, 28.5, 2, 'Chisinau'),
    'RU': ('RU', 25.0, 188.0, 40.0, 79.0, 95.0, 3, 'Moscow'),
    'TR': ('TR', 25.2, 45.5, 35.3, 42.6, 35.5, 3, 'Ankara'),
}
ORDER = ['cis', 'UZ', 'KZ', 'KG', 'TJ', 'TM', 'AZ', 'AM', 'BY', 'MD', 'RU', 'TR']
CIS = ['UZ', 'KZ', 'KG', 'TJ', 'TM', 'AZ', 'AM', 'BY', 'MD', 'RU', 'TR']

NAMES = {
    'cis': {'uz': 'MDH va Turkiya', 'ru': 'СНГ и Турция', 'tr': 'BDT ve Türkiye'},
    'UZ': {'uz': 'O‘zbekiston', 'ru': 'Узбекистан', 'tr': 'Özbekistan'},
    'KZ': {'uz': 'Qozog‘iston', 'ru': 'Казахстан', 'tr': 'Kazakistan'},
    'KG': {'uz': 'Qirg‘iziston', 'ru': 'Кыргызстан', 'tr': 'Kırgızistan'},
    'TJ': {'uz': 'Tojikiston', 'ru': 'Таджикистан', 'tr': 'Tacikistan'},
    'TM': {'uz': 'Turkmaniston', 'ru': 'Туркменистан', 'tr': 'Türkmenistan'},
    'AZ': {'uz': 'Ozarbayjon', 'ru': 'Азербайджан', 'tr': 'Azerbaycan'},
    'AM': {'uz': 'Armaniston', 'ru': 'Армения', 'tr': 'Ermenistan'},
    'BY': {'uz': 'Belarus', 'ru': 'Беларусь', 'tr': 'Belarus'},
    'MD': {'uz': 'Moldova', 'ru': 'Молдова', 'tr': 'Moldova'},
    'RU': {'uz': 'Rossiya', 'ru': 'Россия', 'tr': 'Rusya'},
    'TR': {'uz': 'Turkiya', 'ru': 'Турция', 'tr': 'Türkiye'},
}
# Uzbek spellings of city names (others use the English / Turkish name)
UZ_CITY = {
    'Tashkent': 'Toshkent', 'Samarkand': 'Samarqand', 'Bukhara': 'Buxoro', 'Andijan': 'Andijon', 'Namangan': 'Namangan',
    'Fergana': 'Farg‘ona', 'Qarshi': 'Qarshi', 'Termez': 'Termiz', 'Navoiy': 'Navoiy', 'Jizzakh': 'Jizzax', 'Guliston': 'Guliston',
    'Urgench': 'Urganch', 'Nukus': 'Nukus', 'Kokand': 'Qo‘qon', 'Moscow': 'Moskva', 'Saint Petersburg': 'Sankt-Peterburg',
    'Almaty': 'Olmaota', 'Astana': 'Astana', 'Bishkek': 'Bishkek', 'Dushanbe': 'Dushanbe', 'Ashgabat': 'Ashxobod', 'Baku': 'Boku',
    'Yerevan': 'Yerevan', 'Minsk': 'Minsk', 'Chisinau': 'Kishinyov', 'Ankara': 'Anqara', 'Istanbul': 'Istanbul', 'Khujand': 'Xo‘jand',
    'Osh': 'O‘sh', 'Shymkent': 'Chimkent', 'Turkistan': 'Turkiston',
}
# whose clock the overview uses for each language
OVERVIEW_TZ = {'uz': 5, 'ru': 3, 'tr': 3}

T = {
    'uz': {
        'title': 'Yog‘ingarchilik bo‘lish ehtimolligi',
        'title_temp': 'Havo harorati (2 m)', 'title_cloud': 'Bulutlilik', 'legend_temp': '6 soatlik davrdagi o‘rtacha harorat, °C', 'legend_cloud': 'Umumiy bulutlilik, % (osmonning qancha qismi yopiq)',
        'bars_temp': '{city}: harorat har 6 soatda, °C', 'bars_cloud': '{city}: bulutlilik har 6 soatda, %', 'src_wx': 'Harorat va bulutlar: NOAA GEFS ansambl o‘rtachasi',
        'wd': ['Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan', 'Yak'],
        'rain': 'Yomg‘ir', 'snow': 'Qor', 'clouds': ['Bulutli', 'Qalin bulut'], 'iso': 'Harorat, °C (0° — ko‘k)', 'tline': 'qizil chiziq — harorat',
        'window': '{d1} soat {h1}:00–{h2}:00 ({tz})', 'window2': '{d1} soat {h1}:00 – {d2} soat {h2}:00 ({tz})',
        'legend': '6 soatda yog‘ingarchilik (0,2 mm dan ko‘p) bo‘lish ehtimolligi', 'heavy': 'o‘rtacha ≥ 5 mm / 6 soat',
        'models': 'Modellar: {m}', 'run': 'Prognoz: {run} UTC hisobi', 'bars': '{city}: har 6 soatlik davr, %',
        'tz': {5: 'Toshkent vaqti', 3: 'Moskva vaqti'}, 'utc': 'UTC{o:+d}', 'method': 'Teng vaznli multimodel ansambl ({n} a’zo)',
    },
    'ru': {
        'title': 'Вероятность осадков',
        'title_temp': 'Температура воздуха (2 м)', 'title_cloud': 'Облачность', 'legend_temp': 'Средняя температура за 6 часов, °C', 'legend_cloud': 'Общая облачность, % (какая часть неба закрыта)',
        'bars_temp': '{city}: температура каждые 6 часов, °C', 'bars_cloud': '{city}: облачность каждые 6 часов, %', 'src_wx': 'Температура и облака: среднее ансамбля NOAA GEFS',
        'wd': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
        'rain': 'Дождь', 'snow': 'Снег', 'clouds': ['Облачно', 'Плотная облачность'], 'iso': 'Температура, °C (0° — синяя)', 'tline': 'красная линия — температура',
        'window': '{d1}, {h1}:00–{h2}:00 ({tz})', 'window2': '{d1} {h1}:00 – {d2} {h2}:00 ({tz})',
        'legend': 'Вероятность осадков более 0,2 мм за 6 часов', 'heavy': 'в среднем ≥ 5 мм / 6 ч',
        'models': 'Модели: {m}', 'run': 'Прогноз от {run} UTC', 'bars': '{city}: каждые 6 часов, %',
        'tz': {5: 'ташкентское время', 3: 'московское время'}, 'utc': 'UTC{o:+d}', 'method': 'Мультимодельный ансамбль, модели с равным весом ({n} членов)',
    },
    'tr': {
        'title': 'Yağış olasılığı',
        'title_temp': 'Hava sıcaklığı (2 m)', 'title_cloud': 'Bulutluluk', 'legend_temp': '6 saatlik ortalama sıcaklık, °C', 'legend_cloud': 'Toplam bulutluluk, % (gökyüzünün kapalı kısmı)',
        'bars_temp': '{city}: 6 saatlik sıcaklık, °C', 'bars_cloud': '{city}: 6 saatlik bulutluluk, %', 'src_wx': 'Sıcaklık ve bulutlar: NOAA GEFS topluluk ortalaması',
        'wd': ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'],
        'rain': 'Yağmur', 'snow': 'Kar', 'clouds': ['Bulutlu', 'Yoğun bulut'], 'iso': 'Sıcaklık, °C (0° mavi)', 'tline': 'kırmızı çizgi: sıcaklık',
        'window': '{d1} saat {h1}:00–{h2}:00 ({tz})', 'window2': '{d1} {h1}:00 – {d2} {h2}:00 ({tz})',
        'legend': '6 saatte 0,2 mm üzeri yağış olasılığı', 'heavy': 'ortalama ≥ 5 mm / 6 saat',
        'models': 'Modeller: {m}', 'run': 'Tahmin: {run} UTC çalıştırması', 'bars': '{city}: 6 saatlik dönemler, %',
        'tz': {3: 'TSİ'}, 'utc': 'UTC{o:+d}', 'method': 'Eşit ağırlıklı çoklu model topluluğu ({n} üye)',
    },
}
