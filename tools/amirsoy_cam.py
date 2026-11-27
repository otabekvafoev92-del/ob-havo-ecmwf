"""Amirsoy resort webcams: every run checks the four cameras (ipeye), takes the ones that are online now and records a 30-second
video from them (one camera: 30 s; several: their parts one after another), with a caption bar: the camera, the time in Tashkent and
the weather on the top now (Open-Meteo). Usage: python tools/amirsoy_cam.py out  →  out/amirsoy.mp4, out/amirsoy.jpg, out/meta.json"""
import sys, json, pathlib, subprocess, tempfile, shutil, datetime as dt, requests

CAMS = [('north', '7c8231e409fe4d5f9450384993720b5e', 'Вершина, север · 2290 м', 'Cho‘qqi, shimol · 2290 m'),
        ('south', 'b65cb31c58e44e308d6807c45db86520', 'Вершина, юг · 2290 м', 'Cho‘qqi, janub · 2290 m'),
        ('restaurant', '596eb07e695d415ea677aab3fb1581cd', 'Ресторан 2290', 'Restoran 2290'),
        ('prima', '3d01802be4b544c8b4e64aea00e76e6e', 'Канатная дорога Prima', 'Prima kanat yo‘li')]
H = {'user-agent': 'Mozilla/5.0', 'referer': 'https://ipeye.ru/'}
TOTAL = 30
TOP = (41.4930, 70.0335, 2290)  # Amirsoy, the top station


def font():
    for f in ['/usr/share/fonts/opentype/inter/Inter-Bold.otf', '/usr/share/fonts/truetype/inter/Inter-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']:
        if pathlib.Path(f).exists(): return f
    return subprocess.run(['fc-match', '-f', '%{file}', 'sans:bold'], capture_output=True, text=True).stdout.strip()


def online(dev):
    try:
        j = requests.get(f'https://api.ipeye.ru/v1/stream/info/{dev}', headers=H, timeout=30).json()['orign']['message']
        if not j.get('status'): return None
        u = requests.get(f'https://api.ipeye.ru/device/url/hls/{dev}', headers=H, timeout=30).json()
        return u.get('message') if u.get('status') else None
    except Exception as e: print('cam', dev, e, flush=True); return None


def weather():
    try:
        c = requests.get('https://api.open-meteo.com/v1/forecast', params=dict(latitude=TOP[0], longitude=TOP[1], elevation=TOP[2], current='temperature_2m,wind_speed_10m,wind_gusts_10m,weather_code,snow_depth',
                                                                             wind_speed_unit='ms', timezone='Asia/Tashkent'), timeout=30).json()['current']
        return c
    except Exception as e: print('weather', e, flush=True); return None


def esc(t): return t.replace('\\', '\\\\').replace(':', '\\:').replace("'", "’").replace('%', '\\%')


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); tmp = pathlib.Path(tempfile.mkdtemp())
    live = [(k, d, ru, uz, u) for k, d, ru, uz in CAMS if (u := online(d))]
    print('online:', [c[0] for c in live], flush=True)
    now = dt.datetime.utcnow() + dt.timedelta(hours=5); W = weather(); F = font()
    wtxt = ''
    if W:
        wtxt = f"{W['temperature_2m']:+.0f}°C · ветер {W['wind_speed_10m']:.0f} м/с (порывы {W['wind_gusts_10m']:.0f})" + (f" · снег {W['snow_depth'] * 100:.0f} см" if W.get('snow_depth') else '')
    parts = []  # each camera recorded for the whole 30 s; then the ones that worked share the 30 s (a camera that fails gives its time to the others)
    for k, d, ru, uz, u in live[:3]:
        f = tmp / f'{k}.mp4'
        vf = (f"scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=25,"
              f"drawbox=x=0:y=0:w=iw:h=64:color=0x0b1220@0.72:t=fill,"
              f"drawtext=fontfile={F}:text='OSMON':x=24:y=18:fontsize=28:fontcolor=0xf08a24,"
              f"drawtext=fontfile={F}:text='{esc('Амирсой · ' + ru)}':x=150:y=18:fontsize=28:fontcolor=white,"
              f"drawtext=fontfile={F}:text='{esc(now.strftime('%d.%m %H:%M'))}':x=w-tw-24:y=18:fontsize=28:fontcolor=0xffd29c,"
              f"drawbox=x=0:y=ih-56:w=iw:h=56:color=0x0b1220@0.6:t=fill,"
              f"drawtext=fontfile={F}:text='{esc(wtxt or 'камера в прямом эфире')}':x=24:y=h-42:fontsize=26:fontcolor=white,"
              f"drawtext=fontfile={F}:text='Bot - @ObHavo_ECMWF_bot · Kanal - @osmon_obhavo':x=w-tw-24:y=h-40:fontsize=22:fontcolor=0xa9bdd6")
        r = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-rw_timeout', '15000000', '-i', u, '-t', str(TOTAL), '-an', '-vf', vf, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24', '-g', '25',
                            '-pix_fmt', 'yuv420p', str(f)], capture_output=True, text=True, timeout=180)
        if r.returncode == 0 and f.exists() and f.stat().st_size > 50000: parts.append((k, ru, uz, f))
        else: print('record failed', k, r.stderr[-300:], flush=True)
    if not parts:
        json.dump(dict(made=now.strftime('%Y-%m-%dT%H:%M'), cams=[], ok=False), open(out / 'meta.json', 'w'), ensure_ascii=False); print('no camera recorded'); return
    per = TOTAL / len(parts)
    (tmp / 'l.txt').write_text(''.join(f"file '{p[3]}'\noutpoint {per:.2f}\n" for p in parts))
    dst = out / 'amirsoy.mp4'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(tmp / 'l.txt'), '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                    '-c:a', 'aac', '-b:a', '32k', '-shortest', '-movflags', '+faststart', str(dst)], check=True)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', '2', '-i', str(parts[0][3]), '-frames:v', '1', '-q:v', '3', str(out / 'amirsoy.jpg')])
    json.dump(dict(made=now.strftime('%Y-%m-%dT%H:%M'), ok=True, cams=[dict(k=k, ru=ru, uz=uz) for k, ru, uz, _ in parts], weather=W), open(out / 'meta.json', 'w'), ensure_ascii=False)
    print(dst, dst.stat().st_size // 1024, 'KB', flush=True); shutil.rmtree(tmp)


if __name__ == '__main__':
    main()
