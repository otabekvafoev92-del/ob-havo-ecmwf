"""Check that the GEPS reader in prob/fetch.py works: members, values and timing for a few lead times (out.txt on the probe branch)."""
import subprocess, sys, site, time, datetime as dt
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--user', 'numpy', 'scipy', 'eccodes'], check=True)
site.addsitedir(site.getusersitepackages())
sys.path.insert(0, '../prob'); sys.path.insert(0, '..')
import numpy as np
import fetch as F
out = []
now = dt.datetime.utcnow(); run = (now - dt.timedelta(hours=10)).replace(minute=0, second=0, microsecond=0); run = run.replace(hour=0 if run.hour < 12 else 12)
G = F.Geps(run, [F.GRID]); out.append(f'run {run} url {G.url(24)}')
for s, w in [(6, 6), (24, 6), (195, 3), (198, 6), (360, 6)]:
    t = time.time(); a = G.amounts(s, w)
    out.append(f'+{s}h/{w}: ' + ('none' if a is None else f'{len(a)} members, max {max(float(x[0].max()) for x in a):.1f} mm, mean {np.mean([x[0].mean() for x in a]):.3f}') + f' ({time.time() - t:.1f} s)')
open('out.txt', 'w').write('\n'.join(out) + '\n'); print('\n'.join(out))
