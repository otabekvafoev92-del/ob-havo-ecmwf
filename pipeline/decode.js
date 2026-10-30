// Decoding of ECMWF OpenCharts PNG maps (area "opencharts_western_asia")
// into numeric class grids. Pure functions on RGBA pixel arrays, so the same
// code runs in Node (build script) and in the browser (testing).
//
// Georeferencing: polar stereographic, fitted against a global land mask
// (agreement 95.9 % of pixels). Reference frame = the map frame of the
// "medium-orography" chart (1977 x 988 px inside a 2000 x 1800 PNG).

export const REF = { W: 1977, H: 988 };
export const PROJ = { lon0: 69.35884696, k: 1870.24101851, x0: 948.55152669, y0: -264.66850287 };
// x0/y0 above are relative to the reference frame's top-left corner.

// Region of interest in reference-frame pixels and grid cell size.
export const GRID = { X0: 600, Y0: 400, W: 660, H: 360, CELL: 2 };
GRID.GW = GRID.W / GRID.CELL; // 330
GRID.GH = GRID.H / GRID.CELL; // 180

export function lonlatToRef(lon, lat) {
  const r = PROJ.k * Math.tan((Math.PI / 180) * (45 - lat / 2));
  const a = (Math.PI / 180) * (lon - PROJ.lon0);
  return [PROJ.x0 + r * Math.sin(a), PROJ.y0 + r * Math.cos(a)];
}
export function refToLonlat(X, Y) {
  const dx = X - PROJ.x0, dy = Y - PROJ.y0;
  const r = Math.hypot(dx, dy) / PROJ.k;
  const lat = 90 - 2 * (180 / Math.PI) * Math.atan(r);
  const lon = PROJ.lon0 + (180 / Math.PI) * Math.atan2(dx, dy);
  return [lon, lat];
}
export function lonlatToCell(lon, lat) {
  const [X, Y] = lonlatToRef(lon, lat);
  return [(X - GRID.X0) / GRID.CELL, (Y - GRID.Y0) / GRID.CELL];
}
export function cellToLonlat(gx, gy) {
  return refToLonlat(GRID.X0 + gx * GRID.CELL, GRID.Y0 + gy * GRID.CELL);
}

// ---------- class tables (colours sampled from the charts' legends) ----------
const T = (lo, hi, rgb) => ({ lo, hi, rgb });
export const CLASSES = {
  temp: [ // 2 m temperature, °C
    T(-48, -28, [0, 0, 127]), T(-28, -24, [0, 0, 216]), T(-24, -20, [63, 0, 255]), T(-20, -16, [127, 0, 255]),
    T(-16, -12, [0, 127, 255]), T(-12, -8, [0, 255, 255]), T(-8, -4, [0, 255, 127]), T(-4, 0, [127, 255, 0]),
    T(0, 4, [217, 255, 0]), T(4, 8, [255, 255, 0]), T(8, 12, [255, 245, 0]), T(12, 16, [255, 217, 0]),
    T(16, 20, [255, 176, 0]), T(20, 24, [255, 127, 0]), T(24, 28, [255, 78, 0]), T(28, 32, [255, 37, 0]),
    T(32, 36, [255, 9, 0]), T(36, 40, [255, 0, 0]), T(40, 56, [255, 0, 255]),
  ],
  rain: [ // precipitation during last 6 h, mm (class 0 = below 0.5 mm, chart background)
    T(0, 0.5, null), T(0.5, 2, [0, 255, 255]), T(2, 4, [0, 127, 255]), T(4, 10, [0, 0, 255]),
    T(10, 25, [217, 0, 255]), T(25, 50, [255, 0, 255]), T(50, 100, [255, 127, 0]), T(100, 300, [255, 0, 0]),
  ],
  wind: [ // 10 m wind speed, m/s (class 0 = below 10 m/s, chart background)
    T(0, 10, null), T(10, 15, [255, 255, 102]), T(15, 20, [217, 255, 0]), T(20, 25, [147, 255, 0]),
    T(25, 30, [107, 165, 49]), T(30, 40, [0, 114, 75]), T(40, 50, [0, 84, 71]), T(50, 60, [0, 66, 71]), T(60, 80, [0, 51, 112]),
  ],
  sun: [ // sunshine duration over the last 24 h, hours
    T(0, 0.2, [13, 65, 68]), T(0.2, 2, [92, 117, 119]), T(2, 4, [138, 137, 101]), T(4, 6, [171, 168, 76]),
    T(6, 8, [200, 195, 51]), T(8, 10, [227, 224, 40]), T(10, 12, [255, 255, 0]), T(12, 14, [253, 211, 2]),
    T(14, 16, [253, 178, 2]), T(16, 18, [253, 136, 2]), T(18, 20, [253, 86, 2]), T(20, 22, [245, 163, 122]), T(22, 24, [240, 211, 197]),
  ],
  elev: [ // model orography, m; classes >= 13 are sea depth
    T(-500, 0, [61, 145, 99]), T(0, 50, [219, 255, 20]), T(50, 100, [198, 226, 33]), T(100, 200, [175, 198, 51]),
    T(200, 400, [89, 255, 2]), T(400, 700, [96, 204, 40]), T(700, 1000, [109, 163, 81]), T(1000, 1500, [214, 137, 84]),
    T(1500, 2000, [163, 104, 84]), T(2000, 3000, [114, 73, 45]), T(3000, 4000, [173, 112, 175]), T(4000, 5000, [160, 66, 165]),
    T(5000, 8000, [119, 0, 124]),
    // sea depth (m, positive down)
    T(0, 20, [140, 165, 206]), T(20, 50, [150, 214, 255]), T(50, 100, [96, 193, 255]), T(100, 200, [5, 158, 255]),
    T(200, 500, [45, 107, 255]), T(500, 1000, [0, 76, 255]), T(1000, 2000, [0, 56, 188]), T(2000, 5000, [10, 5, 150]), T(5000, 11000, [0, 0, 25]),
  ],
};
export const SEA_FROM = 13;
// Mid-values used for terrain height (m). Sea classes are flattened to 0.
export const ELEV_MID = [-30, 25, 75, 150, 300, 550, 850, 1250, 1750, 2500, 3500, 4500, 5600];

// Chart backgrounds that mean "class 0" for layers whose class 0 has no colour.
const BACKGROUNDS = {
  rain: [[255, 226, 171], [239, 219, 183], [255, 255, 255], [240, 220, 184]],
  wind: [[255, 226, 171], [239, 219, 183], [255, 255, 255], [240, 220, 184]],
};

function buildMatcher(layer, tol) {
  const list = [];
  CLASSES[layer].forEach((c, i) => { if (c.rgb) list.push([c.rgb[0], c.rgb[1], c.rgb[2], i]); });
  (BACKGROUNDS[layer] || []).forEach(rgb => list.push([rgb[0], rgb[1], rgb[2], 0]));
  const cache = new Map();
  return (r, g, b) => {
    const key = (r << 16) | (g << 8) | b;
    let v = cache.get(key);
    if (v !== undefined) return v;
    let best = -1, bd = tol;
    for (const q of list) {
      const d = Math.abs(q[0] - r) + Math.abs(q[1] - g) + Math.abs(q[2] - b);
      if (d < bd) { bd = d; best = q[3]; }
    }
    cache.set(key, best);
    return best;
  };
}

// Locate the map frame inside a chart PNG: the tallest run of rows that are
// mostly non-white, then the columns inside it.
export function frameBox(img) {
  const { W, H, d } = img;
  const nw = (x, y) => { const i = (y * W + x) * 4; return !(d[i] > 245 && d[i + 1] > 245 && d[i + 2] > 245); };
  let best = [0, 0], cur = null;
  for (let y = 0; y < H; y++) {
    let n = 0;
    for (let x = 0; x < W; x += 2) if (nw(x, y)) n++;
    if (n > 300) { if (cur === null) cur = y; if (y - cur > best[1] - best[0]) best = [cur, y]; } else cur = null;
  }
  const [top, bot] = best;
  const xs = [];
  for (let x = 0; x < W; x++) { let n = 0; for (let y = top; y <= bot; y += 2) if (nw(x, y)) n++; if (n > 100) xs.push(x); }
  return { top, bot, left: xs[0], right: xs[xs.length - 1] };
}
// Known frames, used when detection looks wrong (aspect must be ~2:1).
const KNOWN_FRAMES = {
  'medium-orography': { top: 201, bot: 1189, left: 11, right: 1988 },
  'medium-2t-wind': { top: 201, bot: 1189, left: 11, right: 1988 },
  'medium-rain-detailed': { top: 274, bot: 1262, left: 11, right: 1988 },
  'medium-sund_interval': { top: 255, bot: 1243, left: 11, right: 1988 },
  'medium-wind-10m': { top: 186, bot: 1123, left: 62, right: 1937 },
};
export function checkedFrame(img, product) {
  const f = frameBox(img);
  const w = f.right - f.left, h = f.bot - f.top;
  const ok = w > 1500 && Math.abs(w / h - REF.W / REF.H) < 0.03;
  return ok ? f : (KNOWN_FRAMES[product] || f);
}

// Decode a chart into a GW x GH Uint8Array of class indices (255 = unknown before filling).
export function decodeLayer(img, layer, product, opts = {}) {
  const tol = opts.tol ?? 36, rad = opts.rad ?? 2;
  const f = checkedFrame(img, product);
  const sx = (f.right - f.left) / REF.W, sy = (f.bot - f.top) / REF.H;
  const match = buildMatcher(layer, tol);
  const { GW, GH, X0, Y0, CELL } = GRID;
  const out = new Uint8Array(GW * GH).fill(255);
  const nC = CLASSES[layer].length;
  const cnt = new Uint16Array(nC);
  for (let gy = 0; gy < GH; gy++) {
    for (let gx = 0; gx < GW; gx++) {
      const cx = f.left + (X0 + (gx + 0.5) * CELL) * sx;
      const cy = f.top + (Y0 + (gy + 0.5) * CELL) * sy;
      cnt.fill(0);
      for (let dy = -rad; dy <= rad; dy++) for (let dx = -rad; dx <= rad; dx++) {
        const x = Math.round(cx + dx), y = Math.round(cy + dy);
        if (x < 0 || y < 0 || x >= img.W || y >= img.H) continue;
        const i = (y * img.W + x) * 4;
        const v = match(img.d[i], img.d[i + 1], img.d[i + 2]);
        if (v >= 0) cnt[v]++;
      }
      let b = 255, bn = 0;
      for (let k = 0; k < nC; k++) if (cnt[k] > bn) { bn = cnt[k]; b = k; }
      out[gy * GW + gx] = b;
    }
  }
  return fillUnknown(out, GW, GH);
}

// Replace unknown cells (255) by the majority of known neighbours, growing outwards.
export function fillUnknown(a, W, H) {
  let cur = a;
  for (let pass = 0; pass < 40; pass++) {
    let miss = 0;
    const next = cur.slice();
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const i = y * W + x;
      if (cur[i] !== 255) continue;
      miss++;
      const c = {};
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const X = x + dx, Y = y + dy;
        if (X < 0 || Y < 0 || X >= W || Y >= H) continue;
        const v = cur[Y * W + X];
        if (v !== 255) c[v] = (c[v] || 0) + 1;
      }
      let b = 255, bn = 0;
      for (const k in c) if (c[k] > bn) { bn = c[k]; b = +k; }
      next[i] = b;
    }
    cur = next;
    if (!miss) break;
  }
  for (let i = 0; i < cur.length; i++) if (cur[i] === 255) cur[i] = 0;
  return cur;
}

// Coast / border / lake outline mask at reference resolution (W x H of GRID),
// taken from the orography chart: dark pixels that are not a palette colour.
export function decodeLines(img) {
  const f = checkedFrame(img, 'medium-orography');
  const sx = (f.right - f.left) / REF.W, sy = (f.bot - f.top) / REF.H;
  const pal = CLASSES.elev.map(c => c.rgb);
  const out = new Uint8Array(GRID.W * GRID.H);
  for (let y = 0; y < GRID.H; y++) for (let x = 0; x < GRID.W; x++) {
    const px = Math.round(f.left + (GRID.X0 + x + 0.5) * sx), py = Math.round(f.top + (GRID.Y0 + y + 0.5) * sy);
    const i = (py * img.W + px) * 4;
    const r = img.d[i], g = img.d[i + 1], b = img.d[i + 2];
    const lum = 0.3 * r + 0.59 * g + 0.11 * b;
    if (lum > 120) continue;
    let near = 999;
    for (const c of pal) near = Math.min(near, Math.abs(c[0] - r) + Math.abs(c[1] - g) + Math.abs(c[2] - b));
    if (near < 40) continue;
    out[y * GRID.W + x] = lum < 50 ? 3 : lum < 85 ? 2 : 1; // strength
  }
  return out;
}

// ---------- compact text encoding: class -> letter, runs -> letter+count ----------
export function rle(arr) {
  let s = '', i = 0;
  while (i < arr.length) {
    let j = i;
    while (j < arr.length && arr[j] === arr[i]) j++;
    s += String.fromCharCode(65 + arr[i]) + (j - i > 1 ? (j - i) : '');
    i = j;
  }
  return s;
}
export function unrle(s, n) {
  const out = new Uint8Array(n);
  let p = 0;
  const re = /([A-Z])(\d*)/g;
  let m;
  while ((m = re.exec(s))) {
    const v = m[1].charCodeAt(0) - 65, c = m[2] ? +m[2] : 1;
    out.fill(v, p, p + c);
    p += c;
  }
  return out;
}

// Point value helper: class at fractional cell coordinates (nearest cell).
export function classAt(arr, gx, gy) {
  const x = Math.max(0, Math.min(GRID.GW - 1, Math.floor(gx)));
  const y = Math.max(0, Math.min(GRID.GH - 1, Math.floor(gy)));
  return arr[y * GRID.GW + x];
}

// ======================= global charts (area "opencharts_global") =======================
// Plate carrée: the map frame spans lon −180…180 and lat 90…−90 (verified against a land mask).
export const GGRID = { W: 720, H: 360, D: 0.5 }; // 0.5° cells, row 0 = 90°N, col 0 = 180°W
const G_REF = { W: 1977, H: 984 };
const G_KNOWN = {
  'medium-orography': { top: 201, bot: 1185, left: 11, right: 1988 },
  'medium-2t-wind': { top: 201, bot: 1185, left: 11, right: 1988 },
  'medium-rain-detailed': { top: 278, bot: 1262, left: 11, right: 1988 },
  'medium-sund_interval': { top: 259, bot: 1243, left: 11, right: 1988 },
  'medium-wind-10m': { top: 190, bot: 1123, left: 62, right: 1937 },
};
// Oceans are white on some global charts, so trust left/right/bottom and derive the top from the 2:1 aspect.
export function globalFrame(img, product) {
  const f = frameBox(img), k = G_KNOWN[product];
  const w = f.right - f.left;
  if (!(w > 1500)) return k;
  const g = { left: f.left, right: f.right, bot: f.bot, top: f.bot - Math.round(w * G_REF.H / G_REF.W) };
  if (k && (Math.abs(g.left - k.left) > 4 || Math.abs(g.right - k.right) > 4 || Math.abs(g.bot - k.bot) > 40)) return k;
  return g;
}
export function decodeGlobal(img, layer, product) {
  const f = globalFrame(img, product);
  const match = buildMatcher(layer, 36);
  const { W, H, D } = GGRID, nC = CLASSES[layer].length;
  const out = new Uint8Array(W * H).fill(255), cnt = new Uint16Array(nC);
  for (let j = 0; j < H; j++) {
    const cy = f.top + (j + 0.5) * D / 180 * (f.bot - f.top);
    for (let i = 0; i < W; i++) {
      const cx = f.left + (i + 0.5) * D / 360 * (f.right - f.left);
      cnt.fill(0);
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const x = Math.round(cx + dx), y = Math.round(cy + dy);
        if (x < 0 || y < 0 || x >= img.W || y >= img.H) continue;
        const q = (y * img.W + x) * 4, v = match(img.d[q], img.d[q + 1], img.d[q + 2]);
        if (v >= 0) cnt[v]++;
      }
      let b = 255, bn = 0;
      for (let k = 0; k < nC; k++) if (cnt[k] > bn) { bn = cnt[k]; b = k; }
      out[j * W + i] = b;
    }
  }
  return fillUnknown(out, W, H);
}
export const inRegion = (lon, lat) => { const [gx, gy] = lonlatToCell(lon, lat); return gx >= 0 && gy >= 0 && gx < GRID.GW && gy < GRID.GH; };
export const globalCell = (lon, lat) => [((lon + 180) % 360 + 360) % 360 / GGRID.D, (90 - lat) / GGRID.D];
