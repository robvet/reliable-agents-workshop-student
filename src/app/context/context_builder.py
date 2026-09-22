import json

from ..models.agent_result import AgentResult


class ContextBuilder:
    """Adds prior agent results to the prompt handed to each step.

    This is the single place future context management belongs - relevance selection,
    summarization, token-budget enforcement, and pulling from conversation memory. When
    that arrives it grows inside build(); the pipeline keeps calling build() and never
    changes.
    """

    def build(self, user_prompt: str, completed: list[AgentResult]) -> str:
        """Return the original request plus prior agents' business results."""
        if not completed:
            return user_prompt

        # Questions, SQL, and reasoning are diagnostics, not findings. Excluding them
        # also prevents a prior enriched prompt from being copied into every later one.
        # Keep an ordered list so repeated runs of the same agent are preserved.
        prior_results = [
            {
                "agent": result.agent,
                "data": {
                    key: value
                    for key, value in result.data.items()
                    if key not in ("question", "sql", "reasoning")
                },
            }
            for result in completed
        ]
        return (
            f"{user_prompt}\n\n"
            "Results from agents that already completed this request:\n"
            f"{json.dumps(prior_results, default=str)}"
        )
