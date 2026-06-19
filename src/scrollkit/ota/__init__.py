"""ScrollKit OTA (over-the-air update) package.

Kept import-light on purpose: import the concrete classes from their submodules
(``scrollkit.ota.client.OTAClient``, ``scrollkit.ota.manifest.UpdateManifest``)
rather than from the package root, so merely importing the package does not pull
in the HTTP stack.
"""
