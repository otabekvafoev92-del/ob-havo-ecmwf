"""Excel report "weather against last year" for the bot (business mode), made with the data of tools/lfl.py:
  Сводка — the 14 region centres: since 1 January, this month, last 7 days, the next 15 days (temperature Δ, precipitation, rainy days);
  Недели — week to week (LFL, Mon–Sun) for every region centre, the forecast weeks marked;
  Районы — all 199 districts: the last 8 weeks and the 2 forecast weeks against the same weekdays last year (Open-Meteo, fetched here);
  По дням — this month day by day for every region centre.
Usage: python tools/lfl_xlsx.py lfl/lfl.json out_{lang}.xlsx ru,uz"""
import json, sys, time, datetime as dt, pathlib
import numpy as np, requests
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.utils import get_column_letter

SRC, OUTP = sys.argv[1], sys.argv[2]; LANGS = (sys.argv[3] if len(sys.argv) > 3 else 'ru').split(','); LANG = LANGS[0]; OUT = None
HERE = pathlib.Path(__file__).resolve().parent.parent
TX = {'ru': dict(sum='Сводка', wk='Недели', ds='Районы', dd='По дням', reg='Регион', dist='Район', ytd='С 1 января', mtd='Этот месяц', l7='7 дней', fc='Прогноз 15 дней',
                 t='t° ср.', tl='t° год назад', d='Δ t°', p='Осадки, мм', pl='Осадки год назад, мм', pp='Δ осадков, %', rd='Дней с осадками', rdl='год назад',
                 week='Неделя с', kind='Тип', fact='факт', fcs='прогноз', mix='факт+прогноз', date='Дата', wd='День', lyd='Год назад (LFL)',
                 title='Погода против прошлого года (LFL: те же дни недели 364 дня назад)', made='Данные на {d}. Факт: ERA5 и анализ ECMWF, прогноз: ECMWF IFS (Open-Meteo). Модель, не метеостанции.',
                 wds=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']),
      'uz': dict(sum='Xulosa', wk='Haftalar', ds='Tumanlar', dd='Kunlar', reg='Viloyat', dist='Tuman', ytd='1 yanvardan', mtd='Shu oy', l7='7 kun', fc='15 kunlik prognoz',
                 t='o‘rt. t°', tl='o‘tgan yil t°', d='Δ t°', p='Yog‘in, mm', pl='O‘tgan yil yog‘in, mm', pp='Δ yog‘in, %', rd='Yog‘inli kunlar', rdl='o‘tgan yil',
                 week='Hafta', kind='Turi', fact='fakt', fcs='prognoz', mix='fakt+prognoz', date='Sana', wd='Kun', lyd='O‘tgan yil (LFL)',
                 title='Ob-havo o‘tgan yilga nisbatan (LFL: 364 kun oldingi shu hafta kunlari)', made='{d} holatiga. Fakt: ERA5 va ECMWF tahlili, prognoz: ECMWF IFS (Open-Meteo). Model, meteostansiya emas.',
                 wds=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'])}
X = TX[LANG]
_DS = {}
HEAD = Font(bold=True, color='FFFFFF'); HFILL = PatternFill('solid', fgColor='2B3A4E'); FCF = PatternFill('solid', fgColor='FFF4E8')
THIN = Border(bottom=Side(style='thin', color='DDE3EA'))


def nan(a): return np.array([np.nan if x is None else x for x in a], float)


def stats(tm, pr, I):
    I = [i for i in I if 0 <= i < len(tm) and i - 364 >= 0]
    t, l = np.nanmean(tm[I]) if I else np.nan, np.nanmean(tm[[i - 364 for i in I]]) if I else np.nan
    p, q = np.nansum(pr[I]), np.nansum(pr[[i - 364 for i in I]])
    return [round(t, 1), round(l, 1), round(t - l, 1), round(p, 1), round(q, 1), round((p - q) / q * 100) if q > 0.5 else None,
            int(np.sum(pr[I] >= 1)), int(np.sum(pr[[i - 364 for i in I]] >= 1))]


def header(ws, row, cols, widths=None):
    for j, c in enumerate(cols, 1):
        x = ws.cell(row=row, column=j, value=c); x.font = HEAD; x.fill = HFILL; x.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[row].height = 32
    for j, w in enumerate(widths or [], 1): ws.column_dimensions[get_column_letter(j)].width = w


def dscale(ws, rng):  # Δ t°: blue (colder) — white — orange (warmer)
    ws.conditional_formatting.add(rng, ColorScaleRule(start_type='num', start_value=-6, start_color='7FA8E0', mid_type='num', mid_value=0, mid_color='FFFFFF', end_type='num', end_value=6, end_color='EDA07A'))


def districts(start, today):
    """The 199 districts: daily mean temperature and precipitation for 8 weeks back + 2 ahead, and the same weekdays last year."""
    g = json.load(open(HERE / 'prob' / 'geo_admin.json'))['UZ']; A1 = g['adm1']; D = g['adm2']
    mon = today - dt.timedelta(days=today.weekday()); a = mon - dt.timedelta(weeks=8); b = mon + dt.timedelta(weeks=2) - dt.timedelta(days=1)
    out = []
    for k in range(0, len(D), 50):
        part = D[k:k + 50]
        q = dict(latitude=','.join(str(d['c'][1]) for d in part), longitude=','.join(str(d['c'][0]) for d in part), daily='temperature_2m_mean,precipitation_sum', timezone='Asia/Tashkent')
        def get(url, **p):
            for n in range(5):
                try: r = requests.get(url, params={**q, **p}, timeout=180)
                except requests.RequestException as e: print('retry', e, flush=True); time.sleep(30 * (n + 1)); continue
                if r.ok: j = r.json(); return j if isinstance(j, list) else [j]
                print('retry', r.status_code, r.text[:150], flush=True); time.sleep(30 * (n + 1))
            r.raise_for_status()
        ly = get('https://archive-api.open-meteo.com/v1/archive', start_date=(a - dt.timedelta(days=364)).isoformat(), end_date=(b - dt.timedelta(days=364)).isoformat())
        ar = get('https://archive-api.open-meteo.com/v1/archive', start_date=a.isoformat(), end_date=(today - dt.timedelta(days=2)).isoformat())
        fc = get('https://api.open-meteo.com/v1/forecast', past_days=14, forecast_days=16, models='ecmwf_ifs025')
        for d, L, R, F in zip(part, ly, ar, fc):
            n = (b - a).days + 1; t = np.full(n, np.nan); p = np.full(n, np.nan)
            for blk in (R, F):  # the archive, then the model where the archive has nothing yet
                for i, day in enumerate(blk['daily']['time']):
                    j = (dt.date.fromisoformat(day) - a).days
                    if 0 <= j < n and np.isnan(t[j]) and blk['daily']['temperature_2m_mean'][i] is not None:
                        t[j] = blk['daily']['temperature_2m_mean'][i]; p[j] = blk['daily']['precipitation_sum'][i] or 0
            lt, lp = nan(L['daily']['temperature_2m_mean'][:n]), nan(L['daily']['precipitation_sum'][:n])
            out.append((A1[d['p']]['name'], d['name'], t, p, lt, lp))
        time.sleep(2)
    return out, a


def main():
    d = json.load(open(SRC)); P = [p for p in d['places'] if p.get('iso', 'UZ') == 'UZ']
    s = dt.date.fromisoformat(d['start']); today = dt.date.fromisoformat(d['today']); ti = (today - s).days
    n = len(P[0]['tm']); last = max(i for i in range(n) if any(p['tm'][i] is not None for p in P))
    y0 = (dt.date(today.year, 1, 1) - s).days; m0 = (dt.date(today.year, today.month, 1) - s).days
    wb = Workbook(); ws = wb.active; ws.title = X['sum']
    ws['A1'] = X['title']; ws['A1'].font = Font(bold=True, size=14, color='2B3A4E'); ws['A2'] = X['made'].format(d=today.strftime('%d.%m.%Y')); ws['A2'].font = Font(italic=True, color='6B7A8C')
    blocks = [(X['ytd'], range(y0, ti)), (X['mtd'], range(m0, ti)), (X['l7'], range(ti - 7, ti)), (X['fc'], range(ti, last + 1))]
    cols = [X['reg']] + [f"{b}\n{c}" for b, _ in blocks for c in (X['t'], X['tl'], X['d'], X['p'], X['pl'], X['pp'])]
    header(ws, 4, cols, [26] + [9] * (len(cols) - 1))
    allp = [('Узбекистан' if LANG == 'ru' else 'O‘zbekiston', np.nanmean([nan(p['tm']) for p in P], 0), np.nanmean([nan(p['pr']) for p in P], 0))] + [(p[LANG], nan(p['tm']), nan(p['pr'])) for p in P]
    for r, (nm, tm, pr) in enumerate(allp, 5):
        ws.cell(row=r, column=1, value=nm).font = Font(bold=r == 5)
        c = 2
        for _, I in blocks:
            for v in stats(tm, pr, list(I))[:6]: ws.cell(row=r, column=c, value=v); c += 1
    for k in range(len(blocks)): dscale(ws, f"{get_column_letter(4 + 6 * k)}5:{get_column_letter(4 + 6 * k)}{4 + len(allp)}")
    ws.freeze_panes = 'B5'
    # weeks
    w2 = wb.create_sheet(X['wk']); mons = []
    i = y0 - dt.date(today.year, 1, 1).weekday()
    while i <= last: mons.append(i); i += 7
    header(w2, 1, [X['week'], X['kind']] + [f"{nm}\n{X['d']}" for nm, _, _ in allp] + [f"{nm}\n{X['p']}" for nm, _, _ in allp], [12, 12] + [11] * (2 * len(allp)))
    for r, m in enumerate(reversed(mons), 2):
        I = [i for i in range(m, m + 7) if y0 <= i <= last]
        kind = X['fcs'] if min(I) >= ti else X['mix'] if max(I) >= ti else X['fact']
        w2.cell(row=r, column=1, value=s + dt.timedelta(days=m)).number_format = 'DD.MM.YYYY'; w2.cell(row=r, column=2, value=kind)
        for j, (_, tm, pr) in enumerate(allp):
            st = stats(tm, pr, I); w2.cell(row=r, column=3 + j, value=st[2]); w2.cell(row=r, column=3 + len(allp) + j, value=st[3])
        if kind != X['fact']:
            for c in range(1, 3 + 2 * len(allp)): w2.cell(row=r, column=c).fill = FCF
    dscale(w2, f"C2:{get_column_letter(2 + len(allp))}{1 + len(mons)}"); w2.freeze_panes = 'C2'
    # districts
    try:
        if 'v' not in _DS: _DS['v'] = districts(s, today)  # fetched once for both languages
        DS, a = _DS['v']; DS = [(r_[LANG], n_[LANG], *rest) for r_, n_, *rest in DS]; w3 = wb.create_sheet(X['ds'])
        wk = [(a + dt.timedelta(weeks=k)) for k in range(10)]
        header(w3, 1, [X['reg'], X['dist']] + [f"{w.strftime('%d.%m')}\n{X['d']}" + (f"\n{X['fcs']}" if w + dt.timedelta(days=6) >= today else '') for w in wk] + [f"{w.strftime('%d.%m')}\n{X['p']}" for w in wk], [24, 24] + [10] * 20)
        for r, (rg, nm, t, p, lt, lp) in enumerate(sorted(DS, key=lambda x: (x[0], x[1])), 2):
            w3.cell(row=r, column=1, value=rg); w3.cell(row=r, column=2, value=nm)
            for k in range(10):
                sl = slice(7 * k, 7 * k + 7)
                dv = np.nanmean(t[sl]) - np.nanmean(lt[sl]); w3.cell(row=r, column=3 + k, value=None if np.isnan(dv) else round(float(dv), 1))
                pv = np.nansum(p[sl]); w3.cell(row=r, column=13 + k, value=round(float(pv), 1))
        dscale(w3, f"C2:L{1 + len(DS)}"); w3.freeze_panes = 'C2'; w3.auto_filter.ref = f"A1:V{1 + len(DS)}"
    except Exception as e: print('districts failed', e, flush=True)
    # this month by days
    w4 = wb.create_sheet(X['dd'])
    header(w4, 1, [X['date'], X['wd'], X['lyd'], X['reg'], X['t'], X['tl'], X['d'], X['p'], X['pl'], X['kind']], [12, 6, 14, 26, 9, 11, 8, 10, 12, 10])
    r = 2
    for i in range(m0, last + 1):
        dd = s + dt.timedelta(days=i)
        if dd.month != today.month: break
        for nm, tm, pr in allp:
            vals = [dd, X['wds'][dd.weekday()], s + dt.timedelta(days=i - 364), nm, round(float(tm[i]), 1), round(float(tm[i - 364]), 1), round(float(tm[i] - tm[i - 364]), 1), round(float(pr[i]), 1), round(float(pr[i - 364]), 1), X['fcs'] if i >= ti else X['fact']]
            for c, v in enumerate(vals, 1):
                x = w4.cell(row=r, column=c, value=v)
                if c in (1, 3): x.number_format = 'DD.MM.YYYY'
                if i >= ti: x.fill = FCF
            r += 1
    dscale(w4, f"G2:G{r}"); w4.freeze_panes = 'A2'; w4.auto_filter.ref = f"A1:J{r - 1}"
    wb.save(OUT); print(OUT, OUT.stat().st_size // 1024, 'KB')


if __name__ == '__main__':
    for LANG in LANGS:
        X = TX[LANG]; OUT = pathlib.Path(OUTP.replace('{lang}', LANG)); main()
