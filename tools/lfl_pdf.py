"""PDF report "weather against last year" (A4 landscape) for the bot: Uzbekistan (the mean of the 14 region centres) —
1) the main numbers and conclusions, 2) by weeks since 1 January, 3) this month by days, 4) the regions, 5) the business indicators.
LFL: the same weekdays 364 days back; the climate norm 1991–2020 where tools/lfl_norm.py has been run.
Usage: python tools/lfl_pdf.py lfl/lfl.json 'lfl/UZ_lfl_{lang}.pdf' ru,uz"""
import json, sys, datetime as dt, pathlib
import numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

SRC, OUTP = sys.argv[1], sys.argv[2]; LANGS = (sys.argv[3] if len(sys.argv) > 3 else 'ru').split(',')
NAVY, INK, MUTED, LINE, WARM, COLD, RAIN, LY, NORM = '#2b3a4e', '#2b3a4e', '#6b7a8c', '#dde3ea', '#e0643a', '#2f6fd0', '#3b82d6', '#9aa6b4', '#3f9d6b'
TX = {'ru': dict(t='Погода против прошлого года', uz='Узбекистан · среднее по 14 центрам регионов', lfl='LFL: те же дни недели 364 дня назад', made='Данные на {d}',
                 ytd='С 1 января', mtd='Этот месяц', l7='Последние 7 дней', fc='Прогноз 15 дней', ly='год назад', norm='норма', p='Осадки', mm='мм',
                 sum='Главное', wk='По неделям с 1 января', mon='{m} по дням', tt='Средняя температура, °C', pt='Осадки, мм', reg='Регионы', ind='Показатели для бизнеса',
                 cols=['Регион', 't° месяц', 'Δ к прошл. году', 'Δ к норме', 'Осадки, мм', 'год назад, мм', 'Прогноз: Δ t°'],
                 icol=['Регион', 'Дождл. выходные', 'Жаркие ≥35°', 'Морозные ≤−5°', 'Со снегом', 'Ветреные ≥15 м/с'], this='этот год / год назад', fcz='прогноз',
                 src='Факт: ERA5 (ECMWF / Copernicus) и анализ ECMWF; прогноз: ECMWF IFS (Open-Meteo); норма 1991–2020: ERA5. Модель, не метеостанции.',
                 warmer='теплее', colder='холоднее', s1='С 1 января {t}° — на {d}° {w} прошлого года{n}.', s2='Осадков {a} мм против {b} мм ({p}).',
                 s3='{m}: {t}° — на {d}° {w} прошлого года{n}; осадков {a} мм против {b} мм.', s4='Последние 7 дней: на {d}° {w}, осадков {a} мм против {b} мм.',
                 s5='Прогноз на 15 дней: {t}° — на {d}° {w}, чем год назад; осадков {a} мм против {b} мм.', nn=' и на {d}° {w} нормы',
                 mn=['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'],
                 ms=['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'], page='стр. {i}'),
      'uz': dict(t='Ob-havo o‘tgan yilga nisbatan', uz='O‘zbekiston · 14 viloyat markazi o‘rtachasi', lfl='LFL: 364 kun oldingi shu hafta kunlari', made='{d} holatiga',
                 ytd='1 yanvardan', mtd='Shu oy', l7='So‘nggi 7 kun', fc='15 kunlik prognoz', ly='o‘tgan yil', norm='me’yor', p='Yog‘in', mm='mm',
                 sum='Asosiy', wk='1 yanvardan haftalar', mon='{m} kunlar bo‘yicha', tt='O‘rtacha harorat, °C', pt='Yog‘in, mm', reg='Viloyatlar', ind='Biznes ko‘rsatkichlari',
                 cols=['Viloyat', 't° oy', 'Δ o‘tgan yilga', 'Δ me’yorga', 'Yog‘in, mm', 'o‘tgan yil, mm', 'Prognoz: Δ t°'],
                 icol=['Viloyat', 'Yomg‘irli dam olish', 'Issiq ≥35°', 'Sovuq ≤−5°', 'Qorli', 'Shamolli ≥15 m/s'], this='bu yil / o‘tgan yil', fcz='prognoz',
                 src='Fakt: ERA5 (ECMWF / Copernicus) va ECMWF tahlili; prognoz: ECMWF IFS (Open-Meteo); me’yor 1991–2020: ERA5. Model, meteostansiya emas.',
                 warmer='iliqroq', colder='sovuqroq', s1='1 yanvardan {t}° — o‘tgan yildan {d}° {w}{n}.', s2='Yog‘in {a} mm, o‘tgan yil {b} mm ({p}).',
                 s3='{m}: {t}° — o‘tgan yildan {d}° {w}{n}; yog‘in {a} / {b} mm.', s4='So‘nggi 7 kun: {d}° {w}, yog‘in {a} / {b} mm.',
                 s5='15 kunlik prognoz: {t}° — o‘tgan yildan {d}° {w}; yog‘in {a} / {b} mm.', nn=', me’yordan {d}° {w}',
                 mn=['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr'],
                 ms=['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'], page='{i}-bet')}
nan = lambda a: np.array([np.nan if x is None else x for x in a], float)


def build(lang):
    X = TX[lang]; d = json.load(open(SRC)); P = [p for p in d['places'] if p.get('iso', 'UZ') == 'UZ']
    s = dt.date.fromisoformat(d['start']); today = dt.date.fromisoformat(d['today']); ti = (today - s).days
    n = len(P[0]['tm']); last = max(i for i in range(n) if any(p['tm'][i] is not None for p in P))
    y0 = (dt.date(today.year, 1, 1) - s).days; m0 = (dt.date(today.year, today.month, 1) - s).days
    avg = lambda k: np.nanmean([nan(p[k]) for p in P], 0)
    TM, PR = avg('tm'), avg('pr'); HN = all(p.get('norm') for p in P)
    NT = np.nanmean([nan(p['norm']['tm']) for p in P], 0) if HN else None; NPR = np.nanmean([nan(p['norm']['pr']) for p in P], 0) if HN else None
    f1 = lambda x: f'{x:.1f}'.replace('.', ',') if lang == 'ru' else f'{x:.1f}'
    sg = lambda x: ('+' if x > 0.05 else '−' if x < -0.05 else '±') + f1(abs(x))
    ww = lambda x: X['warmer'] if x > 0 else X['colder']
    def st(tm, pr, I, nt=None):
        I = [i for i in I if 364 <= i < n]; L = [i - 364 for i in I]
        r = dict(t=np.nanmean(tm[I]), l=np.nanmean(tm[L]), a=np.nansum(pr[I]), b=np.nansum(pr[L]))
        if nt is not None: r['n'] = np.nanmean(nt[I])
        return r
    B = dict(ytd=range(y0, ti), mtd=range(m0, ti), l7=range(ti - 7, ti), fc=range(ti, last + 1))
    S = {k: st(TM, PR, I, NT) for k, I in B.items()}
    out = pathlib.Path(OUTP.replace('{lang}', lang))
    with PdfPages(out) as pdf:
        def page(title, i):
            f = plt.figure(figsize=(11.69, 8.27)); f.patch.set_facecolor('#ffffff')
            f.patches.append(plt.Rectangle((0, 0.92), 1, 0.08, transform=f.transFigure, fc=NAVY, ec='none'))
            f.text(0.03, 0.958, f"{X['t']} · {title}", color='#fff', fontsize=17, fontweight='bold', va='center')
            f.text(0.97, 0.958, f"{X['made'].format(d=today.strftime('%d.%m.%Y'))} · {X['page'].format(i=i)}", color='#c9d3df', fontsize=10, va='center', ha='right')
            f.text(0.03, 0.02, X['src'], fontsize=7.5, color=MUTED); return f
        # 1. the main numbers
        f = page(X['sum'], 1); f.text(0.03, 0.87, X['uz'], fontsize=13, color=MUTED); f.text(0.03, 0.835, X['lfl'], fontsize=11, color=MUTED)
        for j, k in enumerate(['ytd', 'mtd', 'l7', 'fc']):
            x0 = 0.03 + j * 0.24; v = S[k]; dtv = v['t'] - v['l']
            f.patches.append(plt.Rectangle((x0, 0.55), 0.22, 0.24, transform=f.transFigure, fc='#f6f8fa', ec=LINE))
            f.text(x0 + 0.012, 0.755, X[k], fontsize=12, color=MUTED, fontweight='bold')
            f.text(x0 + 0.012, 0.68, f"{f1(v['t'])}°", fontsize=30, fontweight='bold', color=INK)
            f.text(x0 + 0.012, 0.64, f"{sg(dtv)}° {X['ly']}" + (f" · {sg(v['t'] - v['n'])}° {X['norm']}" if 'n' in v else ''), fontsize=11, color=WARM if dtv > 0 else COLD)
            f.text(x0 + 0.012, 0.585, f"{X['p']}: {round(v['a'])} / {round(v['b'])} {X['mm']}", fontsize=11, color=RAIN)
        nn = lambda v: X['nn'].format(d=f1(abs(v['t'] - v['n'])), w=ww(v['t'] - v['n'])) if 'n' in v else ''
        a, b = S['ytd']['a'], S['ytd']['b']
        lines = [X['s1'].format(t=f1(S['ytd']['t']), d=f1(abs(S['ytd']['t'] - S['ytd']['l'])), w=ww(S['ytd']['t'] - S['ytd']['l']), n=nn(S['ytd'])),
                 X['s2'].format(a=round(a), b=round(b), p=(sg((a - b) / b * 100)[:-2] + '%') if b else '—'),
                 X['s3'].format(m=X['mn'][today.month - 1], t=f1(S['mtd']['t']), d=f1(abs(S['mtd']['t'] - S['mtd']['l'])), w=ww(S['mtd']['t'] - S['mtd']['l']), n=nn(S['mtd']), a=round(S['mtd']['a']), b=round(S['mtd']['b'])),
                 X['s4'].format(d=f1(abs(S['l7']['t'] - S['l7']['l'])), w=ww(S['l7']['t'] - S['l7']['l']), a=round(S['l7']['a']), b=round(S['l7']['b'])),
                 X['s5'].format(t=f1(S['fc']['t']), d=f1(abs(S['fc']['t'] - S['fc']['l'])), w=ww(S['fc']['t'] - S['fc']['l']), a=round(S['fc']['a']), b=round(S['fc']['b']))]
        for i, l in enumerate(lines): f.text(0.04, 0.46 - i * 0.075, '•  ' + l, fontsize=13.5, color=INK)
        pdf.savefig(f); plt.close(f)
        # 2. weeks, 3. this month by days
        def chart(title, i, idx, labels, fcfrom):
            f = page(title, i); ax = f.add_axes([0.06, 0.52, 0.9, 0.34]); bx = f.add_axes([0.06, 0.09, 0.9, 0.34]); x = np.arange(len(idx))
            T = np.array([np.nanmean(TM[I]) for I in idx]); L = np.array([np.nanmean(TM[[j - 364 for j in I]]) for I in idx])
            Pp = np.array([np.nansum(PR[I]) for I in idx]); Q = np.array([np.nansum(PR[[j - 364 for j in I]]) for I in idx])
            for a_ in (ax, bx):
                a_.set_xlim(-0.6, len(idx) - 0.4); a_.grid(axis='y', color='#eef1f4'); a_.set_axisbelow(True)
                for s_ in ('top', 'right'): a_.spines[s_].set_visible(False)
                if fcfrom < len(idx): a_.axvspan(fcfrom - 0.5, len(idx) - 0.4, color='#fff4e8', zorder=0)
                a_.set_xticks(x[::max(1, len(x) // 12)]); a_.set_xticklabels(labels[::max(1, len(x) // 12)], fontsize=8.5, color=MUTED)
            ax.fill_between(x, T, L, where=T >= L, color=WARM, alpha=0.15, interpolate=True); ax.fill_between(x, T, L, where=T < L, color=COLD, alpha=0.15, interpolate=True)
            ax.plot(x, L, color=LY, lw=1.8, label=str(today.year - 1)); ax.plot(x[:fcfrom + 1], T[:fcfrom + 1], color=WARM, lw=2.4, label=str(today.year))
            ax.plot(x[fcfrom:], T[fcfrom:], color=WARM, lw=2.4, ls=(0, (4, 3)), label=f"{today.year} · {X['fcz']}")
            if HN: ax.plot(x, [np.nanmean(NT[I]) for I in idx], color=NORM, lw=1.4, ls=(0, (1, 2)), label=f"{X['norm']} 1991–2020")
            ax.set_title(X['tt'], loc='left', fontsize=12, color=INK, fontweight='bold'); ax.legend(frameon=False, fontsize=9, ncol=4, loc='upper left')
            bx.bar(x - 0.2, Q, 0.38, color='#c7cfd8', label=str(today.year - 1)); bx.bar(x + 0.2, Pp, 0.38, color=[RAIN if j < fcfrom else '#9cc1ec' for j in range(len(x))], label=str(today.year))
            if HN: bx.plot(x, [np.nansum(NPR[I]) for I in idx], color=NORM, lw=1.4, ls=(0, (1, 2)), label=X['norm'])
            bx.set_title(X['pt'], loc='left', fontsize=12, color=INK, fontweight='bold'); bx.legend(frameon=False, fontsize=9, ncol=3, loc='upper left')
            pdf.savefig(f); plt.close(f)
        mons = list(range(y0 - dt.date(today.year, 1, 1).weekday(), last + 1, 7))
        W = [[j for j in range(m, m + 7) if y0 <= j <= last] for m in mons]
        chart(X['wk'], 2, W, [f"{(s + dt.timedelta(days=m)).day} {X['ms'][(s + dt.timedelta(days=m)).month - 1]}" for m in mons], next((k for k, I in enumerate(W) if max(I) >= ti), len(W)))
        D = [[j] for j in range(m0, last + 1) if (s + dt.timedelta(days=j)).month == today.month]
        chart(X['mon'].format(m=X['mn'][today.month - 1]), 3, D, [str((s + dt.timedelta(days=I[0])).day) for I in D], next((k for k, I in enumerate(D) if I[0] >= ti), len(D)))
        # 4. the regions
        f = page(X['reg'], 4); rows = []
        for p in P:
            tm, pr = nan(p['tm']), nan(p['pr']); a_ = st(tm, pr, B['mtd'], nan(p['norm']['tm']) if p.get('norm') else None); c_ = st(tm, pr, B['fc'])
            rows.append([p[lang], f1(a_['t']), sg(a_['t'] - a_['l']), sg(a_['t'] - a_['n']) if 'n' in a_ else '—', round(a_['a']), round(a_['b']), sg(c_['t'] - c_['l'])])
        ax = f.add_axes([0.03, 0.06, 0.94, 0.82]); ax.axis('off')
        tb = ax.table(cellText=rows, colLabels=X['cols'], loc='upper center', cellLoc='center', colLoc='center', colWidths=[0.25] + [0.125] * 6); tb.auto_set_font_size(False); tb.set_fontsize(10.5); tb.scale(1, 1.55)
        for (r, c), cell in tb.get_celld().items():
            cell.set_edgecolor(LINE)
            if r == 0: cell.set_facecolor(NAVY); cell.get_text().set_color('#fff'); cell.get_text().set_fontweight('bold')
            elif c in (2, 3, 6):
                t_ = cell.get_text().get_text(); cell.set_facecolor('#fde8dd' if t_.startswith('+') else '#e1ebfa' if t_.startswith('−') else '#fff')
            if c == 0 and r > 0: cell.get_text().set_ha('left'); cell._loc = 'left'
        pdf.savefig(f); plt.close(f)
        # 5. the business indicators (this month + the forecast, against last year)
        f = page(X['ind'], 5)
        ind = [lambda p, I: sum(1 for i in I if (s + dt.timedelta(days=i)).weekday() >= 5 and (p['pr'][i] or 0) >= 1), lambda p, I: sum(1 for i in I if (p['tx'][i] or -99) >= 35),
               lambda p, I: sum(1 for i in I if (p['tn'][i] if p['tn'][i] is not None else 99) <= -5), lambda p, I: sum(1 for i in I if (p['sn'][i] or 0) >= 0.5),
               lambda p, I: sum(1 for i in I if p.get('gu') and (p['gu'][i] or 0) >= 15)]
        I = [i for i in range(m0, last + 1) if (s + dt.timedelta(days=i)).month == today.month]; L = [i - 364 for i in I]
        rows = [[p[lang]] + [f"{fn(p, I)} / {fn(p, L)}" for fn in ind] for p in P]
        f.text(0.03, 0.87, f"{X['mn'][today.month - 1]} ({X['mtd'].lower()} + {X['fcz']}) · {X['this']}", fontsize=12, color=MUTED)
        ax = f.add_axes([0.03, 0.06, 0.94, 0.78]); ax.axis('off')
        tb = ax.table(cellText=rows, colLabels=X['icol'], loc='upper center', cellLoc='center', colWidths=[0.25] + [0.15] * 5); tb.auto_set_font_size(False); tb.set_fontsize(10.5); tb.scale(1, 1.55)
        for (r, c), cell in tb.get_celld().items():
            cell.set_edgecolor(LINE)
            if r == 0: cell.set_facecolor(NAVY); cell.get_text().set_color('#fff'); cell.get_text().set_fontweight('bold')
        pdf.savefig(f); plt.close(f)
    print(out, out.stat().st_size // 1024, 'KB')


if __name__ == '__main__':
    for L in LANGS: build(L)
