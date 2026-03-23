"""Core loading, rendering, and validation logic for llm_templating_engine."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from jinja2 import (
    BaseLoader,
    ChoiceLoader,
    DictLoader,
    Environment,
    StrictUndefined,
    Undefined,
    meta,
)
from jinja2.exceptions import TemplateNotFound, UndefinedError

from llm_templating_engine.types import (
    Bindings,
    InspectTemplateRequest,
    InspectTemplateResponse,
    ListTemplatesResponse,
    RenderedTemplate,
    RenderTemplateRequest,
    RenderTemplateResponse,
    TemplateDocument,
    TemplateEntry,
    TemplateOptions,
    TemplateReference,
    TextFileBinding,
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


def _prompt_search_paths(
    *,
    document: TemplateDocument | None,
    options: TemplateOptions,
) -> list[Path]:
    """Build the ordered search-path list for prompt includes."""
    search_paths = [Path(path).expanduser().resolve() for path in options.search_paths]
    if document is None:
        search_paths.append(default_prompts_dir())
        return search_paths

    base_directory = _template_base_directory(document)
    if base_directory is not None:
        search_paths.insert(0, base_directory)
    search_paths.append(default_prompts_dir())
    return search_paths


def _inline_templates(document: TemplateDocument | None) -> dict[str, str]:
    """Return the inline-template mapping for the active document."""
    if document is None:
        return {}
    return {_template_identifier(document): document.body_template}


def _build_loader(search_paths: list[Path], inline_templates: dict[str, str]) -> BaseLoader:
    """Construct the Jinja loader stack for prompt rendering."""
    loaders: list[BaseLoader] = [PromptTemplateLoader(search_paths)]
    if inline_templates:
        loaders.insert(0, DictLoader(inline_templates))
    return loaders[0] if len(loaders) == 1 else ChoiceLoader(loaders)


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
    search_paths = _prompt_search_paths(document=document, options=effective_options)
    loader = _build_loader(search_paths, _inline_templates(document))

    return PromptTemplateEnvironment(
        loader=loader,
        undefined=StrictUndefined if effective_options.strict_undefined else Undefined,
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


def _assert_binding_name_available(
    name: str,
    *,
    materialized: dict[str, Any],
    data_bindings: dict[str, Any],
) -> None:
    """Reject binding names that collide with already-materialized inputs."""
    if name in materialized or name in data_bindings:
        raise ValueError(f"Duplicate binding name: {name}")


def _materialize_text_file_binding(
    text_file: TextFileBinding,
    *,
    document: TemplateDocument,
) -> tuple[str, str]:
    """Read one text-file binding from disk."""
    resolved_path = _resolve_binding_path(text_file.path, document)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Text file binding not found: {resolved_path}")
    return text_file.name, resolved_path.read_text()


def materialize_bindings(
    document: TemplateDocument,
    bindings: Bindings | None = None,
) -> dict[str, Any]:
    """Convert structured bindings into the context passed to Jinja."""
    binding_spec = bindings or Bindings()
    materialized: dict[str, Any] = {}

    for text_file in binding_spec.text_files:
        _assert_binding_name_available(
            text_file.name,
            materialized=materialized,
            data_bindings=binding_spec.data,
        )
        name, content = _materialize_text_file_binding(text_file, document=document)
        materialized[name] = content

    for key, value in binding_spec.data.items():
        if key in materialized:
            raise ValueError(f"Duplicate binding name: {key}")  # pragma: no cover
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

    loader = environment.loader
    assert loader is not None
    source, _, _ = loader.get_source(environment, template_name)
    parsed = environment.parse(source)
    variables = set(meta.find_undeclared_variables(parsed)) - set(environment.globals)
    referenced_templates = meta.find_referenced_templates(parsed)
    if referenced_templates is None:
        return variables  # pragma: no cover

    for referenced in referenced_templates:
        if referenced is None:
            continue  # pragma: no cover
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


def _load_context_blocks(context_files: list[str]) -> str:
    """Read markdown context files and return concatenated <extra-context> blocks."""
    blocks: list[str] = []
    for raw_path in context_files:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Context file not found: {path}")
        _, body = _split_frontmatter(path.read_text())
        blocks.append(f"<extra-context>\n{body.strip()}\n</extra-context>")
    return "\n\n".join(blocks)


def inspect_template(request: InspectTemplateRequest) -> InspectTemplateResponse:
    """Inspect a template without rendering it."""
    del request.options
    return InspectTemplateResponse(template=load_template_document(request.template))


def list_templates(root: Path | None = None) -> ListTemplatesResponse:
    """Walk the prompts directory and return an inventory of all templates."""
    prompts_root = (root or default_prompts_dir()).resolve()
    templates: list[TemplateEntry] = []

    if prompts_root.is_dir():
        for path in sorted(prompts_root.rglob("*.md")):
            frontmatter: dict[str, Any] = {}
            description: str | None = None
            try:
                frontmatter, _ = _split_frontmatter(path.read_text())
                raw_description = frontmatter.get("description")
                if isinstance(raw_description, str):
                    description = raw_description
            except (OSError, TemplateFormatError):
                pass
            slug = str(path.relative_to(prompts_root))
            templates.append(
                TemplateEntry(
                    path=str(path),
                    slug=slug,
                    description=description,
                    frontmatter=frontmatter,
                )
            )

    return ListTemplatesResponse(root=str(prompts_root), templates=templates)


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
        except MissingVariablesError as exc:  # pragma: no cover
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

    if request.context_files:
        context_blocks = _load_context_blocks(request.context_files)
        rendered_body = f"{rendered_body}\n\n{context_blocks}"

    rendered_document = f"{_reconstruct_frontmatter(document.frontmatter)}{rendered_body}"

    return RenderTemplateResponse(
        template=document,
        rendered=RenderedTemplate(
            body=rendered_body,
            document=rendered_document,
        ),
    )
