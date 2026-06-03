# Architecture Documentation

## Module Map: src/markitdesk
```
src/markitdesk/
├── __init__.py
├── main.py              # Application entry point
├── gui/                 # NiceGUI interface components
│   ├── __init__.py
│   ├── main_window.py   # Main application window
│   ├── file_selector.py # File/folder/ZIP/URL input
│   ├── job_queue_view.py# Queue display and controls
│   ├── preview.py       # Markdown preview pane
│   └── settings.py      # Configuration dialog
├── core/                # Business logic
│   ├── __init__.py
│   ├── converter.py     # MarkItDown wrapper
│   ├── job_queue.py     # Job management and scheduling
│   ├── validator.py     # Input validation and security checks
│   ├── quality_checker.py# Output validation
│   └── exporter.py      # File output handling
├── storage/             # Data persistence
│   ├── __init__.py
│   ├── database.py      # SQLite connection and schema
│   ├── models.py        # Data models (Project, File, Job, etc.)
│   └── repository.py    # Data access layer
└── utils/               # Helper functions
    ├── __init__.py
    ├── security.py      # Path traversal, symlink checks
    ├── logging.py       # Application logging
    └── config.py        # Settings management
```

## Data Flow
1. **Input**: User selects files/folders/ZIPs/URLs via GUI
2. **Validation**: Security checks (path traversal, symlinks, size/type limits)
3. **Job Queue**: Validated items added to processing queue with priority
4. **Conversion**: MarkItDown processes each item in worker thread
5. **Quality Check**: Output validated for size, format, content issues
6. **Export**: Converted Markdown saved to output directory
7. **Preview**: Generated Markdown displayed in GUI preview pane
8. **Logging**: All steps recorded in SQLite database for audit trail

## SQLite Table Plan
- **projects**: id, name, created_at, updated_at, settings_json
- **files**: id, project_id, original_path, file_type, size, hash, imported_at
- **jobs**: id, file_id, status, priority, created_at, started_at, completed_at, error_message
- **outputs**: id, job_id, output_path, markdown_size, chunk_count, exported_at
- **logs**: id, job_id, level, message, timestamp
- **presets**: id, name, description, settings_json, created_at, updated_at
- **chunks**: id, output_id, chunk_index, content, token_count, embedding_vector (nullable)

## Error Handling Strategy
- **Validation Errors**: Prevent job creation, show user-friendly messages in GUI
- **Conversion Errors**: Mark job as failed, store error details, continue queue processing
- **Export Errors**: Retry mechanism with exponential backoff, fallback to temp location
- **System Errors**: Crash reporting to local log file, graceful shutdown preservation of queue state
- **User Recovery**: Failed jobs can be retried individually or in batch from GUI