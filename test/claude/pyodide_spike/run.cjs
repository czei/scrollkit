// Phase-0 spike, WASM half: run the REAL ScrollKit library inside Pyodide
// (CPython compiled to WebAssembly) and hand the rendered pixel buffer to JS —
// exactly the browser data path (Python renders -> JS paints to <canvas>).
//
// Run:  node test/claude/pyodide_spike/run.cjs
const path = require("path");
const fs = require("fs");
const { loadPyodide } = require("pyodide");

const SRC = path.resolve(__dirname, "../../../src");           // repo src/ (the package)
const OUT = path.resolve(__dirname, "../spike_out/frame_pyodide.ppm");

const PY = `
import os, sys
sys.path.insert(0, "/src")
os.environ["SCROLLKIT_HEADLESS"] = "1"   # no pygame in WASM anyway; this skips the surface

import numpy as np
from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.dev.metrics import buffer_from_display, lit_pixels

d = SimulatorDisplay(width=64, height=32)
await d.initialize()
await d.clear()
await d.draw_text("HELLO PYODIDE", x=2, y=16, color=0x00AAFF)
d.display.refresh(minimum_frames_per_second=0)   # real displayio rasterize -> pixel buffer

buf = buffer_from_display(d).copy()
lit = int(lit_pixels(buf))
h, w = int(buf.shape[0]), int(buf.shape[1])
no_pygame = "pygame" not in sys.modules
rgb = buf.tobytes()
(lit, w, h, no_pygame)
`;

(async () => {
  console.log("loading Pyodide (WASM CPython)...");
  const pyodide = await loadPyodide();
  console.log("Pyodide", pyodide.version, "- loading numpy + Pillow...");
  // Pillow: the simulator's displayio OnDiskBitmap emulation imports PIL eagerly.
  await pyodide.loadPackage(["numpy", "Pillow"]);

  // Mount the repo src/ into the WASM filesystem so `import scrollkit` works.
  pyodide.FS.mkdir("/src");
  pyodide.FS.mount(pyodide.FS.filesystems.NODEFS, { root: SRC }, "/src");

  const result = await pyodide.runPythonAsync(PY);
  const [lit, w, h, noPygame] = result.toJs();
  result.destroy();

  // Pull the raw RGB bytes across the Python->JS boundary (canvas-ready bytes).
  const rgbProxy = pyodide.globals.get("rgb");
  const rgb = rgbProxy.toJs();           // Uint8Array, length w*h*3
  rgbProxy.destroy();

  // Verify and write a PPM (raw RGB == what you'd putImageData onto a canvas).
  const expected = w * h * 3;
  const header = Buffer.from(`P6\n${w} ${h}\n255\n`, "ascii");
  fs.writeFileSync(OUT, Buffer.concat([header, Buffer.from(rgb)]));

  console.log("=".repeat(64));
  console.log("PHASE-0 SPIKE (WASM): real ScrollKit ran inside Pyodide");
  console.log("=".repeat(64));
  console.log("pyodide version:        ", pyodide.version);
  console.log("buffer w x h:           ", `${w} x ${h}`);
  console.log("rgb bytes to JS:        ", rgb.length, `(expected ${expected})`);
  console.log("lit pixels:             ", lit);
  console.log("pygame untouched in py: ", noPygame);
  console.log("PPM written:            ", OUT);

  const ok = rgb.length === expected && lit > 0 && noPygame === true;
  console.log("\nRESULT:", ok ? "PASS — real library renders in-browser-class WASM, buffer crosses to JS"
                              : "FAIL");
  if (!ok) process.exit(1);
})().catch((e) => { console.error(e); process.exit(1); });
