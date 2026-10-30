import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

/* =========================================================================
   Osmon — ECMWF forecast on a 3D globe.
   Weather: charts.ecmwf.int only (global 0.5° + Central Asia ~11 km), see pipeline/.
   Clouds: ECMWF simulated infrared images (charts.ecmwf.int).
   Terrain: open DEM (AWS Terrain Tiles / SRTM), imagery: Sentinel-2 cloudless (EOX) for
   Central Asia, NASA Blue Marble elsewhere; borders and places: Natural Earth.
   ========================================================================= */

const TZ = 5; // Asia/Tashkent, UTC+5
const DEG = Math.PI / 180;
const R = 100, EARTH_M = 6371000;
const MOBILE = matchMedia('(pointer: coarse)').matches || Math.min(screen.width, screen.height) < 700;
const store = {
  get(k, d) { try { const v = localStorage.getItem('osmon.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('osmon.' + k, JSON.stringify(v)); } catch {} },
};
const ASSET = (window.__ASSET_BASE__ || '') ;

/* ------------------------------ i18n ------------------------------ */
const I18N = {
  uz: {
    tagline: 'ECMWF 3D', 'nav.map': '3D globus', 'nav.forecast': 'Prognoz sharhi', 'nav.maps': 'ECMWF xaritalari', 'nav.prob': 'Yog‘in ehtimolligi', 'nav.guide': 'Qo‘llanma', 'nav.about': 'Ma’lumotlar haqida',
    'loc.title': 'Joyni tanlash', 'loc.main': 'Asosiy nuqta', 'loc.compare': 'Taqqoslash', 'loc.search': 'Shahar, davlat yoki 41.31, 69.28', 'loc.mine': '⌖ Mening joylashuvim', 'loc.save': '☆ Saqlash',
    'loc.saved': 'Saqlangan nuqtalar', 'loc.savedEmpty': 'Hali yo‘q. Globusda nuqtani tanlab «Saqlash»ni bosing.', 'loc.src': 'charts.ecmwf.int →',
    'loc.geoFail': 'Joylashuvni aniqlab bo‘lmadi. Shaharni tanlang yoki globusni bosing.', 'loc.cmpHint': 'Ikkinchi nuqtani tanlang (ro‘yxat yoki globus).', 'loc.country': 'davlat', 'loc.here': 'Siz shu yerdasiz', 'bld.proc': 'Binolar shartli (OSM ga ulanib bo‘lmadi)', 'zen.sun': 'Quyosh tik turgan joy', 'zen.moon': 'Oy tik turgan joy',
    'astro.sun': 'Quyosh', 'astro.moon': 'Oy', 'astro.rise': 'chiqishi', 'astro.set': 'botishi', 'astro.elev': 'balandligi', 'astro.lit': 'yoritilgan', 'astro.waxing': 'o‘sib bormoqda', 'astro.waning': 'kamaymoqda', 'loc.geoAsk': 'Joylashuvingiz aniqlanmoqda…',
    'fx.precip': 'Yomg‘ir va qor', 'fx.wind': 'Shamol oqimi', 'lvl.10m': 'Yer usti', 'lvl.850': '1,5 km', 'lvl.500': '5,5 km', 'lvl.250': '10 km',
    'lvl.title': 'Shamol balandligi: yer usti (10 m), 850 gPa (~1,5 km), 500 gPa (~5,5 km), 250 gPa (~10 km, reaktiv oqim)', 'windNow': 'Shamol (ECMWF)', 'dir': ['shim.', 'shim.-sharq', 'sharq', 'jan.-sharq', 'jan.', 'jan.-g‘arb', 'g‘arb', 'shim.-g‘arb'], 'fx.clouds': 'Bulutlar', 'fx.exag': 'Tog‘ balandligi', 'fx.sun': 'Kun va tun', 'fx.borders': 'Chegaralar',
    'view.globe': 'Butun dunyo', 'view.shot': 'Rasmni saqlash', 'view.tour': 'Sayohat: shaharlar bo‘ylab', 'view.fly': 'Nuqtaga uchish', 'view.top': 'Yuqoridan',
    'fx.more': '⚙ Sozlamalar', 'layer.d5': '5D prognoz', 'd5.title': '5D: 15 kunlik multimodel prognoz', 'd5.all': 'Yog‘in + bulut', 'd5.temp': 'Harorat', 'd5.cloud': 'Bulutlar', 'd5.rain': 'yomg‘ir', 'd5.snow': 'qor', 'd5.leg_all': 'Balandlik va rang — 6 soatda yog‘in ehtimoli; tepada — bulutlar', 'd5.leg_temp': 'Balandlik va rang — havo harorati (2 m)', 'd5.leg_cloud': 'Umumiy bulutlilik', 'd5.rec': '🎬 5D videoni yozib olish', 'd5.recStop': '■ To‘xtatish va saqlash', 'd5.recNo': 'Bu brauzer video yozolmaydi', 'd5.saved': 'Saqlandi', 'layer.relief': 'Relyef', 'layer.temp': 'Harorat', 'layer.rain': 'Yog‘in', 'layer.wind': 'Kuchli shamol', 'layer.sun': 'Quyosh',
    'leg.relief': 'Sentinel-2 va NASA sun’iy yo‘ldosh tasviri, relyef', 'leg.temp': '2 m harorat, °C', 'leg.rain': 'So‘nggi 6 soatdagi yog‘in, mm', 'leg.wind': '10 m shamol tezligi, m/s (10 dan yuqori)', 'leg.sun': 'Quyosh nuri davomiyligi, 24 soatda, soat',
    'panel.point': 'Tanlangan nuqta', 'panel.more': 'Batafsil prognoz →',
    'mob.map': '⌖ Globus', 'mob.forecast': '☀ Prognoz', 'mob.menu': '☰ Joylar',
    loading: 'ECMWF ma’lumotlari yuklanmoqda…', loadFail: 'Ma’lumotlarni yuklab bo‘lmadi.',
    temp: 'Harorat', rain6: 'Yog‘in, 6 soat', wind: 'Shamol', sun: 'Quyosh', elev: 'Balandlik', day: 'kunduzi', night: 'tunda', mm: 'mm', h: 'soat', ms: 'm/s', m: 'm',
    noRain: 'yog‘insiz', calm: '< 10 m/s', snow: 'qor', run: 'Model', updated: 'yangilangan', res: 'aniqlik',
    resReg: 'O‘rta Osiyo, ~11 km', resGlo: 'dunyo, ~50 km',
    'fc.title': 'Prognoz sharhi', 'fc.days': '10 kunlik prognoz', 'fc.chart': 'Harorat va yog‘in, har 6 soatda', 'fc.meteo': 'ECMWF ENS meteogrammasi', 'fc.meteoOpen': 'Bu nuqta uchun ECMWF meteogrammasini ochish →',
    'fc.meteoNote': 'Ansambl prognozi: bulutlilik, yog‘in, shamol va harorat ehtimollari. Rasm to‘g‘ridan-to‘g‘ri ECMWF dan.', 'fc.compare': 'Taqqoslash', 'fc.band': 'harorat oralig‘i', 'fc.bars': 'yog‘in, mm/6 soat',
    'fc.noB': 'Taqqoslash uchun chap paneldagi «Taqqoslash» yorlig‘ida ikkinchi nuqtani tanlang.', 'fc.precise': 'Qiymatlar ECMWF xarita shkalasi bo‘yicha oraliq sifatida berilgan.',
    'maps.title': 'ECMWF xaritalari', 'maps.note': 'Asl xaritalar charts.ecmwf.int dan, har kuni 12:00 UTC (17:00 Toshkent) holatiga.', 'maps.empty': 'Bu namoyish versiyasida asl xaritalar yo‘q — ular saytning to‘liq versiyasida GitHub Actions orqali yuklanadi.',
  },
  ru: {
    tagline: 'ECMWF 3D', 'nav.map': '3D-глобус', 'nav.forecast': 'Обзор прогноза', 'nav.maps': 'Карты ECMWF', 'nav.prob': 'Вероятность осадков', 'nav.guide': 'Руководство', 'nav.about': 'О данных',
    'loc.title': 'Выбор места', 'loc.main': 'Основная точка', 'loc.compare': 'Сравнение', 'loc.search': 'Город, страна или 41.31, 69.28', 'loc.mine': '⌖ Моё местоположение', 'loc.save': '☆ Сохранить',
    'loc.saved': 'Сохранённые точки', 'loc.savedEmpty': 'Пока пусто. Выберите точку на глобусе и нажмите «Сохранить».', 'loc.src': 'charts.ecmwf.int →',
    'loc.geoFail': 'Не удалось определить местоположение. Выберите город или нажмите на глобус.', 'loc.cmpHint': 'Выберите вторую точку (в списке или на глобусе).', 'loc.country': 'страна', 'loc.here': 'Вы здесь', 'bld.proc': 'Здания условные (нет доступа к OSM)', 'zen.sun': 'Солнце в зените', 'zen.moon': 'Луна в зените',
    'astro.sun': 'Солнце', 'astro.moon': 'Луна', 'astro.rise': 'восход', 'astro.set': 'заход', 'astro.elev': 'высота', 'astro.lit': 'освещено', 'astro.waxing': 'растёт', 'astro.waning': 'убывает', 'loc.geoAsk': 'Определяем ваше местоположение…',
    'fx.precip': 'Дождь и снег', 'fx.wind': 'Потоки ветра', 'lvl.10m': 'У земли', 'lvl.850': '1,5 км', 'lvl.500': '5,5 км', 'lvl.250': '10 км',
    'lvl.title': 'Высота ветра: у земли (10 м), 850 гПа (~1,5 км), 500 гПа (~5,5 км), 250 гПа (~10 км, струйное течение)', 'windNow': 'Ветер (ECMWF)', 'dir': ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'], 'fx.clouds': 'Облака', 'fx.exag': 'Высота гор', 'fx.sun': 'День и ночь', 'fx.borders': 'Границы',
    'view.globe': 'Весь мир', 'view.shot': 'Сохранить снимок', 'view.tour': 'Экскурсия по городам', 'view.fly': 'Перелететь к точке', 'view.top': 'Сверху',
    'fx.more': '⚙ Настройки', 'layer.d5': '5D-прогноз', 'd5.title': '5D: мультимодельный прогноз на 15 дней', 'd5.all': 'Осадки + облака', 'd5.temp': 'Температура', 'd5.cloud': 'Облачность', 'd5.rain': 'дождь', 'd5.snow': 'снег', 'd5.leg_all': 'Высота и цвет — вероятность осадков за 6 ч; сверху — облака', 'd5.leg_temp': 'Высота и цвет — температура воздуха (2 м)', 'd5.leg_cloud': 'Общая облачность', 'd5.rec': '🎬 Записать 5D-видео', 'd5.recStop': '■ Остановить и сохранить', 'd5.recNo': 'Этот браузер не умеет записывать видео', 'd5.saved': 'Сохранено', 'layer.relief': 'Рельеф', 'layer.temp': 'Температура', 'layer.rain': 'Осадки', 'layer.wind': 'Сильный ветер', 'layer.sun': 'Солнце',
    'leg.relief': 'Спутниковые снимки Sentinel-2 и NASA, рельеф', 'leg.temp': 'Температура 2 м, °C', 'leg.rain': 'Осадки за 6 часов, мм', 'leg.wind': 'Ветер 10 м, м/с (от 10 и выше)', 'leg.sun': 'Солнечное сияние за 24 часа, ч',
    'panel.point': 'Выбранная точка', 'panel.more': 'Подробный прогноз →',
    'mob.map': '⌖ Глобус', 'mob.forecast': '☀ Прогноз', 'mob.menu': '☰ Места',
    loading: 'Загружаем данные ECMWF…', loadFail: 'Не удалось загрузить данные.',
    temp: 'Температура', rain6: 'Осадки, 6 ч', wind: 'Ветер', sun: 'Солнце', elev: 'Высота', day: 'днём', night: 'ночью', mm: 'мм', h: 'ч', ms: 'м/с', m: 'м',
    noRain: 'без осадков', calm: '< 10 м/с', snow: 'снег', run: 'Модель', updated: 'обновлено', res: 'детализация',
    resReg: 'Центральная Азия, ~11 км', resGlo: 'мир, ~50 км',
    'fc.title': 'Обзор прогноза', 'fc.days': 'Прогноз на 10 дней', 'fc.chart': 'Температура и осадки каждые 6 часов', 'fc.meteo': 'Метеограмма ECMWF ENS', 'fc.meteoOpen': 'Открыть метеограмму ECMWF для этой точки →',
    'fc.meteoNote': 'Ансамблевый прогноз: облачность, осадки, ветер и температура с разбросом. Картинка напрямую от ECMWF.', 'fc.compare': 'Сравнение', 'fc.band': 'интервал температуры', 'fc.bars': 'осадки, мм/6 ч',
    'fc.noB': 'Для сравнения выберите вторую точку на вкладке «Сравнение» слева.', 'fc.precise': 'Значения даны интервалами по шкале карт ECMWF.',
    'maps.title': 'Карты ECMWF', 'maps.note': 'Оригинальные карты с charts.ecmwf.int на 12:00 UTC (17:00 по Ташкенту) каждого дня.', 'maps.empty': 'В демо-версии оригинальных карт нет — на полном сайте их загружает GitHub Actions.',
  },
};
const UZ_PLACE = {"Moscow": "Moskva", "Saint Petersburg": "Sankt-Peterburg", "Almaty": "Olmaota", "Ashgabat": "Ashxobod", "Baku": "Boku", "Chișinău": "Kishinyov", "Kyiv": "Kiyev", "Ankara": "Anqara", "Tehran": "Tehron", "Kabul": "Kobul", "Beijing": "Pekin", "Ürümqi": "Urumchi", "Kashgar": "Qashqar", "Herat": "Hirot", "Mazar-i-Sharif": "Mozori Sharif", "Kandahar": "Qandahor", "Kunduz": "Qunduz", "Khujand": "Xo‘jand", "Osh": "O‘sh", "Jalal-Abad": "Jalolobod", "Shymkent": "Chimkent", "Turkistan": "Turkiston", "Taraz": "Taroz", "Kyzylorda": "Qizilo‘rda", "Mary": "Marv", "Türkmenabat": "Turkmanobod", "Daşoguz": "Dashoguz", "Konye-Urgench": "Ko‘hna Urganch", "Kulob": "Ko‘lob", "Istarawshan": "Istaravshan", "Konibodom": "Konibodom", "Tashkent": "Toshkent", "Samarkand": "Samarqand", "Bukhara": "Buxoro", "Andijan": "Andijon", "Fergana": "Farg‘ona", "Kokand": "Qo‘qon", "Termez": "Termiz", "Jizzakh": "Jizzax", "Urgench": "Urganch", "Khiva": "Xiva", "Kagan": "Kogon", "Katta-Kurgan": "Kattaqo‘rg‘on", "Zarafshan": "Zarafshon", "Chirchiq": "Chirchiq", "Olmaliq": "Olmaliq", "Denov": "Denov", "Shahrisabz": "Shahrisabz", "Iskandar": "Iskandar", "Urgut": "Urgut", "Chimboy": "Chimboy", "Mashhad": "Mashhad", "Istanbul": "Istanbul", "Delhi": "Dehli", "Tbilisi": "Tbilisi", "Yerevan": "Yerevan", "Minsk": "Minsk", "Dushanbe": "Dushanbe", "Bishkek": "Bishkek", "Astana": "Astana", "Karakol": "Qoraqo‘l", "Naryn": "Norin", "Talas": "Talas", "Tokmok": "To‘qmoq", "Aral": "Orol", "Kazan": "Qozon", "Astrakhan": "Astraxan", "Orenburg": "Orenburg", "Lahore": "Lahor", "Islamabad": "Islomobod", "Karachi": "Karachi", "Cairo": "Qohira", "Riyadh": "Ar-Riyod", "Mecca": "Makka", "Medina": "Madina", "Dubai": "Dubay", "Baghdad": "Bag‘dod", "Damascus": "Damashq", "Tokyo": "Tokio", "Seoul": "Seul", "London": "London", "Paris": "Parij", "Berlin": "Berlin", "Rome": "Rim", "New York City": "Nyu-York", "Washington, D.C.": "Vashington", "Bamyan": "Bomiyon", "Balkh": "Balx", "Ghazni": "G‘azni", "Nukus": "Nukus", "Navoiy": "Navoiy", "Qarshi": "Qarshi", "Guliston": "Guliston", "Angren": "Angren", "Namangan": "Namangan", "Mo‘ynoq": "Mo‘ynoq", "Qo‘ng‘irot": "Qo‘ng‘irot", "Xo‘jayli": "Xo‘jayli"}; // Uzbek spellings for the globe labels
const CTY_UZ = { UZ: 'O‘zbekiston', KZ: 'Qozog‘iston', KG: 'Qirg‘iziston', TJ: 'Tojikiston', TM: 'Turkmaniston', AF: 'Afg‘oniston', RU: 'Rossiya', TR: 'Turkiya',
  AZ: 'Ozarbayjon', AM: 'Armaniston', GE: 'Gruziya', BY: 'Belarus', UA: 'Ukraina', MD: 'Moldova', CN: 'Xitoy', IN: 'Hindiston', PK: 'Pokiston', IR: 'Eron',
  MN: 'Mo‘g‘uliston', JP: 'Yaponiya', KR: 'Janubiy Koreya', KP: 'Shimoliy Koreya', US: 'AQSH', CA: 'Kanada', MX: 'Meksika', BR: 'Braziliya', AR: 'Argentina',
  GB: 'Buyuk Britaniya', DE: 'Germaniya', FR: 'Fransiya', IT: 'Italiya', ES: 'Ispaniya', PT: 'Portugaliya', PL: 'Polsha', CZ: 'Chexiya', AT: 'Avstriya',
  CH: 'Shveytsariya', NL: 'Niderlandiya', BE: 'Belgiya', SE: 'Shvetsiya', NO: 'Norvegiya', FI: 'Finlandiya', DK: 'Daniya', GR: 'Gretsiya', HU: 'Vengriya',
  RO: 'Ruminiya', BG: 'Bolgariya', RS: 'Serbiya', LT: 'Litva', LV: 'Latviya', EE: 'Estoniya', SA: 'Saudiya Arabistoni', AE: 'BAA', QA: 'Qatar', KW: 'Quvayt',
  IQ: 'Iroq', SY: 'Suriya', JO: 'Iordaniya', IL: 'Isroil', EG: 'Misr', LB: 'Livan', OM: 'Ummon', YE: 'Yaman', ID: 'Indoneziya', MY: 'Malayziya',
  TH: 'Tailand', VN: 'Vyetnam', PH: 'Filippin', BD: 'Bangladesh', NP: 'Nepal', LK: 'Shri-Lanka', AU: 'Avstraliya', NZ: 'Yangi Zelandiya', ZA: 'Janubiy Afrika',
  NG: 'Nigeriya', ET: 'Efiopiya', KE: 'Keniya', MA: 'Marokash', DZ: 'Jazoir', TN: 'Tunis', LY: 'Liviya', SD: 'Sudan', CU: 'Kuba', CL: 'Chili', PE: 'Peru', CO: 'Kolumbiya',
  VE: 'Venesuela', IE: 'Irlandiya', IS: 'Islandiya', SK: 'Slovakiya', SI: 'Sloveniya', HR: 'Xorvatiya', BA: 'Bosniya va Gersegovina', AL: 'Albaniya', MK: 'Shimoliy Makedoniya', CY: 'Kipr', MM: 'Myanma', KH: 'Kambodja', LA: 'Laos', TW: 'Tayvan', SG: 'Singapur' };
const WD = { uz: ['Yak', 'Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan'], ru: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'] };
const MON = { uz: ['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'], ru: ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'] };

const S = {
  lang: store.get('lang', 'uz'),
  layer: store.get('layer', 'temp'),
  t: 0, playing: false, speed: 2, // forecast hours per second
  A: null, B: null, pickTarget: 'A',
  exag: store.get('exag5', 3),
  fxPrecip: true, fxClouds: true, fxWind: true, windLvl: store.get('windLvl', '10m'), fxSun: store.get('sun', true), fxBorders: true,
  route: 'map',
};
const $ = id => document.getElementById(id);
const tr = k => (I18N[S.lang][k] ?? I18N.uz[k] ?? k);

/* ------------------------------ geometry helpers ------------------------------ */
// lon/lat → world position (matches THREE.SphereGeometry uv layout: u=0 at 180°W)
function vecLL(lon, lat, r = R) { const a = lon * DEG, b = lat * DEG; return new THREE.Vector3(r * Math.cos(b) * Math.cos(a), r * Math.sin(b), -r * Math.cos(b) * Math.sin(a)); }
function llVec(v) { const r = v.length(); return [Math.atan2(-v.z, v.x) / DEG, Math.asin(Math.max(-1, Math.min(1, v.y / r))) / DEG]; }
const kM = () => R / EARTH_M * S.exag; // scene units per metre of height

/* ------------------------------ data ------------------------------ */
let D, GEO; // forecast.json, geo.json
const G = { reg: {}, glo: {} };
function unrle(s, n) {
  const out = new Uint8Array(n); let p = 0; const re = /([A-Z])(\d*)/g; let m;
  while ((m = re.exec(s))) { const c = m[2] ? +m[2] : 1; out.fill(m[1].charCodeAt(0) - 65, p, p + c); p += c; }
  return out;
}
// Central Asia grid (polar stereographic, ECMWF "western_asia")
function regRef(lon, lat) {
  const P = D.region.proj, r = P.k * Math.tan(DEG * (45 - lat / 2)), a = DEG * (lon - P.lon0);
  return [P.x0 + r * Math.sin(a), P.y0 + r * Math.cos(a)];
}
function regCell(lon, lat) { const [X, Y] = regRef(lon, lat), g = D.region.grid; return [(X - g.X0) / g.CELL, (Y - g.Y0) / g.CELL]; }
function inReg(lon, lat) { const [gx, gy] = regCell(lon, lat), g = D.region.grid; return gx >= 0.5 && gy >= 0.5 && gx < g.GW - 0.5 && gy < g.GH - 0.5; }
function refToLL(X, Y) {
  const P = D.region.proj, dx = X - P.x0, dy = Y - P.y0, r = Math.hypot(dx, dy) / P.k;
  return [P.lon0 + Math.atan2(dx, dy) / DEG, 90 - 2 * Math.atan(r) / DEG];
}
// which grid + index to sample for a point
function cellOf(lon, lat) {
  if (inReg(lon, lat)) { const [gx, gy] = regCell(lon, lat), g = D.region.grid; return { src: 'reg', i: Math.min(g.GH - 1, Math.floor(gy)) * g.GW + Math.min(g.GW - 1, Math.floor(gx)) }; }
  const g = D.global.grid; const x = Math.floor((((lon + 180) % 360 + 360) % 360) / g.D), y = Math.min(g.H - 1, Math.max(0, Math.floor((90 - lat) / g.D)));
  return { src: 'glo', i: y * g.W + Math.min(g.W - 1, x) };
}

function prepare() {
  for (const [src, grid] of [['reg', D.region.grid], ['glo', D.global.grid]]) {
    const n = src === 'reg' ? grid.GW * grid.GH : grid.W * grid.H;
    const layers = src === 'reg' ? D.region.layers : D.global.layers;
    G[src].missing = {};
    for (const [key, L] of Object.entries(layers)) {
      const arr = L.frames.map(f => (f ? unrle(f, n) : null));
      for (let i = 0; i < arr.length; i++) if (!arr[i]) arr[i] = arr[i - 1] || arr.find(Boolean);
      if (!arr[0]) { G[src].missing[key] = true; for (let i = 0; i < arr.length; i++) arr[i] = new Uint8Array(n); }
      G[src][key] = arr;
    }
  }
  G.missing = { ...G.glo.missing };
  G.tMax = D.global.layers.temp.steps.at(-1);
}

/* ---------- terrain heights (CPU copies for labels, borders, particles) ---------- */
const DEM = {};
async function loadImageData(url) {
  const img = new Image(); img.src = url; await img.decode();
  const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight;
  const g = c.getContext('2d', { willReadFrequently: true }); g.drawImage(img, 0, 0);
  return { W: c.width, H: c.height, d: g.getImageData(0, 0, c.width, c.height).data };
}
async function loadDem() {
  const [w, ca] = await Promise.all([loadImageData(ASSET + 'assets/dem-world.png'), loadImageData(ASSET + 'assets/dem-ca.png')]);
  const wf = new Float32Array(w.W * w.H);
  for (let i = 0; i < wf.length; i++) { const v = w.d[i * 4]; wf[i] = v >= 64 ? ((v - 64) / 191) ** 2 * 8848 : -(((63 - v) / 63) ** 2) * 11000; }
  DEM.w = { W: w.W, H: w.H, f: wf };
  const cf = new Float32Array(ca.W * ca.H);
  // 4 m steps: h = (R·256 + G)·4 − 1000
  for (let i = 0; i < cf.length; i++) cf[i] = (ca.d[i * 4] * 256 + ca.d[i * 4 + 1]) * 4 - 1000;
  DEM.ca = { W: ca.W, H: ca.H, f: cf };
}
function bil(M, x, y) {
  x = Math.max(0, Math.min(M.W - 1.001, x)); y = Math.max(0, Math.min(M.H - 1.001, y));
  const ix = x | 0, iy = y | 0, ax = x - ix, ay = y - iy, W = M.W, f = M.f;
  return (f[iy * W + ix] * (1 - ax) + f[iy * W + ix + 1] * ax) * (1 - ay) + (f[(iy + 1) * W + ix] * (1 - ax) + f[(iy + 1) * W + ix + 1] * ax) * ay;
}
// height in metres of the displayed surface (sea level for oceans, Caspian level for the Caspian)
function heightAt(lon, lat) {
  if (inReg(lon, lat)) {
    const [X, Y] = regRef(lon, lat), g = D.region.grid;
    const sc = DEM.ca.W / g.W;
    return Math.max(-28, bil(DEM.ca, (X - g.X0) * sc - 0.5, (Y - g.Y0) * sc - 0.5));
  }
  const u = (((lon + 180) % 360 + 360) % 360) / 360 * DEM.w.W - 0.5, v = (90 - lat) / 180 * DEM.w.H - 0.5;
  return Math.max(0, bil(DEM.w, u, v));
}
const surfR = (lon, lat) => R + heightAt(lon, lat) * kM();

/* ------------------------------ formatting ------------------------------ */
const sgn = v => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v);
const fmtT = c => (c ? `${sgn(c.lo)}…${sgn(c.hi)}°` : '—');
const fmtTshort = c => (c ? `${sgn(c.lo)}…${sgn(c.hi)}` : '—');
const r1 = v => (v < 10 ? Math.round(v * 10) / 10 : Math.round(v));
const runDate = () => Date.parse(D.run);
const timeAt = t => new Date(runDate() + t * 3600e3);
function localParts(d) { const l = new Date(d.getTime() + TZ * 3600e3); return { y: l.getUTCFullYear(), m: l.getUTCMonth(), d: l.getUTCDate(), wd: l.getUTCDay(), h: l.getUTCHours(), key: l.toISOString().slice(0, 10) }; }
function fmtTime(t) { const p = localParts(timeAt(t)); return `${WD[S.lang][p.wd]}, ${p.d} ${MON[S.lang][p.m]} · ${String(p.h).padStart(2, '0')}:00`; }
function fmtDay(key) { const d = new Date(key + 'T12:00:00Z'); return { wd: WD[S.lang][d.getUTCDay()], dm: `${d.getUTCDate()} ${MON[S.lang][d.getUTCMonth()]}` }; }
const fmtLL = (lat, lon) => `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lon).toFixed(2)}°${lon >= 0 ? 'E' : 'W'}`;
const fmtElev = (lon, lat) => { const h = heightAt(lon, lat); return h <= 0 && !inReg(lon, lat) ? '0 ' + tr('m') : `${Math.round(h / 10) * 10} ${tr('m')}`; };
const rgbCss = c => (c ? `rgb(${c[0]},${c[1]},${c[2]})` : 'transparent');
const pname = p => p[S.lang] || p.uz || p.ru;

/* ------------------------------ sampling & point forecasts ------------------------------ */
function frameAt(key, t) {
  const st = D.global.layers[key].steps;
  if (key === 'sun') { let i = st.findIndex(s => s >= t); if (i < 0) i = st.length - 1; return { i0: i, i1: i, f: 0 }; }
  if (t <= st[0]) return { i0: 0, i1: 0, f: 0 };
  for (let i = 0; i < st.length - 1; i++) if (t >= st[i] && t <= st[i + 1]) return { i0: i, i1: i + 1, f: (t - st[i]) / (st[i + 1] - st[i]) };
  return { i0: st.length - 1, i1: st.length - 1, f: 0 };
}
const cls = (key, k) => D.classes[key][k];
function valueAt(key, t, lon, lat) {
  const c = cellOf(lon, lat), fr = frameAt(key, t), k = G[c.src][key][fr.f < 0.5 ? fr.i0 : fr.i1][c.i];
  return { k, ...cls(key, k) };
}
function series(p) {
  const c = cellOf(p.lon, p.lat), out = {};
  for (const key of ['temp', 'rain', 'wind', 'sun']) {
    const L = D.global.layers[key];
    out[key] = L.steps.map((s, j) => { const k = G[c.src][key][j][c.i]; return { step: s, time: L.times[j], k, ...cls(key, k) }; });
  }
  out.src = c.src;
  return out;
}
function daily(sr) {
  const days = new Map();
  const day = k => { if (!days.has(k)) days.set(k, { key: k, tDay: null, tNight: null, rain: [0, 0], rainAny: false, wind: 0, sun: null, snow: false }); return days.get(k); };
  const lk = iso => localParts(new Date(iso)).key;
  for (const s of sr.temp) {
    const h = new Date(s.time).getUTCHours(), D0 = day(lk(s.time));
    if (h === 6 || h === 12) { if (!D0.tDay || s.k > D0.tDay.k) D0.tDay = s; }
    if (h === 0) { if (!D0.tNight || s.k < D0.tNight.k) D0.tNight = s; }
  }
  sr.rain.forEach(s => {
    const D0 = day(lk(new Date(Date.parse(s.time) - 3 * 3600e3).toISOString()));
    if (s.k > 0) { D0.rain[0] += s.lo; D0.rain[1] += s.hi; D0.rainAny = true; const t = sr.temp.find(x => x.step === s.step); if (t && t.hi <= 0) D0.snow = true; }
  });
  for (const s of sr.wind) { const D0 = day(lk(s.time)); if (s.k) D0.wind = Math.max(D0.wind, s.lo); }
  if (!G.missing.sun) for (const s of sr.sun) { const D0 = day(lk(new Date(Date.parse(s.time) - 12 * 3600e3).toISOString())); D0.sun = s; }
  return [...days.values()].filter(d => d.tDay && d.tNight).sort((a, b) => a.key.localeCompare(b.key));
}

/* ------------------------------ sun position ------------------------------ */
function subsolar(date) {
  const d = (date.getTime() - Date.UTC(2000, 0, 1, 12)) / 864e5;
  const g = (357.529 + 0.98560028 * d) * DEG, q = 280.459 + 0.98564736 * d;
  const L = (q + 1.915 * Math.sin(g) + 0.020 * Math.sin(2 * g)) * DEG, e = (23.439 - 0.00000036 * d) * DEG;
  const dec = Math.asin(Math.sin(e) * Math.sin(L));
  const ra = Math.atan2(Math.cos(e) * Math.sin(L), Math.cos(L)) / DEG;
  let eqt = (q - ra) % 360; if (eqt > 180) eqt -= 360; if (eqt < -180) eqt += 360; // degrees
  const utcH = date.getUTCHours() + date.getUTCMinutes() / 60 + date.getUTCSeconds() / 3600;
  let lon = -15 * (utcH - 12) - eqt; lon = ((lon + 540) % 360) - 180;
  return [lon, dec / DEG];
}

// Moon: low-precision ephemeris (≈0.3°), enough to place it in the sky and get its phase
function moonInfo(date) {
  const d = (date.getTime() - Date.UTC(2000, 0, 1, 12)) / 864e5;
  const L = (218.316 + 13.176396 * d) * DEG, M = (134.963 + 13.064993 * d) * DEG, F = (93.272 + 13.229350 * d) * DEG;
  const D_ = (297.850 + 12.190749 * d) * DEG, Ms = (357.529 + 0.98560028 * d) * DEG;
  const lam = L + (6.289 * Math.sin(M) + 1.274 * Math.sin(2 * D_ - M) + 0.658 * Math.sin(2 * D_) + 0.214 * Math.sin(2 * M) - 0.186 * Math.sin(Ms)) * DEG;
  const bet = (5.128 * Math.sin(F)) * DEG, e = 23.439 * DEG;
  const ra = Math.atan2(Math.sin(lam) * Math.cos(e) - Math.tan(bet) * Math.sin(e), Math.cos(lam));
  const dec = Math.asin(Math.sin(bet) * Math.cos(e) + Math.cos(bet) * Math.sin(e) * Math.sin(lam));
  const gmst = (280.46061837 + 360.98564736629 * d) % 360;
  let lon = ra / DEG - gmst; lon = ((lon % 360) + 540) % 360 - 180;
  // phase from the Sun–Moon elongation
  const [slon, slat] = subsolar(date), sv = vecLL(slon, slat, 1), mv = vecLL(lon, dec / DEG, 1);
  const elong = Math.acos(Math.max(-1, Math.min(1, sv.dot(mv))));
  const lit = (1 - Math.cos(elong)) / 2;
  return { lon, lat: dec / DEG, lit, waxing: sunMoonWaxing(date) };
}
function sunMoonWaxing(date) { // the Moon's ecliptic longitude runs ahead of the Sun's by 0–180° while waxing
  const d = (date.getTime() - Date.UTC(2000, 0, 1, 12)) / 864e5;
  const Ls = (280.459 + 0.98564736 * d) % 360, Lm = (218.316 + 13.176396 * d + 6.289 * Math.sin((134.963 + 13.064993 * d) * DEG)) % 360;
  return ((Lm - Ls) % 360 + 360) % 360 < 180;
}
// sun elevation (degrees) at a place and time
function sunElev(lat, lon, date) { const [a, b] = subsolar(date); return Math.asin(Math.max(-1, Math.min(1, vecLL(lon, lat, 1).dot(vecLL(a, b, 1))))) / DEG; }
function sunTimes(lat, lon, date) { // sunrise / sunset of the local (UTC+5) day of `date`
  const lp = localParts(date), base = Date.UTC(lp.y, lp.m, lp.d) - TZ * 3600e3;
  let rise = null, set = null, prev = sunElev(lat, lon, new Date(base));
  for (let m = 10; m <= 1440; m += 10) {
    const t = base + m * 60e3, e = sunElev(lat, lon, new Date(t));
    if (prev < -0.833 && e >= -0.833) rise = t - 10 * 60e3 * (e + 0.833) / (e - prev);
    if (prev >= -0.833 && e < -0.833) set = t - 10 * 60e3 * (e + 0.833) / (e - prev);
    prev = e;
  }
  return { rise, set };
}

/* ------------------------------ shaders ------------------------------ */
const COMMON = /* glsl */`
  #define DEG 0.017453292519943295
  uniform usampler2D uA; uniform usampler2D uB; uniform sampler2D uPal;
  uniform float uMix; uniform float uRow; uniform float uAlpha;
  uniform vec3 uSun; uniform float uSunOn; uniform float uK; uniform float uKL;
  uniform sampler2D uDay; uniform sampler2D uNight; uniform float uHaze;
  uniform vec3 uMoon; uniform float uMoonLit; uniform float uTime;
  float hash(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
  float noise(vec3 p){ vec3 i = floor(p), f = fract(p); vec3 u = f*f*(3.0-2.0*f);
    return mix(mix(mix(hash(i), hash(i+vec3(1,0,0)), u.x), mix(hash(i+vec3(0,1,0)), hash(i+vec3(1,1,0)), u.x), u.y),
               mix(mix(hash(i+vec3(0,0,1)), hash(i+vec3(1,0,1)), u.x), mix(hash(i+vec3(0,1,1)), hash(i+vec3(1,1,1)), u.x), u.y), u.z); }
  float fbm(vec3 p){ float v = 0.0, a = 0.5; for (int i = 0; i < 5; i++){ v += a * noise(p); p *= 2.07; a *= 0.5; } return v; }
  float gWater = 0.0; float gDepth = 50.0; vec3 gW = vec3(0.0);
  vec4 pal(uint k){ return texelFetch(uPal, ivec2(int(k), int(uRow)), 0); }
  vec3 enuEast(float lon){ return vec3(-sin(lon*DEG), 0.0, -cos(lon*DEG)); }
  vec3 enuNorth(float lon, float lat){ return vec3(-sin(lat*DEG)*cos(lon*DEG), cos(lat*DEG), sin(lat*DEG)*sin(lon*DEG)); }
  // ---- clouds (ECMWF simulated IR → density 0..1) ----
  uniform sampler2D uCGA; uniform sampler2D uCGB; uniform sampler2D uCRA; uniform sampler2D uCRB;
  uniform float uCMix; uniform float uCOn; uniform float uCHasR; uniform float uCShift; uniform vec4 uCProj; uniform vec4 uCReg;
  vec2 cRef(float lon, float lat){ float r = uCProj.y * tan(DEG * (45.0 - lat * 0.5)); float a = DEG * (lon - uCProj.x); return vec2(uCProj.z + r * sin(a), uCProj.w + r * cos(a)); }
  float cloudAt(float lon, float lat){
    vec2 uvG = vec2(fract((lon + 180.0) / 360.0), clamp((lat + 90.0) / 180.0, 0.001, 0.999));
    float g = mix(texture(uCGA, uvG).r, texture(uCGB, uvG).r, uCMix);
    if (uCHasR > 0.5 && lat > 20.0 && lat < 60.0) {
      vec2 t = (cRef(lon, lat) - uCReg.xy) / uCReg.zw; vec2 e = min(t, 1.0 - t);
      float w = smoothstep(0.0, 0.05, min(e.x, e.y));
      if (w > 0.0) { vec2 tt = vec2(t.x, 1.0 - t.y); g = mix(g, mix(texture(uCRA, tt).r, texture(uCRB, tt).r, uCMix), w); }
    }
    return g;
  }
  float cloudShadow(float lon, float lat, vec3 n){
    if (uCOn < 0.5 || uSunOn < 0.5) return 1.0;
    float mu = dot(n, uSun); if (mu < 0.0) return 1.0;
    float d = uCShift / max(mu, 0.2);
    float dlat = d * dot(uSun, enuNorth(lon, lat)) / DEG, dlon = d * dot(uSun, enuEast(lon)) / DEG / max(cos(lat * DEG), 0.05);
    return 1.0 - 0.6 * smoothstep(0.08, 0.6, cloudAt(lon + dlon, lat + dlat));
  }
  float gShadow = 1.0;
  vec3 haze(vec3 col, vec3 wpos, vec3 n){
    if (uHaze <= 0.0) return col;
    float d = length(cameraPosition - wpos);
    float f = 1.0 - exp(-max(0.0, d * uHaze - 1.0) * 0.18);
    float day = uSunOn > 0.5 ? smoothstep(-0.1, 0.25, dot(n, uSun)) : 1.0;
    return mix(col, mix(vec3(0.015, 0.025, 0.05), vec3(0.64, 0.76, 0.92), day), f * 0.8);
  }
  vec3 shadeAll(vec3 albedo, vec3 n, vec3 N, vec2 uvImg, vec4 wx){
    vec3 L = uSunOn > 0.5 ? uSun : normalize(cameraPosition);
    float lam = max(dot(N, L), 0.0) * gShadow;
    float slope = max(dot(N, n), 0.0);
    float day = uSunOn > 0.5 ? smoothstep(-0.12, 0.22, dot(n, uSun)) : 1.0;
    vec3 lit = albedo * (0.28 + 1.0 * lam) * mix(0.85, 1.0, slope);
    vec3 V = normalize(cameraPosition - gW);
    if (gWater > 0.0) {
      // water: wind-ruffled surface, sky reflection (Fresnel) and the sun glitter
      float dist = length(cameraPosition - gW);
      float amp = 0.10 * (1.0 - smoothstep(0.3, 8.0, dist)) + 0.025;
      vec3 q = gW * 900.0 + vec3(uTime * 0.6, 0.0, uTime * 0.4), q2 = gW * 3600.0 + vec3(-uTime * 1.1, uTime * 0.7, 0.0);
      vec3 pert = vec3(noise(q) - 0.5, noise(q + 17.3) - 0.5, noise(q + 41.7) - 0.5) + 0.5 * vec3(noise(q2) - 0.5, noise(q2 + 9.1) - 0.5, noise(q2 + 23.9) - 0.5);
      vec3 Nw = normalize(n + amp * (pert - n * dot(pert, n)));
      float fres = 0.02 + 0.98 * pow(1.0 - max(dot(Nw, V), 0.0), 5.0);
      vec3 deep = vec3(0.012, 0.045, 0.09), shallow = vec3(0.05, 0.22, 0.26);
      vec3 body = mix(shallow, deep, smoothstep(5.0, 120.0, gDepth));
      body = mix(body, albedo, 0.35);
      vec3 skyc = mix(vec3(0.02, 0.03, 0.06), vec3(0.55, 0.7, 0.9), day);
      vec3 H = normalize(L + V);
      float spec = pow(max(dot(Nw, H), 0.0), 600.0) * 4.0 + pow(max(dot(Nw, H), 0.0), 90.0) * 0.12;
      vec3 wcol = body * (0.35 + 0.65 * lam) + skyc * fres * 0.6 + vec3(1.0, 0.92, 0.75) * spec * gShadow * step(0.0, dot(n, L));
      lit = mix(lit, wcol, gWater);
    }
    vec3 col = mix(lit, wx.rgb, wx.a * uAlpha * (0.55 + 0.45 * lam));
    float ml = max(dot(N, uMoon), 0.0) * uMoonLit * step(0.0, dot(n, uMoon));
    vec3 night = texture(uNight, uvImg).rgb * vec3(1.0, 0.85, 0.6) * 1.3 + albedo * (0.05 + 0.32 * ml) * vec3(0.75, 0.85, 1.1);
    if (gWater > 0.0) { vec3 H2 = normalize(uMoon + V); vec3 Nm = n; night += vec3(0.8, 0.85, 1.0) * pow(max(dot(Nm, H2), 0.0), 300.0) * 2.0 * uMoonLit * gWater * step(0.0, dot(n, uMoon)); }
    night = mix(night, wx.rgb * 0.35, wx.a * uAlpha * 0.8);
    return mix(night, col, day);
  }`;

const GLOBE_VERT = /* glsl */`
  uniform sampler2D uDemW; uniform float uKV;
  out vec2 vUv; out vec3 vN; out vec3 vW;
  void main(){
    vUv = uv;
    vec3 n = normalize(position);
    float h = max(textureLod(uDemW, vec2(uv.x, 1.0 - uv.y), 0.0).r, 0.0);
    vec3 p = n * (${R.toFixed(1)} + h * uKV);
    vN = n;
    vec4 w = modelMatrix * vec4(p, 1.0); vW = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }`;
const GLOBE_FRAG = /* glsl */`
  precision highp float; precision highp usampler2D;
  ${COMMON}
  uniform sampler2D uDemW; uniform vec2 uDemSize; uniform vec2 uGSize;
  uniform vec4 uProj; uniform vec4 uReg; uniform float uPatchOn;
  in vec2 vUv; in vec3 vN; in vec3 vW;
  out vec4 outColor;
  vec4 cellColor(vec2 c){
    vec2 f = c - 0.5; ivec2 i0 = ivec2(floor(f)); vec2 w = fract(f); int W = int(uGSize.x), H = int(uGSize.y);
    ivec2 a = ivec2((i0.x + W) % W, clamp(i0.y, 0, H - 1)), b = ivec2((i0.x + 1 + W) % W, a.y);
    ivec2 cc = ivec2(a.x, clamp(i0.y + 1, 0, H - 1)), d = ivec2(b.x, cc.y);
    vec4 A = mix(mix(pal(texelFetch(uA, a, 0).r), pal(texelFetch(uA, b, 0).r), w.x), mix(pal(texelFetch(uA, cc, 0).r), pal(texelFetch(uA, d, 0).r), w.x), w.y);
    vec4 B = mix(mix(pal(texelFetch(uB, a, 0).r), pal(texelFetch(uB, b, 0).r), w.x), mix(pal(texelFetch(uB, cc, 0).r), pal(texelFetch(uB, d, 0).r), w.x), w.y);
    return mix(A, B, uMix);
  }
  void main(){
    float lon = vUv.x * 360.0 - 180.0, lat = vUv.y * 180.0 - 90.0;
    if (uPatchOn > 0.5) {
      float r = uProj.y * tan(DEG * (45.0 - lat * 0.5)); float a = DEG * (lon - uProj.x);
      vec2 X = vec2(uProj.z + r * sin(a), uProj.w + r * cos(a));
      if (X.x > uReg.x + 1.0 && X.y > uReg.y + 1.0 && X.x < uReg.x + uReg.z - 1.0 && X.y < uReg.y + uReg.w - 1.0) discard;
    }
    vec2 t = vec2(vUv.x, 1.0 - vUv.y);
    vec2 px = 1.0 / uDemSize;
    float hE = max(texture(uDemW, t + vec2(px.x, 0.0)).r, 0.0), hW = max(texture(uDemW, t - vec2(px.x, 0.0)).r, 0.0);
    float hN = max(texture(uDemW, t - vec2(0.0, px.y)).r, 0.0), hS = max(texture(uDemW, t + vec2(0.0, px.y)).r, 0.0);
    float mx = 6371000.0 * 6.2831853 * max(cos(lat * DEG), 0.03) / uDemSize.x, my = 6371000.0 * 3.1415926 / uDemSize.y;
    vec3 n = normalize(vN);
    vec3 N = normalize(n - ((hE - hW) / (2.0 * mx)) * uKL * enuEast(lon) - ((hN - hS) / (2.0 * my)) * uKL * enuNorth(lon, lat));
    vec3 albedo = texture(uDay, vUv).rgb;
    vec4 wx = uAlpha > 0.0 ? cellColor(vec2((lon + 180.0) * 2.0, (90.0 - lat) * 2.0)) : vec4(0.0);
    if (wx.a > 0.0) wx.rgb /= wx.a;
    gShadow = cloudShadow(lon, lat, n);
    float h0 = texture(uDemW, t).r;
    gWater = 1.0 - smoothstep(-30.0, 2.0, h0); gDepth = -h0; gW = vW;
    outColor = vec4(haze(shadeAll(albedo, n, N, vUv, wx), vW, n), 1.0);
  }`;

const PATCH_VERT = /* glsl */`
  in vec3 aDir; in float aH; in vec2 aLL; in vec2 aRef;
  uniform float uKV;
  out vec2 vLL; out vec2 vRef; out vec3 vN; out vec3 vW;
  void main(){
    vLL = aLL; vRef = aRef; vN = aDir;
    vec3 p = aDir * (${R.toFixed(1)} + aH * uKV);
    vec4 w = modelMatrix * vec4(p, 1.0); vW = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }`;
const PATCH_FRAG = /* glsl */`
  precision highp float; precision highp usampler2D;
  ${COMMON}
  uniform sampler2D uDemC; uniform vec4 uReg; uniform vec2 uGSize; uniform float uMPerRef; uniform sampler2D uS2; uniform float uS2On;
  in vec2 vLL; in vec2 vRef; in vec3 vN; in vec3 vW;
  out vec4 outColor;
  vec4 cellColor(vec2 c){
    vec2 f = c - 0.5; ivec2 i0 = ivec2(floor(f)); vec2 w = fract(f); ivec2 mx = ivec2(uGSize) - 1;
    ivec2 a = clamp(i0, ivec2(0), mx), b = clamp(i0 + ivec2(1, 0), ivec2(0), mx), cc = clamp(i0 + ivec2(0, 1), ivec2(0), mx), d = clamp(i0 + ivec2(1, 1), ivec2(0), mx);
    vec4 A = mix(mix(pal(texelFetch(uA, a, 0).r), pal(texelFetch(uA, b, 0).r), w.x), mix(pal(texelFetch(uA, cc, 0).r), pal(texelFetch(uA, d, 0).r), w.x), w.y);
    vec4 B = mix(mix(pal(texelFetch(uB, a, 0).r), pal(texelFetch(uB, b, 0).r), w.x), mix(pal(texelFetch(uB, cc, 0).r), pal(texelFetch(uB, d, 0).r), w.x), w.y);
    return mix(A, B, uMix);
  }
  void main(){
    float lon = vLL.x, lat = vLL.y;
    vec2 t = (vRef - uReg.xy) / uReg.zw;
    vec2 px = 1.0 / vec2(textureSize(uDemC, 0));
    float hE = max(texture(uDemC, t + vec2(px.x, 0.0)).r, -28.0), hW = max(texture(uDemC, t - vec2(px.x, 0.0)).r, -28.0);
    float hS = max(texture(uDemC, t + vec2(0.0, px.y)).r, -28.0), hN = max(texture(uDemC, t - vec2(0.0, px.y)).r, -28.0);
    // ref-frame axes: +x ≈ east rotated by (lon − lon0), +y ≈ south (polar stereographic, pole up)
    float rot = (lon - ${'${LON0}'}) * DEG;
    vec3 n = normalize(vN), e = enuEast(lon), no = enuNorth(lon, lat);
    vec3 ax = normalize(cos(rot) * e - sin(rot) * no), ay = normalize(-sin(rot) * e - cos(rot) * no);
    float d = 2.0 * uMPerRef * px.x * uReg.z; // metres between the two samples (2 texels)
    vec3 N = normalize(n - ((hE - hW) / d) * uKL * ax - ((hS - hN) / d) * uKL * ay);
    vec2 uvImg = vec2((lon + 180.0) / 360.0, (lat + 90.0) / 180.0);
    vec2 eg = min(t, 1.0 - t);
    float wS = uS2On * smoothstep(0.0, 0.025, min(eg.x, eg.y));
    vec3 albedo = texture(uDay, uvImg).rgb;
    if (wS > 0.0) albedo = mix(albedo, pow(texture(uS2, vec2(t.x, 1.0 - t.y)).rgb, vec3(1.08)) * 0.95, wS);
    vec4 wx = uAlpha > 0.0 ? cellColor((vRef - uReg.xy) / 2.0) : vec4(0.0);
    if (wx.a > 0.0) wx.rgb /= wx.a;
    gShadow = cloudShadow(lon, lat, n);
    // water: sea level (Caspian) or flat ground that the satellite image shows as dark blue (lakes, reservoirs)
    float h0 = texture(uDemC, t).r;
    vec3 sc = wS > 0.0 ? texture(uS2, vec2(t.x, 1.0 - t.y)).rgb : albedo;
    float flat_ = 1.0 - smoothstep(12.0, 40.0, abs(hE - hW) + abs(hN - hS));
    float blue = smoothstep(0.01, 0.05, sc.b - sc.r) * (1.0 - smoothstep(0.24, 0.4, dot(sc, vec3(0.333))));
    gWater = max(1.0 - smoothstep(-27.5, -20.0, h0), blue * flat_ * wS);
    gDepth = h0 < -27.0 ? 30.0 : 25.0; gW = vW;
    outColor = vec4(haze(shadeAll(albedo, n, N, uvImg, wx), vW, n), 1.0);
  }`;

const CLOUD_VERT = /* glsl */`
  out vec3 vP;
  void main(){ vP = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
// One shell of the cloud deck. Density c (0..1) comes from ECMWF's simulated IR image: the colder
// the cloud top, the higher it reaches (top ≈ 1 + 10·c km). Each shell shows the clouds whose tops reach
// its height, so towers stand above the layer, and mountains rise through low cloud.
const CLOUD_FRAG = /* glsl */`
  precision highp float; precision highp usampler2D;
  ${COMMON}
  uniform float uH; uniform float uOp;
  in vec3 vP; out vec4 outColor;
  // a cloud column reaches from ~1 km up to its top (colder IR top = higher); every shell is one slice
  // of that volume, with 3-D noise that changes with height, so the stack reads as real cumulus and cloud decks
  float colTop(float c){ return 1.0 + c * 10.5; }
  void main(){
    vec3 n = normalize(vP);
    float lat = asin(clamp(n.y, -1.0, 1.0)) / DEG, lon = atan(-n.z, n.x) / DEG;
    float c = cloudAt(lon, lat);
    if (c < 0.015) discard;
    vec3 wp = n * 220.0 + vec3(uTime * 0.004, uH * 0.9, uTime * 0.003);
    float big = fbm(wp * 0.35), det = fbm(wp * 1.6 + big * 2.0);
    float billow = 1.0 - abs(det * 2.0 - 1.0);  // puffy, rounded cells
    float dens = c * (0.55 + 0.9 * big) + (billow - 0.5) * 0.35 * smoothstep(0.05, 0.5, c);
    float top = colTop(clamp(dens, 0.0, 1.0));
    float base = 1.0 + max(0.0, top - 9.0) * 0.6;
    float a = smoothstep(uH - 0.9, uH + 0.6, top) * smoothstep(base - 1.0, base + 0.3, uH);
    a *= smoothstep(0.02, 0.25, dens);
    if (a < 0.004) discard;
    // light: tops brighter, bases darker; shadow from the cloud standing toward the sun
    float hf = clamp((uH - base) / max(0.8, top - base), 0.0, 1.0);
    vec3 e = enuEast(lon), no = enuNorth(lon, lat);
    vec3 L = uSunOn > 0.5 ? uSun : normalize(cameraPosition);
    float dd = 0.12 / max(cos(lat * DEG), 0.1);
    float toward = cloudAt(lon + dd * dot(L, e) * 2.0, lat + 0.12 * dot(L, no) * 2.0);
    float shadow = smoothstep(0.1, 0.7, toward) * (1.0 - hf) * 0.55;
    float cE = cloudAt(lon + dd, lat), cN = cloudAt(lon, lat + 0.12);
    vec3 N = normalize(n * 0.6 - ((cE - c) * e + (cN - c) * no) * 6.0 - (det - 0.5) * 0.9 * (e + no * 0.7));
    float lam = max(dot(N, L), 0.0);
    float day = uSunOn > 0.5 ? smoothstep(-0.12, 0.16, dot(n, uSun)) : 1.0;
    vec3 col = vec3(1.0) * (0.42 + 0.75 * lam) * mix(0.62, 1.08, hf) * (1.0 - shadow);
    col = mix(col * vec3(0.86, 0.9, 0.97), col, hf);                       // bluish grey bellies
    float rim = pow(1.0 - abs(dot(normalize(cameraPosition - n * length(cameraPosition)), n)), 3.0);
    col += vec3(1.0, 0.95, 0.85) * rim * 0.15 * lam;                     // silver lining
    float low = uSunOn > 0.5 ? smoothstep(0.28, 0.0, dot(n, uSun)) : 0.0;
    col *= mix(vec3(1.0), vec3(1.0, 0.7, 0.5), low * 0.7);
    vec3 night = vec3(0.07, 0.085, 0.13) * (0.5 + 0.5 * hf) + vec3(0.6, 0.65, 0.8) * 0.12 * uMoonLit * max(dot(N, uMoon), 0.0);
    outColor = vec4(mix(night, col, day), clamp(a * uOp, 0.0, 1.0) * uCOn);
  }`;
const ATMO_VERT = /* glsl */`out vec3 vN; out vec3 vW; void main(){ vN = normalize(mat3(modelMatrix) * normal); vec4 w = modelMatrix * vec4(position,1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const ATMO_FRAG = /* glsl */`precision highp float; in vec3 vN; in vec3 vW; out vec4 outColor; uniform vec3 uSun; uniform float uSunOn;
  void main(){ vec3 v = normalize(cameraPosition - vW); float rim = 1.0 - abs(dot(vN, v)); float f = pow(rim, 2.6);
    float mu = dot(normalize(vW), uSun);
    float day = uSunOn > 0.5 ? smoothstep(-0.35, 0.35, mu) : 1.0;
    float dusk = uSunOn > 0.5 ? exp(-mu * mu * 28.0) : 0.0;              // band along the day/night line
    float fwd = uSunOn > 0.5 ? pow(max(dot(-v, uSun), 0.0), 6.0) : 0.0;  // forward scattering when looking towards the sun
    vec3 sky = mix(vec3(0.30, 0.55, 1.0), vec3(0.55, 0.78, 1.0), pow(rim, 6.0));
    vec3 col = sky * (0.08 + day) + vec3(1.0, 0.45, 0.18) * dusk * 0.9 + vec3(1.0, 0.85, 0.6) * fwd * 0.6;
    float a = f * clamp(0.12 + day + dusk * 0.7, 0.0, 1.0);
    outColor = vec4(col * f * 1.3, a); }`;
const LINE_VERT = /* glsl */`in vec3 aDir; in float aH; uniform float uKV; uniform float uLift;
  void main(){ vec3 p = aDir * (${R.toFixed(1)} + aH * uKV + uLift); gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(p, 1.0); }`;
const LINE_FRAG = /* glsl */`precision highp float; uniform vec3 uColor; uniform float uOpacity; out vec4 outColor; void main(){ outColor = vec4(uColor, uOpacity); }`;

/* ------------------------------ scene ------------------------------ */
let renderer, scene, camera, controls, globe, patch, clouds, atmo, raycaster;
const tex = {}, mats = {}, lines = {};
const LAYER_ROWS = { temp: 0, rain: 1, wind: 2, sun: 3 };
const LAYER_ALPHA = { relief: 0, temp: 0.62, rain: 0.92, wind: 0.85, sun: 0.6 };
function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

function classTexture(arr, W, H) {
  const t = new THREE.DataTexture(arr, W, H, THREE.RedIntegerFormat, THREE.UnsignedByteType);
  t.internalFormat = 'R8UI'; t.minFilter = t.magFilter = THREE.NearestFilter; t.unpackAlignment = 1; t.needsUpdate = true;
  return t;
}
function floatTexture(f, W, H) {
  const h = new Uint16Array(f.length);
  for (let i = 0; i < f.length; i++) h[i] = THREE.DataUtils.toHalfFloat(f[i]);
  const t = new THREE.DataTexture(h, W, H, THREE.RedFormat, THREE.HalfFloatType);
  t.minFilter = t.magFilter = THREE.LinearFilter; t.wrapS = THREE.RepeatWrapping; t.unpackAlignment = 2; t.needsUpdate = true;
  return t;
}
function buildPalette() {
  const W = 32, data = new Uint8Array(W * 4 * 4);
  for (const [key, row] of Object.entries(LAYER_ROWS)) D.classes[key].forEach((c, i) => { const o = (row * W + i) * 4; data.set(c.rgb ? [c.rgb[0], c.rgb[1], c.rgb[2], 255] : [0, 0, 0, 0], o); });
  const t = new THREE.DataTexture(data, W, 4, THREE.RGBAFormat); t.minFilter = t.magFilter = THREE.NearestFilter; t.needsUpdate = true;
  return t;
}
async function loadTex(url) {
  const t = await new THREE.TextureLoader().loadAsync(url);
  t.colorSpace = THREE.NoColorSpace; t.anisotropy = 8; t.minFilter = THREE.LinearMipmapLinearFilter;
  return t;
}

async function initScene() {
  const canvas = $('scene');
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, logarithmicDepthBuffer: false });
  renderer.setPixelRatio(Math.min(devicePixelRatio, MOBILE ? 1.5 : 2));
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(40, 1, 0.02, 4000);
  raycaster = new THREE.Raycaster();

  const [day, night, stars, s2] = await Promise.all([loadTex(ASSET + 'assets/earth.jpg'), loadTex(ASSET + 'assets/night.jpg'), loadTex(ASSET + 'assets/stars.jpg'), loadTex(ASSET + 'assets/s2-ca.jpg').catch(() => null)]);
  tex.day = day; tex.night = night; tex.s2 = s2;
  if (s2) { s2.anisotropy = renderer.capabilities.getMaxAnisotropy(); s2.wrapS = s2.wrapT = THREE.ClampToEdgeWrapping; }
  tex.demW = floatTexture(DEM.w.f, DEM.w.W, DEM.w.H);
  tex.demC = floatTexture(DEM.ca.f, DEM.ca.W, DEM.ca.H); tex.demC.wrapS = THREE.ClampToEdgeWrapping;
  tex.pal = buildPalette();
  const gW = D.global.grid.W, gH = D.global.grid.H, rg = D.region.grid;
  tex.blankG = classTexture(new Uint8Array(gW * gH), gW, gH);
  tex.blankR = classTexture(new Uint8Array(rg.GW * rg.GH), rg.GW, rg.GH);

  initCloudUniforms();
  const common = () => ({
    uA: { value: null }, uB: { value: null }, uPal: { value: tex.pal }, uMix: { value: 0 }, uRow: { value: 0 }, uAlpha: { value: 0 },
    uSun: { value: new THREE.Vector3(1, 0, 0) }, uSunOn: { value: 1 }, uK: { value: kM() }, uKL: { value: 1 }, uKV: { value: kM() },
    uDay: { value: tex.day }, uNight: { value: tex.night }, uHaze: CU.uHaze, ...CU,
  });
  // stars
  const sky = new THREE.Mesh(new THREE.SphereGeometry(1800, 48, 24), new THREE.MeshBasicMaterial({ map: stars, side: THREE.BackSide, color: 0x8899aa, depthWrite: false }));
  sky.renderOrder = -2; scene.add(sky); SKY.stars = sky;
  initSky();
  // globe
  const segs = MOBILE ? [384, 192] : [720, 360];
  mats.globe = new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3, vertexShader: GLOBE_VERT, fragmentShader: GLOBE_FRAG,
    uniforms: { ...common(), uDemW: { value: tex.demW }, uDemSize: { value: new THREE.Vector2(DEM.w.W, DEM.w.H) }, uGSize: { value: new THREE.Vector2(gW, gH) },
      uProj: { value: new THREE.Vector4(D.region.proj.lon0, D.region.proj.k, D.region.proj.x0, D.region.proj.y0) },
      uReg: { value: new THREE.Vector4(rg.X0, rg.Y0, rg.W, rg.H) }, uPatchOn: { value: 1 } },
  });
  mats.globe.uniforms.uA.value = mats.globe.uniforms.uB.value = tex.blankG;
  globe = new THREE.Mesh(new THREE.SphereGeometry(R, segs[0], segs[1]), mats.globe);
  scene.add(globe);
  // Central Asia high-detail patch
  buildPatch(common());
  // atmosphere
  mats.atmo = new THREE.ShaderMaterial({ glslVersion: THREE.GLSL3, vertexShader: ATMO_VERT, fragmentShader: ATMO_FRAG, transparent: true, depthWrite: false, side: THREE.BackSide, blending: THREE.AdditiveBlending,
    uniforms: { uSun: { value: new THREE.Vector3(1, 0, 0) }, uSunOn: { value: 1 } } });
  atmo = new THREE.Mesh(new THREE.SphereGeometry(R * 1.035, 96, 48), mats.atmo); scene.add(atmo);
  // clouds: a few shells at real heights (km), drawn bottom to top
  clouds = new THREE.Group(); scene.add(clouds);
  const cgeo = new THREE.SphereGeometry(R, MOBILE ? 256 : 384, MOBILE ? 128 : 192);
  mats.clouds = [];
  CLOUD_SHELLS.forEach(([h, op], i) => {
    const m = new THREE.ShaderMaterial({ glslVersion: THREE.GLSL3, vertexShader: CLOUD_VERT, fragmentShader: CLOUD_FRAG, transparent: true, depthWrite: false, side: THREE.DoubleSide,
      uniforms: { ...common(), uH: { value: h }, uOp: { value: op } } });
    const mesh = new THREE.Mesh(cgeo, m); mesh.renderOrder = 3 + i; mesh.userData.h = h; clouds.add(mesh); mats.clouds.push(m);
  });
  buildBorders();
  initPrecip();
  initBuildings();
  initLightning();
  if (D.wind && !windLevels().includes(S.windLvl)) S.windLvl = windLevels()[0];
  initWind();
  updateExag();
  setupPointer();
  new ResizeObserver(resize).observe($('sceneWrap')); resize();
  setGlobeControls(vecLL(S.A ? S.A.lon : 64, S.A ? Math.max(-60, Math.min(60, S.A.lat - 8)) : 32, R * 2.7));
}

function buildPatch(uniforms) {
  const rg = D.region.grid;
  const NX = MOBILE ? 441 : 991, NY = MOBILE ? 241 : 541;
  const n = NX * NY;
  const dir = new Float32Array(n * 3), aH = new Float32Array(n), aLL = new Float32Array(n * 2), aRef = new Float32Array(n * 2);
  const v = new THREE.Vector3();
  for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
    const X = rg.X0 + i * rg.W / (NX - 1), Y = rg.Y0 + j * rg.H / (NY - 1), k = j * NX + i;
    const [lon, lat] = refToLL(X, Y);
    v.copy(vecLL(lon, lat, 1)); dir.set([v.x, v.y, v.z], k * 3);
    const sc = DEM.ca.W / rg.W;
    let h = Math.max(-28, bil(DEM.ca, (X - rg.X0) * sc - 0.5, (Y - rg.Y0) * sc - 0.5));
    if (i === 0 || j === 0 || i === NX - 1 || j === NY - 1) h -= 2500; // skirt hides the seam with the globe
    aH[k] = h; aLL.set([lon, lat], k * 2); aRef.set([X, Y], k * 2);
  }
  const idx = new Uint32Array((NX - 1) * (NY - 1) * 6); let p = 0;
  for (let j = 0; j < NY - 1; j++) for (let i = 0; i < NX - 1; i++) { const a = j * NX + i, b = a + 1, c = a + NX, d = c + 1; idx.set([a, c, b, b, c, d], p); p += 6; }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(dir.slice(), 3));
  geo.setAttribute('aDir', new THREE.BufferAttribute(dir, 3));
  geo.setAttribute('aH', new THREE.BufferAttribute(aH, 1));
  geo.setAttribute('aLL', new THREE.BufferAttribute(aLL, 2));
  geo.setAttribute('aRef', new THREE.BufferAttribute(aRef, 2));
  geo.setIndex(new THREE.BufferAttribute(idx, 1));
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), R * 1.2);
  // metres per reference-frame pixel at the region centre (polar stereographic scale near 40°N)
  const mPerRef = (() => { const [l1, b1] = refToLL(930, 580), [l2, b2] = refToLL(931, 580); const a = vecLL(l1, b1, EARTH_M), b = vecLL(l2, b2, EARTH_M); return a.distanceTo(b); })();
  mats.patch = new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3, vertexShader: PATCH_VERT, fragmentShader: PATCH_FRAG.replace("${LON0}", D.region.proj.lon0.toFixed(6)),
    uniforms: { ...uniforms, uDemC: { value: tex.demC }, uReg: { value: new THREE.Vector4(rg.X0, rg.Y0, rg.W, rg.H) }, uGSize: { value: new THREE.Vector2(rg.GW, rg.GH) }, uMPerRef: { value: mPerRef },
      uS2: { value: tex.s2 || tex.day }, uS2On: { value: tex.s2 ? 1 : 0 } },
  });
  mats.patch.uniforms.uA.value = mats.patch.uniforms.uB.value = tex.blankR;
  patch = new THREE.Mesh(geo, mats.patch); patch.frustumCulled = false;
  scene.add(patch);
}

/* ---------- borders (Natural Earth) ---------- */
function decodeLine(arr) { const pts = []; let x = 0, y = 0; for (let i = 0; i < arr.length; i += 2) { x += arr[i]; y += arr[i + 1]; pts.push([x / 100, y / 100]); } return pts; }
function buildLineLayer(list, maxStep) {
  const dirs = [], hs = [];
  const v = new THREE.Vector3();
  for (const enc of list) {
    const pts = decodeLine(enc);
    let prev = null;
    for (const p of pts) {
      if (prev) {
        let dlon = p[0] - prev[0]; if (Math.abs(dlon) > 180) { prev = p; continue; } // skip dateline jumps
        const steps = Math.max(1, Math.ceil(Math.max(Math.abs(dlon), Math.abs(p[1] - prev[1])) / maxStep));
        let a = prev;
        for (let s = 1; s <= steps; s++) {
          const b = [prev[0] + dlon * s / steps, prev[1] + (p[1] - prev[1]) * s / steps];
          for (const q of [a, b]) { v.copy(vecLL(q[0], q[1], 1)); dirs.push(v.x, v.y, v.z); hs.push(Math.max(0, heightAt(q[0], q[1]))); }
          a = b;
        }
      }
      prev = p;
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(dirs), 3));
  g.setAttribute('aDir', new THREE.BufferAttribute(new Float32Array(dirs), 3));
  g.setAttribute('aH', new THREE.BufferAttribute(new Float32Array(hs), 1));
  g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), R * 1.2);
  return g;
}
function buildBorders() {
  const mk = (geo, color, op) => {
    const m = new THREE.ShaderMaterial({ glslVersion: THREE.GLSL3, vertexShader: LINE_VERT, fragmentShader: LINE_FRAG, transparent: true, depthWrite: false,
      uniforms: { uKV: { value: kM() }, uLift: { value: 0.03 }, uColor: { value: new THREE.Color(color) }, uOpacity: { value: op } } });
    const l = new THREE.LineSegments(geo, m); l.frustumCulled = false; l.renderOrder = 2; scene.add(l); return l;
  };
  lines.countries = mk(buildLineLayer(GEO.countries, 0.5), 0xffffff, 0.75);
  lines.admin1 = mk(buildLineLayer(GEO.admin1, 0.25), 0xe8e2c8, 0.0);
  lines.urban = mk(buildLineLayer(GEO.urban, 0.05), 0xffb35c, 0.0);
}

/* ---------- buildings: real footprints from OpenStreetMap when close to the ground ---------- */
const BLD = { tiles: new Map(), loading: false, last: 0, src: null };
function initBuildings() {
  BLD.group = new THREE.Group(); scene.add(BLD.group);
  BLD.mat = new THREE.MeshLambertMaterial({ vertexColors: true });
  BLD.sun = new THREE.DirectionalLight(0xfff2dd, 1.5); BLD.sky = new THREE.HemisphereLight(0xcfe0ff, 0x6b5a48, 0.8);
  scene.add(BLD.sun, BLD.sky);
  BLD.attr = document.createElement('div'); BLD.attr.className = 'osm-attr'; BLD.attr.hidden = true; $('sceneWrap').appendChild(BLD.attr);
}
function bldHeight(t, rnd) {
  const num = v => { const x = parseFloat(String(v || '').replace(',', '.')); return isFinite(x) ? x : null; };
  const h = num(t.height); if (h) return Math.min(h, 400);
  const lv = num(t['building:levels']); if (lv) return Math.min(lv * 3.1 + 1.5, 400);
  const b = t.building;
  if (['house', 'detached', 'bungalow', 'semidetached_house', 'hut', 'shed', 'garage', 'garages', 'cabin'].includes(b)) return 4 + rnd * 3;
  if (['apartments', 'residential', 'dormitory', 'hotel'].includes(b)) return 12 + rnd * 18;
  if (['commercial', 'office', 'retail', 'public', 'civic', 'government', 'hospital', 'university', 'school', 'college'].includes(b)) return 10 + rnd * 12;
  if (['industrial', 'warehouse', 'factory', 'hangar'].includes(b)) return 8 + rnd * 5;
  if (['mosque', 'church', 'cathedral', 'temple'].includes(b)) return 14 + rnd * 8;
  return 5 + rnd * 7;
}
function buildingMesh(polys, lon0, lat0) {
  // polys: [{ring: [[lon,lat],…], h: metres, kind}] → one merged mesh in a local frame at (lon0, lat0)
  const s = R / EARTH_M, kx = Math.cos(lat0 * DEG) * 111320, ky = 110574;
  const n = vecLL(lon0, lat0, 1), e = new THREE.Vector3(-Math.sin(lon0 * DEG), 0, -Math.cos(lon0 * DEG));
  const no = new THREE.Vector3(-Math.sin(lat0 * DEG) * Math.cos(lon0 * DEG), Math.cos(lat0 * DEG), Math.sin(lat0 * DEG) * Math.sin(lon0 * DEG));
  const pos = [], col = [];
  const P = (x, y, z) => { pos.push(e.x * x * s + no.x * y * s + n.x * z, e.y * x * s + no.y * y * s + n.y * z, e.z * x * s + no.z * y * s + n.z * z); };
  const C = (c, k) => { for (let i = 0; i < k; i++) col.push(c.r, c.g, c.b); };
  const wall = new THREE.Color(), roof = new THREE.Color();
  const k = kM();
  for (const b of polys) {
    let pts = b.ring.map(([lo, la]) => new THREE.Vector2((lo - lon0) * kx, (la - lat0) * ky));
    if (pts.length > 2 && pts[0].distanceTo(pts[pts.length - 1]) < 0.01) pts.pop();
    if (pts.length < 3) continue;
    if (THREE.ShapeUtils.isClockWise(pts)) pts.reverse();
    const [clon, clat] = b.ring[0];
    const base = heightAt(clon, clat) * k - 25 * s, top = heightAt(clon, clat) * k + b.h * s;
    const tint = 0.86 + ((b.ring.length * 7919) % 100) / 700;
    wall.setRGB(0.86 * tint, 0.81 * tint, 0.74 * tint); roof.setRGB(0.58 * tint, 0.56 * tint, 0.55 * tint);
    if (b.kind === 'proc') { wall.setRGB(0.82 * tint, 0.82 * tint, 0.84 * tint); }
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i], c = pts[(i + 1) % pts.length];
      P(a.x, a.y, base); P(c.x, c.y, base); P(c.x, c.y, top); P(a.x, a.y, base); P(c.x, c.y, top); P(a.x, a.y, top); C(wall, 6);
    }
    const tri = THREE.ShapeUtils.triangulateShape(pts, []);
    for (const t of tri) { for (const j of t) P(pts[j].x, pts[j].y, top + 0.15 * s); C(roof, 3); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.computeVertexNormals();
  const m = new THREE.Mesh(g, BLD.mat); m.position.copy(n.clone().multiplyScalar(R)); m.frustumCulled = false;
  return m;
}
async function fetchOsm(w, s_, e, n_) {
  const q = `[out:json][timeout:25];way["building"](${s_.toFixed(4)},${w.toFixed(4)},${n_.toFixed(4)},${e.toFixed(4)});out geom qt 12000;`;
  for (const host of ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']) {
    try {
      const ctl = new AbortController(); const tm = setTimeout(() => ctl.abort(), 25000);
      const r = await fetch(host + '?data=' + encodeURIComponent(q), { signal: ctl.signal }); clearTimeout(tm);
      if (!r.ok) continue;
      const j = await r.json();
      return j.elements.filter(x => x.geometry && x.geometry.length > 3).map(x => ({ ring: x.geometry.map(g => [g.lon, g.lat]), h: bldHeight(x.tags || {}, ((x.id * 2654435761) % 1000) / 1000), kind: x.tags && x.tags.building }));
    } catch (err) { /* try the next server */ }
  }
  return null;
}
// fallback when OpenStreetMap cannot be reached: illustrative blocks inside the city outline (Natural Earth)
function procBuildings(w, s_, e, n_) {
  const rings = [];
  for (const enc of GEO.urban) { const pts = decodeLine(enc); if (pts.some(([x, y]) => x > w - 0.2 && x < e + 0.2 && y > s_ - 0.2 && y < n_ + 0.2)) rings.push(pts); }
  if (!rings.length) return [];
  const inside = (x, y) => rings.some(r => { let c = false; for (let i = 0, j = r.length - 1; i < r.length; j = i++) { const [xi, yi] = r[i], [xj, yj] = r[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; });
  const out = [], step = 0.0011, cx = (w + e) / 2, cy = (s_ + n_) / 2;
  for (let y = s_; y < n_; y += step) for (let x = w; x < e; x += step / Math.cos(cy * DEG)) {
    const rnd = Math.abs(Math.sin(x * 12.9898 + y * 78.233) * 43758.5453) % 1;
    if (rnd < 0.35 || !inside(x, y)) continue;
    const r2 = Math.abs(Math.sin(x * 93.989 + y * 67.345) * 24634.6345) % 1, r3 = Math.abs(Math.sin(x * 41.3 + y * 17.9) * 9137.31) % 1;
    const d = Math.hypot((x - cx) * Math.cos(cy * DEG), y - cy) / 0.02, sz = 0.00012 + r2 * 0.00028, ln = sz * (1 + r3 * 1.6);
    const ox = x + (r2 - 0.5) * step * 0.5 / Math.cos(cy * DEG), oy = y + (r3 - 0.5) * step * 0.5, a = r3 * Math.PI;
    const ca = Math.cos(a), sa = Math.sin(a), k = 1 / Math.cos(cy * DEG);
    const pt = (u, v) => [ox + (u * ca - v * sa) * k, oy + (u * sa + v * ca)];
    out.push({ ring: [pt(-ln / 2, -sz / 2), pt(ln / 2, -sz / 2), pt(ln / 2, sz / 2), pt(-ln / 2, sz / 2)], h: 4 + rnd * 8 + (r2 > 0.85 ? Math.max(0, 45 - d * 10) * r3 : 0), kind: 'proc' });
    if (out.length > 5000) return out;
  }
  return out;
}
async function loadBuildings(lon, lat) {
  const key = `${(lon / 0.04).toFixed(0)}_${(lat / 0.04).toFixed(0)}`;
  if (BLD.tiles.has(key)) return;
  BLD.loading = true;
  const cx = Math.round(lon / 0.04) * 0.04, cy = Math.round(lat / 0.04) * 0.04, hy = 0.024, hx = hy / Math.cos(cy * DEG);
  let polys = await fetchOsm(cx - hx, cy - hy, cx + hx, cy + hy), src = 'osm';
  if (!polys) { polys = procBuildings(cx - hx, cy - hy, cx + hx, cy + hy); src = 'proc'; }
  BLD.src = src;
  if (polys.length) {
    const m = buildingMesh(polys, cx, cy); m.userData.k = kM();
    BLD.group.add(m); BLD.tiles.set(key, m);
    if (BLD.tiles.size > 6) { const [k0, m0] = BLD.tiles.entries().next().value; BLD.group.remove(m0); m0.geometry.dispose(); BLD.tiles.delete(k0); }
  } else BLD.tiles.set(key, null);
  BLD.loading = false;
}
function updateBuildings(now) {
  if (!BLD.group) return;
  const alt = mode === 'local' && !fly ? camera.position.distanceTo(controls.target) : 1e9;
  const near = alt < 0.16 && S.route === 'map';
  BLD.group.visible = near; BLD.attr.hidden = !near || !BLD.src;
  if (near) BLD.attr.textContent = BLD.src === 'osm' ? '© OpenStreetMap' : tr('bld.proc');
  if (!near) return;
  const [slon, slat] = subsolar(timeAt(S.t)), sv = vecLL(slon, slat, 1), up = controls.target.clone().normalize();
  const el = up.dot(sv);
  BLD.sun.position.copy(sv).multiplyScalar(1000); BLD.sun.target.position.set(0, 0, 0);
  BLD.sun.intensity = S.fxSun ? Math.max(0, Math.min(1.6, el * 4)) : 1.4; BLD.sky.intensity = S.fxSun ? 0.15 + 0.75 * Math.max(0, Math.min(1, (el + 0.1) * 4)) : 0.9;
  // rebuild when the relief scale changed
  for (const [k, m] of BLD.tiles) if (m && m.userData.k !== kM()) { BLD.group.remove(m); m.geometry.dispose(); BLD.tiles.delete(k); }
  if (BLD.loading || now - BLD.last < 700) return;
  BLD.last = now;
  const [lon, lat] = llVec(controls.target);
  loadBuildings(lon, lat);
}

/* ---------- picture of the current view, and a guided tour ---------- */
async function snapshot() {
  renderer.render(scene, camera); // read the canvas in the same task as the render
  const blob = await new Promise(r => $('scene').toBlob(r, 'image/png'));
  const p = localParts(timeAt(S.t)), name = `osmon-${p.key}-${String(p.h).padStart(2, '0')}00.png`;
  try {
    if (window.claude && window.claude.use) { const dl = await window.claude.use('downloads'); if (dl) { await dl.save({ filename: name, data: blob }); return; } }
  } catch (e) { if (e && e.code === 'declined') return; }
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); a.remove();
}
// tour: fly over the region's cities while the forecast plays (each stop ~7 s)
const TOUR = { on: false, i: 0, timer: 0 };
const TOUR_STOPS = [['Toshkent', 69.27, 41.31, 4.5], ['Chimyon', 70.0, 41.55, 1.6], ['Farg‘ona', 71.78, 40.38, 3], ['Pomir', 72.5, 38.7, 6], ['Samarqand', 66.96, 39.65, 3.2], ['Buxoro', 64.42, 39.77, 3.5], ['Orol', 59.6, 45.0, 9], ['Kaspiy', 51.0, 41.5, 10], ['Olmaota', 76.9, 43.24, 4], ['Issiqko‘l', 77.3, 42.45, 5]];
function startTour() { TOUR.on = true; TOUR.i = 0; $('viewTour').setAttribute('aria-pressed', 'true'); setPlaying(true); nextStop(); }
function stopTour() { TOUR.on = false; clearTimeout(TOUR.timer); $('viewTour').setAttribute('aria-pressed', 'false'); }
function nextStop() {
  if (!TOUR.on) return;
  const [nm, lon, lat, dist] = TOUR_STOPS[TOUR.i++ % TOUR_STOPS.length];
  flyTo(lon, lat, { dist, tilt: 1.12 }); showMsg('▶ ' + nm);
  TOUR.timer = setTimeout(nextStop, 7000);
}

/* ---------- lightning: flashes inside deep convective clouds with heavy rain ---------- */
const LIGHT = { flashes: [], next: 0 };
function initLightning() {
  const tex = glowTexture([[0, 'rgba(235,240,255,1)'], [0.15, 'rgba(200,215,255,0.8)'], [1, 'rgba(150,170,255,0)']]);
  LIGHT.pool = Array.from({ length: 6 }, () => { const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0 })); sp.renderOrder = 12; scene.add(sp); return sp; });
}
function stepLightning(now) {
  if (!LIGHT.pool) return;
  for (const sp of LIGHT.pool) sp.material.opacity = Math.max(0, sp.material.opacity - 0.12);
  if (!S.fxClouds || S.route !== 'map' || now < LIGHT.next) return;
  LIGHT.next = now + 250 + Math.random() * 900;
  // pick a random raining cell near the view with heavy rain (≥ class 4 ≈ 10 mm/6 h)
  const fr = frameAt('rain', S.t), rain = G.glo.rain[fr.f < 0.5 ? fr.i0 : fr.i1]; if (!rain) return;
  const { W, D: d } = D.global.grid;
  const look = (mode === 'local' ? controls.target.clone() : camera.position.clone()).normalize();
  const alt = mode === 'local' ? camera.position.distanceTo(controls.target) : camera.position.length() - R;
  const cosA = Math.cos(Math.min(1.1, Math.max(0.05, alt / R * 1.1)));
  for (let t = 0; t < 40; t++) {
    const i = (Math.random() * rain.length) | 0; if (rain[i] < 4) continue;
    const lon = -180 + ((i % W) + Math.random()) * d, lat = 90 - (Math.floor(i / W) + Math.random()) * d, v = vecLL(lon, lat, 1);
    if (v.dot(look) < cosA) continue;
    const sp = LIGHT.pool[(Math.random() * LIGHT.pool.length) | 0];
    sp.position.copy(v.multiplyScalar(R + 6000 * kM())); sp.scale.setScalar(Math.max(0.15, alt * 0.08)); sp.material.opacity = 1;
    break;
  }
}

/* ---------- Sun, Moon, their zenith points, sky colour ---------- */
const SKY = {};
function glowTexture(stops) {
  const c = document.createElement('canvas'); c.width = c.height = 256; const g = c.getContext('2d');
  const grd = g.createRadialGradient(128, 128, 0, 128, 128, 128); stops.forEach(([o, col]) => grd.addColorStop(o, col));
  g.fillStyle = grd; g.fillRect(0, 0, 256, 256); return new THREE.CanvasTexture(c);
}
const MOON_FRAG = /* glsl */`precision highp float; uniform vec3 uSunDir; in vec3 vN; in vec3 vP; out vec4 outColor;
  float h(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
  float n3(vec3 p){ vec3 i = floor(p), f = fract(p); vec3 u = f*f*(3.0-2.0*f);
    return mix(mix(mix(h(i), h(i+vec3(1,0,0)), u.x), mix(h(i+vec3(0,1,0)), h(i+vec3(1,1,0)), u.x), u.y), mix(mix(h(i+vec3(0,0,1)), h(i+vec3(1,0,1)), u.x), mix(h(i+vec3(0,1,1)), h(i+vec3(1,1,1)), u.x), u.y), u.z); }
  void main(){ vec3 p = normalize(vP);
    float maria = smoothstep(0.52, 0.62, n3(p * 2.3 + 4.0) * 0.7 + n3(p * 5.0) * 0.3);
    float crater = n3(p * 22.0) * 0.5 + n3(p * 60.0) * 0.25;
    vec3 alb = mix(vec3(0.78, 0.77, 0.74), vec3(0.42, 0.42, 0.44), maria) * (0.85 + 0.3 * crater);
    float lam = max(dot(normalize(vN), uSunDir), 0.0);
    outColor = vec4(alb * (0.02 + 1.15 * pow(lam, 0.8)), 1.0); }`;
function initSky() {
  SKY.sunCore = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture([[0, 'rgba(255,255,250,1)'], [0.18, 'rgba(255,250,230,1)'], [0.24, 'rgba(255,230,170,0.6)'], [1, 'rgba(255,200,120,0)']]), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
  SKY.sunGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture([[0, 'rgba(255,240,200,0.55)'], [0.3, 'rgba(255,200,120,0.18)'], [1, 'rgba(255,160,80,0)']]), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
  SKY.sunCore.scale.setScalar(70); SKY.sunGlow.scale.setScalar(420);
  SKY.moon = new THREE.Mesh(new THREE.SphereGeometry(13, 64, 32), new THREE.ShaderMaterial({ glslVersion: THREE.GLSL3, fragmentShader: MOON_FRAG,
    vertexShader: `out vec3 vN; out vec3 vP; void main(){ vN = normalize(mat3(modelMatrix) * normal); vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    uniforms: { uSunDir: { value: new THREE.Vector3(1, 0, 0) } } }));
  SKY.moonGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture([[0, 'rgba(200,215,255,0.35)'], [1, 'rgba(160,180,255,0)']]), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
  SKY.moonGlow.scale.setScalar(110);
  for (const o of [SKY.sunGlow, SKY.sunCore, SKY.moon, SKY.moonGlow]) { o.renderOrder = -1; scene.add(o); }
  // daily track of the point where the Sun is overhead (a circle at the Sun's declination)
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(361 * 3), 3));
  SKY.track = new THREE.Line(g, new THREE.LineDashedMaterial({ color: 0xffc35c, dashSize: 0.9, gapSize: 0.6, transparent: true, opacity: 0.75, depthWrite: false }));
  SKY.track.renderOrder = 2; SKY.track.frustumCulled = false; scene.add(SKY.track);
  SKY.trackLat = null;
  // markers
  const stage = $('labels');
  SKY.zs = document.createElement('div'); SKY.zs.className = 'zen sun'; SKY.zm = document.createElement('div'); SKY.zm.className = 'zen moon';
  stage.appendChild(SKY.zs); stage.appendChild(SKY.zm);
}
function updateSky(sv, now) {
  if (!SKY.sunCore) return;
  const date = timeAt(S.t), mi = moonInfo(date), mv = vecLL(mi.lon, mi.lat, 1), dist = 1500;
  SKY.sunCore.position.copy(sv).multiplyScalar(dist * 1.05); SKY.sunGlow.position.copy(SKY.sunCore.position);
  SKY.moon.position.copy(mv).multiplyScalar(dist * 0.95); SKY.moonGlow.position.copy(SKY.moon.position);
  SKY.moon.material.uniforms.uSunDir.value.copy(sv);
  SKY.moonGlow.material.opacity = 0.3 + 0.7 * mi.lit;
  CU.uMoon.value.copy(mv); CU.uMoonLit.value = mi.lit;
  const [slon, slat] = subsolar(date);
  if (SKY.trackLat === null || Math.abs(SKY.trackLat - slat) > 0.02 || SKY.trackK !== kM()) {
    const a = SKY.track.geometry.attributes.position.array, r = R + 0.06;
    for (let i = 0; i <= 360; i++) { const v = vecLL(i - 180, slat, r); a.set([v.x, v.y, v.z], i * 3); }
    SKY.track.geometry.attributes.position.needsUpdate = true; SKY.track.computeLineDistances(); SKY.trackLat = slat; SKY.trackK = kM();
  }
  SKY.track.visible = S.fxSun && S.route === 'map';
  // sky colour seen from close to the ground
  const alt = mode === 'local' ? camera.position.distanceTo(controls.target) : camera.position.length() - R;
  const tn = (mode === 'local' ? controls.target : camera.position).clone().normalize();
  const el = Math.asin(Math.max(-1, Math.min(1, tn.dot(sv)))) / DEG;
  const close = Math.max(0, Math.min(1, (6 - alt) / 5));
  const dayC = new THREE.Color(0x87b4e6).lerp(new THREE.Color(0xf2a35e), Math.max(0, Math.min(1, (8 - el) / 10)) * (el > -4 ? 1 : 0));
  const skyC = new THREE.Color(0x03060c).lerp(dayC, S.fxSun ? Math.max(0, Math.min(1, (el + 6) / 12)) : 1);
  scene.background = new THREE.Color(0x03060c).lerp(skyC, close);
  SKY.stars.material.opacity = 1 - close * Math.max(0, Math.min(1, (el + 8) / 10)); SKY.stars.material.transparent = true;
  // zenith markers
  const r = $('sceneWrap').getBoundingClientRect(), camN = camera.position.clone().normalize(), v = new THREE.Vector3();
  const place = (el_, lon, lat, text) => {
    v.copy(vecLL(lon, lat, surfR(lon, lat) + 0.05)).project(camera);
    const ok = S.fxSun && S.route === 'map' && v.z < 1 && vecLL(lon, lat, 1).dot(camN) > R / camera.position.length() + 0.01 && Math.abs(v.x) < 1 && Math.abs(v.y) < 1;
    el_.hidden = !ok; if (!ok) return;
    el_.style.left = ((v.x + 1) / 2 * r.width) + 'px'; el_.style.top = ((1 - v.y) / 2 * r.height) + 'px';
    if (el_._t !== text) { el_._t = text; el_.textContent = text; }
  };
  place(SKY.zs, slon, slat, '☀ ' + tr('zen.sun'));
  place(SKY.zm, mi.lon, mi.lat, '☾ ' + tr('zen.moon'));
}

function updateExag() {
  const k = kM();
  for (const m of [mats.globe, mats.patch]) { m.uniforms.uKV.value = k; m.uniforms.uK.value = k; m.uniforms.uKL.value = Math.max(2.5, S.exag * 0.9); }
  for (const l of Object.values(lines)) l.material.uniforms.uKV.value = k;
  for (const c of clouds.children) c.scale.setScalar(1 + (c.userData.h * 1000 * k + 0.01) / R);
  CU.uCShift.value = 4500 * S.exag / EARTH_M;
}
const cloudBaseR = () => R + 2500 * kM();

/* ---------- camera & controls ---------- */
let mode = 'globe', fly = null;
function makeControls(up, target) {
  if (controls) controls.dispose();
  camera.up.copy(up);
  controls = new OrbitControls(camera, $('scene'));
  controls.enableDamping = true; controls.dampingFactor = 0.08;
  controls.target.copy(target);
  controls.screenSpacePanning = false;
}
// close to the ground the map is dragged like a map: one finger / left button moves it,
// two fingers / right button turn and tilt, wheel or pinch zooms
function setLocalControls(up, target) {
  mode = 'local';
  makeControls(up, target);
  controls.minDistance = 0.004; controls.maxDistance = R * 1.5; controls.maxPolarAngle = Math.PI * 0.49; controls.enablePan = true;
  controls.mouseButtons = { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE };
  controls.touches = { ONE: THREE.TOUCH.PAN, TWO: THREE.TOUCH.DOLLY_ROTATE };
  controls.zoomToCursor = true;
  controls.update();
}
// keep the pivot on the ground after panning: re-anchor "up" to the new spot
function reanchor() {
  const t = controls.target, n = t.clone().normalize();
  const [lon, lat] = llVec(n), want = surfR(lon, lat);
  if (Math.abs(t.length() - want) > 0.0005) { const d = n.clone().multiplyScalar(want).sub(t); t.add(d); camera.position.add(d); }
  if (n.angleTo(camera.up) > 0.02) { const cam = camera.position.clone(); setLocalControls(n, t.clone()); camera.position.copy(cam); controls.update(); }
}
function setGlobeControls(camPos) {
  mode = 'globe';
  makeControls(new THREE.Vector3(0, 1, 0), new THREE.Vector3());
  controls.enablePan = false; controls.minDistance = R * 1.06; controls.maxDistance = R * 6;
  if (camPos) camera.position.copy(camPos);
  controls.update();
}
function localView(lon, lat, dist = 18, tilt = 0.9) {
  const n = vecLL(lon, lat, 1), target = n.clone().multiplyScalar(surfR(lon, lat));
  const north = new THREE.Vector3(-Math.sin(lat * DEG) * Math.cos(lon * DEG), Math.cos(lat * DEG), Math.sin(lat * DEG) * Math.sin(lon * DEG));
  const cam = target.clone().addScaledVector(n, dist * Math.cos(tilt)).addScaledVector(north, -dist * Math.sin(tilt));
  return { target, cam, up: n };
}
function flyTo(lon, lat, opts = {}) {
  const goLocal = opts.local !== false;
  const end = goLocal ? localView(lon, lat, opts.dist || 5, opts.tilt ?? 1.08) : { target: new THREE.Vector3(), cam: vecLL(lon, lat, R * 2.7), up: new THREE.Vector3(0, 1, 0) };
  const start = { cam: camera.position.clone(), target: controls.target.clone() };
  fly = { start, end, t0: performance.now(), dur: 1600, goLocal };
  controls.enabled = false;
}
function stepFly(now) {
  if (!fly) return;
  let u = Math.min(1, (now - fly.t0) / fly.dur); const e = u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
  const lerpSph = (a, b) => { const ra = a.length(), rb = b.length(); const da = a.clone().normalize(), db = b.clone().normalize(); const d = da.lerp(db, e).normalize(); const arc = Math.sin(Math.PI * e) * Math.max(0, (da.angleTo(db) - 0.2)) * R * 0.9; return d.multiplyScalar(ra + (rb - ra) * e + arc); };
  camera.position.copy(lerpSph(fly.start.cam, fly.end.cam));
  const tgt = fly.start.target.clone().lerp(fly.end.target, e);
  camera.up.copy(new THREE.Vector3(0, 1, 0).lerp(fly.end.up, fly.goLocal ? e : 0).normalize());
  camera.lookAt(tgt);
  if (u >= 1) {
    const f = fly; fly = null;
    if (f.goLocal) { camera.position.copy(f.end.cam); setLocalControls(f.end.up, f.end.target); }
    else setGlobeControls(f.end.cam);
  }
}
let dragging = false;
function adaptControls() {
  if (!controls || fly) return;
  const alt = camera.position.length() - R;
  if (mode === 'globe') { controls.rotateSpeed = Math.min(1, Math.max(0.05, alt / (R * 1.6))); controls.zoomSpeed = 0.9; }
  else {
    const d = camera.position.distanceTo(controls.target); controls.panSpeed = 1; controls.rotateSpeed = 0.5;
    if (d > R * 1.2) { setGlobeControls(camera.position.clone().normalize().multiplyScalar(Math.max(R * 2.2, camera.position.length()))); return; }
    if (!dragging) reanchor();
  }
}
function resize() {
  if (G.tMax) renderTimelineDays();
  const r = $('sceneWrap').getBoundingClientRect();
  if (!r.width || !r.height || !renderer) return;
  renderer.setSize(r.width, r.height, false); camera.aspect = r.width / r.height; camera.updateProjectionMatrix();
}

/* ---------- clouds ---------- */
// height (km) and opacity of each cloud shell
const CLOUD_SHELLS = MOBILE ? [[1.6, 0.55], [3.2, 0.42], [5, 0.38], [7.2, 0.36], [9.6, 0.36]] : [[1.4, 0.45], [2.4, 0.34], [3.5, 0.3], [4.7, 0.3], [6, 0.3], [7.4, 0.3], [8.8, 0.3], [10.3, 0.32]];
const CU = {};
function blankTex() { const t = new THREE.DataTexture(new Uint8Array(4), 1, 1, THREE.RGBAFormat); t.needsUpdate = true; return t; }
function initCloudUniforms() {
  const b = blankTex(), P = D.region.proj, rg = D.region.grid;
  Object.assign(CU, {
    uCGA: { value: b }, uCGB: { value: b }, uCRA: { value: b }, uCRB: { value: b }, uCMix: { value: 0 }, uCOn: { value: 1 }, uCHasR: { value: 0 },
    uCShift: { value: 0 }, uCProj: { value: new THREE.Vector4(P.lon0, P.k, P.x0, P.y0) }, uCReg: { value: new THREE.Vector4(rg.X0, rg.Y0, rg.W, rg.H) }, uHaze: { value: 0 },
    uTime: { value: 0 }, uMoon: { value: new THREE.Vector3(0, 1, 0) }, uMoonLit: { value: 0.5 },
  });
}
// real clouds: ECMWF simulated IR images → density JPEGs (pipeline/clouds.js), loaded on demand
const CL = new Map();
function cloudImg(kind, i) {
  const id = kind + i;
  if (CL.has(id)) return CL.get(id);
  const e = { t: null, used: performance.now() };
  CL.set(id, e);
  new THREE.TextureLoader().load('data/' + D.clouds[kind][i], t => {
    t.colorSpace = THREE.NoColorSpace; t.minFilter = THREE.LinearFilter; t.generateMipmaps = false;
    t.wrapS = kind === 'g' ? THREE.RepeatWrapping : THREE.ClampToEdgeWrapping; t.wrapT = THREE.ClampToEdgeWrapping; e.t = t;
  });
  if (CL.size > 28) { let old = null; for (const [k, v] of CL) if (v.t && (!old || v.used < old[1].used)) old = [k, v]; if (old) { old[1].t.dispose(); CL.delete(old[0]); } }
  return e;
}
function cloudFrame(t) {
  const st = D.clouds.steps;
  if (t <= st[0]) return { i0: 0, i1: 0, f: 0 };
  for (let i = 0; i < st.length - 1; i++) if (t >= st[i] && t <= st[i + 1]) return { i0: i, i1: i + 1, f: (t - st[i]) / (st[i + 1] - st[i]) };
  return { i0: st.length - 1, i1: st.length - 1, f: 0 };
}
let fallbackClouds = null;
function updateClouds() {
  if (D.clouds) {
    const fr = cloudFrame(S.t), now = performance.now();
    for (const kind of D.clouds.r ? ['g', 'r'] : ['g']) {
      const a = cloudImg(kind, fr.i0), b = cloudImg(kind, fr.i1); a.used = b.used = now;
      cloudImg(kind, Math.min(D.clouds.steps.length - 1, fr.i1 + 1)).used = now;
      if (a.t && b.t) { CU[kind === 'g' ? 'uCGA' : 'uCRA'].value = a.t; CU[kind === 'g' ? 'uCGB' : 'uCRB'].value = b.t; if (kind === 'g') CU.uCMix.value = fr.f; else CU.uCHasR.value = 1; }
    }
    return;
  }
  // old data without IR frames: estimate cloud cover from precipitation and sunshine
  const fr = frameAt('temp', S.t), key = fr.i0 + '_' + fr.i1;
  if (!fallbackClouds) {
    const { W, H } = D.global.grid; fallbackClouds = { key: '', A: new THREE.DataTexture(new Uint8Array(W * H), W, H, THREE.RedFormat), B: new THREE.DataTexture(new Uint8Array(W * H), W, H, THREE.RedFormat) };
    for (const t of [fallbackClouds.A, fallbackClouds.B]) { t.minFilter = t.magFilter = THREE.LinearFilter; t.wrapS = THREE.RepeatWrapping; t.unpackAlignment = 1; }
  }
  if (key !== fallbackClouds.key) {
    fallbackClouds.A.image.data = cloudField(fr.i0); fallbackClouds.A.needsUpdate = true; fallbackClouds.B.image.data = cloudField(fr.i1); fallbackClouds.B.needsUpdate = true; fallbackClouds.key = key;
    CU.uCGA.value = fallbackClouds.A; CU.uCGB.value = fallbackClouds.B;
  }
  CU.uCMix.value = fr.f;
}
const cloudCache = new Map();
function blur(src, W, H, r, wrap) {
  const tmp = new Float32Array(src.length), out = new Float32Array(src.length);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { let s = 0, c = 0; for (let d = -r; d <= r; d++) { let X = x + d; if (wrap) X = (X + W) % W; else if (X < 0 || X >= W) continue; s += src[y * W + X]; c++; } tmp[y * W + x] = s / c; }
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { let s = 0, c = 0; for (let d = -r; d <= r; d++) { const Y = y + d; if (Y >= 0 && Y < H) { s += tmp[Y * W + x]; c++; } } out[y * W + x] = s / c; }
  return out;
}
function cloudField(stepIdx) {
  if (cloudCache.has(stepIdx)) return cloudCache.get(stepIdx);
  const { W, H } = D.global.grid, n = W * H, t = D.global.layers.temp.steps[stepIdx];
  const rf = frameAt('rain', t), rain = G.glo.rain[rf.f < 0.5 ? rf.i0 : rf.i1], sun = G.glo.sun[frameAt('sun', t).i0];
  const f = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const r = rain[i] ? Math.min(1, 0.6 + rain[i] * 0.1) : 0;
    const s = D.classes.sun[sun[i]], sh = (s.lo + s.hi) / 2;
    const lat = 90 - (Math.floor(i / W) + 0.5) * D.global.grid.D;
    const dayLen = Math.max(1, 12 - Math.abs(lat) / 90 * 10); // rough: sunshine relative to possible hours
    const overcast = G.missing.sun ? 0 : Math.max(0, Math.min(1, 1 - sh / dayLen)) * 0.7;
    f[i] = Math.max(r, overcast);
  }
  const b = blur(blur(f, W, H, 1, true), W, H, 1, true), out = new Uint8Array(n);
  for (let i = 0; i < n; i++) { const y = Math.floor(i / W), x = i % W; out[(H - 1 - y) * W + x] = Math.round(Math.min(1, b[i]) * 0.8 * 255); }
  if (cloudCache.size > 24) cloudCache.delete(cloudCache.keys().next().value);
  cloudCache.set(stepIdx, out);
  return out;
}

/* ---------- wind flow: real ECMWF wind (u, v) at four heights, drawn as moving streaks ---------- */
// D.wind = { steps, tile: {W, H, cols}, levels: [{id, file, scale, h}], region?: {...} } — see pipeline/wind.py
const WIND = { lv: {}, n: MOBILE ? 3000 : 8000, K: 10 };
function windLevels() { return D.wind ? D.wind.levels.map(l => l.id) : []; }
async function windLoad(id) {
  if (WIND.lv[id]) return WIND.lv[id];
  const L = D.wind.levels.find(l => l.id === id); if (!L) return null;
  WIND.lv[id] = { loading: true };
  const img = await loadImageData('data/' + L.file);
  const t = D.wind.tile, out = { u: [], v: [], scale: L.scale, h: L.h };
  for (let i = 0; i < D.wind.steps.length; i++) {
    const col = (i % t.cols) * 2, row = Math.floor(i / t.cols);
    const u = new Float32Array(t.W * t.H), v = new Float32Array(t.W * t.H);
    for (let y = 0; y < t.H; y++) for (let x = 0; x < t.W; x++) {
      const k = y * t.W + x;
      u[k] = (img.d[(((row * t.H + y) * img.W) + col * t.W + x) * 4] - 128) * L.scale;
      v[k] = (img.d[(((row * t.H + y) * img.W) + (col + 1) * t.W + x) * 4] - 128) * L.scale;
    }
    out.u.push(u); out.v.push(v);
  }
  WIND.lv[id] = out; return out;
}
function windFrame(t) { const st = D.wind.steps; if (t <= st[0]) return { i0: 0, i1: 0, f: 0 }; for (let i = 0; i < st.length - 1; i++) if (t <= st[i + 1]) return { i0: i, i1: i + 1, f: (t - st[i]) / (st[i + 1] - st[i]) }; return { i0: st.length - 1, i1: st.length - 1, f: 0 }; }
// wind (m/s, east and north components) at a point, time interpolated
function windAt(lv, fr, lon, lat) {
  const t = D.wind.tile, x = ((((lon + 180) % 360) + 360) % 360) / 360 * (t.W - 1), y = (90 - lat) / 180 * (t.H - 1);
  const ix = Math.floor(x), iy = Math.min(t.H - 2, Math.floor(y)), ax = x - ix, ay = y - iy, ix1 = (ix + 1) % t.W;
  const s = (a, i) => { const f = a[i]; return (f[iy * t.W + ix] * (1 - ax) + f[iy * t.W + ix1] * ax) * (1 - ay) + (f[(iy + 1) * t.W + ix] * (1 - ax) + f[(iy + 1) * t.W + ix1] * ax) * ay; };
  return [s(lv.u, fr.i0) * (1 - fr.f) + s(lv.u, fr.i1) * fr.f, s(lv.v, fr.i0) * (1 - fr.f) + s(lv.v, fr.i1) * fr.f];
}
function initWind() {
  if (!D.wind) return;
  const n = WIND.n, K = WIND.K;
  WIND.lon = new Float32Array(n); WIND.lat = new Float32Array(n); WIND.age = new Float32Array(n); WIND.life = new Float32Array(n);
  WIND.trail = new Float32Array(n * K * 3); WIND.len = new Uint8Array(n);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * (K - 1) * 6), 3));
  g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(n * (K - 1) * 6), 3));
  WIND.mesh = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  WIND.mesh.frustumCulled = false; WIND.mesh.renderOrder = 8; scene.add(WIND.mesh);
  for (let i = 0; i < n; i++) WIND.age[i] = WIND.life[i] = 1;
  windLoad(S.windLvl);
}
const WCOL = [[0, [0.55, 0.75, 1]], [5, [0.75, 0.95, 1]], [10, [1, 1, 0.6]], [17, [1, 0.72, 0.25]], [25, [1, 0.35, 0.25]], [40, [0.95, 0.3, 0.85]], [70, [0.8, 0.5, 1]]];
function windColor(sp) { for (let i = 1; i < WCOL.length; i++) if (sp < WCOL[i][0]) { const [a, ca] = WCOL[i - 1], [b, cb] = WCOL[i], f = (sp - a) / (b - a); return [ca[0] + (cb[0] - ca[0]) * f, ca[1] + (cb[1] - ca[1]) * f, ca[2] + (cb[2] - ca[2]) * f]; } return WCOL[WCOL.length - 1][1]; }
function stepWind(dt) {
  if (!WIND.mesh) return;
  const lv = WIND.lv[S.windLvl];
  const on = S.fxWind && S.route === 'map' && lv && lv.u;
  WIND.mesh.visible = !!on; if (!on) return;
  const fr = windFrame(S.t), k = kM(), K = WIND.K, n = WIND.n;
  const look = (mode === 'local' ? controls.target.clone() : camera.position.clone()).normalize();
  const alt = mode === 'local' ? camera.position.distanceTo(controls.target) : camera.position.length() - R;
  const ang = Math.min(1.25, Math.max(0.01, alt / R * 1.1)), cosA = Math.cos(ang);
  const [llon, llat] = llVec(look);
  const speedK = 320 * alt; // seconds of real flow shown per second, scaled with the view
  const lift = (lon, lat) => lv.h === 0 ? Math.max(0, heightAt(lon, lat)) * k + 0.0005 + alt * 0.002 : Math.max(lv.h * k, Math.max(0, heightAt(lon, lat)) * k + 300 * k);
  const pos = WIND.mesh.geometry.attributes.position.array, col = WIND.mesh.geometry.attributes.color.array;
  let seg = 0;
  for (let i = 0; i < n; i++) {
    WIND.age[i] += dt;
    let lon = WIND.lon[i], lat = WIND.lat[i];
    const vv = vecLL(lon, lat, 1);
    if (WIND.age[i] > WIND.life[i] || vv.dot(look) < cosA) {
      // respawn uniformly inside the visible cap
      const u = Math.random(), r = Math.acos(1 - u * (1 - cosA)), th = Math.random() * Math.PI * 2;
      const lt = llat * DEG, dlat = Math.asin(Math.sin(lt) * Math.cos(r) + Math.cos(lt) * Math.sin(r) * Math.cos(th));
      const dlon = llon * DEG + Math.atan2(Math.sin(th) * Math.sin(r) * Math.cos(lt), Math.cos(r) - Math.sin(lt) * Math.sin(dlat));
      lon = ((dlon / DEG + 540) % 360) - 180; lat = dlat / DEG;
      WIND.lon[i] = lon; WIND.lat[i] = lat; WIND.age[i] = 0; WIND.life[i] = 1.5 + Math.random() * 2.5; WIND.len[i] = 0;
    }
    const [u, v] = windAt(lv, fr, lon, lat), sp = Math.hypot(u, v);
    const cl = Math.max(0.05, Math.cos(lat * DEG));
    lon += u * speedK * dt / (111320 * cl) * (R / R); lat += v * speedK * dt / 110574;
    if (lat > 89) lat = 89; if (lat < -89) lat = -89;
    lon = ((lon + 540) % 360) - 180;
    WIND.lon[i] = lon; WIND.lat[i] = lat;
    // push into the trail
    const base = i * K * 3; WIND.trail.copyWithin(base + 3, base, base + (K - 1) * 3);
    const p = vecLL(lon, lat, R + lift(lon, lat)); WIND.trail[base] = p.x; WIND.trail[base + 1] = p.y; WIND.trail[base + 2] = p.z;
    WIND.len[i] = Math.min(K, WIND.len[i] + 1);
    const c = windColor(sp), fade = Math.min(1, WIND.age[i] * 2, (WIND.life[i] - WIND.age[i]) * 2) * Math.min(1, 0.45 + sp / 6);
    for (let j = 0; j < WIND.len[i] - 1; j++) {
      const a = base + j * 3, b = base + (j + 1) * 3, o = seg * 6, w0 = fade * (1 - j / (K - 1)), w1 = fade * (1 - (j + 1) / (K - 1));
      pos[o] = WIND.trail[a]; pos[o + 1] = WIND.trail[a + 1]; pos[o + 2] = WIND.trail[a + 2]; pos[o + 3] = WIND.trail[b]; pos[o + 4] = WIND.trail[b + 1]; pos[o + 5] = WIND.trail[b + 2];
      col[o] = c[0] * w0; col[o + 1] = c[1] * w0; col[o + 2] = c[2] * w0; col[o + 3] = c[0] * w1; col[o + 4] = c[1] * w1; col[o + 5] = c[2] * w1;
      seg++;
    }
  }
  WIND.mesh.geometry.setDrawRange(0, seg * 2);
  WIND.mesh.geometry.attributes.position.needsUpdate = true; WIND.mesh.geometry.attributes.color.needsUpdate = true;
}
function renderWindLevels() {
  const el = $('windLvl'); if (!D.wind) { el.innerHTML = ''; $('fxWind').closest('label').hidden = true; return; }
  el.title = tr('lvl.title');
  el.innerHTML = windLevels().map(id => `<button data-l="${id}" aria-pressed="${S.windLvl === id}">${tr('lvl.' + id)}</button>`).join('');
  el.querySelectorAll('button').forEach(b => b.onclick = () => { S.windLvl = b.dataset.l; store.set('windLvl', S.windLvl); windLoad(S.windLvl); WIND.age.fill(99); renderWindLevels(); if (S.A) renderPanelNow(); });
}

/* ---------- precipitation particles ---------- */
const NRAIN = MOBILE ? 3500 : 9000, NSNOW = MOBILE ? 2500 : 6000;
const P = {};
let rainMesh, snowMesh;
function initPrecip() {
  const mk = n => ({ dir: new Float32Array(n * 3), r: new Float32Array(n), floor: new Float32Array(n), v: new Float32Array(n), live: new Uint8Array(n), n });
  P.rain = mk(NRAIN); P.snow = mk(NSNOW);
  const rg = new THREE.BufferGeometry(); rg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(NRAIN * 6), 3));
  rainMesh = new THREE.LineSegments(rg, new THREE.LineBasicMaterial({ color: 0xa8d8ff, transparent: true, opacity: 0.6 })); rainMesh.frustumCulled = false; scene.add(rainMesh);
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(NSNOW * 3), 3));
  const c = document.createElement('canvas'); c.width = c.height = 32; const g = c.getContext('2d');
  const grd = g.createRadialGradient(16, 16, 0, 16, 16, 16); grd.addColorStop(0, 'rgba(255,255,255,1)'); grd.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = grd; g.fillRect(0, 0, 32, 32);
  snowMesh = new THREE.Points(sg, new THREE.PointsMaterial({ size: 3, sizeAttenuation: false, map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false, color: 0xffffff }));
  snowMesh.frustumCulled = false; scene.add(snowMesh);
}
const RAIN_W = [0, 1, 2.5, 5, 9, 14, 20, 28];
let cdfAt = 0;
function buildCdf(t, now) {
  if (now - cdfAt < 400 && P.cdf) return;
  cdfAt = now;
  const { W, H, D: d } = D.global.grid, fr = frameAt('rain', t), rain = G.glo.rain[fr.f < 0.5 ? fr.i0 : fr.i1];
  const tf = frameAt('temp', t); P.temp = G.glo.temp[tf.f < 0.5 ? tf.i0 : tf.i1];
  // only cells near the centre of the view get particles
  const look = (mode === 'local' ? controls.target.clone() : camera.position.clone()).normalize();
  const alt = mode === 'local' ? camera.position.distanceTo(controls.target) : camera.position.length() - R;
  const ang = Math.min(1.2, Math.max(0.03, alt / R * 1.1)), cosA = Math.cos(ang);
  P.ang = ang;
  const cdf = new Float32Array(W * H); let s = 0;
  for (let y = 0; y < H; y++) {
    const lat = (90 - (y + 0.5) * d) * DEG, cl = Math.cos(lat), sl = Math.sin(lat);
    for (let x = 0; x < W; x++) {
      const i = y * W + x, k = rain[i];
      if (k) { const lon = (-180 + (x + 0.5) * d) * DEG; const dot = look.x * cl * Math.cos(lon) + look.y * sl - look.z * cl * Math.sin(lon); if (dot > cosA) s += RAIN_W[k] * cl; }
      cdf[i] = s;
    }
  }
  P.cdf = cdf; P.total = s;
}
function stepPrecip(dt, t, now) {
  const on = S.fxPrecip && S.route === 'map';
  rainMesh.visible = snowMesh.visible = on && S.layer !== 'd5';
  if (!on) return;
  buildCdf(t, now);
  const { W, D: d } = D.global.grid, k = kM();
  const cloudR = cloudBaseR();
  const alt = mode === 'local' ? camera.position.distanceTo(controls.target) : camera.position.length() - R;
  const streak = Math.max(0.02, alt * 0.012), fallT = 1.4;
  const want = Math.min(1, P.total / (P.ang * P.ang * 400 + 1));
  const rp = rainMesh.geometry.attributes.position.array, sp = snowMesh.geometry.attributes.position.array;
  let ri = 0, si = 0;
  const spawn = () => { const r = Math.random() * P.total; let lo = 0, hi = P.cdf.length - 1; while (lo < hi) { const m = (lo + hi) >> 1; if (P.cdf[m] < r) lo = m + 1; else hi = m; } return lo; };
  const step = (A, i, isSnow) => {
    if (!A.live[i]) {
      if (!P.total || Math.random() > want * 0.06) return false;
      const c = spawn(); const snowy = D.classes.temp[P.temp[c]].hi <= 0; if (snowy !== isSnow) return false;
      const lon = -180 + ((c % W) + Math.random()) * d, lat = 90 - (Math.floor(c / W) + Math.random()) * d;
      const v = vecLL(lon, lat, 1); A.dir.set([v.x, v.y, v.z], i * 3);
      A.floor[i] = R + heightAt(lon, lat) * k; A.r[i] = cloudR - Math.random() * (cloudR - A.floor[i]) * 0.3;
      A.v[i] = (cloudR - A.floor[i]) / (isSnow ? fallT * 4 : fallT) * (0.8 + Math.random() * 0.4); A.live[i] = 1;
    }
    A.r[i] -= A.v[i] * dt;
    if (A.r[i] < A.floor[i]) { A.live[i] = 0; return false; }
    return true;
  };
  for (let i = 0; i < P.rain.n; i++) if (step(P.rain, i, false)) { const o = ri * 6, dx = P.rain.dir[i * 3], dy = P.rain.dir[i * 3 + 1], dz = P.rain.dir[i * 3 + 2], r = P.rain.r[i]; rp[o] = dx * r; rp[o + 1] = dy * r; rp[o + 2] = dz * r; rp[o + 3] = dx * (r + streak); rp[o + 4] = dy * (r + streak); rp[o + 5] = dz * (r + streak); ri++; }
  for (let i = 0; i < P.snow.n; i++) if (step(P.snow, i, true)) { const o = si * 3, r = P.snow.r[i], w = Math.sin(r * 9 + i) * streak * 0.4; sp[o] = P.snow.dir[i * 3] * r + w; sp[o + 1] = P.snow.dir[i * 3 + 1] * r; sp[o + 2] = P.snow.dir[i * 3 + 2] * r + w; si++; }
  rainMesh.geometry.setDrawRange(0, ri * 2); rainMesh.geometry.attributes.position.needsUpdate = true;
  snowMesh.geometry.setDrawRange(0, si); snowMesh.geometry.attributes.position.needsUpdate = true;
}

/* ---------- per-frame updates ---------- */
const texCache = new Map();
function classTex(src, key, i) {
  const id = src + key + i;
  if (!texCache.has(id)) { const g = src === 'glo' ? D.global.grid : D.region.grid; texCache.set(id, classTexture(G[src][key][i], src === 'glo' ? g.W : g.GW, src === 'glo' ? g.H : g.GH)); }
  return texCache.get(id);
}
let lastCloudKey = '';
function updateUniforms(now) {
  const sunOn = S.fxSun ? 1 : 0;
  const [slon, slat] = subsolar(timeAt(S.t)), sv = vecLL(slon, slat, 1);
  for (const [m, src] of [[mats.globe, 'glo'], [mats.patch, 'reg']]) {
    const u = m.uniforms; u.uSun.value.copy(sv); u.uSunOn.value = sunOn;
    if (S.layer === 'relief' || S.layer === 'd5') { u.uAlpha.value = 0; continue; }
    const fr = frameAt(S.layer, S.t);
    u.uA.value = classTex(src, S.layer, fr.i0); u.uB.value = classTex(src, S.layer, fr.i1);
    u.uMix.value = S.layer === 'sun' ? 0 : fr.f; u.uRow.value = LAYER_ROWS[S.layer]; u.uAlpha.value = LAYER_ALPHA[S.layer];
  }
  mats.atmo.uniforms.uSun.value.copy(sv); mats.atmo.uniforms.uSunOn.value = sunOn;
  for (const m of mats.clouds) { const u = m.uniforms; u.uSun.value.copy(sv); u.uSunOn.value = sunOn; }
  CU.uTime.value = now / 1000;
  updateSky(sv, now);
  const cOn = S.fxClouds && S.layer !== 'd5';
  CU.uCOn.value = cOn ? 1 : 0; clouds.visible = cOn;
  d5Update();
  updateClouds();
  // borders fade in with zoom
  const alt = (mode === 'local' ? camera.position.distanceTo(controls.target) : camera.position.length() - R);
  CU.uHaze.value = alt < R * 0.6 ? 1 / Math.max(0.05, alt) : 0;
  lines.countries.visible = lines.admin1.visible = lines.urban.visible = S.fxBorders;
  lines.countries.material.uniforms.uOpacity.value = 0.8;
  lines.admin1.material.uniforms.uOpacity.value = Math.max(0, Math.min(0.55, (R * 1.0 - alt) / (R * 0.5)));
  lines.urban.material.uniforms.uOpacity.value = Math.max(0, Math.min(0.95, (R * 0.25 - alt) / (R * 0.12)));
  const lift = Math.max(0.005, alt * 0.0015);
  for (const l of Object.values(lines)) l.material.uniforms.uLift.value = lift;
  camera.near = Math.max(0.00005, Math.min(0.01, alt * 0.05)); camera.far = alt < 1 ? 2000 : 4000; camera.updateProjectionMatrix();
}

let last = performance.now(), uiTick = 0;
const PERF = { ms: 16, n: 0, ratio: 0, lastChange: 0 };
function adaptQuality(now, dtMs) {
  PERF.ms = PERF.ms * 0.95 + dtMs * 0.05;
  if (now - PERF.lastChange < 2500) return;
  const max = Math.min(devicePixelRatio, MOBILE ? 1.5 : 2);
  if (!PERF.ratio) PERF.ratio = renderer.getPixelRatio();
  let r = PERF.ratio;
  if (PERF.ms > 42 && r > 0.6) r = Math.max(0.6, r - 0.25);
  else if (PERF.ms < 20 && r < max) r = Math.min(max, r + 0.25);
  if (r !== PERF.ratio) { PERF.ratio = r; renderer.setPixelRatio(r); resize(); PERF.lastChange = now; }
  // very slow: fewer cloud layers
  if (clouds) clouds.children.forEach((c, i) => { c.visible = PERF.ms < 60 || i === 0 || i === clouds.children.length - 1; });
}
function loop(now) {
  const dtMs = now - last, dt = Math.min(0.05, dtMs / 1000); last = now;
  if (dtMs < 500) adaptQuality(now, dtMs);
  if (S.playing) {
    S.t += dt * S.speed;
    if (S.t > G.tMax) S.t = 0;
    uiTick += dt; if (uiTick > 0.2) { uiTick = 0; syncTimeUI(); }
  }
  if (S.route === 'map') {
    stepFly(now);
    if (!fly) { controls.update(); adaptControls(); }
    updateUniforms(now);
    stepPrecip(dt, S.t, now);
    stepWind(dt);
    stepLightning(now);
    updateBuildings(now);
    renderer.render(scene, camera);
    d5RecFrame();
    placeLabels();
  }
  requestAnimationFrame(loop);
}

/* ---------- labels (pool) ---------- */
const POOL = MOBILE ? 36 : 70;
let labelEls = [], candidates = [];
function buildLabels() {
  const wrap = $('labels'); wrap.innerHTML = '';
  labelEls = Array.from({ length: POOL }, () => {
    const el = document.createElement('div'); el.className = 'lbl'; el.hidden = true;
    el.innerHTML = '<span></span><small></small>';
    wrap.appendChild(el); return el;
  });
  const uzIds = new Set(D.cities.map(c => c.ru));
  candidates = [
    ...D.cities.map(c => ({ ...c, rank: c.country === 'UZ' ? 1 : 3, pop: 1e6, preset: true })),
    ...GEO.places.filter(p => !uzIds.has(p[3])).map(p => ({ id: 'np' + p[0] + p[1], lon: p[0], lat: p[1], uz: UZ_PLACE[p[2]] || p[2], ru: p[3], rank: p[4], pop: p[5], country: p[6], cap: p[7] })),
  ];
  for (const c of candidates) c.v = vecLL(c.lon, c.lat, 1);
}
let labelTick = 0;
function placeLabels() {
  labelTick++;
  const r = $('sceneWrap').getBoundingClientRect(), camN = camera.position.clone().normalize();
  const alt = mode === 'local' ? camera.position.distanceTo(controls.target) : camera.position.length() - R;
  const maxRank = alt > R * 2 ? 2 : alt > R * 1.2 ? 3 : alt > R * 0.6 ? 4 : alt > R * 0.25 ? 6 : alt > R * 0.08 ? 8 : 10;
  const boxes = [], v = new THREE.Vector3();
  const prio = c => (S.A && c.id === S.A.id && Math.abs(c.lat - S.A.lat) < 1e-3 ? -10 : S.B && c.id === S.B.id ? -9 : c.preset && c.country === 'UZ' ? -2 : c.cap === 2 ? -1 : 0) + c.rank;
  const vis = [];
  for (const c of candidates) {
    if (c.rank > maxRank && !(S.A && c.id === S.A.id)) continue;
    const facing = mode === 'local' ? c.v.dot(controls.target.clone().normalize()) > Math.cos(Math.min(1.2, alt / R * 1.5 + 0.02)) : c.v.dot(camN) > R / camera.position.length() + 0.02;
    if (!facing) continue;
    vis.push(c);
  }
  vis.sort((a, b) => prio(a) - prio(b) || b.pop - a.pop);
  let used = 0;
  for (const c of vis) {
    if (used >= POOL) break;
    v.copy(c.v).multiplyScalar(surfR(c.lon, c.lat) + 0.02).project(camera);
    if (v.z > 1 || Math.abs(v.x) > 1.02 || Math.abs(v.y) > 1.02) continue;
    const x = (v.x + 1) / 2 * r.width, y = (1 - v.y) / 2 * r.height;
    const nm = pname(c), w = Math.max(48, nm.length * 7), bx = [x - w / 2, y - 34, x + w / 2, y];
    if (prio(c) > -9 && boxes.some(o => bx[0] < o[2] && bx[2] > o[0] && bx[1] < o[3] && bx[3] > o[1])) continue;
    boxes.push(bx);
    const el = labelEls[used++];
    el.hidden = false; el._p = c; el.style.left = x + 'px'; el.style.top = y + 'px';
    if (el._id !== c.id || labelTick % 8 === 0) { el._id = c.id; el.querySelector('span').textContent = nm; el.querySelector('small').textContent = labelValue(c.lon, c.lat); }
    el.classList.toggle('sel', !!S.A && c.id === S.A.id); el.classList.toggle('cmp', !!S.B && c.id === S.B.id); el.classList.toggle('minor', c.rank > 4 && !c.preset);
  }
  for (let i = used; i < POOL; i++) labelEls[i].hidden = true;
  // selected point marker when it is not a labelled place
  const pin = $('pin');
  if (S.A && S.A.id === 'pt') {
    v.copy(vecLL(S.A.lon, S.A.lat, surfR(S.A.lon, S.A.lat) + 0.02)).project(camera);
    const ok = v.z < 1 && vecLL(S.A.lon, S.A.lat, 1).dot(camN) > R / camera.position.length() - 0.02;
    pin.hidden = !ok; if (ok) { pin.style.left = ((v.x + 1) / 2 * r.width) + 'px'; pin.style.top = ((1 - v.y) / 2 * r.height) + 'px'; }
  } else pin.hidden = true;
}
function labelValue(lon, lat) {
  const L = S.layer;
  if (L === 'relief') { const h = heightAt(lon, lat); return h > 50 ? `${Math.round(h / 10) * 10} ${tr('m')}` : ''; }
  if (L === 'd5') return d5Label(lon, lat);
  const v = valueAt(L, S.t, lon, lat);
  if (L === 'temp') return fmtT(v);
  if (L === 'rain' || L === 'wind') return v.k ? `${v.lo}–${v.hi}` : '';
  return `${v.lo}–${v.hi} ${tr('h')}`;
}

/* ---------- pointer: analytic ray–sphere hit ---------- */
function hitLL(clientX, clientY) {
  const r = $('scene').getBoundingClientRect(), m = new THREE.Vector2((clientX - r.left) / r.width * 2 - 1, -(clientY - r.top) / r.height * 2 + 1);
  raycaster.setFromCamera(m, camera);
  const ro = raycaster.ray.origin, rd = raycaster.ray.direction;
  let rad = R;
  for (let it = 0; it < 3; it++) {
    const b = ro.dot(rd), c = ro.lengthSq() - rad * rad, disc = b * b - c;
    if (disc < 0) return null;
    const tt = -b - Math.sqrt(disc); if (tt < 0) return null;
    const p = ro.clone().addScaledVector(rd, tt), [lon, lat] = llVec(p);
    const nr = surfR(lon, lat); if (Math.abs(nr - rad) < 0.002 || it === 2) return { lon, lat, x: clientX - r.left, y: clientY - r.top };
    rad = nr;
  }
  return null;
}
function setupPointer() {
  const canvas = $('scene'), tip = $('tip');
  let down = null, lastTap = 0;
  canvas.addEventListener('pointermove', e => {
    if (e.pointerType !== 'mouse' || e.buttons) { tip.hidden = true; return; }
    const h = hitLL(e.clientX, e.clientY);
    if (!h) { tip.hidden = true; return; }
    const parts = [fmtLL(h.lat, h.lon), `${tr('elev')}: ${fmtElev(h.lon, h.lat)}`];
    if (S.layer === 'd5') { const l = d5Label(h.lon, h.lat); if (l) parts.push(l); }
    else if (S.layer !== 'relief') { const v = valueAt(S.layer, S.t, h.lon, h.lat); parts.push(`${tr('layer.' + S.layer)}: ${S.layer === 'temp' ? fmtT(v) : S.layer === 'rain' ? (v.k ? `${v.lo}–${v.hi} ${tr('mm')}` : tr('noRain')) : S.layer === 'wind' ? (v.k ? `${v.lo}–${v.hi} ${tr('ms')}` : tr('calm')) : `${v.lo}–${v.hi} ${tr('h')}`}`); }
    tip.innerHTML = parts.map(p => `<div>${p}</div>`).join('');
    tip.style.left = h.x + 'px'; tip.style.top = h.y + 'px'; tip.hidden = false;
  });
  canvas.addEventListener('pointerleave', () => { tip.hidden = true; });
  canvas.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; dragging = true; if (TOUR.on) stopTour(); if (fly) { const f = fly; fly = null; if (f.goLocal) setLocalControls(camera.up.clone().lerp(f.end.up, 1).normalize(), f.end.target.clone()); else setGlobeControls(camera.position.clone()); } });
  window.addEventListener('pointerup', () => { dragging = false; });
  window.addEventListener('pointercancel', () => { dragging = false; });
  canvas.addEventListener('pointerup', e => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 6) return;
    // a tap on a city label selects the city
    const r = canvas.getBoundingClientRect(), tx = e.clientX - r.left, ty = e.clientY - r.top;
    for (const el of labelEls) {
      if (el.hidden || !el._p) continue;
      const x = parseFloat(el.style.left), y = parseFloat(el.style.top), w = Math.max(40, el.offsetWidth);
      if (tx > x - w / 2 - 6 && tx < x + w / 2 + 6 && ty > y - 40 && ty < y + 6) { selectPlace(el._p); return; }
    }
    const h = hitLL(e.clientX, e.clientY); if (!h) return;
    const now = performance.now(), dbl = now - lastTap < 350; lastTap = now;
    const nm = `${h.lat.toFixed(2)}°, ${h.lon.toFixed(2)}°`;
    setPoint({ id: 'pt', lat: h.lat, lon: h.lon, uz: nm, ru: nm }, dbl);
  });
}

/* ---------- 5D: lon · lat · height (probability) · time · colour (rain/snow by temperature) ----------
   prob/d5/index.json + one RGB PNG per 6-h window from prob/export_5d.py (R = probability, G = temperature, B = cloud).
   The multimodel probability rises into relief, is coloured rain or snow by the ensemble temperature, a cloud sheet floats
   above, and the GPU blends smoothly between windows as the timeline plays. The animation can be recorded and saved. */
const D5 = { idx: null, img: [], tex: [], off: 0, prod: store.get('d5prod', 'all'), mesh: null, cloud: null, cv: null, cvI: -1, rec: null };
const D5_VERT = /* glsl */`
in vec3 aDir; in vec2 aUV;
uniform sampler2D uA; uniform sampler2D uB; uniform float uF; uniform float uK; uniform float uBase; uniform int uMode;
out vec3 vW; out vec3 vD; out float vP; out float vT; out float vC;
void main(){
  vec3 v = mix(texture(uA, aUV).rgb, texture(uB, aUV).rgb, uF) * 255.0;
  vP = v.r / 250.0; vT = v.g / 2.0 - 60.0; vC = v.b / 250.0;
  float h = uMode == 0 ? smoothstep(0.06, 1.0, vP) * uK : uMode == 1 ? clamp((vT + 40.0) / 80.0, 0.0, 1.0) * uK * 0.6 : vC * uK * 0.25;
  vD = aDir; vec4 w = modelMatrix * vec4(aDir * (uBase + h), 1.0); vW = w.xyz;
  gl_Position = projectionMatrix * viewMatrix * w;
}`;
const D5_FRAG = /* glsl */`precision highp float;
in vec3 vW; in vec3 vD; in float vP; in float vT; in float vC; uniform int uMode; uniform float uOp; uniform float uCT; out vec4 outColor;
vec3 ramp3(vec3 a, vec3 b, vec3 c, float x){ return x < 0.5 ? mix(a, b, x * 2.0) : mix(b, c, x * 2.0 - 1.0); }
vec3 tcol(float t){
  float x = clamp((t + 40.0) / 80.0, 0.0, 1.0);
  vec3 s[9] = vec3[9](vec3(.18,.04,.42), vec3(.24,.44,.88), vec3(.55,.80,.94), vec3(.86,.94,.95), vec3(.96,.92,.70), vec3(.97,.72,.32), vec3(.88,.38,.16), vec3(.63,.10,.10), vec3(.24,.02,.03));
  float f = x * 8.0; int i = int(min(floor(f), 7.0)); return mix(s[i], s[i + 1], f - float(i));
}
void main(){
  vec3 n = normalize(cross(dFdx(vW), dFdy(vW))); if (dot(n, vD) < 0.0) n = -n;
  vec3 L = normalize(normalize(cameraPosition) * 0.7 + vD * 0.5 + vec3(0.0, 0.35, 0.0));
  float lit = 0.5 + 0.6 * max(dot(n, L), 0.0);
  vec3 c; float a;
  if (uMode == 0) {
    float p = clamp(vP, 0.0, 1.0);
    c = vT <= 0.5 ? ramp3(vec3(.95,.87,.96), vec3(.76,.50,.86), vec3(.43,.14,.59), p) : ramp3(vec3(.78,.89,.97), vec3(.24,.55,.88), vec3(.04,.18,.45), p);
    a = smoothstep(0.08, 0.2, p) * 0.94;
  } else if (uMode == 1) { c = tcol(vT); a = 0.86; }
  else { c = mix(vec3(.72,.76,.82), vec3(.98), vC); a = smoothstep(uCT, 1.0, vC) * 0.62; lit = 0.75 + 0.35 * lit; }
  if (a < 0.01) discard;
  outColor = vec4(c * lit, a * uOp);
}`;
function d5Geometry() {
  const I = D5.idx, sx = MOBILE ? 2 : 1, NX = Math.floor((I.W - 1) / sx) + 1, NY = Math.floor((I.H - 1) / sx) + 1;
  const dir = new Float32Array(NX * NY * 3), uv = new Float32Array(NX * NY * 2);
  for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
    const gi = i * sx, gj = j * sx, k = j * NX + i, v = vecLL(I.lon0 + gi * I.d, I.lat0 - gj * I.d, 1);
    dir.set([v.x, v.y, v.z], k * 3); uv.set([(gi + 0.5) / I.W, (gj + 0.5) / I.H], k * 2);
  }
  const idx = new Uint32Array((NX - 1) * (NY - 1) * 6); let p = 0;
  for (let j = 0; j < NY - 1; j++) for (let i = 0; i < NX - 1; i++) { const a = j * NX + i, b = a + 1, c = a + NX, d = c + 1; idx.set([a, c, b, b, c, d], p); p += 6; }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(dir.slice(), 3)); geo.setAttribute('aDir', new THREE.BufferAttribute(dir, 3));
  geo.setAttribute('aUV', new THREE.BufferAttribute(uv, 2)); geo.setIndex(new THREE.BufferAttribute(idx, 1));
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), R * 1.2);
  return geo;
}
function d5Mat(mode, order) {
  const m = new THREE.ShaderMaterial({ glslVersion: THREE.GLSL3, vertexShader: D5_VERT, fragmentShader: D5_FRAG, transparent: true, depthWrite: mode !== 2, side: THREE.DoubleSide,
    uniforms: { uA: { value: D5.blank }, uB: { value: D5.blank }, uF: { value: 0 }, uK: { value: 2.6 }, uBase: { value: R + 0.45 }, uMode: { value: mode }, uOp: { value: 1 }, uCT: { value: 0.2 } } });
  return m;
}
async function d5Init() {
  try { D5.idx = await (await fetch('prob/d5/index.json', { cache: 'no-cache' })).json(); } catch { D5.idx = null; }
  if (!D5.idx || !D5.idx.steps || !D5.idx.steps.length) { D5.idx = null; G.missing = { ...(G.missing || {}), d5: true }; return; }
  D5.off = (Date.parse(D5.idx.run) - runDate()) / 3600e3; D5.blank = blankTex();
  const geo = d5Geometry();
  D5.mesh = new THREE.Mesh(geo, d5Mat(0)); D5.mesh.renderOrder = 6; D5.mesh.frustumCulled = false; D5.mesh.visible = false;
  D5.cloud = new THREE.Mesh(geo, d5Mat(2)); D5.cloud.renderOrder = 7; D5.cloud.frustumCulled = false; D5.cloud.visible = false;
  D5.cloud.material.uniforms.uBase.value = R + 3.6;
  scene.add(D5.mesh, D5.cloud);
  G.tMax = Math.max(G.tMax, D5.off + D5.idx.steps.at(-1) - 3);
  renderTimelineDays();
}
function d5Tex(i) {
  if (D5.tex[i]) return D5.tex[i];
  if (D5.img[i] === undefined) {
    D5.img[i] = null;
    const im = new Image(); im.crossOrigin = 'anonymous';
    im.onload = () => { D5.img[i] = im; const t = new THREE.Texture(im); t.flipY = false; t.minFilter = t.magFilter = THREE.LinearFilter; t.generateMipmaps = false; t.wrapS = THREE.RepeatWrapping; t.needsUpdate = true; D5.tex[i] = t; };
    im.src = `prob/d5/s${String(D5.idx.steps[i]).padStart(3, '0')}.png`;
  }
  for (let k = 1; k < D5.idx.steps.length; k++) { if (D5.tex[i - k]) return D5.tex[i - k]; if (D5.tex[i + k]) return D5.tex[i + k]; }
  return D5.blank;
}
function d5Frame(t) { // windows are drawn at their centre (end − 3 h)
  const st = D5.idx.steps, x = t - D5.off + 3;
  if (x <= st[0]) return { i0: 0, i1: 0, f: 0 };
  for (let i = 0; i < st.length - 1; i++) if (x <= st[i + 1]) return { i0: i, i1: i + 1, f: (x - st[i]) / (st[i + 1] - st[i]) };
  return { i0: st.length - 1, i1: st.length - 1, f: 0 };
}
function d5Update() {
  const on = !!D5.idx && S.layer === 'd5';
  if (!D5.mesh) return;
  D5.mesh.visible = on; D5.cloud.visible = on && (D5.prod === 'all' || D5.prod === 'cloud');
  if (!on) return;
  const fr = d5Frame(S.t), A = d5Tex(fr.i0), B = d5Tex(fr.i1);
  // preload the next few windows so playback never waits
  for (let k = 2; k < 6; k++) if (fr.i0 + k < D5.idx.steps.length) d5Tex(fr.i0 + k);
  const mode = D5.prod === 'temp' ? 1 : D5.prod === 'cloud' ? -1 : 0;
  D5.mesh.visible = mode >= 0;
  // the relief scales with the camera height, so it never turns into a fog when you zoom in close
  const alt = camera.position.length() - R, zk = Math.max(0.03, Math.min(1, alt / 45));
  const exK = (0.7 + S.exag * 0.1) * zk, base = R + 0.02 + 0.43 * zk;
  for (const m of [D5.mesh.material, D5.cloud.material]) { const u = m.uniforms; u.uA.value = A; u.uB.value = B; u.uF.value = fr.f; u.uK.value = 2.6 * exK; }
  D5.mesh.material.uniforms.uBase.value = base;
  D5.mesh.material.uniforms.uMode.value = Math.max(0, mode);
  D5.cloud.material.uniforms.uBase.value = D5.prod === 'cloud' ? base + 0.15 * zk : base + 2.6 * exK + 0.6 * zk;
  D5.cloud.material.uniforms.uOp.value = D5.prod === 'cloud' ? 1.25 : 0.55; D5.cloud.material.uniforms.uCT.value = D5.prod === 'cloud' ? 0.2 : 0.6;
}
// values under the cursor / labels: read the current window's pixels once
function d5Value(lon, lat) {
  if (!D5.idx) return null;
  const fr = d5Frame(S.t), i = Math.round(fr.i0 + fr.f), im = D5.img[i]; if (!im) return null;
  if (D5.cvI !== i) { const c = D5.cv || (D5.cv = document.createElement('canvas')); c.width = im.width; c.height = im.height; const x = c.getContext('2d', { willReadFrequently: true }); x.drawImage(im, 0, 0); D5.px = x.getImageData(0, 0, im.width, im.height).data; D5.cvI = i; }
  const I = D5.idx; let L = lon; if (L < I.lon0) L += 360;
  const gx = Math.round((L - I.lon0) / I.d), gy = Math.round((I.lat0 - lat) / I.d);
  if (gx < 0 || gy < 0 || gx >= I.W || gy >= I.H) return null;
  const o = (gy * I.W + gx) * 4;
  return { p: Math.round(D5.px[o] / 2.5), t: D5.px[o + 1] / 2 - 60, c: Math.round(D5.px[o + 2] / 2.5) };
}
function d5Label(lon, lat) {
  const v = d5Value(lon, lat); if (!v) return '';
  const fmtT = t => `${t > 0.5 ? '+' : t < -0.5 ? '−' : ''}${Math.abs(Math.round(t))}°`;
  return D5.prod === 'temp' ? fmtT(v.t) : D5.prod === 'cloud' ? `☁ ${v.c}%` : `${v.p}%${v.t <= 0.5 && v.p >= 20 ? ' ❄' : ''} · ${fmtT(v.t)}`;
}
function renderD5Legend(el) {
  const P = (k) => tr('d5.' + k);
  const bar = D5.prod === 'temp' ? `<div class="bar"><i style="background:linear-gradient(90deg,#2e0a6b,#3d70e0,#8ccdf0,#dbf0f2,#f5ebb3,#f7b852,#e0612a,#a11a1a,#3d0508)"></i></div><div class="ticks"><span style="left:0">−40°</span><span style="left:50%">0°</span><span style="left:100%">+40°</span></div>`
    : D5.prod === 'cloud' ? `<div class="bar"><i style="background:linear-gradient(90deg,#3a4250,#b8c2d1,#fafafa)"></i></div><div class="ticks"><span style="left:0">20%</span><span style="left:100%">100%</span></div>`
    : `<div class="bar"><i style="background:linear-gradient(90deg,#c7e3f7,#3d8ce0,#0a2e73)"></i></div><div class="ticks"><span style="left:0">10%</span><span style="left:50%">${P('rain')}</span><span style="left:100%">100%</span></div>
       <div class="bar"><i style="background:linear-gradient(90deg,#f2def5,#c27fdb,#6e2496)"></i></div><div class="ticks"><span style="left:0">10%</span><span style="left:50%">${P('snow')}</span><span style="left:100%">100%</span></div>`;
  el.innerHTML = `<div class="lt">${P('title')}</div>
    <div class="seg small d5prod">${['all', 'temp', 'cloud'].map(k => `<button data-p="${k}" aria-pressed="${D5.prod === k}">${P(k)}</button>`).join('')}</div>
    <div class="lt muted">${P('leg_' + D5.prod)}</div>${bar}
    <div class="muted d5src">${(D5.idx.models || []).join(', ')}</div>
    <button class="btn d5rec" id="d5Rec">${D5.rec ? P('recStop') : P('rec')}</button> <span class="muted" id="d5RecMsg"></span>`;
  el.querySelectorAll('.d5prod button').forEach(b => b.onclick = () => { D5.prod = b.dataset.p; store.set('d5prod', D5.prod); renderLegend(); labelEls.forEach(e => e._id = null); labelTick = 7; });
  $('d5Rec').onclick = () => D5.rec ? d5RecStop() : d5RecStart();
}
// record the 15 days as a video: the WebGL frame + title, time and legend drawn on a 2D canvas
function d5RecStart() {
  const gl = $('scene'), msg = $('d5RecMsg');
  if (!window.MediaRecorder || !HTMLCanvasElement.prototype.captureStream) { msg.textContent = tr('d5.recNo'); return; }
  const sc = Math.min(1, 1280 / gl.width), W = Math.round(gl.width * sc / 2) * 2, H = Math.round(gl.height * sc / 2) * 2;
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const type = ['video/mp4;codecs=avc1.42E01E', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm'].find(t => MediaRecorder.isTypeSupported(t)) || '';
  const mr = new MediaRecorder(cv.captureStream(30), { mimeType: type, videoBitsPerSecond: 6e6 }), chunks = [];
  mr.ondataavailable = e => e.data.size && chunks.push(e.data);
  mr.onstop = async () => {
    const ext = type.includes('mp4') ? 'mp4' : 'webm', blob = new Blob(chunks, { type: type.split(';')[0] || 'video/webm' });
    const name = `osmon-5d-${D5.prod}-${D5.idx.run.slice(0, 10)}.${ext}`;
    const m = $('d5RecMsg'); if (m) m.textContent = '…';
    let ok = false;
    try { const dl = window.claude && window.claude.use ? await window.claude.use('downloads') : null; if (dl) { await dl.save({ filename: name, data: blob }); ok = true; } } catch (e) { ok = e && e.code === 'declined' ? 'no' : false; }
    if (ok === false) { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); a.remove(); ok = true; }
    const m2 = $('d5RecMsg'); if (m2) { m2.textContent = ok === true ? tr('d5.saved') : ''; setTimeout(() => m2.textContent = '', 4000); }
  };
  const t0 = Math.max(0, D5.off + D5.idx.steps[0] - 3);
  D5.rec = { mr, cv, ctx: cv.getContext('2d'), W, H, speed: S.speed, end: G.tMax };
  S.t = t0; S.speed = 12; setPlaying(true); syncTimeUI();
  mr.start(500); renderLegend();
}
function d5RecStop() { const r = D5.rec; if (!r) return; D5.rec = null; S.speed = r.speed; setPlaying(false); try { r.mr.stop(); } catch {} renderLegend(); }
function d5RecFrame() {
  const r = D5.rec; if (!r) return;
  const x = r.ctx, W = r.W, H = r.H, s = W / 1280;
  x.drawImage($('scene'), 0, 0, W, H);
  x.fillStyle = 'rgba(8,14,24,0.62)'; x.fillRect(0, 0, W, 70 * s);
  x.fillStyle = '#fff'; x.font = `600 ${26 * s}px Golos Text, system-ui, sans-serif`; x.fillText(`Osmon 5D · ${tr('d5.' + D5.prod)}`, 20 * s, 32 * s);
  x.font = `500 ${20 * s}px Golos Text, system-ui, sans-serif`; x.fillStyle = '#cfe3ff'; x.fillText(fmtTime(S.t), 20 * s, 58 * s);
  x.textAlign = 'right'; x.fillStyle = 'rgba(255,255,255,0.75)'; x.font = `${13 * s}px Golos Text, system-ui, sans-serif`;
  x.fillText((D5.idx.models || []).join(', '), W - 20 * s, 30 * s); x.fillText('ECMWF (CC BY 4.0) · NOAA', W - 20 * s, 52 * s); x.textAlign = 'left';
  // progress bar
  const t0 = Math.max(0, D5.off + D5.idx.steps[0] - 3), f = Math.max(0, Math.min(1, (S.t - t0) / (r.end - t0)));
  x.fillStyle = 'rgba(255,255,255,0.25)'; x.fillRect(0, H - 6 * s, W, 6 * s); x.fillStyle = '#5aa9ff'; x.fillRect(0, H - 6 * s, W * f, 6 * s);
  if (S.t >= r.end - 0.5 || (r.lastT != null && S.t < r.lastT)) d5RecStop(); else r.lastT = S.t;
}
function d5Enter() { D5.entered = true; flyTo(66, 41, { dist: MOBILE ? 60 : 46, tilt: 1.0 }); setPlaying(true); }

/* ------------------------------ UI ------------------------------ */
const LAYERS = [
  { id: 'd5', sw: 'linear-gradient(90deg,#3d8ce0,#0a2e73,#c27fdb,#f7b852)' },
  { id: 'relief', sw: 'linear-gradient(90deg,#2b5a8a,#6b8a4a,#b9a27a,#eef)' },
  { id: 'temp', sw: 'linear-gradient(90deg,#007fff,#d9ff00,#ffb000,#ff2500)' },
  { id: 'rain', sw: 'linear-gradient(90deg,#00ffff,#0000ff,#ff00ff)' },
  { id: 'wind', sw: 'linear-gradient(90deg,#ffff66,#93ff00,#00724b)' },
  { id: 'sun', sw: 'linear-gradient(90deg,#0d4144,#a8a84c,#ffff00,#fd8802)' },
];
function renderLayerButtons() {
  $('layerBtns').innerHTML = LAYERS.filter(l => !G.missing?.[l.id]).map(l => `<button data-layer="${l.id}" aria-pressed="${S.layer === l.id}"><i style="background:${l.sw}"></i>${tr('layer.' + l.id)}</button>`).join('');
  $('layerBtns').querySelectorAll('button').forEach(b => b.onclick = () => { const was = S.layer; S.layer = b.dataset.layer; store.set('layer', S.layer); if (S.layer === 'd5' && was !== 'd5') d5Enter(); renderLayerButtons(); renderLegend(); labelTick = 7; labelEls.forEach(e => e._id = null); });
}
function renderLegend() {
  const L = S.layer, el = $('legend');
  if (L === 'd5') { if (D5.idx) renderD5Legend(el); return; }
  if (L === 'relief') { el.innerHTML = `<div class="lt">${tr('leg.relief')}</div><div class="bar"><i style="background:linear-gradient(90deg,#1d3d6b,#3d6e3a,#a89070,#e8e2d0,#ffffff)"></i></div><div class="ticks"><span style="left:0">0</span><span style="left:50%">3000</span><span style="left:100%">8000 ${tr('m')}</span></div>`; return; }
  const used = D.classes[L].filter(c => c.rgb).slice(L === 'temp' ? 3 : 0);
  const every = Math.ceil(used.length / 6);
  const ticks = used.map((c, i) => [i / used.length, c.lo]).filter((_, i) => i % every === 0); ticks.push([1, used.at(-1).hi]);
  el.innerHTML = `<div class="lt">${tr('leg.' + L)}</div><div class="bar">${used.map(c => `<i style="background:${rgbCss(c.rgb)}"></i>`).join('')}</div>
    <div class="ticks">${ticks.map(([p, v]) => `<span style="left:${(p * 100).toFixed(1)}%">${v}</span>`).join('')}</div>`;
}
function renderTimelineDays() {
  const el = $('tlDays'); const out = [];
  const width = el.getBoundingClientRect().width || 800, nDays = G.tMax / 24, every = width / nDays < 48 ? 2 : 1;
  let k = 0;
  for (let t = 0; t <= G.tMax; t += 6) {
    const p = localParts(timeAt(t));
    if (p.h === 5 && k++ % every === 0) out.push(`<span style="left:${(t / G.tMax * 100).toFixed(2)}%">${width / nDays < 70 ? p.d : WD[S.lang][p.wd] + ' ' + p.d}</span>`);
  }
  el.innerHTML = out.join('');
}
function syncTimeUI() {
  $('tl').value = S.t;
  $('tlTime').textContent = fmtTime(S.t);
  $('tlRel').textContent = `+${Math.round(S.t)} h`;
  if (S.A) renderPanelNow();
}
function setPlaying(p) { S.playing = p; $('playBtn').textContent = p ? '❚❚' : '▶'; $('playBtn').setAttribute('aria-label', p ? 'Pause' : 'Play'); }

const ctyName = c => S.lang === 'ru' ? c[2] : (CTY_UZ[c[0]] || c[1]);
function searchCountries(q) {
  if (!q || !GEO.cty) return [];
  return GEO.cty.filter(c => [c[1], c[2], CTY_UZ[c[0]] || ''].some(n => n.toLowerCase().startsWith(q)) || c[0].toLowerCase() === q).slice(0, 4);
}
function flyToCountry(c) {
  const [, , , lx, ly, w, s, e, n] = c;
  const span = Math.max((e - w) * Math.cos(((s + n) / 2) * DEG), n - s) * 111e3 * R / EARTH_M; // scene units
  if (span > R * 0.9) flyTo(lx, Math.max(-60, Math.min(60, ly)), { local: false });
  else flyTo((w + e) / 2, (s + n) / 2, { dist: Math.max(1.5, span * 1.25), tilt: 0.55 });
  if (S.route !== 'map') location.hash = '#map';
  if (matchMedia('(max-width: 1100px)').matches) showSheet(null);
}
function searchPlaces(q) {
  q = q.trim().toLowerCase();
  if (!q) return D.cities.map(c => ({ ...c, preset: true }));
  const out = [];
  for (const c of D.cities) if (c.uz.toLowerCase().includes(q) || c.ru.toLowerCase().includes(q)) out.push({ ...c, preset: true });
  for (const p of GEO.places) { if (out.length > 14) break; if (p[2].toLowerCase().includes(q) || p[3].toLowerCase().includes(q) || (UZ_PLACE[p[2]] || '').toLowerCase().includes(q)) { if (!out.some(o => o.ru === p[3])) out.push({ id: 'np' + p[0] + p[1], lon: p[0], lat: p[1], uz: UZ_PLACE[p[2]] || p[2], ru: p[3], country: p[6] }); } }
  return out;
}
function renderPlaces() {
  const q = $('search').value;
  const m = q.trim().match(/^(-?\d+(?:\.\d+)?)\s*[,; ]\s*(-?\d+(?:\.\d+)?)$/);
  let html = '';
  if (m) html += `<li><button data-ll="${m[1]},${m[2]}"><span class="pl-name">${fmtLL(+m[1], +m[2])}</span><span class="pl-meta">→</span></button></li>`;
  const list = m ? [] : searchPlaces(q);
  const ctys = m ? [] : searchCountries(q.trim().toLowerCase());
  html += ctys.map((c, i) => `<li><button data-c="${i}"><span><span class="pl-name">${ctyName(c)}</span> <span class="pl-c">${tr('loc.country')}</span></span><span class="pl-meta">${c[0]} →</span></button></li>`).join('');
  html += list.map((c, i) => {
    const cur = (S.pickTarget === 'B' ? S.B : S.A)?.id === c.id;
    return `<li><button data-i="${i}" class="${S.pickTarget === 'B' ? 'cmp' : ''}" aria-current="${cur}"><span><span class="pl-name">${pname(c)}</span> <span class="pl-c">${c.country || ''}</span></span><span class="pl-meta">${fmtT(valueAt('temp', S.t, c.lon, c.lat))}</span></button></li>`;
  }).join('');
  $('places').innerHTML = html;
  $('places').querySelectorAll('button[data-i]').forEach(b => b.onclick = () => selectPlace(list[+b.dataset.i]));
  $('places').querySelectorAll('button[data-c]').forEach(b => b.onclick = () => flyToCountry(ctys[+b.dataset.c]));
  $('places').querySelectorAll('button[data-ll]').forEach(b => b.onclick = () => { const [lat, lon] = b.dataset.ll.split(',').map(Number); const nm = `${lat.toFixed(2)}°, ${lon.toFixed(2)}°`; setPoint({ id: 'pt', lat, lon, uz: nm, ru: nm }, true); });
}
function renderSaved() {
  const saved = store.get('saved', []);
  $('savedEmpty').hidden = saved.length > 0;
  $('saved').innerHTML = saved.map((p, i) => `<li><button data-i="${i}"><span class="pl-name">${p.name}</span><span class="pl-meta">${p.lat.toFixed(2)}, ${p.lon.toFixed(2)}</span></button></li>`).join('');
  $('saved').querySelectorAll('button').forEach(b => b.onclick = () => { const p = saved[+b.dataset.i]; setPoint({ id: 'pt', lat: p.lat, lon: p.lon, uz: p.name, ru: p.name }, true); });
}
function selectPlace(c) { setPoint({ ...c }, true); }
function setPoint(p, flyThere) {
  if (S.pickTarget === 'B') S.B = p; else S.A = p;
  store.set(S.pickTarget === 'B' ? 'pointB' : 'pointA', { lat: p.lat, lon: p.lon, id: p.id, uz: p.uz, ru: p.ru, meteogram: p.meteogram || null, here: !!p.here });
  renderPlaces(); renderPanel(); S.panelClosed = false; route(true);
  if (S.route === 'forecast') renderForecastPage();
  if (flyThere && S.route === 'map') flyTo(p.lon, p.lat, { dist: inReg(p.lon, p.lat) ? 4.5 : 9 });
  if (matchMedia('(max-width: 1100px)').matches && S.route === 'map') showSheet('panel');
}
// nearest named place to a point (for "you are here")
function nearestPlace(lat, lon) {
  let best = null, bd = 1e9;
  for (const c of candidates) { const d = (c.lat - lat) ** 2 + ((c.lon - lon) * Math.cos(lat * DEG)) ** 2; if (d < bd) { bd = d; best = c; } }
  return bd < 0.25 * 0.25 ? best : null; // within ~25 km
}
function locateMe(loud) {
  if (!navigator.geolocation) { if (loud) showMsg(tr('loc.geoFail')); return; }
  if (loud) showMsg(tr('loc.geoAsk'));
  navigator.geolocation.getCurrentPosition(pos => {
    const lat = pos.coords.latitude, lon = pos.coords.longitude, near = nearestPlace(lat, lon);
    const nm = near ? `${pname(near)} · ${tr('loc.here')}` : `${tr('loc.here')} · ${lat.toFixed(2)}°, ${lon.toFixed(2)}°`;
    store.set('geoDone', true);
    S.pickTarget = 'A';
    setPoint({ id: 'pt', lat, lon, uz: nm, ru: nm, here: true }, true);
    $('geoMsg').hidden = true;
  }, () => { store.set('geoDone', true); if (loud) showMsg(tr('loc.geoFail')); }, { timeout: 10000, maximumAge: 600000 });
}
function showMsg(t) { const el = $('geoMsg'); el.textContent = t; el.hidden = false; clearTimeout(showMsg.t); showMsg.t = setTimeout(() => el.hidden = true, 6000); }

function renderPanel() {
  const p = S.A; if (!p) return;
  $('pName').textContent = pname(p);
  $('pCoords').textContent = `${fmtLL(p.lat, p.lon)} · ${tr('elev')} ${fmtElev(p.lon, p.lat)} · ${tr('res')}: ${inReg(p.lon, p.lat) ? tr('resReg') : tr('resGlo')}`;
  renderPanelNow();
  const days = daily(series(p)).slice(0, 10);
  $('pDays').innerHTML = days.map(d => {
    const f = fmtDay(d.key);
    const extra = [d.snow ? `<span class="chip snow">${tr('snow')}</span>` : '', d.wind ? `<span class="chip wind">${d.wind}+ ${tr('ms')}</span>` : ''].join(' ');
    return `<div class="day-row"><div class="d"><b>${f.wd}</b><span>${f.dm}</span></div>
      <div class="t">${fmtTshort(d.tDay)}° <span class="n">/ ${fmtTshort(d.tNight)}°</span> ${extra}</div>
      <div class="r">${d.rainAny ? `${r1(d.rain[0])}–${r1(d.rain[1])} ${tr('mm')}` : '·'}</div></div>`;
  }).join('');
}
function windStat(p) {
  if (!D.wind) return '';
  const lv = WIND.lv[S.windLvl]; if (!lv || !lv.u) return '';
  const [u, v] = windAt(lv, windFrame(S.t), p.lon, p.lat), sp = Math.hypot(u, v);
  const from = (Math.atan2(-u, -v) / DEG + 360) % 360, dirs = tr('dir');
  return `<div class="stat"><div class="k">${tr('windNow')} · ${tr('lvl.' + S.windLvl)}</div><div class="v">${sp.toFixed(sp < 10 ? 1 : 0)} <small>${tr('ms')} · ${Array.isArray(dirs) ? dirs[Math.round(from / 45) % 8] : ''} <span style="display:inline-block;transform:rotate(${from + 180}deg)">↑</span></small></div></div>`;
}
function astroStats(p) {
  const date = timeAt(S.t), el = sunElev(p.lat, p.lon, date), st = sunTimes(p.lat, p.lon, date), mi = moonInfo(date);
  const hm = t => { if (!t) return '—'; const l = new Date(t + TZ * 3600e3); return `${String(l.getUTCHours()).padStart(2, '0')}:${String(l.getUTCMinutes()).padStart(2, '0')}`; };
  const mel = Math.asin(Math.max(-1, Math.min(1, vecLL(p.lon, p.lat, 1).dot(vecLL(mi.lon, mi.lat, 1))))) / DEG;
  return `<div class="stat"><div class="k">☀ ${tr('astro.sun')}</div><div class="v"><small>↑ ${hm(st.rise)} · ↓ ${hm(st.set)} · ${tr('astro.elev')} ${Math.round(el)}°</small></div></div>
    <div class="stat"><div class="k">☾ ${tr('astro.moon')}</div><div class="v"><small>${Math.round(mi.lit * 100)} % ${tr('astro.lit')}, ${tr(mi.waxing ? 'astro.waxing' : 'astro.waning')} · ${tr('astro.elev')} ${Math.round(mel)}°</small></div></div>`;
}
function renderPanelNow() {
  const p = S.A; if (!p) return;
  const t = valueAt('temp', S.t, p.lon, p.lat), r = valueAt('rain', S.t, p.lon, p.lat), w = valueAt('wind', S.t, p.lon, p.lat), s = valueAt('sun', S.t, p.lon, p.lat);
  $('pNow').innerHTML = `
    <div class="stat big"><div class="k">${tr('temp')} · ${fmtTime(S.t)}</div><div class="v">${fmtT(t)}</div></div>
    <div class="stat"><div class="k">${tr('rain6')}</div><div class="v">${r.k ? `${r.lo}–${r.hi} <small>${tr('mm')}</small>` : `<small>${tr('noRain')}</small>`}</div></div>
    <div class="stat"><div class="k">${tr('wind')}</div><div class="v">${w.k ? `${w.lo}–${w.hi} <small>${tr('ms')}</small>` : `<small>${tr('calm')}</small>`}</div></div>
    ${G.missing.sun ? '' : `<div class="stat"><div class="k">${tr('sun')}</div><div class="v">${s.lo}–${s.hi} <small>${tr('h')}</small></div></div>`}
    ${windStat(p)}
    ${astroStats(p)}
    <div class="stat"><div class="k">${tr('elev')}</div><div class="v"><small>${fmtElev(p.lon, p.lat)}</small></div></div>`;
}

/* ---------- forecast page ---------- */
function chartSvg(sA, sB) {
  const W = 980, H = 300, padL = 40, padR = 40, top = 16, mid = 190, bot = 270;
  const tmax = sA.temp.at(-1).step, X = s => padL + (s / tmax) * (W - padL - padR);
  const allT = [...sA.temp, ...(sB ? sB.temp : [])];
  let lo = Math.floor(Math.min(...allT.map(s => s.lo)) / 4) * 4, hi = Math.ceil(Math.max(...allT.map(s => s.hi)) / 4) * 4; if (hi - lo < 12) hi = lo + 12;
  const Y = v => top + (hi - v) / (hi - lo) * (mid - top);
  const rmax = Math.max(4, ...sA.rain.map(s => s.k ? s.hi : 0), ...(sB ? sB.rain.map(s => s.k ? s.hi : 0) : [0]));
  const RY = v => bot - (v / rmax) * (bot - mid - 18);
  const accent = cssVar('--accent'), cmp = cssVar('--compare'), sky = cssVar('--sky'), line = cssVar('--line'), fg = cssVar('--fg');
  let g = '';
  for (let v = lo; v <= hi; v += 4) g += `<line x1="${padL}" x2="${W - padR}" y1="${Y(v)}" y2="${Y(v)}" stroke="${line}"/><text x="${padL - 6}" y="${Y(v) + 3}" text-anchor="end">${sgn(v)}°</text>`;
  if (lo < 0 && hi > 0) g += `<line x1="${padL}" x2="${W - padR}" y1="${Y(0)}" y2="${Y(0)}" stroke="${sky}" stroke-dasharray="3 3"/>`;
  for (let s = 0; s <= tmax; s += 6) { const p = localParts(timeAt(s)); if (p.h === 5) g += `<line x1="${X(s)}" x2="${X(s)}" y1="${top}" y2="${bot}" stroke="${line}"/><text x="${X(s) + 4}" y="${bot + 14}">${WD[S.lang][p.wd]} ${p.d}</text>`; }
  g += `<line x1="${padL}" x2="${W - padR}" y1="${bot}" y2="${bot}" stroke="${line}"/><text x="${W - padR + 6}" y="${RY(rmax) + 3}">${rmax}</text><text x="${W - padR + 6}" y="${bot}">0 ${tr('mm')}</text>`;
  const band = (sr, color, op) => {
    const up = sr.temp.map(s => `${X(s.step).toFixed(1)},${Y(s.hi).toFixed(1)}`), dn = sr.temp.slice().reverse().map(s => `${X(s.step).toFixed(1)},${Y(s.lo).toFixed(1)}`);
    const midp = sr.temp.map(s => `${X(s.step).toFixed(1)},${Y((s.lo + s.hi) / 2).toFixed(1)}`);
    return `<polygon points="${up.join(' ')} ${dn.join(' ')}" fill="${color}" fill-opacity="${op}"/><polyline points="${midp.join(' ')}" fill="none" stroke="${color}" stroke-width="2"/>`;
  };
  const bars = (sr, color, off) => sr.rain.filter(s => s.k).map(s => { const x = X(s.step) - 6 + off; return `<rect x="${x}" y="${RY(s.hi)}" width="5" height="${bot - RY(s.hi)}" fill="${color}" fill-opacity="0.35"/><rect x="${x}" y="${RY(s.lo)}" width="5" height="${bot - RY(s.lo)}" fill="${color}"/>`; }).join('');
  g += band(sA, accent, 0.25); if (sB) g += band(sB, cmp, 0.2);
  g += bars(sA, sky, 0); if (sB) g += bars(sB, cmp, 5);
  g += `<line x1="${X(S.t)}" x2="${X(S.t)}" y1="${top}" y2="${bot}" stroke="${fg}" stroke-opacity="0.5"/>`;
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${tr('fc.chart')}">${g}</svg>`;
}
function renderForecastPage() {
  const el = $('page-forecast'), p = S.A;
  if (!p) { el.innerHTML = ''; return; }
  const sA = series(p), sB = S.B ? series(S.B) : null;
  const dA = daily(sA).slice(0, 10), dB = sB ? daily(sB) : null;
  const meteo = p.meteogram ? `<img src="data/${p.meteogram}" alt="${tr('fc.meteo')}: ${pname(p)}" loading="lazy">` : '';
  const ecmwfLink = `https://charts.ecmwf.int/products/opencharts_meteogram?lat=${p.lat.toFixed(3)}&lon=${p.lon.toFixed(3)}&epsgram=classical_10d`;
  el.innerHTML = `<div class="inner">
    <div><div class="eyebrow">${tr('fc.title')}</div><h1>${pname(p)}${S.B ? ` <span style="color:var(--compare)">↔ ${pname(S.B)}</span>` : ''}</h1>
      <div class="coords">${fmtLL(p.lat, p.lon)} · ${tr('elev')} ${fmtElev(p.lon, p.lat)} · ${tr('res')}: ${sA.src === 'reg' ? tr('resReg') : tr('resGlo')} · ${tr('run')}: ECMWF IFS ${D.run.slice(0, 13).replace('T', ' ')} UTC</div></div>
    <div class="card"><h3>${tr('fc.days')}</h3><div class="daygrid">${dA.map(d => {
      const f = fmtDay(d.key), b = dB?.find(x => x.key === d.key);
      return `<div class="dcard"><div class="h">${f.wd} <span>${f.dm}</span></div>
        <div class="tt">${fmtTshort(d.tDay)}°</div><div style="color:var(--muted);font:12px var(--f-mono)">${tr('night')} ${fmtTshort(d.tNight)}°</div>
        <div class="mm">${d.rainAny ? `☂ ${r1(d.rain[0])}–${r1(d.rain[1])} ${tr('mm')}` : `☂ ${tr('noRain')}`}</div>
        ${d.sun ? `<div class="sun">☀ ${d.sun.lo}–${d.sun.hi} ${tr('h')}</div>` : ''}
        ${d.snow ? `<span class="chip snow">${tr('snow')}</span>` : ''}${d.wind ? ` <span class="chip wind">${d.wind}+ ${tr('ms')}</span>` : ''}
        ${b ? `<div class="b">${pname(S.B)}: ${fmtTshort(b.tDay)}° / ${fmtTshort(b.tNight)}°</div>` : ''}</div>`;
    }).join('')}</div></div>
    <div class="card"><h3>${tr('fc.chart')}</h3>
      <div class="legend-inline"><span><i style="background:var(--accent)"></i>${pname(p)} — ${tr('fc.band')}</span>${S.B ? `<span><i style="background:var(--compare)"></i>${pname(S.B)}</span>` : ''}<span><i style="background:var(--sky)"></i>${tr('fc.bars')}</span></div>
      <div class="chart-wrap">${chartSvg(sA, sB)}</div><p class="hint">${tr('fc.precise')}</p></div>
    <div class="grid2">
      <div class="card meteo"><h3>${tr('fc.meteo')}</h3>${meteo}<p class="hint">${tr('fc.meteoNote')}</p><a href="${ecmwfLink}" target="_blank" rel="noopener">${tr('fc.meteoOpen')}</a></div>
      <div class="card"><h3>${tr('fc.compare')}</h3>${S.B ? compareTable(dA, dB) : `<p class="hint">${tr('fc.noB')}</p>`}</div>
    </div></div>`;
}
function compareTable(dA, dB) {
  return `<table class="cmp"><thead><tr><th></th><th>${pname(S.A)}</th><th>${pname(S.B)}</th></tr></thead><tbody>${dA.map(d => {
    const b = dB.find(x => x.key === d.key), f = fmtDay(d.key);
    return `<tr><td>${f.wd} ${f.dm}</td><td class="n">${fmtTshort(d.tDay)}° · ${d.rainAny ? r1(d.rain[1]) + ' ' + tr('mm') : '—'}</td><td class="n">${b ? `${fmtTshort(b.tDay)}° · ${b.rainAny ? r1(b.rain[1]) + ' ' + tr('mm') : '—'}` : '—'}</td></tr>`;
  }).join('')}</tbody></table>`;
}

/* ---------- ECMWF maps page ---------- */
let galSel = { g: 0, f: 0 };
function renderMapsPage() {
  const el = $('page-maps'), gal = (D.gallery || []).filter(g => g.frames.length);
  if (!gal.length) { el.innerHTML = `<div class="inner"><h1>${tr('maps.title')}</h1><p class="hint">${tr('maps.empty')}</p></div>`; return; }
  galSel.g = Math.min(galSel.g, gal.length - 1); const g = gal[galSel.g]; galSel.f = Math.min(galSel.f, g.frames.length - 1); const f = g.frames[galSel.f];
  el.innerHTML = `<div class="inner"><h1>${tr('maps.title')}</h1><p class="hint">${tr('maps.note')}</p>
    <div class="gal-controls"><div class="seg">${gal.map((x, i) => `<button data-g="${i}" aria-pressed="${i === galSel.g}">${x.title[S.lang]}</button>`).join('')}</div></div>
    <div class="gal-controls"><div class="seg">${g.frames.map((x, i) => { const p = localParts(new Date(x.valid)); return `<button data-f="${i}" aria-pressed="${i === galSel.f}">${WD[S.lang][p.wd]} ${p.d}</button>`; }).join('')}</div></div>
    <img class="gal-img" src="data/${f.src}" alt="${g.title[S.lang]} — ${fmtTime(f.step)}">
    <p class="hint">© ECMWF, CC BY 4.0 · ${g.product}</p></div>`;
  el.querySelectorAll('[data-g]').forEach(b => b.onclick = () => { galSel = { g: +b.dataset.g, f: galSel.f }; renderMapsPage(); });
  el.querySelectorAll('[data-f]').forEach(b => b.onclick = () => { galSel.f = +b.dataset.f; renderMapsPage(); });
}

/* ---------- precipitation probability report (prob/: multi-model videos for the CIS and Turkey) ---------- */
const PROB_TXT = {
  uz: { title: 'Yog‘ingarchilik bo‘lish ehtimolligi · MDH va Turkiya', run: 'Prognoz hisobi', none: 'Bu hudud uchun video hali tayyor emas.', speed: 'Tezlik', frame: 'Davr',
    h1: 'Nima ko‘rsatiladi', p1: 'Har 6 soatlik davrda kamida 0,2 mm yog‘in tushish ehtimolligi: ko‘k — yomg‘ir, binafsha — qor (harorat 0° atrofida va past). Kulrang — bulutli joylar, chiziqlar — harorat (izotermalar, 0° qalin ko‘k). Shaharlar yonida — ehtimollik va harorat. Pastda — asosiy shahar uchun butun davr: ustunlar ehtimollik, qizil chiziq harorat.',
    h2: 'Qanday hisoblanadi', p2: 'Har bir model tizimi teng vazn oladi: ECMWF IFS ansambli, ECMWF AIFS ansambli, NOAA GEFS ansambli va deterministik modellar (ECMWF IFS, ECMWF AIFS, GFS, ICON) birgalikda. Harorat va bulutlar — ECMWF xaritalaridan (charts.ecmwf.int).',
    h3: 'Manbalar', p3: 'ECMWF ochiq ma’lumotlari (CC BY 4.0), NOAA (GEFS, GFS), DWD (ICON), chegaralar — Natural Earth. Har 12 soatda avtomatik yangilanadi.' },
  ru: { title: 'Вероятность осадков · СНГ и Турция', run: 'Расчёт прогноза', none: 'Видео для этой территории пока не готово.', speed: 'Скорость', frame: 'Период',
    h1: 'Что показано', p1: 'Вероятность осадков не менее 0,2 мм за каждый 6-часовой период: синим — дождь, фиолетовым — снег (температура около 0° и ниже). Серым — облачность, линиями — температура (изотермы, 0° — толстая синяя). У городов — вероятность и температура. Внизу — весь период для главного города: столбики — вероятность, красная линия — температура.',
    h2: 'Как считается', p2: 'Каждая модельная система получает равный вес: ансамбль ECMWF IFS, ансамбль ECMWF AIFS, ансамбль NOAA GEFS и детерминированные модели (ECMWF IFS, ECMWF AIFS, GFS, ICON) вместе. Температура и облака — с карт ECMWF (charts.ecmwf.int).',
    h3: 'Источники', p3: 'Открытые данные ECMWF (CC BY 4.0), NOAA (GEFS, GFS), DWD (ICON), границы — Natural Earth. Обновляется автоматически каждые 12 часов.' },
  tr: { title: 'Yağış olasılığı · BDT ve Türkiye', run: 'Tahmin çalıştırması', none: 'Bu bölge için video henüz hazır değil.', speed: 'Hız', frame: 'Dönem',
    h1: 'Ne gösteriliyor', p1: 'Her 6 saatlik dönemde en az 0,2 mm yağış olasılığı: mavi yağmur, mor kar (sıcaklık 0° civarı ve altı). Gri bulutlu alanlar, çizgiler sıcaklık (izotermler, 0° kalın mavi). Şehirlerin yanında olasılık ve sıcaklık. Altta ana şehir için tüm dönem: sütunlar olasılık, kırmızı çizgi sıcaklık.',
    h2: 'Nasıl hesaplanıyor', p2: 'Her model sistemi eşit ağırlık alır: ECMWF IFS topluluğu, ECMWF AIFS topluluğu, NOAA GEFS topluluğu ve deterministik modeller (ECMWF IFS, ECMWF AIFS, GFS, ICON) birlikte. Sıcaklık ve bulutlar ECMWF haritalarından (charts.ecmwf.int).',
    h3: 'Kaynaklar', p3: 'ECMWF açık verileri (CC BY 4.0), NOAA (GEFS, GFS), DWD (ICON), sınırlar: Natural Earth. Her 12 saatte otomatik güncellenir.' },
};
const PROB_NAMES = { cis: { uz: 'MDH va Turkiya', ru: 'СНГ и Турция', tr: 'BDT ve Türkiye' }, UZ: { uz: 'O‘zbekiston', ru: 'Узбекистан', tr: 'Özbekistan' },
  KZ: { uz: 'Qozog‘iston', ru: 'Казахстан', tr: 'Kazakistan' }, KG: { uz: 'Qirg‘iziston', ru: 'Кыргызстан', tr: 'Kırgızistan' }, TJ: { uz: 'Tojikiston', ru: 'Таджикистан', tr: 'Tacikistan' },
  TM: { uz: 'Turkmaniston', ru: 'Туркменистан', tr: 'Türkmenistan' }, AZ: { uz: 'Ozarbayjon', ru: 'Азербайджан', tr: 'Azerbaycan' }, AM: { uz: 'Armaniston', ru: 'Армения', tr: 'Ermenistan' },
  BY: { uz: 'Belarus', ru: 'Беларусь', tr: 'Belarus' }, MD: { uz: 'Moldova', ru: 'Молдова', tr: 'Moldova' }, RU: { uz: 'Rossiya', ru: 'Россия', tr: 'Rusya' }, TR: { uz: 'Turkiya', ru: 'Турция', tr: 'Türkiye' } };
const PROB = { M: null, region: store.get('probRegion', 'UZ'), lang: null, rate: store.get('probRate', 1), product: store.get('probProduct', 'prob') };
const PROB_UI = {
  uz: { prob: '🌧 Yog‘in va qor', temp: '🌡 Harorat', cloud: '☁ Bulutlar', dl: '⬇ Animatsiyani yuklab olish', dlOk: 'Saqlandi', dlNo: 'Yuklab bo‘lmadi', today: 'Bugun', tomorrow: 'Ertaga', ago: h => `${h} soat oldin hisoblangan`, share: '✈ Telegramda ulashish', copy: '🔗 Havolani nusxalash', copied: 'Nusxalandi', past: 'o‘tgan', days: 'Kunlar bo‘yicha izoh', wd: ['Yak', 'Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan'] },
  ru: { prob: '🌧 Осадки и снег', temp: '🌡 Температура', cloud: '☁ Облачность', dl: '⬇ Скачать анимацию', dlOk: 'Сохранено', dlNo: 'Не удалось скачать', today: 'Сегодня', tomorrow: 'Завтра', ago: h => `рассчитан ${h} ч назад`, share: '✈ Поделиться в Telegram', copy: '🔗 Скопировать ссылку', copied: 'Скопировано', past: 'прошло', days: 'Комментарии по дням', wd: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'] },
  tr: { prob: '🌧 Yağış ve kar', temp: '🌡 Sıcaklık', cloud: '☁ Bulutluluk', dl: '⬇ Animasyonu indir', dlOk: 'Kaydedildi', dlNo: 'İndirilemedi', today: 'Bugün', tomorrow: 'Yarın', ago: h => `${h} saat önce hesaplandı`, share: '✈ Telegram’da paylaş', copy: '🔗 Bağlantıyı kopyala', copied: 'Kopyalandı', past: 'geçti', days: 'Günlük yorumlar', wd: ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'] },
};
async function saveVideo(url, name) {
  // inside claude.ai the page may only hand files over through the downloads capability; elsewhere a plain link works
  try {
    if (window.claude && window.claude.use) {
      const dl = await window.claude.use('downloads');
      if (dl) { const blob = await (await fetch(url)).blob(); await dl.save({ filename: name, data: blob }); return true; }
    }
  } catch (e) { if (e && e.code === 'declined') return false; }
  const a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); return true;
}
function probLink() { return `${location.href.split('#')[0]}#prob/${PROB.region}/${PROB.lang || S.lang}/${PROB.product}`; }
function probNowFrame(M) { // the 6-h window that contains the current moment
  if (!M.steps || !M.run) return 0; const h = (Date.now() - Date.parse(M.run)) / 3600e3;
  const i = M.steps.findIndex(s => h <= s); return i < 0 ? M.steps.length - 1 : Math.max(0, i);
}
async function renderProbPage() {
  const el = $('page-prob');
  if (!PROB.M) {
    el.innerHTML = `<div class="inner prob"><p class="muted">…</p></div>`;
    try { PROB.M = await (await fetch('prob/manifest.json', { cache: 'no-cache' })).json(); } catch { PROB.M = { items: [] }; }
  }
  const M = PROB.M, lang = PROB.lang || S.lang, t = PROB_TXT[lang];
  const have = [...new Set(M.items.map(i => i.region))];
  if (!have.includes(PROB.region)) PROB.region = have[0] || 'cis';
  const U = PROB_UI[lang];
  const prods = ['prob', 'temp', 'cloud'].filter(pr => M.items.some(i => i.region === PROB.region && i.lang === lang && (i.product || 'prob') === pr));
  if (!prods.includes(PROB.product)) PROB.product = 'prob';
  const it = M.items.find(i => i.region === PROB.region && i.lang === lang && (i.product || 'prob') === PROB.product);
  const days = M.items.find(i => i.region === PROB.region && i.lang === lang && i.product === 'days');
  const n = it ? it.frames : 0, fps = M.fps || 1;
  const dayOf = f => { if (!M.steps || !days) return null; const d = new Date(Date.parse(M.run) + (M.steps[f] - 3 + (days.off || 0)) * 3600e3); return d.toISOString().slice(0, 10); };
  const today = new Date(Date.now() + ((days && days.off) || 5) * 3600e3).toISOString().slice(0, 10);
  const tmrw = new Date(Date.now() + (((days && days.off) || 5) + 24) * 3600e3).toISOString().slice(0, 10);
  const ageH = M.run ? Math.max(0, Math.round((Date.now() - Date.parse(M.run)) / 3600e3)) : null;
  if (history.replaceState && S.route === 'prob') history.replaceState(null, '', '#prob/' + PROB.region + '/' + lang + '/' + PROB.product);
  const dd = days && days.days ? days.days : {};
  const card = (dd[today] || dd[tmrw]) ? `<div class="prob-now">${[[today, U.today], [tmrw, U.tomorrow]].filter(([d]) => dd[d]).map(([d, lbl]) => `<div><b>${lbl}</b><span>${dd[d]}</span></div>`).join('')}</div>` : '';
  el.innerHTML = `<div class="inner prob">
    <div class="prob-head"><div><h1>${t.title.split(' · ')[0]} · ${PROB_NAMES[PROB.region][lang]}</h1><div class="muted mono">${M.run ? `${t.run}: ${M.run.slice(0, 16).replace('T', ' ')} UTC (${U.ago(ageH)}) · ${(M.models || []).join(', ')}` : ''}</div></div>
      <div class="seg" id="probLang">${['uz', 'ru', 'tr'].map(l => `<button data-l="${l}" aria-pressed="${l === lang}">${l === 'uz' ? 'O‘zbek' : l === 'ru' ? 'Русский' : 'Türkçe'}</button>`).join('')}</div></div>
    <div class="chips" id="probRegions">${['cis', 'UZ', 'KZ', 'KG', 'TJ', 'TM', 'AZ', 'AM', 'BY', 'MD', 'RU', 'TR'].filter(r => have.includes(r)).map(r => `<button data-r="${r}" aria-pressed="${r === PROB.region}">${PROB_NAMES[r][lang]}</button>`).join('')}</div>
    ${prods.length > 1 ? `<div class="seg" id="probProd">${prods.map(pr => `<button data-p="${pr}" aria-pressed="${pr === PROB.product}">${U[pr]}</button>`).join('')}</div>` : ''}
    ${card}
    ${it ? `<div class="prob-stage"><video id="probVideo" src="prob/${it.video}" muted loop playsinline autoplay preload="auto"></video></div>
    <div class="prob-ctl">
      <button class="icon-btn" id="probPlay" aria-label="Play">❚❚</button>
      <button class="icon-btn" id="probPrev" aria-label="−6 h">‹</button>
      <input type="range" id="probSeek" min="0" max="${n - 1}" step="1" value="0" aria-label="${t.frame}">
      <button class="icon-btn" id="probNext" aria-label="+6 h">›</button>
      <span class="mono muted" id="probIdx">1 / ${n}</span>
      <span class="seg small" id="probRate" aria-label="${t.speed}">${[0.5, 1, 2].map(r => `<button data-r="${r}" aria-pressed="${r === PROB.rate}">${r}×</button>`).join('')}</span>
      <button class="btn" id="probDl">${U.dl}</button> <a class="btn" id="probShare" target="_blank" rel="noopener" href="https://t.me/share/url?url=${encodeURIComponent(probLink())}&text=${encodeURIComponent(t.title + ' · ' + PROB_NAMES[PROB.region][lang])}">${U.share}</a> <button class="btn" id="probCopy">${U.copy}</button> <span class="muted mono" id="probDlMsg"></span>
    </div>` : `<p class="muted">${t.none}</p>`}
    ${days && days.days ? `<section class="prob-days"><h2>${U.days}${days.city ? ' · ' + days.city : ''}</h2><ol id="probDays">${Object.entries(days.days).map(([d, txt]) => { const dt_ = new Date(d + 'T12:00:00Z'); return `<li data-d="${d}"${d < today ? ` class="past" title="${U.past}"` : ''}><b>${U.wd[dt_.getUTCDay()]}, ${String(dt_.getUTCDate()).padStart(2, '0')}.${String(dt_.getUTCMonth() + 1).padStart(2, '0')}</b><span>${txt}</span></li>`; }).join('')}</ol></section>` : ''}
    <div class="prob-notes"><div><h2>${t.h1}</h2><p>${t.p1}</p></div><div><h2>${t.h2}</h2><p>${t.p2}</p></div><div><h2>${t.h3}</h2><p>${t.p3}</p></div></div>
  </div>`;
  const selChip = el.querySelector('#probRegions [aria-pressed="true"]'); if (selChip) selChip.scrollIntoView({ block: 'nearest', inline: 'center' });
  el.querySelectorAll('#probLang button').forEach(b => b.onclick = () => { PROB.lang = b.dataset.l; renderProbPage(); });
  el.querySelectorAll('#probRegions button').forEach(b => b.onclick = () => { PROB.region = b.dataset.r; store.set('probRegion', PROB.region); renderProbPage(); });
  el.querySelectorAll('#probProd button').forEach(b => b.onclick = () => { PROB.product = b.dataset.p; store.set('probProduct', PROB.product); renderProbPage(); });
  el.querySelectorAll('#probDays li').forEach(li => li.onclick = () => { const v = $('probVideo'); if (!v || !M.steps) return; const f = M.steps.findIndex((_, i) => dayOf(i) === li.dataset.d); if (f >= 0) { v.pause(); $('probPlay').textContent = '▶'; v.currentTime = (f + 0.5) / fps; } });
  if (!it) return;
  const v = $('probVideo'), seek = $('probSeek'), idx = $('probIdx');
  const frameOf = () => Math.min(n - 1, Math.floor(v.currentTime * fps + 1e-3));
  v.playbackRate = PROB.rate;
  v.addEventListener('loadedmetadata', () => { v.playbackRate = PROB.rate; const f0 = probNowFrame(M); if (f0 > 0 && f0 < n) v.currentTime = (f0 + 0.5) / fps; }, { once: true });
  $('probCopy').onclick = async () => { const msg = $('probDlMsg'); try { await navigator.clipboard.writeText(probLink()); msg.textContent = U.copied; } catch { msg.textContent = probLink(); } setTimeout(() => msg.textContent = '', 3000); };
  el.onkeydown = null;
  let lastDay = '';
  v.addEventListener('timeupdate', () => { const f = frameOf(); seek.value = f; idx.textContent = `${f + 1} / ${n}`;
    const d = dayOf(f); if (d !== lastDay) { lastDay = d; el.querySelectorAll('#probDays li').forEach(li => li.classList.toggle('now', li.dataset.d === d)); } });
  $('probDl').onclick = async () => { const msg = $('probDlMsg'); msg.textContent = '…'; const ok = await saveVideo('prob/' + it.video, it.video); msg.textContent = ok ? U.dlOk : U.dlNo; setTimeout(() => msg.textContent = '', 4000); };
  const go = f => { v.pause(); $('probPlay').textContent = '▶'; v.currentTime = (Math.max(0, Math.min(n - 1, f)) + 0.5) / fps; };
  seek.oninput = () => go(+seek.value);
  $('probPrev').onclick = () => go(frameOf() - 1); $('probNext').onclick = () => go(frameOf() + 1);
  $('probPlay').onclick = () => { if (v.paused) { v.play(); $('probPlay').textContent = '❚❚'; } else { v.pause(); $('probPlay').textContent = '▶'; } };
  el.querySelectorAll('#probRate button').forEach(b => b.onclick = () => { PROB.rate = +b.dataset.r; store.set('probRate', PROB.rate); v.playbackRate = PROB.rate; el.querySelectorAll('#probRate button').forEach(x => x.setAttribute('aria-pressed', String(x === b))); });
}

/* ---------- text pages ---------- */
const PAGES = {
  guide: {
    uz: `<h1>Qo‘llanma</h1>
      <p><b>Globus.</b> Sichqoncha bilan aylantiring, g‘ildirak bilan yaqinlashtiring. Shahar yoki nuqtani tanlasangiz, kamera o‘sha joyga uchib boradi va tog‘larni yon tomondan ko‘rsatadi; u yerda o‘ng tugma bilan suring, chap tugma bilan aylantiring. «Butun dunyo» tugmasi globusga qaytaradi. Ikki marta bosish — nuqtaga uchish.</p>
      <p><b>Qatlamlar.</b> Relyef (NASA sun’iy yo‘ldosh tasviri), harorat (2 m), so‘nggi 6 soatdagi yog‘in, 10 m/s dan kuchli shamol va kunlik quyosh nuri. «Tog‘ balandligi» relyefni bo‘rttiradi. «Kun va tun» quyoshning haqiqiy holatini va tungi shahar chiroqlarini ko‘rsatadi.</p>
      <p><b>Vaqt.</b> Pastdagi shkala — 10 kun, har 6 soat; ▶ animatsiya (1× — bir soniyada 2 soat). Yomg‘ir tomchilari va qor parchalari yog‘in bor joyda yog‘adi: harorat 0° dan past bo‘lsa — qor.</p>
      <p><b>Bulutlar.</b> ECMWF modelining sun’iy yo‘ldosh infraqizil tasviri (har 6 soat) asosida: past bulutlar, o‘rta qatlam va baland momaqaldiroq bulutlari alohida qatlamlarda; ularning soyasi yerga tushadi.</p>
      <p><b>Chegaralar.</b> Davlatlar doim; viloyatlar va shaharlar chegaralari yaqinlashganda paydo bo‘ladi.</p>
      <p><b>Aniqlik.</b> O‘rta Osiyo uchun ECMWF ning ~11 km li mintaqaviy xaritalari, qolgan dunyo uchun ~50 km li global xaritalar ishlatiladi.</p>`,
    ru: `<h1>Руководство</h1>
      <p><b>Глобус.</b> Вращайте мышью, приближайте колесом. При выборе города или точки камера перелетает туда и показывает горы сбоку; там правая кнопка сдвигает, левая вращает. Кнопка «Весь мир» возвращает глобус. Двойное нажатие — перелёт к точке.</p>
      <p><b>Слои.</b> Рельеф (спутниковый снимок NASA), температура на 2 м, осадки за 6 часов, ветер сильнее 10 м/с и солнечное сияние за сутки. «Высота гор» усиливает рельеф. «День и ночь» показывает настоящее положение Солнца и ночные огни городов.</p>
      <p><b>Время.</b> Шкала внизу — 10 дней с шагом 6 часов; ▶ запускает анимацию (1× — 2 часа прогноза в секунду). Капли дождя и снежинки падают там, где есть осадки; ниже 0° — снег.</p>
      <p><b>Облака.</b> По модельному инфракрасному снимку ECMWF (каждые 6 часов): низкие облака, средний ярус и высокие грозовые башни лежат на разной высоте и отбрасывают тени на землю.</p>
      <p><b>Границы.</b> Страны видны всегда; границы областей и контуры городов появляются при приближении.</p>
      <p><b>Детализация.</b> Для Центральной Азии используются региональные карты ECMWF (~11 км), для остального мира — глобальные (~50 км).</p>`,
  },
  about: {
    uz: `<h1>Ma’lumotlar haqida</h1>
      <p><b>Ob-havo</b> — faqat <a href="https://charts.ecmwf.int" target="_blank" rel="noopener">charts.ecmwf.int</a> (ECMWF OpenCharts, IFS modeli). Skript har 12 soatda «Global» va «Western Asia» xaritalarini yuklab, rang shkalasi bo‘yicha qiymatlarga aylantiradi: harorat (4 °C qadam), 6 soatlik yog‘in, 10 m/s dan kuchli shamol, quyosh nuri; meteogrammalar — ECMWF ENS.</p>
      <p><b>Relyef</b> — ochiq balandlik modeli (AWS Terrain Tiles: SRTM, GMTED, ETOPO); O‘rta Osiyo uchun ~1–3 km, dunyo uchun ~20 km. <b>Tasvir</b> — O‘rta Osiyo uchun Sentinel-2 cloudless (<a href="https://s2maps.eu" target="_blank" rel="noopener">s2maps.eu</a>, EOX IT Services GmbH; Copernicus Sentinel ma’lumotlari asosida, CC BY-NC-SA 4.0), qolgan dunyo uchun NASA Blue Marble va Black Marble. <b>Chegaralar va shaharlar</b> — Natural Earth (ommaviy mulk).</p>
      <p class="muted">Cheklovlar: qiymatlar xarita shkalasi aniqligida; bulutlar ECMWF ning «Simulated images – infrared» xaritalaridan olinadi: bulut qancha sovuq (baland) bo‘lsa, shuncha qalin ko‘rinadi; 10 m/s dan past shamol ko‘rsatilmaydi.</p>
      <p>Litsenziya: ob-havo © ECMWF, <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a>. Bu sayt ECMWF bilan bog‘liq emas.</p>`,
    ru: `<h1>О данных</h1>
      <p><b>Погода</b> — только <a href="https://charts.ecmwf.int" target="_blank" rel="noopener">charts.ecmwf.int</a> (ECMWF OpenCharts, модель IFS). Скрипт каждые 12 часов скачивает карты «Global» и «Western Asia» и переводит цвета шкал в значения: температура (шаг 4 °C), осадки за 6 ч, ветер от 10 м/с, солнечное сияние; метеограммы — ECMWF ENS.</p>
      <p><b>Рельеф</b> — открытая модель высот (AWS Terrain Tiles: SRTM, GMTED, ETOPO), для Центральной Азии ~1–3 км, для мира ~20 км. <b>Изображение Земли</b> — для Центральной Азии Sentinel-2 cloudless (<a href="https://s2maps.eu" target="_blank" rel="noopener">s2maps.eu</a>, EOX IT Services GmbH; содержит изменённые данные Copernicus Sentinel, CC BY-NC-SA 4.0), для остального мира NASA Blue Marble и Black Marble. <b>Границы и города</b> — Natural Earth (общественное достояние).</p>
      <p class="muted">Ограничения: точность — шаг шкалы карт; облака взяты с карт ECMWF «Simulated images – infrared»: чем холоднее (выше) верхняя граница облака, тем оно плотнее и выше на глобусе; ветер слабее 10 м/с не показывается.</p>
      <p>Лицензия: погода © ECMWF, <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a>. Сайт не связан с ECMWF.</p>`,
  },
};

/* ---------- routing, sheets, i18n ---------- */
function route(keepSheet) {
  const [r, ...rest] = (location.hash || '#map').slice(1).split('/');
  if (r === 'prob' && rest.length) { const [rg, lg, pr] = rest; if (PROB_NAMES[rg]) PROB.region = rg; if (PROB_UI[lg]) PROB.lang = lg; if (['prob', 'temp', 'cloud'].includes(pr)) PROB.product = pr; }
  S.route = ['map', 'forecast', 'prob', 'maps', 'guide', 'about'].includes(r) ? r : 'map';
  document.querySelectorAll('.nav a').forEach(a => a.setAttribute('aria-current', a.dataset.route === S.route ? 'page' : 'false'));
  for (const p of ['forecast', 'prob', 'maps', 'guide', 'about']) $('page-' + p).hidden = S.route !== p;
  if (S.route === 'prob') renderProbPage(); else { const v = document.querySelector('#page-prob video'); if (v) v.pause(); }
  $('timeline').hidden = S.route !== 'map';
  $('app').classList.toggle('panel-closed', S.route !== 'map' || !S.A || S.panelClosed);
  if (S.route === 'forecast') renderForecastPage();
  if (S.route === 'maps') renderMapsPage();
  if (S.route === 'guide' || S.route === 'about') $('page-' + S.route).innerHTML = `<div class="inner">${PAGES[S.route][S.lang]}</div>`;
  if (keepSheet !== true) showSheet(null);
  requestAnimationFrame(resize);
}
function showSheet(which) {
  const app = $('app');
  app.classList.toggle('show-panel', which === 'panel');
  app.classList.toggle('show-side', which === 'side');
  document.querySelectorAll('.bottom-nav button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mob === (which || 'map'))));
}
function applyLang() {
  document.documentElement.lang = S.lang;
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = tr(el.dataset.i18n); });
  document.querySelectorAll('[data-i18n-ph]').forEach(el => { el.placeholder = tr(el.dataset.i18nPh); });
  document.querySelectorAll('[data-i18n-title]').forEach(el => { el.title = tr(el.dataset.i18nTitle); el.setAttribute('aria-label', tr(el.dataset.i18nTitle)); });
  $('langUz').setAttribute('aria-pressed', S.lang === 'uz'); $('langRu').setAttribute('aria-pressed', S.lang === 'ru');
  if (!D) return;
  const run = localParts(new Date(D.run)), gen = localParts(new Date(D.generated));
  $('runInfo').textContent = `${tr('run')}: ${run.d} ${MON[S.lang][run.m]} ${String(run.h).padStart(2, '0')}:00 · ${tr('updated')} ${gen.d} ${MON[S.lang][gen.m]} ${String(gen.h).padStart(2, '0')}:${String(new Date(D.generated).getUTCMinutes()).padStart(2, '0')}`;
  renderLayerButtons(); renderLegend(); renderTimelineDays(); syncTimeUI(); renderPlaces(); renderSaved(); renderPanel(); renderWindLevels();
  labelEls.forEach(e => e._id = null);
  route();
}
function themeIcon() { const cur = document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'); $('themeBtn').textContent = cur === 'light' ? '☾' : '☀'; }
function initTheme() {
  const t = store.get('theme', null);
  if (t) document.documentElement.dataset.theme = t;
  themeIcon();
  $('themeBtn').onclick = () => {
    const cur = document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    const next = cur === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = next; store.set('theme', next); themeIcon();
    if (S.route === 'forecast') renderForecastPage();
  };
}
function bindUI() {
  $('langUz').onclick = () => { S.lang = 'uz'; store.set('lang', 'uz'); applyLang(); };
  $('langRu').onclick = () => { S.lang = 'ru'; store.set('lang', 'ru'); applyLang(); };
  $('tl').max = G.tMax;
  $('tl').oninput = e => { S.t = +e.target.value; setPlaying(false); syncTimeUI(); };
  $('playBtn').onclick = () => setPlaying(!S.playing);
  $('fxToggle').onclick = () => { const h = document.querySelector('.hud-tl'), o = !h.classList.contains('open'); h.classList.toggle('open', o); $('fxToggle').setAttribute('aria-expanded', String(o)); };
  if (MOBILE) $('legend').classList.add('mini');
  $('legend').addEventListener('click', e => { if (e.target.classList.contains('lt') && MOBILE) $('legend').classList.toggle('mini'); });
  document.querySelectorAll('.speed button').forEach(b => b.onclick = () => { S.speed = +b.dataset.speed; document.querySelectorAll('.speed button').forEach(x => x.setAttribute('aria-pressed', String(x === b))); });
  $('fxPrecip').onchange = e => { S.fxPrecip = e.target.checked; };
  $('fxWind').onchange = e => { S.fxWind = e.target.checked; };
  renderWindLevels();
  $('fxClouds').onchange = e => { S.fxClouds = e.target.checked; };
  $('fxSun').checked = S.fxSun; $('fxSun').onchange = e => { S.fxSun = e.target.checked; store.set('sun', S.fxSun); };
  $('fxBorders').onchange = e => { S.fxBorders = e.target.checked; };
  $('exag').value = S.exag; $('exagVal').textContent = '×' + S.exag;
  $('exag').oninput = e => { S.exag = +e.target.value; $('exagVal').textContent = '×' + S.exag; store.set('exag5', S.exag); updateExag(); };
  $('viewGlobe').onclick = () => { const [lon, lat] = llVec(mode === 'local' ? controls.target : camera.position); flyTo(lon, Math.max(-60, Math.min(60, lat)), { local: false }); };
  $('viewFly').onclick = () => { if (S.A) flyTo(S.A.lon, S.A.lat, { dist: inReg(S.A.lon, S.A.lat) ? 4.5 : 9 }); };
  $('viewTop').onclick = () => { if (!S.A) return; flyTo(S.A.lon, S.A.lat, { dist: 14, tilt: 0.02 }); };
  $('viewShot').onclick = snapshot;
  $('viewTour').onclick = () => (TOUR.on ? stopTour() : startTour());
  $('search').oninput = renderPlaces;
  $('search').onkeydown = e => { if (e.key === 'Enter') { const b = $('places').querySelector('button'); if (b) b.click(); } };
  $('tabMain').onclick = () => { S.pickTarget = 'A'; $('tabMain').setAttribute('aria-pressed', 'true'); $('tabCompare').setAttribute('aria-pressed', 'false'); renderPlaces(); };
  $('tabCompare').onclick = () => { S.pickTarget = 'B'; $('tabCompare').setAttribute('aria-pressed', 'true'); $('tabMain').setAttribute('aria-pressed', 'false'); renderPlaces(); showMsg(tr('loc.cmpHint')); };
  $('geoBtn').onclick = () => locateMe(true);
  $('saveBtn').onclick = () => {
    const p = S.A; if (!p) return;
    const saved = store.get('saved', []);
    if (!saved.some(x => Math.abs(x.lat - p.lat) < 1e-3 && Math.abs(x.lon - p.lon) < 1e-3)) saved.unshift({ name: pname(p), lat: p.lat, lon: p.lon });
    store.set('saved', saved.slice(0, 12)); renderSaved();
  };
  $('panelClose').onclick = () => { S.panelClosed = true; showSheet(null); route(); };
  document.querySelectorAll('.bottom-nav button').forEach(b => b.onclick = () => {
    const w = b.dataset.mob;
    if (S.route !== 'map') location.hash = '#map';
    if (w === 'map') showSheet(null); else { S.panelClosed = false; showSheet(w); }
  });
  window.addEventListener('hashchange', route);
  window.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT') return;
    if (S.route === 'prob') { const k = { ArrowLeft: 'probPrev', ArrowRight: 'probNext', ' ': 'probPlay' }[e.key]; if (k && $(k)) { e.preventDefault(); $(k).click(); } return; }
    if (S.route !== 'map') return;
    if (e.key === ' ') { e.preventDefault(); setPlaying(!S.playing); }
    if (e.key === 'ArrowRight') { S.t = Math.min(G.tMax, Math.round(S.t / 6) * 6 + 6); syncTimeUI(); }
    if (e.key === 'ArrowLeft') { S.t = Math.max(0, Math.round(S.t / 6) * 6 - 6); syncTimeUI(); }
  });
}

/* ---------- boot ---------- */
function setLoading(text) { const s = $('loading').querySelector('span'); if (s) s.textContent = text; }
async function boot() {
  initTheme(); applyLang();
  const getJson = async u => (await fetch(u, { cache: 'no-cache' })).json();
  [D, GEO] = await Promise.all([window.__FORECAST__ || getJson('data/forecast.json'), getJson(ASSET + 'assets/geo.json')]);
  if (!D.wind) D.wind = await getJson('data/wind.json').catch(() => null); // real wind (pipeline/wind.py), optional
  prepare();
  await loadDem();
  const nowH = (Date.now() - runDate()) / 3600e3;
  S.t = Math.max(0, Math.min(G.tMax, Math.round(nowH / 6) * 6));
  const a = store.get('pointA', null);
  S.A = a && a.lat != null ? { ...a } : { ...D.cities.find(c => c.id === 'toshkent') };
  await initScene();
  await d5Init();
  if (S.layer === 'd5' && !D5.idx) S.layer = 'temp';
  buildLabels(); bindUI(); applyLang();
  $('loading').hidden = true;
  requestAnimationFrame(loop);
  window.__osmon = { S, flyTo, BLD, WIND, CU, cam: () => ({ d: camera.position.distanceTo(controls.target), mode, fly: !!fly }), setT: t => { S.t = t; syncTimeUI(); } }; // small hook for tests / console
  setTimeout(() => { if (S.layer === 'd5') d5Enter(); else if (!D5.entered) flyTo(S.A.lon, S.A.lat, { dist: inReg(S.A.lon, S.A.lat) ? 5 : 10 }); }, 900);
  // first visit: ask for the location once (or silently reuse an existing permission)
  if (!a && !store.get('geoDone', false)) setTimeout(() => locateMe(false), 1200);
  else if (navigator.permissions) navigator.permissions.query({ name: 'geolocation' }).then(st => { if (st.state === 'granted' && a && a.here) locateMe(false); }).catch(() => {});
}
boot().catch(e => { console.error(e); $('loading').innerHTML = `<span class="err">${tr('loadFail')}</span><code style="font-size:11px;max-width:80vw">${String(e && e.stack || e).slice(0, 400)}</code>`; });
