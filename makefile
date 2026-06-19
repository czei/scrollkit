# Destination directory
RELEASE_DESTDIR := ../themeparkwaits.release/
TEST_DIR := /Volumes/CIRCUITPY

# Source directory
SRC_DIR := src

# Python interpreter and pip commands
PYTHON := python
PIP := python -m pip

.PHONY: test test-all test-unit test-coverage install-test-deps dev lint lint-errors clean format mpy
all: test release

# Development mode with simulator
run-local-device-simulator:
	$(PYTHON) -m src.main --dev

# Testing targets
test: test-unit

# Run unit tests
# Note: Temporarily renames code.py to avoid conflict with Python's standard 'code' module
test-unit:
	@echo "Running unit tests (working around code.py naming conflict)..."
	@if [ -f code.py ]; then \
		mv code.py code_temp_backup.py && \
		PYTHONPATH=src $(PYTHON) -m pytest test/unit -v; \
		test_result=$$?; \
		mv code_temp_backup.py code.py; \
		exit $$test_result; \
	else \
		PYTHONPATH=src $(PYTHON) -m pytest test/unit -v; \
	fi

# Run all tests
test-all:
	@echo "Running all tests (working around code.py naming conflict)..."
	@if [ -f code.py ]; then \
		mv code.py code_temp_backup.py && \
		PYTHONPATH=src $(PYTHON) -m pytest; \
		test_result=$$?; \
		mv code_temp_backup.py code.py; \
		exit $$test_result; \
	else \
		PYTHONPATH=src $(PYTHON) -m pytest; \
	fi

# Run tests with coverage report
test-coverage:
	@echo "Running tests with coverage (working around code.py naming conflict)..."
	@if [ -f code.py ]; then \
		mv code.py code_temp_backup.py && \
		PYTHONPATH=src $(PYTHON) -m pytest --cov=src --cov-report=term --cov-report=html; \
		test_result=$$?; \
		mv code_temp_backup.py code.py; \
		exit $$test_result; \
	else \
		PYTHONPATH=src $(PYTHON) -m pytest --cov=src --cov-report=term --cov-report=html; \
	fi

# Install test dependencies
install-test-deps:
	$(PIP) install pytest pytest-asyncio pytest-cov

# Install development dependencies
install-dev-deps:
	$(PIP) install pygame pillow numpy

# Install lint dependencies
install-lint-deps:
	$(PIP) install ruff

# Lint all Python files - comprehensive check
lint:
	@echo "Running Python linter (ruff)..."
	$(PYTHON) -m ruff check $(SRC_DIR) test/ --fix
	@echo "Linting complete!"

# Lint only for critical errors (undefined names, syntax errors, etc.)
lint-errors:
	@echo "Checking for critical errors..."
	$(PYTHON) -m ruff check $(SRC_DIR) --select=E9,F63,F7,F82,F821 --no-fix
	@echo "Critical error check complete!"

# Run lint before tests
test-with-lint: lint-errors test

# Copy all files to the release GIT archive
release: $(SRC_DIR)/*.py
	cp -f boot.py $(RELEASE_DESTDIR)
	cp -f code.py $(RELEASE_DESTDIR)
	cp -rf $(SRC_DIR) $(RELEASE_DESTDIR)

# Copy files to the connected MatrixPortal S3 (with lint check)
copy-to-circuitpy : lint-errors $(TEST_DIR)
	cp -f boot.py $(TEST_DIR)
	cp -f code.py $(TEST_DIR)
	rsync -av --update --progress \
		--exclude='images/' \
		--exclude='.DS_Store' \
		--exclude='**/.DS_Store' \
		--exclude="__pycache__" \
		$(SRC_DIR)/ $(TEST_DIR)/src/

# Copy files without lint check (use with caution)
copy-to-circuitpy-no-lint : $(TEST_DIR)
	cp -f boot.py $(TEST_DIR)
	cp -f code.py $(TEST_DIR)
	rsync -av --update --progress \
		--exclude='images/' \
		--exclude='.DS_Store' \
		--exclude='**/.DS_Store' \
		--exclude="__pycache__" \
		$(SRC_DIR)/ $(TEST_DIR)/src/
# Clean build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".DS_Store" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage

# Format code using ruff
format:
	@echo "Formatting Python code..."
	$(PYTHON) -m ruff format $(SRC_DIR) test/
	@echo "Formatting complete\!"

# Install SLDK with simulator support in development mode
install-sldk-dev:
	@echo "Installing SLDK in development mode..."
	cd sldk && $(PIP) install -e .[dev,simulator]
	@echo "SLDK installed\!"

# Run specific experiment tests
test-experiments:
	@echo "Available experiment categories:"
	@echo "  make test-display    - Run display experiments"
	@echo "  make test-network    - Run network experiments"
	@echo "  make test-system     - Run system experiments"
	@echo "  make test-integration - Run integration experiments"

test-display:
	$(PYTHON) -m pytest test/experiments/display/ -v

test-network:
	$(PYTHON) -m pytest test/experiments/network/ -v

test-system:
	$(PYTHON) -m pytest test/experiments/system/ -v

test-integration:
	$(PYTHON) -m pytest test/experiments/integration/ -v

# Cross-compile the scrollkit library to .mpy (smaller RAM + faster boot on device).
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
