[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/I2I57UKJ8)

# LLM Templating Engine

Generic Jinja-based template loading and rendering for prompt documents, snippets, and
macros.

## Setup

```bash
direnv allow
just setup
```

Local configuration lives in `.envrc` and inherits shared shell configuration from
`~/.envrc`:

```bash
source_up
export PROMPTS_DIR="${PROMPTS_DIR:-$PWD/prompts}"
```

## Direct Use

```bash
uvx --from git+https://github.com/dzackgarza/llm-templating-engine.git \
  llm-template-render --help

uvx --from git+https://github.com/dzackgarza/llm-templating-engine.git \
  llm-template-inspect --help

uvx --from git+https://github.com/dzackgarza/llm-templating-engine.git \
  llm-template-validate --help
```

## Commands

- `llm-template-render` renders one JSON request from stdin.
- `llm-template-inspect` parses and returns template structure without rendering.
- `llm-template-validate` reports whether the provided bindings can render a template.

TypeScript and JavaScript callers can use the JSON request and response shapes in
`types.d.ts`.

## Development

- `just setup` installs the project and dev dependencies.
- `just check` runs typecheck, lint, and tests.
- `just build` builds a publication-ready wheel and sdist.
- `just bump` increments the minor version with `uv version --bump minor`.

Full interface and contract details live in `DESIGN.md`.

## License

MIT
