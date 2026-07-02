# Copyright (c) 2024-2026 Michael Czeiszperger
"""Desktop-only frame capture + encoding for the display recording API.

The user-facing methods (``start_recording`` / ``save_gif`` / ``save_video`` /
``screenshot``) live on ``UnifiedDisplay`` (and are therefore inherited by
``SimulatorDisplay``); the heavy pygame/Pillow/ffmpeg work lives here so the
RAM-constrained device never loads a byte of it — this module is only ever
imported lazily from inside those methods, on desktop.
"""

from __future__ import annotations


def capture_frame(matrix):
    """Return the matrix's current LED-panel surface as an (H, W, 3) uint8 array,
    or None when pygame/the surface isn't available."""
    try:
        import pygame
    except ImportError:
        return None
    surface = (matrix.get_surface()
               if matrix is not None and hasattr(matrix, "get_surface")
               else None)
    if surface is None:
        return None
    # array3d gives (W, H, 3); transpose to image orientation (H, W, 3).
    return pygame.surfarray.array3d(surface).transpose(1, 0, 2).copy()


def save_surface_png(matrix, path):
    """Save the current LED-panel surface (or the window surface) to ``path``.

    Returns the path on success or None when pygame/no surface is available.
    """
    try:
        import pygame
    except ImportError:
        return None
    surface = None
    if matrix is not None and hasattr(matrix, "get_surface"):
        surface = matrix.get_surface()
    if surface is None and pygame.get_init():
        surface = pygame.display.get_surface()
    if surface is None:
        return None
    try:
        pygame.image.save(surface, path)
        return path
    except (pygame.error, OSError) as e:
        print(f"screenshot failed: {e}")
        return None


def encode_gif(frames, path, *, fps=20, target_width=360, max_colors=48,
               loop=0, frame_step=1, disposal=1):
    """Encode recorded frames to an animated GIF (see ``save_gif`` docstring)."""
    if not frames:
        return None
    try:
        from PIL import Image
    except ImportError:
        print("save_gif failed: Pillow not installed (pip install Pillow)")
        return None

    kept = frames[::max(1, int(frame_step))]
    rgb = []
    for arr in kept:
        img = Image.fromarray(arr, "RGB")
        if target_width and img.width != target_width:
            h = max(1, round(img.height * target_width / img.width))
            img = img.resize((target_width, h), Image.LANCZOS)
        rgb.append(img)

    # One shared palette from a handful of evenly-sampled frames: stable
    # colors across the loop (no per-frame flicker) and a much smaller file.
    sample = rgb[::max(1, len(rgb) // 16)]
    montage = Image.new("RGB", (rgb[0].width, rgb[0].height * len(sample)))
    for i, frame_img in enumerate(sample):
        montage.paste(frame_img, (0, i * rgb[0].height))
    palette = montage.quantize(colors=max_colors, method=Image.MEDIANCUT)
    paletted = [im.quantize(palette=palette) for im in rgb]

    duration = int(round(1000.0 / fps)) * max(1, int(frame_step))
    try:
        # disposal=1 ("do not dispose") leaves the prior frame in place so
        # Pillow can crop each frame to just its changed region — the static
        # LED-panel background is written once, shrinking the file several-fold
        # versus disposal=2 (which restores to background and forces full frames).
        paletted[0].save(path, save_all=True, append_images=paletted[1:],
                         duration=duration, loop=loop, optimize=True,
                         disposal=disposal)
        return path
    except (OSError, ValueError) as e:
        print(f"save_gif failed: {e}")
        return None


def encode_video(frames, path, *, fps=24, target_width=None, crf=20,
                 preset="medium", border=0, border_color=(10, 10, 13)):
    """Encode recorded frames to MP4/H.264 via ffmpeg (see ``save_video``)."""
    import shutil
    import subprocess

    if not frames:
        return None
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("save_video failed: ffmpeg not found (e.g. `brew install ffmpeg`)")
        return None

    h0, w0 = int(frames[0].shape[0]), int(frames[0].shape[1])
    if target_width and int(target_width) != w0:
        out_w = int(target_width)
        out_h = max(1, round(h0 * out_w / w0))
    else:
        out_w, out_h = w0, h0
    out_w -= out_w % 2          # yuv420p needs even dimensions
    out_h -= out_h % 2
    if out_w < 2 or out_h < 2:
        return None
    resize = (out_w, out_h) != (w0, h0)
    if resize:
        try:
            from PIL import Image
        except ImportError:
            print("save_video failed: Pillow needed to resize (pip install Pillow)")
            return None

    vf = []
    if border and int(border) > 0:
        b = int(border) - int(border) % 2   # keep padded dims even for yuv420p
        if b > 0:
            bc = border_color
            vf = ["-vf", "pad=iw+%d:ih+%d:%d:%d:color=0x%02X%02X%02X"
                  % (2 * b, 2 * b, b, b, int(bc[0]), int(bc[1]), int(bc[2]))]

    cmd = ([ffmpeg, "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", "%dx%d" % (out_w, out_h), "-r", str(int(fps)), "-i", "-",
            "-an"] + vf
           + ["-c:v", "libx264", "-pix_fmt", "yuv420p",
              "-crf", str(int(crf)), "-preset", str(preset),
              "-movflags", "+faststart", path])
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    except OSError as e:
        print("save_video failed: could not launch ffmpeg (%r)" % (e,))
        return None
    try:
        for arr in frames:
            if resize:
                arr_bytes = Image.fromarray(arr, "RGB").resize(
                    (out_w, out_h), Image.LANCZOS).tobytes()
            else:
                arr_bytes = arr.tobytes()
            proc.stdin.write(arr_bytes)
        proc.stdin.close()
        rc = proc.wait()
    except (OSError, ValueError) as e:
        print("save_video failed: %r" % (e,))
        return None
    if rc != 0:
        print("save_video failed: ffmpeg exited %s" % rc)
        return None
    return path
