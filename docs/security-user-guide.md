# Security User Guide

MarkItDesk is designed to keep documents local and under user control.

## Local-first model

By default, files stay on disk in the configured workspace and output folders. The app does not upload documents to a cloud service unless you later change the configuration or add new functionality.

## Why plugins are off by default

Plugins expand the attack surface. Keeping them disabled by default reduces the chance that a document or conversion workflow can trigger unexpected code paths.

## Why remote URLs are off by default

Remote URLs require network access and weaken the local-first model. They are disabled by default so users do not accidentally fetch external content while processing sensitive documents.

## Safe workspace/output folders

The app restricts file access to configured local folders:

- Workspace: input files that can be processed
- Output: generated Markdown and exports

Keep both paths on local storage. Do not point them at shared folders you do not control.

## Handling sensitive documents

- Keep sensitive source files inside the workspace
- Review preview output before exporting
- Delete temporary or unwanted exports when finished
- Avoid enabling optional features unless you need them

## Known limitations

- Security checks reduce risk, but they do not make untrusted documents safe to execute
- Unsupported formats may still fail during conversion
- ZIP limits reduce archive abuse, but very large archives can still take time to process
- Local controls cannot protect data once you copy it elsewhere
