// Local render test: node tools/shot.mjs <url> <outPrefix>
import { chromium } from 'playwright-core';
const [url, out] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const errors = [];
for (const [name, vp, theme] of [['desk', { width: 1440, height: 900 }, 'dark'], ['phone', { width: 400, height: 860 }, 'light']]) {
  const page = await browser.newPage({ viewport: vp, colorScheme: theme });
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`[${name}] ${m.type()}: ${m.text()}`); });
  page.on('pageerror', e => errors.push(`[${name}] pageerror: ${e.message}`));
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForSelector('#loading[hidden]', { state: 'attached', timeout: 60000 }).catch(() => errors.push(`[${name}] loading never hid`));
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${out}-${name}-1.png` });
  if (name === 'desk') {
    await page.click('[data-layer="rain"]');
    await page.evaluate(() => { const r = document.getElementById('tl'); r.value = 36; r.dispatchEvent(new Event('input')); });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `${out}-${name}-rain.png` });
    await page.click('[data-layer="relief"]');
    await page.click('#viewTop');
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${out}-${name}-relief.png` });
    await page.goto(url.split('#')[0] + '#forecast'); await page.waitForTimeout(3000);
    await page.screenshot({ path: `${out}-${name}-forecast.png`, fullPage: false });
  }
  await page.close();
}
console.log(errors.length ? errors.join('\n') : 'no console errors');
await browser.close();
