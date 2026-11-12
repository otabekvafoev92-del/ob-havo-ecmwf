"""Video: the weather of Uzbekistan by weeks against last year (LFL: the same weekdays 364 days back), with the forecast weeks.
From lfl.json (tools/lfl.py): the mean of the region centres, or one place. Three scenes (title, the weeks drawn one by one, the summary),
each encoded on its own, then joined. Usage: python tools/lfl_video.py lfl.json out.mp4 [ru|uz] [place id]"""
import json, sys, subprocess, pathlib, os, datetime as dt
import numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

SRC, OUT = sys.argv[1], pathlib.Path(sys.argv[2]); LANG = sys.argv[3] if len(sys.argv) > 3 else 'ru'; MODE = sys.argv[4] if len(sys.argv) > 4 else 'weeks'
ONE = sys.argv[5] if len(sys.argv) > 5 else None  # weeks: since 1 January by weeks; month: this month day by day
W, H, FPS = 1920, 1080, 30
NAVY, INK, MUTED, LINE, WARM, COLD, RAIN, LY, PAPER = '#2b3a4e', '#2b3a4e', '#6b7a8c', '#dde3ea', '#e0643a', '#2f6fd0', '#3b82d6', '#9aa6b4', '#f3f5f7'
for f in ('GolosText', 'Golos Text', 'DejaVu Sans'):
    if any(f.replace(' ', '').lower() in x.lower().replace(' ', '') for x in fm.findSystemFonts()): plt.rcParams['font.family'] = f; break
TX = {'ru': dict(t='Погода по неделям против прошлого года', uz_all='Узбекистан · среднее по 14 центрам регионов', lfl='LFL: те же дни недели год назад',
                 tt='Средняя температура за неделю, °C', pt='Осадки за неделю, мм', fc='прогноз', now='сейчас', wk='Неделя', ty='{y}', d='разница',
                 mon=['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'], part='{n} дн.', mix='факт + прогноз',
                 warmer='теплее', colder='холоднее', sum='Итоги', src='Данные: ERA5 (ECMWF / Copernicus) и прогноз ECMWF IFS через Open-Meteo · модель, не метеостанции',
                 s_ytd='С начала года: {t}° в среднем — на {d}° {w} прошлого года', s_pr='Осадков {a} мм против {b} мм ({p})',
                 s_wk='Теплее прошлого года было {k} недель из {n}', s_l4='Последние 4 недели: {d}° к прошлому году, осадков {a} против {b} мм',
                 s_fc='Прогноз на {n} нед.: в среднем {t}° — на {d}° {w}, чем год назад', s_hi='Самая тёплая к прошлому году — неделя с {a} ({da}°)', s_lo='Самая холодная к прошлому году — неделя с {b} ({db}°)',
                 tm='{m}: погода по дням против прошлого года', ttd='Средняя температура за день, °C', ptd='Осадки за день, мм', day='День', since='С 1 {m}',
                 m_mtd='С 1 по {d} {m}: {t}° в среднем — на {x}° {w} прошлого года', m_pr='Осадков {a} мм против {b} мм, дней с осадками {k} против {j}',
                 m_fc='Прогноз до {d} {m}: в среднем {t}° — на {x}° {w}, осадков {a} мм против {b} мм', m_tot='Весь месяц (факт + прогноз): {t}° против {l}°, осадков {a} мм против {b} мм',
                 m_hi='Самый тёплый к прошлому году день — {a} ({da}°)', m_lo='Самый холодный — {b} ({db}°)', wd=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
                 mg=['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
                 mn=['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']),
      'uz': dict(t='Ob-havo haftalar bo‘yicha o‘tgan yilga nisbatan', uz_all='O‘zbekiston · 14 viloyat markazi o‘rtachasi', lfl='LFL: o‘tgan yilning shu hafta kunlari',
                 tt='Haftalik o‘rtacha harorat, °C', pt='Haftalik yog‘in, mm', fc='prognoz', now='hozir', wk='Hafta', ty='{y}', d='farq',
                 mon=['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'], part='{n} kun', mix='fakt + prognoz',
                 warmer='iliqroq', colder='sovuqroq', sum='Xulosa', src='Ma’lumot: ERA5 (ECMWF / Copernicus) va ECMWF IFS prognozi, Open-Meteo orqali · model, meteostansiya emas',
                 s_ytd='Yil boshidan: o‘rtacha {t}° — o‘tgan yildan {d}° {w}', s_pr='Yog‘in {a} mm, o‘tgan yil {b} mm ({p})',
                 s_wk='{n} haftadan {k} tasi o‘tgan yildan iliqroq', s_l4='So‘nggi 4 hafta: o‘tgan yilga {d}°, yog‘in {a} / {b} mm',
                 s_fc='{n} haftalik prognoz: o‘rtacha {t}° — o‘tgan yildan {d}° {w}', s_hi='Eng iliq hafta — {a} ({da}°)', s_lo='Eng sovuq hafta — {b} ({db}°)',
                 tm='{m}: ob-havo kunlar bo‘yicha o‘tgan yilga nisbatan', ttd='Kunlik o‘rtacha harorat, °C', ptd='Kunlik yog‘in, mm', day='Kun', since='1 {m}dan',
                 m_mtd='1–{d} {m}: o‘rtacha {t}° — o‘tgan yildan {x}° {w}', m_pr='Yog‘in {a} mm, o‘tgan yil {b} mm; yog‘inli kunlar {k} / {j}',
                 m_fc='{d} {m}gacha prognoz: o‘rtacha {t}° — {x}° {w}, yog‘in {a} / {b} mm', m_tot='Butun oy (fakt + prognoz): {t}° / {l}°, yog‘in {a} / {b} mm',
                 m_hi='Eng iliq kun — {a} ({da}°)', m_lo='Eng sovuq kun — {b} ({db}°)', wd=['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'],
                 mg=['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'],
                 mn=['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr'])}
X = TX[LANG]
f1 = lambda x: f'{x:.1f}'.replace('.', ',') if LANG == 'ru' else f'{x:.1f}'
sg = lambda x: ('+' if x > 0.05 else '−' if x < -0.05 else '±') + f1(abs(x))


def weeks():
    d = json.load(open(SRC)); P = [p for p in d['places'] if p.get('iso', 'UZ') == 'UZ' and (ONE is None or p['id'] == ONE)]
    s = dt.date.fromisoformat(d['start']); today = dt.date.fromisoformat(d['today']); ti = (today - s).days
    A = lambda k: np.nanmean(np.array([[np.nan if x is None else x for x in p[k]] for p in P], float), 0)
    tm, pr = A('tm'), A('pr'); n = len(tm); last = max(i for i in range(n) if not np.isnan(tm[i]))
    out = []
    if MODE == 'month':
        m1 = (dt.date(today.year, today.month, 1) - s).days
        for i in range(m1, last + 1):
            if (s + dt.timedelta(i)).month != today.month: break
            out.append(dict(mon=s + dt.timedelta(i), t=float(tm[i]), l=float(tm[i - 364]), p=float(pr[i]), q=float(pr[i - 364]), kind='fc' if i >= ti else 'fact', n=1))
        return out, today, (X['uz_all'] if ONE is None else P[0][LANG])
    y0 = (dt.date(today.year, 1, 1) - s).days; m0 = y0 - dt.date(today.year, 1, 1).weekday()
    for m in range(m0, last + 1, 7):
        I = [i for i in range(m, m + 7) if y0 <= i <= last]
        if not I: continue
        L = [i - 364 for i in I]
        out.append(dict(mon=s + dt.timedelta(m), t=float(np.nanmean(tm[I])), l=float(np.nanmean(tm[L])), p=float(np.nansum(pr[I])), q=float(np.nansum(pr[L])),
                        kind='fc' if min(I) >= ti else 'mix' if max(I) >= ti else 'fact', n=len(I)))
    name = X['uz_all'] if ONE is None else P[0][LANG]
    return out, today, name


WK, TODAY, NAME = weeks(); YR = TODAY.year
M = MODE == 'month'; TITLE = X['tm'].format(m=X['mn'][TODAY.month - 1]) if M else X['t']
lab = lambda d: f"{d.day} {X['mon'][d.month - 1]}"
dlab = lambda d: f"{X['wd'][d.weekday()]} {d.day} {X['mon'][d.month - 1]}"


def summary():
    F = [w for w in WK if w['kind'] == 'fact']; C = [w for w in WK if w['kind'] != 'fact']
    t = np.mean([w['t'] for w in F]); l = np.mean([w['l'] for w in F]); a = sum(w['p'] for w in F); b = sum(w['q'] for w in F)
    ww = lambda x: X['warmer'] if x > 0.05 else X['colder']
    out = [X['s_ytd'].format(t=f1(t), d=f1(abs(t - l)), w=ww(t - l)), X['s_pr'].format(a=round(a), b=round(b), p=(sg((a - b) / b * 100)[:-2] if b else '—') + '%'),
           X['s_wk'].format(k=sum(w['t'] > w['l'] for w in F), n=len(F))]
    L4 = F[-4:]; out.append(X['s_l4'].format(d=sg(np.mean([w['t'] - w['l'] for w in L4])), a=round(sum(w['p'] for w in L4)), b=round(sum(w['q'] for w in L4))))
    if C:
        tc, lc = np.mean([w['t'] for w in C]), np.mean([w['l'] for w in C]); out.append(X['s_fc'].format(n=len(C), t=f1(tc), d=f1(abs(tc - lc)), w=ww(tc - lc)))
    hi = max(F, key=lambda w: w['t'] - w['l']); lo = min(F, key=lambda w: w['t'] - w['l'])
    out.append(X['s_hi'].format(a=lab(hi['mon']), da=sg(hi['t'] - hi['l']))); out.append(X['s_lo'].format(b=lab(lo['mon']), db=sg(lo['t'] - lo['l'])))
    return out


def summary_month():
    F = [w for w in WK if w['kind'] == 'fact']; C = [w for w in WK if w['kind'] != 'fact']; mg = X['mg'][TODAY.month - 1]
    ww = lambda x: X['warmer'] if x > 0.05 else X['colder']; out = []
    if F:
        t, l = np.mean([w['t'] for w in F]), np.mean([w['l'] for w in F])
        out.append(X['m_mtd'].format(d=F[-1]['mon'].day, m=mg, t=f1(t), x=f1(abs(t - l)), w=ww(t - l)))
        out.append(X['m_pr'].format(a=round(sum(w['p'] for w in F)), b=round(sum(w['q'] for w in F)), k=sum(w['p'] >= 1 for w in F), j=sum(w['q'] >= 1 for w in F)))
    if C:
        t, l = np.mean([w['t'] for w in C]), np.mean([w['l'] for w in C])
        out.append(X['m_fc'].format(d=C[-1]['mon'].day, m=mg, t=f1(t), x=f1(abs(t - l)), w=ww(t - l), a=round(sum(w['p'] for w in C)), b=round(sum(w['q'] for w in C))))
    out.append(X['m_tot'].format(t=f1(np.mean([w['t'] for w in WK])), l=f1(np.mean([w['l'] for w in WK])), a=round(sum(w['p'] for w in WK)), b=round(sum(w['q'] for w in WK))))
    if F:
        hi = max(F, key=lambda w: w['t'] - w['l']); lo = min(F, key=lambda w: w['t'] - w['l'])
        out.append(X['m_hi'].format(a=dlab(hi['mon']), da=sg(hi['t'] - hi['l']))); out.append(X['m_lo'].format(b=dlab(lo['mon']), db=sg(lo['t'] - lo['l'])))
    return out


def fig():
    f = plt.figure(figsize=(W / 100, H / 100), dpi=100); f.patch.set_facecolor(PAPER); return f


def header(f, sub=None):
    f.patches.append(plt.Rectangle((0, 0.9), 1, 0.1, transform=f.transFigure, fc=NAVY, ec='none'))
    f.text(0.025, 0.955, TITLE, color='#fff', fontsize=30, fontweight='bold', va='center')
    f.text(0.025, 0.918, sub or f"{NAME} · {YR} / {YR - 1} · {X['lfl']}", color='#c9d3df', fontsize=17, va='center')


def raw(f):
    f.canvas.draw(); a = np.asarray(f.canvas.buffer_rgba())[..., :3].copy(); plt.close(f); return a


def encode(frames, name):
    tmp = OUT.parent / f'.{name}.part.mp4'
    p = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                          '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', str(tmp)], stdin=subprocess.PIPE)
    for a in frames: p.stdin.write(a.tobytes())
    p.stdin.close(); assert p.wait() == 0
    final = OUT.parent / f'{name}.mp4'; os.replace(tmp, final); return final


def still(a, sec):
    for _ in range(int(sec * FPS)): yield a


def title():
    f = fig(); header(f)
    f.text(0.5, 0.55, TITLE, ha='center', fontsize=50, fontweight='bold', color=INK)
    f.text(0.5, 0.45, f"{NAME}", ha='center', fontsize=30, color=MUTED)
    f.text(0.5, 0.38, f"{lab(WK[0]['mon']) if M else '1 ' + X['mon'][0]} — {lab(WK[-1]['mon'] + dt.timedelta(days=WK[-1]['n'] - 1))} {YR} · {X['lfl']}", ha='center', fontsize=24, color=MUTED)
    f.text(0.5, 0.06, X['src'], ha='center', fontsize=14, color=MUTED); return raw(f)


def chart(k):  # k: how many weeks are shown (fractional: the last one grows in)
    f = fig(); header(f)
    n = len(WK); x = np.arange(n); kk = int(np.ceil(k)); fr = k - np.floor(k)
    if fr == 0 or k >= n: fr = 1  # a whole number of weeks: the last one is complete
    ax = f.add_axes([0.05, 0.50, 0.66, 0.36]); bx = f.add_axes([0.05, 0.09, 0.66, 0.33])
    T = np.array([w['t'] for w in WK]); L = np.array([w['l'] for w in WK]); Pp = np.array([w['p'] for w in WK]); Q = np.array([w['q'] for w in WK])
    fc0 = next((i for i, w in enumerate(WK) if w['kind'] != 'fact'), n)
    for a in (ax, bx):
        a.set_facecolor('#fff'); a.set_xlim(-0.6, n - 0.4)
        for s_ in ('top', 'right'): a.spines[s_].set_visible(False)
        for s_ in ('left', 'bottom'): a.spines[s_].set_color(LINE)
        a.tick_params(colors=MUTED, labelsize=13); a.grid(axis='y', color='#eef1f4'); a.set_axisbelow(True)
        if fc0 < n: a.axvspan(fc0 - 0.5, n - 0.4, color='#fff4e8', zorder=0)
        if M:
            ticks = [i for i, w in enumerate(WK) if w['mon'].day % 5 == 1 or w['mon'].day == 1]
            a.set_xticks(ticks); a.set_xticklabels([str(WK[i]['mon'].day) for i in ticks])
        else:
            ticks = [i for i, w in enumerate(WK) if w['mon'].day <= 7]
            a.set_xticks(ticks); a.set_xticklabels([X['mon'][WK[i]['mon'].month - 1] if WK[i]['mon'].year == YR else '' for i in ticks])
    lo, hi = min(T.min(), L.min()) - 2, max(T.max(), L.max()) + 3; ax.set_ylim(lo, hi); ax.set_title(X['ttd' if M else 'tt'], loc='left', fontsize=18, color=INK, fontweight='bold', pad=10)
    bx.set_ylim(0, max(Pp.max(), Q.max()) * 1.18 + 1); bx.set_title(X['ptd' if M else 'pt'], loc='left', fontsize=18, color=INK, fontweight='bold', pad=10)
    if fc0 < n:
        ax.text(fc0 - 0.3, hi - 0.6, X['fc'], color='#c0562b', fontsize=15, fontweight='bold', va='top')
    # last year: the whole line faint from the start (the reference), this year drawn week by week
    ax.plot(x, L, color=LY, lw=2.4, zorder=2)
    if kk >= 1:
        xs = list(x[:kk]); ys = list(T[:kk])
        if fr < 1 and kk >= 2: xs[-1] = x[kk - 2] + fr; ys[-1] = T[kk - 2] + (T[kk - 1] - T[kk - 2]) * fr
        xs, ys = np.array(xs), np.array(ys); Lc = np.interp(xs, x, L)
        ax.fill_between(xs, ys, Lc, where=ys >= Lc, color=WARM, alpha=0.18, interpolate=True, zorder=1)
        ax.fill_between(xs, ys, Lc, where=ys < Lc, color=COLD, alpha=0.18, interpolate=True, zorder=1)
        fact = xs <= fc0 - 0.999 if fc0 < n else np.ones_like(xs, bool)
        ax.plot(xs[: max(1, fact.sum())], ys[: max(1, fact.sum())], color=WARM, lw=3.4, zorder=3)
        if (~fact).any(): ax.plot(xs[max(0, fact.sum() - 1):], ys[max(0, fact.sum() - 1):], color=WARM, lw=3.4, ls=(0, (4, 3)), zorder=3)
        ax.plot(xs[-1], ys[-1], 'o', ms=11, color=WARM, mec='#fff', mew=2.5, zorder=4)
        g = np.clip(np.arange(kk) - (k - 1), 0, 1)  # the newest bar grows
        hgt = np.ones(kk); hgt[-1] = fr
        bx.bar(x[:kk] - 0.2, Q[:kk] * 1.0, 0.38, color='#c7cfd8', zorder=2)
        bx.bar(x[:kk] + 0.2, Pp[:kk] * hgt, 0.38, color=[RAIN if WK[i]['kind'] == 'fact' else '#9cc1ec' for i in range(kk)], zorder=3)
    # legend
    for i, (c, t_, ls) in enumerate([(WARM, str(YR), '-'), (WARM, f"{YR} · {X['fc']}", (0, (4, 3))), (LY, str(YR - 1), '-')]):
        ax.plot([], [], color=c, lw=3, ls=ls, label=t_)
    ax.legend(loc='upper left', frameon=False, fontsize=14, ncol=3, labelcolor=INK)
    from matplotlib.patches import Patch
    bx.legend(handles=[Patch(color=RAIN, label=str(YR)), Patch(color='#9cc1ec', label=f"{YR} · {X['fc']}"), Patch(color='#c7cfd8', label=str(YR - 1))], loc='upper left', frameon=False, fontsize=14, ncol=3, labelcolor=INK)
    # the side card: the current week
    i = max(0, min(n - 1, kk - 1)); w = WK[i]
    f.patches.append(plt.Rectangle((0.745, 0.09), 0.23, 0.77, transform=f.transFigure, fc='#fff', ec=LINE, lw=1.2))
    end = w['mon'] + dt.timedelta(days=6)
    kind = {'fact': '', 'mix': X['mix'], 'fc': X['fc']}[w['kind']] + (f" · {X['part'].format(n=w['n'])}" if w['n'] < 7 and not M else '')
    if M:
        f.text(0.76, 0.82, X['day'], fontsize=17, color=MUTED); f.text(0.76, 0.775, dlab(w['mon']), fontsize=26, fontweight='bold', color=INK)
        if not kind: kind = f"↔ {dlab(w['mon'] - dt.timedelta(days=364))} {YR - 1}"; f.text(0.76, 0.74, kind, fontsize=15, color=MUTED); kind = ''
    else:
        f.text(0.76, 0.82, X['wk'], fontsize=17, color=MUTED); f.text(0.76, 0.775, f"{lab(w['mon'])} — {lab(end)}", fontsize=24, fontweight='bold', color=INK)
    if kind: f.text(0.76, 0.74, kind, fontsize=15, color='#c0562b', fontweight='bold')
    dtv = w['t'] - w['l']
    f.text(0.76, 0.66, f"{f1(w['t'])}°", fontsize=58, fontweight='bold', color=INK)
    f.text(0.76, 0.615, f"{YR - 1}: {f1(w['l'])}°", fontsize=18, color=MUTED)
    f.text(0.76, 0.545, f"{sg(dtv)}°", fontsize=40, fontweight='bold', color=WARM if dtv > 0.05 else COLD if dtv < -0.05 else MUTED)
    f.text(0.76, 0.51, X['warmer'] if dtv > 0.05 else X['colder'] if dtv < -0.05 else '', fontsize=17, color=MUTED)
    f.text(0.76, 0.40, f"{round(w['p']) if w['p'] >= 1 else f1(w['p'])} мм" if LANG == 'ru' else f"{round(w['p']) if w['p'] >= 1 else f1(w['p'])} mm", fontsize=44, fontweight='bold', color=RAIN)
    f.text(0.76, 0.36, f"{YR - 1}: {f1(w['q'])} {'мм' if LANG == 'ru' else 'mm'}", fontsize=18, color=MUTED)
    # running totals since 1 January
    F = WK[:kk]; tt = np.mean([v['t'] for v in F]) if F else 0; ll = np.mean([v['l'] for v in F]) if F else 0
    f.text(0.76, 0.25, X['since'].format(m=X['mg'][TODAY.month - 1]) if M else ('С 1 января' if LANG == 'ru' else '1 yanvardan'), fontsize=16, color=MUTED)
    f.text(0.76, 0.20, f"{f1(tt)}° ({sg(tt - ll)}°)", fontsize=24, fontweight='bold', color=INK)
    f.text(0.76, 0.155, f"{round(sum(v['p'] for v in F))} / {round(sum(v['q'] for v in F))} {'мм' if LANG == 'ru' else 'mm'}", fontsize=22, fontweight='bold', color=RAIN)
    f.text(0.025, 0.03, X['src'], fontsize=12, color=MUTED)
    return raw(f)


def summary_card():
    f = fig(); header(f)
    f.text(0.06, 0.80, X['sum'], fontsize=40, fontweight='bold', color=INK)
    for i, s in enumerate(summary_month() if M else summary()):
        f.text(0.07, 0.69 - i * 0.1, '•', fontsize=30, color=WARM, va='center'); f.text(0.095, 0.69 - i * 0.1, s, fontsize=27, color=INK, va='center')
    f.text(0.025, 0.03, X['src'], fontsize=12, color=MUTED); return raw(f)


if __name__ == '__main__':
    OUT.parent.mkdir(parents=True, exist_ok=True); n = len(WK)
    parts = [encode(still(title(), 2.5), 's1')]
    per = 9 if not M else 12  # frames a week (or a day of the month)
    parts.append(encode((chart(min(n, (j + 1) / per)) for j in range(n * per)), 's2'))
    parts.append(encode(still(chart(n), 2.5), 's3'))
    parts.append(encode(still(summary_card(), 7), 's4'))
    lst = OUT.parent / 'parts.txt'; lst.write_text(''.join(f"file '{p.name}'\n" for p in parts))
    tmp = OUT.with_name('.' + OUT.stem + '.part.mp4')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', '-movflags', '+faststart', str(tmp)], check=True)
    os.replace(tmp, OUT)
    for p in parts: p.unlink()
    lst.unlink(); print(OUT, OUT.stat().st_size // 1024, 'KB')
