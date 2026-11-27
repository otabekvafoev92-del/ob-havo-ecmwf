"""Eight more videos for the bot and the channel @osmon_obhavo, in the Osmon look (navy header with the logo, the Bot/Kanal signature):
  pass    — the mountain roads (Qamchiq, Taxtaqoracha, Chimyon road): snow, ice, fog, wind hour by hour for 3 days
  frost   — the frost at night for 7 days (orchards, fields, greenhouses)
  dust    — the wind as streams and the dust (CAMS) for 3 days
  models  — how 10 of the world's models see Tashkent for 7 days (temperature lines, rain per model)
  short   — tomorrow in the 14 provinces, vertical 9:16 for stories / Reels / Shorts
  week    — the past 7 days: rain fallen, the warmest and the coldest town (Sundays)
  snow    — the snow in the mountains, a week ago and now (VIIRS true colour), and the snow depth forecast for the resorts
  sky     — the night sky: where it is clear tonight, sunset, sunrise, the moon
Data: Open-Meteo (forecast, multi-model, air quality: CAMS dust), NASA GIBS (VIIRS).
Usage: python tools/extra_videos.py out uz,ru [names]  →  out/<name>_<lang>.mp4 and out/meta.json"""
import io, sys, json, math, pathlib, shutil, subprocess, tempfile, time, datetime as dt, traceback
import numpy as np, requests
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle, FancyBboxPatch, Circle

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'prob'))
import prob15_video as PV  # noqa: E402  (towns, QR codes)
from brand import brand, mark  # noqa: E402

W, H, DPI = 1920, 1080, 100
NAVY, AMBER, INK, MUTED, FAINT, BG = '#0B2545', '#FFB020', '#15202b', '#5b6876', '#98a3ae', '#F3F6FA'
SIGN = 'Bot - @ObHavo_ECMWF_bot · Kanal - @osmon_obhavo'
OM = 'https://api.open-meteo.com/v1/forecast'; AQ = 'https://air-quality-api.open-meteo.com/v1/air-quality'
TZ = 'Asia/Tashkent'
BOX = (55.5, 73.6, 36.9, 45.9)  # Uzbekistan and around: lon0, lon1, lat0, lat1
COSL = math.cos(math.radians(41.4))
PROV = [('Toshkent', 'Ташкент', 41.311, 69.279), ('Toshkent vil.', 'Ташкентская обл.', 41.0, 69.36), ('Andijon', 'Андижан', 40.783, 72.344),
        ('Farg‘ona', 'Фергана', 40.384, 71.784), ('Qo‘qon', 'Коканд', 40.528, 70.943), ('Namangan', 'Наманган', 40.998, 71.673), ('Sirdaryo (Guliston)', 'Сырдарья (Гулистан)', 40.49, 68.785),
        ('Jizzax', 'Джизак', 40.116, 67.842), ('Samarqand', 'Самарканд', 39.655, 66.976), ('Qashqadaryo', 'Кашкадарья', 38.861, 65.79),
        ('Surxondaryo', 'Сурхандарья', 37.224, 67.278), ('Buxoro', 'Бухара', 39.768, 64.421), ('Navoiy', 'Навои', 40.103, 65.374),
        ('Xorazm', 'Хорезм', 41.55, 60.631), ('Qoraqalpog‘iston', 'Каракалпакстан', 42.461, 59.611)]
PASSES = [('Qamchiq dovoni', 'Перевал Камчик', 41.07, 70.53, 'Toshkent — Farg‘ona', 'Ташкент — Фергана'),
          ('Taxtaqoracha dovoni', 'Перевал Тахтакарача', 39.28, 66.92, 'Samarqand — Shahrisabz', 'Самарканд — Шахрисабз'),
          ('Chimyon yo‘li', 'Дорога на Чимган', 41.53, 70.03, 'Chorvoq — Chimyon — Beldersoy', 'Чарвак — Чимган — Бельдерсай')]
RESORTS = [('Chimyon', 'Чимган', 41.56, 70.02), ('Amirsoy', 'Амирсой', 41.49, 70.08), ('Beldersoy', 'Бельдерсай', 41.6, 70.07)]
WD = {'uz': ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'], 'ru': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']}
T = {'uz': dict(
        pass_t='Tog‘ yo‘llari · 3 kun soatma-soat', pass_k=['qor', 'muz', 'tuman', 'shamol', 'xavfsiz'], pass_leg='Harorat (chiziq), qor va yomg‘ir (ustunlar), xavf (pastki tasma)',
        pass_n='Yo‘lga chiqishdan oldin ko‘ring', frost_t='Tungi sovuq · 7 kun', frost_leg='Tungi eng past harorat · ko‘k — sovuq (0° dan past): bog‘lar va issiqxonalar uchun xavf',
        dust_t='Shamol va chang · 3 kun', dust_leg='Oqimlar — shamol · jigarrang — havodagi chang (CAMS), µg/m³',
        models_t='Modellar bahslashmoqda · Toshkent, 7 kun', models_leg='Har bir chiziq — bitta jahon modeli: harorat °C', models_rain='7 kunda yog‘in, mm (har bir model)',
        short_t='Ertaga viloyatlarda', short_s='Ertangi ob-havo', week_t='Hafta yakuni · o‘tgan 7 kun', week_rain='7 kunda yog‘in, mm', week_hot='Eng issiq', week_cold='Eng sovuq',
        week_wet='Eng ko‘p yog‘in', snow_t='Tog‘lardagi qor · bir hafta oldin va hozir', snow_a='{d} atrofida', snow_depth='Qor qalinligi prognozi, sm',
        sky_t='Tungi osmon · bugun kechasi', sky_leg='Yashil — ochiq osmon (yulduzlar ko‘rinadi) · kulrang — bulutli', sky_sun='Quyosh botishi {a} · chiqishi {b} (Toshkent)',
        sky_moon='Oy: {p}', moon=['yangi oy', 'o‘sayotgan o‘roq', 'birinchi chorak', 'o‘sayotgan oy', 'to‘lin oy', 'kamayayotgan oy', 'oxirgi chorak', 'kamayayotgan o‘roq'],
        src='Open-Meteo: ECMWF, NOAA, DWD, UKMO va boshqalar', src_aq='CAMS (Copernicus) · Open-Meteo', src_snow='NASA GIBS · VIIRS · Open-Meteo', tz='Toshkent vaqti', mm='mm', cm='sm'),
     'ru': dict(
        pass_t='Горные дороги · 3 дня по часам', pass_k=['снег', 'гололёд', 'туман', 'ветер', 'спокойно'], pass_leg='Температура (линия), снег и дождь (столбики), опасность (полоса внизу)',
        pass_n='Посмотрите перед поездкой', frost_t='Заморозки · 7 ночей', frost_leg='Минимальная температура ночью · синее — мороз (ниже 0°): опасно для садов и теплиц',
        dust_t='Ветер и пыль · 3 дня', dust_leg='Потоки — ветер · коричневое — пыль в воздухе (CAMS), мкг/м³',
        models_t='Модели спорят · Ташкент, 7 дней', models_leg='Каждая линия — одна модель мира: температура °C', models_rain='Осадки за 7 дней, мм (по каждой модели)',
        short_t='Завтра по областям', short_s='Погода на завтра', week_t='Итоги недели · последние 7 дней', week_rain='Осадки за 7 дней, мм', week_hot='Самое тёплое', week_cold='Самое холодное',
        week_wet='Больше всего осадков', snow_t='Снег в горах · неделю назад и сейчас', snow_a='около {d}', snow_depth='Прогноз высоты снега, см',
        sky_t='Ночное небо · сегодня ночью', sky_leg='Зелёное — ясно (видны звёзды) · серое — облачно', sky_sun='Закат {a} · восход {b} (Ташкент)',
        sky_moon='Луна: {p}', moon=['новолуние', 'растущий серп', 'первая четверть', 'растущая луна', 'полнолуние', 'убывающая луна', 'последняя четверть', 'убывающий серп'],
        src='Open-Meteo: ECMWF, NOAA, DWD, UKMO и другие', src_aq='CAMS (Copernicus) · Open-Meteo', src_snow='NASA GIBS · VIIRS · Open-Meteo', tz='по Ташкенту', mm='мм', cm='см')}
MODELS = [('ecmwf_ifs025', 'ECMWF IFS'), ('ecmwf_aifs025_single', 'ECMWF AIFS'), ('gfs_global', 'NOAA GFS'), ('ncep_aigfs025', 'NOAA AIGFS'), ('icon_global', 'DWD ICON'),
          ('ukmo_global_deterministic_10km', 'UK Met Office'), ('gem_global', 'Canada GEM'), ('cma_grapes_global', 'China CMA'), ('jma_gsm', 'Japan JMA'), ('meteofrance_arpege_world', 'Météo-France')]
MCOL = ['#0B2545', '#1E63C6', '#d1495b', '#ee8434', '#2a9d8f', '#6a4c93', '#8d6e63', '#c9184a', '#3a86ff', '#5f0f40']


# ---------- data
_OM = {}


def om(url, params, tries=7):
    """Open-Meteo, once per request (the two languages share it); its free limit is per minute: on 429 wait a minute and go on."""
    key = url + json.dumps(params, sort_keys=True)
    if key in _OM: return _OM[key]
    for k in range(tries):
        try:
            r = requests.get(url, params=params, timeout=120)
            if r.ok: _OM[key] = r.json(); return _OM[key]
            print('om', r.status_code, r.text[:120], flush=True)
            if r.status_code == 429: time.sleep(62); continue
        except Exception as e: print('om', e, flush=True)
        time.sleep(3 * (k + 1))
    return None


def om_many(url, lats, lons, params, chunk=100):
    """Open-Meteo for many points at once (in chunks): a list of results in the order of the points."""
    out = []
    for i in range(0, len(lats), chunk):
        j = om(url, dict(params, latitude=','.join(f'{x:.2f}' for x in lats[i:i + chunk]), longitude=','.join(f'{x:.2f}' for x in lons[i:i + chunk]), timezone=TZ))
        if j is None: raise RuntimeError('open-meteo')
        out += j if isinstance(j, list) else [j]
    return out


GBOX = (50.5, 78.5, 36.0, 46.6)  # the data grid covers the whole drawn map (it is wider than Uzbekistan's box)


def grid(d=0.75):
    la = np.arange(GBOX[2], GBOX[3] + 1e-6, d); lo = np.arange(GBOX[0], GBOX[1] + 1e-6, d)
    LO, LA = np.meshgrid(lo, la); return la, lo, LA.ravel(), LO.ravel()


# ---------- drawing
CTX = {}


def borders():
    if 'b' not in CTX:
        G = json.load(open(ROOT / 'prob' / 'geo_casia.json'))['countries']; GA = json.load(open(ROOT / 'prob' / 'geo_admin.json'))['UZ']
        CTX['b'] = [([np.asarray(r) for k, c in G.items() if k != 'UZ' for r in c['rings']], (0.35, 0.42, 0.5, 0.6), 0.9, 6),
                    ([np.asarray(r) for a in GA['adm1'] for r in a['r']], (0.35, 0.42, 0.5, 0.45), 0.6, 6.05), ([np.asarray(r) for r in G['UZ']['rings']], NAVY, 2.0, 6.3)]
        CTX['uz'] = G['UZ']['rings']
    return CTX['b']


def frame(lang, title, sub='', w=W, h=H, bg=BG):
    fig = plt.figure(figsize=(w / DPI, h / DPI), dpi=DPI); fig.patch.set_facecolor(bg)
    hb = 104 / h
    fig.patches.append(Rectangle((0, 1 - hb), 1, hb, transform=fig.transFigure, fc=NAVY, ec='none', zorder=-1))
    mark(fig, 26 / w + 22 / w, 1 - hb / 2, 46, ink='#ffffff', rings=(20, 32, 44))
    fig.text(82 / w, 1 - hb / 2, 'osmon', fontsize=24, fontweight='bold', color='white', va='center')
    fig.text(230 / w, 1 - hb / 2, title, fontsize=24 if w > h else 22, fontweight='bold', color='white', va='center')
    if sub: fig.text(1 - 24 / w, 1 - hb / 2, sub, fontsize=18, color='#ffd29c', ha='right', va='center', fontweight='bold')
    return fig


def foot(fig, src, w=W, h=H):
    fig.text(24 / w, 18 / h, src, fontsize=12, color=MUTED, va='bottom')
    brand(fig, 1 - 24 / w, 18 / h, SIGN, fontsize=12, color=MUTED, ha='right', va='bottom', zorder=9)


def map_ax(fig, rect=(0.0, 0.11, 1.0, 0.79)):
    ax = fig.add_axes(rect); ax.set_facecolor('#e9eef4')
    lon0, lon1, la0, la1 = BOX; wpx = rect[2] * fig.bbox.width; hpx = rect[3] * fig.bbox.height
    span = (la1 - la0) / COSL * wpx / hpx; c = (lon0 + lon1) / 2
    ax.set_xlim(c - span / 2, c + span / 2); ax.set_ylim(la0, la1); ax.set_aspect(1 / COSL); ax.axis('off')
    for rings, col, lw, z in borders(): ax.add_collection(LineCollection(rings, colors=col, linewidths=lw, zorder=z))
    return ax


def towns(ax, lang, vals=None, fmt='{:+.0f}°', z=8):
    for k, tw in enumerate(PV.TOWNS):
        ax.plot(tw[3], tw[2], 'o', ms=6, mfc='white', mec=NAVY, mew=1.4, zorder=z)
        lab = tw[1 if lang == 'uz' else 0] + (f'  {fmt.format(vals[k])}'.replace('+0°', '0°').replace('-0°', '0°') if vals is not None and np.isfinite(vals[k]) else '')
        ax.annotate(lab, (tw[3], tw[2]), xytext=(9, 6), textcoords='offset pixels', fontsize=14, fontweight='bold', color=INK, zorder=z + 1,
                    bbox=dict(boxstyle='round,pad=0.25,rounding_size=0.6', fc='white', ec='none', alpha=0.78))


def save(fig, path):
    fig.savefig(path, dpi=DPI, facecolor=fig.get_facecolor()); plt.close(fig)


def encode(items, out, w=W, h=H):
    """items: [(png, seconds)]; a short crossfade between them; silent stereo track (Telegram plays it as a video, not a GIF)."""
    tmp = pathlib.Path(tempfile.mkdtemp()); n = 0; lst = []; prev = None
    for f, sec in items:
        im = np.asarray(Image.open(f).convert('RGB'), np.float32)
        if prev is not None and prev.shape == im.shape:
            for q in range(1, 8):
                a = q / 8; Image.fromarray(((1 - a) * prev + a * im).astype(np.uint8)).save(tmp / f'{n:04d}.jpg', quality=93); lst.append((n, 1 / 30)); n += 1
        Image.fromarray(im.astype(np.uint8)).save(tmp / f'{n:04d}.jpg', quality=93); lst.append((n, sec)); n += 1; prev = im
    (tmp / 'l.txt').write_text(''.join(f"file '{i:04d}.jpg'\nduration {d}\n" for i, d in lst) + f"file '{lst[-1][0]:04d}.jpg'\n")
    part = out.with_name('.' + out.name + '.part.mp4')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(tmp / 'l.txt'), '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-map', '0:v', '-map', '1:a',
                    '-vf', f'fps=30,scale={w}:{h},format=yuv420p', '-c:v', 'libx264', '-crf', '21', '-maxrate', '5000k', '-bufsize', '10000k', '-preset', 'medium',
                    '-c:a', 'aac', '-b:a', '48k', '-shortest', '-movflags', '+faststart', str(part)], check=True)
    part.replace(out); shutil.rmtree(tmp); print(out, out.stat().st_size // 1024, 'KB', flush=True)


def outro(lang, tmp, w=W, h=H):
    fig = plt.figure(figsize=(w / DPI, h / DPI), dpi=DPI); fig.patch.set_facecolor('white')
    mark(fig, 0.5 if w < h else 0.30, 0.80 if w < h else 0.70, 150, ink=NAVY, rings=(20, 32, 44))
    fig.text(0.5 if w < h else 0.30, 0.68 if w < h else 0.50, 'osmon', fontsize=54, fontweight='bold', color=NAVY, ha='center', va='center')
    fig.text(0.5 if w < h else 0.30, 0.63 if w < h else 0.42, 'OB-HAVO', fontsize=18, fontweight='bold', color=MUTED, ha='center', va='center')
    if w < h:
        PV.qr2(fig, x=0.12, y=0.30, h=0.17)
    else:
        PV.qr2(fig, x=0.56, y=0.36, h=0.36)
    p = tmp / f'outro_{lang}_{w}.png'; save(fig, p); return p


# ---------- 1. mountain roads
def v_pass(lang, tmp):
    X = T[lang]; js = om_many(OM, [p[2] for p in PASSES], [p[3] for p in PASSES], dict(
        hourly='temperature_2m,precipitation,snowfall,visibility,wind_gusts_10m,relative_humidity_2m', forecast_days=3, models='best_match'))
    items = []
    for p, j in zip(PASSES, js):
        hh = j['hourly']; t = [dt.datetime.fromisoformat(x) for x in hh['time']]; n = len(t)
        Tm = np.array(hh['temperature_2m'], float); pr = np.nan_to_num(np.array(hh['precipitation'], float)); sn = np.nan_to_num(np.array(hh['snowfall'], float))
        vis = np.nan_to_num(np.array(hh['visibility'], float), nan=20000); gu = np.nan_to_num(np.array(hh['wind_gusts_10m'], float)) / 3.6
        rh = np.nan_to_num(np.array(hh['relative_humidity_2m'], float))
        risk = np.full(n, 4)  # 0 snow, 1 ice, 2 fog, 3 wind, 4 calm (worst first)
        for i in range(n):
            if sn[i] >= 0.1: risk[i] = 0
            elif Tm[i] <= 0.5 and (pr[i] > 0 or rh[i] >= 95): risk[i] = 1
            elif vis[i] < 1000: risk[i] = 2
            elif gu[i] >= 15: risk[i] = 3
        RC = ['#5e60ce', '#00a6fb', '#9aa5b1', '#ee8434', '#52b788']
        for stage in (0.35, 0.7, 1.0):
            k = max(2, int(n * stage))
            fig = frame(lang, X['pass_t'], p[0] if lang == 'uz' else p[1])
            fig.text(0.03, 0.83, p[0] if lang == 'uz' else p[1], fontsize=40, fontweight='bold', color=INK)
            fig.text(0.03, 0.775, (p[4] if lang == 'uz' else p[5]) + f' · {X["pass_n"]}', fontsize=20, color=MUTED)
            ax = fig.add_axes([0.06, 0.25, 0.9, 0.46]); ax.set_xlim(0, n); ax.set_facecolor('white')
            lo, hi = np.nanmin(Tm) - 2, np.nanmax(Tm) + 2; ax.set_ylim(lo, hi); ax.axhline(0, color='#00a6fb', lw=1.2, ls='--', zorder=1)
            ax.plot(np.arange(k), Tm[:k], color='#e0601b', lw=3.5, zorder=4)
            b2 = ax.twinx(); b2.set_ylim(0, max(4, (pr.max() + 0.5) * 2.2)); b2.bar(np.arange(k) + 0.5, pr[:k], width=0.85, color=np.where(sn[:k] > 0, '#7b61ff', '#1E63C6'), alpha=0.8, zorder=3)
            b2.set_yticks([]); b2.spines[:].set_visible(False)
            for i in range(0, n, 24):
                ax.axvline(i, color='#dfe5ec', lw=1, zorder=0); ax.text(i + 12, hi - 0.4, f"{WD[lang][t[i].weekday()]} {t[i]:%d.%m}", ha='center', va='top', fontsize=16, fontweight='bold', color=MUTED)
            ax.set_xticks(range(0, n + 1, 6)); ax.set_xticklabels([f'{(i % 24):02d}' for i in range(0, n + 1, 6)], fontsize=12, color=MUTED)
            ax.tick_params(axis='y', labelsize=13, colors=MUTED); ax.spines[['top', 'right']].set_visible(False); ax.set_ylabel('°C', fontsize=14, color=MUTED)
            rb = fig.add_axes([0.06, 0.17, 0.9, 0.045]); rb.set_xlim(0, n); rb.set_ylim(0, 1); rb.axis('off')
            for i in range(k): rb.add_patch(Rectangle((i, 0), 1, 1, fc=RC[risk[i]], ec='none'))
            for c in range(5):
                fig.patches.append(Rectangle((0.06 + c * 0.13, 0.115), 0.016, 0.026, transform=fig.transFigure, fc=RC[c], ec='none'))
                fig.text(0.06 + c * 0.13 + 0.022, 0.128, X['pass_k'][c], fontsize=15, color=INK, va='center')
            fig.text(0.96, 0.128, X['pass_leg'], fontsize=12, color=MUTED, ha='right', va='center')
            foot(fig, X['src']); f = tmp / f'pass_{lang}_{p[2]}_{stage}.png'; save(fig, f); items.append((f, 0.8 if stage < 1 else 4.0))
    items.append((outro(lang, tmp), 3.0)); return items


# ---------- 2. frost
def v_frost(lang, tmp):
    X = T[lang]; la, lo, LA, LO = grid()
    js = om_many(OM, LA, LO, dict(daily='temperature_2m_min', forecast_days=7))
    days = js[0]['daily']['time']; M = np.array([[x if x is not None else np.nan for x in j['daily']['temperature_2m_min']] for j in js], float).reshape(len(la), len(lo), -1)
    tj = om_many(OM, [t[2] for t in PV.TOWNS], [t[3] for t in PV.TOWNS], dict(daily='temperature_2m_min', forecast_days=7))
    TV = np.array([[x if x is not None else np.nan for x in j['daily']['temperature_2m_min']] for j in tj], float)
    lev = [-30, -10, -6, -3, 0, 3, 6, 10, 30]; cols = ['#2b2d9b', '#3a5bd9', '#5b8def', '#9cc3ff', '#e9f5e1', '#fff3c4', '#ffd29c', '#f4a261']
    items = []
    for d in range(len(days)):
        dd = dt.date.fromisoformat(days[d]); fig = frame(lang, X['frost_t'], f"{WD[lang][dd.weekday()]} {dd:%d.%m}")
        ax = map_ax(fig); ax.contourf(lo, la, M[..., d], levels=lev, colors=cols, zorder=2, alpha=0.9)
        cs = ax.contour(lo, la, M[..., d], levels=[0], colors=['#1a237e'], linewidths=2.2, zorder=3)
        towns(ax, lang, TV[:, d]); fig.text(0.02, 0.085, X['frost_leg'], fontsize=15, color=INK)
        foot(fig, X['src']); f = tmp / f'frost_{lang}_{d}.png'; save(fig, f); items.append((f, 2.4))
    items.append((outro(lang, tmp), 3.0)); return items


# ---------- 3. wind and dust
def v_dust(lang, tmp):
    X = T[lang]; la, lo, LA, LO = grid(1.0)
    wj = om_many(OM, LA, LO, dict(hourly='wind_speed_10m,wind_direction_10m', forecast_days=3, wind_speed_unit='ms'))
    dj = om_many(AQ, LA, LO, dict(hourly='dust', forecast_days=3), chunk=100)
    times = wj[0]['hourly']['time']; idx = list(range(0, min(len(times), 72), 3))
    def arr(js, key): return np.array([[x if x is not None else np.nan for x in j['hourly'][key][:len(times)]] for j in js], float).reshape(len(la), len(lo), -1)
    S, D = arr(wj, 'wind_speed_10m'), arr(wj, 'wind_direction_10m')
    try: DU = arr(dj, 'dust')
    except Exception: DU = np.zeros_like(S)
    U = -S * np.sin(np.radians(D)); V = -S * np.cos(np.radians(D))
    items = []
    for i in idx:
        t = dt.datetime.fromisoformat(times[i]); fig = frame(lang, X['dust_t'], f"{WD[lang][t.weekday()]} {t:%d.%m} · {t:%H}:00")
        ax = map_ax(fig)
        du = np.nan_to_num(DU[..., i]); ax.contourf(lo, la, du, levels=[20, 50, 100, 200, 400, 800, 5000], colors=['#f6e7c1', '#efd08f', '#e0a85a', '#c7792e', '#9c4f19', '#6b3410'], alpha=0.75, zorder=2)
        wc = matplotlib.colors.LinearSegmentedColormap.from_list('w', ['#7aa6d6', '#1E63C6', '#0B2545', '#d1495b'])
        sp = ax.streamplot(lo, la, np.nan_to_num(U[..., i]), np.nan_to_num(V[..., i]), color=np.nan_to_num(S[..., i]), cmap=wc, norm=matplotlib.colors.Normalize(0, 16),
                           density=1.7, linewidth=1.8, arrowsize=1.4, zorder=4)
        towns(ax, lang); fig.text(0.02, 0.085, X['dust_leg'], fontsize=15, color=INK)
        foot(fig, X['src_aq']); f = tmp / f'dust_{lang}_{i}.png'; save(fig, f); items.append((f, 0.55))
    items[-1] = (items[-1][0], 2.5); items.append((outro(lang, tmp), 3.0)); return items


# ---------- 4. the models disagree
def v_models(lang, tmp):
    X = T[lang]; j = om(OM, dict(latitude=41.31, longitude=69.28, hourly='temperature_2m,precipitation', forecast_days=7, timezone=TZ, models=','.join(m for m, _ in MODELS)))
    hh = j['hourly']; t = [dt.datetime.fromisoformat(x) for x in hh['time']]; n = len(t)
    ser = []
    for (m, name), c in zip(MODELS, MCOL):
        a = np.array([x if x is not None else np.nan for x in hh.get(f'temperature_2m_{m}', [None] * n)], float)
        p = np.nansum(np.array([x if x is not None else np.nan for x in hh.get(f'precipitation_{m}', [None] * n)], float))
        if np.isfinite(a).sum() > 24: ser.append((name, c, a, p))
    items = []
    for stage in np.linspace(0.12, 1, 9):
        k = max(2, int(n * stage)); fig = frame(lang, X['models_t'], f'{len(ser)} model')
        ax = fig.add_axes([0.05, 0.2, 0.66, 0.66]); ax.set_facecolor('white'); ax.set_xlim(0, n)
        allv = np.concatenate([s[2] for s in ser]); ax.set_ylim(np.nanmin(allv) - 2, np.nanmax(allv) + 2)
        for name, c, a, p in ser: ax.plot(np.arange(k), a[:k], color=c, lw=2.4, alpha=0.9)
        for i in range(0, n, 24):
            ax.axvline(i, color='#dfe5ec', lw=1); ax.text(i + 12, ax.get_ylim()[1] - 0.3, f"{WD[lang][t[i].weekday()]} {t[i]:%d.%m}", ha='center', va='top', fontsize=14, fontweight='bold', color=MUTED)
        ax.set_xticks([]); ax.tick_params(labelsize=13, colors=MUTED); ax.spines[['top', 'right']].set_visible(False); ax.set_ylabel('°C', fontsize=14, color=MUTED)
        fig.text(0.05, 0.875, X['models_leg'], fontsize=17, color=INK)
        bx = fig.add_axes([0.76, 0.2, 0.21, 0.66]); bx.set_facecolor('white')
        names = [s[0] for s in ser]; ps = [s[3] * min(1, stage * 1.4) for s in ser]
        bx.barh(range(len(ser)), ps, color=[s[1] for s in ser]); bx.set_yticks(range(len(ser))); bx.set_yticklabels(names, fontsize=13); bx.invert_yaxis()
        bx.set_xlim(0, max(5, max(s[3] for s in ser) * 1.15)); bx.tick_params(axis='x', labelsize=12, colors=MUTED); bx.spines[['top', 'right']].set_visible(False)
        for yi, v in enumerate(ps): bx.text(v + 0.2, yi, f'{v:.0f}', va='center', fontsize=12, color=INK)
        fig.text(0.76, 0.875, X['models_rain'], fontsize=15, color=INK)
        foot(fig, X['src']); f = tmp / f'models_{lang}_{stage:.2f}.png'; save(fig, f); items.append((f, 0.5))
    items[-1] = (items[-1][0], 5.0); items.append((outro(lang, tmp), 3.0)); return items


# ---------- 5. vertical: tomorrow in the provinces
def wico(ax, x, y, code, s=1.0):
    """A small weather icon drawn with shapes (emoji fonts are not on the runners)."""
    sun = lambda: ax.add_patch(Circle((x + 0.25 * s, y + 0.2 * s), 0.28 * s, fc=AMBER, ec='none', zorder=5))
    cloud = lambda col='#9fb3c8': [ax.add_patch(Circle((x + dx * s, y + dy * s), r * s, fc=col, ec='none', zorder=6)) for dx, dy, r in ((-0.25, -0.05, 0.25), (0.05, 0.08, 0.32), (0.35, -0.05, 0.24))]
    if code is None: return
    if code <= 1: ax.add_patch(Circle((x, y), 0.36 * s, fc=AMBER, ec='none', zorder=5)); return
    if code <= 3: sun(); cloud(); return
    if code in (45, 48): cloud('#c3ccd6'); [ax.plot([x - 0.45 * s, x + 0.55 * s], [y - (0.35 + 0.12 * k) * s] * 2, color='#9fb3c8', lw=3, zorder=7) for k in range(2)]; return
    cloud('#7f93a8')
    snow = code in (71, 73, 75, 77, 85, 86)
    for k in range(3):
        xx = x + (-0.25 + 0.27 * k) * s
        if snow: ax.add_patch(Circle((xx, y - 0.45 * s), 0.07 * s, fc='#5e60ce', ec='none', zorder=7))
        else: ax.plot([xx, xx - 0.08 * s], [y - 0.32 * s, y - 0.55 * s], color='#1E63C6', lw=3, zorder=7)
    if code >= 95: ax.plot([x + 0.05 * s, x - 0.08 * s, x + 0.1 * s], [y - 0.25 * s, y - 0.45 * s, y - 0.6 * s], color=AMBER, lw=3, zorder=8)


def v_short(lang, tmp):
    X = T[lang]; w, h = 1080, 1920
    js = om_many(OM, [p[2] for p in PROV], [p[3] for p in PROV], dict(daily='weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max', forecast_days=2))
    tm = dt.date.fromisoformat(js[0]['daily']['time'][1]); items = []
    # the cover
    fig = frame(lang, X['short_s'], '', w, h, bg=NAVY)
    fig.text(0.5, 0.64, X['short_t'], fontsize=56, fontweight='bold', color='white', ha='center', va='center')
    fig.text(0.5, 0.56, f"{WD[lang][tm.weekday()]} · {tm:%d.%m.%Y}", fontsize=40, color=AMBER, ha='center', va='center', fontweight='bold')
    mark(fig, 0.5, 0.36, 260, ink='#ffffff', rings=(20, 32, 44)); brand(fig, 0.5, 0.06, SIGN, fontsize=18, color='#c9d8ec', ha='center', va='bottom')
    f = tmp / f'short_{lang}_0.png'; save(fig, f); items.append((f, 2.0))
    for part in range(3):  # 15 places, five a screen
        fig = frame(lang, X['short_t'], f"{tm:%d.%m}", w, h)
        ax = fig.add_axes([0.04, 0.07, 0.92, 0.84]); ax.set_xlim(0, 10); ax.set_ylim(0, 10 * 0.84 * h / (0.92 * w)); ax.axis('off')  # equal units: the icons stay round
        top = ax.get_ylim()[1]
        for r, k in enumerate(range(part * 5, min(len(PROV), part * 5 + 5))):
            p, j = PROV[k], js[k]['daily']; y = top - 1.6 - r * 3.0
            ax.add_patch(FancyBboxPatch((0.05, y - 1.25), 9.9, 2.5, boxstyle='round,pad=0,rounding_size=0.35', fc='white', ec='none', zorder=2))
            ax.text(0.4, y, p[0] if lang == 'uz' else p[1], fontsize=30, fontweight='bold', color=INK, va='center', zorder=3)
            wico(ax, 6.1, y + 0.1, j['weather_code'][1], 1.5)
            lo_, hi_ = j['temperature_2m_min'][1], j['temperature_2m_max'][1]
            ax.text(9.7, y + 0.3, f"{hi_:+.0f}°".replace('+0°', '0°'), fontsize=32, fontweight='bold', color='#e0601b', ha='right', va='center', zorder=3)
            ax.text(9.7, y - 0.5, f"{lo_:+.0f}°".replace('+0°', '0°'), fontsize=20, color=MUTED, ha='right', va='center', zorder=3)
            pp = j['precipitation_probability_max'][1]
            if pp is not None and pp >= 20: ax.text(7.3, y, f'{pp:.0f}%', fontsize=22, fontweight='bold', color='#1E63C6', va='center', zorder=3)
        brand(fig, 0.5, 0.025, SIGN, fontsize=16, color=MUTED, ha='center', va='bottom')
        f = tmp / f'short_{lang}_{part + 1}.png'; save(fig, f); items.append((f, 4.5))
    items.append((outro(lang, tmp, w, h), 3.0)); return items, (w, h)


# ---------- 6. the week behind
def v_week(lang, tmp):
    X = T[lang]; la, lo, LA, LO = grid()
    js = om_many(OM, LA, LO, dict(daily='precipitation_sum', past_days=7, forecast_days=1))
    R = np.array([np.nansum([x for x in j['daily']['precipitation_sum'][:7] if x is not None]) for j in js], float).reshape(len(la), len(lo))
    tj = om_many(OM, [t[2] for t in PV.TOWNS], [t[3] for t in PV.TOWNS], dict(daily='precipitation_sum,temperature_2m_max,temperature_2m_min', past_days=7, forecast_days=1))
    tr = [np.nansum([x for x in j['daily']['precipitation_sum'][:7] if x is not None]) for j in tj]
    tx = [np.nanmax([x for x in j['daily']['temperature_2m_max'][:7] if x is not None]) for j in tj]
    tn = [np.nanmin([x for x in j['daily']['temperature_2m_min'][:7] if x is not None]) for j in tj]
    d0 = dt.date.fromisoformat(tj[0]['daily']['time'][0]); d1 = dt.date.fromisoformat(tj[0]['daily']['time'][6]); sub = f"{d0:%d.%m} — {d1:%d.%m}"
    items = []
    fig = frame(lang, X['week_t'], sub); ax = map_ax(fig)
    ax.contourf(lo, la, R, levels=[1, 3, 6, 10, 20, 40, 80, 500], colors=['#d8ecff', '#a9d1ff', '#6fb1ff', '#3d8bf2', '#1f5fbf', '#123f8c', '#0b2545'], alpha=0.85, zorder=2)
    towns(ax, lang, np.array(tr), fmt='{:.0f} ' + X['mm']); fig.text(0.02, 0.085, X['week_rain'], fontsize=16, color=INK)
    foot(fig, X['src']); f = tmp / f'week_{lang}_0.png'; save(fig, f); items.append((f, 5.0))
    L = 1 if lang == 'uz' else 0
    fig = frame(lang, X['week_t'], sub)
    for k, (lab, i, v, col) in enumerate([(X['week_hot'], int(np.nanargmax(tx)), max(tx), '#e0601b'), (X['week_cold'], int(np.nanargmin(tn)), min(tn), '#3a5bd9'),
                                          (X['week_wet'], int(np.nanargmax(tr)), max(tr), '#1E63C6')]):
        x0 = 0.05 + k * 0.31
        fig.patches.append(FancyBboxPatch((x0, 0.25), 0.28, 0.5, boxstyle='round,pad=0,rounding_size=0.02', transform=fig.transFigure, fc='white', ec='none'))
        fig.text(x0 + 0.14, 0.66, lab, fontsize=28, fontweight='bold', color=MUTED, ha='center')
        fig.text(x0 + 0.14, 0.48, (f'{v:+.0f}°' if k < 2 else f'{v:.0f} ' + X['mm']).replace('+0°', '0°'), fontsize=72, fontweight='bold', color=col, ha='center', va='center')
        fig.text(x0 + 0.14, 0.32, PV.TOWNS[i][L], fontsize=32, fontweight='bold', color=INK, ha='center')
    foot(fig, X['src']); f = tmp / f'week_{lang}_1.png'; save(fig, f); items.append((f, 5.0))
    items.append((outro(lang, tmp), 3.0)); return items


# ---------- 7. snow in the mountains
SBOX = (66.5, 74.0, 38.3, 42.6)


def gibs_clear(day_end, n=5):
    """A cloud-poor true-colour picture of the mountains: per point the darker-than-middle of n days of VIIRS (clouds are bright and move; the snow stays)."""
    lon0, lon1, la0, la1 = SBOX; px = 2000; hpx = int(px * (la1 - la0) / ((lon1 - lon0) * COSL))
    ims = []
    for k in range(n):
        d = day_end - dt.timedelta(days=k)
        try:
            r = requests.get('https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi', params=dict(SERVICE='WMS', REQUEST='GetMap', VERSION='1.3.0', LAYERS='VIIRS_NOAA20_CorrectedReflectance_TrueColor',
                             STYLES='', CRS='EPSG:4326', BBOX=f'{la0},{lon0},{la1},{lon1}', WIDTH=px, HEIGHT=hpx, FORMAT='image/jpeg', TIME=d.isoformat()), timeout=180)
            if r.ok and r.headers.get('content-type', '').startswith('image') and len(r.content) > 40000: ims.append(np.asarray(Image.open(io.BytesIO(r.content)).convert('RGB'), np.float32))
        except Exception as e: print('gibs', d, e, flush=True)
    if not ims: return None
    S_ = np.stack(ims); L = S_.mean(-1); L[S_.max(-1) < 8] = 1e9
    k = np.argsort(L, axis=0)[min(1, len(ims) - 1)]
    return np.take_along_axis(S_, k[None, ..., None].repeat(3, -1), 0)[0].astype(np.uint8)


def v_snow(lang, tmp):
    X = T[lang]; today = dt.datetime.utcnow().date()
    now_, ago = gibs_clear(today - dt.timedelta(days=1)), gibs_clear(today - dt.timedelta(days=8))
    js = om_many(OM, [r[2] for r in RESORTS], [r[3] for r in RESORTS], dict(hourly='snow_depth', forecast_days=7))
    items = []
    lon0, lon1, la0, la1 = SBOX
    for img, d in ((ago, today - dt.timedelta(days=10)), (now_, today - dt.timedelta(days=3))):
        if img is None: continue
        fig = frame(lang, X['snow_t'], X['snow_a'].format(d=f'{d:%d.%m}'))
        ax = fig.add_axes([0.0, 0.0, 1.0, 1 - 104 / H]); ax.imshow(img, extent=(lon0, lon1, la0, la1), aspect='auto', interpolation='lanczos')
        ax.set_xlim(lon0, lon1); ax.set_ylim(la0, la1); ax.axis('off')
        for rings, col, lw, z in borders(): ax.add_collection(LineCollection(rings, colors='white' if z < 6.3 else '#ffd29c', linewidths=lw, alpha=0.7, zorder=z))
        for r in RESORTS + [('Toshkent', 'Ташкент', 41.31, 69.28), ('Farg‘ona', 'Фергана', 40.39, 71.78), ('Samarqand', 'Самарканд', 39.65, 66.96)]:
            ax.plot(r[3], r[2], 'o', ms=6, mfc='white', mec=NAVY, zorder=8)
            ax.annotate(r[0] if lang == 'uz' else r[1], (r[3], r[2]), xytext=(8, 5), textcoords='offset pixels', fontsize=14, fontweight='bold', color=INK, zorder=9,
                        bbox=dict(boxstyle='round,pad=0.25', fc='white', ec='none', alpha=0.75))
        brand(fig, 1 - 24 / W, 18 / H, X['src_snow'] + ' · ' + SIGN, fontsize=12, color='white', ha='right', va='bottom', zorder=9,
              bbox=dict(boxstyle='round,pad=0.35', fc=NAVY, ec='none', alpha=0.6))
        f = tmp / f'snow_{lang}_{d}.png'; save(fig, f); items.append((f, 3.5))
    fig = frame(lang, X['snow_t'], ''); ax = fig.add_axes([0.07, 0.2, 0.88, 0.62]); ax.set_facecolor('white')
    for r, j, c in zip(RESORTS, js, ['#0B2545', '#1E63C6', '#ee8434']):
        hh = j['hourly']; sd = np.array([x if x is not None else np.nan for x in hh['snow_depth']], float) * 100
        ax.plot(np.arange(len(sd)), sd, color=c, lw=3.5, label=r[0] if lang == 'uz' else r[1])
    t0 = [dt.datetime.fromisoformat(x) for x in js[0]['hourly']['time']]
    ax.set_xticks(range(12, len(t0), 24)); ax.set_xticklabels([f"{WD[lang][t0[i].weekday()]} {t0[i]:%d.%m}" for i in range(12, len(t0), 24)], fontsize=14, color=MUTED)
    ax.tick_params(axis='y', labelsize=13, colors=MUTED); ax.spines[['top', 'right']].set_visible(False); ax.set_ylim(bottom=0); ax.legend(fontsize=16, frameon=False)
    fig.text(0.07, 0.86, X['snow_depth'], fontsize=22, fontweight='bold', color=INK)
    foot(fig, X['src']); f = tmp / f'snow_{lang}_depth.png'; save(fig, f); items.append((f, 5.0))
    items.append((outro(lang, tmp), 3.0)); return items


# ---------- 8. the night sky
def moon_phase(d):
    """0..7: new, waxing crescent, first quarter, waxing gibbous, full, waning gibbous, last quarter, waning crescent."""
    age = ((dt.datetime(d.year, d.month, d.day, 18) - dt.datetime(2000, 1, 6, 18, 14)).total_seconds() / 86400) % 29.530588
    return int((age / 29.530588 * 8 + 0.5)) % 8, age


def v_sky(lang, tmp):
    X = T[lang]; la, lo, LA, LO = grid()
    js = om_many(OM, LA, LO, dict(hourly='cloud_cover', forecast_days=2))
    tt = [dt.datetime.fromisoformat(x) for x in js[0]['hourly']['time']]
    night = [i for i, t in enumerate(tt) if (t.date() == tt[0].date() and t.hour >= 20) or (t.date() > tt[0].date() and t.hour <= 4)]
    C = np.array([np.nanmean([j['hourly']['cloud_cover'][i] for i in night if j['hourly']['cloud_cover'][i] is not None] or [np.nan]) for j in js], float).reshape(len(la), len(lo))
    sj = om(OM, dict(latitude=41.31, longitude=69.28, daily='sunrise,sunset', forecast_days=2, timezone=TZ))
    ss = sj['daily']['sunset'][0][11:16]; sr = sj['daily']['sunrise'][1][11:16]
    ph, age = moon_phase(tt[0].date())
    fig = frame(lang, X['sky_t'], f"{tt[0]:%d.%m} → {(tt[0] + dt.timedelta(days=1)):%d.%m}", bg='#0e1a2b')
    ax = map_ax(fig); ax.set_facecolor('#0e1a2b')
    ax.contourf(lo, la, C, levels=[0, 20, 40, 60, 80, 101], colors=['#2dc653', '#8bd17c', '#c9d1b8', '#9aa5b1', '#6b7785'], alpha=0.85, zorder=2)
    for k, tw in enumerate(PV.TOWNS):
        ax.plot(tw[3], tw[2], 'o', ms=6, mfc='white', mec=NAVY, zorder=8)
        ax.annotate(tw[1 if lang == 'uz' else 0], (tw[3], tw[2]), xytext=(9, 6), textcoords='offset pixels', fontsize=14, fontweight='bold', color=INK, zorder=9,
                    bbox=dict(boxstyle='round,pad=0.25', fc='white', ec='none', alpha=0.8))
    # the moon drawn: a lit disc with the dark part as an ellipse
    mx = fig.add_axes([0.83, 0.62, 0.12, 0.12 * W / H]); mx.set_xlim(-1.2, 1.2); mx.set_ylim(-1.2, 1.2); mx.axis('off'); mx.set_aspect(1)
    mx.add_patch(Circle((0, 0), 1, fc='#2a3a52', ec='none'))
    f_ = (1 - math.cos(2 * math.pi * age / 29.530588)) / 2  # lit fraction
    from matplotlib.patches import Ellipse, Wedge
    waxing = age < 14.77
    mx.add_patch(Wedge((0, 0), 1, -90, 90, fc='#f5f0d0', ec='none') if waxing else Wedge((0, 0), 1, 90, 270, fc='#f5f0d0', ec='none'))
    mx.add_patch(Ellipse((0, 0), 2 * abs(1 - 2 * f_), 2, fc='#f5f0d0' if f_ > 0.5 else '#2a3a52', ec='none'))
    fig.text(0.89, 0.58, X['sky_moon'].format(p=X['moon'][ph]), fontsize=18, color='white', ha='center', fontweight='bold')
    fig.text(0.02, 0.085, X['sky_leg'] + ' · ' + X['sky_sun'].format(a=ss, b=sr), fontsize=15, color='white')
    fig.text(24 / W, 18 / H, X['src'], fontsize=12, color='#a9bdd6', va='bottom')
    brand(fig, 1 - 24 / W, 18 / H, SIGN, fontsize=12, color='#a9bdd6', ha='right', va='bottom', zorder=9)
    f = tmp / f'sky_{lang}.png'; save(fig, f)
    return [(f, 7.0), (outro(lang, tmp), 3.0)]


VIDEOS = {'pass': v_pass, 'frost': v_frost, 'dust': v_dust, 'models': v_models, 'short': v_short, 'week': v_week, 'snow': v_snow, 'sky': v_sky}


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    langs = (sys.argv[2] if len(sys.argv) > 2 else 'uz,ru').split(','); names = (sys.argv[3].split(',') if len(sys.argv) > 3 else list(VIDEOS))
    meta = {'made': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), 'ok': [], 'fail': {}}
    for name in names:
        for lang in langs:
            tmp = pathlib.Path(tempfile.mkdtemp())
            try:
                r = VIDEOS[name](lang, tmp)
                items, size = (r if isinstance(r, tuple) else (r, (W, H)))
                encode(items, out / f'{name}_{lang}.mp4', *size)
                meta['ok'].append(f'{name}_{lang}')
            except Exception as e:
                traceback.print_exc(); meta['fail'][f'{name}_{lang}'] = str(e)[:200]
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    json.dump(meta, open(out / 'meta.json', 'w'), ensure_ascii=False)
    print(meta, flush=True)


if __name__ == '__main__':
    main()
