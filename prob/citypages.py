"""Static city pages for search engines and sharing: site/c/<slug>/index.html (15-day text forecast in Uzbek and Russian,
Turkish when there is one), plus site/c/index.html, sitemap.xml and robots.txt.
Usage: python3 prob/citypages.py site https://otabekvafoev92-del.github.io/ob-havo-ecmwf"""
import datetime as dt, html, json, pathlib, re, sys
from urllib.parse import quote

LANGS = ('uz', 'ru', 'tr')
WD = {'uz': ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'], 'ru': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], 'tr': ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']}
TX = {'uz': dict(t='{c}: 15 kunlik ob-havo', h='15 kunlik ob-havo prognozi', bot='Telegram botda soatlik video va ogohlantirishlar', map='Xaritada ochish', all='Barcha shaharlar'),
      'ru': dict(t='{c}: погода на 15 дней', h='Прогноз погоды на 15 дней', bot='Почасовое видео и предупреждения в Telegram-боте', map='Открыть на карте', all='Все города'),
      'tr': dict(t='{c}: 15 günlük hava durumu', h='15 günlük hava tahmini', bot='Telegram botunda saatlik video ve uyarılar', map='Haritada aç', all='Tüm şehirler')}
NAMES = {'UZ': 'O‘zbekiston', 'KZ': 'Qozog‘iston', 'KG': 'Qirg‘iziston', 'TJ': 'Tojikiston', 'TM': 'Turkmaniston', 'AZ': 'Ozarbayjon',
         'AM': 'Armaniston', 'BY': 'Belarus', 'MD': 'Moldova', 'RU': 'Rossiya', 'TR': 'Turkiya'}
CSS = """:root{--bg:#f6f4ef;--card:#fff;--ink:#1d2733;--muted:#5d6b78;--accent:#1f7a8c;--line:#e3e0d8}
@media (prefers-color-scheme:dark){:root{--bg:#141a21;--card:#1c242d;--ink:#e8edf2;--muted:#9aa8b5;--accent:#5cc2d6;--line:#2a3540}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:860px;margin:0 auto;padding:20px 16px 48px}a{color:var(--accent)}h1{font-size:28px;margin:8px 0 4px}h2{font-size:18px;margin:28px 0 8px}
.top{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}.brand{font-weight:800;text-decoration:none;color:var(--ink)}
.btn{display:inline-block;padding:10px 14px;border-radius:12px;background:var(--accent);color:#fff;text-decoration:none;font-weight:600;margin:4px 6px 4px 0}
.btn.alt{background:transparent;color:var(--accent);border:1px solid var(--accent)}
.day{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin:6px 0}.d{font-weight:700;margin-right:8px}
.muted{color:var(--muted);font-size:14px}.grid{columns:3 180px}.grid a{display:block;padding:3px 0}nav.l a{margin-right:12px}"""


def slug(s):
    s = s.lower().replace('‘', '').replace('’', '').replace("'", '')
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def page(base, c, region, langs, rel):
    first = c['name'].get('uz') or c['name'].get('ru')
    title = TX['uz']['t'].format(c=first) + ' · ' + TX['ru']['t'].format(c=c['name'].get('ru', first))
    desc = next(iter(c['days'].get('ru', {}).values()), '') or next(iter(c['days'].get('uz', {}).values()), '')
    url = f"{base}/c/{rel}/"
    ld = {'@context': 'https://schema.org', '@type': 'Place', 'name': first, 'geo': {'@type': 'GeoCoordinates', 'latitude': c['lat'], 'longitude': c['lon']}, 'url': url}
    out = [f'<!doctype html><html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
           f'<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc[:300])}">',
           f'<link rel="canonical" href="{url}"><meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(desc[:300])}">',
           f'<meta property="og:url" content="{url}"><meta property="og:image" content="{base}/assets/og.jpg"><meta property="og:type" content="website">',
           f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script><style>{CSS}</style></head><body><main>',
           f'<div class="top"><a class="brand" href="../../">☁ Osmon</a><nav class="l">' + ''.join(f'<a href="#{l}">{l.upper()}</a>' for l in langs) + '</nav></div>']
    for l in langs:
        T = TX[l]; nm = c['name'].get(l, first)
        out.append(f'<section id="{l}" lang="{l}"><h1>{html.escape(nm)}</h1><div class="muted">{T["h"]} · {html.escape(NAMES.get(region, region))} · ECMWF, NOAA, DWD</div>')
        for d, txt in sorted(c['days'].get(l, {}).items()):
            day = dt.date.fromisoformat(d)
            out.append(f'<div class="day"><span class="d">{WD[l][day.weekday()]} {day:%d.%m}</span>{html.escape(txt)}</div>')
        out.append(f'<p><a class="btn" href="https://t.me/ObHavo_ECMWF_bot">{T["bot"]}</a>'
                   f'<a class="btn alt" href="../../#prob/{region}/{l if l != 'tr' else 'ru'}/prob/{quote(c['name'].get(l if l != 'tr' else 'ru', nm))}">{T["map"]}</a><a class="btn alt" href="../">{T["all"]}</a></p></section>')
    out.append('<p class="muted">Ma’lumotlar: ECMWF (CC BY 4.0), NOAA GFS, DWD ICON · Данные ECMWF, NOAA, DWD</p></main></body></html>')
    return ''.join(out)


def main():
    site, base = pathlib.Path(sys.argv[1]), sys.argv[2].rstrip('/')
    src = site / 'prob' / 'cities'
    C = {}  # (region, en) → merged record
    for f in sorted(src.glob('*.json')):
        J = json.load(open(f)); reg, lang = J['region'], J['lang']
        if lang not in LANGS: continue
        for c in J['cities']:
            if 'en' not in c: continue
            r = C.setdefault((reg, c['en']), {'en': c['en'], 'lat': c['lat'], 'lon': c['lon'], 'name': {}, 'days': {}})
            r['name'][lang] = c['name']; r['days'][lang] = c['days']
    root = site / 'c'; root.mkdir(exist_ok=True)
    urls, links, used = [f'{base}/'], {}, set()
    for (reg, en), c in sorted(C.items()):
        rel = slug(en) or 'x'
        if rel in used: rel = f'{rel}-{reg.lower()}'
        used.add(rel)
        langs = [l for l in LANGS if c['days'].get(l)]
        if not langs: continue
        d = root / rel; d.mkdir(exist_ok=True)
        (d / 'index.html').write_text(page(base, c, reg, langs, rel))
        urls.append(f'{base}/c/{rel}/'); links.setdefault(reg, []).append((c['name'].get('uz') or c['name'].get('ru') or en, rel))
    idx = [f'<!doctype html><html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Osmon · shaharlar · города</title>',
           f'<meta name="description" content="15 kunlik ob-havo shaharlar bo‘yicha · Погода на 15 дней по городам"><link rel="canonical" href="{base}/c/"><style>{CSS}</style></head><body><main>',
           '<div class="top"><a class="brand" href="../">☁ Osmon</a></div><h1>Shaharlar · Города</h1>']
    order = ['UZ'] + sorted(k for k in links if k != 'UZ')
    for reg in order:
        if reg not in links: continue
        idx.append(f'<h2>{html.escape(NAMES.get(reg, reg))}</h2><div class="grid">' + ''.join(f'<a href="{r}/">{html.escape(n)}</a>' for n, r in sorted(links[reg])) + '</div>')
    idx.append('</main></body></html>')
    (root / 'index.html').write_text(''.join(idx)); urls.insert(1, f'{base}/c/')
    today = dt.date.today().isoformat()
    (site / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
                                      ''.join(f'<url><loc>{u}</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq></url>\n' for u in urls) + '</urlset>\n')
    (site / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n')
    print('city pages:', len(urls) - 2)


if __name__ == '__main__':
    main()
