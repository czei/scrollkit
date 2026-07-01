# ScrollKit library — build, test, lint, and device deploy.

SRC_DIR := src
# Mounted CIRCUITPY drive (override on the command line if it mounts elsewhere).
CIRCUITPY := /Volumes/CIRCUITPY

PYTHON := python
PIP := python -m pip
# PYTHONSAFEPATH keeps the CWD off sys.path; PYTHONPATH=src exposes `scrollkit`.
PYTEST := PYTHONSAFEPATH=1 PYTHONPATH=$(SRC_DIR) $(PYTHON) -m pytest

.PHONY: all test test-unit test-all test-coverage lint lint-errors test-with-lint \
        format clean mpy copy-to-circuitpy hero docs-gifs docs-reference deploy-docs \
        install-test-deps install-dev-deps install-lint-deps

all: test

# --- Testing ---------------------------------------------------------------
test: test-unit

test-unit:
	$(PYTEST) test/unit -v

test-all:
	$(PYTEST)

test-coverage:
	$(PYTEST) --cov=scrollkit --cov-report=term --cov-report=html

# --- Linting / formatting --------------------------------------------------
lint:
	@echo "Running Python linter (ruff)..."
	$(PYTHON) -m ruff check $(SRC_DIR) test/ --fix
	@echo "Linting complete!"

lint-errors:
	@echo "Checking for critical errors..."
	$(PYTHON) -m ruff check $(SRC_DIR) --select=E9,F63,F7,F82,F821 --no-fix
	@echo "Critical error check complete!"

test-with-lint: lint-errors test

format:
	$(PYTHON) -m ruff format $(SRC_DIR) test/

# --- Dependencies ----------------------------------------------------------
install-test-deps:
	$(PIP) install pytest pytest-asyncio pytest-cov

install-dev-deps:
	$(PIP) install pygame pillow numpy

install-lint-deps:
	$(PIP) install ruff

# --- Device deploy ---------------------------------------------------------
# Copy the library to a connected MatrixPortal S3 (CIRCUITPY/lib/scrollkit).
# An application's own code.py/boot.py live in the app, not in this repo.
copy-to-circuitpy: lint-errors
	@test -d "$(CIRCUITPY)" || { echo "CIRCUITPY not mounted at $(CIRCUITPY)"; exit 1; }
	rsync -av --update --progress \
		--exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' \
		$(SRC_DIR)/scrollkit/ "$(CIRCUITPY)/lib/scrollkit/"

# Cross-compile scrollkit to .mpy (smaller RAM + faster boot on device).
# Requires mpy-cross matching your CircuitPython version:  pip install mpy-cross
MPY_CROSS := mpy-cross
mpy:
	@command -v $(MPY_CROSS) >/dev/null 2>&1 || { echo "mpy-cross not found. Install one matching your CircuitPython version: pip install mpy-cross"; exit 1; }
	@echo "Compiling src/scrollkit -> build/scrollkit (.mpy)..."
	@rm -rf build/scrollkit
	@find src/scrollkit -name '*.py' | while read f; do \
		out="build/$${f#src/}"; out="$${out%.py}.mpy"; \
		mkdir -p "$$(dirname "$$out")"; \
		$(MPY_CROSS) "$$f" -o "$$out" || exit 1; \
	done
	@echo "Done -> build/scrollkit/. Copy it to the device (e.g. CIRCUITPY/lib/scrollkit)."

# --- Docs assets -----------------------------------------------------------
# Render the scrollkit.dev landing-page hero video (-> docs/assets/video/).
hero:
	PYTHONSAFEPATH=1 PYTHONPATH=$(SRC_DIR) $(PYTHON) demos/render_hero.py

# Regenerate the Demo Gallery GIF previews (-> docs/assets/demos/).
# Pass demo names to render only some, e.g.:  make docs-gifs ARGS="hello_world showcase"
docs-gifs:
	PYTHONSAFEPATH=1 PYTHONPATH=$(SRC_DIR) $(PYTHON) demos/render_gifs.py $(ARGS)

# Regenerate the per-API Visual Reference samples (-> docs/assets/reference/):
# one isolated GIF/PNG for every transition, scroller, palette effect, splash,
# particle, gradient direction and colour ramp. Pass slugs to render only some,
# e.g.:  make docs-reference ARGS="iris-snap wave-rider"
docs-reference:
	PYTHONSAFEPATH=1 PYTHONPATH=$(SRC_DIR) $(PYTHON) demos/render_reference.py $(ARGS)

# Build and publish the docs to https://scrollkit.dev (static MkDocs on the
# shared EC2 host). The upload step (host/key/docroot) lives in the gitignored
# deployment skill so those infra details stay out of this public repo; install
# that skill to deploy. See .claude/skills/deployment/SKILL.md.
DEPLOY_DOCS_SCRIPT := .claude/skills/deployment/deploy-scrollkit-docs.sh
deploy-docs:
	mkdocs build
	@test -x "$(DEPLOY_DOCS_SCRIPT)" || { echo "Missing $(DEPLOY_DOCS_SCRIPT) — install the 'deployment' skill to deploy."; exit 1; }
	@"$(DEPLOY_DOCS_SCRIPT)"

# --- Housekeeping ----------------------------------------------------------
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".DS_Store" -delete
	rm -rf .pytest_cache htmlcov .coverage build
