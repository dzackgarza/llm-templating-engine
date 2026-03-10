"""Typer-based JSON command surfaces for llm_templating_engine."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypeVar

import typer
from pydantic import BaseModel, ValidationError

from llm_templating_engine.core import (
    MissingVariablesError,
    TemplateFormatError,
    inspect_template,
    render_template,
    validate_template,
)
from llm_templating_engine.types import (
    ErrorDetail,
    ErrorResponse,
    InspectTemplateRequest,
    RenderTemplateRequest,
)

RequestModelT = TypeVar("RequestModelT", bound=BaseModel)

CONTEXT_SETTINGS: dict[str, list[str]] = {"help_option_names": ["-h", "--help"]}


def _build_app(*, help_text: str, no_args_is_help: bool = False) -> typer.Typer:
    """Create a Typer app with shared CLI defaults."""
    return typer.Typer(
        help=help_text,
        add_completion=False,
        no_args_is_help=no_args_is_help,
        pretty_exceptions_enable=False,
        context_settings=CONTEXT_SETTINGS,
    )


app = _build_app(
    help_text="Template loading, inspection, validation, and rendering.",
    no_args_is_help=True,
)
render_app = _build_app(help_text="Render one template request from JSON.")
inspect_app = _build_app(help_text="Inspect one template request from JSON.")
validate_app = _build_app(help_text="Validate one template request from JSON.")


def _read_json_input(input_path: str | None) -> str:
    """Read raw JSON text from a file or stdin."""
    if input_path is not None:
        candidate = Path(input_path)
        if not candidate.exists():
            raise FileNotFoundError(f"Input file not found: {candidate}")
        return candidate.read_text()
    return sys.stdin.read()


def _write_json_output(output_path: str | None, payload: BaseModel) -> None:
    """Write JSON payload to a file or stdout."""
    content = payload.model_dump_json(indent=2)
    if output_path is not None:
        Path(output_path).write_text(content)
    else:
        typer.echo(content)


def _write_error(output_path: str | None, error: Exception) -> None:
    """Write a structured error payload."""
    payload = ErrorResponse(
        error=ErrorDetail(
            type=type(error).__name__,
            message=str(error),
        )
    )
    _write_json_output(output_path, payload)


def _parse_request(model_type: type[RequestModelT], input_path: str | None) -> RequestModelT:
    """Parse one command request model from JSON."""
    raw = _read_json_input(input_path)
    try:
        return model_type.model_validate_json(raw)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def _execute_render(input_path: str | None, output_path: str | None) -> None:
    request = _parse_request(RenderTemplateRequest, input_path)
    response = render_template(request)
    _write_json_output(output_path, response)


def _execute_inspect(input_path: str | None, output_path: str | None) -> None:
    request = _parse_request(InspectTemplateRequest, input_path)
    response = inspect_template(request)
    _write_json_output(output_path, response)


def _execute_validate(input_path: str | None, output_path: str | None) -> None:
    request = _parse_request(RenderTemplateRequest, input_path)
    response = validate_template(request)
    _write_json_output(output_path, response)


def _command_wrapper(executor: callable, input_path: str | None, output_path: str | None) -> None:
    """Execute one command and emit a structured error payload on failure."""
    try:
        executor(input_path, output_path)
    except (
        FileNotFoundError,
        MissingVariablesError,
        TemplateFormatError,
        ValueError,
    ) as exc:
        _write_error(output_path, exc)
        raise typer.Exit(code=1) from exc


@render_app.callback(invoke_without_command=True)
def render_command(
    input_path: Annotated[
        str | None,
        typer.Option("--input", "-i", help="Read request JSON from this file."),
    ] = None,
    output_path: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Write response JSON to this file."),
    ] = None,
) -> None:
    """Render a template request."""
    _command_wrapper(_execute_render, input_path, output_path)


@inspect_app.callback(invoke_without_command=True)
def inspect_command(
    input_path: Annotated[
        str | None,
        typer.Option("--input", "-i", help="Read request JSON from this file."),
    ] = None,
    output_path: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Write response JSON to this file."),
    ] = None,
) -> None:
    """Inspect a template request."""
    _command_wrapper(_execute_inspect, input_path, output_path)


@validate_app.callback(invoke_without_command=True)
def validate_command(
    input_path: Annotated[
        str | None,
        typer.Option("--input", "-i", help="Read request JSON from this file."),
    ] = None,
    output_path: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Write response JSON to this file."),
    ] = None,
) -> None:
    """Validate a template request."""
    _command_wrapper(_execute_validate, input_path, output_path)


app.add_typer(render_app, name="render", help="Render one template request.")
app.add_typer(inspect_app, name="inspect", help="Inspect one template request.")
app.add_typer(validate_app, name="validate", help="Validate one template request.")


def main() -> None:
    """Run the umbrella llm-templating-engine command."""
    app()


def render_main() -> None:
    """Run the standalone llm-template-render command."""
    render_app()


def inspect_main() -> None:
    """Run the standalone llm-template-inspect command."""
    inspect_app()


def validate_main() -> None:
    """Run the standalone llm-template-validate command."""
    validate_app()


if __name__ == "__main__":
    main()
