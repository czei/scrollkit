#!/usr/bin/env python3
"""Basic test of SLDK web framework."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

def test_web_imports():
    """Test that web framework imports work."""
    print("Testing SLDK web framework imports...")
    
    # Test basic imports
    from sldk.web import SLDKWebServer, WebHandler, StaticFileHandler
    print("✓ Core web classes imported")
    
    # Test adapters
    from sldk.web.adapters import ServerAdapter, route
    print("✓ Server adapters imported")
    
    # Test templates
    from sldk.web.templates import TemplateEngine, HTMLBuilder
    print("✓ Template engine imported")
    
    # Test forms
    from sldk.web.forms import FormBuilder, TextField, SelectField
    print("✓ Form builders imported")
    
    print("\nAll web framework imports successful!")

def test_html_builder():
    """Test HTML builder functionality."""
    print("\nTesting HTML builder...")
    
    from sldk.web.templates import HTMLBuilder
    
    # Create HTML page
    builder = HTMLBuilder("Test Page")
    builder.add_viewport()
    builder.add_css_link("/style.css")
    builder.add_heading("Hello World", level=1)
    builder.add_paragraph("This is a test page.")
    
    # Add a form
    form = builder.add_form(action="/submit", method="POST")
    form.add_label("Name:")
    form.add_input("text", "name", placeholder="Enter your name")
    form.add_button("Submit")
    form.end_form()
    
    html = builder.build()
    
    # Basic validation
    assert "<title>Test Page</title>" in html
    assert "<h1>Hello World</h1>" in html
    assert "<form action=\"/submit\" method=\"POST\">" in html
    
    print("✓ HTML builder working correctly")
    print(f"  Generated {len(html)} characters of HTML")

def test_form_builder():
    """Test form builder functionality."""
    print("\nTesting form builder...")
    
    from sldk.web.forms import FormBuilder
    
    # Create form
    form = FormBuilder(action="/test", method="POST")
    form.text_field('name', label='Your Name', required=True)
    form.number_field('age', label='Age', min_value=0, max_value=120)
    form.select_field('color', [('red', 'Red'), ('green', 'Green'), ('blue', 'Blue')], 
                     label='Favorite Color')
    form.checkbox_field('subscribe', label='Subscribe to newsletter')
    
    # Test validation
    test_data = {
        'name': 'John Doe',
        'age': '25',
        'color': 'blue',
        'subscribe': '1'
    }
    
    is_valid = form.validate(test_data)
    assert is_valid, f"Form validation failed: {form.errors}"
    
    processed_data = form.get_data(test_data)
    assert processed_data['name'] == 'John Doe'
    assert processed_data['age'] == 25.0
    assert processed_data['color'] == 'blue'
    assert processed_data['subscribe'] == True
    
    print("✓ Form builder working correctly")
    print(f"  Processed data: {processed_data}")

def test_template_engine():
    """Test template engine functionality."""
    print("\nTesting template engine...")
    
    from sldk.web.templates import TemplateEngine
    
    engine = TemplateEngine()
    
    # Test variable substitution
    template = "Hello {{name}}! You have {{count}} messages."
    context = {'name': 'Alice', 'count': 5}
    result = engine.render_string(template, context)
    
    expected = "Hello Alice! You have 5 messages."
    assert result == expected, f"Expected '{expected}', got '{result}'"
    
    # Test conditionals
    template = "{% if logged_in %}Welcome back!{% endif %}"
    result_true = engine.render_string(template, {'logged_in': True})
    result_false = engine.render_string(template, {'logged_in': False})
    
    assert result_true == "Welcome back!"
    assert result_false == ""
    
    # Test loops
    template = "{% for item in items %}{{item}} {% endfor %}"
    context = {'items': ['apple', 'banana', 'cherry']}
    result = engine.render_string(template, context)
    
    expected = "apple banana cherry "
    assert result == expected, f"Expected '{expected}', got '{result}'"
    
    print("✓ Template engine working correctly")
    print(f"  Variable substitution: '{result.strip()}'")

def test_route_decorator():
    """Test route decorator functionality."""
    print("\nTesting route decorator...")
    
    from sldk.web.adapters import route
    from sldk.web.handlers import WebHandler
    
    class TestHandler(WebHandler):
        @route("/test")
        def test_route(self, request):
            return self.create_response("Test response")
        
        @route("/api/data", methods=["GET", "POST"])
        def api_route(self, request):
            return self.create_response('{"status": "ok"}', content_type="application/json")
    
    # Check that route info is attached
    handler = TestHandler(None)
    
    assert hasattr(handler.test_route, '_route_info')
    assert handler.test_route._route_info['path'] == '/test'
    assert handler.test_route._route_info['methods'] == ['GET']
    
    assert hasattr(handler.api_route, '_route_info')
    assert handler.api_route._route_info['path'] == '/api/data'
    assert handler.api_route._route_info['methods'] == ['GET', 'POST']
    
    print("✓ Route decorator working correctly")
    print(f"  Routes registered: {len([attr for attr in dir(handler) if hasattr(getattr(handler, attr), '_route_info')])}")

if __name__ == "__main__":
    print("SLDK Web Framework Test Suite")
    print("=" * 50)
    
    try:
        test_web_imports()
        test_html_builder()
        test_form_builder()
        test_template_engine()
        test_route_decorator()
        
        print("\n" + "=" * 50)
        print("All web framework tests passed! ✓")
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()