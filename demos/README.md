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

| Run this | What you'll see | Needs internet? |
|----------|-----------------|-----------------|
| `demos/easy/hello_world.py` | Scrolling text | No |
| `demos/easy/colors.py` | A word cycling through colors | No |
| `demos/easy/clock.py` | A digital clock | No |
| `demos/medium/rainbow.py` | Big-font rainbow scroll — tall letters that fill the display height | No |
| `demos/medium/temperature.py` | Live temperature | Yes |
| `demos/hard/crypto_dashboard.py` | Animated multi-row dashboard: rainbow intro, live crypto + weather, scrolling ticker | Yes |

Start with `easy/hello_world.py`. The `hard` one is the showpiece.

When you're ready for more, the tutorials in `docs/tutorials/` walk through the
easy/medium/hard examples line by line.
