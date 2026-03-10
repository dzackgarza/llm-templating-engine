"""Public package interface for llm_templating_engine."""

from __future__ import annotations

from llm_templating_engine.core import (
    MissingVariablesError,
    TemplateFormatError,
    build_prompt_environment,
    default_prompts_dir,
    inspect_template,
    load_template_document,
    materialize_bindings,
    render_body,
    render_template,
    resolve_prompt_path,
    validate_template,
)
from llm_templating_engine.types import (
    Bindings,
    ErrorDetail,
    ErrorResponse,
    InspectTemplateRequest,
    InspectTemplateResponse,
    RenderedTemplate,
    RenderTemplateRequest,
    RenderTemplateResponse,
    TemplateDocument,
    TemplateOptions,
    TemplateReference,
    TextFileBinding,
    ValidateTemplateResponse,
)

__version__ = "0.1.0"

__all__ = [
    "Bindings",
    "ErrorDetail",
    "ErrorResponse",
    "InspectTemplateRequest",
    "InspectTemplateResponse",
    "MissingVariablesError",
    "RenderTemplateRequest",
    "RenderTemplateResponse",
    "RenderedTemplate",
    "TemplateDocument",
    "TemplateFormatError",
    "TemplateOptions",
    "TemplateReference",
    "TextFileBinding",
    "ValidateTemplateResponse",
    "build_prompt_environment",
    "default_prompts_dir",
    "inspect_template",
    "load_template_document",
    "materialize_bindings",
    "render_body",
    "render_template",
    "resolve_prompt_path",
    "validate_template",
]
