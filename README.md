# MarkItDesk

MarkItDesk is a local-first GUI for converting files, folders, ZIPs, and supported URLs into Markdown using MarkItDown. It adds queueing, preview, quality checks, recipes, and RAG-oriented exports on top of the converter.

## What it does

- Converts supported local files to Markdown
- Processes folders and ZIP archives in bulk
- Shows a Markdown preview
- Saves conversion history in SQLite
- Exports Markdown and RAG-ready outputs
- Applies local security checks before file access and conversion

## What it does not do

- It does not upload documents to the cloud by default
- It does not run AI enrichment by default
- It does not enable plugins by default
- It does not guarantee support for every proprietary format
- It does not replace a document editor

## Install

MarkItDesk requires **Python 3.11+**.

Create and activate a virtual environment, then install the project:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

On macOS or Linux:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Run

Start the app with:

```bash
python -m markitdesk.app
```

Then open `http://localhost:8080`.

You can also use the helper scripts:

```powershell
.\scripts\run_dev.ps1
```

```sh
./scripts/run_dev.sh
```

Default local paths:

- Workspace: `./workspace`
- Output: `./output`
- SQLite database: `./markitdesk.db`

## Convert files

1. Add a supported file from the workspace.
2. Start a conversion.
3. Review the Markdown preview and any quality warnings.
4. Export the result if needed.

Supported inputs depend on the installed MarkItDown backend and the app settings. Local files are restricted to the configured workspace.

## Bulk convert folder

1. Select a folder inside the workspace.
2. Enqueue the folder for bulk processing.
3. The queue processes files one by one.
4. Failed jobs remain in history and can be retried.

Bulk conversion supports supported files under the selected folder and can recurse into subfolders when enabled by the chosen workflow or recipe.

## Export RAG pack

Use a recipe that includes RAG exports, such as **RAG Pack** or **Tender/RFP Pack**.

Typical outputs include:

- Markdown ZIP archives
- Chunked JSONL output
- CSV index files

Exported files are written to the configured output folder.

## Troubleshooting

- If the app will not start, confirm you are using Python 3.11+ and the virtual environment is active.
- If files are not visible, confirm they are inside the configured workspace.
- If a conversion fails, check the queue entry for the error message and retry the job if appropriate.
- If the output folder is empty, confirm the conversion completed and the export action was run.
- If PowerShell blocks script activation, adjust the execution policy for your user account.

## More docs

- [Packaging and local run](docs/packaging.md)
- [User guide](docs/user-guide.md)
- [Security guide](docs/security-user-guide.md)
