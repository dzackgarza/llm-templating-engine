"""Core templating logic for markdown prompt templates.

Templates may use either standard markdown frontmatter:

    ---
    key: value
    ---
    body

or the legacy workspace format:

    key: value
    ---
    body

Use load_micro_agent(path) to parse them into a MicroAgent,
or render_template() for the high-level JSON API.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from jinja2 import BaseLoader, Environment
from jinja2.exceptions import TemplateNotFound

if TYPE_CHECKING:
    pass


class MissingVariablesError(ValueError):
    """Raised when required template variables are not provided to render()."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"Missing required template variable(s): {', '.join(missing)}")


class TemplateFormatError(ValueError):
    """Raised when a micro-agent template file is structurally invalid."""


def default_prompts_dir() -> Path:
    """Return the workspace prompt root.

    PROMPTS_DIR environment variable may override the workspace default.
    """
    return Path(os.environ.get("PROMPTS_DIR", "/home/dzack/ai/prompts")).expanduser()


def resolve_prompt_path(path: str | Path) -> Path:
    """Resolve a prompt template path against PROMPTS_DIR."""
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return default_prompts_dir() / candidate


def _parse_yaml_block(frontmatter_text: str) -> dict:
    """Parse YAML frontmatter text into a dictionary."""
    try:
        metadata = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as exc:
        raise TemplateFormatError(f"Invalid YAML frontmatter: {exc}") from exc
    if not isinstance(metadata, dict):
        raise TemplateFormatError("Template frontmatter must be a YAML mapping")
    return metadata


def _split_frontmatter(content: str) -> tuple[dict, str]:
    """Split YAML frontmatter from template body.

    Supports two formats:
    1. Standard markdown: ---\nkey: value\n---\nbody
    2. Legacy format: key: value\n---\nbody
    """
    if content.startswith("---\n"):
        end_marker = "\n---\n"
        end_idx = content.find(end_marker, 4)
        if end_idx == -1:
            raise TemplateFormatError("Opening markdown frontmatter marker missing closing '---'")
        frontmatter_text = content[4:end_idx]
        body = content[end_idx + len(end_marker) :].lstrip("\n")
        return _parse_yaml_block(frontmatter_text), body

    lines = content.split("\n")
    sep_idx = next((i for i, line in enumerate(lines) if line == "---"), None)
    if sep_idx is None:
        return {}, content

    frontmatter_text = "\n".join(lines[:sep_idx])
    body = "\n".join(lines[sep_idx + 1 :]).lstrip("\n")
    metadata = _parse_yaml_block(frontmatter_text)
    return metadata, body


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    """Remove duplicate paths while preserving order."""
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        deduped.append(resolved)
        seen.add(resolved)
    return deduped


def _template_name_for_path(path: Path) -> str:
    """Get a template name for a path, relative to prompts dir if possible."""
    resolved = path.resolve()
    prompts_dir = default_prompts_dir().resolve()
    try:
        return str(resolved.relative_to(prompts_dir))
    except ValueError:
        return str(resolved)


class PromptTemplateLoader(BaseLoader):
    """Load prompt-template markdown files, stripping child frontmatter."""

    def __init__(self, search_paths: list[Path]) -> None:
        self.search_paths = _dedupe_paths(search_paths)

    def get_source(
        self,
        environment: Environment,
        template: str,
    ) -> tuple[str, str, Any]:
        """Get template source, stripping frontmatter from included files."""
        candidate = Path(template).expanduser()
        paths: list[Path]
        if candidate.is_absolute():
            paths = [candidate]
        else:
            paths = [search_path / candidate for search_path in self.search_paths]

        for path in paths:
            if not path.exists() or not path.is_file():
                continue
            source = path.read_text()
            _, body = _split_frontmatter(source)
            mtime = path.stat().st_mtime

            def uptodate(path: Path = path, mtime: float = mtime) -> bool:
                try:
                    return path.stat().st_mtime == mtime
                except OSError:
                    return False

            return body, str(path), uptodate

        raise TemplateNotFound(template)


class PromptTemplateEnvironment(Environment):
    """Jinja environment for prompt-template composition."""

    def join_path(self, template: str, parent: str) -> str:
        """Resolve relative paths in includes/imports."""
        if template.startswith(("./", "../")):
            parent_path = Path(parent)
            if not parent_path.is_absolute():
                parent_path = (default_prompts_dir() / parent_path).resolve()
            return str((parent_path.parent / template).resolve())
        return template


def build_prompt_environment(
    template_path: str | Path | None = None,
    search_paths: list[Path] | None = None,
) -> PromptTemplateEnvironment:
    """Create a Jinja environment rooted at PROMPTS_DIR and the template parent.

    Args:
        template_path: Optional path to the main template (adds its parent to search paths)
        search_paths: Optional additional search paths for includes/imports

    Returns:
        Configured PromptTemplateEnvironment
    """
    all_paths: list[Path] = []

    if search_paths:
        all_paths.extend(search_paths)

    all_paths.append(default_prompts_dir())

    if template_path is not None:
        all_paths.insert(0, Path(template_path).expanduser().resolve().parent)

    return PromptTemplateEnvironment(loader=PromptTemplateLoader(all_paths))


def _render_with_environment(
    body: str,
    *,
    variables: dict[str, str],
    template_path: str | Path | None = None,
    search_paths: list[Path] | None = None,
) -> str:
    """Render a template body using Jinja2 environment."""
    environment = build_prompt_environment(template_path, search_paths)
    if template_path is not None:
        template_name = _template_name_for_path(Path(template_path).expanduser())
        return environment.get_template(template_name).render(**variables)
    return environment.from_string(body).render(**variables)


@dataclass
class RenderResult:
    """Result of rendering a template."""

    content: str
    frontmatter: dict[str, Any]
    output_mode: str  # "full" or "body"


@dataclass
class MicroAgent:
    """Parsed micro-agent template.

    Attributes:
        path: Resolved path to the template file
        frontmatter: Dictionary of YAML frontmatter metadata
        system: Optional system prompt from frontmatter
        body: Template body (Jinja2 template)
        _required_inputs: List of required input names (private)
    """

    path: Path
    frontmatter: dict[str, Any]
    system: str | None
    body: str
    _required_inputs: list[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        inputs: list[dict] = self.frontmatter.get("inputs") or []
        self._required_inputs = [inp["name"] for inp in inputs if inp.get("required", False)]

    def render(self, **variables: str) -> str:
        """Render the body as a Jinja2 template.

        Raises MissingVariablesError if any required inputs (declared in
        frontmatter 'inputs:') are absent from variables.
        """
        missing = [k for k in self._required_inputs if k not in variables]
        if missing:
            raise MissingVariablesError(missing)
        return _render_with_environment(
            self.body,
            variables=variables,
            template_path=self.path,
        )


def load_micro_agent(path: str | Path) -> MicroAgent:
    """Parse a micro-agent .md file into frontmatter, system prompt, and body.

    The system prompt is taken from the 'system:' field in the YAML frontmatter.
    The body is the Jinja2 template below the frontmatter separator.

    Raises TemplateFormatError if the template is structurally invalid.
    Raises FileNotFoundError if the template file doesn't exist.
    """
    resolved_path = resolve_prompt_path(path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Template not found: {resolved_path}")
    content = resolved_path.read_text()
    frontmatter, body = _split_frontmatter(content)
    system = frontmatter.get("system")
    return MicroAgent(path=resolved_path, frontmatter=frontmatter, system=system, body=body)


def render_body(
    body: str,
    *,
    template_path: str | Path | None = None,
    search_paths: list[Path] | None = None,
    **variables: str,
) -> str:
    """Render a Jinja2 template body string with the given variables."""
    return _render_with_environment(
        body, variables=variables, template_path=template_path, search_paths=search_paths
    )


def _reconstruct_frontmatter(frontmatter: dict[str, Any]) -> str:
    """Reconstruct YAML frontmatter from a dictionary."""
    if not frontmatter:
        return ""
    yaml_content = yaml.dump(
        frontmatter, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    return f"---\n{yaml_content}---\n\n"


def render_template(
    template_path: str | Path,
    *,
    variables: dict[str, Any] | None = None,
    output_mode: str = "full",
    search_paths: list[str] | list[Path] | None = None,
) -> RenderResult:
    """High-level API to render a template with variable substitution.

    Args:
        template_path: Path to the template file (absolute or relative to PROMPTS_DIR)
        variables: Dictionary with optional keys:
            - string_vars: Dict of string variable names to values
            - file_vars: List of {name, path} dicts to read file contents
        output_mode: "full" (include frontmatter) or "body" (body only)
        search_paths: Additional paths to search for includes/imports

    Returns:
        RenderResult with content and frontmatter

    Raises:
        FileNotFoundError: If template or file variable doesn't exist
        MissingVariablesError: If required template variables are missing
        TemplateFormatError: If template structure is invalid
    """
    # Load the template
    agent = load_micro_agent(template_path)

    # Prepare variables
    all_variables: dict[str, str] = {}

    if variables:
        # Load file variables
        file_vars: list[dict[str, str]] = variables.get("file_vars", [])
        for file_spec in file_vars:
            name = file_spec["name"]
            path = Path(file_spec["path"]).expanduser()
            if not path.is_absolute():
                path = Path(template_path).parent / path
            if not path.exists():
                raise FileNotFoundError(f"File variable not found: {path}")
            all_variables[name] = path.read_text()

        # Load string variables (can override file vars)
        string_vars: dict[str, str] = variables.get("string_vars", {})
        all_variables.update(string_vars)

    # Render the template
    rendered_body = agent.render(**all_variables)

    # Construct result based on output mode
    if output_mode == "body":
        content = rendered_body
    else:  # full
        reconstructed_frontmatter = _reconstruct_frontmatter(agent.frontmatter)
        content = reconstructed_frontmatter + rendered_body

    return RenderResult(
        content=content,
        frontmatter=agent.frontmatter,
        output_mode=output_mode,
    )
