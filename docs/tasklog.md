# Implementation Task Log

## Phase 1: Foundation
- [x] Set up project structure (src/markitdesk, docs, tests)
- [ ] Create basic NiceGUI main window with menu and status bar
- [ ] Implement file/folder selector with workspace restriction
- [x] Set up SQLite database with initial schema (projects, files)
- [x] Create MarkItDown conversion wrapper in core/converter.py
- [x] Add basic validation (file type, size limits) in core/validator.py (implemented in security.py)
- [x] Implement simple job queue (FIFO) in core/job_queue.py (implemented in jobs.py)
- [ ] Add preview pane for Markdown output
- [ ] Implement export to Markdown files
- [x] Log conversion jobs to SQLite

## Phase 2: Core Features
- [ ] Enhance job queue with priority and pause/resume controls
- [ ] Add ZIP file handling with bomb defense (size/ratio limits)
- [ ] Implement URL fetching with timeout and size limits
- [ ] Add quality checking (output size, basic content validation)
- [ ] Create settings dialog for workspace and conversion options
- [ ] Implement audit logging (detailed conversion metrics)
- [ ] Add support for drag-and-drop file input
- [ ] Create basic recipe system (presets for conversion options)
- [ ] Enhance preview with syntax highlighting

## Phase 3: Polish and V2 Preparation
- [ ] Implement comprehensive error handling and user notifications
- [ ] Add batch processing controls (cancel, retry failed jobs)
- [ ] Create export presets (different output directories, naming)
- [ ] Add chunking for RAG-ready exports (optional)
- [ ] Implement plugin framework with security boundaries (disabled by default)
- [ ] Add advanced security features (symlink handling, secret scanning placeholder)
- [ ] Optimize performance (caching, async processing)
- [ ] Write comprehensive user documentation and tooltips
- [ ] Prepare for packaging (PyInstaller/Briefcase scripts)

## Ongoing
- [x] Write unit tests for core components (validator, converter, job queue)
- [ ] Run security audits on new features
- [x] Update documentation as features evolve
- [ ] Collect user feedback for prioritization

## Release Candidate
- Status: passed
- Verified on 2026-06-02 with `99 passed` in the full pytest suite
- Remaining work: non-blocking datetime deprecation warnings only
