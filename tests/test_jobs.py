"""Tests for the job queue module."""

import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from markitdesk.config import Settings
from markitdesk.jobs import JobQueue, _safe_add_log, initialize_job_queue, shutdown_job_queue, get_job_queue


def test_job_queue_initialization():
    """Test job queue initialization."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        
        # Create settings
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        
        # Initialize job queue
        job_queue = JobQueue(config, max_workers=2)
        
        assert job_queue.config == config
        assert job_queue.max_workers == 2
        assert job_queue.executor is None  # Not started yet
        
        # Start the queue
        job_queue.start()
        assert job_queue.executor is not None
        assert not job_queue._shutdown
        
        # Stop the queue
        job_queue.stop()
        assert job_queue._shutdown


def test_enqueue_file():
    """Test enqueuing a single file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        output_root.mkdir()
        
        # Create settings
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        
        # Initialize database
        db_path = workspace / "markitdesk.db"
        # We'll need to mock the database path for simplicity in this test
        
        # Create a test file
        test_file = workspace / "test.txt"
        test_file.write_text("Hello, world!")
        
        # Create job queue
        job_queue = JobQueue(config, max_workers=2)
        
        # Mock the database functions to avoid complex setup
        with patch('markitdesk.jobs.register_file') as mock_register, \
             patch('markitdesk.jobs.create_job') as mock_create_job, \
             patch.object(job_queue, '_process_job') as mock_process:
            
            mock_register.return_value = 1  # file_id
            mock_create_job.return_value = 1  # job_id
            
            # Enqueue a file
            job_id = job_queue.enqueue_file(test_file, 1)  # project_id = 1
            
            # Verify calls
            assert job_id == 1
            mock_register.assert_called_once()
            mock_create_job.assert_called_once()
            mock_process.assert_called_once_with(1, test_file, 1)  # job_id, file_path, project_id


def test_enqueue_many():
    """Test enqueuing multiple files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        output_root.mkdir()
        
        # Create settings
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        
        # Create test files
        test_file1 = workspace / "test1.txt"
        test_file1.write_text("Hello, world 1!")
        test_file2 = workspace / "test2.txt"
        test_file2.write_text("Hello, world 2!")
        
        # Create job queue
        job_queue = JobQueue(config, max_workers=2)
        
        # Mock the database functions
        with patch('markitdesk.jobs.register_file') as mock_register, \
             patch('markitdesk.jobs.create_job') as mock_create_job, \
             patch.object(job_queue, '_process_job') as mock_process:
            
            mock_register.side_effect = [1, 2]  # file_ids
            mock_create_job.side_effect = [1, 2]  # job_ids
            
            # Enqueue multiple files
            job_ids = job_queue.enqueue_many([test_file1, test_file2], 1)  # project_id = 1
            
            # Verify calls
            assert job_ids == [1, 2]
            assert mock_register.call_count == 2
            assert mock_create_job.call_count == 2
            assert mock_process.call_count == 2


def test_enqueue_many_falls_back_when_batch_registration_table_missing():
    """Batch enqueue should fall back to per-file registration when the optimized path is unavailable."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        output_root.mkdir()

        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root

        test_file1 = workspace / "test1.txt"
        test_file1.write_text("Hello, world 1!")
        test_file2 = workspace / "test2.txt"
        test_file2.write_text("Hello, world 2!")

        job_queue = JobQueue(config, max_workers=2)

        with patch("markitdesk.jobs.register_files_and_create_jobs") as mock_batch_register, \
             patch("markitdesk.jobs.register_file") as mock_register, \
             patch("markitdesk.jobs.create_job") as mock_create_job, \
             patch.object(job_queue, "_process_job") as mock_process:

            mock_batch_register.side_effect = sqlite3.OperationalError("no such table: jobs")
            mock_register.side_effect = [10, 11]
            mock_create_job.side_effect = [20, 21]

            job_ids = job_queue.enqueue_many([test_file1, test_file2], 1)

            assert job_ids == [20, 21]
            mock_batch_register.assert_called_once()
            assert mock_register.call_count == 2
            assert mock_create_job.call_count == 2
            assert mock_process.call_count == 2


def test_enqueue_many_reraises_unexpected_operational_errors():
    """Unexpected sqlite operational errors should not be silently swallowed."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        output_root.mkdir()

        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root

        test_file = workspace / "test.txt"
        test_file.write_text("Hello, world!")

        job_queue = JobQueue(config, max_workers=2)

        with patch("markitdesk.jobs.register_files_and_create_jobs", side_effect=sqlite3.OperationalError("database is locked")):
            with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                job_queue.enqueue_many([test_file], 1)


def test_job_queue_snapshot():
    """Test getting queue snapshot."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        output_root.mkdir()
        
        # Create settings
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        
        # Create job queue
        job_queue = JobQueue(config, max_workers=2)
        
        # Mock list_recent_jobs to return test data
        with patch('markitdesk.jobs.list_recent_jobs') as mock_list:
            mock_list.return_value = [
                (1, 'completed', '2023-01-01 10:00:00', '2023-01-01 10:00:05', None, 
                 1, '/workspace/test.txt', 'txt', 1, 'Test Project')
            ]
            
            snapshot = job_queue.get_queue_snapshot()
            
            assert len(snapshot) == 1
            job = snapshot[0]
            assert job['job_id'] == 1
            assert job['status'] == 'completed'
            assert job['source_path'] == '/workspace/test.txt'
            assert job['project_name'] == 'Test Project'


def test_selected_recipe_lookup(monkeypatch):
    """Test that the job queue reads the selected recipe from the convert module."""
    monkeypatch.setattr("markitdesk.ui.convert.get_selected_recipe", lambda: "recipe-a")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = Settings()
        config.workspace_root = temp_path / "workspace"
        config.output_root = temp_path / "output"
        config.workspace_root.mkdir()
        config.output_root.mkdir()

        job_queue = JobQueue(config, max_workers=1)
        assert job_queue._get_selected_recipe_name() == "recipe-a"


def test_global_job_queue_functions():
    """Test the global job queue functions."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        output_root.mkdir()
        
        # Create settings
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        
        # Initialize global job queue
        job_queue = initialize_job_queue(config, max_workers=2)
        
        assert job_queue is not None
        assert isinstance(job_queue, JobQueue)
        
        # Get the job queue
        retrieved_queue = get_job_queue()
        assert retrieved_queue is job_queue
        
        # Shutdown the job queue
        shutdown_job_queue()
        assert get_job_queue() is None


def test_safe_add_log_swallows_logging_failures():
    """Queue logging helper should never raise back into queue processing."""
    with patch("markitdesk.jobs.add_log", side_effect=RuntimeError("log down")):
        _safe_add_log(Path("test.db"), "info", "hello", 1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
