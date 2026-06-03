"""Background job queue for bulk file conversion."""

import threading
import time
import sqlite3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Dict, Any
from queue import Queue, Empty

from .config import Settings
from .converter import convert_file
from .database import (
    get_connection, 
    create_job, 
    update_job_status, 
    add_log,
    register_file,
    register_files_and_create_jobs,
    list_recent_jobs,
    get_job_by_id,
    normalize_job_status,
)


JOB_STATUS_PENDING = "pending"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_CANCELLED = "cancelled"


def _safe_add_log(db_path: Path, level: str, message: str, job_id: Optional[int] = None) -> None:
    """Best-effort job logging that never changes the queue outcome."""
    try:
        add_log(db_path, level, message, job_id)
    except Exception:
        pass


class JobQueue:
    """Background job queue for processing file conversions."""
    
    def __init__(self, config: Settings, max_workers: int = 2):
        """
        Initialize the job queue.
        
        Args:
            config: Application configuration
            max_workers: Maximum number of worker threads (default: 2)
        """
        self.config = config
        self.max_workers = max_workers
        self.db_path = self.config.workspace_root.parent / "markitdesk.db"
        self.output_root = self.config.output_root
        self.executor: Optional[ThreadPoolExecutor] = None
        self._shutdown = False
        self._lock = threading.Lock()
        
    def start(self):
        """Start the job queue executor."""
        with self._lock:
            if self.executor is None or self.executor._shutdown:
                self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
                self._shutdown = False
                
    def stop(self, wait: bool = True):
        """Stop the job queue executor."""
        with self._lock:
            if self.executor is not None:
                self.executor.shutdown(wait=wait)
                self.executor = None
                self._shutdown = True
    
    def enqueue_file(self, file_path: Path, project_id: int) -> int:
        """
        Enqueue a single file for conversion.
        
        Args:
            file_path: Path to the file to convert
            project_id: ID of the project this file belongs to
            
        Returns:
            Job ID of the enqueued job
        """
        recipe_name = self._get_selected_recipe_name()
        file_id = register_file(
            self.db_path,
            project_id,
            str(file_path),
            file_type=file_path.suffix.lower(),
            size_bytes=file_path.stat().st_size if file_path.exists() else None,
        )
        job_id = create_job(self.db_path, file_id, recipe_name=recipe_name)

        # Submit the job for processing
        if self.executor is not None:
            self.executor.submit(self._process_job, job_id, file_path, project_id, file_id)
        else:
            # If executor not started, process synchronously (for testing)
            self._process_job(job_id, file_path, project_id)
            
        return job_id

    def _get_selected_recipe_name(self) -> Optional[str]:
        """Resolve the selected recipe once per enqueue path."""
        try:
            from .ui.convert import get_selected_recipe
            return get_selected_recipe()
        except (ImportError, AttributeError):
            return None
    
    def enqueue_many(self, file_paths: List[Path], project_id: int) -> List[int]:
        """
        Enqueue multiple files for conversion.
        
        Args:
            file_paths: List of file paths to convert
            project_id: ID of the project these files belong to
            
        Returns:
            List of job IDs for the enqueued jobs
        """
        recipe_name = self._get_selected_recipe_name()
        file_records = [
            (
                str(file_path),
                file_path.suffix.lower(),
                file_path.stat().st_size if file_path.exists() else None,
            )
            for file_path in file_paths
        ]

        try:
            registrations = register_files_and_create_jobs(
                self.db_path,
                project_id,
                file_records,
                recipe_name=recipe_name,
            )
        except sqlite3.OperationalError as exc:
            if "no such table" not in str(exc):
                raise
            registrations = []

        if not registrations:
            registrations = []
            for file_path in file_paths:
                file_id = register_file(
                    self.db_path,
                    project_id,
                    str(file_path),
                    file_type=file_path.suffix.lower(),
                    size_bytes=file_path.stat().st_size if file_path.exists() else None,
                )
                job_id = create_job(self.db_path, file_id, recipe_name=recipe_name)
                registrations.append((file_id, job_id))

        job_ids = []
        for file_path, (file_id, job_id) in zip(file_paths, registrations):
            job_ids.append(job_id)
            if self.executor is not None:
                self.executor.submit(self._process_job, job_id, file_path, project_id, file_id)
            else:
                self._process_job(job_id, file_path, project_id, file_id)
        return job_ids
    
    def _process_job(self, job_id: int, file_path: Path, project_id: int, file_id: Optional[int] = None):
        """
        Process a single job (internal method).
        
        Args:
            job_id: ID of the job to process
            file_path: Path to the file to convert
            project_id: ID of the project this file belongs to
        """
        db_path = self.db_path

        try:
            # Update job status to processing
            try:
                update_job_status(db_path, job_id, JOB_STATUS_PROCESSING)
            except ValueError as exc:
                if "Invalid job status transition" in str(exc):
                    _safe_add_log(db_path, "info", f"Job {job_id} was cancelled before processing", job_id)
                    return
                raise
            _safe_add_log(db_path, "info", f"Starting conversion of {file_path.name}", job_id)
            
            # Perform the conversion
            conversion_result = convert_file(file_path, self.output_root, self.config)
            
            if conversion_result.success:
                with get_connection(db_path) as conn:
                    cursor = conn.cursor()
                    output_file_id = file_id
                    if output_file_id is None:
                        cursor.execute("SELECT file_id FROM jobs WHERE id = ?", (job_id,))
                        row = cursor.fetchone()
                        if row is None:
                            raise ValueError(f"Job {job_id} could not be loaded")
                        output_file_id = row["file_id"]

                    now = datetime.utcnow()
                    cursor.execute("""
                        UPDATE jobs
                        SET status = ?, finished_at = ?, error_message = NULL
                        WHERE id = ?
                    """, (JOB_STATUS_COMPLETED, now, job_id))
                    cursor.execute("""
                        INSERT INTO outputs (file_id, output_path, output_type, text_length, quality_score)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        output_file_id,
                        str(conversion_result.output_path),
                        "markdown",
                        conversion_result.text_length,
                        conversion_result.quality_report.score if conversion_result.quality_report else 0
                    ))
                    conn.commit()

                _safe_add_log(db_path, "info", f"Conversion completed: {conversion_result.text_length} characters", job_id)
            else:
                # Update job status to failed
                update_job_status(db_path, job_id, JOB_STATUS_FAILED, conversion_result.error_message or "Unknown error")
                _safe_add_log(db_path, "error", f"Conversion failed: {conversion_result.error_message}", job_id)
                
        except Exception as e:
            # Update job status to failed with exception details
            error_msg = f"Job processing error: {str(e)}"
            try:
                current_job = get_job_by_id(db_path, job_id)
                if current_job and normalize_job_status(current_job["status"]) != JOB_STATUS_CANCELLED:
                    update_job_status(db_path, job_id, JOB_STATUS_FAILED, error_msg)
            except Exception:
                pass
            _safe_add_log(db_path, "error", error_msg, job_id)

    def retry_job(self, job_id: int) -> int:
        """
        Retry a failed job by creating a new job attempt for the same file.

        Returns:
            The new job ID.
        """
        db_path = self.db_path
        job_record = get_job_by_id(db_path, job_id)
        if job_record is None:
            raise ValueError(f"Job {job_id} not found")

        if normalize_job_status(job_record["status"]) != JOB_STATUS_FAILED:
            raise ValueError("Only failed jobs can be retried")

        recipe_name = job_record["recipe_name"] if "recipe_name" in job_record.keys() else None
        new_job_id = create_job(db_path, job_record["file_id"], recipe_name)
        file_path = Path(job_record["source_path"])
        project_id = job_record["project_id"]

        _safe_add_log(db_path, "info", f"Retrying job {job_id} as new job {new_job_id}", new_job_id)

        if self.executor is not None:
            self.executor.submit(self._process_job, new_job_id, file_path, project_id, job_record["file_id"])
        else:
            self._process_job(new_job_id, file_path, project_id, job_record["file_id"])

        return new_job_id

    def cancel_job(self, job_id: int) -> bool:
        """
        Cancel a pending job if it has not started yet.

        Returns:
            True if the job was cancelled, False otherwise.
        """
        db_path = self.db_path
        job_record = get_job_by_id(db_path, job_id)
        if job_record is None:
            raise ValueError(f"Job {job_id} not found")

        if normalize_job_status(job_record["status"]) != JOB_STATUS_PENDING:
            return False

        update_job_status(db_path, job_id, JOB_STATUS_CANCELLED)
        _safe_add_log(db_path, "info", f"Cancelled pending job {job_id}", job_id)
        return True
    
    def get_queue_snapshot(self) -> List[Dict[str, Any]]:
        """
        Get a snapshot of the current queue status for UI display.
        
        Returns:
            List of dictionaries containing job information
        """
        db_path = self.db_path
        jobs = list_recent_jobs(db_path, limit=100)  # Get recent jobs
        
        snapshot = []
        for job in jobs:
            if hasattr(job, "keys"):
                def get_value(key, index):
                    return job[key]
            else:
                def get_value(key, index):
                    return job[index] if index is not None and index < len(job) else None

            status = normalize_job_status(get_value("status", 1))
            snapshot.append({
                'job_id': get_value("job_id", 0),
                'status': status,
                'started_at': get_value("started_at", 2),
                'finished_at': get_value("finished_at", 3),
                'error_message': get_value("error_message", 4),
                'file_id': get_value("file_id", 5),
                'source_path': get_value("source_path", 6),
                'file_type': get_value("file_type", 7),
                'project_id': get_value("project_id", 8),
                'project_name': get_value("project_name", 9),
                'output_id': get_value("output_id", 10),
                'output_path': get_value("output_path", 11),
                'output_type': get_value("output_type", 12),
                'text_length': get_value("text_length", 13),
                'quality_score': get_value("quality_score", 14) or 0,
            })
        
        return snapshot


# Global job queue instance (will be initialized with config)
_job_queue: Optional[JobQueue] = None


def get_job_queue() -> Optional[JobQueue]:
    """Get the global job queue instance."""
    return _job_queue


def initialize_job_queue(config: Settings, max_workers: int = 2) -> JobQueue:
    """
    Initialize the global job queue.
    
    Args:
        config: Application configuration
        max_workers: Maximum number of worker threads
        
    Returns:
        The initialized JobQueue instance
    """
    global _job_queue
    _job_queue = JobQueue(config, max_workers)
    _job_queue.start()
    return _job_queue


def shutdown_job_queue():
    """Shutdown the global job queue."""
    global _job_queue
    if _job_queue is not None:
        _job_queue.stop()
        _job_queue = None
