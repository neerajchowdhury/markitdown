"""SQLite database for MarkItDesk persistence."""

import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Any


JOB_STATUS_PENDING = "pending"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_CANCELLED = "cancelled"

JOB_STATUS_ALIASES = {
    "running": JOB_STATUS_PROCESSING,
}

JOB_STATUS_TRANSITIONS = {
    JOB_STATUS_PENDING: {JOB_STATUS_PROCESSING, JOB_STATUS_FAILED, JOB_STATUS_CANCELLED},
    JOB_STATUS_PROCESSING: {JOB_STATUS_COMPLETED, JOB_STATUS_FAILED, JOB_STATUS_CANCELLED},
    JOB_STATUS_COMPLETED: set(),
    JOB_STATUS_FAILED: set(),
    JOB_STATUS_CANCELLED: set(),
}


def normalize_job_status(status: Optional[str]) -> Optional[str]:
    """Map legacy or alternate status names to the canonical queue status."""
    if status is None:
        return None
    return JOB_STATUS_ALIASES.get(status, status)


def is_valid_job_transition(current_status: Optional[str], new_status: str) -> bool:
    """Return whether a status transition is allowed."""
    current = normalize_job_status(current_status)
    next_status = normalize_job_status(new_status)
    if current is None:
        return next_status == JOB_STATUS_PENDING
    if current == next_status:
        return True
    return next_status in JOB_STATUS_TRANSITIONS.get(current, set())


@contextmanager
def get_connection(db_path: Path):
    """
    Get a connection to the SQLite database.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        SQLite connection object
    """
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    try:
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row  # Enable column access by name
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    """
    Initialize the database with required tables.
    
    Args:
        db_path: Path to the SQLite database file
    """
    with get_connection(db_path) as conn:
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        
        # Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                workspace_root TEXT NOT NULL,
                output_root TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                source_path TEXT NOT NULL,
                file_type TEXT,
                size_bytes INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )
        """)
        
        # Jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                error_message TEXT,
                recipe_name TEXT,  -- Recipe used for this job
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES files (id)
            )
        """)
        
        # Outputs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                output_path TEXT NOT NULL,
                output_type TEXT DEFAULT 'markdown',
                text_length INTEGER,
                quality_score INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES files (id)
            )
        """)
        
        # Logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_project_id ON files(project_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_file_id ON jobs(file_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_outputs_file_id ON outputs(file_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_job_id ON logs(job_id)
        """)
        
        conn.commit()


def register_file_and_create_job(db_path: Path, project_id: int, source_path: str,
                                 recipe_name: Optional[str] = None,
                                 file_type: Optional[str] = None,
                                 size_bytes: Optional[int] = None) -> Tuple[int, int]:
    """
    Register a file and create its job in a single transaction.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO files (project_id, source_path, file_type, size_bytes)
            VALUES (?, ?, ?, ?)
        """, (project_id, source_path, file_type, size_bytes))
        file_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO jobs (file_id, status, recipe_name)
            VALUES (?, ?, ?)
        """, (file_id, JOB_STATUS_PENDING, recipe_name))
        job_id = cursor.lastrowid
        conn.commit()
        return file_id, job_id


def register_files_and_create_jobs(
    db_path: Path,
    project_id: int,
    file_records: List[Tuple[str, Optional[str], Optional[int]]],
    recipe_name: Optional[str] = None,
) -> List[Tuple[int, int]]:
    """
    Register multiple files and jobs in a single transaction.

    Args:
        db_path: Path to the SQLite database file
        project_id: Project ID for all files
        file_records: Tuples of (source_path, file_type, size_bytes)
        recipe_name: Optional recipe name to store on each job

    Returns:
        List of (file_id, job_id) tuples in the same order as file_records.
    """
    registrations: List[Tuple[int, int]] = []
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for source_path, file_type, size_bytes in file_records:
            cursor.execute("""
                INSERT INTO files (project_id, source_path, file_type, size_bytes)
                VALUES (?, ?, ?, ?)
            """, (project_id, source_path, file_type, size_bytes))
            file_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO jobs (file_id, status, recipe_name)
                VALUES (?, ?, ?)
            """, (file_id, JOB_STATUS_PENDING, recipe_name))
            job_id = cursor.lastrowid
            registrations.append((file_id, job_id))
        conn.commit()
        return registrations


def create_project(db_path: Path, name: str, workspace_root: str, output_root: str) -> int:
    """
    Create a new project.
    
    Args:
        db_path: Path to the SQLite database file
        name: Project name
        workspace_root: Workspace root path
        output_root: Output root path
        
    Returns:
        ID of the created project
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO projects (name, workspace_root, output_root)
            VALUES (?, ?, ?)
        """, (name, workspace_root, output_root))
        conn.commit()
        return cursor.lastrowid


def register_file(db_path: Path, project_id: int, source_path: str, 
                  file_type: Optional[str] = None, size_bytes: Optional[int] = None) -> int:
    """
    Register a file for processing.
    
    Args:
        db_path: Path to the SQLite database file
        project_id: ID of the project this file belongs to
        source_path: Path to the source file
        file_type: Type/extension of the file
        size_bytes: Size of the file in bytes
        
    Returns:
        ID of the registered file
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO files (project_id, source_path, file_type, size_bytes)
            VALUES (?, ?, ?, ?)
        """, (project_id, source_path, file_type, size_bytes))
        conn.commit()
        return cursor.lastrowid


def create_job(db_path: Path, file_id: int, recipe_name: Optional[str] = None) -> int:
    """
    Create a new job for a file.
    
    Args:
        db_path: Path to the SQLite database file
        file_id: ID of the file to process
        recipe_name: Optional name of the recipe used for this job
        
    Returns:
        ID of the created job
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO jobs (file_id, status, recipe_name)
            VALUES (?, 'pending', ?)
        """, (file_id, recipe_name))
        conn.commit()
        return cursor.lastrowid


def update_job_status(db_path: Path, job_id: int, status: str, 
                      error_message: Optional[str] = None) -> None:
    """
    Update the status of a job.
    
    Args:
        db_path: Path to the SQLite database file
        job_id: ID of the job to update
        status: New status (pending, processing, completed, failed)
        error_message: Error message if status is failed
    """
    normalized_status = normalize_job_status(status)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, started_at, finished_at FROM jobs WHERE id = ?", (job_id,))
        current_row = cursor.fetchone()
        if current_row is None:
            raise ValueError(f"Job {job_id} does not exist")

        current_status = normalize_job_status(current_row["status"])
        if not is_valid_job_transition(current_status, normalized_status):
            raise ValueError(f"Invalid job status transition: {current_status} -> {normalized_status}")

        now = datetime.utcnow()

        if normalized_status == JOB_STATUS_PROCESSING:
            cursor.execute("""
                UPDATE jobs 
                SET status = ?,
                    started_at = COALESCE(started_at, ?),
                    finished_at = NULL,
                    error_message = NULL
                WHERE id = ?
            """, (normalized_status, now, job_id))
        elif normalized_status in (JOB_STATUS_COMPLETED, JOB_STATUS_FAILED, JOB_STATUS_CANCELLED):
            cursor.execute("""
                UPDATE jobs 
                SET status = ?, finished_at = ?, error_message = ?
                WHERE id = ?
            """, (normalized_status, now, error_message if normalized_status == JOB_STATUS_FAILED else None, job_id))
        else:
            cursor.execute("""
                UPDATE jobs 
                SET status = ?
                WHERE id = ?
            """, (normalized_status, job_id))
        
        conn.commit()


def add_output(db_path: Path, file_id: int, output_path: str, 
               output_type: str = 'markdown', text_length: int = 0, quality_score: int = 0) -> int:
    """
    Add an output record for a converted file.
    
    Args:
        db_path: Path to the SQLite database file
        file_id: ID of the file this output is for
        output_path: Path to the output file
        output_type: Type of output (default: markdown)
        text_length: Length of the output text in characters
        quality_score: Quality score of the output (0-100)
        
    Returns:
        ID of the created output record
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO outputs (file_id, output_path, output_type, text_length, quality_score)
            VALUES (?, ?, ?, ?, ?)
        """, (file_id, output_path, output_type, text_length, quality_score))
        conn.commit()
        return cursor.lastrowid


def add_log(db_path: Path, level: str, message: str, 
            job_id: Optional[int] = None) -> int:
    """
    Add a log entry.
    
    Args:
        db_path: Path to the SQLite database file
        level: Log level (debug, info, warning, error)
        message: Log message
        job_id: Optional ID of the job this log is associated with
        
    Returns:
        ID of the created log entry
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO logs (job_id, level, message)
            VALUES (?, ?, ?)
        """, (job_id, level, message))
        conn.commit()
        return cursor.lastrowid


def list_recent_jobs(db_path: Path, limit: int = 100) -> List[Tuple[Any, ...]]:
    """
    List recent jobs with their associated file and project information.
    
    Args:
        db_path: Path to the SQLite database file
        limit: Maximum number of jobs to return
        
    Returns:
        List of tuples containing job information
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                j.id as job_id,
                j.status,
                j.started_at,
                j.finished_at,
                j.error_message,
                f.id as file_id,
                f.source_path,
                f.file_type,
                p.id as project_id,
                p.name as project_name,
                o.id as output_id,
                o.output_path,
                o.output_type,
                o.text_length,
                o.quality_score
            FROM jobs j
            JOIN files f ON j.file_id = f.id
            JOIN projects p ON f.project_id = p.id
            LEFT JOIN outputs o ON o.id = (
                SELECT o2.id
                FROM outputs o2
                WHERE o2.file_id = f.id
                ORDER BY o2.created_at DESC, o2.id DESC
                LIMIT 1
            )
            ORDER BY j.created_at DESC, j.id DESC
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()


def get_job_by_id(db_path: Path, job_id: int):
    """Fetch a job with its associated file, project, and latest output information."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                j.id as job_id,
                j.status,
                j.started_at,
                j.finished_at,
                j.error_message,
                j.recipe_name,
                j.created_at,
                f.id as file_id,
                f.source_path,
                f.file_type,
                f.project_id,
                p.name as project_name,
                o.id as output_id,
                o.output_path,
                o.output_type,
                o.text_length,
                o.quality_score
            FROM jobs j
            JOIN files f ON j.file_id = f.id
            JOIN projects p ON f.project_id = p.id
            LEFT JOIN outputs o ON o.id = (
                SELECT o2.id
                FROM outputs o2
                WHERE o2.file_id = f.id
                ORDER BY o2.created_at DESC, o2.id DESC
                LIMIT 1
            )
            WHERE j.id = ?
        """, (job_id,))
        return cursor.fetchone()


# For backward compatibility with the architecture document's table plan
# Note: The actual implementation uses slightly different column names/types
# based on practical considerations, but maintains the same conceptual structure
