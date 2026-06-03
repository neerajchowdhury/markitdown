"""Conversion utilities wrapping MarkItDown."""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from types import SimpleNamespace

try:
    from markitdown import MarkItDown
except ImportError:
    class MarkItDown:  # type: ignore[override]
        """Minimal local fallback used when the markitdown package is absent."""

        def __init__(self, enable_plugins: bool = False):
            self.enable_plugins = enable_plugins

        def convert(self, source_path: str):
            return SimpleNamespace(text_content=Path(source_path).read_text(encoding="utf-8"))

from .config import Settings
from .security import ValidationResult, validate_input_file, safe_output_path
from .quality import assess_markdown_quality, QualityReport
from .audit import log_audit_event


def _safe_log_audit_event(**kwargs) -> None:
    """Best-effort audit logging that never changes conversion outcome."""
    try:
        log_audit_event(**kwargs)
    except Exception:
        pass


@dataclass
class ConversionResult:
    """Result of a file conversion operation."""
    source_path: Path
    output_path: Path
    success: bool
    text_length: int = 0
    error_message: Optional[str] = None
    duration_ms: int = 0
    quality_report: Optional['QualityReport'] = None


def convert_file(input_path: Path, output_root: Path, config: Settings) -> ConversionResult:
    """
    Convert a file to Markdown using MarkItDown.
    
    Args:
        input_path: Path to the input file
        output_root: Root directory for output files
        config: Application configuration
        
    Returns:
        ConversionResult with conversion details
    """
    start_time = time.time()
    
    # Validate input file
    validation_result = validate_input_file(input_path, config)
    if not validation_result.is_valid:
        # Log validation failure
        _safe_log_audit_event(
            level="warning",
            event_type="validation_failed",
            message=f"Validation failed for {input_path.name}: {validation_result.error_message}",
            source_path=input_path,
            metadata={"error": validation_result.error_message}
        )
        return ConversionResult(
            source_path=input_path,
            output_path=Path(),
            success=False,
            error_message=validation_result.error_message,
            duration_ms=int((time.time() - start_time) * 1000)
        )
    
    # Log conversion started
    _safe_log_audit_event(
        level="info",
        event_type="conversion_started",
        message=f"Starting conversion of {input_path.name}",
        source_path=input_path
    )
    
    # Determine safe output path
    output_path = safe_output_path(input_path, output_root)
    
    # Initialize MarkItDown with plugins disabled (security requirement)
    try:
        markitdown = MarkItDown(enable_plugins=False)
        
        # Perform conversion
        result = markitdown.convert(str(input_path))
        
        # Write Markdown output to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.text_content, encoding='utf-8')
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Assess quality of the conversion
        quality_report = assess_markdown_quality(result.text_content, input_path)

        # Log successful conversion
        _safe_log_audit_event(
            level="info",
            event_type="conversion_done",
            message=f"Conversion completed for {input_path.name}: {len(result.text_content)} characters",
            source_path=input_path,
            metadata={
                "text_length": len(result.text_content),
                "duration_ms": duration_ms,
                "quality_score": quality_report.score if quality_report else 0
            }
        )
        
        return ConversionResult(
            source_path=input_path,
            output_path=output_path,
            success=True,
            text_length=len(result.text_content),
            duration_ms=duration_ms,
            quality_report=quality_report
        )
        
    except Exception as e:
        # Calculate duration even on failure
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log conversion failure
        _safe_log_audit_event(
            level="error",
            event_type="conversion_failed",
            message=f"Conversion failed for {input_path.name}: {str(e)}",
            source_path=input_path,
            metadata={"error": str(e), "duration_ms": duration_ms}
        )
        
        return ConversionResult(
            source_path=input_path,
            output_path=output_path,
            success=False,
            error_message=str(e),
            duration_ms=duration_ms
        )
