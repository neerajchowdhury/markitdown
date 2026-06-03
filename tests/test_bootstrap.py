import os
from pathlib import Path
from markitdesk.config import Settings


def test_settings_defaults():
    """Test that default settings are secure and sensible."""
    # Unset environment variables to test defaults
    env_vars = [
        "WORKSPACE_ROOT",
        "OUTPUT_ROOT",
        "MAX_FILE_MB",
        "ALLOW_PLUGINS",
        "ALLOW_REMOTE_URLS",
        "ALLOW_AI_ENRICHMENT",
    ]
    original_values = {}
    for var in env_vars:
        original_values[var] = os.environ.get(var)
        if var in os.environ:
            del os.environ[var]

    try:
        settings = Settings(_env_file=None)  # Prevent loading .env file
        # Check defaults
        assert settings.workspace_root == Path("./workspace")
        assert settings.output_root == Path("./output")
        assert settings.max_file_mb == 100
        assert settings.allow_plugins is False
        assert settings.allow_remote_urls is False
        assert settings.allow_ai_enrichment is False
    finally:
        # Restore environment variables
        for var, value in original_values.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]


def test_settings_from_env(monkeypatch):
    """Test that settings can be overridden by environment variables."""
    monkeypatch.setenv("WORKSPACE_ROOT", "/custom/workspace")
    monkeypatch.setenv("OUTPUT_ROOT", "/custom/output")
    monkeypatch.setenv("MAX_FILE_MB", "50")
    monkeypatch.setenv("ALLOW_PLUGINS", "true")
    monkeypatch.setenv("ALLOW_REMOTE_URLS", "true")
    monkeypatch.setenv("ALLOW_AI_ENRICHMENT", "true")

    settings = Settings(_env_file=None)
    assert settings.workspace_root == Path("/custom/workspace")
    assert settings.output_root == Path("/custom/output")
    assert settings.max_file_mb == 50
    assert settings.allow_plugins is True
    assert settings.allow_remote_urls is True
    assert settings.allow_ai_enrichment is True