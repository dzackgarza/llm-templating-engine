# llm-templating-engine Design

## Purpose

`llm-templating-engine` is a general template library and renderer for prompt-oriented
documents and snippets.

It owns:

- template loading
- frontmatter parsing
- snippet/include resolution
- variable materialization
- Jinja rendering
- JSON-first CLI and Python interfaces

It does not own:

- model providers
- API keys
- model invocation
- output validation for LLM responses
- runner-specific metadata semantics

The engine treats frontmatter as data. It does not interpret fields like `model`,
`temperature`, `output_schema`, or `response_template`. Other tools may interpret those
fields, but this package only preserves and returns them.

## Design Goals

- Support a reusable library of prompt documents, snippets, and macros.
- Make structured data the default variable model, not a string-only workaround.
- Support file-backed variables for large text inputs without leaking file I/O into
  consumers.
- Expose simple JSON stdin/stdout contracts for JS/TS interop.
- Keep the Python API and CLI aligned with the same request and response models.
- Keep template semantics independent from any LLM runner semantics.

## Core Concepts

### Template Document

A template document is a text file with:

- optional YAML frontmatter
- a template body
- optional Jinja includes or imports

The engine should support both full prompt documents and smaller reusable snippets.

### Template Reference

A template may be referenced by:

- filesystem path
- inline text plus a logical name

Inline text support matters for programmatic consumers and tests. Path-based references
matter for prompt libraries.

### Bindings

Bindings are the values exposed to Jinja.

Bindings should have two sources:

- `data`: arbitrary JSON-serializable values available directly inside templates
- `text_files`: files that are read as text and exposed as string values

This is the canonical split. The engine should not force everything through
`string_vars`. Structured data should stay structured.

### Search Roots

Search roots define where includes and imports are resolved. They should include:

- the current template directory
- explicit search paths from the request
- an optional library root from environment or configuration

## Canonical JSON Contracts

The CLI should be command-based, but every command should accept and emit JSON.
No ad hoc action multiplexer envelope.

### `render`

Input:

```json
{
  "template": {
    "path": "prompts/review.md"
  },
  "bindings": {
    "data": {
      "ticket": {
        "id": 42,
        "title": "broken import"
      },
      "tier": "B"
    },
    "text_files": [
      {
        "name": "diff",
        "path": "artifacts/current.diff"
      }
    ]
  },
  "options": {
    "search_paths": ["prompts", "prompts/snippets"],
    "render_mode": "body",
    "strict_undefined": true
  }
}
```

Output:

```json
{
  "template": {
    "path": "/abs/path/prompts/review.md",
    "frontmatter": {
      "description": "Code review prompt"
    },
    "body_template": "Review {{ ticket.title }}"
  },
  "rendered": {
    "body": "Review broken import",
    "document": "---\ndescription: Code review prompt\n---\n\nReview broken import"
  }
}
```

Notes:

- `render_mode` controls which field callers actually care about, but the response can
  still return both rendered forms for convenience.
- `body_template` is useful for inspection and debugging.

### `inspect`

Input:

```json
{
  "template": {
    "path": "prompts/review.md"
  },
  "options": {
    "search_paths": ["prompts", "prompts/snippets"]
  }
}
```

Output:

```json
{
  "template": {
    "path": "/abs/path/prompts/review.md",
    "frontmatter": {
      "description": "Code review prompt"
    },
    "body_template": "Review {{ ticket.title }}"
  }
}
```

This command should not render. It should only parse and load.

### `validate`

Input:

```json
{
  "template": {
    "path": "prompts/review.md"
  },
  "bindings": {
    "data": {
      "ticket": {
        "title": "broken import"
      }
    }
  },
  "options": {
    "search_paths": ["prompts"]
  }
}
```

Output:

```json
{
  "valid": true,
  "missing_bindings": []
}
```

`validate` exists to support prompt authoring and CI. It should answer whether the
template can render under the provided bindings without forcing consumers to do a full
render step themselves.

## CLI Shape

Primary CLI:

- `llm-templating-engine render`
- `llm-templating-engine inspect`
- `llm-templating-engine validate`

Standalone scripts:

- `llm-template-render`
- `llm-template-inspect`
- `llm-template-validate`

Each command should:

- default to stdin for input JSON
- default to stdout for output JSON
- optionally support `--input` and `--output` file paths

The CLI should remain thin. Real behavior belongs in library functions and request/response
models.

## Python API Shape

The package should expose a small public surface:

- load a template document
- inspect a template document
- materialize bindings
- render a template document
- validate a template document against bindings

Suggested module layout:

```text
src/llm_templating_engine/
  __init__.py
  contracts.py
  bindings.py
  documents.py
  loader.py
  renderer.py
  validation.py
  cli.py
  cli_render.py
  cli_inspect.py
  cli_validate.py
```

This keeps the package shallow while separating concerns cleanly.

## Reserved Semantics

The templating engine should reserve as little meaning as possible.

Allowed engine-owned semantics:

- frontmatter parsing rules
- include/import resolution rules
- binding materialization rules
- render mode selection

Not engine-owned:

- `model`
- `models`
- `temperature`
- `max_tokens`
- `retries`
- `output_schema`
- `system_template`
- `response_template`

Those are runner concerns and should stay outside this package's interpretation logic.

## Key Design Decisions

### Structured Data Is Canonical

Templates should receive arbitrary JSON-like structures, not only strings.

That allows:

- lists and dicts in loops
- conditional logic on nested data
- richer response templating later in `llm-runner`

### File Inputs Materialize to Text

File bindings should be an explicit convenience layer. Their job is to read files and
inject text under a named variable. They should not mutate the rest of the binding model.

### Frontmatter Is Preserved, Not Interpreted

The engine should preserve all frontmatter exactly as parsed. Consumers may read runner
metadata from it later, but the engine should not understand runner policy.

### JSON Is the Interop Boundary

JS/TS callers should not need handwritten bridge logic beyond spawning a Python command
and passing JSON.

### No Runner Logic in This Repo

The engine may be used by `llm-runner`, but it should not evolve around `llm-runner`.
That dependency direction matters.

## Open Extension Points

These are valid future additions if needed, but they are not required for the initial
boundary:

- library indexing or catalog search
- template dependency graphs
- frontmatter rendering
- alternate template engines behind the same contracts
- JSON file bindings in addition to text file bindings
