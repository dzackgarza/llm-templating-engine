# Template Parsing Engine - Design Document

## Overview

Extract the templating engine from `~/ai/scripts/llm/templates.py` into a standalone uv package that provides:

- Python module + CLI for template rendering
- JSON I/O contract for TypeScript/Node.js integration
- Support for Jinja2 templating with YAML frontmatter
- File-based and string-based variable substitution
- Flexible output modes (full markdown or body-only)

## Extraction Scope

### Source (from ~/ai/scripts/llm/)

1. **templates.py** - Core extraction target:
   - `MicroAgent` dataclass
   - `load_micro_agent()` - parses YAML frontmatter + body
   - `render_body()` - Jinja2 rendering with environment
   - `_split_frontmatter()` - handles both `---\n` and legacy formats
   - `PromptTemplateLoader` - custom Jinja2 loader
   - `PromptTemplateEnvironment` - Jinja2 environment with path resolution
   - `MissingVariablesError`, `TemplateFormatError` - exceptions
   - `default_prompts_dir()`, `resolve_prompt_path()` - path resolution

2. **schemas.py** - Optional inclusion:
   - `SCHEMAS` registry for output validation
   - `resolve_schema()` for schema lookup
   - `make_schema_from_dict()` for inline schema definitions
   - Can be kept separate or integrated as optional feature

3. **bridge.py** - Reference for I/O contract:
   - JSON request/response format
   - Action dispatch pattern
   - Error handling approach

## Package Structure

```
template-parsing-engine/
├── src/
│   └── template_parsing_engine/
│       ├── __init__.py          # Public API
│       ├── core.py              # Core templating logic (extracted from templates.py)
│       ├── cli.py               # CLI entry point with JSON I/O
│       └── types.py             # TypeScript-compatible type definitions
├── tests/
│   ├── test_core.py             # Core functionality tests
│   ├── test_cli.py              # CLI integration tests
│   └── fixtures/                # Test templates
│       ├── basic.md
│       ├── with_includes.md
│       └── with_variables.md
├── template_parsing_engine.pyi  # TypeScript type stubs (for Python consumers)
├── pyproject.toml               # uv package config
├── README.md                    # Usage documentation
└── DESIGN.md                    # This file
```

## Input/Output Contract

### Input Schema (JSON)

```json
{
  "template_path": "/path/to/template.md",
  "output_mode": "full" | "body",  // default: "full"
  "variables": {
    "string_vars": {
      "var_name": "value"
    },
    "file_vars": [
      {"name": "file_content", "path": "/path/to/file.txt"}
    ]
  },
  "search_paths": ["/optional/custom/search/path"]
}
```

### Output Schema (JSON)

**Success:**

```json
{
  "ok": true,
  "result": {
    "content": "rendered markdown content",
    "frontmatter": {
      "description": "...",
      "mode": "primary"
      // ... other frontmatter keys
    }
  }
}
```

**Error:**

```json
{
  "ok": false,
  "error": "error message",
  "error_type": "MissingVariablesError" | "TemplateFormatError" | "TemplateNotFound" | "FileNotFoundError"
}
```

### CLI Interface

```bash
# Read from stdin, write to stdout
echo '{"template_path": "/path/to/template.md", ...}' | uv run template-parsing-engine

# File-based input/output
uv run template-parsing-engine --input request.json --output result.json

# Direct template rendering with inline variables
uv run template-parsing-engine \
  --template /path/to/template.md \
  --var-string name="value" \
  --var-file content=/path/to/content.txt \
  --output-mode body
```

## Key Design Decisions

### 1. Variable Substitution

**File Variables (`file_vars`):**

- Read entire file as string content
- Variable name maps to file content in template
- Supports relative paths resolved against template directory
- Example: `{"name": "readme", "path": "./README.md"}` → `{{ readme }}` in template

**String Variables (`string_vars`):**

- Direct key-value mapping
- Example: `{"name": "Alice"}` → `{{ name }}` in template

**Combined Resolution:**

- File vars loaded first, then string vars (string vars can override)
- Both available in Jinja2 rendering context

### 2. Frontmatter Handling

**Input Templates Support:**

- Standard YAML frontmatter: `---\nkey: value\n---\n`
- Legacy format: `key: value\n---\n`
- Access via `{{ frontmatter.key }}` in templates

**Output Modes:**

- `"full"`: Returns rendered content with reconstructed YAML frontmatter
- `"body"`: Returns only the rendered body (after frontmatter separator)

### 3. Include/Import Resolution

**Jinja2 Support:**

- `{% include "./relative/path.md" %}`
- `{% import "./macros.md" as macros %}`
- Relative paths resolved against template's parent directory
- Absolute paths resolved against `search_paths`

**Search Path Priority:**

1. Template's parent directory (highest)
2. `search_paths` from input (in order)
3. `PROMPTS_DIR` environment variable (lowest, if set)

### 4. Error Handling

**Exception Types:**

- `MissingVariablesError`: Required template variables not provided
- `TemplateFormatError`: Invalid YAML frontmatter or structure
- `TemplateNotFoundError`: Included/imported template not found
- `FileNotFoundError`: File variable path doesn't exist

**CLI Behavior:**

- All errors return JSON with `ok: false`
- Non-zero exit code on error
- stderr for logging (optional `--verbose` flag)

### 5. TypeScript Integration

**JSON Bridge:**

- TypeScript can spawn Python subprocess
- Send JSON request via stdin
- Receive JSON response via stdout

**Type Definitions (template_parsing_engine.d.ts):**

```typescript
export interface RenderRequest {
  template_path: string;
  output_mode?: "full" | "body";
  variables?: {
    string_vars?: Record<string, string>;
    file_vars?: Array<{ name: string; path: string }>;
  };
  search_paths?: string[];
}

export interface RenderResponse {
  ok: boolean;
  result?: {
    content: string;
    frontmatter: Record<string, any>;
  };
  error?: string;
  error_type?: string;
}
```

## Implementation Phases

### Phase 1: Core Extraction

1. Copy templating logic from `templates.py`
2. Create `src/template_parsing_engine/core.py`
3. Maintain backward-compatible API
4. Add comprehensive tests

### Phase 2: CLI Development

1. Create `src/template_parsing_engine/cli.py`
2. Implement JSON I/O handling
3. Add argument parsing for direct use
4. Test CLI with various input modes

### Phase 3: Type Definitions

1. Create TypeScript type definitions
2. Add usage examples in README
3. Document JSON bridge pattern

### Phase 4: Integration

1. Update `~/ai/scripts/llm` to use new package
2. Add package as dependency
3. Test existing workflows still work
4. Document migration path

## Usage Examples

### Python Module

```python
from template_parsing_engine import render_template

result = render_template(
    template_path="/path/to/template.md",
    variables={
        "string_vars": {"name": "Alice"},
        "file_vars": [{"name": "content", "path": "/path/to/content.txt"}]
    },
    output_mode="full"
)
print(result.content)
print(result.frontmatter)
```

### CLI (JSON Mode)

```bash
# Prepare request
cat > request.json << 'EOF'
{
  "template_path": "/home/user/prompts/agent.md",
  "output_mode": "body",
  "variables": {
    "string_vars": {"model": "gpt-4"},
    "file_vars": [{"name": "context", "path": "./context.txt"}]
  }
}
EOF

# Execute
uv run template-parsing-engine < request.json > result.json

# Check result
cat result.json | jq '.result.content'
```

### TypeScript/Node.js

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
```

## Dependencies

**Core:**

- `jinja2` - Template engine
- `pyyaml` - YAML frontmatter parsing
- `pydantic` - Input validation (optional but recommended)

**Development:**

- `pytest` - Testing
- `mypy` - Type checking

## Environment Variables

- `PROMPTS_DIR` - Default directory for template resolution (optional)
- `TEMPLATE_SEARCH_PATHS` - Colon-separated default search paths (optional)

## Migration Notes

### From ~/ai/scripts/llm

**Old code:**

```python
from scripts.llm.templates import load_micro_agent, render_body

agent = load_micro_agent("path/to/template.md")
rendered = agent.render(**variables)
```

**New code:**

```python
from template_parsing_engine import render_template

result = render_template(
    template_path="path/to/template.md",
    variables={"string_vars": variables},
    output_mode="body"
)
rendered = result.content
```

## Testing Strategy

1. **Unit tests** for core functions
2. **Integration tests** for CLI
3. **Cross-language tests** verify Python output matches TypeScript expectations
4. **Migration tests** ensure backward compatibility
