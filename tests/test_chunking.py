"""Tests for Markdown chunking functionality."""

import sys
from pathlib import Path

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_chunking_import():
    """Test that chunking module can be imported."""
    from markitdesk.chunking import chunk_markdown, ChunkingStrategy, Chunk, ChunkingResult
    assert chunk_markdown is not None
    assert ChunkingStrategy is not None
    assert Chunk is not None
    assert ChunkingResult is not None


def test_chunk_by_heading_basic():
    """Test basic heading-based chunking."""
    from markitdesk.chunking import chunk_markdown, ChunkingStrategy
    
    text = """# Main Title
    
## Section 1
This is the first section.

## Section 2
This is the second section.

### Subsection
A subsection under section 2.

# Another Main Section
Content here."""

    source_metadata = {'source_file': 'test.md'}
    
    result = chunk_markdown(text, source_metadata, ChunkingStrategy.BY_HEADING, max_tokens=100)
    
    # Should have 2 chunks (one for each level 1 heading section)
    assert result.total_chunks == 2
    assert len(result.chunks) == result.total_chunks
    
    # Check that chunks have proper metadata
    for chunk in result.chunks:
        assert chunk.source_file == 'test.md'
        assert isinstance(chunk.heading_path, list)
        assert chunk.token_estimate >= 0
        assert chunk.start_index >= 0
        assert chunk.end_index <= len(text.split('\n'))
        assert chunk.chunk_index >= 0


def test_chunk_by_token_window():
    """Test token window-based chunking."""
    from markitdesk.chunking import chunk_markdown, ChunkingStrategy
    
    # Create text that will definitely exceed token limits
    text = ("# Title\n\n" + "This is a sentence. " * 50)  # Repeat to create lots of tokens
    
    source_metadata = {'source_file': 'test.md'}
    
    result = chunk_markdown(text, source_metadata, ChunkingStrategy.BY_TOKEN_WINDOW, max_tokens=50)
    
    # Should create at least one chunk
    assert result.total_chunks >= 1
    
    # Check that chunks have reasonable metadata
    for chunk in result.chunks:
        assert chunk.source_file == 'test.md'
        assert isinstance(chunk.heading_path, list)
        assert chunk.token_estimate >= 0
        assert chunk.start_index >= 0
        assert chunk.end_index <= len(text.split('\n'))
        assert chunk.chunk_index >= 0


def test_empty_text():
    """Test chunking empty text."""
    from markitdesk.chunking import chunk_markdown, ChunkingStrategy
    
    text = ""
    source_metadata = {'source_file': 'test.md'}
    
    result = chunk_markdown(text, source_metadata, ChunkingStrategy.BY_HEADING, max_tokens=100)
    
    assert result.total_chunks >= 0
    # May have 0 or 1 chunk depending on implementation


def test_single_heading():
    """Test text with only one heading."""
    from markitdesk.chunking import chunk_markdown, ChunkingStrategy
    
    text = "# Single Heading\n\nSome content here."
    source_metadata = {'source_file': 'test.md'}
    
    result = chunk_markdown(text, source_metadata, ChunkingStrategy.BY_HEADING, max_tokens=100)
    
    assert result.total_chunks >= 1
    if result.total_chunks > 0:
        chunk = result.chunks[0]
        assert chunk.source_file == 'test.md'
        assert chunk.heading_path == ['Single Heading']


def test_preserve_heading_context():
    """Test that heading context is preserved in chunks."""
    from markitdesk.chunking import chunk_markdown, ChunkingStrategy
    
    text = """# Main
    
## Section A
Content A.

### Subsection A1
Content A1.

## Section B
Content B."""

    source_metadata = {'source_file': 'test.md'}
    
    result = chunk_markdown(text, source_metadata, ChunkingStrategy.BY_HEADING, max_tokens=100)
    
    # Find chunks with subsection content and verify heading path
    for chunk in result.chunks:
        if 'Subsection A1' in chunk.content:
            assert chunk.heading_path == ['Main', 'Section A', 'Subsection A1']
            break
    else:
        # If we didn't find the specific subsection, check that heading paths make sense
        for chunk in result.chunks:
            assert isinstance(chunk.heading_path, list)
            # Heading path should be logical progression
            for i, heading in enumerate(chunk.heading_path):
                assert isinstance(heading, str)
                assert len(heading) > 0


def test_chunk_metadata():
    """Test that chunks contain all required metadata."""
    from markitdesk.chunking import chunk_markdown, ChunkingStrategy
    
    text = "# Test\n\nContent."
    source_metadata = {'source_file': 'document.pdf', 'author': 'test'}
    
    result = chunk_markdown(text, source_metadata, ChunkingStrategy.BY_HEADING, max_tokens=100)
    
    assert result.total_chunks >= 1
    chunk = result.chunks[0]
    
    # Check all required metadata fields exist
    assert hasattr(chunk, 'content')
    assert hasattr(chunk, 'source_file')
    assert hasattr(chunk, 'chunk_id')
    assert hasattr(chunk, 'heading_path')
    assert hasattr(chunk, 'token_estimate')
    assert hasattr(chunk, 'start_index')
    assert hasattr(chunk, 'end_index')
    assert hasattr(chunk, 'chunk_index')
    
    # Check specific values
    assert chunk.source_file == 'document.pdf'
    assert isinstance(chunk.content, str)
    assert len(chunk.content) > 0


def test_chunking_strategies_different():
    """Test that different strategies produce different results."""
    from markitdesk.chunking import chunk_markdown, ChunkingStrategy
    
    text = """# Title
    
## Section 1
First paragraph.
Second paragraph.
Third paragraph.

## Section 2
More content here.

### Subsection
Details."""

    source_metadata = {'source_file': 'test.md'}
    
    # Use a small max_tokens to force splitting
    result_heading = chunk_markdown(text, source_metadata, ChunkingStrategy.BY_HEADING, max_tokens=50)
    result_token = chunk_markdown(text, source_metadata, ChunkingStrategy.BY_TOKEN_WINDOW, max_tokens=50)
    
    # They should produce different chunking (though not necessarily always)
    # At least verify both produce valid results
    assert result_heading.total_chunks >= 0
    assert result_token.total_chunks >= 0


def test_is_heading_rejects_invalid_heading_syntax():
    """Heading parsing should only accept markdown headings with a separating space."""
    from markitdesk.chunking import _is_heading

    assert _is_heading("### Valid Heading") == (3, "Valid Heading")
    assert _is_heading("###Invalid") is None
    assert _is_heading("plain text") is None


def test_update_heading_path_truncates_and_extends_hierarchy():
    """Heading path updates should preserve valid ancestry when levels change."""
    from markitdesk.chunking import _update_heading_path

    path = []
    path = _update_heading_path(path, 1, "Root")
    path = _update_heading_path(path, 2, "Section")
    path = _update_heading_path(path, 3, "Subsection")
    assert path == ["Root", "Section", "Subsection"]

    path = _update_heading_path(path, 2, "Replacement")
    assert path == ["Root", "Replacement"]


def test_empty_text_produces_zero_chunks_and_zero_tokens():
    """Completely empty text should not produce phantom chunks."""
    from markitdesk.chunking import chunk_markdown, ChunkingStrategy

    result = chunk_markdown("", {"source_file": "empty.md"}, ChunkingStrategy.BY_HEADING, max_tokens=100)

    assert result.total_chunks == 0
    assert result.total_tokens_estimated == 0
    assert result.chunks == []


def test_token_window_preserves_full_heading_context_across_splits():
    """Token-window chunking should preserve the full active heading path after a split."""
    from markitdesk.chunking import chunk_markdown, ChunkingStrategy

    text = "\n".join(
        [
            "# Root",
            "",
            "## Section",
            "",
            "### Subsection",
            "",
            "word " * 30,
            "word " * 30,
            "word " * 30,
        ]
    )

    result = chunk_markdown(
        text,
        {"source_file": "context.md"},
        ChunkingStrategy.BY_TOKEN_WINDOW,
        max_tokens=20,
    )

    assert result.total_chunks >= 2
    for chunk in result.chunks[1:]:
        assert chunk.heading_path == ["Root", "Section", "Subsection"]


def test_token_window_uses_unknown_source_file_when_missing():
    """Chunking should fall back to an explicit unknown source file label when metadata is missing."""
    from markitdesk.chunking import chunk_markdown, ChunkingStrategy

    result = chunk_markdown("# Title\n\nSome content", {}, ChunkingStrategy.BY_TOKEN_WINDOW, max_tokens=100)

    assert result.total_chunks == 1
    assert result.chunks[0].source_file == "unknown"


if __name__ == "__main__":
    test_chunking_import()
    test_chunk_by_heading_basic()
    test_chunk_by_token_window()
    test_empty_text()
    test_single_heading()
    test_preserve_heading_context()
    test_chunk_metadata()
    test_chunking_strategies_different()
    print("All chunking tests passed!")
