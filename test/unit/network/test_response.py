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

# --- lazy .content + StreamingResponse (2026-07-19 fragmentation fix) ---------
# The old eager `content = text.encode()` silently DOUBLED every payload's
# contiguous footprint on the device; StreamingResponse is the socket-owning
# chunked path that avoids whole-body materialization entirely.

from scrollkit.network.http_client import BaseResponse, StreamingResponse


class TestLazyContent:
    def test_content_not_materialized_until_accessed(self):
        r = BaseResponse(200, "x" * 100)
        assert r._content is None, "bytes copy must not exist eagerly"
        assert r.content == b"x" * 100          # lazy encode on first access
        assert r._content is not None

    def test_explicit_content_still_honored(self):
        r = BaseResponse(200, "text", content=b"bytes")
        assert r.content == b"bytes"

    def test_read_works_via_lazy_content(self):
        r = BaseResponse(200, "hello world")
        assert r.read(5) == b"hello"
        assert r.read() == b" world"

    def test_json_does_not_touch_content(self):
        r = BaseResponse(200, '{"a": 1}')
        assert r.json() == {"a": 1}
        assert r._content is None, "json() must parse from .text, not .content"


class _FakeNative:
    """Native-response stand-in with real chunked iter_content."""
    def __init__(self, body=b"0123456789", status_code=200, headers=None):
        self.body = body
        self.status_code = status_code
        self.headers = headers or {"Date": "x"}
        self.closed = 0

    def iter_content(self, chunk_size=4):
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i:i + chunk_size]

    def close(self):
        self.closed += 1


class TestStreamingResponse:
    def test_native_chunks_pass_through(self):
        native = _FakeNative(b"abcdefgh")
        s = StreamingResponse(native)
        assert list(s.iter_content(3)) == [b"abc", b"def", b"gh"]
        assert s.status_code == 200 and s.headers.get("Date") == "x"

    def test_text_only_fallback_yields_one_chunk(self):
        s = StreamingResponse(MockResponse(200, "hello"))
        assert list(s.iter_content(4)) == [b"hello"]

    def test_context_manager_closes_inner(self):
        native = _FakeNative()
        with StreamingResponse(native) as s:
            assert s.status_code == 200
        assert native.closed == 1
        s.close()                                # double-close is safe
        assert native.closed == 1

    def test_iter_after_close_is_empty(self):
        s = StreamingResponse(_FakeNative())
        s.close()
        assert list(s.iter_content()) == []

    def test_native_path_never_touches_text(self):
        """Device-path contract: with native iter_content present, .text must
        never be materialized (that would recreate the whole-body allocation
        streaming exists to avoid)."""
        class _NativeOnly:
            status_code = 200
            headers = {}

            @property
            def text(self):
                raise AssertionError("device path must not materialize .text")

            def iter_content(self, chunk_size=4):
                yield b"ab"

            def close(self):
                pass

        s = StreamingResponse(_NativeOnly())
        assert list(s.iter_content()) == [b"ab"]
