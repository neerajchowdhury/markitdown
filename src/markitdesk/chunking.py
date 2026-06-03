"""Deterministic Markdown chunking utilities for RAG exports."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
from enum import Enum


class ChunkingStrategy(Enum):
    """Available chunking strategies."""
    BY_HEADING = "by_heading"
    BY_TOKEN_WINDOW = "by_token_window"


@dataclass
class Chunk:
    """A chunk of Markdown text with associated metadata."""
    content: str
    source_file: str
    chunk_id: int
    heading_path: List[str]
    token_estimate: int
    start_index: int
    end_index: int
    chunk_index: int  # Index within the chunked document


@dataclass
class ChunkingResult:
    """Result of chunking a Markdown document."""
    chunks: List[Chunk]
    total_chunks: int
    total_tokens_estimated: int


def _estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in text.
    Using rough approximation: 0.75 tokens per word for English.
    
    Args:
        text: Text to estimate tokens for
        
    Returns:
        Estimated token count
    """
    word_count = len(text.split()) if text.strip() else 0
    return int(word_count * 0.75)


def _is_heading(line: str) -> Optional[tuple[int, str]]:
    """
    Check if a line is a markdown heading and return its level and text.
    
    Args:
        line: Line to check
        
    Returns:
        Tuple of (level, heading_text) if line is a heading, None otherwise
    """
    if not line.startswith('#'):
        return None
    
    # Count leading # characters
    level = 0
    for char in line:
        if char == '#':
            level += 1
        else:
            break
    
    # Check if it's a valid heading (has space after #s)
    if level == 0 or len(line) <= level or line[level] != ' ':
        return None
    
    heading_text = line[level+1:].strip()
    return (level, heading_text)


def _update_heading_path(current_path: List[str], level: int, heading_text: str) -> List[str]:
    """
    Update heading path based on a new heading.
    
    Args:
        current_path: Current heading path
        level: Heading level (1-based)
        heading_text: Heading text
        
    Returns:
        Updated heading path
    """
    if level <= len(current_path):
        # Same or higher level - truncate and add new heading
        return current_path[:level-1] + [heading_text]
    else:
        # Deeper level - append new heading
        return current_path + [heading_text]


def _rebuild_heading_path(lines: List[str], end_index: int, lookback: int = 100) -> List[str]:
    """
    Rebuild the active heading path from prior lines.

    Args:
        lines: Full document lines
        end_index: Exclusive upper bound to inspect
        lookback: Maximum number of lines to inspect backward from end_index

    Returns:
        Heading path active at end_index.
    """
    start_index = max(0, end_index - lookback)
    heading_path: List[str] = []
    for line in lines[start_index:end_index]:
        heading_info = _is_heading(line)
        if heading_info:
            level, heading_text = heading_info
            heading_path = _update_heading_path(heading_path, level, heading_text)
    return heading_path


def chunk_markdown(
    text: str, 
    source_metadata: Dict[str, Any],
    strategy: ChunkingStrategy = ChunkingStrategy.BY_HEADING,
    max_tokens: int = 500
) -> ChunkingResult:
    """
    Chunk Markdown text according to the specified strategy.
    
    Args:
        text: Markdown text to chunk
        source_metadata: Metadata about the source file (should include source_file)
        strategy: Chunking strategy to use
        max_tokens: Maximum tokens per chunk
        
    Returns:
        ChunkingResult containing list of chunks
    """
    if strategy == ChunkingStrategy.BY_HEADING:
        return _chunk_by_heading(text, source_metadata, max_tokens)
    elif strategy == ChunkingStrategy.BY_TOKEN_WINDOW:
        return _chunk_by_token_window(text, source_metadata, max_tokens)
    else:
        raise ValueError(f"Unknown chunking strategy: {strategy}")


def _chunk_by_heading(
    text: str, 
    source_metadata: Dict[str, Any],
    max_tokens: int
) -> ChunkingResult:
    """
    Chunk markdown by headings, preserving heading context.
    
    Args:
        text: Markdown text to chunk
        source_metadata: Metadata about the source file
        max_tokens: Maximum tokens per chunk
        
    Returns:
        ChunkingResult containing list of chunks
    """
    lines = text.split('\n')
    
    # Find all headings with their positions and levels
    headings = []
    for i, line in enumerate(lines):
        heading_info = _is_heading(line)
        if heading_info:
            level, heading_text = heading_info
            headings.append((i, level, heading_text))

    # If no headings found, treat entire text as one chunk
    if not headings:
        chunk_content = text
        chunk_tokens = _estimate_tokens(chunk_content)
        chunk = Chunk(
            content=chunk_content,
            source_file=source_metadata.get('source_file', 'unknown'),
            chunk_id=hash(chunk_content) % 1000000,
            heading_path=[],
            token_estimate=chunk_tokens,
            start_index=0,
            end_index=len(lines),
            chunk_index=0
        )
        chunks = [chunk] if chunk_content.strip() else []
    else:
        # Group content by top-level sections while preserving nested context.
        chunks = []
        current_chunk_lines = []
        current_heading_path: List[str] = []
        current_start_index = 0
        chunk_index = 0
        saw_nested_heading = False

        for i, line in enumerate(lines):
            heading_info = _is_heading(line)
            if heading_info and heading_info[0] <= 2 and current_chunk_lines and saw_nested_heading:
                chunk_content = '\n'.join(current_chunk_lines)
                if chunk_content.strip():
                    chunk_tokens = _estimate_tokens(chunk_content)
                    chunk = Chunk(
                        content=chunk_content,
                        source_file=source_metadata.get('source_file', 'unknown'),
                        chunk_id=hash(chunk_content) % 1000000,
                        heading_path=list(current_heading_path),
                        token_estimate=chunk_tokens,
                        start_index=current_start_index,
                        end_index=i,
                        chunk_index=chunk_index
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                current_chunk_lines = []
                current_start_index = i
                current_heading_path = current_heading_path[:1]
                saw_nested_heading = False

            if heading_info:
                level, heading_text = heading_info
                current_heading_path = _update_heading_path(current_heading_path, level, heading_text)
                if level >= 3:
                    saw_nested_heading = True

            current_chunk_lines.append(line)

        if current_chunk_lines:
            chunk_content = '\n'.join(current_chunk_lines)
            if chunk_content.strip():
                chunk_tokens = _estimate_tokens(chunk_content)
                chunk = Chunk(
                    content=chunk_content,
                    source_file=source_metadata.get('source_file', 'unknown'),
                    chunk_id=hash(chunk_content) % 1000000,
                    heading_path=list(current_heading_path),
                    token_estimate=chunk_tokens,
                    start_index=current_start_index,
                    end_index=len(lines),
                    chunk_index=chunk_index
                )
                chunks.append(chunk)
    
    # Calculate totals
    total_chunks = len(chunks)
    total_tokens_estimated = sum(chunk.token_estimate for chunk in chunks)
    
    return ChunkingResult(
        chunks=chunks,
        total_chunks=total_chunks,
        total_tokens_estimated=total_tokens_estimated
    )


def _chunk_by_token_window(
    text: str, 
    source_metadata: Dict[str, Any],
    max_tokens: int
) -> ChunkingResult:
    """
    Chunk markdown using a sliding token window approach.
    
    Args:
        text: Markdown text to chunk
        source_metadata: Metadata about the source file
        max_tokens: Maximum tokens per chunk
        
    Returns:
        ChunkingResult containing list of chunks
    """
    lines = text.split('\n')
    chunks = []
    
    current_chunk_lines = []
    current_token_count = 0
    current_start_index = 0
    chunk_index = 0
    current_heading_path = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        line_tokens = _estimate_tokens(line)
        
        # Check if adding this line would exceed max_tokens
        if current_token_count + line_tokens > max_tokens and current_chunk_lines:
            # Create chunk from current content
            chunk_content = '\n'.join(current_chunk_lines)
            if chunk_content.strip():  # Only create non-empty chunks
                chunk = Chunk(
                    content=chunk_content,
                    source_file=source_metadata.get('source_file', 'unknown'),
                    chunk_id=hash(chunk_content) % 1000000,
                    heading_path=list(current_heading_path),
                    token_estimate=current_token_count,
                    start_index=current_start_index,
                    end_index=i,
                    chunk_index=chunk_index
                )
                chunks.append(chunk)
                chunk_index += 1
            
            # Reset for next chunk
            current_chunk_lines = []
            current_token_count = 0
            current_start_index = i
            
            # Re-evaluate heading path for the new chunk.
            current_heading_path = _rebuild_heading_path(lines, i)
        
        # Add line to current chunk
        current_chunk_lines.append(line)
        current_token_count += line_tokens
        
        # Update heading path if this line is a heading
        heading_info = _is_heading(line)
        if heading_info:
            level, heading_text = heading_info
            current_heading_path = _update_heading_path(current_heading_path, level, heading_text)
        
        i += 1
    
    # Handle remaining content
    if current_chunk_lines:
        chunk_content = '\n'.join(current_chunk_lines)
        if chunk_content.strip():  # Only create non-empty chunks
            chunk = Chunk(
                content=chunk_content,
                source_file=source_metadata.get('source_file', 'unknown'),
                chunk_id=hash(chunk_content) % 1000000,
                heading_path=list(current_heading_path),
                token_estimate=current_token_count,
                start_index=current_start_index,
                end_index=len(lines),
                chunk_index=chunk_index
            )
            chunks.append(chunk)
    
    # Calculate totals
    total_chunks = len(chunks)
    total_tokens_estimated = sum(chunk.token_estimate for chunk in chunks)
    
    return ChunkingResult(
        chunks=chunks,
        total_chunks=total_chunks,
        total_tokens_estimated=total_tokens_estimated
    )
