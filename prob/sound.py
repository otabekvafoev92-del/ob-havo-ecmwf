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
        # rain: a bright hiss plus drops whose number grows with the rain
        hiss = _bp(wn, 1200, 7000)
        out[ch] += hiss * 0.45 * rainy ** 0.8
        drops = np.zeros(n); rate = 60 * rainy  # drops per second
        hit = rng.random(n) < rate / SR
        drops[hit] = rng.uniform(0.3, 1.0, hit.sum()) * rng.choice([-1, 1], hit.sum())
        kern = np.exp(-np.arange(int(0.012 * SR)) / (0.0025 * SR))
        out[ch] += _bp(np.convolve(drops, kern)[:n], 900, 6000) * 0.5
        # snow: soft, muffled, close to silence (as falling snow is)
        out[ch] += _bp(wn, 200, 1400) * 0.10 * snowy ** 0.8
        # thunder: a few low rumbles while a storm is on
        th = np.zeros(n); t0 = 0
        while t0 < n:
            t0 += int(SR * rng.uniform(4, 9))
            if t0 >= n or storm[min(t0, n - 1)] < 0.5: continue
            ln = int(SR * rng.uniform(2.5, 4.5)); seg = np.arange(min(ln, n - t0))
            th[t0:t0 + len(seg)] += np.exp(-seg / (0.9 * SR)) * (1 - np.exp(-seg / (0.03 * SR)))
        rum = _lp(br, 120); rum /= np.percentile(np.abs(rum), 99) + 1e-9
        out[ch] += rum * th * 0.45
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
