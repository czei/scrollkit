"""Scratch: run the showcase reel on a connected MatrixPortal S3 via the raw REPL.

Interrupts whatever is running (ThemeParkWaits), releases the existing displays,
then drives a BOUNDED number of showcase frames on the real panel and reports
init/render success + free RAM. Non-destructive: imports the already-copied
/showcase.py; never edits code.py/boot.py.

    python test/claude/_run_showcase_device.py [frames]
"""

import sys

from cpy_repl import run_on_device

# args: frames [sleep_ms]   (sleep_ms=50 -> ~20 fps, the real app-loop cadence;
#                            sleep_ms=0  -> flat-out, for stress/measurement only)
FRAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 1800
SLEEP_MS = int(sys.argv[2]) if len(sys.argv) > 2 else 50
SLEEP_S = SLEEP_MS / 1000.0

CODE = """
import gc, traceback
import displayio
displayio.release_displays()          # free the matrix the running app created
gc.collect()
print("MEM_START", gc.mem_free())
try:
    import asyncio
    import showcase
    async def main():
        app = showcase.ShowcaseApp()
        app.display = await app.create_display()
        await app.display.initialize()
        await app.setup()
        content = await app.prepare_display_content()
        d = app.display
        gc.collect(); print("INIT_OK mem", gc.mem_free())
        for i in range(%d):
            await d.clear()
            await content.render(d)
            await d.show()
            await asyncio.sleep(%f)        # match the real ~20 fps app-loop pacing
            if i %% 50 == 0:
                gc.collect(); print("frame", i, "scene", content._i, "mem", gc.mem_free())
        gc.collect(); print("RENDER_OK frames %d mem", gc.mem_free())
    asyncio.run(main())
except Exception:
    traceback.print_exc()
print("PROBE_DONE")
""" % (FRAMES, SLEEP_S, FRAMES)


if __name__ == "__main__":
    out = run_on_device(CODE, exec_timeout=300.0)
    print(out)
