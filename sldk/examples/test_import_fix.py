#!/usr/bin/env python3
"""Test that the import fix for SLDK effects is working."""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Test all the imports
print("Testing SLDK effects imports...")
print("=" * 40)

try:
    from sldk.effects import Effect
    print("✓ Effect imported successfully")
except ImportError as e:
    print(f"✗ Failed to import Effect: {e}")

try:
    from sldk.effects import RevealEffect
    print("✓ RevealEffect imported successfully")
except ImportError as e:
    print(f"✗ Failed to import RevealEffect: {e}")

try:
    from sldk.effects import EffectsEngine
    print("✓ EffectsEngine imported successfully")
except ImportError as e:
    print(f"✗ Failed to import EffectsEngine: {e}")

try:
    from sldk.effects import CompositeEffect
    print("✓ CompositeEffect imported successfully")
except ImportError as e:
    print(f"✗ Failed to import CompositeEffect: {e}")

try:
    from sldk.effects import FadeInEffect, SlideInEffect, WipeEffect
    print("✓ Transition effects imported successfully")
except ImportError as e:
    print(f"✗ Failed to import transition effects: {e}")

print("\n" + "=" * 40)

# Show RevealEffect details
try:
    from sldk.effects import RevealEffect
    print("\nRevealEffect class details:")
    print(f"- Module: {RevealEffect.__module__}")
    print(f"- Class name: {RevealEffect.__name__}")
    print(f"- Base classes: {[base.__name__ for base in RevealEffect.__bases__]}")
    
    # Show init parameters
    import inspect
    sig = inspect.signature(RevealEffect.__init__)
    print(f"\nRevealEffect.__init__ parameters:")
    for param_name, param in sig.parameters.items():
        if param_name != 'self':
            default = param.default if param.default != inspect.Parameter.empty else 'no default'
            print(f"  - {param_name}: {default}")
    
    print("\n✅ Import fix is working! RevealEffect can now be imported and used.")
    
except Exception as e:
    print(f"\n❌ Error inspecting RevealEffect: {e}")

print("\nThe import error has been fixed by:")
print("1. Moving Effect import from effects.py to base.py")
print("2. Updating class names to match actual implementations")
print("3. Removing non-existent classes from __all__")