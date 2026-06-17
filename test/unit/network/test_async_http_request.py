"""
Tests for the async_http_request module.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from src.network.async_http_request import (
    async_read_url,
    read_http_header,
    read_http_body,
    read_http_chunked_body,
    parse_http_content_length,
    get_domain_from_url,
    get_path_from_url
)


class TestAsyncHttpRequest:
    def test_get_domain_from_url(self):
        """Test extracting domain from URL"""
        # With protocol
        assert get_domain_from_url("https://example.com/path") == "example.com"
        assert get_domain_from_url("http://api.example.com/path?query=value") == "api.example.com"
        
        # Without protocol
        assert get_domain_from_url("example.com/path") == "example.com"
        
        # Without path
        assert get_domain_from_url("https://example.com") == "example.com"
        assert get_domain_from_url("example.com") == "example.com"
    
    def test_get_path_from_url(self):
        """Test extracting path from URL"""
        # With protocol
        assert get_path_from_url("https://example.com/path") == "/path"
        assert get_path_from_url("http://api.example.com/path/to/resource?query=value") == "/path/to/resource?query=value"
        
        # Without protocol
        assert get_path_from_url("example.com/path") == "/path"
        
        # Without path
        assert get_path_from_url("https://example.com") == "/"
        assert get_path_from_url("example.com") == "/"
    
    def test_parse_http_content_length(self):
        """Test parsing Content-Length from HTTP headers"""
        # Header with Content-Length
        header = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 1024\r\n\r\n"
        assert parse_http_content_length(header) == 1024
        
        # Header with lowercase content-length
        header = "HTTP/1.1 200 OK\r\ncontent-length: 512\r\nContent-Type: application/json\r\n\r\n"
        assert parse_http_content_length(header) == 512
        
        # Header without Content-Length
        header = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n"
        assert parse_http_content_length(header) == 0
    
    @pytest.mark.asyncio
    async def test_read_http_header(self):
        """Test reading HTTP header from reader"""
        # Create mock reader
        mock_reader = AsyncMock()
        mock_reader.readline.side_effect = [
            b"HTTP/1.1 200 OK\r\n",
            b"Content-Type: application/json\r\n",
            b"Content-Length: 1024\r\n",
            b"\r\n"  # Empty line signifies end of headers
        ]
        
        header = await read_http_header(mock_reader)
        
        # Verify header was read correctly
        assert "HTTP/1.1 200 OK" in header
        assert "Content-Type: application/json" in header
        assert "Content-Length: 1024" in header
        assert "\r\n\r\n" in header  # End of headers marker
    
    @pytest.mark.asyncio
    async def test_read_http_body(self):
        """Test reading HTTP body with Content-Length"""
        # Create mock reader
        mock_reader = AsyncMock()
        mock_reader.readexactly.return_value = b'{"key": "value"}'
        
        # Create header with Content-Length
        header = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 15\r\n\r\n"
        
        body = await read_http_body(mock_reader, header)
        
        # Verify readexactly was called with correct size
        mock_reader.readexactly.assert_called_once_with(15)
        # Verify body was returned correctly
        assert body == b'{"key": "value"}'
    
    @pytest.mark.asyncio
    async def test_read_http_chunked_body(self):
        """Test reading HTTP chunked body"""
        # Create mock reader
        mock_reader = AsyncMock()
        mock_reader.readline.side_effect = [
            b"7\r\n",   # First chunk size (7 bytes)
            b"3\r\n",   # Second chunk size (3 bytes)
            b"0\r\n"    # End of chunked data
        ]
        mock_reader.readexactly.side_effect = [
            b"chunk1\r\n",  # First chunk data
            b"\r\n",        # First chunk CRLF
            b"abc",         # Second chunk data
            b"\r\n"         # Second chunk CRLF
        ]
        
        body = await read_http_chunked_body(mock_reader)
        
        # Verify body combines chunks correctly
        assert body == b"chunk1\r\nabc"
    
    @pytest.mark.asyncio
    async def test_async_read_url(self):
        """Test the main async_read_url function"""
        from src.network.async_http_request import async_read_url
        from unittest.mock import AsyncMock

        mock_reader = AsyncMock()
        mock_writer = AsyncMock()

        # Simulate HTTP response
        mock_reader.readline.side_effect = [
            b"HTTP/1.1 200 OK\r\n",
            b"Content-Type: application/json\r\n",
            b"Content-Length: 13\r\n",
            b"\r\n",
        ]
        mock_reader.readexactly.return_value = b'{"key":"val"}'

        with patch('ssl.create_default_context'):
            with patch('asyncio.open_connection', new_callable=AsyncMock) as mock_connect:
                mock_connect.return_value = (mock_reader, mock_writer)

                header, body = await async_read_url("example.com", "/test")

                assert "200" in header
                assert body == b'{"key":"val"}'