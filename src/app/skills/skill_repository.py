"""Loads runtime domain skill files: a threshold in front matter, guidance in prose."""
from pathlib import Path

import yaml


class SkillRepository:
    """Fixed key -> file lookup for skills/, same pattern as PromptLoader.

    Every skill file carries both the enforcement threshold(s) (YAML front matter)
    and the prose guidance a model reads at inference time, so the rubric and the
    guardrail can never drift apart.
    """

    _SKILLS_DIR = Path(__file__).parent

    @classmethod
    def get(cls, skill_name: str) -> tuple[dict, str]:
        """Return (front_matter, guidance) for the named skill.

        Args:
            skill_name: File stem under skills/, e.g. "event_severity_classification".

        Returns:
            Tuple of (front-matter dict, prose guidance string).
        """
        path = cls._SKILLS_DIR / f"{skill_name}.md"
        _, front_matter_text, guidance = path.read_text().split("---", 2)
        front_matter = yaml.safe_load(front_matter_text) or {}
        return front_matter, guidance.strip()
