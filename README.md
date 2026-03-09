[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/I2I57UKJ8)

# Template Parsing Engine

Parse Jinja2 and YAML markdown templates with this standalone engine. It supports frontmatter and complex template structures.

## Features

- **YAML Frontmatter Parsing**: Extract metadata from markdown templates efficiently.
- **Jinja2 Templating**: Include files, import modules, and substitute variables with full Jinja2 support.
- **File Variables**: Read file contents directly into template variables.
- **JSON I/O**: Integrate easily with TypeScript or JavaScript via a JSON API.
- **CLI and Module**: Use the engine as a command-line tool or a Python module.

## Installation

### Via uv (recommended)

Install and run directly with `uvx`:

```bash
uvx --from git+https://github.com/dzackgarza/template-parsing-engine template-parsing-engine
```

### As a dependency

Add the engine to your `pyproject.toml`:

```toml
# pyproject.toml
dependencies = [
    "template-parsing-engine @ git+https://github.com/dzackgarza/template-parsing-engine"
]
```

## Usage

### CLI

**JSON Mode** (reads from stdin, writes to stdout):

```bash
echo '{
  "template_path": "/path/to/template.md",
  "output_mode": "body",
  "variables": {
    "string_vars": {"name": "Alice"},
    "file_vars": [{"name": "content", "path": "/path/to/content.txt"}]
  }
}' | uv run template-parsing-engine
```

**File-based I/O**:

```bash
uv run template-parsing-engine --input request.json --output result.json
```

**Direct Rendering**:

```bash
uv run template-parsing-engine \
  --template /path/to/template.md \
  --var-string name="Alice" \
  --var-file content=/path/to/content.txt \
  --output-mode body
```

### Python Module

Use the `render_template` function in your Python code:

```python
from template_parsing_engine import render_template

result = render_template(
    template_path="/path/to/template.md",
    variables={
        "string_vars": {"name": "Alice"},
        "file_vars": [{"name": "content", "path": "/path/to/content.txt"}]
    },
    output_mode="full"  # or "body"
)

print(result.content)
print(result.frontmatter)
```

### TypeScript/Node.js

Spawn a process to render templates from Node.js:

```typescript
import { spawn } from "child_process";

async function renderTemplate(request: RenderRequest): Promise<RenderResponse> {
  return new Promise((resolve, reject) => {
    const proc = spawn("uv", ["run", "template-parsing-engine"]);
    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (data) => (stdout += data));
    proc.stderr.on("data", (data) => (stderr += data));
    proc.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr || `Process exited with code ${code}`));
      } else {
        resolve(JSON.parse(stdout));
      }
    });

    proc.stdin.write(JSON.stringify(request));
    proc.stdin.end();
  });
}

// Usage
const result = await renderTemplate({
  template_path: "/path/to/template.md",
  output_mode: "body",
  variables: {
    string_vars: { name: "Alice" },
  },
});
```

## Template Format

Templates use markdown with optional YAML frontmatter:

```markdown
---
description: My agent template
mode: primary
---

# {{ title }}

Content here can use {{ variables }} and Jinja2 includes:

{% include "./partial.md" %}
```

## API Reference

### Input Schema

Configure the engine with this JSON structure:

```json
{
  "template_path": "/path/to/template.md",
  "output_mode": "full" | "body",
  "variables": {
    "string_vars": {"key": "value"},
    "file_vars": [{"name": "var_name", "path": "/path/to/file"}]
  },
  "search_paths": ["/optional/custom/search/path"]
}
```

### Output Schema

The engine returns results in these formats:

**Success:**

```json
{
  "ok": true,
  "result": {
    "content": "rendered content",
    "frontmatter": { "description": "...", "mode": "primary" }
  }
}
```

**Error:**

```json
{
  "ok": false,
  "error": "error message",
  "error_type": "MissingVariablesError"
}
```

## Environment Variables

- `PROMPTS_DIR`: Set the default directory for template resolution (default: `/home/dzack/ai/prompts`).

## License

MIT
