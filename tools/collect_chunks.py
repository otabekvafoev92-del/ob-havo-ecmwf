import json, glob, base64, sys, collections
parts = collections.defaultdict(dict); totals = {}
for f in glob.glob('/root/.claude/projects/-home-claude/5dd8bf11-c108-57bf-92b5-edd39b16fc5b/tool-results/*.txt'):
    try: t = json.load(open(f))[0]['text']
    except Exception: continue
    if not t.startswith('"CHUNK|'): continue
    try: s = json.loads(t.split('\n\n(captured')[0])
    except Exception: continue
    try: _, k, i, n, data = s.split('|', 4); int(n)
    except Exception: continue
    if '|PAD|' in data: data = data[:data.rindex('|PAD|')]
    parts[k][int(i)] = data; totals[k] = int(n)
out = {}
for k, d in parts.items():
    missing = [i for i in range(totals[k]) if i not in d]
    print(k, 'chunks', len(d), '/', totals[k], 'missing', missing)
    if not missing: out[k] = ''.join(d[i] for i in range(totals[k]))
json.dump({k: v for k, v in out.items()}, open(sys.argv[1], 'w'))
