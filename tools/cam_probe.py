"""Amirsoy webcams (ipeye): the player's ajax endpoint, and a test of 30 s recording from each camera's HLS stream."""
import re, json, subprocess, requests
D = {'restaurant': '596eb07e695d415ea677aab3fb1581cd', 'north': '7c8231e409fe4d5f9450384993720b5e', 'south': 'b65cb31c58e44e308d6807c45db86520', 'prima': '3d01802be4b544c8b4e64aea00e76e6e'}
H = {'user-agent': 'Mozilla/5.0', 'referer': 'https://ipeye.ru/', 'origin': 'https://ipeye.ru'}
out = []
jt = requests.get('https://ipeye.ru/ipeye_service/api/player_dist/ipeyePlayer.js?ver=1.85', headers=H, timeout=60).text
for m in re.finditer(r'(url\s*:|\$\.ajax|\.get\(|fetch\()', jt):
    out.append('ajax...' + jt[max(0, m.start() - 80):m.end() + 260].replace('\n', ' '))
for k, dev in D.items():
    for u in [f'https://api.ipeye.ru/v1/stream/info/1/{dev}', f'https://api.ipeye.ru/v1/stream/info/{dev}', f'https://api.ipeye.ru/device/url/hls/{dev}', f'https://api.ipeye.ru/v1/stream/status/1/{dev}']:
        try: r = requests.get(u, headers=H, timeout=30); out.append(f'{k} {u} {r.status_code} {r.text[:300]}')
        except Exception as e: out.append(f'{k} {u} {e}')
open('probe.txt', 'w').write('\n'.join(out)[:100000]); print('\n'.join(out)[:8000])
