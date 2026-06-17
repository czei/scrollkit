"""Application packager for SLDK.

Handles packaging applications for deployment to CircuitPython devices.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import json
from typing import List, Optional, Tuple, Union
from pathlib import Path

from ..exceptions import DeploymentError


class SLDKPackager:
    """Packages SLDK applications for deployment.

    Features:
    - .mpy compilation for smaller file sizes
    - Dependency management
    - File optimization
    - CircuitPython compatibility checking
    """

    project_dir: Path
    src_dir: Path
    build_dir: Path
    dist_dir: Path
    optimize_mpy: bool
    include_tests: bool
    min_circuitpython_version: str
    max_file_size: int
    include_patterns: List[str]
    exclude_patterns: List[str]
    remove_debug: bool

    def __init__(self, project_dir: str = ".") -> None:
        """Initialize packager.

        Args:
            project_dir: Project directory path
        """
        self.project_dir = Path(project_dir).resolve()
        self.src_dir = self.project_dir / "src"
        self.build_dir = self.project_dir / "build"
        self.dist_dir = self.project_dir / "dist"

        self.optimize_mpy = True
        self.include_tests = False
        self.min_circuitpython_version = "8.0.0"
        self.max_file_size = 1024 * 1024

        self.include_patterns = [
            "*.py",
            "*.json",
            "*.txt",
            "*.bdf",
            "*.bmp",
            "*.md",
        ]

        self.exclude_patterns = [
            "__pycache__",
            "*.pyc",
            "*.pyo",
            ".pytest_cache",
            ".git",
            ".vscode",
            "*.egg-info",
        ]

        if not self.include_tests:
            self.exclude_patterns.extend([
                "test_*.py",
                "*_test.py",
                "tests/",
                "conftest.py",
            ])

    def package(
        self,
        output_dir: Optional[str] = None,
        version: Optional[str] = None,
    ) -> Tuple[bool, Union[str, Path]]:
        """Package application for deployment.

        Args:
            output_dir: Output directory (uses dist/ if None)
            version: Package version

        Returns:
            tuple: (success, package_path_or_error)
        """
        try:
            if output_dir is None:
                output_dir = self.dist_dir
            else:
                output_dir = Path(output_dir)

            output_dir.mkdir(parents=True, exist_ok=True)

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                package_dir = temp_path / "package"
                package_dir.mkdir()

                print("Copying source files...")
                self._copy_source_files(package_dir)

                if self.optimize_mpy:
                    print("Compiling to .mpy files...")
                    success, error = self._compile_mpy(package_dir)
                    if not success:
                        print(f"Warning: .mpy compilation failed: {error}")

                print("Optimizing files...")
                self._optimize_files(package_dir)

                print("Validating package...")
                is_valid, validation_error = self._validate_package(package_dir)
                if not is_valid:
                    return False, f"Package validation failed: {validation_error}"

                print("Creating deployment package...")
                package_name = f"sldk-app-{version or 'latest'}"
                package_path = output_dir / f"{package_name}.zip"

                success, error = self._create_zip_package(package_dir, package_path)
                if not success:
                    return False, error

                manifest_path = output_dir / f"{package_name}-manifest.json"
                self._create_manifest(package_dir, manifest_path, version)

                print(f"Package created: {package_path}")
                print(f"Manifest created: {manifest_path}")

                return True, package_path

        except DeploymentError:
            raise
        except Exception as e:
            return False, str(e)

    def _copy_source_files(self, target_dir: Path) -> None:
        """Copy source files to package directory.

        Args:
            target_dir: Target directory
        """
        for root, dirs, files in os.walk(self.src_dir):
            dirs[:] = [d for d in dirs if not self._is_excluded(d)]

            for file in files:
                if self._should_include_file(file):
                    source_path = Path(root) / file
                    relative_path = source_path.relative_to(self.src_dir)
                    target_path = target_dir / relative_path

                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, target_path)

        for file in ["README.md", "LICENSE", "requirements.txt"]:
            source_path = self.project_dir / file
            if source_path.exists():
                shutil.copy2(source_path, target_dir / file)

    def _should_include_file(self, filename: str) -> bool:
        """Check if file should be included.

        Args:
            filename: File name

        Returns:
            bool: Should include
        """
        if self._is_excluded(filename):
            return False

        for pattern in self.include_patterns:
            if self._matches_pattern(filename, pattern):
                return True

        return False

    def _is_excluded(self, name: str) -> bool:
        """Check if name matches exclude patterns.

        Args:
            name: File or directory name

        Returns:
            bool: Is excluded
        """
        for pattern in self.exclude_patterns:
            if self._matches_pattern(name, pattern):
                return True
        return False

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches pattern.

        Args:
            name: Name to check
            pattern: Pattern (supports * wildcard)

        Returns:
            bool: Matches
        """
        import fnmatch
        return fnmatch.fnmatch(name, pattern)

    def _compile_mpy(self, package_dir: Path) -> Tuple[bool, str]:
        """Compile Python files to .mpy.

        Args:
            package_dir: Package directory

        Returns:
            tuple: (success, error_message)
        """
        try:
            result = subprocess.run(
                ['mpy-cross', '--version'],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                return False, "mpy-cross not found in PATH"

            for root, dirs, files in os.walk(package_dir):
                for file in files:
                    if file.endswith('.py'):
                        py_path = Path(root) / file
                        mpy_path = py_path.with_suffix('.mpy')

                        result = subprocess.run([
                            'mpy-cross',
                            str(py_path),
                            '-o', str(mpy_path),
                        ], capture_output=True, text=True)

                        if result.returncode == 0:
                            py_path.unlink()
                        else:
                            print(f"Warning: Failed to compile {py_path}: {result.stderr}")

            return True, ""

        except Exception as e:
            return False, str(e)

    def _optimize_files(self, package_dir: Path) -> None:
        """Optimize files for deployment.

        Args:
            package_dir: Package directory
        """
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = Path(root) / file

                if file_path.stat().st_size > self.max_file_size:
                    print(f"Warning: Large file {file_path} ({file_path.stat().st_size} bytes)")

                if file.endswith('.py'):
                    self._optimize_python_file(file_path)
                elif file.endswith('.json'):
                    self._optimize_json_file(file_path)

    def _optimize_python_file(self, file_path: Path) -> None:
        """Optimize Python file.

        Args:
            file_path: Python file path
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if hasattr(self, 'remove_debug') and self.remove_debug:
                lines = content.split('\n')
                optimized_lines = []

                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith('print(') and 'debug' in stripped.lower():
                        continue
                    if stripped.startswith('assert '):
                        continue
                    optimized_lines.append(line)

                content = '\n'.join(optimized_lines)

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

        except Exception as e:
            print(f"Warning: Failed to optimize {file_path}: {e}")

    def _optimize_json_file(self, file_path: Path) -> None:
        """Optimize JSON file.

        Args:
            file_path: JSON file path
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, separators=(',', ':'))

        except Exception as e:
            print(f"Warning: Failed to optimize {file_path}: {e}")

    def _validate_package(self, package_dir: Path) -> Tuple[bool, str]:
        """Validate package for CircuitPython compatibility.

        Args:
            package_dir: Package directory

        Returns:
            tuple: (is_valid, error_message)
        """
        main_py = package_dir / "main.py"
        if not main_py.exists():
            return False, "main.py not found"

        total_size = 0
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = Path(root) / file
                file_size = file_path.stat().st_size
                total_size += file_size

                if file_size > self.max_file_size:
                    return False, f"File too large: {file_path} ({file_size} bytes)"

        max_total_size = 2 * 1024 * 1024
        if total_size > max_total_size:
            return False, f"Package too large: {total_size} bytes (max {max_total_size})"

        for root, dirs, files in os.walk(package_dir):
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file

                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        compile(content, str(file_path), 'exec')

                    except SyntaxError as e:
                        return False, f"Syntax error in {file_path}: {e}"
                    except Exception as e:
                        print(f"Warning: Could not validate {file_path}: {e}")

        return True, ""

    def _create_zip_package(self, package_dir: Path, output_path: Path) -> Tuple[bool, str]:
        """Create ZIP package.

        Args:
            package_dir: Source directory
            output_path: Output ZIP path

        Returns:
            tuple: (success, error_message)
        """
        try:
            import zipfile

            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(package_dir):
                    for file in files:
                        file_path = Path(root) / file
                        arc_name = file_path.relative_to(package_dir)
                        zf.write(file_path, arc_name)

            return True, ""

        except Exception as e:
            return False, str(e)

    def _create_manifest(self, package_dir: Path, manifest_path: Path, version: Optional[str]) -> None:
        """Create deployment manifest.

        Args:
            package_dir: Package directory
            manifest_path: Manifest output path
            version: Package version
        """
        total_size = 0
        file_count = 0

        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = Path(root) / file
                total_size += file_path.stat().st_size
                file_count += 1

        manifest = {
            'name': 'SLDK Application',
            'version': version or 'latest',
            'description': 'SLDK application package',
            'created': self._get_timestamp(),
            'circuitpython_version': f">={self.min_circuitpython_version}",
            'package_info': {
                'total_size': total_size,
                'file_count': file_count,
                'compressed': True,
                'mpy_compiled': self.optimize_mpy,
            },
            'requirements': {
                'memory_minimum': 50000,
                'storage_minimum': total_size * 2,
            },
            'installation': {
                'extract_to': '/',
                'reboot_required': True,
                'backup_recommended': True,
            },
        }

        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

    def _get_timestamp(self) -> str:
        """Get current timestamp.

        Returns:
            str: ISO timestamp
        """
        try:
            from datetime import datetime
            return datetime.now().isoformat()
        except Exception:
            return "unknown"

    def set_optimization_options(
        self,
        mpy: bool = True,
        remove_debug: bool = False,
        include_tests: bool = False,
    ) -> None:
        """Set optimization options.

        Args:
            mpy: Enable .mpy compilation
            remove_debug: Remove debug statements
            include_tests: Include test files
        """
        self.optimize_mpy = mpy
        self.remove_debug = remove_debug
        self.include_tests = include_tests

        if not include_tests:
            self.exclude_patterns.extend([
                "test_*.py",
                "*_test.py",
                "tests/",
                "conftest.py",
            ])
        else:
            test_patterns = ["test_*.py", "*_test.py", "tests/", "conftest.py"]
            self.exclude_patterns = [p for p in self.exclude_patterns
                                   if p not in test_patterns]