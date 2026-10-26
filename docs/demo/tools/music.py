"""Soundtrack for the Lapidary demo: a soft A-minor pad, bass, a plucked arpeggio and transition whooshes, one shared reverb."""
import sys
import wave

import numpy as np

SR, DUR = 48000, 64.0
BPM = 84.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(7)

def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)

# A minor, F, C, G (MIDI notes)
CHORDS = [[57, 60, 64, 69], [53, 57, 60, 65], [48, 52, 55, 64], [55, 59, 62, 67]]
ROOTS = [45, 41, 48, 43]

def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    b = 1 - a
    for i in range(len(x)):  # small enough at 48 kHz for one pass per layer
        acc = b * x[i] + a * acc
        y[i] = acc
    return y

def env(start, length, attack, release):
    e = np.zeros(N)
    i0, i1 = int(start * SR), min(N, int((start + length) * SR))
    if i1 <= i0:
        return e
    seg = np.arange(i1 - i0) / SR
    a = np.clip(seg / attack, 0, 1)
    r = np.clip((length - seg) / release, 0, 1)
    e[i0:i1] = np.minimum(a, r)
    return e

pad = np.zeros(N)
bass = np.zeros(N)
nbars = int(np.ceil(DUR / BAR)) + 1
for b in range(nbars):
    start = b * BAR
    if start >= DUR:
        break
    chord = CHORDS[b % 4]
    e = env(start, BAR + 0.6, 0.9, 1.2)
    for m in chord:
        f = hz(m)
        for det in (-0.12, 0.0, 0.11):  # soft detuned triangles
            ph = 2 * np.pi * f * (1 + det / 100) * t
            pad += e * (2 / np.pi) * np.arcsin(np.sin(ph)) * 0.05
    if start >= 6.2:
        eb = env(start, BAR, 0.05, 0.6)
        bass += eb * np.sin(2 * np.pi * hz(ROOTS[b % 4]) * t) * 0.16
pad = lowpass(pad, 1400.0)

# plucked arpeggio in eighths from the comparison on, quieter under the end card
arp = np.zeros(N)
eighth = BEAT / 2
k = 0
tt = 12.6
while tt < DUR - 1.5:
    b = int(tt // BAR)
    chord = CHORDS[b % 4]
    note = chord[[0, 2, 1, 3, 2, 1, 3, 2][k % 8]] + 12
    i0 = int(tt * SR)
    L = int(1.1 * SR)
    seg = np.arange(min(L, N - i0)) / SR
    tone = np.sin(2 * np.pi * hz(note) * seg) + 0.25 * np.sin(4 * np.pi * hz(note) * seg)
    arp[i0:i0 + len(seg)] += tone * np.exp(-seg * 5.5) * 0.06
    tt += eighth
    k += 1

# whooshes on scene changes: band-limited noise swells
whoosh = np.zeros(N)
for c in (6.3, 12.6, 27.6, 39.6, 50.1, 58.1):
    i0, L = int((c - 0.55) * SR), int(0.9 * SR)
    n = rng.standard_normal(L)
    n = lowpass(n, 900.0) - lowpass(n, 180.0)
    shape = np.sin(np.linspace(0, np.pi, L)) ** 2
    whoosh[i0:i0 + L] += n * shape * 0.22

dry = pad + bass + arp + whoosh

# one shared reverb: decaying noise impulse response, FFT convolution
ir_len = int(1.8 * SR)
ir = rng.standard_normal(ir_len) * np.exp(-np.arange(ir_len) / SR * 3.2)
ir = lowpass(ir, 3000.0)
ir /= np.sqrt(np.sum(ir ** 2))
def conv(x):
    n = len(x) + ir_len
    m = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[:len(x)]
wetL, wetR = conv(dry), conv(np.roll(dry, 240))
L = dry + 0.32 * wetL
R = dry + 0.32 * wetR

fade = np.ones(N)
fi, fo = int(1.2 * SR), int(3.0 * SR)
fade[:fi] = np.linspace(0, 1, fi)
fade[-fo:] = np.linspace(1, 0, fo) ** 1.5
L *= fade
R *= fade
peak = max(np.abs(L).max(), np.abs(R).max())
g = 10 ** (-3 / 20) / peak
L *= g
R *= g
rms = np.sqrt(np.mean((L ** 2 + R ** 2) / 2))
print(f"peak -3.0 dBFS, rms {20 * np.log10(rms):.1f} dBFS")
out = np.stack([L, R], axis=1)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((np.clip(out, -1, 1) * 32767).astype("<i2").tobytes())
