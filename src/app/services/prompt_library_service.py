"""Prompt library service backed by prompts/suggestive/suggestive-prompts.yaml."""
from pathlib import Path

import yaml


class PromptLibraryService:
    """Load and serve the nested suggestive prompt collection."""

    def __init__(self) -> None:
        yaml_path = Path(__file__).parent.parent / "prompts" / "suggestive" / "suggestive-prompts.yaml"
        with open(yaml_path, "r", encoding="utf-8") as f:
            self._prompts: dict[str, object] = yaml.safe_load(f) or {}

    def get_all(self) -> dict[str, object]:
        return self._prompts