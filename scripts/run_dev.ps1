$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$python = if (Test-Path $venvPython) { $venvPython } else { 'python' }

$workspaceRoot = Join-Path $repoRoot 'workspace'
$outputRoot = Join-Path $repoRoot 'output'

New-Item -ItemType Directory -Force -Path $workspaceRoot, $outputRoot | Out-Null

if (-not $env:WORKSPACE_ROOT) { $env:WORKSPACE_ROOT = $workspaceRoot }
if (-not $env:OUTPUT_ROOT) { $env:OUTPUT_ROOT = $outputRoot }

& $python -m markitdesk.app
