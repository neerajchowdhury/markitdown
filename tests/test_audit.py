"""Tests for audit logging functionality."""

import sys
import tempfile
import json
from pathlib import Path

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import the modules we need for testing
from markitdesk.audit import (
    init_audit_table,
    log_audit_event,
    get_audit_events
)
from markitdesk.config import Settings
from markitdesk.database import init_db


def test_audit_import():
    """Test that audit module can be imported."""
    assert init_audit_table is not None
    assert log_audit_event is not None
    assert get_audit_events is not None


def test_init_audit_table():
    """Test initializing the audit table."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        output = Path(temp_dir) / "output"
        workspace.mkdir()
        output.mkdir()
        
        # Configure settings to use our temporary directory
        settings_obj = Settings()
        settings_obj.workspace_root = workspace
        settings_obj.output_root = output
        
        # Temporarily override the settings module's settings object
        import markitdesk.config
        original_settings = markitdesk.config.settings
        markitdesk.config.settings = settings_obj
        
        try:
            # Initialize database
            db_path = workspace.parent / "markitdesk.db"
            init_db(db_path)
            
            # Initialize audit table
            init_audit_table(db_path)
            
            # Verify table exists by trying to insert a record
            from markitdesk.database import get_connection
            with get_connection(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'")
                result = cursor.fetchone()
                assert result is not None
                assert result[0] == 'audit_logs'
        finally:
            # Restore original settings
            markitdesk.config.settings = original_settings


def test_log_audit_event():
    """Test logging an audit event."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        output = Path(temp_dir) / "output"
        workspace.mkdir()
        output.mkdir()
        
        # Configure settings to use our temporary directory
        settings_obj = Settings()
        settings_obj.workspace_root = workspace
        settings_obj.output_root = output
        
        # Temporarily override the settings module's settings object
        import markitdesk.config
        original_settings = markitdesk.config.settings
        markitdesk.config.settings = settings_obj
        
        try:
            # Initialize database
            db_path = workspace.parent / "markitdesk.db"
            init_db(db_path)
            
            # Initialize audit table
            init_audit_table(db_path)
            
            # Log an audit event
            test_source = workspace / "test.txt"
            test_source.write_text("test content")
            
            event_id = log_audit_event(
                level="info",
                event_type="file_registered",
                message="Test file registered",
                source_path=test_source,
                job_id=123,
                metadata={"test_key": "test_value", "number": 42}
            )
            
            assert event_id is not None
            assert event_id > 0
            
            # Retrieve the event and verify its contents
            events = get_audit_events(limit=1)
            assert len(events) == 1
            
            event = events[0]
            assert event['id'] == event_id
            assert event['level'] == "info"
            assert event['event_type'] == "file_registered"
            assert event['message'] == "Test file registered"
            assert event['source_path'] == str(test_source)
            assert event['job_id'] == 123
            assert event['metadata'] == {"test_key": "test_value", "number": 42}
        finally:
            # Restore original settings
            markitdesk.config.settings = original_settings


def test_get_audit_events():
    """Test retrieving audit events with filtering."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        output = Path(temp_dir) / "output"
        workspace.mkdir()
        output.mkdir()
        
        # Configure settings to use our temporary directory
        settings_obj = Settings()
        settings_obj.workspace_root = workspace
        settings_obj.output_root = output
        
        # Temporarily override the settings module's settings object
        import markitdesk.config
        original_settings = markitdesk.config.settings
        markitdesk.config.settings = settings_obj
        
        try:
            # Initialize database
            db_path = workspace.parent / "markitdesk.db"
            init_db(db_path)
            
            # Initialize audit table
            init_audit_table(db_path)
            
            # Log several events
            log_audit_event(
                level="info",
                event_type="file_registered",
                message="First file registered",
                metadata={"seq": 1}
            )
            
            log_audit_event(
                level="warning",
                event_type="validation_failed",
                message="Validation failed",
                metadata={"seq": 2}
            )
            
            log_audit_event(
                level="info",
                event_type="file_registered",
                message="Second file registered",
                metadata={"seq": 3}
            )
            
            # Test getting all events
            events = get_audit_events(limit=10)
            assert len(events) == 3
            
            # Test getting events with limit
            events = get_audit_events(limit=2)
            assert len(events) == 2
            
            # Test filtering by level
            events = get_audit_events(level="info")
            assert len(events) == 2
            
            # Test filtering by event_type
            events = get_audit_events(event_type="file_registered")
            assert len(events) == 2
            
            # Test filtering by level and event_type
            events = get_audit_events(level="info", event_type="file_registered")
            assert len(events) == 2
            
            # Test offset
            events = get_audit_events(limit=2, offset=1)
            assert len(events) == 2
            assert events[0]['metadata']['seq'] == 2
            assert events[1]['metadata']['seq'] == 3
        finally:
            # Restore original settings
            markitdesk.config.settings = original_settings


def test_log_audit_event_without_optional_fields():
    """Test logging an audit event without optional fields."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        output = Path(temp_dir) / "output"
        workspace.mkdir()
        output.mkdir()
        
        # Configure settings to use our temporary directory
        settings_obj = Settings()
        settings_obj.workspace_root = workspace
        settings_obj.output_root = output
        
        # Temporarily override the settings module's settings object
        import markitdesk.config
        original_settings = markitdesk.config.settings
        markitdesk.config.settings = settings_obj
        
        try:
            # Initialize database
            db_path = workspace.parent / "markitdesk.db"
            init_db(db_path)
            
            # Initialize audit table
            init_audit_table(db_path)
            
            # Log an audit event without optional fields
            event_id = log_audit_event(
                level="error",
                event_type="conversion_failed",
                message="Conversion failed"
            )
            
            assert event_id is not None
            assert event_id > 0
            
            # Retrieve the event and verify its contents
            events = get_audit_events(limit=1)
            assert len(events) == 1
            
            event = events[0]
            assert event['id'] == event_id
            assert event['level'] == "error"
            assert event['event_type'] == "conversion_failed"
            assert event['message'] == "Conversion failed"
            assert event['source_path'] is None
            assert event['job_id'] is None
            assert event['metadata'] is None
        finally:
            # Restore original settings
            markitdesk.config.settings = original_settings


if __name__ == "__main__":
    test_audit_import()
    test_init_audit_table()
    test_log_audit_event()
    test_get_audit_events()
    test_log_audit_event_without_optional_fields()
    print("All audit tests passed!")