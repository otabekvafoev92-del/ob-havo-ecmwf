"""Bundle site/ + a forecast.json snapshot into one self-contained HTML page (demo)."""
import json, re, sys, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
data_path, out_path = sys.argv[1], sys.argv[2]
html = (root / 'site/index.html').read_text()
css = (root / 'site/style.css').read_text()
js = (root / 'site/app.js').read_text()
data = json.loads(pathlib.Path(data_path).read_text())
body = re.search(r'<!--APP-->(.*)<!--/APP-->', html, re.S).group(1)
head = f"""<title>Osmon ECMWF 3D</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700&family=Unbounded:wght@500;700&family=JetBrains+Mono:wght@400;600&display=swap">
<style>{css}</style>
<script type="importmap">{{"imports":{{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}}}</script>
"""
payload = json.dumps(data, separators=(',', ':')).replace('</', '<\\/')
out = head + body + f"<script>window.__FORECAST__={payload};</script>\n<script type=\"module\">\n{js}\n</script>\n"
pathlib.Path(out_path).write_text(out)
print(len(out))
