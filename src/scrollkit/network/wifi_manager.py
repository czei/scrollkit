"""
WiFi connection management.
Copyright (c) 2024-2026 Michael Winslow Czeiszperger
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
    
    def __init__(self, settings_manager):
        """
        Initialize the WiFi manager
        
        Args:
            settings_manager: The settings manager
        """
        self.settings_manager = settings_manager
        self.ssid, self.password = load_credentials()
        self.is_connected = False
        self.wifi_client = None
        self.ap_enabled = False

        # Development mode values
        self.AP_SSID = "WifiManager_DEV"
        self.AP_PASSWORD = "password"

        try:
            # Check if in development mode
            if is_dev_mode():
                # In dev mode, simulate WiFi capabilities
                _logger().info("Running in development mode, using simulated WiFi")
                self.wifi = None
                self.HAS_WIFI = False
                # Set dummy values for development
                self.AP_SSID = "WifiManager_DEV"
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
            self.AP_SSID = "WifiManager_" + mac_ap[5:10] + mac_ap[1:2]
            self.AP_PASSWORD = "password"
            self.AP_AUTHMODES = [self.wifi.AuthMode.WPA2, self.wifi.AuthMode.PSK]
            
        except (ImportError, AttributeError) as e:
            # Mock for non-CircuitPython environments
            self.wifi = None
            self.HAS_WIFI = False
            _logger().debug(f"WiFi module not available or incomplete: {e}")

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

    async def disconnect(self):
        """Disconnect from WiFi"""
        if is_dev_mode() or not self.HAS_WIFI or not self.is_connected:
            return
            
        try:
            _logger().info("Disconnecting from WiFi")
            # Some CircuitPython versions may not have the disconnect method
            if hasattr(self.wifi.radio, 'disconnect'):
                self.wifi.radio.disconnect()
            self.is_connected = False
            
        except Exception as e:
            _logger().error(e, "Error disconnecting from WiFi")
            
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
        
    def is_available(self):
        """
        Check if WiFi is available
        
        Returns:
            True if WiFi is available, False otherwise
        """
        return self.HAS_WIFI or is_dev_mode()

    def get_ip_address(self):
        """
        Get the current IP address
        
        Returns:
            The IP address as a string, or None if not connected
        """
        if is_dev_mode():
            # In dev mode, return a dummy IP
            return "127.0.0.1"
            
        if not self.HAS_WIFI or not self.is_connected:
            return None
            
        try:
            return str(self.wifi.radio.ipv4_address)
        except Exception:
            return None
            
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

    def start_access_point(self,port=80):
        """Start the WiFi access point"""
        if is_dev_mode() or not self.HAS_WIFI:
            _logger().debug("Cannot start access point in dev mode or without WiFi hardware")
            self.ap_enabled = True
            return
            
        self.wifi.radio.enabled = True
        if self.ap_enabled is False:
            # to use encrypted AP, use authmode=[wifi.AuthMode.WPA2, wifi.AuthMode.PSK]
            if (self.AP_AUTHMODES[0] == self.wifi.AuthMode.OPEN):
                self.wifi.radio.start_ap(ssid=self.AP_SSID, authmode=self.AP_AUTHMODES)
            else:
                self.wifi.radio.start_ap(ssid=self.AP_SSID, password=self.AP_PASSWORD, authmode=self.AP_AUTHMODES)
            self.ap_enabled = True

    def stop_access_point(self):
        """Stop the WiFi access point"""
        if is_dev_mode() or not self.HAS_WIFI:
            _logger().debug("Cannot stop access point in dev mode or without WiFi hardware")
            self.ap_enabled = False
            return
            
        self.wifi.radio.stop_ap()
        self.ap_enabled = False
        
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

