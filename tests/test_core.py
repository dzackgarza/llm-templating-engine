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
    inspect_template,
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
