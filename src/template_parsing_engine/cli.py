"""CLI entry point for template-parsing-engine.

Reads JSON from stdin (or --input file), renders template, writes JSON to stdout (or --output file).

Examples:
    # JSON mode (reads from stdin)
    echo '{"template_path": "/path/to/template.md", "variables": {"string_vars": {"name": "Alice"}}}' | uv run template-parsing-engine

    # File-based I/O
    uv run template-parsing-engine --input request.json --output result.json

    # Direct rendering with inline variables
    uv run template-parsing-engine --template /path/to/template.md --var-string name="Alice" --var-file content=/path/to/file.txt
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from template_parsing_engine.core import (
    MissingVariablesError,
    TemplateFormatError,
    render_template,
)
from template_parsing_engine.types import (
    FileVariable,
    RenderRequest,
    RenderResponseError,
    RenderResponseSuccess,
    VariableSpec,
)

logger = logging.getLogger(__name__)


def _create_error_response(error: Exception) -> RenderResponseError:
    """Create an error response from an exception."""
    error_type = type(error).__name__
    error_message = str(error)

    # Map specific error types
    if isinstance(error, MissingVariablesError):
        error_type = "MissingVariablesError"
    elif isinstance(error, TemplateFormatError):
        error_type = "TemplateFormatError"
    elif isinstance(error, FileNotFoundError):
        error_type = "FileNotFoundError"
    elif "TemplateNotFound" in error_type:
        error_type = "TemplateNotFound"

    return RenderResponseError(error=error_message, error_type=error_type)


def _parse_inline_variables(args: list[str]) -> dict[str, str]:
    """Parse --var-string key=value arguments."""
    variables: dict[str, str] = {}
    for arg in args:
        if "=" not in arg:
            raise ValueError(f"Invalid variable format (expected key=value): {arg}")
        key, value = arg.split("=", 1)
        variables[key] = value
    return variables


def _parse_file_variables(args: list[str]) -> list[FileVariable]:
    """Parse --var-file name=path arguments."""
    variables: list[FileVariable] = []
    for arg in args:
        if "=" not in arg:
            raise ValueError(f"Invalid file variable format (expected name=path): {arg}")
        name, path = arg.split("=", 1)
        variables.append(FileVariable(name=name, path=path))
    return variables


def _build_request_from_args(args: argparse.Namespace) -> RenderRequest:
    """Build a RenderRequest from CLI arguments."""
    string_vars = _parse_inline_variables(args.var_string or [])
    file_vars = _parse_file_variables(args.var_file or [])

    return RenderRequest(
        template_path=args.template,
        output_mode=args.output_mode,
        variables=VariableSpec(string_vars=string_vars, file_vars=file_vars),
        search_paths=args.search_path or [],
    )


def _render_from_request(request: RenderRequest) -> RenderResponseSuccess:
    """Execute the render from a request."""
    from template_parsing_engine.types import RenderResultData

    # Convert file_vars to dict format for render_template
    file_vars_dicts = [{"name": fv.name, "path": fv.path} for fv in request.variables.file_vars]

    variables_dict: dict[str, Any] = {
        "string_vars": request.variables.string_vars,
        "file_vars": file_vars_dicts,
    }

    result = render_template(
        template_path=request.template_path,
        variables=variables_dict,
        output_mode=request.output_mode,
        search_paths=request.search_paths,
    )

    return RenderResponseSuccess(
        result=RenderResultData(
            content=result.content,
            frontmatter=result.frontmatter,
        )
    )


def _read_input(args: argparse.Namespace) -> RenderRequest:
    """Read input from file or stdin."""
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        raw = input_path.read_text()
    else:
        raw = sys.stdin.read()

    if not raw.strip():
        raise ValueError(
            "No input provided. Use --template for direct rendering or provide JSON via stdin."
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON input: {exc}")

    return RenderRequest.model_validate(data)


def _write_output(
    args: argparse.Namespace, response: RenderResponseSuccess | RenderResponseError
) -> None:
    """Write output to file or stdout."""
    output = json.dumps(response.model_dump(), indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output)
    else:
        print(output)


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Template parsing engine for Jinja2/YAML markdown templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # JSON mode (stdin)
  echo '{"template_path":"/path/to/template.md"}' | uv run template-parsing-engine

  # File-based I/O
  uv run template-parsing-engine --input request.json --output result.json

  # Direct rendering
  uv run template-parsing-engine --template /path/to/template.md --var-string name="Alice"
        """,
    )

    # Input/output options
    parser.add_argument(
        "--input",
        "-i",
        help="Input JSON file (default: read from stdin)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output JSON file (default: write to stdout)",
    )

    # Direct rendering options
    parser.add_argument(
        "--template",
        "-t",
        help="Path to template file (for direct rendering mode)",
    )
    parser.add_argument(
        "--output-mode",
        "-m",
        choices=["full", "body"],
        default="full",
        help="Output mode: 'full' includes frontmatter, 'body' is template only (default: full)",
    )
    parser.add_argument(
        "--var-string",
        "-s",
        action="append",
        metavar="KEY=VALUE",
        help="String variable (can specify multiple)",
    )
    parser.add_argument(
        "--var-file",
        "-f",
        action="append",
        metavar="NAME=PATH",
        help="File variable: reads file content as variable (can specify multiple)",
    )
    parser.add_argument(
        "--search-path",
        "-p",
        action="append",
        metavar="PATH",
        help="Additional search path for includes/imports (can specify multiple)",
    )

    # Other options
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    try:
        # Determine input mode
        if args.template:
            # Direct rendering mode
            request = _build_request_from_args(args)
        else:
            # JSON mode
            request = _read_input(args)

        # Execute render
        response = _render_from_request(request)
        _write_output(args, response)
        return 0

    except Exception as exc:
        response = _create_error_response(exc)
        _write_output(args, response)
        return 1


if __name__ == "__main__":
    sys.exit(main())
