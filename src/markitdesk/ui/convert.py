"""Convert page for MarkItDesk."""

import asyncio
from pathlib import Path
from ..ui_runtime import ui
from ..jobs import initialize_job_queue, get_job_queue
from ..config import settings
from ..database import init_db, create_project, get_connection
from ..discovery import discover_files, discover_files_from_zip


_selected_recipe_name = None


def get_selected_recipe():
    """Get the currently selected recipe name."""
    return _selected_recipe_name


def set_selected_recipe(recipe_name):
    """Update the selected recipe name."""
    global _selected_recipe_name
    _selected_recipe_name = recipe_name if recipe_name else None


def get_or_create_default_project_id(db_path: Path) -> int:
    """Return the first project if present, otherwise create a default one."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM projects ORDER BY id LIMIT 1")
        row = cursor.fetchone()
        if row:
            return row["id"]

    return create_project(
        db_path,
        "Default",
        str(settings.workspace_root),
        str(settings.output_root),
    )


def process_uploaded_files(files, project_id: int) -> str:
    """Persist uploaded files, discover supported inputs, and enqueue them."""
    if not files:
        return "No files selected"

    all_file_paths = []
    errors = []
    for file_info in files:
        content = file_info.content.read()
        item_path = settings.workspace_root / file_info.name
        item_path.parent.mkdir(parents=True, exist_ok=True)
        with open(item_path, "wb") as handle:
            handle.write(content)

        try:
            recipe_name = get_selected_recipe()
            if item_path.suffix.lower() == ".zip":
                discovered_paths = discover_files_from_zip(item_path, settings, recipe_name)
            else:
                discovered_paths = discover_files([item_path], settings, recipe_name)
            all_file_paths.extend(discovered_paths)
        except Exception as exc:
            errors.append(f"{file_info.name}: {str(exc)}")
            continue

    job_queue = get_job_queue()
    if job_queue and all_file_paths:
        job_ids = job_queue.enqueue_many(all_file_paths, project_id=project_id)
        message = f"Added {len(all_file_paths)} files to queue. Job IDs: {job_ids}"
        if errors:
            return f"{message}. Skipped {len(errors)} item(s): {'; '.join(errors)}"
        return message
    if errors:
        return f"Error processing upload(s): {'; '.join(errors)}"
    if not all_file_paths:
        return "No supported files found in upload"
    return "Error: Job queue not initialized"


def convert_page() -> None:
    """Render the convert page."""
    # Initialize database and job queue if not already done
    db_path = settings.workspace_root.parent / "markitdesk.db"
    init_db(db_path)
    from ..recipes import initialize_recipes
    initialize_recipes()  # Ensure recipes are initialized

    project_id = get_or_create_default_project_id(db_path)
    
    # Initialize job queue
    job_queue = initialize_job_queue(settings)
    
    # State variables
    upload = ui.upload(auto_upload=False, multiple=True).classes('w-full')
    status_label = ui.label().classes('mt-2')
    
    # Recipe selection UI elements
    recipe_select = None
    
    def handle_recipe_change(recipe_name):
        """Handle recipe selection change."""
        set_selected_recipe(recipe_name)
        status_label.text = f"Selected recipe: {recipe_name}" if recipe_name else "No recipe selected"

    async def handle_upload(upload_component):
        """Handle file uploads and add them to the job queue."""
        try:
            status_label.text = "Processing uploads..."
            files = await upload_component
            status_label.text = process_uploaded_files(files, project_id)
        except Exception as exc:
            status_label.text = f"Error: {str(exc)}"
    
    with ui.column().classes('w-full max-w-4xl mx-auto p-4'):
        ui.label('Convert Files').classes('text-2xl font-bold mb-4')
        
        # Recipe selection
        with ui.card().classes('w-full mb-4'):
            ui.label('Conversion Recipe').classes('mb-2')
            with ui.row().classes('w-full items-center'):
                recipe_select = ui.select(
                    options={},
                    label='Select a recipe',
                    with_input=True,
                    on_change=lambda e: handle_recipe_change(e.value)
                ).classes('flex-1')
                ui.button('Refresh', on_click=lambda: refresh_recipes(recipe_select)).props('outline size=sm')
        
        # File picker/upload
        with ui.card().classes('w-full mb-4'):
            ui.label('Select files or folders to convert').classes('mb-2')
            with ui.row().classes('w-full items-center'):
                upload
                ui.button('Add to Queue', on_click=lambda: asyncio.create_task(handle_upload(upload))).props('outline')
        
        # Status area
        with ui.card().classes('w-full mb-4'):
            ui.label('Status').classes('mb-2')
            status_label
        
        # Output folder display
        with ui.card().classes('w-full mb-4'):
            ui.label('Output Folder').classes('mb-2')
            with ui.row().classes('items-center'):
                ui.icon('folder').classes('text-xl')
                ui.label(str(settings.output_root)).classes('ml-2')
                ui.space()
                ui.button('Open Folder', on_click=lambda: ui.notify(f'Opening {settings.output_root}')).props('outline size=sm')
        
        # Start conversion button (disabled for now - queue processes automatically)
    with ui.row().classes('justify-end'):
        ui.button('Start Conversion', on_click=lambda: ui.notify('Conversion starts automatically when files are added to queue')).props('icon=play_arrow')
        
    # Load initial recipes
    refresh_recipes(recipe_select)
    
    
def refresh_recipes(recipe_select):
    """Refresh the recipe dropdown with available recipes."""
    from ..recipes import load_all_recipes
    recipes = load_all_recipes()
    options = {recipe.name: recipe.name for recipe in recipes}
    recipe_select.set_options(options)
    if options and recipe_select.value not in options:
        # Select first recipe if current selection is not valid
        recipe_select.set_value(list(options.keys())[0] if options else None)
