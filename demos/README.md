# ScrollKit Demos

See ScrollKit running on a simulated LED matrix — no hardware needed.

### 1. Install the simulator

```bash
pip install pygame
```

### 2. Run a demo (from the repo root)

```bash
PYTHONPATH=src python demos/easy/hello_world.py
```

A window opens with scrolling text. Press `Ctrl-C` (or close the window) to stop.

### The demos

| Preview | Run this | What you'll see | Needs internet? |
|---------|----------|-----------------|-----------------|
| <img src="../docs/assets/demos/hello_world.gif" width="220"> | `demos/easy/hello_world.py` | Scrolling text | No |
| <img src="../docs/assets/demos/colors.gif" width="220"> | `demos/easy/colors.py` | A word cycling through colors | No |
| <img src="../docs/assets/demos/clock.gif" width="220"> | `demos/easy/clock.py` | A digital clock | No |
| <img src="../docs/assets/demos/rainbow.gif" width="220"> | `demos/medium/rainbow.py` | Big-font rainbow scroll — tall letters that fill the display height | No |
| <img src="../docs/assets/demos/temperature.gif" width="220"> | `demos/medium/temperature.py` | Live temperature | Yes |
| <img src="../docs/assets/demos/crypto_dashboard.gif" width="220"> | `demos/hard/crypto_dashboard.py` | Animated multi-row dashboard: rainbow intro, live crypto + weather, scrolling ticker | Yes |

Start with `easy/hello_world.py`. The `hard` one is the showpiece. All thirteen
demos, with animated previews, are in the **[Demo Gallery](../docs/demos.md)**.

> Previews are generated from the simulator with `python demos/render_gifs.py`.

When you're ready for more, the tutorials in `docs/tutorials/` walk through the
easy/medium/hard examples line by line.
