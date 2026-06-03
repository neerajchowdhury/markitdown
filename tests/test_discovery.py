"""Tests for file discovery functionality."""

import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from markitdesk.config import Settings


def test_discover_files_import():
    """Test that discovery module can be imported."""
    from markitdesk.discovery import discover_files, discover_files_from_zip

    assert discover_files is not None
    assert discover_files_from_zip is not None


def setup_test_environment():
    """Set up test environment with temporary directories and stubbed audit logging."""
    temp_dir = Path(tempfile.mkdtemp())
    workspace = temp_dir / "workspace"
    output = temp_dir / "output"
    workspace.mkdir()
    output.mkdir()

    settings = Settings()
    settings.workspace_root = workspace
    settings.output_root = output

    import markitdesk.config
    original_settings = markitdesk.config.settings
    markitdesk.config.settings = settings

    import markitdesk.discovery as discovery_module
    original_log_audit_event = discovery_module.log_audit_event
    discovery_module.log_audit_event = lambda *args, **kwargs: 0

    return temp_dir, workspace, output, settings, original_settings, original_log_audit_event


def teardown_test_environment(original_settings, original_log_audit_event):
    """Restore original settings."""
    import markitdesk.config
    import markitdesk.discovery as discovery_module

    markitdesk.config.settings = original_settings
    discovery_module.log_audit_event = original_log_audit_event


def test_discover_files_directory():
    """Test discovering files in a directory."""
    from markitdesk.discovery import discover_files

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        # Create test files
        (workspace / "test1.txt").write_text("content1")
        (workspace / "test2.pdf").write_text("content2")
        (workspace / "normal_hidden.txt").write_text("hidden")  # This should be included (not actually hidden)
        (workspace / ".hidden").write_text("dotfile")  # This should be excluded (actually hidden)

        # Create subdirectory
        subdir = workspace / "subdir"
        subdir.mkdir()
        (subdir / "test3.docx").write_text("content3")

        # Discover files
        files = discover_files([workspace], settings)

        # Debug: print what we found
        print(f"Discovered files: {[f.name for f in files]}")

        # Should find 3 files (test1.txt, test2.pdf, test3.docx) plus normal_hidden.txt
        # The .hidden file should be excluded
        assert len(files) == 4
        file_names = {f.name for f in files}
        assert "test1.txt" in file_names
        assert "test2.pdf" in file_names
        assert "test3.docx" in file_names
        assert "normal_hidden.txt" in file_names
        # Should not find actually hidden file (starting with dot)
        assert ".hidden" not in file_names
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_discover_files_directory_symlink_escape_rejected():
    """Test that symlinked files pointing outside the workspace are skipped."""
    from markitdesk.discovery import discover_files

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        (workspace / "inside.pdf").write_text("content")
        outside_file = Path(temp_dir) / "outside.pdf"
        outside_file.write_text("secret")

        link_path = workspace / "linked.pdf"
        try:
            link_path.symlink_to(outside_file)
        except (OSError, NotImplementedError):
            pytest.skip("Symlink creation not available in this environment")

        files = discover_files([workspace], settings)
        file_names = {f.name for f in files}

        assert "inside.pdf" in file_names
        assert "linked.pdf" not in file_names
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_discover_files_single_file():
    """Test discovering a single file."""
    from markitdesk.discovery import discover_files

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        # Create test file
        test_file = workspace / "test.txt"
        test_file.write_text("content")

        # Discover files
        files = discover_files([test_file], settings)

        # Should find the file
        assert len(files) == 1
        assert files[0].name == "test.txt"
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_discover_files_unsupported_extension():
    """Test that unsupported file extensions are skipped."""
    from markitdesk.discovery import discover_files

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        # Create test files with unsupported extensions
        (workspace / "test.exe").write_text("content")
        (workspace / "test.tmp").write_text("content")

        # Discover files
        files = discover_files([workspace], settings)

        # Should find no files
        assert len(files) == 0
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_discover_files_from_zip():
    """Test discovering files from a ZIP archive."""
    from markitdesk.discovery import discover_files_from_zip

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        # Create a ZIP file with test content
        zip_path = workspace / "test.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("file1.txt", "content1")
            zf.writestr("file2.pdf", "content2")
            zf.writestr("hidden.txt", "hidden")  # This is not actually a hidden file (no leading dot)
            zf.writestr(".actually_hidden.txt", "hidden")  # This IS a hidden file

        # Discover files from ZIP
        files = discover_files_from_zip(zip_path, settings)

        # Debug: print what we found
        print(f"Discovered files from ZIP: {[f.name for f in files]}")

        # Should find 3 files (file1.txt, file2.pdf, hidden.txt) - the actually hidden one should be excluded
        assert len(files) == 3
        file_names = {f.name for f in files}
        assert "file1.txt" in file_names
        assert "file2.pdf" in file_names
        assert "hidden.txt" in file_names  # Not actually hidden, so included
        # Should not find actually hidden file (starting with dot)
        assert ".actually_hidden.txt" not in file_names
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_discover_files_from_zip_duplicate_names_are_disambiguated():
    """ZIP extraction should avoid overwriting duplicate basenames."""
    from markitdesk.discovery import discover_files_from_zip

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        zip_path = workspace / "duplicates.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("a/report.txt", "first")
            zf.writestr("b/report.txt", "second")

        files = discover_files_from_zip(zip_path, settings)

        assert [path.name for path in files] == ["report.txt", "report_1.txt"]
        assert files[0].read_text(encoding="utf-8") == "first"
        assert files[1].read_text(encoding="utf-8") == "second"
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_discover_files_from_zip_rejected_when_recipe_disables_extraction(monkeypatch):
    """Recipe settings should be able to disable ZIP extraction entirely."""
    from markitdesk import discovery as discovery_module

    class FakeRecipe:
        allowed_extensions = [".txt"]
        extract_zip = False

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        zip_path = workspace / "disabled.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file.txt", "content")

        monkeypatch.setattr(discovery_module, "load_recipe", lambda name: FakeRecipe())

        with pytest.raises(ValueError, match="ZIP extraction is disabled"):
            discovery_module.discover_files_from_zip(zip_path, settings, recipe_name="No ZIP")
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_recipe_specific_extensions(monkeypatch):
    """Recipe-specific allowed extensions should override defaults."""
    from markitdesk import discovery as discovery_module

    class FakeRecipe:
        allowed_extensions = [".special"]
        extract_zip = True

    monkeypatch.setattr(discovery_module, "load_recipe", lambda name: FakeRecipe())

    assert discovery_module.get_allowed_extensions("any-recipe") == {".special"}


def test_discover_files_from_zip_oversized_member_rejected():
    """Test that ZIP members over the per-file size limit are rejected."""
    from markitdesk.discovery import discover_files_from_zip

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        settings.max_file_mb = 0
        zip_path = workspace / "oversized.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("big.txt", "x")

        with pytest.raises(ValueError, match="ZIP member too large"):
            discover_files_from_zip(zip_path, settings)
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_discover_files_from_zip_too_many_files_rejected():
    """ZIP archives over the configured file-count limit should be rejected."""
    from markitdesk.discovery import discover_files_from_zip

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        settings.max_zip_files = 1
        zip_path = workspace / "too_many.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("a.txt", "a")
            zf.writestr("b.txt", "b")

        with pytest.raises(ValueError, match="too many files"):
            discover_files_from_zip(zip_path, settings)
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_discover_files_from_zip_uncompressed_size_limit_rejected():
    """ZIP archives over the configured total uncompressed size limit should be rejected."""
    from markitdesk.discovery import discover_files_from_zip

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        settings.max_zip_uncompressed_mb = 0
        zip_path = workspace / "too_large.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("a.txt", "a")

        with pytest.raises(ValueError, match="uncompressed size too large"):
            discover_files_from_zip(zip_path, settings)
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_discover_files_from_zip_absolute_path_rejected():
    """ZIP entries with absolute paths should be rejected."""
    from markitdesk.discovery import discover_files_from_zip

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        zip_path = workspace / "absolute.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("/abs.txt", "bad")

        with pytest.raises(ValueError, match="absolute path"):
            discover_files_from_zip(zip_path, settings)
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_discover_files_from_zip_bad_zip_raises():
    """Corrupted ZIP files should raise BadZipFile."""
    from markitdesk.discovery import discover_files_from_zip

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        zip_path = workspace / "broken.zip"
        zip_path.write_text("not a zip", encoding="utf-8")

        with pytest.raises(zipfile.BadZipFile):
            discover_files_from_zip(zip_path, settings)
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_discover_files_from_zip_unsupported_members_are_skipped():
    """Unsupported ZIP members should be ignored without failing the whole archive."""
    from markitdesk.discovery import discover_files_from_zip

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        zip_path = workspace / "mixed.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("keep.txt", "ok")
            zf.writestr("skip.exe", "bad")

        files = discover_files_from_zip(zip_path, settings)

        assert [path.name for path in files] == ["keep.txt"]
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_discover_files_from_zip_path_traversal():
    """Test that ZIP files with path traversal are rejected."""
    from markitdesk.discovery import discover_files_from_zip

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        # Create a ZIP file with path traversal
        zip_path = workspace / "malicious.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("../evil.txt", "bad content")

        # Discover files from ZIP should raise ValueError
        try:
            files = discover_files_from_zip(zip_path, settings)
            print(f"ERROR: Should have raised ValueError but got files: {[f.name for f in files]}")
            assert False, "Should have raised ValueError for path traversal"
        except ValueError as e:
            print(f"Got expected ValueError: {e}")
            assert "path traversal" in str(e).lower()
        except Exception as e:
            print(f"Got unexpected exception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


def test_is_hidden_or_system_path():
    """Test the hidden/system path detection."""
    from markitdesk.discovery import is_hidden_or_system_path

    temp_dir, workspace, output, settings, original_settings, original_log_audit_event = setup_test_environment()
    try:
        # Test hidden file
        hidden_file = workspace / ".hidden"
        hidden_file.write_text("content")
        assert is_hidden_or_system_path(hidden_file, workspace) == True

        # Test normal file
        normal_file = workspace / "normal.txt"
        normal_file.write_text("content")
        assert is_hidden_or_system_path(normal_file, workspace) == False

        # Test system directory
        sys_dir = workspace / "__pycache__"
        sys_dir.mkdir()
        assert is_hidden_or_system_path(sys_dir, workspace) == True
    finally:
        teardown_test_environment(original_settings, original_log_audit_event)


if __name__ == "__main__":
    test_discover_files_import()
    test_discover_files_directory()
    test_discover_files_single_file()
    test_discover_files_unsupported_extension()
    test_discover_files_from_zip()
    test_discover_files_from_zip_path_traversal()
    test_is_hidden_or_system_path()
    print("All tests passed!")
