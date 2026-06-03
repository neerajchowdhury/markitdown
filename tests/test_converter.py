"""Tests for the conversion wrapper."""

import importlib.util
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from markitdesk.config import Settings
from markitdesk.converter import ConversionResult, _safe_log_audit_event, convert_file


REAL_MARKITDOWN_AVAILABLE = importlib.util.find_spec("markitdown") is not None


def _write_minimal_docx(path: Path) -> None:
    """Create a minimal DOCX file with simple paragraph content."""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    document = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Hello DOCX</w:t></w:r></w:p>
    <w:p><w:r><w:t>Alpha Beta</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)


def _write_minimal_xlsx(path: Path) -> None:
    """Create a minimal XLSX file with one worksheet and inline strings."""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf/></cellStyleXfs>
  <cellXfs count="1"><xf xfId="0"/></cellXfs>
</styleSheet>"""
    sheet = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="inlineStr"><is><t>name</t></is></c><c r="B1" t="inlineStr"><is><t>value</t></is></c></row>
    <row r="2"><c r="A2" t="inlineStr"><is><t>foo</t></is></c><c r="B2"><v>1</v></c></row>
    <row r="3"><c r="A3" t="inlineStr"><is><t>bar</t></is></c><c r="B3"><v>2</v></c></row>
  </sheetData>
</worksheet>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/styles.xml", styles)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


def _write_minimal_pptx(path: Path) -> None:
    """Create a minimal PPTX file with one slide and simple text."""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>"""
    presentation = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldIdLst>
    <p:sldId id="256" r:id="rId1"/>
  </p:sldIdLst>
</p:presentation>"""
    presentation_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>"""
    slide = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="1" name="Title 1"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:txBody>
          <a:bodyPr/>
          <a:lstStyle/>
          <a:p><a:r><a:t>Hello PPTX</a:t></a:r></a:p>
          <a:p><a:r><a:t>Alpha Beta</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("ppt/presentation.xml", presentation)
        archive.writestr("ppt/_rels/presentation.xml.rels", presentation_rels)
        archive.writestr("ppt/slides/slide1.xml", slide)


def test_conversion_result_creation():
    """Test ConversionResult dataclass creation."""
    source = Path("input.txt")
    output = Path("output.md")
    
    result = ConversionResult(
        source_path=source,
        output_path=output,
        success=True,
        text_length=100,
        duration_ms=50
    )
    
    assert result.source_path == source
    assert result.output_path == output
    assert result.success is True
    assert result.text_length == 100
    assert result.duration_ms == 50
    assert result.error_message is None


def test_convert_txt_file_success():
    """Test successful conversion of a text file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        
        # Create a test text file
        input_file = workspace / "test.txt"
        test_content = "Hello, world!\nThis is a test file."
        input_file.write_text(test_content, encoding='utf-8')
        
        # Configure settings
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        
        # Convert the file
        result = convert_file(input_file, output_root, config)
        
        # Check result
        assert result.success is True
        assert result.source_path == input_file
        assert result.text_length > 0
        assert result.duration_ms >= 0
        assert result.error_message is None
        
        # Check output file exists and has content
        assert result.output_path.exists()
        output_content = result.output_path.read_text(encoding='utf-8')
        assert len(output_content) > 0
        # Should contain the converted markdown content
        assert "Hello, world!" in output_content


def test_convert_md_file_success():
    """Test successful conversion of a markdown file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        
        # Create a test markdown file
        input_file = workspace / "test.md"
        test_content = "# Hello\n\nThis is **markdown**."
        input_file.write_text(test_content, encoding='utf-8')
        
        # Configure settings
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        
        # Convert the file
        result = convert_file(input_file, output_root, config)
        
        # Check result
        assert result.success is True
        assert result.text_length > 0
        assert result.output_path.exists()
        
        # Output should be markdown (potentially processed)
        output_content = result.output_path.read_text(encoding='utf-8')
        assert len(output_content) > 0


@pytest.mark.skipif(not REAL_MARKITDOWN_AVAILABLE, reason="real markitdown package is not installed")
def test_convert_html_file_with_real_markitdown():
    """Real MarkItDown conversion should extract readable markdown from simple HTML."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"

        input_file = workspace / "sample.html"
        input_file.write_text("<html><body><h1>Hello</h1><p>Alpha Beta</p></body></html>", encoding="utf-8")

        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root

        result = convert_file(input_file, output_root, config)

        assert result.success is True
        output_content = result.output_path.read_text(encoding="utf-8")
        assert "# Hello" in output_content
        assert "Alpha Beta" in output_content


@pytest.mark.skipif(not REAL_MARKITDOWN_AVAILABLE, reason="real markitdown package is not installed")
def test_convert_csv_file_with_real_markitdown():
    """Real MarkItDown conversion should preserve simple CSV rows as a markdown table."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"

        input_file = workspace / "sample.csv"
        input_file.write_text("name,value\nfoo,1\nbar,2\n", encoding="utf-8")

        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root

        result = convert_file(input_file, output_root, config)

        assert result.success is True
        output_content = result.output_path.read_text(encoding="utf-8")
        assert "| name | value |" in output_content
        assert "| foo | 1 |" in output_content
        assert "| bar | 2 |" in output_content


@pytest.mark.skipif(not REAL_MARKITDOWN_AVAILABLE, reason="real markitdown package is not installed")
def test_convert_json_file_with_real_markitdown():
    """Real MarkItDown conversion should preserve simple JSON content."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"

        input_file = workspace / "sample.json"
        input_file.write_text(json.dumps({"title": "Hello JSON", "items": ["a", "b"]}, indent=2), encoding="utf-8")

        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root

        result = convert_file(input_file, output_root, config)

        assert result.success is True
        output_content = result.output_path.read_text(encoding="utf-8")
        assert '"title": "Hello JSON"' in output_content
        assert '"items": [' in output_content


@pytest.mark.skipif(not REAL_MARKITDOWN_AVAILABLE, reason="real markitdown package is not installed")
def test_convert_xml_file_with_real_markitdown():
    """Real MarkItDown conversion should preserve simple XML content."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"

        input_file = workspace / "sample.xml"
        input_file.write_text("<root><title>Hello XML</title><item>Alpha</item></root>", encoding="utf-8")

        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root

        result = convert_file(input_file, output_root, config)

        assert result.success is True
        output_content = result.output_path.read_text(encoding="utf-8")
        assert "<root>" in output_content
        assert "Hello XML" in output_content


@pytest.mark.skipif(not REAL_MARKITDOWN_AVAILABLE, reason="real markitdown package is not installed")
def test_convert_docx_file_with_real_markitdown():
    """Real MarkItDown conversion should extract text from a minimal DOCX file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"

        input_file = workspace / "sample.docx"
        _write_minimal_docx(input_file)

        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root

        result = convert_file(input_file, output_root, config)

        assert result.success is True
        output_content = result.output_path.read_text(encoding="utf-8")
        assert "Hello DOCX" in output_content
        assert "Alpha Beta" in output_content


@pytest.mark.skipif(not REAL_MARKITDOWN_AVAILABLE, reason="real markitdown package is not installed")
def test_convert_xlsx_file_with_real_markitdown():
    """Real MarkItDown conversion should extract a simple worksheet as markdown."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"

        input_file = workspace / "sample.xlsx"
        _write_minimal_xlsx(input_file)

        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root

        result = convert_file(input_file, output_root, config)

        assert result.success is True
        output_content = result.output_path.read_text(encoding="utf-8")
        assert "## Sheet1" in output_content
        assert "| name | value |" in output_content
        assert "| foo | 1 |" in output_content


@pytest.mark.skipif(not REAL_MARKITDOWN_AVAILABLE, reason="real markitdown package is not installed")
def test_convert_pptx_file_with_real_markitdown():
    """Real MarkItDown conversion should extract text from a minimal PPTX file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"

        input_file = workspace / "sample.pptx"
        _write_minimal_pptx(input_file)

        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root

        result = convert_file(input_file, output_root, config)

        assert result.success is True
        output_content = result.output_path.read_text(encoding="utf-8")
        assert "Hello PPTX" in output_content
        assert "Alpha Beta" in output_content


def test_convert_unsupported_file():
    """Test conversion of unsupported file type fails safely."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        
        # Create an unsupported file (e.g., executable)
        input_file = workspace / "test.exe"
        input_file.write_bytes(b"MZ\x90\x00")  # DOS header
        
        # Configure settings
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        
        # Convert the file
        result = convert_file(input_file, output_root, config)
        
        # Should fail gracefully
        assert result.success is False
        assert result.error_message is not None
        assert len(result.error_message) > 0
        assert result.text_length == 0


def test_convert_nonexistent_file():
    """Test conversion of non-existent file fails safely."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        
        # Non-existent file
        input_file = workspace / "nonexistent.pdf"
        
        # Configure settings
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        
        # Convert the file
        result = convert_file(input_file, output_root, config)
        
        # Should fail gracefully
        assert result.success is False
        assert result.error_message is not None
        assert "does not exist" in result.error_message


def test_convert_file_outside_workspace():
    """Test conversion of file outside workspace fails safely."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        
        # Create file outside workspace
        outside_file = temp_path / "outside.pdf"
        outside_file.write_text("content")
        
        # Configure settings
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        
        # Convert the file
        result = convert_file(outside_file, output_root, config)
        
        # Should fail due to security validation
        assert result.success is False
        assert result.error_message is not None
        assert "Path traversal detected" in result.error_message


def test_convert_empty_file():
    """Test conversion of empty file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        
        # Create an empty text file
        input_file = workspace / "empty.txt"
        input_file.write_text("", encoding='utf-8')
        
        # Configure settings
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        
        # Convert the file
        result = convert_file(input_file, output_root, config)
        
        # Should succeed but with minimal content
        assert result.success is True
        assert result.output_path.exists()
        output_content = result.output_path.read_text(encoding='utf-8')
        # MarkItDown might add some metadata or formatting
        assert len(output_content) >= 0


def test_convert_file_creates_output_directory():
    """Test that conversion creates output directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "nonexistent" / "output"
        
        # Create a test file
        input_file = workspace / "test.txt"
        input_file.write_text("test content", encoding='utf-8')
        
        # Configure settings
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        
        # Convert the file
        result = convert_file(input_file, output_root, config)
        
        # Should succeed and create output directory
        assert result.success is True
        assert result.output_path.exists()
        assert output_root.exists()
        assert output_root.is_dir()


@patch('markitdesk.converter.MarkItDown')
def test_convert_handles_markitdown_exception(mock_markitdown_class):
    """Test that converter handles MarkItDown exceptions gracefully."""
    # Setup mock to raise an exception
    mock_instance = Mock()
    mock_instance.convert.side_effect = Exception("Conversion failed")
    mock_markitdown_class.return_value = mock_instance
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        
        # Create a test file
        input_file = workspace / "test.txt"
        input_file.write_text("test content", encoding='utf-8')
        
        # Configure settings
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        
        # Convert the file
        result = convert_file(input_file, output_root, config)
        
        # Should fail gracefully
        assert result.success is False
        assert result.error_message == "Conversion failed"
        assert result.text_length == 0
        assert result.duration_ms >= 0


@patch("markitdesk.converter.MarkItDown")
def test_convert_initializes_markitdown_with_plugins_disabled(mock_markitdown_class):
    """Converter should always construct MarkItDown with plugins disabled."""
    mock_instance = Mock()
    mock_instance.convert.return_value = SimpleNamespace(text_content="hello world")
    mock_markitdown_class.return_value = mock_instance

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"

        input_file = workspace / "test.txt"
        input_file.write_text("test content", encoding="utf-8")

        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root

        result = convert_file(input_file, output_root, config)

        assert result.success is True
        mock_markitdown_class.assert_called_once_with(enable_plugins=False)


def test_convert_respects_max_file_size():
    """Test that converter respects max file size setting."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"
        
        # Create a file that exceeds the size limit
        input_file = workspace / "large.txt"
        # Create content larger than 1MB
        large_content = "x" * (2 * 1024 * 1024)  # 2MB
        input_file.write_text(large_content, encoding='utf-8')
        
        # Configure settings with 1MB limit
        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root
        config.max_file_mb = 1  # 1 MB limit
        
        # Convert the file
        result = convert_file(input_file, output_root, config)
        
        # Should fail due to size limit
        assert result.success is False
        assert result.error_message is not None
        assert "File too large" in result.error_message


def test_safe_log_audit_event_swallows_logging_failures():
    """Audit logging helper should never raise back into conversion flow."""
    with patch("markitdesk.converter.log_audit_event", side_effect=RuntimeError("audit down")):
        _safe_log_audit_event(level="info", event_type="test", message="hello")


@patch("markitdesk.converter.log_audit_event", side_effect=RuntimeError("audit down"))
def test_convert_succeeds_even_when_audit_logging_fails(mock_audit_log):
    """Conversion should still succeed if audit logging is unavailable."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workspace = temp_path / "workspace"
        workspace.mkdir()
        output_root = temp_path / "output"

        input_file = workspace / "audit.txt"
        input_file.write_text("audit fallback content", encoding="utf-8")

        config = Settings()
        config.workspace_root = workspace
        config.output_root = output_root

        result = convert_file(input_file, output_root, config)

        assert result.success is True
        assert result.output_path.exists()
        assert mock_audit_log.call_count >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
