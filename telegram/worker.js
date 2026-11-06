// Osmon Telegram bot (Cloudflare Workers, free plan).
//  • Private chat: /start → language → country/continent → today & tomorrow, by days, 15-day videos, the site as a Mini App.
//  • Groups and channels: add the bot (as admin in a channel) and it posts the forecast by itself after every update
//    every day at the hour the group picked (default 07:00 Tashkent). An admin picks the language, one or several
//    countries and the hour with /sozla (/settings). Each post: 3 videos + today/tomorrow/next days + weather by city.
//  • /help: instructions in Uzbek, Russian and Turkish.
//  • /hit and /stats: anonymous visit counter for the website (daily totals per country and city).
// Everything is read from the website built by GitHub Actions (SITE_URL/prob/manifest.json and the .mp4 files).
// Settings (Workers → Settings): BOT_TOKEN (secret), SITE_URL (variable), D1 database bound as DB,
// cron trigger (e.g. every 20 minutes) for the automatic group posts.
// Connect once: open <worker URL>/setup in a browser (webhook, command menus, bot description).

const NAMES = {
  world: { uz: 'Butun dunyo', ru: 'Весь мир', tr: 'Tüm dünya' }, EU: { uz: 'Yevropa', ru: 'Европа', tr: 'Avrupa' }, AS: { uz: 'Osiyo', ru: 'Азия', tr: 'Asya' },
  AF: { uz: 'Afrika', ru: 'Африка', tr: 'Afrika' }, NA: { uz: 'Shimoliy Amerika', ru: 'Северная Америка', tr: 'Kuzey Amerika' },
  SA: { uz: 'Janubiy Amerika', ru: 'Южная Америка', tr: 'Güney Amerika' }, OC: { uz: 'Okeaniya', ru: 'Океания', tr: 'Okyanusya' },
  cis: { uz: 'MDH va Turkiya', ru: 'СНГ и Турция', tr: 'BDT ve Türkiye' }, UZ: { uz: 'O‘zbekiston', ru: 'Узбекистан', tr: 'Özbekistan' },
  KZ: { uz: 'Qozog‘iston', ru: 'Казахстан', tr: 'Kazakistan' }, KG: { uz: 'Qirg‘iziston', ru: 'Кыргызстан', tr: 'Kırgızistan' },
  TJ: { uz: 'Tojikiston', ru: 'Таджикистан', tr: 'Tacikistan' }, TM: { uz: 'Turkmaniston', ru: 'Туркменистан', tr: 'Türkmenistan' },
  AZ: { uz: 'Ozarbayjon', ru: 'Азербайджан', tr: 'Azerbaycan' }, AM: { uz: 'Armaniston', ru: 'Армения', tr: 'Ermenistan' },
  BY: { uz: 'Belarus', ru: 'Беларусь', tr: 'Belarus' }, MD: { uz: 'Moldova', ru: 'Молдова', tr: 'Moldova' },
  RU: { uz: 'Rossiya', ru: 'Россия', tr: 'Rusya' }, TR: { uz: 'Turkiya', ru: 'Турция', tr: 'Türkiye' },
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
  tr: {
    cities: '🏙 Şehirler', cPick: '🏙 Şehir seçin:', cTitle: '🏙 Bugün şehirlerde', time: '⏰ Tahmin gruba saat kaçta gönderilsin? (Taşkent saati)', help: 'ℹ️ Yardım',
    d15: '15 günlük tahmin', hi: '☀️ <b>Osmon</b> — hava tahmini\n6 modele göre 15 günlük (ECMWF, NOAA).\n\nDil seçin:', pick: '📍 Ülke veya kıta seçin:',
    menu: 'Ne göstereyim?', today: '⏱ Bugün ve yarın saat saat', all: '🎬 15 günlük video', days: '🗓 15 gün', site: '🗺 Site ve küre', rep: '📊 Rapor', menuHint: '⌨️ Tüm bölümler — alttaki düğmelerde.\n📍 Konum gönderin veya şehir adı yazın, örneğin: Antalya', locAsk: '📍 Alttaki düğmeye basın — konumunuz gönderilir.',
    back: '↩️ Ülkeler', none: '⏳ Veriler henüz hazır değil, biraz sonra deneyin.', tdy: 'Bugün', tmw: 'Yarın', next: 'Sonraki günler',
    upd: 'Güncellendi', swipe: '🎬 Videoları kaydırın: 🌧 yağış · 🌡 sıcaklık · ☁️ bulutlar · 💨 rüzgâr', bot: '🤖 Bot',
    gHi: '👋 Merhaba! Her gün buraya videolu hava tahmini göndereceğim.\nGrup yöneticisi: dil, ülke ve saati seçin 👇 (/settings)',
    gSet: '✅ Hazır! Her gün {time}’da (Taşkent saati) bu sohbete tahmin gönderilecek: <b>{name}</b> ({lang}).\nDeğiştirmek için: /settings', gMulti: '📍 Ülkeleri işaretleyin (birden fazla olabilir) ve «Tamam»a basın:', done: '✅ Tamam', gNone: 'En az bir ülke seçin.', gAdm: '⚙️ Ayarları yalnızca bu grubun yöneticisi değiştirebilir. Ondan /settings yazmasını isteyin.', gLang: 'Dil seçin:', lang: 'Türkçe',
    pdf: '📄 Kılavuz (PDF)', adm: '✉️ Yöneticiye yaz', admAsk: '✍️ Bot yöneticisine mesajınızı yazın (metin, fotoğraf veya sesli mesaj), ileteceğim.\nİptal: /cancel', admSent: '✅ Mesajınız yöneticiye gönderildi. Cevap bu sohbete gelecek.', admAns: '💬 Yönetici cevabı:', admOff: 'Bot yöneticisi henüz bağlanmadı, daha sonra deneyin.', cancel: 'İptal edildi.', guideCap: '📄 Osmon botu — tam kılavuz',
    sub: '🔔 Her gün', unsub: '🔕 Kapat', subAsk: '🔔 {name} tahminini her gün saat kaçta göndereyim? (Taşkent saati)', subOk: '✅ Her gün {time}’da buraya tahmin gelecek: {name}.\nKapatmak için menüdeki 🔔 düğmesi.', subOff: '🔕 Günlük gönderim kapatıldı.',
  },
};
const HELP = {
  uz: `ℹ️ <b>Osmon bot — yo‘riqnoma</b>

<b>Shaxsiy chatda</b>
/start — til va davlatni tanlash
📍 <b>Joylashuv</b> yuboring yoki <b>shahar nomini</b> yozing — dunyoning istalgan joyi uchun 15 kunlik prognoz
📅 <b>Bugun va ertaga</b> — asosiy shahar bo‘yicha qisqa prognoz
🗓 <b>Kunlar bo‘yicha</b> — 15 kun
🏙 <b>Shaharlar</b> — istalgan shahar uchun prognoz
🎬 <b>15 kunlik video</b> — yog‘in, harorat, bulutlar
🔔 <b>Har kuni</b> — prognozni har kuni o‘zingiz tanlagan vaqtda olish; kuchli yog‘in bo‘lsa — ⚠️ ogohlantirish
/alerts — kuchli yog‘in ogohlantirishlari
📊 Hisobot / 🌍 Globus — sayt Telegram ichida ochiladi
/bugun — O‘zbekiston, bugun va ertaga

<b>Guruh yoki kanalda</b>
1. Botni guruhga qo‘shing (kanalda — admin qilib, «xabar yuborish» huquqi bilan).
2. Admin /sozla yozadi: til → davlatlar (bir nechta) → «Tayyor» → yuborish vaqti.
3. Har kuni tanlangan vaqtda har bir davlat uchun post keladi: 3 ta video + bugun/ertaga + shaharlar.
/bugun — guruhda hozirgi prognoz.

✉️ <b>Adminga yozish</b> — savol yoki taklif, javob shu yerga keladi (/admin)
📄 /guide — to‘liq yo‘riqnoma PDF faylda

Ma’lumot: ECMWF IFS/AIFS, NOAA GFS/GEFS, DWD ICON. Kuniga 2 marta yangilanadi.`,
  ru: `ℹ️ <b>Бот Osmon — инструкция</b>

<b>В личном чате</b>
/start — выбрать язык и страну
📍 Отправьте <b>геолокацию</b> или напишите <b>название города</b> — прогноз на 15 дней для любой точки мира
📅 <b>Сегодня и завтра</b> — коротко по главному городу
🗓 <b>По дням</b> — все 15 дней
🏙 <b>Города</b> — прогноз для любого города страны
🎬 <b>Видео на 15 дней</b> — осадки, температура, облака
🔔 <b>Каждый день</b> — получать прогноз ежедневно в выбранное время; при сильных осадках — ⚠️ предупреждение
/alerts — предупреждения о сильных осадках
📊 Отчёт / 🌍 Глобус — сайт открывается прямо в Телеграме
/today — Узбекистан, сегодня и завтра

<b>В группе или канале</b>
1. Добавьте бота в группу (в канал — администратором с правом публикации).
2. Администратор пишет /settings: язык → страны (можно несколько) → «Готово» → время отправки.
3. Каждый день в выбранное время по каждой стране приходит пост: 3 видео + сегодня/завтра + погода по городам.
/bugun — прогноз в группу прямо сейчас.

✉️ <b>Написать админу</b> — вопрос или предложение, ответ придёт сюда (/admin)
📄 /guide — полная инструкция в PDF

Данные: ECMWF IFS/AIFS, NOAA GFS/GEFS, DWD ICON. Обновление 2 раза в сутки.`,
  tr: `ℹ️ <b>Osmon botu — kılavuz</b>

<b>Özel sohbette</b>
/start — dil ve ülke seçimi
📍 <b>Konum</b> gönderin veya <b>şehir adı</b> yazın — dünyanın her yeri için 15 günlük tahmin
📅 <b>Bugün ve yarın</b> — ana şehir için kısa tahmin
🗓 <b>Günlere göre</b> — 15 gün
🏙 <b>Şehirler</b> — herhangi bir şehir için tahmin
🎬 <b>15 günlük video</b> — yağış, sıcaklık, bulutlar
🔔 <b>Her gün</b> — tahmini her gün seçtiğiniz saatte alın; kuvvetli yağışta ⚠️ uyarı
/alerts — kuvvetli yağış uyarıları
📊 Rapor / 🌍 Küre — site Telegram içinde açılır

<b>Grupta veya kanalda</b>
1. Botu gruba ekleyin (kanalda yönetici olarak, gönderme izniyle).
2. Yönetici /settings yazar: dil → ülkeler (birden fazla) → «Tamam» → gönderme saati.
3. Her gün seçilen saatte her ülke için gönderi gelir: 3 video + bugün/yarın + şehirler.

✉️ <b>Yöneticiye yaz</b> — soru veya öneri, cevap buraya gelir (/admin)
📄 /guide — PDF olarak tam kılavuz

Veri: ECMWF IFS/AIFS, NOAA GFS/GEFS, DWD ICON. Günde 2 kez güncellenir.`,
};
const WD = { uz: ['Yak', 'Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan'], ru: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'], tr: ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'] };
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
    if (req.method === 'GET' && url.pathname === '/setup') return setup(env, url);
    if (url.pathname === '/hit' || url.pathname === '/stats') return visits(req, env, url);
    if (req.method === 'GET' && url.pathname === '/broadcast') { const r = await broadcast(env); return new Response(JSON.stringify(r), { headers: { 'content-type': 'application/json' } }); }
    if (req.method !== 'POST') return new Response('Osmon bot is running. Open /setup once to connect it to Telegram.');
    if (req.headers.get('x-telegram-bot-api-secret-token') !== await secret(env)) return new Response('forbidden', { status: 403 });
    const up = await req.json().catch(() => ({}));
    // answer Telegram at once; sending videos can take longer than its webhook timeout
    ctx.waitUntil(handle(up, env).catch(e => console.log('error', e && e.stack)));
    return new Response('ok');
  },
  async scheduled(ev, env, ctx) {
    ctx.waitUntil((async () => { const r = await broadcast(env); if (!r || !r.due) { await alertTick(env); await mtnTick(env).catch(e => console.log('mtn', e && e.stack)); await staleTick(env); await statsTick(env); await backupTick(env); } await buildTick(env); })().catch(e => console.log('broadcast', e && e.stack)));
  },
};

// the admin's own command menu and buttons: /users, /admin, /yt
const ADMIN_BTN = '👤 Пользователи';
const ADMIN_KB = { inline_keyboard: [[{ text: ADMIN_BTN, callback_data: 'AU:ru' }, { text: '📺 YouTube', callback_data: 'AY:ru' }]] };
async function adminMenu(env, chat) {
  await tg(env, 'setMyCommands', { scope: { type: 'chat', chat_id: Number(chat) }, commands: [{ command: 'users', description: '👤 Пользователи бота' }, { command: 'searches', description: '🔎 Что ищут (7 дней)' }, { command: 'accuracy', description: '🎯 Точность прогноза' }, { command: 'admin', description: '👑 Статистика' }, { command: 'yt', description: '📺 Видеообзор для YouTube' }, { command: 'start', description: 'Меню' }] });
}
async function setup(env, url) {
  { const a = await kv(env, 'admin'); if (a) await adminMenu(env, a); }
  const hook = await tg(env, 'setWebhook', { url: `${url.origin}/`, secret_token: await secret(env), allowed_updates: ['message', 'callback_query', 'my_chat_member', 'channel_post'] });
  await tg(env, 'setMyCommands', { commands: [  // ☰ only the basics: everything else is on the keyboard under the input field
    { command: 'home', description: '🏠 Menyu / Меню (klaviatura / клавиатура)' },
    { command: 'help', description: 'ℹ️ Yordam, PDF / Помощь, PDF' },
    { command: 'admin', description: '✉️ Adminga yozish / Написать админу' },
    { command: 'start', description: '🔤 Til / Язык / Dil' }] });
  await tg(env, 'setMyCommands', { scope: { type: 'all_group_chats' }, commands: [{ command: 'sozla', description: 'Davlat va til (adminlar uchun)' }, { command: 'settings', description: 'Страна и язык (для админов)' }, { command: 'bugun', description: 'Bugun va ertaga / Сегодня и завтра' }, { command: 'help', description: 'Yordam / Помощь' }] });
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
const langKb = (p = 'L') => ({ inline_keyboard: [[{ text: '🇺🇿 O‘zbekcha', callback_data: `${p}:uz` }, { text: '🇷🇺 Русский', callback_data: `${p}:ru` }, { text: '🇹🇷 Türkçe', callback_data: `${p}:tr` }]] });
const countryKb = (lang, p = 'C') => ({ inline_keyboard: GROUPS.map(row => row.map(id => ({ text: `${FLAG[id]} ${NAMES[id][lang]}`, callback_data: `${p}:${lang}:${id}` }))) });
const OLK = { uz: '📅 Haftalar va oylar', ru: '📅 Недели и месяцы', tr: '📅 Haftalar ve aylar' };
// Uzbekistan: the past week, the next two weeks and this and next month as five maps (prob/outlook.py)
async function sendOutlook(env, chat, lang) {
  const I = await (await fetch(`${base(env)}/prob/outlook/index.json?t=${Date.now()}`)).json().catch(() => null);
  let its = I ? I.items.filter(i => i.lang === lang) : []; if (I && !its.length) its = I.items.filter(i => i.lang === 'ru');
  if (!its.length) return tg(env, 'sendMessage', { chat_id: chat, text: T[lang].none });
  // every map is its own message with its own caption: big enough to read, clear what it shows
  const dd = x => `${x.slice(8, 10)}.${x.slice(5, 7)}`, v = encodeURIComponent(I.made || '');
  await tg(env, 'sendMessage', { chat_id: chat, text: `🇺🇿 <b>${OLK[lang]}</b>`, parse_mode: 'HTML' });
  let r = null;
  for (const i of its) {
    const imgs = i.imgs || [i.img], caps = i.caps || [];
    for (let k = 0; k < imgs.length; k++) {
      const cap = `<b>${esc(i.title)}</b>${caps[k] ? ` · ${esc(caps[k])}` : ''}\n${dd(i.start)}–${dd(i.end)}${k === 0 && i.text ? `\n${esc(i.text)}` : ''}`;
      await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_photo' });
      r = await tg(env, 'sendPhoto', { chat_id: chat, photo: `${base(env)}/prob/${imgs[k]}?v=${v}`, caption: cap.slice(0, 1024), parse_mode: 'HTML' });
    }
  }
  return r;
}
/* ---------- mountains of Uzbekistan: fresh snow and good days for a trip (site/prob/mountains.json, prob/mountains.py) ---------- */
const MTX = {
  ru: { title: '🏔 <b>Горы Узбекистана: снег и поездки</b>', m: 'м', snow: '❄️ Свежий снег', noSnow: '❄️ Снегопадов в ближайшие 16 дней не видно', cm: 'см', cover: '⛄ Снег лежит', go: '🥾 Когда ехать', noGo: '🥾 Хороших дней для поездки пока не видно', after: '👉 После снега лучше всего', wind: 'ветер до', ms: 'м/с',
    foot: 'Прогноз на 16 дней с поправкой на высоту · ECMWF, DWD, NOAA (Open-Meteo). Снегопад — от 2 см за сутки; хороший день — сухо, солнечно, без сильного ветра.', sub: '🔔 Сигнал о снеге в горах', unsub: '🔕 Выключить сигнал о снеге', on: '🔔 Сигнал включён: напишу, как только в горах ожидается свежий снег, и подскажу, в какой день лучше ехать.', off: '🔕 Сигнал о снеге выключен.', alert: '❄️ <b>Снег в горах!</b>', fresh: 'свежего снега', all: '🏔 Все горы', none: 'Данные по горам ещё готовятся, попробуйте чуть позже.' },
  uz: { title: '🏔 <b>O‘zbekiston tog‘lari: qor va sayohat</b>', m: 'm', snow: '❄️ Yangi qor', noSnow: '❄️ Yaqin 16 kunda qor yog‘ishi kutilmayapti', cm: 'sm', cover: '⛄ Qor qoplami', go: '🥾 Qachon borish kerak', noGo: '🥾 Hozircha sayohat uchun yaxshi kun ko‘rinmayapti', after: '👉 Qordan keyin eng yaxshi kun', wind: 'shamol', ms: 'm/s',
    foot: '16 kunlik prognoz, balandlikka moslangan · ECMWF, DWD, NOAA (Open-Meteo). Qor yog‘ishi — sutkada 2 sm dan; yaxshi kun — quruq, quyoshli, kuchli shamolsiz.', sub: '🔔 Tog‘da qor haqida xabar', unsub: '🔕 Qor xabarini o‘chirish', on: '🔔 Xabar yoqildi: tog‘larda yangi qor kutilishi bilan yozaman va qaysi kuni borish yaxshiligini aytaman.', off: '🔕 Qor xabari o‘chirildi.', alert: '❄️ <b>Tog‘larda qor!</b>', fresh: 'yangi qor', all: '🏔 Barcha tog‘lar', none: 'Tog‘lar ma’lumoti hali tayyorlanmoqda, birozdan keyin urinib ko‘ring.' },
  tr: { title: '🏔 <b>Özbekistan dağları: kar ve gezi</b>', m: 'm', snow: '❄️ Taze kar', noSnow: '❄️ Önümüzdeki 16 günde kar yağışı görünmüyor', cm: 'cm', cover: '⛄ Kar örtüsü', go: '🥾 Ne zaman gidilir', noGo: '🥾 Şimdilik gezi için iyi gün görünmüyor', after: '👉 Kardan sonra en iyi gün', wind: 'rüzgâr', ms: 'm/s',
    foot: 'Yüksekliğe göre düzeltilmiş 16 günlük tahmin · ECMWF, DWD, NOAA (Open-Meteo). Kar yağışı — günde 2 cm’den; iyi gün — kuru, güneşli, sert rüzgârsız.', sub: '🔔 Dağlarda kar bildirimi', unsub: '🔕 Kar bildirimini kapat', on: '🔔 Bildirim açık: dağlarda taze kar beklendiğinde yazacağım ve hangi gün gitmenin iyi olduğunu söyleyeceğim.', off: '🔕 Kar bildirimi kapatıldı.', alert: '❄️ <b>Dağlarda kar!</b>', fresh: 'taze kar', all: '🏔 Tüm dağlar', none: 'Dağ verileri henüz hazırlanıyor, biraz sonra deneyin.' },
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
async function sendMountains(env, chat, lang) {
  const X = MTX[lang] || MTX.ru, M = await mountainsData(env);
  if (!M || !M.spots) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  const today = todayTZ(), out = [X.title];
  for (const sp of M.spots) {
    const days = sp.days.filter(d => d.d >= today), snow = days.filter(d => d.sn >= (M.snow_cm || 2));
    out.push('', `<b>${esc(sp.name[lang] || sp.name.ru)}</b> · ${sp.elev} ${X.m} · ${esc(sp.area[lang] || sp.area.ru)}`);
    out.push(snow.length ? `${X.snow}: ${snow.slice(0, 4).map(d => `${dayLabel(d.d, lang)} ~${Math.round(d.sn)} ${X.cm}`).join(', ')}` : X.noSnow);
    if (days[0] && days[0].depth >= 1) out.push(`${X.cover}: ~${days[0].depth} ${X.cm}`);
    const a = snow.length ? afterSnow(sp, snow[0].d) : null;
    if (a) out.push(`${X.after}: <b>${dayW(a, lang)}</b>`);
    const g = days.slice(0, 10).filter(d => d.good > 0).sort((p, q) => q.good - p.good || (p.d < q.d ? -1 : 1)).slice(0, 3).sort((p, q) => p.d < q.d ? -1 : 1);
    if (g.length) { out.push(`${X.go}:`); g.forEach(d => out.push(`   • ${dayW(d, lang)}`)); } else out.push(X.noGo);
  }
  out.push('', `<i>${X.foot}</i>`);
  const s = await mtnSub(env, chat);
  return tg(env, 'sendMessage', { chat_id: chat, text: out.join('\n').slice(0, 4000), parse_mode: 'HTML', disable_web_page_preview: true,
    reply_markup: { inline_keyboard: [[{ text: s ? X.unsub : X.sub, callback_data: `MS:${lang}`, style: s ? undefined : 'success' }]] } });
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
      out.push('', `<b>${esc(sp.name[lang] || sp.name.ru)}</b> — ${dayLabel(d.d, lang)}: ~${Math.round(d.sn)} ${X.cm} ${X.fresh} ${wIcon(d.code)}`);
      const a = afterSnow(sp, d.d); if (a) out.push(`${X.after}: <b>${dayW(a, lang)}</b>`);
    }
    const r = await tg(env, 'sendMessage', { chat_id: s.chat_id, text: out.join('\n'), parse_mode: 'HTML', reply_markup: { inline_keyboard: [[{ text: X.all, callback_data: `MT:${lang}` }]] } });
    if (!r.ok && /blocked|deactivated|chat not found|kicked/i.test(r.description || '')) { await env.DB.prepare('DELETE FROM mtn WHERE chat_id = ?1').bind(s.chat_id).run(); continue; }
    await env.DB.prepare('UPDATE mtn SET ver = ?2 WHERE chat_id = ?1').bind(s.chat_id, ver).run();
  }
}
// the menu is a keyboard under the input field (white buttons, as in the screenshot): one place for everything, no buttons under messages
const RKL = {
  ru: { hourly: '⏱ Сегодня и завтра по часам', days: '🗓 15 дней', video: '🎬 Видео на 15 дней', outlook: '📅 Недели и месяцы', mtn: '🏔 Горы и снег', now: '🌡 Сейчас', cities: '🏙 Города', loc: '📍 Моё место', countries: '🌍 Страны', daily: '🔔 Каждый день', accuracy: '🎯 Точность', alerts: '⚠️ Предупреждения', site: '🗺 Сайт и глобус', home: '🏠 Главная', reset: '🔄 Сбросить', back: '⬅️ Назад', help: 'ℹ️ Помощь' },
  uz: { hourly: '⏱ Bugun va ertaga soatma-soat', days: '🗓 15 kun', video: '🎬 15 kunlik video', outlook: '📅 Haftalar va oylar', mtn: '🏔 Tog‘lar va qor', now: '🌡 Hozir', cities: '🏙 Shaharlar', loc: '📍 Mening joyim', countries: '🌍 Davlatlar', daily: '🔔 Har kuni', accuracy: '🎯 Aniqlik', alerts: '⚠️ Ogohlantirishlar', site: '🗺 Sayt va globus', home: '🏠 Bosh menyu', reset: '🔄 Qayta boshlash', back: '⬅️ Orqaga', help: 'ℹ️ Yordam' },
  tr: { hourly: '⏱ Bugün ve yarın saat saat', days: '🗓 15 gün', video: '🎬 15 günlük video', outlook: '📅 Haftalar ve aylar', mtn: '🏔 Dağlar ve kar', now: '🌡 Şimdi', cities: '🏙 Şehirler', loc: '📍 Konumum', countries: '🌍 Ülkeler', daily: '🔔 Her gün', accuracy: '🎯 Doğruluk', alerts: '⚠️ Uyarılar', site: '🗺 Site ve küre', home: '🏠 Ana menü', reset: '🔄 Sıfırla', back: '⬅️ Geri', help: 'ℹ️ Yardım' } };
const rkAct = text => { for (const L of Object.values(RKL)) for (const [k, v] of Object.entries(L)) if (v === text) return k; return null; };
function replyKb(env, lang, id) {
  const X = RKL[lang] || RKL.ru, b = t => ({ text: t });
  return { keyboard: [
    [b(X.hourly)],
    [b(X.days), b(X.video)],
    ...(id === 'UZ' ? [[b(X.outlook), b(X.mtn)]] : []),
    [b(X.now), b(X.cities)],
    [{ text: X.loc, request_location: true }, b(X.countries)],
    [b(X.daily), b(X.alerts)],
    [b(X.accuracy), { text: X.site, web_app: { url: site(env, `prob/${id}/${lang}/prob`) } }],
    [b(X.home), b(X.reset)]], resize_keyboard: true, is_persistent: true, input_field_placeholder: { uz: 'Shahar nomi…', ru: 'Название города…', tr: 'Şehir adı…' }[lang] };
}
// countries and cities are keyboards too: the chosen one is marked with ✅
function countryRk(lang, cur) {
  const X = RKL[lang] || RKL.ru;
  return { keyboard: [...GROUPS.map(row => row.map(id => ({ text: `${cur === id ? '✅ ' : ''}${FLAG[id]} ${NAMES[id][lang]}` }))), [{ text: X.home }]], resize_keyboard: true };
}
const countryOf = text => { const t = text.replace(/^✅ /, ''); for (const id of Object.keys(NAMES)) for (const l of ['uz', 'ru', 'tr']) if (t === `${FLAG[id]} ${NAMES[id][l]}`) return id; return null; };
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
  return tg(env, 'sendMessage', { chat_id: chat, text: `${FLAG[id]} <b>${NAMES[id][lang]}</b> · ${DK[lang].ask}`, parse_mode: 'HTML', reply_markup: { keyboard: rows, resize_keyboard: true, input_field_placeholder: { uz: 'Shahar nomi…', ru: 'Название города…', tr: 'Şehir adı…' }[lang] } });
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
  tr: { home: '🏠 Ana menü', reset: '🔄 Sıfırla', ask: 'Ayarlar sıfırlanıp baştan başlansın mı?\nSeçili ülke, kayıtlı konum ve günlük tahmin aboneliği silinir.', yes: '✅ Evet, sıfırla', no: '❌ Hayır', done: '🔄 Ayarlar sıfırlandı. Dil seçin:' } };
const homeRow = lang => [{ text: (HK[lang] || HK.ru).home, callback_data: `HM:${lang}` }, { text: (HK[lang] || HK.ru).reset, callback_data: `RS:${lang}` }];
const DK = {
  uz: { ask: '15 kunlik prognoz: shaharni tanlang yoki dunyodagi istalgan shahar nomini yozing (masalan: Parij, Dubay)', mine: 'Mening joyim', loc: '📍 Joylashuvni yuborish', other: '🌍 Boshqa davlat', vid: '🎬 Shu shahar videosi', vidC: '🎬 Video 15 kun', more: '🏙 Boshqa shahar', globe: '🌍 Globusda ochish' },
  ru: { ask: 'Прогноз на 15 дней: выберите город или напишите название любого города мира (например: Париж, Дубай)', mine: 'Моё место', loc: '📍 Отправить геолокацию', other: '🌍 Другая страна', vid: '🎬 Видео этого города', vidC: '🎬 Видео на 15 дней', more: '🏙 Другой город', globe: '🌍 Открыть на глобусе' },
  tr: { ask: '15 günlük tahmin: şehir seçin ya da dünyadaki herhangi bir şehrin adını yazın (ör. Paris, Dubai)', mine: 'Konumum', loc: '📍 Konum gönder', other: '🌍 Başka ülke', vid: '🎬 Bu şehrin videosu', vidC: '🎬 15 günlük video', more: '🏙 Başka şehir', globe: '🌍 Kürede aç' } };
// under a 15-day text: the matching video (this city's own, or the country's), another city, the countries
function dayKb(lang, rid, cityVideo) {
  const X = DK[lang] || DK.ru;
  return { inline_keyboard: [
    [cityVideo ? { text: X.vid, callback_data: cityVideo, style: 'primary' } : { text: X.vidC, callback_data: `V:${lang}:${rid}`, style: 'primary' }],
    [{ text: X.more, callback_data: `D:${lang}:${rid}` }, { text: X.other, callback_data: `L:${lang}` }], homeRow(lang)] };
}
const helpKb = lang => ({ inline_keyboard: [[{ text: T[lang].pdf, callback_data: `P:${lang}` }, { text: T[lang].adm, callback_data: `M:${lang}` }]] });
// groups and channels cannot open Mini Apps from buttons: plain links
const LIVE = { ru: '🗺 Интерактивная карта по часам', uz: '🗺 Interaktiv xarita soatma-soat', tr: '🗺 Saat saat etkileşimli harita' };
// the interactive map: inside Telegram in a private chat (mini app), a plain link in groups (Telegram allows mini-app buttons only in private chats)
const liveBtn = (env, lang, id, chat) => ({ text: LIVE[lang] || LIVE.ru, ...(chat > 0 ? { web_app: { url: `${base(env)}/live.html?r=${id}&l=${lang}` } } : { url: `${base(env)}/live.html?r=${id}&l=${lang}` }) });
const postKb = (env, lang, id, bot, chat) => ({ inline_keyboard: [...(chat ? [[liveBtn(env, lang, id, chat)]] : []), [{ text: T[lang].rep, url: link(env, `prob/${id}/${lang}/prob`) }, { text: T[lang].site, url: link(env, 'map') }], ...(bot ? [[{ text: T[lang].bot, url: `https://t.me/${bot}` }]] : [])] });

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
  tr: { heat: 'aşırı sıcak, gündüz', frost: 'şiddetli soğuk, gece', ice: 'buzlanma (yollarda don)', wind: 'kuvvetli rüzgâr, ortalama', storm: 'gök gürültülü sağanak', dust: 'toz fırtınası / hava kirliliği', ms: 'm/s', title: '⚠️ <b>Uyarı: tehlikeli hava</b>' },
};
const AL = {
  uz: { title: '⚠️ <b>Ogohlantirish: kuchli yog‘in</b>', r1: 'kuchli yomg‘ir', r2: 'juda kuchli yomg‘ir', s1: 'kuchli qor', s2: 'juda kuchli qor', mm: 'mm', peak: 'eng kuchli', foot: 'ECMWF, NOAA, DWD modellari ansambli bo‘yicha. Ehtiyot bo‘ling!', none: '✅ Yaqin 3 kunda kuchli yog‘in kutilmayapti.' },
  ru: { title: '⚠️ <b>Предупреждение: сильные осадки</b>', r1: 'сильный дождь', r2: 'очень сильный дождь', s1: 'сильный снег', s2: 'очень сильный снег', mm: 'мм', peak: 'пик', foot: 'По ансамблю моделей ECMWF, NOAA, DWD. Будьте осторожны!', none: '✅ В ближайшие 3 дня сильных осадков не ожидается.' },
  tr: { title: '⚠️ <b>Uyarı: kuvvetli yağış</b>', r1: 'kuvvetli yağmur', r2: 'çok kuvvetli yağmur', s1: 'yoğun kar', s2: 'çok yoğun kar', mm: 'mm', peak: 'en yoğun', foot: 'ECMWF, NOAA, DWD model topluluğuna göre. Dikkatli olun!', none: '✅ Önümüzdeki 3 günde kuvvetli yağış beklenmiyor.' },
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
  tr: { locBtn: '📍 Bulunduğum yerde hava', locHint: '📍 Alttaki düğmeye basın — konumunuz için 15 günlük tahmin.\nYa da şehir adı yazın, örneğin: <i>Antalya</i>', nf: '🔎 Şehir bulunamadı. Farklı yazmayı deneyin veya 📍 konum gönderin.', pick: '🔎 Hangisi?', head: '15 günlük tahmin', none: 'yağışsız', rain: 'yağmur', snow: 'kar', ms: 'm/s', mm: 'mm', vid: '🎬 Ülke videosu', src: 'ECMWF, NOAA, DWD topluluğu · ~50 km ızgara', far: 'Bu nokta için veri yok.' },
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
  tr: { brief: 'Özet', allDry: '15 gün boyunca kayda değer yağış yok', wetNow: 'Bugünden itibaren yağış olası', dryUntil: '{d} dahil kuru',
    wetDays: 'Yağışlı gün: {n}; en kuvvetlisi {peak}', snowOn: 'Kar: {d}', cooler: 'Soğuma: gündüz {a} → {b}', warmer: 'Isınma: gündüz {a} → {b}',
    steady: 'Sıcaklıkta sert değişim yok: gündüz {a} … {b}', frost: 'Don {t} ({d})', wind: 'Kuvvetli rüzgâr {w} m/s ({d})', windW: 'rüzgâr',
    dry: 'yağışsız', rain: 'yağmur', snow: 'kar', next: 'Sonraki günler', cDay: 'Gün', cT: 'Sıcaklık', cP: 'Yağış', run: 'Hesaplama', upd: 'Güncellendi', model: 'model çalıştırması',
    note: 'Yağış: günlük olasılık ve model topluluğunun ortalama miktarı.', noRain: 'Şemsiye gerekmez', rainAt: '{w} {a}–{b} saatlerinde olası (%{p} e kadar)', wear: 'Giyim' },
};
const WEAR = {
  ru: { c: ['зимняя куртка, шапка, перчатки', 'тёплая куртка и шапка', 'куртка или пальто, шарф', 'лёгкая куртка или свитер', 'кофта, вечером лёгкая куртка', 'футболка и лёгкая одежда', 'лёгкая одежда, головной убор, вода'], u: 'зонт', b: 'непромокаемая обувь', w: 'ветровка' },
  uz: { c: ['qishki kurtka, telpak, qo‘lqop', 'issiq kurtka va telpak', 'kurtka yoki palto, sharf', 'yengil kurtka yoki sviter', 'kofta, kechqurun yengil kurtka', 'futbolka, yengil kiyim', 'yengil kiyim, bosh kiyim, suv'], u: 'soyabon', b: 'suv o‘tkazmaydigan poyabzal', w: 'shamoldan himoya kurtka' },
  tr: { c: ['kışlık mont, bere, eldiven', 'kalın mont ve bere', 'mont veya kaban, atkı', 'ince ceket veya kazak', 'hırka, akşam ince ceket', 'tişört ve hafif giysiler', 'hafif giysiler, şapka, su'], u: 'şemsiye', b: 'su geçirmez ayakkabı', w: 'rüzgârlık' },
};
function wearText(lang, lo, hi, p, snow, w) {
  const W = WEAR[lang] || WEAR.ru, t = (lo + 2 * hi) / 3, k = t <= -10 ? 0 : t <= 0 ? 1 : t <= 8 ? 2 : t <= 15 ? 3 : t <= 22 ? 4 : t <= 28 ? 5 : 6;
  return [W.c[k], ...(p >= 40 ? [snow ? W.b : W.u] : []), ...(w >= 8 ? [W.w] : [])].join(', ');
}
const MK = {  // the main keyboard under the chat: four buttons for everything
  ru: { today: '📅 Сегодня и завтра', d15: '🗓 15 дней', video: '🎬 Видео', more: '⚙️ Меню' },
  uz: { today: '📅 Bugun va ertaga', d15: '🗓 15 kun', video: '🎬 Video', more: '⚙️ Menyu' },
  tr: { today: '📅 Bugün ve yarın', d15: '🗓 15 gün', video: '🎬 Video', more: '⚙️ Menü' },
};
const mainKb = () => ({ remove_keyboard: true });  // (kept for old callers)
const locOnce = lang => ({ keyboard: [[{ text: PT[lang].locBtn, request_location: true }]], resize_keyboard: true, one_time_keyboard: true });
const FILLER = new Set('погода погоду погоды прогноз в во на для город городе сегодня завтра какая какой ob-havo obhavo havo bugun ertaga shahar shahrida hava durumu bugün yarın için weather in today tomorrow'.split(' '));
// today and tomorrow hour by hour: the country's video with the main city's timing and clothing advice (prob/hourly.py)
// Telegram caches a file by its URL, so every media link carries the hour: a new build is always fetched again
const fresh = () => Math.floor(Date.now() / 3600e3);
async function sendHourly(env, chat, lang, id) {
  let H = null;
  for (const l of [lang, 'ru', 'uz']) { const r = await fetch(`${base(env)}/prob/hr/${id}_${l}.json`, { cf: { cacheTtl: 600 } }); if (r.ok) { H = await r.json(); break; } }
  if (!H) return sendToday(env, chat, lang, id);
  const K = PK[lang], X = { ru: ['Сегодня', 'Завтра', 'по часам'], uz: ['Bugun', 'Ertaga', 'soatma-soat'], tr: ['Bugün', 'Yarın', 'saat saat'] }[lang];
  const part = (lbl, d) => d ? `<b>${lbl}</b> ${d.range}\n☂️ ${d.rain}\n🧥 ${K.wear}: ${d.wear}` : '';
  const cap = [`${FLAG[id] || ''} <b>${esc(NAMES[id][lang])}</b> · ${esc(H.city)} — ${X[0].toLowerCase()} / ${X[1].toLowerCase()} ${X[2]}`, '', part(X[0], H.info.today), '', part(X[1], H.info.tomorrow)].join('\n').slice(0, 1024);
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
  const url = `${base(env)}/prob/${H.video}?v=${fresh()}`, kb0 = menuKb(env, lang, id);
  // the interactive map (a Telegram mini app): touch the map, drag the hours, hear the weather — private chats only
  // (the keyboard under the input field stays as it is; this message carries the mini-app button)
  const kb = chat > 0 ? { inline_keyboard: [[liveBtn(env, lang, id, chat)]] } : kb0;
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
const pname = (p, lang) => (lang === 'uz' ? p[1] || p[2] : lang === 'tr' ? p[3] || p[2] : p[0] || p[2]);
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
  tr: { 0: 'açık', 1: 'çoğunlukla açık', 2: 'parçalı bulutlu', 3: 'kapalı', 45: 'sis', 48: 'kırağılı sis', 51: 'çisenti', 53: 'çisenti', 55: 'yoğun çisenti', 56: 'dondurucu çisenti', 57: 'dondurucu çisenti', 61: 'hafif yağmur', 63: 'yağmur', 65: 'kuvvetli yağmur', 66: 'dondurucu yağmur', 67: 'dondurucu yağmur', 71: 'hafif kar', 73: 'kar', 75: 'yoğun kar', 77: 'kar taneleri', 80: 'sağanak', 81: 'sağanak', 82: 'kuvvetli sağanak', 85: 'kar sağanağı', 86: 'yoğun kar sağanağı', 95: 'gök gürültülü fırtına', 96: 'dolu ile fırtına', 99: 'dolu ile fırtına' } };
const NOWX = { uz: { now: 'Hozir', feels: 'his qilinadi', hum: 'namlik', wind: 'shamol', gust: 'shiddat', ms: 'm/s' }, ru: { now: 'Сейчас', feels: 'ощущается', hum: 'влажность', wind: 'ветер', gust: 'порывы', ms: 'м/с' }, tr: { now: 'Şimdi', feels: 'hissedilen', hum: 'nem', wind: 'rüzgâr', gust: 'hamle', ms: 'm/s' } };
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
async function pointForecast(env, chat, lang, lat, lon, place, kbOver) {
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
  const rows = D.slice(2).map(x => `${x.ic} ${pad(wd(x.d), 9)}${pad(`${f(x.lo)}…${f(x.hi)}°`, 10)}${bar(x.p)} ${pad(x.p < 20 ? '—' : `${x.p}%`, 4)}${x.mm >= 0.5 ? ` ${x.mm < 9.5 ? x.mm.toFixed(0) : Math.round(x.mm)} ${L.mm}` : ''}`);
  const nm = place ? `${FLAG[place[4]] || '📍'} <b>${esc(pname(place, lang))}</b>` : `📍 <b>${lat.toFixed(2)}, ${lon.toFixed(2)}</b>`;
  const hm = t => { const l = new Date(t + off * 3600e3); return `${String(l.getUTCDate()).padStart(2, '0')}.${String(l.getUTCMonth() + 1).padStart(2, '0')} ${String(l.getUTCHours()).padStart(2, '0')}:${String(l.getUTCMinutes()).padStart(2, '0')}`; };
  const u = I.built ? `${hm(Date.parse(I.built))} · ${K.model} ${hm(run).slice(0, 5)} ${hm(run).slice(6)}` : hm(run);
  const detail = x => {  // when it rains and what to wear (3-hour windows of that day)
    const ws = wins.filter(v => v.d === x.d), wet = ws.filter(v => v.p >= 40);
    let r = K.noRain;
    if (wet.length) { const top = wet.reduce((a, b) => (b.p > a.p ? b : a)); let a = top, b = top; const i = ws.indexOf(top);
      for (let j = i - 1; j >= 0 && ws[j].p >= 40; j--) a = ws[j]; for (let j = i + 1; j < ws.length && ws[j].p >= 40; j++) b = ws[j];
      r = K.rainAt.replace('{w}', x.snow ? K.snow : K.rain).replace('{a}', String(a.h1).padStart(2, '0')).replace('{b}', String(b.h2).padStart(2, '0')).replace('{p}', Math.round(top.p)); }
    return `\n      ☂️ ${r}\n      🧥 ${K.wear}: ${wearText(lang, x.lo, x.hi, x.p, x.snow, x.w)}`;
  };
  const day = (x, w) => `${x.ic} <b>${w}</b> · ${wd(x.d)}\n      ${deg(x.lo)}…${deg(x.hi)} · ${pr(x)}${isFinite(x.w) && x.w >= 5 ? ` · ${K.windW} ${Math.round(x.w)} ${L.ms}` : ''}${detail(x)}`;
  const isAdmin = String(chat) === (await kv(env, 'admin'));  // update times only for the bot's admin
  const text = [`${nm} · ${L.head}`, ...(isAdmin ? [`<i>${I.built ? K.upd : K.run} ${u} (UTC${off >= 0 ? '+' : ''}${off})</i>`] : []), '', ...(nowT ? [nowT, ''] : []),
    `<b>${K.brief}</b>`, ...sum.map(x => `▸ ${x}`), '',
    day(D[0], D[0].d === today ? T[lang].tdy : wd(D[0].d)), ...(D[1] ? [day(D[1], D[1].d === tmrw ? T[lang].tmw : wd(D[1].d))] : []), '',
    ...(rows.length ? [`<b>${K.next}</b>`, `<pre>${esc('   ' + pad(K.cDay, 9) + pad(K.cT, 10) + K.cP)}\n${esc(rows.join('\n'))}</pre>`] : []),
    `<i>${K.note}</i>`].join('\n');
  let kb = kbOver && kbOver.keyboard ? kbOver : null;
  if (!kb) { const uu = await getUser(env, chat); kb = replyKb(env, lang, place && NAMES[place[4]] ? place[4] : (uu && NAMES[uu.region] ? uu.region : 'UZ')); }
  return tg(env, 'sendMessage', { chat_id: chat, text: text.slice(0, 4000), parse_mode: 'HTML', ...(kb ? { reply_markup: kb } : {}) });
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
async function buildTick(env) {
  if (!env.GH_TOKEN || !env.DB) return;
  const last = +(await kv(env, 'build_at') || 0);
  if (Date.now() - last < 3 * 3600e3 - 10 * 60e3) return;
  const r = await fetch('https://api.github.com/repos/otabekvafoev92-del/ob-havo-ecmwf/actions/workflows/update.yml/dispatches', {
    method: 'POST', headers: { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json', 'user-agent': 'osmon-bot', 'content-type': 'application/json' },
    body: JSON.stringify({ ref: 'main' }) });
  await setKv(env, 'build_at', String(Date.now()));
  if (r.status !== 204) { const a = await kv(env, 'admin'); if (a) await tg(env, 'sendMessage', { chat_id: a, text: `⚠️ Не удалось запустить обновление данных (GitHub ${r.status}). Проверьте ключ GH_TOKEN.` }); }
}
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
async function staleTick(env) {
  const M = await manifest(env); if (!M || !M.run) return;
  const age = (Date.now() - Date.parse(M.run)) / 3600e3;
  if (age < 33) return;
  const last = +(await kv(env, 'stale_at') || 0), admin = await kv(env, 'admin');
  if (!admin || Date.now() - last < 12 * 3600e3) return;
  await setKv(env, 'stale_at', String(Date.now()));
  await tg(env, 'sendMessage', { chat_id: admin, text: `⚠️ Данные сайта и бота не обновлялись ${Math.round(age)} ч (последний расчёт ${tkt(M.run)} по Ташкенту).\nПроверьте вкладку Actions в репозитории на GitHub.`, disable_web_page_preview: true });
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
      if (cmd === 'help') { const s = await sub(env, chat.id); return tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[(s && s.lang) || 'ru'], parse_mode: 'HTML' }); }
      if (cmd === 'bugun' || cmd === 'today') { const s = await sub(env, chat.id), regs = regionsOf(s).length ? regionsOf(s) : ['UZ']; for (const r of regs) await sendToday(env, chat.id, s ? s.lang : cmd === 'today' ? 'ru' : 'uz', r, true); return; }
      return;
    }
  }
  if (!cb) return;
  const chat = cb.message.chat, [kind, lang, id] = cb.data.split(':');
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
    return;
  }
  if (kind === 'Y' || kind === 'Z') {  // cities of a country: Y list, Z:lang:id:index one city
    await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id, ...(kind === 'Z' ? { text: ({ uz: '⏳ Tayyorlanmoqda…', ru: '⏳ Готовлю…', tr: '⏳ Hazırlanıyor…' })[lang] || '⏳' } : {}) });
    const [, , rid, ci] = cb.data.split(':'), C = await cities(env, rid, lang);
    if (!C || !C.cities.length) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].none });
    if (kind === 'Y' && chat.type === 'private') return cityPicker(env, chat.id, lang, rid);
    if (kind === 'Y') {
      const rows = []; C.cities.forEach((c, i) => { if (i % 3 === 0) rows.push([]); rows[rows.length - 1].push({ text: c.name, callback_data: `Z:${lang}:${rid}:${i}` }); });
      rows.push([{ text: T[lang].back, callback_data: `C:${lang}:${rid}` }]);
      return say(env, cb, { chat_id: chat.id, text: `${FLAG[rid]} <b>${NAMES[rid][lang]}</b> · ${T[lang].cPick}`, parse_mode: 'HTML', reply_markup: { inline_keyboard: rows } });
    }
    const c = C.cities[+ci]; if (!c) return;
    const kb = chat.type === 'private' ? replyKb(env, lang, rid) : { inline_keyboard: [[{ text: T[lang].cities, callback_data: `Y:${lang}:${rid}` }, { text: T[lang].back, callback_data: `C:${lang}:${rid}` }]] };
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
  await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id, ...(['T', 'V', 'DC', 'Q', 'O'].includes(kind) ? { text: ({ uz: '⏳ Tayyorlanmoqda…', ru: '⏳ Готовлю…', tr: '⏳ Hazırlanıyor…' })[lang] || '⏳' } : {}) });
  if (chat.type === 'private') await saveUser(env, chat.id, who(cb.from));
  if (kind === 'S') {  // first language choice after /start: the guide, then the countries
    await saveUser(env, chat.id, { lang });
    await tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[lang], parse_mode: 'HTML', reply_markup: helpKb(lang) });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryRk(lang) });
  }
  if ((kind === 'AU' || kind === 'AY') && chat.type === 'private') return privateMsg({ chat, from: cb.from, message_id: cb.message.message_id, text: kind === 'AU' ? '/users' : '/yt' }, env);
  if (kind === 'O') return sendOutlook(env, chat.id, lang);
  if (kind === 'MT') return sendMountains(env, chat.id, lang);
  if (kind === 'MS') {  // the snow signal on / off: the button under the mountains message changes with it
    const X = MTX[lang] || MTX.ru, cur = await mtnSub(env, chat.id);
    if (cur) await env.DB.prepare('DELETE FROM mtn WHERE chat_id = ?1').bind(chat.id).run();
    else await env.DB.prepare('INSERT OR REPLACE INTO mtn (chat_id, lang, ver, added) VALUES (?1, ?2, ?3, ?4)').bind(chat.id, lang, (await kv(env, 'mtn_ver')) || '', new Date().toISOString()).run();
    await tg(env, 'editMessageReplyMarkup', { chat_id: chat.id, message_id: cb.message.message_id, reply_markup: { inline_keyboard: [[{ text: cur ? X.sub : X.unsub, callback_data: `MS:${lang}` }]] } });
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
    const media = vids.map(v => ({ type: 'video', media: `${base(env)}/prob/${v.video}?v=${fresh()}`, supports_streaming: true }));
    media[0].caption = forecastText(days, lang, NAMES[id][lang], id, { more: 3, limit: 1000 }) || `${NAMES[id][lang]} · ${T[lang].d15}`;
    media[0].parse_mode = 'HTML';
    await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_video' });
    let r = await tg(env, 'sendMediaGroup', { chat_id: chat.id, media });
    // Telegram could not fetch the files by link: download them here and upload them
    if (!r.ok) r = await uploadGroup(env, chat.id, media);
    if (!r.ok) await tg(env, 'sendMessage', { chat_id: chat.id, text: `${T[lang].none}\n(${r.description || r.error_code || '?'})` });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].menu, reply_markup: menuKb(env, lang, id) });
  }
}

/* ---------- private chat: commands, guide and messages to the bot's admin ---------- */
async function privateMsg(msg, env) {
  const chat = msg.chat, text = msg.text || '', cmd = (text.trim().match(/^\/(\w+)(@\w+)?/) || [])[1];
  const u = await getUser(env, chat.id), lang = (u && T[u.lang] && u.lang) || (/^ru/.test(msg.from && msg.from.language_code || '') ? 'ru' : /^tr/.test(msg.from && msg.from.language_code || '') ? 'tr' : 'uz');
  await saveUser(env, chat.id, who(msg.from));
  const admin = await kv(env, 'admin');
  // the admin answers a user: Reply to the forwarded message
  if (admin && String(chat.id) === admin && msg.reply_to_message && !cmd) {
    const to = env.DB && await env.DB.prepare('SELECT chat, lang FROM msgmap WHERE mid = ?1').bind(msg.reply_to_message.message_id).first();
    if (to) {
      const L = T[to.lang] ? to.lang : 'ru';
      await tg(env, 'sendMessage', { chat_id: to.chat, text: T[L].admAns });
      const r = await tg(env, 'copyMessage', { chat_id: to.chat, from_chat_id: chat.id, message_id: msg.message_id });
      return tg(env, 'sendMessage', { chat_id: chat.id, text: r.ok ? '✅' : `⚠️ ${r.description || ''}`, reply_to_message_id: msg.message_id });
    }
  }
  if (cmd === 'cancel') { await saveUser(env, chat.id, { mode: '' }); return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].cancel }); }
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
  if (u && u.mode === 'contact' && !cmd) {  // pass the message on to the admin
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
    return pointForecast(env, chat.id, lang, la, lo, await nearestPlace(env, la, lo));
  }
  if (!text) return;
  // the ☰ menu (and the buttons of the old keyboard that some chats still show): one action each, no duplicates
  {
    const rid = (u && NAMES[u.region] && u.region) || 'UZ', old = k => !cmd && Object.values(MK).some(m => m[k] === text);
    const rk = !cmd && rkAct(text);
    const act = rk === 'back' ? 'home' : rk === 'loc' ? 'location' : rk || (old('today') ? 'hourly' : old('d15') ? 'days' : old('video') ? 'video' : old('more') ? 'countries' : Object.values(PT).some(m => m.locBtn === text) ? 'location' : cmd);
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
    if (act === 'outlook') return sendOutlook(env, chat.id, lang);
    if (act === 'mtn') return sendMountains(env, chat.id, lang);
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
    tr: { t: '🎯 <b>Tahmin doğruluğu</b> (son 30 gün)', rain: 'Yağış var/yok doğru', temp: 'Ortalama sıcaklık hatası', t2: '±2° içinde', city: 'Şehirler', wait: 'Doğrulama başladı: yarın tahminleri kaydediliyor, ilk sonuçlar 2–3 gün içinde.', how: 'Yarın tahmini (24–48 saat önce) gerçek hava ile karşılaştırılır: yağış ≥ 1 mm, olasılık ≥ %50 = «yağış».', days: 'gün' } }[lang] || null;
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
async function getUser(env, id) { if (!env.DB) return null; await db(env); return env.DB.prepare('SELECT * FROM users WHERE chat_id = ?1').bind(id).first(); }
const who = f => (f ? { name: [f.first_name, f.last_name].filter(Boolean).join(' ') || null, username: f.username || null } : {});
async function saveUser(env, id, f) {
  if (!env.DB) return; await db(env);
  await env.DB.prepare('INSERT INTO users (chat_id, lang, mode, name, seen, region, username, place, first) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?5) ON CONFLICT(chat_id) DO UPDATE SET lang = COALESCE(?2, lang), mode = COALESCE(?3, mode), name = COALESCE(?4, name), seen = ?5, region = COALESCE(?6, region), username = COALESCE(?7, username), place = COALESCE(?8, place)')
    .bind(id, f.lang ?? null, f.mode ?? null, f.name ?? null, new Date().toISOString(), f.region ?? null, f.username ?? null, f.place ?? null).run();
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
  fd.append('document', new Blob([await f.arrayBuffer()], { type: 'application/pdf' }), `Osmon_${lang === 'ru' ? 'instrukciya' : lang === 'tr' ? 'kilavuz' : 'yoriqnoma'}.pdf`);
  const r = await (await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendDocument`, { method: 'POST', body: fd })).json();
  if (r.ok && r.result.document && env.DB) await setKv(env, key, r.result.document.file_id);
  return r;
}

async function uploadGroup(env, chat, media) {
  const fd = new FormData();
  fd.append('chat_id', String(chat));
  const m2 = [];
  for (let i = 0; i < media.length; i++) {
    const f = await fetch(media[i].media);
    if (!f.ok) return { ok: false, description: `site ${f.status}` };
    fd.append(`v${i}`, new Blob([await f.arrayBuffer()], { type: 'video/mp4' }), `v${i}.mp4`);
    m2.push({ ...media[i], media: `attach://v${i}` });
  }
  fd.append('media', JSON.stringify(m2));
  const r = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendMediaGroup`, { method: 'POST', body: fd });
  return r.json();
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
  if (st === 'left' || st === 'kicked') { if (env.DB) { await db(env); await env.DB.prepare('DELETE FROM subs WHERE chat_id = ?1').bind(chat.id).run(); } return; }
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
  if (!vids.length) return tg(env, 'sendMessage', { chat_id: chat, text: cap, parse_mode: 'HTML', reply_markup: postKb(env, lang, id, bot, chat), disable_web_page_preview: true });
  const media = vids.map(v => ({ type: 'video', media: `${base(env)}/prob/${v.video}?v=${fresh()}`, supports_streaming: true }));
  media[0].caption = cap; media[0].parse_mode = 'HTML';
  let r = await tg(env, 'sendMediaGroup', { chat_id: chat, media });
  // Telegram could not fetch the videos by link: upload the files
  if (!r.ok && !/kicked|blocked|deactivated|not a member|chat not found|have no rights|was deleted/i.test(r.description || '')) r = await uploadGroup(env, chat, media);
  if (!r.ok) return r;
  // weather by city for today, with the buttons the album cannot carry
  const lines = await cityLines(env, id, lang);
  if (lines) await tg(env, 'sendMessage', { chat_id: chat, text: `${T[lang].cTitle} · ${FLAG[id]} <b>${esc(NAMES[id][lang])}</b>\n\n${lines}`.slice(0, 4000), parse_mode: 'HTML', reply_markup: postKb(env, lang, id, bot), disable_web_page_preview: true });
  return r;
}

async function broadcast(env) {
  if (!env.DB) return { ok: false, error: 'no DB' };
  await db(env);
  const hour = new Date(Date.now() + TZ * 3600e3).getUTCHours(), day = todayTZ();
  const due = (await env.DB.prepare("SELECT * FROM subs WHERE COALESCE(last_run, '') <> ?1 AND COALESCE(post_hour, ?3) <= ?2 LIMIT ?4").bind(day, hour, POST_HOUR, PER_TICK).all()).results;
  if (!due.length) return { ok: true, day, hour, due: 0 };
  const M = await manifest(env, true);
  if (!M) return { ok: false, error: 'no manifest' };
  const me = await tg(env, 'getMe', {}), bot = me.ok ? me.result.username : '';
  let sent = 0;
  for (const s of due) {
    let gone = false;
    for (const r of (regionsOf(s).length ? regionsOf(s) : ['UZ'])) {
      const res = await post(env, M, s.chat_id, s.lang, r, s.type === 'private' ? '' : bot);
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
