"""Markdown quality scoring utilities."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class QualityReport:
    """Report on the quality of converted Markdown."""
    score: int  # 0-100
    warnings: List[str] = field(default_factory=list)
    text_length: int = 0
    word_count: int = 0
    heading_count: int = 0
    table_count: int = 0
    link_count: int = 0
    token_estimate: int = 0
    rag_readiness: str = "poor"  # poor, fair, good


def assess_markdown_quality(text: str, source_path: Optional[Path] = None) -> QualityReport:
    """
    Assess the quality of Markdown text.
    
    Args:
        text: The Markdown text to assess
        source_path: Optional source file path (for context-specific checks)
        
    Returns:
        QualityReport with score and metrics
    """
    warnings = []
    
    # Basic metrics
    text_length = len(text)
    word_count = len(text.split()) if text.strip() else 0
    
    # Count Markdown elements
    heading_count = len(re.findall(r'^#{1,6}\s+.+', text, re.MULTILINE))
    # Simple table detection (lines with | characters)
    table_count = len([line for line in text.split('\n') if '|' in line and line.count('|') >= 2])
    # Count Markdown links [text](url)
    link_count = len(re.findall(r'\[([^\]]+)\]\([^\)]+\)', text))
    
    # Rough token estimate (approximately 0.75 tokens per word for English)
    token_estimate = int(word_count * 0.75)
    
    # Initialize score
    score = 0
    
    # Length scoring (0-30 points)
    if text_length >= 1000:
        score += 30
    elif text_length >= 500:
        score += 20
    elif text_length >= 100:
        score += 10
    elif text_length >= 50:
        score += 5
    
    # Word count scoring (0-20 points)
    if word_count >= 200:
        score += 20
    elif word_count >= 100:
        score += 15
    elif word_count >= 50:
        score += 10
    elif word_count >= 20:
        score += 5
    
    # Heading count scoring (0-20 points)
    if heading_count >= 10:
        score += 20
    elif heading_count >= 5:
        score += 15
    elif heading_count >= 3:
        score += 10
    elif heading_count >= 1:
        score += 5
    
    # Table count scoring (0-15 points)
    if table_count >= 5:
        score += 15
    elif table_count >= 3:
        score += 10
    elif table_count >= 1:
        score += 5
    
    # Link count scoring (0-15 points)
    if link_count >= 20:
        score += 15
    elif link_count >= 10:
        score += 10
    elif link_count >= 5:
        score += 5
    
    # Apply warnings and adjust score/readiness
    
    # Empty or tiny output warning
    if text_length < 20:
        warnings.append("Output is extremely small (< 20 characters)")
        score = max(0, score - 20)  # Penalty for tiny output
    elif text_length < 50:
        warnings.append("Output is very small (< 50 characters)")
        score = max(0, score - 10)
    
    # Suspected scanned PDF warning
    if source_path and source_path.suffix.lower() == '.pdf':
        if text_length < 100 and word_count < 20:
            warnings.append("PDF input produced very little text - possibly a scanned/image-based PDF")
            score = max(0, score - 15)
    
    # No structure warning
    if heading_count == 0 and text_length > 200:
        warnings.append("No headings detected in substantial output - consider adding structure")
        score = max(0, score - 10)
    
    # Very low link density warning for long texts
    if word_count > 300 and link_count == 0:
        warnings.append("No links detected in substantial output - may lack references")
        score = max(0, score - 5)
    
    # Ensure score is in valid range
    score = max(0, min(100, score))
    
    # Determine RAG readiness
    if score >= 80:
        rag_readiness = "good"
    elif score >= 50:
        rag_readiness = "fair"
    else:
        rag_readiness = "poor"
    
    return QualityReport(
        score=score,
        warnings=warnings,
        text_length=text_length,
        word_count=word_count,
        heading_count=heading_count,
        table_count=table_count,
        link_count=link_count,
        token_estimate=token_estimate,
        rag_readiness=rag_readiness
    )