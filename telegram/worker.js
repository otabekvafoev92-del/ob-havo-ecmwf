// Osmon bot — paused while the new version is built (the old bot: branch legacy-v1).
// Every message gets a short note; no menus, no notifications. The user list (D1 "osmon") is kept untouched.
const NOTE = {
  ru: '🔧 Osmon обновляется: мы полностью перестраиваем бота и сайт. Скоро вернёмся с новой версией — она придёт сюда же.',
  uz: '🔧 Osmon yangilanmoqda: bot va sayt butunlay qayta qurilmoqda. Tez orada yangi versiya bilan qaytamiz — shu yerga keladi.'
};
async function tg(env, method, body) {
  return fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
}
async function lang(env, id) {
  try { const r = await env.DB.prepare('SELECT lang FROM users WHERE chat_id = ?1').bind(id).first(); return r && r.lang === 'uz' ? 'uz' : 'ru'; } catch (e) { return 'ru'; }
}
export default {
  async fetch(req, env) {
    if (req.method !== 'POST') return new Response('Osmon: new version coming soon', { status: 200 });
    let u; try { u = await req.json(); } catch (e) { return new Response('ok'); }
    const m = u.message || u.edited_message, cb = u.callback_query;
    const chat = m ? m.chat : cb && cb.message ? cb.message.chat : null;
    if (cb) await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id });
    if (chat && chat.type === 'private') {
      const L = await lang(env, chat.id);
      await tg(env, 'sendMessage', { chat_id: chat.id, text: NOTE[L], reply_markup: { remove_keyboard: true } });
    }
    return new Response('ok');
  },
  async scheduled(ev, env) {  // paused: no notifications; the old menu button and command list are taken away
    for (const lc of [undefined, 'ru', 'uz', 'tr']) await tg(env, 'deleteMyCommands', lc ? { language_code: lc } : {});
    await tg(env, 'setChatMenuButton', { menu_button: { type: 'default' } });
  }
};
