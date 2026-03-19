[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/I2I57UKJ8)

# LLM Templating Engine

Jinja-based template renderer for prompt documents. Pass JSON, get rendered text. No installation required.

## Template Format

Templates are Markdown files with optional YAML frontmatter:

```markdown
---
description: Code review prompt
model: gpt-4o
---

Review the following ticket:

**Ticket:** {{ ticket.title }}
**ID:** #{{ ticket.id }}

{% if diff %}
\`\`\`diff
{{ diff }}
\`\`\`
{% endif %}

Tier: {{ tier }}
```

Variables come from `bindings.data`. For large text (diffs, file contents), use `bindings.text_files` — the engine reads the file and exposes it as a string variable.

## Commands

### `llm-template-render`

Takes a template + bindings, returns rendered output.

**Input (stdin or `--input`):**

```json
{
  "template": { "path": "prompts/review.md" },
  "bindings": {
    "data": {
      "ticket": { "id": 42, "title": "broken import" },
      "tier": "B"
    },
    "text_files": [{ "name": "diff", "path": "artifacts/current.diff" }]
  },
  "options": {
    "search_paths": ["prompts", "prompts/snippets"]
  }
}
```

**Output:**

````json
{
  "template": {
    "path": "/abs/path/prompts/review.md",
    "frontmatter": { "description": "Code review prompt" },
    "body_template": "Review the following ticket..."
  },
  "rendered": {
    "body": "Review the following ticket:\n\n**Ticket:** broken import\n**ID:** #42\n\n```diff\n+ import foo\n- import bar\n```\n\nTier: B",
    "document": "---\ndescription: Code review prompt\n---\n\nReview the following ticket..."
  }
}
````

### `llm-template-inspect`

Parse a template without rendering. Useful for checking frontmatter or body structure.

**Input:**

```json
{
  "template": { "path": "prompts/review.md" },
  "options": { "search_paths": ["prompts"] }
}
```

**Output:**

```json
{
  "template": {
    "path": "/abs/path/prompts/review.md",
    "frontmatter": { "description": "Code review prompt" },
    "body_template": "Review the following ticket..."
  }
}
```

### `llm-template-validate`

Check if bindings satisfy all template variables before rendering.

**Input:**

```json
{
  "template": { "path": "prompts/review.md" },
  "bindings": { "data": { "ticket": { "title": "broken" } } },
  "options": { "search_paths": ["prompts"] }
}
```

**Output:**

```json
{ "valid": false, "missing_bindings": ["ticket.id", "tier", "diff"] }
```

### `llm-templating-engine list`

Scan `$PROMPTS_DIR` and return an inventory of all available templates. No input required.

```bash
uvx --from git+https://github.com/dzackgarza/llm-templating-engine.git \
  llm-templating-engine list
```

**Output:**

```json
{
  "root": "/path/to/prompts",
  "templates": [
    {
      "path": "/path/to/prompts/review.md",
      "slug": "review.md",
      "description": "Code review prompt",
      "frontmatter": { "description": "Code review prompt" }
    }
  ]
}
```

## Usage

Invoke via `uvx` — no installation needed:

```bash
# Render
echo '{"template":{"path":"prompts/review.md"},"bindings":{"data":{"ticket":{"id":42,"title":"broken"}}}}' \
  | uvx --from git+https://github.com/dzackgarza/llm-templating-engine.git llm-template-render

# Inspect
echo '{"template":{"path":"prompts/review.md"}}' \
  | uvx --from git+https://github.com/dzackgarza/llm-templating-engine.git llm-template-inspect

# Validate
echo '{"template":{"path":"prompts/review.md"},"bindings":{"data":{"ticket":{"id":42}}}}' \
  | uvx --from git+https://github.com/dzackgarza/llm-templating-engine.git llm-template-validate

# List inventory
uvx --from git+https://github.com/dzackgarza/llm-templating-engine.git \
  llm-templating-engine list
```

For files instead of stdin, use `--input` and `--output`:

```bash
uvx --from git+https://github.com/dzackgarza/llm-templating-engine.git \
  llm-template-render --input request.json --output result.json
```

## Includes

Templates can include other templates via Jinja `{% include %}`:

```markdown
---
description: Main template
---

{% include "./partial.md" %}
```

Search paths are resolved in this order: template directory → `options.search_paths` → `$PROMPTS_DIR`.

## Options

| Option             | Default  | Description                                                       |
| ------------------ | -------- | ----------------------------------------------------------------- |
| `search_paths`     | `[]`     | Additional directories to search for includes                     |
| `render_mode`      | `"body"` | `"body"` returns just the body; `"document"` includes frontmatter |
| `strict_undefined` | `true`   | Raise an error if a template variable is missing                  |

## Development

```bash
just install   # install deps
just check    # typecheck, lint, tests
just build    # build wheel/sdist
just bump     # bump minor version
```
