"""Tests for the CLI interface."""

import json
import sys

from template_parsing_engine.cli import main


class TestCLIJSONMode:
    """Tests for CLI JSON input/output mode."""

    def test_cli_json_mode_success(self, tmp_path, monkeypatch):
        """Test successful JSON mode execution."""
        template = tmp_path / "test.md"
        template.write_text("---\ndescription: Test\n---\n\nHello, {{ name }}!")

        request = {
            "template_path": str(template),
            "output_mode": "body",
            "variables": {"string_vars": {"name": "Alice"}},
        }

        # Mock sys.argv for CLI
        monkeypatch.setattr(sys, "argv", ["template-parsing-engine"])

        class MockStdin:
            def read(self):
                return json.dumps(request)

        monkeypatch.setattr(sys, "stdin", MockStdin())

        # Capture stdout
        outputs = []

        class MockStdout:
            def write(self, data):
                outputs.append(data)

        monkeypatch.setattr(sys, "stdout", MockStdout())

        result = main()
        assert result == 0

        output = json.loads("".join(outputs))
        assert output["ok"] is True
        assert "Hello, Alice!" in output["result"]["content"]

    def test_cli_json_mode_missing_template(self, tmp_path, monkeypatch):
        """Test JSON mode with missing template."""
        request = {
            "template_path": "/nonexistent/template.md",
            "output_mode": "body",
        }

        monkeypatch.setattr(sys, "argv", ["template-parsing-engine"])

        class MockStdin:
            def read(self):
                return json.dumps(request)

        monkeypatch.setattr(sys, "stdin", MockStdin())

        outputs = []

        class MockStdout:
            def write(self, data):
                outputs.append(data)

        monkeypatch.setattr(sys, "stdout", MockStdout())

        result = main()
        assert result == 1

        output = json.loads("".join(outputs))
        assert output["ok"] is False
        assert "FileNotFoundError" in output["error_type"]

    def test_cli_json_mode_invalid_json(self, monkeypatch):
        """Test JSON mode with invalid input."""

        monkeypatch.setattr(sys, "argv", ["template-parsing-engine"])

        class MockStdin:
            def read(self):
                return "not valid json"

        monkeypatch.setattr(sys, "stdin", MockStdin())

        outputs = []

        class MockStdout:
            def write(self, data):
                outputs.append(data)

        monkeypatch.setattr(sys, "stdout", MockStdout())

        result = main()
        assert result == 1

        output = json.loads("".join(outputs))
        assert output["ok"] is False


class TestCLIDirectMode:
    """Tests for CLI direct rendering mode."""

    def test_cli_direct_mode_success(self, tmp_path, monkeypatch):
        """Test successful direct mode execution."""
        template = tmp_path / "test.md"
        template.write_text("---\ndescription: Test\n---\n\nHello, {{ name }}!")

        # Mock sys.argv
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "template-parsing-engine",
                "--template",
                str(template),
                "--var-string",
                "name=Alice",
                "--output-mode",
                "body",
            ],
        )

        outputs = []

        class MockStdout:
            def write(self, data):
                outputs.append(data)

        monkeypatch.setattr(sys, "stdout", MockStdout())

        result = main()
        assert result == 0

        output = json.loads("".join(outputs))
        assert output["ok"] is True
        assert "Hello, Alice!" in output["result"]["content"]

    def test_cli_direct_mode_file_variable(self, tmp_path, monkeypatch):
        """Test direct mode with file variable."""
        template = tmp_path / "test.md"
        template.write_text("---\n---\n\nContent: {{ content }}")

        content_file = tmp_path / "content.txt"
        content_file.write_text("File content")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "template-parsing-engine",
                "--template",
                str(template),
                "--var-file",
                f"content={content_file}",
                "--output-mode",
                "body",
            ],
        )

        outputs = []

        class MockStdout:
            def write(self, data):
                outputs.append(data)

        monkeypatch.setattr(sys, "stdout", MockStdout())

        result = main()
        assert result == 0

        output = json.loads("".join(outputs))
        assert output["ok"] is True
        assert "File content" in output["result"]["content"]


class TestCLIFileIO:
    """Tests for CLI file-based I/O."""

    def test_cli_file_input_output(self, tmp_path, monkeypatch):
        """Test file-based input and output."""
        template = tmp_path / "test.md"
        template.write_text("---\ndescription: Test\n---\n\nHello, {{ name }}!")

        input_file = tmp_path / "request.json"
        input_file.write_text(
            json.dumps(
                {
                    "template_path": str(template),
                    "output_mode": "body",
                    "variables": {"string_vars": {"name": "Alice"}},
                }
            )
        )

        output_file = tmp_path / "result.json"

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "template-parsing-engine",
                "--input",
                str(input_file),
                "--output",
                str(output_file),
            ],
        )

        result = main()
        assert result == 0

        output = json.loads(output_file.read_text())
        assert output["ok"] is True
        assert "Hello, Alice!" in output["result"]["content"]


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_cli_missing_variables(self, tmp_path, monkeypatch):
        """Test CLI with missing required variables."""
        template = tmp_path / "test.md"
        template.write_text(
            "---\ninputs:\n  - name: required\n    required: true\n---\n\n{{ required }}"
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "template-parsing-engine",
                "--template",
                str(template),
                "--output-mode",
                "body",
            ],
        )

        outputs = []

        class MockStdout:
            def write(self, data):
                outputs.append(data)

        monkeypatch.setattr(sys, "stdout", MockStdout())

        result = main()
        assert result == 1

        output = json.loads("".join(outputs))
        assert output["ok"] is False
        assert output["error_type"] == "MissingVariablesError"

    def test_cli_template_format_error(self, tmp_path, monkeypatch):
        """Test CLI with invalid template format."""
        template = tmp_path / "test.md"
        template.write_text("---\ninvalid: [yaml\n---\nbody")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "template-parsing-engine",
                "--template",
                str(template),
                "--output-mode",
                "body",
            ],
        )

        outputs = []

        class MockStdout:
            def write(self, data):
                outputs.append(data)

        monkeypatch.setattr(sys, "stdout", MockStdout())

        result = main()
        assert result == 1

        output = json.loads("".join(outputs))
        assert output["ok"] is False
        assert output["error_type"] == "TemplateFormatError"
