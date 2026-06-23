"""Web handlers for SLDK web framework.

Provides base classes for handling HTTP requests and serving content.
"""

from __future__ import annotations

import os
try:
    from typing import Any, Dict, Optional, Tuple, Union
except ImportError:  # CircuitPython has no 'typing' module
    pass

from .adapters import route, MockResponse, RouteRegistryMixin


class WebHandler(RouteRegistryMixin):
    """Base class for web request handlers.

    Provides common functionality for handling HTTP requests
    and generating responses.

    Inherits ``RouteRegistryMixin`` so ``@route``-decorated ``route_*`` methods are
    collected into a class-level ``_routes`` registry (CircuitPython-safe) rather
    than tagged as function attributes.
    """

    adapter: Any
    _static_cache: Dict[str, Tuple[Union[str, bytes], str]]

    def __init__(self, adapter: Any) -> None:
        """Initialize web handler.

        Args:
            adapter: Server adapter instance
        """
        self.adapter = adapter
        self._static_cache = {}

    def create_response(
        self,
        body: Union[str, bytes],
        status: int = 200,
        content_type: str = "text/html",
    ) -> MockResponse:
        """Create an HTTP response.

        Args:
            body: Response body content
            status: HTTP status code
            content_type: MIME content type

        Returns:
            Response object
        """
        return MockResponse(body, status, content_type)

    def create_redirect_response(
        self,
        message: str,
        status: str = "success",
        redirect_url: str = "/",
        delay: int = 3,
    ) -> MockResponse:
        """Create a redirect response with status message.

        Args:
            message: Message to display
            status: Status type (success, error, info)
            redirect_url: URL to redirect to
            delay: Delay in seconds before redirect

        Returns:
            Response object with redirect HTML
        """
        status_colors: Dict[str, str] = {
            "success": "#4CAF50",
            "error": "#f44336",
            "info": "#2196F3",
            "warning": "#ff9800",
        }

        color = status_colors.get(status, "#2196F3")
        # CircuitPython's str has no .title(); capitalize the status word safely.
        status_title = (status[:1].upper() + status[1:]) if status else status

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>SLDK - {status_title}</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            text-align: center;
            max-width: 500px;
            width: 100%;
        }}
        .status {{
            color: {color};
            font-size: 48px;
            margin-bottom: 20px;
        }}
        .message {{
            font-size: 18px;
            margin-bottom: 20px;
            color: #333;
        }}
        .redirect {{
            color: #666;
            font-size: 14px;
        }}
        .progress {{
            width: 100%;
            height: 4px;
            background: #eee;
            border-radius: 2px;
            overflow: hidden;
            margin: 20px 0;
        }}
        .progress-bar {{
            height: 100%;
            background: {color};
            width: 0%;
            animation: progress {delay}s linear forwards;
        }}
        @keyframes progress {{
            to {{ width: 100%; }}
        }}
    </style>
    <meta http-equiv="refresh" content="{delay};url={redirect_url}">
</head>
<body>
    <div class="container">
        <div class="status">{"✓" if status == "success" else "⚠" if status == "warning" else "✗" if status == "error" else "ℹ"}</div>
        <div class="message">{message}</div>
        <div class="progress">
            <div class="progress-bar"></div>
        </div>
        <div class="redirect">Redirecting in {delay} seconds...</div>
    </div>
</body>
</html>
"""
        return self.create_response(html)

    def get_content_type(self, filename: str) -> str:
        """Get MIME content type for a file.

        Args:
            filename: Name of the file

        Returns:
            str: MIME content type
        """
        ext = os.path.splitext(filename)[1].lower()

        content_types: Dict[str, str] = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.ico': 'image/x-icon',
            '.svg': 'image/svg+xml',
            '.txt': 'text/plain',
            '.xml': 'application/xml',
        }

        return content_types.get(ext, 'application/octet-stream')

    def serve_static_file(
        self,
        filename: str,
        static_dir: Optional[str] = None,
    ) -> Optional[MockResponse]:
        """Serve a static file.

        Args:
            filename: Name of the file to serve
            static_dir: Directory containing static files

        Returns:
            Response object or None if file not found
        """
        if static_dir is None:
            static_dir = self.adapter.static_dir

        if '..' in filename or filename.startswith('/'):
            return None

        file_path = os.path.join(static_dir, filename)

        if file_path in self._static_cache:
            content, content_type = self._static_cache[file_path]
            return self.create_response(content, content_type=content_type)

        try:
            content_type = self.get_content_type(filename)
            is_binary = content_type.startswith('image/') or content_type == 'application/octet-stream'

            mode = 'rb' if is_binary else 'r'
            encoding = None if is_binary else 'utf-8'

            with open(file_path, mode, encoding=encoding) as f:
                content = f.read()

            self._static_cache[file_path] = (content, content_type)

            return self.create_response(content, content_type=content_type)

        except (OSError, IOError):
            return None

    @route("/")
    def route_index(self, request: Any) -> MockResponse:
        """Handle index page requests."""
        return self.create_response("""
<!DOCTYPE html>
<html>
<head>
    <title>SLDK Application</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            color: white;
            text-align: center;
        }
        .container {
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            max-width: 600px;
            margin: 0 auto;
        }
        h1 {
            font-size: 48px;
            margin-bottom: 20px;
        }
        p {
            font-size: 18px;
            line-height: 1.6;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>SLDK Application</h1>
        <p>Welcome to your SLDK (Scrolling LED Dev Kit) application!</p>
        <p>This is the default handler. Override route_index() in your WebHandler subclass to customize this page.</p>
    </div>
</body>
</html>
""")


class StaticFileHandler(WebHandler):
    """Handler specifically for serving static files.

    Provides efficient static file serving with caching.
    """

    def __init__(self, adapter: Any, static_dir: Optional[str] = None) -> None:
        """Initialize static file handler.

        Args:
            adapter: Server adapter instance
            static_dir: Directory containing static files
        """
        super().__init__(adapter)
        if static_dir:
            self.adapter.static_dir = static_dir

    @route("/static/<path:filename>")
    def route_static(self, request: Any) -> MockResponse:
        """Handle static file requests."""
        path = request.path
        if path.startswith('/static/'):
            filename = path[8:]
        else:
            filename = os.path.basename(path)

        response = self.serve_static_file(filename)
        if response:
            return response
        else:
            return self.create_response("File not found", status=404, content_type="text/plain")

    @route("/style.css")
    def route_css(self, request: Any) -> MockResponse:
        """Handle CSS file requests."""
        response = self.serve_static_file("style.css")
        if response:
            return response
        else:
            return self.create_response(self.get_default_css(), content_type="text/css")

    @route("/favicon.ico")
    def route_favicon(self, request: Any) -> MockResponse:
        """Handle favicon requests."""
        response = self.serve_static_file("favicon.ico")
        if response:
            return response
        else:
            return self.create_response("", status=204)

    def get_default_css(self) -> str:
        """Get default CSS styles for SLDK applications."""
        return """
/* SLDK Default Styles */
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    margin: 0;
    padding: 20px;
    min-height: 100vh;
    color: #333;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    background: white;
    border-radius: 15px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    overflow: hidden;
}

.header {
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    padding: 30px;
    text-align: center;
    color: white;
}

.header h1 {
    margin: 0;
    font-size: 36px;
    font-weight: 300;
}

.content {
    padding: 30px;
}

.form-group {
    margin-bottom: 20px;
}

.form-group label {
    display: block;
    margin-bottom: 5px;
    font-weight: 600;
    color: #555;
}

.form-control {
    width: 100%;
    padding: 12px;
    border: 2px solid #ddd;
    border-radius: 8px;
    font-size: 16px;
    transition: border-color 0.3s;
}

.form-control:focus {
    outline: none;
    border-color: #4facfe;
    box-shadow: 0 0 0 3px rgba(79, 172, 254, 0.1);
}

.btn {
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    color: white;
    padding: 12px 30px;
    border: none;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
}

.btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(79, 172, 254, 0.4);
}

.btn:active {
    transform: translateY(0);
}

.status-indicator {
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-right: 8px;
}

.status-online {
    background: #4CAF50;
}

.status-offline {
    background: #f44336;
}

.card {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    border-left: 4px solid #4facfe;
}

.card h3 {
    margin-top: 0;
    color: #333;
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
}

@media (max-width: 768px) {
    .container {
        margin: 10px;
        border-radius: 10px;
    }

    .header {
        padding: 20px;
    }

    .header h1 {
        font-size: 28px;
    }

    .content {
        padding: 20px;
    }

    .grid {
        grid-template-columns: 1fr;
    }
}
"""


class APIHandler(WebHandler):
    """Handler for API endpoints that return JSON responses."""

    def create_json_response(self, data: Any, status: int = 200) -> MockResponse:
        """Create a JSON response.

        Args:
            data: Data to serialize as JSON
            status: HTTP status code

        Returns:
            Response object with JSON content
        """
        import json

        try:
            json_data = json.dumps(data)
            return self.create_response(json_data, status=status, content_type="application/json")
        except (TypeError, ValueError) as e:
            error_data = {"error": "Failed to serialize response", "details": str(e)}
            return self.create_response(
                json.dumps(error_data),
                status=500,
                content_type="application/json",
            )

    def create_error_response(
        self,
        message: str,
        status: int = 400,
        error_code: Optional[str] = None,
    ) -> MockResponse:
        """Create a JSON error response.

        Args:
            message: Error message
            status: HTTP status code
            error_code: Optional error code

        Returns:
            Response object with JSON error
        """
        error_data: Dict[str, Any] = {
            "error": message,
            "status": status,
        }

        if error_code:
            error_data["code"] = error_code

        return self.create_json_response(error_data, status=status)

    @route("/api/status")
    def route_api_status(self, request: Any) -> MockResponse:
        """Handle API status requests."""
        status_data: Dict[str, str] = {
            "status": "running",
            "framework": "SLDK",
            "version": "0.1.0",
        }
        return self.create_json_response(status_data)