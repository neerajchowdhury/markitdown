"""Integration tests for queue functionality."""

import sys
import tempfile
from pathlib import Path

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_imports():
    """Test that all required modules can be imported."""
    from markitdesk.ui.convert import convert_page
    from markitdesk.ui.queue import queue_page
    from markitdesk.jobs import initialize_job_queue, get_job_queue
    from markitdesk.config import Settings
    from markitdesk.database import init_db
    
    assert convert_page is not None
    assert queue_page is not None
    assert initialize_job_queue is not None
    assert get_job_queue is not None
    assert Settings is not None
    assert init_db is not None


def test_job_queue_initialization():
    """Test that job queue can be initialized."""
    # Import inside function to avoid issues
    from markitdesk.config import Settings
    
    # Create temporary directories for testing
    temp_dir = tempfile.mkdtemp()
    try:
        workspace = Path(temp_dir) / "workspace"
        output = Path(temp_dir) / "output"
        workspace.mkdir()
        output.mkdir()
        
        # Create settings
        settings = Settings()
        settings.workspace_root = workspace
        settings.output_root = output
        
        # Initialize database
        from markitdesk.database import init_db
        db_path = workspace.parent / "markitdesk.db"
        init_db(db_path)
        
        # Initialize job queue
        from markitdesk.jobs import initialize_job_queue, get_job_queue
        job_queue = initialize_job_queue(settings)
        assert job_queue is not None
        
        # Test getting job queue
        retrieved_queue = get_job_queue()
        assert retrieved_queue is job_queue
        
        # Clean up
        job_queue.stop()
    finally:
        # Clean up temp directory
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_imports()
    test_job_queue_initialization()
    print("All tests passed!")