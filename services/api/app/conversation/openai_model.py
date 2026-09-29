"""OpenAI calls, with the same contract as the Claude client: a forced function call
labels the caller's message, and a second call phrases the reply from the engine's
brief. Neither can change state."""

from __future__ import annotations

import json
from typing import Any

import openai

from app.conversation.claude import INTERPRET_SYSTEM, RESPOND_SYSTEM
from app.conversation.interpretation import INTERPRETATION_SCHEMA, Interpretation


class OpenAIModel:
    mode = "openai"

    def __init__(self, api_key: str, model: str, *, timeout: float = 45.0) -> None:
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=2)
        self.model = model
        # Reasoning models reject a custom temperature; the GPT-4 family takes one.
        self._sampling: dict[str, Any] = {"temperature": 0} if model.startswith("gpt-4") else {}

    def interpret(self, context: dict[str, Any], text: str) -> Interpretation:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": INTERPRET_SYSTEM},
                {
                    "role": "user",
                    "content": "Context:\n" + json.dumps(context, ensure_ascii=False)
                    + "\n\nCaller's latest message:\n<caller_message>\n" + text + "\n</caller_message>",
                },
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "record_interpretation",
                        "description": "Record the labels for the caller's latest message.",
                        "parameters": INTERPRETATION_SCHEMA,
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": "record_interpretation"}},
            **self._sampling,
        )
        calls = response.choices[0].message.tool_calls or []
        if not calls:
            raise ValueError("model did not call record_interpretation")
        return Interpretation.model_validate_json(calls[0].function.arguments)

    def respond(self, brief: dict[str, Any], history: list[dict[str, str]]) -> str:
        system = RESPOND_SYSTEM.format(brief=json.dumps(brief, ensure_ascii=False, indent=1))
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *history],
            **({"temperature": 0.3} if self._sampling else {}),
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise ValueError("empty reply from model")
        return text
