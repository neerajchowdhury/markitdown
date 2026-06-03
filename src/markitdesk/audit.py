"""Audit logging for MarkItDesk."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from .database import get_connection
from .config import settings as default_settings


def init_audit_table(db_path: Path) -> None:
    """Initialize the audit table in the database."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                level TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                source_path TEXT,
                job_id INTEGER,
                metadata TEXT,  -- JSON string
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Create indexes for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_logs_job_id ON audit_logs(job_id)
        """)
        conn.commit()


def log_audit_event(
    level: str,
    event_type: str,
    message: str,
    source_path: Optional[Path] = None,
    job_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """
    Log an audit event.
    
    Args:
        level: Log level (debug, info, warning, error)
        event_type: Type of audit event (from predefined list)
        message: Human-readable message
        source_path: Optional source file path
        job_id: Optional job ID
        metadata: Optional metadata as dictionary (will be JSON serialized)
        
    Returns:
        ID of the created audit log entry
    """
    from .config import settings
    db_path = settings.workspace_root.parent / "markitdesk.db"
    
    # Convert source_path to string if provided
    source_path_str = str(source_path) if source_path else None
    
    # Serialize metadata to JSON if provided
    metadata_json = json.dumps(metadata) if metadata else None
    
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_logs 
            (timestamp, level, event_type, message, source_path, job_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.utcnow(),
            level,
            event_type,
            message,
            source_path_str,
            job_id,
            metadata_json
        ))
        conn.commit()
        return cursor.lastrowid


def get_audit_events(
    limit: int = 100,
    offset: int = 0,
    event_type: Optional[str] = None,
    level: Optional[str] = None,
    job_id: Optional[int] = None
) -> list:
    """
    Retrieve audit events with optional filtering.
    
    Args:
        limit: Maximum number of events to return
        offset: Number of events to skip
        event_type: Filter by event type
        level: Filter by level
        job_id: Filter by job ID
        
    Returns:
        List of audit event dictionaries
    """
    from .config import settings
    db_path = settings.workspace_root.parent / "markitdesk.db"
    
    # Build query dynamically based on filters
    query = "SELECT id, timestamp, level, event_type, message, source_path, job_id, metadata FROM audit_logs"
    params = []
    
    conditions = []
    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)
    if level:
        conditions.append("level = ?")
        params.append(level)
    if job_id is not None:
        conditions.append("job_id = ?")
        params.append(job_id)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY timestamp ASC, id ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Convert rows to dictionaries
        events = []
        for row in rows:
            event = {
                'id': row[0],
                'timestamp': row[1],
                'level': row[2],
                'event_type': row[3],
                'message': row[4],
                'source_path': row[5],
                'job_id': row[6],
                'metadata': json.loads(row[7]) if row[7] else None
            }
            events.append(event)
        
        return events
