"""Joins the parts of a video drawn on several machines (tools/place15.py with P15_PART=k/n): the pictures one after another
(copied, not encoded again) and the weather's sound made for the whole. Usage: python tools/seg_join.py dir n  →  dir/<name>.mp4"""
import sys, json, pathlib, subprocess
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'prob'))
d, n = pathlib.Path(sys.argv[1]), int(sys.argv[2])
J = [json.load(open(d / f'seg_{k}.json')) for k in range(n)]
out = d / J[0]['name']; lst = d / 'segs.txt'
lst.write_text(''.join(f"file 'seg_{k}.mp4'\n" for k in range(n)))
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', '-movflags', '+faststart', str(out)], check=True)
try:
    import sound
    lv = [l for j in J for l in j['lv']]; wav = str(out) + '.wav'
    sound.track(lv, 0.1, wav, mode={'temp': 'temp', 'cloud': 'cloud'}.get(J[0].get('mode'), 'precip')); sound.mux(out, wav); pathlib.Path(wav).unlink(missing_ok=True)
except Exception as e:
    print('sound', e, flush=True)
for k in range(n): (d / f'seg_{k}.mp4').unlink(); (d / f'seg_{k}.json').unlink()
print(out, out.stat().st_size // 1024, 'KB', flush=True)
