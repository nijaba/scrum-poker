#!/usr/bin/env python3
"""Add the voice-over to the tour video: docs/video/tour.webm becomes docs/video/tour.mp4.

Each row of the cue table in docs/video/tour-voiceover.md is spoken with macOS's `say` and
placed at its time. The script also saves a poster frame, docs/video/tour-poster.png, for the
README. It needs macOS (for `say`) and an ffmpeg with libx264 and AAC: one on the PATH, the
one named by $FFMPEG, or the one the `imageio-ffmpeg` package brings.

    python scripts/tour_video.py        # the silent recording, when a screen changed
    python scripts/tour_voiceover.py    # the narrated MP4
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "docs" / "video"
SILENT = FOLDER / "tour.webm"
NARRATED = FOLDER / "tour.mp4"
POSTER = FOLDER / "tour-poster.png"
SCRIPT = FOLDER / "tour-voiceover.md"
VOICE = "Samantha"
RATE = 160  # words a minute
POSTER_AT = 18.5  # seconds: the cards revealed, with the final points outlined
CUE = re.compile(r"^\| (\d+):(\d+(?:\.\d+)?) \| [^|]+ \| ([^|]+) \|$")


def cues() -> list[tuple[float, str]]:
    found = []
    for line in SCRIPT.read_text().splitlines():
        m = CUE.match(line.strip())
        if m:
            found.append((int(m[1]) * 60 + float(m[2]), m[3].strip()))
    if not found:
        raise SystemExit(f"no cues found in {SCRIPT.relative_to(ROOT)}")
    return found


def ffmpeg() -> str:
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise SystemExit(
            "needs ffmpeg: install it, set FFMPEG, or pip install imageio-ffmpeg"
        ) from None


def length(path: Path) -> float:
    out = subprocess.run(["afinfo", str(path)], capture_output=True, text=True, check=True).stdout
    return float(re.search(r"estimated duration: ([\d.]+)", out)[1])


def main() -> None:
    if not SILENT.is_file():
        raise SystemExit("record the video first: python scripts/tour_video.py")
    if not shutil.which("say"):
        raise SystemExit("needs macOS's say command")
    exe = ffmpeg()
    lines = cues()
    with tempfile.TemporaryDirectory() as tmp:
        clips = []
        for i, (at, text) in enumerate(lines):
            clip = Path(tmp) / f"line{i}.aiff"
            subprocess.run(["say", "-v", VOICE, "-r", str(RATE), "-o", str(clip), text], check=True)
            ends = at + length(clip)
            following = lines[i + 1][0] if i + 1 < len(lines) else None
            late = following is not None and ends > following
            note = "  (runs into the next cue)" if late else ""
            print(f"{at:5.1f}s to {ends:5.1f}s  {text}{note}")
            clips.append((at, clip))

        inputs = ["-i", str(SILENT)]
        chains = []
        for i, (at, clip) in enumerate(clips, start=1):
            inputs += ["-i", str(clip)]
            ms = int(at * 1000)
            chains.append(f"[{i}:a]aresample=48000,adelay={ms}:all=1[a{i}]")
        mix = "".join(f"[a{i}]" for i in range(1, len(clips) + 1))
        chains.append(f"{mix}amix=inputs={len(clips)}:normalize=0,apad[voice]")
        subprocess.run(
            [exe, "-y", "-loglevel", "error", *inputs]
            + ["-filter_complex", ";".join(chains), "-map", "0:v", "-map", "[voice]"]
            + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24", "-preset", "slow"]
            + ["-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart"]
            + [str(NARRATED)],
            check=True,
        )
    subprocess.run(
        [exe, "-y", "-loglevel", "error", "-ss", str(POSTER_AT), "-i", str(SILENT)]
        + ["-frames:v", "1", str(POSTER)],
        check=True,
    )
    print(f"wrote {NARRATED.relative_to(ROOT)} and {POSTER.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
