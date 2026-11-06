"""Mountains of Uzbekistan: when fresh snow falls and which days are good for a trip (Chimgan, Amirsoy, Beldersay, the Kamchik pass,
Urgut, Zomin). Daily forecast for 16 days from Open-Meteo (best mix of ECMWF, DWD ICON, NOAA GFS), corrected to each
spot's own height (the elevation parameter), with the snow cover from the hourly snow depth.
  out/mountains.json
Usage: python3 prob/mountains.py out"""
import datetime as dt, json, pathlib, sys, time
import requests

UA = {'User-Agent': 'osmon-weather/1.0 (Telegram @ObHavo_ECMWF_bot)'}
# id, names, region, lat, lon, height of the place people go to (m)
SPOTS = [
    ('chimgan', {'uz': 'Chimyon', 'ru': 'Чимган', 'tr': 'Çimgan'}, {'uz': 'Toshkent viloyati', 'ru': 'Ташкентская обл.', 'tr': 'Taşkent ili'}, 41.545, 70.010, 1700),
    ('amirsoy', {'uz': 'Amirsoy', 'ru': 'Амирсой', 'tr': 'Amirsoy'}, {'uz': 'Toshkent viloyati', 'ru': 'Ташкентская обл.', 'tr': 'Taşkent ili'}, 41.490, 69.995, 1900),
    ('beldersay', {'uz': 'Beldersoy', 'ru': 'Бельдерсай', 'tr': 'Beldersay'}, {'uz': 'Toshkent viloyati', 'ru': 'Ташкентская обл.', 'tr': 'Taşkent ili'}, 41.520, 70.070, 1800),
    ('kamchik', {'uz': 'Qamchiq dovoni', 'ru': 'Перевал Камчик', 'tr': 'Kamçik geçidi'}, {'uz': 'Toshkent – Farg‘ona yo‘li', 'ru': 'дорога Ташкент – Фергана', 'tr': 'Taşkent – Fergana yolu'}, 41.100, 70.518, 2268),
    ('urgut', {'uz': 'Urgut tog‘lari', 'ru': 'Ургут (горы)', 'tr': 'Urgut dağları'}, {'uz': 'Samarqand viloyati', 'ru': 'Самаркандская обл.', 'tr': 'Semerkant ili'}, 39.340, 67.270, 1600),
    ('zomin', {'uz': 'Zomin', 'ru': 'Зомин', 'tr': 'Zomin'}, {'uz': 'Jizzax viloyati', 'ru': 'Джизакская обл.', 'tr': 'Cizzak ili'}, 39.620, 68.430, 2000),
]
SNOW_CM = 2.0   # a day with at least this much fresh snow is a snow day


def get(params):
    for k in range(5):
        try:
            r = requests.get('https://api.open-meteo.com/v1/forecast', params=params, headers=UA, timeout=60)
            if r.status_code == 200: return r.json()
            print('open-meteo', r.status_code, r.text[:200], flush=True)
        except Exception as e: print('open-meteo', e, flush=True)
        time.sleep(5 * (k + 1))
    raise RuntimeError('open-meteo failed')


def good(d):
    """A good day to go up: dry, not stormy, mostly sunny, not bitterly cold. 2 = very good, 1 = good, 0 = no."""
    if d['pr'] >= 1 or d['sn'] >= 0.5 or d['gust'] > 12 or d['sun'] < 4 or d['tmax'] < -12: return 0
    return 2 if d['sun'] >= 6 and d['gust'] <= 8 else 1


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    r = get({'latitude': ','.join(str(s[3]) for s in SPOTS), 'longitude': ','.join(str(s[4]) for s in SPOTS), 'elevation': ','.join(str(s[5]) for s in SPOTS),
             'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,showers_sum,snowfall_sum,wind_gusts_10m_max,sunshine_duration',
             'hourly': 'snow_depth', 'forecast_days': 16, 'timezone': 'Asia/Tashkent', 'wind_speed_unit': 'ms'})
    r = r if isinstance(r, list) else [r]
    res = {'made': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), 'snow_cm': SNOW_CM, 'spots': []}
    for (sid, name, area, la, lo, el), x in zip(SPOTS, r):
        D, H = x['daily'], x.get('hourly', {})
        depth = {}
        for t, v in zip(H.get('time', []), H.get('snow_depth', [])):
            if v is not None: depth[t[:10]] = max(depth.get(t[:10], 0), v)
        f = lambda k, i, nd=1: None if D[k][i] is None else round(D[k][i], nd)
        days = []
        for i, d in enumerate(D['time']):
            if D['temperature_2m_max'][i] is None: continue
            row = {'d': d, 'code': D['weather_code'][i], 'tmin': f('temperature_2m_min', i, 0), 'tmax': f('temperature_2m_max', i, 0),
                   'pr': f('precipitation_sum', i) or 0, 'sn': f('snowfall_sum', i) or 0, 'gust': f('wind_gusts_10m_max', i, 0) or 0,
                   'sun': round((D['sunshine_duration'][i] or 0) / 3600, 1),
                   'rn': round(((D.get('rain_sum') or [0] * (i + 1))[i] or 0) + ((D.get('showers_sum') or [0] * (i + 1))[i] or 0), 1), 'depth': round(depth.get(d, 0) * 100)}
            row['good'] = good(row); days.append(row)
        res['spots'].append({'id': sid, 'name': name, 'area': area, 'lat': la, 'lon': lo, 'elev': el, 'days': days})
        snow = [f"{d['d'][5:]} {d['sn']}cm" for d in days if d['sn'] >= SNOW_CM]
        print(sid, 'snow:', snow or '—', '| good:', [d['d'][5:] for d in days if d['good']][:5], flush=True)
    json.dump(res, open(out / 'mountains.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    for lang in ('ru', 'uz', 'tr'):
        try: picture(res, lang, out / f'mountains_{lang}.png')
        except Exception as e: print('mountains picture failed:', lang, e, flush=True)


PX = {
    'ru': dict(title='Горы Узбекистана', sub='снег и дни для поездки', good='хороший день', great='отличный день', snow='снег, см', best='лучший день после снега',
               wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], m='м', s_snow='снег', s_go='ехать лучше', none='снега нет', cm='см', rain='дождь, мм', s_rain='дождь', mm='мм'),
    'uz': dict(title='O‘zbekiston tog‘lari', sub='qor va sayohat kunlari', good='yaxshi kun', great='a’lo kun', snow='qor, sm', best='qordan keyingi eng yaxshi kun',
               wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'], m='m', s_snow='qor', s_go='borish yaxshi', none='qor yo‘q', cm='sm', rain='yomg‘ir, mm', s_rain='yomg‘ir', mm='mm'),
    'tr': dict(title='Özbekistan dağları', sub='kar ve gezi günleri', good='iyi gün', great='çok iyi gün', snow='kar, cm', best='kardan sonraki en iyi gün',
               wd=['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'], m='m', s_snow='kar', s_go='gitmek için', none='kar yok', cm='cm', rain='yağmur, mm', s_rain='yağmur', mm='mm'),
}


def picture(res, lang, path, ndays=10):
    """One picture of the mountains for the next 10 days: a row per place, a column per day: the day's temperatures,
    fresh snow as a lilac bar with its centimetres, good days in green, the best day after a snowfall framed; and one
    line of plain text per place under the table."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import render as Rn
    from render import plt, matplotlib
    X = PX[lang]; NAVY = '#2b3a4e'
    today = (dt.datetime.utcnow() + dt.timedelta(hours=5)).date().isoformat()
    spots = [(sp, [d for d in sp['days'] if d['d'] >= today][:ndays]) for sp in res['spots']]
    dates = [d['d'] for d in spots[0][1]]
    if not dates: return
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100); fig.patch.set_facecolor('#f3f5f7')
    fig.patches.append(matplotlib.patches.Rectangle((0, 0.93), 1, 0.07, transform=fig.transFigure, facecolor=NAVY, edgecolor='none', zorder=-6))
    ink0 = Rn.INK; Rn.INK = '#ffffff'
    try: x = Rn._brand(fig, 0.016, 0.965, size=11)
    finally: Rn.INK = ink0
    tt = fig.text(x + 0.014, 0.965, X['title'], fontsize=14, fontfamily=Rn.DISPLAY, fontweight='bold', color='#ffffff', va='center')
    bb = tt.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
    fig.text(bb.x1 + 0.016, 0.965, X['sub'], fontsize=11, color='#a9bdd6', va='center')
    fd = lambda d: f"{d[8:10]}.{d[5:7]}"
    fig.text(0.984, 0.965, f"{fd(dates[0])} – {fd(dates[-1])}", fontsize=14, fontweight='bold', color='#f0b88a', ha='right', va='center')
    # the table
    L0, C0, C1, top, bot = 0.012, 0.2, 0.988, 0.875, 0.3
    cw = (C1 - C0) / len(dates); rh = (top - bot) / len(spots)
    Rn._card(fig, L0 - 0.004, bot - 0.012, C1 - L0 + 0.008, top - bot + 0.07, fc='#ffffff', ec='#dde3ea', r=0.01)
    for j, d in enumerate(dates):
        wd = dt.date.fromisoformat(d).weekday(); xc = C0 + (j + 0.5) * cw
        fig.text(xc, top + 0.035, X['wd'][wd], fontsize=10, fontweight='bold', color='#c8784a' if wd >= 5 else NAVY, ha='center', va='center')
        fig.text(xc, top + 0.012, fd(d), fontsize=8.5, color=Rn.MUTED, ha='center', va='center')
    maxsn = max([1.0] + [d['sn'] for _, ds in spots for d in ds]); maxrn = max([1.0] + [d.get('rn', 0) or 0 for _, ds in spots for d in ds])
    lines = []
    for i, (sp, ds) in enumerate(spots):
        y1 = top - i * rh; y0 = y1 - rh
        fig.add_artist(matplotlib.lines.Line2D([L0 + 0.006, C1 - 0.004], [y1, y1], color='#e8edf2', lw=0.8, transform=fig.transFigure))
        fig.text(L0 + 0.01, y0 + rh * 0.62, sp['name'][lang], fontsize=11.5, fontweight='bold', color=NAVY, va='center')
        fig.text(L0 + 0.01, y0 + rh * 0.3, f"{sp['elev']} {X['m']} · {sp['area'][lang]}", fontsize=7.6, color=Rn.MUTED, va='center')
        snow_days = [d for d in ds if d['sn'] >= res.get('snow_cm', 2)]
        after = None
        if snow_days:
            s0 = snow_days[0]['d']; after = next((d['d'] for d in ds if d['d'] > s0 and d['good'] > 0 and (dt.date.fromisoformat(d['d']) - dt.date.fromisoformat(s0)).days <= 3), None)
        for j, d in enumerate(ds):
            x0 = C0 + j * cw
            if d['good']:
                Rn._card(fig, x0 + 0.002, y0 + 0.004, cw - 0.004, rh - 0.008, fc='#d7efd9' if d['good'] == 2 else '#ebf6ec', ec='none', r=0.006)
            rn = d.get('rn', 0) or 0; has_s, has_r = d['sn'] >= 0.5, rn >= 0.5
            slots = ([('s', 0.08, 0.40), ('r', 0.52, 0.40)] if has_s and has_r else [('s', 0.18, 0.64)] if has_s else [('r', 0.18, 0.64)] if has_r else [])
            for kind, xs, ws in slots:  # snow lilac (cm), rain blue (mm): short enough for the label under the temperatures
                if kind == 's':
                    h = (rh - 0.05) * min(1, d['sn'] / maxsn) * 0.5 + 0.008
                    Rn._card(fig, x0 + cw * xs, y0 + 0.006, cw * ws, h, fc='#cdb6e6' if d['sn'] >= res.get('snow_cm', 2) else '#e6dcf2', ec='none', r=0.004)
                    fig.text(x0 + cw * (xs + ws / 2), y0 + 0.006 + h + 0.012, (f"{d['sn']:.0f}" + ('' if has_r else f" {X['cm']}")) if d['sn'] >= 1 else '<1', fontsize=8.5, fontweight='bold', color='#6b4a9a', ha='center', va='center')
                else:
                    h = (rh - 0.05) * min(1, rn / maxrn) * 0.5 + 0.008
                    Rn._card(fig, x0 + cw * xs, y0 + 0.006, cw * ws, h, fc='#9cc6e6' if rn >= 2 else '#cfe3f2', ec='none', r=0.004)
                    fig.text(x0 + cw * (xs + ws / 2), y0 + 0.006 + h + 0.012, (f"{rn:.0f}" + ('' if has_s else f" {X['mm']}")) if rn >= 1 else '<1', fontsize=8.5, fontweight='bold', color='#2f6c9e', ha='center', va='center')
            fig.text(x0 + cw / 2, y1 - 0.02, f"{Rn.fmt_t(d['tmin'])}…{Rn.fmt_t(d['tmax'])}".replace('-', '−'), fontsize=8.6, color=NAVY, ha='center', va='center')
            if d['d'] == after:
                Rn._card(fig, x0 + 0.002, y0 + 0.004, cw - 0.004, rh - 0.008, fc='none', ec='#e0895a', r=0.006, z=5)
                fig.patches[-1].set_linewidth(2.2)
        sn_t = ', '.join(f"{fd(d['d'])} ~{d['sn']:.0f} {X['cm']}" for d in snow_days[:3])
        rain_days = [d for d in ds if (d.get('rn', 0) or 0) >= 2]
        line = f"{sp['name'][lang]}: " + (f"{X['s_snow']} {sn_t}" if snow_days else X['none'])
        if rain_days: line += f" · {X['s_rain']} " + ', '.join(fd(d['d']) for d in rain_days[:3])
        if after: line += f" · {X['s_go']} {fd(after)}"
        else:
            g = [d['d'] for d in ds if d['good'] == 2][:2] or [d['d'] for d in ds if d['good']][:2]
            if g: line += f" · {X['s_go']} {', '.join(fd(x_) for x_ in g)}"
        lines.append(line)
    # the key and the plain-text lines
    ky = 0.245; kx = 0.012
    for fc, ec, lbl in (('#d7efd9', 'none', X['great']), ('#ebf6ec', 'none', X['good']), ('#cdb6e6', 'none', X['snow']), ('#9cc6e6', 'none', X['rain']), ('#ffffff', '#e0895a', X['best'])):
        Rn._card(fig, kx, ky - 0.012, 0.022, 0.024, fc=fc, ec=ec, r=0.004); t_ = fig.text(kx + 0.028, ky, lbl, fontsize=8.5, color=NAVY, va='center')
        kx = t_.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted()).x1 + 0.025
    for k, line in enumerate(lines):
        col, row = k % 2, k // 2
        fig.text(0.012 + col * 0.495, 0.195 - row * 0.05, line, fontsize=9.3, color=NAVY, va='center')
    fig.text(0.988, 0.012, 'ECMWF · DWD · NOAA (Open-Meteo) · t.me/ObHavo_ECMWF_bot', fontsize=6.5, color=Rn.FAINT, ha='right', va='center')
    fig.savefig(path, dpi=150, facecolor='#f3f5f7'); plt.close(fig)


if __name__ == '__main__':
    main()
