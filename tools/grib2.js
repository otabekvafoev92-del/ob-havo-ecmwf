// Minimal GRIB2 decoder for one message (regular lat/lon grids).
// Supports data representation templates 5.0 (simple), 5.3 (complex + spatial differencing, NCEP)
// and 5.42 (CCSDS/AEC, ECMWF open data). Works in the browser and in Node.
// decodeGrib2(u8) -> { Ni, Nj, la1, lo1, la2, lo2, di, dj, scan, values: Float32Array }

class Bits {
  constructor(u8, pos = 0) { this.u8 = u8; this.p = pos * 8; }
  read(n) { // n <= 32
    let v = 0;
    while (n > 0) {
      const byte = this.u8[this.p >> 3], off = this.p & 7, take = Math.min(8 - off, n);
      v = v * (1 << take) + ((byte >> (8 - off - take)) & ((1 << take) - 1));
      this.p += take; n -= take;
    }
    return v;
  }
  fs() { // count zeros up to the next 1 (fundamental sequence)
    let n = 0;
    for (;;) {
      const off = this.p & 7, byte = (this.u8[this.p >> 3] << off) & 0xff;
      if (byte === 0) { n += 8 - off; this.p += 8 - off; continue; }
      const lz = Math.clz32(byte) - 24; n += lz; this.p += lz + 1; return n;
    }
  }
  align() { this.p = (this.p + 7) & ~7; }
}

const sm16 = (dv, o) => { const v = dv.getUint16(o); return v & 0x8000 ? -(v & 0x7fff) : v; };
const smN = (u8, o, n) => { let v = 0; for (let i = 0; i < n; i++) v = v * 256 + u8[o + i]; const top = 2 ** (8 * n - 1); return v >= top ? -(v - top) : v; };

// CCSDS 121.0-B adaptive entropy decoder (as used by libaec), returns Uint32 samples
function aecDecode(u8, nbits, flags, bsize, rsi, n) {
  const out = new Uint32Array(n);
  const pre = !!(flags & 8), restricted = !!(flags & 16), padRsi = !!(flags & 32);
  let idLen = nbits > 16 ? 5 : nbits > 8 ? 4 : 3;
  if (restricted && nbits <= 4) idLen = nbits <= 2 ? 1 : 2;
  const idMax = (1 << idLen) - 1, xmax = nbits >= 32 ? 0xffffffff : (2 ** nbits) - 1, med = Math.floor(xmax / 2) + 1;
  const b = new Bits(u8);
  let o = 0;
  const rsiSamples = rsi * bsize;
  while (o < n) {
    const rsiStart = o;
    const rsiEnd = Math.min(n, rsiStart + rsiSamples);
    let blk = 0;
    const res = []; // residuals of this RSI (before post-processing)
    while (rsiStart + blk * bsize < rsiEnd) {
      const ref = pre && blk === 0 ? 1 : 0;
      const id = b.read(idLen);
      if (id === 0) {
        const se = b.read(1);
        if (ref) res.push(b.read(nbits));
        if (se) { // second extension
          let i = ref;
          while (i < bsize) {
            const m = b.fs();
            let beta = Math.floor((Math.sqrt(8 * m + 1) - 1) / 2);
            while (((beta + 1) * (beta + 2)) / 2 <= m) beta++;
            while ((beta * (beta + 1)) / 2 > m) beta--;
            const d1 = m - (beta * (beta + 1)) / 2;
            if ((i & 1) === 0) { res.push(beta - d1); i++; }
            res.push(d1); i++;
          }
        } else { // zero blocks
          let z = b.fs() + 1;
          if (z === 5) { const rsiBlocks = Math.ceil((rsiEnd - rsiStart) / bsize); z = Math.min(rsiBlocks - blk, 64 - (blk % 64)); }
          else if (z > 5) z--;
          for (let i = 0; i < z * bsize - ref; i++) res.push(0);
          blk += z;
          continue;
        }
      } else if (id === idMax) { // uncompressed
        if (ref) res.push(b.read(nbits));
        for (let i = ref; i < bsize; i++) res.push(b.read(nbits));
      } else { // split sample, k = id - 1
        const k = id - 1;
        if (ref) res.push(b.read(nbits));
        const start = res.length;
        for (let i = ref; i < bsize; i++) res.push(b.fs() * (2 ** k));
        if (k) for (let i = start; i < res.length; i++) res[i] += b.read(k);
      }
      blk++;
    }
    // post-process (unit-delay predictor, unsigned data)
    const cnt = rsiEnd - rsiStart;
    if (pre) {
      let data = res[0]; out[o++] = data;
      for (let i = 1; i < cnt; i++) {
        const d = res[i], half = Math.floor(d / 2) + (d & 1);
        const big = data >= med;
        const room = big ? xmax - data : data;
        if (half <= room) data = d & 1 ? data - half : data + Math.floor(d / 2);
        else data = big ? xmax - d : d;
        out[o++] = data;
      }
    } else for (let i = 0; i < cnt; i++) out[o++] = res[i];
    if (padRsi) b.align();
  }
  return out;
}

function complexDecode(u8, s5, n, dv5) {
  // u8: section 7 payload (after the 5-byte header); s5: section 5 bytes
  const d = new DataView(s5.buffer, s5.byteOffset, s5.length);
  const nbits = s5[19], mvm = s5[22], NG = d.getUint32(31), refW = s5[35], bitsW = s5[36];
  const refL = d.getUint32(37), incL = s5[41], lastL = d.getUint32(42), bitsL = s5[46];
  const order = s5[47], ostep = s5[48];
  let pos = 0, ival1 = 0, ival2 = 0, minsd = 0;
  if (order > 0) { ival1 = smN(u8, pos, ostep); pos += ostep; if (order === 2) { ival2 = smN(u8, pos, ostep); pos += ostep; } minsd = smN(u8, pos, ostep); pos += ostep; }
  const b = new Bits(u8, pos);
  const gref = new Float64Array(NG), gw = new Uint8Array(NG), gl = new Uint32Array(NG);
  for (let i = 0; i < NG; i++) gref[i] = nbits ? b.read(nbits) : 0;
  b.align();
  for (let i = 0; i < NG; i++) gw[i] = refW + (bitsW ? b.read(bitsW) : 0);
  b.align();
  for (let i = 0; i < NG; i++) gl[i] = refL + (bitsL ? b.read(bitsL) : 0) * incL;
  b.align();
  gl[NG - 1] = lastL;
  const X = new Float64Array(n), miss = new Uint8Array(n);
  let o = 0;
  for (let g = 0; g < NG; g++) {
    const w = gw[g], L = gl[g];
    const allOnes = w ? 2 ** w - 1 : 0, refOnes = nbits ? 2 ** nbits - 1 : -1;
    for (let i = 0; i < L && o < n; i++, o++) {
      const v = w ? b.read(w) : 0;
      if (mvm && ((w && v === allOnes) || (!w && gref[g] === refOnes))) { miss[o] = 1; continue; }
      X[o] = gref[g] + v;
    }
  }
  if (order > 0) {
    const idx = []; for (let i = 0; i < n; i++) if (!miss[i]) idx.push(i);
    if (order === 1) { X[idx[0]] = ival1; for (let j = 1; j < idx.length; j++) X[idx[j]] += minsd + X[idx[j - 1]]; }
    else { X[idx[0]] = ival1; if (idx.length > 1) X[idx[1]] = ival2; for (let j = 2; j < idx.length; j++) X[idx[j]] += minsd + 2 * X[idx[j - 1]] - X[idx[j - 2]]; }
  }
  return { X, miss };
}

export function decodeGrib2(u8) {
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.length);
  if (dv.getUint32(0) !== 0x47524942) throw new Error('not GRIB');
  let p = 16, grid = null, s5 = null, tmpl5 = -1, npts = 0, bitmap = null, s7 = null;
  while (p < u8.length - 4) {
    if (dv.getUint32(p) === 0x37373737) break;
    const L = dv.getUint32(p), sec = u8[p + 4];
    if (sec === 3) {
      const t = dv.getUint16(p + 12);
      if (t !== 0) throw new Error('grid template ' + t);
      const q = p; const s32 = o => { const v = dv.getUint32(q + o); return v & 0x80000000 ? -(v & 0x7fffffff) : v; };
      grid = { Ni: dv.getUint32(q + 30), Nj: dv.getUint32(q + 34), la1: s32(46) / 1e6, lo1: s32(50) / 1e6, la2: s32(55) / 1e6, lo2: s32(59) / 1e6, di: dv.getUint32(q + 63) / 1e6, dj: dv.getUint32(q + 67) / 1e6, scan: u8[q + 71] };
    } else if (sec === 5) { npts = dv.getUint32(p + 5); tmpl5 = dv.getUint16(p + 9); s5 = u8.subarray(p, p + L); }
    else if (sec === 6) { if (u8[p + 5] === 0) bitmap = u8.subarray(p + 6, p + L); }
    else if (sec === 7) { s7 = u8.subarray(p + 5, p + L); }
    p += L;
  }
  const d5 = new DataView(s5.buffer, s5.byteOffset, s5.length);
  const R = d5.getFloat32(11), E = sm16(d5, 15), Dd = sm16(d5, 17), nbits = s5[19];
  const e2 = 2 ** E, d10 = 10 ** -Dd;
  const vals = new Float32Array(npts);
  if (tmpl5 === 0) {
    const b = new Bits(s7); for (let i = 0; i < npts; i++) vals[i] = (R + (nbits ? b.read(nbits) : 0) * e2) * d10;
  } else if (tmpl5 === 42) {
    if (!nbits) vals.fill(R * d10);
    else { const X = aecDecode(s7, nbits, s5[21], s5[22], d5.getUint16(23), npts); for (let i = 0; i < npts; i++) vals[i] = (R + X[i] * e2) * d10; }
  } else if (tmpl5 === 3 || tmpl5 === 2) {
    const { X, miss } = complexDecode(s7, s5, npts);
    for (let i = 0; i < npts; i++) vals[i] = miss[i] ? NaN : (R + X[i] * e2) * d10;
  } else throw new Error('packing template ' + tmpl5);
  let values = vals;
  if (bitmap) { const n = grid.Ni * grid.Nj; values = new Float32Array(n).fill(NaN); let j = 0; for (let i = 0; i < n; i++) if (bitmap[i >> 3] & (128 >> (i & 7))) values[i] = vals[j++]; }
  return { ...grid, values };
}
