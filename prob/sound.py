"""Weather sound for the videos: rain, snow, wind and thunder that follow the forecast frame by frame, over a quiet
calm pad, all synthesised here (no recordings, nothing licensed). A video with a sound track is also a real video in
Telegram (a silent mp4 is shown as a GIF that loops without controls).
  levels: one dict per video frame: rain 0…1, snow bool, wind 0…1, storm 0…1
  track(levels, frame_sec, path, intro_sec=0)  → a 48 kHz stereo WAV
  mux(mp4, wav)                                → the same mp4 with an AAC sound track
  from_series(P, T, W, K=None)                 → levels from a place's chance of precipitation (%), temperature (°C),
                                                 wind (m/s) and CAPE (J/kg)"""
import subprocess, wave
import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
CTL = 100  # control rate of the envelopes (Hz)


def _bp(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], btype='band', fs=SR, output='sos'), x)


def _lp(x, f):
    return sosfilt(butter(2, f, btype='low', fs=SR, output='sos'), x)


def _env(values, frame_sec, intro_sec, n, smooth=0.7):
    """Per-frame levels → a smooth per-sample envelope (the intro takes the first frame's level)."""
    k = int(round(frame_sec * CTL)); ki = int(round(intro_sec * CTL))
    c = np.concatenate([np.full(ki, values[0] if len(values) else 0.0)] + [np.full(k, v) for v in values]) if len(values) else np.zeros(1)
    w = max(1, int(smooth * CTL)); c = np.convolve(np.pad(c, (w, w), mode='edge'), np.ones(w) / w, mode='same')[w:-w]
    return np.interp(np.arange(n) / SR * CTL, np.arange(len(c)), c)


def _bubbles(rng, n, level, rate, ch):
    """Rain drops as bubbles: each a short sine whose pitch rises while it fades (the classic drop-in-water model)."""
    out = np.zeros(n); L = int(0.03 * SR); t = np.arange(L) / SR
    lam = rate * level / SR; pos = np.flatnonzero(rng.random(n) < lam)
    for p in pos[:200000]:
        f0 = rng.uniform(1200, 4200); d = rng.uniform(0.004, 0.012)
        k = min(L, n - p); tt = t[:k]
        out[p:p + k] += rng.uniform(0.2, 1.0) * np.sin(2 * np.pi * f0 * tt * (1 + 18 * tt)) * np.exp(-tt / d)
    return out


def _bells(rng, n, level, ch):
    """Soft high bells for snow: a few bright partials with a long, quiet decay, about one every two seconds."""
    out = np.zeros(n); L = int(2.5 * SR); t = np.arange(L) / SR
    notes = [1046.5, 1174.7, 1318.5, 1568.0, 1760.0, 2093.0]  # C major pentatonic, high
    pos = np.flatnonzero(rng.random(n) < 0.5 * level / SR)
    for p in pos:
        f = notes[int(rng.integers(len(notes)))]; k = min(L, n - p); tt = t[:k]
        tone = np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * 2.76 * f * tt) * np.exp(-tt / 0.15)
        out[p:p + k] += rng.uniform(0.4, 1.0) * tone * np.exp(-tt / 0.7) * (1 - np.exp(-tt / 0.004))
    return out


def from_series(P, T, W, K=None):
    P, T, W = (np.asarray(a, float) if a is not None else None for a in (P, T, W))
    out = []
    for i in range(len(P)):
        p = float(np.nan_to_num(P[i])) / 100
        t = float(T[i]) if T is not None and np.isfinite(T[i]) else 10.0
        w = float(W[i]) if W is not None and np.isfinite(W[i]) else 2.0
        k = float(K[i]) if K is not None and np.isfinite(K[i]) else 0.0
        rain = 0.0 if p < 0.2 else min(1.0, (p - 0.2) / 0.6)  # below 20 % nothing, full at 80 %
        out.append({'rain': rain, 'snow': t <= 0.5, 'wind': float(np.clip((w - 1) / 13, 0, 1)), 'storm': 1.0 if (k >= 1200 and p >= 0.4 and t >= 5) else 0.0})
    return out


def track(levels, frame_sec, path, intro_sec=0.0, seed=7):
    rng = np.random.default_rng(seed)
    dur = intro_sec + frame_sec * max(1, len(levels)); n = int(dur * SR) + SR // 2
    g = lambda key: _env([float(l.get(key, 0)) for l in levels], frame_sec, intro_sec, n)
    rain, wind, storm = g('rain'), g('wind'), g('storm')
    snow = _env([1.0 if l.get('snow') else 0.0 for l in levels], frame_sec, intro_sec, n)
    rainy, snowy = rain * (1 - snow), rain * snow
    out = np.zeros((2, n))
    for ch in range(2):  # two decorrelated channels: a wide, natural sound
        wn = rng.standard_normal(n)
        # wind: brown noise, low and breathy, with slow gusts; a light breeze is always there
        br = np.cumsum(rng.standard_normal(n)); br -= _lp(br, 0.5); br /= np.percentile(np.abs(br), 99) + 1e-9
        gust = np.interp(np.arange(n), np.linspace(0, n, max(4, int(dur / 2.5))), 0.55 + 0.45 * rng.random(max(4, int(dur / 2.5))))  # a gust every few seconds
        wsig = _lp(br, 500) * 0.9 + _bp(wn, 250, 1100) * 0.12
        out[ch] += wsig * (0.06 + 0.55 * wind ** 1.2) * gust
        # rain, four layers (procedural rain): a soft roar of distant rain, a bright hiss that flickers,
        # drops that land as bubbles (a short tone that rises in pitch: the sound of a drop in water), and thuds on roofs
        flick = np.interp(np.arange(n), np.linspace(0, n, int(dur * 8) + 2), 0.75 + 0.25 * rng.random(int(dur * 8) + 2))
        out[ch] += _bp(wn, 300, 1500) * 0.16 * rainy ** 1.3
        out[ch] += _bp(wn, 1800, 9000) * 0.20 * rainy ** 1.5 * flick  # the hiss only fills in when the rain is heavy
        out[ch] += _bubbles(rng, n, rainy, 90, ch) * 0.55
        thud = np.zeros(n); hit = rng.random(n) < 25 * rainy / SR
        thud[hit] = rng.uniform(0.3, 1.0, hit.sum())
        out[ch] += _bp(np.convolve(thud, np.exp(-np.arange(int(0.03 * SR)) / (0.006 * SR)))[:n], 120, 900) * 0.35
        # snow: falling snow is almost silent, so a muffled hush and soft high bells (the winter sign of the video);
        # heavy snow with wind turns into a blizzard: a howling whistle that slides up and down
        out[ch] += _bp(wn, 150, 900) * 0.08 * snowy ** 0.8
        out[ch] += _bells(rng, n, snowy, ch) * 0.10
        howl = np.zeros(n); blz = snowy * wind
        if blz.max() > 0.05:
            fc = 450 + 250 * np.sin(2 * np.pi * np.cumsum(np.full(n, 0.11)) / SR + rng.random() * 6)
            for lo in (300, 520, 760):  # three overlapping bands follow the slow pitch
                band = _bp(wn, lo, lo * 1.25); howl += band * np.exp(-((fc - lo * 1.12) / 140) ** 2)
            out[ch] += howl * 0.6 * blz
        # thunder: a crack of lightning, then after a moment (the distance) a rolling rumble
        th = np.zeros(n); cr = np.zeros(n); t0 = 0
        while t0 < n:
            t0 += int(SR * rng.uniform(5, 11))
            if t0 >= n or storm[min(t0, n - 1)] < 0.5: continue
            near = rng.random() < 0.4
            c = np.arange(min(int(0.25 * SR), n - t0)); cr[t0:t0 + len(c)] += np.exp(-c / (0.05 * SR)) * (1.0 if near else 0.25)
            t1 = t0 + int(SR * (rng.uniform(0.05, 0.3) if near else rng.uniform(1.0, 2.5)))
            ln = int(SR * rng.uniform(3.0, 5.5)); seg = np.arange(max(0, min(ln, n - t1)))
            if len(seg):  # a few swells inside one roll
                sw = 1 + 0.6 * np.sin(2 * np.pi * seg / SR * rng.uniform(0.6, 1.4)) ** 2
                th[t1:t1 + len(seg)] += np.exp(-seg / (1.3 * SR)) * (1 - np.exp(-seg / (0.08 * SR))) * sw
        rum = _lp(br, 160); rum /= np.percentile(np.abs(rum), 99) + 1e-9
        out[ch] += rum * th * 0.95 + _bp(wn, 500, 7000) * cr * 0.8
    # drips: clear single drops ("plip") falling from roofs into puddles, panned left and right — the sound people
    # know as rain even when it is light
    L = int(0.12 * SR); tt = np.arange(L) / SR
    for p in np.flatnonzero(rng.random(n) < (np.where(rainy > 0.04, 2.5 + 6 * rainy, 0)) / SR):
        f0 = rng.uniform(650, 1500); d = rng.uniform(0.025, 0.05); k = min(L, n - p)
        tone = np.sin(2 * np.pi * f0 * tt[:k] * (1 + 7 * tt[:k])) * np.exp(-tt[:k] / d) * (1 - np.exp(-tt[:k] / 0.0008))
        amp = rng.uniform(0.35, 0.8) * (0.5 + 0.5 * min(1, rainy[p] * 3)); pan = rng.uniform(0.15, 0.85)
        out[0, p:p + k] += tone * amp * (1 - pan); out[1, p:p + k] += tone * amp * pan
    # a quiet calm pad (C major add 9) that steps back when the weather gets loud
    t = np.arange(n) / SR; pad = np.zeros(n)
    for f, a in ((130.81, 1.0), (196.0, 0.7), (261.63, 0.6), (293.66, 0.35), (329.63, 0.45)):
        pad += a * np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 0.07 * t))
    pad *= (0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t)) * 0.018 * (1 - 0.7 * np.clip(rain + wind, 0, 1))
    out += pad
    # fade in and out; fixed levels (a calm day stays quiet, a storm is loud), a soft limiter for the peaks
    f = int(0.8 * SR); ramp = np.ones(n); ramp[:f] = np.linspace(0, 1, f); ramp[-f:] = np.linspace(1, 0, f)
    out = np.tanh(out * ramp * 1.1) * 0.9
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((out.T * 32767).astype('<i2').tobytes())
    return path


def mux(mp4, wav):
    """Add the sound to the video (the picture is copied as it is)."""
    tmp = str(mp4) + '.a.mp4'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(mp4), '-i', str(wav), '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k',
                    '-shortest', '-movflags', '+faststart', tmp], check=True)
    import os; os.replace(tmp, mp4); os.remove(wav)
