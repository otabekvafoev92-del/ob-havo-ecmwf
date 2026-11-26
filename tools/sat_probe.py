"""Probe EUMETSAT IODC (Meteosat over the Indian Ocean) colour layers over Uzbekistan: which names answer with a picture."""
import re, sys, pathlib, requests
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
V = (55, 74, 36.5, 46); log = []
for lay in ['rgb_naturalenhncd', 'rgb_natural', 'rgb_naturalcolor', 'rgb_truecolour', 'rgb_truecolor', 'rgb_eview', 'hrv', 'rgb_hrv', 'rgb_hrvfog', 'rgb_dust', 'rgb_convection',
            'rgb_airmass', 'rgb_fog', 'rgb_snow', 'rgb_microphysics', 'rgb_cloudtype', 'vis006', 'ir108', 'clm']:
    name = f'msg_iodc:{lay}'
    try:
        cap = requests.get(f'https://view.eumetsat.int/geoserver/msg_iodc/{lay}/wms', params=dict(service='WMS', request='GetCapabilities', version='1.3.0'), timeout=60).text
        m = re.search(r'<Dimension[^>]*name="time"[^>]*default="([^"]+)"', cap)
        r = requests.get('https://view.eumetsat.int/geoserver/wms', params=dict(service='WMS', version='1.3.0', request='GetMap', layers=name, styles='', crs='EPSG:4326',
                         bbox=f'{V[2]},{V[0]},{V[3]},{V[1]}', width=1900, height=950, format='image/jpeg'), timeout=120)
        ok = r.ok and r.headers.get('content-type', '').startswith('image')
        log.append(f"{name} cap={len(cap)} latest={m.group(1) if m else None} map={r.status_code} {r.headers.get('content-type')} {len(r.content)}")
        if ok: (out / f'{lay}.jpg').write_bytes(r.content)
    except Exception as e: log.append(f'{name} {e}')
    print(log[-1], flush=True)
(out / 'log.txt').write_text('\n'.join(log))
