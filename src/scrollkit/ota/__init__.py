# Copyright (c) 2024-2026 Michael Czeiszperger
"""ScrollKit OTA (over-the-air update) package.

Kept import-light on purpose: import the concrete classes from their submodules
(``scrollkit.ota.client.OTAClient``, ``scrollkit.ota.manifest.UpdateManifest``)
rather than from the package root, so merely importing the package does not pull
in the HTTP stack.

Producing/publishing a release is the desktop/CI-only ``scrollkit.ota.publish``
module (``build_manifest`` / ``publish_to_branch``); it imports ``os.walk``,
``subprocess`` and the ``git`` CLI and raises ``ImportError`` on CircuitPython,
so it is never imported from the package root either.
"""
