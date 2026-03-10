"""CLI integration tests for llm-templating-engine."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(
    *args: str,
    stdin: str | None = None,
    script: str = "llm-templating-engine",
) -> subprocess.CompletedProcess[str]:
    """Run a console script through uv and capture stdout/stderr."""
    command = ["uv", "run", script, *args]
    return subprocess.run(
        command,
        input=stdin,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
        check=False,
    )


def test_cli_help_lists_contract_commands() -> None:
    result = run_cli("--help")

    assert result.returncode == 0
    assert "render" in result.stdout
    assert "inspect" in result.stdout
    assert "validate" in result.stdout


def test_render_command_reads_json_from_stdin(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    diff_file = tmp_path / "diff.txt"
    template.write_text("---\ndescription: Review prompt\n---\n\n{{ ticket.title }}\n{{ diff }}")
    diff_file.write_text("line one")

    request = {
        "template": {"path": str(template)},
        "bindings": {
            "data": {"ticket": {"title": "Broken import"}},
            "text_files": [{"name": "diff", "path": str(diff_file)}],
        },
    }

    result = run_cli("render", stdin=json.dumps(request))

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["template"]["frontmatter"] == {"description": "Review prompt"}
    assert payload["rendered"]["body"] == "Broken import\nline one"


def test_inspect_command_supports_file_input_and_output(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    template.write_text("---\ndescription: Review prompt\n---\n\n{{ ticket.title }}")
    input_file = tmp_path / "request.json"
    output_file = tmp_path / "response.json"
    input_file.write_text(json.dumps({"template": {"path": str(template)}}))

    result = run_cli("inspect", "--input", str(input_file), "--output", str(output_file))

    assert result.returncode == 0
    payload = json.loads(output_file.read_text())
    assert payload["template"]["body_template"] == "{{ ticket.title }}"
    assert payload["template"]["path"] == str(template.resolve())


def test_validate_command_reports_missing_bindings(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    template.write_text("{{ ticket.title }}\n{{ diff }}")

    request = {
        "template": {"path": str(template)},
        "bindings": {"data": {"ticket": {"title": "Broken import"}}},
    }

    result = run_cli("validate", stdin=json.dumps(request))

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["valid"] is False
    assert payload["missing_bindings"] == ["diff"]


def test_standalone_render_script_matches_main_command(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    template.write_text("Hello {{ name }}")

    request = {
        "template": {"path": str(template)},
        "bindings": {"data": {"name": "Alice"}},
    }

    result = run_cli(stdin=json.dumps(request), script="llm-template-render")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["rendered"]["body"] == "Hello Alice"
