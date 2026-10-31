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
# continents and the whole world (rendered from the 0.5° world grid, glob.npz, with prob/geo_world.json)
# id: (lon0, lon1, lat0, lat1, centre lon, centre lat, utc offset or None = the language's clock, main city per language)
CONT = {
    'world': (-180, 180, -58, 80, 0, 0, None, {'uz': 'Tashkent', 'ru': 'Moscow', 'tr': 'Istanbul'}),
    'EU': (-25, 45, 34, 72, 12, 52, 1, {'uz': 'London', 'ru': 'Moscow', 'tr': 'Istanbul'}),
    'AS': (25, 180, -10, 78, 95, 40, None, {'uz': 'Tashkent', 'ru': 'Novosibirsk', 'tr': 'Tashkent'}),
    'AF': (-20, 55, -36, 38, 18, 2, 2, {'uz': 'Cairo', 'ru': 'Cairo', 'tr': 'Cairo'}),
    'NA': (-170, -50, 7, 75, -100, 45, -5, {'uz': 'New York City', 'ru': 'New York City', 'tr': 'New York City'}),
    'SA': (-85, -33, -56, 13, -60, -20, -3, {'uz': 'São Paulo', 'ru': 'São Paulo', 'tr': 'São Paulo'}),
    'OC': (110, 180, -48, 0, 145, -25, 10, {'uz': 'Sydney', 'ru': 'Sydney', 'tr': 'Sydney'}),
}
CONT_ORDER = ['world', 'EU', 'AS', 'AF', 'NA', 'SA', 'OC']
ORDER = ['cis', 'UZ', 'KZ', 'KG', 'TJ', 'TM', 'AZ', 'AM', 'BY', 'MD', 'RU', 'TR']
CIS = ['UZ', 'KZ', 'KG', 'TJ', 'TM', 'AZ', 'AM', 'BY', 'MD', 'RU', 'TR']

NAMES = {
    'world': {'uz': 'Butun dunyo', 'ru': 'Весь мир', 'tr': 'Tüm dünya'},
    'EU': {'uz': 'Yevropa', 'ru': 'Европа', 'tr': 'Avrupa'}, 'AS': {'uz': 'Osiyo', 'ru': 'Азия', 'tr': 'Asya'},
    'AF': {'uz': 'Afrika', 'ru': 'Африка', 'tr': 'Afrika'}, 'NA': {'uz': 'Shimoliy Amerika', 'ru': 'Северная Америка', 'tr': 'Kuzey Amerika'},
    'SA': {'uz': 'Janubiy Amerika', 'ru': 'Южная Америка', 'tr': 'Güney Amerika'}, 'OC': {'uz': 'Avstraliya va Okeaniya', 'ru': 'Австралия и Океания', 'tr': 'Avustralya ve Okyanusya'},
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
    'London': 'London', 'Cairo': 'Qohira', 'New York City': 'Nyu-York', 'São Paulo': 'San-Paulu', 'Sydney': 'Sidney', 'Paris': 'Parij', 'Berlin': 'Berlin', 'Rome': 'Rim', 'Madrid': 'Madrid',
    'Beijing': 'Pekin', 'Tokyo': 'Tokio', 'Delhi': 'Dehli', 'New Delhi': 'Dehli', 'Mumbai': 'Mumbay', 'Shanghai': 'Shanxay', 'Tehran': 'Tehron', 'Kabul': 'Kobul', 'Riyadh': 'Ar-Riyod', 'Lagos': 'Lagos',
    'Kinshasa': 'Kinshasa', 'Nairobi': 'Nayrobi', 'Johannesburg': 'Yoxannesburg', 'Mexico City': 'Mexiko', 'Los Angeles': 'Los-Anjeles', 'Chicago': 'Chikago', 'Toronto': 'Toronto', 'Buenos Aires': 'Buenos-Ayres',
    'Lima': 'Lima', 'Bogotá': 'Bogota', 'Rio de Janeiro': 'Rio-de-Janeyro', 'Jakarta': 'Jakarta', 'Bangkok': 'Bangkok', 'Seoul': 'Seul', 'Melbourne': 'Melburn', 'Algiers': 'Jazoir', 'Athens': 'Afina', 'Kyiv': 'Kiyev', 'Budapest': 'Budapesht', 'Rabat': 'Rabot', 'Dhaka': 'Dakka', 'Khartoum': 'Xartum', 'Warsaw': 'Varshava', 'Vienna': 'Vena', 'Ankara': 'Anqara', 'Karachi': 'Karachi', 'Lahore': 'Lahor', 'Manila': 'Manila', 'Hanoi': 'Xanoy', 'Auckland': 'Oklend', 'Baghdad': 'Bag‘dod',
}
# whose clock the overview uses for each language
OVERVIEW_TZ = {'uz': 5, 'ru': 3, 'tr': 3}

T = {
    'uz': {
        'title': 'Yog‘ingarchilik bo‘lish ehtimolligi',
        'title_temp': 'Havo harorati (2 m)', 'title_cloud': 'Bulutlilik', 'legend_temp': '{h}lik davrdagi o‘rtacha harorat, °C', 'legend_cloud': 'Umumiy bulutlilik, % (osmonning qancha qismi yopiq)',
        'bars_temp': '{city}: harorat har bir davrda (3–6 soat), °C', 'bars_cloud': '{city}: bulutlilik har bir davrda (3–6 soat), %', 'src_wx': 'Harorat va bulutlar: NOAA GEFS ansambl o‘rtachasi',
        'wd': ['Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan', 'Yak'],
        'rain': 'Yomg‘ir', 'snow': 'Qor', 'clouds': ['Bulutli', 'Qalin bulut'], 'iso': 'Harorat, °C (0° — ko‘k)', 'tline': 'qizil chiziq — harorat',
        'window': '{d1} soat {h1}:00–{h2}:00 ({tz})', 'window2': '{d1} soat {h1}:00 – {d2} soat {h2}:00 ({tz})',
        'legend': '{h}da yog‘ingarchilik (0,2 mm dan ko‘p) bo‘lish ehtimolligi', 'heavy': 'o‘rtacha ≥ 5 mm / {h}',
        'models': 'Modellar: {m}', 'run': 'Prognoz: {run} UTC hisobi', 'bars': '{city}: har bir davr (3–6 soat), %',
        'tz': {5: 'Toshkent vaqti', 3: 'Moskva vaqti'}, 'utc': 'UTC{o:+d}', 'method': 'Teng vaznli multimodel ansambl ({n} a’zo)',
    },
    'ru': {
        'title': 'Вероятность осадков',
        'title_temp': 'Температура воздуха (2 м)', 'title_cloud': 'Облачность', 'legend_temp': 'Средняя температура за {h}, °C', 'legend_cloud': 'Общая облачность, % (какая часть неба закрыта)',
        'bars_temp': '{city}: температура по периодам (3–6 ч), °C', 'bars_cloud': '{city}: облачность по периодам (3–6 ч), %', 'src_wx': 'Температура и облака: среднее ансамбля NOAA GEFS',
        'wd': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
        'rain': 'Дождь', 'snow': 'Снег', 'clouds': ['Облачно', 'Плотная облачность'], 'iso': 'Температура, °C (0° — синяя)', 'tline': 'красная линия — температура',
        'window': '{d1}, {h1}:00–{h2}:00 ({tz})', 'window2': '{d1} {h1}:00 – {d2} {h2}:00 ({tz})',
        'legend': 'Вероятность осадков более 0,2 мм за {h}', 'heavy': 'в среднем ≥ 5 мм за {h}',
        'models': 'Модели: {m}', 'run': 'Прогноз от {run} UTC', 'bars': '{city}: по периодам (3–6 ч), %',
        'tz': {5: 'ташкентское время', 3: 'московское время'}, 'utc': 'UTC{o:+d}', 'method': 'Мультимодельный ансамбль, модели с равным весом ({n} членов)',
    },
    'tr': {
        'title': 'Yağış olasılığı',
        'title_temp': 'Hava sıcaklığı (2 m)', 'title_cloud': 'Bulutluluk', 'legend_temp': '{h}lik ortalama sıcaklık, °C', 'legend_cloud': 'Toplam bulutluluk, % (gökyüzünün kapalı kısmı)',
        'bars_temp': '{city}: dönemlere göre sıcaklık (3–6 saat), °C', 'bars_cloud': '{city}: dönemlere göre bulutluluk (3–6 saat), %', 'src_wx': 'Sıcaklık ve bulutlar: NOAA GEFS topluluk ortalaması',
        'wd': ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'],
        'rain': 'Yağmur', 'snow': 'Kar', 'clouds': ['Bulutlu', 'Yoğun bulut'], 'iso': 'Sıcaklık, °C (0° mavi)', 'tline': 'kırmızı çizgi: sıcaklık',
        'window': '{d1} saat {h1}:00–{h2}:00 ({tz})', 'window2': '{d1} {h1}:00 – {d2} {h2}:00 ({tz})',
        'legend': '{h}te 0,2 mm üzeri yağış olasılığı', 'heavy': 'ortalama ≥ 5 mm / {h}',
        'models': 'Modeller: {m}', 'run': 'Tahmin: {run} UTC çalıştırması', 'bars': '{city}: dönemler (3–6 saat), %',
        'tz': {3: 'TSİ'}, 'utc': 'UTC{o:+d}', 'method': 'Eşit ağırlıklı çoklu model topluluğu ({n} üye)',
    },
}
