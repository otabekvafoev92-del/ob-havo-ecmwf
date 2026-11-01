"""Joins the outputs of the parallel render jobs into one site/prob folder: files are copied (a later part wins, so the
city-video part goes last), manifest.json items and alerts.json warnings are combined.
Usage: python3 prob/merge.py site/prob part1 part2 ..."""
import json, pathlib, shutil, sys


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    M, items, alerts = None, {}, {}
    for part in map(pathlib.Path, sys.argv[2:]):
        if not part.is_dir(): continue
        for f in part.rglob('*'):
            if f.is_dir() or f.name in ('manifest.json', 'alerts.json') and f.parent == part: continue
            dst = out / f.relative_to(part); dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, dst)
        if (part / 'manifest.json').exists():
            m = json.load(open(part / 'manifest.json'))
            if M is None or (m.get('steps') and not M.get('steps')): M = {k: v for k, v in m.items() if k != 'items'}
            for i in m.get('items', []): items[(i.get('region'), i.get('lang'), i.get('product'))] = i
        if (part / 'alerts.json').exists():
            for a in json.load(open(part / 'alerts.json')).get('items', []): alerts[(a['region'], a['en'], a['date'], a['snow'])] = a
            M = M or {}; M.setdefault('run', json.load(open(part / 'alerts.json')).get('run'))
    if M is not None:
        M['items'] = list(items.values())
        json.dump(M, open(out / 'manifest.json', 'w'), ensure_ascii=False, indent=1)
        json.dump({'run': M.get('run'), 'items': list(alerts.values())}, open(out / 'alerts.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    print('merged', len(items), 'items,', len(alerts), 'warnings →', out)


if __name__ == '__main__':
    main()
