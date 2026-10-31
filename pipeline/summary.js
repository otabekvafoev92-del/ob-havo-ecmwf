// Point forecast summaries from forecast.json (shared logic, also mirrored in site/app.js).
import { unrle, classAt } from './decode.js';

const TZ_OFFSET_H = 5; // Asia/Tashkent

export function pointSeries(data, gx, gy) {
  const R = data.region || data; // v2 keeps the regional grid under "region"
  const n = R.grid.GW * R.grid.GH;
  const res = {};
  for (const [key, L] of Object.entries(R.layers)) {
    res[key] = L.frames.map((f, i) => {
      if (!f) return null;
      const k = classAt(unrle(f, n), gx, gy);
      const c = data.classes[key][k];
      return { time: L.times[i], k, lo: c.lo, hi: c.hi };
    });
  }
  return res;
}

const localDate = iso => new Date(Date.parse(iso) + TZ_OFFSET_H * 3600e3).toISOString().slice(0, 10);
const utcHour = iso => new Date(iso).getUTCHours();

// Daily summary keyed by local date (Tashkent).
export function daily(series) {
  const days = new Map();
  const day = d => { if (!days.has(d)) days.set(d, { date: d, tDay: null, tNight: null, rain: [0, 0], rainN: 0, wind: 0, sun: null }); return days.get(d); };
  for (const s of series.temp) {
    if (!s) continue;
    const h = utcHour(s.time), D = day(localDate(s.time));
    if (h === 6 || h === 12) { if (!D.tDay || s.k > D.tDay.k) D.tDay = s; }
    if (h === 0) { if (!D.tNight || s.k < D.tNight.k) D.tNight = s; }
  }
  for (const s of series.rain) {
    if (!s) continue;
    // 6-h window ending at s.time belongs to the local day of its midpoint
    const D = day(localDate(new Date(Date.parse(s.time) - 3 * 3600e3).toISOString()));
    if (s.k > 0) { D.rain[0] += s.lo; D.rain[1] += s.hi; }
    D.rainN++;
  }
  for (const s of series.wind) { if (s) { const D = day(localDate(s.time)); D.wind = Math.max(D.wind, s.k ? s.lo : 0); } }
  for (const s of series.sun) { if (s) { const D = day(localDate(new Date(Date.parse(s.time) - 12 * 3600e3).toISOString())); D.sun = s; } }
  return [...days.values()].filter(d => d.tDay || d.tNight).sort((a, b) => a.date.localeCompare(b.date));
}

export const fmtT = c => c ? `${c.lo > 0 ? '+' : ''}${c.lo}…${c.hi > 0 ? '+' : ''}${c.hi}°` : '—';
export const fmtRain = r => r[1] === 0 ? '0' : `${round(r[0])}–${round(r[1])}`;
const round = v => v < 10 ? Math.round(v * 10) / 10 : Math.round(v);
