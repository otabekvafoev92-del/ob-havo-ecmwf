// Builds site/data from ECMWF OpenCharts (https://charts.ecmwf.int).
// Usage: node pipeline/build.mjs [outDir]
// Env: MAX_STEP (default 240), STEP_HOURS (6), DELAY_MS (900), GALLERY (1)
import fs from 'node:fs/promises';
import path from 'node:path';
import { PNG } from 'pngjs';
import {
  REF, PROJ, GRID, GGRID, CLASSES, ELEV_MID, SEA_FROM,
  decodeLayer, decodeLines, decodeGlobal, rle, lonlatToCell,
} from './decode.js';
import { CITIES } from './cities.js';
import { IR_PRODUCT, CLOUD_G, CLOUD_R, irGlobal, irRegion, cloudDensity } from './clouds.js';

const API = 'https://charts.ecmwf.int/opencharts-api/v1';
const AREA = 'opencharts_western_asia';
const OUT = path.resolve(process.argv[2] || 'site/data');
const MAX_STEP = +(process.env.MAX_STEP || 240);
const STEP_H = +(process.env.STEP_HOURS || 6);
const DELAY = +(process.env.DELAY_MS || 900);
const GALLERY = process.env.GALLERY !== '0';
const UA = { 'User-Agent': 'atmos-uz/1.0 (+https://github.com) weather site, ECMWF CC-BY-4.0' };

const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
let requests = 0;

async function getJson(url) {
  for (let attempt = 0; attempt < 7; attempt++) {
    requests++;
    await sleep(DELAY);
    let res, body;
    try {
      res = await fetch(url, { headers: UA });
      body = await res.text();
    } catch (e) {
      log('network error', e.message); await sleep(4000 * (attempt + 1)); continue;
    }
    if (res.status === 429 || /Too many requests/i.test(body)) { await sleep(6000 * (attempt + 1)); continue; }
    if (res.status >= 500) { await sleep(4000 * (attempt + 1)); continue; }
    try { return { status: res.status, json: JSON.parse(body) }; } catch { return { status: res.status, json: null }; }
  }
  throw new Error('gave up: ' + url);
}
async function getBuffer(url) {
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      const res = await fetch(url, { headers: UA });
      if (res.ok) return Buffer.from(await res.arrayBuffer());
      log('image status', res.status);
    } catch (e) { log('image error', e.message); }
    await sleep(3000 * (attempt + 1));
  }
  throw new Error('image failed: ' + url);
}
// Returns {href, description} or null when the product/step does not exist.
async function product(name, params, area = AREA) {
  const q = new URLSearchParams({ projection: area, ...params });
  const { status, json } = await getJson(`${API}/products/${name}/?${q}`);
  if (json && json.data && json.data.link) return { href: json.data.link.href, description: json.data.attributes?.description || '' };
  if (status !== 404 && status !== 400) log('no data', name, JSON.stringify(params), status, JSON.stringify(json).slice(0, 160));
  return null;
}
function readPng(buf) {
  const p = PNG.sync.read(buf);
  return { W: p.width, H: p.height, d: p.data };
}
const isoStep = (run, h) => new Date(Date.parse(run) + h * 3600e3).toISOString().replace('.000', '');

async function pickRun() {
  const { json } = await getJson(`${API}/schema/?package=openchart&product=medium-2t-wind`);
  const params = json?.paths?.['/products/medium-2t-wind/']?.get?.parameters || [];
  const bt = params.find(p => p.name === 'base_time');
  const runs = (bt?.schema?.enum || []).filter(s => /T(00|12):00:00Z$/.test(s));
  for (const run of runs.slice(0, 4)) {
    const ok = await product('medium-2t-wind', { base_time: run, step: MAX_STEP });
    if (ok) return run;
    log('run not complete yet:', run);
  }
  throw new Error('no complete 00/12 UTC run found');
}

async function saveGallery(buf, rel) {
  const file = path.join(OUT, rel);
  await fs.mkdir(path.dirname(file), { recursive: true });
  try {
    const sharp = (await import('sharp')).default;
    await sharp(buf).resize({ width: 1200 }).webp({ quality: 78 }).toFile(file.replace(/\.png$/, '.webp'));
    return rel.replace(/\.png$/, '.webp');
  } catch {
    await fs.writeFile(file, buf);
    return rel;
  }
}

async function buildClouds(run, runTag, tReg, tGlo) {
  const { unrle } = await import('./decode.js');
  const steps = tReg.steps, gG = [], gR = [];
  for (const h of steps) {
    const pg = await product(IR_PRODUCT, { base_time: run, step: h }, 'opencharts_global');
    const pr = await product(IR_PRODUCT, { base_time: run, step: h });
    gG.push(pg ? irGlobal(readPng(await getBuffer(pg.href))) : null);
    gR.push(pr ? irRegion(readPng(await getBuffer(pr.href))) : null);
    log('clouds', '+' + h + 'h', pg ? 'g' : '-', pr ? 'r' : '-');
  }
  const fill = a => a.map((v, i) => v || a.slice(0, i).reverse().find(Boolean) || a.find(Boolean));
  if (!gG.some(Boolean)) return null;
  const tg = tGlo.frames.map(f => f && unrle(f, GGRID.W * GGRID.H)), tr = tReg.frames.map(f => f && unrle(f, GRID.GW * GRID.GH));
  const dG = cloudDensity({ gray: fill(gG), temp: fill(tg), steps, W: CLOUD_G.W, H: CLOUD_G.H, CW: GGRID.W, CH: GGRID.H, wrap: true });
  const dR = gR.some(Boolean) ? cloudDensity({ gray: fill(gR), temp: fill(tr), steps, W: CLOUD_R.W, H: CLOUD_R.H, CW: GRID.GW, CH: GRID.GH, wrap: false }) : null;
  const sharp = (await import('sharp')).default, dir = path.join(OUT, 'clouds');
  await fs.rm(dir, { recursive: true, force: true }); await fs.mkdir(dir, { recursive: true });
  const name = (p, h) => `clouds/${runTag}_${p}${String(h).padStart(3, '0')}.jpg`;
  for (let i = 0; i < steps.length; i++) {
    await sharp(Buffer.from(dG[i]), { raw: { width: CLOUD_G.W, height: CLOUD_G.H, channels: 1 } }).jpeg({ quality: 82 }).toFile(path.join(OUT, name('g', steps[i])));
    if (dR) await sharp(Buffer.from(dR[i]), { raw: { width: CLOUD_R.W, height: CLOUD_R.H, channels: 1 } }).jpeg({ quality: 85 }).toFile(path.join(OUT, name('r', steps[i])));
  }
  return { product: IR_PRODUCT, steps, times: tReg.times, g: steps.map(h => name('g', h)), r: dR ? steps.map(h => name('r', h)) : null, gSize: CLOUD_G, rSize: CLOUD_R };
}

async function main() {
  await fs.mkdir(OUT, { recursive: true });
  const run = await pickRun();
  log('run', run);
  const runTag = run.slice(0, 13).replace(/[-T:]/g, '');

  // ---- terrain ----
  const oro = await product('medium-orography', {});
  if (!oro) throw new Error('orography unavailable');
  const oroImg = readPng(await getBuffer(oro.href));
  const elev = decodeLayer(oroImg, 'elev', 'medium-orography', { rad: 1 });
  const lines = decodeLines(oroImg);

  // ---- weather layers ----
  const layers = {
    temp: { product: 'medium-2t-wind', params: { layer_name: '2t' }, from: 0, every: STEP_H },
    rain: { product: 'medium-rain-detailed', params: {}, from: STEP_H, every: STEP_H },
    wind: { product: 'medium-wind-10m', params: {}, from: 0, every: STEP_H },
    sun: { product: 'medium-sund_interval', params: {}, from: 24, every: 24 },
  };
  const out = {}, outG = {};
  const galleryKeep = { 'medium-2t-wind': [], 'medium-rain-detailed': [], 'medium-wind-10m': [] };
  const galleryHours = new Set();
  for (let h = 12; h <= MAX_STEP; h += 24) galleryHours.add(h);

  for (const [key, L] of Object.entries(layers)) {
    const steps = [], times = [], frames = [], framesG = [];
    for (let h = L.from; h <= MAX_STEP; h += L.every) {
      steps.push(h); times.push(isoStep(run, h));
      const pg = await product(L.product, { base_time: run, step: h, ...L.params }, 'opencharts_global');
      framesG.push(pg ? rle(decodeGlobal(readPng(await getBuffer(pg.href)), key, L.product)) : null);
      const p = await product(L.product, { base_time: run, step: h, ...L.params });
      if (!p) { frames.push(null); continue; }
      const buf = await getBuffer(p.href);
      const grid = decodeLayer(readPng(buf), key, L.product);
      frames.push(rle(grid));
      if (GALLERY && galleryKeep[L.product] && galleryHours.has(h)) {
        const src = await saveGallery(buf, `maps/${L.product}/${runTag}_${String(h).padStart(3, '0')}.png`);
        galleryKeep[L.product].push({ step: h, valid: isoStep(run, h), src });
      }
      log(key, '+' + h + 'h', 'ok');
    }
    out[key] = { product: L.product, steps, times, frames };
    outG[key] = { product: L.product, steps, times, frames: framesG };
  }

  // ---- real clouds: ECMWF simulated infrared images ----
  const clouds = await buildClouds(run, runTag, out.temp, outG.temp);

  // ---- extra gallery-only charts ----
  const gallery = [
    { product: 'medium-2t-wind', title: { uz: '2 m harorat va 10 m shamol', ru: 'Температура 2 м и ветер 10 м' }, frames: galleryKeep['medium-2t-wind'] },
    { product: 'medium-rain-detailed', title: { uz: 'So‘nggi 6 soatdagi yog‘in', ru: 'Осадки за 6 часов' }, frames: galleryKeep['medium-rain-detailed'] },
    { product: 'medium-wind-10m', title: { uz: '10 m shamol va bosim', ru: 'Ветер 10 м и давление' }, frames: galleryKeep['medium-wind-10m'] },
  ];
  if (GALLERY) {
    for (const [name, title] of [
      ['medium-clouds', { uz: 'Umumiy bulutlilik', ru: 'Общая облачность' }],
      ['medium-mslp-wind850', { uz: 'Dengiz sathidagi bosim va 850 hPa shamol', ru: 'Давление у моря и ветер 850 гПа' }],
    ]) {
      const frames = [];
      for (const h of galleryHours) {
        const p = await product(name, { base_time: run, step: h });
        if (!p) continue;
        const src = await saveGallery(await getBuffer(p.href), `maps/${name}/${runTag}_${String(h).padStart(3, '0')}.png`);
        frames.push({ step: h, valid: isoStep(run, h), src });
        log('gallery', name, '+' + h + 'h');
      }
      gallery.push({ product: name, title, frames });
    }
  }

  // ---- ENS meteograms for preset points ----
  const cities = [];
  for (const c of CITIES) {
    const [gx, gy] = lonlatToCell(c.lon, c.lat);
    let meteogram = null;
    const q = new URLSearchParams({ lat: c.lat, lon: c.lon, epsgram: 'classical_10d' });
    const { json } = await getJson(`${API}/products/opencharts_meteogram/?${q}`);
    if (json?.data?.link?.href) {
      const rel = `meteo/${c.id}.png`;
      await fs.mkdir(path.join(OUT, 'meteo'), { recursive: true });
      await fs.writeFile(path.join(OUT, rel), await getBuffer(json.data.link.href));
      meteogram = rel;
      log('meteogram', c.id);
    }
    cities.push({ ...c, gx: +gx.toFixed(2), gy: +gy.toFixed(2), meteogram });
  }

  const data = {
    version: 2,
    generated: new Date().toISOString(),
    source: 'https://charts.ecmwf.int',
    model: 'ECMWF IFS HRES',
    area: AREA,
    run,
    classes: CLASSES, elevMid: ELEV_MID, seaFrom: SEA_FROM,
    region: { ref: REF, proj: PROJ, grid: GRID, elev: rle(elev), lines: rle(lines), layers: out },
    global: { grid: GGRID, layers: outG },
    cities,
    gallery,
    clouds,
    requests,
  };
  await fs.writeFile(path.join(OUT, 'forecast.json'), JSON.stringify(data));
  // keep only maps of the current run
  for (const g of gallery) {
    const dir = path.join(OUT, 'maps', g.product);
    try {
      for (const f of await fs.readdir(dir)) if (!f.startsWith(runTag)) await fs.rm(path.join(dir, f));
    } catch {}
  }
  log('done', 'requests:', requests, 'run:', run);
}

main().catch(e => { console.error(e); process.exit(1); });
