"""
Tests for the MockResponse class in the HTTP client module.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from scrollkit.network.http_client import MockResponse


class TestMockResponse:
    def test_initialization(self):
        """Test MockResponse initialization"""
        # Default initialization
        response = MockResponse()
        assert response.status_code == 200
        assert response.text == ""
        assert response._json_cache is None
        
        # Initialization with parameters
        response = MockResponse(404, "Not Found")
        assert response.status_code == 404
        assert response.text == "Not Found"

    def test_response_headers(self):
        """Responses expose headers (used to read the HTTP 'Date' header as a
        fallback time source). Defaults to an empty dict, never None."""
        assert MockResponse().headers == {}
        resp = MockResponse(200, "", headers={"Date": "Wed, 21 Oct 2025 07:28:00 GMT"})
        assert resp.headers.get("Date") == "Wed, 21 Oct 2025 07:28:00 GMT"

    def test_json_parsing(self):
        """Test JSON parsing of response text"""
        # Test valid JSON
        response = MockResponse(200, '{"key": "value"}')
        data = response.json()
        assert data["key"] == "value"
        
        # Test caching behavior
        response._json_cache = {"cached": True}
        data = response.json()
        assert data["cached"] is True
    
    def test_json_parsing_with_whitespace(self):
        """Test JSON parsing with whitespace"""
        response = MockResponse(200, ' \n{"key": "value"}\n ')
        data = response.json()
        assert data["key"] == "value"
    
    def test_json_parsing_with_bom(self):
        """Test JSON parsing with BOM character"""
        response = MockResponse(200, '\ufeff{"key": "value"}')
        data = response.json()
        assert data["key"] == "value"
    
    def test_json_parsing_with_empty_response(self):
        """Test JSON parsing with empty response"""
        response = MockResponse(200, '')
        data = response.json()
        assert data == {}
        
        response = MockResponse(200, ' ')
        data = response.json()
        assert data == {}
    
    def test_json_parsing_error(self):
        """Test error handling when JSON parsing fails"""
        response = MockResponse(200, '{"invalid": json}')
        
        # Mock the logger to avoid actual error logging
        with patch('scrollkit.network.http_client._logger') as mock_logger:
            with pytest.raises(ValueError) as excinfo:
                response.json()
            
            # Verify the error message contains "syntax error in JSON"
            assert "syntax error in JSON" in str(excinfo.value)
            
            # Verify logger was called to log the error (mock_logger patches the
            # _logger() factory; the ErrorHandler it returns is mock_logger.return_value)
            assert mock_logger.return_value.error.called