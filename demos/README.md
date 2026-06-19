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
| `demos/medium/temperature.py` | Live temperature | Yes |
| `demos/hard/crypto_dashboard.py` | Web UI + effects + live prices | Yes |

That's it. When you're ready for more, the tutorials in `docs/tutorials/` walk
through each demo line by line.
