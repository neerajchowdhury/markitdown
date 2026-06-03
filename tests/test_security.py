"""Tests for security validation functions."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from markitdesk.config import Settings
from markitdesk.security import (
    ValidationResult,
    resolve_inside_base,
    validate_input_file,
    safe_output_path,
)


def test_resolve_inside_base_success():
    """Test successful path resolution within base directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        test_file = base / "test.txt"
        test_file.touch()
        
        # Test relative path
        resolved = resolve_inside_base("test.txt", base)
        assert resolved == test_file.resolve()
        
        # Test absolute path
        resolved = resolve_inside_base(test_file, base)
        assert resolved == test_file.resolve()
        
        # Test subdirectory path
        subdir = base / "subdir"
        subdir.mkdir()
        sub_file = subdir / "file.txt"
        sub_file.touch()
        
        resolved = resolve_inside_base("subdir/file.txt", base)
        assert resolved == sub_file.resolve()


def test_resolve_inside_base_traversal_rejected():
    """Test that path traversal is rejected."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        
        # Test .. traversal
        with pytest.raises(ValueError, match="Path traversal detected"):
            resolve_inside_base("../evil.txt", base)
        
        # Test absolute path outside base
        evil_path = Path(temp_dir) / ".." / "evil.txt"
        evil_path = evil_path.resolve()  # Normalize
        with pytest.raises(ValueError, match="Path traversal detected"):
            resolve_inside_base(evil_path, base)


def test_resolve_inside_base_symlink_escape():
    """Test that symlink escape is rejected (if feasible to test)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Make base a subdirectory to have room for a truly outside file
        base = Path(temp_dir) / "workspace"
        base.mkdir()
        
        # Create a file outside base (in the parent temp directory)
        outside_file = Path(temp_dir) / "secret.txt"
        outside_file.touch()
        
        # Create symlink inside base pointing to outside file
        inside_link = base / "link.txt"
        try:
            inside_link.symlink_to(outside_file)
            
            # This should raise ValueError for symlink escape
            with pytest.raises(ValueError, match="Symlink escape detected"):
                resolve_inside_base(inside_link, base)
        except (OSError, NotImplementedError):
            # Symlinks might not be supported or creatable in test environment
            # On Windows, symlink creation might require special privileges
            pass
        finally:
            # Clean up
            if inside_link.exists():
                inside_link.unlink()
            if outside_file.exists():
                outside_file.unlink()


def test_resolve_inside_base_broken_symlink():
    """Test handling of broken symlinks."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        
        # Create broken symlink
        broken_link = base / "broken.txt"
        try:
            broken_link.symlink_to("/non/existent/file.txt")
            
            # Should still work if the symlink itself is inside base
            resolved = resolve_inside_base(broken_link, base)
            assert resolved == broken_link.resolve()
        except (OSError, NotImplementedError):
            # Symlinks might not be supported
            pass
        finally:
            if broken_link.exists():
                broken_link.unlink()


def test_validate_input_file_success():
    """Test successful file validation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        test_file = base / "document.pdf"
        test_file.write_text("dummy content")
        
        # Create config mock
        config = Mock()
        config.workspace_root = base
        config.max_file_mb = 100
        
        result = validate_input_file(test_file, config)
        assert result.is_valid
        assert result.error_message == ""


def test_validate_input_file_not_found():
    """Test validation of non-existent file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        
        config = Mock()
        config.workspace_root = base
        config.max_file_mb = 100
        
        non_existent = base / "missing.pdf"
        result = validate_input_file(non_existent, config)
        assert not result.is_valid
        assert "does not exist" in result.error_message


def test_validate_input_file_directory():
    """Test validation rejects directories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        subdir = base / "subdir"
        subdir.mkdir()
        
        config = Mock()
        config.workspace_root = base
        config.max_file_mb = 100
        
        result = validate_input_file(subdir, config)
        assert not result.is_valid
        assert "not a file" in result.error_message


def test_validate_input_file_wrong_extension():
    """Test validation rejects wrong file extensions."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        test_file = base / "document.exe"
        test_file.write_text("dummy")
        
        config = Mock()
        config.workspace_root = base
        config.max_file_mb = 100
        
        result = validate_input_file(test_file, config)
        assert not result.is_valid
        assert "File type not allowed" in result.error_message


def test_validate_input_file_oversized():
    """Test validation rejects oversized files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        test_file = base / "large.pdf"
        # Create a file larger than 1 MB (but we'll mock the size check)
        test_file.write_text("x" * 100)  # Small file
        
        config = Mock()
        config.workspace_root = base
        config.max_file_mb = 0  # Zero MB limit
        
        result = validate_input_file(test_file, config)
        assert not result.is_valid
        assert "File too large" in result.error_message


def test_validate_input_file_outside_workspace():
    """Test validation rejects files outside workspace."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir) / "workspace"
        base.mkdir()
        # Create file outside the workspace
        outside_file = Path(temp_dir) / "secret.pdf"
        outside_file.write_text("dummy")

        config = Mock()
        config.workspace_root = base
        config.max_file_mb = 100

        result = validate_input_file(outside_file, config)
        assert not result.is_valid
        assert "Path traversal detected" in result.error_message


def test_validate_input_file_allowed_extensions():
    """Test that all allowed extensions are accepted."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        
        config = Mock()
        config.workspace_root = base
        config.max_file_mb = 100
        
        allowed_extensions = [
            '.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv', '.json', '.xml',
            '.html', '.htm', '.txt', '.md', '.zip', '.epub', '.jpg', '.jpeg',
            '.png', '.webp', '.mp3', '.wav'
        ]
        
        for ext in allowed_extensions:
            test_file = base / f"test{ext}"
            test_file.write_text("dummy")
            
            result = validate_input_file(test_file, config)
            assert result.is_valid, f"Extension {ext} should be allowed"
            
            # Clean up
            test_file.unlink()


def test_safe_output_path_basic():
    """Test basic safe output path generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_root = Path(temp_dir)
        input_path = Path("document.pdf")
        
        output_path = safe_output_path(input_path, output_root)
        
        assert output_path == output_root / "document.md"
        assert output_path.parent == output_root


def test_safe_output_path_preserves_name():
    """Test that safe output path preserves input filename stem."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_root = Path(temp_dir)
        input_path = Path("my_document.txt")
        
        output_path = safe_output_path(input_path, output_root, suffix=".md")
        
        assert output_path.stem == "my_document"
        assert output_path.suffix == ".md"


def test_safe_output_path_prevents_overwrite():
    """Test that safe output path prevents overwrites by adding numeric suffix."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_root = Path(temp_dir)
        input_path = Path("report.pdf")
        
        # Create existing output file
        existing = output_root / "report.md"
        existing.write_text("existing content")
        
        output_path = safe_output_path(input_path, output_root)
        
        # Should get report_1.md since report.md exists
        assert output_path == output_root / "report_1.md"
        assert not output_path.exists()  # Should not overwrite


def test_safe_output_path_multiple_existing():
    """Test handling of multiple existing files with numeric suffixes."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_root = Path(temp_dir)
        input_path = Path("data.csv")
        
        # Create existing files: data.md, data_1.md, data_3.md
        (output_root / "data.md").write_text("existing")
        (output_root / "data_1.md").write_text("existing")
        (output_root / "data_3.md").write_text("existing")
        
        output_path = safe_output_path(input_path, output_root)
        
        # Should get data_2.md (first available)
        assert output_path == output_root / "data_2.md"


def test_safe_output_path_absolute_input():
    """Test safe output path with absolute input path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_root = Path(temp_dir)
        input_path = Path(temp_dir) / "workspace" / "document.docx"
        input_path.parent.mkdir(parents=True)
        input_path.write_text("dummy")
        
        output_path = safe_output_path(input_path, output_root)
        
        # Should use just the filename part
        assert output_path == output_root / "document.md"


def test_safe_output_path_traversal_protection():
    """Test that safe output path protects against path traversal."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_root = Path(temp_dir)
        # Try to trick it with path traversal in input
        input_path = Path("../../etc/passwd")
        
        output_path = safe_output_path(input_path, output_root)
        
        # Should be safely contained within output_root
        assert output_root in output_path.parents
        assert output_path.is_relative_to(output_root)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])