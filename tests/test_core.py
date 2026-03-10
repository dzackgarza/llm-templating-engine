"""Tests for the core templating functionality."""

from pathlib import Path

import pytest

from template_parsing_engine.core import (
    MissingVariablesError,
    RenderResult,
    TemplateFormatError,
    _dedupe_paths,
    _reconstruct_frontmatter,
    _split_frontmatter,
    _template_name_for_path,
    build_prompt_environment,
    default_prompts_dir,
    load_micro_agent,
    render_body,
    render_template,
    resolve_prompt_path,
)


class TestSplitFrontmatter:
    """Tests for frontmatter parsing."""

    def test_standard_frontmatter(self):
        content = "---\nkey: value\n---\n\nbody content"
        frontmatter, body = _split_frontmatter(content)
        assert frontmatter == {"key": "value"}
        assert body == "body content"

    def test_legacy_frontmatter(self):
        content = "key: value\n---\nbody content"
        frontmatter, body = _split_frontmatter(content)
        assert frontmatter == {"key": "value"}
        assert body == "body content"

    def test_no_frontmatter(self):
        content = "just body content"
        frontmatter, body = _split_frontmatter(content)
        assert frontmatter == {}
        assert body == "just body content"

    def test_multiline_body(self):
        content = "---\nkey: value\n---\n\nline1\nline2\nline3"
        frontmatter, body = _split_frontmatter(content)
        assert frontmatter == {"key": "value"}
        assert body == "line1\nline2\nline3"

    def test_invalid_yaml(self):
        content = "---\ninvalid: [unclosed\n---\nbody"
        with pytest.raises(TemplateFormatError):
            _split_frontmatter(content)


class TestLoadMicroAgent:
    """Tests for loading micro-agent templates."""

    def test_load_basic_template(self, tmp_path):
        template = tmp_path / "test.md"
        template.write_text("---\ndescription: Test\n---\n\n# Hello")

        agent = load_micro_agent(str(template))
        assert agent.frontmatter == {"description": "Test"}
        assert agent.body == "# Hello"
        assert agent.system is None

    def test_load_with_system_prompt(self, tmp_path):
        template = tmp_path / "test.md"
        template.write_text("---\nsystem: You are a helpful assistant\n---\n\n# Hello")

        agent = load_micro_agent(str(template))
        assert agent.system == "You are a helpful assistant"

    def test_load_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_micro_agent("/nonexistent/path/template.md")


class TestRenderBody:
    """Tests for rendering template bodies."""

    def test_simple_variable(self):
        result = render_body("Hello, {{ name }}!", name="Alice")
        assert result == "Hello, Alice!"

    def test_multiple_variables(self):
        result = render_body("{{ greeting }}, {{ name }}!", greeting="Hi", name="Bob")
        assert result == "Hi, Bob!"

    def test_no_variables(self):
        result = render_body("Static content")
        assert result == "Static content"


class TestRenderTemplate:
    """Tests for the high-level render_template API."""

    def test_render_basic(self, tmp_path):
        template = tmp_path / "test.md"
        template.write_text("---\ndescription: Test\n---\n\nHello, {{ name }}!")

        result = render_template(
            str(template),
            variables={"string_vars": {"name": "Alice"}},
            output_mode="body",
        )
        assert isinstance(result, RenderResult)
        assert result.content == "Hello, Alice!"
        assert result.frontmatter == {"description": "Test"}
        assert result.output_mode == "body"

    def test_render_full(self, tmp_path):
        template = tmp_path / "test.md"
        template.write_text("---\ndescription: Test\n---\n\nHello, {{ name }}!")

        result = render_template(
            str(template),
            variables={"string_vars": {"name": "Alice"}},
            output_mode="full",
        )
        assert "---" in result.content
        assert "description: Test" in result.content
        assert "Hello, Alice!" in result.content

    def test_render_with_file_variable(self, tmp_path):
        # Create content file
        content_file = tmp_path / "content.txt"
        content_file.write_text("File content here")

        # Create template
        template = tmp_path / "test.md"
        template.write_text("---\n---\n\nContent: {{ content }}")

        result = render_template(
            str(template),
            variables={"file_vars": [{"name": "content", "path": str(content_file)}]},
            output_mode="body",
        )
        assert "File content here" in result.content

    def test_render_missing_required_variable(self, tmp_path):
        template = tmp_path / "test.md"
        template.write_text(
            "---\ninputs:\n  - name: required_var\n    required: true\n---\n\n{{ required_var }}"
        )

        with pytest.raises(MissingVariablesError):
            render_template(str(template), output_mode="body")


class TestPathFunctions:
    """Tests for path-related utilities."""

    def test_default_prompts_dir(self):
        result = default_prompts_dir()
        assert isinstance(result, Path)

    def test_resolve_prompt_path_absolute(self):
        result = resolve_prompt_path("/absolute/path/to/template.md")
        assert result == Path("/absolute/path/to/template.md")

    def test_dedupe_paths(self):
        paths = [Path("/a"), Path("/b"), Path("/a")]  # /a is duplicated
        result = _dedupe_paths(paths)
        assert len(result) == 2
        assert result[0] == Path("/a").resolve()
        assert result[1] == Path("/b").resolve()

    def test_template_name_for_path_within_prompts(self, tmp_path, monkeypatch):
        # Mock default_prompts_dir to return our temp path
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        def mock_default():
            return prompts_dir

        monkeypatch.setattr(
            "template_parsing_engine.core.default_prompts_dir",
            mock_default,
        )

        template = prompts_dir / "subdir" / "template.md"
        template.parent.mkdir(parents=True)

        result = _template_name_for_path(template)
        # Should return relative path when inside prompts_dir
        assert "subdir/template.md" in result or "subdir\\template.md" in result


class TestBuildEnvironment:
    """Tests for building Jinja environments."""

    def test_build_basic_environment(self):
        env = build_prompt_environment()
        assert env is not None

    def test_build_with_template_path(self, tmp_path):
        template = tmp_path / "test.md"
        template.touch()
        env = build_prompt_environment(str(template))
        assert env is not None


class TestReconstructFrontmatter:
    """Tests for frontmatter reconstruction."""

    def test_reconstruct_simple(self):
        frontmatter = {"description": "Test"}
        result = _reconstruct_frontmatter(frontmatter)
        assert result.startswith("---")
        assert "description: Test" in result
        assert result.endswith("---\n\n")

    def test_reconstruct_empty(self):
        result = _reconstruct_frontmatter({})
        assert result == ""

    def test_reconstruct_multiple_fields(self):
        frontmatter = {"description": "Test", "mode": "primary"}
        result = _reconstruct_frontmatter(frontmatter)
        assert "description: Test" in result
        assert "mode: primary" in result
