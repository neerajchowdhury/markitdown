# AGENTS.md

## Vision
MarkItDesk converts files/folders/ZIPs/URLs into Markdown using MarkItDown, then adds bulk queueing, preview, quality checks, RAG-ready exports, recipes, local security controls, and audit logs.

## Stack
Python 3.11+, NiceGUI, MarkItDown, SQLite, pathlib, pydantic-settings or equivalent, pytest.

## Security Rules
- Local-first by default.
- No cloud upload unless explicitly enabled later.
- Never execute input documents.
- Disable plugins by default.
- Restrict file access to configured workspace folders.
- Defend against path traversal, symlink escape, zip bombs, oversized files, unsupported types, and unsafe output overwrites.
- Keep raw conversion output separate from AI/enriched output.

## Coding Standards
- Prefer small modules over large files.
- Every code change must include or update tests where practical.
- Do not rewrite unrelated files.
- Do not introduce large frameworks unless justified in docs/decisions.md.
- Avoid broad repo scans. Read only files relevant to the task.

## Testing Rules
- Write tests for new functionality.
- Update tests when modifying existing code.
- Run tests before considering a task complete.
- Use pytest as the testing framework.

## Token Discipline
- Before editing, list the exact files you need to inspect.
- Inspect only those files.
- Return a compact summary: files changed, tests run, risks, next task.
- Do not paste full file contents unless necessary.
- Do not regenerate unchanged code.

## Definition of Done
- Code is written and tested.
- Tests pass.
- Changes are minimal and focused.
- Security rules are followed.
- Documentation is updated if necessary.
- No unrelated files are modified.