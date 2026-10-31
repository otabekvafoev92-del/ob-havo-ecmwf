// node tools/assemble_demo.mjs raw.json out.json  — wraps a browser-collected snapshot into forecast.json
import fs from 'node:fs';
import { REF, PROJ, GRID, CLASSES, ELEV_MID, SEA_FROM, lonlatToCell } from '../pipeline/decode.js';
import { CITIES } from '../pipeline/cities.js';
const [inp, out] = process.argv.slice(2);
const raw = JSON.parse(fs.readFileSync(inp, 'utf8'));
const run = raw.run;
const iso = h => new Date(Date.parse(run) + h * 3600e3).toISOString().replace('.000', '');
const layers = {};
for (const [k, L] of Object.entries(raw.layers)) layers[k] = { product: L.product, steps: L.steps, times: L.steps.map(iso), frames: L.frames };
const data = {
  version: 1, generated: raw.generated, source: 'https://charts.ecmwf.int', model: 'ECMWF IFS HRES', area: 'opencharts_western_asia', run,
  ref: REF, proj: PROJ, grid: GRID, classes: CLASSES, elevMid: ELEV_MID, seaFrom: SEA_FROM,
  elev: raw.elev, lines: raw.lines, layers,
  cities: CITIES.map(c => { const [gx, gy] = lonlatToCell(c.lon, c.lat); return { ...c, gx: +gx.toFixed(2), gy: +gy.toFixed(2), meteogram: null }; }),
  gallery: [],
};
fs.writeFileSync(out, JSON.stringify(data));
console.log('ok', JSON.stringify(data).length, Object.fromEntries(Object.entries(layers).map(([k, v]) => [k, v.frames.filter(Boolean).length + '/' + v.frames.length])));
