"""Tests for the database module."""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from markitdesk.database import (
    init_db,
    create_project,
    register_file,
    create_job,
    update_job_status,
    add_output,
    add_log,
    list_recent_jobs,
    get_connection,
    normalize_job_status,
    is_valid_job_transition,
    register_file_and_create_job,
    register_files_and_create_jobs,
)


def test_init_db_creates_tables():
    """Test that init_db creates all required tables."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        
        # Initialize the database
        init_db(db_path)
        
        # Check that the database file was created
        assert db_path.exists()
        
        # Check that all tables exist
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            
            # Get list of tables
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = {row[0] for row in cursor.fetchall()}
            
            expected_tables = {'projects', 'files', 'jobs', 'outputs', 'logs'}
            assert expected_tables.issubset(tables)


def test_create_project():
    """Test creating a project."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        init_db(db_path)
        
        # Create a project
        project_id = create_project(
            db_path, 
            "Test Project", 
            "/workspace", 
            "/output"
        )
        
        # Verify the project was created
        assert project_id > 0
        
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['name'] == "Test Project"
            assert row['workspace_root'] == "/workspace"
            assert row['output_root'] == "/output"
            assert row['created_at'] is not None


def test_register_file():
    """Test registering a file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        init_db(db_path)
        
        # Create a project first
        project_id = create_project(db_path, "Test Project", "/workspace", "/output")
        
        # Register a file
        file_id = register_file(
            db_path,
            project_id,
            "/workspace/document.pdf",
            "pdf",
            1024
        )
        
        # Verify the file was registered
        assert file_id > 0
        
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['project_id'] == project_id
            assert row['source_path'] == "/workspace/document.pdf"
            assert row['file_type'] == "pdf"
            assert row['size_bytes'] == 1024
            assert row['status'] == "pending"
            assert row['created_at'] is not None


def test_create_job():
    """Test creating a job."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        init_db(db_path)
        
        # Create project and file
        project_id = create_project(db_path, "Test Project", "/workspace", "/output")
        file_id = register_file(db_path, project_id, "/workspace/document.pdf", "pdf", 1024)
        
        # Create a job
        job_id = create_job(db_path, file_id)
        
        # Verify the job was created
        assert job_id > 0
        
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['file_id'] == file_id
            assert row['status'] == "pending"
            assert row['started_at'] is None
            assert row['finished_at'] is None
            assert row['error_message'] is None


def test_update_job_status():
    """Test updating job status."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        init_db(db_path)
        
        # Create project, file, and job
        project_id = create_project(db_path, "Test Project", "/workspace", "/output")
        file_id = register_file(db_path, project_id, "/workspace/document.pdf", "pdf", 1024)
        job_id = create_job(db_path, file_id)
        
        # Update job to processing
        update_job_status(db_path, job_id, "processing")
        
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['status'] == "processing"
            assert row['started_at'] is not None
            
        # Update job to completed
        update_job_status(db_path, job_id, "completed")
        
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['status'] == "completed"
            assert row['finished_at'] is not None
            
        # Create a separate job to verify failure transitions from processing
        second_file_id = register_file(db_path, project_id, "/workspace/document-2.pdf", "pdf", 1024)
        second_job_id = create_job(db_path, second_file_id)
        update_job_status(db_path, second_job_id, "processing")
        update_job_status(db_path, second_job_id, "failed", "Conversion failed")

        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (second_job_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['status'] == "failed"
            assert row['error_message'] == "Conversion failed"


def test_add_output():
    """Test adding an output record."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        init_db(db_path)
        
        # Create project and file
        project_id = create_project(db_path, "Test Project", "/workspace", "/output")
        file_id = register_file(db_path, project_id, "/workspace/document.pdf", "pdf", 1024)
        
        # Add an output
        output_id = add_output(
            db_path,
            file_id,
            "/output/document.md",
            "markdown",
            500
        )
        
        # Verify the output was added
        assert output_id > 0
        
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM outputs WHERE id = ?", (output_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['file_id'] == file_id
            assert row['output_path'] == "/output/document.md"
            assert row['output_type'] == "markdown"
            assert row['text_length'] == 500
            assert row['created_at'] is not None


def test_add_log():
    """Test adding a log entry."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        init_db(db_path)
        
        # Create project, file, and job for testing job_id association
        project_id = create_project(db_path, "Test Project", "/workspace", "/output")
        file_id = register_file(db_path, project_id, "/workspace/document.pdf", "pdf", 1024)
        job_id = create_job(db_path, file_id)
        
        # Add a log entry with job_id
        log_id = add_log(db_path, "info", "Processing started", job_id)
        
        # Verify the log was added
        assert log_id > 0
        
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM logs WHERE id = ?", (log_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['job_id'] == job_id
            assert row['level'] == "info"
            assert row['message'] == "Processing started"
            assert row['created_at'] is not None
            
        # Add a log entry without job_id
        log_id2 = add_log(db_path, "error", "Something went wrong")
        
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM logs WHERE id = ?", (log_id2,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row['job_id'] is None
            assert row['level'] == "error"
            assert row['message'] == "Something went wrong"


def test_list_recent_jobs():
    """Test listing recent jobs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        init_db(db_path)
        
        # Create project
        project_id = create_project(db_path, "Test Project", "/workspace", "/output")
        
        # Create multiple files and jobs
        file1_id = register_file(db_path, project_id, "/workspace/doc1.pdf", "pdf", 1024)
        file2_id = register_file(db_path, project_id, "/workspace/doc2.docx", "docx", 2048)
        
        job1_id = create_job(db_path, file1_id)
        job2_id = create_job(db_path, file2_id)
        
        # Update job statuses
        update_job_status(db_path, job1_id, "processing")
        update_job_status(db_path, job1_id, "completed")
        update_job_status(db_path, job2_id, "processing")
        update_job_status(db_path, job2_id, "failed", "Error processing")
        
        # List recent jobs
        jobs = list_recent_jobs(db_path, limit=10)
        
        # Should have 2 jobs
        assert len(jobs) == 2
        
        # Check the structure of returned data
        job1 = jobs[0]  # Most recent first
        job2 = jobs[1]
        
        # Check job1 (should be job2_id since it was created after job1_id but we ordered by created_at DESC)
        # Actually, job2_id was created after job1_id, so it should be first
        assert job1[0] == job2_id  # job_id
        assert job1[1] == "failed"  # status
        assert job1[5] == file2_id  # file_id
        assert job1[6] == "/workspace/doc2.docx"  # source_path
        assert job1[8] == project_id  # project_id
        assert job1[9] == "Test Project"  # project_name
        
        assert job2[0] == job1_id  # job_id
        assert job2[1] == "completed"  # status
        assert job2[5] == file1_id  # file_id
        assert job2[6] == "/workspace/doc1.pdf"  # source_path
        assert job2[8] == project_id  # project_id
        assert job2[9] == "Test Project"  # project_name


def test_database_foreign_key_constraints():
    """Test that foreign key constraints work."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        init_db(db_path)
        
        # Try to register a file with non-existent project ID
        # This should fail due to foreign key constraint
        with pytest.raises(Exception):  # sqlite3.IntegrityError
            register_file(db_path, 999, "/workspace/test.pdf", "pdf", 1024)
        
        # Create a valid project first
        project_id = create_project(db_path, "Test Project", "/workspace", "/output")
        
        # Now registering a file should work
        file_id = register_file(db_path, project_id, "/workspace/test.pdf", "pdf", 1024)
        assert file_id > 0
        
        # Try to create a job with non-existent file ID
        with pytest.raises(Exception):  # sqlite3.IntegrityError
            create_job(db_path, 999)
            
        # Now creating a job with valid file ID should work
        job_id = create_job(db_path, file_id)
        assert job_id > 0


def test_normalize_job_status_maps_legacy_aliases():
    """Legacy queue status aliases should normalize to canonical values."""
    assert normalize_job_status("running") == "processing"
    assert normalize_job_status("completed") == "completed"
    assert normalize_job_status(None) is None


def test_is_valid_job_transition_accepts_alias_equivalents():
    """Transition validation should respect canonical and aliased statuses."""
    assert is_valid_job_transition(None, "pending") is True
    assert is_valid_job_transition("pending", "running") is True
    assert is_valid_job_transition("running", "completed") is True
    assert is_valid_job_transition("completed", "running") is False


def test_register_file_and_create_job_is_atomic():
    """Combined registration helper should create linked file and job rows together."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        init_db(db_path)
        project_id = create_project(db_path, "Test Project", "/workspace", "/output")

        file_id, job_id = register_file_and_create_job(
            db_path,
            project_id,
            "/workspace/atomic.txt",
            recipe_name="Basic Markdown",
            file_type=".txt",
            size_bytes=42,
        )

        with get_connection(db_path) as conn:
            file_row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
            job_row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

        assert file_row is not None
        assert job_row is not None
        assert file_row["source_path"] == "/workspace/atomic.txt"
        assert job_row["file_id"] == file_id
        assert job_row["recipe_name"] == "Basic Markdown"


def test_register_files_and_create_jobs_preserves_input_order():
    """Batch registration should return file/job pairs in the same order as inputs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        init_db(db_path)
        project_id = create_project(db_path, "Test Project", "/workspace", "/output")

        registrations = register_files_and_create_jobs(
            db_path,
            project_id,
            [
                ("/workspace/a.txt", ".txt", 1),
                ("/workspace/b.txt", ".txt", 2),
            ],
            recipe_name="RAG Pack",
        )

        assert len(registrations) == 2
        first_file_id, first_job_id = registrations[0]
        second_file_id, second_job_id = registrations[1]
        assert first_file_id < second_file_id
        assert first_job_id < second_job_id

        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT f.source_path, j.recipe_name FROM files f JOIN jobs j ON j.file_id = f.id ORDER BY f.id ASC"
            ).fetchall()

        assert [row["source_path"] for row in rows] == ["/workspace/a.txt", "/workspace/b.txt"]
        assert {row["recipe_name"] for row in rows} == {"RAG Pack"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
