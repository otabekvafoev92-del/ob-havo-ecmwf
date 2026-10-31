// node tools/make_clouds_local.mjs ir.json forecast.json outDataDir
// ir.json: {g:{step: base64 jpeg 1024×512 grey}, r:{step: base64 jpeg 660×360 grey}} collected in the browser
import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';
import { unrle, GGRID, GRID } from '../pipeline/decode.js';
import { CLOUD_G, CLOUD_R, cloudDensity, IR_PRODUCT } from '../pipeline/clouds.js';
const [irF, fcF, outDir] = process.argv.slice(2);
const ir = JSON.parse(fs.readFileSync(irF, 'utf8')), D = JSON.parse(fs.readFileSync(fcF, 'utf8'));
const steps = D.global.layers.temp.steps, runTag = D.run.slice(0, 13).replace(/[-T:]/g, '');
const gray = async (b64, W, H) => { const { data, info } = await sharp(Buffer.from(b64, 'base64')).greyscale().resize(W, H, { fit: 'fill' }).raw().toBuffer({ resolveWithObject: true }); const f = new Float32Array(W * H); for (let i = 0; i < W * H; i++) f[i] = data[i * info.channels]; return f; };
const gG = [], gR = [];
for (const h of steps) { gG.push(await gray(ir.g[h], CLOUD_G.W, CLOUD_G.H)); gR.push(await gray(ir.r[h], CLOUD_R.W, CLOUD_R.H)); }
const fill = a => a.map((v, i) => v || a.slice(0, i).reverse().find(Boolean) || a.find(Boolean));
const tg = fill(D.global.layers.temp.frames.map(f => f && unrle(f, GGRID.W * GGRID.H)));
const trr = fill(D.region.layers.temp.frames.map(f => f && unrle(f, GRID.GW * GRID.GH)));
const dG = cloudDensity({ gray: gG, temp: tg, steps, W: CLOUD_G.W, H: CLOUD_G.H, CW: GGRID.W, CH: GGRID.H, wrap: true });
const dR = cloudDensity({ gray: gR, temp: trr, steps, W: CLOUD_R.W, H: CLOUD_R.H, CW: GRID.GW, CH: GRID.GH, wrap: false });
fs.mkdirSync(path.join(outDir, 'clouds'), { recursive: true });
const name = (p, h) => `clouds/${runTag}_${p}${String(h).padStart(3, '0')}.jpg`;
let bytes = 0;
for (let i = 0; i < steps.length; i++) {
  await sharp(Buffer.from(dG[i]), { raw: { width: CLOUD_G.W, height: CLOUD_G.H, channels: 1 } }).jpeg({ quality: 82 }).toFile(path.join(outDir, name('g', steps[i])));
  await sharp(Buffer.from(dR[i]), { raw: { width: CLOUD_R.W, height: CLOUD_R.H, channels: 1 } }).jpeg({ quality: 85 }).toFile(path.join(outDir, name('r', steps[i])));
  bytes += fs.statSync(path.join(outDir, name('g', steps[i]))).size + fs.statSync(path.join(outDir, name('r', steps[i]))).size;
}
D.clouds = { product: IR_PRODUCT, steps, times: D.global.layers.temp.times, g: steps.map(h => name('g', h)), r: steps.map(h => name('r', h)), gSize: CLOUD_G, rSize: CLOUD_R };
fs.writeFileSync(path.join(outDir, 'forecast.json'), JSON.stringify(D));
const mean = a => a.reduce((s, v) => s + v, 0) / a.length / 255;
console.log('ok', (bytes / 1e6).toFixed(2), 'MB', 'mean cover g', mean(dG[5]).toFixed(3), 'r', mean(dR[5]).toFixed(3));
