// Osmon Telegram bot — answers people on demand (Cloudflare Workers, free plan).
// The scheduled posts come from GitHub Actions (prob/telegram_send.py); this worker lets anyone ask the bot:
//   /start            choose language and country with buttons
//   /bugun /today     today and tomorrow in words for the chosen country
//   /prognoz          the 3 videos (rain & snow, temperature, clouds) + the next days in words
// Everything is read from the website built by GitHub Actions (SITE_URL/prob/manifest.json and the .mp4 files),
// so the bot needs no database: the choice travels inside the button data.
// Settings (Workers → Settings → Variables): BOT_TOKEN (secret), SITE_URL (e.g. https://name.github.io/repo).
// Connect once: open <worker URL>/setup in a browser (sets the webhook and the command menu).

const NAMES = {
  cis: { uz: 'MDH va Turkiya', ru: 'СНГ и Турция', tr: 'BDT ve Türkiye' }, UZ: { uz: 'O‘zbekiston', ru: 'Узбекистан', tr: 'Özbekistan' },
  KZ: { uz: 'Qozog‘iston', ru: 'Казахстан', tr: 'Kazakistan' }, KG: { uz: 'Qirg‘iziston', ru: 'Кыргызстан', tr: 'Kırgızistan' },
  TJ: { uz: 'Tojikiston', ru: 'Таджикистан', tr: 'Tacikistan' }, TM: { uz: 'Turkmaniston', ru: 'Туркменистан', tr: 'Türkmenistan' },
  AZ: { uz: 'Ozarbayjon', ru: 'Азербайджан', tr: 'Azerbaycan' }, AM: { uz: 'Armaniston', ru: 'Армения', tr: 'Ermenistan' },
  BY: { uz: 'Belarus', ru: 'Беларусь', tr: 'Belarus' }, MD: { uz: 'Moldova', ru: 'Молдова', tr: 'Moldova' },
  RU: { uz: 'Rossiya', ru: 'Россия', tr: 'Rusya' }, TR: { uz: 'Turkiya', ru: 'Турция', tr: 'Türkiye' },
};
const T = {
  uz: { d15: '15 kunlik prognoz', hi: 'Assalomu alaykum! Tilni tanlang:', pick: 'Davlatni tanlang:', menu: 'Nimani ko‘rsatay?', today: '📅 Bugun va ertaga', all: '🎬 15 kunlik video', days: '🗓 Kunlar bo‘yicha', site: '🌍 3D globus', back: '↩ Davlatlar', none: 'Ma’lumot hali tayyor emas, birozdan keyin urinib ko‘ring.' },
  ru: { d15: 'прогноз на 15 дней', hi: 'Здравствуйте! Выберите язык:', pick: 'Выберите страну:', menu: 'Что показать?', today: '📅 Сегодня и завтра', all: '🎬 Видео на 15 дней', days: '🗓 По дням', site: '🌍 3D-глобус', back: '↩ Страны', none: 'Данные ещё не готовы, попробуйте чуть позже.' },
  tr: { d15: '15 günlük tahmin', hi: 'Merhaba! Dil seçin:', pick: 'Ülke seçin:', menu: 'Ne göstereyim?', today: '📅 Bugün ve yarın', all: '🎬 15 günlük video', days: '🗓 Günlere göre', site: '🌍 3B küre', back: '↩ Ülkeler', none: 'Veriler henüz hazır değil, biraz sonra deneyin.' },
};
const WD = { uz: ['Yak', 'Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan'], ru: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'], tr: ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'] };

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (req.method === 'GET' && url.pathname === '/setup') {
      const hook = await tg(env, 'setWebhook', { url: `${url.origin}/`, allowed_updates: ['message', 'callback_query'] });
      await tg(env, 'setMyCommands', { commands: [{ command: 'start', description: 'Til / Язык / Dil' }, { command: 'bugun', description: 'Bugun va ertaga (O‘zbekiston)' }, { command: 'prognoz', description: '15 kunlik prognoz' }, { command: 'today', description: 'Сегодня и завтра' }] });
      const me = await tg(env, 'getMe', {});
      return new Response(hook.ok ? `OK: @${me.result && me.result.username} is connected. Open Telegram and send /start.` : `Error: ${JSON.stringify(hook)}`, { headers: { 'content-type': 'text/plain; charset=utf-8' } });
    }
    if (req.method !== 'POST') return new Response('Osmon bot is running. Open /setup once to connect it to Telegram.');
    const up = await req.json().catch(() => ({}));
    try { await handle(up, env); } catch (e) { console.log('error', e && e.stack); }
    return new Response('ok');
  },
};

async function tg(env, method, body) {
  const r = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  return r.json();
}
async function manifest(env) {
  const r = await fetch(`${env.SITE_URL.replace(/\/$/, '')}/prob/manifest.json`, { cf: { cacheTtl: 600 } });
  return r.ok ? r.json() : null;
}
const langKb = () => ({ inline_keyboard: [[{ text: 'O‘zbek', callback_data: 'L:uz' }, { text: 'Русский', callback_data: 'L:ru' }, { text: 'Türkçe', callback_data: 'L:tr' }]] });
function countryKb(lang) {
  const ids = Object.keys(NAMES), rows = [];
  for (let i = 0; i < ids.length; i += 3) rows.push(ids.slice(i, i + 3).map(id => ({ text: NAMES[id][lang], callback_data: `C:${lang}:${id}` })));
  return { inline_keyboard: rows };
}
function menuKb(env, lang, id) {
  return { inline_keyboard: [
    [{ text: T[lang].today, callback_data: `T:${lang}:${id}` }, { text: T[lang].days, callback_data: `D:${lang}:${id}` }],
    [{ text: T[lang].all, callback_data: `V:${lang}:${id}` }],
    [{ text: T[lang].site, url: `${env.SITE_URL.replace(/\/$/, '')}/#prob` }, { text: T[lang].back, callback_data: `L:${lang}` }],
  ] };
}
function dayLines(item, lang, from, count) {
  const out = [];
  for (const [d, txt] of Object.entries((item && item.days) || {})) {
    if (d < from) continue;
    const dt = new Date(d + 'T12:00:00Z');
    out.push(`<b>${WD[lang][dt.getUTCDay()]} ${String(dt.getUTCDate()).padStart(2, '0')}.${String(dt.getUTCMonth() + 1).padStart(2, '0')}</b> — ${txt}`);
    if (out.length >= count) break;
  }
  return out.join('\n');
}

async function handle(up, env) {
  const msg = up.message, cb = up.callback_query;
  if (msg && msg.text) {
    const chat = msg.chat.id, text = msg.text.trim();
    const lang = /^\/(bugun|prognoz)/.test(text) ? 'uz' : /^\/today/.test(text) ? 'ru' : null;
    if (text.startsWith('/start') || !lang) return tg(env, 'sendMessage', { chat_id: chat, text: T.uz.hi + '\n' + T.ru.hi, reply_markup: langKb() });
    return tg(env, 'sendMessage', { chat_id: chat, text: T[lang].pick, reply_markup: countryKb(lang) });
  }
  if (!cb) return;
  const chat = cb.message.chat.id, [kind, lang, id] = cb.data.split(':');
  await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id });
  if (kind === 'L') return tg(env, 'sendMessage', { chat_id: chat, text: T[lang].pick, reply_markup: countryKb(lang) });
  if (kind === 'C') return tg(env, 'sendMessage', { chat_id: chat, text: `<b>${NAMES[id][lang]}</b> · ${T[lang].menu}`, parse_mode: 'HTML', reply_markup: menuKb(env, lang, id) });
  const M = await manifest(env);
  const items = M ? M.items.filter(i => i.region === id && i.lang === lang) : [];
  if (!items.length) return tg(env, 'sendMessage', { chat_id: chat, text: T[lang].none });
  const days = items.find(i => i.product === 'days'), today = new Date(Date.now() + 5 * 3600e3).toISOString().slice(0, 10);
  if (kind === 'T' || kind === 'D') {
    const body = dayLines(days, lang, today, kind === 'T' ? 2 : 15);
    return tg(env, 'sendMessage', { chat_id: chat, text: `<b>${NAMES[id][lang]}</b>\n\n${body}`, parse_mode: 'HTML', reply_markup: menuKb(env, lang, id) });
  }
  if (kind === 'V') {
    const base = env.SITE_URL.replace(/\/$/, '') + '/prob/';
    const vids = ['prob', 'temp', 'cloud'].map(p => items.find(i => (i.product || 'prob') === p)).filter(Boolean);
    const media = vids.map(v => ({ type: 'video', media: base + v.video, supports_streaming: true }));
    media[0].caption = `<b>${NAMES[id][lang]}</b> · ${T[lang].d15}\n\n${dayLines(days, lang, today, 5)}`.slice(0, 1000);
    media[0].parse_mode = 'HTML';
    await tg(env, 'sendMediaGroup', { chat_id: chat, media });
    return tg(env, 'sendMessage', { chat_id: chat, text: T[lang].menu, reply_markup: menuKb(env, lang, id) });
  }
}
