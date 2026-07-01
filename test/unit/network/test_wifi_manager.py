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
                    assert "WifiManager_" in wifi_manager.AP_SSID
    
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
                with patch('scrollkit.network.wifi_manager.logger') as mock_logger:
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
                with patch('scrollkit.network.wifi_manager.logger') as mock_logger:
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
                with patch('scrollkit.network.wifi_manager.logger') as mock_logger:
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
                with patch('scrollkit.network.wifi_manager.logger') as mock_logger:
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