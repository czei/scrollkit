"""
Error handling utility for logging errors and debug information.
Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""
import os
import traceback

try:
    import storage
except (ImportError, AttributeError):
    # `storage` is a CircuitPython-only module. Bind it to None on desktop so the
    # module attribute always exists (the detection branch below gates on
    # `storage is not None`, and tests patch this name).
    storage = None

class ErrorHandler:
    """
    Centralized error handling and logging facility.
    Handles writing to log files with fallback to console output.
    """
    
    # Class-level registry to track instances by filename
    _instances = {}
    
    # Class-level mode setting
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    _mode = PRODUCTION  # Default to production mode

    # Cap each log generation so logging can never fill the device's tiny flash
    # (the field failure: unbounded append eventually fills storage and the app
    # can't write settings/cache and goes dark). When the file reaches this size
    # it is rotated to "<file>.old" (one generation kept), bounding total log
    # storage to ~2x this value while preserving recent history.
    MAX_LOG_BYTES = 16384

    def __new__(cls, file_name, mode=None):
        """Return one shared instance per log file.

        The previous code faked a singleton inside __init__ by copying fields out of
        the cached instance into a *newly allocated* object and returning that — so
        every ``ErrorHandler("error_log")`` was a distinct object. When one detected
        a read-only filesystem and set is_readonly=True, the others never saw it and
        kept thrashing the filesystem on every write; mode/state diverged silently.
        Holding identity in __new__ makes all callers share a single object.
        """
        inst = cls._instances.get(file_name)
        if inst is None:
            inst = super().__new__(cls)
            cls._instances[file_name] = inst
        return inst

    def __init__(self, file_name, mode=None):
        """
        Initialize the error handler with read-only filesystem detection

        Args:
            file_name: The name of the log file
            mode: Either 'development' or 'production' (optional, uses class default if not specified)
        """
        # Shared singleton: run setup exactly once per file. A later construction may
        # still update the mode when the caller passes one explicitly (an explicit
        # override wins); otherwise first-construction state stands.
        if getattr(self, "_initialized", False):
            if mode is not None:
                self.mode = mode
            return
        self._initialized = True

        # Continue with normal initialization for new instance
        self.fileName = file_name
        # Set instance mode - use parameter if provided, otherwise use class default
        self.mode = mode if mode else ErrorHandler._mode
        # Start with the assumption that the filesystem is read-only
        # We'll only set it to writable if we can successfully write to it
        self.is_readonly = True

        # First check if we can directly detect read-only status via storage module
        if storage is not None:
            try:
                # Get mount location
                mount_path = '/'
                try:
                    # Try to get the mount path for the file's directory
                    dir_path = os.path.dirname(file_name)
                    if dir_path and os.path.exists(dir_path):
                        mount_path = dir_path
                except OSError:
                    pass
                    
                # Check if storage shows readonly
                self.is_readonly = storage.getmount(mount_path).readonly
                print(f"Filesystem read-only status from storage: {self.is_readonly}")
                
                # If storage says it's read-only, trust that and skip the write test
                if self.is_readonly:
                    print("Filesystem is read-only according to storage module")
                    print("ErrorHandler initialized - read-only filesystem")  # Exact match for test
                    return
            except (AttributeError, OSError):
                # Continue with write test if storage check fails
                print("Storage module check failed, will try write test")

        # Preserve crash evidence across reboots. The old code deleted the log here
        # AND truncated it with a 'w' write-test below, so a crash -> reboot erased
        # exactly the log that would explain the crash (why field failures were
        # undiagnosable). Only DEVELOPMENT starts each run with a fresh log.
        if self.mode == ErrorHandler.DEVELOPMENT:
            try:
                if self.file_exists(file_name):
                    print(f"Deleting existing log file: {file_name}")
                    os.remove(file_name)
            except OSError:
                # Can't delete, assume readonly
                self.is_readonly = True
                print(f"Failed to delete existing log file: {file_name}")

        # Verify writability WITHOUT truncating: append-open creates the file if it
        # is missing and leaves any existing contents intact (so PRODUCTION keeps
        # the prior session's log for post-mortem).
        try:
            with open(self.fileName, 'a'):
                pass
            self.is_readonly = False
        except OSError as e:
            # If any error occurs during write/create, filesystem is read-only
            self.is_readonly = True
            print(f"Write test failed: {str(e)}")

        # Log system state at initialization based on final determination
        if self.is_readonly:
            print("ErrorHandler initialized - read-only filesystem")
        else:
            print("ErrorHandler initialized - writable filesystem")

    @classmethod
    def set_mode(cls, mode):
        """
        Set the global mode for all new ErrorHandler instances
        
        Args:
            mode: Either 'development' or 'production'
        """
        if mode in [cls.DEVELOPMENT, cls.PRODUCTION]:
            cls._mode = mode
        else:
            raise ValueError(f"Invalid mode: {mode}. Must be either '{cls.DEVELOPMENT}' or '{cls.PRODUCTION}'")
    
    @classmethod
    def get_mode(cls):
        """
        Get the current global mode
        
        Returns:
            The current mode string
        """
        return cls._mode

    @staticmethod
    def filter_non_ascii(text):
        """
        Filter out non-ASCII characters from a string
        
        Args:
            text: The text to filter
            
        Returns:
            A string with only ASCII characters
        """
        if text is None:
            return ""
        return "".join(c for c in str(text) if ord(c) < 128)

    @staticmethod
    def file_exists(file_name):
        """
        Check if a file exists
        
        Args:
            file_name: The name of the file to check
            
        Returns:
            True if the file exists, False otherwise
        """
        file_exists = True
        try:
            status = os.stat(file_name)
        except OSError:
            file_exists = False
        return file_exists

    def error(self, e, str_description):
        """
        Log an error with a description and stack trace

        Args:
            e: The exception that occurred
            str_description: A description of the error
        """
        # Handle the case where e is None (no exception but error message)
        if e is None:
            except_str = str_description
            st_str = ""
        else:
            except_str = str_description + ":" + str(e)
            try:
                st = traceback.format_exception(e)
                st_str = "stack trace:"
                for line in st:
                    st_str = st_str + line
            except Exception:
                # Fallback for cases where traceback.format_exception fails
                st_str = "stack trace unavailable"

        # Filter out non-ASCII characters to prevent UnicodeEncodeError
        filtered_except_str = self.filter_non_ascii(except_str)
        filtered_st_str = self.filter_non_ascii(st_str)

        # Always print errors to console for visibility
        print(filtered_except_str)
        if filtered_st_str:
            print(filtered_st_str)

        # Only attempt to write to file if filesystem is writable. Errors ARE
        # persisted in both modes (they're the post-mortem); rotation keeps the
        # file bounded so even an error storm can't fill flash.
        if not self.is_readonly:
            self._rotate_if_needed()
            try:
                with open(self.fileName, 'a') as file:
                    file.write(filtered_except_str + "\n")
                    if filtered_st_str:
                        file.write(filtered_st_str + "\n")
            except OSError:
                # If write fails unexpectedly, update readonly state
                self.is_readonly = True
                # Only print this message once when we first detect a failure
                print("Filesystem detected as read-only, logs will be displayed on console only")

    def debug(self, message):
        """
        Log a debug message
        
        Args:
            message: The debug message to log
        """
        print(message)
        # Only write debug messages to file in development mode
        if self.mode == ErrorHandler.DEVELOPMENT:
            self.write_to_file(message)

    def _rotate_if_needed(self):
        """Rotate the log to '<file>.old' once it reaches MAX_LOG_BYTES, so logging
        can never fill flash. Keeps one prior generation."""
        if self.is_readonly:
            return
        try:
            size = os.stat(self.fileName)[6]   # st_size
        except OSError:
            return
        if size < self.MAX_LOG_BYTES:
            return
        backup = self.fileName + ".old"
        try:
            try:
                os.remove(backup)              # drop the older generation
            except OSError:
                pass
            os.rename(self.fileName, backup)
        except OSError:
            # Rename failed (transient FS hiccup). Do NOT blind-truncate here: the
            # old code did `open(file, 'w')`, destroying exactly the recent crash
            # evidence this log exists to preserve. Prefer a tail-preserving trim
            # that keeps the most recent bytes; if even that fails, skip rotation
            # this cycle (keep appending, accept temporary oversize) and leave a
            # one-line marker. rename is retried next cycle and usually succeeds.
            if not self._tail_trim():
                try:
                    with open(self.fileName, 'a') as f:
                        f.write("[log rotation failed; not truncated]\n")
                except OSError:
                    self.is_readonly = True

    def _tail_trim(self):
        """Rewrite the log keeping only its most recent bytes — the fallback for when
        rename-based rotation is unavailable, preserving recent crash evidence while
        still bounding size. Returns True on success, False if seek/read/rewrite is
        not reliable on this filesystem (the caller then leaves the file intact
        rather than destroying it). Binary mode so end-relative seeks work on both
        CPython and CircuitPython."""
        keep = self.MAX_LOG_BYTES // 2
        try:
            with open(self.fileName, 'rb') as f:
                try:
                    f.seek(-keep, 2)           # last `keep` bytes (whence 2 = end)
                except (OSError, ValueError):
                    f.seek(0)                  # file smaller than keep / no end-seek
                tail = f.read()
            with open(self.fileName, 'wb') as f:
                f.write(b"[log trimmed to recent history]\n")
                f.write(tail)
            return True
        except (OSError, ValueError):
            return False

    def write_to_file(self, message):
        """
        Write a message to the log file

        Args:
            message: The message to write
        """
        # Only attempt to write if filesystem is writable
        if self.is_readonly:
            # In read-only mode, we'll just print to console without error messages
            # We don't print "Error writing to log file" as that confuses users
            return

        self._rotate_if_needed()
        try:
            # Filter out non-ASCII characters to prevent UnicodeEncodeError
            filtered_message = self.filter_non_ascii(message)

            with open(self.fileName, 'a') as file:
                file.write(filtered_message + "\n")
        except OSError:
            # If write fails unexpectedly, update readonly state
            self.is_readonly = True
            # Only print this message once when we first detect a failure
            print("Filesystem detected as read-only, logs will be displayed on console only")

    def info(self, message):
        """
        Log an informational message
        
        Args:
            message: The informational message to log
        """
        print(message)
        # Info is high-frequency (every fetch attempt/success). Persisting it to
        # flash on every refresh fills the device's tiny storage over days, so write
        # it only in DEVELOPMENT; PRODUCTION keeps info on the console. Errors are
        # still persisted in both modes (see error()).
        if self.mode == ErrorHandler.DEVELOPMENT:
            self.write_to_file(message)