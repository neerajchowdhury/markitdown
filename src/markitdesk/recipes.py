"""Recipe management for MarkItDesk."""

from dataclasses import dataclass, asdict
from typing import List, Optional
from pathlib import Path
import json
from .database import get_connection
from .config import settings as default_settings


@dataclass
class Recipe:
    """A conversion recipe."""
    name: str
    description: str = ""
    allowed_extensions: List[str] = None
    recursive: bool = True
    extract_zip: bool = True
    quality_check: bool = True
    chunking_strategy: str = "by_heading"  # or "by_token_window"
    max_chunk_tokens: int = 500
    exports: List[str] = None  # e.g., ["markdown_zip", "jsonl_chunks", "csv_index"]

    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = ['.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv', '.json', '.xml',
                                       '.html', '.htm', '.txt', '.md', '.zip', '.epub', '.jpg', '.jpeg',
                                       '.png', '.webp', '.mp3', '.wav']
        if self.exports is None:
            self.exports = []


def init_recipe_table(db_path: Path) -> None:
    """Initialize the recipe table in the database."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                allowed_extensions TEXT,  -- JSON list
                recursive BOOLEAN DEFAULT 1,
                extract_zip BOOLEAN DEFAULT 1,
                quality_check BOOLEAN DEFAULT 1,
                chunking_strategy TEXT DEFAULT 'by_heading',
                max_chunk_tokens INTEGER DEFAULT 500,
                exports TEXT  -- JSON list
            )
        """)
        conn.commit()


def save_recipe(recipe: Recipe) -> int:
    """Save a recipe to the database, returning the recipe ID."""
    from .config import settings
    db_path = settings.workspace_root.parent / "markitdesk.db"
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO recipes 
            (name, description, allowed_extensions, recursive, extract_zip, quality_check, 
             chunking_strategy, max_chunk_tokens, exports)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            recipe.name,
            recipe.description,
            json.dumps(recipe.allowed_extensions),
            int(recipe.recursive),
            int(recipe.extract_zip),
            int(recipe.quality_check),
            recipe.chunking_strategy,
            recipe.max_chunk_tokens,
            json.dumps(recipe.exports)
        ))
        conn.commit()
        return cursor.lastrowid


def load_recipe(name: str) -> Optional[Recipe]:
    """Load a recipe by name from the database."""
    from .config import settings
    db_path = settings.workspace_root.parent / "markitdesk.db"
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, description, allowed_extensions, recursive, extract_zip, quality_check, 
                   chunking_strategy, max_chunk_tokens, exports
            FROM recipes WHERE name = ?
        """, (name,))
        row = cursor.fetchone()
        if row:
            return Recipe(
                name=row[0],
                description=row[1],
                allowed_extensions=json.loads(row[2]) if row[2] else None,
                recursive=bool(row[3]),
                extract_zip=bool(row[4]),
                quality_check=bool(row[5]),
                chunking_strategy=row[6],
                max_chunk_tokens=row[7],
                exports=json.loads(row[8]) if row[8] else None
            )
        return None


def load_all_recipes() -> List[Recipe]:
    """Load all recipes from the database."""
    from .config import settings
    db_path = settings.workspace_root.parent / "markitdesk.db"
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, description, allowed_extensions, recursive, extract_zip, quality_check, 
                   chunking_strategy, max_chunk_tokens, exports
            FROM recipes ORDER BY name
        """)
        recipes = []
        for row in cursor.fetchall():
            recipes.append(Recipe(
                name=row[0],
                description=row[1],
                allowed_extensions=json.loads(row[2]) if row[2] else None,
                recursive=bool(row[3]),
                extract_zip=bool(row[4]),
                quality_check=bool(row[5]),
                chunking_strategy=row[6],
                max_chunk_tokens=row[7],
                exports=json.loads(row[8]) if row[8] else None
            ))
        return recipes


def delete_recipe(name: str) -> bool:
    """Delete a recipe by name. Returns True if deleted."""
    from .config import settings
    db_path = settings.workspace_root.parent / "markitdesk.db"
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recipes WHERE name = ?", (name,))
        conn.commit()
        return cursor.rowcount > 0


def load_default_recipes() -> List[Recipe]:
    """Load the default recipes."""
    return [
        Recipe(
            name="Basic Markdown",
            description="Convert files to Markdown with quality check",
            allowed_extensions=['.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv', '.json', '.xml',
                               '.html', '.htm', '.txt', '.md', '.zip', '.epub', '.jpg', '.jpeg',
                               '.png', '.webp', '.mp3', '.wav'],
            recursive=True,
            extract_zip=True,
            quality_check=True,
            chunking_strategy="by_heading",
            max_chunk_tokens=500,
            exports=[]
        ),
        Recipe(
            name="RAG Pack",
            description="Convert, quality check, chunk by heading, export JSONL + CSV index",
            allowed_extensions=['.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv', '.json', '.xml',
                               '.html', '.htm', '.txt', '.md', '.zip', '.epub', '.jpg', '.jpeg',
                               '.png', '.webp', '.mp3', '.wav'],
            recursive=True,
            extract_zip=True,
            quality_check=True,
            chunking_strategy="by_heading",
            max_chunk_tokens=500,
            exports=["jsonl_chunks", "csv_index"]
        ),
        Recipe(
            name="Tender/RFP Pack",
            description="Convert, quality check, chunk by heading, export Markdown ZIP + JSONL + CSV index",
            allowed_extensions=['.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv', '.json', '.xml',
                               '.html', '.htm', '.txt', '.md', '.zip', '.epub', '.jpg', '.jpeg',
                               '.png', '.webp', '.mp3', '.wav'],
            recursive=True,
            extract_zip=True,
            quality_check=True,
            chunking_strategy="by_heading",
            max_chunk_tokens=500,
            exports=["markdown_zip", "jsonl_chunks", "csv_index"]
        ),
        Recipe(
            name="Manuscript Research Pack",
            description="Convert, quality check, chunk by heading, export Markdown ZIP + CSV index",
            allowed_extensions=['.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv', '.json', '.xml',
                               '.html', '.htm', '.txt', '.md', '.zip', '.epub', '.jpg', '.jpeg',
                               '.png', '.webp', '.mp3', '.wav'],
            recursive=True,
            extract_zip=True,
            quality_check=True,
            chunking_strategy="by_heading",
            max_chunk_tokens=500,
            exports=["markdown_zip", "csv_index"]
        )
    ]


def initialize_recipes() -> None:
    """Initialize the recipe table and populate with default recipes if empty."""
    from .config import settings
    db_path = settings.workspace_root.parent / "markitdesk.db"
    init_recipe_table(db_path)
    
    # Check if we have any recipes
    recipes = load_all_recipes()
    if not recipes:
        # Insert default recipes
        for recipe in load_default_recipes():
            save_recipe(recipe)
