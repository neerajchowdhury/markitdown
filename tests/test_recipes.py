"""Tests for recipe functionality."""

import sys
import tempfile
from pathlib import Path

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import the modules we need for testing
from markitdesk.recipes import (
    Recipe,
    init_recipe_table,
    save_recipe,
    load_recipe,
    load_all_recipes,
    delete_recipe,
    load_default_recipes,
    initialize_recipes
)
from markitdesk.config import Settings
from markitdesk.database import init_db


def test_recipes_import():
    """Test that recipes module can be imported."""
    assert Recipe is not None
    assert init_recipe_table is not None
    assert save_recipe is not None
    assert load_recipe is not None
    assert load_all_recipes is not None
    assert delete_recipe is not None
    assert load_default_recipes is not None
    assert initialize_recipes is not None


def test_recipe_dataclass():
    """Test Recipe dataclass."""
    
    recipe = Recipe(
        name="Test Recipe",
        description="A test recipe",
        allowed_extensions=[".txt", ".md"],
        recursive=False,
        extract_zip=False,
        quality_check=False,
        chunking_strategy="by_token_window",
        max_chunk_tokens=1000,
        exports=["csv_index"]
    )
    
    assert recipe.name == "Test Recipe"
    assert recipe.description == "A test recipe"
    assert recipe.allowed_extensions == [".txt", ".md"]
    assert recipe.recursive is False
    assert recipe.extract_zip is False
    assert recipe.quality_check is False
    assert recipe.chunking_strategy == "by_token_window"
    assert recipe.max_chunk_tokens == 1000
    assert recipe.exports == ["csv_index"]


def test_recipe_defaults():
    """Test Recipe default values."""
    
    recipe = Recipe(name="Test")
    
    assert recipe.name == "Test"
    assert recipe.description == ""
    assert len(recipe.allowed_extensions) > 0  # Should have default extensions
    assert recipe.recursive is True
    assert recipe.extract_zip is True
    assert recipe.quality_check is True
    assert recipe.chunking_strategy == "by_heading"
    assert recipe.max_chunk_tokens == 500
    assert recipe.exports == []


def test_save_and_load_recipe():
    """Test saving and loading a recipe."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        output = Path(temp_dir) / "output"
        workspace.mkdir()
        output.mkdir()
        
        # Configure settings to use our temporary directory
        settings_obj = Settings()
        settings_obj.workspace_root = workspace
        settings_obj.output_root = output
        
        # Temporarily override the settings module's settings object
        import markitdesk.config
        original_settings = markitdesk.config.settings
        markitdesk.config.settings = settings_obj
        
        try:
            # Initialize database
            db_path = workspace.parent / "markitdesk.db"
            init_db(db_path)
            
            # Initialize recipe table
            init_recipe_table(db_path)
            
            # Create and save a recipe
            recipe = Recipe(
                name="Test Recipe",
                description="A test recipe for saving/loading",
                allowed_extensions=[".txt", ".md"],
                recursive=True,
                extract_zip=False,
                quality_check=True,
                chunking_strategy="by_token_window",
                max_chunk_tokens=200,
                exports=["csv_index"]
            )
            
            recipe_id = save_recipe(recipe)
            assert recipe_id > 0
            
            # Load the recipe
            loaded_recipe = load_recipe("Test Recipe")
            assert loaded_recipe is not None
            assert loaded_recipe.name == recipe.name
            assert loaded_recipe.description == recipe.description
            assert loaded_recipe.allowed_extensions == recipe.allowed_extensions
            assert loaded_recipe.recursive == recipe.recursive
            assert loaded_recipe.extract_zip == recipe.extract_zip
            assert loaded_recipe.quality_check == recipe.quality_check
            assert loaded_recipe.chunking_strategy == recipe.chunking_strategy
            assert loaded_recipe.max_chunk_tokens == recipe.max_chunk_tokens
            assert loaded_recipe.exports == recipe.exports
            
            # Test loading non-existent recipe
            non_existent = load_recipe("Non-existent Recipe")
            assert non_existent is None
            
            # Test deleting recipe
            deleted = delete_recipe("Test Recipe")
            assert deleted is True
            
            # Verify it's gone
            assert load_recipe("Test Recipe") is None
            
            # Test deleting non-existent recipe
            deleted_none = delete_recipe("Non-existent Recipe")
            assert deleted_none is False
        finally:
            # Restore original settings
            markitdesk.config.settings = original_settings


def test_load_all_recipes():
    """Test loading all recipes."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        output = Path(temp_dir) / "output"
        workspace.mkdir()
        output.mkdir()
        
        # Configure settings to use our temporary directory
        settings_obj = Settings()
        settings_obj.workspace_root = workspace
        settings_obj.output_root = output
        
        # Temporarily override the settings module's settings object
        import markitdesk.config
        original_settings = markitdesk.config.settings
        markitdesk.config.settings = settings_obj
        
        try:
            # Initialize database
            db_path = workspace.parent / "markitdesk.db"
            init_db(db_path)
            
            # Initialize recipe table
            init_recipe_table(db_path)
            
            # Start with no recipes
            assert load_all_recipes() == []
            
            # Add two recipes
            recipe1 = Recipe(name="Recipe 1", description="First recipe")
            recipe2 = Recipe(name="Recipe 2", description="Second recipe")
            
            save_recipe(recipe1)
            save_recipe(recipe2)
            
            # Load all recipes
            recipes = load_all_recipes()
            assert len(recipes) == 2
            
            # Check they are sorted by name
            assert recipes[0].name == "Recipe 1"
            assert recipes[1].name == "Recipe 2"
            
            # Delete one recipe
            delete_recipe("Recipe 1")
            
            # Load all recipes again
            recipes = load_all_recipes()
            assert len(recipes) == 1
            assert recipes[0].name == "Recipe 2"
        finally:
            # Restore original settings
            markitdesk.config.settings = original_settings


def test_load_default_recipes():
    """Test loading default recipes."""
    
    default_recipes = load_default_recipes()
    assert len(default_recipes) == 4
    
    # Check recipe names
    names = [r.name for r in default_recipes]
    assert "Basic Markdown" in names
    assert "RAG Pack" in names
    assert "Tender/RFP Pack" in names
    assert "Manuscript Research Pack" in names
    
    # Check a specific recipe
    basic_markdown = next(r for r in default_recipes if r.name == "Basic Markdown")
    assert basic_markdown.description == "Convert files to Markdown with quality check"
    assert basic_markdown.exports == []
    assert basic_markdown.quality_check is True
    assert basic_markdown.chunking_strategy == "by_heading"


def test_initialize_recipes():
    """Initialize recipes in a temporary database."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        output = Path(temp_dir) / "output"
        workspace.mkdir()
        output.mkdir()
        
        # Configure settings to use our temporary directory
        settings_obj = Settings()
        settings_obj.workspace_root = workspace
        settings_obj.output_root = output
        
        # Temporarily override the settings module's settings object
        import markitdesk.config
        original_settings = markitdesk.config.settings
        markitdesk.config.settings = settings_obj
        
        try:
            # Initialize database
            db_path = workspace.parent / "markitdesk.db"
            init_db(db_path)
            
            # Initialize recipes (should create table and add defaults if empty)
            initialize_recipes()
            
            # Should now have the default recipes
            recipes = load_all_recipes()
            assert len(recipes) == 4
            
            # Check that we have the expected recipes
            names = [r.name for r in recipes]
            assert "Basic Markdown" in names
            assert "RAG Pack" in names
            assert "Tender/RFP Pack" in names
            assert "Manuscript Research Pack" in names
        finally:
            # Restore original settings
            markitdesk.config.settings = original_settings


if __name__ == "__main__":
    test_recipes_import()
    test_recipe_dataclass()
    test_recipe_defaults()
    test_save_and_load_recipe()
    test_load_all_recipes()
    test_load_default_recipes()
    test_initialize_recipes()
    print("All recipe tests passed!")