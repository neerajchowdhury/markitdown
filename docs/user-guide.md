# User Guide

This guide covers the basic workflows in MarkItDesk.

## Basic Markdown conversion

1. Start the app.
2. Add a supported file from the workspace.
3. Run conversion.
4. Read the Markdown preview.
5. Export if needed.

The preview shows the converted Markdown content and the queue shows job status.

## Bulk folder workflow

1. Select a folder inside the workspace.
2. Enqueue the folder for bulk conversion.
3. Let the queue process items.
4. Review failed jobs and retry if needed.

Bulk jobs are stored in SQLite, so completed and failed jobs remain visible after restart.

## ZIP workflow

1. Add a ZIP file from the workspace.
2. Confirm ZIP extraction is allowed in the current settings or recipe.
3. Convert the ZIP.
4. Review the queue and preview.

ZIP processing is limited by the configured archive controls, including file count and uncompressed size limits.

## Quality warnings

Quality checks may flag:

- Empty or very short output
- Unsupported or suspicious input
- Oversized files

Treat warnings as a prompt to review the result before exporting.

## Preview

The preview pane shows the Markdown output for the selected item. Use it to spot obvious formatting problems before exporting.

## Recipes

Recipes are saved conversion presets. They can control:

- Allowed file types
- Recursive folder processing
- ZIP extraction
- Quality checks
- Chunking strategy
- Export types

Use a recipe when you want repeatable settings for a specific workflow.

## Export types

Supported export types include:

- Plain Markdown output
- Markdown ZIP bundles
- Chunked JSONL output
- CSV index files

Some exports are intended for RAG-style pipelines. Use the recipe name and export list to choose the right output set.
