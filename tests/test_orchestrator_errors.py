from app.agents.orchestrator import Orchestrator


class TestOrchestratorErrors:
    def test_hides_exception_details_by_default(self) -> None:
        orchestrator = Orchestrator.__new__(Orchestrator)
        orchestrator._show_verbose_errors = False

        event = orchestrator._error_event(RuntimeError("database unavailable"))

        assert event.payload == {"message": "The system encountered a technical issue."}

    def test_shows_exception_details_when_enabled(self) -> None:
        orchestrator = Orchestrator.__new__(Orchestrator)
        orchestrator._show_verbose_errors = True

        event = orchestrator._error_event(RuntimeError("database unavailable"))

        assert event.payload == {"message": "database unavailable"}