"""
Contract: OTA Update System
Public API for over-the-air firmware updates from GitHub.
"""


class OTAClientContract:
    """
    Checks for and applies firmware updates.
    Manifest is fetched from a GitHub raw URL.

    Usage:
        client = OTAClient(
            update_server_url="https://raw.githubusercontent.com/owner/repo/releases",
            current_version="1.0.0"
        )
        has_update, manifest = client.check_for_updates()
        if has_update:
            client.download_update(manifest)
            client.apply_update()
            # device reboots
    """

    def __init__(
        self,
        update_server_url: str,
        current_version: str = "0.0.0",
        update_dir: str = "/updates",
        backup_dir: str = "/backup",
    ):
        raise NotImplementedError

    def check_for_updates(self) -> tuple:
        """
        Returns (True, UpdateManifest) if a newer version is available.
        Returns (False, str) with a reason message otherwise.
        """
        raise NotImplementedError

    def download_update(self, manifest=None) -> tuple:
        """
        Downloads all files listed in the manifest to update_dir.
        Returns (True, '') on success or (False, error_message) on failure.
        """
        raise NotImplementedError

    def apply_update(self) -> tuple:
        """
        Moves downloaded files into place.
        Creates a backup of the current version in backup_dir.
        Returns (True, '') or (False, error_message).
        On CircuitPython, triggers a soft reboot after success.
        """
        raise NotImplementedError

    def rollback(self) -> tuple:
        """
        Restores the previous version from backup_dir.
        Returns (True, '') or (False, error_message).
        """
        raise NotImplementedError


class UpdateManifestContract:
    """Describes a firmware release."""

    version: str                   # semver string
    description: str
    files: dict                    # {relative_path: {size, checksum, required}}
    requirements: dict             # {circuitpython_version, memory_required, storage_required}

    def compare_version(self, other_version: str) -> int:
        """Returns -1, 0, or 1 (like strcmp)."""
        raise NotImplementedError

    def validate(self) -> tuple:
        """Returns (True, '') or (False, error_message)."""
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict):
        """Deserialize from JSON-parsed dict."""
        raise NotImplementedError

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        raise NotImplementedError


# --- Contract tests ---

def test_manifest_from_dict_roundtrip():
    """Manifest must serialize and deserialize without data loss."""
    import json
    from scrollkit.ota.manifest import UpdateManifest

    original = UpdateManifest(version="1.2.3", description="Test release")
    original.files = {
        "src/main.py": {"size": 1024, "checksum": "abc123", "required": True}
    }

    data = json.loads(original.to_json())
    restored = UpdateManifest.from_dict(data)

    assert restored.version == "1.2.3"
    assert "src/main.py" in restored.files
    assert restored.files["src/main.py"]["checksum"] == "abc123"


def test_manifest_version_comparison():
    """compare_version must follow semver ordering."""
    from scrollkit.ota.manifest import UpdateManifest

    m = UpdateManifest(version="1.2.0")
    assert m.compare_version("1.1.0") > 0   # 1.2.0 > 1.1.0
    assert m.compare_version("1.2.0") == 0  # equal
    assert m.compare_version("2.0.0") < 0   # 1.2.0 < 2.0.0


def test_ota_client_accepts_github_url():
    """OTAClient must accept a GitHub raw content URL without error."""
    from scrollkit.ota.client import OTAClient

    client = OTAClient(
        update_server_url="https://raw.githubusercontent.com/owner/repo/releases",
        current_version="0.9.0",
    )
    assert client is not None


def test_ota_client_check_returns_tuple():
    """check_for_updates must return (bool, manifest_or_message)."""
    from unittest.mock import MagicMock
    from scrollkit.ota.client import OTAClient

    client = OTAClient(
        update_server_url="http://localhost:9999",
        current_version="99.0.0",
    )
    # With an unreachable server, must return (False, reason_string)
    result = client.check_for_updates()
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert result[0] is False
    assert isinstance(result[1], str)
