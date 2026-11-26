"""Probe satellite sources for Uzbekistan: EUMETSAT IODC layer names, and NASA GIBS true colour (VIIRS / MODIS) of today and yesterday."""
import re, sys, pathlib, datetime as dt, requests
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
t = requests.get('https://view.eumetsat.int/geoserver/msg_iodc/wms', params=dict(service='WMS', request='GetCapabilities', version='1.3.0'), timeout=120).text
names = sorted(set(re.findall(r'<Name>(msg_iodc:[^<]+)</Name>', t)))
(out / 'iodc_layers.txt').write_text('\n'.join(names)); print(names)
V = (55, 74, 36.5, 46)
for d in [dt.date.today(), dt.date.today() - dt.timedelta(days=1)]:
    for lay in ['VIIRS_NOAA20_CorrectedReflectance_TrueColor', 'VIIRS_NOAA21_CorrectedReflectance_TrueColor', 'VIIRS_SNPP_CorrectedReflectance_TrueColor', 'MODIS_Terra_CorrectedReflectance_TrueColor', 'MODIS_Aqua_CorrectedReflectance_TrueColor']:
        r = requests.get('https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi', params=dict(SERVICE='WMS', REQUEST='GetMap', VERSION='1.3.0', LAYERS=lay, STYLES='', CRS='EPSG:4326',
                         BBOX=f'{V[2]},{V[0]},{V[3]},{V[1]}', WIDTH=1900, HEIGHT=950, FORMAT='image/jpeg', TIME=d.isoformat()), timeout=180)
        print(d, lay, r.status_code, r.headers.get('content-type'), len(r.content))
        if r.ok and 'image' in r.headers.get('content-type', ''): (out / f'{d}_{lay.split("_")[0]}_{lay.split("_")[1]}.jpg').write_bytes(r.content)
# a natural colour RGB of IODC if there is one
for lay in [n for n in names if re.search(r'natural|rgb|hrv|true', n, re.I)][:4]:
    r = requests.get('https://view.eumetsat.int/geoserver/wms', params=dict(service='WMS', version='1.3.0', request='GetMap', layers=lay, styles='', crs='EPSG:4326', bbox=f'{V[2]},{V[0]},{V[3]},{V[1]}', width=1900, height=950, format='image/jpeg'), timeout=180)
    print(lay, r.status_code, len(r.content))
    if r.ok: (out / f'iodc_{lay.split(":")[1]}.jpg').write_bytes(r.content)
