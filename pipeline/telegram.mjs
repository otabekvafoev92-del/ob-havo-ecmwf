// Sends a daily summary to Telegram after build.
// Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (required), SITE_URL, TG_LANG (uz|ru), TG_CITIES (comma ids)
import fs from 'node:fs/promises';
import path from 'node:path';
import { pointSeries, daily, fmtT, fmtRain } from './summary.js';

const token = process.env.TELEGRAM_BOT_TOKEN, chat = process.env.TELEGRAM_CHAT_ID;
const DRY = process.env.DRY_RUN === '1';
if (!DRY && (!token || !chat)) { console.log('Telegram: secrets not set, skipping'); process.exit(0); }
const OUT = path.resolve(process.argv[2] || 'site/data');
const lang = process.env.TG_LANG === 'ru' ? 'ru' : 'uz';
const pick = (process.env.TG_CITIES || 'toshkent,samarqand,buxoro,andijon,fargona,namangan,nukus,termiz').split(',');
const site = process.env.SITE_URL || '';

const L = {
  uz: { title: 'ECMWF prognozi', day: 'kunduzi', night: 'tunda', rain: 'yog‘in', mm: 'mm', wind: 'shamol', ms: 'm/s', run: 'Model ishga tushirilgan', more: 'Batafsil 3D xaritada', today: 'Bugun', tomorrow: 'Ertaga', src: 'Manba: ECMWF (CC BY 4.0), charts.ecmwf.int', note: 'Harorat ECMWF shkalasi bo‘yicha 4° oraliqda.' },
  ru: { title: 'Прогноз ECMWF', day: 'днём', night: 'ночью', rain: 'осадки', mm: 'мм', wind: 'ветер', ms: 'м/с', run: 'Запуск модели', more: 'Подробно на 3D-карте', today: 'Сегодня', tomorrow: 'Завтра', src: 'Источник: ECMWF (CC BY 4.0), charts.ecmwf.int', note: 'Температура — интервал шкалы ECMWF (4°).' },
}[lang];

const esc = s => String(s).replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));

async function tg(method, body, isForm = false) {
  const res = await fetch(`https://api.telegram.org/bot${token}/${method}`, isForm
    ? { method: 'POST', body }
    : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const j = await res.json();
  if (!j.ok) throw new Error(`${method}: ${j.description}`);
  return j;
}

const data = JSON.parse(await fs.readFile(path.join(OUT, 'forecast.json'), 'utf8'));
const todayLocal = new Date(Date.now() + 5 * 3600e3).toISOString().slice(0, 10);
const lines = [];
for (const label of [L.today, L.tomorrow]) {
  const offset = label === L.today ? 0 : 1;
  const date = new Date(Date.parse(todayLocal) + offset * 864e5).toISOString().slice(0, 10);
  lines.push(`\n<b>${label}, ${date.slice(8, 10)}.${date.slice(5, 7)}</b>`);
  for (const id of pick) {
    const c = data.cities.find(x => x.id === id);
    if (!c) continue;
    const d = daily(pointSeries(data, c.gx, c.gy)).find(x => x.date === date);
    if (!d) continue;
    let s = `${esc(c[lang])}: ${L.day} ${fmtT(d.tDay)}, ${L.night} ${fmtT(d.tNight)}`;
    if (d.rain[1] > 0) s += `, ${L.rain} ${fmtRain(d.rain)} ${L.mm}`;
    if (d.wind >= 10) s += `, ${L.wind} ≥${d.wind} ${L.ms}`;
    lines.push(s);
  }
}
const runLocal = new Date(Date.parse(data.run) + 5 * 3600e3).toISOString().slice(0, 16).replace('T', ' ');
let text = `🌦 <b>${L.title}</b>\n${L.run}: ${runLocal} (UZT)` + lines.join('\n') + `\n\n<i>${L.note}</i>\n${L.src}`;
if (site) text += `\n<a href="${site}">${L.more}</a>`;
if (DRY) { console.log(text); process.exit(0); }
await tg('sendMessage', { chat_id: chat, text, parse_mode: 'HTML', disable_web_page_preview: true });

const tash = data.cities.find(c => c.id === 'toshkent');
if (tash?.meteogram) {
  const form = new FormData();
  form.append('chat_id', chat);
  form.append('caption', `ECMWF ENS meteogramma — ${tash[lang]}`);
  form.append('photo', new Blob([await fs.readFile(path.join(OUT, tash.meteogram))], { type: 'image/png' }), 'meteogram.png');
  await tg('sendPhoto', form, true);
}
console.log('Telegram: sent');
