"""Jinja2 prompt template loader."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


class PromptLoader:
    """Renders Jinja2 prompt templates from the prompts/ directory.

    Stateless facade: the Jinja Environment is built once as a class attribute and
    reused for every render, so callers use PromptLoader.render(...) directly with
    no instance to construct.
    """

    _PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
    _ENV = Environment(
        loader=FileSystemLoader(_PROMPTS_DIR),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    @classmethod
    def render(cls, template_name: str, **kwargs) -> str:
        """Render a prompt template with the given variables.

        Args:
            template_name: Name of template file (e.g., "aggregate.jinja2").
            **kwargs: Variables to pass to the template.

        Returns:
            Rendered prompt string.
        """
        return cls._ENV.get_template(template_name).render(**kwargs)

    @staticmethod
    def format_history(history: list[dict]) -> str:
        """Format conversation history into 'User: …' / 'Assistant: …' lines."""
        return "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in history
        )

