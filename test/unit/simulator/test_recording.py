"""Test simulator recording: GIFs and the MP4/ffmpeg sibling."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless pygame

import shutil
import subprocess

import pytest

pygame = pytest.importorskip("pygame")
Image = pytest.importorskip("PIL.Image")

from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.display._recording import encode_video


class _FakeStdin:
    def __init__(self, fail=False):
        self.data = bytearray()
        self.closed = False
        self.fail = fail

    def write(self, data):
        if self.fail:
            raise OSError("broken pipe")
        self.data.extend(data)

    def close(self):
        self.closed = True


class _FakeProcess:
    def __init__(self, returncode=0, fail_write=False):
        self.stdin = _FakeStdin(fail=fail_write)
        self.returncode = returncode

    def wait(self):
        return self.returncode


@pytest.mark.asyncio
async def test_save_gif_writes_a_multiframe_animation(tmp_path):
    display = SimulatorDisplay(width=64, height=32)
    await display.initialize()

    display.start_recording()
    assert display.is_recording
    # Move the text so successive captured frames actually differ.
    for i in range(6):
        await display.clear()
        await display.draw_text("HI", 5 + i * 5, 12, 0x00AAFF)
        await display.show()

    out = str(tmp_path / "demo.gif")
    result = display.save_gif(out, frame_step=1)

    assert result == out
    assert os.path.exists(out) and os.path.getsize(out) > 0
    assert not display.is_recording          # save stops/clears the recording
    with Image.open(out) as im:
        assert getattr(im, "n_frames", 1) > 1  # it's an animation, not one frame


@pytest.mark.asyncio
async def test_save_gif_with_nothing_recorded_returns_none(tmp_path):
    display = SimulatorDisplay(width=64, height=32)
    await display.initialize()
    # No start_recording(): there is nothing to save, and that's not an error.
    assert display.save_gif(str(tmp_path / "empty.gif")) is None


def test_encode_video_returns_none_without_frames_or_ffmpeg(monkeypatch, tmp_path):
    import numpy as np

    assert encode_video([], str(tmp_path / "empty.mp4")) is None
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert encode_video([np.zeros((2, 2, 3), dtype=np.uint8)],
                        str(tmp_path / "missing.mp4")) is None


def test_encode_video_pipes_rgb_frames_to_expected_ffmpeg_command(monkeypatch, tmp_path):
    import numpy as np

    proc = _FakeProcess()
    commands = []
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, stdin: (
        commands.append((cmd, stdin)) or proc))
    frames = [np.full((4, 6, 3), 17, dtype=np.uint8),
              np.full((4, 6, 3), 23, dtype=np.uint8)]

    out = str(tmp_path / "movie.mp4")
    assert encode_video(frames, out, fps=12, crf=19, preset="fast",
                        border=3, border_color=(1, 2, 3)) == out
    cmd, stdin = commands[0]
    assert stdin is subprocess.PIPE
    start = cmd.index("-s")
    assert cmd[start:start + 4] == ["-s", "6x4", "-r", "12"]
    assert "pad=iw+4:ih+4:2:2:color=0x010203" in cmd
    assert "libx264" in cmd and "yuv420p" in cmd
    assert bytes(proc.stdin.data) == b"".join(frame.tobytes() for frame in frames)
    assert proc.stdin.closed


def test_encode_video_handles_process_failures(monkeypatch, tmp_path):
    import numpy as np

    frames = [np.zeros((2, 2, 3), dtype=np.uint8)]
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: _FakeProcess(1))
    assert encode_video(frames, str(tmp_path / "failed.mp4")) is None

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: _FakeProcess(fail_write=True))
    assert encode_video(frames, str(tmp_path / "broken.mp4")) is None


@pytest.mark.asyncio
async def test_save_video_consumes_recording_and_forwards_options(monkeypatch, tmp_path):
    display = SimulatorDisplay(width=64, height=32)
    await display.initialize()
    display.start_recording()
    await display.clear()
    await display.draw_text("MP4", 2, 12, 0x00AAFF)
    await display.show()

    captured = {}

    def fake_encode(frames, path, **opts):
        captured["frames"] = frames
        captured["path"] = path
        captured["opts"] = opts
        return path

    monkeypatch.setattr("scrollkit.display._recording.encode_video", fake_encode)
    out = str(tmp_path / "forwarded.mp4")
    assert display.save_video(out, fps=15, target_width=320, border=12) == out
    assert not display.is_recording and captured["frames"]
    assert captured["path"] == out
    assert captured["opts"] == {"fps": 15, "target_width": 320, "crf": 20,
                                "preset": "medium", "border": 12,
                                "border_color": (10, 10, 13)}


@pytest.mark.ffmpeg
def test_encode_video_real_ffmpeg_smoke(tmp_path):
    """Encode the public MP4 path once when CI provides ffmpeg + ffprobe."""
    import numpy as np

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg and ffprobe are required for the MP4 smoke test")
    frames = [np.full((32, 64, 3), color, dtype=np.uint8)
              for color in (0, 90, 180, 255)]
    out = tmp_path / "smoke.mp4"
    assert encode_video(frames, str(out), fps=12, border=3) == str(out)
    assert out.exists() and out.stat().st_size > 0

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,pix_fmt,width,height",
         "-of", "default=noprint_wrappers=1", str(out)],
        check=True, capture_output=True, text=True)
    values = dict(line.split("=", 1) for line in probe.stdout.splitlines())
    assert values == {"codec_name": "h264", "width": "68", "height": "36",
                      "pix_fmt": "yuv420p"}
