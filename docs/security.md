# Security Policy

## Local-First Policy
- All processing occurs on the local machine by default.
- No data is transmitted to external servers without explicit user consent.
- Cloud features (if added in V2) will be opt-in and clearly indicated.

## Workspace Sandboxing
- Users must configure one or more workspace folders where the application can read/write.
- File operations are restricted to these configured workspaces.
- Attempts to access paths outside the workspace are blocked and logged.

## Path Traversal Defense
- All input paths are normalized and checked for `..` or absolute paths that escape the workspace.
- Use of `os.path.normpath` and verification that the resolved path starts with the workspace root.
- Reject any path that contains symbolic links pointing outside the workspace (see Symlink Handling).

## Symlink Handling
- Symbolic links are resolved and checked against workspace boundaries.
- If a symlink points outside the workspace, the file is rejected and the event is logged.
- Optionally, users may be warned about symlinks within the workspace (configurable).

## ZIP Bomb Defense
- Limit the decompression ratio for ZIP files (e.g., max 10:1 compressed to uncompressed size).
- Set a maximum absolute size for extracted content (e.g., 100MB).
- Abort extraction and notify the user if limits are exceeded.

## File Size/Type Limits
- Configurable maximum file size for individual files (default: 100MB).
- Maintain a list of allowed file types (based on MarkItDown support) and block others.
- Log attempts to process oversized or disallowed file types.

## Secret Scanning Placeholder
- Future versions may include optional scanning for common secrets (API keys, passwords) in converted Markdown.
- This feature will be off by default and configurable.
- Any detected secrets will be highlighted in the preview but not altered in the output.

## Plugin/OCR/AI Safety Boundaries
- Plugins (if enabled) run in a restricted environment with no access to the filesystem outside the workspace.
- OCR and AI features (if added) will process data only in memory and not store results beyond the session unless explicitly saved by the user.
- All external processors (OCR/AI) are subject to the same file size and type limits as regular files.
- Users must explicitly enable plugins, OCR, or AI features, and are presented with clear warnings about data leaving the local environment (if applicable to the plugin).