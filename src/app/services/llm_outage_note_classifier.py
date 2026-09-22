"""LlmOutageNoteClassifier — judges whether a crew's field note warrants escalating an outage's linked event."""
import logging

from agent_framework import Agent, ChatOptions
from agent_framework.openai import OpenAIChatClient

from ..config.config import Settings
from ..identity.azure_identity_provider import AzureIdentityProvider
from ..models.note_triage_result import NoteTriageResult
from ..skills.skill_repository import SkillRepository
from ..utils.prompt_loader import PromptLoader


class LlmOutageNoteClassifier:
    """Reads a free-text outage note and recommends whether to escalate severity.

    Same "model proposes, code validates" split as LlmIntentClassifier: this class
    only returns a recommendation and never writes to the database. The caller
    (OutageAgent) independently checks the note against the outage_note_triage
    skill's own hazard_keywords before acting on a HIGH recommendation.
    """

    def __init__(self) -> None:
        settings = Settings.get_instance()
        identity = AzureIdentityProvider.default()
        client = OpenAIChatClient(
            azure_endpoint=settings.azure_openai_endpoint,
            model=settings.intent_slm_deployment,
            credential=identity.token_provider,
        )
        self._agent: Agent = Agent(
            client=client,
            name="outage-note-triage",
            instructions=(
                "You judge whether a field crew's outage note describes something "
                "more severe than a routine outage, using the skill guidance supplied "
                "in each prompt. You only recommend - you never write to any database."
            ),
            default_options={
                "reasoning": {"effort": "high", "summary": "detailed"},
                "store": False,
            },
        )

    async def classify(self, note: str) -> NoteTriageResult:
        """Return a severity-escalation recommendation for a free-text outage note."""
        _, guidance = SkillRepository.get("outage_note_triage")
        prompt = PromptLoader.render("outage_note_triage.jinja2", note=note, guidance=guidance)
        try:
            response = await self._agent.run(
                prompt,
                options=ChatOptions(response_format=NoteTriageResult),
            )
        except Exception:
            logging.exception("LlmOutageNoteClassifier.classify: model call failed")
            raise
        result = response.value
        if not isinstance(result, NoteTriageResult):
            raise RuntimeError("Outage note triage model did not return a NoteTriageResult")
        return result
