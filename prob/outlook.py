"""Uzbekistan outlook maps: the past week (what fell), the next two weeks (ECMWF EC46) and this and next month
(ECMWF SEAS5), as precipitation totals and temperature against the normal, in the Osmon video style.
Data: Open-Meteo (https://open-meteo.com, CC BY 4.0), which serves the ECMWF extended-range and seasonal ensemble
means with anomalies against the model climate (hindcasts), and its recent-days analysis for the past week.
  out/outlook/<period>_<lang>.png, out/outlook/index.json
Usage: python3 prob/outlook.py prob.npz wx.npz site/prob [--langs uz,ru,tr]"""
import argparse, datetime as dt, json, pathlib, sys, time, calendar
import numpy as np
import requests

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render as Rn
from render import plt, matplotlib, ListedColormap, BoundaryNorm
from scipy.interpolate import RegularGridInterpolator

LONS = np.round(np.arange(55.5, 73.51, 0.75), 2)
LATS = np.round(np.arange(36.75, 46.01, 0.75), 2)
UA = {'User-Agent': 'osmon-weather/1.0 (Telegram @ObHavo_ECMWF_bot)'}
TX = {
    'ru': dict(past='Прошедшая неделя', w1='Следующая неделя', w2='Через неделю', m0='Этот месяц', m1='Следующий месяц', fact='факт', pr='Осадки, мм',
               ta='Температура: отклонение от нормы', tm='Средняя температура', norm='от нормы', more='больше нормы', less='меньше нормы', about='около нормы',
               warmer='теплее нормы', colder='холоднее нормы', src_f='Прогноз ECMWF EC46 (ансамбль) · данные Open-Meteo', src_m='Прогноз ECMWF SEAS5 (ансамбль) · данные Open-Meteo',
               src_p='Анализ моделей за прошедшие 7 дней · данные Open-Meteo', title='Узбекистан', mm='мм',
               months=['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']),
    'uz': dict(past='O‘tgan hafta', w1='Keyingi hafta', w2='Bir haftadan keyin', m0='Shu oy', m1='Keyingi oy', fact='haqiqiy', pr='Yog‘in, mm',
               ta='Harorat: me’yordan farqi', tm='O‘rtacha harorat', norm='me’yordan', more='me’yordan ko‘p', less='me’yordan kam', about='me’yor atrofida',
               warmer='me’yordan issiq', colder='me’yordan sovuq', src_f='ECMWF EC46 prognozi (ansambl) · Open-Meteo ma’lumotlari', src_m='ECMWF SEAS5 prognozi (ansambl) · Open-Meteo ma’lumotlari',
               src_p='O‘tgan 7 kun modellar tahlili · Open-Meteo ma’lumotlari', title='O‘zbekiston', mm='mm',
               months=['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr']),
    'tr': dict(past='Geçen hafta', w1='Gelecek hafta', w2='Bir sonraki hafta', m0='Bu ay', m1='Gelecek ay', fact='gerçekleşen', pr='Yağış, mm',
               ta='Sıcaklık: normalden fark', tm='Ortalama sıcaklık', norm='normalden', more='normalin üstünde', less='normalin altında', about='normal civarında',
               warmer='normalden sıcak', colder='normalden soğuk', src_f='ECMWF EC46 tahmini (topluluk) · Open-Meteo verisi', src_m='ECMWF SEAS5 tahmini (topluluk) · Open-Meteo verisi',
               src_p='Son 7 günün model analizi · Open-Meteo verisi', title='Özbekistan', mm='mm',
               months=['ocak', 'şubat', 'mart', 'nisan', 'mayıs', 'haziran', 'temmuz', 'ağustos', 'eylül', 'ekim', 'kasım', 'aralık']),
}
PR_LV = [0, 1, 3, 5, 10, 20, 40, 80, 500]
PR_COL = ['#f2f5f7', '#d6ecf3', '#a9d7ea', '#72bde0', '#3f9bd2', '#2a77b5', '#1b5592', '#5b2c7e']
TA_LV = [-8, -4, -3, -2, -1, -0.5, 0.5, 1, 2, 3, 4, 8]
TA_COL = ['#2c3f94', '#3c64b8', '#6a93d0', '#a2c2e4', '#d4e4f2', '#f1f1ee', '#f9dcc4', '#f4b48e', '#e8805f', '#cf4d3f', '#9c2232']


def get(url, params):
    for k in range(5):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=60)
            if r.status_code == 200: return r.json()
            print('open-meteo', r.status_code, r.text[:200], flush=True)
        except Exception as e: print('open-meteo', e, flush=True)
        time.sleep(5 * (k + 1))
    raise RuntimeError('open-meteo failed')


def fetch(points):
    """Seasonal (weekly EC46 + monthly SEAS5 ensemble means) and the past 7 days, for every grid point."""
    sea, past = [], []
    for i in range(0, len(points), 100):
        ch = points[i:i + 100]; la = ','.join(str(p[0]) for p in ch); lo = ','.join(str(p[1]) for p in ch)
        r = get('https://seasonal-api.open-meteo.com/v1/seasonal', {'latitude': la, 'longitude': lo, 'models': 'ecmwf_seasonal_ensemble_mean_seamless',
                'weekly': 'temperature_2m_mean,temperature_2m_anomaly,precipitation_mean,precipitation_anomaly',
                'monthly': 'temperature_2m_mean,temperature_2m_anomaly,precipitation_mean,precipitation_anomaly', 'timezone': 'Asia/Tashkent'})
        sea += r if isinstance(r, list) else [r]
        r = get('https://api.open-meteo.com/v1/forecast', {'latitude': la, 'longitude': lo, 'daily': 'precipitation_sum,temperature_2m_mean',
                'past_days': 7, 'forecast_days': 1, 'timezone': 'Asia/Tashkent'})
        past += r if isinstance(r, list) else [r]
        time.sleep(1)
    return sea, past


def fetch_aq(points):
    """CAMS (ECMWF Copernicus) air quality for the next 4 days: hourly PM10 and dust, as daily maxima."""
    out = []
    for i in range(0, len(points), 100):
        ch = points[i:i + 100]
        r = get('https://air-quality-api.open-meteo.com/v1/air-quality', {'latitude': ','.join(str(p[0]) for p in ch), 'longitude': ','.join(str(p[1]) for p in ch),
                'hourly': 'pm10,dust', 'forecast_days': 4, 'timezone': 'Asia/Tashkent'})
        out += r if isinstance(r, list) else [r]
        time.sleep(1)
    days = sorted({t[:10] for t in out[0]['hourly']['time']})[:4]
    res = []
    for d in days:
        ix = [k for k, t in enumerate(out[0]['hourly']['time']) if t.startswith(d)]
        mx = lambda key: np.array([max([x['hourly'][key][k] for k in ix if x['hourly'][key][k] is not None] or [np.nan]) for x in out], float)
        res.append({'date': dt.date.fromisoformat(d), 'pm10': mx('pm10'), 'dust': mx('dust')})
    return res


AQ_LV = [0, 20, 50, 100, 200, 400, 5000]
AQ_COL = ['#dff1e2', '#b9dfa8', '#f3dd7a', '#f2a65a', '#d9534f', '#7d2a5c']
DX = {'ru': dict(title='Пыль и качество воздуха', sub='PM10, максимум за день, мкг/м³', bands=['хорошо', 'умеренно', 'вредно для чувствительных', 'вредно', 'очень вредно', 'опасно'], src='Прогноз CAMS (ECMWF Copernicus) · данные Open-Meteo'),
      'uz': dict(title='Chang va havo sifati', sub='PM10, kunlik maksimum, mkg/m³', bands=['yaxshi', 'o‘rtacha', 'sezgirlar uchun zararli', 'zararli', 'juda zararli', 'xavfli'], src='CAMS prognozi (ECMWF Copernicus) · Open-Meteo ma’lumotlari'),
      'tr': dict(title='Toz ve hava kalitesi', sub='PM10, günlük en yüksek, µg/m³', bands=['iyi', 'orta', 'hassaslar için zararlı', 'zararlı', 'çok zararlı', 'tehlikeli'], src='CAMS tahmini (ECMWF Copernicus) · Open-Meteo verisi')}


def draw_dust(R, aq, lang, path, cities):
    X = DX[lang]; L = Rn.T[lang]
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100); fig.patch.set_facecolor(Rn.BG)
    x = Rn._brand(fig, 0.022, 0.948)
    fig.text(x + 0.012, 0.948, TX[lang]['title'], fontsize=18, fontfamily=Rn.DISPLAY, fontweight='bold', color=Rn.INK, va='center')
    fig.text(0.985, 0.955, X['title'], fontsize=15, fontweight='bold', color=Rn.ACCENT, ha='right', va='center')
    fig.text(0.985, 0.913, X['sub'], fontsize=11, color=Rn.MUTED, ha='right', va='center')
    worst = None
    for k, day in enumerate(aq[:4]):
        box = [0.012 + (k % 2) * 0.494, 0.505 - (k // 2) * 0.355, 0.482, 0.34]
        ax = Rn._basemap(fig, R, box)
        F = field(day['pm10'], R)
        if F is not None: ax.contourf(R.XU, R.YU, Rn._up(R, F), levels=AQ_LV, colors=AQ_COL, zorder=2, alpha=0.85, antialiased=True)
        Rn._borders(ax, R)
        d = day['date']
        fig.text(box[0] + 0.01, box[1] + box[3] - 0.03, f"{L['wd'][d.weekday()]} {d:%d.%m}", fontsize=11, fontweight='bold', color=Rn.INK, va='center',
                 bbox=dict(boxstyle='round,pad=0.3,rounding_size=0.5', fc=Rn.LABEL_BG, ec='none', alpha=0.85))
        lab = {}
        for p in cities[:7]:
            gx, gy = R._xy(p); v = float(Rn.bilinear(F, gx, gy)) if F is not None else np.nan
            lab[id(p)] = f"{Rn.city_name(p, lang)} {v:.0f}" if np.isfinite(v) else Rn.city_name(p, lang)
            if np.isfinite(v) and (worst is None or v > worst[2]): worst = (p, d, v)
        R.main = cities[0]
        Rn._cities(fig, ax, R, lambda p, main: lab.get(id(p), Rn.city_name(p, lang)))
    Rn._chips(fig, 0.03, 0.08, AQ_COL, X['bands'], w=0.153, h=0.032, gap=0.004, dark_from=4)
    fig.text(0.986, 0.03, X['src'] + ' · t.me/ObHavo_ECMWF_bot', fontsize=8, color=Rn.FAINT, va='center', ha='right')
    fig.savefig(path, dpi=150, facecolor=Rn.BG); plt.close(fig)
    return worst


def per_day(unit, days):
    """Factor from the weekly/monthly precipitation value to the period total in mm (Open-Meteo: "mm" = the total)."""
    u = (unit or '').lower()
    if '6h' in u or '6 h' in u: return 4 * days
    if 'day' in u or '/d' in u: return days
    return 1  # plain "mm": already the week's or the month's total (Tashkent: ~34 mm a week, ~83 mm in November, not ×7 / ×30)


def periods(sea, past):
    today = (dt.datetime.utcnow() + dt.timedelta(hours=5)).date()
    s0 = sea[0]; wk, mo = s0.get('weekly', {}), s0.get('monthly', {})
    wu, mu = s0.get('weekly_units', {}), s0.get('monthly_units', {})
    print('units', wu, mu, flush=True)
    wt = [dt.date.fromisoformat(t[:10]) for t in wk.get('time', [])]
    nxt = [i for i, t in enumerate(wt) if t >= today][:2] or list(range(min(2, len(wt))))
    mt = [dt.date.fromisoformat(t[:10]) for t in mo.get('time', [])]
    cur = [i for i, t in enumerate(mt) if (t.year, t.month) >= (today.year, today.month)][:2]
    G = lambda key, sect, i: np.array([np.nan if x.get(sect, {}).get(key) is None or x[sect][key][i] is None else x[sect][key][i] for x in sea], float)
    out = []
    pd_ = np.array([np.nansum([v for v in x['daily']['precipitation_sum'][:7] if v is not None]) for x in past])
    td_ = np.array([np.nanmean([v for v in x['daily']['temperature_2m_mean'][:7] if v is not None] or [np.nan]) for x in past])
    d0 = dt.date.fromisoformat(past[0]['daily']['time'][0])
    out.append(dict(key='past', start=d0, end=d0 + dt.timedelta(days=6), pr=pd_, t=td_, ta=None, pa=None))
    for k, i in zip(('w1', 'w2'), nxt):
        f = per_day(wu.get('precipitation_mean'), 7)
        out.append(dict(key=k, start=wt[i], end=wt[i] + dt.timedelta(days=6), pr=G('precipitation_mean', 'weekly', i) * f, pa=G('precipitation_anomaly', 'weekly', i) * f,
                        t=G('temperature_2m_mean', 'weekly', i), ta=G('temperature_2m_anomaly', 'weekly', i)))
    for k, i in zip(('m0', 'm1'), cur):
        n = calendar.monthrange(mt[i].year, mt[i].month)[1]; f = per_day(mu.get('precipitation_mean'), n)
        out.append(dict(key=k, start=mt[i], end=mt[i] + dt.timedelta(days=n - 1), pr=G('precipitation_mean', 'monthly', i) * f, pa=G('precipitation_anomaly', 'monthly', i) * f,
                        t=G('temperature_2m_mean', 'monthly', i), ta=G('temperature_2m_anomaly', 'monthly', i)))
    return out


def field(vals, R):
    """Grid points → the map's own grid (bilinear), smooth."""
    A = vals.reshape(len(LATS), len(LONS))
    if np.isnan(A).all(): return None
    A = np.where(np.isnan(A), np.nanmean(A), A)
    f = RegularGridInterpolator((LATS, LONS), A, bounds_error=False, fill_value=None)
    out = f(np.stack([np.clip(R.LAT, LATS[0], LATS[-1]), np.clip(R.LON, LONS[0], LONS[-1])], -1))
    return Rn.gaussian_filter(out, 1.0)


def draw(R, per, lang, path, cities):
    X = TX[lang]; L = Rn.T[lang]; mon = X['months']
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100); fig.patch.set_facecolor(Rn.BG)
    x = Rn._brand(fig, 0.022, 0.948)
    fig.text(x + 0.012, 0.948, X['title'], fontsize=18, fontfamily=Rn.DISPLAY, fontweight='bold', color=Rn.INK, va='center')
    s, e = per['start'], per['end']
    when = f"{mon[s.month - 1].capitalize()} {s.year}" if per['key'] in ('m0', 'm1') else f"{s:%d.%m} – {e:%d.%m.%Y}"
    fig.text(0.985, 0.955, X[per['key']], fontsize=15, fontweight='bold', color=Rn.ACCENT, ha='right', va='center')
    fig.text(0.985, 0.913, when + (f" · {X['fact']}" if per['key'] == 'past' else ''), fontsize=11, color=Rn.MUTED, ha='right', va='center')
    P = field(per['pr'], R); Tf = field(per['ta'] if per['ta'] is not None else per['t'], R)
    for j, (F, title) in enumerate(((P, X['pr']), (Tf, X['ta'] if per['ta'] is not None else X['tm']))):
        box = [0.012 + j * 0.494, 0.27, 0.482, 0.55]
        ax = Rn._basemap(fig, R, box)
        if F is not None:
            if j == 0: ax.contourf(R.XU, R.YU, Rn._up(R, F), levels=PR_LV, colors=PR_COL, zorder=2, alpha=0.9, antialiased=True)
            elif per['ta'] is not None: ax.contourf(R.XU, R.YU, Rn._up(R, F), levels=TA_LV, colors=TA_COL, extend='both', zorder=2, alpha=0.9, antialiased=True)
            else: ax.contourf(R.XU, R.YU, Rn._up(R, F), levels=Rn.T_LV, colors=Rn.T_COL[:len(Rn.T_LV) - 1], extend='both', zorder=2, alpha=0.88, antialiased=True)
        Rn._borders(ax, R)
        fig.text(box[0] + 0.012, 0.79, title, fontsize=11, fontweight='bold', color=Rn.INK, va='center',
                 bbox=dict(boxstyle='round,pad=0.35,rounding_size=0.6', fc=Rn.LABEL_BG, ec='none', alpha=0.85))
        R.main = cities[0]
        pts = []
        for p in cities:
            gx, gy = R._xy(p)
            v = float(Rn.bilinear(F, gx, gy)) if F is not None else np.nan
            txt = f"{Rn.city_name(p, lang)} {v:.0f} {X['mm']}" if j == 0 else (f"{Rn.city_name(p, lang)} {'+' if v > 0.05 else ''}{v:.1f}°" if per['ta'] is not None else f"{Rn.city_name(p, lang)} {Rn.fmt_t(v)}")
            pts.append((p, txt))
        lab = {id(p): t for p, t in pts}
        Rn._cities(fig, ax, R, lambda p, main: lab.get(id(p), Rn.city_name(p, lang)))
    # legends
    Rn._chips(fig, 0.03, 0.15, PR_COL[1:], ['1', '3', '5', '10', '20', '40', '80+'], w=0.06, h=0.03, gap=0.003, dark_from=4)
    fig.text(0.03, 0.185, X['pr'], fontsize=9, color=Rn.MUTED, va='center')
    if per['ta'] is not None:
        Rn._chips(fig, 0.524, 0.15, TA_COL[1:-1], ['−3', '−2', '−1', '−½', '0', '+½', '+1', '+2', '+3'], w=0.048, h=0.03, gap=0.003, dark_from=9)
        fig.text(0.524, 0.185, X['ta'] + ', °C', fontsize=9, color=Rn.MUTED, va='center')
    # the main city in words
    m = cities[0]; gx, gy = R._xy(m)
    v = lambda a: float(Rn.bilinear(field(a, R), gx, gy)) if a is not None and field(a, R) is not None else np.nan
    pr, pa, tt, ta = v(per['pr']), v(per['pa']), v(per['t']), v(per['ta'])
    words = f"{Rn.city_name(m, lang)}: {pr:.0f} {X['mm']}"
    if np.isfinite(pa) and pr > 1: words += f" ({X['more'] if pa > 0.15 * max(pr - pa, 1) else X['less'] if pa < -0.15 * max(pr - pa, 1) else X['about']})"
    if np.isfinite(tt): words += f" · {Rn.fmt_t(tt)}"
    if np.isfinite(ta): words += f" ({'+' if ta > 0 else ''}{ta:.1f}° {X['norm']}, {X['warmer'] if ta >= 0.5 else X['colder'] if ta <= -0.5 else X['about']})"
    Rn._card(fig, 0.012, 0.035, 0.976, 0.075)
    fig.text(0.026, 0.073, words, fontsize=12, fontweight='bold', color=Rn.INK, va='center')
    fig.text(0.026, 0.047, X['src_p'] if per['key'] == 'past' else X['src_m'] if per['key'] in ('m0', 'm1') else X['src_f'], fontsize=8, color=Rn.MUTED, va='center')
    fig.text(0.986, 0.047, 't.me/ObHavo_ECMWF_bot · ECMWF CC BY 4.0', fontsize=8, color=Rn.FAINT, va='center', ha='right')
    fig.savefig(path, dpi=150, facecolor=Rn.BG); plt.close(fig)
    return words


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('npz'); ap.add_argument('wx'); ap.add_argument('out'); ap.add_argument('--langs', default='uz,ru,tr')
    a = ap.parse_args()
    D = Rn.load(a.npz); P, _, _ = Rn.probability(D); Rn._CTX['wx'] = Rn.load_wx_npz(D, a.wx)
    R = Rn.Region(D, Rn.Geo(None), 'UZ', P, D['amt'])
    pts = [(la, lo) for la in LATS for lo in LONS]
    sea, past = fetch(pts)
    pers = periods(sea, past)
    out = pathlib.Path(a.out) / 'outlook'; out.mkdir(parents=True, exist_ok=True)
    idx = {'made': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), 'items': []}
    for lang in a.langs.split(','):
        cities = [R.mains[lang]] + [p for p in R.cities if p is not R.mains[lang]][:9]
        for per in pers:
            words = draw(R, per, lang, out / f"{per['key']}_{lang}.png", cities)
            idx['items'].append({'key': per['key'], 'lang': lang, 'img': f"outlook/{per['key']}_{lang}.png", 'start': per['start'].isoformat(), 'end': per['end'].isoformat(),
                                 'title': TX[lang][per['key']], 'text': words})
            print('outlook', per['key'], lang, words, flush=True)
    # dust and air quality (CAMS): one map of four days, and warnings for very dusty days at the cities
    try:
        aq = fetch_aq(pts); alerts = []
        for lang in a.langs.split(','):
            cities = [R.mains[lang]] + [p for p in R.cities if p is not R.mains[lang]][:9]
            w = draw_dust(R, aq, lang, out / f'dust_{lang}.png', cities)
            txt = f"{Rn.city_name(w[0], lang)} {w[1]:%d.%m}: PM10 {w[2]:.0f}" if w else ''
            idx['items'].append({'key': 'dust', 'lang': lang, 'img': f'outlook/dust_{lang}.png', 'start': aq[0]['date'].isoformat(), 'end': aq[-1]['date'].isoformat(), 'title': DX[lang]['title'], 'text': txt})
        for p in R.cities:
            gx, gy = R._xy(p)
            for day in aq[:3]:
                v = float(Rn.bilinear(field(day['pm10'], R), gx, gy))
                if v >= 300: alerts.append({'region': 'UZ', 'en': p['en'], 'name': {l: Rn.city_name(p, l) for l in ('uz', 'ru', 'tr')}, 'date': day['date'].isoformat(), 'kind': 'dust', 'pm10': int(v), 'level': 2 if v >= 600 else 1})
        json.dump({'run': D['run'], 'items': alerts}, open(pathlib.Path(a.out) / 'alerts.json', 'w'), ensure_ascii=False)
        json.dump({'run': D['run'], 'items': alerts}, open(out / 'alerts.json', 'w'), ensure_ascii=False)  # kept for the runs that reuse these maps
        print('dust ok, warnings:', len(alerts), flush=True)
    except Exception as e: print('dust failed:', e, flush=True)
    json.dump(idx, open(out / 'index.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
