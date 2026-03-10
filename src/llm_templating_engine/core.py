"""Core loading, rendering, and validation logic for llm_templating_engine."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from jinja2 import BaseLoader, ChoiceLoader, DictLoader, Environment, StrictUndefined, meta
from jinja2.exceptions import TemplateNotFound, UndefinedError

from llm_templating_engine.types import (
    Bindings,
    InspectTemplateRequest,
    InspectTemplateResponse,
    RenderedTemplate,
    RenderTemplateRequest,
    RenderTemplateResponse,
    TemplateDocument,
    TemplateOptions,
    TemplateReference,
    ValidateTemplateResponse,
)

_INLINE_TEMPLATE_NAME = "__inline__.md"
_UNDEFINED_NAME_RE = re.compile(r"'([^']+)' is undefined")
_MISSING_ATTRIBUTE_RE = re.compile(r"has no attribute '([^']+)'")


class MissingVariablesError(ValueError):
    """Raised when required template bindings are missing."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"Missing template binding(s): {', '.join(missing)}")


class TemplateFormatError(ValueError):
    """Raised when a template document cannot be parsed."""


def default_prompts_dir() -> Path:
    """Return the default prompt-library root."""
    configured = os.environ.get("PROMPTS_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.cwd() / "prompts").resolve()


def resolve_prompt_path(path: str | Path) -> Path:
    """Resolve a prompt path from cwd or the configured prompt library."""
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    cwd_candidate = (Path.cwd() / candidate).resolve()
    if cwd_candidate.exists():
        return cwd_candidate
    return (default_prompts_dir() / candidate).resolve()


def _parse_yaml_block(frontmatter_text: str) -> dict[str, Any]:
    """Parse YAML frontmatter into a mapping."""
    try:
        metadata = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as exc:
        raise TemplateFormatError(f"Invalid YAML frontmatter: {exc}") from exc
    if not isinstance(metadata, dict):
        raise TemplateFormatError("Template frontmatter must be a YAML mapping.")
    return metadata


def _split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from a template body."""
    if not content.startswith("---"):
        return {}, content

    lines = content.split("\n")
    sep_idx = next((index for index, line in enumerate(lines[1:]) if line == "---"), None)
    if sep_idx is None:
        raise TemplateFormatError("Opening markdown frontmatter marker missing closing '---'.")
    actual_sep_idx = sep_idx + 1
    frontmatter_text = "\n".join(lines[1:actual_sep_idx])
    body = "\n".join(lines[actual_sep_idx + 1 :]).lstrip("\n")
    return _parse_yaml_block(frontmatter_text), body


def _reconstruct_frontmatter(frontmatter: dict[str, Any]) -> str:
    """Render frontmatter back into canonical YAML document form."""
    if not frontmatter:
        return ""
    yaml_content = yaml.dump(
        frontmatter,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    return f"---\n{yaml_content}---\n\n"


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    """Deduplicate paths while preserving order."""
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        deduped.append(resolved)
        seen.add(resolved)
    return deduped


def _template_identifier(document: TemplateDocument) -> str:
    """Return the internal template identifier used by the Jinja environment."""
    if document.path is not None:
        return document.path
    if document.name is not None:
        return document.name
    return _INLINE_TEMPLATE_NAME


def _template_base_directory(document: TemplateDocument) -> Path | None:
    """Return the base directory used for relative file resolution."""
    identifier = document.path or document.name
    if identifier is None:
        return None
    return Path(identifier).expanduser().resolve().parent


class PromptTemplateLoader(BaseLoader):
    """Load prompt templates and strip frontmatter from included documents."""

    def __init__(self, search_paths: list[Path]) -> None:
        self.search_paths = _dedupe_paths(search_paths)

    def get_source(
        self,
        environment: Environment,
        template: str,
    ) -> tuple[str, str, Any]:
        """Load a template body by absolute path or search-root relative name."""
        del environment
        candidate = Path(template).expanduser()
        if candidate.is_absolute():
            paths = [candidate]
        else:
            paths = [root / candidate for root in self.search_paths]

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

            return body, str(path.resolve()), uptodate

        raise TemplateNotFound(template)


class PromptTemplateEnvironment(Environment):
    """Jinja environment for prompt templates."""

    def join_path(self, template: str, parent: str) -> str:
        """Resolve relative include/import references against the parent template."""
        if template.startswith(("./", "../")):
            return str((Path(parent).expanduser().resolve().parent / template).resolve())
        return template


def build_prompt_environment(
    *,
    document: TemplateDocument | None = None,
    options: TemplateOptions | None = None,
) -> PromptTemplateEnvironment:
    """Create a Jinja environment for a template document."""
    effective_options = options or TemplateOptions()
    search_paths = [Path(path).expanduser().resolve() for path in effective_options.search_paths]
    if document is not None:
        base_directory = _template_base_directory(document)
        if base_directory is not None:
            search_paths.insert(0, base_directory)
    search_paths.append(default_prompts_dir())

    inline_templates: dict[str, str] = {}
    if document is not None:
        inline_templates[_template_identifier(document)] = document.body_template

    loaders: list[BaseLoader] = []
    if inline_templates:
        loaders.append(DictLoader(inline_templates))
    loaders.append(PromptTemplateLoader(search_paths))
    loader = loaders[0] if len(loaders) == 1 else ChoiceLoader(loaders)

    return PromptTemplateEnvironment(
        loader=loader,
        undefined=StrictUndefined if effective_options.strict_undefined else None,
    )


def load_template_document(template: TemplateReference) -> TemplateDocument:
    """Load a template document from disk or inline text."""
    if template.path is not None:
        resolved_path = resolve_prompt_path(template.path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"Template not found: {resolved_path}")
        frontmatter, body = _split_frontmatter(resolved_path.read_text())
        return TemplateDocument(
            path=str(resolved_path),
            frontmatter=frontmatter,
            body_template=body,
        )

    assert template.text is not None
    frontmatter, body = _split_frontmatter(template.text)
    resolved_name = None
    if template.name is not None:
        resolved_name = str(Path(template.name).expanduser().resolve())
    return TemplateDocument(
        name=resolved_name,
        frontmatter=frontmatter,
        body_template=body,
    )


def _resolve_binding_path(raw_path: str, document: TemplateDocument) -> Path:
    """Resolve a text-file binding path against the template base directory."""
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    base_directory = _template_base_directory(document)
    if base_directory is not None:
        return (base_directory / candidate).resolve()
    return (Path.cwd() / candidate).resolve()


def materialize_bindings(
    document: TemplateDocument,
    bindings: Bindings | None = None,
) -> dict[str, Any]:
    """Convert structured bindings into the context passed to Jinja."""
    binding_spec = bindings or Bindings()
    materialized: dict[str, Any] = {}

    for text_file in binding_spec.text_files:
        if text_file.name in materialized or text_file.name in binding_spec.data:
            raise ValueError(f"Duplicate binding name: {text_file.name}")
        resolved_path = _resolve_binding_path(text_file.path, document)
        if not resolved_path.exists():
            raise FileNotFoundError(f"Text file binding not found: {resolved_path}")
        materialized[text_file.name] = resolved_path.read_text()

    for key, value in binding_spec.data.items():
        if key in materialized:
            raise ValueError(f"Duplicate binding name: {key}")
        materialized[key] = value

    return materialized


def _render_document_body(
    document: TemplateDocument,
    *,
    bindings: dict[str, Any],
    options: TemplateOptions,
) -> str:
    """Render the body of a template document."""
    environment = build_prompt_environment(document=document, options=options)
    try:
        template = environment.get_template(_template_identifier(document))
        return template.render(**bindings).strip()
    except UndefinedError as exc:
        missing_name = _missing_name_from_error(exc)
        raise MissingVariablesError([missing_name]) from exc


def render_body(
    body: str,
    *,
    template_name: str | None = None,
    bindings: dict[str, Any] | None = None,
    search_paths: list[str] | None = None,
    strict_undefined: bool = True,
) -> str:
    """Render an inline template body with the same environment rules."""
    document = TemplateDocument(
        name=str(Path(template_name).expanduser().resolve()) if template_name is not None else None,
        body_template=body,
    )
    options = TemplateOptions(
        search_paths=search_paths or [],
        strict_undefined=strict_undefined,
    )
    return _render_document_body(document, bindings=bindings or {}, options=options)


def _collect_template_variables(
    environment: PromptTemplateEnvironment,
    template_name: str,
    *,
    seen: set[str],
) -> set[str]:
    """Recursively collect undeclared template variables across static references."""
    if template_name in seen:
        return set()
    seen.add(template_name)

    source, _, _ = environment.loader.get_source(environment, template_name)
    parsed = environment.parse(source)
    variables = set(meta.find_undeclared_variables(parsed)) - set(environment.globals)
    referenced_templates = meta.find_referenced_templates(parsed)
    if referenced_templates is None:
        return variables

    for referenced in referenced_templates:
        if referenced is None:
            continue
        variables |= _collect_template_variables(environment, referenced, seen=seen)
    return variables


def _missing_name_from_error(error: UndefinedError) -> str:
    """Extract a usable binding name from a Jinja undefined-variable error."""
    message = str(error)
    match = _UNDEFINED_NAME_RE.search(message)
    if match is not None:
        return match.group(1)
    match = _MISSING_ATTRIBUTE_RE.search(message)
    if match is not None:
        return match.group(1)
    return "<unknown>"


def inspect_template(request: InspectTemplateRequest) -> InspectTemplateResponse:
    """Inspect a template without rendering it."""
    del request.options
    return InspectTemplateResponse(template=load_template_document(request.template))


def validate_template(request: RenderTemplateRequest) -> ValidateTemplateResponse:
    """Validate whether the provided bindings can render a template."""
    document = load_template_document(request.template)
    materialized = materialize_bindings(document, request.bindings)
    environment = build_prompt_environment(document=document, options=request.options)
    missing_bindings = sorted(
        name
        for name in _collect_template_variables(
            environment,
            _template_identifier(document),
            seen=set(),
        )
        if name not in materialized
    )
    if missing_bindings:
        return ValidateTemplateResponse(valid=False, missing_bindings=missing_bindings)

    if request.options.strict_undefined:
        try:
            _render_document_body(document, bindings=materialized, options=request.options)
        except MissingVariablesError as exc:
            return ValidateTemplateResponse(
                valid=False,
                missing_bindings=sorted(set(exc.missing)),
            )

    return ValidateTemplateResponse(valid=True, missing_bindings=[])


def render_template(request: RenderTemplateRequest) -> RenderTemplateResponse:
    """Render a template request into both body and full-document outputs."""
    document = load_template_document(request.template)
    validation = validate_template(request)
    if not validation.valid:
        raise MissingVariablesError(validation.missing_bindings)

    materialized = materialize_bindings(document, request.bindings)
    rendered_body = _render_document_body(
        document,
        bindings=materialized,
        options=request.options,
    )
    rendered_document = f"{_reconstruct_frontmatter(document.frontmatter)}{rendered_body}"

    return RenderTemplateResponse(
        template=document,
        rendered=RenderedTemplate(
            body=rendered_body,
            document=rendered_document,
        ),
    )
