"""
Settings manager for handling user configuration.
Copyright 2024 3DUPFitters LLC
"""
import json

from scrollkit.utils.error_handler import ErrorHandler
from scrollkit.config.transition_names import TRANSITION_NAMES

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
        self._schema = []

        # Built-in library settings — always defined so the default web UI shows them.
        self.define("brightness_scale", 0.5, label="Brightness", min=0.0, max=1.0, step=0.05)
        self.define("scroll_speed", "Medium", label="Scroll Speed",
                    options=["None", "Slow", "Medium", "Fast"])
        self.define("default_color", 0xFFFFFF, label="Default Color", type="color")
        # Choices derive from the single source of truth (config.transition_names),
        # which the dispatch map in effects.transitions is tested to match — so a
        # selectable name can never silently fail to dispatch. Plain "None" + list
        # concatenation (no *-unpacking) for CircuitPython-parser safety.
        self.define("transition_style", "None", label="Transition Style",
                    options=["None"] + list(TRANSITION_NAMES))

        # Apply application-provided defaults
        if defaults:
            self.set_defaults(defaults)

    def define(self, key, default, label=None, type=None, options=None,
               min=None, max=None, step=None):
        """Declare a setting with display metadata for the auto-generating web UI.

        The UI renders a form field for every defined setting in the order they
        were declared. Type is inferred from the default value when not given:
        bool -> checkbox, options list -> select, min/max -> range,
        int/float -> number, else text.  Use type="color" explicitly for
        colour pickers (stored as int 0xRRGGBB).

        Args:
            key: Settings key (used as the form field name)
            default: Default value (only applied when no saved value exists)
            label: Human-readable label; defaults to title-cased key name
            type: Field type override ("text","number","range","color","select","checkbox")
            options: List of string choices (implies type="select")
            min: Numeric lower bound for range/number inputs
            max: Numeric upper bound for range/number inputs
            step: Numeric step for range/number inputs
        """
        if type is not None:
            resolved_type = type
        elif options:
            resolved_type = "select"
        elif min is not None or max is not None:
            resolved_type = "range"
        elif isinstance(default, bool):  # must check before int (bool subclasses int)
            resolved_type = "checkbox"
        elif isinstance(default, (int, float)):
            resolved_type = "number"
        else:
            resolved_type = "text"

        resolved_label = label if label is not None else SettingsManager.get_pretty_name(key)

        self._schema.append({
            "key": key,
            "label": resolved_label,
            "type": resolved_type,
            "default": default,
            "options": options,
            "min": min,
            "max": max,
            "step": step,
        })

        if resolved_type == "checkbox":
            self.add_bool_keys(key)

        self.set_defaults({key: default})

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
        """Return scroll speed in seconds per pixel (for timing loops)."""
        return self.scroll_speed.get(
            self.settings.get("scroll_speed", "Medium"), 0.04
        )

    def get_scroll_speed_px(self):
        """Return scroll speed in pixels per second (for ScrollingText speed= arg).

        Returns 0 when scroll_speed is "None" — ScrollingText treats 0 as
        static-display mode: text is shown centred for a fixed duration rather
        than scrolling.
        """
        if self.settings.get("scroll_speed", "Medium") == "None":
            return 0
        secs = self.get_scroll_speed()
        return int(round(1.0 / secs)) if secs > 0 else 25

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
