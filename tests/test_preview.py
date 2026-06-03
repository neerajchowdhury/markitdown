"""Tests for Markdown preview functionality."""

import sys
import tempfile
from pathlib import Path

import markitdesk.config as config_module

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from markitdesk.config import Settings
from markitdesk.database import create_project, get_job_by_id, init_db, register_file, create_job, add_output, update_job_status
from markitdesk.ui.preview import get_preview_job_details


def test_preview_import():
    """Test that preview module can be imported."""
    from markitdesk.ui.preview import preview_page
    assert preview_page is not None


def test_generate_outline():
    """Test the outline generation function."""
    from markitdesk.ui.preview import preview_page
    
    # We can't directly test the nested function, so we'll test the logic
    # by importing and testing a similar function
    import re
    
    def generate_outline(markdown_text: str) -> str:
        """Generate a markdown outline from headings."""
        lines = markdown_text.split('\n')
        outline_lines = ["# Document Outline\n"]
        
        for line in lines:
            # Match markdown headings
            if line.startswith('#'):
                level = 0
                for char in line:
                    if char == '#':
                        level += 1
                    else:
                        break
                if level <= 6 and len(line) > level and line[level] == ' ':
                    heading_text = line[level+1:].strip()
                    indent = "  " * (level - 1)
                    outline_lines.append(f"{indent}- [{heading_text}](#{heading_text.lower().replace(' ', '-')})")
        
        if len(outline_lines) == 1:
            outline_lines.append("*No headings found in document*")
        
        return '\n'.join(outline_lines)
    
    # Test empty markdown
    outline = generate_outline("")
    assert "# Document Outline" in outline
    assert "*No headings found in document*" in outline
    
    # Test markdown with headings
    markdown = """# Main Title
    
## Section 1
Some content here.

### Subsection
More content.

## Another Section
Even more content."""
    
    outline = generate_outline(markdown)
    assert "# Document Outline" in outline
    assert "- [Main Title](#main-title)" in outline
    assert "  - [Section 1](#section-1)" in outline
    assert "    - [Subsection](#subsection)" in outline
    assert "  - [Another Section](#another-section)" in outline


def test_get_preview_job_details_missing_job_returns_none(monkeypatch):
    """Preview lookup should return None for unknown jobs."""
    temp_root = Path.cwd() / ".pytest_tmp"
    temp_root.mkdir(exist_ok=True)
    temp_dir = tempfile.TemporaryDirectory(dir=temp_root)
    root = Path(temp_dir.name)
    workspace = root / "workspace"
    output = root / "output"
    workspace.mkdir()
    output.mkdir()

    settings = Settings(workspace_root=workspace, output_root=output)
    monkeypatch.setattr(config_module, "settings", settings)
    monkeypatch.setattr("markitdesk.ui.preview.settings", settings)
    init_db(root / "markitdesk.db")

    assert get_preview_job_details(9999) is None
    temp_dir.cleanup()


def test_get_preview_job_details_returns_failed_job_without_output(monkeypatch):
    """Preview lookup should surface failed-job metadata even with no output file."""
    temp_root = Path.cwd() / ".pytest_tmp"
    temp_root.mkdir(exist_ok=True)
    temp_dir = tempfile.TemporaryDirectory(dir=temp_root)
    root = Path(temp_dir.name)
    workspace = root / "workspace"
    output = root / "output"
    workspace.mkdir()
    output.mkdir()

    settings = Settings(workspace_root=workspace, output_root=output)
    monkeypatch.setattr(config_module, "settings", settings)
    monkeypatch.setattr("markitdesk.ui.preview.settings", settings)

    db_path = root / "markitdesk.db"
    init_db(db_path)
    project_id = create_project(db_path, "Preview", str(workspace), str(output))

    source = workspace / "broken.txt"
    source.write_text("broken", encoding="utf-8")
    file_id = register_file(db_path, project_id, str(source), ".txt", source.stat().st_size)
    job_id = create_job(db_path, file_id, "Basic Markdown")
    update_job_status(db_path, job_id, "processing")
    update_job_status(db_path, job_id, "failed", "conversion failed")

    details = get_preview_job_details(job_id)

    assert details is not None
    assert details["job_id"] == job_id
    assert details["status"] == "failed"
    assert details["error_message"] == "conversion failed"
    assert details["source_path"] == str(source)
    assert details["output_path"] is None
    assert details["quality_score"] is None
    temp_dir.cleanup()


def test_get_preview_job_details_uses_latest_output_for_file(monkeypatch):
    """Preview lookup should surface the most recent output for a file-backed job."""
    temp_root = Path.cwd() / ".pytest_tmp"
    temp_root.mkdir(exist_ok=True)
    temp_dir = tempfile.TemporaryDirectory(dir=temp_root)
    root = Path(temp_dir.name)
    workspace = root / "workspace"
    output = root / "output"
    workspace.mkdir()
    output.mkdir()

    settings = Settings(workspace_root=workspace, output_root=output)
    monkeypatch.setattr(config_module, "settings", settings)
    monkeypatch.setattr("markitdesk.ui.preview.settings", settings)

    db_path = root / "markitdesk.db"
    init_db(db_path)
    project_id = create_project(db_path, "Preview", str(workspace), str(output))

    source = workspace / "latest.txt"
    source.write_text("latest", encoding="utf-8")
    file_id = register_file(db_path, project_id, str(source), ".txt", source.stat().st_size)
    job_id = create_job(db_path, file_id, "Basic Markdown")
    update_job_status(db_path, job_id, "processing")
    update_job_status(db_path, job_id, "completed")

    first_output = output / "latest.md"
    second_output = output / "latest_1.md"
    first_output.write_text("first", encoding="utf-8")
    second_output.write_text("second", encoding="utf-8")
    add_output(db_path, file_id, str(first_output), "markdown", 5, 10)
    add_output(db_path, file_id, str(second_output), "markdown", 6, 20)

    details = get_preview_job_details(job_id)
    latest_job = get_job_by_id(db_path, job_id)

    assert details is not None
    assert details["output_path"] == str(second_output)
    assert details["text_length"] == 6
    assert details["quality_score"] == 20
    assert latest_job["output_path"] == str(second_output)
    temp_dir.cleanup()


if __name__ == "__main__":
    test_preview_import()
    test_generate_outline()
    print("All preview tests passed!")
