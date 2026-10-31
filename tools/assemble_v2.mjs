// node tools/assemble_v2.mjs regional_raw.json global_res.json out.json
// Wraps browser-collected snapshots (regional + global) into forecast.json v2.
import fs from 'node:fs';
import { REF, PROJ, GRID, GGRID, CLASSES, ELEV_MID, SEA_FROM, lonlatToCell } from '../pipeline/decode.js';
import { CITIES } from '../pipeline/cities.js';
const [rinp, ginp, out] = process.argv.slice(2);
const raw = JSON.parse(fs.readFileSync(rinp, 'utf8'));
const gres = ginp && fs.existsSync(ginp) ? JSON.parse(fs.readFileSync(ginp, 'utf8')) : {};
const run = raw.run;
const iso = h => new Date(Date.parse(run) + h * 3600e3).toISOString().replace('.000', '');
const region = {}, global = {};
for (const [k, L] of Object.entries(raw.layers)) {
  region[k] = { product: L.product, steps: L.steps, times: L.steps.map(iso), frames: L.frames };
  global[k] = { product: L.product, steps: L.steps, times: L.steps.map(iso), frames: L.steps.map(h => gres[k + '.' + h] || null) };
}
const data = {
  version: 2, generated: raw.generated, source: 'https://charts.ecmwf.int', model: 'ECMWF IFS HRES', run,
  classes: CLASSES, elevMid: ELEV_MID, seaFrom: SEA_FROM,
  region: { ref: REF, proj: PROJ, grid: GRID, elev: raw.elev, lines: raw.lines, layers: region },
  global: { grid: GGRID, layers: global },
  cities: CITIES.map(c => { const [gx, gy] = lonlatToCell(c.lon, c.lat); return { ...c, gx: +gx.toFixed(2), gy: +gy.toFixed(2), meteogram: null }; }),
  gallery: [],
};
fs.writeFileSync(out, JSON.stringify(data));
console.log('ok', (JSON.stringify(data).length / 1e6).toFixed(2) + ' MB', Object.fromEntries(Object.entries(global).map(([k, v]) => [k, v.frames.filter(Boolean).length + '/' + v.frames.length])));
