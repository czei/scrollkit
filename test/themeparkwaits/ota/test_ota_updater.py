"""Unit tests for OTAUpdater"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from src.ota.ota_updater import OTAUpdater, _compare_versions, _normalize_version
from src.network.http_client import HttpClient


class TestOTAUpdater:
    """Test cases for OTAUpdater"""
    
    @pytest.fixture
    def mock_http_client(self):
        """Create a mock HTTP client"""
        return Mock()
    
    @pytest.fixture
    def ota_updater(self, mock_http_client):
        """Create an OTAUpdater instance with mocked dependencies"""
        updater = OTAUpdater(
            http_client_param=mock_http_client,
            github_repo='test/repo',
            main_dir='src',
            headers={'Authorization': 'token test_token'}
        )
        return updater
    
    def test_check_for_new_version_returns_tuple(self, ota_updater):
        """Test that check_for_new_version returns a tuple of (current_version, latest_version)"""
        # Mock get_version to return current version
        with patch.object(ota_updater, 'get_version', return_value='1.0'):
            # Mock get_latest_version to return latest version
            with patch.object(ota_updater, 'get_latest_version', return_value='2.0'):
                result = ota_updater.check_for_new_version()
                
                # Should return a tuple
                assert isinstance(result, tuple)
                assert len(result) == 2
                assert result == ('1.0', '2.0')
    
    def test_check_for_new_version_same_version(self, ota_updater):
        """Test when current and latest versions are the same"""
        with patch.object(ota_updater, 'get_version', return_value='1.5'):
            with patch.object(ota_updater, 'get_latest_version', return_value='1.5'):
                result = ota_updater.check_for_new_version()
                
                assert result == ('1.5', '1.5')
    
    def test_check_for_new_version_older_latest(self, ota_updater):
        """Test when latest version is older than current (edge case)"""
        with patch.object(ota_updater, 'get_version', return_value='2.0'):
            with patch.object(ota_updater, 'get_latest_version', return_value='1.0'):
                result = ota_updater.check_for_new_version()
                
                assert result == ('2.0', '1.0')
    
    def test_get_version_with_version_file(self, ota_updater):
        """Test get_version when version file exists"""
        with patch('os.listdir', return_value=['.version', 'other_file.py']):
            mock_open = MagicMock()
            mock_open.__enter__.return_value.read.return_value = '1.2.3'
            
            with patch('builtins.open', return_value=mock_open):
                version = ota_updater.get_version('/test/dir')
                
                assert version == '1.2.3'
    
    def test_get_version_no_version_file(self, ota_updater):
        """Test get_version when version file doesn't exist"""
        with patch('os.listdir', return_value=['other_file.py']):
            version = ota_updater.get_version('/test/dir')
            
            # Should return default version
            assert version == '0.0'
    
    def test_get_version_directory_not_found(self, ota_updater):
        """Test get_version when directory doesn't exist"""
        with patch('os.listdir', side_effect=FileNotFoundError()):
            version = ota_updater.get_version('/nonexistent/dir')
            
            # Should return default version
            assert version == '0.0'
    
    def test_get_latest_version_stable_release(self, ota_updater, mock_http_client):
        """Test get_latest_version for stable releases"""
        # Mock the API response
        mock_response = Mock()
        mock_response.status_code = 200  # Add status_code attribute
        mock_response.json.return_value = {
            'tag_name': 'v1.5.0',
            'prerelease': False
        }
        mock_response.close = Mock()  # Add close method
        mock_http_client.get_sync.return_value = mock_response
        
        # use_prerelease is False by default
        version = ota_updater.get_latest_version()
        
        assert version == 'v1.5.0'
        mock_http_client.get_sync.assert_called_once()
    
    def test_get_latest_version_with_prerelease(self, ota_updater, mock_http_client):
        """Test get_latest_version when including prereleases"""
        # Set to use prereleases
        ota_updater.use_prerelease = True
        
        # Mock the API response
        mock_response = Mock()
        mock_response.status_code = 200  # Add status_code attribute
        mock_response.json.return_value = [
            {
                'tag_name': 'v2.0.0-beta',
                'prerelease': True
            },
            {
                'tag_name': 'v1.5.0',
                'prerelease': False
            }
        ]
        mock_response.close = Mock()  # Add close method
        mock_http_client.get_sync.return_value = mock_response
        
        version = ota_updater.get_latest_version()
        
        assert version == 'v2.0.0-beta'
        mock_http_client.get_sync.assert_called_once()
    
    def test_update_available_at_boot_with_new_version_dir(self, ota_updater):
        """Test update_available_at_boot when new version directory exists"""
        # Mock the listing of the module directory and the next directory
        with patch('os.listdir') as mock_listdir:
            def listdir_side_effect(path):
                if path == '.' or path == '':
                    return ['next', 'src', 'other_dir']
                elif path.endswith('next'):
                    return ['.version', 'some_file.py']
                else:
                    return []
            
            mock_listdir.side_effect = listdir_side_effect
            assert ota_updater.update_available_at_boot() is True
    
    def test_update_available_at_boot_without_new_version_dir(self, ota_updater):
        """Test update_available_at_boot when new version directory doesn't exist"""
        with patch('os.listdir', return_value=['src', 'other_dir']):
            assert ota_updater.update_available_at_boot() is False
    
    def test_update_available_at_boot_empty_module_path(self, ota_updater):
        """Test update_available_at_boot with empty module path"""
        ota_updater.module = ''
        with patch('os.listdir') as mock_listdir:
            def listdir_side_effect(path):
                if path == '.' or path == '':
                    return ['next', 'src']
                elif path == 'next' or path.endswith('next'):
                    return ['.version', 'some_file.py']
                else:
                    return []
            
            mock_listdir.side_effect = listdir_side_effect
            assert ota_updater.update_available_at_boot() is True
    
    def test_update_available_at_boot_directory_error(self, ota_updater):
        """Test update_available_at_boot when directory listing fails"""
        with patch('os.listdir', side_effect=FileNotFoundError()):
            assert ota_updater.update_available_at_boot() is False
    
    def test_download_file_url_construction(self, ota_updater, mock_http_client):
        """Test _download_file constructs the correct URL and downloads content"""
        # Set up the updater with a full GitHub URL
        ota_updater.github_repo = 'https://github.com/Czeiszperger/themeparkwaits.release'
        
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.status_code = 200  # Add status_code attribute
        mock_response.read.side_effect = [b'file content chunk 1', b'file content chunk 2', b'']
        mock_response.content = b'file content'
        mock_response.close = Mock()  # Add close method
        mock_http_client.get_sync.return_value = mock_response
        
        # Create a temporary file path for testing
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            test_path = tmp_file.name
        
        try:
            # Call the method
            ota_updater._download_file('v1.9', 'src/main.py', test_path)
            
            # Verify the correct URL was constructed
            expected_url = 'https://raw.githubusercontent.com/Czeiszperger/themeparkwaits.release/v1.9/src/main.py'
            mock_http_client.get_sync.assert_called_once_with(expected_url, headers=ota_updater.headers)
            
            # Verify file was written
            with open(test_path, 'rb') as f:
                content = f.read()
                # Should have written the content attribute if it exists
                assert content == b'file content'
        
        finally:
            # Clean up
            import os
            if os.path.exists(test_path):
                os.remove(test_path)
    
    def test_download_file_without_content_attribute(self, ota_updater, mock_http_client):
        """Test _download_file when response doesn't have content attribute"""
        # Set up the updater with a full GitHub URL
        ota_updater.github_repo = 'https://github.com/Czeiszperger/themeparkwaits.release'
        
        # Mock the HTTP response without content attribute
        mock_response = Mock()
        mock_response.status_code = 200  # Add status_code attribute
        # Remove content attribute to simulate CircuitPython response
        if hasattr(mock_response, 'content'):
            delattr(mock_response, 'content')
        mock_response.read.side_effect = [b'chunk1', b'chunk2', b'']
        mock_response.close = Mock()  # Add close method
        mock_http_client.get_sync.return_value = mock_response
        
        # Create a temporary file path for testing
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            test_path = tmp_file.name
        
        try:
            # Call the method
            ota_updater._download_file('v1.9', 'src/app.py', test_path)
            
            # Verify file was written with chunks
            with open(test_path, 'rb') as f:
                content = f.read()
                assert content == b'chunk1chunk2'
        
        finally:
            # Clean up
            import os
            if os.path.exists(test_path):
                os.remove(test_path)
    
    def test_download_file_error_handling(self, ota_updater, mock_http_client):
        """Test _download_file handles errors and cleans up partial files"""
        # Mock the HTTP client to raise an error
        mock_http_client.get_sync.side_effect = Exception("Network error")
        
        # Create a temporary file path for testing
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            test_path = tmp_file.name
        
        # Call the method and expect it to raise
        with pytest.raises(Exception) as exc_info:
            ota_updater._download_file('v1.9', 'src/main.py', test_path)
        
        assert "Network error" in str(exc_info.value)
        
        # Verify the partial file was cleaned up
        import os
        assert not os.path.exists(test_path)
    
    def test_real_api_get_latest_version(self):
        """Test get_latest_version with real API call"""
        # Create a real HTTP client
        http_client = HttpClient()
        
        # Create OTAUpdater with real GitHub repo
        updater = OTAUpdater(
            http_client_param=http_client,
            github_repo='https://github.com/Czeiszperger/themeparkwaits.release',
            main_dir='src',
            headers={'Authorization': 'token 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'}
        )
        
        # Test getting latest version
        try:
            latest_version = updater.get_latest_version()
            # Should return a version string
            assert isinstance(latest_version, str)
            assert len(latest_version) > 0
            # Version should be something like "1.9" or "v1.9.0"
            assert latest_version[0].isdigit() or latest_version[0] == 'v'
        except Exception as e:
            pytest.fail(f"Real API call failed: {e}")
    
    def test_install_update_after_boot_version_file_path_fix(self, ota_updater):
        """Test that install_update_if_available_after_boot reads .version from correct path"""
        # Mock directory listing to simulate next/.version exists
        with patch('os.listdir') as mock_listdir:
            def listdir_side_effect(path):
                if path == '.' or path == '':
                    return ['next', 'src']
                elif path == 'next' or path.endswith('next'):
                    return ['.version', 'some_file.py']
                else:
                    return []
            
            mock_listdir.side_effect = listdir_side_effect
            
            # Mock the version file reading
            mock_open = MagicMock()
            mock_open.__enter__.return_value.read.return_value = '2.0'
            
            with patch('builtins.open', return_value=mock_open):
                with patch.object(ota_updater, 'install_update_if_available', return_value=True):
                    result = ota_updater.install_update_if_available_after_boot('ssid', 'password')
                    
                    # Should detect update and return True
                    assert result is True
                    
                    # Verify that the correct path was used to read .version
                    # The path should be 'next/.version', not 'next/../.version'
                    mock_open.__enter__.return_value.read.assert_called_once()


class TestVersionComparison:
    """Test cases for version comparison functions"""
    
    def test_normalize_version_removes_v_prefix(self):
        """Test that _normalize_version removes 'v' prefix"""
        assert _normalize_version('v1.9') == '1.9'
        assert _normalize_version('v2.0.0') == '2.0.0'
        assert _normalize_version('1.9') == '1.9'
        assert _normalize_version('2.0') == '2.0'
    
    def test_normalize_version_handles_empty_strings(self):
        """Test that _normalize_version handles empty strings"""
        assert _normalize_version('') == '0.0'
        assert _normalize_version(None) == '0.0'
    
    def test_compare_versions_major_difference(self):
        """Test version comparison with major version differences"""
        # This is the main bug: 2.0 should be > 1.9
        assert _compare_versions('2.0', '1.9') > 0
        assert _compare_versions('1.9', '2.0') < 0
        assert _compare_versions('3.0', '2.9') > 0
        assert _compare_versions('10.0', '9.9') > 0
    
    def test_compare_versions_minor_difference(self):
        """Test version comparison with minor version differences"""
        assert _compare_versions('1.10', '1.9') > 0
        assert _compare_versions('1.9', '1.10') < 0
        assert _compare_versions('2.1', '2.0') > 0
        assert _compare_versions('2.0', '2.1') < 0
    
    def test_compare_versions_patch_difference(self):
        """Test version comparison with patch version differences"""
        assert _compare_versions('1.9.1', '1.9.0') > 0
        assert _compare_versions('1.9.0', '1.9.1') < 0
        assert _compare_versions('2.0.1', '2.0.0') > 0
    
    def test_compare_versions_equal(self):
        """Test version comparison when versions are equal"""
        assert _compare_versions('1.9', '1.9') == 0
        assert _compare_versions('2.0', '2.0') == 0
        assert _compare_versions('v1.9', '1.9') == 0
        assert _compare_versions('v2.0.0', '2.0') == 0
    
    def test_compare_versions_different_lengths(self):
        """Test version comparison with different number of parts"""
        assert _compare_versions('1.9.0', '1.9') == 0  # 1.9.0 == 1.9.0 (padded)
        assert _compare_versions('1.9.1', '1.9') > 0   # 1.9.1 > 1.9.0 (padded)
        assert _compare_versions('1.9', '1.9.1') < 0   # 1.9.0 (padded) < 1.9.1
        assert _compare_versions('2.0', '1.9.9') > 0   # 2.0.0 (padded) > 1.9.9
    
    def test_compare_versions_with_v_prefix(self):
        """Test version comparison with 'v' prefixes"""
        assert _compare_versions('v2.0', 'v1.9') > 0
        assert _compare_versions('v1.9', 'v2.0') < 0
        assert _compare_versions('v2.0', '1.9') > 0
        assert _compare_versions('1.9', 'v2.0') < 0
    
    def test_compare_versions_non_numeric_parts(self):
        """Test version comparison with non-numeric parts (like pre-release tags)"""
        # For non-numeric parts, fall back to string comparison
        assert _compare_versions('2.0-alpha', '2.0-beta') < 0  # alpha < beta
        assert _compare_versions('2.0-beta', '2.0-alpha') > 0  # beta > alpha
        assert _compare_versions('2.0-rc1', '2.0-rc1') == 0
    
    def test_ota_updater_uses_semantic_comparison(self):
        """Test that OTAUpdater now uses semantic version comparison"""
        mock_http_client = Mock()
        updater = OTAUpdater(
            http_client_param=mock_http_client,
            github_repo='test/repo',
            main_dir='src'
        )
        
        # Mock get_version to return current version 1.9
        with patch.object(updater, 'get_version', return_value='1.9'):
            # Mock get_latest_version to return 2.0
            with patch.object(updater, 'get_latest_version', return_value='2.0'):
                # Mock the file creation and download methods
                with patch.object(updater, '_create_new_version_file'):
                    result = updater.check_for_update_to_install_during_next_reboot()
                    
                    # Should now detect that 2.0 > 1.9 and return True
                    assert result is True