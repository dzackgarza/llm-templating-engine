"""Tests for the templating-engine core contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_templating_engine import (
    Bindings,
    InspectTemplateRequest,
    RenderTemplateRequest,
    TemplateOptions,
    TemplateReference,
    TextFileBinding,
    build_prompt_environment,
    inspect_template,
    list_templates,
    render_template,
    validate_template,
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
