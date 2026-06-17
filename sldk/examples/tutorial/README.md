# SLDK Tutorial Examples

Welcome to the SLDK (Simplified LED Display Kit) tutorial examples! These examples will guide you from your first "Hello World" to creating dynamic LED matrix displays.

## Prerequisites

- Python 3.7+ or CircuitPython 8.x/9.x
- SLDK library installed (`pip install sldk` or copy to CircuitPython device)
- Optional: LED matrix hardware (examples work in terminal simulator too!)

## Running the Examples

### On Your Computer (Terminal Simulator)

```bash
# Run any example directly
python 01_hello_minimal.py

# Or with explicit Python version
python3 01_hello_minimal.py
```

### On CircuitPython Device

1. Copy the SLDK library to your device's `lib/` folder
2. Copy the example file to the root of your CIRCUITPY drive
3. Rename it to `code.py` or import it from your `code.py`
4. The display will update automatically!

### On Raspberry Pi with LED Matrix

```bash
# Run with sudo for GPIO access
sudo python3 01_hello_minimal.py
```

## Example Progression

1. **01_hello_minimal.py** - Your first SLDK app (2 lines!)
   - Absolute minimum code needed
   - Shows "Hello, World!" in default color

2. **02_colors_minimal.py** - Add some color
   - Demonstrates color options
   - Shows how to use built-in color constants

3. **03_clock_minimal.py** - Dynamic content
   - Creates a simple digital clock
   - Introduces the update loop concept

4. **04_basic_patterns.py** - Common display patterns
   - Scrolling text
   - Color cycling
   - Simple animations

5. **05_progressive_demo.py** - All concepts in one file
   - Commented sections for different complexity levels
   - Uncomment sections as you learn
   - Great for experimenting!

## Troubleshooting

### "No module named 'sldk'"
- Make sure SLDK is installed: `pip install sldk`
- For CircuitPython: Copy the `sldk` folder to the `lib/` directory

### Display shows nothing
- Check your LED matrix connections (hardware only)
- Verify power supply is adequate (hardware only)
- Try running in terminal simulator first to verify code

### Colors look wrong
- Different LED matrices may have different color orders (RGB vs GRB)
- Adjust color values or use the color configuration options

### Text is cut off
- The default 6x8 font may not fit all text
- Try shorter messages or implement scrolling (see example 04)

### Memory errors on CircuitPython
- SLDK automatically adjusts to available memory
- Try the minimal examples first
- Close other running programs

## Next Steps

After completing these tutorials:
- Explore the `advanced/` examples for complex animations
- Check out `hardware/` examples for specific LED matrix models
- Read the SLDK API documentation for all available features
- Join our community forum for help and to share your creations!

## Tips for Learning

1. Start with example 01 and run it successfully before moving on
2. Modify each example - change colors, text, timing
3. Combine concepts from different examples
4. Use example 05 as a playground for experimentation
5. Don't be afraid to break things - that's how you learn!

Happy LED programming! 🚀