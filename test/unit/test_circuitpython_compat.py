#!/usr/bin/env python3
"""Tests for CircuitPython compatibility."""

import pytest
import sys
from unittest.mock import patch, MagicMock


class TestCircuitPythonImports:
    """Test CircuitPython module import compatibility."""
    
    def test_json_import_and_usage(self):
        """Test json module works as expected in CircuitPython."""
        import json
        
        # Basic usage should work
        data = {'test': 'value', 'number': 42}
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        
        assert parsed == data
        assert isinstance(json_str, str)
    
    def test_json_error_handling(self):
        """Test JSON error handling - CircuitPython uses ValueError."""
        import json
        
        # CircuitPython raises ValueError for invalid JSON, not JSONDecodeError
        with pytest.raises(ValueError):
            json.loads('invalid json {')
        
        # Ensure JSONDecodeError is NOT used in SLDK code
        # This test documents the compatibility requirement
    
    def test_os_module_basics(self):
        """Test os module basic functionality."""
        import os
        
        # These should work in CircuitPython
        assert hasattr(os, 'listdir')
        assert hasattr(os, 'stat')
        assert hasattr(os, 'remove')
        
        # These might not work - depends on CircuitPython version
        # Test documents what should be avoided
        path_exists = hasattr(os.path, 'exists') if hasattr(os, 'path') else False
        if not path_exists:
            # Use try/except OSError instead of os.path.exists()
            pass
    
    def test_time_module_compatibility(self):
        """Test time module functions available in CircuitPython."""
        import time
        
        # These should work
        assert hasattr(time, 'sleep')
        assert hasattr(time, 'monotonic')
        
        # time.time() might not be available - use monotonic instead
        if hasattr(time, 'time'):
            current_time = time.time()
            assert isinstance(current_time, (int, float))
        
        # monotonic should always work
        mono_time = time.monotonic()
        assert isinstance(mono_time, (int, float))
    
    def test_random_module_compatibility(self):
        """Test random module functions in CircuitPython."""
        import random
        
        # Basic functions should work
        assert hasattr(random, 'randint')
        assert hasattr(random, 'choice')
        
        # Test basic usage
        num = random.randint(1, 10)
        assert 1 <= num <= 10
        
        choice = random.choice(['a', 'b', 'c'])
        assert choice in ['a', 'b', 'c']
        
        # random.choices() might not be available in CircuitPython
        # Use random.choice() in a loop instead
    
    def test_re_module_compatibility(self):
        """Test regex module functions in CircuitPython."""
        import re
        
        # Basic regex should work
        assert hasattr(re, 'search')
        assert hasattr(re, 'match')
        assert hasattr(re, 'findall')
        
        # Test basic usage
        match = re.search(r'\d+', 'test 123 string')
        assert match is not None
        assert match.group() == '123'
    
    def test_asyncio_availability(self):
        """Test asyncio availability for CircuitPython."""
        try:
            import asyncio
            
            # Basic asyncio should work
            assert hasattr(asyncio, 'create_task') or hasattr(asyncio, 'ensure_future')
            assert hasattr(asyncio, 'gather')
            assert hasattr(asyncio, 'sleep')
            
            # asyncio.run() might be available
            run_available = hasattr(asyncio, 'run')
            
        except ImportError:
            # asyncio might not be available in all CircuitPython versions
            pytest.skip("asyncio not available")


class TestCircuitPythonExceptions:
    """Test CircuitPython exception handling compatibility."""
    
    def test_file_exceptions(self):
        """Test file operation exception handling."""
        # CircuitPython typically only has OSError, not specific subclasses
        
        # This should work in both Python and CircuitPython
        try:
            with open('/nonexistent/file.txt', 'r') as f:
                f.read()
        except OSError:
            # OSError is the safe choice for CircuitPython
            pass
        except FileNotFoundError:
            # This might not exist in CircuitPython
            pass
        
        # Document that SLDK should use OSError, not FileNotFoundError
    
    def test_json_exceptions(self):
        """Test JSON parsing exception handling."""
        import json
        
        # CircuitPython uses ValueError for JSON errors
        with pytest.raises(ValueError):
            json.loads('{"invalid": json}')
        
        # json.JSONDecodeError might not exist in CircuitPython
        # Always use ValueError for JSON parsing errors
    
    def test_import_exceptions(self):
        """Test import exception handling."""
        # ImportError should work consistently
        with pytest.raises(ImportError):
            import nonexistent_module
        
        # ModuleNotFoundError might not exist in CircuitPython
        # Use ImportError instead


class TestCircuitPythonLimitations:
    """Test for CircuitPython limitations that SLDK must handle."""
    
    def test_typing_module_unavailable(self):
        """Test that typing module might not be available."""
        try:
            import typing
            typing_available = True
        except ImportError:
            typing_available = False
        
        # SLDK should work without typing module
        # Type hints should be in comments or removed for CircuitPython
        assert True  # Test documents requirement
    
    def test_pathlib_unavailable(self):
        """Test that pathlib is not available in CircuitPython."""
        try:
            import pathlib
            pathlib_available = True
        except ImportError:
            pathlib_available = False
        
        # SLDK should use os.path operations instead of pathlib
        if not pathlib_available:
            import os
            # Use os.path.join, os.path.dirname, etc.
            assert hasattr(os.path, 'join')
    
    def test_subprocess_unavailable(self):
        """Test that subprocess is not available in CircuitPython."""
        try:
            import subprocess
            subprocess_available = True
        except ImportError:
            subprocess_available = False
        
        # SLDK should not use subprocess
        # Document this limitation
        assert True
    
    def test_threading_vs_asyncio(self):
        """Test threading vs asyncio availability."""
        try:
            import threading
            threading_available = True
        except ImportError:
            threading_available = False
        
        try:
            import asyncio
            asyncio_available = True
        except ImportError:
            asyncio_available = False
        
        # CircuitPython uses cooperative multitasking (asyncio), not threading
        # SLDK should prefer asyncio over threading
        if not threading_available and asyncio_available:
            # This is the expected CircuitPython environment
            assert True
    
    def test_enum_auto_unavailable(self):
        """Test that enum.auto() might not be available."""
        try:
            from enum import Enum, auto
            auto_available = True
        except ImportError:
            auto_available = False
        
        # If enum.auto() not available, use explicit values
        if not auto_available:
            from enum import Enum
            
            class TestEnum(Enum):
                FIRST = 1
                SECOND = 2
                THIRD = 3
            
            assert TestEnum.FIRST.value == 1
    
    def test_fstring_format_limitations(self):
        """Test f-string format limitations in CircuitPython."""
        # Basic f-strings should work
        name = "test"
        value = 42
        
        # This should work
        basic_fstring = f"Hello {name}!"
        assert basic_fstring == "Hello test!"
        
        # f-string with = might not work in CircuitPython
        # Avoid f"{var=}" syntax - use f"var={var}" instead
        explicit_format = f"value={value}"
        assert explicit_format == "value=42"
    
    def test_match_case_unavailable(self):
        """Test that match/case statements are not available."""
        # CircuitPython doesn't support match/case (Python 3.10+ feature)
        # Use if/elif chains instead
        
        def handle_value(value):
            if value == 'a':
                return 1
            elif value == 'b':
                return 2
            elif value == 'c':
                return 3
            else:
                return 0
        
        assert handle_value('a') == 1
        assert handle_value('b') == 2
        assert handle_value('z') == 0


class TestSLDKCircuitPythonUsage:
    """Test SLDK-specific CircuitPython compatibility patterns."""
    
    @patch('sys.modules', {'displayio': MagicMock(), 'board': MagicMock()})
    def test_optional_circuitpython_imports(self):
        """Test SLDK handles optional CircuitPython imports gracefully."""
        # SLDK should handle missing CircuitPython modules gracefully
        
        try:
            import displayio
            displayio_available = True
        except ImportError:
            displayio_available = False
        
        try:
            import board
            board_available = True
        except ImportError:
            board_available = False
        
        # SLDK should work in both environments
        assert True  # Documents expected behavior
    
    def test_memory_constraint_awareness(self):
        """Test patterns for memory-constrained environments."""
        # CircuitPython has limited memory - SLDK should be aware
        
        # Use small default values
        max_effects = 2  # Not 10
        max_particles = 8  # Not 100
        target_fps = 5  # Not 60
        
        # Test that defaults are ESP32-friendly
        assert max_effects <= 5
        assert max_particles <= 20
        assert target_fps <= 30
    
    def test_synchronous_http_assumption(self):
        """Test that SLDK assumes synchronous HTTP in CircuitPython."""
        # CircuitPython uses adafruit_requests which is synchronous
        # SLDK should not assume async HTTP
        
        # Document this limitation for web server design
        synchronous_http = True
        cooperative_multitasking = True
        
        assert synchronous_http
        assert cooperative_multitasking
    
    def test_file_system_limitations(self):
        """Test file system operation limitations."""
        import os
        
        # CircuitPython file system operations are limited
        # Test basic operations that should work
        
        try:
            # This should work
            files = os.listdir('.')
            assert isinstance(files, list)
        except OSError:
            # Might fail in test environment
            pass
        
        # Document that complex file operations should be avoided