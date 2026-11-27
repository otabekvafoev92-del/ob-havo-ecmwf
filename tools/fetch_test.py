"""Short run of prob/fetch.py (12 h) to check the new models: ICON-EPS, IFS 0.1°, UK Met Office."""
import subprocess, sys, os
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'eccodes', 'numpy', 'scipy', 'netCDF4'], check=True)
r = subprocess.run([sys.executable, '-u', '../prob/fetch.py', 'p.npz', '--max-step', '12', '--glob', '', '--wx', ''], capture_output=True, text=True)
txt = r.stdout[-6000:] + '\nERR\n' + r.stderr[-3000:]
try:
    import numpy as np
    D = np.load('p.npz', allow_pickle=True)
    txt += '\n' + str({k: D[k].tolist() for k in D.files if k.startswith('n_')}) + '\ndet_avail ' + str(D['det_avail'].tolist()) + ' ' + str(D['det_names'].tolist())
    os.remove('p.npz')
except Exception as e: txt += f'\nload {e}'
print(txt); open('probe.txt', 'w').write(txt)
