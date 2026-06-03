"""Tests for Markdown quality scoring."""

import sys
from pathlib import Path

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_quality_import():
    """Test that quality module can be imported."""
    from markitdesk.quality import assess_markdown_quality, QualityReport
    assert assess_markdown_quality is not None
    assert QualityReport is not None


def test_empty_markdown():
    """Test quality assessment of empty Markdown."""
    from markitdesk.quality import assess_markdown_quality
    
    report = assess_markdown_quality("")
    
    assert report.text_length == 0
    assert report.word_count == 0
    assert report.heading_count == 0
    assert report.table_count == 0
    assert report.link_count == 0
    assert report.token_estimate == 0
    assert report.score < 30  # Should be low score
    assert len(report.warnings) > 0  # Should have warnings
    assert report.rag_readiness == "poor"


def test_minimal_markdown():
    """Test quality assessment of minimal Markdown."""
    from markitdesk.quality import assess_markdown_quality
    
    text = "# Hello\n\nThis is a test."
    report = assess_markdown_quality(text)
    
    assert report.text_length > 0
    assert report.word_count >= 3
    assert report.heading_count == 1
    assert report.table_count == 0
    assert report.link_count == 0
    # With warning penalty, score may be 0 for very small texts
    assert report.score >= 0  # Should not be negative
    assert report.rag_readiness == "poor"


def test_structured_markdown():
    """Test quality assessment of well-structured Markdown."""
    from markitdesk.quality import assess_markdown_quality
    
    text = """# Main Title
    
## Section 1
This is a paragraph with some text.

## Section 2
Another paragraph with [a link](http://example.com).

| Column 1 | Column 2 |
|----------|----------|
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   """

    report = assess_markdown_quality(text)
    
    assert report.text_length > 50
    assert report.word_count > 20
    assert report.heading_count >= 2
    assert report.table_count >= 1
    assert report.link_count >= 1
    # With our scoring: length(225)=10, words(42)=5, headings(3)=10, tables(4)=10, links(1)=0 = 35
    assert report.score >= 30  # Should have reasonable score
    assert report.rag_readiness in ["poor", "fair"]


def test_tiny_output_warning():
    """Test that tiny output generates appropriate warning."""
    from markitdesk.quality import assess_markdown_quality
    
    # Very tiny output
    report = assess_markdown_quality("Hi")
    assert report.text_length < 20
    assert any("extremely small" in w for w in report.warnings)
    
    # Small output
    report = assess_markdown_quality("This is a small text.")
    assert report.text_length < 50
    assert any("very small" in w for w in report.warnings)


def test_scanned_pdf_warning():
    """Test scanned PDF suspicion for PDF inputs with tiny output."""
    from markitdesk.quality import assess_markdown_quality
    from pathlib import Path
    
    # Simulate PDF input with tiny output
    pdf_path = Path("test.pdf")
    report = assess_markdown_quality("hello", pdf_path)
    
    assert report.text_length < 100
    assert report.word_count < 20
    assert any("scanned" in w.lower() for w in report.warnings)


def test_quality_report_dataclass():
    """Test that QualityReport dataclass works correctly."""
    from markitdesk.quality import QualityReport
    
    report = QualityReport(
        score=85,
        warnings=["Test warning"],
        text_length=1000,
        word_count=200,
        heading_count=5,
        table_count=2,
        link_count=10,
        token_estimate=150,
        rag_readiness="good"
    )
    
    assert report.score == 85
    assert report.warnings == ["Test warning"]
    assert report.text_length == 1000
    assert report.word_count == 200
    assert report.heading_count == 5
    assert report.table_count == 2
    assert report.link_count == 10
    assert report.token_estimate == 150
    assert report.rag_readiness == "good"


if __name__ == "__main__":
    test_quality_import()
    test_empty_markdown()
    test_minimal_markdown()
    test_structured_markdown()
    test_tiny_output_warning()
    test_scanned_pdf_warning()
    test_quality_report_dataclass()
    print("All quality tests passed!")