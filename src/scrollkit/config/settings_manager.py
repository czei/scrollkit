"""
Settings manager for handling user configuration.
Copyright 2024 3DUPFitters LLC
"""
import json

from scrollkit.utils.error_handler import ErrorHandler

# Initialize logger
logger = ErrorHandler("error_log")


class SettingsManager:
    """
    Manages application settings with persistence to a JSON file.

    Applications can register their own defaults by calling
    set_defaults({'key': value, ...}) after construction.
    """

    def __init__(self, filename, defaults=None, bool_keys=None):
        """
        Initialize the settings manager.

        Args:
            filename: The name of the settings file
            defaults: Optional dict of default settings
            bool_keys: Optional list of keys that should be treated as booleans
                       (needed because CircuitPython's JSON parser may store them as strings)
        """
        self.filename = filename
        self.settings = self.load_settings()
        self.scroll_speed = {"Slow": 0.06, "Medium": 0.04, "Fast": 0.02}
        self._bool_keys = bool_keys or []

        # Generic defaults (non application-specific)
        if self.settings.get("brightness_scale") is None:
            self.settings["brightness_scale"] = "0.5"
        if self.settings.get("scroll_speed") is None:
            self.settings["scroll_speed"] = "Medium"

        # Apply application-provided defaults
        if defaults:
            self.set_defaults(defaults)

    def set_defaults(self, defaults):
        """
        Register application-specific defaults. Only sets values that
        are not already present in settings.

        Args:
            defaults: Dict of {key: default_value}
        """
        for key, value in defaults.items():
            if key not in self.settings:
                self.settings[key] = value

    def add_bool_keys(self, *keys):
        """Register additional keys that should be treated as booleans."""
        for key in keys:
            if key not in self._bool_keys:
                self._bool_keys.append(key)

    def get_scroll_speed(self):
        """
        Get the scroll speed based on the current setting.

        Returns:
            The scroll speed in seconds per pixel
        """
        return self.scroll_speed.get(
            self.settings.get("scroll_speed", "Medium"), 0.04
        )

    @staticmethod
    def get_pretty_name(settings_name):
        """
        Convert a settings key to a display-friendly name.

        Args:
            settings_name: The settings key

        Returns:
            A display-friendly name
        """
        new_name = settings_name.replace("_", " ")
        return " ".join(word[0].upper() + word[1:] for word in new_name.split(' '))

    def load_settings(self):
        """
        Load settings from the settings file.

        Returns:
            A dictionary of settings
        """
        logger.info(f"Loading settings {self.filename}")
        try:
            with open(self.filename, 'r') as f:
                return json.load(f)
        except OSError:
            return {}

    def save_settings(self):
        """Save settings to the settings file"""
        logger.info(f"Saving settings {self.filename}")
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.settings, f)
        except OSError as e:
            logger.error(e, f"Error saving settings to {self.filename}")

    def get(self, key, default=None):
        """
        Get a setting by key with a default value.

        Args:
            key: The settings key
            default: The default value if the key is not found

        Returns:
            The setting value, or the default if not found
        """
        value = self.settings.get(key, default)

        # Special handling for boolean settings that might be stored as strings
        # This can happen with CircuitPython's JSON parser
        if key in self._bool_keys and isinstance(value, str):
            return value.lower() == "true"

        return value

    def set(self, key, value):
        """
        Set a setting by key.

        Args:
            key: The settings key
            value: The value to set
        """
        self.settings[key] = value
