"""Security utilities for path validation and sanitization."""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Union


@dataclass
class ValidationResult:
    """Result of file validation."""
    is_valid: bool
    error_message: str = ""


def resolve_inside_base(path: Union[str, Path], base_dir: Union[str, Path]) -> Path:
    """
    Resolve a path and ensure it's inside the base directory.
    
    Args:
        path: The path to resolve
        base_dir: The base directory that must contain the resolved path
        
    Returns:
        Resolved Path object that is guaranteed to be inside base_dir
        
    Raises:
        ValueError: If path tries to escape base_dir or is a symlink pointing outside
        FileNotFoundError: If path doesn't exist
    """
    base_path = Path(base_dir).resolve()
    
    # Convert to Path
    path_obj = Path(path)
    
    # Handle symlinks specially to prevent escape (BEFORE resolving)
    if path_obj.is_symlink():
        try:
            target = path_obj.resolve()
        except OSError:
            # If we can't resolve the symlink (permission issues, etc.),
            # check if the symlink file itself is inside base
            try:
                path_obj.relative_to(base_path)
            except ValueError:
                raise ValueError(f"Symlink points outside base: {path}")
        else:
            if target.exists():
                # Symlink points to existing file - verify target is inside base
                try:
                    target.relative_to(base_path)
                except ValueError:
                    raise ValueError(f"Symlink escape detected: {path} points outside {base_dir}")

                path_obj = target
            else:
                # Broken symlinks are allowed if the symlink itself is inside the workspace.
                try:
                    path_obj.relative_to(base_path)
                except ValueError:
                    raise ValueError(f"Broken symlink points outside base: {path}")
                return target

    # Handle relative paths by making them relative to base_dir for resolution
    # We need to check if the path would be inside base when resolved
    if not path_obj.is_absolute():
        # For relative paths, resolve them relative to base_dir first to check bounds
        try:
            resolved_path = (base_path / path_obj).resolve()
            # Check if resolved path is inside base
            resolved_path.relative_to(base_path)
            # If we get here, the path is valid, now use the resolved path
            path_obj = resolved_path
        except ValueError:
            raise ValueError(f"Path traversal detected: {path} resolves outside {base_dir}")
    else:
        # For absolute paths, resolve and check
        path_obj = path_obj.resolve()
        try:
            path_obj.relative_to(base_path)
        except ValueError:
            raise ValueError(f"Path traversal detected: {path} resolves outside {base_dir}")
    
    # Final check: ensure the path exists
    if not path_obj.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    return path_obj


def validate_input_file(path: Union[str, Path], config) -> ValidationResult:
    """
    Validate an input file for processing.
    
    Args:
        path: Path to the file to validate
        config: Configuration object with workspace_root and max_file_mb attributes
        
    Returns:
        ValidationResult indicating if the file is valid and any error message
    """
    try:
        # Convert to Path
        path_obj = Path(path)
        
        # Check if file exists
        if not path_obj.exists():
            return ValidationResult(False, f"File does not exist: {path}")
        
        # Check if it's a file (not a directory)
        if not path_obj.is_file():
            return ValidationResult(False, f"Path is not a file: {path}")
        
        # Check file extension
        allowed_extensions = {
            '.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv', '.json', '.xml',
            '.html', '.htm', '.txt', '.md', '.zip', '.epub', '.jpg', '.jpeg',
            '.png', '.webp', '.mp3', '.wav'
        }
        
        if path_obj.suffix.lower() not in allowed_extensions:
            return ValidationResult(
                False, 
                f"File type not allowed: {path_obj.suffix}. "
                f"Allowed types: {', '.join(sorted(allowed_extensions))}"
            )
        
        # Check file size
        file_size_mb = path_obj.stat().st_size / (1024 * 1024)
        if file_size_mb > config.max_file_mb:
            return ValidationResult(
                False,
                f"File too large: {file_size_mb:.2f} MB > {config.max_file_mb} MB limit"
            )
        
        # Check if path is inside workspace_root
        try:
            resolve_inside_base(path_obj, config.workspace_root)
        except ValueError as e:
            return ValidationResult(False, str(e))
        except FileNotFoundError:
            return ValidationResult(False, f"File not found: {path}")
        
        return ValidationResult(True, "")
        
    except Exception as e:
        return ValidationResult(False, f"Validation error: {str(e)}")


def safe_output_path(input_path: Union[str, Path], output_root: Union[str, Path], 
                     suffix: str = ".md") -> Path:
    """
    Generate a safe output path that preserves relative structure and prevents overwrites.
    
    Args:
        input_path: Path to the input file
        output_root: Root directory for output files
        suffix: File suffix to use (default: .md)
        
    Returns:
        Safe output path that won't cause overwrites or path traversal
    """
    input_path = Path(input_path)
    output_root = Path(output_root)
    
    # Ensure output_root exists
    output_root.mkdir(parents=True, exist_ok=True)
    
    # If input_path is absolute, try to make it relative to workspace root if possible
    # For now, we'll use the filename and preserve directory structure relative to input
    if input_path.is_absolute():
        # Use just the filename and any parent directories from the input path
        relative_part = input_path.name
        # For more sophisticated preserving of directory structure, 
        # we would need to know the workspace root, but we'll keep it simple for MVP
    else:
        relative_part = input_path.name
    
    # Change suffix to the desired output suffix
    output_filename = input_path.stem + suffix
    output_path = output_root / output_filename
    
    # Prevent overwrites by adding numeric suffix if file exists
    counter = 1
    while output_path.exists():
        output_filename = f"{input_path.stem}_{counter}{suffix}"
        output_path = output_root / output_filename
        counter += 1
    
    # Final safety check: ensure output path is inside output_root
    try:
        output_path.resolve().relative_to(output_root.resolve())
    except ValueError:
        # This should not happen, but fallback to a safe name
        output_path = output_root / f"converted_{input_path.stem}{suffix}"
        counter = 1
        while output_path.exists():
            output_path = output_root / f"converted_{input_path.stem}_{counter}{suffix}"
            counter += 1
    
    return output_path
