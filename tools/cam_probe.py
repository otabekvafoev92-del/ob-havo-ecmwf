"""How the Amirsoy webcams (ipeye.ru player) are streamed: the iframe's HTML/JS, the stream URLs in it."""
import re, requests
D = {'restaurant': '596eb07e695d415ea677aab3fb1581cd', 'north': '7c8231e409fe4d5f9450384993720b5e', 'south': 'b65cb31c58e44e308d6807c45db86520', 'prima': '3d01802be4b544c8b4e64aea00e76e6e'}
H = {'user-agent': 'Mozilla/5.0', 'referer': 'https://www.amirsoy.com/'}
out = []
for k, dev in D.items():
    u = f'https://ipeye.ru/ipeye_service/api/iframe.php?iframe_player=1&dev={dev}&autoplay=0&archive=1'
    r = requests.get(u, headers=H, timeout=60); t = r.text
    out.append(f'== {k} {r.status_code} {len(t)}')
    out += sorted(set(re.findall(r'''["'](https?://[^"']+|wss?://[^"']+|/[^"'\s]*(?:m3u8|flv|hls|stream|api)[^"']*)["']''', t)))[:60]
    for m in re.finditer(r'(m3u8|hls|flv|wss?:|stream|devcode|server|token)', t):
        out.append('   ...' + t[max(0, m.start() - 120):m.end() + 160].replace('\n', ' '))
        if len(out) > 400: break
    for js in sorted(set(re.findall(r'src=["\']([^"\']+\.js[^"\']*)', t)))[:6]:
        ju = js if js.startswith('http') else 'https://ipeye.ru' + (js if js.startswith('/') else '/ipeye_service/api/' + js)
        try:
            jt = requests.get(ju, headers=H, timeout=60).text
            out.append(f'-- js {ju} {len(jt)}')
            for m in re.finditer(r'(m3u8|/hls|\.flv|wss?://|api/v\d|stream_url|getStream|/stream/)', jt):
                out.append('   js...' + jt[max(0, m.start() - 160):m.end() + 200].replace('\n', ' '))
        except Exception as e: out.append(f'js err {e}')
    break_after = False
open('probe.txt', 'w').write('\n'.join(out)[:200000]); print('\n'.join(out)[:6000])
