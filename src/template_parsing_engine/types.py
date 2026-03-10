"""Type definitions for the template parsing engine.

These types support both Python and TypeScript consumers via JSON serialization.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FileVariable(BaseModel):
    """A file variable that reads content from a file path.

    Attributes:
        name: The variable name to use in templates (e.g., "content")
        path: Path to the file (relative to template dir or absolute)
    """

    name: str = Field(..., description="Variable name for template substitution")
    path: str = Field(..., description="Path to file containing variable content")


class VariableSpec(BaseModel):
    """Variable specification combining string and file variables.

    Attributes:
        string_vars: Dictionary of variable names to string values
        file_vars: List of file variables to read and substitute
    """

    string_vars: dict[str, str] = Field(
        default_factory=dict,
        description="String variables for template substitution",
    )
    file_vars: list[FileVariable] = Field(
        default_factory=list,
        description="File variables to read and substitute",
    )


class RenderRequest(BaseModel):
    """Request to render a template.

    This is the primary input for the CLI and JSON API.

    Attributes:
        template_path: Path to the template file (.md with YAML frontmatter)
        output_mode: Whether to return "full" content with frontmatter or "body" only
        variables: Variable substitutions for the template
        search_paths: Additional paths to search for includes/imports
    """

    template_path: str = Field(
        ...,
        description="Path to the template file (absolute or relative to PROMPTS_DIR)",
    )
    output_mode: str = Field(
        default="full",
        pattern="^(full|body)$",
        description="Output mode: 'full' includes frontmatter, 'body' is template body only",
    )
    variables: VariableSpec = Field(
        default_factory=VariableSpec,
        description="Variables for template substitution",
    )
    search_paths: list[str] = Field(
        default_factory=list,
        description="Additional paths to search for includes/imports",
    )


class RenderResultData(BaseModel):
    """Rendered template result data.

    Attributes:
        content: The rendered template content
        frontmatter: The parsed YAML frontmatter as a dictionary
    """

    content: str = Field(..., description="Rendered template content")
    frontmatter: dict[str, Any] = Field(
        default_factory=dict,
        description="Parsed YAML frontmatter from the template",
    )


class RenderResponseSuccess(BaseModel):
    """Successful render response.

    Attributes:
        ok: Always True for success
        result: The rendered template result
    """

    ok: bool = Field(default=True, description="Success indicator")
    result: RenderResultData = Field(..., description="Rendered template result")


class RenderResponseError(BaseModel):
    """Error render response.

    Attributes:
        ok: Always False for errors
        error: Human-readable error message
        error_type: Machine-readable error type for handling
    """

    ok: bool = Field(default=False, description="Error indicator")
    error: str = Field(..., description="Error message")
    error_type: str = Field(
        default="UnknownError",
        description="Error type: MissingVariablesError, TemplateFormatError, FileNotFoundError, TemplateNotFound, UnknownError",
    )


# Union type for responses
RenderResponse = RenderResponseSuccess | RenderResponseError
