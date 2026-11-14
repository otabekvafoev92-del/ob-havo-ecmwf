"""PDF report "Weather against last year" (A4 landscape, Osmon), for the bot and for business readers.
Uzbekistan — the mean of the 14 region centres (tools/lfl.py), the districts (lfl/districts.json from tools/lfl_xlsx.py), the climate
norm 1991–2020 (tools/lfl_norm.py). LFL: the same weekdays 364 days back.
  1 Summary: the numbers, what happened, the signals of the next two weeks
  2 Week to week since 1 January (temperature, the difference, precipitation, the norm)
  3 Heat map: regions × the last 10 weeks and the 2 forecast weeks
  4 This month day by day
  5 Regions: the month, last year, the norm, the forecast, a 12-week trend line
  6 Districts: the warmest, coldest and wettest against last year (last week and next week)
  7 Business: rainy weekends, hot / frost / snow / windy days; the next two weekends
  8 Method and sources
Usage: python tools/lfl_pdf.py lfl/lfl.json 'lfl/UZ_lfl_{lang}.pdf' ru,uz"""
import json, sys, datetime as dt, pathlib, textwrap
import numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.patches import FancyBboxPatch

SRC, OUTP = sys.argv[1], sys.argv[2]; LANGS = (sys.argv[3] if len(sys.argv) > 3 else 'ru').split(',')
for f_ in ('Inter', 'DejaVu Sans'):
    if any(f_.lower() == fm.FontProperties(fname=x).get_name().lower() for x in fm.findSystemFonts() if f_.split()[0].lower() in x.lower()): plt.rcParams['font.family'] = f_; break
plt.rcParams.update({'axes.edgecolor': '#c9d1da', 'axes.labelcolor': '#4a5868', 'xtick.color': '#6b7a8c', 'ytick.color': '#6b7a8c', 'axes.titleweight': 'bold'})
NAVY, INK, MUTED, LINE, SOFT, WARM, COLD, RAIN, LY, NORM, ACC = '#1f2d3d', '#1f2d3d', '#6b7a8c', '#dde3ea', '#f5f7f9', '#d9562b', '#2f6fd0', '#2f7fd1', '#a3adb9', '#2e8b57', '#f08a24'
DIV = LinearSegmentedColormap.from_list('d', ['#2f6fd0', '#9fbfee', '#f7f7f7', '#f3b08f', '#d9562b'])
WET = LinearSegmentedColormap.from_list('w', ['#b7791f', '#efd9b0', '#f7f7f7', '#a9cdf2', '#2f7fd1'])
nan = lambda a: np.array([np.nan if x is None else x for x in a], float)

TX = {'ru': dict(
    brand='OSMON · погодная аналитика', t='Погода против прошлого года', sub='Узбекистан · 14 центров регионов и 199 районов', made='Данные на {d}',
    lfl='LFL: сравнение с теми же днями недели 364 дня назад', page='{i} / {n}', cont='Содержание',
    toc=['Главное и сигналы', 'Неделя к неделе с 1 января', 'Тепловая карта: регионы × недели', '{m} по дням', 'Регионы', 'Районы: лидеры отклонений', 'Показатели для бизнеса', 'Методика и источники'],
    ytd='С 1 января', mtd='{m}', l7='7 дней', fc='Прогноз 15 дней', ly='к прошлому году', nm='к норме', p='Осадки', mm='мм', prev='год назад',
    key='Что произошло', sig='Сигналы на 2 недели', none_sig='Особых сигналов нет: погода близка к прошлому году.', warmer='теплее', colder='холоднее',
    k1='С 1 января в среднем {t}° — на {d}° {w} прошлого года{n}.', k2='Осадков с 1 января {a} мм против {b} мм год назад ({p}).',
    k3='{m}: {t}° — на {d}° {w} прошлого года{n}; осадков {a} мм против {b} мм.', k4='Последние 7 дней: на {d}° {w} прошлого года, осадков {a} мм против {b} мм.',
    k5='Самая большая разница по регионам за месяц: {r1} ({d1}°), самая маленькая — {r2} ({d2}°).', nn=' и на {d}° {w} нормы',
    s_tmp='Ближайшие 15 дней на {d}° {w}, чем год назад ({t}° против {l}°).', s_wk='Выходные {d}: осадки ожидаются в {k} из 14 регионов (год назад — в {j}).',
    s_cold='Морозные дни (≤−5°) в прогнозе: {r}.', s_hot='Жаркие дни (≥35°) в прогнозе: {r}.', s_wet='Самые дождливые 15 дней ожидаются в: {r}.', s_big='Сильнее всего отличается от прошлого года: {r} ({d}°).',
    wk='Неделя к неделе с 1 января', tt='Средняя температура за неделю, °C', dd='Разница с прошлым годом, °C', pt='Осадки за неделю, мм', fcz='прогноз', norm='норма 1991–2020',
    hm='Тепловая карта: разница температуры с прошлым годом, °C', hp='Осадки: разница с прошлым годом за неделю, мм (синее — больше, коричневое — меньше)', week='неделя с',
    mon='{m} по дням', dtt='Средняя температура за день, °C', dpt='Осадки за день, мм',
    reg='Регионы', rc=['Регион', 't° за месяц', 'к прошл. году', 'к норме', 'Осадки, мм', 'год назад', 'Прогноз 15 дн.', 'Тренд 12 недель (Δ к прошл. году)'],
    ds='Районы: лидеры отклонений', dw='Прошлая неделя ({d})', dn='Следующая неделя ({d}), прогноз', dwarm='Сильнее всего потеплело к прошлому году', dcold='Сильнее всего похолодало к прошлому году', dwarm2='Меньше всего потеплело к прошлому году', dcold2='Меньше всего похолодало к прошлому году', dwet='Больше всего осадков, мм',
    biz='Показатели для бизнеса', bc=['Регион', 'Дождливые\nвыходные', 'Жаркие\n≥35°', 'Морозные\n≤−5°', 'Со\nснегом', 'Ветреные\n≥15 м/с'], bnote='{m} (факт и прогноз): этот год / год назад',
    wkd='Ближайшие выходные: вероятность осадков', wkc=['Регион', '{a}', '{b}', 'год назад'],
    meth='Методика и источники', mt=[
        ('LFL (like-for-like)', 'Каждый день сравнивается с тем же днём недели 364 дня назад: суббота с субботой, понедельник с понедельником. Так погода сопоставима с продажами и трафиком.'),
        ('Норма 1991–2020', 'Средняя для каждого дня года за 30 лет по реанализу ERA5, сглаженная (температура ±7 дней, осадки ±15 дней).'),
        ('Узбекистан', 'Среднее по 14 центрам регионов. Районы — по центру каждого из 199 районов.'),
        ('Факт', 'Реанализ ERA5 (ECMWF / Copernicus, сетка ~10–25 км); последние дни — анализ модели ECMWF IFS.'),
        ('Прогноз', 'Модель ECMWF IFS 0,25°, до 15 дней; вероятность осадков — по ансамблю ECMWF.'),
        ('Ограничения', 'Это модельные данные, не показания метеостанций: температура обычно в пределах 1–2°, осадки за отдельные дни могут отличаться сильнее, особенно ливни и горные районы.'),
        ('Обновление', 'Отчёт пересобирается автоматически 3 раза в день (05:23, 11:23, 17:23 по Ташкенту).'),
        ('Данные', '© ECMWF (CC BY 4.0); ERA5: Copernicus Climate Change Service; доступ через Open-Meteo. Отчёт: бот @ObHavo_ECMWF_bot.')],
    mn=['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'],
    mg=['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
    ms=['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'], wd=['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'], uz='Узбекистан'),
  'uz': dict(
    brand='OSMON · ob-havo tahlili', t='Ob-havo o‘tgan yilga nisbatan', sub='O‘zbekiston · 14 viloyat markazi va 199 tuman', made='{d} holatiga',
    lfl='LFL: 364 kun oldingi shu hafta kunlari bilan solishtirish', page='{i} / {n}', cont='Mundarija',
    toc=['Asosiy va signallar', '1 yanvardan hafta haftaga', 'Issiqlik xaritasi: viloyatlar × haftalar', '{m} kunlar bo‘yicha', 'Viloyatlar', 'Tumanlar: eng katta farqlar', 'Biznes ko‘rsatkichlari', 'Uslub va manbalar'],
    ytd='1 yanvardan', mtd='{m}', l7='7 kun', fc='15 kunlik prognoz', ly='o‘tgan yilga', nm='me’yorga', p='Yog‘in', mm='mm', prev='o‘tgan yil',
    key='Nima bo‘ldi', sig='2 haftalik signallar', none_sig='Alohida signal yo‘q: ob-havo o‘tgan yilga yaqin.', warmer='iliqroq', colder='sovuqroq',
    k1='1 yanvardan o‘rtacha {t}° — o‘tgan yildan {d}° {w}{n}.', k2='1 yanvardan yog‘in {a} mm, o‘tgan yil {b} mm ({p}).',
    k3='{m}: {t}° — o‘tgan yildan {d}° {w}{n}; yog‘in {a} / {b} mm.', k4='So‘nggi 7 kun: o‘tgan yildan {d}° {w}, yog‘in {a} / {b} mm.',
    k5='Oy bo‘yicha eng katta farq: {r1} ({d1}°), eng kichik — {r2} ({d2}°).', nn=', me’yordan {d}° {w}',
    s_tmp='Keyingi 15 kun o‘tgan yildan {d}° {w} ({t}° / {l}°).', s_wk='{d} dam olish kunlari: 14 viloyatdan {k} tasida yog‘in kutilmoqda (o‘tgan yil — {j}).',
    s_cold='Prognozda sovuq kunlar (≤−5°): {r}.', s_hot='Prognozda issiq kunlar (≥35°): {r}.', s_wet='Eng ko‘p yog‘in kutilayotgan joylar: {r}.', s_big='O‘tgan yildan eng katta farq: {r} ({d}°).',
    wk='1 yanvardan hafta haftaga', tt='Haftalik o‘rtacha harorat, °C', dd='O‘tgan yildan farq, °C', pt='Haftalik yog‘in, mm', fcz='prognoz', norm='me’yor 1991–2020',
    hm='Issiqlik xaritasi: o‘tgan yildan harorat farqi, °C', hp='Yog‘in: o‘tgan yildan haftalik farq, mm (ko‘k — ko‘proq, jigarrang — kamroq)', week='hafta',
    mon='{m} kunlar bo‘yicha', dtt='Kunlik o‘rtacha harorat, °C', dpt='Kunlik yog‘in, mm',
    reg='Viloyatlar', rc=['Viloyat', 'Oy t°', 'o‘tgan yilga', 'me’yorga', 'Yog‘in, mm', 'o‘tgan yil', '15 kun prognoz', '12 hafta trendi (o‘tgan yilga Δ)'],
    ds='Tumanlar: eng katta farqlar', dw='O‘tgan hafta ({d})', dn='Keyingi hafta ({d}), prognoz', dwarm='O‘tgan yildan eng ko‘p iliqlashgan', dcold='O‘tgan yildan eng ko‘p sovuqlashgan', dwarm2='O‘tgan yildan eng kam iliqlashgan', dcold2='O‘tgan yildan eng kam sovuqlashgan', dwet='Eng ko‘p yog‘in, mm',
    biz='Biznes ko‘rsatkichlari', bc=['Viloyat', 'Yomg‘irli\ndam olish', 'Issiq\n≥35°', 'Sovuq\n≤−5°', 'Qorli', 'Shamolli\n≥15 m/s'], bnote='{m} (fakt va prognoz): bu yil / o‘tgan yil',
    wkd='Yaqin dam olish kunlari: yog‘in ehtimoli', wkc=['Viloyat', '{a}', '{b}', 'o‘tgan yil'],
    meth='Uslub va manbalar', mt=[
        ('LFL (like-for-like)', 'Har bir kun 364 kun oldingi shu hafta kuni bilan solishtiriladi: shanba shanba bilan. Shunda ob-havo savdo va oqim bilan taqqoslanadi.'),
        ('Me’yor 1991–2020', 'ERA5 reanalizi bo‘yicha yilning har bir kuni uchun 30 yillik o‘rtacha (harorat ±7 kun, yog‘in ±15 kun silliqlangan).'),
        ('O‘zbekiston', '14 viloyat markazi o‘rtachasi. Tumanlar — har bir tuman markazi bo‘yicha.'),
        ('Fakt', 'ERA5 reanalizi (ECMWF / Copernicus, ~10–25 km); so‘nggi kunlar — ECMWF IFS tahlili.'),
        ('Prognoz', 'ECMWF IFS 0,25° modeli, 15 kungacha; yog‘in ehtimoli — ECMWF ansambli.'),
        ('Cheklovlar', 'Bu model ma’lumoti, meteostansiya emas: harorat odatda 1–2° ichida, alohida kunlardagi yog‘in ko‘proq farq qilishi mumkin.'),
        ('Yangilanish', 'Hisobot kuniga 3 marta avtomatik yangilanadi (Toshkent vaqti 05:23, 11:23, 17:23).'),
        ('Ma’lumot', '© ECMWF (CC BY 4.0); ERA5: Copernicus Climate Change Service; Open-Meteo orqali. Bot: @ObHavo_ECMWF_bot.')],
    mn=['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr'],
    mg=['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'],
    ms=['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'], wd=['du', 'se', 'ch', 'pa', 'ju', 'sh', 'ya'], uz='O‘zbekiston')}


def build(lang):
    X = TX[lang]; d = json.load(open(SRC)); P = [p for p in d['places'] if p.get('iso', 'UZ') == 'UZ']
    s = dt.date.fromisoformat(d['start']); today = dt.date.fromisoformat(d['today']); ti = (today - s).days
    n = len(P[0]['tm']); last = max(i for i in range(n) if any(p['tm'][i] is not None for p in P))
    y0 = (dt.date(today.year, 1, 1) - s).days; m0 = (dt.date(today.year, today.month, 1) - s).days
    D_ = lambda i: s + dt.timedelta(days=i); MN = X['mn'][today.month - 1]
    try: DS = json.load(open(pathlib.Path(SRC).parent / 'districts.json'))
    except Exception: DS = None
    A = lambda k: np.nanmean([nan(p[k]) for p in P], 0)
    TM, PR = A('tm'), A('pr'); HN = all(p.get('norm') for p in P)
    NT = np.nanmean([nan(p['norm']['tm']) for p in P], 0) if HN else None; NP = np.nanmean([nan(p['norm']['pr']) for p in P], 0) if HN else None
    f1 = lambda x: (f'{x:.1f}'.replace('.', ',') if lang == 'ru' else f'{x:.1f}') if x == x else '—'
    sg = lambda x: ('+' if x > 0.05 else '−' if x < -0.05 else '±') + f1(abs(x)) if x == x else '—'
    ww = lambda x: X['warmer'] if x > 0 else X['colder']
    def st(tm, pr, I, nt=None):
        I = [i for i in I if 364 <= i < n]; L = [i - 364 for i in I]
        r = dict(t=np.nanmean(tm[I]) if I else np.nan, l=np.nanmean(tm[L]) if I else np.nan, a=np.nansum(pr[I]), b=np.nansum(pr[L]))
        if nt is not None and I: r['n'] = np.nanmean(nt[I])
        return r
    B = dict(ytd=range(y0, ti), mtd=range(m0, ti), l7=range(ti - 7, ti), fc=range(ti, last + 1))
    S = {k: st(TM, PR, I, NT) for k, I in B.items()}
    R = [(p, nan(p['tm']), nan(p['pr']), nan(p['norm']['tm']) if p.get('norm') else None) for p in P]
    mons = list(range(y0 - dt.date(today.year, 1, 1).weekday(), last + 1, 7))
    W = [[j for j in range(m, m + 7) if y0 <= j <= last] for m in mons]; fw = next((k for k, I in enumerate(W) if max(I) >= ti), len(W))
    NPG = 8; out = pathlib.Path(OUTP.replace('{lang}', lang))

    with PdfPages(out) as pdf:
        def page(i, title):
            f = plt.figure(figsize=(11.69, 8.27)); f.patch.set_facecolor('#ffffff')
            f.patches.append(plt.Rectangle((0, 0.935), 1, 0.065, transform=f.transFigure, fc=NAVY, ec='none'))
            f.patches.append(plt.Rectangle((0, 0.935), 0.006, 0.065, transform=f.transFigure, fc=ACC, ec='none'))
            f.text(0.03, 0.967, title, color='#fff', fontsize=16, fontweight='bold', va='center')
            f.text(0.97, 0.967, X['brand'], color='#9fb0c4', fontsize=9.5, va='center', ha='right')
            f.add_artist(plt.Line2D([0.03, 0.97], [0.045, 0.045], transform=f.transFigure, color=LINE, lw=0.8))
            f.text(0.03, 0.024, f"{X['t']} · {X['made'].format(d=today.strftime('%d.%m.%Y'))} · {X['lfl']}", fontsize=7.5, color=MUTED)
            f.text(0.97, 0.024, X['page'].format(i=i, n=NPG), fontsize=8, color=MUTED, ha='right'); return f
        def card(f, x, y, w, h, fc=SOFT, ec=LINE):
            f.patches.append(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0,rounding_size=0.008', transform=f.transFigure, fc=fc, ec=ec, lw=0.8, zorder=-1))
        def style(ax, grid='y'):
            for s_ in ('top', 'right'): ax.spines[s_].set_visible(False)
            ax.tick_params(labelsize=8.5, length=0); ax.grid(axis=grid, color='#eef1f4', lw=0.8); ax.set_axisbelow(True)

        # ---------- 1. summary
        f = plt.figure(figsize=(11.69, 8.27)); f.patch.set_facecolor('#ffffff')
        f.patches.append(plt.Rectangle((0, 0), 0.30, 1, transform=f.transFigure, fc=NAVY, ec='none'))
        f.patches.append(plt.Rectangle((0.30, 0), 0.004, 1, transform=f.transFigure, fc=ACC, ec='none'))
        f.text(0.03, 0.92, 'OSMON', color='#fff', fontsize=26, fontweight='bold'); f.text(0.03, 0.885, X['brand'].split('·')[1].strip(), color='#9fb0c4', fontsize=11)
        f.text(0.03, 0.72, '\n'.join(textwrap.wrap(X['t'], 20)), color='#fff', fontsize=20, fontweight='bold', linespacing=1.15)
        f.text(0.03, 0.665, '\n'.join(textwrap.wrap(X['sub'], 34)), color='#c9d3df', fontsize=10, va='top')
        f.text(0.03, 0.605, X['made'].format(d=today.strftime('%d.%m.%Y')), color='#c9d3df', fontsize=10.5)
        f.text(0.03, 0.53, X['cont'], color=ACC, fontsize=11, fontweight='bold')
        for k, t_ in enumerate(X['toc']): f.text(0.03, 0.495 - k * 0.032, f"{k + 1:>2}   {t_.format(m=MN)}", color='#dfe6ee', fontsize=10)
        f.text(0.03, 0.075, '\n'.join(textwrap.wrap(X['lfl'], 42)), color='#9fb0c4', fontsize=8.5, va='bottom'); f.text(0.03, 0.04, '© ECMWF · ERA5 Copernicus', color='#9fb0c4', fontsize=8.5)
        for j, (k, lab) in enumerate([('ytd', X['ytd']), ('mtd', X['mtd'].format(m=MN)), ('l7', X['l7']), ('fc', X['fc'])]):
            v = S[k]; x0 = 0.33 + j * 0.163; dtv = v['t'] - v['l']; card(f, x0, 0.70, 0.152, 0.25)
            f.text(x0 + 0.012, 0.915, lab.upper(), fontsize=8.5, color=MUTED, fontweight='bold')
            f.text(x0 + 0.012, 0.845, f"{f1(v['t'])}°", fontsize=27, fontweight='bold', color=INK)
            f.text(x0 + 0.012, 0.805, f"{sg(dtv)}° {X['ly']}", fontsize=9.5, color=WARM if dtv > 0 else COLD, fontweight='bold')
            if 'n' in v: f.text(x0 + 0.012, 0.778, f"{sg(v['t'] - v['n'])}° {X['nm']}", fontsize=9, color=NORM)
            f.text(x0 + 0.012, 0.735, f"{X['p']}: {round(v['a'])} {X['mm']}", fontsize=9, color=RAIN, fontweight='bold'); f.text(x0 + 0.012, 0.712, f"{X['prev']}: {round(v['b'])} {X['mm']}", fontsize=8, color=MUTED)
        nn = lambda v: X['nn'].format(d=f1(abs(v['t'] - v['n'])), w=ww(v['t'] - v['n'])) if 'n' in v else ''
        reg_m = sorted([(p[lang], st(tm, pr, B['mtd'])) for p, tm, pr, _ in R], key=lambda x: x[1]['t'] - x[1]['l'])
        a, b = S['ytd']['a'], S['ytd']['b']
        keys = [X['k1'].format(t=f1(S['ytd']['t']), d=f1(abs(S['ytd']['t'] - S['ytd']['l'])), w=ww(S['ytd']['t'] - S['ytd']['l']), n=nn(S['ytd'])),
                X['k2'].format(a=round(a), b=round(b), p=(sg((a - b) / b * 100)[:-2] + '%') if b else '—'),
                X['k3'].format(m=MN, t=f1(S['mtd']['t']), d=f1(abs(S['mtd']['t'] - S['mtd']['l'])), w=ww(S['mtd']['t'] - S['mtd']['l']), n=nn(S['mtd']), a=round(S['mtd']['a']), b=round(S['mtd']['b'])),
                X['k4'].format(d=f1(abs(S['l7']['t'] - S['l7']['l'])), w=ww(S['l7']['t'] - S['l7']['l']), a=round(S['l7']['a']), b=round(S['l7']['b']))]
        if len(reg_m) > 1: keys.append(X['k5'].format(r1=reg_m[-1][0], d1=sg(reg_m[-1][1]['t'] - reg_m[-1][1]['l']), r2=reg_m[0][0], d2=sg(reg_m[0][1]['t'] - reg_m[0][1]['l'])))
        # the signals of the next two weeks
        sig = []; F = list(B['fc'])
        if F:
            v = S['fc']; sig.append(('🌡', X['s_tmp'].format(d=f1(abs(v['t'] - v['l'])), w=ww(v['t'] - v['l']), t=f1(v['t']), l=f1(v['l']))))
            sat = next((i for i in F if D_(i).weekday() == 5), None)
            if sat is not None:
                we = [i for i in (sat, sat + 1) if i <= last]
                k_ = sum(1 for p in P if any((p['pr'][i] or 0) >= 1 for i in we)); j_ = sum(1 for p in P if any((p['pr'][i - 364] or 0) >= 1 for i in we))
                sig.append(('☂', X['s_wk'].format(d=f"{D_(sat).day}–{D_(sat + 1).day} {X['mg'][D_(sat).month - 1]}", k=k_, j=j_)))
            fr = [p[lang] for p in P if any((p['tn'][i] if p['tn'][i] is not None else 99) <= -5 for i in F)]
            if fr: sig.append(('❄', X['s_cold'].format(r=', '.join(fr[:5]) + ('…' if len(fr) > 5 else ''))))
            ht = [p[lang] for p in P if any((p['tx'][i] or -99) >= 35 for i in F)]
            if ht: sig.append(('☀', X['s_hot'].format(r=', '.join(ht[:5]) + ('…' if len(ht) > 5 else ''))))
            wet = sorted(((p[lang], np.nansum(nan(p['pr'])[F])) for p in P), key=lambda x: -x[1])
            if wet[0][1] >= 5: sig.append(('💧', X['s_wet'].format(r=', '.join(f"{nm} {round(v)} {X['mm']}" for nm, v in wet[:3] if v >= 2))))
            big = max(((p[lang], st(tm, pr, F)) for p, tm, pr, _ in R), key=lambda x: abs(x[1]['t'] - x[1]['l']))
            if abs(big[1]['t'] - big[1]['l']) >= 2: sig.append(('⚑', X['s_big'].format(r=big[0], d=sg(big[1]['t'] - big[1]['l']))))
        f.text(0.33, 0.645, X['key'], fontsize=13, fontweight='bold', color=INK)
        y = 0.605
        for k_ in keys:
            ln = textwrap.wrap(k_, 98); f.text(0.335, y, '—', fontsize=10, color=ACC, fontweight='bold', va='top'); f.text(0.355, y, '\n'.join(ln), fontsize=10, color=INK, va='top', linespacing=1.3); y -= 0.022 + 0.026 * len(ln)
        card(f, 0.33, 0.06, 0.64, y - 0.08, fc='#fff8f0', ec='#f3d9bd')
        f.text(0.345, y - 0.055, X['sig'], fontsize=13, fontweight='bold', color='#a1520c'); y2 = y - 0.095
        for ic, t_ in (sig or [('•', X['none_sig'])]):
            ln = textwrap.wrap(t_, 92); f.text(0.35, y2, '→', fontsize=10, color=ACC, fontweight='bold', va='top'); f.text(0.368, y2, '\n'.join(ln), fontsize=10, color=INK, va='top', linespacing=1.3); y2 -= 0.02 + 0.026 * len(ln)
        pdf.savefig(f); plt.close(f)

        # ---------- 2. week to week
        f = page(2, X['wk']); x = np.arange(len(W))
        T = np.array([np.nanmean(TM[I]) for I in W]); L = np.array([np.nanmean(TM[[j - 364 for j in I]]) for I in W])
        Pp = np.array([np.nansum(PR[I]) for I in W]); Q = np.array([np.nansum(PR[[j - 364 for j in I]]) for I in W])
        labs = [f"{D_(m).day} {X['ms'][D_(m).month - 1]}" for m in mons]
        ax = f.add_axes([0.06, 0.60, 0.9, 0.29]); cx = f.add_axes([0.06, 0.40, 0.9, 0.14], sharex=ax); bx = f.add_axes([0.06, 0.09, 0.9, 0.25], sharex=ax)
        for a_ in (ax, cx, bx):
            style(a_); a_.axvspan(fw - 0.5, len(W) - 0.5, color='#fff4e8', zorder=0)
        ax.plot(x, L, color=LY, lw=1.8, label=str(today.year - 1)); ax.plot(x[:fw + 1], T[:fw + 1], color=WARM, lw=2.4, label=str(today.year))
        ax.plot(x[fw:], T[fw:], color=WARM, lw=2.4, ls=(0, (4, 3)), label=f"{today.year} · {X['fcz']}")
        if HN: ax.plot(x, [np.nanmean(NT[I]) for I in W], color=NORM, lw=1.3, ls=(0, (1, 2)), label=X['norm'])
        ax.set_title(X['tt'], loc='left', fontsize=11, color=INK); ax.legend(frameon=False, fontsize=8.5, ncol=4, loc='upper left'); plt.setp(ax.get_xticklabels(), visible=False)
        dif = T - L; cx.bar(x, dif, 0.75, color=[WARM if v > 0 else COLD for v in dif], alpha=[1 if k < fw else 0.5 for k in range(len(x))] if False else 0.85); cx.axhline(0, color='#9aa6b4', lw=0.8)
        for k in sorted(range(len(dif)), key=lambda k: -abs(dif[k]))[:3]: cx.annotate(sg(dif[k]), (k, dif[k]), ha='center', va='bottom' if dif[k] > 0 else 'top', fontsize=8, color=INK, fontweight='bold', xytext=(0, 2 if dif[k] > 0 else -2), textcoords='offset points')
        cx.set_title(X['dd'], loc='left', fontsize=11, color=INK); plt.setp(cx.get_xticklabels(), visible=False)
        bx.bar(x - 0.2, Q, 0.38, color='#c7cfd8', label=str(today.year - 1)); bx.bar(x + 0.2, Pp, 0.38, color=[RAIN if k < fw else '#9cc1ec' for k in range(len(x))], label=str(today.year))
        if HN: bx.plot(x, [np.nansum(NP[I]) for I in W], color=NORM, lw=1.3, ls=(0, (1, 2)), label=X['norm'])
        bx.set_title(X['pt'], loc='left', fontsize=11, color=INK); bx.legend(frameon=False, fontsize=8.5, ncol=3, loc='upper left')
        bx.set_xticks(x[::max(1, len(x) // 13)]); bx.set_xticklabels(labs[::max(1, len(x) // 13)]); bx.set_xlim(-0.6, len(W) - 0.4)
        pdf.savefig(f); plt.close(f)

        # ---------- 3. heat map regions × weeks
        f = page(3, X['toc'][2]); K = list(range(max(0, len(W) - 12), len(W)))
        hm = np.array([[st(tm, pr, W[k])['t'] - st(tm, pr, W[k])['l'] for k in K] for _, tm, pr, _ in R])
        hp = np.array([[(lambda v: v['a'] - v['b'])(st(tm, pr, W[k])) for k in K] for _, tm, pr, _ in R])
        names = [p[lang] for p, *_ in R]; cols = [f"{D_(mons[k]).day} {X['ms'][D_(mons[k]).month - 1]}" + ('*' if k >= fw else '') for k in K]
        for (y0_, h_, M_, cm, nm_, title, fmt) in ((0.50, 0.38, hm, DIV, TwoSlopeNorm(0, -8, 8), X['hm'], lambda v: sg(v)), (0.08, 0.36, np.clip(hp, -25, 25), WET, TwoSlopeNorm(0, -25, 25), X['hp'], lambda v: '·' if abs(v) < 0.5 else ('+' if v > 0 else '−') + f"{abs(v):.0f}")):
            ax = f.add_axes([0.2, y0_, 0.77, h_]); ax.imshow(M_, cmap=cm, norm=nm_, aspect='auto')
            ax.set_yticks(range(len(names))); ax.set_yticklabels(names, fontsize=8.5); ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, fontsize=8)
            ax.tick_params(length=0); [s_.set_visible(False) for s_ in ax.spines.values()]; ax.set_title(title, loc='left', fontsize=11, color=INK, x=-0.21)
            for r_ in range(M_.shape[0]):
                for c_ in range(M_.shape[1]):
                    v = (hm if M_ is hm else hp)[r_, c_]; ax.text(c_, r_, fmt(v), ha='center', va='center', fontsize=7.2, color='#ffffff' if (M_ is hm and abs(v) > 5) else INK)
            if K[-1] >= fw: ax.axvline(K.index(fw) - 0.5 if fw in K else -0.5, color=ACC, lw=1.5)
        f.text(0.97, 0.055, '* ' + X['fcz'], fontsize=8, color=MUTED, ha='right')
        pdf.savefig(f); plt.close(f)

        # ---------- 4. this month by days
        f = page(4, X['mon'].format(m=MN)); Dm = [j for j in range(m0, last + 1) if D_(j).month == today.month]; x = np.arange(len(Dm)); fd = next((k for k, j in enumerate(Dm) if j >= ti), len(Dm))
        T = TM[Dm]; L = TM[[j - 364 for j in Dm]]
        ax = f.add_axes([0.06, 0.52, 0.9, 0.37]); bx = f.add_axes([0.06, 0.13, 0.9, 0.31], sharex=ax)
        for a_ in (ax, bx): style(a_); a_.axvspan(fd - 0.5, len(Dm) - 0.5, color='#fff4e8', zorder=0)
        ax.fill_between(x, T, L, where=T >= L, color=WARM, alpha=0.15, interpolate=True); ax.fill_between(x, T, L, where=T < L, color=COLD, alpha=0.15, interpolate=True)
        ax.plot(x, L, color=LY, lw=1.8, label=str(today.year - 1)); ax.plot(x[:fd + 1], T[:fd + 1], color=WARM, lw=2.4, label=str(today.year)); ax.plot(x[fd:], T[fd:], color=WARM, lw=2.4, ls=(0, (4, 3)), label=X['fcz'])
        if HN: ax.plot(x, NT[Dm], color=NORM, lw=1.3, ls=(0, (1, 2)), label=X['norm'])
        ax.set_title(X['dtt'], loc='left', fontsize=11, color=INK); ax.legend(frameon=False, fontsize=8.5, ncol=4, loc='upper right'); plt.setp(ax.get_xticklabels(), visible=False)
        bx.bar(x - 0.2, PR[[j - 364 for j in Dm]], 0.38, color='#c7cfd8', label=str(today.year - 1)); bx.bar(x + 0.2, PR[Dm], 0.38, color=[RAIN if k < fd else '#9cc1ec' for k in range(len(x))], label=str(today.year))
        bx.set_title(X['dpt'], loc='left', fontsize=11, color=INK); bx.legend(frameon=False, fontsize=8.5, ncol=2, loc='upper right')
        bx.set_xticks(x); bx.set_xticklabels([f"{D_(j).day}\n{X['wd'][D_(j).weekday()]}" for j in Dm], fontsize=7.5); bx.set_xlim(-0.6, len(Dm) - 0.4)
        for k, j in enumerate(Dm):
            if D_(j).weekday() >= 5: bx.get_xticklabels()[k].set_color(WARM)
        pdf.savefig(f); plt.close(f)

        # ---------- 5. regions
        f = page(5, X['reg']); rows = []; K12 = list(range(max(0, fw - 12), fw))
        for p, tm, pr, nt in R:
            a_ = st(tm, pr, B['mtd'], nt); c_ = st(tm, pr, B['fc'])
            rows.append((p[lang], a_['t'], a_['t'] - a_['l'], (a_['t'] - a_['n']) if 'n' in a_ else np.nan, a_['a'], a_['b'], c_['t'] - c_['l'], [st(tm, pr, W[k])['t'] - st(tm, pr, W[k])['l'] for k in K12]))
        rows.sort(key=lambda r: -r[2]); cx_ = [0.03, 0.25, 0.33, 0.42, 0.51, 0.59, 0.67, 0.77]; top = 0.87; rh = 0.054
        for j, c in enumerate(X['rc']): f.text(cx_[j] + (0 if j in (0, 7) else 0.035), top, c, fontsize=8.8, color=MUTED, fontweight='bold', ha='left' if j in (0, 7) else 'center')
        for i, r in enumerate(rows):
            y = top - 0.04 - i * rh
            if i % 2 == 0: f.patches.append(plt.Rectangle((0.025, y - 0.02), 0.95, rh, transform=f.transFigure, fc=SOFT, ec='none', zorder=-1))
            f.text(cx_[0], y, r[0], fontsize=9.5, color=INK, va='center')
            vals = [(f1(r[1]) + '°', None), (sg(r[2]), r[2]), (sg(r[3]), r[3]), (str(round(r[4])), None), (str(round(r[5])), None), (sg(r[6]), r[6])]
            for j, (t_, v) in enumerate(vals, 1):
                f.text(cx_[j] + 0.035, y, t_, fontsize=9.5, ha='center', va='center', color=(WARM if v > 0.3 else COLD if v < -0.3 else INK) if v is not None and v == v else INK, fontweight='bold' if v is not None else 'normal')
            sx = f.add_axes([cx_[7], y - 0.016, 0.19, 0.032]); sp = np.array(r[7]); sx.bar(range(len(sp)), sp, color=[WARM if v > 0 else COLD for v in sp], width=0.8); sx.axhline(0, color='#9aa6b4', lw=0.6)
            sx.set_ylim(-8, 8); sx.axis('off')
        pdf.savefig(f); plt.close(f)

        # ---------- 6. districts
        f = page(6, X['ds'])
        if DS and DS.get('d'):
            wk = [dt.date.fromisoformat(w) for w in DS['weeks']]; kl = max(k for k, w in enumerate(wk) if w + dt.timedelta(days=6) < today); kn = min(len(wk) - 1, kl + 2 if wk[kl + 1] <= today else kl + 1)
            def lst(ax, items, title, col, fmt):
                ax.axis('off'); ax.set_title(title, loc='left', fontsize=10, color=col, fontweight='bold')
                for i, (nm_, rg, v) in enumerate(items):
                    ax.text(0, 1 - (i + 1) * 0.095, f"{i + 1}. {nm_}", fontsize=8.6, color=INK, transform=ax.transAxes)
                    ax.text(0, 1 - (i + 1) * 0.095 - 0.042, rg, fontsize=7, color=MUTED, transform=ax.transAxes)
                    ax.text(1, 1 - (i + 1) * 0.095, fmt(v), fontsize=9, color=col, fontweight='bold', ha='right', transform=ax.transAxes)
            rg_ = lambda w: f"{w.day}–{(w + dt.timedelta(days=6)).day} {X['ms'][(w + dt.timedelta(days=6)).month - 1]}"
            for row, (k, ttl) in enumerate(((kl, X['dw'].format(d=rg_(wk[kl]))), (kn, X['dn'].format(d=rg_(wk[kn]))))):
                y0_ = 0.50 if row == 0 else 0.07
                f.text(0.03, y0_ + 0.385, ttl, fontsize=12, fontweight='bold', color=INK)
                v = [(x_['n'][lang], x_['r'][lang], x_['dt'][k]) for x_ in DS['d'] if x_['dt'][k] is not None]
                hi_, lo_ = sorted(v, key=lambda z: -z[2])[:9], sorted(v, key=lambda z: z[2])[:9]
                lst(f.add_axes([0.03, y0_, 0.28, 0.35]), hi_, X['dwarm'] if hi_[0][2] > 0 else X['dcold2'], WARM if hi_[0][2] > 0 else COLD, lambda z: sg(z) + '°')
                lst(f.add_axes([0.36, y0_, 0.28, 0.35]), lo_, X['dcold'] if lo_[0][2] < 0 else X['dwarm2'], COLD if lo_[0][2] < 0 else WARM, lambda z: sg(z) + '°')
                pv = [(x_['n'][lang], x_['r'][lang], x_['p'][k]) for x_ in DS['d']]
                lst(f.add_axes([0.69, y0_, 0.28, 0.35]), sorted(pv, key=lambda z: -z[2])[:9], X['dwet'], RAIN, lambda z: f"{z:.0f}")
        pdf.savefig(f); plt.close(f)

        # ---------- 7. business
        f = page(7, X['biz'])
        Im = [i for i in range(m0, last + 1) if D_(i).month == today.month]; Lm = [i - 364 for i in Im]
        ind = [lambda p, I: sum(1 for i in I if D_(i).weekday() >= 5 and (p['pr'][i] or 0) >= 1), lambda p, I: sum(1 for i in I if (p['tx'][i] or -99) >= 35),
               lambda p, I: sum(1 for i in I if (p['tn'][i] if p['tn'][i] is not None else 99) <= -5), lambda p, I: sum(1 for i in I if (p['sn'][i] or 0) >= 0.5),
               lambda p, I: sum(1 for i in I if p.get('gu') and (p['gu'][i] or 0) >= 15)]
        f.text(0.03, 0.885, X['bnote'].format(m=MN), fontsize=10, color=MUTED)
        cx_ = [0.03, 0.19, 0.245, 0.30, 0.355, 0.41]; top = 0.84; rh = 0.053
        for j, c in enumerate(X['bc']): f.text(cx_[j] + (0 if j == 0 else 0.03), top, c, fontsize=8, color=MUTED, fontweight='bold', ha='left' if j == 0 else 'center', va='center', linespacing=1.1)
        for i, p in enumerate(P):
            y = top - 0.045 - i * rh
            if i % 2 == 0: f.patches.append(plt.Rectangle((0.025, y - 0.02), 0.445, rh, transform=f.transFigure, fc=SOFT, ec='none', zorder=-1))
            f.text(cx_[0], y, p[lang], fontsize=8.8, color=INK, va='center')
            for j, fn in enumerate(ind, 1):
                a_, b_ = fn(p, Im), fn(p, Lm); f.text(cx_[j] + 0.03, y, f"{a_} / {b_}", fontsize=9, ha='center', va='center', color=WARM if a_ > b_ else COLD if a_ < b_ else INK, fontweight='bold' if a_ != b_ else 'normal')
        # the next two weekends: chance of rain
        sats = [i for i in range(ti, last + 1) if D_(i).weekday() == 5][:2]
        if sats:
            f.text(0.52, 0.885, X['wkd'], fontsize=11, fontweight='bold', color=INK)
            hd = [X['wkc'][0]] + [f"{D_(i).day}–{D_(i + 1).day} {X['ms'][D_(i).month - 1]}" for i in sats] + [X['wkc'][3]]
            cx2 = [0.52, 0.70, 0.79, 0.88]
            for j, c in enumerate(hd): f.text(cx2[j] + (0 if j == 0 else 0.04), top, c, fontsize=8.5, color=MUTED, fontweight='bold', ha='left' if j == 0 else 'center')
            for i, p in enumerate(P):
                y = top - 0.045 - i * rh
                if i % 2 == 0: f.patches.append(plt.Rectangle((0.515, y - 0.02), 0.455, rh, transform=f.transFigure, fc=SOFT, ec='none', zorder=-1))
                f.text(cx2[0], y, p[lang], fontsize=8.8, color=INK, va='center')
                for j, sa in enumerate(sats, 1):
                    days_ = [i_ for i_ in (sa, sa + 1) if i_ <= last]; pp = max([(p.get('pp') or [None] * n)[i_] or 0 for i_ in days_] or [0]); mm = sum((p['pr'][i_] or 0) for i_ in days_)
                    c_ = '#d6e8fb' if pp >= 60 else '#eef5fd' if pp >= 30 else None
                    if c_: f.patches.append(FancyBboxPatch((cx2[j] + 0.008, y - 0.015), 0.064, 0.03, boxstyle='round,pad=0,rounding_size=0.006', transform=f.transFigure, fc=c_, ec='none'))
                    f.text(cx2[j] + 0.04, y, f"{pp:.0f}% · {mm:.0f} {X['mm']}", fontsize=8.5, ha='center', va='center', color=RAIN if pp >= 30 else INK)
                ly_ = sum(1 for sa in sats for i_ in (sa - 364, sa - 363) if (p['pr'][i_] or 0) >= 1)
                f.text(cx2[3] + 0.04, y, f"{ly_} / {2 * len(sats)}", fontsize=8.5, ha='center', va='center', color=MUTED)
        pdf.savefig(f); plt.close(f)

        # ---------- 8. method
        f = page(8, X['meth'])
        for i, (h, t_) in enumerate(X['mt']):
            y = 0.86 - i * 0.1; f.text(0.04, y, h, fontsize=11, fontweight='bold', color=INK)
            tt_ = f.text(0.24, y, t_, fontsize=10, color='#3a4858', va='top', wrap=True); tt_._get_wrap_line_width = lambda: 0.7 * f.bbox.width
        pdf.savefig(f); plt.close(f)
    print(out, out.stat().st_size // 1024, 'KB')


if __name__ == '__main__':
    for L in LANGS: build(L)
