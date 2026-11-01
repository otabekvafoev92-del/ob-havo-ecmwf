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
    upd: 'Yangilandi', swipe: '🎬 Videoni suring: 🌧 yog‘in · 🌡 harorat · ☁️ bulutlar', bot: '🤖 Bot',
    gHi: '👋 Salom! Men har kuni shu yerga ob-havoni video bilan yuboraman.\nAdmin: til, davlat va vaqtni tanlang 👇',
    gSet: '✅ Tayyor! Har kuni soat {time} da (Toshkent vaqti) bu chatga prognoz yuboriladi: <b>{name}</b> ({lang}).\nO‘zgartirish: /sozla', gMulti: '📍 Davlatlarni tanlang (bir nechtasini ham), so‘ng «Tayyor» tugmasini bosing:', done: '✅ Tayyor', gNone: 'Kamida bitta davlatni tanlang.', gAdm: 'Faqat adminlar o‘zgartira oladi.', gLang: 'Tilni tanlang:', lang: 'o‘zbekcha',
  },
  ru: {
    cities: '🏙 Города', cPick: '🏙 Выберите город:', cTitle: '🏙 Сегодня по городам', time: '⏰ Во сколько присылать прогноз в группу? (по Ташкенту)', help: 'ℹ️ Помощь',
    d15: 'прогноз на 15 дней', hi: '☀️ <b>Osmon</b> — прогноз погоды\nна 15 дней по 6 моделям (ECMWF, NOAA).\n\nВыберите язык:', pick: '📍 Выберите страну или континент:',
    menu: 'Что показать?', today: '📅 Сегодня и завтра', all: '🎬 Видео на 15 дней', days: '🗓 По дням', site: '🌍 Глобус', rep: '📊 Отчёт',
    back: '↩️ Страны', none: '⏳ Данные ещё не готовы, попробуйте чуть позже.', tdy: 'Сегодня', tmw: 'Завтра', next: 'Дальше',
    upd: 'Обновлено', swipe: '🎬 Листайте видео: 🌧 осадки · 🌡 температура · ☁️ облака', bot: '🤖 Бот',
    gHi: '👋 Привет! Я буду каждый день присылать сюда прогноз погоды с видео.\nАдминистратор, выберите язык, страны и время 👇',
    gSet: '✅ Готово! Каждый день в {time} (по Ташкенту) в этот чат будет приходить прогноз: <b>{name}</b> ({lang}).\nИзменить: /settings', gMulti: '📍 Отметьте страны (можно несколько) и нажмите «Готово»:', done: '✅ Готово', gNone: 'Отметьте хотя бы одну страну.', gAdm: 'Менять настройки могут только администраторы.', gLang: 'Выберите язык:', lang: 'по-русски',
  },
  tr: {
    cities: '🏙 Şehirler', cPick: '🏙 Şehir seçin:', cTitle: '🏙 Bugün şehirlerde', time: '⏰ Tahmin gruba saat kaçta gönderilsin? (Taşkent saati)', help: 'ℹ️ Yardım',
    d15: '15 günlük tahmin', hi: '☀️ <b>Osmon</b> — hava tahmini\n6 modele göre 15 günlük (ECMWF, NOAA).\n\nDil seçin:', pick: '📍 Ülke veya kıta seçin:',
    menu: 'Ne göstereyim?', today: '📅 Bugün ve yarın', all: '🎬 15 günlük video', days: '🗓 Günlere göre', site: '🌍 Küre', rep: '📊 Rapor',
    back: '↩️ Ülkeler', none: '⏳ Veriler henüz hazır değil, biraz sonra deneyin.', tdy: 'Bugün', tmw: 'Yarın', next: 'Sonraki günler',
    upd: 'Güncellendi', swipe: '🎬 Videoları kaydırın: 🌧 yağış · 🌡 sıcaklık · ☁️ bulutlar', bot: '🤖 Bot',
    gHi: '👋 Merhaba! Her gün buraya videolu hava tahmini göndereceğim.\nYönetici: dil, ülke ve saati seçin 👇',
    gSet: '✅ Hazır! Her gün {time}’da (Taşkent saati) bu sohbete tahmin gönderilecek: <b>{name}</b> ({lang}).\nDeğiştirmek için: /settings', gMulti: '📍 Ülkeleri işaretleyin (birden fazla olabilir) ve «Tamam»a basın:', done: '✅ Tamam', gNone: 'En az bir ülke seçin.', gAdm: 'Ayarları yalnızca yöneticiler değiştirebilir.', gLang: 'Dil seçin:', lang: 'Türkçe',
  },
};
const HELP = {
  uz: `ℹ️ <b>Osmon bot — yo‘riqnoma</b>

<b>Shaxsiy chatda</b>
/start — til va davlatni tanlash
📅 <b>Bugun va ertaga</b> — asosiy shahar bo‘yicha qisqa prognoz
🗓 <b>Kunlar bo‘yicha</b> — 15 kun
🏙 <b>Shaharlar</b> — istalgan shahar uchun prognoz
🎬 <b>15 kunlik video</b> — yog‘in, harorat, bulutlar
📊 Hisobot / 🌍 Globus — sayt Telegram ichida ochiladi
/bugun — O‘zbekiston, bugun va ertaga

<b>Guruh yoki kanalda</b>
1. Botni guruhga qo‘shing (kanalda — admin qilib, «xabar yuborish» huquqi bilan).
2. Admin /sozla yozadi: til → davlatlar (bir nechta) → «Tayyor» → yuborish vaqti.
3. Har kuni tanlangan vaqtda har bir davlat uchun post keladi: 3 ta video + bugun/ertaga + shaharlar.
/bugun — guruhda hozirgi prognoz.

Ma’lumot: ECMWF IFS/AIFS, NOAA GFS/GEFS, DWD ICON. Kuniga 2 marta yangilanadi.`,
  ru: `ℹ️ <b>Бот Osmon — инструкция</b>

<b>В личном чате</b>
/start — выбрать язык и страну
📅 <b>Сегодня и завтра</b> — коротко по главному городу
🗓 <b>По дням</b> — все 15 дней
🏙 <b>Города</b> — прогноз для любого города страны
🎬 <b>Видео на 15 дней</b> — осадки, температура, облака
📊 Отчёт / 🌍 Глобус — сайт открывается прямо в Телеграме
/today — Узбекистан, сегодня и завтра

<b>В группе или канале</b>
1. Добавьте бота в группу (в канал — администратором с правом публикации).
2. Администратор пишет /settings: язык → страны (можно несколько) → «Готово» → время отправки.
3. Каждый день в выбранное время по каждой стране приходит пост: 3 видео + сегодня/завтра + погода по городам.
/bugun — прогноз в группу прямо сейчас.

Данные: ECMWF IFS/AIFS, NOAA GFS/GEFS, DWD ICON. Обновление 2 раза в сутки.`,
  tr: `ℹ️ <b>Osmon botu — kılavuz</b>

<b>Özel sohbette</b>
/start — dil ve ülke seçimi
📅 <b>Bugün ve yarın</b> — ana şehir için kısa tahmin
🗓 <b>Günlere göre</b> — 15 gün
🏙 <b>Şehirler</b> — herhangi bir şehir için tahmin
🎬 <b>15 günlük video</b> — yağış, sıcaklık, bulutlar
📊 Rapor / 🌍 Küre — site Telegram içinde açılır

<b>Grupta veya kanalda</b>
1. Botu gruba ekleyin (kanalda yönetici olarak, gönderme izniyle).
2. Yönetici /settings yazar: dil → ülkeler (birden fazla) → «Tamam» → gönderme saati.
3. Her gün seçilen saatte her ülke için gönderi gelir: 3 video + bugün/yarın + şehirler.

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
    const up = await req.json().catch(() => ({}));
    // answer Telegram at once; sending videos can take longer than its webhook timeout
    ctx.waitUntil(handle(up, env).catch(e => console.log('error', e && e.stack)));
    return new Response('ok');
  },
  async scheduled(ev, env, ctx) { ctx.waitUntil(broadcast(env).catch(e => console.log('broadcast', e && e.stack))); },
};

async function setup(env, url) {
  const hook = await tg(env, 'setWebhook', { url: `${url.origin}/`, allowed_updates: ['message', 'callback_query', 'my_chat_member', 'channel_post'] });
  await tg(env, 'setMyCommands', { commands: [{ command: 'start', description: 'Til / Язык / Dil' }, { command: 'bugun', description: 'Bugun va ertaga' }, { command: 'today', description: 'Сегодня и завтра' }, { command: 'prognoz', description: '15 kunlik video' }, { command: 'help', description: 'Yordam / Помощь' }] });
  await tg(env, 'setMyCommands', { scope: { type: 'all_group_chats' }, commands: [{ command: 'sozla', description: 'Davlat va til (adminlar uchun)' }, { command: 'settings', description: 'Страна и язык (для админов)' }, { command: 'bugun', description: 'Bugun va ertaga / Сегодня и завтра' }, { command: 'help', description: 'Yordam / Помощь' }] });
  await tg(env, 'setChatMenuButton', { menu_button: { type: 'web_app', text: 'Osmon', web_app: { url: site(env, 'map') } } });
  await tg(env, 'setMyShortDescription', { short_description: 'Ob-havo · Погода · Hava — 15 kun, 6 model (ECMWF, NOAA). Guruhlarga avtomatik prognoz.' });
  await tg(env, 'setMyDescription', { description: '☀️ Osmon — ob-havo prognozi 15 kunga\n🌧 Yog‘in ehtimoli, 🌡 harorat, ☁️ bulutlar — 6 ta model asosida (ECMWF IFS/AIFS, NOAA GFS/GEFS).\n🌍 Butun dunyo, qit’alar, MDH va Turkiya.\n👥 Guruh yoki kanalga qo‘shing — prognozni o‘zi yuboradi.\n\nПогода на 15 дней по 6 моделям. Добавьте в группу — бот сам будет присылать прогноз.' });
  if (env.DB) await db(env);
  const me = await tg(env, 'getMe', {});
  return new Response(hook.ok ? `OK: @${me.result && me.result.username} is connected. Open Telegram and send /start.` : `Error: ${JSON.stringify(hook)}`, { headers: { 'content-type': 'text/plain; charset=utf-8' } });
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
    [{ text: T[lang].back, callback_data: `L:${lang}` }],
  ] };
}
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
  if (msg && msg.text) {
    const chat = msg.chat, group = chat.type !== 'private';
    const cmd = (msg.text.trim().match(/^\/(\w+)(@\w+)?/) || [])[1];
    if (group) {
      if (cmd === 'sozla' || cmd === 'settings' || cmd === 'start') return tg(env, 'sendMessage', { chat_id: chat.id, text: T.uz.gLang + ' / ' + T.ru.gLang, reply_markup: langKb('GL') });
      if (cmd === 'help') { const s = await sub(env, chat.id); return tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[(s && s.lang) || 'ru'], parse_mode: 'HTML' }); }
      if (cmd === 'bugun' || cmd === 'today') { const s = await sub(env, chat.id), regs = regionsOf(s).length ? regionsOf(s) : ['UZ']; for (const r of regs) await sendToday(env, chat.id, s ? s.lang : cmd === 'today' ? 'ru' : 'uz', r, true); return; }
      return;
    }
    if (cmd === 'help') return tg(env, 'sendMessage', { chat_id: chat.id, text: HELP.ru + '\n\n' + HELP.uz, parse_mode: 'HTML' });
    if (cmd === 'bugun') return sendToday(env, chat.id, 'uz', 'UZ');
    if (cmd === 'today') return sendToday(env, chat.id, 'ru', 'UZ');
    if (cmd === 'prognoz') return tg(env, 'sendMessage', { chat_id: chat.id, text: T.uz.pick, reply_markup: countryKb('uz') });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T.uz.hi + '\n\n' + T.ru.hi.split('\n').slice(0, 2).join('\n') + '\nВыберите язык:', parse_mode: 'HTML', reply_markup: langKb() });
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
  if (kind === 'L') return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryKb(lang) });
  if (kind === 'C') return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[id]} <b>${NAMES[id][lang]}</b> · ${T[lang].menu}`, parse_mode: 'HTML', reply_markup: menuKb(env, lang, id) });
  if (kind === 'T') return sendToday(env, chat.id, lang, id);
  const M = await manifest(env);
  const items = M ? M.items.filter(i => i.region === id && i.lang === lang) : [];
  if (!items.length) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].none });
  const days = items.find(i => i.product === 'days');
  if (kind === 'D') return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[id]} <b>${NAMES[id][lang]}</b>\n\n${allDays(days, lang)}`, parse_mode: 'HTML', reply_markup: menuKb(env, lang, id) });
  if (kind === 'V') {
    const vids = ['prob', 'temp', 'cloud'].map(p => items.find(i => (i.product || 'prob') === p)).filter(Boolean);
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
  try { await env.DB.exec('ALTER TABLE subs ADD COLUMN post_hour INTEGER'); } catch (e) { /* already there */ }
}
async function sub(env, chat) { if (!env.DB) return null; await db(env); return env.DB.prepare('SELECT * FROM subs WHERE chat_id = ?1').bind(chat).first(); }
async function saveSub(env, chat, regions, lang, lastDay, hour = POST_HOUR) {
  if (!env.DB) return; await db(env);
  await env.DB.prepare('INSERT INTO subs (chat_id, title, type, region, lang, last_run, added, post_hour) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8) ON CONFLICT(chat_id) DO UPDATE SET title = ?2, region = ?4, lang = ?5, last_run = ?6, post_hour = ?8')
    .bind(chat.id, chat.title || '', chat.type, regions.join(','), lang, lastDay || '', new Date().toISOString(), hour).run();
}
async function memberChange(m, env) {
  const chat = m.chat, st = m.new_chat_member && m.new_chat_member.status;
  if (chat.type === 'private') return;
  if (st === 'left' || st === 'kicked') { if (env.DB) { await db(env); await env.DB.prepare('DELETE FROM subs WHERE chat_id = ?1').bind(chat.id).run(); } return; }
  if ((st === 'member' || st === 'administrator') && !(await sub(env, chat.id))) {
    await saveSub(env, chat, ['UZ'], 'uz', '');  // default until an admin chooses
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T.uz.gHi + '\n\n' + T.ru.gHi, reply_markup: langKb('GL') });
  }
}
async function isAdmin(env, chat, user) {
  if (chat.type === 'channel') return true;  // only admins can press buttons under a channel's own post anyway
  const r = await tg(env, 'getChatMember', { chat_id: chat.id, user_id: user.id });
  return r.ok && ['creator', 'administrator'].includes(r.result.status);
}
// one forecast post: the precipitation video with today, tomorrow and the next days in the caption, and link buttons
async function post(env, M, chat, lang0, id0, bot) {
  const lang = T[lang0] ? lang0 : 'uz', id = NAMES[id0] ? id0 : 'UZ';
  const items = M.items.filter(i => i.region === id && i.lang === lang);
  const days = items.find(i => i.product === 'days');
  const vids = ['prob', 'temp', 'cloud'].map(p => items.find(i => (i.product || 'prob') === p)).filter(Boolean);
  const updated = M.run.slice(8, 10) + '.' + M.run.slice(5, 7) + ' ' + M.run.slice(11, 16) + ' UTC';
  const cap = forecastText(days, lang, NAMES[id][lang], id, { updated, more: 3, foot: T[lang].swipe, limit: 1024 });
  if (!cap) return { ok: false, description: 'no data' };
  if (!vids.length) return tg(env, 'sendMessage', { chat_id: chat, text: cap, parse_mode: 'HTML', reply_markup: postKb(env, lang, id, bot), disable_web_page_preview: true });
  const media = vids.map(v => ({ type: 'video', media: `${base(env)}/prob/${v.video}`, supports_streaming: true }));
  media[0].caption = cap; media[0].parse_mode = 'HTML';
  let r = await tg(env, 'sendMediaGroup', { chat_id: chat, media });
  // Telegram could not fetch the videos by link: upload the files
  if (!r.ok && !/kicked|not a member|chat not found|have no rights|was deleted/i.test(r.description || '')) r = await uploadGroup(env, chat, media);
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
      const res = await post(env, M, s.chat_id, s.lang, r, bot);
      if (res.ok) sent++;
      // the bot was removed or cannot write there: forget the chat
      if (!res.ok && [400, 403].includes(res.error_code) && /kicked|not a member|chat not found|have no rights|was deleted/i.test(res.description || '')) { gone = true; break; }
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
