"""
Tests for the ThemeParkService class.
"""
import json
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.api.theme_park_service import ThemeParkService
from src.models.theme_park import ThemePark
from src.models.theme_park_list import ThemeParkList
from src.models.vacation import Vacation
from src.config.settings_manager import SettingsManager

class TestThemeParkService:
    def test_initialization(self):
        """Test initializing the ThemeParkService"""
        # Create mock http client and settings manager
        mock_http = MagicMock()
        mock_settings = MagicMock()
        
        # Initialize service
        service = ThemeParkService(mock_http, mock_settings)
        
        # Verify attributes were set
        assert service.http_client == mock_http
        assert service.settings_manager == mock_settings
        assert service.park_list is None
        assert isinstance(service.vacation, Vacation)
        assert service.update_needed is False
    
    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Test successful initialization"""
        # Create mock http client and settings manager
        mock_http = MagicMock()
        mock_settings = MagicMock()
        mock_settings.settings = {}
        
        # Create successful response for park list
        mock_response = MagicMock()
        mock_response.text = json.dumps([{"id": 1, "name": "Test Park"}])
        
        # Set up http client to return the response
        mock_http.get = AsyncMock(return_value=mock_response)
        
        # Create the service
        service = ThemeParkService(mock_http, mock_settings)
        
        # Mock park list and vacation methods
        with patch('src.api.theme_park_service.ThemeParkList') as mock_park_list_class:
            mock_park_list = MagicMock()
            mock_park_list.park_list = [MagicMock()]  # Non-empty list
            mock_park_list_class.return_value = mock_park_list
            
            # Also need to mock logger
            with patch('src.api.theme_park_service.logger') as mock_logger:
                # Call initialize
                await service.initialize()
                
                # Verify http client was called
                mock_http.get.assert_called_once_with("https://queue-times.com/parks.json")
                
                # Verify park list and vacation settings were loaded
                mock_park_list.load_settings.assert_called_once_with(mock_settings)
                
                # Verify park list was created and stored
                assert service.park_list == mock_park_list
    
    @pytest.mark.asyncio
    async def test_initialize_retry(self):
        """Test initialization with retries"""
        # Create mock http client and settings manager
        mock_http = MagicMock()
        mock_settings = MagicMock()
        
        # Create a failed response followed by a successful one
        mock_http.get = AsyncMock(side_effect=[
            Exception("Network error"),  # First attempt fails
            MagicMock(text=json.dumps([{"id": 1, "name": "Test Park"}]))  # Second succeeds
        ])
        
        # Create the service
        service = ThemeParkService(mock_http, mock_settings)
        
        # Mock sleep to avoid waiting
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Mock park list and vacation methods
            with patch('src.api.theme_park_service.ThemeParkList') as mock_park_list_class:
                mock_park_list = MagicMock()
                mock_park_list.park_list = [MagicMock()]  # Non-empty list
                mock_park_list_class.return_value = mock_park_list
                
                with patch.object(Vacation, 'load_settings') as mock_vacation_load:
                    # Call initialize
                    await service.initialize()
                    
                    # Verify http client was called twice
                    assert mock_http.get.call_count == 2
                    
                    # Verify sleep was called after first failure
                    mock_sleep.assert_called()
                    
                    # Verify park list was created from second attempt
                    mock_park_list_class.assert_called()
                    assert service.park_list == mock_park_list
    
    @pytest.mark.asyncio
    async def test_initialize_all_retries_fail(self):
        """Test initialization when all retries fail"""
        mock_http = MagicMock()
        mock_settings = MagicMock()
        mock_settings.settings = {}

        # All HTTP calls fail
        mock_http.get = AsyncMock(side_effect=Exception("Network error"))

        service = ThemeParkService(mock_http, mock_settings)

        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch('src.api.theme_park_service.ThemeParkList') as mock_park_list_class:
                mock_park_list = MagicMock()
                mock_park_list.park_list = []  # Empty - triggers another attempt
                mock_park_list_class.return_value = mock_park_list
                with patch.object(Vacation, 'load_settings'):
                    with patch('src.api.theme_park_service.logger'):
                        await service.initialize()

                        # Should have created an empty park list as fallback
                        mock_park_list_class.assert_called_with([])
                        assert service.park_list is not None

    @pytest.mark.asyncio
    async def test_fetch_park_list_failure(self):
        """Test park list fetching when all retries fail"""
        mock_http = MagicMock()
        mock_settings = MagicMock()
        mock_settings.settings = {}

        # All HTTP calls fail
        mock_http.get = AsyncMock(side_effect=Exception("Network error"))

        service = ThemeParkService(mock_http, mock_settings)

        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch('src.api.theme_park_service.logger'):
                result = await service.fetch_park_list()

                # Should return empty park list as fallback
                assert result is not None
                assert len(result.park_list) == 0
                # Should have tried 3 times
                assert mock_http.get.call_count == 3
    
    @pytest.mark.asyncio
    async def test_fetch_park_data_success(self):
        """Test fetching park data successfully"""
        # Create mock http client and settings manager
        mock_http = MagicMock()
        mock_settings = MagicMock()
        
        # Create successful response
        mock_response = MagicMock()
        mock_response.text = json.dumps({"lands": [], "rides": []})
        mock_http.get = AsyncMock(return_value=mock_response)
        
        # Create the service
        service = ThemeParkService(mock_http, mock_settings)
        
        # Call fetch_park_data
        result = await service.fetch_park_data(1)
        
        # Verify http client was called with correct URL
        mock_http.get.assert_called_once_with("https://queue-times.com/parks/1/queue_times.json")
        
        # Verify result
        assert result == {"lands": [], "rides": []}
    
    @pytest.mark.asyncio
    async def test_fetch_park_data_failure(self):
        """Test fetch park data failure"""
        # Create mock http client and settings manager
        mock_http = MagicMock()
        mock_settings = MagicMock()
        
        # Make http request fail
        mock_http.get = AsyncMock(side_effect=Exception("Network error"))
        
        # Create the service
        service = ThemeParkService(mock_http, mock_settings)
        
        # Mock asyncio.sleep to prevent delays in testing
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Mock logger
            with patch('src.api.theme_park_service.logger') as mock_logger:
                # Call fetch_park_data
                result = await service.fetch_park_data(1)
                
                # Verify http client was called for each attempt (should be 2 retries now)
                assert mock_http.get.call_count == 2
                
                # Verify sleep was called between retries (only 1 sleep for 2 attempts)
                assert mock_sleep.call_count == 1
                
                # Verify the correct URL was called
                mock_http.get.assert_called_with("https://queue-times.com/parks/1/queue_times.json")
                
                # Verify error was logged
                assert mock_logger.error.call_count > 0
                
                # Verify result is None on failure
                assert result is None
    
    @pytest.mark.asyncio
    async def test_update_current_park_success(self):
        """Test updating current park successfully"""
        # Create mock http client and settings manager
        mock_http = MagicMock()
        mock_settings = MagicMock()
        
        # Create the service
        service = ThemeParkService(mock_http, mock_settings)
        
        # Create a mock park list with current park
        mock_park = MagicMock()
        mock_park.id = 1
        mock_park.is_valid.return_value = True
        
        mock_park_list = MagicMock()
        mock_park_list.current_park = mock_park
        
        service.park_list = mock_park_list
        
        # Mock fetch_park_data to return test data
        park_data = {"lands": [], "rides": []}
        with patch.object(service, 'fetch_park_data', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = park_data
            
            # Call update_current_park
            result = await service.update_current_park()
            
            # Verify fetch_park_data was called
            mock_fetch.assert_called_once_with(1)
            
            # Verify park.update was called
            mock_park.update.assert_called_once_with(park_data)
            
            # Verify result is True on success
            assert result is True
    
    @pytest.mark.asyncio
    async def test_update_current_park_no_valid_park(self):
        """Test update current park with no valid park"""
        # Create mock http client and settings manager
        mock_http = MagicMock()
        mock_settings = MagicMock()
        
        # Create the service
        service = ThemeParkService(mock_http, mock_settings)
        
        # Two test cases: park_list is None, and current_park is not valid
        
        # Case 1: park_list is None
        service.park_list = None
        
        # Mock logger
        with patch('src.api.theme_park_service.logger') as mock_logger:
            # Call update_current_park
            result = await service.update_current_park()
            
            # Verify debug message
            mock_logger.debug.assert_called_once_with("No valid current park to update")
            
            # Verify result is False
            assert result is False
            
            # Reset mocks
            mock_logger.reset_mock()
            
            # Case 2: park_list exists but current_park is not valid
            mock_park = MagicMock()
            mock_park.is_valid.return_value = False
            
            mock_park_list = MagicMock()
            mock_park_list.current_park = mock_park
            
            service.park_list = mock_park_list
            
            # Call update_current_park
            result = await service.update_current_park()
            
            # Verify debug message
            mock_logger.debug.assert_called_once_with("No valid current park to update")
            
            # Verify result is False
            assert result is False
    
    @pytest.mark.asyncio
    async def test_update_current_park_fetch_fails(self):
        """Test update current park when fetch fails"""
        # Create mock http client and settings manager
        mock_http = MagicMock()
        mock_settings = MagicMock()
        
        # Create the service
        service = ThemeParkService(mock_http, mock_settings)
        
        # Create a mock park list with current park
        mock_park = MagicMock()
        mock_park.id = 1
        mock_park.is_valid.return_value = True
        
        mock_park_list = MagicMock()
        mock_park_list.current_park = mock_park
        
        service.park_list = mock_park_list
        
        # Mock fetch_park_data to return None
        with patch.object(service, 'fetch_park_data', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            
            # Call update_current_park
            result = await service.update_current_park()
            
            # Verify fetch_park_data was called
            mock_fetch.assert_called_once_with(1)
            
            # Verify park.update was not called
            mock_park.update.assert_not_called()
            
            # Verify result is False on failure
            assert result is False
    
    def test_save_settings(self):
        """Test saving settings"""
        # Create mock http client and settings manager
        mock_http = MagicMock()
        mock_settings = MagicMock()
        
        # Create the service
        service = ThemeParkService(mock_http, mock_settings)
        
        # Create mock park list and vacation
        mock_park_list = MagicMock()
        mock_vacation = MagicMock()
        
        service.park_list = mock_park_list
        service.vacation = mock_vacation
        
        # Call save_settings
        service.save_settings()
        
        # Verify all settings were saved
        mock_park_list.store_settings.assert_called_once_with(mock_settings)
        mock_vacation.store_settings.assert_called_once_with(mock_settings)
        mock_settings.save_settings.assert_called_once()
    
    def test_parse_query_params_with_park_params(self):
        """Test parsing query parameters with park parameters"""
        # Create mock http client and settings manager
        mock_http = MagicMock()
        mock_settings = MagicMock()
        
        # Create the service
        service = ThemeParkService(mock_http, mock_settings)
        
        # Create mock park list and vacation
        mock_park_list = MagicMock()
        mock_vacation = MagicMock()
        
        service.park_list = mock_park_list
        service.vacation = mock_vacation
        
        # Mock save_settings
        service.save_settings = MagicMock()
        
        # Call parse_query_params with park-id parameter
        service.parse_query_params("park-id=1")
        
        # Verify park list parse was called
        mock_park_list.parse.assert_called_once_with("park-id=1")
        
        # Verify vacation parse was not called
        mock_vacation.parse.assert_not_called()
        
        # Verify settings were saved
        service.save_settings.assert_called_once()
    
    def test_parse_query_params_with_vacation_params(self):
        """Test parsing query parameters with vacation parameters"""
        # Create mock http client and settings manager
        mock_http = MagicMock()
        mock_settings = MagicMock()
        
        # Create the service
        service = ThemeParkService(mock_http, mock_settings)
        
        # Create mock park list and vacation
        mock_park_list = MagicMock()
        mock_vacation = MagicMock()
        
        service.park_list = mock_park_list
        service.vacation = mock_vacation
        
        # Mock save_settings
        service.save_settings = MagicMock()
        
        # Call parse_query_params with Name parameter
        service.parse_query_params("Name=Test+Vacation")
        
        # Verify park list parse was not called
        mock_park_list.parse.assert_not_called()
        
        # Verify vacation parse was called
        mock_vacation.parse.assert_called_once_with("Name=Test+Vacation")
        
        # Verify settings were saved
        service.save_settings.assert_called_once()
    
    def test_parse_query_params_with_both_params(self):
        """Test parsing query parameters with both park and vacation parameters"""
        # Create mock http client and settings manager
        mock_http = MagicMock()
        mock_settings = MagicMock()
        
        # Create the service
        service = ThemeParkService(mock_http, mock_settings)
        
        # Create mock park list and vacation
        mock_park_list = MagicMock()
        mock_vacation = MagicMock()
        
        service.park_list = mock_park_list
        service.vacation = mock_vacation
        
        # Mock save_settings
        service.save_settings = MagicMock()
        
        # Call parse_query_params with both parameters
        service.parse_query_params("park-id=1&Name=Test+Vacation")
        
        # Verify both parse methods were called
        mock_park_list.parse.assert_called_once_with("park-id=1&Name=Test+Vacation")
        mock_vacation.parse.assert_called_once_with("park-id=1&Name=Test+Vacation")
        
        # Verify settings were saved
        service.save_settings.assert_called_once()
    
    def test_parse_query_params_no_park_list(self):
        """Test parsing query parameters with no park list"""
        # Create mock http client and settings manager
        mock_http = MagicMock()
        mock_settings = MagicMock()
        
        # Create the service with no park list
        service = ThemeParkService(mock_http, mock_settings)
        service.park_list = None
        
        # Mock vacation
        mock_vacation = MagicMock()
        service.vacation = mock_vacation
        
        # Mock save_settings
        service.save_settings = MagicMock()
        
        # Call parse_query_params
        service.parse_query_params("park-id=1&Name=Test+Vacation")
        
        # Verify no methods were called since park_list is None
        mock_vacation.parse.assert_not_called()
        service.save_settings.assert_not_called()