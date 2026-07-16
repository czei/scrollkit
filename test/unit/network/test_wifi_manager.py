"""
Tests for the WiFiManager class.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from scrollkit.network.wifi_manager import WiFiManager
from scrollkit.config.settings_manager import SettingsManager


class TestWiFiManager:
    def test_initialization_with_wifi(self):
        """Test initialization with WiFi module available"""
        # Mock is_dev_mode to return False
        with patch('scrollkit.network.wifi_manager.is_dev_mode', return_value=False):
            # Mock the wifi import
            mock_wifi = MagicMock()
            mock_wifi.radio.mac_address_ap = [0x00, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE]
            # Mock AuthMode enum
            mock_wifi.AuthMode.WPA2 = 1
            mock_wifi.AuthMode.PSK = 2
            mock_wifi.AuthMode.OPEN = 0
            
            # Mock settings manager
            mock_sm = MagicMock()
            
            # Mock load_credentials
            with patch('scrollkit.network.wifi_manager.load_credentials') as mock_load_credentials:
                mock_load_credentials.return_value = ('TestSSID', 'TestPassword')
                
                # Mock the import statement inside the __init__ method
                with patch.dict('sys.modules', {'wifi': mock_wifi}):
                    # Create WiFiManager
                    wifi_manager = WiFiManager(mock_sm)
                    
                    # Verify initialization
                    assert wifi_manager.HAS_WIFI is True
                    assert wifi_manager.ssid == 'TestSSID'
                    assert wifi_manager.password == 'TestPassword'
                    assert wifi_manager.is_connected is False
                    # Hyphen separator since ap_name became configurable:
                    # "<base>-<MAC tail>" (base defaults to WifiManager).
                    assert "WifiManager-" in wifi_manager.AP_SSID
    
    def test_initialization_without_wifi(self):
        """Test initialization without WiFi module available"""
        mock_sm = MagicMock()

        with patch('scrollkit.network.wifi_manager.load_credentials') as mock_load_credentials:
            mock_load_credentials.return_value = ('TestSSID', 'TestPassword')
            # Simulate no wifi module by not adding it to sys.modules
            wifi_manager = WiFiManager(mock_sm)

            assert wifi_manager.HAS_WIFI is False
            assert wifi_manager.ssid == 'TestSSID'
            assert wifi_manager.password == 'TestPassword'
            assert wifi_manager.is_connected is False
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful WiFi connection"""
        mock_wifi = MagicMock()
        mock_wifi.radio.connect = MagicMock()
        mock_wifi.radio.ipv4_address = "192.168.1.100"

        mock_sm = MagicMock()

        with patch('scrollkit.network.wifi_manager.load_credentials') as mock_load_credentials:
            mock_load_credentials.return_value = ('TestSSID', 'TestPassword')

            with patch.dict('sys.modules', {'wifi': mock_wifi}):
                wifi_manager = WiFiManager(mock_sm)
                wifi_manager.create_http_session = MagicMock(return_value=MagicMock())

                mock_callback = AsyncMock()
                result = await wifi_manager.connect(display_callback=mock_callback)

                assert result is True
                assert wifi_manager.is_connected is True
                mock_wifi.radio.connect.assert_called_once_with('TestSSID', 'TestPassword')
                assert wifi_manager.create_http_session.called
    
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test failed WiFi connection"""
        mock_wifi = MagicMock()
        mock_wifi.radio.connect = MagicMock(side_effect=Exception("Connection failed"))

        mock_sm = MagicMock()

        with patch('scrollkit.network.wifi_manager.load_credentials') as mock_load_credentials:
            mock_load_credentials.return_value = ('TestSSID', 'TestPassword')

            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                with patch.dict('sys.modules', {'wifi': mock_wifi}):
                    wifi_manager = WiFiManager(mock_sm)

                    mock_callback = AsyncMock()
                    result = await wifi_manager.connect(display_callback=mock_callback)

                    assert result is False
                    assert wifi_manager.is_connected is False
                    assert mock_wifi.radio.connect.call_count == 3
                    assert mock_callback.call_count == 3
                    assert mock_sleep.call_count == 3
    
    @pytest.mark.asyncio
    async def test_connect_no_credentials(self):
        """Test connection with missing credentials"""
        # Mock is_dev_mode to return False
        with patch('scrollkit.network.wifi_manager.is_dev_mode', return_value=False):
            # Mock the wifi import
            mock_wifi = MagicMock()
            
            # Mock settings manager
            mock_sm = MagicMock()
            
            # Mock load_credentials to return empty credentials
            with patch('scrollkit.network.wifi_manager.load_credentials') as mock_load_credentials:
                mock_load_credentials.return_value = ('', '')
                
                # Mock logger to prevent actual logging
                with patch('scrollkit.network.wifi_manager._logger') as mock_logger:
                    # Mock the import statement
                    with patch.dict('sys.modules', {'wifi': mock_wifi}):
                        # Create WiFiManager
                        wifi_manager = WiFiManager(mock_sm)
                        
                        # Connect to WiFi (should fail due to missing credentials)
                        result = await wifi_manager.connect()
                        
                        # Verify connection failed
                        assert result is False
    
    @pytest.mark.asyncio
    async def test_reconnect(self):
        """Test reconnection when disconnected"""
        # Mock is_dev_mode to return False
        with patch('scrollkit.network.wifi_manager.is_dev_mode', return_value=False):
            # Mock the wifi import
            mock_wifi = MagicMock()
            
            # Mock settings manager
            mock_sm = MagicMock()
            
            # Mock load_credentials
            with patch('scrollkit.network.wifi_manager.load_credentials') as mock_load_credentials:
                mock_load_credentials.return_value = ('TestSSID', 'TestPassword')
                
                # Mock logger to prevent actual logging
                with patch('scrollkit.network.wifi_manager._logger') as mock_logger:
                    # Mock the import statement
                    with patch.dict('sys.modules', {'wifi': mock_wifi}):
                        # Create WiFiManager with connect method mocked
                        wifi_manager = WiFiManager(mock_sm)
                        wifi_manager.connect = AsyncMock(return_value=True)
                        
                        # Test when already connected
                        wifi_manager.is_connected = True
                        result = await wifi_manager.reconnect()
                        assert result is True
                        assert not wifi_manager.connect.called
                        
                        # Test when disconnected
                        wifi_manager.is_connected = False
                        result = await wifi_manager.reconnect()
                        assert result is True
                        assert wifi_manager.connect.called
    
    def test_create_http_session(self):
        """Test HTTP session creation"""
        mock_wifi = MagicMock()
        mock_sm = MagicMock()

        with patch('scrollkit.network.wifi_manager.load_credentials') as mock_load_credentials:
            mock_load_credentials.return_value = ('TestSSID', 'TestPassword')

            with patch.dict('sys.modules', {'wifi': mock_wifi}):
                wifi_manager = WiFiManager(mock_sm)
                wifi_manager.is_connected = True

                mock_ssl = MagicMock()
                mock_pool = MagicMock()
                mock_requests = MagicMock()
                mock_socketpool = MagicMock()
                mock_socketpool.SocketPool = MagicMock(return_value=mock_pool)
                mock_session = MagicMock()
                mock_requests.Session.return_value = mock_session

                with patch.dict('sys.modules', {
                    'ssl': mock_ssl,
                    'socketpool': mock_socketpool,
                    'adafruit_requests': mock_requests,
                }):
                    result = wifi_manager.create_http_session()

                    assert result is not None
                    mock_requests.Session.assert_called_once()
    
    def test_scan_networks(self):
        """Test scanning for WiFi networks"""
        # Mock is_dev_mode to return False
        with patch('scrollkit.network.wifi_manager.is_dev_mode', return_value=False):
            # Mock the wifi import
            mock_wifi = MagicMock()
            # Setup mock networks
            mock_network1 = MagicMock(ssid="Network1", rssi=-65, channel=6)
            mock_network2 = MagicMock(ssid="Network2", rssi=-75, channel=11)
            mock_hidden = MagicMock(ssid="", rssi=-80, channel=1)  # Hidden network should be skipped
            
            mock_wifi.radio.start_scanning_networks.return_value = [
                mock_network1, mock_network2, mock_hidden
            ]
            
            # Mock settings manager
            mock_sm = MagicMock()
            
            # Mock load_credentials
            with patch('scrollkit.network.wifi_manager.load_credentials') as mock_load_credentials:
                # Mock logger to prevent actual logging
                with patch('scrollkit.network.wifi_manager._logger') as mock_logger:
                    mock_load_credentials.return_value = ('TestSSID', 'TestPassword')
                    
                    # Mock the import statement
                    with patch.dict('sys.modules', {'wifi': mock_wifi}):
                        # Create WiFiManager
                        wifi_manager = WiFiManager(mock_sm)
                        # Force non-HAS_WIFI mode to test the mock path
                        wifi_manager.HAS_WIFI = False
                        
                        # Scan networks
                        networks = wifi_manager.scan_networks()
                        
                        # Verify mock networks were returned
                        assert len(networks) == 2  # Should return 2 mock networks
                        assert networks[0]["ssid"] == "HomeNetwork"
                        assert networks[1]["ssid"] == "GuestWiFi"
    
    def test_save_credentials(self):
        """Test saving WiFi credentials"""
        # Mock is_dev_mode to return False
        with patch('scrollkit.network.wifi_manager.is_dev_mode', return_value=False):
            # Mock the wifi import
            mock_wifi = MagicMock()
            
            # Mock settings manager
            mock_sm = MagicMock()
            mock_sm.settings = {}
            
            # Mock load_credentials
            with patch('scrollkit.network.wifi_manager.load_credentials') as mock_load_credentials:
                # Mock logger to prevent actual logging
                with patch('scrollkit.network.wifi_manager._logger') as mock_logger:
                    mock_load_credentials.return_value = ('TestSSID', 'TestPassword')

                    # Mock the import statement
                    with patch.dict('sys.modules', {'wifi': mock_wifi}):
                        # Create WiFiManager
                        wifi_manager = WiFiManager(mock_sm)

                        # Update credentials
                        wifi_manager.ssid = "NewSSID"
                        wifi_manager.password = "NewPassword"

                        # Save credentials
                        wifi_manager.save_credentials()

                        # Verify credentials were saved to settings manager
                        assert mock_sm.settings["wifi_ssid"] == "NewSSID"
                        assert mock_sm.settings["wifi_password"] == "NewPassword"
                        assert mock_sm.save_settings.called


def _real_sm(saved):
    with patch.object(SettingsManager, "load_settings", return_value=saved):
        return SettingsManager("test_settings.json")


class TestCredentialsPrecedence:
    """The no-file-editing promise: portal-saved settings beat secrets.py."""

    def test_settings_credentials_win_over_secrets(self):
        sm = _real_sm({"wifi_ssid": "PortalNet", "wifi_password": "portalpw"})
        with patch("scrollkit.network.wifi_manager.load_credentials",
                   return_value=("SecretsNet", "secretspw")):
            wm = WiFiManager(sm)
        assert wm.ssid == "PortalNet"
        assert wm.password == "portalpw"

    def test_falls_back_to_secrets_when_settings_empty(self):
        sm = _real_sm({})
        with patch("scrollkit.network.wifi_manager.load_credentials",
                   return_value=("SecretsNet", "secretspw")):
            wm = WiFiManager(sm)
        assert wm.ssid == "SecretsNet"

    def test_non_string_settings_values_are_ignored(self):
        sm = _real_sm({"wifi_ssid": 12345})   # garbage after a bad write
        with patch("scrollkit.network.wifi_manager.load_credentials",
                   return_value=("SecretsNet", "secretspw")):
            wm = WiFiManager(sm)
        assert wm.ssid == "SecretsNet"

    def test_settings_ssid_with_missing_password_defaults_empty(self):
        sm = _real_sm({"wifi_ssid": "OpenNet"})
        with patch("scrollkit.network.wifi_manager.load_credentials",
                   return_value=("SecretsNet", "secretspw")):
            wm = WiFiManager(sm)
        assert wm.ssid == "OpenNet"
        assert wm.password == ""


class TestAccessPointDevMode:
    """The restored AP half of the onboarding feature (simulated on desktop)."""

    def _wm(self):
        with patch("scrollkit.network.wifi_manager.load_credentials",
                   return_value=("", "")):
            return WiFiManager(MagicMock())

    def test_start_and_stop_toggle_ap_enabled(self):
        wm = self._wm()
        assert wm.ap_enabled is False
        wm.start_access_point()
        assert wm.ap_enabled is True
        wm.stop_access_point()
        assert wm.ap_enabled is False

    def test_ap_ip_address_in_dev_mode(self):
        assert self._wm().ap_ip_address() == "127.0.0.1"


class TestRunSetupPortal:
    @pytest.mark.asyncio
    async def test_delegates_to_portal_and_skips_reboot_on_desktop(self):
        with patch("scrollkit.network.wifi_manager.load_credentials",
                   return_value=("", "")):
            wm = WiFiManager(MagicMock())

        portal_instance = MagicMock()
        portal_instance.run = AsyncMock(return_value=True)
        portal_cls = MagicMock(return_value=portal_instance)
        wm.reset = AsyncMock()

        with patch("scrollkit.web.wifi_setup.WiFiSetupPortal", portal_cls):
            saved = await wm.run_setup_portal(display="DISPLAY", timeout_s=9)

        assert saved is True
        portal_cls.assert_called_once_with(wm, display="DISPLAY", port=80)
        portal_instance.run.assert_awaited_once_with(timeout_s=9)
        # Desktop never reboots — that's hardware-only behavior.
        wm.reset.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_false_when_nothing_saved(self):
        with patch("scrollkit.network.wifi_manager.load_credentials",
                   return_value=("", "")):
            wm = WiFiManager(MagicMock())
        portal_instance = MagicMock()
        portal_instance.run = AsyncMock(return_value=False)
        with patch("scrollkit.web.wifi_setup.WiFiSetupPortal",
                   MagicMock(return_value=portal_instance)):
            assert await wm.run_setup_portal() is False

class TestAccessPointNaming:
    """The onboarding AP's SSID base is per-app configuration (ap_name), never a
    product name hardwired in the library. The library owns only the uniqueness
    tail (MAC-derived on hardware, -DEV off-device)."""

    def _make(self, **kw):
        mock_sm = MagicMock()
        with patch('scrollkit.network.wifi_manager.load_credentials') as lc:
            lc.return_value = ('TestSSID', 'TestPassword')
            return WiFiManager(mock_sm, **kw)

    def test_default_base_is_generic(self):
        wm = self._make()
        assert wm.AP_SSID.startswith("WifiManager-")
        assert "ThemeParkWaits" not in wm.AP_SSID     # no app brand in the library

    def test_app_brand_flows_through(self):
        wm = self._make(ap_name="ThemeParkWaits")
        assert wm.AP_SSID.startswith("ThemeParkWaits-")


class TestBounce:
    """bounce(): the forced radio restart for the looks-up-but-outbound-dead wedge."""

    @pytest.mark.asyncio
    async def test_bounce_is_noop_true_in_dev_mode(self):
        with patch('scrollkit.network.wifi_manager.is_dev_mode', return_value=True):
            wifi_manager = WiFiManager(MagicMock())
            wifi_manager.connect = AsyncMock(return_value=True)

            assert await wifi_manager.bounce() is True
            wifi_manager.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_bounce_toggles_radio_and_reconnects_even_when_connected(self):
        """Unlike reconnect(), bounce() must act while the link LOOKS up — the
        2026-07-15 wedge kept is_connected True while outbound was dead."""
        with patch('scrollkit.network.wifi_manager.is_dev_mode', return_value=False):
            mock_wifi = MagicMock()
            with patch.dict('sys.modules', {'wifi': mock_wifi}):
                wifi_manager = WiFiManager(MagicMock())
                wifi_manager.is_connected = True
                wifi_manager.connect = AsyncMock(return_value=True)

                assert await wifi_manager.bounce() is True

                # Radio power-cycled (left ON afterwards) and reassociated.
                assert mock_wifi.radio.enabled is True
                wifi_manager.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_bounce_never_raises(self):
        with patch('scrollkit.network.wifi_manager.is_dev_mode', return_value=False):
            mock_wifi = MagicMock()
            with patch.dict('sys.modules', {'wifi': mock_wifi}):
                wifi_manager = WiFiManager(MagicMock())
                wifi_manager.connect = AsyncMock(side_effect=RuntimeError("assoc failed"))

                assert await wifi_manager.bounce() is False

    @pytest.mark.asyncio
    async def test_bounce_sync_is_noop_true_in_dev_mode(self):
        with patch('scrollkit.network.wifi_manager.is_dev_mode', return_value=True):
            wifi_manager = WiFiManager(MagicMock())
            assert wifi_manager.bounce_sync() is True

    def test_bounce_sync_toggles_radio_and_connects(self):
        with patch('scrollkit.network.wifi_manager.is_dev_mode', return_value=False):
            mock_wifi = MagicMock()
            mock_wifi.radio.ipv4_address = "10.0.0.9"
            with patch.dict('sys.modules', {'wifi': mock_wifi}):
                wifi_manager = WiFiManager(MagicMock())
                wifi_manager._resolve_credentials = lambda: ("SSID", "pw")

                assert wifi_manager.bounce_sync() is True
                assert mock_wifi.radio.enabled is True
                mock_wifi.radio.connect.assert_called_once_with("SSID", "pw")

    def test_bounce_sync_never_raises(self):
        with patch('scrollkit.network.wifi_manager.is_dev_mode', return_value=False):
            mock_wifi = MagicMock()
            mock_wifi.radio.connect.side_effect = RuntimeError("assoc failed")
            with patch.dict('sys.modules', {'wifi': mock_wifi}):
                wifi_manager = WiFiManager(MagicMock())
                wifi_manager._resolve_credentials = lambda: ("SSID", "pw")
                assert wifi_manager.bounce_sync() is False
