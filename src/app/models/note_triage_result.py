"""Recommendation returned by LlmOutageNoteClassifier - never written to the DB directly."""

from pydantic import BaseModel


class NoteTriageResult(BaseModel):
    escalate: bool
    severity: str
    reasoning: str
