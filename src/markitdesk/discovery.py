"""File discovery utilities for finding supported files in directories and ZIP archives."""

import zipfile
import os
from pathlib import Path
from typing import List, Union, Optional
from .config import Settings
from .security import resolve_inside_base, ValidationResult
from .audit import log_audit_event
from .recipes import load_recipe


def is_hidden_or_system_path(path: Path, base_dir: Path) -> bool:
    """
    Check if a path should be skipped as hidden or system file/directory.
    
    Args:
        path: Path to check
        base_dir: Base directory for relative path calculation
        
    Returns:
        True if path should be skipped
    """
    try:
        # Get relative path from base
        relative_path = path.relative_to(base_dir)
        
        # Check if any component starts with . (hidden)
        for part in relative_path.parts:
            if part.startswith('.'):
                return True
                
        # Check for common system directories to skip
        system_dirs = {'__pycache__', 'node_modules', '.git', '.svn', '.hg'}
        if any(part in system_dirs for part in relative_path.parts):
            return True
            
        return False
    except ValueError:
        # Path is not relative to base_dir
        return False


def get_allowed_extensions(recipe_name: Optional[str] = None) -> set:
    """
    Get the set of allowed file extensions for processing.
    
    Args:
        recipe_name: Optional recipe name to get recipe-specific extensions
        
    Returns:
        Set of allowed file extensions (lowercase, including dot)
    """
    if recipe_name:
        recipe = load_recipe(recipe_name)
        if recipe and recipe.allowed_extensions:
            return set(recipe.allowed_extensions)
    
    # Default extensions
    return {
        '.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv', '.json', '.xml',
        '.html', '.htm', '.txt', '.md', '.zip', '.epub', '.jpg', '.jpeg',
        '.png', '.webp', '.mp3', '.wav'
    }


def discover_files(paths: List[Union[str, Path]], config: Settings, recipe_name: Optional[str] = None) -> List[Path]:
    """
    Discover supported files from a list of paths (files and directories).
    
    Args:
        paths: List of file or directory paths to scan
        config: Application configuration
        recipe_name: Optional recipe name to determine allowed extensions
        
    Returns:
        Sorted list of discovered file paths that are valid for processing
    """
    discovered_files = []
    allowed_extensions = get_allowed_extensions(recipe_name)
    
    for path_item in paths:
        path_obj = Path(path_item)
        
        try:
            # Validate that the path is inside workspace
            resolved_path = resolve_inside_base(path_obj, config.workspace_root)
            
            if resolved_path.is_file():
                # Check if it's a supported file type
                if resolved_path.suffix.lower() in allowed_extensions:
                    discovered_files.append(resolved_path)
                    # Log file registered
                    log_audit_event(
                        level="info",
                        event_type="file_registered",
                        message=f"File registered for processing: {resolved_path.name}",
                        source_path=resolved_path,
                        metadata={"file_type": resolved_path.suffix.lower(), "size": resolved_path.stat().st_size if resolved_path.exists() else 0}
                    )
            elif resolved_path.is_dir():
                # Recursively scan directory
                for file_path in resolved_path.rglob('*'):
                    if file_path.is_file():
                        try:
                            resolved_file = resolve_inside_base(file_path, config.workspace_root)
                        except (ValueError, FileNotFoundError):
                            log_audit_event(
                                level="warning",
                                event_type="security_violation",
                                message=f"File skipped outside workspace: {file_path.name}",
                                source_path=file_path,
                                metadata={"reason": "workspace_escape"}
                            )
                            continue

                        # Skip hidden/system paths
                        if is_hidden_or_system_path(file_path, config.workspace_root):
                            # Log security violation for hidden/system paths
                            log_audit_event(
                                level="warning",
                                event_type="security_violation",
                                message=f"Hidden/system file skipped: {file_path.name}",
                                source_path=file_path,
                                metadata={"reason": "hidden_or_system_path"}
                            )
                            continue
                            
                        # Check if it's a supported file type
                        if resolved_file.suffix.lower() in allowed_extensions:
                            discovered_files.append(resolved_file)
                            # Log file registered
                            log_audit_event(
                                level="info",
                                event_type="file_registered",
                                message=f"File registered for processing: {resolved_file.name}",
                                source_path=resolved_file,
                                metadata={"file_type": resolved_file.suffix.lower(), "size": resolved_file.stat().st_size if resolved_file.exists() else 0}
                            )
        except (ValueError, FileNotFoundError):
            # Skip invalid paths (will be handled by validation later)
            continue
    
    # Remove duplicates and sort for deterministic output
    unique_files = list(dict.fromkeys(discovered_files))  # Preserves order while removing duplicates
    unique_files.sort(key=lambda p: str(p).lower())  # Case-insensitive sort
    
    return unique_files


def discover_files_from_zip(zip_path: Path, config: Settings, recipe_name: Optional[str] = None) -> List[Path]:
    """
    Safely discover files inside a ZIP archive.
    
    Args:
        zip_path: Path to the ZIP file
        config: Application configuration
        recipe_name: Optional recipe name to determine allowed extensions and extraction decision
        
    Returns:
        List of discovered file paths extracted to workspace/extracted/{zip_stem}/
        
    Raises:
        ValueError: If ZIP file is invalid or security constraints violated
        zipfile.BadZipFile: If ZIP file is corrupted
    """
    # Security limits from config (with defaults if not present)
    max_zip_files = getattr(config, 'max_zip_files', 500)
    max_zip_uncompressed_mb = getattr(config, 'max_zip_uncompressed_mb', 500)
    allow_zip_extract = getattr(config, 'allow_zip_extract', True)
    
    # Override allow_zip_extract with recipe setting if recipe provides it
    if recipe_name:
        recipe = load_recipe(recipe_name)
        if recipe is not None:
            allow_zip_extract = recipe.extract_zip
    
    if not allow_zip_extract:
        # Log ZIP extraction rejected due to configuration
        log_audit_event(
            level="warning",
            event_type="zip_extract_rejected",
            message=f"ZIP extraction rejected for {zip_path.name}: ZIP extraction is disabled",
            source_path=zip_path,
            metadata={"reason": "zip_extraction_disabled"}
        )
        raise ValueError("ZIP extraction is disabled")
    
    # Validate the ZIP file itself
    try:
        zip_path_resolved = resolve_inside_base(zip_path, config.workspace_root)
    except (ValueError, FileNotFoundError):
        # Log security violation for invalid ZIP path
        log_audit_event(
            level="warning",
            event_type="security_violation",
            message=f"Invalid ZIP file path: {zip_path}",
            source_path=zip_path,
            metadata={"reason": "invalid_path"}
        )
        raise ValueError(f"Invalid ZIP file path: {zip_path}")
    
    # Create extraction directory
    extract_dir = config.workspace_root / "extracted" / zip_path_resolved.stem
    extract_dir.mkdir(parents=True, exist_ok=True)
    
    # Log ZIP extraction started
    log_audit_event(
        level="info",
        event_type="zip_extract_started",
        message=f"Starting ZIP extraction for {zip_path.name}",
        source_path=zip_path,
        metadata={"extract_dir": str(extract_dir)}
    )
    
    discovered_files = []
    allowed_extensions = get_allowed_extensions(recipe_name)
    
    try:
        with zipfile.ZipFile(zip_path_resolved, 'r') as zip_file:
            # Get file list and validate
            file_list = zip_file.infolist()
            
            # Check file count limit
            if len(file_list) > max_zip_files:
                # Log security violation for too many files
                log_audit_event(
                    level="warning",
                    event_type="security_violation",
                    message=f"ZIP file contains too many files: {len(file_list)} > {max_zip_files}",
                    source_path=zip_path,
                    metadata={"file_count": len(file_list), "limit": max_zip_files}
                )
                raise ValueError(f"ZIP file contains too many files: {len(file_list)} > {max_zip_files}")
            
            # Calculate total uncompressed size and check limit
            total_uncompressed_size = sum(info.file_size for info in file_list)
            total_uncompressed_mb = total_uncompressed_size / (1024 * 1024)
            
            if total_uncompressed_mb > max_zip_uncompressed_mb:
                # Log security violation for too large ZIP
                log_audit_event(
                    level="warning",
                    event_type="security_violation",
                    message=f"ZIP file uncompressed size too large: {total_uncompressed_mb:.2f} MB > {max_zip_uncompressed_mb} MB",
                    source_path=zip_path,
                    metadata={"size_mb": total_uncompressed_mb, "limit_mb": max_zip_uncompressed_mb}
                )
                raise ValueError(f"ZIP file uncompressed size too large: {total_uncompressed_mb:.2f} MB > {max_zip_uncompressed_mb} MB")
            
            # Check decompression ratio (crude ZIP bomb detection)
            compressed_size = sum(info.compress_size for info in file_list)
            if compressed_size > 0:
                ratio = total_uncompressed_size / compressed_size
                if ratio > 100:  # More than 100:1 compression ratio is suspicious
                    # Log security violation for ZIP bomb
                    log_audit_event(
                        level="warning",
                        event_type="security_violation",
                        message=f"ZIP file decompression ratio too high: {ratio:.2f}:1 (possible ZIP bomb)",
                        source_path=zip_path,
                        metadata={"ratio": ratio, "threshold": 100}
                    )
                    raise ValueError(f"ZIP file decompression ratio too high: {ratio:.2f}:1 (possible ZIP bomb)")
            
            # Process each file in the ZIP
            for zip_info in file_list:
                # Skip directories
                if zip_info.is_dir():
                    continue

                # Enforce per-file size limits before extraction
                max_file_bytes = getattr(config, 'max_file_mb', 100) * 1024 * 1024
                if zip_info.file_size > max_file_bytes:
                    log_audit_event(
                        level="warning",
                        event_type="security_violation",
                        message=f"ZIP member too large: {zip_info.filename}",
                        source_path=zip_path,
                        metadata={"file_in_zip": zip_info.filename, "reason": "oversized_member", "size_bytes": zip_info.file_size, "limit_bytes": max_file_bytes}
                    )
                    raise ValueError(f"ZIP member too large: {zip_info.filename}")
                    
                # Skip hidden/system files
                # Skip entries that start with . (hidden files) but allow .. and . as special cases
                zip_path_obj = Path(zip_info.filename)
                skip_entry = False
                for part in zip_path_obj.parts:
                    # Skip if part starts with . but is not exactly "." or ".."
                    if part.startswith('.') and part not in ['.', '..']:
                        skip_entry = True
                        break
                if skip_entry:
                    # Log security violation for hidden/system file in ZIP
                    log_audit_event(
                        level="warning",
                        event_type="security_violation",
                        message=f"Hidden/system file skipped in ZIP: {zip_info.filename}",
                        source_path=zip_path,
                        metadata={"file_in_zip": zip_info.filename, "reason": "hidden_or_system_path"}
                    )
                    continue
                
                # Security checks on filename
                # Check for absolute paths
                if zip_info.filename.startswith('/') or (len(zip_info.filename) > 2 and zip_info.filename[1:3] == ':\\'):
                    # Log security violation for absolute path in ZIP
                    log_audit_event(
                        level="warning",
                        event_type="security_violation",
                        message=f"ZIP contains absolute path: {zip_info.filename}",
                        source_path=zip_path,
                        metadata={"file_in_zip": zip_info.filename, "reason": "absolute_path"}
                    )
                    raise ValueError(f"ZIP contains absolute path: {zip_info.filename}")
                
                # Check for path traversal
                normalized = os.path.normpath(zip_info.filename)
                if normalized.startswith('..') or '/../' in normalized or '\\..\\' in normalized:
                    # Log security violation for path traversal in ZIP
                    log_audit_event(
                        level="warning",
                        event_type="security_violation",
                        message=f"ZIP contains path traversal: {zip_info.filename}",
                        source_path=zip_path,
                        metadata={"file_in_zip": zip_info.filename, "reason": "path_traversal"}
                    )
                    raise ValueError(f"ZIP contains path traversal: {zip_info.filename}")
                
                # Additional check for paths that start with .. after normalization
                # Handle cases like "..\\file" or "../file"
                if normalized.startswith('..') or normalized.startswith('..' + os.sep):
                    # Log security violation for path traversal in ZIP
                    log_audit_event(
                        level="warning",
                        event_type="security_violation",
                        message=f"ZIP contains path traversal: {zip_info.filename}",
                        source_path=zip_path,
                        metadata={"file_in_zip": zip_info.filename, "reason": "path_traversal"}
                    )
                    raise ValueError(f"ZIP contains path traversal: {zip_info.filename}")
                
                # Construct safe extraction path
                safe_filename = os.path.basename(zip_info.filename)  # Only use filename, ignore directory structure for simplicity
                if not safe_filename:
                    continue  # Skip empty filenames
                
                # Check extension
                if Path(safe_filename).suffix.lower() not in allowed_extensions:
                    # Log skipped unsupported file type in ZIP
                    log_audit_event(
                        level="debug",
                        event_type="security_violation",
                        message=f"Unsupported file type skipped in ZIP: {safe_filename}",
                        source_path=zip_path,
                        metadata={"file_in_zip": zip_info.filename, "reason": "unsupported_type", "extension": Path(safe_filename).suffix.lower()}
                    )
                    continue  # Skip unsupported file types
                
                extract_path = extract_dir / safe_filename
                
                # Prevent overwrites by adding counter if needed
                counter = 1
                original_extract_path = extract_path
                while extract_path.exists():
                    stem = original_extract_path.stem
                    suffix = original_extract_path.suffix
                    extract_path = extract_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
                
                # Extract the file
                with zip_file.open(zip_info) as source, open(extract_path, "wb") as target:
                    target.write(source.read())
                
                # Validate the extracted file is inside workspace (should be by construction)
                try:
                    resolve_inside_base(extract_path, config.workspace_root)
                    discovered_files.append(extract_path)
                    
                    # Log successful extraction of file from ZIP
                    log_audit_event(
                        level="info",
                        event_type="file_registered",
                        message=f"File extracted from ZIP registered for processing: {safe_filename}",
                        source_path=extract_path,
                        metadata={
                            "file_type": Path(safe_filename).suffix.lower(),
                            "size": extract_path.stat().st_size if extract_path.exists() else 0,
                            "extracted_from_zip": zip_path.name,
                            "original_zip_path": zip_info.filename
                        }
                    )
                except ValueError:
                    # This shouldn't happen, but clean up if it does
                    if extract_path.exists():
                        extract_path.unlink()
                    # Log security violation for extracted file escaping workspace
                    log_audit_event(
                        level="warning",
                        event_type="security_violation",
                        message=f"Extracted file escapes workspace: {extract_path}",
                        source_path=zip_path,
                        metadata={"file_in_zip": zip_info.filename, "extracted_path": str(extract_path), "reason": "path_escape"}
                    )
                    raise ValueError(f"Extracted file escapes workspace: {extract_path}")
    
    except zipfile.BadZipFile:
        # Log security violation for invalid/corrupted ZIP
        log_audit_event(
            level="warning",
            event_type="security_violation",
            message=f"Invalid or corrupted ZIP file: {zip_path}",
            source_path=zip_path,
            metadata={"reason": "bad_zip_file"}
        )
        raise zipfile.BadZipFile(f"Invalid or corrupted ZIP file: {zip_path}")
    
    # Log ZIP extraction completed
    log_audit_event(
        level="info",
        event_type="zip_extract_started",  # Note: This should probably be a different event type, but keeping as is for now
        message=f"ZIP extraction completed for {zip_path.name}: {len(discovered_files)} files extracted",
        source_path=zip_path,
        metadata={"files_extracted": len(discovered_files), "extract_dir": str(extract_dir)}
    )
    
    # Remove duplicates and sort
    unique_files = list(dict.fromkeys(discovered_files))
    unique_files.sort(key=lambda p: str(p).lower())
    
    return unique_files
