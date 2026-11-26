// Osmon Telegram bot (Cloudflare Workers, free plan).
//  • Private chat: /start → language → country/continent → today & tomorrow, by days, 15-day videos, the site as a Mini App.
//  • Groups and channels: add the bot (as admin in a channel) and it posts the forecast by itself after every update
//    every day at the hour the group picked (default 07:00 Tashkent). An admin picks the language, one or several
//    countries and the hour with /sozla (/settings). Each post: 3 videos + today/tomorrow/next days + weather by city.
//  • /help: instructions in Uzbek, Russian and English.
//  • /hit and /stats: anonymous visit counter for the website (daily totals per country and city).
// Everything is read from the website built by GitHub Actions (SITE_URL/prob/manifest.json and the .mp4 files).
// Settings (Workers → Settings): BOT_TOKEN (secret), SITE_URL (variable), D1 database bound as DB,
// cron trigger (e.g. every 20 minutes) for the automatic group posts.
// Connect once: open <worker URL>/setup in a browser (webhook, command menus, bot description).

const NAMES = {
  world: { uz: 'Butun dunyo', ru: 'Весь мир', en: 'Whole world' }, EU: { uz: 'Yevropa', ru: 'Европа', en: 'Europe' }, AS: { uz: 'Osiyo', ru: 'Азия', en: 'Asia' },
  AF: { uz: 'Afrika', ru: 'Африка', en: 'Africa' }, NA: { uz: 'Shimoliy Amerika', ru: 'Северная Америка', en: 'North America' },
  SA: { uz: 'Janubiy Amerika', ru: 'Южная Америка', en: 'South America' }, OC: { uz: 'Okeaniya', ru: 'Океания', en: 'Oceania' },
  cis: { uz: 'MDH va Turkiya', ru: 'СНГ и Турция', en: 'CIS and Türkiye' }, UZ: { uz: 'O‘zbekiston', ru: 'Узбекистан', en: 'Uzbekistan' },
  KZ: { uz: 'Qozog‘iston', ru: 'Казахстан', en: 'Kazakhstan' }, KG: { uz: 'Qirg‘iziston', ru: 'Кыргызстан', en: 'Kyrgyzstan' },
  TJ: { uz: 'Tojikiston', ru: 'Таджикистан', en: 'Tajikistan' }, TM: { uz: 'Turkmaniston', ru: 'Туркменистан', en: 'Turkmenistan' },
  AZ: { uz: 'Ozarbayjon', ru: 'Азербайджан', en: 'Azerbaijan' }, AM: { uz: 'Armaniston', ru: 'Армения', en: 'Armenia' },
  BY: { uz: 'Belarus', ru: 'Беларусь', en: 'Belarus' }, MD: { uz: 'Moldova', ru: 'Молдова', en: 'Moldova' },
  RU: { uz: 'Rossiya', ru: 'Россия', en: 'Russia' }, TR: { uz: 'Turkiya', ru: 'Турция', en: 'Türkiye' },
};
const FLAG = { world: '🌍', EU: '🌍', AF: '🌍', AS: '🌏', OC: '🌏', NA: '🌎', SA: '🌎', cis: '🗺', UZ: '🇺🇿', KZ: '🇰🇿', KG: '🇰🇬', TJ: '🇹🇯', TM: '🇹🇲', AZ: '🇦🇿', AM: '🇦🇲', BY: '🇧🇾', MD: '🇲🇩', RU: '🇷🇺', TR: '🇹🇷' };
const GROUPS = [['UZ', 'KZ', 'KG'], ['TJ', 'TM', 'AZ'], ['AM', 'BY', 'MD'], ['RU', 'TR', 'cis'], ['world', 'EU', 'AS'], ['AF', 'NA', 'SA'], ['OC']];
const T = {
  uz: {
    cities: '🏙 Shaharlar', cPick: '🏙 Shaharni tanlang:', cTitle: '🏙 Bugun shaharlarda', time: '⏰ Guruhga prognoz qaysi vaqtda yuborilsin? (Toshkent vaqti)', help: 'ℹ️ Yordam',
    d15: '15 kunlik prognoz', hi: '☀️ <b>Osmon</b> — ob-havo prognozi\n6 ta model (ECMWF, NOAA) asosida 15 kunga.\n\nTilni tanlang:', pick: '📍 Davlat yoki qit’ani tanlang:',
    menu: 'Nimani ko‘rsatay?', today: '⏱ Bugun va ertaga soatma-soat', all: '🎬 15 kunlik video', days: '🗓 15 kun', site: '🗺 Sayt va globus', rep: '📊 Hisobot', menuHint: '⌨️ Barcha bo‘limlar — pastdagi tugmalarda.\n📍 Joylashuvni yuboring yoki shahar nomini yozing, masalan: Namangan', locAsk: '📍 Pastdagi tugmani bosing — joylashuvingiz yuboriladi.',
    back: '↩️ Davlatlar', none: '⏳ Ma’lumot hali tayyor emas, birozdan keyin urinib ko‘ring.', tdy: 'Bugun', tmw: 'Ertaga', next: 'Keyingi kunlar',
    upd: 'Yangilandi', swipe: '🎬 Videoni suring: 🌧 yog‘in · 🌡 harorat · ☁️ bulutlar · 💨 shamol', bot: '🤖 Bot',
    gHi: '👋 Salom! Men har kuni shu yerga ob-havoni video bilan yuboraman.\nGuruh admini: til, davlat va vaqtni tanlang 👇 (/sozla)',
    gSet: '✅ Tayyor! Har kuni soat {time} da (Toshkent vaqti) bu chatga prognoz yuboriladi: <b>{name}</b> ({lang}).\nO‘zgartirish: /sozla', gMulti: '📍 Davlatlarni tanlang (bir nechtasini ham), so‘ng «Tayyor» tugmasini bosing:', done: '✅ Tayyor', gNone: 'Kamida bitta davlatni tanlang.', gAdm: '⚙️ Guruh sozlamalarini faqat shu guruhning admini o‘zgartira oladi. Undan /sozla yozishini so‘rang.', gLang: 'Tilni tanlang:', lang: 'o‘zbekcha',
    pdf: '📄 Yo‘riqnoma (PDF)', adm: '✉️ Adminga yozish', admAsk: '✍️ Bot adminiga xabaringizni yozing (matn, rasm yoki ovozli xabar) — men uni yetkazaman.\nBekor qilish: /cancel', admSent: '✅ Xabaringiz adminga yuborildi. Javob shu chatga keladi.', admAns: '💬 Admin javobi:', admOff: 'Admin hali ulanmagan, keyinroq urinib ko‘ring.', cancel: 'Bekor qilindi.', guideCap: '📄 Osmon bot — to‘liq yo‘riqnoma',
    sub: '🔔 Har kuni', unsub: '🔕 O‘chirish', subAsk: '🔔 {name} prognozini har kuni soat nechada yuboray? (Toshkent vaqti)', subOk: '✅ Har kuni soat {time} da shu yerga prognoz keladi: {name}.\nO‘chirish: menyudagi 🔔 tugmasi.', subOff: '🔕 Kunlik yuborish o‘chirildi.',
  },
  ru: {
    cities: '🏙 Города', cPick: '🏙 Выберите город:', cTitle: '🏙 Сегодня по городам', time: '⏰ Во сколько присылать прогноз в группу? (по Ташкенту)', help: 'ℹ️ Помощь',
    d15: 'прогноз на 15 дней', hi: '☀️ <b>Osmon</b> — прогноз погоды\nна 15 дней по 6 моделям (ECMWF, NOAA).\n\nВыберите язык:', pick: '📍 Выберите страну или континент:',
    menu: 'Что показать?', today: '⏱ Сегодня и завтра по часам', all: '🎬 Видео на 15 дней', days: '🗓 15 дней', site: '🗺 Сайт и глобус', rep: '📊 Отчёт', menuHint: '⌨️ Все разделы — на кнопках внизу.\n📍 Отправьте геолокацию или напишите город, например: Наманган', locAsk: '📍 Нажмите кнопку внизу — бот получит ваше место.',
    back: '↩️ Страны', none: '⏳ Данные ещё не готовы, попробуйте чуть позже.', tdy: 'Сегодня', tmw: 'Завтра', next: 'Дальше',
    upd: 'Обновлено', swipe: '🎬 Листайте видео: 🌧 осадки · 🌡 температура · ☁️ облака · 💨 ветер', bot: '🤖 Бот',
    gHi: '👋 Привет! Я буду каждый день присылать сюда прогноз погоды с видео.\nАдминистратор группы: выберите язык, страны и время 👇 (/settings)',
    gSet: '✅ Готово! Каждый день в {time} (по Ташкенту) в этот чат будет приходить прогноз: <b>{name}</b> ({lang}).\nИзменить: /settings', gMulti: '📍 Отметьте страны (можно несколько) и нажмите «Готово»:', done: '✅ Готово', gNone: 'Отметьте хотя бы одну страну.', gAdm: '⚙️ Настройки меняет только администратор этой группы. Попросите его написать /settings.', gLang: 'Выберите язык:', lang: 'по-русски',
    pdf: '📄 Инструкция (PDF)', adm: '✉️ Написать админу', admAsk: '✍️ Напишите сообщение администратору бота (текст, фото или голосовое) — я передам.\nОтмена: /cancel', admSent: '✅ Сообщение отправлено администратору. Ответ придёт в этот чат.', admAns: '💬 Ответ администратора:', admOff: 'Администратор бота ещё не подключён, попробуйте позже.', cancel: 'Отменено.', guideCap: '📄 Бот Osmon — полная инструкция',
    sub: '🔔 Каждый день', unsub: '🔕 Отключить', subAsk: '🔔 Во сколько каждый день присылать прогноз: {name}? (по Ташкенту)', subOk: '✅ Каждый день в {time} сюда будет приходить прогноз: {name}.\nОтключить — кнопка 🔔 в меню.', subOff: '🔕 Ежедневная рассылка отключена.',
  },
  en: {
    cities: '🏙 Cities', cPick: '🏙 Choose a city:', cTitle: '🏙 Today in the cities', time: '⏰ At what time should the group get the forecast? (Tashkent time)', help: 'ℹ️ Help',
    d15: '15-day forecast', hi: '☀️ <b>Osmon</b> — weather forecast\nfor 15 days from 6 models (ECMWF, NOAA).\n\nChoose a language:', pick: '📍 Choose a country or continent:',
    menu: 'What shall I show?', today: '⏱ Today and tomorrow by the hour', all: '🎬 15-day video', days: '🗓 15 days', site: '🗺 Website and globe', rep: '📊 Report', menuHint: '⌨️ All sections are on the buttons below.\n📍 Send your location or type a city name, e.g.: London', locAsk: '📍 Press the button below — your location will be sent.',
    back: '↩️ Countries', none: '⏳ The data is not ready yet, try again a little later.', tdy: 'Today', tmw: 'Tomorrow', next: 'Next days',
    upd: 'Updated', swipe: '🎬 Swipe the videos: 🌧 precipitation · 🌡 temperature · ☁️ clouds · 💨 wind', bot: '🤖 Bot',
    gHi: '👋 Hello! Every day I will send a weather forecast with videos here.\nGroup admin: choose the language, country and time 👇 (/settings)',
    gSet: '✅ Done! Every day at {time} (Tashkent time) this chat will get the forecast: <b>{name}</b> ({lang}).\nTo change: /settings', gMulti: '📍 Tick the countries (you can pick several) and press «Done»:', done: '✅ Done', gNone: 'Choose at least one country.', gAdm: '⚙️ Only an admin of this group can change the settings. Ask them to type /settings.', gLang: 'Choose a language:', lang: 'English',
    pdf: '📄 Guide (PDF)', adm: '✉️ Write to the admin', admAsk: '✍️ Write your message to the bot admin (text, photo or voice), I will pass it on.\nCancel: /cancel', admSent: '✅ Your message has been sent to the admin. The answer will come to this chat.', admAns: '💬 Answer from the admin:', admOff: 'The bot admin is not connected yet, try later.', cancel: 'Cancelled.', guideCap: '📄 Osmon bot — the full guide',
    sub: '🔔 Every day', unsub: '🔕 Turn off', subAsk: '🔔 At what time shall I send the forecast for {name} every day? (Tashkent time)', subOk: '✅ Every day at {time} the forecast for {name} will come here.\nTo turn it off: the 🔔 button in the menu.', subOff: '🔕 Daily sending is turned off.',
  },
};
const HELP = {
  uz: `ℹ️ <b>Osmon — qanday foydalanish</b>

<b>Pastdagi tugmalar</b>
⏱ <b>Bugun va ertaga soatma-soat</b> — 48 soatlik ovozli video va «🗺 Interaktiv xarita»: xaritaga bosing — o‘sha joy ob-havosi; pastdagi soatlar chizig‘ini suring; ▶ — ijro, 🔈 — ob-havo ovozi, ⛶ — to‘liq ekran
🗓 <b>15 kunlik prognoz</b> — shaharni tanlang, kunlar bo‘yicha prognoz keladi
🎬 <b>15 kunlik video-prognoz</b> — shahringiz yoki davlat uchun yog‘in va harorat videosi
📅 <b>Haftalar va oylar</b> — davrni tugma bilan tanlang: o‘tgan hafta, keyingi haftalar, oylar, chang
🏔 <b>Tog‘lar: qor va sayohat</b> — 10 kunlik rasm (qor, yomg‘ir, yaxshi kunlar); joy nomli tugma — batafsil; 🔔 — qor haqida xabar
🌡 <b>Hozirgi ob-havo</b> — joyingizda hozir qanday
🌫 <b>Bugungi havo sifati</b> — chang va havo sifati soatma-soat
🏙 <b>Shaharni tanlash</b> · 🌍 <b>Davlatni almashtirish</b>
📍 <b>Joyimni yuborish</b> — aynan sizning nuqtangiz uchun prognoz (yoki shunchaki shahar nomini yozing)
🔔 <b>Har tongi prognoz</b> — kunlik prognoz siz tanlagan vaqtda
⏰ <b>Bildirishnomalarim</b> — nima va soat nechada kelsin: soatma-soat, haftalar, tog‘lar, havo sifati
⚠️ <b>Xavfli ob-havo</b> — kuchli yog‘in, chang
🎯 <b>Prognoz aniqligi</b> — prognozlar haqiqiy ob-havo bilan solishtiriladi
🗺 <b>Xarita-sayt va globus</b> — sayt Telegram ichida ochiladi

<b>Avtomatik yuborish</b>
Bo‘limlar ostida «⏰ Avtomatik yuborish» tugmasi bor: vaqtni tanlang — bo‘lim o‘zi keladi. O‘chirish — o‘sha yerda yoki «⏰ Bildirishnomalarim» da. Vaqt — Toshkent vaqti.

<b>Guruh yoki kanalda</b>
1. Botni guruhga qo‘shing (kanalda — admin qilib, «xabar yuborish» huquqi bilan).
2. Admin /sozla yozadi: til → davlatlar (bir nechta) → «Tayyor» → yuborish vaqti.
3. Har kuni tanlangan vaqtda har bir davlat uchun post keladi.
4. Keyin «⏰ Bu chatga nima yuborilsin» chiqadi: soatma-soat, haftalar, tog‘lar, havo sifati, qor xabari — har biriga vaqt, yoki «✅ Hammasini yoqish». Keyinroq: /notify
/bugun — guruhda hozirgi prognoz.

✉️ Savol yoki taklif — /admin, javob shu yerga keladi
📄 /guide — PDF yo‘riqnoma

Ma’lumot: ECMWF, NOAA, DWD modellari; havo sifati — CAMS. Har 3 soatda yangilanadi.`,
  ru: `ℹ️ <b>Osmon — как пользоваться</b>

<b>Кнопки внизу экрана</b>
⏱ <b>Сегодня и завтра по часам</b> — видео со звуком на 48 часов и «🗺 Интерактивная карта»: нажмите на карту — погода в этой точке; тяните полосу часов внизу; ▶ — проиграть, 🔈 — звук погоды, ⛶ — во весь экран
🗓 <b>Прогноз на 15 дней</b> — выберите город и получите прогноз по дням
🎬 <b>Видео-прогноз 15 дней</b> — видео осадков и температуры для вашего города или страны
📅 <b>Недели и месяцы</b> — выберите период кнопкой: прошедшая неделя, следующие недели, месяцы, пыль
🏔 <b>Горы: снег и поездки</b> — картинка на 10 дней (снег, дождь, хорошие дни); кнопка с названием места — подробно; 🔔 — сигнал о снеге
🌡 <b>Погода сейчас</b> — что сейчас в вашем месте
🌫 <b>Воздух сегодня</b> — пыль и качество воздуха по часам
🏙 <b>Выбрать город</b> · 🌍 <b>Сменить страну</b>
📍 <b>Отправить моё место</b> — прогноз точно для вашей точки (или просто напишите название города)
🔔 <b>Прогноз каждое утро</b> — прогноз на день в выбранное время
⏰ <b>Мои уведомления</b> — что и во сколько присылать: по часам, недели, горы, воздух
⚠️ <b>Опасная погода</b> — сильные осадки, пыль
🎯 <b>Точность прогноза</b> — как прогнозы совпали с фактом
🗺 <b>Карта-сайт и глобус</b> — сайт прямо в Telegram

<b>Автоотправка</b>
Под разделами есть кнопка «⏰ Присылать автоматически»: выберите время — и раздел будет приходить сам. Выключить — там же или в «⏰ Мои уведомления». Время — по Ташкенту.

<b>В группе или канале</b>
1. Добавьте бота в группу (в канал — администратором с правом публикации).
2. Администратор пишет /settings: язык → страны (можно несколько) → «Готово» → время отправки.
3. Каждый день в выбранное время по каждой стране приходит пост.
4. Затем появится «⏰ Что присылать в этот чат»: по часам, недели и месяцы, горы, воздух, сигнал о снеге — у каждого своё время, или «✅ Включить всё». Позже: /notify
/bugun — прогноз в группу прямо сейчас.

✉️ Вопрос или предложение — /admin, ответ придёт сюда
📄 /guide — инструкция в PDF

Данные: модели ECMWF, NOAA, DWD; качество воздуха — CAMS. Обновление каждые 3 часа.`,
  en: `ℹ️ <b>Osmon — how to use it</b>

<b>The buttons below</b>
⏱ <b>Today and tomorrow by the hour</b> — a 48-hour video with sound and «🗺 Interactive map»: tap the map — the weather at that spot; swipe the hours strip; ▶ — play, 🔈 — weather sounds, ⛶ — full screen
🗓 <b>15-day forecast</b> — choose a city, get the forecast by days
🎬 <b>15-day video forecast</b> — precipitation and temperature video for your city or country
📅 <b>Weeks and months</b> — pick a period with a button: last week, next weeks, months, dust
🏔 <b>Mountains: snow and trips</b> — a 10-day picture (snow, rain, good days); a place button — details; 🔔 — snow alerts
🌡 <b>Weather now</b> — right now where you are
🌫 <b>Air quality today</b> — dust and air quality by the hour
🏙 <b>Choose a city</b> · 🌍 <b>Change country</b>
📍 <b>Send my location</b> — the forecast exactly for your spot (or type a city name)
🔔 <b>Forecast every morning</b> — a daily forecast at the time you choose
⏰ <b>My notifications</b> — what comes and when: by the hour, weeks, mountains, air quality
⚠️ <b>Dangerous weather</b> — heavy precipitation, dust
🎯 <b>Forecast accuracy</b> — forecasts compared with what happened
🗺 <b>Map website and globe</b> — the website opens inside Telegram

<b>Automatic sending</b>
Under the sections there is a «⏰ Send automatically» button: choose the time — the section comes by itself. To turn it off — the same place or «⏰ My notifications». Time — Tashkent time.

<b>In a group or channel</b>
1. Add the bot to the group (in a channel as an admin allowed to post).
2. An admin types /settings: language → countries (several) → «Done» → sending time.
3. Every day at the chosen time a post comes for each country.
4. Then «⏰ What to send to this chat» appears: by the hour, weeks, mountains, air quality, snow alerts — a time for each or «✅ Turn all on». Later: /notify

✉️ Questions or ideas — /admin, the answer comes here
📄 /guide — the PDF guide

Data: ECMWF, NOAA, DWD models; air quality — CAMS. Updated every 3 hours.`,
};
const WD = { uz: ['Yak', 'Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan'], ru: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'], en: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] };
const PER_TICK = 4;      // groups per cron run (Workers free plan: 50 subrequests per run; a group may want several countries)
const POST_HOUR = 7, TZ = 5;  // default daily post at 07:00 Tashkent; each group can pick its hour (hourly cron)
const HOURS = [6, 7, 8, 9, 10, 12, 15, 18, 20, 21];
const hh = h => `${String(h).padStart(2, '0')}:00`;
const timeKb = (lang, cur) => ({ inline_keyboard: [HOURS.slice(0, 5), HOURS.slice(5)].map(row => row.map(h => ({ text: `${h === cur ? '✅ ' : ''}${hh(h)}`, callback_data: `GH:${lang}:${h}` }))) });
// a stored UTC time shown in Tashkent time: "06.11 12:04"
const tkt = iso => { if (!iso) return '—'; const t = new Date(Date.parse(iso) + TZ * 3600e3); return isNaN(t) ? '—' : `${String(t.getUTCDate()).padStart(2, '0')}.${String(t.getUTCMonth() + 1).padStart(2, '0')} ${String(t.getUTCHours()).padStart(2, '0')}:${String(t.getUTCMinutes()).padStart(2, '0')}`; };
const todayTZ = () => new Date(Date.now() + TZ * 3600e3).toISOString().slice(0, 10);
const multiKb = (lang, sel) => ({ inline_keyboard: [...GROUPS.map(row => row.map(id => ({ text: `${sel.includes(id) ? '✅' : FLAG[id]} ${NAMES[id][lang]}`, callback_data: `GT:${lang}:${id}` }))), [{ text: T[lang].done, callback_data: `GD:${lang}` }]] });
const regionsOf = s => (s && s.region ? s.region.split(',').filter(r => NAMES[r]) : []);

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (req.method === 'GET' && url.pathname.startsWith('/card/')) {  // the forecast pictures (SVG), fetched by wsrv.nl for Telegram
      const id = url.pathname.slice(6).replace(/\.svg$/, '').replace(/[^0-9a-f]/g, '');
      const row = env.DB ? await env.DB.prepare('SELECT s FROM cards WHERE id = ?1').bind(id).first().catch(() => null) : null;
      return row ? new Response(row.s, { headers: { 'content-type': 'image/svg+xml; charset=utf-8', 'cache-control': 'public, max-age=21600' } }) : new Response('not found', { status: 404 });
    }
    if (req.method === 'GET' && url.pathname === '/setup') return setup(env, url);
    if (url.pathname === '/hit' || url.pathname === '/stats') return visits(req, env, url);
    if (req.method === 'GET' && url.pathname === '/invite') return new Response(JSON.stringify(await invite(env, +(url.searchParams.get('n') || 12))), { headers: { 'content-type': 'application/json' } });
    if (req.method === 'GET' && url.pathname === '/broadcast') { const r = await broadcast(env); return new Response(JSON.stringify(r), { headers: { 'content-type': 'application/json' } }); }
    if (req.method !== 'POST') return new Response('Osmon bot is running. Open /setup once to connect it to Telegram.');
    if (req.headers.get('x-telegram-bot-api-secret-token') !== await secret(env)) return new Response('forbidden', { status: 403 });
    const up = await req.json().catch(() => ({}));
    // answer Telegram at once; sending videos can take longer than its webhook timeout
    ctx.waitUntil(handle(up, env).catch(e => console.log('error', e && e.stack)));
    return new Response('ok');
  },
  async scheduled(ev, env, ctx) {
    // each job on its own, so one failure (or Cloudflare's limit of requests per run) cannot stop the others;
    // the check of the site builds goes first: it is small and it matters most
    const run = (name, f) => f().catch(e => console.log(name, e && e.stack));
    if (ev && ev.cron === WATCH_CRON) return ctx.waitUntil((async () => { await run('watch', () => watchTick(env)); await run('pv', () => pvTick(env)); await run('sat', () => satTick(env)); })());  // its own runs: the weather at people's places
    ctx.waitUntil((async () => {
      await run('stale', () => staleTick(env));
      await run('pv', () => pvTick(env));
      const r = await broadcast(env).catch(e => { console.log('broadcast', e && e.stack); return null; });
      if (!r || !r.due) for (const [n, f] of [['alert', alertTick], ['mtn', mtnTick], ['notif', notifTick], ['stats', statsTick], ['backup', backupTick]]) await run(n, () => f(env));
      else await run('notif', () => notifTick(env, true));
      await run('sat', () => satTick(env));  // the morning auto-send is going: the notifications still go, fewer a run
    })());
  },
};

// the admin's own command menu and buttons: /users, /admin, /yt
const ADMIN_BTN = '👤 Пользователи';
const ADMIN_KB = { inline_keyboard: [[{ text: ADMIN_BTN, callback_data: 'AU:ru' }, { text: '📺 YouTube', callback_data: 'AY:ru' }], [{ text: '📈 Динамика', callback_data: 'AD:ru' }, { text: '🆕 Изменения', callback_data: 'AC:ru' }]] };
// admin: day by day — how many people used the bot, how many were new, site visits, and how many have the daily auto-send on
async function dstatSnap(env) {  // today's subscription counts, kept per day (so unsubscribes show in the history too)
  const one = async q => ((await env.DB.prepare(q).first()) || {}).n || 0;
  const prv = await one("SELECT COUNT(*) AS n FROM subs WHERE type = 'private'"), grp = await one("SELECT COUNT(*) AS n FROM subs WHERE type <> 'private'");
  const mtn = await one('SELECT COUNT(*) AS n FROM mtn'), users = await one('SELECT COUNT(*) AS n FROM users');
  await env.DB.prepare('INSERT INTO dstat (day, prv, grp, mtn, users) VALUES (?1, ?2, ?3, ?4, ?5) ON CONFLICT(day) DO UPDATE SET prv = ?2, grp = ?3, mtn = ?4, users = ?5').bind(todayTZ(), prv, grp, mtn, users).run();
  return { prv, grp, mtn, users };
}
async function sendDynamics(env, chat, n = 14) {
  if (!env.DB) return; await db(env);
  const now = await dstatSnap(env), all = async (q, ...a) => (await env.DB.prepare(q).bind(...a).all()).results;
  const days = []; for (let i = n - 1; i >= 0; i--) days.push(new Date(Date.now() + TZ * 3600e3 - i * 864e5).toISOString().slice(0, 10));
  const from = days[0], map = (rows, k = 'n') => Object.fromEntries(rows.map(r => [r.day, r[k]]));
  const act = map(await all('SELECT day, COUNT(*) AS n FROM daily WHERE day >= ?1 GROUP BY day', from));
  const neu = map(await all(`SELECT date(first, '+${TZ} hours') AS day, COUNT(*) AS n FROM users WHERE first IS NOT NULL AND chat_id > 0 GROUP BY day HAVING day >= ?1`, from));
  let site = {}; try { site = map(await all('SELECT day, SUM(n) AS n FROM hits WHERE day >= ?1 GROUP BY day', from)); } catch (e) { /* no site counter yet */ }
  const snap = Object.fromEntries((await all('SELECT * FROM dstat WHERE day >= ?1', from)).map(r => [r.day, r]));
  // days before the snapshots began: today's subscribers counted by the day they subscribed
  const added = await all(`SELECT date(added, '+${TZ} hours') AS day, type FROM subs WHERE added IS NOT NULL`);
  const subsOn = d => snap[d] ? snap[d].prv + snap[d].grp : added.filter(x => x.day <= d).length;
  const newSubs = map(await all(`SELECT date(added, '+${TZ} hours') AS day, COUNT(*) AS n FROM subs GROUP BY day HAVING day >= ?1`, from));
  const top = Math.max(1, ...days.map(d => act[d] || 0)), bar = v => '█'.repeat(Math.round((v || 0) / top * 8)).padEnd(8, '·');
  const pad = (v, w) => String(v ?? 0).padStart(w);
  const rows = days.map(d => `${d.slice(8, 10)}.${d.slice(5, 7)} ${bar(act[d])}${pad(act[d], 4)}${pad(neu[d], 4)}${pad(site[d], 5)}${pad(subsOn(d), 4)}${newSubs[d] ? '+' + newSubs[d] : ''}`);
  const sum = k => days.reduce((a, d) => a + (k[d] || 0), 0), avg = Math.round(sum(act) / Math.max(1, days.filter(d => act[d]).length));
  const text = [`📈 <b>Динамика за ${n} дней</b> (по Ташкенту)`, '',
    `<pre>${esc(`Дата  Заходили    Нов Сайт  🔔\n${rows.join('\n')}`)}</pre>`,
    `👤 Заходили: в среднем <b>${avg}</b> в день · всего уникальных за период: <b>${((await env.DB.prepare('SELECT COUNT(DISTINCT chat_id) AS n FROM daily WHERE day >= ?1').bind(from).first()) || {}).n || 0}</b>`,
    `🆕 Новых за период: <b>${sum(neu)}</b> · всего пользователей: <b>${now.users}</b>`,
    `🔔 Автоотправка погоды включена: <b>${now.prv + now.grp}</b> (👤 личных ${now.prv} · 👥 групп и каналов ${now.grp})`,
    `❄️ Сигнал о снеге в горах: <b>${now.mtn}</b>`,
    `<i>«Заходили» считается с ${(await env.DB.prepare('SELECT MIN(day) AS d FROM daily').first() || {}).d || 'сегодня'}; столбец 🔔 — сколько подписок было в тот день, «+» — новые подписки.</i>`].join('\n');
  return tg(env, 'sendMessage', { chat_id: chat, text: text.slice(0, 4000), parse_mode: 'HTML',
    reply_markup: { inline_keyboard: [[7, 14, 30].map(k => ({ text: `${k === n ? '✅ ' : ''}${k} дней`, callback_data: `AD:ru:${k}` }))] } });
}
// admin: what changed lately (telegram/changes.json in the repository) and how the last site builds went (GitHub Actions)
async function sendChanges(env, chat) {
  const REPO = 'otabekvafoev92-del/ob-havo-ecmwf', H = { 'User-Agent': 'osmon-bot', Accept: 'application/vnd.github+json' };
  const [ch, runs] = await Promise.all([
    fetch(`https://raw.githubusercontent.com/${REPO}/main/telegram/changes.json?t=${Date.now()}`).then(r => r.ok ? r.json() : null).catch(() => null),
    fetch(`https://api.github.com/repos/${REPO}/actions/runs?per_page=6`, { headers: H }).then(r => r.ok ? r.json() : null).catch(() => null)]);
  const st = { success: '✅ готово', failure: '❌ ошибка', cancelled: '⏭ заменена новой', in_progress: '⏳ идёт', queued: '🕓 в очереди', pending: '🕓 в очереди' };
  const out = ['🆕 <b>Последние изменения</b>', ''];
  for (const it of ((ch && ch.items) || []).slice(0, 12)) out.push(`• <b>${esc(it.d.slice(8, 10) + '.' + it.d.slice(5, 7) + ' ' + it.d.slice(11))}</b> — ${esc(it.t)}`);
  if (!ch) out.push('Список изменений сейчас недоступен.');
  if (runs && runs.workflow_runs) {
    out.push('', '🛠 <b>Сборки сайта и видео</b>');
    for (const r of runs.workflow_runs.slice(0, 5)) {
      const s = r.status === 'completed' ? (st[r.conclusion] || r.conclusion) : (st[r.status] || r.status);
      const mins = r.run_started_at ? Math.max(0, Math.round(((r.status === 'completed' ? Date.parse(r.updated_at) : Date.now()) - Date.parse(r.run_started_at)) / 60000)) : 0;
      out.push(`• ${tkt(r.created_at)} — ${s}${r.status !== 'queued' && mins ? ` · ${mins} мин` : ''} · ${r.event === 'schedule' ? 'по расписанию' : r.event === 'push' ? 'после изменений' : 'вручную'}`);
    }
  }
  return tg(env, 'sendMessage', { chat_id: chat, text: out.join('\n').slice(0, 4000), parse_mode: 'HTML', disable_web_page_preview: true });
}
async function adminMenu(env, chat) {
  await tg(env, 'setMyCommands', { scope: { type: 'chat', chat_id: Number(chat) }, commands: [{ command: 'users', description: '👤 Пользователи бота' }, { command: 'searches', description: '🔎 Что ищут (7 дней)' }, { command: 'accuracy', description: '🎯 Точность прогноза' }, { command: 'admin', description: '👑 Статистика' }, { command: 'yt', description: '📺 Видеообзор для YouTube' }, { command: 'changes', description: '🆕 Последние изменения' }, { command: 'dyn', description: '📈 Динамика по дням' }, { command: 'start', description: 'Меню' }] });
}
async function setup(env, url) {
  { const a = await kv(env, 'admin'); if (a) await adminMenu(env, a); }
  const hook = await tg(env, 'setWebhook', { url: `${url.origin}/`, secret_token: await secret(env), allowed_updates: ['message', 'callback_query', 'my_chat_member', 'channel_post'] });
  await tg(env, 'setMyCommands', { commands: [  // ☰ only the basics: everything else is on the keyboard under the input field
    { command: 'home', description: '🏠 Menyu / Меню (klaviatura / клавиатура)' },
    { command: 'help', description: 'ℹ️ Yordam, PDF / Помощь, PDF' },
    { command: 'admin', description: '✉️ Adminga yozish / Написать админу' },
    { command: 'start', description: '🔤 Til / Язык / Dil' }] });
  await tg(env, 'setMyCommands', { scope: { type: 'all_group_chats' }, commands: [{ command: 'sozla', description: 'Davlat va til (adminlar uchun)' }, { command: 'settings', description: 'Страна и язык (для админов)' }, { command: 'bugun', description: 'Bugun va ertaga / Сегодня и завтра' }, { command: 'notify', description: '⏰ Nima yuborilsin / Что присылать (adminlar)' }, { command: 'help', description: 'Yordam / Помощь' }] });
  await tg(env, 'setChatMenuButton', { menu_button: { type: 'commands' } });  // ☰ opens the command menu
  await tg(env, 'setMyShortDescription', { short_description: 'Ob-havo · Погода · Hava — 15 kun, 6 model (ECMWF, NOAA). Guruhlarga avtomatik prognoz.' });
  await tg(env, 'setMyDescription', { description: '☀️ Osmon — ob-havo prognozi 15 kunga\n🌧 Yog‘in ehtimoli, 🌡 harorat, ☁️ bulutlar — 6 ta model asosida (ECMWF IFS/AIFS, NOAA GFS/GEFS).\n🌍 Butun dunyo, qit’alar, MDH va Turkiya.\n👥 Guruh yoki kanalga qo‘shing — prognozni o‘zi yuboradi.\n\nПогода на 15 дней по 6 моделям. Добавьте в группу — бот сам будет присылать прогноз.' });
  if (env.DB) await db(env);
  const me = await tg(env, 'getMe', {});
  return new Response(hook.ok ? `OK: @${me.result && me.result.username} is connected. Open Telegram and send /start.` : `Error: ${JSON.stringify(hook)}`, { headers: { 'content-type': 'text/plain; charset=utf-8' } });
}

// Telegram sends this header with every update (set in /setup): fake updates posted to the worker are refused
async function secret(env) {
  const h = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode('osmon:' + env.BOT_TOKEN)));
  return [...h].map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 48);
}
async function tg(env, method, body) {
  const r = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  return r.json();
}
async function manifest(env, fresh) {
  const r = await fetch(`${base(env)}/prob/manifest.json${fresh ? '?t=' + Date.now() : ''}`, { cf: { cacheTtl: fresh ? 0 : 600 } });
  return r.ok ? r.json() : null;
}
const base = env => env.SITE_URL.replace(/\/$/, '');
async function cities(env, id, lang) {
  const r = await fetch(`${base(env)}/prob/cities/${id}_${lang}.json`, { cf: { cacheTtl: 600 } });
  return r.ok ? r.json() : null;
}
// one line per city for today: "⛅ Ташкент: +11°…+16°, дождь маловероятен (24 %)"
async function cityLines(env, id, lang, n = 10) {
  const C = await cities(env, id, lang); if (!C) return '';
  const d = localToday(C.off);
  return C.cities.slice(0, n).map(c => c.days[d]).filter(Boolean).map(t => `${icon(t)} ${esc(t.replace(/, (ясно|переменная облачность|облачно|пасмурно|ochiq havo|qisman bulutli|bulutli|qalin bulutli|açık|parçalı bulutlu|bulutlu|kapalı)\.$/, '.'))}`).join('\n');
}
// the website opens inside Telegram (Mini App): ?view= picks the page, country, language and tab
const site = (env, view) => `${base(env)}/?tg=1&view=${encodeURIComponent(view)}`;
const link = (env, view) => `${base(env)}/?view=${encodeURIComponent(view)}`;
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/* ---------- keyboards ---------- */
const langKb = (p = 'L') => ({ inline_keyboard: [[{ text: '🇺🇿 O‘zbekcha', callback_data: `${p}:uz` }, { text: '🇷🇺 Русский', callback_data: `${p}:ru` }, { text: '🇬🇧 English', callback_data: `${p}:en` }]] });
const countryKb = (lang, p = 'C') => ({ inline_keyboard: GROUPS.map(row => row.map(id => ({ text: `${FLAG[id]} ${NAMES[id][lang]}`, callback_data: `${p}:${lang}:${id}` }))) });
const OLK = { uz: '📅 Haftalar va oylar', ru: '📅 Недели и месяцы', en: '📅 Weeks and months' };
// Uzbekistan: the past week, the next two weeks, this and next month and the dust (prob/outlook.py), in segments:
// first a menu of periods, then each period's maps on their own with the same buttons under the last one
const OLA = { ru: { pick: 'Выберите период — пришлю его карты:', all: '📤 Все карты сразу', dust: '🌫' },
              uz: { pick: 'Davrni tanlang — xaritalarini yuboraman:', all: '📤 Barcha xaritalar', dust: '🌫' },
              en: { pick: 'Choose a period — I will send its maps:', all: '📤 All maps', dust: '🌫' } };
const OL_ICON = { past: '⏪', w1: '📆', w2: '📆', m0: '🗓', m1: '🗓', dust: '🌫' };
async function outlookItems(env, lang) {
  const I = await (await fetch(`${base(env)}/prob/outlook/index.json?t=${Date.now()}`)).json().catch(() => null);
  let its = I ? I.items.filter(i => i.lang === lang) : []; if (I && !its.length) its = I.items.filter(i => i.lang === 'ru');
  return { I, its };
}
const ddm = x => `${x.slice(8, 10)}.${x.slice(5, 7)}`;
// the segments as buttons: the past week alone, the two weeks side by side, the two months side by side, the dust, "all at once"
function outlookKb(its, lang, cur) {
  const A = OLA[lang] || OLA.ru, btn = i => ({ text: `${cur === i.key ? '✅' : OL_ICON[i.key] || '📅'} ${i.title}${/^w/.test(i.key) ? ` · ${ddm(i.start)}–${ddm(i.end)}` : ''}`, callback_data: `OP:${lang}:${i.key}` });
  const by = k => its.filter(i => k.includes(i.key)).map(btn), rows = [by(['past']), by(['w1', 'w2']), by(['m0', 'm1']), by(['dust']),
    its.filter(i => !['past', 'w1', 'w2', 'm0', 'm1', 'dust'].includes(i.key)).map(btn)].filter(r => r.length);
  rows.push([{ text: A.all, callback_data: `OA:${lang}` }]);
  rows.push(...weeksKb(lang).inline_keyboard);
  rows.push([notifBtn(lang, 'outlook')]);
  return { inline_keyboard: rows };
}
/* ---------- a week day by day: the ISO weeks within the 15-day forecast, at the user's place (or Tashkent) ---------- */
const WKX = {
  ru: { btn: '📆 Неделя {n} · {a}–{b} по дням', head: 'неделя {n} · {a}–{b}', temp: 'Температура за неделю: от {lo} ночью до {hi} днём', wet: 'Осадки вероятны {n} дн.: {d}', mm: ', всего ~{mm} мм', dry: 'Неделя без заметных осадков',
        part: 'Прогноз по дням есть до {last}; дальше — в «📅 Недели и месяцы» (осадки и температура к норме).', far: 'Прогноз по дням пока есть только до {last}. Для этой недели смотрите «📅 Недели и месяцы».', pick: '📆 Выберите неделю — пришлю погоду по дням:' },
  uz: { btn: '📆 Hafta {n} · {a}–{b} kunma-kun', head: 'hafta {n} · {a}–{b}', temp: 'Hafta harorati: kechasi {lo} dan kunduzi {hi} gacha', wet: 'Yog‘in ehtimoli {n} kun: {d}', mm: ', jami ~{mm} mm', dry: 'Hafta sezilarli yog‘insiz',
        part: 'Kunma-kun prognoz {last} gacha bor; keyingisi — «📅 Haftalar va oylar»da (yog‘in va harorat me’yorga nisbatan).', far: 'Kunma-kun prognoz hozircha {last} gacha. Bu hafta uchun «📅 Haftalar va oylar»ni ko‘ring.', pick: '📆 Haftani tanlang — kunma-kun ob-havoni yuboraman:' },
  en: { btn: '📆 Week {n} · {a}–{b} day by day', head: 'week {n} · {a}–{b}', temp: 'Temperature this week: from {lo} at night to {hi} by day', wet: 'Precipitation likely on {n} days: {d}', mm: ', about {mm} mm in all', dry: 'A week without notable precipitation',
        part: 'The day-by-day forecast goes up to {last}; after that — «📅 Weeks and months» (precipitation and temperature against the normal).', far: 'The day-by-day forecast only goes up to {last} so far. For this week see «📅 Weeks and months».', pick: '📆 Choose a week — I will send the weather day by day:' } };
const WDL = { uz: ['Yakshanba', 'Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba'], ru: ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'], en: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'] };
function isoWeek(d) { const t = new Date(d + 'T12:00:00Z'); t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7)); const y0 = Date.UTC(t.getUTCFullYear(), 0, 1); return Math.ceil(((t - y0) / 864e5 + 1) / 7); }
const isoKey = d => { const t = new Date(d + 'T12:00:00Z'); t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7)); return `${isoWeek(d)}-${t.getUTCFullYear()}`; };  // «49-2026»: the week and its ISO year
const dAdd = (d, n) => new Date(Date.parse(d + 'T12:00:00Z') + n * 864e5).toISOString().slice(0, 10);
function weeksKb(lang, cur) {  // this ISO week and the next two (the forecast reaches ~15 days)
  const X = WKX[lang] || WKX.ru, today = new Date(Date.now() + TZ * 3600e3).toISOString().slice(0, 10), dow = new Date(today + 'T12:00:00Z').getUTCDay() || 7, mon = dAdd(today, 1 - dow);
  return { inline_keyboard: [0, 1, 2, 3, 4, 5].map(k => { const a = dAdd(mon, 7 * k), b = dAdd(a, 6);  // six weeks: the first two from the 15-day forecast, then ECMWF EC46
    return [{ text: `${cur === a ? '✅ ' : ''}${X.btn.replace('{n}', isoKey(a)).replace('{a}', ddm(a)).replace('{b}', ddm(b))}`, callback_data: `WK:${lang}:${a}`, ...(cur === a ? {} : { style: 'success' }) }]; }) };
}
async function weekDays(env, chat, lang, a, b) {  // the week's video day by day (Uzbekistan), then the user's place (saved, else Tashkent) day by day
  const u = await getUser(env, chat), pl = u && u.place ? JSON.parse(u.place) : [41.311, 69.279];
  const today = new Date(Date.now() + TZ * 3600e3).toISOString().slice(0, 10), dow = new Date(a + 'T12:00:00Z').getUTCDay() || 7, mon = dAdd(a, 1 - dow);
  const L = lang === 'uz' ? 'uz' : 'ru', vu = `${EVRAW}/weeks/wk_${isoKey(mon)}_${L}.mp4`;
  if (!b && await fetch(vu, { method: 'HEAD' }).then(r => r.ok).catch(() => false)) {
    await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
    await tg(env, 'sendVideo', { chat_id: chat, video: `${vu}?v=${Math.floor(Date.now() / 3600e3)}`, supports_streaming: true, width: 1920, height: 1080, parse_mode: 'HTML',
      caption: `📆 ${FLAG.UZ} <b>${(WKX[lang] || WKX.ru).head.replace('{n}', isoKey(mon)).replace('{a}', ddm(mon)).replace('{b}', ddm(dAdd(mon, 6)))}</b>` });
    if (a > dAdd(today, 13)) return true;  // beyond the 15-day forecast: the video (EC46) is the answer
  }
  return pointForecast(env, chat, lang, +pl[0], +pl[1], await nearestPlace(env, +pl[0], +pl[1], 8), null, [a, b || dAdd(a, 6)]);
}
// "30.11–06.12", "с 30 ноября по 6 декабря", "30 noyabr – 6 dekabr", "неделя", "следующая неделя", "неделя 49"
const MON_RX = [['янв', 'yanv', 'oca', 'jan'], ['фев', 'fev', 'şub', 'feb'], ['мар', 'mart', 'mar', 'mar'], ['апр', 'apr', 'nis', 'apr'], ['ма[йя]', 'may', 'mayıs', 'may'], ['июн', 'iyun', 'haz', 'jun'], ['июл', 'iyul', 'tem', 'jul'], ['авг', 'avg', 'ağu', 'aug'], ['сен', 'sen', 'eyl', 'sep'], ['окт', 'okt', 'eki', 'oct'], ['ноя', 'noy', 'kas', 'nov'], ['дек', 'dek', 'ara', 'dec']];
function parseRange(text) {
  const t = text.toLowerCase().replace(/ё/g, 'е'), today = new Date(Date.now() + TZ * 3600e3).toISOString().slice(0, 10), Y = +today.slice(0, 4);
  const dow = new Date(today + 'T12:00:00Z').getUTCDay() || 7, mon = dAdd(today, 1 - dow);
  const mk = (d, m) => { let y = Y; const s = `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`; if (s < dAdd(today, -60)) y++; return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`; };
  let m = t.match(/(\d{1,2})[./](\d{1,2})\D{1,12}?(\d{1,2})[./](\d{1,2})/);
  if (m) return [mk(+m[1], +m[2]), mk(+m[3], +m[4])];
  const mon_ = w => MON_RX.findIndex(v => v.some(x => new RegExp('^' + x).test(w))) + 1;
  m = t.match(/(\d{1,2})\s*([a-zа-яʻ‘'ğışçöü]+)?\s*(?:-|–|—|по|до|gacha|dan|\.\.)\s*(\d{1,2})\s+([a-zа-яʻ‘'ğışçöü]+)/);
  if (m && mon_(m[4])) { const m2 = mon_(m[4]), m1 = m[2] && mon_(m[2]) ? mon_(m[2]) : m2; return [mk(+m[1], m1), mk(+m[3], m2)]; }
  if (/(неделя|недел[юи]|hafta|week)\s*(\d{1,2})\b/.test(t)) { const n = +t.match(/(неделя|недел[юи]|hafta|week)\s*(\d{1,2})/)[2], a = dAdd(mon, 7 * (n - isoWeek(mon))); return [a, dAdd(a, 6)]; }
  if (/(\d{1,2})\s*-?\s*hafta/.test(t)) { const n = +t.match(/(\d{1,2})\s*-?\s*hafta/)[1], a = dAdd(mon, 7 * (n - isoWeek(mon))); return [a, dAdd(a, 6)]; }
  if (/(следующ[а-я]* недел|keyingi hafta|через неделю|next week)/.test(t)) return [dAdd(mon, 7), dAdd(mon, 13)];
  if (/^(эта |на |погода на )?(недел[яюи]|hafta|bu hafta|this week|week)$/.test(t.trim())) return [mon, dAdd(mon, 6)];
  return null;
}
async function sendOutlook(env, chat, lang) {
  const { its } = await outlookItems(env, lang);
  if (!its.length) return tg(env, 'sendMessage', { chat_id: chat, text: T[lang].none });
  return tg(env, 'sendMessage', { chat_id: chat, text: `🇺🇿 <b>${OLK[lang]}</b>\n${(OLA[lang] || OLA.ru).pick}`, parse_mode: 'HTML', reply_markup: outlookKb(its, lang) });
}
// one period (key) or all of them: every map is its own photo with its own caption; the segment buttons go under the last one
async function sendOutlookPart(env, chat, lang, key) {
  const quiet = chat < 0;  // a group or channel: just the maps
  const { I, its } = await outlookItems(env, lang);
  if (!its.length) return tg(env, 'sendMessage', { chat_id: chat, text: T[lang].none });
  const v = encodeURIComponent(I.made || ''), list = key ? its.filter(i => i.key === key) : its;
  if (!list.length) return sendOutlook(env, chat, lang);
  const shots = [];
  for (const i of list) {
    const imgs = i.imgs || [i.img], caps = i.caps || [];
    imgs.forEach((im, k) => shots.push({ im, cap: `<b>${esc(i.title)}</b>${caps[k] ? ` · ${esc(caps[k])}` : ''}\n${ddm(i.start)}–${ddm(i.end)}${k === 0 && i.text ? `\n${esc(i.text)}` : ''}` }));
  }
  let r = null;
  for (let n = 0; n < shots.length; n++) {
    await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_photo' });
    r = await tg(env, 'sendPhoto', { chat_id: chat, photo: `${base(env)}/prob/${shots[n].im}?v=${v}`, caption: shots[n].cap.slice(0, 1024), parse_mode: 'HTML',
      ...(n === shots.length - 1 && !quiet ? { reply_markup: outlookKb(its, lang, key) } : {}) });
  }
  return r;
}
/* ---------- the weather by regions and districts (Uzbekistan, Kazakhstan, Kyrgyzstan; prob/admin_wx.py) ---------- */
const ADM = new Set(['UZ', 'KZ', 'KG']);
const RGX = {
  ru: { btn: '🗺 Погода по регионам и районам', detail: 'Нажмите район — пришлю подробный прогноз: по часам и на 15 дней.', title: 'Погода по регионам', pick: 'Нажмите регион — покажу погоду по его районам:', today: 'сегодня', tomorrow: 'завтра', none: 'Погода по регионам ещё готовится, попробуйте чуть позже.', back: '⬅️ Все регионы', dists: 'по районам', foot: 'Температура: ночь…день. ☂ — вероятность дождя, ❄ — снега, ☀ — без осадков.' },
  uz: { btn: '🗺 Viloyat va tumanlar bo‘yicha', detail: 'Tumanni bosing — batafsil prognoz yuboraman: soatma-soat va 15 kunga.', title: 'Viloyatlar bo‘yicha ob-havo', pick: 'Viloyatni bosing — tumanlari bo‘yicha ob-havoni ko‘rsataman:', today: 'bugun', tomorrow: 'ertaga', none: 'Viloyatlar bo‘yicha ma’lumot tayyorlanmoqda, birozdan keyin urinib ko‘ring.', back: '⬅️ Barcha viloyatlar', dists: 'tumanlar bo‘yicha', foot: 'Harorat: tun…kun. ☂ — yomg‘ir ehtimoli, ❄ — qor, ☀ — yog‘insiz.' },
  en: { btn: '🗺 By regions and districts', detail: 'Tap a district — I will send the detailed forecast: by the hour and for 15 days.', title: 'Weather by regions', pick: 'Tap a region — I will show the weather in its districts:', today: 'today', tomorrow: 'tomorrow', none: 'The regions’ data is being prepared, try again a little later.', back: '⬅️ All regions', dists: 'by districts', foot: 'Temperature: night…day. ☂ — chance of rain, ❄ — snow, ☀ — dry.' } };
const t0 = v => v == null ? '—' : `${v > 0.5 ? '+' : ''}${Math.round(v)}°`.replace('+0°', '0°').replace('-0°', '0°');
const admLine = v => !v ? '—' : `${t0(v[0])}…${t0(v[1])} ${v[2] >= 20 ? `${v[3] ? '❄' : '☂'}${v[2]}%` : '☀'}`;
const admName = (a, lang) => (a.name[lang] || a.name.ru);
// a neat table in a fixed-width font: the name, today's night…day °C and precipitation, tomorrow's
const TBH = { ru: ['Регион', 'Сегодня', 'Завтра', 'Район'], uz: ['Hudud', 'Bugun', 'Ertaga', 'Tuman'], en: ['Region', 'Today', 'Tomorrow', 'District'] };
const TBF = { ru: 'Температура: ночь…день, °C · ☂ — вероятность дождя, ❄ — снега, — без осадков', uz: 'Harorat: tun…kun, °C · ☂ — yomg‘ir ehtimoli, ❄ — qor, — yog‘insiz', en: 'Temperature: night…day, °C · ☂ — chance of rain, ❄ — snow, — dry' };
const admCell = v => { if (!v) return ['—', '']; const t = `${t0(v[0])}…${t0(v[1])}`.replace(/°/g, ''); return [t, v[2] >= 20 ? `${v[3] ? '❄' : '☂'}${v[2]}%` : '—']; };
function admTable(rows, lang, first) {
  const H = TBH[lang] || TBH.ru, short = n => n.replace(/ viloyati$| обл\.$| области$| tumani$| р-н$| region$| district$/, '');
  let nm = rows.map(r => short(r.name)); nm = nm.map((x, i) => nm.some((y, j) => j !== i && (y === x || y.startsWith(x + ' '))) ? rows[i].name.replace(/ viloyati$/, ' vil.').replace(/ области$| обл\.$/, ' обл.') : x);
  const w = Math.min(17, Math.max(...nm.map(x => x.length), 6));
  const cut = x => x.length > w ? x.slice(0, w - 1) + '…' : x.padEnd(w);
  const line = (n, a, b) => `${cut(n)} ${a[0].padStart(7)} ${a[1].padEnd(5)} ${b[0].padStart(7)} ${b[1]}`;
  const head = `${(first || H[0]).padEnd(w)} ${H[1].padStart(7)}       ${H[2].padStart(7)}`;
  return `<pre>${esc([head, '─'.repeat(w + 30), ...rows.map((r, i) => line(nm[i], admCell(r.v[0]), admCell(r.v[1])))].join('\n'))}</pre>`;
}
async function adminData(env, rid) { return fetch(`${base(env)}/prob/hr/${rid}_admin.json?v=${fresh()}`).then(r => r.ok ? r.json() : null).catch(() => null); }
function regionsKb(A, lang, rid, cur) {
  const b = [...A.adm1].sort((x, y) => admName(x, lang).localeCompare(admName(y, lang))).map(a => ({ text: `${cur === a.id ? '✅ ' : ''}${admName(a, lang).replace(/ обл\.$| viloyati$/, '')}`, callback_data: `RD:${lang}:${rid}:${a.id}` }));
  const rows = []; for (let i = 0; i < b.length; i += 2) rows.push(b.slice(i, i + 2));
  return { inline_keyboard: rows };
}
// the two maps (today, tomorrow), then every region in a line with buttons that open its districts
async function sendRegions(env, chat, lang, rid) {
  const X = RGX[lang] || RGX.ru, A = await adminData(env, rid);
  if (!A) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  const L = lang === 'en' ? 'ru' : lang, v = encodeURIComponent(A.run);
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_photo' });
  await tg(env, 'sendMediaGroup', { chat_id: chat, media: [0, 1].map(k => ({ type: 'photo', media: `${base(env)}/prob/hr/${rid}_adm_${L}_${k}.png?v=${v}`, ...(k ? {} : { caption: `${FLAG[rid]} ${NAMES[rid][lang]} · ${X.title}` }) })) });
  return tg(env, 'sendMessage', regionsList(A, lang, rid, chat));
}
function regionsList(A, lang, rid, chat) {
  const X = RGX[lang] || RGX.ru, rows = [...A.adm1].sort((x, y) => admName(x, lang).localeCompare(admName(y, lang))).map(a => ({ name: admName(a, lang), v: a.v }));
  return { chat_id: chat, text: [`${FLAG[rid]} <b>${NAMES[rid][lang]} · ${X.title}</b>`, admTable(rows, lang), `<i>${TBF[lang] || TBF.ru}</i>`, '', X.pick].join('\n').slice(0, 4000), parse_mode: 'HTML', reply_markup: regionsKb(A, lang, rid) };
}
// one region: its districts, today and tomorrow (the message changes in place when another region is pressed)
async function sendDistricts(env, chat, lang, rid, id, msgId) {
  const X = RGX[lang] || RGX.ru, A = await adminData(env, rid);
  if (!A) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  const r = A.adm1.find(a => a.id === id); if (!r) return sendRegions(env, chat, lang, rid);
  if (!msgId) { const mv = await moist2Url(env, lang, rid, 0, id); if (mv) await tg(env, 'sendVideo', { chat_id: chat, video: mv, caption: `💧 ${esc(admName(r, lang))} · ${(TJX[lang] || TJX.ru).moist2}`, parse_mode: 'HTML', supports_streaming: true }); }
  const ds = A.adm2.map((d, i) => ({ ...d, i })).filter(d => d.p === id).sort((x, y) => admName(x, lang).localeCompare(admName(y, lang)));
  const text = [`🗺 <b>${esc(admName(r, lang))}</b> · ${X.dists}`, `${X.today}: ${admLine(r.v[0])} · ${X.tomorrow}: ${admLine(r.v[1])}`,
    admTable(ds.map(d => ({ name: admName(d, lang), v: d.v })), lang, (TBH[lang] || TBH.ru)[3]), `<i>${TBF[lang] || TBF.ru}</i>`, '', `<i>${X.detail}</i>`].join('\n').slice(0, 4000);
  // a button per district: its detailed forecast (by hours, 15 days) at the district's centre
  const btn = ds.map(d => ({ text: admName(d, lang).replace(/ р-н$| tumani$/, ''), callback_data: `RX:${lang}:${rid}:${d.i}` })), rows = [];
  for (let i = 0; i < btn.length; i += 3) rows.push(btn.slice(i, i + 3));
  const cc = r.c || (ds[0] && ds[0].c);  // the region's 15 days as a chart, at its centre
  const kb = { inline_keyboard: [...(cc ? [[{ ...phBtn(lang, +cc[1], +cc[0]), text: `${(PHX[lang] || PHX.ru).btn}: ${admName(r, lang)}` }]] : []), ...rows, [{ text: X.back, callback_data: `RB:${lang}:${rid}` }]] };
  const body = { chat_id: chat, text, parse_mode: 'HTML', reply_markup: kb };
  if (msgId) { const e = await tg(env, 'editMessageText', { ...body, message_id: msgId }); if (e.ok || /not modified/.test(e.description || '')) return e; }
  return tg(env, 'sendMessage', body);
}

/* ---------- where the rain and snow come from (prob/trajectory.py: the air's path 2 days back) ---------- */
const TRJ = new Set(['UZ', 'KZ', 'KG']);
const TJX = { ru: { btn: '🧭 Откуда придут осадки', moist: 'Откуда идёт дождь, 3 дня: серое — тучи, синее — дождь, фиолетовое — снег, красное — циклон, жёлтое — сильный ветер, оранжевый пунктир — путь влаги к городу (ECMWF)', m15: '📅 Видео на 15 дней', acc: '💧 Сколько выпадет дождя и снега', accCap: 'Сколько выпадет: дождь (мм) и снег (см) нарастают с начала прогноза; у городов — сумма (ECMWF, 3 дня)', moist2: 'дождь, снег и ветер на 2 дня (область — в окне)', moist15: 'Дождь, снег и ветер на 15 дней (ECMWF; после 10-го дня — один из сценариев ансамбля, это ориентир)', m15none: 'Видео на 15 дней ещё готовится — загляните чуть позже.', title: 'Откуда придут осадки', none: 'В ближайшие 3 дня осадков в крупных городах не ожидается — показывать нечего. ☀️', foot: 'Линия — путь воздуха (на высоте ~3 км), который принесёт осадки, за 2 суток до их начала. Модель ECMWF.' },
              uz: { btn: '🧭 Yog‘in qayerdan keladi', moist: 'Yomg‘ir qayerdan keladi, 3 kun: kulrang — bulut, ko‘k — yomg‘ir, binafsha — qor, qizil — siklon, sariq — kuchli shamol, to‘q sariq punktir — namlikning shaharga yo‘li (ECMWF)', m15: '📅 15 kunlik video', acc: '💧 Qancha yomg‘ir va qor yog‘adi', accCap: 'Qancha yog‘adi: yomg‘ir (mm) va qor (sm) prognoz boshidan yig‘iladi; shaharlarda — jami (ECMWF, 3 kun)', moist2: 'yomg‘ir, qor va shamol 2 kunga (viloyat — oynada)', moist15: 'Yomg‘ir, qor va shamol 15 kunga (ECMWF; 10-kundan keyin — ansamblning bir ssenariysi, taxminiy)', m15none: '15 kunlik video hali tayyorlanmoqda — birozdan keyin qarang.', title: 'Yog‘in qayerdan keladi', none: 'Yaqin 3 kunda yirik shaharlarda yog‘in kutilmaydi — ko‘rsatadigan narsa yo‘q. ☀️', foot: 'Chiziq — yog‘in olib keladigan havoning (~3 km balandlikda) boshlanishidan 2 kun oldingi yo‘li. ECMWF modeli.' },
              en: { btn: '🧭 Where the rain comes from', moist: 'Where the rain comes from, 3 days: grey — clouds, blue — rain, violet — snow, red — cyclone, yellow — strong wind, orange dashes — the moisture’s path to a city (ECMWF)', m15: '📅 15-day video', acc: '💧 How much rain and snow will fall', accCap: 'How much will fall: rain (mm) and snow (cm) adding up from the start of the forecast; totals at the cities (ECMWF, 3 days)', moist2: 'Rain, snow and wind for 2 days (the region in a window)', moist15: 'Rain, snow and wind for 15 days (ECMWF; after day 10 one ensemble scenario, approximate)', m15none: 'The 15-day video is still being prepared — check a little later.', title: 'Where the rain comes from', none: 'No precipitation expected in the big cities in the next 3 days. ☀️', foot: 'The line — the 2-day path of the air (at ~3 km) that brings the precipitation, before it starts. ECMWF model.' } };
async function trajData(env, rid) { return fetch(`${base(env)}/prob/hr/${rid}_traj.json?v=${fresh()}`).then(r => r.ok ? r.json() : null).catch(() => null); }
/* ---------- 🎬 all the videos in one place, in the one look (tools/prob15_video.py, moist15_video.py, weeks_video.py, place15.py) ---------- */
const VHX = { ru: { temp: '🌡 Температура воздуха · 15 дней по часам', tcap: 'Температура воздуха · 15 дней по часам · изотермы, ветер', cap: 'Вероятность осадков и температура · 15 дней по часам · тучи, туман, гроза', moist: '🧭 Откуда идёт влага · тучи и осадки · 15 дней', weeks: '📅 По неделям: осадки к норме и температура', sat: '🛰 Спутник: чёткие снимки дня и облака до текущего часа', place: '📍 Моё место крупно + страна' },
  uz: { temp: '🌡 Havo harorati · 15 kun soatma-soat', tcap: 'Havo harorati · 15 kun soatma-soat · izotermalar, shamol', cap: 'Yog‘ingarchilik ehtimoli va harorat · 15 kun soatma-soat · bulut, tuman, momaqaldiroq', moist: '🧭 Namlik qayerdan keladi · bulut va yog‘in · 15 kun', weeks: '📅 Haftalar bo‘yicha: yog‘in me’yorga va harorat', sat: '🛰 Sun’iy yo‘ldosh: kunning aniq suratlari va hozirgacha bulutlar', place: '📍 Mening joyim yaqindan + davlat' },
  en: { temp: '🌡 Air temperature · 15 days by the hour', tcap: 'Air temperature · 15 days by the hour · isotherms, wind', cap: 'Chance of precipitation and temperature · 15 days by the hour · clouds, fog, thunder', moist: '🧭 Where the moisture comes from · clouds and rain · 15 days', weeks: '📅 By weeks: precipitation against the normal and temperature', sat: '🛰 Satellite: sharp passes of the day and clouds up to now', place: '📍 My place close up + the country' } };
const p15url = (rid, L, t = '') => rid === 'UZ' ? `${EVRAW}/p15/p15${t}_${L}.mp4` : `${EVRAW}/p15c-${rid}/country_${rid}${t}_${L}.mp4`;
const VMX = { ru: { h: '🎬 <b>Видео</b> · {n} — что показать?', prob: '🌧 Осадки · 15 дней', temp: '🌡 Температура · 15 дней', cloud: '☁️ Тучи · 15 дней', moist: '🧭 Откуда идёт влага', weeks: '📅 По неделям', sat: '🛰 Спутник сейчас', air: '🌫 Воздух · 24 часа', place: '📍 Моё место крупно', ccap: 'Тучи и осадки · 15 дней по часам · ветер, грозы' },
  uz: { h: '🎬 <b>Video</b> · {n} — nimani ko‘rsatay?', prob: '🌧 Yog‘in · 15 kun', temp: '🌡 Harorat · 15 kun', cloud: '☁️ Bulut · 15 kun', moist: '🧭 Namlik qayerdan', weeks: '📅 Haftalar bo‘yicha', sat: '🛰 Sun’iy yo‘ldosh', air: '🌫 Havo · 24 soat', place: '📍 Joyim yaqindan', ccap: 'Bulut va yog‘in · 15 kun soatma-soat · shamol, momaqaldiroq' },
  en: { h: '🎬 <b>Video</b> · {n} — what shall I show?', prob: '🌧 Precipitation · 15 days', temp: '🌡 Temperature · 15 days', cloud: '☁️ Clouds · 15 days', moist: '🧭 Where moisture comes from', weeks: '📅 By weeks', sat: '🛰 Satellite now', air: '🌫 Air · 24 hours', place: '📍 My place close up', ccap: 'Clouds and precipitation · 15 days by the hour · wind, thunder' } };
async function videoMenu(env, chat, lang, rid, u) {  // all the videos as one menu: two big buttons a row
  const X = VMX[lang] || VMX.ru, b = (t, k) => ({ text: X[t], callback_data: `${k}:${lang}:${rid}` }), pl = u && u.place ? JSON.parse(u.place) : null;
  const rows = [[b('prob', 'VP'), b('temp', 'TV')], [b('cloud', 'CV'), ...(rid === 'UZ' ? [b('moist', 'MV')] : [])]];
  if (rid === 'UZ') rows.push([b('weeks', 'WV'), b('sat', 'ST')], [b('air', 'AQV')]);
  if (pl) rows[rows.length - 1].push({ ...pvBtn(lang, +pl[0], +pl[1]), text: X.place });
  return tg(env, 'sendMessage', { chat_id: chat, text: X.h.replace('{n}', `${FLAG[rid] || ''} ${NAMES[rid][lang]}`), parse_mode: 'HTML', reply_markup: { inline_keyboard: rows } });
}
async function newVids(id, lang) {  // the 15-day videos in the new look that exist for the place: chance of precipitation, temperature, clouds
  const L = lang === 'uz' ? 'uz' : 'ru', urls = ['', '_t', '_c'].map(t => p15url(id, L, t));
  const ok = await Promise.all(urls.map(x => fetch(x, { method: 'HEAD' }).then(r => r.ok).catch(() => false)));
  return ok[0] ? urls.filter((x, k) => ok[k]) : [];
}
async function videoHub(env, chat, lang, rid, u) {
  const X = VHX[lang] || VHX.ru, L = lang === 'uz' ? 'uz' : 'ru', url = p15url(rid, L);
  if (!(await fetch(url, { method: 'HEAD' }).then(r => r.ok).catch(() => false))) return handle({ callback_query: { id: '0', from: { id: chat }, data: `V:${lang}:${rid}`, message: { chat: { id: chat, type: 'private' } } } }, env);
  const pl = u && u.place ? JSON.parse(u.place) : null, rows = [];
  if (rid === 'UZ') rows.push([{ text: X.moist, callback_data: `MV:${lang}:UZ` }], [{ text: X.weeks, callback_data: `WV:${lang}:UZ` }], [{ text: X.sat, callback_data: `ST:${lang}:UZ` }]);
  if (pl) rows.push([{ ...pvBtn(lang, +pl[0], +pl[1]), text: X.place }]);
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
  return tg(env, 'sendVideo', { chat_id: chat, video: `${url}?v=${Math.floor(Date.now() / 1800e3)}`, caption: `🎬 ${FLAG[rid] || ''} <b>${NAMES[rid][lang]}</b> · ${X.cap}`, parse_mode: 'HTML', supports_streaming: true, width: 1920, height: 1080,
    ...(rows.length ? { reply_markup: { inline_keyboard: rows } } : {}) });
}
async function sendMoist15(env, chat, lang, rid) {  // the long video: 15 days of rain, snow and wind (Uzbekistan: tools/moist15_video.py; elsewhere prob/moisture.py --days 15)
  const X = TJX[lang] || TJX.ru, L = lang === 'en' ? 'ru' : lang, url = rid === 'UZ' ? `${EVRAW}/m15/moist15_${L}.mp4` : `${base(env)}/prob/hr/${rid}_moist15_${L}.mp4`;
  const ok = await fetch(url, { method: 'HEAD' }).then(r => r.ok).catch(() => false);
  if (!ok) return tg(env, 'sendMessage', { chat_id: chat, text: X.m15none });
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
  return tg(env, 'sendVideo', { chat_id: chat, video: `${url}?v=${fresh()}`, caption: `📅 ${FLAG[rid]} ${NAMES[rid][lang]} · ${X.moist15}`, supports_streaming: true });
}
let TJ_CACHE = null;
async function sendTrajLite(env, chat, lang, rid) {  // the morning 🧭: only the video, with buttons for the rest
  if (rid === 'UZ') return sendMoist15(env, chat, lang, rid);  // the new look
  const X = TJX[lang] || TJX.ru, L = lang === 'en' ? 'ru' : lang;
  if (!TJ_CACHE || TJ_CACHE.t < Date.now() - 600e3) TJ_CACHE = { t: Date.now(), J: {} };
  if (!(rid in TJ_CACHE.J)) TJ_CACHE.J[rid] = await trajData(env, rid);
  const J = TJ_CACHE.J[rid], v = encodeURIComponent(J ? J.run : fresh());
  return tg(env, 'sendVideo', { chat_id: chat, video: `${base(env)}/prob/hr/${rid}_moist_${L}.mp4?v=${v}`, caption: `🧭 ${FLAG[rid]} ${NAMES[rid][lang]} · ${X.moist}`, supports_streaming: true,
    reply_markup: { inline_keyboard: [[{ text: X.btn, callback_data: `TJ:${lang}:${rid}` }], [{ text: X.m15, callback_data: `MV:${lang}:${rid}` }], ...moistBtns(env, lang, rid, chat)] } });
}
async function sendTraj(env, chat, lang, rid) {
  if (rid === 'UZ') return sendMoist15(env, chat, lang, rid);  // the new look
  const X = TJX[lang] || TJX.ru, J = await trajData(env, rid);
  if (!J || !J.items.length) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
  // first the moving picture of the moisture coming in (prob/moisture.py), then the map of the air's paths
  const L = lang === 'en' ? 'ru' : lang, v = encodeURIComponent(J.run);
  // the 3-day video, then the 15-day one (the old map of the paths is gone: the videos show them)
  await tg(env, 'sendVideo', { chat_id: chat, video: `${base(env)}/prob/hr/${rid}_moist_${L}.mp4?v=${v}`, caption: `💧 ${FLAG[rid]} ${NAMES[rid][lang]} · ${X.moist}`, supports_streaming: true,
    reply_markup: { inline_keyboard: [[{ text: X.acc, callback_data: `AV:${lang}:${rid}` }], ...moistBtns(env, lang, rid, chat)] } });
  await sendMoist15(env, chat, lang, rid);
  const seen = new Set(), lines = [...J.items].sort((a, b) => a.k - b.k || b.p - a.p).filter(it => !seen.has(it.city.ru + it.day) && seen.add(it.city.ru + it.day)).slice(0, 10)
    .map(it => `<b>${esc(it.city[lang] || it.city.ru)} · ${dayLabel(it.day, lang)} · ${it.snow ? '❄' : '☂'} ${it.p}%</b>\n🧭 ${esc(it.text[lang] || it.text.ru)}`);
  return tg(env, 'sendMessage', { chat_id: chat, text: [`🧭 <b>${X.title}</b>`, '', lines.join('\n\n'), '', `<i>${X.foot}</i>`].join('\n').slice(0, 4000), parse_mode: 'HTML' });
}

/* ---------- the weather at the person's place: a word only when it matters ----------
   At each entry (/start, or the first message of the day) the bot asks where the person is; the place they send is
   watched until the next time: rain or snow starting (or within the hour), a thunderstorm, great heat, hard frost,
   strong wind. Normal weather: silence. Night (23:00–07:00): silence. Open-Meteo, checked every 20 minutes. */
const WATCH_CRON = '10,30,50 * * * *';
const WX = {
  ru: { ask: '📍 <b>Где вы сейчас?</b>\nОтправьте своё место — я сообщу, если начнётся дождь или снег, будет гроза, сильная жара, мороз или ветер. В обычную погоду писать не буду.', send: '📍 Отправить моё место', sameP: '✅ Я там же: ', off: '🔕 Не предупреждать',
    onOk: '🔔 Слежу за погодой: <b>{p}</b>\nСообщу, если начнётся дождь или снег, будет гроза, сильная жара, мороз или сильный ветер. В обычную погоду — тишина, ночью тоже.', offOk: '🔕 Хорошо, предупреждать не буду. Включить снова — отправьте 📍 своё место.', here: 'ваше место',
    rainSoon: '🌧 <b>{p}</b>: примерно через {m} мин начнётся дождь', snowSoon: '🌨 <b>{p}</b>: примерно через {m} мин начнётся снег', rainNow: '🌧 <b>{p}</b>: у вас начался дождь', snowNow: '🌨 <b>{p}</b>: у вас пошёл снег',
    storm: '⛈ <b>{p}</b>: гроза в ближайший час — лучше быть в помещении', heat: '🥵 <b>{p}</b>: очень жарко — {t}, ощущается как {f}. Пейте воду, в полдень лучше в тень', cold: '🥶 <b>{p}</b>: сильный мороз — {t}, ощущается как {f}. Одевайтесь теплее', wind: '💨 <b>{p}</b>: сильный ветер, порывы до {w} м/с' },
  uz: { ask: '📍 <b>Hozir qayerdasiz?</b>\nJoyingizni yuboring — yomg‘ir yoki qor boshlansa, momaqaldiroq, kuchli issiq, sovuq yoki shamol bo‘lsa xabar beraman. Oddiy ob-havoda yozmayman.', send: '📍 Joyimni yuborish', sameP: '✅ O‘sha joydaman: ', off: '🔕 Ogohlantirmaslik',
    onOk: '🔔 Ob-havoni kuzataman: <b>{p}</b>\nYomg‘ir yoki qor boshlansa, momaqaldiroq, kuchli issiq, sovuq yoki kuchli shamol bo‘lsa xabar beraman. Oddiy ob-havoda va kechasi — jimlik.', offOk: '🔕 Yaxshi, ogohlantirmayman. Qayta yoqish — 📍 joyingizni yuboring.', here: 'joyingiz',
    rainSoon: '🌧 <b>{p}</b>: taxminan {m} daqiqadan keyin yomg‘ir boshlanadi', snowSoon: '🌨 <b>{p}</b>: taxminan {m} daqiqadan keyin qor boshlanadi', rainNow: '🌧 <b>{p}</b>: yomg‘ir boshlandi', snowNow: '🌨 <b>{p}</b>: qor yog‘a boshladi',
    storm: '⛈ <b>{p}</b>: yaqin bir soatda momaqaldiroq — xonada bo‘lgan ma’qul', heat: '🥵 <b>{p}</b>: juda issiq — {t}, {f} kabi seziladi. Suv iching, tushda soyada bo‘ling', cold: '🥶 <b>{p}</b>: qattiq sovuq — {t}, {f} kabi seziladi. Issiq kiyining', wind: '💨 <b>{p}</b>: kuchli shamol, {w} m/s gacha' },
  en: { ask: '📍 <b>Where are you now?</b>\nSend your location — I will tell you if rain or snow starts, or there is a thunderstorm, great heat, frost or wind. In normal weather I stay quiet.', send: '📍 Send my location', sameP: '✅ I am in the same place: ', off: '🔕 Do not warn me',
    onOk: '🔔 Watching the weather: <b>{p}</b>\nI will tell you if rain or snow starts, or there is a thunderstorm, great heat, frost or strong wind. In normal weather and at night — silence.', offOk: '🔕 OK, I will not warn you. To turn it on again, send your 📍 location.', here: 'your location',
    rainSoon: '🌧 <b>{p}</b>: rain will start in about {m} min', snowSoon: '🌨 <b>{p}</b>: snow will start in about {m} min', rainNow: '🌧 <b>{p}</b>: rain has started', snowNow: '🌨 <b>{p}</b>: snow has started',
    storm: '⛈ <b>{p}</b>: a thunderstorm within the hour — stay indoors', heat: '🥵 <b>{p}</b>: very hot — {t}, feels like {f}. Drink water, stay in the shade at midday', cold: '🥶 <b>{p}</b>: hard frost — {t}, feels like {f}. Dress warmly', wind: '💨 <b>{p}</b>: strong wind, up to {w} m/s' } };
async function watchGet(env, chat) { if (!env.DB) return null; await db(env); return env.DB.prepare('SELECT * FROM watch WHERE chat_id = ?1').bind(chat).first(); }
async function watchSet(env, chat, f) {
  if (!env.DB) return; await db(env);
  const w = (await watchGet(env, chat)) || {}, n = { ...w, ...f };
  await env.DB.prepare('INSERT OR REPLACE INTO watch (chat_id, lat, lon, name, lang, on_, asked, st, checked) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)')
    .bind(chat, n.lat ?? null, n.lon ?? null, n.name ?? null, n.lang ?? null, n.on_ ?? 0, n.asked ?? null, n.st ?? '{}', n.checked ?? null).run();
}
// "where are you now?" — once a day at most; not after the person said no
async function watchAsk(env, chat, lang) {
  const W = WX[lang] || WX.ru, w = await watchGet(env, chat);
  if (w && (w.asked === todayTZ() || (w.on_ === 0 && w.asked))) return;
  await watchSet(env, chat, { asked: todayTZ(), lang });
  const kb = [[{ text: W.send, request_location: true }], ...(w && w.lat != null ? [[{ text: W.sameP + (w.name || '📍') }]] : []), [{ text: W.off }]];
  return tg(env, 'sendMessage', { chat_id: chat, text: W.ask, parse_mode: 'HTML', reply_markup: { keyboard: kb, resize_keyboard: true, one_time_keyboard: true } });
}
async function watchTick(env) {
  if (!env.DB) return; await db(env);
  const rows = (await env.DB.prepare("SELECT * FROM watch WHERE on_ = 1 AND lat IS NOT NULL ORDER BY COALESCE(checked, '') LIMIT 22").all()).results;
  for (const w of rows) {
    const now = Date.now(); await env.DB.prepare('UPDATE watch SET checked = ?2 WHERE chat_id = ?1').bind(w.chat_id, new Date(now).toISOString()).run();
    const j = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${(+w.lat).toFixed(3)}&longitude=${(+w.lon).toFixed(3)}&current=temperature_2m,apparent_temperature,precipitation,rain,snowfall,weather_code,wind_gusts_10m&minutely_15=precipitation,snowfall,weather_code&forecast_minutely_15=6&wind_speed_unit=ms&timezone=auto`).then(r => r.ok ? r.json() : null).catch(() => null);
    if (!j || !j.current) continue;
    const hourL = new Date(now + (j.utc_offset_seconds || 0) * 1000).getUTCHours();
    if (hourL >= 23 || hourL < 7) continue;  // night: silence
    const st = JSON.parse(w.st || '{}'), c = j.current, m = j.minutely_15 || {}, lang = WX[w.lang] ? w.lang : 'ru', X = WX[lang], p = esc(w.name || X.here), day = todayTZ();
    const ago = k => now - (st[k] || 0), out = [];
    const snowy = (c.snowfall || 0) > 0 || (c.temperature_2m ?? 9) <= 0.5;
    const wetNow = (c.precipitation || 0) >= 0.1, soonI = (m.precipitation || []).slice(1, 5).findIndex(v => v >= 0.15);  // 15-min steps: within the hour
    if ((wetNow || soonI >= 0) && ago('rain') > 3 * 3600e3 && !st.wet) {
      out.push(wetNow ? (snowy ? X.snowNow : X.rainNow).replace('{p}', p) : (snowy ? X.snowSoon : X.rainSoon).replace('{p}', p).replace('{m}', String((soonI + 1) * 15)));
      st.rain = now;
    }
    st.wet = wetNow || soonI >= 0 ? 1 : (st.wet && ago('rain') < 2 * 3600e3 ? 1 : 0);  // dry again for a while: the next rain is news again
    const code = Math.max(c.weather_code || 0, ...(m.weather_code || []).slice(0, 4));
    if (code >= 95 && ago('storm') > 3 * 3600e3) { out.push(X.storm.replace('{p}', p)); st.storm = now; }
    const t = c.temperature_2m, f = c.apparent_temperature, ft = v => `${v > 0 ? '+' : ''}${Math.round(v)}°`;
    if ((t >= 38 || f >= 40) && st.heat !== day) { out.push(X.heat.replace('{p}', p).replace('{t}', ft(t)).replace('{f}', ft(f))); st.heat = day; }
    if ((t <= -15 || f <= -20) && st.cold !== day) { out.push(X.cold.replace('{p}', p).replace('{t}', ft(t)).replace('{f}', ft(f))); st.cold = day; }
    if ((c.wind_gusts_10m || 0) >= 15 && ago('wind') > 6 * 3600e3) { out.push(X.wind.replace('{p}', p).replace('{w}', String(Math.round(c.wind_gusts_10m)))); st.wind = now; }
    await env.DB.prepare('UPDATE watch SET st = ?2 WHERE chat_id = ?1').bind(w.chat_id, JSON.stringify(st)).run();
    if (!out.length) continue;  // normal weather: nothing
    const r = await tg(env, 'sendMessage', { chat_id: w.chat_id, text: out.join('\n\n'), parse_mode: 'HTML' });
    if (!r.ok && /blocked|deactivated|chat not found/i.test(r.description || '')) await env.DB.prepare('UPDATE watch SET on_ = 0 WHERE chat_id = ?1').bind(w.chat_id).run();
  }
}

/* ---------- automatic sending of one section at the hour the person picked (⏰) ---------- */
const NX_ = {
  ru: { btn: '⏰ Присылать автоматически', ask: '⏰ Во сколько присылать «{s}»? Время — по Ташкенту.', weekly: ' (по понедельникам)', off: '🔕 Не присылать', on: '✅ «{s}» будет приходить каждый день в {h}.', onW: '✅ «{s}» будет приходить по понедельникам в {h}.', offT: '🔕 «{s}» больше не присылаю.', list: '⏰ <b>Мои уведомления</b>', none: 'Пока ничего не приходит автоматически. Нажмите раздел ниже и выберите время:', at: 'в', edit: 'Нажмите раздел, чтобы поменять время или выключить:', daily: '🔔 Прогноз каждое утро — включается кнопкой «🔔 Прогноз каждое утро»' },
  uz: { btn: '⏰ Avtomatik yuborish', ask: '⏰ «{s}» soat nechada kelsin? Vaqt — Toshkent bo‘yicha.', weekly: ' (dushanba kunlari)', off: '🔕 Yubormaslik', on: '✅ «{s}» har kuni soat {h} da keladi.', onW: '✅ «{s}» har dushanba soat {h} da keladi.', offT: '🔕 «{s}» endi yuborilmaydi.', list: '⏰ <b>Bildirishnomalarim</b>', none: 'Hozircha hech narsa avtomatik kelmaydi. Quyidagi bo‘limni bosing va vaqtni tanlang:', at: 'soat', edit: 'Vaqtni o‘zgartirish yoki o‘chirish uchun bo‘limni bosing:', daily: '🔔 Har tongi prognoz — «🔔 Har tongi prognoz» tugmasi bilan yoqiladi' },
  en: { btn: '⏰ Send automatically', ask: '⏰ At what time should «{s}» come? Time — Tashkent time.', weekly: ' (on Mondays)', off: '🔕 Do not send', on: '✅ «{s}» will come every day at {h}.', onW: '✅ «{s}» will come every Monday at {h}.', offT: '🔕 «{s}» will no longer be sent.', list: '⏰ <b>My notifications</b>', none: 'Nothing comes automatically now. Choose a section below and set the time:', at: 'at', edit: 'Tap a section to change its time or turn it off:', daily: '🔔 Forecast every morning — turned on with the «🔔 Forecast every morning» button' } };
const NSEC = ['days', 'brief', 'dyn', 'hourly', 'outlook', 'mtn', 'air', 'traj'];  // days: the 15-day forecast of the person's own place (the picture) at the chosen hour  // sections that can come by themselves (the 15 days already have 🔔 Прогноз каждое утро)
const NWEEKLY = { outlook: true, dyn: true };  // «📊 against last year» on Mondays: the summary and the Excel report                   // the weeks and months change slowly: once a week is enough
const secName = (sec, lang) => ((RKL[lang] || RKL.ru)[sec] || sec).replace(/^\S+\s/, '');
const notifBtn = (lang, sec) => ({ text: (NX_[lang] || NX_.ru).btn, callback_data: `NS:${lang}:${sec}` });
async function notifGet(env, chat, sec) { if (!env.DB) return null; await db(env); return env.DB.prepare('SELECT * FROM notif WHERE chat_id = ?1 AND sec = ?2').bind(chat, sec).first(); }
async function notifAsk(env, chat, lang, sec) {
  const N = NX_[lang] || NX_.ru, cur = await notifGet(env, chat, sec), hrs = HOURS;
  const rows = [hrs.slice(0, 5), hrs.slice(5)].map(r => r.map(h => ({ text: `${cur && cur.hour === h ? '✅ ' : ''}${hh(h)}`, callback_data: `NT:${lang}:${sec}:${h}` })));
  if (cur) rows.push([{ text: N.off, callback_data: `NO:${lang}:${sec}` }]);
  return tg(env, 'sendMessage', { chat_id: chat, text: N.ask.replace('{s}', secName(sec, lang)) + (NWEEKLY[sec] ? N.weekly : ''), reply_markup: { inline_keyboard: rows } });
}
async function notifSet(env, chat, lang, sec, hour, msgId) {
  const N = NX_[lang] || NX_.ru, now = new Date(Date.now() + TZ * 3600e3), u = chat > 0 ? await getUser(env, chat) : { region: regionsOf(await sub(env, chat))[0] };
  // an hour already past today: the first one comes tomorrow
  const last = hour <= now.getUTCHours() ? todayTZ() : '';
  await env.DB.prepare('INSERT INTO notif (chat_id, sec, hour, lang, region, last_day, added) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7) ON CONFLICT(chat_id, sec) DO UPDATE SET hour = ?3, lang = ?4, region = ?5, last_day = ?6')
    .bind(chat, sec, hour, lang, (u && u.region) || 'UZ', last, new Date().toISOString()).run();
  const text = (NWEEKLY[sec] ? N.onW : N.on).replace('{s}', secName(sec, lang)).replace('{h}', hh(hour));
  if (chat < 0) { if (msgId) await tg(env, 'deleteMessage', { chat_id: chat, message_id: msgId }); return groupNotif(env, chat, lang, null, text); }  // a group: back to its menu
  return msgId ? tg(env, 'editMessageText', { chat_id: chat, message_id: msgId, text }) : tg(env, 'sendMessage', { chat_id: chat, text });
}
async function notifList(env, chat, lang) {
  const N = NX_[lang] || NX_.ru; if (!env.DB) return; await db(env);
  const rows = (await env.DB.prepare('SELECT * FROM notif WHERE chat_id = ?1').bind(chat).all()).results, by = Object.fromEntries(rows.map(r => [r.sec, r]));
  const d = await sub(env, chat), lines = [N.list, ''];
  for (const sec of NSEC) if (by[sec]) lines.push(`✅ ${secName(sec, lang)} — ${N.at} ${hh(by[sec].hour)}${NWEEKLY[sec] ? N.weekly : ''}`);
  if (d) lines.push(`✅ ${secName('daily', lang)} — ${N.at} ${hh(d.post_hour ?? POST_HOUR)}`);
  lines.push('', rows.length || d ? N.edit : N.none);
  const kb = NSEC.map(sec => [{ text: `${by[sec] ? '✅' : '➕'} ${(RKL[lang] || RKL.ru)[sec]}${by[sec] ? ` · ${hh(by[sec].hour)}` : ''}`, callback_data: `NS:${lang}:${sec}` }]);
  return tg(env, 'sendMessage', { chat_id: chat, text: lines.join('\n') + (d ? '' : `\n\n<i>${N.daily}</i>`), parse_mode: 'HTML', reply_markup: { inline_keyboard: kb } });
}
// a group or channel: one message with every section that can come by itself, its hour, and "turn everything on / off"
const GNX = {
  ru: { head: '⏰ <b>Что присылать в этот чат</b>', main: '🗓 Ежедневный прогноз (главный пост) — в {h}, страны: {c}. Изменить: /settings', snow: '❄️ Сигнал о снеге в горах', tip: 'Нажмите раздел, чтобы выбрать время или выключить. Время — по Ташкенту. Менять могут только администраторы.', all: '✅ Включить всё', allOff: '🔕 Выключить всё', allOn: '✅ Включено всё: разделы будут приходить в {h} (недели и месяцы — по понедельникам).', offAll: '🔕 Дополнительные разделы выключены. Ежедневный прогноз остаётся.' },
  uz: { head: '⏰ <b>Bu chatga nima yuborilsin</b>', main: '🗓 Kunlik prognoz (asosiy post) — soat {h}, davlatlar: {c}. O‘zgartirish: /sozla', snow: '❄️ Tog‘larda qor haqida xabar', tip: 'Vaqtni tanlash yoki o‘chirish uchun bo‘limni bosing. Vaqt — Toshkent bo‘yicha. Faqat adminlar o‘zgartira oladi.', all: '✅ Hammasini yoqish', allOff: '🔕 Hammasini o‘chirish', allOn: '✅ Hammasi yoqildi: bo‘limlar soat {h} da keladi (haftalar va oylar — dushanba kunlari).', offAll: '🔕 Qo‘shimcha bo‘limlar o‘chirildi. Kunlik prognoz qoladi.' },
  en: { head: '⏰ <b>What to send to this chat</b>', main: '🗓 Daily forecast (the main post) — at {h}, countries: {c}. To change: /settings', snow: '❄️ Snow alerts in the mountains', tip: 'Tap a section to choose its time or turn it off. Time — Tashkent time. Only admins can change it.', all: '✅ Turn all on', allOff: '🔕 Turn all off', allOn: '✅ All on: the sections will come at {h} (weeks and months — on Mondays).', offAll: '🔕 The extra sections are off. The daily forecast goes on.' } };
async function groupNotif(env, chat, lang, msgId, note) {
  if (!env.DB) return; await db(env);
  const G = GNX[lang] || GNX.ru, s0 = await sub(env, chat), regs = regionsOf(s0), uz = !regs.length || regs.includes('UZ');
  const rows = (await env.DB.prepare('SELECT * FROM notif WHERE chat_id = ?1').bind(chat).all()).results, by = Object.fromEntries(rows.map(r => [r.sec, r]));
  const snow = await mtnSub(env, chat), secs = NSEC.filter(x => uz || !['outlook', 'mtn', 'dyn'].includes(x));  // weeks/months and the mountains are about Uzbekistan
  const text = [...(note ? [note, ''] : []), G.head, '', G.main.replace('{h}', hh(s0 && s0.post_hour != null ? s0.post_hour : POST_HOUR)).replace('{c}', (regs.length ? regs : ['UZ']).map(r => `${FLAG[r] || ''} ${NAMES[r] ? NAMES[r][lang] : r}`).join(', ')), '', G.tip].join('\n');
  const kb = [...secs.map(sec => [{ text: `${by[sec] ? '✅' : '➕'} ${(RKL[lang] || RKL.ru)[sec]}${by[sec] ? ` · ${hh(by[sec].hour)}` : ''}`, callback_data: `NS:${lang}:${sec}` }]),
    ...(uz ? [[{ text: `${snow ? '✅' : '➕'} ${G.snow}`, callback_data: `WS:${lang}` }]] : []),
    [{ text: G.all, callback_data: `WA:${lang}` }, { text: G.allOff, callback_data: `WX:${lang}` }]];
  const body = { chat_id: chat, text, parse_mode: 'HTML', reply_markup: { inline_keyboard: kb } };
  if (msgId) { const r = await tg(env, 'editMessageText', { ...body, message_id: msgId }); if (r.ok || /not modified/.test(r.description || '')) return r; }
  return tg(env, 'sendMessage', body);
}
async function groupAll(env, chat, lang, on) {  // every section at the group's post hour (and the snow signal), or all of them off
  const s0 = await sub(env, chat), h = s0 && s0.post_hour != null ? s0.post_hour : POST_HOUR, regs = regionsOf(s0), uz = !regs.length || regs.includes('UZ');
  if (!on) { await env.DB.prepare('DELETE FROM notif WHERE chat_id = ?1').bind(chat).run(); await env.DB.prepare('DELETE FROM mtn WHERE chat_id = ?1').bind(chat).run(); return; }
  const last = h <= new Date(Date.now() + TZ * 3600e3).getUTCHours() ? todayTZ() : '';
  for (const sec of NSEC.filter(x => uz || !['outlook', 'mtn', 'dyn'].includes(x)))
    await env.DB.prepare('INSERT INTO notif (chat_id, sec, hour, lang, region, last_day, added) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7) ON CONFLICT(chat_id, sec) DO UPDATE SET hour = ?3, lang = ?4, region = ?5')
      .bind(chat, sec, h, lang, regs[0] || 'UZ', last, new Date().toISOString()).run();
  if (uz) await env.DB.prepare('INSERT OR REPLACE INTO mtn (chat_id, lang, ver, added) VALUES (?1, ?2, ?3, ?4)').bind(chat, lang, (await kv(env, 'mtn_ver')) || '', new Date().toISOString()).run();
}

// each cron run: the sections that are due now (a few per run: videos and pictures take time)
async function notifTick(env, small = false) {
  if (!env.DB) return; await db(env);
  const now = new Date(Date.now() + TZ * 3600e3), day = todayTZ(), hour = now.getUTCHours(), monday = now.getUTCDay() === 1;
  if (!(await kv(env, 'brief_mig'))) {  // once: everyone who gets the morning 🧭 also gets the ☀️ briefing at 07:00 (from tomorrow; it can be turned off)
    await env.DB.prepare("INSERT OR IGNORE INTO notif (chat_id, sec, hour, lang, region, last_day, added) SELECT chat_id, 'brief', 7, lang, region, ?1, ?2 FROM notif WHERE sec = 'traj'").bind(day, new Date().toISOString()).run();
    await setKv(env, 'brief_mig', day);
  }
  let due = (await env.DB.prepare("SELECT * FROM notif WHERE hour <= ?1 AND COALESCE(last_day, '') <> ?2 ORDER BY hour LIMIT 30").bind(hour, day).all()).results;
  if (due.some(n => n.sec !== 'air')) { const F = await siteFresh(env); if (!F.fresh) due = due.filter(n => n.sec === 'air' || hour - n.hour >= HOLD_MAX_H); }
  // a light section (one video each: 🧭) lets more people through in one run; the others stay at 6
  let heavy = 0, done = 0, br = 0;
  due = due.filter(n => (n.sec === 'traj' ? done++ < (small ? 5 : 12) : n.sec === 'brief' ? br++ < (small ? 3 : 7) : heavy++ < (small ? 2 : 6)));  // each send costs 2–3 of the 50 requests a run may make
  for (const n of due) {
    await env.DB.prepare('UPDATE notif SET last_day = ?3 WHERE chat_id = ?1 AND sec = ?2').bind(n.chat_id, n.sec, day).run();
    if (NWEEKLY[n.sec] && !monday) continue;
    const lang = RKL[n.lang] ? n.lang : 'ru', rid = NAMES[n.region] ? n.region : 'UZ';  // (groups: saved from their settings)
    let r = null;
    try {
      if (n.sec === 'days') {  // the 15-day forecast of the saved place (a group: its country's capital)
        const uu = n.chat_id > 0 ? await getUser(env, n.chat_id) : null, C = !(uu && uu.place) ? ((await cities(env, rid, lang)) || (await cities(env, rid, 'ru'))) : null, c0 = C && C.cities.find(c => c.lat != null);
        const pl = uu && uu.place ? JSON.parse(uu.place) : c0 ? [c0.lat, c0.lon] : [41.311, 69.279];
        r = await pointForecast(env, n.chat_id, lang, +pl[0], +pl[1], await nearestPlace(env, +pl[0], +pl[1], 8), null);
      } else if (n.sec === 'brief') r = await sendBrief(env, n.chat_id, lang, rid);
      else if (n.sec === 'dyn') { r = await sendDyn(env, n.chat_id, lang); await sendDynXlsx(env, n.chat_id, lang, 'pdf'); await sendDynXlsx(env, n.chat_id, lang); }
      else if (n.sec === 'hourly') r = await sendHourly(env, n.chat_id, lang, rid);
      else if (n.sec === 'outlook') r = await sendOutlookPart(env, n.chat_id, lang, 'w1');
      else if (n.sec === 'mtn') r = await sendMountains(env, n.chat_id, lang);
      else if (n.sec === 'air') r = await sendAir(env, n.chat_id, lang, rid);
      else if (n.sec === 'traj') r = await sendTrajLite(env, n.chat_id, lang, TRJ.has(rid) ? rid : 'UZ');
    } catch (e) {
      console.log('notif', n.sec, e && e.stack);
      if (/subrequests/i.test(String(e && e.message))) {  // out of this run's budget: not sent, so the next run tries again
        await env.DB.prepare('UPDATE notif SET last_day = NULL WHERE chat_id = ?1 AND sec = ?2').bind(n.chat_id, n.sec).run().catch(() => {});
        break;
      }
    }
    if (r && !r.ok && /blocked|deactivated|chat not found|kicked|not a member|was deleted|not enough rights/i.test(r.description || '')) await env.DB.prepare('DELETE FROM notif WHERE chat_id = ?1').bind(n.chat_id).run();
  }
}

/* ---------- the air today: dust and air quality hour by hour at the person's place (CAMS via Open-Meteo) ---------- */
const AQX = {
  ru: { title: '🌫 <b>Воздух сегодня</b>', now: 'Сейчас', max: 'Хуже всего сегодня', hours: 'По часам (индекс AQI)', pm: 'PM10 {a} · PM2.5 {b} мкг/м³', dust: 'пыль {d} мкг/м³',
    bands: ['хорошо', 'умеренно', 'вредно для чувствительных', 'вредно', 'очень вредно', 'опасно'],
    tips: ['', '', '🙂 Людям с астмой и детям лучше меньше быть на улице', '😷 Сократите время на улице, закройте окна', '😷 Маска N95, без нужды не выходите', '⛔ Оставайтесь дома, закройте окна'],
    src: 'Прогноз CAMS (ECMWF Copernicus) · Open-Meteo', none: 'Не удалось получить данные о воздухе, попробуйте позже.', map: 'Карта пыли по Узбекистану' },
  uz: { title: '🌫 <b>Bugungi havo sifati</b>', now: 'Hozir', max: 'Bugun eng yomoni', hours: 'Soatma-soat (AQI indeksi)', pm: 'PM10 {a} · PM2.5 {b} mkg/m³', dust: 'chang {d} mkg/m³',
    bands: ['yaxshi', 'o‘rtacha', 'sezgirlar uchun zararli', 'zararli', 'juda zararli', 'xavfli'],
    tips: ['', '', '🙂 Astmasi borlar va bolalar ko‘chada kamroq bo‘lgani yaxshi', '😷 Ko‘chada kamroq bo‘ling, derazalarni yoping', '😷 N95 niqob, keraksiz chiqmang', '⛔ Uyda qoling, derazalarni yoping'],
    src: 'CAMS prognozi (ECMWF Copernicus) · Open-Meteo', none: 'Havo ma’lumotlarini olib bo‘lmadi, keyinroq urinib ko‘ring.', map: 'O‘zbekiston bo‘yicha chang xaritasi' },
  en: { title: '🌫 <b>Air quality today</b>', now: 'Now', max: 'Worst today', hours: 'By the hour (AQI)', pm: 'PM10 {a} · PM2.5 {b} µg/m³', dust: 'dust {d} µg/m³',
    bands: ['good', 'moderate', 'unhealthy for sensitive groups', 'unhealthy', 'very unhealthy', 'hazardous'],
    tips: ['', '', '🙂 People with asthma and children should stay outside less', '😷 Stay outside less, close the windows', '😷 N95 mask, do not go out without need', '⛔ Stay at home, close the windows'],
    src: 'CAMS forecast (ECMWF Copernicus) · Open-Meteo', none: 'Could not get the air data, try again later.', map: 'Dust map of Uzbekistan' } };
const aqBand = v => v == null ? 0 : v <= 50 ? 0 : v <= 100 ? 1 : v <= 150 ? 2 : v <= 200 ? 3 : v <= 300 ? 4 : 5;
const AQ_DOT = ['🟢', '🟡', '🟠', '🔴', '🟣', '🟤'];
async function sendAir(env, chat, lang, rid) {
  const X = AQX[lang] || AQX.ru, u = chat > 0 ? await getUser(env, chat) : null, pl = u && u.place ? JSON.parse(u.place) : null;
  let lat, lon, name;
  if (pl) { lat = +pl[0]; lon = +pl[1]; const np = await nearestPlace(env, lat, lon); name = np ? `${FLAG[np[4]] || '📍'} ${pname(np, lang)}` : `📍 ${lat.toFixed(2)}, ${lon.toFixed(2)}`; }
  else { const C = (await cities(env, rid, lang)) || (await cities(env, rid, 'ru')), c = C && C.cities.find(c => c.lat != null);
    if (c) { lat = c.lat; lon = c.lon; name = `${FLAG[rid] || ''} ${c.name}`; } else { lat = 41.31; lon = 69.28; name = '🇺🇿 Toshkent'; } }
  const j = await fetch(`https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${lat.toFixed(3)}&longitude=${lon.toFixed(3)}&hourly=us_aqi,pm10,pm2_5,dust&current=us_aqi,pm10,pm2_5,dust&timezone=auto&forecast_days=1`).then(r => r.ok ? r.json() : null).catch(() => null);
  if (!j || !j.hourly) return tg(env, 'sendMessage', { chat_id: chat, text: X.none, ...(chat > 0 ? { reply_markup: { inline_keyboard: [[notifBtn(lang, 'air')]] } } : {}) });
  const Hh = j.hourly, c = j.current || {}, b = aqBand(c.us_aqi), r0 = v => v == null ? '—' : Math.round(v);
  let mi = 0; Hh.us_aqi.forEach((v, i) => { if (v != null && v > (Hh.us_aqi[mi] ?? -1)) mi = i; });
  const hrs = []; for (let i = 0; i < Hh.time.length; i += 3) { const v = Hh.us_aqi[i]; hrs.push(`${Hh.time[i].slice(11, 13)}:00 ${AQ_DOT[aqBand(v)]} ${r0(v)}`); }
  const out = [`${X.title} · <b>${esc(name)}</b>`, '',
    `${X.now}: ${AQ_DOT[b]} <b>${r0(c.us_aqi)}</b> — ${X.bands[b]}`, `   ${X.pm.replace('{a}', r0(c.pm10)).replace('{b}', r0(c.pm2_5))}${c.dust >= 20 ? ` · ${X.dust.replace('{d}', r0(c.dust))}` : ''}`,
    `${X.max}: ${AQ_DOT[aqBand(Hh.us_aqi[mi])]} <b>${r0(Hh.us_aqi[mi])}</b> ${X.bands[aqBand(Hh.us_aqi[mi])]} · ${Hh.time[mi].slice(11, 16)}`,
    ...(X.tips[Math.max(b, aqBand(Hh.us_aqi[mi]))] ? ['', X.tips[Math.max(b, aqBand(Hh.us_aqi[mi]))]] : []),
    '', `<b>${X.hours}</b>`, `<pre>${hrs.reduce((a, x, i) => a + x.padEnd(14) + (i % 2 ? '\n' : ''), '')}</pre>`,
    `🟢 ≤50 · 🟡 ≤100 · 🟠 ≤150 · 🔴 ≤200 · 🟣 ≤300 · 🟤 >300`, `<i>${X.src}</i>`];
  const kb = chat > 0 ? { inline_keyboard: [[notifBtn(lang, 'air')]] } : undefined;
  // in Uzbekistan the dust map of today goes first (prob/outlook.py, dust0)
  const av = `${EVRAW}/air/air24_${lang === 'uz' ? 'uz' : 'ru'}.mp4`;
  if (rid === 'UZ' && await fetch(av, { method: 'HEAD' }).then(r => r.ok).catch(() => false)) {  // the 24-hour air video (CAMS, made every hour) instead of the picture
    await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
    await tg(env, 'sendVideo', { chat_id: chat, video: `${av}?v=${Math.floor(Date.now() / 1800e3)}`, supports_streaming: true, width: 1920, height: 1080, caption: `🌫 ${X.title} · 24 ${lang === 'uz' ? 'soat' : lang === 'en' ? 'hours' : 'часа'} · CAMS (Copernicus)` });
  } else if (rid === 'UZ') {
    const I = await (await fetch(`${base(env)}/prob/outlook/index.json?t=${fresh()}`)).json().catch(() => null), it = I && (I.items.find(i => i.key === 'dust' && i.lang === lang) || I.items.find(i => i.key === 'dust'));
    if (it) await tg(env, 'sendPhoto', { chat_id: chat, photo: `${base(env)}/prob/${(it.imgs || [it.img])[0]}?v=${encodeURIComponent(I.made || '')}`, caption: `🌫 ${X.map}` });
  }
  return tg(env, 'sendMessage', { chat_id: chat, text: out.join('\n'), parse_mode: 'HTML', ...(kb ? { reply_markup: kb } : {}) });
}

/* ---------- mountains of Uzbekistan: fresh snow and good days for a trip (site/prob/mountains.json, prob/mountains.py) ---------- */
const MTX = {
  ru: { title: '🏔 <b>Горы Узбекистана: снег и поездки</b>', rain: '🌧 Дождь', mm: 'мм', m: 'м', snow: '❄️ Ожидается снег', noSnow: '❄️ Снегопадов в ближайшие 16 дней не видно', cm: 'см', cover: '⛄ Снег лежит', go: '🥾 Когда ехать', noGo: '🥾 Хороших дней для поездки пока не видно', after: '👉 После снега лучше всего', wind: 'ветер до', ms: 'м/с',
    foot: 'Прогноз на 16 дней с поправкой на высоту · ECMWF, DWD, NOAA (Open-Meteo). Снегопад — от 2 см за сутки; хороший день — сухо, солнечно, без сильного ветра.', sub: '🔔 Сигнал о снеге в горах', unsub: '🔕 Выключить сигнал о снеге', on: '🔔 Сигнал включён: напишу, как только в горах ожидается снег, и подскажу, в какой день лучше ехать.', off: '🔕 Сигнал о снеге выключен.', alert: '❄️ <b>В горах ожидается снег!</b>', fresh: (n, cm) => `ожидается ~${n} ${cm} снега`, all: '🏔 Все горы', none: 'Данные по горам ещё готовятся, попробуйте чуть позже.' },
  uz: { title: '🏔 <b>O‘zbekiston tog‘lari: qor va sayohat</b>', rain: '🌧 Yomg‘ir', mm: 'mm', m: 'm', snow: '❄️ Qor kutilmoqda', noSnow: '❄️ Yaqin 16 kunda qor yog‘ishi kutilmayapti', cm: 'sm', cover: '⛄ Qor qoplami', go: '🥾 Qachon borish kerak', noGo: '🥾 Hozircha sayohat uchun yaxshi kun ko‘rinmayapti', after: '👉 Qordan keyin eng yaxshi kun', wind: 'shamol', ms: 'm/s',
    foot: '16 kunlik prognoz, balandlikka moslangan · ECMWF, DWD, NOAA (Open-Meteo). Qor yog‘ishi — sutkada 2 sm dan; yaxshi kun — quruq, quyoshli, kuchli shamolsiz.', sub: '🔔 Tog‘da qor haqida xabar', unsub: '🔕 Qor xabarini o‘chirish', on: '🔔 Xabar yoqildi: tog‘larda qor kutilishi bilan yozaman va qaysi kuni borish yaxshiligini aytaman.', off: '🔕 Qor xabari o‘chirildi.', alert: '❄️ <b>Tog‘larda qor kutilmoqda!</b>', fresh: (n, cm) => `~${n} ${cm} qor kutilmoqda`, all: '🏔 Barcha tog‘lar', none: 'Tog‘lar ma’lumoti hali tayyorlanmoqda, birozdan keyin urinib ko‘ring.' },
  en: { title: '🏔 <b>Mountains of Uzbekistan: snow and trips</b>', rain: '🌧 Rain', mm: 'mm', m: 'm', snow: '❄️ Snow expected', noSnow: '❄️ No snowfall in sight in the next 16 days', cm: 'cm', cover: '⛄ Snow cover', go: '🥾 When to go', noGo: '🥾 No good day for a trip in sight yet', after: '👉 The best day after the snow', wind: 'wind', ms: 'm/s',
    foot: 'A 16-day forecast corrected for height · ECMWF, DWD, NOAA (Open-Meteo). Snowfall — from 2 cm a day; a good day — dry, sunny, no hard wind.', sub: '🔔 Snow alerts in the mountains', unsub: '🔕 Turn snow alerts off', on: '🔔 Alerts on: I will write when snow is expected in the mountains and say which day is good to go.', off: '🔕 Snow alerts are off.', alert: '❄️ <b>Snow expected in the mountains!</b>', fresh: (n, cm) => `~${n} ${cm} of snow expected`, all: '🏔 All mountains', none: 'The mountains’ data is being prepared, try again a little later.' },
};
const wIcon = c => c == null ? '' : c <= 1 ? '☀️' : c === 2 ? '🌤' : c === 3 ? '☁️' : c <= 48 ? '🌫' : c <= 67 ? '🌧' : c <= 77 ? '🌨' : c <= 82 ? '🌦' : c <= 86 ? '🌨' : '⛈';
const sgn = t => `${t > 0 ? '+' : t < 0 ? '−' : ''}${Math.abs(Math.round(t))}°`;
async function mountainsData(env) {
  const r = await fetch(`${base(env)}/prob/mountains.json?t=${Date.now()}`, { cf: { cacheTtl: 0 } });
  return r.ok ? r.json().catch(() => null) : null;
}
const dayW = (d, lang) => { const X = MTX[lang] || MTX.ru; return `${dayLabel(d.d, lang)} ${wIcon(d.code)} ${sgn(d.tmin)}…${sgn(d.tmax)}, ${X.wind} ${Math.round(d.gust)} ${X.ms}`; };
// the first good day after a snow day (the same three days), for "when to go and see the snow"
const afterSnow = (sp, d) => sp.days.find(x => x.d > d && x.good > 0 && (new Date(x.d) - new Date(d)) <= 3 * 864e5);
async function mtnSub(env, chat) { if (!env.DB) return null; await db(env); return env.DB.prepare('SELECT * FROM mtn WHERE chat_id = ?1').bind(chat).first(); }
const MTA = { ru: { pick: 'Выберите место — расскажу про снег и лучшие дни:', all: '📋 Все горы текстом' },
              uz: { pick: 'Joyni tanlang — qor va eng yaxshi kunlarni aytaman:', all: '📋 Barcha tog‘lar matnda' },
              en: { pick: 'Choose a place — I will tell you about the snow and the best days:', all: '📋 All mountains as text' } };
function spotLines(sp, M, lang) {
  const X = MTX[lang] || MTX.ru, today = todayTZ(), days = sp.days.filter(d => d.d >= today), snow = days.filter(d => d.sn >= (M.snow_cm || 2)), out = [];
  out.push(`<b>${esc(sp.name[lang] || sp.name.ru)}</b> · ${sp.elev} ${X.m} · ${esc(sp.area[lang] || sp.area.ru)}`);
  out.push(snow.length ? `${X.snow}: ${snow.slice(0, 4).map(d => `${dayLabel(d.d, lang)} ~${Math.round(d.sn)} ${X.cm}`).join(', ')}` : X.noSnow);
  const rain = days.slice(0, 10).filter(d => (d.rn || 0) >= 2);
  if (rain.length) out.push(`${X.rain}: ${rain.slice(0, 4).map(d => `${dayLabel(d.d, lang)} ~${Math.round(d.rn)} ${X.mm}`).join(', ')}`);
  if (days[0] && days[0].depth >= 1) out.push(`${X.cover}: ~${days[0].depth} ${X.cm}`);
  const a = snow.length ? afterSnow(sp, snow[0].d) : null;
  if (a) out.push(`${X.after}: <b>${dayW(a, lang)}</b>`);
  const g = days.slice(0, 10).filter(d => d.good > 0).sort((p, q) => q.good - p.good || (p.d < q.d ? -1 : 1)).slice(0, 3).sort((p, q) => p.d < q.d ? -1 : 1);
  if (g.length) { out.push(`${X.go}:`); g.forEach(d => out.push(`   • ${dayW(d, lang)}`)); } else out.push(X.noGo);
  return out;
}
// the segment buttons: one per place (two in a row, a snowflake where fresh snow is coming), all as text, the snow signal
async function mountainsKb(env, chat, lang, M, cur) {
  const X = MTX[lang] || MTX.ru, A = MTA[lang] || MTA.ru, today = todayTZ(), s = await mtnSub(env, chat);
  const b = M.spots.map(sp => ({ text: `${cur === sp.id ? '✅' : sp.days.some(d => d.d >= today && d.sn >= (M.snow_cm || 2)) ? '❄️' : '⛰'} ${sp.name[lang] || sp.name.ru}`, callback_data: `MP:${lang}:${sp.id}` }));
  const rows = []; for (let i = 0; i < b.length; i += 2) rows.push(b.slice(i, i + 2));
  rows.push([{ text: A.all, callback_data: `MA:${lang}` }]);
  rows.push([{ text: s ? X.unsub : X.sub, callback_data: `MS:${lang}`, style: s ? undefined : 'success' }]);
  rows.push([notifBtn(lang, 'mtn')]);
  return { inline_keyboard: rows };
}
async function sendMountains(env, chat, lang) {
  const X = MTX[lang] || MTX.ru, M = await mountainsData(env);
  if (!M || !M.spots) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  // the picture (10 days for every place) with the places as buttons under it
  if (chat < 0) {  // a group or channel: the picture and every place as text, no buttons
    await tg(env, 'sendPhoto', { chat_id: chat, photo: `${base(env)}/prob/mountains_${lang === 'uz' ? 'uz' : 'ru'}.png?v=${fresh()}`, caption: X.title, parse_mode: 'HTML' });
    return sendMountainText(env, chat, lang, null);
  }
  const kb = await mountainsKb(env, chat, lang, M), cap = `${X.title}\n${(MTA[lang] || MTA.ru).pick}`;
  // the video on the map first (tools/mtn_video.py, the "mtn" branch), the picture if it is not there
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
  const rv = await tg(env, 'sendVideo', { chat_id: chat, video: `${EVRAW}/mtn/mtn_${lang === 'uz' ? 'uz' : 'ru'}.mp4?v=${Math.floor(Date.now() / 3600e3)}`, caption: cap, parse_mode: 'HTML', supports_streaming: true, width: 1920, height: 1080, reply_markup: kb });
  if (rv.ok) return rv;
  const r = await tg(env, 'sendPhoto', { chat_id: chat, photo: `${base(env)}/prob/mountains_${lang === 'uz' ? 'uz' : 'ru'}.png?v=${fresh()}`, caption: cap, parse_mode: 'HTML', reply_markup: kb });
  return r.ok ? r : tg(env, 'sendMessage', { chat_id: chat, text: cap, parse_mode: 'HTML', reply_markup: kb });
}
// one place (id) or all of them as text, with the same buttons
async function sendMountainText(env, chat, lang, id) {
  const X = MTX[lang] || MTX.ru, M = await mountainsData(env);
  if (!M || !M.spots) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  const spots = id ? M.spots.filter(sp => sp.id === id) : M.spots, out = id ? [] : [X.title];
  spots.forEach(sp => { if (out.length) out.push(''); out.push(...spotLines(sp, M, lang)); });
  out.push('', `<i>${X.foot}</i>`);
  return tg(env, 'sendMessage', { chat_id: chat, text: out.join('\n').slice(0, 4000), parse_mode: 'HTML', disable_web_page_preview: true, ...(chat > 0 ? { reply_markup: await mountainsKb(env, chat, lang, M, id) } : {}) });
}
// after each update: tell everyone who asked about NEW fresh snow in the next 6 days, with the best day to go (07–21 h)
async function mtnTick(env) {
  if (!env.DB) return; await db(env);
  const hour = new Date(Date.now() + TZ * 3600e3).getUTCHours();
  if (hour < 7 || hour > 21) return;
  const M = await mountainsData(env); if (!M || !M.spots) return;
  if ((await kv(env, 'mtn_made')) !== M.made) {
    const today = todayTZ(), lim = new Date(Date.now() + TZ * 3600e3 + 6 * 864e5).toISOString().slice(0, 10);
    const prev = JSON.parse((await kv(env, 'mtn_keys')) || '[]'), ev = [];
    for (const sp of M.spots) for (const d of sp.days) if (d.sn >= (M.snow_cm || 2) && d.d >= today && d.d <= lim && !prev.includes(`${sp.id}|${d.d}`)) ev.push({ id: sp.id, d: d.d });
    if (ev.length) {
      await setKv(env, 'mtn_new', JSON.stringify(ev)); await setKv(env, 'mtn_ver', M.made);
      await setKv(env, 'mtn_keys', JSON.stringify([...prev.slice(-200), ...ev.map(e => `${e.id}|${e.d}`)]));
    }
    await setKv(env, 'mtn_made', M.made);
  }
  const ver = await kv(env, 'mtn_ver'); if (!ver) return;
  const ev = JSON.parse((await kv(env, 'mtn_new')) || '[]'); if (!ev.length) return;
  const due = (await env.DB.prepare("SELECT * FROM mtn WHERE COALESCE(ver, '') <> ?1 LIMIT 10").bind(ver).all()).results;
  for (const s of due) {
    const lang = MTX[s.lang] ? s.lang : 'ru', X = MTX[lang], out = [X.alert];
    for (const e of ev) {
      const sp = M.spots.find(x => x.id === e.id), d = sp && sp.days.find(x => x.d === e.d); if (!d) continue;
      out.push('', `<b>${esc(sp.name[lang] || sp.name.ru)}</b> — ${dayLabel(d.d, lang)}: ${X.fresh(Math.round(d.sn), X.cm)} ${wIcon(d.code)}`);
      const a = afterSnow(sp, d.d); if (a) out.push(`${X.after}: <b>${dayW(a, lang)}</b>`);
    }
    const r = await tg(env, 'sendMessage', { chat_id: s.chat_id, text: out.join('\n'), parse_mode: 'HTML', reply_markup: { inline_keyboard: [[{ text: X.all, callback_data: `MT:${lang}` }]] } });
    if (!r.ok && /blocked|deactivated|chat not found|kicked/i.test(r.description || '')) { await env.DB.prepare('DELETE FROM mtn WHERE chat_id = ?1').bind(s.chat_id).run(); continue; }
    await env.DB.prepare('UPDATE mtn SET ver = ?2 WHERE chat_id = ?1').bind(s.chat_id, ver).run();
  }
}
// the menu is a keyboard under the input field (white buttons, as in the screenshot): one place for everything, no buttons under messages
const RKL = {
  ru: { evv: '🎬 Видео: тучи 12 ч и 3 дня', brief: '☀️ Утренний брифинг', dyn: '📊 Динамика к прошлому году', rain: '🌧 Осадки и тучи', more: '⚙️ Ещё', traj: '🧭 Откуда придут осадки', hourly: '⏱ Сегодня и завтра по часам', regions: '🗺 Погода по регионам', days: '🗓 Прогноз на 15 дней', video: '🎬 Видео-прогноз 15 дней', outlook: '📅 Недели и месяцы (карты)', mtn: '🏔 Горы: снег и поездки', now: '🌡 Погода сейчас', air: '🌫 Воздух сегодня', cities: '🏙 Выбрать город', loc: '📍 Отправить моё место', countries: '🌍 Сменить страну', daily: '🔔 Прогноз каждое утро', notif: '⏰ Мои уведомления', accuracy: '🎯 Точность прогноза', alerts: '⚠️ Опасная погода', site: '🗺 Карта-сайт и глобус', home: '🏠 Главное меню', reset: '🔄 Начать заново', back: '⬅️ Назад', help: 'ℹ️ Инструкция' },
  uz: { evv: '🎬 Video: bulutlar 12 soat va 3 kun', brief: '☀️ Ertalabki brifing', dyn: '📊 O‘tgan yilga nisbatan dinamika', rain: '🌧 Yog‘in va bulutlar', more: '⚙️ Yana', traj: '🧭 Yog‘in qayerdan keladi', hourly: '⏱ Bugun va ertaga soatma-soat', regions: '🗺 Viloyatlar bo‘yicha', days: '🗓 15 kunlik prognoz', video: '🎬 15 kunlik video-prognoz', outlook: '📅 Haftalar va oylar (xaritalar)', mtn: '🏔 Tog‘lar: qor va sayohat', now: '🌡 Hozirgi ob-havo', air: '🌫 Bugungi havo sifati', cities: '🏙 Shaharni tanlash', loc: '📍 Joyimni yuborish', countries: '🌍 Davlatni almashtirish', daily: '🔔 Har tongi prognoz', notif: '⏰ Bildirishnomalarim', accuracy: '🎯 Prognoz aniqligi', alerts: '⚠️ Xavfli ob-havo', site: '🗺 Xarita-sayt va globus', home: '🏠 Bosh menyu', reset: '🔄 Qaytadan boshlash', back: '⬅️ Orqaga', help: 'ℹ️ Yo‘riqnoma' },
  en: { evv: '🎬 Video: clouds 12 hours and 3 days', brief: '☀️ Morning summary', dyn: '📊 Compared with last year', rain: '🌧 Precipitation and clouds', more: '⚙️ More', traj: '🧭 Where the rain comes from', hourly: '⏱ Today and tomorrow by the hour', regions: '🗺 By regions', days: '🗓 15-day forecast', video: '🎬 15-day video forecast', outlook: '📅 Weeks and months (maps)', mtn: '🏔 Mountains: snow and trips', now: '🌡 Weather now', air: '🌫 Air quality today', cities: '🏙 Choose a city', loc: '📍 Send my location', countries: '🌍 Change country', daily: '🔔 Forecast every morning', notif: '⏰ My notifications', accuracy: '🎯 Forecast accuracy', alerts: '⚠️ Dangerous weather', site: '🗺 Map website and globe', home: '🏠 Main menu', reset: '🔄 Start over', back: '⬅️ Back', help: 'ℹ️ Guide' } };
// the labels the keyboard had before (people may still have the old keyboard on their phone): they keep working
const RKL_OLD = {
  ru: { days: '🗓 15 дней', video: '🎬 Видео на 15 дней', outlook: '📅 Недели и месяцы', mtn: '🏔 Горы и снег', now: '🌡 Сейчас', cities: '🏙 Города', loc: '📍 Моё место', countries: '🌍 Страны', daily: '🔔 Каждый день', accuracy: '🎯 Точность', alerts: '⚠️ Предупреждения', site: '🗺 Сайт и глобус', home: '🏠 Главная', reset: '🔄 Сбросить', help: 'ℹ️ Помощь' },
  uz: { days: '🗓 15 kun', video: '🎬 15 kunlik video', outlook: '📅 Haftalar va oylar', mtn: '🏔 Tog‘lar va qor', now: '🌡 Hozir', cities: '🏙 Shaharlar', loc: '📍 Mening joyim', countries: '🌍 Davlatlar', daily: '🔔 Har kuni', accuracy: '🎯 Aniqlik', alerts: '⚠️ Ogohlantirishlar', site: '🗺 Sayt va globus', reset: '🔄 Qayta boshlash', help: 'ℹ️ Yordam' },
  en: { days: '🗓 15 days', video: '🎬 15-day video', outlook: '📅 Weeks and months', mtn: '🏔 Mountains and snow', now: '🌡 Now', cities: '🏙 Cities', loc: '📍 My location', countries: '🌍 Countries', daily: '🔔 Every day', accuracy: '🎯 Accuracy', alerts: '⚠️ Alerts', site: '🗺 Website and globe', reset: '🔄 Reset', help: 'ℹ️ Help' } };
// «🌧 Rain and clouds»: everything about rain and snow in one place; «⚙️ More»: the rare things
const RAINM = { ru: { t: '🌧 <b>Осадки и тучи</b> — выберите:', now: '⏱ Сегодня и завтра (видео)', pr: '🎬 Вероятность осадков, 15 дней' }, uz: { t: '🌧 <b>Yog‘in va bulutlar</b> — tanlang:', now: '⏱ Bugun va ertaga (video)', pr: '🎬 Yog‘in ehtimoli, 15 kun' },
  en: { t: '🌧 <b>Precipitation and clouds</b> — choose:', now: '⏱ Today and tomorrow (video)', pr: '🎬 Chance of precipitation, 15 days' } };
function rainMenu(env, chat, lang, rid) {
  const X = TJX[lang] || TJX.ru, M = RAINM[lang] || RAINM.ru, R = RKL[lang] || RKL.ru;
  const rows = [[{ text: R.traj, callback_data: `TJ:${lang}:${rid}` }], [{ text: M.now, callback_data: `MA:${lang}:hourly` }],
    [{ text: X.m15, callback_data: `MV:${lang}:${rid}` }], [{ text: X.acc, callback_data: `AV:${lang}:${rid}` }], [{ text: M.pr, callback_data: `V:${lang}:${rid}` }],
    [{ text: (SATX[lang] || SATX.ru).cl, callback_data: `SV:${lang}:${rid}:clouds` }], ...moistBtns(env, lang, rid, chat)];
  return tg(env, 'sendMessage', { chat_id: chat, text: M.t, parse_mode: 'HTML', reply_markup: { inline_keyboard: rows } });
}
// the satellite videos (tools/sat_videos.py, the workflow sat.yml every ~30 min, kept on the repository's "sat" branch)
const SATX = { ru: { cl: '🛰 Спутник онлайн: тучи и осадки', rn: '🌧 Видео со спутника: где идут осадки', capc: 'Спутник Meteosat (EUMETSAT) за 6 часов: белое — ясно, серое — тучи, синее — осадки', capr: 'Где идут осадки: оценка со спутника (H SAF) за 6 часов',
    last: 'последний снимок', none: 'Видео со спутника готовится — загляните через несколько минут.' },
  uz: { cl: '🛰 Sun’iy yo‘ldosh onlayn: bulut va yog‘in', rn: '🌧 Sun’iy yo‘ldosh videosi: yog‘in qayerda', capc: 'Meteosat (EUMETSAT), 6 soat: oq — ochiq osmon, kulrang — bulut, ko‘k — yog‘in', capr: 'Yog‘in qayerda: sun’iy yo‘ldosh bahosi (H SAF), 6 soat',
    last: 'oxirgi surat', none: 'Sun’iy yo‘ldosh videosi tayyorlanmoqda — bir necha daqiqadan keyin qarang.' } };
const satRaw = (f, ref = 'sat') => `https://raw.githubusercontent.com/${REPO}/${ref}/${f}`;
// the newest commit of the "sat" branch: its files by commit are never served stale by GitHub's cache (the branch name is, up to 5 min)
async function satRef(env) { const r = await ghApi(env, 'commits/sat').then(x => x.ok ? x.json() : null).catch(() => null); return r && r.sha ? r.sha : 'sat'; }
async function sendSat(env, chat, lang, rid, kind) {
  const X = SATX[lang] || SATX.ru, L = lang === 'uz' ? 'uz' : 'ru';
  const ref = await satRef(env), meta = await fetch(satRaw('meta.json', ref)).then(r => r.ok ? r.json() : null).catch(() => null);
  const v = meta && await fetch(satRaw(`${rid}_${kind}_${L}.mp4`, ref)).then(r => r.ok ? r.arrayBuffer() : null).catch(() => null);
  if (!v) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  const t = new Date(Date.parse(kind === 'rain' ? meta.rain : meta.last) + (rid === 'KG' ? 6 : 5) * 3600e3).toISOString().slice(11, 16);
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
  const fd = new FormData(); fd.append('chat_id', String(chat)); fd.append('supports_streaming', 'true');
  fd.append('caption', `${FLAG[rid]} ${NAMES[rid][lang]} · ${kind === 'rain' ? X.capr : X.capc} · ${X.last} ${t}`);
  fd.append('video', new Blob([v], { type: 'video/mp4' }), `${rid}_${kind}.mp4`);
  return fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendVideo`, { method: 'POST', body: fd }).then(r => r.json()).catch(() => null);
}
// keep the satellite videos fresh: GitHub's schedule is unreliable, so the bot asks for a new one when the last is over 35 min old
async function satTick(env) {  // every 10 minutes: a new snapshot at EUMETSAT → new videos at once (they take ~3 min)
  if (!env.GH_TOKEN) return;
  const meta = await fetch(satRaw('meta.json', await satRef(env))).then(r => r.ok ? r.json() : null).catch(() => null);
  const cap = await fetch('https://view.eumetsat.int/geoserver/msg_iodc/ir108/wms?service=WMS&request=GetCapabilities&version=1.3.0').then(r => r.ok ? r.text() : '').catch(() => '');
  const m = cap.match(/<Dimension[^>]*name="time"[^>]*default="([^"]+)"/), newest = m ? Date.parse(m[1]) : 0;
  const have = meta ? Date.parse(meta.last) : 0;
  if (newest ? newest <= have : (meta && Date.now() - Date.parse(meta.made) < 35 * 60e3)) return;  // nothing newer yet
  if (Date.now() - +(await kv(env, 'sat_kick') || 0) < 7 * 60e3) return;  // asked a moment ago: it is being made
  await setKv(env, 'sat_kick', String(Date.now()));
  await ghApi(env, 'actions/workflows/sat.yml/dispatches', { method: 'POST', body: JSON.stringify({ ref: 'main' }), headers: { 'content-type': 'application/json' } });
}
// ---- ☀️ the morning briefing: one card — today at the person's place, against the same weekday last year, rain hours, gusts, warnings, tomorrow
const BRX = {
  ru: { hi: '☀️ <b>Доброе утро! Брифинг на {d}</b>', day: 'Днём', night: 'ночью', ly: '📊 К прошлому году ({d}): <b>{x}°</b> — {w}', warmer: 'теплее', colder: 'холоднее', same: 'так же',
    rain: '🌧 Осадки: {p}%, ~{mm} мм{h}', hrs: ', {a}:00–{b}:00', dry: '🌤 Без осадков', gust: '💨 Порывы до {g} м/с', tom: '➡️ Завтра: {i} {a}…{b}°, осадки {p}% · к прошлому году {x}°',
    big: '‼️ Завтра заметно {w}, чем год назад', hourly: '⏱ По часам', sat: '🛰 Спутник сейчас', dyn: '📊 Динамика', src: 'ECMWF · ERA5', mon: ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'], wd: ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'] },
  uz: { hi: '☀️ <b>Xayrli tong! {d} uchun brifing</b>', day: 'Kunduzi', night: 'kechasi', ly: '📊 O‘tgan yilga nisbatan ({d}): <b>{x}°</b> — {w}', warmer: 'iliqroq', colder: 'sovuqroq', same: 'xuddi shunday',
    rain: '🌧 Yog‘in: {p}%, ~{mm} mm{h}', hrs: ', {a}:00–{b}:00', dry: '🌤 Yog‘insiz', gust: '💨 Shamol shiddati {g} m/s gacha', tom: '➡️ Ertaga: {i} {a}…{b}°, yog‘in {p}% · o‘tgan yilga {x}°',
    big: '‼️ Ertaga o‘tgan yildan sezilarli {w}', hourly: '⏱ Soatma-soat', sat: '🛰 Sun’iy yo‘ldosh', dyn: '📊 Dinamika', src: 'ECMWF · ERA5', mon: ['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'], wd: ['ya', 'du', 'se', 'ch', 'pa', 'ju', 'sh'] } };
BRX.en = BRX.ru;
const BRC = { UZ: [41.31, 69.28], KZ: [51.17, 71.45], KG: [42.87, 74.59], TJ: [38.56, 68.79], TM: [37.95, 58.38] };
async function sendBrief(env, chat, lang, rid) {
  const X = BRX[lang] || BRX.ru, u = chat > 0 ? await getUser(env, chat) : null, pl = u && u.place ? JSON.parse(u.place) : null;
  const [lat, lon] = pl ? [+pl[0], +pl[1]] : (BRC[rid] || BRC.UZ), np = await nearestPlace(env, lat, lon, 40);
  const q = `latitude=${lat.toFixed(3)}&longitude=${lon.toFixed(3)}&timezone=auto`;
  const f = await fetch(`https://api.open-meteo.com/v1/forecast?${q}&daily=weather_code,temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,precipitation_probability_max,wind_gusts_10m_max&hourly=precipitation&wind_speed_unit=ms&forecast_days=2&models=ecmwf_ifs025`).then(r => r.ok ? r.json() : null).catch(() => null);
  if (!f || !f.daily) return tg(env, 'sendMessage', { chat_id: chat, text: (T[lang] || T.ru).none });
  const D = f.daily, d0 = new Date(D.time[0] + 'T00:00:00Z'), ly = i => new Date(d0.getTime() + (i - 364) * 864e5).toISOString().slice(0, 10);
  const a = await fetch(`https://archive-api.open-meteo.com/v1/archive?${q}&daily=temperature_2m_mean,temperature_2m_max&start_date=${ly(0)}&end_date=${ly(1)}`).then(r => r.ok ? r.json() : null).catch(() => null);
  const dl = dt => `${X.wd[dt.getUTCDay()]}, ${dt.getUTCDate()} ${X.mon[dt.getUTCMonth()]}`, sg = x => (x > 0 ? '+' : x < 0 ? '−' : '±') + Math.abs(x).toFixed(1).replace('.', lang === 'ru' ? ',' : '.');
  const t = x => `${x > 0 ? '+' : ''}${Math.round(x)}`;
  const out = [X.hi.replace('{d}', dl(d0)), `📍 ${np ? esc(pname(np, lang)) : `${lat.toFixed(2)}, ${lon.toFixed(2)}`}`, ''];
  out.push(`${wmoIcon(D.weather_code[0], true)} ${X.day} <b>${t(D.temperature_2m_max[0])}°</b>, ${X.night} ${t(D.temperature_2m_min[0])}° · ${((WMO[lang] || WMO.ru)[D.weather_code[0]] || '')}`);
  const dm = i => a && a.daily && a.daily.temperature_2m_mean[i] != null && D.temperature_2m_mean[i] != null ? D.temperature_2m_mean[i] - a.daily.temperature_2m_mean[i] : null;
  const w = x => x > 0.5 ? X.warmer : x < -0.5 ? X.colder : X.same;
  if (dm(0) != null) out.push(X.ly.replace('{d}', dl(new Date(d0.getTime() - 364 * 864e5)) + ' ' + (d0.getUTCFullYear() - 1)).replace('{x}', sg(dm(0))).replace('{w}', w(dm(0))));
  const H = f.hourly ? f.hourly.precipitation.slice(0, 24) : [], wet = H.map((x, i) => x >= 0.1 ? i : -1).filter(i => i >= 0);
  const mm = D.precipitation_sum[0] || 0, pp = D.precipitation_probability_max[0] ?? 0;
  out.push(mm >= 0.3 || pp >= 50 ? X.rain.replace('{p}', pp).replace('{mm}', mm < 1 ? mm.toFixed(1) : Math.round(mm)).replace('{h}', wet.length ? X.hrs.replace('{a}', String(wet[0]).padStart(2, '0')).replace('{b}', String(wet[wet.length - 1] + 1).padStart(2, '0')) : '') : X.dry);
  if ((D.wind_gusts_10m_max[0] || 0) >= 10) out.push(X.gust.replace('{g}', Math.round(D.wind_gusts_10m_max[0])));
  const A = await alertsData(env).catch(() => null), today = D.time[0], tom = D.time[1];
  const al = A ? A.items.filter(i => i.region === rid && (i.date === today || i.date === tom)).slice(0, 3) : [];
  if (al.length) { const txt = alertText(al, lang).split('\n').filter(l => /^[^\s<]/.test(l) && !/<b>[^<]*<\/b>$/.test(l)).slice(-3); out.push(...txt.map(l => '⚠️ ' + l.replace(/^\S+\s/, ''))); }
  if (D.time.length > 1) {
    out.push('', X.tom.replace('{i}', wmoIcon(D.weather_code[1], true)).replace('{a}', t(D.temperature_2m_min[1])).replace('{b}', t(D.temperature_2m_max[1])).replace('{p}', D.precipitation_probability_max[1] ?? 0).replace('{x}', dm(1) != null ? sg(dm(1)) : '—'));
    if (dm(1) != null && Math.abs(dm(1)) >= 5) out.push(X.big.replace('{w}', w(dm(1))));
  }
  out.push('', `<i>${X.src}</i>`);
  const kb = [[{ text: X.hourly, callback_data: `MA:${lang}:hourly` }, ...(TRJ.has(rid) ? [{ text: X.sat, callback_data: `SV:${lang}:${rid}:clouds` }] : [])], ...(rid === 'UZ' ? [[{ text: X.dyn, callback_data: `MA:${lang}:dyn` }]] : [])];
  return tg(env, 'sendMessage', { chat_id: chat, text: out.join('\n'), parse_mode: 'HTML', reply_markup: { inline_keyboard: kb } });
}

// ---- weather against last year: a short summary, the interactive page and two videos (made 3 times a day on the "lfl" branch)
const lflRaw = (f, ref) => `https://raw.githubusercontent.com/otabekvafoev92-del/ob-havo-ecmwf/${ref || 'lfl'}/${f}`;
async function lflRef(env) { const r = await ghApi(env, 'commits/lfl').then(x => x.ok ? x.json() : null).catch(() => null); return r && r.sha ? r.sha : 'lfl'; }
const DYN = {
  ru: { h: '📊 <b>Погода против прошлого года</b> · Узбекистан (среднее по 14 центрам регионов), LFL — те же дни недели год назад', m: 'Этот месяц', w: 'С начала года',
    pdf: '📄 PDF-отчёт с графиками и выводами', pdfc: '📄 Погода против прошлого года · PDF: главное, недели, месяц, регионы, показатели для бизнеса', xl: '📥 Excel-отчёт: регионы и 199 районов', xlc: '📊 Погода против прошлого года · Excel: сводка, недели, районы (8 недель + прогноз), этот месяц по дням', open: '📈 Интерактивно: регион, район, координаты', vw: '🎬 Видео: по неделям с начала года', vm: '🎬 Видео: этот месяц по дням', none: 'Данные готовятся, попробуйте через несколько минут.',
    note: 'Данные: ERA5 и прогноз ECMWF (модель, не метеостанции).' },
  uz: { h: '📊 <b>Ob-havo o‘tgan yilga nisbatan</b> · O‘zbekiston (14 viloyat markazi o‘rtachasi), LFL — o‘tgan yilning shu hafta kunlari', m: 'Shu oy', w: 'Yil boshidan',
    pdf: '📄 PDF-hisobot: grafiklar va xulosalar', pdfc: '📄 Ob-havo o‘tgan yilga nisbatan · PDF: asosiy, haftalar, oy, viloyatlar, biznes ko‘rsatkichlari', xl: '📥 Excel-hisobot: viloyatlar va 199 tuman', xlc: '📊 Ob-havo o‘tgan yilga nisbatan · Excel: xulosa, haftalar, tumanlar (8 hafta + prognoz), shu oy kunlar bo‘yicha', open: '📈 Interaktiv: viloyat, tuman, koordinata', vw: '🎬 Video: yil boshidan haftalar', vm: '🎬 Video: shu oy kunlar bo‘yicha', none: 'Ma’lumot tayyorlanmoqda, birozdan keyin urinib ko‘ring.',
    note: 'Ma’lumot: ERA5 va ECMWF prognozi (model, meteostansiya emas).' } };
async function sendDyn(env, chat, lang) {
  const L = lang === 'uz' ? 'uz' : 'ru', X = DYN[L], ref = await lflRef(env);
  const [w, m] = await Promise.all(['weeks', 'month'].map(k => fetch(lflRaw(`UZ_${k}_${L}.json`, ref)).then(r => r.ok ? r.json() : null).catch(() => null)));
  const esc = t => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const block = (t, o, n) => o ? `\n\n<b>${t}</b>\n` + o.lines.slice(0, n).map(x => '• ' + esc(x)).join('\n') : '';
  const text = w || m ? X.h + block(X.m, m, 4) + block(X.w, w, 5) + `\n\n<i>${X.note}</i>` : `${X.h}\n\n${X.none}`;
  return tg(env, 'sendMessage', { chat_id: chat, text, parse_mode: 'HTML', reply_markup: { inline_keyboard: [
    [{ text: X.open, web_app: { url: site(env, `lfl.html?lang=${L}`) } }], [{ text: X.vm, callback_data: `DV:${L}:month` }], [{ text: X.vw, callback_data: `DV:${L}:weeks` }], [{ text: X.pdf, callback_data: `DV:${L}:pdf` }], [{ text: X.xl, callback_data: `DV:${L}:xlsx` }]] } });
}
async function sendDynXlsx(env, chat, lang, ext = 'xlsx') {  // the Excel or PDF report (made with the videos, 3 times a day)
  const L = lang === 'uz' ? 'uz' : 'ru', X = DYN[L], ref = await lflRef(env);
  const f = await fetch(lflRaw(`UZ_lfl_${L}.${ext}`, ref)).then(r => r.ok ? r.arrayBuffer() : null).catch(() => null);
  if (!f) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_document' });
  const fd = new FormData(); fd.append('chat_id', String(chat)); fd.append('caption', ext === 'pdf' ? X.pdfc : X.xlc);
  fd.append('document', new Blob([f], { type: ext === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }), `${L === 'uz' ? 'ob-havo_otgan_yil' : 'pogoda_vs_proshlyi_god'}_${todayTZ()}.${ext}`);
  return fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendDocument`, { method: 'POST', body: fd }).then(r => r.json()).catch(() => null);
}
async function sendDynVideo(env, chat, lang, kind) {
  const L = lang === 'uz' ? 'uz' : 'ru', X = DYN[L], ref = await lflRef(env);
  const [v, j] = await Promise.all([fetch(lflRaw(`UZ_${kind}_${L}.mp4`, ref)).then(r => r.ok ? r.arrayBuffer() : null).catch(() => null), fetch(lflRaw(`UZ_${kind}_${L}.json`, ref)).then(r => r.ok ? r.json() : null).catch(() => null)]);
  if (!v) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
  const fd = new FormData(); fd.append('chat_id', String(chat)); fd.append('supports_streaming', 'true');
  fd.append('caption', `📊 ${j ? j.title : ''} · ${j ? j.name : ''}`.slice(0, 1000));
  fd.append('reply_markup', JSON.stringify({ inline_keyboard: [[{ text: X.open, web_app: { url: site(env, `lfl.html?lang=${L}`) } }], [{ text: kind === 'month' ? X.vw : X.vm, callback_data: `DV:${L}:${kind === 'month' ? 'weeks' : 'month'}` }]] }));
  fd.append('video', new Blob([v], { type: 'video/mp4' }), `UZ_${kind}.mp4`);
  return fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendVideo`, { method: 'POST', body: fd }).then(r => r.json()).catch(() => null);
}
const MOREM = { ru: '⚙️ <b>Ещё</b>', uz: '⚙️ <b>Yana</b>', en: '⚙️ <b>More</b>' };
function moreMenu(env, chat, lang, rid) {
  const R = RKL[lang] || RKL.ru, a = k => ({ text: R[k], callback_data: `MA:${lang}:${k}` });
  return tg(env, 'sendMessage', { chat_id: chat, text: MOREM[lang] || MOREM.ru, parse_mode: 'HTML', reply_markup: { inline_keyboard: [
    [a('air'), a('alerts')], ...(rid === 'UZ' ? [[a('mtn'), a('dyn')]] : []), [a('notif'), a('daily')], [a('brief'), a('cities')], [a('accuracy')], [{ text: lang === 'uz' ? '📊 Ob-havo o‘tgan yilga nisbatan' : '📊 Погода против прошлого года', web_app: { url: site(env, `lfl.html?lang=${lang}`) } }], [{ text: R.site, web_app: { url: site(env, `prob/${rid}/${lang}/prob`) } }],
    ...(TRJ.has(rid) ? [] : []), [a('help'), a('reset')]] } });
}
const rkAct = text => { for (const L of [...Object.values(RKS), ...Object.values(RKL), ...Object.values(RKL_OLD)]) for (const [k, v] of Object.entries(L)) if (v === text) return k; return null; };
const RKS = {  // the main keyboard: six big buttons by meaning; each opens a small menu
  ru: { fc: '🌤 Прогноз', video: '🎬 Видео', regions: '🗺 Регионы', countries: '🌍 Страны', mtnair: '🏔 Горы · воздух', air: '🌫 Воздух', loc: '📍 Моё место', settings: '⚙️ Настройки' },
  uz: { fc: '🌤 Prognoz', video: '🎬 Video', regions: '🗺 Viloyatlar', countries: '🌍 Davlatlar', mtnair: '🏔 Tog‘lar · havo', air: '🌫 Havo sifati', loc: '📍 Mening joyim', settings: '⚙️ Sozlamalar' },
  en: { fc: '🌤 Forecast', video: '🎬 Video', regions: '🗺 Regions', countries: '🌍 Countries', mtnair: '🏔 Mountains · air', air: '🌫 Air quality', loc: '📍 My place', settings: '⚙️ Settings' } };
function replyKb(env, lang, id) {
  const X = RKS[lang] || RKS.ru, b = t => ({ text: t });
  return { keyboard: [
    [b(X.fc), b(X.video)],
    [b(ADM.has(id) ? X.regions : X.countries), b(id === 'UZ' ? X.mtnair : X.air)],
    [{ text: X.loc, request_location: true }, b(X.settings)]], resize_keyboard: true, is_persistent: true, input_field_placeholder: { uz: 'Shahar nomi…', ru: 'Название города…', en: 'City name…' }[lang] };
}
const SUBM = {  // the small menus behind the big buttons
  ru: { fc: '🌤 <b>Прогноз</b> — что показать?', mtnair: '🏔 <b>Горы и воздух</b>', settings: '⚙️ <b>Настройки</b>', week: '📆 Неделя по дням', photo: '🖼 График на 15 дней (фото)', country: '🌍 Страна и континент', remind: '⏰ Присылать прогноз на 15 дней каждый день' },
  uz: { fc: '🌤 <b>Prognoz</b> — nimani ko‘rsatay?', mtnair: '🏔 <b>Tog‘lar va havo</b>', settings: '⚙️ <b>Sozlamalar</b>', week: '📆 Hafta kunma-kun', photo: '🖼 15 kunlik grafik (rasm)', country: '🌍 Davlat va qit’a', remind: '⏰ 15 kunlik prognozni har kuni yuborish' },
  en: { fc: '🌤 <b>Forecast</b> — what shall I show?', mtnair: '🏔 <b>Mountains and air</b>', settings: '⚙️ <b>Settings</b>', week: '📆 A week day by day', photo: '🖼 15-day chart (picture)', country: '🌍 Country and continent', remind: '⏰ Send the 15-day forecast every day' } };
async function subMenu(env, chat, lang, rid, which, u) {
  const R = RKL[lang] || RKL.ru, M = SUBM[lang] || SUBM.ru, a = k => ({ text: R[k], callback_data: `MA:${lang}:${k}` });
  const CAP = { UZ: [41.311, 69.279], KZ: [51.169, 71.449], KG: [42.875, 74.612], TJ: [38.56, 68.774], TM: [37.96, 58.326], AZ: [40.41, 49.867], AM: [40.177, 44.513], BY: [53.9, 27.567], MD: [47.011, 28.863], RU: [55.756, 37.617], TR: [39.92, 32.854] };
  const pl = u && u.place ? JSON.parse(u.place) : CAP[rid] || CAP.UZ;
  let rows;
  if (which === 'fc') rows = [[a('now'), a('days')], [{ text: M.week, callback_data: `MA:${lang}:wkpick` }, phBtn(lang, +pl[0], +pl[1])], [a('alerts'), ...(rid === 'UZ' ? [a('outlook')] : [])],
    [{ text: M.remind, callback_data: `NS:${lang}:days` }]];
  else if (which === 'mtnair') rows = [[a('mtn'), a('air')], [a('alerts')]];
  else rows = [[{ text: M.country, callback_data: `MA:${lang}:countries` }, a('cities')], [a('daily'), a('notif')], ...(rid === 'UZ' ? [[a('dyn'), a('accuracy')]] : [[a('accuracy')]]), [a('help'), a('reset')]];
  rows[1] && which === 'fc' && (rows[1][1] = { ...rows[1][1], text: M.photo });
  return tg(env, 'sendMessage', { chat_id: chat, text: M[which], parse_mode: 'HTML', reply_markup: { inline_keyboard: rows } });
}
// countries and cities are keyboards too: the chosen one is marked with ✅
function countryRk(lang, cur) {  // the continents first (then the countries, the towns, the regions and districts), the current country as a shortcut
  const X = RKL[lang] || RKL.ru, C = CONT[lang] || CONT.ru;
  const rows = [[{ text: C.AS }, { text: C.EU }], [{ text: C.AF }, { text: C.AU }], [{ text: C.NA }, { text: C.SA }], [{ text: C.AN }]];
  if (cur && NAMES[cur] && FLAG[cur]) rows.unshift([{ text: `✅ ${FLAG[cur]} ${NAMES[cur][lang]}` }]);
  rows.push([{ text: X.home }]);
  return { keyboard: rows, resize_keyboard: true };
}
/* ---------- continents → countries → towns, regions and districts ---------- */
const WORLD = [["ID","Индонезия","Indonesia","Endonezya","AS"],["MY","Малайзия","Malaysia","Malezya","AS"],["CL","Чили","Chile","Şili","SA"],["BO","Боливия","Bolivia","Bolivya","SA"],["PE","Перу","Peru","Peru","SA"],["AR","Аргентина","Argentina","Arjantin","SA"],["CY","Кипр","Cyprus","Kıbrıs Cumhuriyeti","AS"],["IN","Индия","India","Hindistan","AS"],["CN","Китайская Народная Республика","People's Republic of China","Çin Halk Cumhuriyeti","AS"],["IL","Израиль","Israel","İsrail","AS"],["PS","Палестина","Palestine","Filistin","AS"],["LB","Ливан","Lebanon","Lübnan","AS"],["ET","Эфиопия","Ethiopia","Etiyopya","AF"],["SS","Южный Судан","South Sudan","Güney Sudan","AF"],["SO","Сомали","Somalia","Somali","AF"],["KE","Кения","Kenya","Kenya","AF"],["MW","Малави","Malawi","Malavi","AF"],["TZ","Танзания","Tanzania","Tanzanya","AF"],["SY","Сирия","Syria","Suriye","AS"],["FR","Франция","France","Fransa","EU"],["SR","Суринам","Suriname","Surinam","SA"],["GY","Гайана","Guyana","Guyana","SA"],["KR","Республика Корея","South Korea","Güney Kore","AS"],["KP","КНДР","North Korea","Kuzey Kore","AS"],["MA","Марокко","Morocco","Fas","AF"],["EH","Западная Сахара","Western Sahara","Batı Sahra","AF"],["CR","Коста-Рика","Costa Rica","Kosta Rika","NA"],["NI","Никарагуа","Nicaragua","Nikaragua","NA"],["CG","Республика Конго","Republic of the Congo","Kongo Cumhuriyeti","AF"],["CD","Демократическая Республика Конго","Democratic Republic of the Congo","Demokratik Kongo Cumhuriyeti","AF"],["BT","Бутан","Bhutan","Bhutan","AS"],["UA","Украина","Ukraine","Ukrayna","EU"],["BY","Белоруссия","Belarus","Beyaz Rusya","EU"],["NA","Намибия","Namibia","Namibya","AF"],["ZA","ЮАР","South Africa","Güney Afrika Cumhuriyeti","AF"],["MF","Сен-Мартен","Saint Martin","Saint Martin","NA"],["SX","Синт-Мартен","Sint Maarten","Sint Maarten","NA"],["OM","Оман","Oman","Umman","AS"],["UZ","Узбекистан","Uzbekistan","Özbekistan","AS"],["KZ","Казахстан","Kazakhstan","Kazakistan","AS"],["TJ","Таджикистан","Tajikistan","Tacikistan","AS"],["LT","Литва","Lithuania","Litvanya","EU"],["BR","Бразилия","Brazil","Brezilya","SA"],["UY","Уругвай","Uruguay","Uruguay","SA"],["MN","Монголия","Mongolia","Moğolistan","AS"],["RU","Россия","Russia","Rusya","EU"],["CZ","Чехия","Czech Republic","Çek Cumhuriyeti","EU"],["DE","Германия","Germany","Almanya","EU"],["EE","Эстония","Estonia","Estonya","EU"],["LV","Латвия","Latvia","Letonya","EU"],["NO","Норвегия","Norway","Norveç","EU"],["SE","Швеция","Sweden","İsveç","EU"],["FI","Финляндия","Finland","Finlandiya","EU"],["VN","Вьетнам","Vietnam","Vietnam","AS"],["KH","Камбоджа","Cambodia","Kamboçya","AS"],["LU","Люксембург","Luxembourg","Lüksemburg","EU"],["AE","Объединённые Арабские Эмираты","United Arab Emirates","Birleşik Arap Emirlikleri","AS"],["BE","Бельгия","Belgium","Belçika","EU"],["GE","Грузия","Georgia","Gürcistan","AS"],["MK","Северная Македония","North Macedonia","Kuzey Makedonya","EU"],["AL","Албания","Albania","Arnavutluk","EU"],["AZ","Азербайджан","Azerbaijan","Azerbaycan","AS"],["XK","Республика Косово","Kosovo","Kosova","EU"],["TR","Турция","Turkey","Türkiye","AS"],["ES","Испания","Spain","İspanya","EU"],["LA","Лаос","Laos","Laos","AS"],["KG","Киргизия","Kyrgyzstan","Kırgızistan","AS"],["AM","Армения","Armenia","Ermenistan","AS"],["DK","Дания","Denmark","Danimarka","EU"],["LY","Ливия","Libya","Libya","AF"],["TN","Тунис","Tunisia","Tunus","AF"],["RO","Румыния","Romania","Romanya","EU"],["HU","Венгрия","Hungary","Macaristan","EU"],["SK","Словакия","Slovakia","Slovakya","EU"],["PL","Польша","Poland","Polonya","EU"],["IE","Ирландия","Ireland","İrlanda","EU"],["GB","Великобритания","United Kingdom","Birleşik Krallık","EU"],["GR","Греция","Greece","Yunanistan","EU"],["ZM","Замбия","Zambia","Zambiya","AF"],["SL","Сьерра-Леоне","Sierra Leone","Sierra Leone","AF"],["GN","Гвинея","Guinea","Gine","AF"],["LR","Либерия","Liberia","Liberya","AF"],["CF","Центральноафриканская Республика","Central African Republic","Orta Afrika Cumhuriyeti","AF"],["SD","Судан","Sudan","Sudan","AF"],["DJ","Джибути","Djibouti","Cibuti","AF"],["ER","Эритрея","Eritrea","Eritre","AF"],["AT","Австрия","Austria","Avusturya","EU"],["IQ","Ирак","Iraq","Irak","AS"],["IT","Италия","Italy","İtalya","EU"],["CH","Швейцария","Switzerland","İsviçre","EU"],["IR","Иран","Iran","İran","AS"],["NL","Нидерланды","Netherlands","Hollanda","EU"],["LI","Лихтенштейн","Liechtenstein","Lihtenştayn","EU"],["CI","Кот-д’Ивуар","Ivory Coast","Fildişi Sahili","AF"],["RS","Сербия","Serbia","Sırbistan","EU"],["ML","Мали","Mali","Mali","AF"],["SN","Сенегал","Senegal","Senegal","AF"],["NG","Нигерия","Nigeria","Nijerya","AF"],["BJ","Бенин","Benin","Benin","AF"],["AO","Ангола","Angola","Angola","AF"],["HR","Хорватия","Croatia","Hırvatistan","EU"],["SI","Словения","Slovenia","Slovenya","EU"],["QA","Катар","Qatar","Katar","AS"],["SA","Саудовская Аравия","Saudi Arabia","Suudi Arabistan","AS"],["BW","Ботсвана","Botswana","Botsvana","AF"],["ZW","Зимбабве","Zimbabwe","Zimbabve","AF"],["PK","Пакистан","Pakistan","Pakistan","AS"],["BG","Болгария","Bulgaria","Bulgaristan","EU"],["TH","Таиланд","Thailand","Tayland","AS"],["SM","Сан-Марино","San Marino","San Marino","EU"],["HT","Республика Гаити","Haiti","Haiti","NA"],["DO","Доминиканская Республика","Dominican Republic","Dominik Cumhuriyeti","NA"],["TD","Чад","Chad","Çad","AF"],["KW","Кувейт","Kuwait","Kuveyt","AS"],["SV","Сальвадор","El Salvador","El Salvador","NA"],["GT","Гватемала","Guatemala","Guatemala","NA"],["TL","Восточный Тимор","East Timor","Doğu Timor","AS"],["BN","Бруней","Brunei","Brunei","AS"],["MC","Монако","Monaco","Monako","EU"],["DZ","Алжир","Algeria","Cezayir","AF"],["MZ","Мозамбик","Mozambique","Mozambik","AF"],["SZ","Эсватини","Eswatini","Esvatini","AF"],["BI","Бурунди","Burundi","Burundi","AF"],["RW","Руанда","Rwanda","Ruanda","AF"],["MM","Мьянма","Myanmar","Myanmar","AS"],["BD","Бангладеш","Bangladesh","Bangladeş","AS"],["AD","Андорра","Andorra","Andorra","EU"],["AF","Афганистан","Afghanistan","Afganistan","AS"],["ME","Черногория","Montenegro","Karadağ","EU"],["BA","Босния и Герцеговина","Bosnia and Herzegovina","Bosna-Hersek","EU"],["UG","Уганда","Uganda","Uganda","AF"],["CU","Куба","Cuba","Küba","NA"],["HN","Гондурас","Honduras","Honduras","NA"],["EC","Эквадор","Ecuador","Ekvador","SA"],["CO","Колумбия","Colombia","Kolombiya","SA"],["PY","Парагвай","Paraguay","Paraguay","SA"],["PT","Португалия","Portugal","Portekiz","EU"],["MD","Молдавия","Moldova","Moldova","EU"],["TM","Туркмения","Turkmenistan","Türkmenistan","AS"],["JO","Иордания","Jordan","Ürdün","AS"],["NP","Непал","Nepal","Nepal","AS"],["LS","Лесото","Lesotho","Lesotho","AF"],["CM","Камерун","Cameroon","Kamerun","AF"],["GA","Габон","Gabon","Gabon","AF"],["NE","Нигер","Niger","Nijer","AF"],["BF","Буркина-Фасо","Burkina Faso","Burkina Faso","AF"],["TG","Того","Togo","Togo","AF"],["GH","Гана","Ghana","Gana","AF"],["GW","Гвинея-Бисау","Guinea-Bissau","Gine-Bissau","AF"],["GI","Гибралтар","Gibraltar","Cebelitarık","EU"],["US","США","United States of America","Amerika Birleşik Devletleri","NA"],["CA","Канада","Canada","Kanada","NA"],["MX","Мексика","Mexico","Meksika","NA"],["BZ","Белиз","Belize","Belize","NA"],["PA","Панама","Panama","Panama","NA"],["VE","Венесуэла","Venezuela","Venezuela","SA"],["PG","Папуа — Новая Гвинея","Papua New Guinea","Papua Yeni Gine","AU"],["EG","Египет","Egypt","Mısır","AF"],["YE","Йемен","Yemen","Yemen","AS"],["MR","Мавритания","Mauritania","Moritanya","AF"],["GQ","Экваториальная Гвинея","Equatorial Guinea","Ekvator Ginesi","AF"],["GM","Гамбия","The Gambia","Gambiya","AF"],["HK","Гонконг","Hong Kong","Hong Kong","AS"],["VA","Ватикан","Vatican City","Vatikan","EU"],["AQ","Антарктида","Antarctica","Antarktika","AN"],["AU","Австралия","Australia","Avustralya","AU"],["GL","Гренландия","Greenland","Grönland","NA"],["FJ","Фиджи","Fiji","Fiji","AU"],["NZ","Новая Зеландия","New Zealand","Yeni Zelanda","AU"],["NC","Новая Каледония","New Caledonia","Yeni Kaledonya","AU"],["MG","Мадагаскар","Madagascar","Madagaskar","AF"],["PH","Филиппины","Philippines","Filipinler","AS"],["LK","Шри-Ланка","Sri Lanka","Sri Lanka","AS"],["CW","Кюрасао","Curaçao","Curaçao","NA"],["AW","Аруба","Aruba","Aruba","NA"],["BS","Багамские Острова","The Bahamas","Bahamalar","NA"],["TC","Тёркс и Кайкос","Turks and Caicos Islands","Turks ve Caicos Adaları","NA"],["TW","Тайвань","Taiwan","Çin Cumhuriyeti","AS"],["JP","Япония","Japan","Japonya","AS"],["PM","Сен-Пьер и Микелон","Saint Pierre and Miquelon","Saint Pierre ve Miquelon","NA"],["IS","Исландия","Iceland","İzlanda","EU"],["PN","Острова Питкэрн","Pitcairn Islands","Pitcairn Adaları","AU"],["PF","Французская Полинезия","French Polynesia","Fransız Polinezyası","AU"],["KI","Кирибати","Kiribati","Kiribati","AU"],["MH","Маршалловы Острова","Marshall Islands","Marshall Adaları","AU"],["TT","Тринидад и Тобаго","Trinidad and Tobago","Trinidad ve Tobago","NA"],["GD","Гренада","Grenada","Grenada","NA"],["VC","Сент-Винсент и Гренадины","Saint Vincent and the Grenadines","Saint Vincent ve Grenadinler","NA"],["BB","Барбадос","Barbados","Barbados","NA"],["LC","Сент-Люсия","Saint Lucia","Saint Lucia","NA"],["DM","Доминика","Dominica","Dominika","NA"],["UM","Внешние малые острова США","United States Minor Outlying Islands","United States Minor Outlying Islands","NA"],["MS","Монтсеррат","Montserrat","Montserrat","NA"],["AG","Антигуа и Барбуда","Antigua and Barbuda","Antigua ve Barbuda","NA"],["KN","Сент-Китс и Невис","Saint Kitts and Nevis","Saint Kitts ve Nevis","NA"],["VI","Американские Виргинские острова","United States Virgin Islands","ABD Virjin Adaları","NA"],["BL","Сен-Бартелеми","Saint Barthélemy","Saint Barthélemy","NA"],["PR","Пуэрто-Рико","Puerto Rico","Porto Riko","NA"],["AI","Ангилья","Anguilla","Anguilla","NA"],["VG","Британские Виргинские острова","British Virgin Islands","Britanya Virjin Adaları","NA"],["JM","Ямайка","Jamaica","Jamaika","NA"],["KY","острова Кайман","Cayman Islands","Cayman Adaları","NA"],["BM","Бермудские Острова","Bermuda","Bermuda","NA"],["KM","Коморы","Comoros","Komorlar","AF"],["ST","Сан-Томе и Принсипи","São Tomé and Príncipe","São Tomé ve Príncipe","AF"],["CV","Кабо-Верде","Cape Verde","Yeşil Burun Adaları","AF"],["MT","Мальта","Malta","Malta","EU"],["JE","Джерси","Jersey","Jersey","EU"],["GG","Гернси","Guernsey","Guernsey","EU"],["IM","остров Мэн","Isle of Man","Man Adası","EU"],["AX","Аландские острова","Åland","Åland","EU"],["FO","Фарерские острова","Faroe Islands","Faroe Adaları","EU"],["SG","Сингапур","Singapore","Singapur","AS"],["NF","Норфолк","Norfolk Island","Norfolk Adası","AU"],["CK","Острова Кука","Cook Islands","Cook Adaları","AU"],["TO","Тонга","Tonga","Tonga","AU"],["WF","Уоллис и Футуна","Wallis and Futuna","Wallis ve Futuna Adaları","AU"],["WS","Самоа","Samoa","Samoa","AU"],["SB","Соломоновы Острова","Solomon Islands","Solomon Adaları","AU"],["TV","Тувалу","Tuvalu","Tuvalu","AU"],["NR","Науру","Nauru","Nauru","AU"],["FM","Микронезия","Federated States of Micronesia","Mikronezya","AU"],["FK","Фолклендские острова","Falkland Islands","Falkland Adaları","SA"],["VU","Вануату","Vanuatu","Vanuatu","AU"],["NU","Ниуэ","Niue","Niue","AU"],["AS","Американское Самоа","American Samoa","Amerikan Samoası","AU"],["PW","Палау","Palau","Palau","AU"],["GU","Гуам","Guam","Guam","AU"],["MP","Северные Марианские острова","Northern Mariana Islands","Kuzey Mariana Adaları","AU"],["BH","Бахрейн","Bahrain","Bahreyn","AS"],["MO","Макао","Macau","Makao","AS"]];  // [ISO, ru, en, tr, continent]: Natural Earth countries
const CONT = {
  ru: { AU: '🦘 Австралия', AN: '🧊 Антарктида', AF: '🌍 Африка', AS: '🌏 Азия', EU: '🌍 Европа', NA: '🌎 Северная Америка', SA: '🌎 Южная Америка', pick: '{c} — выберите страну:', whole: '🗺 Весь регион: {n}', towns: '🏙 Города — нажмите, пришлю прогноз:', regs: '🗺 Регионы и районы', noTowns: 'Городов в списке нет — напишите название места или отправьте геолокацию 📍.', back: '⬅️ Континенты', more: 'Ещё ▶', prev: '◀ Назад', menu: '📋 Все разделы страны', page: 'стр. {i}/{n}' },
  uz: { AU: '🦘 Avstraliya', AN: '🧊 Antarktida', AF: '🌍 Afrika', AS: '🌏 Osiyo', EU: '🌍 Yevropa', NA: '🌎 Shimoliy Amerika', SA: '🌎 Janubiy Amerika', pick: '{c} — davlatni tanlang:', whole: '🗺 Butun hudud: {n}', towns: '🏙 Shaharlar — bosing, prognoz yuboraman:', regs: '🗺 Viloyat va tumanlar', noTowns: 'Ro‘yxatda shahar yo‘q — joy nomini yozing yoki joylashuvni yuboring 📍.', back: '⬅️ Qit’alar', more: 'Yana ▶', prev: '◀ Orqaga', menu: '📋 Davlatning barcha bo‘limlari', page: '{i}/{n}-bet' },
  en: { AU: '🦘 Australia', AN: '🧊 Antarctica', AF: '🌍 Africa', AS: '🌏 Asia', EU: '🌍 Europe', NA: '🌎 North America', SA: '🌎 South America', pick: '{c} — choose a country:', whole: '🗺 The whole region: {n}', towns: '🏙 Cities — tap one, I will send the forecast:', regs: '🗺 Regions and districts', noTowns: 'No cities on the list — type the name of a place or send your location 📍.', back: '⬅️ Continents', more: 'More ▶', prev: '◀ Back', menu: '📋 All sections of the country', page: 'page {i}/{n}' } };
const CONT_REG = { AU: ['OC'], AN: [], AF: ['AF'], AS: ['AS', 'cis'], EU: ['EU'], NA: ['NA'], SA: ['SA'] };  // the bot's own maps of a continent
const flagOf = iso => /^[A-Z]{2}$/.test(iso) ? String.fromCodePoint(...[...iso].map(c => 127397 + c.charCodeAt(0))) : '🏳';
const wname = (r, lang) => lang === 'ru' ? r[1] : r[2];
const contOf = (text, lang) => { const t = text.trim(); for (const l of [lang, 'ru', 'uz', 'en']) for (const [k, v] of Object.entries(CONT[l])) if (['AU', 'AN', 'AF', 'AS', 'EU', 'NA', 'SA'].includes(k) && v === t) return k; return null; };
async function sendCountries(env, chat, lang, code, page = 0, edit) {
  const C = CONT[lang] || CONT.ru, PER = 30;
  const list = WORLD.filter(r => r[4] === code).sort((a, b) => wname(a, lang).localeCompare(wname(b, lang), lang));
  const pages = Math.max(1, Math.ceil(list.length / PER)), part = list.slice(page * PER, page * PER + PER), rows = [];
  for (const id of CONT_REG[code] || []) if (NAMES[id]) rows.push([{ text: C.whole.replace('{n}', NAMES[id][lang]), callback_data: `CR:${lang}:${id}`, style: 'primary' }]);
  part.forEach((r, i) => { if (i % 3 === 0) rows.push([]); rows[rows.length - 1].push({ text: `${flagOf(r[0])} ${wname(r, lang)}`.slice(0, 40), callback_data: `CY:${lang}:${r[0]}` }); });
  if (pages > 1) rows.push([...(page > 0 ? [{ text: C.prev, callback_data: `CT:${lang}:${code}:${page - 1}` }] : []), { text: C.page.replace('{i}', page + 1).replace('{n}', pages), callback_data: `CT:${lang}:${code}:${page}` }, ...(page < pages - 1 ? [{ text: C.more, callback_data: `CT:${lang}:${code}:${page + 1}` }] : [])]);
  const text = C.pick.replace('{c}', `<b>${C[code]}</b>`);
  if (edit) return tg(env, 'editMessageText', { chat_id: chat, message_id: edit, text, parse_mode: 'HTML', reply_markup: { inline_keyboard: rows } });
  return tg(env, 'sendMessage', { chat_id: chat, text, parse_mode: 'HTML', reply_markup: { inline_keyboard: rows } });
}
async function sendCountry(env, chat, lang, iso) {
  const C = CONT[lang] || CONT.ru, r = WORLD.find(x => x[0] === iso); if (!r) return;
  const towns = (await places(env)).filter(p => p[4] === iso).sort((a, b) => (b[8] || 0) - (a[8] || 0) || b[7] - a[7]).slice(0, 24), rows = [];
  if (NAMES[iso]) {  // a country with the bot's own maps: remember it, its menu comes on the keyboard
    await saveUser(env, chat, { lang, region: iso });
    rows.push([{ text: C.menu, callback_data: `CR:${lang}:${iso}`, style: 'primary' }]);
  }
  if (ADM.has(iso)) rows.push([{ text: C.regs, callback_data: `RG:${lang}:${iso}`, style: 'success' }]);
  if (towns[0]) rows.push([{ ...phBtn(lang, +towns[0][5], +towns[0][6]), text: `${(PHX[lang] || PHX.ru).btn}: ${pname(towns[0], lang)}` }]);  // the biggest town's 15 days as a chart
  towns.forEach((p, i) => { if (i % 3 === 0) rows.push([]); rows[rows.length - 1].push({ text: pname(p, lang).slice(0, 30), callback_data: `Q:${lang}:${(+p[5]).toFixed(3)}:${(+p[6]).toFixed(3)}` }); });
  rows.push([{ text: C.back, callback_data: `CT:${lang}:${r[4]}:0` }]);
  return tg(env, 'sendMessage', { chat_id: chat, text: `${flagOf(iso)} <b>${esc(wname(r, lang))}</b>\n${towns.length ? C.towns : C.noTowns}`, parse_mode: 'HTML', reply_markup: { inline_keyboard: rows } });
}
const countryOf = text => { const t = text.replace(/^✅ /, ''); for (const id of Object.keys(NAMES)) for (const l of ['uz', 'ru', 'en']) if (t === `${FLAG[id]} ${NAMES[id][l]}`) return id; return null; };
async function cityPicker(env, chat, lang, id, u) {
  const X = RKL[lang] || RKL.ru, C = (await cities(env, id, lang)) || (await cities(env, id, 'ru'));
  const rows = [[{ text: X.loc, request_location: true }]];
  const names = (C ? C.cities.map(c => c.name) : []).slice(0, 30);
  for (const p of await places(env)) {  // more towns of the country, by population, up to 30 buttons
    if (names.length >= 30) break;
    const n = pname(p, lang); if (p[4] === id && n && !names.some(x => norm(x) === norm(n))) names.push(n);
  }
  names.forEach((n, i) => { if (i % 3 === 0) rows.push([]); rows[rows.length - 1].push({ text: n }); });
  rows.push([{ text: X.countries }, { text: X.home }]);
  return tg(env, 'sendMessage', { chat_id: chat, text: `${FLAG[id]} <b>${NAMES[id][lang]}</b> · ${DK[lang].ask}`, parse_mode: 'HTML', reply_markup: { keyboard: rows, resize_keyboard: true, input_field_placeholder: { uz: 'Shahar nomi…', ru: 'Название города…', en: 'City name…' }[lang] } });
}
function menuKb(env, lang, id) { return replyKb(env, lang, id); }
function menuKbInline(env, lang, id) {
  return { inline_keyboard: [
    // coloured buttons (Telegram 2026+): blue = main actions, green = forecast texts, the rest plain
    [{ text: T[lang].today, callback_data: `T:${lang}:${id}`, style: 'primary' }],
    [{ text: T[lang].days, callback_data: `D:${lang}:${id}`, style: 'success' }, { text: T[lang].all, callback_data: `V:${lang}:${id}`, style: 'primary' }],
    ...(id === 'UZ' ? [[{ text: OLK[lang], callback_data: `O:${lang}:${id}`, style: 'success' }]] : []),
    [{ text: T[lang].cities, callback_data: `Y:${lang}:${id}` }, { text: T[lang].sub, callback_data: `B:${lang}:${id}` }],
    [{ text: T[lang].site, web_app: { url: site(env, `prob/${id}/${lang}/prob`) } }, { text: T[lang].back, callback_data: `L:${lang}` }],
    [{ text: (HK[lang] || HK.ru).reset, callback_data: `RS:${lang}` }],
  ] };
}
const HK = {
  uz: { home: '🏠 Bosh menyu', reset: '🔄 Qayta boshlash', ask: 'Sozlamalarni o‘chirib, boshidan boshlaymizmi?\nDavlat, saqlangan joy va kunlik prognoz obunasi o‘chiriladi.', yes: '✅ Ha, qayta boshlash', no: '❌ Yo‘q', done: '🔄 Sozlamalar tozalandi. Tilni tanlang:' },
  ru: { home: '🏠 Главная', reset: '🔄 Сбросить', ask: 'Сбросить настройки и начать заново?\nБудут удалены: выбранная страна, сохранённое место и подписка на ежедневный прогноз.', yes: '✅ Да, сбросить', no: '❌ Нет', done: '🔄 Настройки сброшены. Выберите язык:' },
  en: { home: '🏠 Main menu', reset: '🔄 Reset', ask: 'Reset the settings and start over?\nThe chosen country, the saved location and the daily forecast subscription will be deleted.', yes: '✅ Yes, reset', no: '❌ No', done: '🔄 The settings are reset. Choose a language:' } };
const homeRow = lang => [{ text: (HK[lang] || HK.ru).home, callback_data: `HM:${lang}` }, { text: (HK[lang] || HK.ru).reset, callback_data: `RS:${lang}` }];
const DK = {
  uz: { ask: '15 kunlik prognoz: shaharni tanlang yoki dunyodagi istalgan shahar nomini yozing (masalan: Parij, Dubay)', mine: 'Mening joyim', loc: '📍 Joylashuvni yuborish', other: '🌍 Boshqa davlat', vid: '🎬 Shu shahar videosi', vidC: '🎬 Video 15 kun', more: '🏙 Boshqa shahar', globe: '🌍 Globusda ochish' },
  ru: { ask: 'Прогноз на 15 дней: выберите город или напишите название любого города мира (например: Париж, Дубай)', mine: 'Моё место', loc: '📍 Отправить геолокацию', other: '🌍 Другая страна', vid: '🎬 Видео этого города', vidC: '🎬 Видео на 15 дней', more: '🏙 Другой город', globe: '🌍 Открыть на глобусе' },
  en: { ask: '15-day forecast: choose a city or type the name of any city in the world (e.g. Paris, Dubai)', mine: 'My location', loc: '📍 Send location', other: '🌍 Another country', vid: '🎬 This city’s video', vidC: '🎬 15-day video', more: '🏙 Another city', globe: '🌍 Open on the globe' } };
// under a 15-day text: the matching video (this city's own, or the country's), another city, the countries
function dayKb(lang, rid, cityVideo) {
  const X = DK[lang] || DK.ru;
  return { inline_keyboard: [
    [cityVideo ? { text: X.vid, callback_data: cityVideo, style: 'primary' } : { text: X.vidC, callback_data: `V:${lang}:${rid}`, style: 'primary' }],
    [{ text: X.more, callback_data: `D:${lang}:${rid}` }, { text: X.other, callback_data: `L:${lang}` }], homeRow(lang)] };
}
const helpKb = lang => ({ inline_keyboard: [[{ text: T[lang].pdf, callback_data: `P:${lang}` }, { text: T[lang].adm, callback_data: `M:${lang}` }]] });
// groups and channels cannot open Mini Apps from buttons: plain links
const LIVE = { ru: '🗺 Интерактивная карта по часам', uz: '🗺 Interaktiv xarita soatma-soat', en: '🗺 Interactive map by the hour' };
// the interactive map: inside Telegram in a private chat (mini app), a plain link in groups (Telegram allows mini-app buttons only in private chats)
const LIVE15 = { ru: '🗺 Интерактивная карта на 15 дней', uz: '🗺 15 kunlik interaktiv xarita', en: '🗺 Interactive 15-day map' };
const liveBtn = (env, lang, id, chat, d15) => { const u = `${base(env)}/live.html?r=${id}&l=${lang}${d15 ? '&m=15' : ''}`;
  return { text: (d15 ? LIVE15 : LIVE)[lang] || (d15 ? LIVE15 : LIVE).ru, ...(chat > 0 ? { web_app: { url: u } } : { url: u }) }; };
// the interactive «where the rain comes from» map and the satellite now (site/moist.html; Uzbekistan, Kazakhstan, Kyrgyzstan)
const MBTN = { ru: ['🗺 Интерактивная карта осадков', '🛰 Онлайн: тучи со спутника'], uz: ['🗺 Interaktiv yog‘in xaritasi', '🛰 Onlayn: sun’iy yo‘ldoshdan bulutlar'], en: ['🗺 Interactive precipitation map', '🛰 Live: clouds from the satellite'] };
const moistBtns = (env, lang, id, chat) => !TRJ.has(id) ? [] : [0, 1].map(k => { const u = `${base(env)}/moist.html?r=${id}&l=${lang === 'uz' ? 'uz' : 'ru'}${k ? '&m=sat' : ''}`;
  return [{ text: (MBTN[lang] || MBTN.ru)[k], ...(chat > 0 ? { web_app: { url: u } } : { url: u }) }]; });
const postKb = (env, lang, id, bot, chat) => ({ inline_keyboard: [...(chat ? [[liveBtn(env, lang, id, chat)], [liveBtn(env, lang, id, chat, true)]] : []), [{ text: T[lang].rep, url: link(env, `prob/${id}/${lang}/prob`) }, { text: T[lang].site, url: link(env, 'map') }], ...(bot ? [[{ text: T[lang].bot, url: `https://t.me/${bot}` }]] : [])] });

/* ---------- forecast text ---------- */
function icon(txt) {
  const p = +((txt.match(/(\d+)\s*%/) || [])[1] || 0), snow = /снег|\bqor\b|\bkar\b/i.test(txt);
  if (p >= 60) return snow ? '❄️' : '🌧';
  if (p >= 35) return snow ? '🌨' : '🌦';
  if (/ясно|ochiq havo|açık\./i.test(txt)) return '☀️';
  if (/пасмурно|qalin bulutli|kapalı/i.test(txt)) return '☁️';
  if (/переменная|qisman|parçalı/i.test(txt)) return '⛅';
  if (/облачно|bulutl/i.test(txt)) return '🌥';
  return '⛅';
}
/* ---------- warnings about heavy rain and snow (site/prob/alerts.json, written by prob/render.py) ---------- */
const AX = {  // more kinds of warnings
  uz: { heat: 'kuchli issiq, kunduzi', frost: 'kuchli sovuq, tunda', ice: 'yaxmalak xavfi (muzlagan yo‘llar)', wind: 'kuchli shamol, o‘rtacha', storm: 'momaqaldiroq, jala', dust: 'chang bo‘roni / havo ifloslanishi', ms: 'm/s', title: '⚠️ <b>Ogohlantirish: xavfli ob-havo</b>' },
  ru: { heat: 'сильная жара, днём', frost: 'сильный мороз, ночью', ice: 'гололёд (обледенение дорог)', wind: 'сильный ветер, в среднем', storm: 'гроза, ливень', dust: 'пыльная буря / загрязнение воздуха', ms: 'м/с', title: '⚠️ <b>Предупреждение: опасная погода</b>' },
  en: { heat: 'great heat, by day', frost: 'hard frost, at night', ice: 'ice (frost on the roads)', wind: 'strong wind, mean', storm: 'thunderstorm with heavy rain', dust: 'dust storm / air pollution', ms: 'm/s', title: '⚠️ <b>Warning: dangerous weather</b>' },
};
const AL = {
  uz: { title: '⚠️ <b>Ogohlantirish: kuchli yog‘in</b>', r1: 'kuchli yomg‘ir', r2: 'juda kuchli yomg‘ir', s1: 'kuchli qor', s2: 'juda kuchli qor', mm: 'mm', peak: 'eng kuchli', foot: 'ECMWF, NOAA, DWD modellari ansambli bo‘yicha. Ehtiyot bo‘ling!', none: '✅ Yaqin 3 kunda kuchli yog‘in kutilmayapti.' },
  ru: { title: '⚠️ <b>Предупреждение: сильные осадки</b>', r1: 'сильный дождь', r2: 'очень сильный дождь', s1: 'сильный снег', s2: 'очень сильный снег', mm: 'мм', peak: 'пик', foot: 'По ансамблю моделей ECMWF, NOAA, DWD. Будьте осторожны!', none: '✅ В ближайшие 3 дня сильных осадков не ожидается.' },
  en: { title: '⚠️ <b>Warning: heavy precipitation</b>', r1: 'heavy rain', r2: 'very heavy rain', s1: 'heavy snow', s2: 'very heavy snow', mm: 'mm', peak: 'heaviest', foot: 'From the ECMWF, NOAA, DWD model ensemble. Take care!', none: '✅ No heavy precipitation expected in the next 3 days.' },
};
async function alertsData(env) {
  const r = await fetch(`${base(env)}/prob/alerts.json?t=${Date.now()}`, { cf: { cacheTtl: 0 } });
  return r.ok ? r.json() : null;
}
function alertText(items, lang) {
  const A = AL[lang] || AL.ru, out = [items.every(i => !i.kind || i.kind === 'rain' || i.kind === 'snow') ? A.title : (AX[lang] || AX.ru).title];
  const regs = [...new Set(items.map(i => i.region))];
  for (const rg of regs) {
    out.push('', `${FLAG[rg] || ''} <b>${esc(NAMES[rg] ? NAMES[rg][lang] : rg)}</b>`);
    for (const i of items.filter(x => x.region === rg).slice(0, 10)) {
      const k = i.kind || (i.snow ? 'snow' : 'rain'), X = AX[lang] || AX.ru, nm = `<b>${esc(i.name[lang] || i.name.ru)}</b> — ${dayLabel(i.date, lang)}`;
      if (k === 'rain' || k === 'snow') { const w = i.snow ? (i.level > 1 ? A.s2 : A.s1) : (i.level > 1 ? A.r2 : A.r1); out.push(`${i.snow ? '❄️' : i.level > 1 ? '⛈' : '🌧'} ${nm}: ${w}, ~${Math.round(i.mm)} ${A.mm} (${i.p} %), ${A.peak} ${i.peak}`); }
      else if (k === 'heat') out.push(`🔥 ${nm}: ${X.heat} ${i.t > 0 ? '+' : ''}${i.t}°`);
      else if (k === 'frost') out.push(`🥶 ${nm}: ${X.frost} ${i.t}°`);
      else if (k === 'ice') out.push(`🧊 ${nm}: ${X.ice}`);
      else if (k === 'wind') out.push(`💨 ${nm}: ${X.wind} ${i.w} ${X.ms}`);
      else if (k === 'dust') out.push(`🌫 ${nm}: ${X.dust} (PM10 ~${i.pm10} µg/m³)`);
      else if (k === 'storm') out.push(`⛈ ${nm}: ${X.storm}${i.peak ? ` (${i.peak})` : ''}, ${i.p}%`);
    }
  }
  out.push('', `<i>${A.foot}</i>`);
  return out.join('\n').slice(0, 4000);
}
// after each update: warn every group and personal subscriber about NEW heavy precipitation in their countries (07–21 h)
async function alertTick(env) {
  if (!env.DB) return; await db(env);
  const hour = new Date(Date.now() + TZ * 3600e3).getUTCHours();
  if (hour < 7 || hour > 21) return;
  const A = await alertsData(env); if (!A || !A.run) return;
  const key = i => `${i.region}|${i.en}|${i.date}|${i.kind || (i.snow ? 's' : 'r')}`;
  if ((await kv(env, 'alert_run')) !== A.run) {  // a new model run: keep only the events we have not warned about yet
    const prev = JSON.parse((await kv(env, 'alert_keys')) || '[]');
    const today = todayTZ();
    await setKv(env, 'alert_new', JSON.stringify(A.items.filter(i => i.date >= today && !prev.includes(key(i)))));
    await setKv(env, 'alert_keys', JSON.stringify([...new Set([...prev.slice(-300), ...A.items.map(key)])]));
    await setKv(env, 'alert_run', A.run);
  }
  const fresh = JSON.parse((await kv(env, 'alert_new')) || '[]');
  const due = (await env.DB.prepare("SELECT * FROM subs WHERE COALESCE(alert_run, '') <> ?1 LIMIT 8").bind(A.run).all()).results;
  const me = due.length && fresh.length ? await tg(env, 'getMe', {}) : null, bot = me && me.ok ? me.result.username : '';
  for (const s of due) {
    const regs = regionsOf(s), items = fresh.filter(i => regs.includes(i.region));
    if (items.length) {
      const r = await tg(env, 'sendMessage', { chat_id: s.chat_id, text: alertText(items, T[s.lang] ? s.lang : 'ru'), parse_mode: 'HTML', reply_markup: postKb(env, T[s.lang] ? s.lang : 'ru', items[0].region, s.type === 'private' ? '' : bot), disable_web_page_preview: true });
      if (!r.ok && /kicked|blocked|deactivated|not a member|chat not found|was deleted/i.test(r.description || '')) { await env.DB.prepare('DELETE FROM subs WHERE chat_id = ?1').bind(s.chat_id).run(); continue; }
    }
    await env.DB.prepare('UPDATE subs SET alert_run = ?2 WHERE chat_id = ?1').bind(s.chat_id, A.run).run();
  }
}
/* ---------- forecast for any point: the user's location or a searched town (site/prob/pt, prob/points.py) ---------- */
const PT = {
  uz: { locBtn: '📍 Mening joyimdagi ob-havo', locHint: '📍 Pastdagi tugmani bosing — joylashuvingiz bo‘yicha 15 kunlik prognoz.\nYoki shahar nomini yozing, masalan: <i>Namangan</i>', nf: '🔎 Bunday shahar topilmadi. Boshqacha yozib ko‘ring yoki 📍 joylashuvni yuboring.', pick: '🔎 Qaysi biri?', head: '15 kunlik prognoz', none: 'yog‘insiz', rain: 'yomg‘ir', snow: 'qor', ms: 'm/s', mm: 'mm', vid: '🎬 Davlat videosi', src: 'ECMWF, NOAA, DWD ansambli · ~50 km to‘r', far: 'Bu nuqta uchun ma’lumot yo‘q.' },
  ru: { locBtn: '📍 Погода у меня', locHint: '📍 Нажмите кнопку внизу — прогноз на 15 дней для вашего места.\nИли напишите название города, например: <i>Наманган</i>', nf: '🔎 Не нашла такой город. Попробуйте написать иначе или отправьте 📍 геолокацию.', pick: '🔎 Какой из них?', head: 'Прогноз на 15 дней', none: 'без осадков', rain: 'дождь', snow: 'снег', ms: 'м/с', mm: 'мм', vid: '🎬 Видео страны', src: 'Ансамбль ECMWF, NOAA, DWD · сетка ~50 км', far: 'Для этой точки нет данных.' },
  en: { locBtn: '📍 Weather where I am', locHint: '📍 Press the button below — the 15-day forecast for your location.\nOr type a city name, e.g.: <i>London</i>', nf: '🔎 City not found. Try writing it differently or send your 📍 location.', pick: '🔎 Which one?', head: '15-day forecast', none: 'dry', rain: 'rain', snow: 'snow', ms: 'm/s', mm: 'mm', vid: '🎬 Country video', src: 'ECMWF, NOAA, DWD ensemble · ~50 km grid', far: 'No data for this point.' },
};
const PK = {  // words of the point forecast
  ru: { brief: 'Коротко', allDry: 'Все 15 дней без существенных осадков', wetNow: 'Осадки возможны уже сегодня', dryUntil: 'Сухо до {d} включительно',
    wetDays: 'Дней с осадками: {n}; сильнее всего {peak}', snowOn: 'Снег: {d}', cooler: 'Похолодание: днём с {a} до {b} к концу периода', warmer: 'Потепление: днём с {a} до {b} к концу периода',
    steady: 'Без резких перемен температуры: днём от {a} до {b}', frost: 'Заморозки до {t} ({d})', wind: 'Сильный ветер до {w} м/с ({d})', windW: 'ветер',
    dry: 'без осадков', rain: 'дождь', snow: 'снег', next: 'Дальше по дням', cDay: 'День', cT: 'Темп.', cP: 'Осадки', run: 'Расчёт', upd: 'Обновлено', model: 'расчёт моделей',
    note: 'Осадки: вероятность за сутки и среднее количество по ансамблю моделей.', noRain: 'Зонт не понадобится', rainAt: '{w} вероятен {a}–{b} ч (до {p} %)', wear: 'Одежда' },
  uz: { brief: 'Qisqacha', allDry: '15 kun davomida sezilarli yog‘in kutilmaydi', wetNow: 'Bugunoq yog‘in bo‘lishi mumkin', dryUntil: '{d} gacha quruq',
    wetDays: 'Yog‘inli kunlar: {n}; eng kuchlisi {peak}', snowOn: 'Qor: {d}', cooler: 'Sovish: kunduzi {a} dan {b} gacha', warmer: 'Isish: kunduzi {a} dan {b} gacha',
    steady: 'Harorat keskin o‘zgarmaydi: kunduzi {a} … {b}', frost: 'Sovuq {t} gacha ({d})', wind: 'Kuchli shamol {w} m/s gacha ({d})', windW: 'shamol',
    dry: 'yog‘insiz', rain: 'yomg‘ir', snow: 'qor', next: 'Keyingi kunlar', cDay: 'Kun', cT: 'Harorat', cP: 'Yog‘in', run: 'Hisob', upd: 'Yangilandi', model: 'modellar hisobi',
    note: 'Yog‘in: sutkalik ehtimol va modellar ansamblining o‘rtacha miqdori.', noRain: 'Soyabon kerak bo‘lmaydi', rainAt: '{w} ehtimoli {a}–{b} soatlarda ({p} % gacha)', wear: 'Kiyim' },
  en: { brief: 'Summary', allDry: 'No notable precipitation for 15 days', wetNow: 'Precipitation likely from today', dryUntil: 'Dry up to and including {d}',
    wetDays: 'Days with precipitation: {n}; the heaviest {peak}', snowOn: 'Snow: {d}', cooler: 'Cooling: by day {a} → {b}', warmer: 'Warming: by day {a} → {b}',
    steady: 'No sharp change in temperature: by day {a} … {b}', frost: 'Frost {t} ({d})', wind: 'Strong wind {w} m/s ({d})', windW: 'wind',
    dry: 'dry', rain: 'rain', snow: 'snow', next: 'Next days', cDay: 'Day', cT: 'Temperature', cP: 'Precipitation', run: 'Run', upd: 'Updated', model: 'model run',
    note: 'Precipitation: the daily chance and the mean amount of the model ensemble.', noRain: 'No umbrella needed', rainAt: '{w} likely {a}–{b} (up to {p}%)', wear: 'What to wear' },
};
const WEAR = {
  ru: { c: ['зимняя куртка, шапка, перчатки', 'тёплая куртка и шапка', 'куртка или пальто, шарф', 'лёгкая куртка или свитер', 'кофта, вечером лёгкая куртка', 'футболка и лёгкая одежда', 'лёгкая одежда, головной убор, вода'], u: 'зонт', b: 'непромокаемая обувь', w: 'ветровка' },
  uz: { c: ['qishki kurtka, telpak, qo‘lqop', 'issiq kurtka va telpak', 'kurtka yoki palto, sharf', 'yengil kurtka yoki sviter', 'kofta, kechqurun yengil kurtka', 'futbolka, yengil kiyim', 'yengil kiyim, bosh kiyim, suv'], u: 'soyabon', b: 'suv o‘tkazmaydigan poyabzal', w: 'shamoldan himoya kurtka' },
  en: { c: ['winter coat, hat, gloves', 'warm coat and hat', 'coat or jacket, scarf', 'light jacket or sweater', 'cardigan, a light jacket in the evening', 'T-shirt and light clothes', 'light clothes, a hat, water'], u: 'umbrella', b: 'waterproof shoes', w: 'windbreaker' },
};
function wearText(lang, lo, hi, p, snow, w) {
  const W = WEAR[lang] || WEAR.ru, t = (lo + 2 * hi) / 3, k = t <= -10 ? 0 : t <= 0 ? 1 : t <= 8 ? 2 : t <= 15 ? 3 : t <= 22 ? 4 : t <= 28 ? 5 : 6;
  return [W.c[k], ...(p >= 40 ? [snow ? W.b : W.u] : []), ...(w >= 8 ? [W.w] : [])].join(', ');
}
const MK = {  // the main keyboard under the chat: four buttons for everything
  ru: { today: '📅 Сегодня и завтра', d15: '🗓 15 дней', video: '🎬 Видео', more: '⚙️ Меню' },
  uz: { today: '📅 Bugun va ertaga', d15: '🗓 15 kun', video: '🎬 Video', more: '⚙️ Menyu' },
  en: { today: '📅 Today and tomorrow', d15: '🗓 15 days', video: '🎬 Video', more: '⚙️ Menu' },
};
const mainKb = () => ({ remove_keyboard: true });  // (kept for old callers)
const locOnce = lang => ({ keyboard: [[{ text: PT[lang].locBtn, request_location: true }]], resize_keyboard: true, one_time_keyboard: true });
const FILLER = new Set('погода погоду погоды прогноз в во на для город городе сегодня завтра какая какой ob-havo obhavo havo bugun ertaga shahar shahrida hava durumu bugün yarın için weather in today tomorrow'.split(' '));
// today and tomorrow hour by hour: the country's video with the main city's timing and clothing advice (prob/hourly.py)
// Telegram caches a file by its URL, so every media link carries the hour: a new build is always fetched again
const fresh = () => Math.floor(Date.now() / 3600e3);
// the short line: "🌧 99% ehtimoli bor · ertaga harorat kunduzi +12…+15° kechasi +3…+8° kutilyapti"
function reaction(d, lang, which) {
  if (!d) return '';
  const p = d.p || 0, emo = d.snow && p >= 30 ? '🌨' : d.storm ? '🌧⛈️' : p >= 30 ? '🌧' : p >= 10 ? '🌦' : '☀️';
  const sg = v => (v > 0 ? '+' : '') + v, rng = a => a ? (a[0] === a[1] ? `${sg(a[0])}°` : `${sg(a[0])}…${sg(a[1])}°`) : '';
  const W = { uz: { today: 'bugun', tomorrow: 'ertaga', p: x => x >= 10 ? `${x}% yog‘in ehtimoli bor` : 'yog‘ingarchilik kutilmayapti', t: (w, dd, nn) => `${w} harorat kunduzi ${dd}${nn ? ` kechasi ${nn}` : ''} kutilyapti` },
    ru: { today: 'сегодня', tomorrow: 'завтра', p: x => x >= 10 ? `вероятность осадков ${x}%` : 'осадков не ожидается', t: (w, dd, nn) => `${w} днём ${dd}${nn ? `, ночью ${nn}` : ''}` },
    en: { today: 'today', tomorrow: 'tomorrow', p: x => x >= 10 ? `chance of precipitation ${x}%` : 'no precipitation expected', t: (w, dd, nn) => `${w} by day ${dd}${nn ? `, at night ${nn}` : ''}` } }[lang] || null;
  if (!W) return '';
  return `${emo} ${W.p(p)} · ${W.t(W[which], rng(d.day) || d.range, rng(d.night))}`;
}
// the 2-day video «where the rain comes from», with a window on the person's region when we know it (prob/moisture.py --days 2)
async function moist2Url(env, lang, id, chat, k = null) {
  const L = lang === 'en' ? 'ru' : lang, head = u => fetch(u, { method: 'HEAD' }).then(r => r.ok).catch(() => false);
  if (k == null && chat > 0) {
    const u = await getUser(env, chat), pl = u && u.place ? JSON.parse(u.place) : null;
    if (pl) { const A = await adminData(env, id); if (A) { let best = null, bd = 9e9; for (const a of A.adm1) { const d = (a.c[1] - pl[0]) ** 2 + ((a.c[0] - pl[1]) * Math.cos(pl[0] / 57.3)) ** 2; if (d < bd) { bd = d; best = a.id; } } if (bd < 9) k = best; } }
  }
  for (const u of [...(k != null ? [`${base(env)}/prob/hr/${id}_moist2_${L}_${k}.mp4`] : []), `${base(env)}/prob/hr/${id}_moist2_${L}.mp4`]) if (await head(u)) return `${u}?v=${fresh()}`;
  return null;
}
async function sendHourly(env, chat, lang, id) {
  let H = null;
  for (const l of [lang, 'ru', 'uz']) { const r = await fetch(`${base(env)}/prob/hr/${id}_${l}.json`, { cf: { cacheTtl: 600 } }); if (r.ok) { H = await r.json(); break; } }
  if (!H) return sendToday(env, chat, lang, id);
  const K = PK[lang], X = { ru: ['Сегодня', 'Завтра', 'по часам'], uz: ['Bugun', 'Ertaga', 'soatma-soat'], en: ['Today', 'Tomorrow', 'by the hour'] }[lang];
  const part = (lbl, d) => d ? `<b>${lbl}</b> ${d.range}\n☂️ ${d.rain}\n🧥 ${K.wear}: ${d.wear}` : '';
  // where the coming rain or snow of the main city comes from (Uzbekistan, Kazakhstan; prob/trajectory.py)
  const TJ = TRJ.has(id) ? await trajData(env, id) : null, ti = TJ && TJ.items.filter(it => it.city[lang] === H.city || it.city.ru === H.city).sort((a, b) => a.k - b.k)[0];
  const rx = [reaction(H.info.today, lang, 'today'), reaction(H.info.tomorrow, lang, 'tomorrow')].filter(Boolean);
  const cap = [`${FLAG[id] || ''} <b>${esc(NAMES[id][lang])}</b> · ${esc(H.city)} — ${X[0].toLowerCase()} / ${X[1].toLowerCase()} ${X[2]}`, ...(rx.length ? ['', ...rx.map(esc)] : []), '', part(X[0], H.info.today), '', part(X[1], H.info.tomorrow),
    ...(ti ? ['', `🧭 ${esc(ti.text[lang] || ti.text.ru)}`] : [])].join('\n').slice(0, 1024);
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
  const url = (await moist2Url(env, lang, id, chat)) || `${base(env)}/prob/${H.video}?v=${fresh()}`;  // the 2-day rain video, else the old one
  // the interactive map (a Telegram mini app): touch the map, drag the hours, hear the weather — private chats only
  // (the keyboard under the input field stays as it is; this message carries the mini-app button)
  // groups and channels: only a link to the interactive map (keyboards under the input field and mini-app buttons work in private chats only)
  // three buttons: the map, where the rain comes from, the notification
  const kb = chat > 0 ? { inline_keyboard: [[liveBtn(env, lang, id, chat)], ...(TRJ.has(id) ? [[{ text: (TJX[lang] || TJX.ru).btn, callback_data: `TJ:${lang}:${id}` }]] : []), [notifBtn(lang, 'hourly')]] } : { inline_keyboard: [[liveBtn(env, lang, id, chat)]] };
  let r = await tg(env, 'sendVideo', { chat_id: chat, video: url, caption: cap, parse_mode: 'HTML', supports_streaming: true, reply_markup: kb });
  if (!r.ok) { const f = await fetch(url); if (f.ok) { const fd = new FormData(); fd.append('chat_id', String(chat)); fd.append('caption', cap); fd.append('parse_mode', 'HTML'); fd.append('supports_streaming', 'true'); fd.append('reply_markup', JSON.stringify(kb)); fd.append('video', new Blob([await f.arrayBuffer()], { type: 'video/mp4' }), `${id}_${lang}.mp4`); r = await (await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendVideo`, { method: 'POST', body: fd })).json(); } }
  if (!r.ok) return tg(env, 'sendMessage', { chat_id: chat, text: cap, parse_mode: 'HTML', reply_markup: kb });
  return r;
}
const locKb = lang => ({ keyboard: [[{ text: PT[lang].locBtn, request_location: true }]], resize_keyboard: true, is_persistent: true });
const MEMO = new Map();  // per-isolate cache: answers stay fast between messages
async function memo(key, ttl, fn) { const m = MEMO.get(key); if (m && Date.now() - m.t < ttl) return m.v; const v = await fn(); if (v) MEMO.set(key, { t: Date.now(), v }); return v; }
async function places(env) { return (await memo('places', 3600e3, async () => { const r = await fetch(`${base(env)}/prob/places.json`, { cf: { cacheTtl: 3600 } }); return r.ok ? r.json() : null; })) || []; }
const norm = t => String(t || '').toLowerCase().replace(/[‘’ʻʼ`´']/g, "'").replace(/ё/g, 'е').replace(/[^\p{L}\p{N}' -]/gu, '').trim();
const pname = (p, lang) => (lang === 'uz' ? p[1] || p[2] : lang === 'en' ? p[2] || p[0] : p[0] || p[2]);
async function searchPlaces(env, q) {
  q = norm(q); if (q.length < 2) return [];
  const P = await places(env), hit = [], part = [];
  for (const p of P) {
    const names = [p[0], p[1], p[2], p[3]].map(norm).filter(Boolean);
    if (names.some(n => n === q)) hit.push(p); else if (names.some(n => n.startsWith(q))) part.push(p);
  }
  return [...hit, ...part].slice(0, 8);
}
async function nearestPlace(env, lat, lon, km = 35) {
  let best = null, bd = km;
  for (const p of await places(env)) { const d = Math.hypot((p[5] - lat) * 111, (p[6] - lon) * 111 * Math.cos(lat * Math.PI / 180)); if (d < bd) { bd = d; best = p; } }
  return best;
}
// the weather right now (Open-Meteo current conditions: the latest model analysis and nowcast, every 15 minutes)
const WMO = {
  uz: { 0: 'ochiq osmon', 1: 'asosan ochiq', 2: 'qisman bulutli', 3: 'bulutli', 45: 'tuman', 48: 'qirovli tuman', 51: 'mayda yomg‘ir', 53: 'mayda yomg‘ir', 55: 'mayda yomg‘ir', 56: 'muzlovchi yomg‘ir', 57: 'muzlovchi yomg‘ir', 61: 'yengil yomg‘ir', 63: 'yomg‘ir', 65: 'kuchli yomg‘ir', 66: 'muzlovchi yomg‘ir', 67: 'muzlovchi yomg‘ir', 71: 'yengil qor', 73: 'qor', 75: 'kuchli qor', 77: 'qor donalari', 80: 'jala', 81: 'jala', 82: 'kuchli jala', 85: 'qor', 86: 'kuchli qor', 95: 'momaqaldiroq', 96: 'do‘lli momaqaldiroq', 99: 'do‘lli momaqaldiroq' },
  ru: { 0: 'ясно', 1: 'преимущественно ясно', 2: 'переменная облачность', 3: 'пасмурно', 45: 'туман', 48: 'изморозь, туман', 51: 'морось', 53: 'морось', 55: 'сильная морось', 56: 'ледяная морось', 57: 'ледяная морось', 61: 'небольшой дождь', 63: 'дождь', 65: 'сильный дождь', 66: 'ледяной дождь', 67: 'ледяной дождь', 71: 'небольшой снег', 73: 'снег', 75: 'сильный снег', 77: 'снежная крупа', 80: 'ливень', 81: 'ливень', 82: 'сильный ливень', 85: 'снегопад', 86: 'сильный снегопад', 95: 'гроза', 96: 'гроза с градом', 99: 'гроза с градом' },
  en: { 0: 'clear', 1: 'mostly clear', 2: 'partly cloudy', 3: 'overcast', 45: 'fog', 48: 'rime fog', 51: 'drizzle', 53: 'drizzle', 55: 'heavy drizzle', 56: 'freezing drizzle', 57: 'freezing drizzle', 61: 'light rain', 63: 'rain', 65: 'heavy rain', 66: 'freezing rain', 67: 'freezing rain', 71: 'light snow', 73: 'snow', 75: 'heavy snow', 77: 'snow grains', 80: 'showers', 81: 'showers', 82: 'heavy showers', 85: 'snow showers', 86: 'heavy snow showers', 95: 'thunderstorm', 96: 'thunderstorm with hail', 99: 'thunderstorm with hail' } };
const NOWX = { uz: { now: 'Hozir', feels: 'his qilinadi', hum: 'namlik', wind: 'shamol', gust: 'shiddat', ms: 'm/s' }, ru: { now: 'Сейчас', feels: 'ощущается', hum: 'влажность', wind: 'ветер', gust: 'порывы', ms: 'м/с' }, en: { now: 'Now', feels: 'feels like', hum: 'humidity', wind: 'wind', gust: 'gusts', ms: 'm/s' } };
const wmoIcon = (c, day) => c >= 95 ? '⛈' : c >= 85 || (c >= 71 && c <= 77) ? '🌨' : c >= 80 ? '🌦' : c >= 51 ? '🌧' : c >= 45 ? '🌫' : c === 3 ? '☁️' : c === 2 ? '⛅' : day ? '☀️' : '🌙';
async function nowWeather(lat, lon) {
  const k = `now:${lat.toFixed(2)},${lon.toFixed(2)}`;
  return memo(k, 10 * 60e3, async () => {
    try {
      const r = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat.toFixed(3)}&longitude=${lon.toFixed(3)}&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,wind_gusts_10m,precipitation,is_day&daily=weather_code&forecast_days=16&wind_speed_unit=ms&timezone=auto`, { cf: { cacheTtl: 600 } });
      if (!r.ok) return null; const j = await r.json(); const c = j.current || {}; c.codes = {}; (j.daily && j.daily.time || []).forEach((d, i) => { c.codes[d] = j.daily.weather_code[i]; }); return c;
    } catch (e) { return null; }
  });
}
function nowLine(c, lang) {
  if (!c || c.temperature_2m == null) return '';
  const X = NOWX[lang] || NOWX.ru, f = v => `${v > 0.5 ? '+' : ''}${Math.round(v)}°`.replace(/^-0°$/, '0°');
  const w = (WMO[lang] || WMO.ru)[c.weather_code] || '';
  return `${wmoIcon(c.weather_code, c.is_day)} <b>${X.now}: ${f(c.temperature_2m)}</b>${w ? `, ${w}` : ''}\n      ${X.feels} ${f(c.apparent_temperature)} · ${X.hum} ${Math.round(c.relative_humidity_2m)}% · ${X.wind} ${Math.round(c.wind_speed_10m)} ${X.ms}${c.wind_gusts_10m >= 10 ? ` (${X.gust} ${Math.round(c.wind_gusts_10m)})` : ''}`;
}
const MAPB = { ru: '🗺 Показать на карте (район выделен)', uz: '🗺 Xaritada ko‘rsatish (tuman ajratilgan)', en: '🗺 Show on the map (district marked)' };
async function pointForecast(env, chat, lang, lat, lon, place, kbOver, range) {
  const L = PT[lang];
  await saveUser(env, chat, { place: JSON.stringify([lat, lon]) });
  // the 0.25° tiles of the region first (the same numbers as the videos, city texts and hourly forecast), the 0.5° world tiles elsewhere
  const idx = dir => memo(dir, 600e3, async () => (await fetch(`${base(env)}/prob/${dir}/index.json`, { cf: { cacheTtl: 600 } })).json().catch(() => null));
  let I = null, r = null;
  for (const dir of ['pt25', 'pt']) {
    const J = await idx(dir); if (!J) continue;
    if (J.box && !(lon >= J.box[0] && lon <= J.box[1] - J.d && lat >= J.box[2] + J.d && lat <= J.box[3])) continue;
    if (!J.box && (lat > 80 || lat <= -60)) continue;
    const t = Math.ceil(lat / J.tile) * J.tile, l = Math.floor(lon / J.tile) * J.tile;
    const q = await fetch(`${base(env)}/prob/${dir}/${t}_${l}.bin`, { cf: { cacheTtl: 600 } });
    if (q.ok) { I = J; r = q; break; }
  }
  if (!I) return tg(env, 'sendMessage', { chat_id: chat, text: L.far });
  const top = Math.ceil(lat / I.tile) * I.tile, left = Math.floor(lon / I.tile) * I.tile, n = I.n, S = I.steps.length;
  const B = new Uint8Array(await r.arrayBuffer()), fy = (top - lat) / I.d, fx = (lon - left) / I.d;
  const y0 = Math.min(n - 2, Math.floor(fy)), x0 = Math.min(n - 2, Math.floor(fx)), ay = fy - y0, ax = fx - x0;
  const val = (s, v) => { let sum = 0, w = 0;
    for (const [dy, dx, k] of [[0, 0, (1 - ay) * (1 - ax)], [0, 1, (1 - ay) * ax], [1, 0, ay * (1 - ax)], [1, 1, ay * ax]]) { const b = B[((s * 5 + v) * n + y0 + dy) * n + x0 + dx]; if (b !== 255) { sum += b * k; w += k; } }
    return w ? sum / w : NaN; };
  const TZC = { UZ: 5, KZ: 5, KG: 6, TJ: 5, TM: 5, AZ: 4, AM: 4, GE: 4, TR: 3, BY: 3, MD: 2, UA: 2, AF: 4.5, IR: 3.5, CN: 8, IN: 5.5 };
  const cc = place ? place[4] : (lat > 37 && lat < 45.6 && lon > 56 && lon < 73.2 ? 'UZ' : '');
  const off = TZC[cc] ?? (cc === 'RU' ? Math.max(2, Math.min(12, Math.round(lon / 15))) : Math.max(-11, Math.min(12, Math.round(lon / 15))));
  const run = Date.parse(I.run), days = new Map(), wins = [];
  for (let s = 0; s < S; s++) {
    const mid = new Date(run + (I.steps[s] - I.win[s] / 2 + off) * 3600e3).toISOString().slice(0, 10);
    wins.push({ d: mid, h1: new Date(run + (I.steps[s] - I.win[s] + off) * 3600e3).getUTCHours(), h2: new Date(run + (I.steps[s] + off) * 3600e3).getUTCHours() || 24, p: val(s, 0) / 2.5, t: val(s, 1) / 2 - 60, w: val(s, 3) / 5 });
    const d = days.get(mid) || { P: 0, T: [], A: 0, C: [], W: 0, wetT: [] };
    const p = val(s, 0) / 2.5, t = val(s, 1) / 2 - 60, c = val(s, 2) / 250, w = val(s, 3) / 5, a = Math.expm1(val(s, 4) / 40);
    if (isFinite(p)) d.P = Math.max(d.P, p); if (isFinite(t)) d.T.push(t); if (isFinite(a)) d.A += a; if (isFinite(c)) d.C.push(c); if (isFinite(w)) d.W = Math.max(d.W, w);
    if (p >= 30 && isFinite(t)) d.wetT.push(t);
    days.set(mid, d);
  }
  const today = new Date(Date.now() + off * 3600e3).toISOString().slice(0, 10), tmrw = new Date(Date.now() + (off + 24) * 3600e3).toISOString().slice(0, 10);
  const f = v => `${v > 0.5 ? '+' : ''}${Math.round(v)}`.replace(/^-0$/, '0'), deg = v => f(v) + '°';
  const K = PK[lang], D = [];
  for (const [d, x] of days) {
    if (d < today || !x.T.length) continue;
    const snow = x.wetT.length ? x.wetT.reduce((a, b) => a + b) / x.wetT.length <= 0.5 : Math.min(...x.T) < -1;
    const cm = x.C.length ? x.C.reduce((a, b) => a + b) / x.C.length : 0, p = Math.round(x.P);
    D.push({ d, lo: Math.min(...x.T), hi: Math.max(...x.T), p, mm: x.A, w: x.W, snow, ic: p >= 60 ? (snow ? '❄️' : '🌧') : p >= 35 ? (snow ? '🌨' : '🌦') : cm > 0.7 ? '☁️' : cm > 0.35 ? '⛅' : '☀️' });
  }
  if (!D.length) return tg(env, 'sendMessage', { chat_id: chat, text: L.far });
  const wd = d => { const t = new Date(d + 'T12:00:00Z'); return `${WD[lang][t.getUTCDay()]} ${String(t.getUTCDate()).padStart(2, '0')}.${String(t.getUTCMonth() + 1).padStart(2, '0')}`; };
  const wet = x => x.p >= 40, pr = x => !wet(x) && x.p < 20 ? K.dry : `${x.snow ? K.snow : K.rain} ${x.p} %${x.mm >= 0.5 ? `, ~${x.mm < 9.5 ? x.mm.toFixed(0) : Math.round(x.mm)} ${L.mm}` : ''}`;
  // short analysis for the reader
  const sum = [], firstWet = D.findIndex(wet), wetDays = D.filter(wet);
  if (firstWet < 0) sum.push(K.allDry);
  else {
    sum.push(firstWet === 0 ? K.wetNow : K.dryUntil.replace('{d}', wd(D[firstWet - 1].d)));
    const peak = wetDays.reduce((a, b) => (b.mm > a.mm || (b.mm === a.mm && b.p > a.p) ? b : a));
    sum.push(K.wetDays.replace('{n}', wetDays.length).replace('{peak}', `${wd(peak.d)} — ${peak.p} %${peak.mm >= 1 ? `, ~${Math.round(peak.mm)} ${L.mm}` : ''}`));
    if (wetDays.some(x => x.snow)) sum.push(K.snowOn.replace('{d}', wetDays.filter(x => x.snow).slice(0, 3).map(x => wd(x.d)).join(', ')));
  }
  const n3 = Math.min(3, D.length), hi0 = D.slice(0, n3).reduce((a, x) => a + x.hi, 0) / n3, hi1 = D.slice(-n3).reduce((a, x) => a + x.hi, 0) / n3;
  if (hi1 - hi0 <= -4) sum.push(K.cooler.replace('{a}', deg(hi0)).replace('{b}', deg(hi1)));
  else if (hi1 - hi0 >= 4) sum.push(K.warmer.replace('{a}', deg(hi0)).replace('{b}', deg(hi1)));
  else sum.push(K.steady.replace('{a}', deg(Math.min(...D.map(x => x.hi)))).replace('{b}', deg(Math.max(...D.map(x => x.hi)))));
  const frost = D.reduce((a, x) => (x.lo < a.lo ? x : a));
  if (frost.lo < 0) sum.push(K.frost.replace('{t}', deg(frost.lo)).replace('{d}', wd(frost.d)));
  const windy = D.reduce((a, x) => (x.w > a.w ? x : a));
  if (isFinite(windy.w) && windy.w >= 10) sum.push(K.wind.replace('{w}', Math.round(windy.w)).replace('{d}', wd(windy.d)));
  // the next days as an aligned table
  const pad = (t, n) => t + ' '.repeat(Math.max(0, n - [...t].length));
  const bar = p => { const k = Math.max(0, Math.min(5, Math.round(p / 20))); return '█'.repeat(k) + '░'.repeat(5 - k); };
  const NW = await nowWeather(lat, lon), nowT = nowLine(NW, lang);
  // one icon per day: rain drops, snow, sun, clouds, and fog or thunder from the day's weather code
  for (const x of D) { const c = NW && NW.codes ? NW.codes[x.d] : null;
    x.ic = c >= 95 && x.p >= 30 ? '⛈' : (c === 45 || c === 48) && x.p < 35 ? '🌫' : x.p >= 35 ? (x.snow ? '❄️' : '💧') : x.ic; }
  // the columns as wide as their longest text; the icon at the end of the line (an emoji's width differs between phones and broke the columns)
  const Dn = D.slice(2), tt = x => `${f(x.lo)}…${f(x.hi)}°`, mmT = x => x.mm >= 0.5 ? `${x.mm < 9.5 ? x.mm.toFixed(0) : Math.round(x.mm)} ${L.mm}` : '';
  const cw = { d: Math.max([...K.cDay].length, ...Dn.map(x => [...wd(x.d)].length)) + 2, t: Math.max([...K.cT].length, ...Dn.map(x => [...tt(x)].length)) + 2, m: Math.max(0, ...Dn.map(x => [...mmT(x)].length)) };
  const rows = Dn.map(x => `${pad(wd(x.d), cw.d)}${pad(tt(x), cw.t)}${bar(x.p)} ${pad(x.p < 20 ? '—' : `${x.p}%`, 4)} ${pad(mmT(x), cw.m)} ${x.ic}`);
  const nm = place ? `${FLAG[place[4]] || '📍'} <b>${esc(pname(place, lang))}</b>` : `📍 <b>${lat.toFixed(2)}, ${lon.toFixed(2)}</b>`;
  const hm = t => { const l = new Date(t + off * 3600e3); return `${String(l.getUTCDate()).padStart(2, '0')}.${String(l.getUTCMonth() + 1).padStart(2, '0')} ${String(l.getUTCHours()).padStart(2, '0')}:${String(l.getUTCMinutes()).padStart(2, '0')}`; };
  const u = I.built ? `${hm(Date.parse(I.built))} · ${K.model} ${hm(run).slice(0, 5)} ${hm(run).slice(6)}` : hm(run);
  const umbr = x => {  // when it rains (3-hour windows of that day)
    const ws = wins.filter(v => v.d === x.d), wet = ws.filter(v => v.p >= 40);
    let r = K.noRain;
    if (wet.length) { const top = wet.reduce((a, b) => (b.p > a.p ? b : a)); let a = top, b = top; const i = ws.indexOf(top);
      for (let j = i - 1; j >= 0 && ws[j].p >= 40; j--) a = ws[j]; for (let j = i + 1; j < ws.length && ws[j].p >= 40; j++) b = ws[j];
      r = K.rainAt.replace('{w}', x.snow ? K.snow : K.rain).replace('{a}', String(a.h1).padStart(2, '0')).replace('{b}', String(b.h2).padStart(2, '0')).replace('{p}', Math.round(top.p)); }
    return r;
  };
  const detail = x => `\n      ☂️ ${umbr(x)}\n      🧥 ${K.wear}: ${wearText(lang, x.lo, x.hi, x.p, x.snow, x.w)}`;
  const day = (x, w) => `${x.ic} <b>${w}</b> · ${wd(x.d)}\n      ${deg(x.lo)}…${deg(x.hi)} · ${pr(x)}${isFinite(x.w) && x.w >= 5 ? ` · ${K.windW} ${Math.round(x.w)} ${L.ms}` : ''}${detail(x)}`;
  if (range === 'photo') return photo15(env, chat, lang, lat, lon, place, D);  // the 15 days as one picture
  if (range) {  // one week (or any days asked for), day by day
    const WX = WKX[lang] || WKX.ru, [a, b] = range, Dw = D.filter(x => x.d >= a && x.d <= b);
    const nm0 = place ? `${FLAG[place[4]] || '📍'} <b>${esc(pname(place, lang))}</b>` : `📍 <b>${lat.toFixed(2)}, ${lon.toFixed(2)}</b>`;
    const head = `${nm0} · ${WX.head.replace('{n}', isoKey(a)).replace('{a}', ddm(a)).replace('{b}', ddm(b))}`;
    if (!Dw.length) return tg(env, 'sendMessage', { chat_id: chat, text: `${head}\n\n${WX.far.replace('{last}', ddm(D[D.length - 1].d))}`, parse_mode: 'HTML', reply_markup: weeksKb(lang) });
    const wetW = Dw.filter(wet), mm = Dw.reduce((s_, x) => s_ + (x.mm || 0), 0), lo = Math.min(...Dw.map(x => x.lo)), hi = Math.max(...Dw.map(x => x.hi));
    const brief = [WX.temp.replace('{lo}', deg(lo)).replace('{hi}', deg(hi)), wetW.length ? WX.wet.replace('{n}', wetW.length).replace('{d}', wetW.map(x => wd(x.d)).join(', ')) + (mm >= 1 ? WX.mm.replace('{mm}', Math.round(mm)) : '') : WX.dry];
    const cut = Dw.length < 1 + (Date.parse(b) - Date.parse(a)) / 864e5 ? `\n<i>${WX.part.replace('{last}', ddm(D[D.length - 1].d))}</i>` : '';
    const txt = [head, '', ...brief.map(x => `▸ ${x}`), '', ...Dw.map(x => day(x, x.d === today ? T[lang].tdy : x.d === tmrw ? T[lang].tmw : WDL[lang][new Date(x.d + 'T12:00:00Z').getUTCDay()])), cut, `<i>${K.note}</i>`].join('\n');
    return tg(env, 'sendMessage', { chat_id: chat, text: txt.slice(0, 4000), parse_mode: 'HTML', reply_markup: weeksKb(lang, a) });
  }
  const isAdmin = String(chat) === (await kv(env, 'admin'));  // update times only for the bot's admin
  const text = [`${nm} · ${L.head}`, ...(isAdmin ? [`<i>${I.built ? K.upd : K.run} ${u} (UTC${off >= 0 ? '+' : ''}${off})</i>`] : []), '', ...(nowT ? [nowT, ''] : []),
    `<b>${K.brief}</b>`, ...sum.map(x => `▸ ${x}`), '',
    day(D[0], D[0].d === today ? T[lang].tdy : wd(D[0].d)), ...(D[1] ? [day(D[1], D[1].d === tmrw ? T[lang].tmw : wd(D[1].d))] : []), '',
    ...(rows.length ? [`<b>${K.next}</b>`, `<pre>${esc(pad(K.cDay, cw.d) + pad(K.cT, cw.t) + K.cP)}\n${esc(rows.join('\n'))}</pre>`] : []),
    `<i>${K.note}</i>`].join('\n');
  let kb = kbOver && kbOver.keyboard ? kbOver : null;
  // the picture: the city behind (its season and weather now), the same forecast on it; the text stays the fallback
  const pn = place ? noEmo(pname(place, lang)) : `${lat.toFixed(2)}, ${lon.toFixed(2)}`;
  const cardD = { name: pn, sub: `${L.head} · ${wd(D[0].d)}`, bh: K.brief, nh: K.next, brief: sum.map(noEmo).slice(0, 5), note: noEmo(K.note), foot: 't.me/ObHavo_ECMWF_bot',
    now: NW && NW.temperature_2m != null ? { t: `${NW.temperature_2m > 0.5 ? '+' : ''}${Math.round(NW.temperature_2m)}°`.replace(/^-0°$/, '0°'), ic: wmoKey(NW.weather_code, NW.is_day),
      txt: ((WMO[lang] || WMO.ru)[NW.weather_code] || '').replace(/^./, c => c.toUpperCase()),
      more: `${(NOWX[lang] || NOWX.ru).feels} ${Math.round(NW.apparent_temperature)}° · ${(NOWX[lang] || NOWX.ru).hum} ${Math.round(NW.relative_humidity_2m)}% · ${(NOWX[lang] || NOWX.ru).wind} ${Math.round(NW.wind_speed_10m)} ${(NOWX[lang] || NOWX.ru).ms}` } : null,
    two: D.slice(0, 2).map((x, k) => ({ w: `${k ? (x.d === tmrw ? T[lang].tmw : wd(x.d)) : (x.d === today ? T[lang].tdy : wd(x.d))} · ${wd(x.d)}`.replace(/^(.+) · \1$/, '$1'), ic: icKey(x.ic), t: `${deg(x.lo)}…${deg(x.hi)}`,
      pr: noEmo(pr(x)), umb: noEmo(umbr(x)), wear: `${K.wear}: ${noEmo(wearText(lang, x.lo, x.hi, x.p, x.snow, x.w))}` })),
    list: Dn.map(x => ({ wd: wd(x.d), ic: icKey(x.ic), lo: x.lo, hi: x.hi, lot: deg(x.lo), hit: deg(x.hi), p: x.p, mm: mmT(x), snow: !!x.snow })) };
  const cardQ = { city: place ? pname(place, 'en') : `${lat.toFixed(1)}, ${lon.toFixed(1)}`, country: place && NAMES[place[4]] ? NAMES[place[4]].en : '', lat, month: +new Date(Date.now() + off * 3600e3).toISOString().slice(5, 7),
    code: NW ? NW.weather_code : 2, day: NW ? !!NW.is_day : true, t: NW && NW.temperature_2m != null ? NW.temperature_2m : D[0].hi };
  const capC = `${nm} · ${L.head}${nowT ? `\n${nowT.split('\n')[0]}` : ''}`;
  if (!kb) { const uu = await getUser(env, chat); kb = replyKb(env, lang, place && NAMES[place[4]] ? place[4] : (uu && NAMES[uu.region] ? uu.region : 'UZ')); }
  // the place on the interactive map: its district and region outlined (Uzbekistan, Kazakhstan, Kyrgyzstan)
  const rid_ = ['UZ', 'KZ', 'KG'].find(c => { const A = { UZ: [55.9, 73.2, 37.1, 45.6], KZ: [46.4, 87.4, 40.5, 55.5], KG: [69.2, 80.3, 39.1, 43.3] }[c]; return lon >= A[0] && lon <= A[1] && lat >= A[2] && lat <= A[3]; });
  if (rid_ && chat > 0 && !(kbOver && kbOver.keyboard)) {
    const u = `${base(env)}/live.html?r=${rid_}&l=${lang}&lat=${lat.toFixed(3)}&lon=${lon.toFixed(3)}&n=${encodeURIComponent(String(nm).replace(/<[^>]+>/g, '').slice(0, 40))}`;
    // (the menu keyboard under the input field is persistent: it stays while this message carries the map button)
    const mk = { inline_keyboard: [[{ text: (MAPB[lang] || MAPB.ru), web_app: { url: u } }], [phBtn(lang, lat, lon)], [pvBtn(lang, lat, lon)], [{ text: (SUBM[lang] || SUBM.ru).remind, callback_data: `NS:${lang}:days` }]] };
    if (await sendCard(env, chat, cardD, cardQ, capC, mk)) return true;
    return tg(env, 'sendMessage', { chat_id: chat, text: text.slice(0, 4000), parse_mode: 'HTML', reply_markup: mk });
  }
  const mk2 = chat > 0 ? { inline_keyboard: [[phBtn(lang, lat, lon)], [pvBtn(lang, lat, lon)], [{ text: (SUBM[lang] || SUBM.ru).remind, callback_data: `NS:${lang}:days` }]] } : kb;
  if (await sendCard(env, chat, cardD, cardQ, capC, mk2)) return true;
  if (chat > 0) return tg(env, 'sendMessage', { chat_id: chat, text: text.slice(0, 4000), parse_mode: 'HTML', reply_markup: mk2 });
  return tg(env, 'sendMessage', { chat_id: chat, text: text.slice(0, 4000), parse_mode: 'HTML', ...(kb ? { reply_markup: kb } : {}) });
}
/* ---------- 🏙 the forecast of a place as a picture: its city in the season and weather of today behind (Workers AI), the forecast on it.
   The bot writes an SVG (/card/<id>.svg), wsrv.nl turns it into a JPEG, Telegram fetches that: no drawing on the bot's own (tiny) CPU budget. ---------- */
const BOT_ORIGIN = 'https://osmon-bot.vafoev-otabek97.workers.dev';
const xe = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const noEmo = s => String(s || '').replace(/<[^>]+>/g, '').replace(/[\u{1F000}-\u{1FAFF}\u{2190}-\u{21FF}\u{2300}-\u{23FF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}\u{200D}]/gu, '').replace(/\s+/g, ' ').trim();
const icKey = e => /⛈/.test(e) ? 'storm' : /🌫/.test(e) ? 'fog' : /❄|🌨/.test(e) ? 'snow' : /💧|🌧|☔|🌦/.test(e) ? 'rain' : /⛅|🌤|🌥/.test(e) ? 'part' : /☁/.test(e) ? 'cloud' : /☀|🌞/.test(e) ? 'sun' : /🌙/.test(e) ? 'moon' : 'part';
const wmoKey = (c, day) => c >= 95 ? 'storm' : c >= 85 || (c >= 71 && c <= 77) ? 'snow' : c >= 51 ? 'rain' : c >= 45 ? 'fog' : c === 3 ? 'cloud' : c === 2 ? 'part' : day ? 'sun' : 'moon';
function svgIcon(k, x, y, r) {
  const sun = (cx, cy, rr) => `<circle cx="${cx}" cy="${cy}" r="${rr}" fill="#ffc93c"/>` + [0, 1, 2, 3, 4, 5, 6, 7].map(i => { const a = i * Math.PI / 4; return `<line x1="${(cx + Math.cos(a) * rr * 1.35).toFixed(1)}" y1="${(cy + Math.sin(a) * rr * 1.35).toFixed(1)}" x2="${(cx + Math.cos(a) * rr * 1.75).toFixed(1)}" y2="${(cy + Math.sin(a) * rr * 1.75).toFixed(1)}" stroke="#ffc93c" stroke-width="${(rr * 0.22).toFixed(1)}" stroke-linecap="round"/>`; }).join('');
  const cloud = (cx, cy, rr, col) => `<g fill="${col}"><circle cx="${cx - rr * 0.55}" cy="${cy + rr * 0.15}" r="${rr * 0.55}"/><circle cx="${cx}" cy="${cy - rr * 0.2}" r="${rr * 0.75}"/><circle cx="${cx + rr * 0.6}" cy="${cy + rr * 0.1}" r="${rr * 0.6}"/><rect x="${cx - rr * 0.55}" y="${cy + rr * 0.1}" width="${rr * 1.15}" height="${rr * 0.6}"/></g>`;
  if (k === 'sun') return sun(x, y, r * 0.6);
  if (k === 'moon') return `<circle cx="${x}" cy="${y}" r="${r * 0.6}" fill="#f4e7b5"/><circle cx="${x + r * 0.28}" cy="${y - r * 0.2}" r="${r * 0.5}" fill="#0c1626"/>`;
  if (k === 'part') return sun(x - r * 0.35, y - r * 0.3, r * 0.42) + cloud(x + r * 0.15, y + r * 0.15, r * 0.62, '#eef2f7');
  if (k === 'fog') return [0, 1, 2].map(j => `<line x1="${x - r * 0.75}" y1="${y - r * 0.4 + j * r * 0.4}" x2="${x + r * 0.75}" y2="${y - r * 0.4 + j * r * 0.4}" stroke="#d6dde6" stroke-width="${r * 0.16}" stroke-linecap="round"/>`).join('');
  let s = cloud(x, y - r * 0.15, r * 0.7, k === 'cloud' ? '#e3e9f0' : '#cfd8e3');
  if (k === 'rain') s += [-1, 0, 1].map(i => `<line x1="${x + i * r * 0.38}" y1="${y + r * 0.45}" x2="${x + i * r * 0.38 - r * 0.12}" y2="${y + r * 0.8}" stroke="#5fb0ff" stroke-width="${r * 0.14}" stroke-linecap="round"/>`).join('');
  if (k === 'snow') s += [-1, 0, 1].map(i => `<circle cx="${x + i * r * 0.38}" cy="${y + r * 0.62}" r="${r * 0.11}" fill="#ffffff"/>`).join('');
  if (k === 'storm') s += `<path d="M${x + r * 0.05} ${y + r * 0.3} L${x - r * 0.25} ${y + r * 0.75} L${x + r * 0.02} ${y + r * 0.7} L${x - r * 0.12} ${y + r * 1.05} L${x + r * 0.32} ${y + r * 0.55} L${x + r * 0.05} ${y + r * 0.58} Z" fill="#ffd23c"/>`;
  return s;
}
function wrapT(s, maxw, size, bold, maxl) {  // the lines of a text in a width (DejaVu Sans: ~0.55 em a letter, bold ~0.6)
  const cw = size * (bold ? 0.62 : 0.56), out = []; let line = '';
  for (const w of String(s).split(' ')) { const t = line ? line + ' ' + w : w; if ([...t].length * cw > maxw && line) { out.push(line); line = w; } else line = t; }
  if (line) out.push(line);
  if (out.length > maxl) { out.length = maxl; out[maxl - 1] = out[maxl - 1].replace(/\s*\S*$/, '') + '…'; }
  return out;
}
const tColor = t => { const S = [[-25, [110, 64, 190]], [-10, [70, 110, 220]], [0, [90, 180, 235]], [8, [110, 200, 140]], [16, [235, 210, 70]], [25, [245, 140, 50]], [35, [220, 60, 45]]];
  if (t <= S[0][0]) return `rgb(${S[0][1]})`; const i = S.findIndex(q => t <= q[0]); if (i < 0) return `rgb(${S[S.length - 1][1]})`;
  const a = (t - S[i - 1][0]) / (S[i][0] - S[i - 1][0]); return `rgb(${[0, 1, 2].map(k => Math.round(S[i - 1][1][k] + (S[i][1][k] - S[i - 1][1][k]) * a))})`; };
function cardSvg(d, bg) {
  const W = 1080, F = 'font-family="DejaVu Sans, Verdana, sans-serif"', T = (s, x, y, sz, col, o = {}) => `<text x="${x}" y="${y}" ${F} font-size="${sz}" font-weight="${o.b ? 700 : 400}" fill="${col}"${o.a ? ` text-anchor="${o.a}"` : ''}${o.op ? ` fill-opacity="${o.op}"` : ''}${o.sh ? ' filter="url(#sh)"' : ''}>${xe(s)}</text>`;
  const br = d.brief.map(b => wrapT(b, W - 160, 31, false, 2)), nb = br.reduce((s, l) => s + l.length, 0);
  let y = 560, body = '';
  body += T(d.bh, 56, y, 34, '#ffd29c', { b: 1 }); y += 18;
  for (const L of br) { body += `<circle cx="68" cy="${y + 30}" r="6" fill="#f08a24"/>`; L.forEach((l, i) => { body += T(l, 90, y + 41 + i * 40, 31, '#ffffff'); }); y += 46 * L.length; }
  y += 26;
  const cw = (W - 112 - 24) / 2;
  d.two.forEach((o, k) => { const x = 56 + k * (cw + 24);
    body += `<rect x="${x}" y="${y}" width="${cw}" height="236" rx="22" fill="#ffffff" fill-opacity="0.08" stroke="#ffffff" stroke-opacity="0.14" stroke-width="2"/>`;
    body += T(o.w, x + 26, y + 50, 29, '#ffd29c', { b: 1 }) + svgIcon(o.ic, x + cw - 56, y + 46, 40) + T(o.t, x + 26, y + 104, 44, '#ffffff', { b: 1 }) + T(wrapT(o.pr, cw - 52, 26, false, 1)[0], x + 26, y + 144, 26, '#ffffff', { op: 0.85 });
    body += T(wrapT(o.umb, cw - 52, 23, false, 1)[0], x + 26, y + 182, 23, '#ffffff', { op: 0.75 }) + T(wrapT(o.wear, cw - 52, 23, false, 1)[0], x + 26, y + 214, 23, '#ffffff', { op: 0.75 }); });
  y += 236 + 46;
  body += T(d.nh, 56, y, 34, '#ffd29c', { b: 1 }); y += 22;
  const lo = Math.min(...d.list.map(r => r.lo)), hi = Math.max(...d.list.map(r => r.hi)), sp = Math.max(1, hi - lo), bx0 = 470, bw = 250;
  d.list.forEach((r, j) => { const yy = y + 16 + j * 58;
    if (j % 2 === 0) body += `<rect x="40" y="${yy}" width="${W - 80}" height="56" rx="14" fill="#ffffff" fill-opacity="0.05"/>`;
    body += T(r.wd, 64, yy + 38, 28, '#ffffff', { b: 1 }) + svgIcon(r.ic, 300, yy + 28, 23) + T(r.lot, bx0 - 16, yy + 38, 27, '#ffffff', { a: 'end', op: 0.75 });
    let a0 = bx0 + bw * (r.lo - lo) / sp, a1 = bx0 + bw * (r.hi - lo) / sp; if (a1 - a0 < 12) a1 = a0 + 12;
    body += `<defs><linearGradient id="t${j}" x1="0" x2="1"><stop offset="0" stop-color="${tColor(r.lo)}"/><stop offset="1" stop-color="${tColor(r.hi)}"/></linearGradient></defs>`;
    body += `<rect x="${bx0}" y="${yy + 23}" width="${bw}" height="10" rx="5" fill="#ffffff" fill-opacity="0.12"/><rect x="${a0.toFixed(1)}" y="${yy + 23}" width="${(a1 - a0).toFixed(1)}" height="10" rx="5" fill="url(#t${j})"/>`;
    body += T(r.hit, bx0 + bw + 16, yy + 38, 27, '#ffffff', { b: 1 });
    if (r.p >= 20) { const col = r.snow ? '#c9a7ff' : '#5fb0ff';
      body += `<path d="M${W - 258} ${yy + 30} L${W - 250} ${yy + 14} L${W - 242} ${yy + 30} A8 8 0 1 1 ${W - 258} ${yy + 30} Z" fill="${col}"/>` + T(`${r.p}%`, W - 230, yy + 38, 27, col, { b: 1 }) + (r.mm ? T(r.mm, W - 60, yy + 38, 25, '#ffffff', { a: 'end', op: 0.7 }) : '');
    } else body += T('—', W - 230, yy + 38, 27, '#ffffff', { op: 0.35 }); });
  y += 16 + d.list.length * 58 + 50;
  body += wrapT(d.note, W - 112, 22, false, 2).map((l, i) => T(l, W / 2, y + i * 30, 22, '#ffffff', { a: 'middle', op: 0.5 })).join(''); y += 64;
  body += T(d.foot, W / 2, y, 24, '#ffd29c', { a: 'middle', b: 1, op: 0.8 }); const H = y + 40;
  const head = T(d.name, 56, 112, d.name.length > 16 ? 52 : 66, '#ffffff', { b: 1, sh: 1 }) + T(d.sub, 58, 162, 30, '#ffffff', { op: 0.9, sh: 1 }) +
    (d.now ? T(d.now.t, W - 56, 140, 120, '#ffffff', { b: 1, a: 'end', sh: 1 }) + svgIcon(d.now.ic, W - 56 - [...d.now.t].length * 72 - 60, 98, 52) + T(d.now.txt, W - 56, 196, 30, '#ffffff', { b: 1, a: 'end', sh: 1 }) + T(d.now.more, W - 56, 238, 24, '#ffffff', { a: 'end', op: 0.9, sh: 1 }) : '');
  return `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
<defs><filter id="sh" x="-5%" y="-20%" width="110%" height="140%"><feDropShadow dx="0" dy="2" stdDeviation="5" flood-color="#000" flood-opacity="0.6"/></filter>
<linearGradient id="gt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#08101e" stop-opacity="0.65"/><stop offset="1" stop-color="#08101e" stop-opacity="0"/></linearGradient>
<linearGradient id="gb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0c1626" stop-opacity="0"/><stop offset="0.55" stop-color="#0c1626" stop-opacity="0.82"/><stop offset="1" stop-color="#0c1626"/></linearGradient></defs>
<rect width="${W}" height="${H}" fill="#0c1626"/>
${bg ? `<image x="0" y="0" width="${W}" height="1080" preserveAspectRatio="xMidYMid slice" href="data:image/jpeg;base64,${bg}" xlink:href="data:image/jpeg;base64,${bg}"/>` : `<rect width="${W}" height="1080" fill="#26476b"/>`}
<rect width="${W}" height="320" fill="url(#gt)"/><rect y="420" width="${W}" height="480" fill="url(#gb)"/><rect y="899" width="${W}" height="${H - 899}" fill="#0c1626"/>
${head}${body}</svg>`;
}
async function cardBg(env, q) {  // the city's picture for this season, weather and time of day: made once, kept in the database
  if (!env.DB) return null;
  await env.DB.prepare('CREATE TABLE IF NOT EXISTS bgimg (k TEXT PRIMARY KEY, b TEXT, t INTEGER)').run();
  const north = q.lat >= 0, m = q.month, idx = Math.floor(((north ? m : (m + 5) % 12 + 1) % 12) / 3);  // 0 winter, 1 spring, 2 summer, 3 autumn
  let season = Math.abs(q.lat) < 23 ? 'tropical' : ['winter', 'spring', 'summer', 'autumn'][idx];
  const SE = { winter: q.t <= 2 ? 'winter, snow on roofs, streets and trees' : 'mild winter, bare trees, no snow', spring: 'spring, fresh green trees and blossoms', summer: 'summer, lush green trees',
    autumn: q.t <= 1 ? 'late autumn, frosty air, a light dusting of first snow, last yellow leaves' : 'autumn, golden and orange leaves', tropical: 'tropical, palm trees and lush greenery' }[season];
  if (season === 'autumn' && q.t <= 1) season = 'lateaut';
  const wx = wmoKey(q.code, 1), WXT = { sun: 'clear blue sky, soft sunlight', part: 'partly cloudy sky', cloud: 'overcast grey sky', rain: 'rain, wet reflective streets', snow: 'falling snow', fog: 'misty fog', storm: 'dramatic storm clouds' }[wx];
  const key = `${(q.city + '-' + q.country).toLowerCase().replace(/[^a-z0-9]+/g, '-')}_${season}_${wx}_${q.day ? 'd' : 'n'}`;
  const row = await env.DB.prepare('SELECT b FROM bgimg WHERE k = ?1').bind(key).first();
  if (row && row.b) return row.b;
  if (!env.AI) return null;
  const prompt = `Beautiful photorealistic view of ${q.city}, ${q.country}: its famous landmarks and characteristic architecture, ${SE}, ${WXT}, ${q.day ? 'daytime' : 'at night, warm city lights glowing'}. Professional travel photography, wide angle, natural colours, sharp details, no text, no watermark, no logo.`;
  const r = await env.AI.run('@cf/black-forest-labs/flux-1-schnell', { prompt, steps: 6 }).catch(e => { console.log('bg ai', e && e.message); return null; });
  const b = r && r.image; if (!b) return null;
  await env.DB.prepare('INSERT OR REPLACE INTO bgimg (k, b, t) VALUES (?1, ?2, ?3)').bind(key, b, Date.now()).run();
  return b;
}
async function sendCard(env, chat, d, q, caption, markup) {  // → the Telegram result, or null when the picture could not be made
  try {
    const bg = await cardBg(env, q);
    await env.DB.prepare('CREATE TABLE IF NOT EXISTS cards (id TEXT PRIMARY KEY, s TEXT, t INTEGER)').run();
    const id = [...crypto.getRandomValues(new Uint8Array(9))].map(v => v.toString(16).padStart(2, '0')).join('');
    await env.DB.prepare('DELETE FROM cards WHERE t < ?1').bind(Date.now() - 6 * 3600e3).run();
    await env.DB.prepare('INSERT INTO cards (id, s, t) VALUES (?1, ?2, ?3)').bind(id, cardSvg(d, bg), Date.now()).run();
    const url = `https://wsrv.nl/?url=${encodeURIComponent(`${BOT_ORIGIN}/card/${id}.svg`)}&output=jpg&q=88`;
    const r = await tg(env, 'sendPhoto', { chat_id: chat, photo: url, caption: caption.slice(0, 1024), parse_mode: 'HTML', ...(markup ? { reply_markup: markup } : {}) });
    if (!r.ok) console.log('card', r.description);
    return r.ok ? r : null;
  } catch (e) { console.log('card', e && e.stack); return null; }
}
/* ---------- 🖼 the 15 days of a place as one picture (Full HD, drawn by QuickChart from the same numbers as the text) ---------- */
const PHX = { ru: { btn: '🖼 Фото прогноза на 15 дней', t: '{n} · прогноз на 15 дней', p: 'Вероятность осадков, %', hi: 'Днём, °C', lo: 'Ночью, °C', src: 'Osmon · модели ECMWF, NOAA, DWD · t.me/ObHavo_ECMWF_bot', fail: '😔 Не удалось нарисовать картинку, попробуйте позже.' },
  uz: { btn: '🖼 15 kunlik prognoz rasmi', t: '{n} · 15 kunlik prognoz', p: 'Yog‘in ehtimoli, %', hi: 'Kunduzi, °C', lo: 'Kechasi, °C', src: 'Osmon · ECMWF, NOAA, DWD modellari · t.me/ObHavo_ECMWF_bot', fail: '😔 Rasmni chizib bo‘lmadi, keyinroq urinib ko‘ring.' },
  en: { btn: '🖼 15-day forecast picture', t: '{n} · 15-day forecast', p: 'Chance of precipitation, %', hi: 'By day, °C', lo: 'At night, °C', src: 'Osmon · ECMWF, NOAA, DWD models · t.me/ObHavo_ECMWF_bot', fail: '😔 Could not draw the picture, try again later.' } };
const phBtn = (lang, lat, lon) => ({ text: (PHX[lang] || PHX.ru).btn, callback_data: `PH:${lang}:${(+lat).toFixed(3)}:${(+lon).toFixed(3)}` });
function chart15(X, nm, lab, D, rc, r1) {  // Chart.js 2 config as code (the label formatters are functions)
  const F = { hi: 'function(v){return (v>0?"+":"")+v+"°"}', pc: 'function(v){return v>=10?v+"%":""}', tk: 'function(v){return v+"°"}' };
  const cfg = { type: 'bar', data: { labels: lab, datasets: [
      { type: 'line', label: X.hi, data: D.map(x => r1(x.hi)), yAxisID: 't', borderColor: '#e0601b', backgroundColor: '#e0601b', borderWidth: 4, pointRadius: 6, fill: false, lineTension: 0.35, datalabels: { align: 'top', color: '#c2410c', font: { size: 22, weight: 'bold' }, formatter: '@hi' } },
      { type: 'line', label: X.lo, data: D.map(x => r1(x.lo)), yAxisID: 't', borderColor: '#3f7fd6', backgroundColor: '#3f7fd6', borderWidth: 3, pointRadius: 5, fill: false, lineTension: 0.35, datalabels: { align: 'bottom', color: '#1d4ed8', font: { size: 19, weight: 'bold' }, formatter: '@hi' } },
      { label: X.p, data: D.map(x => x.p), yAxisID: 'p', backgroundColor: D.map(rc), barPercentage: 0.75, datalabels: { anchor: 'end', align: 'start', color: '#15202b', font: { size: 18, weight: 'bold' }, formatter: '@pc' } }] },
    options: { layout: { padding: { left: 20, right: 30, top: 10, bottom: 10 } },
      title: { display: true, text: [X.t.replace('{n}', nm)], fontSize: 40, fontColor: '#14233a', fontStyle: 'bold', padding: 24 },
      legend: { position: 'bottom', labels: { fontSize: 22, fontColor: '#5b6876', padding: 26 } },
      scales: { xAxes: [{ gridLines: { display: false }, ticks: { fontSize: 20, fontColor: '#15202b' } }],
        yAxes: [{ id: 'p', position: 'right', ticks: { min: 0, max: 300, display: false }, gridLines: { display: false } },
                { id: 't', position: 'left', ticks: { fontSize: 18, fontColor: '#98a3ae', callback: '@tk', min: Math.floor(Math.min(...D.map(x => x.lo)) - 8), max: Math.ceil(Math.max(...D.map(x => x.hi)) + 4) }, gridLines: { color: '#eef1f4' } }] },
      plugins: { datalabels: { display: true } } } };
  return JSON.stringify(cfg).replace(/"@(hi|pc|tk)"/g, (m, k) => F[k]);
}
async function photo15(env, chat, lang, lat, lon, place, D) {
  const X = PHX[lang] || PHX.ru, nm = place ? pname(place, lang) : `${lat.toFixed(2)}, ${lon.toFixed(2)}`;  // no flag: the picture's font has no flags
  const lab = D.map(x => { const t = new Date(x.d + 'T12:00:00Z'); return [`${x.ic} ${WD[lang][t.getUTCDay()]}`, `${String(t.getUTCDate()).padStart(2, '0')}.${String(t.getUTCMonth() + 1).padStart(2, '0')}`]; });
  const rc = x => x.p < 10 ? '#e7edf3' : x.snow ? ['#eadcff', '#d3bcfa', '#b897f0', '#9b72e2', '#7a4bc8'][Math.min(4, Math.floor(x.p / 20))] : ['#d4e9f9', '#93c6ee', '#4a98e0', '#1c63c0', '#5b2fa8'][Math.min(4, Math.floor(x.p / 20))];
  const r1 = v => Math.round(v), chart = chart15(X, nm, lab, D, rc, r1);
  const r = await fetch('https://quickchart.io/chart/create', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ chart, width: 1920, height: 1080, devicePixelRatio: 1, backgroundColor: '#ffffff', format: 'png', version: '2' }) }).then(r => r.json()).catch(() => null);
  if (!r || !r.url) return tg(env, 'sendMessage', { chat_id: chat, text: X.fail });
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_photo' });
  const o = await tg(env, 'sendDocument', { chat_id: chat, document: r.url + '.png', caption: `🖼 ${X.t.replace('{n}', nm)}\n${X.src}`, ...(chat > 0 ? { reply_markup: { inline_keyboard: [[pvBtn(lang, lat, lon)]] } } : {}) });
  if (!o.ok) return tg(env, 'sendPhoto', { chat_id: chat, photo: r.url, caption: `🖼 ${X.t.replace('{n}', nm)}\n${X.src}` });
  return o;
}
/* ---------- 🎬 the 15-day video of a place on demand: the country's video and the place's close-up (.github/workflows/place15.yml) ---------- */
const PVX = { ru: { btn: '🎬 Видео 15 дней по часам: страна + это место', wait: '⏳ Готовлю 2 видео: вся страна и {n} крупно — осадки и температура на 15 дней по часам. Пришлю сюда минут через 15–25.', late: '😔 Видео не успело подготовиться, попробуйте ещё раз чуть позже.', capC: '🎬 {n}: вероятность осадков и температура на 15 дней по часам', capP: '📍 {n}: вероятность осадков и температура на 15 дней по часам', busy: '⏳ Видео уже готовится, пришлю, как будет готово.', fail: '😔 Не удалось запустить подготовку видео, попробуйте позже.' },
  uz: { btn: '🎬 15 kunlik soatma-soat video: davlat + shu joy', wait: '⏳ 2 ta video tayyorlayapman: butun davlat va {n} yaqindan — 15 kunga soatma-soat yog‘in va harorat. 15–25 daqiqada shu yerga yuboraman.', late: '😔 Video tayyor bo‘lmadi, birozdan keyin qayta urinib ko‘ring.', capC: '🎬 {n}: 15 kunga soatma-soat yog‘in ehtimoli va harorat', capP: '📍 {n}: 15 kunga soatma-soat yog‘in ehtimoli va harorat', busy: '⏳ Video tayyorlanmoqda, tayyor bo‘lishi bilan yuboraman.', fail: '😔 Videoni tayyorlashni boshlab bo‘lmadi, keyinroq urinib ko‘ring.' },
  en: { btn: '🎬 15-day hourly video: country + this place', wait: '⏳ Preparing 2 videos: the whole country and {n} close up — precipitation and temperature for 15 days by the hour. I will send them here in 15–25 minutes.', late: '😔 The video was not ready in time, please try again a little later.', capC: '🎬 {n}: chance of precipitation and temperature for 15 days by the hour', capP: '📍 {n}: chance of precipitation and temperature for 15 days by the hour', busy: '⏳ The video is being prepared, I will send it when it is ready.', fail: '😔 Could not start the video, try again later.' } };
const pvBtn = (lang, lat, lon) => ({ text: (PVX[lang] || PVX.ru).btn, callback_data: `PV:${lang}:${(+lat).toFixed(3)}:${(+lon).toFixed(3)}`, style: 'primary' });
async function placeVideo(env, chat, lang, lat, lon) {
  const X = PVX[lang] || PVX.ru, key = `pv_${chat}`, last = +(await kv(env, key) || 0);
  if (Date.now() - last < 8 * 60e3) return tg(env, 'sendMessage', { chat_id: chat, text: X.busy });
  const p = await nearestPlace(env, lat, lon, 25), name = p ? pname(p, lang) : `${lat.toFixed(2)}, ${lon.toFixed(2)}`;
  const r = await ghApi(env, 'actions/workflows/place15.yml/dispatches', { method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ ref: 'main', inputs: { lat: String(lat), lon: String(lon), name, iso: p ? p[4] : '', lang: lang === 'uz' ? 'uz' : 'ru', chat: String(chat) } }) });
  if (!r.ok) { console.log('place15', r.status, await r.text()); return tg(env, 'sendMessage', { chat_id: chat, text: X.fail }); }
  await setKv(env, key, String(Date.now()));
  const pend = JSON.parse((await kv(env, 'pv_pend')) || '[]').filter(x => x.c !== String(chat) && Date.now() - x.t < 90 * 60e3);
  pend.push({ c: String(chat), l: lang, n: name, cn: p && NAMES[p[4]] ? NAMES[p[4]][lang] : '', t: Date.now() }); await setKv(env, 'pv_pend', JSON.stringify(pend));
  return tg(env, 'sendMessage', { chat_id: chat, text: X.wait.replace('{n}', name) });
}
// the on-demand videos are made by GitHub (place15.yml → branch od-<chat>); every cron run the bot looks for the finished ones and sends them
async function pvTick(env) {
  const pend = JSON.parse((await kv(env, 'pv_pend')) || '[]'); if (!pend.length) return;
  const keep = [];
  for (const x of pend) {
    const X = PVX[x.l] || PVX.ru;
    const b = await ghApi(env, `branches/od-${x.c}`).then(r => r.ok ? r.json() : null).catch(() => null);
    const sha = b && b.commit && b.commit.sha, when = b && Date.parse(b.commit.commit.committer.date);
    if (!sha || when < x.t) { if (Date.now() - x.t < 75 * 60e3) keep.push(x); else await tg(env, 'sendMessage', { chat_id: x.c, text: X.late }); continue; }
    const tree = await ghApi(env, `git/trees/${sha}`).then(r => r.ok ? r.json() : null).catch(() => null);
    const files = ((tree && tree.tree) || []).map(f => f.path).filter(f => f.endsWith('.mp4')).sort((a, c) => (a.startsWith('place') ? 1 : 0) - (c.startsWith('place') ? 1 : 0));
    for (const f of files) {
      const r = await tg(env, 'sendVideo', { chat_id: x.c, video: `https://raw.githubusercontent.com/${REPO}/${sha}/${f}`, supports_streaming: true, width: 1920, height: 1080,
        caption: (f.startsWith('place') ? X.capP.replace('{n}', x.n) : X.capC.replace('{n}', x.cn || x.n)) });
      if (!r.ok) console.log('pv send', x.c, f, r.description);
    }
    await setKv(env, `pv_${x.c}`, '0');
  }
  await setKv(env, 'pv_pend', JSON.stringify(keep));
}
// the data stopped updating (the GitHub workflow failed): tell the bot's admin, at most every 12 hours
// every morning at 09:00 (Tashkent): how many people used the bot and the site
async function statsTick(env) {
  const now = new Date(Date.now() + TZ * 3600e3); if (now.getUTCHours() < 9) return;
  const day = now.toISOString().slice(0, 10), admin = await kv(env, 'admin');
  if (!admin || (await kv(env, 'stats_day')) === day) return;
  await setKv(env, 'stats_day', day);
  const since = new Date(Date.now() - 864e5).toISOString(), one = async (q, ...a) => (await env.DB.prepare(q).bind(...a).first()) || {};
  const tot = await one('SELECT COUNT(*) AS n FROM users'), act = await one('SELECT COUNT(*) AS n FROM users WHERE seen > ?1', since), neu = await one('SELECT COUNT(*) AS n FROM users WHERE first > ?1', since);
  const grp = await one("SELECT COUNT(*) AS n FROM subs WHERE type <> 'private'"), prv = await one("SELECT COUNT(*) AS n FROM subs WHERE type = 'private'");
  const langs = (await env.DB.prepare('SELECT lang, COUNT(*) AS n FROM users WHERE seen > ?1 GROUP BY lang ORDER BY n DESC').bind(since).all()).results;
  let site = '';
  try { const y = new Date(Date.now() - 864e5).toISOString().slice(0, 10); const h = await one('SELECT COALESCE(SUM(n),0) AS n FROM hits WHERE day = ?1', y); site = `\n🌐 Сайт за вчера: ${h.n}`; } catch (e) { /* no visits table yet */ }
  try { const S = await searchStats(env, 1); if (S.tot) site += `\n🔎 Поиск: ${S.tot} — ${S.top.slice(0, 5).map(x => `${esc(x.q)} ${x.n}`).join(', ')}${S.miss.length ? ` · не нашлось: ${S.miss.slice(0, 3).map(x => esc(x.q)).join(', ')}` : ''}`; } catch (e) { /* no searches yet */ }
  try { const V = await (await fetch(`${base(env)}/prob/verify/index.json`)).json(); const o = V.uz || V.overall; if (o) site += `\n🎯 Точность (30 дн.): осадки ${o.rain}%, температура ±${o.t_mae}°`; } catch (e) { /* not yet */ }
  await tg(env, 'sendMessage', { chat_id: admin, text: `📊 <b>Бот за сутки</b> (${day})\n👤 Заходили: <b>${act.n}</b>\n🆕 Новых: <b>${neu.n}</b>\n👥 Всего пользователей: ${tot.n}\n💬 Групп и каналов: ${grp.n}\n🔔 Личных подписок: ${prv.n}\n🗣 Языки: ${langs.map(x => `${x.lang || '?'} ${x.n}`).join(', ') || '—'}${site}\n\n/users — список`, parse_mode: 'HTML' });
}
// GitHub often skips scheduled runs: the worker starts the site build itself every 3 hours (needs the GH_TOKEN secret)
// a copy of the bot's database (users, subscriptions, settings) sent to the admin as a file every night at 03:00
async function backupTick(env) {
  if (!env.DB) return;
  const now = new Date(Date.now() + TZ * 3600e3); if (now.getUTCHours() < 3) return;
  const day = now.toISOString().slice(0, 10), admin = await kv(env, 'admin');
  if (!admin || (await kv(env, 'backup_day')) === day) return;
  await setKv(env, 'backup_day', day);
  const dump = {};
  for (const t of ['users', 'subs', 'meta']) { try { dump[t] = (await env.DB.prepare(`SELECT * FROM ${t}`).all()).results; } catch (e) { dump[t] = []; } }
  dump.meta = dump.meta.filter(r => !/^(guide|alert_|build_at)/.test(r.k));
  const fd = new FormData();
  fd.append('chat_id', admin); fd.append('caption', `💾 Резервная копия базы бота · ${day}\nПользователей: ${dump.users.length}, подписок: ${dump.subs.length}`);
  fd.append('disable_notification', 'true');
  fd.append('document', new Blob([JSON.stringify(dump, null, 1)], { type: 'application/json' }), `osmon_backup_${day}.json`);
  await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendDocument`, { method: 'POST', body: fd });
}
// the second safety net for the site builds (the first is the hourly knock in .github/workflows/update.yml): this worker's
// own cron, which never skips, looks at when the live site was built (site/build.json). Over 3.5 h old and no build
// running → it starts a new build itself (needs the GH_TOKEN secret: a GitHub token with Actions read & write for this
// repository) and tells the admin; when the fresh data is on the site, it says so too.
const REPO = 'otabekvafoev92-del/ob-havo-ecmwf';
async function ghApi(env, path, init = {}) {
  return fetch(`https://api.github.com/repos/${REPO}/${path}`, { ...init, headers: { 'user-agent': 'osmon-bot', accept: 'application/vnd.github+json',
    ...(env.GH_TOKEN ? { authorization: `Bearer ${env.GH_TOKEN}` } : {}), ...(init.headers || {}) } });
}
// a newer complete forecast run (00/12 UTC: ECMWF ENS, AIFS ENS and GEFS all to 15 days) than the one on the site
async function newRunReady(env, model) {
  const now = Date.now(), H = 3600e3;
  let r = Math.floor(now / (12 * H)) * 12 * H; if (now - r < 7.4 * H) r -= 12 * H;  // they are complete ~7.5 h after the run
  if (model && Date.parse(model) >= r) return false;
  const k = new Date(r).toISOString(), d = k.slice(0, 10).replace(/-/g, ''), h = k.slice(11, 13);
  if ((await kv(env, 'run_seen')) === k) return true;
  const urls = [`https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com/${d}/${h}z/ifs/0p25/enfo/${d}${h}0000-360h-enfo-ef.index`,
    `https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com/${d}/${h}z/aifs-ens/0p25/enfo/${d}${h}0000-360h-enfo-pf.index`,
    `https://noaa-gefs-pds.s3.amazonaws.com/gefs.${d}/${h}/atmos/pgrb2ap5/gep30.t${h}z.pgrb2a.0p50.f360.idx`];
  for (const u of urls) if (!(await fetch(u, { method: 'HEAD' }).then(x => x.ok).catch(() => false))) return false;
  await setKv(env, 'run_seen', k); return true;
}
async function staleTick(env) {
  const admin = await kv(env, 'admin');
  const B = await fetch(`${base(env)}/build.json?t=${Date.now()}`).then(r => r.ok ? r.json() : null).catch(() => null);
  if (!B || !B.built) return;  // the stamp comes with the first build after this change
  const built = Date.parse(B.built), age = (Date.now() - built) / 3600e3;
  const kicked = +(await kv(env, 'kick_at') || 0);
  // a build we started has reached the site: good news, once
  if (kicked && built > kicked) {
    await setKv(env, 'kick_at', '');
    if (admin && (await kv(env, 'kick_why')) === 'stale') await tg(env, 'sendMessage', { chat_id: admin, text: `✅ Данные обновлены после перезапуска: сайт собран ${tkt(B.built)} по Ташкенту.` });
    return;
  }
  if (age < 3.5 && !(await newRunReady(env, B.model))) return;  // old site, or a newer forecast is out: build
  if (kicked && Date.now() - kicked < 100 * 60e3) return;  // a build we started is still on its way (they take 40–80 min)
  const runs = await ghApi(env, 'actions/workflows/update.yml/runs?per_page=5').then(r => r.ok ? r.json() : null).catch(() => null);
  const busy = runs && (runs.workflow_runs || []).find(r => r.status === 'in_progress' || r.status === 'queued' || r.status === 'pending' || r.status === 'waiting');
  if (busy) {  // GitHub is building already: only worry when it hangs
    const mins = (Date.now() - Date.parse(busy.run_started_at || busy.created_at)) / 60e3;
    if (mins > 150 && admin && Date.now() - +(await kv(env, 'hang_at') || 0) > 6 * 3600e3) {
      await setKv(env, 'hang_at', String(Date.now()));
      await tg(env, 'sendMessage', { chat_id: admin, text: `⚠️ Сборка сайта идёт уже ${Math.round(mins)} мин (обычно 40–80). Посмотреть: ${busy.html_url}`, disable_web_page_preview: true });
    }
    return;
  }
  const last = runs && (runs.workflow_runs || [])[0], why = last && last.conclusion && last.conclusion !== 'success' ? ` Последняя сборка: ${last.conclusion}.` : '';
  if (env.GH_TOKEN) {
    const r = await ghApi(env, 'actions/workflows/update.yml/dispatches', { method: 'POST', body: JSON.stringify({ ref: 'main' }), headers: { 'content-type': 'application/json' } });
    await setKv(env, 'kick_at', String(Date.now())); await setKv(env, 'kick_why', age >= 3.5 ? 'stale' : 'run');
    if (admin && (age >= 3.5 || r.status !== 204)) await tg(env, 'sendMessage', { chat_id: admin, text: r.status === 204  // a routine new-run build: no message
      ? `🔄 Обновление было пропущено: данным на сайте ${Math.round(age)} ч.${why} Запустил новую сборку сам — данные будут примерно через 45 мин, я напишу.`
      : `⚠️ Данным ${Math.round(age)} ч, но запустить сборку не удалось (GitHub ответил ${r.status}). Проверьте токен GH_TOKEN в Cloudflare.` });
    return;
  }
  // no token: tell the admin how to fix it (at most twice a day)
  if (admin && Date.now() - +(await kv(env, 'stale_at') || 0) > 12 * 3600e3) {
    await setKv(env, 'stale_at', String(Date.now()));
    await tg(env, 'sendMessage', { chat_id: admin, text: `⚠️ Данные сайта и бота не обновлялись ${Math.round(age)} ч.${why}\nЧтобы я сам перезапускал пропущенные сборки, добавьте в Cloudflare секрет GH_TOKEN (токен GitHub с правом Actions: Read and write).` });
  }
}
const dayLabel = (d, lang) => { const dt = new Date(d + 'T12:00:00Z'); return `${WD[lang][dt.getUTCDay()]} ${String(dt.getUTCDate()).padStart(2, '0')}.${String(dt.getUTCMonth() + 1).padStart(2, '0')}`; };
const localToday = off => new Date(Date.now() + (off || 0) * 3600e3).toISOString().slice(0, 10);
function forecastText(item, lang, name, id, opt = {}) {
  const days = Object.entries((item && item.days) || {}).filter(([d]) => d >= localToday(item && item.off));
  if (!days.length) return null;
  const city = item.city ? `${item.city}: ` : '';
  const strip = t => (city && t.startsWith(city) ? t.slice(city.length) : t);
  const out = [`${FLAG[id] || '🌍'} <b>${esc(name)}</b>${item.city ? ` · ${esc(item.city)}` : ''}`];
  if (opt.updated) out.push(`<i>${T[lang].upd}: ${opt.updated}</i>`);
  out.push('');
  const [d0, d1] = days;
  out.push(`${icon(d0[1])} <b>${T[lang].tdy}, ${dayLabel(d0[0], lang)}</b>\n${esc(strip(d0[1]))}`);
  if (d1) out.push(`\n${icon(d1[1])} <b>${T[lang].tmw}, ${dayLabel(d1[0], lang)}</b>\n${esc(strip(d1[1]))}`);
  const rest = days.slice(2, 2 + (opt.more ?? 5));
  if (rest.length) {
    out.push(`\n📆 <b>${T[lang].next}</b>`);
    for (const [d, t] of rest) out.push(`${icon(t)} ${dayLabel(d, lang)} — ${esc(strip(t).replace(/\.\s.*$/, '.'))}`);
  }
  let s = out.join('\n');
  if (opt.foot) s += `\n\n${opt.foot}`;
  // Telegram counts the visible characters (tags excluded): drop later days until the caption fits
  const visible = x => x.replace(/<[^>]+>/g, '').replace(/&(amp|lt|gt);/g, '_').length;
  if (opt.limit && visible(s) > opt.limit) return (opt.more ?? 5) > 0 ? forecastText(item, lang, name, id, { ...opt, more: (opt.more ?? 5) - 1 }) : s.slice(0, opt.limit);
  return s;
}
function allDays(item, lang) {
  return Object.entries((item && item.days) || {}).filter(([d]) => d >= localToday(item && item.off)).map(([d, t]) => `${icon(t)} <b>${dayLabel(d, lang)}</b> — ${esc(t)}`).join('\n');
}

/* ---------- updates ---------- */
// ECMWF phone videos (branch ev, every 3 h): the stations over the last 6 hours, then the forecast for 12 hours or 3 days with the clouds moving
const EVRAW = 'https://raw.githubusercontent.com/otabekvafoev92-del/ob-havo-ecmwf';
const EVT = {
  ru: { t: '🎬 <b>Видео-прогноз ECMWF</b>\nТучи и осадки в движении: сначала факт метеостанций за 6 часов, затем прогноз.', b12: '🎬 12 часов', b3: '🎬 3 дня', bobs: '📡 Факт: метеостанции', byest: '📅 Как было вчера (метеостанции)', pyest: '📅 Выберите область — покажу, что было по метеостанциям вчера и сегодня:', bplace: '📍 Мой город, регион, район или посёлок', pplace: '📍 Что показать?', bcity: '🏙 Город', bregion: '🗺 Регион (область)', bdist: '📍 Район', bvil: '🏘 Посёлок / кишлак', pcity: '🏙 Выберите город:', pdreg: '📍 Сначала область:', pdist: '📍 Район:', pvil: '🏘 Напишите название посёлка после /v — например:\n<code>/v Чимган</code>\nИли отправьте 📎 геолокацию — покажу погоду в этой точке.', nf: 'Не нашёл «{q}» в Узбекистане. Попробуйте иначе написать или отправьте геолокацию.', fnow: 'сейчас', fnight: 'до {t}° к ночи', fday: 'до {t}° днём', frain: '🌧 дождь {a}–{b} ч, до {mm} мм', fsnow: '🌨 снег {a}–{b} ч, до {mm} мм', fdry: '☀️ без осадков 12 ч', ffog: '🌫 туман {a}–{b} ч', fin: 'в районе {d}', b7: '🗓 По дням: 7 дней', c7: '🗓 <b>Погода по дням: 7 дней</b>', breg: '📍 Моя область крупно', preg: '📍 Выберите область — покажу её целиком, с районами:', creg: '📍 <b>{r}</b> · прогноз на 12 часов',
        c12: '🌦 <b>Погода: 6 часов факт + 12 часов прогноз</b>', c3: '🌦 <b>Погода: 6 часов факт + 3 дня прогноз</b>', cobs: '📡 <b>Что показали метеостанции Узбекистана</b>',
        run: 'Прогон ECMWF {r} UTC · обновлено {m} по Ташкенту', wet: 'Больше всего осадков: {t} — {mm} мм', dry: 'Заметных осадков не ожидается', err: 'Видео сейчас обновляется, попробуйте через пару минут.' },
  uz: { t: '🎬 <b>ECMWF video-prognozi</b>\nBulutlar va yog‘in harakatda: avval 6 soatlik meteostansiyalar fakti, keyin prognoz.', b12: '🎬 12 soat', b3: '🎬 3 kun', bobs: '📡 Fakt: meteostansiyalar', byest: '📅 Kecha qanday bo‘ldi (meteostansiyalar)', pyest: '📅 Viloyatni tanlang — meteostansiyalar kecha va bugun nima ko‘rsatganini aytaman:', bplace: '📍 Shahrim, viloyat, tuman yoki qishloq', pplace: '📍 Nimani ko‘rsatay?', bcity: '🏙 Shahar', bregion: '🗺 Viloyat', bdist: '📍 Tuman', bvil: '🏘 Qishloq / posyolok', pcity: '🏙 Shaharni tanlang:', pdreg: '📍 Avval viloyat:', pdist: '📍 Tuman:', pvil: '🏘 Qishloq nomini /v dan keyin yozing — masalan:\n<code>/v Chimyon</code>\nYoki 📎 geolokatsiya yuboring — shu nuqtadagi ob-havoni ko‘rsataman.', nf: '«{q}» O‘zbekistonda topilmadi. Boshqacha yozib ko‘ring yoki geolokatsiya yuboring.', fnow: 'hozir', fnight: 'tunga {t}° gacha', fday: 'kunduzi {t}° gacha', frain: '🌧 yomg‘ir {a}–{b}, {mm} mm gacha', fsnow: '🌨 qor {a}–{b}, {mm} mm gacha', fdry: '☀️ 12 soat yog‘insiz', ffog: '🌫 tuman {a}–{b}', fin: '{d} tumanida', b7: '🗓 Kunlar bo‘yicha: 7 kun', c7: '🗓 <b>Kunlar bo‘yicha ob-havo: 7 kun</b>', breg: '📍 Viloyatim yaqindan', preg: '📍 Viloyatni tanlang — tumanlari bilan butunligicha ko‘rsataman:', creg: '📍 <b>{r}</b> · 12 soatlik prognoz',
        c12: '🌦 <b>Ob-havo: 6 soat fakt + 12 soat prognoz</b>', c3: '🌦 <b>Ob-havo: 6 soat fakt + 3 kun prognoz</b>', cobs: '📡 <b>O‘zbekiston meteostansiyalari nimani ko‘rsatdi</b>',
        run: 'ECMWF hisobi {r} UTC · Toshkent vaqti {m} da yangilandi', wet: 'Eng ko‘p yog‘in: {t} — {mm} mm', dry: 'Sezilarli yog‘in kutilmaydi', err: 'Video hozir yangilanmoqda, bir necha daqiqadan so‘ng urinib ko‘ring.' } };
const evKb = L => ({ inline_keyboard: [[{ text: EVT[L].b12, callback_data: `EV:${L}:12h` }, { text: EVT[L].b3, callback_data: `EV:${L}:3d` }], [{ text: EVT[L].b7, callback_data: `EV:${L}:7d` }], [{ text: EVT[L].bplace, callback_data: `EV:${L}:place` }], [{ text: EVT[L].byest, callback_data: `EV:${L}:yest` }], [{ text: EVT[L].bobs, callback_data: `EV:${L}:obs` }]] });
const EVREG = [[13, 'Ташкент', 'Toshkent sh.'], [8, 'Ташкентская', 'Toshkent vil.'], [7, 'Самаркандская', 'Samarqand'], [11, 'Бухарская', 'Buxoro'], [12, 'Кашкадарьинская', 'Qashqadaryo'],
  [6, 'Сурхандарьинская', 'Surxondaryo'], [5, 'Навоийская', 'Navoiy'], [10, 'Джизакская', 'Jizzax'], [9, 'Сырдарьинская', 'Sirdaryo'], [2, 'Ферганская', 'Farg‘ona'],
  [0, 'Андижанская', 'Andijon'], [1, 'Наманганская', 'Namangan'], [4, 'Хорезмская', 'Xorazm'], [3, 'Каракалпакстан', 'Qoraqalpog‘iston']];
const two = btns => btns.reduce((rows, b, i) => { if (i % 2 === 0) rows.push([]); rows[rows.length - 1].push(b); return rows; }, []);
const evRegKb = (L, p = 'r') => ({ inline_keyboard: two(EVREG.map(r => ({ text: L === 'uz' ? r[2] : r[1], callback_data: `EV:${L}:${p}${r[0]}` }))) });
// what the weather stations reported yesterday and today (obs branch, stations_days.json), with what it meant for going out
const EVY = {
  ru: { title: '📅 <b>{r}</b> · по метеостанциям', d0: 'Вчера', d1: 'Сегодня (до {h})', imp: ['🟢 благоприятно', '🟡 так себе', '🔴 неблагоприятно'],
        why: { fog_morning: 'утренний туман', fog: 'туман', snow: 'снег', rain_heavy: 'сильный дождь', rain: 'дождь', thunder: 'гроза', dust: 'пыль', frost: 'мороз', cold: 'холодно', heat: 'сильная жара', hot: 'жарко', storm: 'шторм', wind: 'сильный ветер' },
        none: 'Нет свежих сводок станций этой области.', fogw: '🌫 туман {h} (видимость от {v} км)', pr: '💧 {mm} мм', wind: '💨 до {w} м/с', src: 'Источник: сводки SYNOP метеостанций (ВМО), каждые 3 часа.' },
  uz: { title: '📅 <b>{r}</b> · meteostansiyalar bo‘yicha', d0: 'Kecha', d1: 'Bugun ({h} gacha)', imp: ['🟢 qulay', '🟡 o‘rtacha', '🔴 noqulay'],
        why: { fog_morning: 'ertalabki tuman', fog: 'tuman', snow: 'qor', rain_heavy: 'kuchli yomg‘ir', rain: 'yomg‘ir', thunder: 'momaqaldiroq', dust: 'chang', frost: 'sovuq', cold: 'salqin', heat: 'kuchli issiq', hot: 'issiq', storm: 'bo‘ron', wind: 'kuchli shamol' },
        none: 'Bu viloyat stansiyalaridan yangi xabar yo‘q.', fogw: '🌫 tuman {h} (ko‘rinish {v} km dan)', pr: '💧 {mm} mm', wind: '💨 {w} m/s gacha', src: 'Manba: meteostansiyalar SYNOP xabarlari (JMT), har 3 soatda.' } };
async function evYesterday(env, chat, L, rid) {
  const X = EVY[L], back = { inline_keyboard: [[{ text: EVT[L].byest, callback_data: `EV:${L}:yest` }]] };
  let D = null; try { D = await (await fetch(`${EVRAW}/obs/stations_days.json?t=${Math.floor(Date.now() / 300e3)}`)).json(); } catch (e) {}
  const ws = D && D.regions && D.regions[rid] || [], reg = EVREG.find(r => String(r[0]) === rid) || [0, '', ''];
  if (!ws.length) return tg(env, 'sendMessage', { chat_id: chat, text: X.none, reply_markup: back });
  const f = v => v == null ? '—' : (v > 0 ? '+' : '') + Math.round(v), out = [X.title.replace('{r}', L === 'uz' ? reg[2] : reg[1])];
  for (const w of ws.slice(0, 6)) {
    const s = D.stations[w]; out.push('', `<b>${s[L] || s.ru}</b>`);
    D.days.forEach((day, i) => {
      const d = s.days[day]; if (!d) return;
      const bits = [`${f(d.t_min)}…${f(d.t_max)}°`];
      if (d.pr != null && d.pr > 0) bits.push(X.pr.replace('{mm}', String(d.pr).replace('.', ',')));
      if (d.fog_hours.length) bits.push(X.fogw.replace('{h}', String(d.fog_hours[0]).padStart(2, '0') + '–' + String(d.fog_hours[d.fog_hours.length - 1] + 3).padStart(2, '0')).replace('{v}', String(d.vis_min).replace('.', ',')));
      if (d.wind_max >= 8) bits.push(X.wind.replace('{w}', d.wind_max));
      const why = d.why.map(k => X.why[k] || k).join(', ');
      out.push(`${i === 0 ? X.d0 : X.d1.replace('{h}', d.last)}: ${bits.join(' · ')} — ${X.imp[d.impact]}${why ? ' (' + why + ')' : ''}`);
    });
  }
  out.push('', `<i>${X.src}</i>`);
  return tg(env, 'sendMessage', { chat_id: chat, text: out.join('\n').slice(0, 4000), parse_mode: 'HTML', reply_markup: back });
}
async function evPoints(env) { try { return await (await fetch(`${EVRAW}/ev/points.json?t=${Math.floor(Date.now() / 300e3)}`)).json(); } catch (e) { return null; } }
function evCaption(L, P, name, s, dname) {  // a point's next 12 hours in a few lines
  const X = EVT[L], hrs = P.hours, t = s.t, n = t.length, f = v => (v > 0 ? '+' : '') + Math.round(v);
  const out = [`📍 <b>${name}</b>${dname ? ' · ' + X.fin.replace('{d}', dname) : ''}`, `🌡 ${X.fnow} ${f(t[0])}° · ` + (Math.min(...t) < t[0] - 1 ? X.fnight.replace('{t}', f(Math.min(...t))) : X.fday.replace('{t}', f(Math.max(...t))))];
  const wet = s.pr.map((v, i) => v >= 0.1 ? i : -1).filter(i => i >= 0);
  if (wet.length) { const mm = s.pr.reduce((a, b) => a + b, 0), snow = t[wet[0]] <= 0.5; out.push((snow ? X.fsnow : X.frain).replace('{a}', hrs[wet[0]]).replace('{b}', hrs[Math.min(n - 1, wet[wet.length - 1] + 1)] || hrs[n - 1]).replace('{mm}', mm < 1 ? mm.toFixed(1) : Math.round(mm))); }
  else out.push(X.fdry);
  const fg = s.fog.map((v, i) => v >= 0.5 ? i : -1).filter(i => i >= 0);
  if (fg.length) out.push(X.ffog.replace('{a}', hrs[fg[0]]).replace('{b}', hrs[Math.min(n - 1, fg[fg.length - 1] + 1)]));
  return out.join('\n');
}
function evNearest(P, lon, lat) {  // the district nearest to a point (its centre)
  let best = null;
  for (const [rid, ds] of Object.entries(P.districts || {})) for (let j = 0; j < ds.length; j++) { const d = ds[j], q = (d.c[0] - lon) ** 2 * 0.57 + (d.c[1] - lat) ** 2; if (!best || q < best.q) best = { rid, j, q }; }
  return best;
}
async function evPlaceVideo(env, chat, L, rid, caption) {  // the region's video with the place's forecast under it
  const X = EVT[L]; let meta = {}; try { meta = await (await fetch(`${EVRAW}/ev/meta.json?t=${Math.floor(Date.now() / 300e3)}`)).json(); } catch (e) {}
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
  const r = await tg(env, 'sendVideo', { chat_id: chat, video: `${EVRAW}/ev/reg/${rid}_${L}.mp4?v=${encodeURIComponent(meta.made || Math.floor(Date.now() / 1800e3))}`, caption: caption.slice(0, 1000), parse_mode: 'HTML', supports_streaming: true, width: 1080, height: 1920, reply_markup: evKb(L) });
  if (!r || !r.ok) return tg(env, 'sendMessage', { chat_id: chat, text: caption + '\n\n' + X.err, parse_mode: 'HTML', reply_markup: evKb(L) });
  return r;
}
async function evVillage(env, chat, lang, q, lon, lat) {  // a village by name (the places of the site) or a location
  const L = lang === 'uz' ? 'uz' : 'ru', X = EVT[L], P = await evPoints(env); if (!P) return tg(env, 'sendMessage', { chat_id: chat, text: X.err });
  let name = q;
  if (lon == null) {
    const n = norm(q), ps = (await places(env)).filter(p => p[4] === 'UZ');
    const p = ps.find(p => [p[0], p[1], p[2], p[3]].some(x => norm(x) === n)) || ps.find(p => [p[0], p[1], p[2], p[3]].some(x => norm(x).startsWith(n)));
    if (!p) return tg(env, 'sendMessage', { chat_id: chat, text: X.nf.replace('{q}', q) });
    name = pname(p, L); lat = p[5]; lon = p[6];
  }
  const b = evNearest(P, lon, lat); if (!b) return tg(env, 'sendMessage', { chat_id: chat, text: X.err });
  const d = P.districts[b.rid][b.j];
  return evPlaceVideo(env, chat, L, b.rid, evCaption(L, P, name || d[L], d, d[L]));
}
async function evMenu(env, chat, lang) {
  const L = lang === 'uz' ? 'uz' : 'ru';
  return tg(env, 'sendMessage', { chat_id: chat, text: EVT[L].t, parse_mode: 'HTML', reply_markup: evKb(L) });
}
async function sendEv(env, chat, lang, which) {
  const L = lang === 'uz' ? 'uz' : 'ru', X = EVT[L], fill = (s, o) => s.replace(/\{(\w+)\}/g, (_, k) => o[k] ?? '');
  let meta = {}; try { meta = await (await fetch(`${EVRAW}/ev/meta.json?t=${Math.floor(Date.now() / 300e3)}`)).json(); } catch (e) {}
  let url, cap;
  if (which === 'yest') return tg(env, 'sendMessage', { chat_id: chat, text: X.pyest, reply_markup: evRegKb(L, 'y') });
  if (/^y\d+$/.test(which)) return evYesterday(env, chat, L, which.slice(1));
  if (which === 'place') return tg(env, 'sendMessage', { chat_id: chat, text: X.pplace, reply_markup: { inline_keyboard: [[{ text: X.bcity, callback_data: `EV:${L}:city` }, { text: X.bregion, callback_data: `EV:${L}:regs` }], [{ text: X.bdist, callback_data: `EV:${L}:dreg` }, { text: X.bvil, callback_data: `EV:${L}:vil` }]] } });
  if (which === 'regs') return tg(env, 'sendMessage', { chat_id: chat, text: X.preg, reply_markup: evRegKb(L) });
  if (which === 'dreg') return tg(env, 'sendMessage', { chat_id: chat, text: X.pdreg, reply_markup: evRegKb(L, 'd') });
  if (which === 'vil') return tg(env, 'sendMessage', { chat_id: chat, text: X.pvil, parse_mode: 'HTML' });
  if (which === 'city' || /^[cdq]/.test(which)) {
    const P = await evPoints(env); if (!P) return tg(env, 'sendMessage', { chat_id: chat, text: X.err });
    if (which === 'city') return tg(env, 'sendMessage', { chat_id: chat, text: X.pcity, reply_markup: { inline_keyboard: two(P.towns.map((t, i) => ({ text: t[L], callback_data: `EV:${L}:c${i}` }))) } });
    if (which[0] === 'c') { const t = P.towns[+which.slice(1)]; if (!t) return; return evPlaceVideo(env, chat, L, t.rid, evCaption(L, P, t[L], t)); }
    if (which[0] === 'd') { const id = which.slice(1), ds = P.districts[id] || []; return tg(env, 'sendMessage', { chat_id: chat, text: X.pdist, reply_markup: { inline_keyboard: two(ds.map((d, j) => ({ text: d[L], callback_data: `EV:${L}:q${id}_${j}` }))) } }); }
    if (which[0] === 'q') { const [id, j] = which.slice(1).split('_'), d = (P.districts[id] || [])[+j]; if (!d) return; return evPlaceVideo(env, chat, L, id, evCaption(L, P, d[L], d)); }
  }
  if (which === 'obs') { url = `${EVRAW}/obs/obs_${L}.mp4?v=${Math.floor(Date.now() / 1800e3)}`; cap = X.cobs; }
  else if (/^r\d+$/.test(which)) {
    const id = which.slice(1), nm = (meta.regions && meta.regions[id] && meta.regions[id][L]) || (EVREG.find(r => String(r[0]) === id) || [0, '', ''])[L === 'uz' ? 2 : 1];
    url = `${EVRAW}/ev/reg/${id}_${L}.mp4?v=${encodeURIComponent(meta.made || Math.floor(Date.now() / 1800e3))}`; cap = fill(X.creg, { r: nm });
  }
  else {
    const k = which === '3d' ? '3d' : which === '7d' ? '7d' : '12h', m = meta[k] || {};
    url = `${EVRAW}/ev/${k}_${L}.mp4?v=${encodeURIComponent(meta.made || Math.floor(Date.now() / 1800e3))}`;
    const run = (meta.run || '').replace(/^(\d{4})-(\d\d)-(\d\d)T(\d\d)Z$/, '$3.$2 $4:00');
    const made = meta.made ? new Date(Date.parse(meta.made.replace(/Z$/, ':00Z')) + 5 * 3600e3) : null;
    const mt = made && !isNaN(made) ? `${String(made.getUTCDate()).padStart(2, '0')}.${String(made.getUTCMonth() + 1).padStart(2, '0')} ${String(made.getUTCHours()).padStart(2, '0')}:${String(made.getUTCMinutes()).padStart(2, '0')}` : '';
    cap = [k === '12h' ? X.c12 : k === '7d' ? X.c7 : X.c3, k === '7d' ? '' : m.wettest && m.wettest[1] >= 1 ? fill(X.wet, { t: m.wettest[0], mm: Math.round(m.wettest[1]) }) : X.dry, meta.run ? fill(X.run, { r: run, m: mt }) : ''].filter(Boolean).join('\n');
  }
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
  const r = await tg(env, 'sendVideo', { chat_id: chat, video: url, caption: cap, parse_mode: 'HTML', supports_streaming: true, width: 1080, height: 1920, reply_markup: evKb(L) });
  if (!r || !r.ok) return tg(env, 'sendMessage', { chat_id: chat, text: X.err, reply_markup: evKb(L) });
  return r;
}
async function handle(up, env) {
  if (up.my_chat_member) return memberChange(up.my_chat_member, env);
  const msg = up.message || up.channel_post, cb = up.callback_query;
  if (msg && msg.chat.type === 'private') return privateMsg(msg, env);
  if (msg && msg.text) {
    const chat = msg.chat, group = chat.type !== 'private';
    const cmd = (msg.text.trim().match(/^\/(\w+)(@\w+)?/) || [])[1];
    if (group) {
      if (cmd === 'sozla' || cmd === 'settings' || cmd === 'start') {
        if (!(await isAdmin(env, chat, msg.from, msg.sender_chat))) { const s = await sub(env, chat.id); return tg(env, 'sendMessage', { chat_id: chat.id, text: T[(s && s.lang) || 'ru'].gAdm, reply_to_message_id: msg.message_id }); }
        return tg(env, 'sendMessage', { chat_id: chat.id, text: T.uz.gLang + ' / ' + T.ru.gLang, reply_markup: langKb('GL') });
      }
      if (cmd === 'notify' || cmd === 'xabar' || cmd === 'bildirim') {
        const s = await sub(env, chat.id), lg = (s && s.lang) || 'ru';
        if (!(await isAdmin(env, chat, msg.from, msg.sender_chat))) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lg].gAdm, reply_to_message_id: msg.message_id });
        return groupNotif(env, chat.id, lg);
      }
      if (cmd === 'help') { const s = await sub(env, chat.id); return tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[(s && s.lang) || 'ru'], parse_mode: 'HTML' }); }
      if (cmd === 'bugun' || cmd === 'today') { const s = await sub(env, chat.id), regs = regionsOf(s).length ? regionsOf(s) : ['UZ']; for (const r of regs) await sendToday(env, chat.id, s ? s.lang : cmd === 'today' ? 'ru' : 'uz', r, true); return; }
      return;
    }
  }
  if (!cb) return;
  const chat = cb.message.chat, [kind, lang0, id] = cb.data.split(':'), lang = lang0 === 'tr' ? 'en' : lang0;
  if (kind === 'MA' && id === 'wkpick') { await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id }); return tg(env, 'sendMessage', { chat_id: chat.id, text: (WKX[lang] || WKX.ru).pick, reply_markup: weeksKb(lang) }); }
  if (kind === 'MA' && RKL[lang] && RKL[lang][id]) { await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id }); return handle({ message: { chat, from: cb.from, text: RKL[lang][id], message_id: cb.message.message_id } }, env); }  // a menu button = its keyboard button
  if (kind[0] === 'G') {  // group settings: GL language → GT toggle countries → GD done → GH hour
    if (!(await isAdmin(env, chat, cb.from))) return tg(env, 'answerCallbackQuery', { callback_query_id: cb.id, text: T[lang].gAdm, show_alert: true });
    const cur = await sub(env, chat.id);
    let sel = regionsOf(cur); const hour = cur && cur.post_hour != null ? cur.post_hour : POST_HOUR, last = cur && cur.last_run;
    if (kind === 'GL') { if (!sel.length) sel = ['UZ']; await saveSub(env, chat, sel, lang, last, hour); }
    if (kind === 'GT') { sel = sel.includes(id) ? sel.filter(r => r !== id) : [...sel, id]; await saveSub(env, chat, sel, lang, last, hour); }
    if (kind === 'GD' && !sel.length) return tg(env, 'answerCallbackQuery', { callback_query_id: cb.id, text: T[lang].gNone, show_alert: true });
    await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id });
    const edit = (text, kb, html) => tg(env, 'editMessageText', { chat_id: chat.id, message_id: cb.message.message_id, text, ...(kb ? { reply_markup: kb } : {}), ...(html ? { parse_mode: 'HTML' } : {}) });
    if (kind === 'GL' || kind === 'GT') return edit(T[lang].gMulti, multiKb(lang, sel));
    if (kind === 'GD') return edit(T[lang].time, timeKb(lang, hour));
    // GH: hour chosen. Today's post is sent right now; the daily ones start tomorrow
    const h = +id;
    await saveSub(env, chat, sel, lang, todayTZ(), h);
    await edit(T[lang].gSet.replace('{time}', hh(h)).replace('{name}', sel.map(r => `${FLAG[r]} ${esc(NAMES[r][lang])}`).join(', ')).replace('{lang}', T[lang].lang), null, true);
    const M = await manifest(env), me = await tg(env, 'getMe', {});
    if (M) for (const r of sel) await post(env, M, chat.id, lang, r, me.ok ? me.result.username : '');
    return groupNotif(env, chat.id, lang);  // next: what else to send here (hourly, weeks, mountains, air) — or everything at once
  }
  if (kind === 'Y' || kind === 'Z') {  // cities of a country: Y list, Z:lang:id:index one city
    await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id, ...(kind === 'Z' ? { text: ({ uz: '⏳ Tayyorlanmoqda…', ru: '⏳ Готовлю…', en: '⏳ Preparing…' })[lang] || '⏳' } : {}) });
    const [, , rid, ci] = cb.data.split(':'), C = await cities(env, rid, lang);
    if (!C || !C.cities.length) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].none });
    if (kind === 'Y' && chat.type === 'private') return cityPicker(env, chat.id, lang, rid);
    if (kind === 'Y') {
      const rows = []; C.cities.forEach((c, i) => { if (i % 3 === 0) rows.push([]); rows[rows.length - 1].push({ text: c.name, callback_data: `Z:${lang}:${rid}:${i}` }); });
      rows.push([{ text: T[lang].back, callback_data: `C:${lang}:${rid}` }]);
      return say(env, cb, { chat_id: chat.id, text: `${FLAG[rid]} <b>${NAMES[rid][lang]}</b> · ${T[lang].cPick}`, parse_mode: 'HTML', reply_markup: { inline_keyboard: rows } });
    }
    const c = C.cities[+ci]; if (!c) return;
    const kb = chat.type === 'private' ? { inline_keyboard: [[liveBtn(env, lang, rid, chat.id, true)]] } : { inline_keyboard: [[{ text: T[lang].cities, callback_data: `Y:${lang}:${rid}` }, { text: T[lang].back, callback_data: `C:${lang}:${rid}` }]] };
    const text = forecastText({ days: c.days, off: C.off, city: c.name }, lang, NAMES[rid][lang], rid, { more: c.video ? 4 : 5, limit: c.video ? 1024 : 4000 });
    if (!text) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].none, reply_markup: kb });
    if (c.video) {  // the precipitation video with this city's timeline (Uzbekistan and Kazakhstan)
      await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_video' });
      const url = `${base(env)}/prob/${c.video}?v=${fresh()}`;
      let r = await tg(env, 'sendVideo', { chat_id: chat.id, video: url, caption: text, parse_mode: 'HTML', supports_streaming: true, reply_markup: kb });
      if (!r.ok) {
        const f = await fetch(url);
        if (f.ok) {
          const fd = new FormData();
          fd.append('chat_id', String(chat.id)); fd.append('caption', text); fd.append('parse_mode', 'HTML'); fd.append('supports_streaming', 'true');
          fd.append('reply_markup', JSON.stringify(kb)); fd.append('video', new Blob([await f.arrayBuffer()], { type: 'video/mp4' }), c.video);
          r = await (await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendVideo`, { method: 'POST', body: fd })).json();
        }
      }
      if (r.ok) return;
    }
    return tg(env, 'sendMessage', { chat_id: chat.id, text, parse_mode: 'HTML', reply_markup: kb });
  }
  await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id, ...(['T', 'V', 'DC', 'Q', 'O', 'OP', 'OA'].includes(kind) ? { text: ({ uz: '⏳ Tayyorlanmoqda…', ru: '⏳ Готовлю…', en: '⏳ Preparing…' })[lang] || '⏳' } : {}) });
  if (chat.type === 'private') await saveUser(env, chat.id, who(cb.from));
  if (kind === 'S') {  // first language choice after /start: the guide, then the countries
    await saveUser(env, chat.id, { lang });
    await tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[lang], parse_mode: 'HTML', reply_markup: helpKb(lang) });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryRk(lang) });
  }
  if (kind === 'AC' && chat.type === 'private' && String(chat.id) === (await kv(env, 'admin'))) return sendChanges(env, chat.id);
  if (kind === 'AD' && chat.type === 'private' && String(chat.id) === (await kv(env, 'admin'))) return sendDynamics(env, chat.id, +(id || 14));
  if ((kind === 'AU' || kind === 'AY') && chat.type === 'private') return privateMsg({ chat, from: cb.from, message_id: cb.message.message_id, text: kind === 'AU' ? '/users' : '/yt' }, env);
  if (kind === 'EV') { await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id, text: ({ uz: '⏳ Video yuklanmoqda…', ru: '⏳ Загружаю видео…', en: '⏳ Loading the video…' })[lang] || '⏳' }); return sendEv(env, chat.id, lang, id); }
  if (kind === 'O') return sendOutlook(env, chat.id, lang);
  if (kind === 'OP') return sendOutlookPart(env, chat.id, lang, id);
  if (kind === 'CT') return sendCountries(env, chat.id, lang, id, +(cb.data.split(':')[3] || 0), cb.message && cb.message.message_id && cb.id !== '0' ? cb.message.message_id : null);
  if (kind === 'CY') return sendCountry(env, chat.id, lang, id);
  if (kind === 'CR' && NAMES[id]) { await saveUser(env, chat.id, { lang, region: id }); return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[id] || '🌍'} <b>${NAMES[id][lang]}</b> · ${T[lang].menu}`, parse_mode: 'HTML', reply_markup: replyKb(env, lang, id) }); }
  if (kind === 'WK') return weekDays(env, chat.id, lang, id);
  if (kind === 'ST') {  // the satellite in true colour: the latest clear pass as a picture, the last two days' passes as a video (tools/sat_true.py)
    const L = lang === 'uz' ? 'uz' : 'ru', v = Math.floor(Date.now() / 1800e3), cap = `🛰 ${FLAG.UZ} <b>${NAMES.UZ[lang]}</b> · ${(VHX[lang] || VHX.ru).sat}`;
    await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_photo' });
    await tg(env, 'sendPhoto', { chat_id: chat.id, photo: `${EVRAW}/sattrue/sattrue_${L}.jpg?v=${v}`, caption: cap, parse_mode: 'HTML' });
    return tg(env, 'sendVideo', { chat_id: chat.id, video: `${EVRAW}/sattrue/sattrue_${L}.mp4?v=${v}`, supports_streaming: true, width: 1920, height: 1080 }); }
  if (kind === 'VP' && NAMES[id]) return videoHub(env, chat.id, lang, id, null);
  if (kind === 'AQV') return sendAir(env, chat.id, lang, 'UZ');
  if (kind === 'CV' && NAMES[id]) {  // the 15-day clouds-and-precipitation video
    const L = lang === 'uz' ? 'uz' : 'ru', url = p15url(id, L, '_c'), X = VMX[lang] || VMX.ru;
    if (!(await fetch(url, { method: 'HEAD' }).then(r => r.ok).catch(() => false))) return tg(env, 'sendMessage', { chat_id: chat.id, text: lang === 'uz' ? 'Video tayyorlanmoqda, birozdan keyin qayta urinib ko‘ring.' : lang === 'en' ? 'The video is being made, try again a little later.' : 'Видео готовится, попробуйте чуть позже.' });
    await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_video' });
    return tg(env, 'sendVideo', { chat_id: chat.id, video: `${url}?v=${Math.floor(Date.now() / 1800e3)}`, caption: `☁️ ${FLAG[id] || ''} <b>${NAMES[id][lang]}</b> · ${X.ccap}`, parse_mode: 'HTML', supports_streaming: true, width: 1920, height: 1080 });
  }
  if (kind === 'TV' && NAMES[id]) {  // the 15-day temperature video of the place's country or continent
    const L = lang === 'uz' ? 'uz' : 'ru', url = p15url(id, L, '_t'), X = VHX[lang] || VHX.ru;
    if (!(await fetch(url, { method: 'HEAD' }).then(r => r.ok).catch(() => false))) return tg(env, 'sendMessage', { chat_id: chat.id, text: lang === 'uz' ? 'Video tayyorlanmoqda, birozdan keyin qayta urinib ko‘ring.' : lang === 'en' ? 'The video is being made, try again a little later.' : 'Видео готовится, попробуйте чуть позже.' });
    await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_video' });
    return tg(env, 'sendVideo', { chat_id: chat.id, video: `${url}?v=${Math.floor(Date.now() / 1800e3)}`, caption: `🌡 ${FLAG[id] || ''} <b>${NAMES[id][lang]}</b> · ${X.tcap}`, parse_mode: 'HTML', supports_streaming: true, width: 1920, height: 1080 });
  }
  if (kind === 'WV') { await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_video' }); return tg(env, 'sendVideo', { chat_id: chat.id, video: `${EVRAW}/weeks/weeks_${lang === 'uz' ? 'uz' : 'ru'}.mp4?v=${Math.floor(Date.now() / 3600e3)}`, caption: `📅 ${FLAG.UZ} <b>${NAMES.UZ[lang]}</b> · ${(VHX[lang] || VHX.ru).weeks}`, parse_mode: 'HTML', supports_streaming: true }); }
  if (kind === 'PH') { const [, , la, lo] = cb.data.split(':'); await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_photo' }); return pointForecast(env, chat.id, lang, +la, +lo, await nearestPlace(env, +la, +lo, 25), null, 'photo'); }
  if (kind === 'PV') { const [, , la, lo] = cb.data.split(':'); return placeVideo(env, chat.id, lang, +la, +lo); }
  if (kind === 'OA') return sendOutlookPart(env, chat.id, lang, null);
  if (kind === 'MP') return sendMountainText(env, chat.id, lang, id);
  if (kind === 'RG' && ADM.has(id)) return sendRegions(env, chat.id, lang, id);
  if (kind === 'TJ' && TRJ.has(id)) return sendTraj(env, chat.id, lang, id);
  if (kind === 'MV' && TRJ.has(id)) return sendMoist15(env, chat.id, lang, id);
  if (kind === 'DV') return id === 'xlsx' || id === 'pdf' ? sendDynXlsx(env, chat.id, lang, id) : sendDynVideo(env, chat.id, lang, id === 'weeks' ? 'weeks' : 'month');
  if (kind === 'SV' && TRJ.has(id)) return sendSat(env, chat.id, lang, id, 'clouds');  // one video: clouds and rain together (old "rain" buttons get it too)
  if (kind === 'AV' && TRJ.has(id)) {  // how much rain and snow falls (prob/moisture.py accum_video)
    const X = TJX[lang] || TJX.ru, url = `${base(env)}/prob/hr/${id}_accum_${lang === 'en' ? 'ru' : lang}.mp4`;
    if (!(await fetch(url, { method: 'HEAD' }).then(r => r.ok).catch(() => false))) return tg(env, 'sendMessage', { chat_id: chat.id, text: X.m15none });
    await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_video' });
    return tg(env, 'sendVideo', { chat_id: chat.id, video: `${url}?v=${fresh()}`, caption: `💧 ${FLAG[id]} ${NAMES[id][lang]} · ${X.accCap}`, supports_streaming: true });
  }
  if (kind === 'RX' && ADM.has(id)) {  // one district: the full forecast at its centre, named "district, region"
    const A = await adminData(env, id), d = A && A.adm2[+cb.data.split(':')[3]];
    if (d) { const r = A.adm1.find(a => a.id === d.p), nm = l => `${d.name[l] || d.name.ru}${r ? ', ' + (r.name[l] || r.name.ru) : ''}`;
      return pointForecast(env, chat.id, lang, d.c[1], d.c[0], [nm('ru'), nm('uz'), d.name.en || nm('ru'), nm('ru'), id, d.c[1], d.c[0], 0, 0]); } }
  if (kind === 'RB' && ADM.has(id)) { const A = await adminData(env, id); if (A) return tg(env, 'editMessageText', { ...regionsList(A, lang, id, chat.id), message_id: cb.message.message_id }); }
  if (kind === 'RD' && ADM.has(id)) return sendDistricts(env, chat.id, lang, id, +cb.data.split(':')[3], cb.message.message_id);
  if (chat.type !== 'private' && ['NS', 'NT', 'NO', 'MS', 'WS', 'WA', 'WX'].includes(kind) && !(await isAdmin(env, chat, cb.from)))
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].gAdm });
  if (kind === 'WS') { if (await mtnSub(env, chat.id)) await env.DB.prepare('DELETE FROM mtn WHERE chat_id = ?1').bind(chat.id).run(); else await env.DB.prepare('INSERT OR REPLACE INTO mtn (chat_id, lang, ver, added) VALUES (?1, ?2, ?3, ?4)').bind(chat.id, lang, (await kv(env, 'mtn_ver')) || '', new Date().toISOString()).run(); return groupNotif(env, chat.id, lang, cb.message.message_id); }
  if (kind === 'WA' || kind === 'WX') { await groupAll(env, chat.id, lang, kind === 'WA'); const G = GNX[lang] || GNX.ru, s0 = await sub(env, chat.id);
    return groupNotif(env, chat.id, lang, cb.message.message_id, kind === 'WA' ? G.allOn.replace('{h}', hh(s0 && s0.post_hour != null ? s0.post_hour : POST_HOUR)) : G.offAll); }
  if (kind === 'NS' && NSEC.includes(id)) return notifAsk(env, chat.id, lang, id);
  if (kind === 'NT' && NSEC.includes(id)) return notifSet(env, chat.id, lang, id, +cb.data.split(':')[3], cb.message.message_id);
  if (kind === 'NO' && NSEC.includes(id)) { await env.DB.prepare('DELETE FROM notif WHERE chat_id = ?1 AND sec = ?2').bind(chat.id, id).run(); if (chat.id < 0) { await tg(env, 'deleteMessage', { chat_id: chat.id, message_id: cb.message.message_id }); return groupNotif(env, chat.id, lang); } return tg(env, 'editMessageText', { chat_id: chat.id, message_id: cb.message.message_id, text: (NX_[lang] || NX_.ru).offT.replace('{s}', secName(id, lang)) }); }
  if (kind === 'MA') return sendMountainText(env, chat.id, lang, null);
  if (kind === 'MT') return sendMountains(env, chat.id, lang);
  if (kind === 'MS') {  // the snow signal on / off: the button under the mountains message changes with it
    const X = MTX[lang] || MTX.ru, cur = await mtnSub(env, chat.id);
    if (cur) await env.DB.prepare('DELETE FROM mtn WHERE chat_id = ?1').bind(chat.id).run();
    else await env.DB.prepare('INSERT OR REPLACE INTO mtn (chat_id, lang, ver, added) VALUES (?1, ?2, ?3, ?4)').bind(chat.id, lang, (await kv(env, 'mtn_ver')) || '', new Date().toISOString()).run();
    const old = cb.message.reply_markup && cb.message.reply_markup.inline_keyboard;  // keep the place buttons, flip only the signal button
    const kb = old ? old.map(row => row.map(x => x.callback_data && x.callback_data.startsWith('MS:') ? { text: cur ? X.sub : X.unsub, callback_data: `MS:${lang}`, ...(cur ? { style: 'success' } : {}) } : x)) : [[{ text: cur ? X.sub : X.unsub, callback_data: `MS:${lang}` }]];
    await tg(env, 'editMessageReplyMarkup', { chat_id: chat.id, message_id: cb.message.message_id, reply_markup: { inline_keyboard: kb } });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: cur ? X.off : X.on });
  }
  if (kind === 'Q') { const [, , la, lo] = cb.data.split(':'); return pointForecast(env, chat.id, lang, +la, +lo, await nearestPlace(env, +la, +lo, 5)); }
  if (kind === 'DC') {  // 15 days for one city of the country list: the same numbers as its video, and the video under it
    const [, , rid, ci] = cb.data.split(':'), C = (await cities(env, rid, lang)) || (await cities(env, rid, 'ru')), c = C && C.cities[+ci];
    if (!c || c.lat == null) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].none });
    return pointForecast(env, chat.id, lang, c.lat, c.lon, (await nearestPlace(env, c.lat, c.lon, 8)) || [c.name, c.name, c.en, c.name, rid, c.lat, c.lon, 0, 0], replyKb(env, lang, rid));
  }
  if (kind === 'H') return tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[lang], parse_mode: 'HTML', reply_markup: helpKb(lang) });
  if (kind === 'HM') {  // the main menu: the country chosen last time (or Uzbekistan)
    const uu = await getUser(env, chat.id), rid = uu && NAMES[uu.region] ? uu.region : 'UZ';
    return say(env, cb, { chat_id: chat.id, text: `${FLAG[rid]} <b>${NAMES[rid][lang]}</b> · ${T[lang].menu}`, parse_mode: 'HTML', reply_markup: menuKb(env, lang, rid) });
  }
  if (kind === 'RS') { const X = HK[lang] || HK.ru; return say(env, cb, { chat_id: chat.id, text: X.ask, reply_markup: { inline_keyboard: [[{ text: X.yes, callback_data: `RSY:${lang}`, style: 'danger' }, { text: X.no, callback_data: `HM:${lang}` }]] } }); }
  if (kind === 'RSY') {  // reset: forget the country, the place and the private daily subscription; start again from the language
    await env.DB.prepare('UPDATE users SET region = NULL, place = NULL, mode = NULL WHERE chat_id = ?1').bind(chat.id).run();
    if (chat.type === 'private') await env.DB.prepare('DELETE FROM subs WHERE chat_id = ?1').bind(chat.id).run();
    return say(env, cb, { chat_id: chat.id, text: (HK[lang] || HK.ru).done, reply_markup: langKb('S') });
  }
  if (kind === 'LQ') return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].locAsk, reply_markup: locOnce(lang) });
  if (kind === 'P') return sendGuide(env, chat.id, lang);
  if (kind === 'M') { await saveUser(env, chat.id, { lang, mode: 'contact' }); return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].admAsk }); }
  if (kind === 'L') await saveUser(env, chat.id, { lang });
  if (kind === 'C') await saveUser(env, chat.id, { lang, region: id });
  if (kind === 'B' || kind === 'BH' || kind === 'BX') {  // personal daily forecast in the private chat
    const cur = await sub(env, chat.id), nm = `${FLAG[id] || ''} ${NAMES[id] ? NAMES[id][lang] : ''}`;
    if (kind === 'BX') { await env.DB.prepare('DELETE FROM subs WHERE chat_id = ?1').bind(chat.id).run(); return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].subOff }); }
    if (kind === 'B') {
      const kb = timeKb(lang, cur && regionsOf(cur)[0] === id ? cur.post_hour ?? POST_HOUR : -1);
      kb.inline_keyboard.forEach(row => row.forEach(b => { b.callback_data = `BH:${lang}:${id}:${b.callback_data.split(':')[2]}`; }));
      if (cur) kb.inline_keyboard.push([{ text: T[lang].unsub, callback_data: `BX:${lang}:${id}` }]);
      return say(env, cb, { chat_id: chat.id, text: T[lang].subAsk.replace('{name}', nm), reply_markup: kb });
    }
    const h = +cb.data.split(':')[3];
    await saveSub(env, chat, [id], lang, todayTZ(), h);
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].subOk.replace('{time}', hh(h)).replace('{name}', nm), reply_markup: menuKb(env, lang, id) });
  }
  if (kind === 'L') return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryRk(lang, (await getUser(env, chat.id) || {}).region) });
  if (kind === 'C') return say(env, cb, { chat_id: chat.id, text: `${FLAG[id]} <b>${NAMES[id][lang]}</b> · ${T[lang].menu}`, parse_mode: 'HTML', reply_markup: menuKb(env, lang, id) });
  if (kind === 'T') return sendHourly(env, chat.id, lang, id);
  const M = await manifest(env);
  const items = M ? M.items.filter(i => i.region === id && i.lang === lang) : [];
  if (!items.length) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].none });
  const days = items.find(i => i.product === 'days');
  if (kind === 'D') return cityPicker(env, chat.id, lang, id);
  if (kind === 'D_old') {  // 15 days: first choose where — a city of this country, my place, or any town in the world by name
    const C = (await cities(env, id, lang)) || (await cities(env, id, 'ru'));
    const uu = await getUser(env, chat.id), pl = uu && uu.place ? JSON.parse(uu.place) : null, near = pl ? await nearestPlace(env, pl[0], pl[1], 40) : null;
    const rows = [];
    if (pl) rows.push([{ text: `📍 ${near ? pname(near, lang) : DK[lang].mine}`, callback_data: `Q:${lang}:${(+pl[0]).toFixed(3)}:${(+pl[1]).toFixed(3)}`, style: 'success' }]);
    (C ? C.cities.slice(0, 21) : []).forEach((c, i) => { if (c.lat == null) return; if (!rows.length || rows[rows.length - 1].length === 3 || (pl && rows.length === 1)) rows.push([]); rows[rows.length - 1].push({ text: c.name, callback_data: `DC:${lang}:${id}:${i}` }); });
    rows.push([{ text: DK[lang].loc, callback_data: `LQ:${lang}` }, { text: DK[lang].other, callback_data: `L:${lang}` }]);
    rows.push([{ text: T[lang].back, callback_data: `C:${lang}:${id}` }, { text: (HK[lang] || HK.ru).home, callback_data: `HM:${lang}` }]);
    if (rows.length <= 2 && !C) return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[id]} <b>${NAMES[id][lang]}</b>\n\n${allDays(days, lang)}`, parse_mode: 'HTML', reply_markup: menuKb(env, lang, id) });
    return say(env, cb, { chat_id: chat.id, text: `${FLAG[id]} <b>${NAMES[id][lang]}</b> · ${DK[lang].ask}`, parse_mode: 'HTML', reply_markup: { inline_keyboard: rows } });
  }
  if (kind === 'V') {
    let vids = ['prob', 'temp', 'cloud', 'wind'].map(p => items.find(i => (i.product || 'prob') === p)).filter(Boolean);
    if (!vids.length) vids = ['prob', 'temp', 'cloud', 'wind'].map(p => M.items.find(i => i.region === id && i.lang === 'ru' && (i.product || 'prob') === p)).filter(Boolean);
    const nv = await newVids(id, lang);  // the new look first: chance of precipitation, temperature, clouds
    const media = nv.length ? nv.map(u => ({ type: 'video', media: `${u}?v=${Math.floor(Date.now() / 1800e3)}`, supports_streaming: true })) : vids.map(v => ({ type: 'video', media: `${base(env)}/prob/${v.video}?v=${fresh()}`, supports_streaming: true }));
    media[0].caption = forecastText(days, lang, NAMES[id][lang], id, { more: 3, limit: 1000 }) || `${NAMES[id][lang]} · ${T[lang].d15}`;
    media[0].parse_mode = 'HTML';
    await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_video' });
    let r = await tg(env, 'sendMediaGroup', { chat_id: chat.id, media });
    // Telegram could not take them by link: the two lightest ones (uploading from here breaks on big files)
    if (!r.ok) { console.log('album', chat.id, id, r.description); const m2 = media.slice(-2); m2[0] = { ...m2[0], caption: media[0].caption, parse_mode: 'HTML' }; r = await tg(env, 'sendMediaGroup', { chat_id: chat.id, media: m2 }); }
    if (!r.ok) await tg(env, 'sendMessage', { chat_id: chat.id, text: `${T[lang].none}\n(${r.description || r.error_code || '?'})` });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].menu, reply_markup: menuKb(env, lang, id) });
  }
}

/* ---------- private chat: commands, guide and messages to the bot's admin ---------- */
async function privateMsg(msg, env) {
  const chat = msg.chat, text = msg.text || '', cmd = (text.trim().match(/^\/(\w+)(@\w+)?/) || [])[1];
  const u = await getUser(env, chat.id), lang = (u && T[u.lang] && u.lang) || (/^ru/.test(msg.from && msg.from.language_code || '') ? 'ru' : /^uz/.test(msg.from && msg.from.language_code || '') || !(msg.from && msg.from.language_code) ? 'uz' : 'en');
  await saveUser(env, chat.id, who(msg.from));
  if (cmd === 'v') { const q = text.replace(/^\/v(@\w+)?\s*/, '').trim(); if (!q) return evMenu(env, chat.id, lang === 'uz' ? 'uz' : 'ru').then(() => sendEv(env, chat.id, lang, 'vil')); return evVillage(env, chat.id, lang, q); }
  const admin = await kv(env, 'admin');
  // the admin answers a user: Reply to the forwarded message
  if (admin && String(chat.id) === admin && msg.reply_to_message && !cmd) {
    const to = env.DB && await env.DB.prepare('SELECT chat, lang FROM msgmap WHERE mid = ?1').bind(msg.reply_to_message.message_id).first();
    if (to) {
      const L = T[to.lang] ? to.lang : 'ru';
      await tg(env, 'sendMessage', { chat_id: to.chat, text: T[L].admAns });
      const r = await tg(env, 'copyMessage', { chat_id: to.chat, from_chat_id: chat.id, message_id: msg.message_id });
      const gone = !r.ok && /blocked|deactivated|chat not found|kicked/i.test(r.description || '');
      if (gone) for (const q of ['DELETE FROM subs WHERE chat_id = ?1', 'DELETE FROM notif WHERE chat_id = ?1', 'DELETE FROM mtn WHERE chat_id = ?1', 'UPDATE watch SET on_ = 0 WHERE chat_id = ?1']) await env.DB.prepare(q).bind(to.chat).run().catch(() => {});
      return tg(env, 'sendMessage', { chat_id: chat.id, text: r.ok ? '✅ Доставлено' : gone ? '🚫 Пользователь заблокировал бота или удалил аккаунт — ответ не доставлен. Рассылки ему отключены.' : `⚠️ Не доставлено: ${r.description || ''}`, reply_to_message_id: msg.message_id });
    }
  }
  if (cmd === 'cancel') { await saveUser(env, chat.id, { mode: '' }); return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].cancel }); }
  // the weather watch at the person's place: the answers to "where are you now?", then the question itself at each entry
  { const W = WX[lang] || WX.ru, wt = text.trim();
    if (wt === W.off) { await watchSet(env, chat.id, { on_: 0, asked: todayTZ() }); return tg(env, 'sendMessage', { chat_id: chat.id, text: W.offOk, reply_markup: replyKb(env, lang, (u && NAMES[u.region] && u.region) || 'UZ') }); }
    if (wt.startsWith(W.sameP)) { const w = await watchGet(env, chat.id); await watchSet(env, chat.id, { on_: 1, asked: todayTZ() });
      return tg(env, 'sendMessage', { chat_id: chat.id, text: W.onOk.replace('{p}', (w && w.name) || '📍'), parse_mode: 'HTML', reply_markup: replyKb(env, lang, (u && NAMES[u.region] && u.region) || 'UZ') }); }
    if (u && u.lang && !msg.location && !['now', 'loc'].includes(rkAct(wt)) && (cmd === 'start' || (u.seen && new Date(Date.parse(u.seen) + TZ * 3600e3).toISOString().slice(0, 10) < todayTZ()))) await watchAsk(env, chat.id, lang);
  }
  if (cmd === 'yt' && admin === String(chat.id)) {  // the YouTube / channel briefing, ready to publish
    const I = await (await fetch(`${base(env)}/prob/yt/index.json?t=${Date.now()}`)).json().catch(() => null);
    const want = (text.split(/\s+/)[1] || lang).toLowerCase(), b = I && (I.items.find(i => i.lang === want) || I.items[0]);
    if (!b) return tg(env, 'sendMessage', { chat_id: chat.id, text: '⏳ Видеообзора ещё нет.' });
    await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_video' });
    const url = `${base(env)}/prob/${b.video}?v=${fresh()}`;
    let r = await tg(env, 'sendVideo', { chat_id: chat.id, video: url, caption: b.title, supports_streaming: true });
    if (!r.ok) { const f = await fetch(url); if (f.ok) { const fd = new FormData(); fd.append('chat_id', String(chat.id)); fd.append('caption', b.title); fd.append('supports_streaming', 'true'); fd.append('video', new Blob([await f.arrayBuffer()], { type: 'video/mp4' }), `osmon_${b.lang}.mp4`); r = await (await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendVideo`, { method: 'POST', body: fd })).json(); } }
    await tg(env, 'sendPhoto', { chat_id: chat.id, photo: `${base(env)}/prob/${b.thumb}?v=${fresh()}`, caption: 'YouTube thumbnail' });
    const t = await (await fetch(`${base(env)}/prob/${b.text}`)).text().catch(() => '');
    return tg(env, 'sendMessage', { chat_id: chat.id, text: (r.ok ? '' : `⚠️ ${r.description || ''}\n${url}\n\n`) + t.slice(0, 4000), disable_web_page_preview: true });
  }
  if (cmd === 'changes' && admin === String(chat.id)) return sendChanges(env, chat.id);
  if (cmd === 'dyn' && admin === String(chat.id)) return sendDynamics(env, chat.id);
  if (cmd === 'searches' && admin === String(chat.id)) {
    const S = await searchStats(env, 7);
    return tg(env, 'sendMessage', { chat_id: chat.id, parse_mode: 'HTML', text: `🔎 <b>Поиск городов за 7 дней</b>: ${S.tot}\n\n${S.top.map((x, i) => `${i + 1}. ${esc(x.q)} — ${x.n}`).join('\n') || '—'}${S.miss.length ? `\n\n❓ <b>Не нашлось</b>:\n${S.miss.map(x => `• ${esc(x.q)} — ${x.n}`).join('\n')}` : ''}` });
  }
  if ((cmd === 'users' || text === ADMIN_BTN) && admin === String(chat.id)) {
    const rows = (await env.DB.prepare('SELECT * FROM users ORDER BY seen DESC LIMIT 100').all()).results;
    const n = (await env.DB.prepare('SELECT COUNT(*) AS n FROM users').first()).n;
    const lines = rows.map((x, i) => `${i + 1}. ${esc(x.name || '—')}${x.username ? ' @' + esc(x.username) : ''} · ${x.lang || '?'}${x.region ? ' · ' + (FLAG[x.region] || x.region) : ''} · ${tkt(x.seen)}`);
    const out = [`👤 <b>Users: ${n}</b> (last 100, время Ташкента)`, ...lines]; let buf = '';
    for (const l of out) { if ((buf + l).length > 3800) { await tg(env, 'sendMessage', { chat_id: chat.id, text: buf, parse_mode: 'HTML' }); buf = ''; } buf += l + '\n'; }
    return tg(env, 'sendMessage', { chat_id: chat.id, text: buf, parse_mode: 'HTML' });
  }
  if (cmd === 'admin') {
    if (!admin && env.DB) {  // the first one to send /admin becomes the bot's admin
      await setKv(env, 'admin', String(chat.id)); await adminMenu(env, chat.id);
      return tg(env, 'sendMessage', { chat_id: chat.id, text: '👑 Siz bot adminisiz / Вы — администратор бота.\n\nFoydalanuvchilar xabarlari shu yerga keladi. Javob berish uchun xabarga Reply qiling.\nСообщения пользователей будут приходить сюда. Чтобы ответить, нажмите «Ответить» (Reply) на сообщении.' });
    }
    if (admin === String(chat.id)) {
      const g = await env.DB.prepare("SELECT COUNT(*) AS n FROM subs WHERE type <> 'private'").first(), us = await env.DB.prepare('SELECT COUNT(*) AS n FROM users').first();
      const list = (await env.DB.prepare('SELECT title, type, region, lang, post_hour FROM subs ORDER BY added DESC LIMIT 30').all()).results;
      await adminMenu(env, chat.id);
      return tg(env, 'sendMessage', { chat_id: chat.id, reply_markup: ADMIN_KB, text: `👑 Admin  (/users — list, /yt ru|uz — YouTube briefing)\n👤 Users: ${us.n}\n👥 Groups: ${g.n}\n🔔 Daily (private): ${(await env.DB.prepare("SELECT COUNT(*) AS n FROM subs WHERE type = 'private'").first()).n}\n\n${list.map(x => `• ${x.type === 'private' ? '👤' : '👥'} ${x.title || '?'} — ${x.region} · ${x.lang} · ${hh(x.post_hour ?? POST_HOUR)}`).join('\n')}`.slice(0, 4000) });
    }
    await saveUser(env, chat.id, { lang, mode: 'contact' });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].admAsk });
  }
  let placeOnly = false;  // "Farg‘ona" typed after "write to the admin" by mistake: a town name alone is a weather question
  if (u && u.mode === 'contact' && !cmd && text && text.trim().split(/\s+/).length <= 3 && !/[?!.,]/.test(text)) {
    const q = norm(text); placeOnly = (await searchPlaces(env, text)).some(p => [p[0], p[1], p[2], p[3]].some(x => norm(x) === q));
    if (placeOnly) await saveUser(env, chat.id, { mode: '' });
  }
  if (u && u.mode === 'contact' && !cmd && !placeOnly) {  // pass the message on to the admin
    await saveUser(env, chat.id, { mode: '' });
    if (!admin) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].admOff });
    const f = msg.from || {}, who = `✉️ <b>${esc([f.first_name, f.last_name].filter(Boolean).join(' ') || '?')}</b>${f.username ? ' @' + esc(f.username) : ''} · <code>${chat.id}</code> · ${lang}`;
    const ids = [];
    if (text) { const r = await tg(env, 'sendMessage', { chat_id: admin, text: `${who}\n\n${esc(text)}`.slice(0, 4000), parse_mode: 'HTML' }); if (r.ok) ids.push(r.result.message_id); }
    else {
      const h = await tg(env, 'sendMessage', { chat_id: admin, text: who, parse_mode: 'HTML' }); if (h.ok) ids.push(h.result.message_id);
      const r = await tg(env, 'copyMessage', { chat_id: admin, from_chat_id: chat.id, message_id: msg.message_id }); if (r.ok) ids.push(r.result.message_id);
    }
    for (const id of ids) await env.DB.prepare('INSERT OR REPLACE INTO msgmap (mid, chat, lang) VALUES (?1, ?2, ?3)').bind(id, chat.id, lang).run();
    return tg(env, 'sendMessage', { chat_id: chat.id, text: ids.length ? T[lang].admSent : T[lang].admOff, reply_markup: replyKb(env, lang, (u && NAMES[u.region] && u.region) || 'UZ') });
  }
  if (cmd === 'guide') return sendGuide(env, chat.id, lang);
  if (cmd === 'alerts') { const A = await alertsData(env), rid = (u && NAMES[u.region] && u.region) || null; const it = A ? A.items.filter(i => !rid || i.region === rid) : []; return tg(env, 'sendMessage', { chat_id: chat.id, text: it.length ? alertText(it, lang) : AL[lang].none, parse_mode: 'HTML' }); }
  if (cmd === 'help') return tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[lang], parse_mode: 'HTML', reply_markup: helpKb(lang) });
  if (cmd === 'bugun' || cmd === 'today') return sendHourly(env, chat.id, u && u.lang && T[u.lang] ? u.lang : cmd === 'today' ? 'ru' : 'uz', (u && NAMES[u.region] && u.region) || 'UZ');
  if (cmd === 'prognoz') return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryRk(lang, u && u.region) });
  if (msg.location) {  // weather right here
    const { latitude: la, longitude: lo } = msg.location;
    await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'typing' });
    const np = await nearestPlace(env, la, lo), r = await pointForecast(env, chat.id, lang, la, lo, np);
    // from now on: a message when it starts to rain or snow here, a storm, great heat or frost, strong wind — not in normal weather
    await watchSet(env, chat.id, { lat: la, lon: lo, name: np ? pname(np, lang) : `${la.toFixed(2)}, ${lo.toFixed(2)}`, lang, on_: 1, asked: todayTZ() });
    await tg(env, 'sendMessage', { chat_id: chat.id, text: (WX[lang] || WX.ru).onOk.replace('{p}', esc(np ? pname(np, lang) : (WX[lang] || WX.ru).here)), parse_mode: 'HTML', reply_markup: replyKb(env, lang, (u && NAMES[u.region] && u.region) || 'UZ') });
    return r;
  }
  if (!text) return;
  // the ☰ menu (and the buttons of the old keyboard that some chats still show): one action each, no duplicates
  {
    const rid = (u && NAMES[u.region] && u.region) || 'UZ', old = k => !cmd && Object.values(MK).some(m => m[k] === text);
    const rk = !cmd && rkAct(text);
    const act = rk === 'back' ? 'home' : rk === 'loc' ? 'location' : rk || (old('today') ? 'hourly' : old('d15') ? 'days' : old('video') ? 'video' : old('more') ? 'countries' : Object.values(PT).some(m => m.locBtn === text) ? 'location' : cmd);
    const ct = !cmd && !rk && contOf(text, lang);
    if (ct) return sendCountries(env, chat.id, lang, ct, 0);
    const cid = !cmd && !rk && countryOf(text);
    if (cid) {  // a country from the keyboard: remember it and show its menu
      await saveUser(env, chat.id, { lang, region: cid });
      return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[cid]} <b>${NAMES[cid][lang]}</b> · ${T[lang].menu}`, parse_mode: 'HTML', reply_markup: replyKb(env, lang, cid) });
    }
    if (!cmd && !rk && u && u.lang) {  // a city of the chosen country from the keyboard: the same 15-day layout as a searched town
      const C = (await cities(env, rid, lang)) || null, c = C && C.cities.find(x => x.name === text.trim());
      if (c && c.lat != null) return pointForecast(env, chat.id, lang, c.lat, c.lon, (await nearestPlace(env, c.lat, c.lon, 8)) || [c.name, c.name, c.en, c.name, rid, c.lat, c.lon, 0, 0], replyKb(env, lang, rid));
      if (c) {  // older city lists without coordinates: find the town by name in this country
        const q = norm(c.en || c.name), p = (await places(env)).find(p => p[4] === rid && [p[0], p[1], p[2], p[3]].some(x => norm(x) === q || norm(x) === norm(c.name)));
        if (p) return pointForecast(env, chat.id, lang, p[5], p[6], p, replyKb(env, lang, rid));
      }
    }
    const cbk = data => handle({ callback_query: { id: '0', from: msg.from, data, message: { chat, message_id: msg.message_id } } }, env);
    const rg = !cmd && !rk && parseRange(text);
    if (rg && rg[0] <= rg[1] && (Date.parse(rg[1]) - Date.parse(rg[0])) / 864e5 <= 15) return weekDays(env, chat.id, lang, rg[0], rg[1]);
    if (cmd === 'week' || cmd === 'hafta' || cmd === 'nedelya') return tg(env, 'sendMessage', { chat_id: chat.id, text: (WKX[lang] || WKX.ru).pick, reply_markup: weeksKb(lang) });
    
    if (['rain', 'video', 'hourly', 'evv', 'traj'].includes(act)) return videoMenu(env, chat.id, lang, rid, u);  // one menu for all the videos
    if (act === 'fc' || act === 'mtnair' || act === 'settings' || act === 'more') return subMenu(env, chat.id, lang, rid, act === 'more' ? 'settings' : act, u);
    if (act === 'wkpick') return tg(env, 'sendMessage', { chat_id: chat.id, text: (WKX[lang] || WKX.ru).pick, reply_markup: weeksKb(lang) });
    if (act === 'more') return moreMenu(env, chat.id, lang, rid);
    if (act === 'traj') return TRJ.has(rid) ? sendTraj(env, chat.id, lang, rid) : cbk(`V:${lang}:${rid}`);
    if (act === 'home') return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[rid]} <b>${NAMES[rid][lang]}</b> · ${T[lang].menu}`, parse_mode: 'HTML', reply_markup: replyKb(env, lang, rid) });
    if (act === 'days' || act === 'cities') return cityPicker(env, chat.id, lang, rid, u);
    if (act === 'help') return tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[lang], parse_mode: 'HTML', reply_markup: helpKb(lang) });
    if (act === 'alerts') { const A = await alertsData(env); const it = A ? A.items.filter(i => i.region === rid) : []; return tg(env, 'sendMessage', { chat_id: chat.id, text: it.length ? alertText(it, lang) : AL[lang].none, parse_mode: 'HTML' }); }
    if (act === 'video') {  // the video that matches the last forecast: that city's own video (Uzbekistan, Kazakhstan) or the country's
      const pl = u && u.place ? JSON.parse(u.place) : null, C = pl ? await cities(env, rid, lang) : null;
      const np = pl ? await nearestPlace(env, pl[0], pl[1], 8) : null;
      const ci = C ? C.cities.findIndex(c => c.video && (c.lat != null ? Math.hypot(c.lat - pl[0], (c.lon - pl[1]) * Math.cos(pl[0] * Math.PI / 180)) < 0.12 : np && (c.en === np[2] || norm(c.name) === norm(pname(np, lang))))) : -1;
      return cbk(ci >= 0 ? `Z:${lang}:${rid}:${ci}` : `V:${lang}:${rid}`);
    }
    if (act === 'reset') return cbk(`RS:${lang}`);
    if (act === 'hourly') return sendHourly(env, chat.id, lang, rid);
    if (act === 'outlook') return rid === 'UZ' ? sendOutlook(env, chat.id, lang) : tg(env, 'sendMessage', { chat_id: chat.id, text: (WKX[lang] || WKX.ru).pick, reply_markup: weeksKb(lang) });
    if (act === 'evv') return evMenu(env, chat.id, lang);
    if (act === 'dyn') return sendDyn(env, chat.id, lang);
    if (act === 'brief') { await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'typing' }); return sendBrief(env, chat.id, lang, rid); }
    if (act === 'mtn') return sendMountains(env, chat.id, lang);
    if (act === 'regions') return sendRegions(env, chat.id, lang, ADM.has(rid) ? rid : 'UZ');
    if (act === 'air') { await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'typing' }); return sendAir(env, chat.id, lang, rid); }
    if (act === 'notif') return notifList(env, chat.id, lang);
    if (act === 'accuracy') return sendAccuracy(env, chat.id, lang);
    if (act === 'now') {  // right now at the user's place (or the country's capital), with the forecast below
      const pl = u && u.place ? JSON.parse(u.place) : null;
      if (pl) {  // just the weather right now, short; the 15 days are one button away
        const np = await nearestPlace(env, pl[0], pl[1]), c = await nowWeather(+pl[0], +pl[1]), line = nowLine(c, lang);
        if (line) return tg(env, 'sendMessage', { chat_id: chat.id, parse_mode: 'HTML', text: `${np ? `${FLAG[np[4]] || '📍'} <b>${esc(pname(np, lang))}</b>` : `📍 <b>${(+pl[0]).toFixed(2)}, ${(+pl[1]).toFixed(2)}</b>`}\n\n${line}`, reply_markup: replyKb(env, lang, rid) });
        return pointForecast(env, chat.id, lang, pl[0], pl[1], np);
      }
      return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].locAsk, reply_markup: locOnce(lang) });
    }
    if (act === 'days') return cbk(`D:${lang}:${rid}`);
    if (act === 'video') return cbk(`V:${lang}:${rid}`);
    if (act === 'cities') return cbk(`Y:${lang}:${rid}`);
    if (act === 'daily') return cbk(`B:${lang}:${rid}`);
    if (act === 'countries' || act === 'prognoz') return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryRk(lang, u && u.region) });
    if (act === 'location') return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].locAsk, reply_markup: locOnce(lang) });
    if (act === 'site') return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[rid]} ${NAMES[rid][lang]}`, reply_markup: { inline_keyboard: [[{ text: T[lang].site, web_app: { url: site(env, `prob/${rid}/${lang}/prob`) } }], [{ text: T[lang].rep, web_app: { url: site(env, 'map') } }]] } });
  }
  if (!cmd && u && u.lang && env.AI && isQuestion(text)) {  // a question in words: the assistant (falls back to the town search)
    const r = await askWeather(env, chat.id, u.lang, u, text).catch(e => { console.log('ask', e && e.stack); return null; });
    if (r) return r;
  }
  if (!cmd && u && u.lang) {  // a town name (also "погода в Самарканде завтра"): search it anywhere in the world
    const q = text.split(/\s+/).filter(w => !FILLER.has(norm(w))).join(' ').trim() || text;
    let found = await searchPlaces(env, q);
    for (const v of [q.replace(/(ом|ем|ой|ей|ах|ях|е|у|ю|а|я|и|ы)$/iu, ''), q.replace(/(dagi|da|ga|ning|ni|dan|de|da|ta|te|'?(d|t)[ae])$/iu, '')])  // "в Самарканде", "Samarqandda", "Antalya'da"
      if (!found.length && v.length >= 3 && v !== q) found = await searchPlaces(env, v);
    ctxLog(env, logSearch(env, q, found.length));
    if (found.length === 1 || (found.length && norm([found[0][0], found[0][1], found[0][2], found[0][3]].find(x => norm(x) === norm(q)) || '') === norm(q) && !found.slice(1).some(p => [p[0], p[1], p[2], p[3]].some(x => norm(x) === norm(q)))))
      return pointForecast(env, chat.id, lang, found[0][5], found[0][6], found[0]);
    if (found.length) return tg(env, 'sendMessage', { chat_id: chat.id, text: PT[lang].pick, reply_markup: { inline_keyboard: found.map(p => [{ text: `${FLAG[p[4]] || '📍'} ${pname(p, lang)}${NAMES[p[4]] ? ', ' + NAMES[p[4]][lang] : ' (' + p[4] + ')'}`, callback_data: `Q:${lang}:${p[5]}:${p[6]}` }]) } });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: PT[lang].nf + '\n\n' + T[lang].menuHint });
  }
  const kb = langKb('S');  // a returning user goes straight back to the country they chose last time
  if (u && u.region && NAMES[u.region] && T[u.lang]) kb.inline_keyboard.push([{ text: `▶️ ${FLAG[u.region]} ${NAMES[u.region][u.lang]}`, callback_data: `C:${u.lang}:${u.region}` }]);
  return tg(env, 'sendMessage', { chat_id: chat.id, text: T.uz.hi + '\n\n' + T.ru.hi.split('\n').slice(0, 2).join('\n') + '\nВыберите язык:', parse_mode: 'HTML', reply_markup: kb });
}
// ---- 🤖 the assistant: a question in words → what, where and when (Workers AI) → the numbers (Open-Meteo: forecast, ERA5 history, last year) → a short answer
// the model only reads the question and writes the answer from the numbers given to it; the numbers come from the data, never from the model
const isQuestion = t => /\?|^(будет|будут|когда|сколько|какая|какой|какие|где|почему|нужен|нужно|можно|стоит|ли|а |как |что |qachon|qancha|qanday|qayerda|bormi|kerakmi|bo‘ladimi|boladimi|yog[‘']?adimi)/i.test(t.trim()) || t.trim().split(/\s+/).length >= 5;
const AIM = '@cf/meta/llama-3.3-70b-instruct-fp8-fast';
const ASKX = { ru: { think: '🤖 Смотрю данные…', nf: 'Не понял, о каком месте или времени вопрос. Напишите, например: «будет ли дождь в Самарканде в субботу?» или «сколько осадков было в мае против прошлого года в Ташкенте?»', src: '🤖 Ответ по данным ECMWF / ERA5 (Open-Meteo). Модель, не метеостанции.' },
  uz: { think: '🤖 Ma’lumotlarni ko‘ryapman…', nf: 'Qaysi joy yoki vaqt haqida so‘rayotganingizni tushunmadim. Masalan: «shanba kuni Samarqandda yomg‘ir bo‘ladimi?» yoki «Toshkentda may oyida o‘tgan yilga nisbatan qancha yog‘in bo‘ldi?»', src: '🤖 ECMWF / ERA5 ma’lumotlari asosida (Open-Meteo). Model, meteostansiya emas.' } };
async function ai(env, messages, json) {
  const r = await env.AI.run(AIM, { messages, max_tokens: json ? 300 : 600, temperature: 0.2, ...(json ? { response_format: { type: 'json_object' } } : {}) });
  const t = r && (typeof r.response === 'string' ? r.response : JSON.stringify(r.response || ''));
  return t || '';
}
async function askWeather(env, chat, lang, u, text) {
  const L = lang === 'uz' ? 'uz' : 'ru', X = ASKX[L], today = todayTZ(), wd = new Date(today + 'T00:00:00Z').toLocaleDateString('en-GB', { weekday: 'long', timeZone: 'UTC' });
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'typing' });
  // 1. what is asked
  const q = await ai(env, [{ role: 'system', content: `Today is ${today} (${wd}), Uzbekistan. Extract from the user's weather question a JSON object: {"weather": true|false (is it about weather/climate at all), "place": place name as written or null, "from": "YYYY-MM-DD", "to": "YYYY-MM-DD" (the dates asked about; "tomorrow", "Saturday", "this week", "in May" → concrete dates; if no date: today), "compare_last_year": true|false, "metric": "temp"|"rain"|"snow"|"wind"|"all"}. Only JSON.` }, { role: 'user', content: text }], true);
  let Q; try { Q = JSON.parse(q.slice(q.indexOf('{'), q.lastIndexOf('}') + 1)); } catch (e) { return null; }
  if (!Q || Q.weather === false) return null;
  // 2. where
  let lat, lon, name;
  if (Q.place) {
    let f = await searchPlaces(env, Q.place);
    if (!f.length) f = await searchPlaces(env, String(Q.place).replace(/(ом|ем|ой|ей|ах|ях|е|у|ю|а|я|и|ы|da|dagi|ga)$/iu, ''));
    if (f.length) { lat = f[0][5]; lon = f[0][6]; name = pname(f[0], lang); }
    else for (const v of [Q.place, String(Q.place).replace(/(ом|ем|ой|ей|ах|ях|е|у|ю|а|я|и|ы|da|dagi|ga)$/iu, '')]) {  // anywhere in the world: the Open-Meteo geocoder
      const g = await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(v)}&count=1&language=${L}`).then(r => r.ok ? r.json() : null).catch(() => null);
      if (g && g.results && g.results[0]) { lat = g.results[0].latitude; lon = g.results[0].longitude; name = g.results[0].name; break; }
    }
  }
  if (lat == null) { const pl = u && u.place ? JSON.parse(u.place) : null; if (pl) { lat = +pl[0]; lon = +pl[1]; const np = await nearestPlace(env, lat, lon, 40); name = np ? pname(np, lang) : `${lat.toFixed(2)}, ${lon.toFixed(2)}`; } }
  if (lat == null) { if (Q.place) return tg(env, 'sendMessage', { chat_id: chat, text: X.nf }); [lat, lon] = BRC[u && u.region] || BRC.UZ; name = L === 'uz' ? 'Toshkent' : 'Ташкент'; }
  // 3. the numbers
  const ok = d => /^\d{4}-\d{2}-\d{2}$/.test(d || '');
  let a = ok(Q.from) ? Q.from : today, b = ok(Q.to) ? Q.to : a; if (b < a) [a, b] = [b, a];
  const day = 864e5, tD = Date.parse(today), maxF = new Date(tD + 15 * day).toISOString().slice(0, 10);
  if (b > maxF) b = maxF; if (a > b) a = b;
  if ((Date.parse(b) - Date.parse(a)) / day > 92) a = new Date(Date.parse(b) - 92 * day).toISOString().slice(0, 10);
  const V = 'temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,snowfall_sum,precipitation_probability_max,wind_gusts_10m_max';
  const loc = `latitude=${(+lat).toFixed(3)}&longitude=${(+lon).toFixed(3)}&timezone=auto&wind_speed_unit=ms`;
  const get = async (from, to) => {
    const fc = Date.parse(from) >= tD - 85 * day;  // recent and future: the forecast API (with its past days); older: the ERA5 archive
    const url = fc ? `https://api.open-meteo.com/v1/forecast?${loc}&daily=${V}&start_date=${from}&end_date=${to}&models=ecmwf_ifs025`
      : `https://archive-api.open-meteo.com/v1/archive?${loc}&daily=${V.replace(',precipitation_probability_max', '')}&start_date=${from}&end_date=${to}`;
    const j = await fetch(url).then(r => r.ok ? r.json() : null).catch(() => null); return j && j.daily ? j.daily : null;
  };
  const cur = await get(a, b); if (!cur) return null;
  const sh = d => new Date(Date.parse(d) - 364 * day).toISOString().slice(0, 10);
  const prev = Q.compare_last_year ? await get(sh(a), sh(b)) : null;
  const rows = cur.time.map((d, i) => [d, ...['temperature_2m_max', 'temperature_2m_min', 'temperature_2m_mean', 'precipitation_sum', 'snowfall_sum', 'precipitation_probability_max', 'wind_gusts_10m_max'].map(k => cur[k] ? cur[k][i] : null)]);
  const sum = (D, k) => D && D[k] ? +D[k].reduce((s, x) => s + (x || 0), 0).toFixed(1) : null, mean = (D, k) => D && D[k] ? +(D[k].filter(x => x != null).reduce((s, x) => s + x, 0) / Math.max(1, D[k].filter(x => x != null).length)).toFixed(1) : null;
  const facts = { place: name, today, period: [a, b], forecast_from: today, days: rows.length <= 31 ? rows.map(r => ({ date: r[0], tmax: r[1], tmin: r[2], tmean: r[3], rain_mm: r[4], snow_cm: r[5], rain_prob: r[6], gust_ms: r[7] })) : undefined,
    totals: { tmean: mean(cur, 'temperature_2m_mean'), rain_mm: sum(cur, 'precipitation_sum'), snow_cm: sum(cur, 'snowfall_sum'), rainy_days: cur.precipitation_sum.filter(x => x >= 1).length },
    ...(prev ? { last_year_same_weekdays: { period: [sh(a), sh(b)], tmean: mean(prev, 'temperature_2m_mean'), rain_mm: sum(prev, 'precipitation_sum'), snow_cm: sum(prev, 'snowfall_sum'), rainy_days: prev.precipitation_sum.filter(x => x >= 1).length } } : {}) };
  // 4. the answer, only from these numbers
  const ans = await ai(env, [{ role: 'system', content: `You are the weather assistant of the Telegram bot Osmon. Answer in ${L === 'uz' ? 'Uzbek (Latin script)' : 'Russian'}, briefly (2–6 short lines), friendly, with a few weather emoji. Use ONLY the numbers in DATA, never invent any; dates on or after "forecast_from" are a forecast, earlier ones are past data — say so when it matters. Round temperatures to whole degrees, rain to whole mm (or one decimal under 1 mm). If DATA cannot answer the question, say what you can tell from it. No markdown headers, no tables.` },
    { role: 'user', content: `Question: ${text}\nDATA: ${JSON.stringify(facts)}` }], false);
  if (!ans) return null;
  return tg(env, 'sendMessage', { chat_id: chat, text: `${esc(ans.trim()).slice(0, 3800)}\n\n<i>${X.src}</i>`, parse_mode: 'HTML', reply_markup: { inline_keyboard: [[{ text: L === 'uz' ? '📊 Dinamika' : '📊 Динамика', callback_data: `MA:${lang}:dyn` }, { text: L === 'uz' ? '⏱ Soatma-soat' : '⏱ По часам', callback_data: `MA:${lang}:hourly` }]] } })
    .then(r => r.ok ? r : tg(env, 'sendMessage', { chat_id: chat, text: `${ans.trim()}\n\n${X.src}`.slice(0, 4000) }));
}
// what people search for (admin statistics): daily totals per query, nothing about the person
function ctxLog(env, p) { if (env._ctx) env._ctx.waitUntil(p.catch(() => {})); else p.catch(() => {}); }
async function logSearch(env, q, n) {
  if (!env.DB) return; await db(env);
  await env.DB.prepare('INSERT INTO searches (day, q, found, n) VALUES (?1, ?2, ?3, 1) ON CONFLICT(day, q) DO UPDATE SET n = n + 1, found = ?3').bind(todayTZ(), norm(q).slice(0, 60), n ? 1 : 0).run();
}
async function searchStats(env, days = 7) {
  await db(env); const since = new Date(Date.now() + TZ * 3600e3 - days * 864e5).toISOString().slice(0, 10);
  const top = (await env.DB.prepare('SELECT q, SUM(n) AS n FROM searches WHERE day >= ?1 AND found = 1 GROUP BY q ORDER BY n DESC LIMIT 15').bind(since).all()).results;
  const miss = (await env.DB.prepare('SELECT q, SUM(n) AS n FROM searches WHERE day >= ?1 AND found = 0 GROUP BY q ORDER BY n DESC LIMIT 10').bind(since).all()).results;
  const tot = await env.DB.prepare('SELECT COALESCE(SUM(n),0) AS n FROM searches WHERE day >= ?1').bind(since).first();
  return { top, miss, tot: tot.n };
}
// forecast accuracy (prob/verify.py): the last 30 days, forecast for tomorrow against what happened
async function sendAccuracy(env, chat, lang) {
  const V = await memo('verify', 1800e3, async () => { const r = await fetch(`${base(env)}/prob/verify/index.json`, { cf: { cacheTtl: 1800 } }); return r.ok ? r.json() : null; });
  const X = { uz: { t: '🎯 <b>Prognoz aniqligi</b> (oxirgi 30 kun)', rain: 'Yog‘in bor/yo‘q to‘g‘ri topildi', temp: 'Harorat xatosi o‘rtacha', t2: '±2° ichida', city: 'Shaharlar bo‘yicha', wait: 'Tekshiruv boshlandi: ertangi prognozlar saqlanmoqda, birinchi natijalar 2–3 kunda chiqadi.', how: 'Ertangi kun prognozi (24–48 soat oldin) haqiqiy ob-havo bilan solishtiriladi: yog‘in ≥ 1 mm, ehtimol ≥ 50 % = «yog‘in».', days: 'kun' },
    ru: { t: '🎯 <b>Точность прогноза</b> (последние 30 дней)', rain: 'Угадано «будут осадки / нет»', temp: 'Средняя ошибка температуры', t2: 'в пределах ±2°', city: 'По городам', wait: 'Проверка запущена: прогнозы на завтра сохраняются, первые результаты — через 2–3 дня.', how: 'Прогноз на завтра (за 24–48 ч) сравнивается с фактической погодой: осадки ≥ 1 мм, вероятность ≥ 50 % = «будут осадки».', days: 'дн.' },
    en: { t: '🎯 <b>Forecast accuracy</b> (last 30 days)', rain: 'Rain / no rain right', temp: 'Mean temperature error', t2: 'within ±2°', city: 'Cities', wait: 'Checking has started: tomorrow’s forecasts are being saved, the first results in 2–3 days.', how: 'The forecast for tomorrow (made 24–48 h before) is compared with the real weather: precipitation ≥ 1 mm, chance ≥ 50% = «precipitation».', days: 'days' } }[lang] || null;
  const o = V && (V.uz || V.overall);
  if (!o) return tg(env, 'sendMessage', { chat_id: chat, text: `${X.t}

${X.wait}`, parse_mode: 'HTML' });
  const rows = (V.cities || []).filter(c => c.n).slice(0, 14).map(c => `${(c.name[lang] || c.name.ru).padEnd(12).slice(0, 12)} ${String(c.rain).padStart(3)}%  ±${c.t_mae ?? '—'}°`);
  const text = [X.t, '', `☂️ ${X.rain}: <b>${o.rain}%</b>`, ...(o.t_mae != null ? [`🌡 ${X.temp}: <b>±${o.t_mae}°</b> (${o.t2}% ${X.t2})`] : []), `📅 ${V.days.length} ${X.days} · ${o.n}`,
    ...(rows.length ? ['', `<b>${X.city}</b>`, `<pre>${esc(rows.join('\n'))}</pre>`] : []), `<i>${X.how}</i>`].join('\n');
  return tg(env, 'sendMessage', { chat_id: chat, text, parse_mode: 'HTML' });
}
// interactive menus: a menu message turns into the next menu in place (no new message); forecasts, videos and long texts stay
async function say(env, cb, payload) {
  const m = cb && cb.id !== '0' && cb.message;
  if (payload.reply_markup && payload.reply_markup.keyboard) {  // the answer brings the keyboard under the input: the dialog's own buttons go away
    if (m) await tg(env, 'editMessageReplyMarkup', { chat_id: payload.chat_id, message_id: m.message_id, reply_markup: { inline_keyboard: [] } });
    return tg(env, 'sendMessage', payload);
  }
  if (m && typeof m.text === 'string' && m.text.length < 260 && !/<pre>|☂️|🧥/.test(m.text)) {
    const r = await tg(env, 'editMessageText', { ...payload, message_id: m.message_id });
    if (r.ok || /not modified/.test(r.description || '')) return r;
  }
  return tg(env, 'sendMessage', payload);
}
async function kv(env, k) { if (!env.DB) return null; await db(env); const r = await env.DB.prepare('SELECT v FROM meta WHERE k = ?1').bind(k).first(); return r ? r.v : null; }
async function setKv(env, k, v) { await db(env); await env.DB.prepare('INSERT OR REPLACE INTO meta (k, v) VALUES (?1, ?2)').bind(k, v).run(); }
async function getUser(env, id) { if (!env.DB) return null; await db(env); const u = await env.DB.prepare('SELECT * FROM users WHERE chat_id = ?1').bind(id).first(); if (u && u.lang === 'tr') u.lang = 'en'; return u; }  // Turkish was replaced by English
const who = f => (f ? { name: [f.first_name, f.last_name].filter(Boolean).join(' ') || null, username: f.username || null } : {});
async function saveUser(env, id, f) {
  if (!env.DB) return; await db(env);
  await env.DB.prepare('INSERT INTO users (chat_id, lang, mode, name, seen, region, username, place, first) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?5) ON CONFLICT(chat_id) DO UPDATE SET lang = COALESCE(?2, lang), mode = COALESCE(?3, mode), name = COALESCE(?4, name), seen = ?5, region = COALESCE(?6, region), username = COALESCE(?7, username), place = COALESCE(?8, place)')
    .bind(id, f.lang ?? null, f.mode ?? null, f.name ?? null, new Date().toISOString(), f.region ?? null, f.username ?? null, f.place ?? null).run();
  if (id > 0) await env.DB.prepare('INSERT OR IGNORE INTO daily (day, chat_id) VALUES (?1, ?2)').bind(todayTZ(), id).run();  // people only, not groups
}
// the PDF guide: uploaded once from the repository, then re-sent by Telegram's file_id
const GUIDE_V = 3;
async function sendGuide(env, chat, lang) {
  const key = `guide${GUIDE_V}_${lang}`, fid = await kv(env, key);
  if (fid) { const r = await tg(env, 'sendDocument', { chat_id: chat, document: fid, caption: T[lang].guideCap }); if (r.ok) return r; }
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_document' });
  const f = await fetch(`https://raw.githubusercontent.com/otabekvafoev92-del/ob-havo-ecmwf/main/telegram/guide/osmon_guide_${lang}.pdf`);
  if (!f.ok) return tg(env, 'sendMessage', { chat_id: chat, text: HELP[lang], parse_mode: 'HTML' });
  const fd = new FormData();
  fd.append('chat_id', String(chat)); fd.append('caption', T[lang].guideCap);
  fd.append('document', new Blob([await f.arrayBuffer()], { type: 'application/pdf' }), `Osmon_${lang === 'ru' ? 'instrukciya' : lang === 'en' ? 'guide' : 'yoriqnoma'}.pdf`);
  const r = await (await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendDocument`, { method: 'POST', body: fd })).json();
  if (r.ok && r.result.document && env.DB) await setKv(env, key, r.result.document.file_id);
  return r;
}


async function sendToday(env, chat, lang, id, group) {
  const M = await manifest(env);
  const days = M && M.items.find(i => i.region === id && i.lang === lang && i.product === 'days');
  const text = days && forecastText(days, lang, NAMES[id][lang], id, { more: group ? 3 : 0 });
  if (!text) return tg(env, 'sendMessage', { chat_id: chat, text: T[lang].none });
  return tg(env, 'sendMessage', { chat_id: chat, text, parse_mode: 'HTML', reply_markup: group ? postKb(env, lang, id) : menuKb(env, lang, id), disable_web_page_preview: true });
}

/* ---------- groups: subscriptions and automatic posts ---------- */
async function db(env) {
  await env.DB.exec('CREATE TABLE IF NOT EXISTS subs (chat_id INTEGER PRIMARY KEY, title TEXT, type TEXT, region TEXT, lang TEXT, last_run TEXT, added TEXT)');
  await env.DB.exec('CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)');
  await env.DB.exec('CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY, lang TEXT, mode TEXT, name TEXT, seen TEXT)');
  try { await env.DB.exec('ALTER TABLE users ADD COLUMN region TEXT'); } catch (e) { /* already there */ }
  try { await env.DB.exec('ALTER TABLE users ADD COLUMN username TEXT'); } catch (e) { /* already there */ }
  for (const c of ['place TEXT', 'first TEXT']) { try { await env.DB.exec(`ALTER TABLE users ADD COLUMN ${c}`); } catch (e) { /* already there */ } }
  await env.DB.exec('CREATE TABLE IF NOT EXISTS msgmap (mid INTEGER PRIMARY KEY, chat INTEGER, lang TEXT)');
  await env.DB.exec('CREATE TABLE IF NOT EXISTS searches (day TEXT, q TEXT, found INTEGER, n INTEGER, PRIMARY KEY (day, q))');
  try { await env.DB.exec('ALTER TABLE subs ADD COLUMN post_hour INTEGER'); } catch (e) { /* already there */ }
  try { await env.DB.exec('ALTER TABLE subs ADD COLUMN alert_run TEXT'); } catch (e) { /* already there */ }
  await env.DB.exec('CREATE TABLE IF NOT EXISTS mtn (chat_id INTEGER PRIMARY KEY, lang TEXT, ver TEXT, added TEXT)');
  // who used the bot on which day (Tashkent date) and a daily snapshot of the auto-send subscriptions: for the admin's 📈 Динамика
  await env.DB.exec('CREATE TABLE IF NOT EXISTS daily (day TEXT, chat_id INTEGER, PRIMARY KEY (day, chat_id))');
  await env.DB.exec('CREATE TABLE IF NOT EXISTS dstat (day TEXT PRIMARY KEY, prv INTEGER, grp INTEGER, mtn INTEGER, users INTEGER)');
  await env.DB.exec('CREATE TABLE IF NOT EXISTS watch (chat_id INTEGER PRIMARY KEY, lat REAL, lon REAL, name TEXT, lang TEXT, on_ INTEGER, asked TEXT, st TEXT, checked TEXT)');
  await env.DB.exec('CREATE TABLE IF NOT EXISTS notif (chat_id INTEGER, sec TEXT, hour INTEGER, lang TEXT, region TEXT, last_day TEXT, added TEXT, PRIMARY KEY (chat_id, sec))');
}
async function sub(env, chat) { if (!env.DB) return null; await db(env); return env.DB.prepare('SELECT * FROM subs WHERE chat_id = ?1').bind(chat).first(); }
async function saveSub(env, chat, regions, lang, lastDay, hour = POST_HOUR) {
  if (!env.DB) return; await db(env);
  await env.DB.prepare('INSERT INTO subs (chat_id, title, type, region, lang, last_run, added, post_hour) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8) ON CONFLICT(chat_id) DO UPDATE SET title = ?2, region = ?4, lang = ?5, last_run = ?6, post_hour = ?8')
    .bind(chat.id, chat.title || chat.first_name || '', chat.type, regions.join(','), lang, lastDay || '', new Date().toISOString(), hour).run();
}
async function memberChange(m, env) {
  const chat = m.chat, st = m.new_chat_member && m.new_chat_member.status;
  if (chat.type === 'private') { if (st === 'kicked' && env.DB) { await db(env); await env.DB.prepare('DELETE FROM subs WHERE chat_id = ?1').bind(chat.id).run(); } return; }
  if (st === 'left' || st === 'kicked') { if (env.DB) { await db(env); for (const t of ['subs', 'notif', 'mtn']) await env.DB.prepare(`DELETE FROM ${t} WHERE chat_id = ?1`).bind(chat.id).run(); } return; }
  if ((st === 'member' || st === 'administrator') && !(await sub(env, chat.id))) {
    await saveSub(env, chat, ['UZ'], 'uz', '');  // default until an admin chooses
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T.uz.gHi + '\n\n' + T.ru.gHi, reply_markup: langKb('GL') });
  }
}
async function isAdmin(env, chat, user, senderChat) {
  if (chat.type === 'channel') return true;
  if (senderChat && senderChat.id === chat.id) return true;  // an anonymous admin writes as the group itself
  if (!user) return false;
  if (user.id === 1087968824) return true;  // @GroupAnonymousBot = anonymous admin  // only admins can press buttons under a channel's own post anyway
  const r = await tg(env, 'getChatMember', { chat_id: chat.id, user_id: user.id });
  if (!r.ok) console.log('getChatMember', chat.id, user.id, r.description);
  return r.ok && ['creator', 'administrator'].includes(r.result.status);
}
// one forecast post: the precipitation video with today, tomorrow and the next days in the caption, and link buttons
async function post(env, M, chat, lang0, id0, bot) {
  const lang = T[lang0] ? lang0 : 'uz', id = NAMES[id0] ? id0 : 'UZ';
  const items = M.items.filter(i => i.region === id && i.lang === lang);
  const days = items.find(i => i.product === 'days');
  let vids = ['prob', 'temp', 'cloud', 'wind'].map(p => items.find(i => (i.product || 'prob') === p)).filter(Boolean);
  if (!vids.length) vids = ['prob', 'temp', 'cloud', 'wind'].map(p => M.items.find(i => i.region === id && i.lang === 'ru' && (i.product || 'prob') === p)).filter(Boolean);
  const updated = M.run.slice(8, 10) + '.' + M.run.slice(5, 7) + ' ' + M.run.slice(11, 16) + ' UTC';
  const cap = forecastText(days, lang, NAMES[id][lang], id, { more: 3, foot: T[lang].swipe, limit: 1024 });
  if (!cap) return { ok: false, description: 'no data' };
  const nv = await newVids(id, lang);
  if (!vids.length && !nv.length) return tg(env, 'sendMessage', { chat_id: chat, text: cap, parse_mode: 'HTML', reply_markup: postKb(env, lang, id, bot, chat), disable_web_page_preview: true });
  const media = nv.length ? nv.map(u => ({ type: 'video', media: `${u}?v=${Math.floor(Date.now() / 1800e3)}`, supports_streaming: true })) : vids.map(v => ({ type: 'video', media: `${base(env)}/prob/${v.video}?v=${fresh()}`, supports_streaming: true }));
  media[0].caption = cap; media[0].parse_mode = 'HTML';
  let r = await tg(env, 'sendMediaGroup', { chat_id: chat, media });
  // Telegram could not take the videos by link (too big, the site slow): try the two lightest ones, then the text alone.
  // (Uploading the files from here broke the whole daily sending: "Network connection lost" on ~50 MB of video.)
  const gone = x => /kicked|blocked|deactivated|not a member|chat not found|have no rights|was deleted/i.test(x.description || '');
  if (!r.ok && !gone(r)) { console.log('album', chat, id, r.description); const m2 = media.slice(-2); m2[0] = { ...m2[0], caption: cap, parse_mode: 'HTML' }; r = await tg(env, 'sendMediaGroup', { chat_id: chat, media: m2 }); }
  if (!r.ok && !gone(r)) r = await tg(env, 'sendMessage', { chat_id: chat, text: cap, parse_mode: 'HTML', reply_markup: postKb(env, lang, id, bot, chat), disable_web_page_preview: true });
  if (!r.ok) return r;
  // weather by city for today, with the buttons the album cannot carry
  const lines = await cityLines(env, id, lang);
  if (lines) await tg(env, 'sendMessage', { chat_id: chat, text: `${T[lang].cTitle} · ${FLAG[id]} <b>${esc(NAMES[id][lang])}</b>\n\n${lines}`.slice(0, 4000), parse_mode: 'HTML', reply_markup: postKb(env, lang, id, bot, chat), disable_web_page_preview: true });
  return r;
}

// is the data on the site fresh? (site/build.json: when the last build finished). Normally a new build every ~3 hours;
// over 5 hours means an update was skipped or late (the watchdog in staleTick is already restarting it)
const FRESH_H = 5, HOLD_MAX_H = 3;  // wait for fresh data at most 3 hours past the person's hour, then send what there is
async function siteFresh(env) {
  const B = await fetch(`${base(env)}/build.json?t=${Date.now()}`).then(r => r.ok ? r.json() : null).catch(() => null);
  if (!B || !B.built) return { fresh: true, age: 0 };  // no stamp yet: do not hold anything
  const age = (Date.now() - Date.parse(B.built)) / 3600e3;
  // a build made after midnight (Tashkent) is today's forecast: the morning sends (from 06:00) go out on time with it
  const sameDay = new Date(Date.parse(B.built) + TZ * 3600e3).toISOString().slice(0, 10) === new Date(Date.now() + TZ * 3600e3).toISOString().slice(0, 10);
  return { fresh: age < FRESH_H || sameDay, age, built: B.built };
}
// one invitation for the people who use the bot without the daily forecast: today's forecast for their country and a
// button to get it every morning. Each person gets it once at most (table invited), in small batches per call
const INV = { ru: { head: '☀️ Свежий прогноз от Osmon', btn: '🔔 Получать прогноз каждое утро', tip: 'Хотите получать такой прогноз каждый день в удобное время? Нажмите кнопку ниже.' },
              uz: { head: '☀️ Osmon’dan yangi prognoz', btn: '🔔 Har kuni ertalab prognoz olish', tip: 'Bunday prognozni har kuni qulay vaqtda olishni xohlaysizmi? Quyidagi tugmani bosing.' },
              en: { head: '☀️ Fresh forecast from Osmon', btn: '🔔 Get the forecast every morning', tip: 'Want this forecast every day at the time you like? Tap the button below.' } };
async function invite(env, n) {
  if (!env.DB) return { ok: false }; await db(env);
  await env.DB.exec('CREATE TABLE IF NOT EXISTS invited (chat_id INTEGER PRIMARY KEY, at TEXT, ok INTEGER)');
  const rows = (await env.DB.prepare('SELECT u.chat_id, u.lang, u.region FROM users u WHERE u.chat_id > 0 AND u.chat_id NOT IN (SELECT chat_id FROM subs) AND u.chat_id NOT IN (SELECT chat_id FROM invited) LIMIT ?1').bind(Math.min(20, n)).all()).results;
  if (!rows.length) return { ok: true, sent: 0, left: 0 };
  const M = await manifest(env, true); if (!M) return { ok: false, error: 'no manifest' };
  let sent = 0, failed = 0;
  for (const u of rows) {
    const lang = INV[u.lang] ? u.lang : 'uz', id = NAMES[u.region] ? u.region : 'UZ', X = INV[lang];
    await env.DB.prepare('INSERT OR REPLACE INTO invited (chat_id, at, ok) VALUES (?1, ?2, 0)').bind(u.chat_id, new Date().toISOString()).run();  // first: never twice
    const days = M.items.find(i => i.region === id && i.lang === lang && i.product === 'days') || M.items.find(i => i.region === id && i.lang === 'ru' && i.product === 'days');
    const txt = forecastText(days, lang, NAMES[id][lang], id, { more: 3 });
    if (!txt) { failed++; continue; }
    const r = await tg(env, 'sendMessage', { chat_id: u.chat_id, text: `<b>${X.head}</b>\n\n${txt}\n\n${X.tip}`.slice(0, 4000), parse_mode: 'HTML', disable_web_page_preview: true,
      reply_markup: { inline_keyboard: [[{ text: X.btn, callback_data: `B:${lang}:${id}`, style: 'success' }]] } });
    if (r.ok) { sent++; await env.DB.prepare('UPDATE invited SET ok = 1 WHERE chat_id = ?1').bind(u.chat_id).run(); } else failed++;
  }
  const left = ((await env.DB.prepare('SELECT COUNT(*) AS n FROM users WHERE chat_id > 0 AND chat_id NOT IN (SELECT chat_id FROM subs) AND chat_id NOT IN (SELECT chat_id FROM invited)').first()) || {}).n || 0;
  return { ok: true, sent, failed, left };
}
async function broadcast(env) {
  if (!env.DB) return { ok: false, error: 'no DB' };
  await db(env);
  const hour = new Date(Date.now() + TZ * 3600e3).getUTCHours(), day = todayTZ();
  let due = (await env.DB.prepare("SELECT * FROM subs WHERE COALESCE(last_run, '') <> ?1 AND COALESCE(post_hour, ?3) <= ?2 ORDER BY COALESCE(post_hour, ?3) LIMIT ?4").bind(day, hour, POST_HOUR, PER_TICK * 3).all()).results;
  if (!due.length) return { ok: true, day, hour, due: 0 };
  // late data: the daily posts wait (not marked as sent) and go out at the first run after the fresh data arrives —
  // unless the wait is already 3 hours past the chosen hour; then the forecast we have is better than none
  const F = await siteFresh(env);
  if (!F.fresh) {
    const waiting = due.filter(s => hour - (s.post_hour ?? POST_HOUR) < HOLD_MAX_H);
    due = due.filter(s => hour - (s.post_hour ?? POST_HOUR) >= HOLD_MAX_H);
    if (waiting.length && (await kv(env, 'hold_day')) !== day) {
      await setKv(env, 'hold_day', day); const a = await kv(env, 'admin');
      if (a) await tg(env, 'sendMessage', { chat_id: a, text: `⏳ Утренняя рассылка ждёт свежих данных: на сайте данные ${Math.round(F.age)} ч назад. Как только сборка закончится, рассылка уйдёт сразу (самое позднее — через ${HOLD_MAX_H} ч после времени подписчика, с тем, что есть).` });
    }
    if (!due.length) return { ok: true, day, hour, due: 0, held: waiting.length };
  }
  due = due.slice(0, PER_TICK);
  const M = await manifest(env, true);
  if (!M) return { ok: false, error: 'no manifest' };
  const me = await tg(env, 'getMe', {}), bot = me.ok ? me.result.username : '';
  let sent = 0;
  for (const s of due) {
    let gone = false;
    for (const r of (regionsOf(s).length ? regionsOf(s) : ['UZ'])) {
      const res = await post(env, M, s.chat_id, s.lang, r, s.type === 'private' ? '' : bot).catch(e => { console.log('post', s.chat_id, r, e && e.stack); return { ok: false, description: String(e) }; });  // one bad chat never stops the rest
      if (res.ok) sent++;
      // the bot was removed or cannot write there: forget the chat
      if (!res.ok && [400, 403].includes(res.error_code) && /kicked|blocked|deactivated|not a member|chat not found|have no rights|was deleted/i.test(res.description || '')) { gone = true; break; }
    }
    if (gone) await env.DB.prepare('DELETE FROM subs WHERE chat_id = ?1').bind(s.chat_id).run();
    else await env.DB.prepare('UPDATE subs SET last_run = ?2 WHERE chat_id = ?1').bind(s.chat_id, day).run();
  }
  return { ok: true, day, run: M.run, due: due.length, sent };
}

/* ---------- visit counter for the website (by country and city) ----------
   The site sends one POST /hit per visitor per day; Cloudflare already knows the visitor's country and city
   (request.cf), so nothing is stored about the person: only daily totals per city. GET /stats returns the totals. */
const CORS = { 'access-control-allow-origin': '*', 'access-control-allow-methods': 'GET,POST,OPTIONS', 'access-control-allow-headers': 'content-type' };
async function visits(req, env, url) {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS });
  const json = (o, extra = {}) => new Response(JSON.stringify(o), { headers: { 'content-type': 'application/json; charset=utf-8', ...CORS, ...extra } });
  if (!env.DB) return json({ ok: false, error: 'no database (bind a D1 database as DB)' });
  await env.DB.exec('CREATE TABLE IF NOT EXISTS hits (day TEXT, country TEXT, city TEXT, n INTEGER, PRIMARY KEY (day, country, city))');
  if (url.pathname === '/hit' && req.method === 'POST') {
    const cf = req.cf || {}, day = new Date().toISOString().slice(0, 10);
    const country = String(cf.country || '??').slice(0, 2), city = String(cf.city || '').slice(0, 60);
    await env.DB.prepare('INSERT INTO hits (day, country, city, n) VALUES (?1, ?2, ?3, 1) ON CONFLICT(day, country, city) DO UPDATE SET n = n + 1').bind(day, country, city).run();
    return json({ ok: true });
  }
  const day = new Date().toISOString().slice(0, 10);
  const one = async (q, ...a) => (await env.DB.prepare(q).bind(...a).all()).results;
  const [tot] = await one('SELECT COALESCE(SUM(n),0) AS n FROM hits');
  const [today] = await one('SELECT COALESCE(SUM(n),0) AS n FROM hits WHERE day = ?1', day);
  const countries = await one('SELECT country, SUM(n) AS n FROM hits GROUP BY country ORDER BY n DESC LIMIT 12');
  const cities = await one("SELECT country, city, SUM(n) AS n FROM hits WHERE city <> '' GROUP BY country, city ORDER BY n DESC LIMIT 12");
  return json({ ok: true, total: tot.n, today: today.n, countries, cities }, { 'cache-control': 'public, max-age=300' });
}
