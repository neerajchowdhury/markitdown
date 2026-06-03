"""Export utilities for converted Markdown outputs and chunks."""

import csv
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from .database import get_connection
from .config import Settings
from .audit import log_audit_event


def _resolve_export_path(export_path: Path, output_root: Path) -> Path:
    """
    Resolve an export path inside the configured output root.

    Unlike file validation helpers, exports create a new file, so the final
    path may not exist yet. The containment check therefore applies to the
    resolved candidate path, not the leaf file's existence.
    """
    output_root_resolved = Path(output_root).resolve()
    candidate = Path(export_path)

    if not candidate.is_absolute():
        candidate = output_root_resolved / candidate

    resolved_candidate = candidate.resolve(strict=False)
    try:
        resolved_candidate.relative_to(output_root_resolved)
    except ValueError as exc:
        raise ValueError(f"Export path must be inside output root: {output_root}") from exc

    return resolved_candidate


def get_recent_outputs(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get recent output records from the database.
    
    Args:
        limit: Maximum number of records to return
        
    Returns:
        List of output records with associated file and job information
    """
    from .config import settings
    
    db_path = settings.workspace_root.parent / "markitdesk.db"
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                o.id as output_id,
                o.file_id,
                o.output_path,
                o.output_type,
                o.text_length,
                o.quality_score,
                o.created_at,
                f.source_path,
                f.file_type,
                (
                    SELECT j2.id
                    FROM jobs j2
                    WHERE j2.file_id = f.id
                    ORDER BY j2.created_at DESC, j2.id DESC
                    LIMIT 1
                ) as job_id,
                (
                    SELECT j2.status
                    FROM jobs j2
                    WHERE j2.file_id = f.id
                    ORDER BY j2.created_at DESC, j2.id DESC
                    LIMIT 1
                ) as job_status
            FROM outputs o
            JOIN files f ON o.file_id = f.id
            ORDER BY o.created_at DESC
            LIMIT ?
        """, (limit,))
        
        columns = [description[0] for description in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        
        return results


def export_markdown_zip(output_ids: List[int], export_path: Path, config: Settings) -> Dict[str, Any]:
    """
    Export selected Markdown outputs as a ZIP file with manifest.
    
    Args:
        output_ids: List of output IDs to export
        export_path: Path where ZIP file should be created
        config: Application configuration
        
    Returns:
        Dictionary with success status and message
    """
    try:
        # Get outputs from database
        outputs = get_recent_outputs(limit=1000)
        selected_outputs = [o for o in outputs if o['output_id'] in output_ids]
        
        if not selected_outputs:
            return {"success": False, "message": "No valid outputs found for export"}
        
        # Security check: Ensure export path is inside output root
        try:
            safe_export_path = _resolve_export_path(export_path, config.output_root)
        except ValueError:
            return {"success": False, "message": f"Export path must be inside output root: {config.output_root}"}
        
        # Create export directory if it doesn't exist
        safe_export_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create ZIP file
        with zipfile.ZipFile(safe_export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add each Markdown file
            for output in selected_outputs:
                output_path = Path(output['output_path'])
                if output_path.exists():
                    # Use just the filename for the archive to avoid path issues
                    arcname = output_path.name
                    zipf.write(output_path, arcname)
            
            # Create and add manifest.json
            manifest = {
                "export_info": {
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "total_files": len(selected_outputs),
                    "format": "markdown_zip",
                    "version": "1.0"
                },
                "files": [
                    {
                        "output_id": output['output_id'],
                        "file_id": output['file_id'],
                        "source_path": output['source_path'],
                        "output_path": output['output_path'],
                        "text_length": output['text_length'],
                        "quality_score": output['quality_score'],
                        "created_at": output['created_at'],
                        "job_id": output['job_id'],
                        "job_status": output['job_status']
                    }
                    for output in selected_outputs
                ]
            }
            
            manifest_json = json.dumps(manifest, indent=2)
            zipf.writestr("manifest.json", manifest_json)
        
        # Log export created
        from markitdesk.config import settings
        db_path = settings.workspace_root.parent / "markitdesk.db"
        # Get the first job_id for logging (or None if no outputs)
        job_id = selected_outputs[0]['job_id'] if selected_outputs else None
        
        log_audit_event(
            level="info",
            event_type="export_created",
            message=f"Markdown ZIP export created: {safe_export_path.name} ({len(selected_outputs)} files)",
            source_path=safe_export_path,
            job_id=job_id,
            metadata={
                "export_type": "markdown_zip",
                "file_count": len(selected_outputs),
                "export_path": str(safe_export_path),
                "output_ids": output_ids
            }
        )
        
        return {"success": True, "message": f"Successfully exported {len(selected_outputs)} files to {safe_export_path}"}
     
    except Exception as e:
        # Log export failure
        from markitdesk.config import settings
        db_path = settings.workspace_root.parent / "markitdesk.db"
        
        log_audit_event(
            level="error",
            event_type="export_created",  # Still logging as export_created but will indicate failure in message
            message=f"Failed to create export ZIP: {str(e)}",
            source_path=export_path if 'export_path' in locals() else None,
            metadata={
                "export_type": "markdown_zip",
                "error": str(e),
                "output_ids": output_ids
            }
        )
        
        return {"success": False, "message": f"Failed to create export ZIP: {str(e)}"}


def export_jsonl_chunks(
    output_ids: List[int], 
    export_path: Path, 
    config: Settings
) -> Dict[str, Any]:
    """
    Export selected outputs as JSONL chunks (placeholder implementation).
    
    Args:
        output_ids: List of output IDs to export
        export_path: Path where JSONL file should be created
        config: Application configuration
        
    Returns:
        Dictionary with success status and message
    """
    try:
        # Security check: Ensure export path is inside output root
        try:
            safe_export_path = _resolve_export_path(export_path, config.output_root)
        except ValueError:
            return {"success": False, "message": f"Export path must be inside output root: {config.output_root}"}
        
        # Get outputs from database
        outputs = get_recent_outputs(limit=1000)
        selected_outputs = [o for o in outputs if o['output_id'] in output_ids]
        
        if not selected_outputs:
            return {"success": False, "message": "No valid outputs found for export"}
        
        # Create export directory if it doesn't exist
        safe_export_path.parent.mkdir(parents=True, exist_ok=True)
        
        # For now, create a simple JSONL file with output metadata
        # In a full implementation, this would include actual chunked content
        with open(safe_export_path, 'w', encoding='utf-8') as f:
            for output in selected_outputs:
                chunk_data = {
                    "output_id": output['output_id'],
                    "file_id": output['file_id'],
                    "source_path": output['source_path'],
                    "output_path": output['output_path'],
                    "text_length": output['text_length'],
                    "quality_score": output['quality_score'],
                    "created_at": output['created_at'],
                    "job_id": output['job_id'],
                    "job_status": output['job_status'],
                    "content_preview": "Content chunking not implemented in this version"
                }
                
                f.write(json.dumps(chunk_data) + '\n')
        
        # Log export created
        from markitdesk.config import settings
        db_path = settings.workspace_root.parent / "markitdesk.db"
        # Get the first job_id for logging (or None if no outputs)
        job_id = selected_outputs[0]['job_id'] if selected_outputs else None
        
        log_audit_event(
            level="info",
            event_type="export_created",
            message=f"JSONL chunks export created: {safe_export_path.name} ({len(selected_outputs)} outputs)",
            source_path=safe_export_path,
            job_id=job_id,
            metadata={
                "export_type": "jsonl_chunks",
                "output_count": len(selected_outputs),
                "export_path": str(safe_export_path),
                "output_ids": output_ids
            }
        )
        
        return {"success": True, "message": f"Successfully exported {len(selected_outputs)} outputs as JSONL to {safe_export_path}"}
     
    except Exception as e:
        # Log export failure
        from markitdesk.config import settings
        db_path = settings.workspace_root.parent / "markitdesk.db"
        
        log_audit_event(
            level="error",
            event_type="export_created",
            message=f"Failed to create JSONL export: {str(e)}",
            source_path=export_path if 'export_path' in locals() else None,
            metadata={
                "export_type": "jsonl_chunks",
                "error": str(e),
                "output_ids": output_ids
            }
        )
        
        return {"success": False, "message": f"Failed to create JSONL export: {str(e)}"}


def export_csv_index(
    output_ids: List[int], 
    export_path: Path, 
    config: Settings
) -> Dict[str, Any]:
    """
    Export selected outputs as a CSV index file.
    
    Args:
        output_ids: List of output IDs to export
        export_path: Path where CSV file should be created
        config: Application configuration
        
    Returns:
        Dictionary with success status and message
    """
    try:
        # Security check: Ensure export path is inside output root
        try:
            safe_export_path = _resolve_export_path(export_path, config.output_root)
        except ValueError:
            return {"success": False, "message": f"Export path must be inside output root: {config.output_root}"}
        
        # Get outputs from database
        outputs = get_recent_outputs(limit=1000)
        selected_outputs = [o for o in outputs if o['output_id'] in output_ids]
        
        if not selected_outputs:
            return {"success": False, "message": "No valid outputs found for export"}
        
        # Create export directory if it doesn't exist
        safe_export_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create CSV file
        with open(safe_export_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                'output_id', 'file_id', 'source_path', 'output_path', 
                'text_length', 'quality_score', 'created_at', 'job_id', 'job_status'
            ])
            
            # Write data rows
            for output in selected_outputs:
                writer.writerow([
                    output['output_id'],
                    output['file_id'],
                    output['source_path'] or '',
                    output['output_path'],
                    output['text_length'] or 0,
                    output['quality_score'] or 0,
                    output['created_at'] or '',
                    output['job_id'] or '',
                    output['job_status'] or ''
                ])
        
        # Log export created
        from markitdesk.config import settings
        db_path = settings.workspace_root.parent / "markitdesk.db"
        # Get the first job_id for logging (or None if no outputs)
        job_id = selected_outputs[0]['job_id'] if selected_outputs else None
        
        log_audit_event(
            level="info",
            event_type="export_created",
            message=f"CSV index export created: {safe_export_path.name} ({len(selected_outputs)} outputs)",
            source_path=safe_export_path,
            job_id=job_id,
            metadata={
                "export_type": "csv_index",
                "output_count": len(selected_outputs),
                "export_path": str(safe_export_path),
                "output_ids": output_ids
            }
        )
        
        return {"success": True, "message": f"Successfully exported {len(selected_outputs)} outputs to {safe_export_path}"}
     
    except Exception as e:
        # Log export failure
        from markitdesk.config import settings
        db_path = settings.workspace_root.parent / "markitdesk.db"
        
        log_audit_event(
            level="error",
            event_type="export_created",
            message=f"Failed to create CSV export: {str(e)}",
            source_path=export_path if 'export_path' in locals() else None,
            metadata={
                "export_type": "csv_index",
                "error": str(e),
                "output_ids": output_ids
            }
        )
        
        return {"success": False, "message": f"Failed to create CSV export: {str(e)}"}
