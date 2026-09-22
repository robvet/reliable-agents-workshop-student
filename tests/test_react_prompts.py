from app.utils.prompt_loader import PromptLoader


class TestReActPrompts:
    def test_system_prompt_defines_selection_and_stop(self) -> None:
        prompt = PromptLoader.render("system/react.jinja2")

        assert "Select one available domain agent" in prompt
        assert "stop when the existing observations are sufficient" in prompt
        assert "Never select an agent that is not listed" in prompt

    def test_decision_prompt_renders_request_and_agent_catalog(self) -> None:
        prompt = PromptLoader.render(
            "react_decision.jinja2",
            user_prompt="Which crews are assigned?",
            agents={"asset": "Find assets", "crew": "Find crews"},
        )

        assert "Which crews are assigned?" in prompt
        assert "- asset: Find assets" in prompt
        assert "- crew: Find crews" in prompt
        assert "or null if none" in prompt