"""Posts the precipitation / temperature / cloud report to Telegram as one album per country:
3 videos you swipe through (rain & snow, temperature, clouds) + a caption with the next days in words,
then buttons that open the website. Run after prob/render.py.

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SITE_URL (the GitHub Pages address, optional),
     PROB_TG — which posts, e.g. "UZ:uz,cis:ru,TR:tr" (country:language), DRY_RUN=1 prints instead of sending.
Usage: python3 prob/telegram_send.py site/prob"""
import datetime as dt, json, os, pathlib, sys
import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from regions import NAMES

HEAD = {
    'uz': '🌧 <b>{name}: ob-havo prognozi, 15 kun</b>\nYog‘in ehtimoli · harorat · bulutlar — videoni suring ➡️',
    'ru': '🌧 <b>{name}: прогноз на 15 дней</b>\nВероятность осадков · температура · облачность — листайте видео ➡️',
    'tr': '🌧 <b>{name}: 15 günlük tahmin</b>\nYağış olasılığı · sıcaklık · bulutluluk — videoları kaydırın ➡️',
}
FOOT = {
    'uz': '<i>{n} ta prognoz: {m}. Hisob {run} UTC.</i>',
    'ru': '<i>{n} прогнозов: {m}. Расчёт {run} UTC.</i>',
    'tr': '<i>{n} tahmin: {m}. Çalıştırma {run} UTC.</i>',
}
BTN = {
    'uz': ('🌍 Globus', '📊 To‘liq hisobot'), 'ru': ('🌍 Глобус', '📊 Полный отчёт'), 'tr': ('🌍 Küre', '📊 Tam rapor'),
}
WD = {'uz': ['Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan', 'Yak'], 'ru': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], 'tr': ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']}


def caption(man, region, lang, days_item, limit=1024):
    head = HEAD[lang].format(name=NAMES[region][lang])
    foot = FOOT[lang].format(n=man['members'], m=', '.join(man['models']), run=man['run'][:16].replace('T', ' '))
    today = dt.date.today().isoformat()
    lines = []
    for d, txt in (days_item or {}).get('days', {}).items():
        if d < today: continue
        dd = dt.date.fromisoformat(d)
        lines.append(f"<b>{WD[lang][dd.weekday()]} {dd:%d.%m}</b> — {txt}")
    body = ''
    for l in lines:  # as many days as fit into Telegram's 1024-character caption
        if len(head) + len(body) + len(l) + len(foot) + 4 > limit: break
        body += l + '\n'
    return f"{head}\n\n{body}\n{foot}"


def main():
    out = pathlib.Path(sys.argv[1]); man = json.load(open(out / 'manifest.json'))
    tok, chat, site = os.environ.get('TELEGRAM_BOT_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID'), os.environ.get('SITE_URL', '').rstrip('/')
    want = [x.split(':') for x in os.environ.get('PROB_TG', 'UZ:uz,cis:ru,TR:tr').split(',') if ':' in x]
    for region, lang in want:
        items = {i.get('product', 'prob'): i for i in man['items'] if i['region'] == region and i['lang'] == lang}
        vids = [out / items[p]['video'] for p in ('prob', 'temp', 'cloud') if p in items and (out / items[p]['video']).exists()]
        if not vids: print('skip', region, lang); continue
        cap = caption(man, region, lang, items.get('days'))
        if os.environ.get('DRY_RUN') or not tok:
            print('DRY', region, lang, [v.name for v in vids]); print(cap); print('---'); continue
        media = [{'type': 'video', 'media': f'attach://v{i}', 'supports_streaming': True} for i in range(len(vids))]
        media[0].update(caption=cap, parse_mode='HTML')
        files = {f'v{i}': open(v, 'rb') for i, v in enumerate(vids)}
        r = requests.post(f'https://api.telegram.org/bot{tok}/sendMediaGroup', data={'chat_id': chat, 'media': json.dumps(media)}, files=files, timeout=600)
        print(region, lang, 'album', r.status_code, r.text[:160])
        if site:  # an album cannot carry buttons, so the links follow as a short message
            # channels cannot open Mini Apps from buttons, so these are plain links (the bot's menu opens the site inside Telegram)
            kb = {'inline_keyboard': [[{'text': BTN[lang][0], 'url': f'{site}/?view=map'}, {'text': BTN[lang][1], 'url': f'{site}/?view=prob/{region}/{lang}/prob'}]]}
            requests.post(f'https://api.telegram.org/bot{tok}/sendMessage', data={'chat_id': chat, 'text': '👇', 'reply_markup': json.dumps(kb)}, timeout=60)


if __name__ == '__main__':
    main()
