"""
WiFi connection management.
Copyright (c) 2024-2026 Michael Czeiszperger
"""
import asyncio
import sys
import os

# Check if running on CircuitPython
is_circuitpython = hasattr(sys, 'implementation') and sys.implementation.name == 'circuitpython'

# Only import platform if not running on CircuitPython
if not is_circuitpython:
    import platform

from scrollkit.config.settings_manager import SettingsManager
from scrollkit.utils.url_utils import load_credentials


__all__ = ['WiFiManager', 'is_dev_mode']

def _logger():
    # Lazy: constructing ErrorHandler does a filesystem write-test, so it must
    # not run merely from importing this module. Its own __new__ singleton
    # guard makes repeat calls cheap.
    from scrollkit.utils.error_handler import ErrorHandler
    return ErrorHandler("error_log")


def is_dev_mode():
    """True when there is no real WiFi radio available (desktop dev environment).

    Replaces the retired ``display_factory.is_dev_mode``. On CircuitPython this is
    always False (real hardware). On desktop it's True unless a ``wifi`` module is
    importable (which the test suite mocks to exercise the production path).
    """
    if is_circuitpython:
        return False
    try:
        import wifi  # noqa: F401
        return False
    except ImportError:
        return True

class WiFiManager:
    """
    Manages WiFi connections for the application
    """
    
    def __init__(self, settings_manager, ap_name=None):
        """
        Initialize the WiFi manager

        Args:
            settings_manager: The settings manager
            ap_name: Brand name for the setup-portal access point. The SSID a
                customer sees while onboarding is ``"<ap_name>-<tail>"`` where
                the tail is a short MAC-derived suffix (kept library-side so two
                un-onboarded boxes in one home never broadcast identical SSIDs).
                Apps SHOULD pass their product name — the default is the
                generic ``WifiManager`` prefix, deliberately not a product name
                (branding belongs to the app, never hardwired here).
        """
        self.settings_manager = settings_manager
        self._ap_base = ap_name or "WifiManager"
        self.ssid, self.password = self._resolve_credentials()
        self.is_connected = False
        self.wifi_client = None
        self.ap_enabled = False

        # Development mode values
        self.AP_SSID = self._ap_base + "-DEV"
        self.AP_PASSWORD = "password"

        try:
            # Check if in development mode
            if is_dev_mode():
                # In dev mode, simulate WiFi capabilities
                _logger().info("Running in development mode, using simulated WiFi")
                self.wifi = None
                self.HAS_WIFI = False
                # Set dummy values for development
                self.AP_SSID = self._ap_base + "-DEV"
                self.AP_PASSWORD = "password"
                return

            # Try to import CircuitPython specific modules
            import wifi
            self.wifi = wifi
            self.HAS_WIFI = True
            # extract access point mac address
            mac_ap = ' '.join([hex(i) for i in self.wifi.radio.mac_address_ap])
            mac_ap = mac_ap.replace('0x', '').replace(' ', '').upper()
            # access point settings
            self.AP_SSID = self._ap_base + "-" + mac_ap[5:10] + mac_ap[1:2]
            self.AP_PASSWORD = "password"
            self.AP_AUTHMODES = [self.wifi.AuthMode.WPA2, self.wifi.AuthMode.PSK]
            
        except (ImportError, AttributeError) as e:
            # Mock for non-CircuitPython environments
            self.wifi = None
            self.HAS_WIFI = False
            _logger().debug(f"WiFi module not available or incomplete: {e}")

    def _resolve_credentials(self):
        """Resolve WiFi credentials: settings.json first, secrets.py fallback.

        Settings win because they are what the no-file-editing setup portal
        writes (see run_setup_portal) — the user's latest choice must beat a
        stale secrets.py. Returns ("", "") when neither source has an SSID.
        """
        sm = self.settings_manager
        if sm is not None:
            try:
                ssid = sm.get("wifi_ssid")
                password = sm.get("wifi_password")
            except Exception:
                ssid = password = None
            # Strict str checks: settings.json could hold garbage after a bad
            # write, and tests hand in MagicMock settings managers.
            if isinstance(ssid, str) and ssid:
                return ssid, password if isinstance(password, str) else ""
        return load_credentials()

    async def reset(self):
        """Reset the microcontroller after delay"""
        await asyncio.sleep(4)
        if not is_dev_mode():
            try:
                import microcontroller
                microcontroller.reset()
            except ImportError:
                _logger().debug("Microcontroller module not available, skipping reset")
                # In non-hardware environments, just simulate a reset
                os._exit(0)

    async def connect(self, display_callback=None):
        """
        Connect to WiFi
        
        Args:
            display_callback: Optional callback function to update display during connection attempts
            
        Returns:
            True if connected, False otherwise
        """
        if is_dev_mode() or not self.HAS_WIFI:
            _logger().debug("WiFi not available or in dev mode, simulating connection")
            self.is_connected = True
            return True
            
        try:
            if not self.ssid or not self.password:
                _logger().error(ValueError("Missing WiFi credentials"), "WiFi credentials not found")
                return False
                
            _logger().info(f"Connecting to WiFi network: {self.ssid}")
            
            # Maximum connection attempts
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    # Connect to the network
                    self.wifi.radio.connect(self.ssid, self.password)
                    self.is_connected = True
                    break
                except Exception as conn_err:
                    # Only log on final attempt, otherwise just try again
                    if attempt == max_attempts - 1:
                        _logger().error(conn_err, f"Failed to connect to WiFi after {max_attempts} attempts")
                    
                    # Update display if callback provided
                    if display_callback:
                        await display_callback(f"Attempt {attempt+1}/{max_attempts}")
                    
                    # Short delay before retry
                    await asyncio.sleep(1)
            
            if self.is_connected:
                # Log connection info
                ip_address = self.wifi.radio.ipv4_address
                _logger().info(f"Connected to WiFi. IP address: {ip_address}")
                
                # Now that we're connected, create the HTTP session
                # This should only happen AFTER a successful WiFi connection
                try:
                    session = self.create_http_session()
                    _logger().info("Created HTTP session after WiFi connection")
                except Exception as session_error:
                    _logger().error(session_error, "Failed to create HTTP session after WiFi connection")
                
                return True
            else:
                return False
            
        except Exception as e:
            _logger().error(e, "Error connecting to WiFi")
            self.is_connected = False
            return False
            
    def create_http_session(self):
        """
        Create and return a new HTTP session
        This should only be called after WiFi is connected
        
        Returns:
            A new adafruit_requests.Session or None if not available
        """
        if is_dev_mode() or not self.HAS_WIFI or not self.is_connected:
            _logger().debug("Cannot create HTTP session without WiFi connection or in dev mode")
            return None
            
        try:
            import ssl
            import socketpool
            import adafruit_requests
            
            # Create a fresh socket pool from the radio
            pool = socketpool.SocketPool(self.wifi.radio)
            
            # Create a new SSL context
            ssl_context = ssl.create_default_context()
            
            # Create and return the session
            session = adafruit_requests.Session(pool, ssl_context)
            return session

        except Exception as e:
            _logger().error(e, "Error creating HTTP session")
            return None

    async def reconnect(self):
        """
        Reconnect to WiFi if disconnected

        Returns:
            True if connected, False otherwise
        """
        if self.is_connected:
            return True

        # Try to reconnect
        return await self.connect()

    async def bounce(self):
        """FORCE a radio restart + fresh association, even when the link looks up.

        ``reconnect()`` is useless against the long-uptime field wedge this
        exists for: after ~26 h the ESP32's WiFi/lwIP session can degrade so
        INBOUND traffic still works (the radio reports connected, the device's
        web server answers) while every OUTBOUND ``connect()`` fails EBUSY —
        session rebuilds and pooled-socket eviction cannot clear it, but a
        radio disconnect + reassociation does (verified live on hardware,
        2026-07-15: a bare ``wifi.radio.connect()`` at the REPL restored
        outbound TCP AND TLS with the wedged app state still in RAM).

        After a successful bounce the caller should drop pooled sockets
        (``HttpClient.close_pooled_sockets()``) — they belonged to the dead
        association. Returns True if reassociated; never raises. Desktop/dev:
        no-op True.
        """
        if is_dev_mode():
            return True
        try:
            try:
                import wifi
                wifi.radio.enabled = False
                await asyncio.sleep(1)
                wifi.radio.enabled = True
            except Exception as e:
                _logger().error(e, "radio disable/enable failed; trying plain connect")
            return bool(await self.connect())
        except Exception as e:
            _logger().error(e, "WiFi bounce failed")
            return False

    def bounce_sync(self):
        """Synchronous ``bounce()`` for non-async call sites (the update-check
        runs inside a synchronous web handler). Radio off → settle → on →
        direct ``wifi.radio.connect`` with the saved credentials — no display
        callbacks, no retries. Returns True if reassociated; never raises.
        Desktop/dev: no-op True.
        """
        if is_dev_mode():
            return True
        try:
            import time
            import wifi
            try:
                wifi.radio.enabled = False
                time.sleep(1)
                wifi.radio.enabled = True
            except Exception as e:
                _logger().error(e, "radio disable/enable failed; trying plain connect")
            ssid, password = self._resolve_credentials()
            if not ssid:
                return False
            wifi.radio.connect(ssid, password)
            return wifi.radio.ipv4_address is not None
        except Exception as e:
            _logger().error(e, "WiFi bounce_sync failed")
            return False
        
    def save_credentials(self):
        """
        Save WiFi credentials to settings manager
        """
        if hasattr(self, 'settings_manager') and self.settings_manager:
            try:
                # Save SSID and password to settings
                self.settings_manager.settings["wifi_ssid"] = self.ssid
                self.settings_manager.settings["wifi_password"] = self.password

                # Save settings to disk
                self.settings_manager.save_settings()
                _logger().info(f"Saved WiFi credentials to settings manager")

            except Exception as e:
                _logger().error(e, "Failed to save WiFi credentials to settings manager")

    def scan_networks(self):
        """
        Scan for available WiFi networks
        
        Returns:
            List of network info (SSID, RSSI, channel, security)
        """
        if is_dev_mode() or not self.HAS_WIFI:
            _logger().debug("WiFi not available or in dev mode, returning mock networks")
            # Return mock data for testing
            return [
                {"ssid": "HomeNetwork", "rssi": -65, "channel": 6},
                {"ssid": "GuestWiFi", "rssi": -70, "channel": 11}
            ]
            
        try:
            _logger().debug("Scanning for WiFi networks...")
            networks = []
            
            # Scan for networks
            for network in self.wifi.radio.start_scanning_networks():
                # Skip hidden networks
                if not network.ssid:
                    continue
                    
                net_info = {
                    "ssid": network.ssid,
                    "rssi": network.rssi,
                    "channel": network.channel
                }
                networks.append(net_info)
                
            # Sort networks by signal strength (strongest first)
            networks.sort(key=lambda x: x["rssi"], reverse=True)
            
            self.wifi.radio.stop_scanning_networks()
            _logger().debug(f"Found {len(networks)} WiFi networks")
            return networks
            
        except Exception as e:
            _logger().error(e, "Error scanning for WiFi networks")
            # Return empty list on error
            return []

    # ------------------------------------------------------------------ #
    # Access-point mode + the no-file-editing setup portal
    # ------------------------------------------------------------------ #

    def start_access_point(self):
        """Start the device's own WiFi access point (for the setup portal)."""
        if is_dev_mode() or not self.HAS_WIFI:
            _logger().debug("Simulating access point in dev mode")
            self.ap_enabled = True
            return

        self.wifi.radio.enabled = True
        if not self.ap_enabled:
            authmodes = getattr(self, "AP_AUTHMODES", None)
            open_ap = bool(authmodes) and authmodes[0] == self.wifi.AuthMode.OPEN
            if open_ap:
                self.wifi.radio.start_ap(ssid=self.AP_SSID, authmode=authmodes)
            else:
                self.wifi.radio.start_ap(ssid=self.AP_SSID,
                                         password=self.AP_PASSWORD,
                                         authmode=authmodes)
            self.ap_enabled = True

    def stop_access_point(self):
        """Stop the device's WiFi access point."""
        if is_dev_mode() or not self.HAS_WIFI:
            self.ap_enabled = False
            return
        try:
            self.wifi.radio.stop_ap()
        except Exception as e:
            _logger().error(e, "Error stopping access point")
        self.ap_enabled = False

    def ap_ip_address(self):
        """The IP a phone should browse to while joined to the setup AP."""
        if is_dev_mode() or not self.HAS_WIFI:
            return "127.0.0.1"
        try:
            return str(self.wifi.radio.ipv4_address_ap)
        except Exception:
            # CircuitPython's soft-AP default; better than nothing on panels.
            return "192.168.4.1"

    async def run_setup_portal(self, display=None, *, port=80, reboot=True,
                               timeout_s=None):
        """Run the no-file-editing WiFi onboarding portal (blocking).

        Starts the device's own access point and serves a setup page where
        the user picks a network + password from a phone; credentials are
        saved via the SettingsManager (settings.json — never a code file) and
        the device reboots to connect. Typical wiring, at the START of an
        app's setup() — before the display loop owns the screen::

            wm = WiFiManager(self.settings)
            if not await wm.connect():
                await wm.run_setup_portal(display=self.display)
                # (device reboots on save; on desktop this just returns)

        Args:
            display: Optional DisplayInterface — join instructions are
                scrolled on the panel while the portal runs.
            port: HTTP port for the portal (default 80).
            reboot: Reboot the device after a successful save (hardware
                only; desktop always just returns). A fresh boot picks the
                saved credentials up via _resolve_credentials().
            timeout_s: Optional give-up timeout in seconds.

        Returns:
            True when credentials were saved, else False.

        Imported lazily so an already-configured boot never pays RAM for the
        portal. Contract: the portal only writes settings; it owns the
        display exclusively (boot phase), never the content queue.
        """
        from scrollkit.web.wifi_setup import WiFiSetupPortal
        portal = WiFiSetupPortal(self, display=display, port=port)
        saved = await portal.run(timeout_s=timeout_s)
        if saved and reboot and is_circuitpython:
            # Hardware only: a clean reboot re-runs boot with the new
            # credentials. reset() sleeps ~4s first, letting the linger page
            # note on the panel be seen.
            await self.reset()
        return saved

