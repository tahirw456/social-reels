#!/usr/bin/env python3
"""Generate an original, royalty-free background track (WAV) with numpy.
Every track is different (seeded): random key, chord progression, tempo and arpeggio pattern.
mood 'upbeat' (cargo / sourcing) or 'chill' (fashion).

Usage: python3 make_music.py --out music.wav --seconds 12 --mood upbeat --seed "any text"
"""
import argparse, hashlib, wave
import numpy as np

SR = 44100
PROGS = [[0, 7, 9, 5], [9, 5, 0, 7], [0, 9, 5, 7], [0, 5, 9, 7], [9, 7, 5, 7], [0, 4, 9, 5]]
MAJOR = {0: "maj", 2: "min", 4: "min", 5: "maj", 7: "maj", 9: "min"}


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def chord(root_midi, quality):
    third = 4 if quality == "maj" else 3
    return [root_midi, root_midi + third, root_midi + 7]


def osc(freq, n, kind="saw", harmonics=8):
    t = np.arange(n) / SR
    if kind == "sine":
        return np.sin(2 * np.pi * freq * t)
    out = np.zeros(n)
    for h in range(1, harmonics + 1):
        if kind == "square" and h % 2 == 0:
            continue
        out += np.sin(2 * np.pi * freq * h * t) / h
    return out * 0.6


def env(n, a=0.01, d=0.2, s=0.6, r=0.2):
    e = np.ones(n)
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    a = max(1, min(a, n)); e[:a] = np.linspace(0, 1, a)
    d2 = max(1, min(d, n - a)); e[a:a + d2] = np.linspace(1, s, d2)
    e[a + d2:] = s
    r = max(1, min(r, n)); e[-r:] *= np.linspace(1, 0, r)
    return e


def lowpass(x, alpha):
    # simple one-pole lowpass, vectorised via cumulative filter approximation
    y = np.empty_like(x); acc = 0.0
    for i in range(0, len(x), 64):
        seg = x[i:i + 64]
        for j, v in enumerate(seg):
            acc += alpha * (v - acc)
            y[i + j] = acc
    return y


def add(buf, sig, start):
    end = min(len(buf), start + len(sig))
    if start < len(buf):
        buf[start:end] += sig[:end - start]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=12)
    ap.add_argument("--mood", default="upbeat", choices=["upbeat", "chill"])
    ap.add_argument("--seed", default="")
    a = ap.parse_args()

    rng = np.random.default_rng(int(hashlib.md5(a.seed.encode()).hexdigest()[:8], 16))
    upbeat = a.mood == "upbeat"
    bpm = rng.integers(108, 124) if upbeat else rng.integers(84, 96)
    beat = 60.0 / bpm
    key = 48 + int(rng.integers(0, 12))  # C3..B3
    if key > 53: key -= 12
    prog = PROGS[int(rng.integers(0, len(PROGS)))]
    arp_pattern = [[0, 1, 2, 1], [0, 2, 1, 2], [0, 1, 2, 3], [2, 1, 0, 1]][int(rng.integers(0, 4))]
    n = int(a.seconds * SR)
    L = np.zeros(n); R = np.zeros(n)
    bar = 4 * beat
    nbars = int(np.ceil(a.seconds / bar)) + 1

    for b in range(nbars):
        deg = prog[b % len(prog)]
        notes = chord(key + deg, MAJOR[deg])
        t0 = int(b * bar * SR); blen = int(bar * SR)
        # pad (stereo detuned)
        pad = np.zeros(blen)
        for m in notes:
            pad += osc(midi_hz(m + 12), blen, "saw", 6)
        padR = np.zeros(blen)
        for m in notes:
            padR += osc(midi_hz(m + 12) * 1.004, blen, "saw", 6)
        e = env(blen, 0.25 if not upbeat else 0.08, 0.5, 0.7, 0.3)
        add(L, pad * e * 0.05, t0); add(R, padR * e * 0.05, t0)
        # bass
        for k in range(4 if upbeat else 2):
            step = beat if upbeat else 2 * beat
            ln = int(step * SR * 0.9)
            bs = osc(midi_hz(notes[0] - 12), ln, "square", 5) * env(ln, 0.005, 0.15, 0.4, 0.05) * 0.16
            add(L, bs, t0 + int(k * step * SR)); add(R, bs, t0 + int(k * step * SR))
        # arpeggio pluck (8ths for chill, 16ths for upbeat)
        div = 4 if upbeat else 2
        tones = notes + [notes[0] + 12]
        for k in range(4 * div):
            m = tones[arp_pattern[k % 4]] + 24
            ln = int(beat / div * SR * 1.6)
            pl = osc(midi_hz(m), ln, "square" if upbeat else "sine", 4) * env(ln, 0.002, 0.12, 0.0, 0.05) * (0.06 if upbeat else 0.09)
            pan = 0.5 + 0.35 * np.sin(k)
            st = t0 + int(k * beat / div * SR)
            add(L, pl * (1 - pan) * 2, st); add(R, pl * pan * 2, st)
        # drums
        for k in range(4):
            st = t0 + int(k * beat * SR)
            if upbeat or k % 2 == 0:
                ln = int(0.25 * SR); tt = np.arange(ln) / SR
                kick = np.sin(2 * np.pi * (50 + 90 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 12) * (0.5 if upbeat else 0.35)
                add(L, kick, st); add(R, kick, st)
            if k % 2 == 1:
                ln = int(0.18 * SR); tt = np.arange(ln) / SR
                sn = rng.standard_normal(ln) * np.exp(-tt * 22) * (0.06 if upbeat else 0.03)
                add(L, sn, st); add(R, sn, st)
            # hats on off-beats
            ln = int(0.05 * SR); tt = np.arange(ln) / SR
            hat = np.diff(rng.standard_normal(ln + 1)) * np.exp(-tt * 80) * (0.02 if upbeat else 0.012)
            add(L, hat, st + int(beat / 2 * SR)); add(R, hat, st + int(beat / 2 * SR))

    mix = np.stack([L, R], axis=1)
    # gentle tone shaping + fade in/out, normalise
    for c in range(2):
        mix[:, c] = 0.6 * mix[:, c] + 0.4 * lowpass(mix[:, c], 0.25)
    f_in, f_out = int(0.4 * SR), int(1.2 * SR)
    mix[:f_in] *= np.linspace(0, 1, f_in)[:, None]
    mix[-f_out:] *= np.linspace(1, 0, f_out)[:, None]
    mix = np.tanh(mix * 1.2)
    mix *= 0.85 / max(1e-6, np.abs(mix).max())
    pcm = (mix * 32767).astype("<i2")
    with wave.open(a.out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("OK", a.out, bpm, "bpm")


if __name__ == "__main__":
    main()
