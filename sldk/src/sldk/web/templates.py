"""Template engine for SLDK web framework.

Provides simple HTML template generation with variable substitution.
Designed for memory-constrained CircuitPython environments.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Match, Optional, Tuple, Union

from ..exceptions import ResourceNotFoundError


class TemplateEngine:
    """Simple template engine for HTML generation.

    Supports variable substitution, basic conditionals, and loops.
    Optimized for memory usage on CircuitPython.
    """

    template_dir: str
    _template_cache: Dict[str, str]

    def __init__(self, template_dir: Optional[str] = None) -> None:
        """Initialize template engine.

        Args:
            template_dir: Directory containing template files
        """
        self.template_dir = template_dir or "./templates"
        self._template_cache = {}

    def render_string(self, template_str: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Render a template string with context variables.

        Args:
            template_str: Template string
            context: Dictionary of variables to substitute

        Returns:
            str: Rendered template
        """
        if context is None:
            context = {}

        result = template_str

        result = self._process_conditionals(result, context)

        result = self._process_loops(result, context)

        def replace_var(match: Match) -> str:
            var_name = match.group(1).strip()
            return str(context.get(var_name, ''))

        result = re.sub(r'\{\{\s*([^}]+)\s*\}\}', replace_var, result)

        return result

    def _substitute_variables(self, template_str: str, context: Dict[str, Any]) -> str:
        """Substitute variables in template.

        Args:
            template_str: Template string
            context: Context variables

        Returns:
            str: Template with variables substituted
        """
        def replace_var(match: Match) -> str:
            var_name = match.group(1).strip()
            return str(context.get(var_name, ''))

        return re.sub(r'\{\{\s*([^}]+)\s*\}\}', replace_var, template_str)

    def render_file(self, template_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Render a template file with context variables.

        Args:
            template_name: Name of template file
            context: Dictionary of variables to substitute

        Returns:
            str: Rendered template
        """
        template_str = self.load_template(template_name)
        return self.render_string(template_str, context)

    def load_template(self, template_name: str) -> str:
        """Load a template file.

        Args:
            template_name: Name of template file

        Returns:
            str: Template content
        """
        if template_name in self._template_cache:
            return self._template_cache[template_name]

        try:
            import os
            file_path = os.path.join(self.template_dir, template_name)

            with open(file_path, 'r', encoding='utf-8') as f:
                template_str = f.read()

            self._template_cache[template_name] = template_str
            return template_str

        except (OSError, IOError):
            raise ResourceNotFoundError(f"Template not found: {template_name}")

    def _process_conditionals(self, template_str: str, context: Dict[str, Any]) -> str:
        """Process {% if %} conditionals in template.

        Args:
            template_str: Template string
            context: Context variables

        Returns:
            str: Processed template
        """
        pattern = r'\{%\s*if\s+([^%]+)\s*%\}(.*?)\{%\s*endif\s*%\}'

        def replace_conditional(match: Match) -> str:
            condition = match.group(1).strip()
            content = match.group(2)

            if self._evaluate_condition(condition, context):
                return content
            else:
                return ''

        return re.sub(pattern, replace_conditional, template_str, flags=re.DOTALL)

    def _process_loops(self, template_str: str, context: Dict[str, Any]) -> str:
        """Process {% for %} loops in template.

        Args:
            template_str: Template string
            context: Context variables

        Returns:
            str: Processed template
        """
        pattern = r'\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}'

        def replace_loop(match: Match) -> str:
            item_name = match.group(1).strip()
            list_name = match.group(2).strip()
            content = match.group(3)

            items = context.get(list_name, [])

            result = ''
            for item in items:
                loop_context = context.copy()
                loop_context[item_name] = item
                rendered_content = self._substitute_variables(content, loop_context)
                result += rendered_content

            return result

        return re.sub(pattern, replace_loop, template_str, flags=re.DOTALL)

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a simple condition.

        Args:
            condition: Condition string
            context: Context variables

        Returns:
            bool: Condition result
        """
        var_name = condition.strip()

        if var_name.startswith('not '):
            var_name = var_name[4:].strip()
            return not self._is_truthy(context.get(var_name))

        return self._is_truthy(context.get(var_name))

    def _is_truthy(self, value: Any) -> bool:
        """Check if a value is truthy.

        Args:
            value: Value to check

        Returns:
            bool: True if truthy
        """
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, (str, list, dict)):
            return len(value) > 0
        return bool(value)


class HTMLBuilder:
    """HTML builder for programmatic HTML generation.

    Provides a fluent interface for building HTML without templates.
    """

    title: str
    head_content: List[str]
    body_content: List[str]
    css_links: List[str]
    js_links: List[str]
    inline_css: List[str]
    inline_js: List[str]

    def __init__(self, title: str = "SLDK Application") -> None:
        """Initialize HTML builder.

        Args:
            title: Page title
        """
        self.title = title
        self.head_content = []
        self.body_content = []
        self.css_links = []
        self.js_links = []
        self.inline_css = []
        self.inline_js = []

    def add_css_link(self, href: str) -> HTMLBuilder:
        """Add a CSS link to the head.

        Args:
            href: CSS file URL

        Returns:
            self: For method chaining
        """
        self.css_links.append(href)
        return self

    def add_js_link(self, src: str) -> HTMLBuilder:
        """Add a JavaScript link to the head.

        Args:
            src: JavaScript file URL

        Returns:
            self: For method chaining
        """
        self.js_links.append(src)
        return self

    def add_inline_css(self, css: str) -> HTMLBuilder:
        """Add inline CSS to the head.

        Args:
            css: CSS content

        Returns:
            self: For method chaining
        """
        self.inline_css.append(css)
        return self

    def add_inline_js(self, js: str) -> HTMLBuilder:
        """Add inline JavaScript to the head.

        Args:
            js: JavaScript content

        Returns:
            self: For method chaining
        """
        self.inline_js.append(js)
        return self

    def add_meta_tag(self, **attrs: str) -> HTMLBuilder:
        """Add a meta tag to the head.

        Args:
            **attrs: Meta tag attributes

        Returns:
            self: For method chaining
        """
        meta_attrs = ' '.join(f'{k}="{v}"' for k, v in attrs.items())
        self.head_content.append(f'<meta {meta_attrs}>')
        return self

    def add_viewport(self) -> HTMLBuilder:
        """Add responsive viewport meta tag.

        Returns:
            self: For method chaining
        """
        return self.add_meta_tag(name="viewport", content="width=device-width, initial-scale=1.0")

    def add_to_head(self, content: str) -> HTMLBuilder:
        """Add raw content to the head.

        Args:
            content: HTML content

        Returns:
            self: For method chaining
        """
        self.head_content.append(content)
        return self

    def add_to_body(self, content: str) -> HTMLBuilder:
        """Add content to the body.

        Args:
            content: HTML content

        Returns:
            self: For method chaining
        """
        self.body_content.append(content)
        return self

    def add_heading(self, text: str, level: int = 1, **attrs: str) -> HTMLBuilder:
        """Add a heading to the body.

        Args:
            text: Heading text
            level: Heading level (1-6)
            **attrs: Additional attributes

        Returns:
            self: For method chaining
        """
        attr_str = ' '.join(f'{k}="{v}"' for k, v in attrs.items())
        attr_str = ' ' + attr_str if attr_str else ''
        self.body_content.append(f'<h{level}{attr_str}>{text}</h{level}>')
        return self

    def add_paragraph(self, text: str, **attrs: str) -> HTMLBuilder:
        """Add a paragraph to the body.

        Args:
            text: Paragraph text
            **attrs: Additional attributes

        Returns:
            self: For method chaining
        """
        attr_str = ' '.join(f'{k}="{v}"' for k, v in attrs.items())
        attr_str = ' ' + attr_str if attr_str else ''
        self.body_content.append(f'<p{attr_str}>{text}</p>')
        return self

    def add_div(self, content: str = "", **attrs: str) -> HTMLBuilder:
        """Add a div to the body.

        Args:
            content: Div content
            **attrs: Additional attributes

        Returns:
            self: For method chaining
        """
        attr_str = ' '.join(f'{k}="{v}"' for k, v in attrs.items())
        attr_str = ' ' + attr_str if attr_str else ''
        self.body_content.append(f'<div{attr_str}>{content}</div>')
        return self

    def add_form(self, action: str = "/", method: str = "POST", **attrs: str) -> FormBuilder:
        """Start a form element.

        Args:
            action: Form action URL
            method: HTTP method
            **attrs: Additional attributes

        Returns:
            FormBuilder: For building form content
        """
        return FormBuilder(self, action, method, **attrs)

    def build(self) -> str:
        """Build the complete HTML document.

        Returns:
            str: Complete HTML document
        """
        html_parts = []

        html_parts.append('<!DOCTYPE html>')
        html_parts.append('<html lang="en">')

        html_parts.append('<head>')
        html_parts.append(f'<title>{self.title}</title>')
        html_parts.append('<meta charset="UTF-8">')

        for href in self.css_links:
            html_parts.append(f'<link rel="stylesheet" href="{href}">')

        if self.inline_css:
            html_parts.append('<style>')
            html_parts.extend(self.inline_css)
            html_parts.append('</style>')

        html_parts.extend(self.head_content)

        for src in self.js_links:
            html_parts.append(f'<script src="{src}"></script>')

        if self.inline_js:
            html_parts.append('<script>')
            html_parts.extend(self.inline_js)
            html_parts.append('</script>')

        html_parts.append('</head>')

        html_parts.append('<body>')
        html_parts.extend(self.body_content)
        html_parts.append('</body>')

        html_parts.append('</html>')

        return '\n'.join(html_parts)


class FormBuilder:
    """Builder for HTML forms."""

    html_builder: HTMLBuilder
    action: str
    method: str
    attrs: Dict[str, str]
    form_content: List[str]

    def __init__(self, html_builder: HTMLBuilder, action: str, method: str, **attrs: str) -> None:
        """Initialize form builder.

        Args:
            html_builder: Parent HTML builder
            action: Form action URL
            method: HTTP method
            **attrs: Additional form attributes
        """
        self.html_builder = html_builder
        self.action = action
        self.method = method
        self.attrs = attrs
        self.form_content = []

    def add_input(self, input_type: str = "text", name: str = "", value: str = "", **attrs: str) -> FormBuilder:
        """Add an input field to the form.

        Args:
            input_type: Input type
            name: Input name
            value: Input value
            **attrs: Additional attributes

        Returns:
            self: For method chaining
        """
        all_attrs = {'type': input_type, 'name': name, 'value': value}
        all_attrs.update(attrs)

        attr_str = ' '.join(f'{k}="{v}"' for k, v in all_attrs.items())
        self.form_content.append(f'<input {attr_str}>')
        return self

    def add_select(
        self,
        name: str,
        options: Union[Dict[str, str], List[Tuple[str, str]]],
        selected: Optional[str] = None,
        **attrs: str,
    ) -> FormBuilder:
        """Add a select field to the form.

        Args:
            name: Select name
            options: List of (value, label) tuples or dict
            selected: Selected value
            **attrs: Additional attributes

        Returns:
            self: For method chaining
        """
        attr_str = ' '.join(f'{k}="{v}"' for k, v in attrs.items())
        attr_str = ' ' + attr_str if attr_str else ''

        select_html = [f'<select name="{name}"{attr_str}>']

        if isinstance(options, dict):
            option_items = options.items()
        else:
            option_items = options

        for value, label in option_items:
            selected_attr = ' selected' if value == selected else ''
            select_html.append(f'<option value="{value}"{selected_attr}>{label}</option>')

        select_html.append('</select>')
        self.form_content.append('\n'.join(select_html))
        return self

    def add_button(self, text: str, button_type: str = "submit", **attrs: str) -> FormBuilder:
        """Add a button to the form.

        Args:
            text: Button text
            button_type: Button type
            **attrs: Additional attributes

        Returns:
            self: For method chaining
        """
        all_attrs = {'type': button_type}
        all_attrs.update(attrs)

        attr_str = ' '.join(f'{k}="{v}"' for k, v in all_attrs.items())
        self.form_content.append(f'<button {attr_str}>{text}</button>')
        return self

    def add_label(self, text: str, for_input: Optional[str] = None) -> FormBuilder:
        """Add a label to the form.

        Args:
            text: Label text
            for_input: Input field this label is for

        Returns:
            self: For method chaining
        """
        for_attr = f' for="{for_input}"' if for_input else ''
        self.form_content.append(f'<label{for_attr}>{text}</label>')
        return self

    def add_raw(self, html: str) -> FormBuilder:
        """Add raw HTML to the form.

        Args:
            html: Raw HTML content

        Returns:
            self: For method chaining
        """
        self.form_content.append(html)
        return self

    def end_form(self) -> HTMLBuilder:
        """End the form and return to HTML builder.

        Returns:
            HTMLBuilder: Parent HTML builder
        """
        all_attrs = {'action': self.action, 'method': self.method}
        all_attrs.update(self.attrs)

        attr_str = ' '.join(f'{k}="{v}"' for k, v in all_attrs.items())

        form_html = [f'<form {attr_str}>']
        form_html.extend(self.form_content)
        form_html.append('</form>')

        self.html_builder.add_to_body('\n'.join(form_html))
        return self.html_builder


class TemplateError(ResourceNotFoundError):
    """Template engine error."""
    pass