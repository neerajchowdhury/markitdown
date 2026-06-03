# Packaging and Local Run

MarkItDesk targets **Python 3.11+**.

## Virtual environment

Create and activate a virtual environment before installing dependencies.

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS or Linux:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
```

## Install

Install the project into the active environment:

```bash
python -m pip install -e .
```

For local testing:

```bash
python -m pip install -e .[dev]
```

## Run

Start the app with either command:

```bash
python -m markitdesk.app
```

or:

```powershell
.\scripts\run_dev.ps1
```

```sh
./scripts/run_dev.sh
```

## Default storage

Unless overridden by environment variables, the app uses local paths only:

- Workspace: `./workspace`
- Output: `./output`
- SQLite database: `./markitdesk.db`

The database file is created next to the workspace root, which keeps the default state inside the project tree.

## Security defaults

The default configuration is local-first:

- No cloud upload
- Remote URLs remain disabled
- Plugins stay disabled
- Workspace file access is restricted
- Path traversal, symlink escape, and unsafe overwrite checks stay enabled

## Troubleshooting

- If `markitdesk.app` is not found, verify the virtual environment is activated and the project was installed with `pip install -e .`.
- If PowerShell blocks `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once for the current user.
- If the app cannot create `workspace`, `output`, or the SQLite database, confirm you have write access to the repository directory.
- If you changed `WORKSPACE_ROOT` or `OUTPUT_ROOT`, make sure both point to local directories that exist or can be created.
