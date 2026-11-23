"""Add an instrumental soundtrack to the race videos.

By default each video gets its own synthesized track: an original, royalty-free piece (pads, bass, plucked
arpeggio and drums) whose key, tempo, chords and sounds are picked from the file name, so no two uploads share
the same music. It builds up during the race and fades out over the closing hold.

Pass --track to use a track of your own instead (from Suno, YouTube's Audio Library...): it is looped if the
video is longer, faded in and out and levelled to -16 LUFS.

Usage:
    FFMPEG=/path/to/ffmpeg python3 scripts/video/add_music.py videos/es/videos/*.mp4
    FFMPEG=/path/to/ffmpeg python3 scripts/video/add_music.py --track song.mp3 videos/en/videos/nba-rings-en.mp4

The video stream is copied untouched; the file is replaced by the version with music.
Requires numpy.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
SR = 44100
END_HOLD = 6.0  # seconds of the closing hold, where the music fades out

# Chord progressions as scale degrees (0 = tonic) of a natural minor or major scale.
MINOR = [0, 2, 3, 5, 7, 8, 10]
MAJOR = [0, 2, 4, 5, 7, 9, 11]
PROGRESSIONS = [
    (MINOR, [0, 5, 2, 6]),  # i  VI III VII
    (MINOR, [0, 3, 5, 4]),  # i  iv VI  v
    (MINOR, [0, 6, 5, 6]),  # i VII VI VII
    (MAJOR, [0, 4, 5, 3]),  # I  V  vi IV
    (MAJOR, [5, 3, 0, 4]),  # vi IV I   V
    (MAJOR, [0, 5, 3, 4]),  # I  vi IV  V
]


def duration(video: Path) -> float:
    out = subprocess.run([FFMPEG, "-i", str(video)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def env(n: int, attack: float, release: float) -> np.ndarray:
    """A linear attack, then an exponential decay to the end of the note."""
    t = np.arange(n) / SR
    a = np.minimum(1, t / max(attack, 1e-4))
    return a * np.exp(-t / release)


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    """One-pole low-pass, applied twice for a gentler, warmer top end."""
    k = 1 - np.exp(-2 * np.pi * cutoff / SR)
    for _ in range(2):
        y = np.empty_like(x)
        acc = 0.0
        # Vectorise in blocks: the recursion runs over a decimated signal and is interpolated back.
        step = 8
        xs = x[::step]
        ys = np.empty_like(xs)
        kk = 1 - (1 - k) ** step
        for i, v in enumerate(xs):
            acc += kk * (v - acc)
            ys[i] = acc
        y = np.interp(np.arange(len(x)), np.arange(len(xs)) * step, ys)
        x = y
    return x


def song(seconds: float, seed: str) -> np.ndarray:
    rng = np.random.default_rng(int(hashlib.sha256(seed.encode()).hexdigest()[:12], 16))
    scale, degrees = PROGRESSIONS[rng.integers(len(PROGRESSIONS))]
    root = 45 + int(rng.integers(0, 8))  # A2 .. E3
    bpm = float(rng.choice([92, 96, 100, 104, 108, 112, 116]))
    beat = 60 / bpm
    bar = 4 * beat
    wave_kind = rng.choice(["saw", "square", "soft"])
    arp_pattern = [[0, 1, 2, 1], [0, 2, 1, 2], [0, 1, 2, 3], [2, 1, 0, 1]][rng.integers(4)]
    n = int(seconds * SR) + SR
    left, right = np.zeros(n), np.zeros(n)

    def add(sig: np.ndarray, start: float, gain: float, pan: float = 0.0) -> None:
        i = int(start * SR)
        if i >= n:
            return
        sig = sig[: n - i] * gain
        left[i : i + len(sig)] += sig * (1 - pan) / 2 ** 0.5 * 1.4
        right[i : i + len(sig)] += sig * (1 + pan) / 2 ** 0.5 * 1.4

    def tone(freq: float, length: float, kind: str) -> np.ndarray:
        t = np.arange(int(length * SR)) / SR
        if kind == "saw":
            sig = sum(np.sin(2 * np.pi * freq * h * t) / h for h in range(1, 7))
        elif kind == "square":
            sig = sum(np.sin(2 * np.pi * freq * h * t) / h for h in range(1, 9, 2))
        else:
            sig = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t)
        return sig

    def chord(deg: int) -> list[int]:
        # A triad (plus the seventh) on the scale degree, as MIDI notes above the root.
        idx = [deg, deg + 2, deg + 4, deg + 6]
        return [root + 12 * (i // 7) + scale[i % 7] for i in idx]

    bars = int(np.ceil(seconds / bar)) + 1
    music_end = seconds - END_HOLD * 0.5
    for b in range(bars):
        t0 = b * bar
        if t0 > music_end:
            break
        notes = chord(degrees[b % len(degrees)])
        intensity = min(1.0, 0.35 + b / 16)  # the arrangement fills in over the first bars
        # Pad: the chord held over the bar, detuned left and right.
        for i, m in enumerate(notes[:3]):
            for detune, pan in ((-0.07, -0.6), (0.07, 0.6)):
                sig = tone(hz(m + 12 + detune), bar + 0.4, wave_kind) * env(int((bar + 0.4) * SR), 0.6, 2.5)
                add(sig, t0, 0.045, pan)
        # Bass: root on every eighth, an octave jump on the off-beats.
        if b >= 2:
            for e in range(8):
                m = notes[0] - 12 + (12 if e % 2 and rng.random() < 0.25 else 0)
                sig = tone(hz(m), beat / 2, "soft") * env(int(beat / 2 * SR), 0.005, 0.18)
                add(sig, t0 + e * beat / 2, 0.22 * intensity)
        # Arpeggio: plucked sixteenths over the chord, from bar 4.
        if b >= 4:
            for s in range(16):
                m = notes[arp_pattern[s % 4]] + 24
                sig = tone(hz(m), beat / 2, "square") * env(int(beat / 2 * SR), 0.002, 0.09)
                add(sig, t0 + s * beat / 4, 0.05 * intensity, 0.35 if s % 2 else -0.35)
        # Drums: kick on the beats from bar 2, hats on the off-beats, a clap on 2 and 4 from bar 8.
        if b >= 2:
            for q in range(4):
                tq = t0 + q * beat
                k = np.arange(int(0.25 * SR)) / SR
                kick = np.sin(2 * np.pi * (45 * k + 60 * (1 - np.exp(-k * 30)) / 30)) * np.exp(-k * 14)
                add(kick, tq, 0.55 * intensity)
                hat = rng.standard_normal(int(0.05 * SR)) * np.exp(-np.arange(int(0.05 * SR)) / SR * 90)
                add(np.diff(hat, prepend=0), tq + beat / 2, 0.06 * intensity, 0.3)
                if b >= 8 and q in (1, 3):
                    clap = rng.standard_normal(int(0.18 * SR)) * np.exp(-np.arange(int(0.18 * SR)) / SR * 22)
                    add(lowpass(clap, 2500), tq, 0.16 * intensity, -0.1)

    mix = np.stack([left, right])
    # A short room: a few feedback-free echoes, slightly different per side.
    for d, g in ((0.031, 0.25), (0.047, 0.2), (0.073, 0.15), (0.113, 0.1)):
        s = int(d * SR)
        mix[0, s:] += g * mix[1, :-s]
        mix[1, s:] += g * mix[0, :-s]
    mix = mix[:, : int(seconds * SR)]
    # Fade in over half a second and out over the closing hold.
    t = np.arange(mix.shape[1]) / SR
    fade = np.minimum(1, t / 0.5) * np.clip((seconds - t) / END_HOLD, 0, 1) ** 1.5
    mix *= fade
    return mix / (np.abs(mix).max() + 1e-9) * 0.8


def write_wav(path: Path, mix: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix.T * 32767).astype("<i2").tobytes())


def mux(video: Path, audio: Path, seconds: float, own_track: bool) -> None:
    out = video.with_suffix(".music.mp4")
    if own_track:
        filters = f"afade=t=in:d=1,afade=t=out:st={max(0, seconds - END_HOLD):.2f}:d={END_HOLD},loudnorm=I=-16:TP=-1.5"
        src = ["-stream_loop", "-1", "-i", str(audio)]
    else:
        filters = "loudnorm=I=-16:TP=-1.5"
        src = ["-i", str(audio)]
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(video), *src, "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-af", filters, "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
                    "-t", f"{seconds:.3f}", "-movflags", "+faststart", str(out)], check=True)
    out.replace(video)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("videos", nargs="+", type=Path)
    parser.add_argument("--track", type=Path, help="use this audio file instead of a synthesized track")
    args = parser.parse_args()
    for video in args.videos:
        seconds = duration(video)
        if args.track:
            mux(video, args.track, seconds, own_track=True)
        else:
            with tempfile.TemporaryDirectory() as tmp:
                wav = Path(tmp) / "music.wav"
                write_wav(wav, song(seconds, video.stem))
                mux(video, wav, seconds, own_track=False)
        print(f"music added: {video} ({seconds:.0f} s)")


if __name__ == "__main__":
    sys.exit(main())
