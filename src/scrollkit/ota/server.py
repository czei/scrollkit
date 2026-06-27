# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""OTA update server.

Serves update packages to CircuitPython devices.
"""

from __future__ import annotations

import os
import json
import hashlib
try:
    from typing import Any, Dict, List, Optional, Tuple, Union
except ImportError:  # CircuitPython has no 'typing' module
    pass

from ..exceptions import OTAError
from .manifest import UpdateManifest


class OTAServer:
    """OTA update server.

    Serves update packages to devices:
    - Hosts update manifests
    - Serves individual files
    - Manages update packages
    - Provides web interface for uploads
    """

    updates_dir: str
    web_interface: Any
    current_manifest: Optional[UpdateManifest]
    update_packages: Dict[str, UpdateManifest]

    def __init__(self, updates_dir: str = "./updates", web_interface: Any = None) -> None:
        """Initialize OTA server.

        Args:
            updates_dir: Directory containing update packages
            web_interface: Optional web server instance
        """
        self.updates_dir = updates_dir
        self.web_interface = web_interface
        self.current_manifest = None
        self.update_packages = {}

        os.makedirs(updates_dir, exist_ok=True)

        self._load_existing_packages()

    def _load_existing_packages(self) -> None:
        """Load existing update packages from disk."""
        try:
            for item in os.listdir(self.updates_dir):
                item_path = os.path.join(self.updates_dir, item)

                if os.path.isdir(item_path):
                    manifest_path = os.path.join(item_path, "manifest.json")

                    if os.path.exists(manifest_path):
                        try:
                            with open(manifest_path, 'r') as f:
                                manifest_data = json.loads(f.read())

                            manifest = UpdateManifest.from_dict(manifest_data)
                            self.update_packages[manifest.version] = manifest

                            if (not self.current_manifest or
                                manifest.compare_version(self.current_manifest.version) > 0):
                                self.current_manifest = manifest

                        except Exception as e:
                            print(f"Error loading package {item}: {e}")

        except Exception as e:
            print(f"Error loading packages: {e}")

    def create_package(
        self,
        version: str,
        description: str = "",
        source_dir: str = "./src",
    ) -> Tuple[bool, Union[str, UpdateManifest]]:
        """Create new update package.

        Args:
            version: Version string
            description: Package description
            source_dir: Source directory to package

        Returns:
            tuple: (success, manifest_or_error)
        """
        try:
            manifest = UpdateManifest(version=version, description=description)

            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    if file.endswith('.py') or file.endswith('.mpy'):
                        source_path = os.path.join(root, file)
                        relative_path = os.path.relpath(source_path, source_dir)

                        device_path = "/" + relative_path.replace(os.sep, "/")

                        manifest.add_file(device_path, file_path=source_path)

            is_valid, error = manifest.validate()
            if not is_valid:
                return False, f"Invalid manifest: {error}"

            package_dir = os.path.join(self.updates_dir, version)
            os.makedirs(package_dir, exist_ok=True)

            manifest_path = os.path.join(package_dir, "manifest.json")
            with open(manifest_path, 'w') as f:
                f.write(manifest.to_json())

            files_dir = os.path.join(package_dir, "files")
            os.makedirs(files_dir, exist_ok=True)

            for device_path in manifest.files.keys():
                source_path = os.path.join(source_dir, device_path.lstrip('/'))
                target_path = os.path.join(files_dir, device_path.lstrip('/'))

                target_dir = os.path.dirname(target_path)
                if target_dir:
                    os.makedirs(target_dir, exist_ok=True)

                with open(source_path, 'rb') as src:
                    with open(target_path, 'wb') as dst:
                        dst.write(src.read())

            self.update_packages[version] = manifest

            if (not self.current_manifest or
                manifest.compare_version(self.current_manifest.version) > 0):
                self.current_manifest = manifest

            return True, manifest

        except OTAError:
            raise
        except Exception as e:
            return False, str(e)

    def get_manifest_json(self, version: Optional[str] = None) -> Optional[str]:
        """Get manifest as JSON.

        Args:
            version: Specific version (uses current if None)

        Returns:
            str: JSON manifest or None
        """
        manifest = self.current_manifest

        if version and version in self.update_packages:
            manifest = self.update_packages[version]

        if manifest:
            return manifest.to_json()
        return None

    def get_file_content(self, file_path: str, version: Optional[str] = None) -> Optional[bytes]:
        """Get file content from package.

        Args:
            file_path: File path
            version: Package version (uses current if None)

        Returns:
            bytes: File content or None
        """
        if version is None and self.current_manifest:
            version = self.current_manifest.version

        if not version or version not in self.update_packages:
            return None

        try:
            package_dir = os.path.join(self.updates_dir, version)
            files_dir = os.path.join(package_dir, "files")
            full_path = os.path.join(files_dir, file_path.lstrip('/'))

            if os.path.exists(full_path):
                with open(full_path, 'rb') as f:
                    return f.read()

        except Exception as e:
            print(f"Error reading file {file_path}: {e}")

        return None

    def list_packages(self) -> List[Dict[str, Any]]:
        """List all available packages.

        Returns:
            list: Package info dictionaries
        """
        packages: List[Dict[str, Any]] = []

        for version, manifest in self.update_packages.items():
            packages.append({
                'version': version,
                'description': manifest.description,
                'file_count': len(manifest.files),
                'total_size': manifest.calculate_total_size(),
                'is_current': manifest == self.current_manifest,
            })

        packages.sort(key=lambda p: p['version'], reverse=True)
        return packages

    def delete_package(self, version: str) -> bool:
        """Delete update package.

        Args:
            version: Version to delete

        Returns:
            bool: Success
        """
        if version not in self.update_packages:
            return False

        try:
            del self.update_packages[version]

            package_dir = os.path.join(self.updates_dir, version)
            if os.path.exists(package_dir):
                import shutil
                shutil.rmtree(package_dir)

            if self.current_manifest and self.current_manifest.version == version:
                self.current_manifest = None
                for manifest in self.update_packages.values():
                    if (not self.current_manifest or
                        manifest.compare_version(self.current_manifest.version) > 0):
                        self.current_manifest = manifest

            return True

        except Exception as e:
            print(f"Error deleting package {version}: {e}")
            return False

