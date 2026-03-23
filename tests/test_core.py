"""Tests for the templating-engine core contracts."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from llm_templating_engine import (
    Bindings,
    InspectTemplateRequest,
    MissingVariablesError,
    RenderTemplateRequest,
    TemplateFormatError,
    TemplateOptions,
    TemplateReference,
    TextFileBinding,
    build_prompt_environment,
    default_prompts_dir,
    inspect_template,
    list_templates,
    render_body,
    render_template,
    resolve_prompt_path,
    validate_template,
)
from llm_templating_engine.core import (
    _INLINE_TEMPLATE_NAME,
    _collect_template_variables,
    _missing_name_from_error,
    _parse_yaml_block,
    _resolve_binding_path,
    _split_frontmatter,
    _template_base_directory,
    _template_identifier,
)


def test_inspect_template_loads_frontmatter_and_body(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    template.write_text("---\ndescription: Review prompt\n---\n\nReview {{ ticket.title }}")

    response = inspect_template(
        InspectTemplateRequest(
            template=TemplateReference(path=str(template)),
        )
    )

    assert response.template.path == str(template.resolve())
    assert response.template.frontmatter == {"description": "Review prompt"}
    assert response.template.body_template == "Review {{ ticket.title }}"


def test_render_template_renders_structured_data_and_text_files(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    diff_file = tmp_path / "diff.txt"
    template.write_text(
        "---\n"
        "description: Review prompt\n"
        "---\n\n"
        "Ticket {{ ticket.id }}: {{ ticket.title }}\n"
        "{{ diff }}"
    )
    diff_file.write_text("line one\nline two")

    response = render_template(
        RenderTemplateRequest(
            template=TemplateReference(path=str(template)),
            bindings=Bindings(
                data={"ticket": {"id": 42, "title": "Broken import"}},
                text_files=[TextFileBinding(name="diff", path=str(diff_file))],
            ),
        )
    )

    assert response.template.frontmatter == {"description": "Review prompt"}
    assert response.rendered.body == "Ticket 42: Broken import\nline one\nline two"
    assert response.rendered.document == (
        "---\ndescription: Review prompt\n---\n\nTicket 42: Broken import\nline one\nline two"
    )


def test_render_template_supports_inline_text_with_logical_name(tmp_path: Path) -> None:
    snippets = tmp_path / "snippets"
    snippets.mkdir()
    partial = snippets / "partial.md"
    partial.write_text("---\nlabel: partial\n---\n\n{{ suffix }}")

    response = render_template(
        RenderTemplateRequest(
            template=TemplateReference(
                text=(
                    "---\n"
                    "description: Inline prompt\n"
                    "---\n\n"
                    "Hello {{ name }} {% include './partial.md' %}"
                ),
                name=str(snippets / "main.md"),
            ),
            bindings=Bindings(data={"name": "Alice", "suffix": "there"}),
            options=TemplateOptions(search_paths=[str(snippets)]),
        )
    )

    assert response.template.name == str((snippets / "main.md").resolve())
    assert response.rendered.body == "Hello Alice there"


def test_render_template_supports_path_templates_without_frontmatter(tmp_path: Path) -> None:
    template = tmp_path / "response_template.md"
    template.write_text(
        "{% if probe_prompt %}Probe {{ probe_prompt }}{% else %}Tier {{ tier }}{% endif %}"
    )

    response = render_template(
        RenderTemplateRequest(
            template=TemplateReference(path=str(template)),
            bindings=Bindings(data={"tier": "model-self", "probe_prompt": ""}),
        )
    )

    assert response.template.frontmatter == {}
    assert response.rendered.body == "Tier model-self"
    assert response.rendered.document == "Tier model-self"


def test_build_prompt_environment_supports_search_paths_without_document(
    tmp_path: Path,
) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "greeting.md").write_text("Hello {{ name }}")

    environment = build_prompt_environment(
        options=TemplateOptions(search_paths=[str(prompts_dir)]),
    )

    rendered = environment.get_template("greeting.md").render({"name": "Alice"})

    assert rendered == "Hello Alice"


def test_validate_template_reports_missing_bindings(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    template.write_text("{{ ticket.title }}\n{{ diff }}\n{{ extra }}")

    response = validate_template(
        request=RenderTemplateRequest(
            template=TemplateReference(path=str(template)),
            bindings=Bindings(data={"ticket": {"title": "Broken import"}}),
        )
    )

    assert response.valid is False
    assert response.missing_bindings == ["diff", "extra"]


def test_validate_template_accepts_complete_bindings(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    diff_file = tmp_path / "diff.txt"
    template.write_text("{{ ticket.title }}\n{{ diff }}")
    diff_file.write_text("line one")

    response = validate_template(
        request=RenderTemplateRequest(
            template=TemplateReference(path=str(template)),
            bindings=Bindings(
                data={"ticket": {"title": "Broken import"}},
                text_files=[TextFileBinding(name="diff", path=str(diff_file))],
            ),
        )
    )

    assert response.valid is True
    assert response.missing_bindings == []


def test_render_template_rejects_duplicate_binding_names(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    diff_file = tmp_path / "diff.txt"
    template.write_text("{{ diff }}")
    diff_file.write_text("line one")

    with pytest.raises(ValueError):
        render_template(
            RenderTemplateRequest(
                template=TemplateReference(path=str(template)),
                bindings=Bindings(
                    data={"diff": "inline"},
                    text_files=[TextFileBinding(name="diff", path=str(diff_file))],
                ),
            )
        )


def test_render_template_raises_for_missing_text_file_binding(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    missing_file = tmp_path / "missing.txt"
    template.write_text("{{ diff }}")

    with pytest.raises(FileNotFoundError):
        render_template(
            RenderTemplateRequest(
                template=TemplateReference(path=str(template)),
                bindings=Bindings(
                    text_files=[TextFileBinding(name="diff", path=str(missing_file))],
                ),
            )
        )


def test_template_reference_requires_one_source() -> None:
    with pytest.raises(ValueError):
        TemplateReference()

    with pytest.raises(ValueError):
        TemplateReference(path="a.md", text="{{ name }}")


def test_render_response_round_trips_as_json(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    template.write_text("Hello {{ name }}")

    response = render_template(
        RenderTemplateRequest(
            template=TemplateReference(path=str(template)),
            bindings=Bindings(data={"name": "Alice"}),
        )
    )

    payload = json.loads(response.model_dump_json())
    assert payload["template"]["body_template"] == "Hello {{ name }}"
    assert payload["rendered"]["body"] == "Hello Alice"


def test_render_template_appends_context_files_as_extra_context_blocks(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    ctx1 = tmp_path / "skill1.md"
    ctx2 = tmp_path / "skill2.md"
    template.write_text("---\ndescription: Review\n---\n\nReview {{ ticket }}")
    ctx1.write_text("---\ndescription: Skill one\n---\n\nFirst context body.")
    ctx2.write_text("Second context body, no frontmatter.")

    response = render_template(
        RenderTemplateRequest(
            template=TemplateReference(path=str(template)),
            bindings=Bindings(data={"ticket": "broken import"}),
            context_files=[str(ctx1), str(ctx2)],
        )
    )

    body = response.rendered.body
    assert body.startswith("Review broken import")
    assert "<extra-context>\nFirst context body.\n</extra-context>" in body
    assert "<extra-context>\nSecond context body, no frontmatter.\n</extra-context>" in body
    assert body.index("First") < body.index("Second")


def test_render_template_with_no_context_files_is_unchanged(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    template.write_text("Hello {{ name }}")

    response = render_template(
        RenderTemplateRequest(
            template=TemplateReference(path=str(template)),
            bindings=Bindings(data={"name": "Alice"}),
        )
    )

    assert response.rendered.body == "Hello Alice"
    assert "<extra-context>" not in response.rendered.body


def test_list_templates_returns_inventory(tmp_path: Path) -> None:
    # Create a nested template structure
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (tmp_path / "review.md").write_text(
        "---\ndescription: Review prompt\n---\n\nReview {{ ticket }}"
    )
    (subdir / "summarize.md").write_text(
        "---\ndescription: Summarize\ntags: [docs]\n---\n\nSummarize: {{ text }}"
    )
    (tmp_path / "bare.md").write_text("No frontmatter here")

    response = list_templates(root=tmp_path)

    assert response.root == str(tmp_path.resolve())
    slugs = {entry.slug for entry in response.templates}
    assert slugs == {"review.md", "subdir/summarize.md", "bare.md"}

    review_entry = next(e for e in response.templates if e.slug == "review.md")
    assert review_entry.description == "Review prompt"
    assert review_entry.frontmatter == {"description": "Review prompt"}

    bare_entry = next(e for e in response.templates if e.slug == "bare.md")
    assert bare_entry.description is None
    assert bare_entry.frontmatter == {}

    summarize_entry = next(e for e in response.templates if e.slug == "subdir/summarize.md")
    assert summarize_entry.description == "Summarize"
    assert summarize_entry.frontmatter == {"description": "Summarize", "tags": ["docs"]}


def test_list_templates_handles_missing_dir(tmp_path: Path) -> None:
    nonexistent = tmp_path / "does_not_exist"
    response = list_templates(root=nonexistent)
    assert response.root == str(nonexistent.resolve())
    assert response.templates == []


# ---------------------------------------------------------------------------
# Coverage-filling tests for pre-existing uncovered lines
# ---------------------------------------------------------------------------


def test_missing_variables_error_has_missing_attribute() -> None:
    err = MissingVariablesError(["a", "b"])
    assert err.missing == ["a", "b"]
    assert "a" in str(err)
    assert "b" in str(err)


def test_default_prompts_dir_uses_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMPTS_DIR", "/tmp/my-prompts")
    result = default_prompts_dir()
    assert result == Path("/tmp/my-prompts").resolve()


def test_resolve_prompt_path_relative_in_cwd(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    template.write_text("hello")
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = resolve_prompt_path("review.md")
        assert result == template.resolve()
    finally:
        os.chdir(old_cwd)


def test_resolve_prompt_path_relative_falls_back_to_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    template = prompts_dir / "review.md"
    template.write_text("hello")
    monkeypatch.setenv("PROMPTS_DIR", str(prompts_dir))
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = resolve_prompt_path("review.md")
        assert result == template.resolve()
    finally:
        os.chdir(old_cwd)


def test_parse_yaml_block_invalid_yaml() -> None:
    with pytest.raises(TemplateFormatError, match="Invalid YAML"):
        _parse_yaml_block("{{{invalid yaml>>>")


def test_parse_yaml_block_non_dict() -> None:
    with pytest.raises(TemplateFormatError, match="must be a YAML mapping"):
        _parse_yaml_block("- just a list\n- not a mapping\n")


def test_split_frontmatter_unclosed_marker() -> None:
    with pytest.raises(TemplateFormatError, match="missing closing"):
        _split_frontmatter("---\nkey: value\nbody text but no closing")


def test_template_identifier_uses_inline_name() -> None:
    from llm_templating_engine.types import TemplateDocument

    doc_name = "/some/inline/name.md"
    doc = TemplateDocument(name=doc_name, body_template="hello {{ name }}")
    assert _template_identifier(doc) == doc_name


def test_template_identifier_uses_default_when_no_path_or_name() -> None:
    from llm_templating_engine.types import TemplateDocument

    doc = TemplateDocument(body_template="hello")
    assert _template_identifier(doc) == _INLINE_TEMPLATE_NAME


def test_template_base_directory_returns_none_when_no_path_or_name() -> None:
    from llm_templating_engine.types import TemplateDocument

    doc = TemplateDocument(body_template="hello")
    assert _template_base_directory(doc) is None


def test_prompt_template_loader_raises_template_not_found(tmp_path: Path) -> None:
    from jinja2.exceptions import TemplateNotFound

    from llm_templating_engine.core import PromptTemplateEnvironment, PromptTemplateLoader

    loader = PromptTemplateLoader([tmp_path])
    env = PromptTemplateEnvironment(loader=loader)
    with pytest.raises(TemplateNotFound):
        loader.get_source(env, "nonexistent.md")


def test_prompt_template_loader_uptodate_callback(tmp_path: Path) -> None:
    import time

    from llm_templating_engine.core import PromptTemplateEnvironment, PromptTemplateLoader

    template = tmp_path / "review.md"
    template.write_text("hello {{ name }}")
    loader = PromptTemplateLoader([tmp_path])
    env = PromptTemplateEnvironment(loader=loader)
    source, path, uptodate = loader.get_source(env, "review.md")
    assert source == "hello {{ name }}"
    assert uptodate() is True
    # Ensure mtime actually changes
    time.sleep(1.0)
    template.write_text("changed")
    assert uptodate() is False


def test_load_template_document_missing_file() -> None:
    with pytest.raises(FileNotFoundError, match="Template not found"):
        render_template(
            RenderTemplateRequest(
                template=TemplateReference(path="/nonexistent/path/template.md"),
                bindings=Bindings(data={"name": "Alice"}),
            )
        )


def test_resolve_binding_path_relative_without_base_directory() -> None:
    from llm_templating_engine.types import TemplateDocument

    doc = TemplateDocument(body_template="hello")
    result = _resolve_binding_path("artifacts/diff.txt", doc)
    assert result == (Path.cwd() / "artifacts" / "diff.txt").resolve()


def test_materialize_bindings_data_key_collides_with_text_file(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    f = tmp_path / "diff.txt"
    template.write_text("{{ diff }}")
    f.write_text("data")

    with pytest.raises(ValueError, match="Duplicate binding name: diff"):
        render_template(
            RenderTemplateRequest(
                template=TemplateReference(path=str(template)),
                bindings=Bindings(
                    data={"diff": "from_data"},
                    text_files=[TextFileBinding(name="diff", path=str(f))],
                ),
            )
        )


def test_render_body_without_template_name() -> None:
    result = render_body("Hello {{ name }}", bindings={"name": "Alice"})
    assert result == "Hello Alice"


def test_render_body_with_search_paths(tmp_path: Path) -> None:
    (tmp_path / "inc.md").write_text("---\n---\nincluded content")
    result = render_body(
        'Hello {% include "inc.md" %}',
        bindings={},
        search_paths=[str(tmp_path)],
    )
    assert result == "Hello included content"


def test_render_body_non_strict_undefined_allows_missing() -> None:
    result = render_body("Hello {{ name }}", bindings={}, strict_undefined=False)
    assert result == "Hello"


def test_collect_template_variables_with_no_referenced_templates() -> None:
    from llm_templating_engine.types import TemplateDocument

    doc = TemplateDocument(body_template="Hello {{ name }}")
    env = build_prompt_environment(document=doc)
    name = _template_identifier(doc)
    # Prime the environment with the inline template
    env.loader.get_source(env, name)  # type: ignore[union-attr]
    variables = _collect_template_variables(env, name, seen=set())
    assert "name" in variables


def test_missing_name_from_error_unknown_format() -> None:
    from jinja2.exceptions import UndefinedError

    exc = UndefinedError("some weird unparseable error message")
    assert _missing_name_from_error(exc) == "<unknown>"


def test_validate_template_non_strict_mode(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    template.write_text("Hello {{ name }}")

    # Non-strict mode skips the test render but still reports missing bindings
    # from static analysis. Provide the binding to make it valid.
    response = validate_template(
        RenderTemplateRequest(
            template=TemplateReference(path=str(template)),
            bindings=Bindings(data={"name": "Alice"}),
            options=TemplateOptions(strict_undefined=False),
        )
    )

    assert response.valid is True
    assert response.missing_bindings == []


def test_render_template_raises_on_validation_failure(tmp_path: Path) -> None:
    template = tmp_path / "review.md"
    template.write_text("Hello {{ name }}")
    with pytest.raises(MissingVariablesError, match="name"):
        render_template(
            RenderTemplateRequest(
                template=TemplateReference(path=str(template)),
                bindings=Bindings(),
            )
        )


def test_uptodate_callback_handles_os_error(tmp_path: Path) -> None:
    import time

    from llm_templating_engine.core import PromptTemplateEnvironment, PromptTemplateLoader

    template = tmp_path / "review.md"
    template.write_text("hello")
    loader = PromptTemplateLoader([tmp_path])
    env = PromptTemplateEnvironment(loader=loader)
    source, path, uptodate = loader.get_source(env, "review.md")
    assert uptodate() is True
    # Delete the file — stat() raises OSError, uptodate should return False
    time.sleep(1.0)
    template.unlink()
    assert uptodate() is False


def test_resolve_binding_path_relative_with_base_directory(tmp_path: Path) -> None:
    from llm_templating_engine.core import _resolve_binding_path
    from llm_templating_engine.types import TemplateDocument

    doc_path = str(tmp_path / "template.md")
    doc = TemplateDocument(path=doc_path, body_template="hello")
    result = _resolve_binding_path("artifacts/diff.txt", doc)
    assert result == (tmp_path / "artifacts" / "diff.txt").resolve()


def test_materialize_bindings_data_key_collides_with_existing_key(tmp_path: Path) -> None:
    from llm_templating_engine.core import materialize_bindings
    from llm_templating_engine.types import TemplateDocument

    doc = TemplateDocument(body_template="hello")
    with pytest.raises(ValueError, match="Duplicate binding name: x"):
        materialize_bindings(
            doc,
            Bindings(
                data={"x": "duplicate"},
                text_files=[TextFileBinding(name="x", path=str(tmp_path / "dummy.txt"))],
            ),
        )
    # Also test the reverse: data key collides with already-materialized text file
    dummy = tmp_path / "dummy.txt"
    dummy.write_text("content")
    with pytest.raises(ValueError, match="Duplicate binding name: y"):
        materialize_bindings(
            doc,
            Bindings(
                data={"y": "dup"},
                text_files=[TextFileBinding(name="y", path=str(dummy))],
            ),
        )


def test_render_document_body_missing_variable_catches_undefined() -> None:
    from llm_templating_engine.core import _render_document_body
    from llm_templating_engine.types import TemplateDocument, TemplateOptions

    doc = TemplateDocument(body_template="Hello {{ name }}")
    with pytest.raises(MissingVariablesError, match="name"):
        _render_document_body(doc, bindings={}, options=TemplateOptions())


def test_collect_template_variables_skips_already_seen() -> None:
    doc_path = "/tmp/fake.md"
    from llm_templating_engine.types import TemplateDocument

    doc = TemplateDocument(path=doc_path, body_template="Hello {{ name }}")
    env = build_prompt_environment(document=doc)
    from llm_templating_engine.core import _template_identifier

    name = _template_identifier(doc)
    # Already seen — should return empty set without loading
    result = _collect_template_variables(env, name, seen={name})
    assert result == set()


def test_collect_template_variables_skips_none_referenced() -> None:
    from llm_templating_engine.types import TemplateDocument

    # A template with no Jinja includes/imports — find_referenced_templates returns None
    doc = TemplateDocument(body_template="Hello {{ name }}")
    env = build_prompt_environment(document=doc)
    from llm_templating_engine.core import _template_identifier

    name = _template_identifier(doc)
    env.loader.get_source(env, name)  # type: ignore[union-attr]
    variables = _collect_template_variables(env, name, seen=set())
    assert "name" in variables


def test_missing_name_from_error_missing_attribute() -> None:
    from jinja2.exceptions import UndefinedError

    exc = UndefinedError("'foo' has no attribute 'bar'")
    assert _missing_name_from_error(exc) == "bar"


def test_load_context_blocks_missing_file() -> None:
    from llm_templating_engine.core import _load_context_blocks

    with pytest.raises(FileNotFoundError, match="Context file not found"):
        _load_context_blocks(["/nonexistent/context.md"])


def test_list_templates_skips_malformed_templates(tmp_path: Path) -> None:
    # A .md file with unclosed frontmatter should be skipped, not crash
    (tmp_path / "bad.md").write_text("---\nunclosed frontmatter")
    (tmp_path / "good.md").write_text("No frontmatter, just body")

    response = list_templates(root=tmp_path)
    slugs = {e.slug for e in response.templates}
    # bad.md should still appear (frontmatter parsing fails but it's caught)
    assert "good.md" in slugs
