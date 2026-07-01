"""
Tests for error handling in the HTTP client.
"""
import json
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock, call

from scrollkit.network.http_client import HttpClient
from scrollkit.exceptions import NetworkError


class TestHttpClientErrors:
    @pytest.mark.asyncio
    async def test_get_request_retry(self):
        """Test retry mechanism on GET request failure"""
        # Set up the mock session
        mock_session = MagicMock()
        mock_session.get.side_effect = [
            Exception("Connection error"),  # First attempt fails
            MagicMock(status_code=200, text=json.dumps({"status": "success"}))  # Second attempt succeeds
        ]
        
        # Mock asyncio.sleep to avoid actual waiting
        with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
            with patch('scrollkit.network.http_client._logger') as mock_logger:
                # Create client and make request
                client = HttpClient(session=mock_session)
                client.using_adafruit = True
                
                response = await client.get("https://example.com/api/test")
                
                # Verify that retry was attempted
                assert mock_session.get.call_count == 2
                # Verify sleep was called between retries
                assert mock_sleep.called
                # Verify the final response is successful
                assert response.status_code == 200
                assert json.loads(response.text)["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_get_request_max_retries_exceeded(self):
        """After all retries fail, get() raises NetworkError (not a synthesized 500)."""
        # Set up the mock session to always fail
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Connection error")

        # Mock asyncio.sleep to avoid actual waiting
        with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
            with patch('scrollkit.network.http_client._logger') as mock_logger:
                # Create client and make request
                client = HttpClient(session=mock_session)
                client.using_adafruit = True

                # Use a lower max_retries for faster testing
                with pytest.raises(NetworkError):
                    await client.get("https://example.com/api/test", max_retries=2)

                # Verify that all retries were attempted
                assert mock_session.get.call_count == 2
                # Verify sleep was called between retries
                assert mock_sleep.call_count == 2
    
    @pytest.mark.asyncio
    async def test_out_of_retries_exception_handling(self):
        """Test specific handling of OutOfRetries exception"""
        mock_session = MagicMock()

        # Create a simple OutOfRetries-like exception
        class OutOfRetries(Exception):
            pass

        mock_session.get.side_effect = OutOfRetries("Socket failures")

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with patch('scrollkit.network.http_client._logger'):
                client = HttpClient(session=mock_session)
                client.using_adafruit = True

                # Mock internal session recreation attempt
                with patch('scrollkit.network.http_client.adafruit_requests', create=True):
                    with patch('scrollkit.network.http_client.socketpool', create=True):
                        with patch('scrollkit.network.http_client.wifi', create=True):
                            with patch('scrollkit.network.http_client.ssl', create=True):
                                with pytest.raises(NetworkError):
                                    await client.get("https://example.com/api/test", max_retries=2)

                                # Verify sleep was called during retry cycle
                                assert mock_sleep.call_count > 0
    
    @pytest.mark.asyncio
    async def test_post_request_error(self):
        """A failed POST raises NetworkError (whose message carries the cause)."""
        # Set up the mock session to fail
        mock_session = MagicMock()
        mock_session.post.side_effect = Exception("Connection error")

        with patch('scrollkit.network.http_client._logger') as mock_logger:
            # Create client and make request
            client = HttpClient(session=mock_session)
            client.using_adafruit = True

            with pytest.raises(NetworkError) as exc:
                await client.post("https://example.com/api/test", data={"test": "data"})

            # Verify error was logged (mock_logger patches the _logger() factory;
            # the ErrorHandler instance it returns is mock_logger.return_value)
            assert mock_logger.return_value.error.called
            # The cause is carried in the NetworkError message and on last_error.
            assert "Connection error" in str(exc.value)
            assert str(client.last_error) == "Connection error"