# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL: Never Modify boot.py or code.py AND Never Add Files to Root Directory
**⚠️ IMPORTANT: The files `boot.py` and `code.py` in the root directory are FIXED and must NEVER be modified.**
**⚠️ CRITICAL: NO new Python files should EVER be added to the root CircuitPython directory.**

### Root Directory Restrictions:
- **NEVER modify** `boot.py` or `code.py` - they are frozen from release1.9
- **NEVER add** any new `.py` files to the root directory
- **NEVER create** new modules in the root - ALL code must go in `/src`
- The OTA update system can ONLY update files in the `/src` directory
- Any files outside `/src` cannot be updated via OTA and will break the update mechanism

### Required Structure:
- `code.py` contains only: `import src.themeparkwaits`
- All application logic MUST be in `/src` directory or subdirectories
- The bridge module `src/themeparkwaits.py` handles the import chain to the main application
- Entry point is now `src/main.py` (not `theme_park_main.py` in root)

## Build Commands
* `make copy_to_circuitpy` - Deploy to MatrixPortal S3 device (runs lint check first)
* `make copy_to_circuitpy-no-lint` - Deploy without lint check (use with caution)
* `make release` - Copy files to release archive

## Linting
* `make lint` - Run comprehensive linting with auto-fix (uses ruff)
* `make lint-errors` - Check for critical errors only (undefined names, syntax errors)
* `make install-lint-deps` - Install linting dependencies (ruff)
* Note: `make copy_to_circuitpy` automatically runs `lint-errors` to catch critical issues before deployment

## Testing
* Run all tests: `make test-all` or `python -m pytest`
* Run unit tests only: `make test-unit` or `python -m pytest test/unit -v`
* Run legacy tests: `make test-legacy` or `python -m pytest test/test-suite.py -v`
* Run a single test: `python -m pytest test/unit/path/to/test_file.py::TestClass::test_method_name -v`
* Generate test coverage report: `make test-coverage` (requires pytest-cov)

### Test Organization
* Unit tests: `test/unit/` - organized by module (models, network, utils, etc.)
* Integration tests: `test/integration/` - tests for multiple components
* Legacy tests: `test/test-suite.py` - original test suite
* Test fixtures: `test/fixtures/` - test data files
* Helpers: `test/helpers.py` - testing utilities

### Test Tips
* Writing tests is difficult because CircuitPython is a subset of MicroPython, and many calls won't work when run on a computer. Also, the code that runs on the board expects hardware to be there.
* Use MagicMock() to stub out hardware component calls
* Use the MockHardwareContext from helpers.py when testing code that requires multiple hardware components
* Test fixtures in conftest.py provide access to common test data

## Code Style
* Think hard about how to find the root cause of problems. DO NOT cover up issues such as the lack of data.
* If there are significant details or questions about what is intended ask me for more details before doing anything.
* **Linting**: ALWAYS run `make lint-errors` before deploying to CircuitPython to catch undefined names, syntax errors, and other critical issues
* **Unit Tests**: ALWAYS run unit tests after ANY code changes using `make test-unit` or `python -m pytest test/unit -v`. If tests fail, iterate and fix the issues until all tests pass. NEVER commit or consider a change complete until all unit tests are passing.
* **Imports**: Group by stdlib, third-party (Adafruit), then project modules
* **Classes**: PascalCase (e.g., `ThemeParkList`)
* **Functions/Variables**: snake_case (e.g., `get_park_by_id`, `park_list`)
* **Constants**: UPPERCASE (e.g., `REQUIRED_MESSAGE`)
* **Error Handling**: Use try/except blocks with specific exceptions
* **Logging**: Use `ErrorHandler` class for centralized error logging
* **Documentation**: Use docstrings for classes and methods
* **Documentation**: ALL documentation files, plans, recommendations, and design documents MUST go in the `plans/` folder
* **Testing**: Temporary test programs to solve problems should be created in the directory test/claude
* **Hardware Abstraction**: Include fallbacks when hardware components aren't available

## CircuitPython Development

### CRITICAL: CircuitPython Compatibility Requirements
**⚠️ BEFORE using ANY Python standard library feature, exception, or module:**
1. **CHECK** if it exists in CircuitPython by consulting the [CircuitPython API documentation](https://docs.circuitpython.org/en/latest/docs/library/index.html)
2. **VERIFY** compatibility with CircuitPython 8.x/9.x (not just MicroPython)
3. **TEST** with actual imports in the CircuitPython REPL when possible

### Common CircuitPython Incompatibilities to Avoid:
| Standard Python | CircuitPython Alternative | Notes |
|-----------------|---------------------------|-------|
| `json.JSONDecodeError` | `ValueError` | CircuitPython's json.loads() raises ValueError for invalid JSON |
| `FileNotFoundError` | `OSError` | CircuitPython only has OSError, not the specific subclasses |
| `pathlib.Path` | `os.path` operations | pathlib not available in CircuitPython |
| `urllib.parse` | Manual string parsing | urllib module not available |
| `threading` | `asyncio` | Only cooperative multitasking available |
| `subprocess` | Not available | Cannot spawn processes |
| `typing` module | Remove type hints | Type hints should be in comments or removed |
| `enum.auto()` | Explicit values | auto() not available in CircuitPython's enum |
| `f-strings with =` | Regular f-strings | f"{var=}" syntax not supported |
| `match/case` | `if/elif` | Pattern matching not available |

### Required Compatibility Patterns:
```python
# ❌ WRONG - Standard Python only
try:
    data = json.loads(response)
except json.JSONDecodeError:
    pass

# ✅ CORRECT - CircuitPython compatible
try:
    data = json.loads(response)
except ValueError:  # CircuitPython uses ValueError
    pass

# ❌ WRONG - Standard Python only
except FileNotFoundError:
    pass

# ✅ CORRECT - CircuitPython compatible  
except OSError:  # CircuitPython only has OSError
    pass
```

### CRITICAL: There should be only one web user interface for both the dev and CircuitPython execution.
### CRITICAL: There should be only one LED display for both the dev and CircuitPython execution.
**⚠️ IMPORTANT: If the LED display in the dev environment doesn't match the reported behavior of CircuitPython, adjust the LED simulator code, not the shared display code. NO EXCEPTIONS.**

### CRITICAL: Thread Safety - Web Server Must Never Modify Message Queue
**⚠️ IMPORTANT: The web server runs in a separate context/thread and must NEVER directly modify the message queue data structures.**

Thread safety rules:
1. **NEVER** call `message_queue.init()` from the web server
2. **NEVER** directly modify any message queue data from the web server
3. **NEVER** call methods that modify the message queue state
4. The message queue is owned by the main display loop thread
5. Only the main thread that runs the display loop can safely modify message queue data
6. Web server should only:
   - Update settings that the main thread reads
   - Set flags that the main thread checks
   - Never directly manipulate display or queue state

### CircuitPython Development Guidelines:
* Instructions for the wait times API are at:  https://queue-times.com/pages/api
* CircuitPython uses its own http library adafruit_requests, and all HTTP calls are synchronous.
* All changes should be made to work on both the MatrixPortal S3 hardware and in the simulated dev environment. 
* Remember that CircuitPython 8.x/9.x is a fork of MicroPython, and the standard libraries either aren't available or have versions specific to CircuitPython
* CircuitPython devices are very slow and use cooperative multitasking using asyncio, not multithreading. This is made more difficult because the CircuitPython HTTP library is synchronous, so background tasks like scrolling stop when HTTP calls are made.
* **IMPORTANT**: On the CIRCUITPY drive, libraries are stored in `src/lib/` not just `lib/`. When importing Adafruit libraries, you may need to add `/src/lib` to `sys.path` first.
* When in doubt about CircuitPython compatibility, check:
  - [CircuitPython Core Modules](https://docs.circuitpython.org/en/latest/docs/library/index.html)
  - [CircuitPython vs MicroPython differences](https://docs.circuitpython.org/en/latest/docs/design_guide.html)
  - Test imports in REPL: `import module_name` to verify availability
* Support both running on actual hardware and testing in standard Python environment
* Test functionality in isolation before deploying to hardware
* Ensure tests properly mock CircuitPython-specific modules
* Separate functionality that could be applied to any CircuitPython project from the specific functionality of this project. The ultimate goal is to refactor into an open source library.

### CircuitPython-Safe Module Usage:
```python
# File operations
import os
# ✅ os.listdir(), os.stat(), os.remove() - available
# ❌ os.path.exists() - use try/except OSError instead

# JSON handling
import json
# ✅ json.loads(), json.dumps() - available
# ❌ json.JSONDecodeError - use ValueError instead

# Time operations  
import time
# ✅ time.sleep(), time.monotonic() - available
# ❌ time.time() - use time.monotonic() instead

# Async operations
import asyncio
# ✅ asyncio.create_task(), asyncio.gather() - available
# ❌ asyncio.run() - use asyncio.run() only at top level

# Random numbers
import random
# ✅ random.randint(), random.choice() - available
# ❌ random.choices() - not available in CircuitPython

# Regular expressions
import re
# ✅ re.search(), re.match(), re.findall() - available
# ❌ re.Pattern type hints - not available
```

### Before Adding New Code:
1. **Run lint check**: `make lint-errors` to catch undefined names
2. **Check CircuitPython docs**: Verify module/exception exists
3. **Test imports**: Try `import module_name` in CircuitPython REPL
4. **Use try/except**: Wrap imports that might fail in dev vs hardware

## Using the think tool
Before taking any action or responding to the user after receiving tool results, use the think tool as a scratchpad to:
- List the specific rules that apply to the current request
- Check if all required information is collected
- Verify that the planned action complies with all policies
- Iterate over tool results for correctness

Here are some examples of what to iterate over inside the think tool:
<think_tool_example_1>
User wants to cancel flight ABC123
- Need to verify: user ID, reservation ID, reason
- Check cancellation rules:
    * Is it within 24h of booking?
    * If not, check ticket class and insurance
- Verify no segments flown or are in the past
- Plan: collect missing info, verify rules, get confirmation
  </think_tool_example_1>

<think_tool_example_2>
User wants to book 3 tickets to NYC with 2 checked bags each
- Need user ID to check:
    * Membership tier for baggage allowance
    * Which payments methods exist in profile
- Baggage calculation:
    * Economy class × 3 passengers
    * If regular member: 1 free bag each → 3 extra bags = $150
    * If silver member: 2 free bags each → 0 extra bags = $0
    * If gold member: 3 free bags each → 0 extra bags = $0
- Payment rules to verify:
    * Max 1 travel certificate, 1 credit card, 3 gift cards
    * All payment methods must be in profile
    * Travel certificate remainder goes to waste
- Plan:
1. Get user ID
2. Verify membership level for bag fees
3. Check which payment methods in profile and if their combination is allowed
4. Calculate total: ticket price + any bag fees
5. Get explicit confirmation for booking
   </think_tool_example_2>
