"""Scratch: run the showcase reel on a connected MatrixPortal S3 via the raw REPL.

Interrupts whatever is running (ThemeParkWaits), releases the existing displays,
then drives a BOUNDED number of reel frames on the real panel and reports
init/render success + free RAM. Non-destructive: imports the already-copied
/showcase_reel.py; never edits code.py/boot.py.

The reel is self-driving (setup() runs the show and never returns), so the
bound is applied by wrapping the app's per-frame presenter: after N presented
frames it clears ``app.running``, which every act checks, and setup() exits.

    python test/claude/_run_showcase_device.py [frames]
"""

import sys

from cpy_repl import run_on_device

# args: frames [sleep_ms is inherent — the reel sleeps 0.05 per frame itself]
FRAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 1800

CODE = """
import gc, traceback
import displayio
displayio.release_displays()          # free the matrix the running app created
gc.collect()
print("MEM_START", gc.mem_free())
try:
    import asyncio
    import showcase_reel
    async def main():
        app = showcase_reel.ShowcaseReelApp()
        app.display = await app.create_display()
        await app.display.initialize()
        app.running = True
        gc.collect(); print("INIT_OK mem", gc.mem_free())
        orig_frame = app._frame
        state = {"n": 0}
        async def bounded_frame():
            ok = await orig_frame()
            state["n"] += 1
            if state["n"] %% 50 == 0:
                gc.collect(); print("frame", state["n"], "mem", gc.mem_free())
            if state["n"] >= %d:
                app.running = False           # acts check this every frame
            return ok
        app._frame = bounded_frame
        await app.setup()                     # returns once running goes False
        gc.collect(); print("RENDER_OK frames", state["n"], "mem", gc.mem_free())
    asyncio.run(main())
except Exception:
    traceback.print_exc()
print("PROBE_DONE")
""" % FRAMES


if __name__ == "__main__":
    out = run_on_device(CODE, exec_timeout=600.0)
    print(out)
