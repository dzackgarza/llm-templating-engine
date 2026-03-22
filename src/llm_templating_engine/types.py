"""Typed request and response models for llm_templating_engine."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class TemplateReference(BaseModel):
    """Reference to a template by path or inline text."""

    path: str | None = Field(default=None, description="Filesystem path to the template.")
    text: str | None = Field(default=None, description="Inline template document text.")
    name: str | None = Field(
        default=None,
        description="Logical template name for inline templates.",
    )

    @model_validator(mode="after")
    def validate_source(self) -> TemplateReference:
        """Require exactly one source field."""
        source_count = int(self.path is not None) + int(self.text is not None)
        if source_count != 1:
            raise ValueError("Exactly one of 'path' or 'text' must be provided.")
        return self


class TextFileBinding(BaseModel):
    """A text file to materialize into a named template binding."""

    name: str = Field(..., description="Binding name to expose inside templates.")
    path: str = Field(..., description="Path to a text file to read.")


class Bindings(BaseModel):
    """Structured bindings exposed to Jinja templates."""

    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary structured data exposed directly to templates.",
    )
    text_files: list[TextFileBinding] = Field(
        default_factory=list,
        description="Text files to read and expose as string bindings.",
    )


class TemplateOptions(BaseModel):
    """Rendering and loading options for template commands."""

    search_paths: list[str] = Field(
        default_factory=list,
        description="Additional search paths for includes and imports.",
    )
    strict_undefined: bool = Field(
        default=True,
        description="Raise on missing bindings during rendering when true.",
    )


class TemplateDocument(BaseModel):
    """Parsed template document metadata."""

    path: str | None = Field(default=None, description="Resolved template path when path-backed.")
    name: str | None = Field(default=None, description="Logical name when inline-backed.")
    frontmatter: dict[str, Any] = Field(
        default_factory=dict,
        description="Parsed YAML frontmatter.",
    )
    body_template: str = Field(..., description="Template body with frontmatter removed.")


class InspectTemplateRequest(BaseModel):
    """Request to inspect a template without rendering it."""

    template: TemplateReference
    options: TemplateOptions = Field(default_factory=TemplateOptions)


class InspectTemplateResponse(BaseModel):
    """Inspection response containing the parsed template document."""

    template: TemplateDocument


class RenderedTemplate(BaseModel):
    """Rendered template outputs."""

    body: str = Field(..., description="Rendered template body.")
    document: str = Field(..., description="Rendered document including frontmatter.")


class RenderTemplateRequest(BaseModel):
    """Request to render a template document."""

    template: TemplateReference
    bindings: Bindings = Field(default_factory=Bindings)
    options: TemplateOptions = Field(default_factory=TemplateOptions)


class RenderTemplateResponse(BaseModel):
    """Rendered template response."""

    template: TemplateDocument
    rendered: RenderedTemplate


class ValidateTemplateResponse(BaseModel):
    """Validation response for a renderable template request."""

    valid: bool
    missing_bindings: list[str] = Field(default_factory=list)


class ErrorDetail(BaseModel):
    """Structured error payload for CLI output."""

    type: str
    message: str


class ErrorResponse(BaseModel):
    """Command error response."""

    error: ErrorDetail


class TemplateEntry(BaseModel):
    """A single template in the inventory."""

    path: str = Field(..., description="Resolved filesystem path to the template.")
    slug: str = Field(
        ..., description="Relative path from the prompts root, usable as a template reference."
    )
    description: str | None = Field(
        default=None, description="Description from frontmatter, if present."
    )
    frontmatter: dict[str, Any] = Field(
        default_factory=dict,
        description="Full frontmatter metadata.",
    )


class ListTemplatesResponse(BaseModel):
    """Inventory of available templates in the prompts directory."""

    root: str = Field(..., description="The prompts directory that was scanned.")
    templates: list[TemplateEntry] = Field(
        default_factory=list, description="All discovered templates."
    )
