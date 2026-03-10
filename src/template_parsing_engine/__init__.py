"""Template Parsing Engine - Standalone Jinja2/YAML template renderer.

This module provides a standalone templating engine for markdown prompt templates
with YAML frontmatter, supporting Jinja2 includes, imports, and variable substitution.
"""

from __future__ import annotations

from template_parsing_engine.core import (
    MissingVariablesError,
    RenderResult,
    TemplateFormatError,
    build_prompt_environment,
    load_micro_agent,
    render_body,
    render_template,
    resolve_prompt_path,
)
from template_parsing_engine.types import (
    RenderRequest,
    RenderResponse,
    RenderResponseError,
    RenderResponseSuccess,
    VariableSpec,
)

__version__ = "0.1.0"

__all__ = [
    # Core classes
    "RenderResult",
    # Exceptions
    "MissingVariablesError",
    "TemplateFormatError",
    # Functions
    "build_prompt_environment",
    "load_micro_agent",
    "render_body",
    "render_template",
    "resolve_prompt_path",
    # Types
    "RenderRequest",
    "RenderResponse",
    "RenderResponseError",
    "RenderResponseSuccess",
    "VariableSpec",
]
