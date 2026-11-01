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
    menu: 'Nimani ko‘rsatay?', today: '📅 Bugun va ertaga', all: '🎬 15 kunlik video', days: '🗓 Kunlar bo‘yicha', site: '🌍 Globus', rep: '📊 Hisobot',
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
    menu: 'Что показать?', today: '📅 Сегодня и завтра', all: '🎬 Видео на 15 дней', days: '🗓 По дням', site: '🌍 Глобус', rep: '📊 Отчёт',
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
    menu: 'Ne göstereyim?', today: '📅 Bugün ve yarın', all: '🎬 15 günlük video', days: '🗓 Günlere göre', site: '🌍 Küre', rep: '📊 Rapor',
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
    ctx.waitUntil((async () => { const r = await broadcast(env); if (!r || !r.due) { await alertTick(env); await staleTick(env); await statsTick(env); } })().catch(e => console.log('broadcast', e && e.stack)));
  },
};

// the admin's own command menu and buttons: /users, /admin, /yt
const ADMIN_BTN = '👤 Пользователи';
const ADMIN_KB = { inline_keyboard: [[{ text: ADMIN_BTN, callback_data: 'AU:ru' }, { text: '📺 YouTube', callback_data: 'AY:ru' }]] };
async function adminMenu(env, chat) {
  await tg(env, 'setMyCommands', { scope: { type: 'chat', chat_id: Number(chat) }, commands: [{ command: 'users', description: '👤 Пользователи бота' }, { command: 'admin', description: '👑 Статистика' }, { command: 'yt', description: '📺 Видеообзор для YouTube' }, { command: 'start', description: 'Меню' }] });
}
async function setup(env, url) {
  { const a = await kv(env, 'admin'); if (a) await adminMenu(env, a); }
  const hook = await tg(env, 'setWebhook', { url: `${url.origin}/`, secret_token: await secret(env), allowed_updates: ['message', 'callback_query', 'my_chat_member', 'channel_post'] });
  await tg(env, 'setMyCommands', { commands: [{ command: 'start', description: 'Til / Язык / Dil' }, { command: 'bugun', description: 'Bugun va ertaga' }, { command: 'today', description: 'Сегодня и завтра' }, { command: 'prognoz', description: '15 kunlik video' }, { command: 'help', description: 'Yordam / Помощь' }, { command: 'guide', description: 'Yo‘riqnoma PDF / Инструкция PDF' }, { command: 'alerts', description: 'Ogohlantirishlar / Предупреждения' }, { command: 'admin', description: 'Adminga yozish / Написать админу' }] });
  await tg(env, 'setMyCommands', { scope: { type: 'all_group_chats' }, commands: [{ command: 'sozla', description: 'Davlat va til (adminlar uchun)' }, { command: 'settings', description: 'Страна и язык (для админов)' }, { command: 'bugun', description: 'Bugun va ertaga / Сегодня и завтра' }, { command: 'help', description: 'Yordam / Помощь' }] });
  await tg(env, 'setChatMenuButton', { menu_button: { type: 'web_app', text: 'Osmon', web_app: { url: site(env, 'map') } } });
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
function menuKb(env, lang, id) {
  return { inline_keyboard: [
    [{ text: T[lang].today, callback_data: `T:${lang}:${id}` }, { text: T[lang].days, callback_data: `D:${lang}:${id}` }],
    [{ text: T[lang].cities, callback_data: `Y:${lang}:${id}` }, { text: T[lang].all, callback_data: `V:${lang}:${id}` }],
    [{ text: T[lang].rep, web_app: { url: site(env, `prob/${id}/${lang}/prob`) } }, { text: T[lang].site, web_app: { url: site(env, 'map') } }],
    [{ text: T[lang].sub, callback_data: `B:${lang}:${id}` }, { text: T[lang].help, callback_data: `H:${lang}` }],
    [{ text: T[lang].adm, callback_data: `M:${lang}` }, { text: T[lang].back, callback_data: `L:${lang}` }],
  ] };
}
const helpKb = lang => ({ inline_keyboard: [[{ text: T[lang].pdf, callback_data: `P:${lang}` }], [{ text: T[lang].adm, callback_data: `M:${lang}` }]] });
// groups and channels cannot open Mini Apps from buttons: plain links
const postKb = (env, lang, id, bot) => ({ inline_keyboard: [[{ text: T[lang].rep, url: link(env, `prob/${id}/${lang}/prob`) }, { text: T[lang].site, url: link(env, 'map') }], ...(bot ? [[{ text: T[lang].bot, url: `https://t.me/${bot}` }]] : [])] });

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
  const A = AL[lang] || AL.ru, out = [A.title];
  const regs = [...new Set(items.map(i => i.region))];
  for (const rg of regs) {
    out.push('', `${FLAG[rg] || ''} <b>${esc(NAMES[rg] ? NAMES[rg][lang] : rg)}</b>`);
    for (const i of items.filter(x => x.region === rg).slice(0, 10)) {
      const w = i.snow ? (i.level > 1 ? A.s2 : A.s1) : (i.level > 1 ? A.r2 : A.r1);
      out.push(`${i.snow ? '❄️' : i.level > 1 ? '⛈' : '🌧'} <b>${esc(i.name[lang] || i.name.ru)}</b> — ${dayLabel(i.date, lang)}: ${w}, ~${Math.round(i.mm)} ${A.mm} (${i.p} %), ${A.peak} ${i.peak}`);
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
  const key = i => `${i.region}|${i.en}|${i.date}|${i.snow ? 's' : 'r'}`;
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
    dry: 'без осадков', rain: 'дождь', snow: 'снег', next: 'Дальше по дням', cDay: 'День', cT: 'Темп.', cP: 'Осадки', run: 'Расчёт',
    note: 'Осадки: вероятность за сутки и среднее количество по ансамблю моделей.', noRain: 'Зонт не понадобится', rainAt: '{w} вероятен {a}–{b} ч (до {p} %)', wear: 'Одежда' },
  uz: { brief: 'Qisqacha', allDry: '15 kun davomida sezilarli yog‘in kutilmaydi', wetNow: 'Bugunoq yog‘in bo‘lishi mumkin', dryUntil: '{d} gacha quruq',
    wetDays: 'Yog‘inli kunlar: {n}; eng kuchlisi {peak}', snowOn: 'Qor: {d}', cooler: 'Sovish: kunduzi {a} dan {b} gacha', warmer: 'Isish: kunduzi {a} dan {b} gacha',
    steady: 'Harorat keskin o‘zgarmaydi: kunduzi {a} … {b}', frost: 'Sovuq {t} gacha ({d})', wind: 'Kuchli shamol {w} m/s gacha ({d})', windW: 'shamol',
    dry: 'yog‘insiz', rain: 'yomg‘ir', snow: 'qor', next: 'Keyingi kunlar', cDay: 'Kun', cT: 'Harorat', cP: 'Yog‘in', run: 'Hisob',
    note: 'Yog‘in: sutkalik ehtimol va modellar ansamblining o‘rtacha miqdori.', noRain: 'Soyabon kerak bo‘lmaydi', rainAt: '{w} ehtimoli {a}–{b} soatlarda ({p} % gacha)', wear: 'Kiyim' },
  tr: { brief: 'Özet', allDry: '15 gün boyunca kayda değer yağış yok', wetNow: 'Bugünden itibaren yağış olası', dryUntil: '{d} dahil kuru',
    wetDays: 'Yağışlı gün: {n}; en kuvvetlisi {peak}', snowOn: 'Kar: {d}', cooler: 'Soğuma: gündüz {a} → {b}', warmer: 'Isınma: gündüz {a} → {b}',
    steady: 'Sıcaklıkta sert değişim yok: gündüz {a} … {b}', frost: 'Don {t} ({d})', wind: 'Kuvvetli rüzgâr {w} m/s ({d})', windW: 'rüzgâr',
    dry: 'yağışsız', rain: 'yağmur', snow: 'kar', next: 'Sonraki günler', cDay: 'Gün', cT: 'Sıcaklık', cP: 'Yağış', run: 'Hesaplama',
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
const mainKb = lang => ({ keyboard: [[{ text: PT[lang].locBtn, request_location: true }], [{ text: MK[lang].today }, { text: MK[lang].d15 }], [{ text: MK[lang].video }, { text: MK[lang].more }]], resize_keyboard: true, is_persistent: true });
const FILLER = new Set('погода погоду погоды прогноз в во на для город городе сегодня завтра какая какой ob-havo obhavo havo bugun ertaga shahar shahrida hava durumu bugün yarın için weather in today tomorrow'.split(' '));
// today and tomorrow hour by hour: the country's video with the main city's timing and clothing advice (prob/hourly.py)
async function sendHourly(env, chat, lang, id) {
  let H = null;
  for (const l of [lang, 'ru', 'uz']) { const r = await fetch(`${base(env)}/prob/hr/${id}_${l}.json`, { cf: { cacheTtl: 600 } }); if (r.ok) { H = await r.json(); break; } }
  if (!H) return sendToday(env, chat, lang, id);
  const K = PK[lang], X = { ru: ['Сегодня', 'Завтра', 'по часам'], uz: ['Bugun', 'Ertaga', 'soatma-soat'], tr: ['Bugün', 'Yarın', 'saat saat'] }[lang];
  const part = (lbl, d) => d ? `<b>${lbl}</b> ${d.range}\n☂️ ${d.rain}\n🧥 ${K.wear}: ${d.wear}` : '';
  const cap = [`${FLAG[id] || ''} <b>${esc(NAMES[id][lang])}</b> · ${esc(H.city)} — ${X[0].toLowerCase()} / ${X[1].toLowerCase()} ${X[2]}`, '', part(X[0], H.info.today), '', part(X[1], H.info.tomorrow)].join('\n').slice(0, 1024);
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
  const url = `${base(env)}/prob/${H.video}`, kb = menuKb(env, lang, id);
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
async function pointForecast(env, chat, lang, lat, lon, place) {
  const L = PT[lang], I = await memo('ptidx', 600e3, async () => (await fetch(`${base(env)}/prob/pt/index.json`, { cf: { cacheTtl: 600 } })).json().catch(() => null));
  await saveUser(env, chat, { place: JSON.stringify([lat, lon]) });
  if (!I || lat > 80 || lat <= -60) return tg(env, 'sendMessage', { chat_id: chat, text: L.far });
  const top = Math.ceil(lat / I.tile) * I.tile, left = Math.floor(lon / I.tile) * I.tile, n = I.n, S = I.steps.length;
  const r = await fetch(`${base(env)}/prob/pt/${top}_${left}.bin`, { cf: { cacheTtl: 600 } });
  if (!r.ok) return tg(env, 'sendMessage', { chat_id: chat, text: L.far });
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
  const rows = D.slice(2).map(x => `${pad(wd(x.d), 9)}${pad(`${f(x.lo)}…${f(x.hi)}°`, 10)}${bar(x.p)} ${pad(x.p < 20 ? '—' : `${x.p}%`, 4)}${x.mm >= 0.5 ? ` ${x.mm < 9.5 ? x.mm.toFixed(0) : Math.round(x.mm)} ${L.mm}` : ''}${x.snow && x.p >= 20 ? ' ❄' : ''}`);
  const nm = place ? `${FLAG[place[4]] || '📍'} <b>${esc(pname(place, lang))}</b>` : `📍 <b>${lat.toFixed(2)}, ${lon.toFixed(2)}</b>`;
  const loc = new Date(run + off * 3600e3), u = `${String(loc.getUTCDate()).padStart(2, '0')}.${String(loc.getUTCMonth() + 1).padStart(2, '0')} ${String(loc.getUTCHours()).padStart(2, '0')}:00`;
  const detail = x => {  // when it rains and what to wear (3-hour windows of that day)
    const ws = wins.filter(v => v.d === x.d), wet = ws.filter(v => v.p >= 40);
    let r = K.noRain;
    if (wet.length) { const top = wet.reduce((a, b) => (b.p > a.p ? b : a)); let a = top, b = top; const i = ws.indexOf(top);
      for (let j = i - 1; j >= 0 && ws[j].p >= 40; j--) a = ws[j]; for (let j = i + 1; j < ws.length && ws[j].p >= 40; j++) b = ws[j];
      r = K.rainAt.replace('{w}', x.snow ? K.snow : K.rain).replace('{a}', String(a.h1).padStart(2, '0')).replace('{b}', String(b.h2).padStart(2, '0')).replace('{p}', Math.round(top.p)); }
    return `\n      ☂️ ${r}\n      🧥 ${K.wear}: ${wearText(lang, x.lo, x.hi, x.p, x.snow, x.w)}`;
  };
  const day = (x, w) => `${x.ic} <b>${w}</b> · ${wd(x.d)}\n      ${deg(x.lo)}…${deg(x.hi)} · ${pr(x)}${isFinite(x.w) && x.w >= 5 ? ` · ${K.windW} ${Math.round(x.w)} ${L.ms}` : ''}${detail(x)}`;
  const text = [`${nm} · ${L.head}`, `<i>${K.run} ${u} (UTC${off >= 0 ? '+' : ''}${off}) · ECMWF, NOAA, DWD</i>`, '',
    `<b>${K.brief}</b>`, ...sum.map(x => `▸ ${x}`), '',
    day(D[0], D[0].d === today ? T[lang].tdy : wd(D[0].d)), ...(D[1] ? [day(D[1], D[1].d === tmrw ? T[lang].tmw : wd(D[1].d))] : []), '',
    ...(rows.length ? [`<b>${K.next}</b>`, `<pre>${esc(pad(K.cDay, 9) + pad(K.cT, 10) + K.cP)}\n${esc(rows.join('\n'))}</pre>`] : []),
    `<i>${K.note}</i>`].join('\n');
  const kb = place && NAMES[place[4]] ? { inline_keyboard: [[{ text: L.vid, callback_data: `C:${lang}:${place[4]}` }]] } : undefined;
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
  await tg(env, 'sendMessage', { chat_id: admin, text: `📊 <b>Бот за сутки</b> (${day})\n👤 Заходили: <b>${act.n}</b>\n🆕 Новых: <b>${neu.n}</b>\n👥 Всего пользователей: ${tot.n}\n💬 Групп и каналов: ${grp.n}\n🔔 Личных подписок: ${prv.n}\n🗣 Языки: ${langs.map(x => `${x.lang || '?'} ${x.n}`).join(', ') || '—'}${site}\n\n/users — список`, parse_mode: 'HTML' });
}
async function staleTick(env) {
  const M = await manifest(env); if (!M || !M.run) return;
  const age = (Date.now() - Date.parse(M.run)) / 3600e3;
  if (age < 33) return;
  const last = +(await kv(env, 'stale_at') || 0), admin = await kv(env, 'admin');
  if (!admin || Date.now() - last < 12 * 3600e3) return;
  await setKv(env, 'stale_at', String(Date.now()));
  await tg(env, 'sendMessage', { chat_id: admin, text: `⚠️ Данные сайта и бота не обновлялись ${Math.round(age)} ч (последний расчёт ${M.run.slice(0, 16)} UTC).\nПроверьте вкладку Actions в репозитории на GitHub.`, disable_web_page_preview: true });
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
    await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id });
    const [, , rid, ci] = cb.data.split(':'), C = await cities(env, rid, lang);
    if (!C || !C.cities.length) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].none });
    if (kind === 'Y') {
      const rows = []; C.cities.forEach((c, i) => { if (i % 3 === 0) rows.push([]); rows[rows.length - 1].push({ text: c.name, callback_data: `Z:${lang}:${rid}:${i}` }); });
      rows.push([{ text: T[lang].back, callback_data: `C:${lang}:${rid}` }]);
      return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[rid]} <b>${NAMES[rid][lang]}</b> · ${T[lang].cPick}`, parse_mode: 'HTML', reply_markup: { inline_keyboard: rows } });
    }
    const c = C.cities[+ci]; if (!c) return;
    const kb = { inline_keyboard: [[{ text: T[lang].cities, callback_data: `Y:${lang}:${rid}` }, { text: T[lang].back, callback_data: `C:${lang}:${rid}` }]] };
    const text = forecastText({ days: c.days, off: C.off, city: c.name }, lang, NAMES[rid][lang], rid, { more: c.video ? 4 : 5, limit: c.video ? 1024 : 4000 });
    if (!text) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].none, reply_markup: kb });
    if (c.video) {  // the precipitation video with this city's timeline (Uzbekistan and Kazakhstan)
      await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_video' });
      const url = `${base(env)}/prob/${c.video}`;
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
  await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id });
  if (chat.type === 'private') await saveUser(env, chat.id, who(cb.from));
  if (kind === 'S') {  // first language choice after /start: the guide, then the countries
    await saveUser(env, chat.id, { lang });
    await tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[lang], parse_mode: 'HTML', reply_markup: helpKb(lang) });
    await tg(env, 'sendMessage', { chat_id: chat.id, text: PT[lang].locHint, parse_mode: 'HTML', reply_markup: mainKb(lang) });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryKb(lang) });
  }
  if ((kind === 'AU' || kind === 'AY') && chat.type === 'private') return privateMsg({ chat, from: cb.from, message_id: cb.message.message_id, text: kind === 'AU' ? '/users' : '/yt' }, env);
  if (kind === 'Q') { const [, , la, lo] = cb.data.split(':'); return pointForecast(env, chat.id, lang, +la, +lo, await nearestPlace(env, +la, +lo, 5)); }
  if (kind === 'H') return tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[lang], parse_mode: 'HTML', reply_markup: helpKb(lang) });
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
      return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].subAsk.replace('{name}', nm), reply_markup: kb });
    }
    const h = +cb.data.split(':')[3];
    await saveSub(env, chat, [id], lang, todayTZ(), h);
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].subOk.replace('{time}', hh(h)).replace('{name}', nm), reply_markup: menuKb(env, lang, id) });
  }
  if (kind === 'L') return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryKb(lang) });
  if (kind === 'C') return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[id]} <b>${NAMES[id][lang]}</b> · ${T[lang].menu}`, parse_mode: 'HTML', reply_markup: menuKb(env, lang, id) });
  if (kind === 'T') return sendHourly(env, chat.id, lang, id);
  const M = await manifest(env);
  const items = M ? M.items.filter(i => i.region === id && i.lang === lang) : [];
  if (!items.length) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].none });
  const days = items.find(i => i.product === 'days');
  if (kind === 'D') return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[id]} <b>${NAMES[id][lang]}</b>\n\n${allDays(days, lang)}`, parse_mode: 'HTML', reply_markup: menuKb(env, lang, id) });
  if (kind === 'V') {
    let vids = ['prob', 'temp', 'cloud', 'wind'].map(p => items.find(i => (i.product || 'prob') === p)).filter(Boolean);
    if (!vids.length) vids = ['prob', 'temp', 'cloud', 'wind'].map(p => M.items.find(i => i.region === id && i.lang === 'ru' && (i.product || 'prob') === p)).filter(Boolean);
    const media = vids.map(v => ({ type: 'video', media: `${base(env)}/prob/${v.video}`, supports_streaming: true }));
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
    const url = `${base(env)}/prob/${b.video}`;
    let r = await tg(env, 'sendVideo', { chat_id: chat.id, video: url, caption: b.title, supports_streaming: true });
    if (!r.ok) { const f = await fetch(url); if (f.ok) { const fd = new FormData(); fd.append('chat_id', String(chat.id)); fd.append('caption', b.title); fd.append('supports_streaming', 'true'); fd.append('video', new Blob([await f.arrayBuffer()], { type: 'video/mp4' }), `osmon_${b.lang}.mp4`); r = await (await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendVideo`, { method: 'POST', body: fd })).json(); } }
    await tg(env, 'sendPhoto', { chat_id: chat.id, photo: `${base(env)}/prob/${b.thumb}`, caption: 'YouTube thumbnail' });
    const t = await (await fetch(`${base(env)}/prob/${b.text}`)).text().catch(() => '');
    return tg(env, 'sendMessage', { chat_id: chat.id, text: (r.ok ? '' : `⚠️ ${r.description || ''}\n${url}\n\n`) + t.slice(0, 4000), disable_web_page_preview: true });
  }
  if ((cmd === 'users' || text === ADMIN_BTN) && admin === String(chat.id)) {
    const rows = (await env.DB.prepare('SELECT * FROM users ORDER BY seen DESC LIMIT 100').all()).results;
    const n = (await env.DB.prepare('SELECT COUNT(*) AS n FROM users').first()).n;
    const lines = rows.map((x, i) => `${i + 1}. ${esc(x.name || '—')}${x.username ? ' @' + esc(x.username) : ''} · ${x.lang || '?'}${x.region ? ' · ' + (FLAG[x.region] || x.region) : ''} · ${(x.seen || '').slice(5, 16).replace('T', ' ')}`);
    const out = [`👤 <b>Users: ${n}</b> (last 100, UTC)`, ...lines]; let buf = '';
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
    return tg(env, 'sendMessage', { chat_id: chat.id, text: ids.length ? T[lang].admSent : T[lang].admOff, reply_markup: { inline_keyboard: [[{ text: T[lang].back, callback_data: `L:${lang}` }]] } });
  }
  if (cmd === 'guide') return sendGuide(env, chat.id, lang);
  if (cmd === 'alerts') { const A = await alertsData(env), rid = (u && NAMES[u.region] && u.region) || null; const it = A ? A.items.filter(i => !rid || i.region === rid) : []; return tg(env, 'sendMessage', { chat_id: chat.id, text: it.length ? alertText(it, lang) : AL[lang].none, parse_mode: 'HTML' }); }
  if (cmd === 'help') return tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[lang], parse_mode: 'HTML', reply_markup: helpKb(lang) });
  if (cmd === 'bugun' || cmd === 'today') return sendHourly(env, chat.id, u && u.lang && T[u.lang] ? u.lang : cmd === 'today' ? 'ru' : 'uz', (u && NAMES[u.region] && u.region) || 'UZ');
  if (cmd === 'prognoz') return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryKb(lang) });
  if (msg.location) {  // weather right here
    const { latitude: la, longitude: lo } = msg.location;
    await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'typing' });
    return pointForecast(env, chat.id, lang, la, lo, await nearestPlace(env, la, lo));
  }
  if (!text) return;
  if (!cmd) {  // the four buttons of the main keyboard (in any language)
    const rid = (u && NAMES[u.region] && u.region) || 'UZ';
    const hit = k => Object.values(MK).some(m => m[k] === text);
    if (hit('today')) return sendHourly(env, chat.id, lang, rid);
    if (hit('video')) return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[rid]} <b>${NAMES[rid][lang]}</b> · ${T[lang].menu}`, parse_mode: 'HTML', reply_markup: menuKb(env, lang, rid) });
    if (hit('more')) { await tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[lang], parse_mode: 'HTML', reply_markup: helpKb(lang) }); return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryKb(lang) }); }
    if (hit('d15')) {
      const pl = u && u.place ? JSON.parse(u.place) : null;
      if (pl) return pointForecast(env, chat.id, lang, pl[0], pl[1], await nearestPlace(env, pl[0], pl[1], 5));
      const cap = await nearestPlace(env, 41.31, 69.28, 5); return pointForecast(env, chat.id, lang, 41.31, 69.28, cap);
    }
  }
  if (!cmd && u && u.lang) {  // a town name (also "погода в Самарканде завтра"): search it anywhere in the world
    const q = text.split(/\s+/).filter(w => !FILLER.has(norm(w))).join(' ').trim() || text;
    let found = await searchPlaces(env, q);
    for (const v of [q.replace(/(ом|ем|ой|ей|ах|ях|е|у|ю|а|я|и|ы)$/iu, ''), q.replace(/(dagi|da|ga|ning|ni|dan|de|da|ta|te|'?(d|t)[ae])$/iu, '')])  // "в Самарканде", "Samarqandda", "Antalya'da"
      if (!found.length && v.length >= 3 && v !== q) found = await searchPlaces(env, v);
    if (found.length === 1 || (found.length && norm([found[0][0], found[0][1], found[0][2], found[0][3]].find(x => norm(x) === norm(q)) || '') === norm(q) && !found.slice(1).some(p => [p[0], p[1], p[2], p[3]].some(x => norm(x) === norm(q)))))
      return pointForecast(env, chat.id, lang, found[0][5], found[0][6], found[0]);
    if (found.length) return tg(env, 'sendMessage', { chat_id: chat.id, text: PT[lang].pick, reply_markup: { inline_keyboard: found.map(p => [{ text: `${FLAG[p[4]] || '📍'} ${pname(p, lang)}${NAMES[p[4]] ? ', ' + NAMES[p[4]][lang] : ' (' + p[4] + ')'}`, callback_data: `Q:${lang}:${p[5]}:${p[6]}` }]) } });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: PT[lang].nf, reply_markup: mainKb(lang) });
  }
  if (u && u.lang && T[u.lang]) await tg(env, 'sendMessage', { chat_id: chat.id, text: PT[u.lang].locHint, parse_mode: 'HTML', reply_markup: mainKb(u.lang) });
  const kb = langKb('S');  // a returning user goes straight back to the country they chose last time
  if (u && u.region && NAMES[u.region] && T[u.lang]) kb.inline_keyboard.push([{ text: `▶️ ${FLAG[u.region]} ${NAMES[u.region][u.lang]}`, callback_data: `C:${u.lang}:${u.region}` }]);
  return tg(env, 'sendMessage', { chat_id: chat.id, text: T.uz.hi + '\n\n' + T.ru.hi.split('\n').slice(0, 2).join('\n') + '\nВыберите язык:', parse_mode: 'HTML', reply_markup: kb });
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
  try { await env.DB.exec('ALTER TABLE subs ADD COLUMN post_hour INTEGER'); } catch (e) { /* already there */ }
  try { await env.DB.exec('ALTER TABLE subs ADD COLUMN alert_run TEXT'); } catch (e) { /* already there */ }
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
  const cap = forecastText(days, lang, NAMES[id][lang], id, { updated, more: 3, foot: T[lang].swipe, limit: 1024 });
  if (!cap) return { ok: false, description: 'no data' };
  if (!vids.length) return tg(env, 'sendMessage', { chat_id: chat, text: cap, parse_mode: 'HTML', reply_markup: postKb(env, lang, id, bot), disable_web_page_preview: true });
  const media = vids.map(v => ({ type: 'video', media: `${base(env)}/prob/${v.video}`, supports_streaming: true }));
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
