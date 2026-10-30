// Real clouds from ECMWF "Simulated images – infrared" (medium-simulated-ir).
// The chart is a grey-scale brightness-temperature image: warm surface = dark, cold cloud tops = white.
// We strip coastlines/borders/graticule, then compare each pixel with the grey a cloud-free surface
// would have at the forecast 2 m temperature. The excess brightness is the cloud density.
import { CLASSES, GRID, GGRID } from './decode.js';

export const IR_PRODUCT = 'medium-simulated-ir';
// map frame of the IR chart (both projections), in chart pixels
export const IR_FRAME = { top: 248, bot: 1236, left: 11, right: 1988 };
export const CLOUD_G = { W: 1024, H: 512 };          // global, plate carrée, row 0 = 90°N
export const CLOUD_R = { W: GRID.W, H: GRID.H };     // Central Asia, 1 px = 1 reference pixel of the region grid

// clear-sky grey as a function of T2m (measured on cloud-free pixels of the global chart)
const CLEAR = [[-38, 236], [-26, 229], [-22, 218], [-18, 210], [-14, 194], [-10, 190], [-6, 181], [-2, 171], [2, 148], [6, 131], [10, 113], [14, 98], [18, 83], [22, 73], [26, 59], [30, 52]];
export function clearGray(t) {
  if (t <= CLEAR[0][0]) return CLEAR[0][1];
  for (let i = 1; i < CLEAR.length; i++) if (t <= CLEAR[i][0]) { const [t0, g0] = CLEAR[i - 1], [t1, g1] = CLEAR[i]; return g0 + (g1 - g0) * (t - t0) / (t1 - t0); }
  const [t0, g0] = CLEAR[CLEAR.length - 2], [t1, g1] = CLEAR[CLEAR.length - 1];
  return Math.max(20, g1 + (g1 - g0) * (t - t1) / (t1 - t0));
}

// img: {W, H, d (RGBA)}; returns the green channel of the frame with drawn lines removed
export function cleanGray(img, f = IR_FRAME) {
  const W = f.right - f.left, H = f.bot - f.top, n = W * H;
  const g0 = new Float32Array(n), rb = new Int16Array(n);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const i = ((y + f.top) * img.W + x + f.left) * 4, k = y * W + x; g0[k] = img.d[i + 1]; rb[k] = img.d[i] - img.d[i + 2]; }
  const pass = (src, horiz, fn, rad) => {
    const o = new Float32Array(n);
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      let v = src[y * W + x];
      for (let d = -rad; d <= rad; d++) { const X = horiz ? x + d : x, Y = horiz ? y : y + d; if (X < 0 || Y < 0 || X >= W || Y >= H) continue; v = fn(v, src[Y * W + X]); }
      o[y * W + x] = v;
    }
    return o;
  };
  const M = Math.max, m = Math.min;
  const C = pass(pass(pass(pass(g0, true, M, 3), false, M, 3), true, m, 3), false, m, 3); // closing: removes thin dark lines
  const O = pass(pass(pass(pass(g0, true, m, 1), false, m, 1), true, M, 1), false, M, 1); // opening: removes thin light lines
  const ok = new Uint8Array(n), g = new Float32Array(g0);
  for (let k = 0; k < n; k++) ok[k] = (C[k] - g0[k] > 16 || (g0[k] - O[k] > 8 && rb[k] >= 3) || rb[k] >= 6) ? 0 : 1;
  for (let it = 0; it < 14; it++) {
    const nk = [];
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const k = y * W + x; if (ok[k]) continue; let s = 0, c = 0;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { const X = x + dx, Y = y + dy; if (X < 0 || Y < 0 || X >= W || Y >= H) continue; const kk = Y * W + X; if (ok[kk] === 1) { s += g[kk]; c++; } }
      if (c) { g[k] = s / c; nk.push(k); }
    }
    for (const k of nk) ok[k] = 1; if (!nk.length) break;
  }
  for (let k = 0; k < n; k++) if (!ok[k]) g[k] = C[k];
  return { W, H, g };
}

// area-average resize of a float grid
export function resize(src, W, H, ow, oh) {
  const out = new Float32Array(ow * oh), sx = W / ow, sy = H / oh;
  for (let y = 0; y < oh; y++) {
    const y0 = y * sy, y1 = y0 + sy;
    for (let x = 0; x < ow; x++) {
      const x0 = x * sx, x1 = x0 + sx; let s = 0, w = 0;
      for (let Y = Math.floor(y0); Y < Math.min(H, Math.ceil(y1)); Y++) {
        const wy = Math.min(Y + 1, y1) - Math.max(Y, y0);
        for (let X = Math.floor(x0); X < Math.min(W, Math.ceil(x1)); X++) { const wx = Math.min(X + 1, x1) - Math.max(X, x0); s += src[Y * W + X] * wx * wy; w += wx * wy; }
      }
      out[y * ow + x] = w ? s / w : 0;
    }
  }
  return out;
}
// global IR chart -> CLOUD_G grey; regional IR chart -> CLOUD_R grey (crop of the region grid)
export const irGlobal = img => { const c = cleanGray(img); return resize(c.g, c.W, c.H, CLOUD_G.W, CLOUD_G.H); };
export const irRegion = img => cleanGray(img, { top: IR_FRAME.top + GRID.Y0, bot: IR_FRAME.top + GRID.Y0 + GRID.H, left: IR_FRAME.left + GRID.X0, right: IR_FRAME.left + GRID.X0 + GRID.W }).g;

function bilinearClassTemp(cls, CW, CH, ow, oh, wrap) {
  const mid = CLASSES.temp.map(c => (c.lo + c.hi) / 2), out = new Float32Array(ow * oh);
  for (let y = 0; y < oh; y++) for (let x = 0; x < ow; x++) {
    const fx = (x + 0.5) * CW / ow - 0.5, fy = Math.min(CH - 1, Math.max(0, (y + 0.5) * CH / oh - 0.5));
    const ix = Math.floor(fx), iy = Math.floor(fy), ax = fx - ix, ay = fy - iy;
    const X = i => wrap ? (i + CW) % CW : Math.min(CW - 1, Math.max(0, i)), Y = i => Math.min(CH - 1, i);
    const v = (i, j) => mid[cls[Y(j) * CW + X(i)]];
    out[y * ow + x] = (v(ix, iy) * (1 - ax) + v(ix + 1, iy) * ax) * (1 - ay) + (v(ix, iy + 1) * (1 - ax) + v(ix + 1, iy + 1) * ax) * ay;
  }
  return out;
}
function boxBlur(src, W, H, r) {
  const t = new Float32Array(src.length), o = new Float32Array(src.length);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { let s = 0, c = 0; for (let d = -r; d <= r; d++) { const X = x + d; if (X >= 0 && X < W) { s += src[y * W + X]; c++; } } t[y * W + x] = s / c; }
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { let s = 0, c = 0; for (let d = -r; d <= r; d++) { const Y = y + d; if (Y >= 0 && Y < H) { s += t[Y * W + x]; c++; } } o[y * W + x] = s / c; }
  return o;
}

// gray[i]: Float32Array (W×H) per step; temp[i]: class grid (CW×CH) per step or null; steps[i]: lead time (h)
// returns Uint8Array density per step (0 = clear, 255 = thick cold cloud)
export function cloudDensity({ gray, temp, steps, W, H, CW, CH, wrap }) {
  const n = W * H;
  const ex = gray.map((g, i) => {
    const tc = temp[i] || temp[Math.max(0, i - 1)];
    const T = bilinearClassTemp(tc, CW, CH, W, H, wrap), e = new Float32Array(n);
    for (let k = 0; k < n; k++) e[k] = g[k] - clearGray(T[k]);
    return e;
  });
  // per pixel and time of day: the lowest excess over all days is the surface bias (clear days exist)
  const bias = {};
  for (const hod of [0, 6, 12, 18]) {
    const idx = steps.map((s, i) => [s, i]).filter(([s]) => s % 24 === hod).map(([, i]) => i);
    const b = new Float32Array(n).fill(1e9);
    for (const i of idx) for (let k = 0; k < n; k++) b[k] = Math.min(b[k], ex[i][k]);
    for (let k = 0; k < n; k++) b[k] = Math.max(-30, Math.min(25, b[k] === 1e9 ? 0 : b[k]));
    bias[hod] = boxBlur(b, W, H, 3);
  }
  return ex.map((e, i) => {
    const b = bias[steps[i] % 24] || bias[0], o = new Uint8Array(n);
    for (let k = 0; k < n; k++) { const v = (e[k] - b[k] - 14) / 105; o[k] = v <= 0 ? 0 : Math.round(Math.pow(Math.min(1, v), 0.8) * 255); }
    return o;
  });
}
export { GGRID };
