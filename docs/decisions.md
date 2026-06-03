# Technical Decisions

## MVP Choices

### NiceGUI for the GUI
- **Why**: Provides a modern, Python-native web-based UI with minimal setup, ideal for rapid prototyping and local-first applications.
- **Alternatives Considered**: PyQt, Tkinter, Electron (with Python backend). Rejected due to either complexity (PyQt), outdated look (Tkinter), or excessive resource usage (Electron).
- **Trade-offs**: Less mature than PyQt but sufficient for MVP; allows easy iteration and deployment as a single executable or via pip.

### SQLite for Storage
- **Why**: Lightweight, zero-configuration, file-based database that fits the local-first philosophy and requires no separate server.
- **Alternatives Considered**: PostgreSQL (overkill for single-user app), TinyDB (less featured), JSON files (not scalable for querying).
- **Trade-offs**: Limited concurrent write handling (not an issue for single-user desktop app); excellent read performance and simplicity.

### Local Workers for Conversion
- **Why**: MarkItDown is a Python library; running conversion in local worker threads/processes keeps data on the machine and avoids latency.
- **Alternatives Considered**: Offloading to a cloud service (violates local-first), using asyncio directly (CPU-bound tasks block event loop).
- **Trade-offs**: Added complexity of managing workers/processes; mitigated by using Python's `concurrent.futures` or similar.

## Deferred Choices

### Tauri for Desktop Packaging
- **Why Deferred**: NiceGUI can be packaged with tools like PyInstaller or Briefcase for now; Tauri adds Rust build complexity not needed for MVP.
- **Condition for Adoption**: If we need significantly smaller binaries, better system integration, or plan to expand to mobile/web in V2.

### FastAPI for Backend/Services
- **Why Deferred**: The MVP is a single-user desktop app; a separate backend service adds unnecessary complexity.
- **Condition for Adoption**: If we introduce multi-user features, cloud sync, or need to expose APIs for plugins in V2.

### Cloud Sync (e.g., Dropbox, Google Drive)
- **Why Deferred**: Violates the local-first principle unless explicitly enabled by the user; adds significant complexity in authentication and conflict resolution.
- **Condition for Adoption**: As an opt-in feature in V2 with clear UI indicators and user controls.

### User Accounts and Team Permissions
- **Why Deferred**: The target MVP is for individual knowledge workers; team features are V2 considerations.
- **Condition for Adoption**: If we expand to collaborative environments with role-based access control and shared workspaces.

### Integrated AI/OCR Features
- **Why Deferred**: To keep the MVP focused and avoid dependency on large models or external services; safety and licensing concerns.
- **Condition for Adoption**: As optional, clearly marked plugins with strict sandboxing in V2, if at all.
