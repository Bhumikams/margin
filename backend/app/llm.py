"""Pluggable LLM backend. Switch with LLM_PROVIDER=groq|claude — no other code changes."""
from __future__ import annotations

from typing import Protocol

from .config import Settings


class LLM(Protocol):
    name: str

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str: ...


class GroqLLM:
    def __init__(self, api_key: str, model: str, temperature: float, reasoning_effort: str = "low"):
        from groq import Groq

        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set. Get a free key at console.groq.com.")
        self.client = Groq(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.name = f"groq/{model}"

    def complete(self, system, user, *, json_mode=False):
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if "gpt-oss" in self.model:
            kwargs["reasoning_effort"] = self.reasoning_effort
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **kwargs,
        )
        return resp.choices[0].message.content or ""


class ClaudeLLM:
    def __init__(self, api_key: str, model: str, temperature: float):
        import anthropic

        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.name = f"anthropic/{model}"

    def complete(self, system, user, *, json_mode=False):
        if json_mode:
            system += "\nRespond with a single valid JSON object and nothing else."
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def build_llm(s: Settings) -> LLM:
    if s.llm_provider == "claude":
        return ClaudeLLM(s.anthropic_api_key, s.claude_model, s.temperature)
    if s.llm_provider == "groq":
        return GroqLLM(s.groq_api_key, s.groq_model, s.temperature, s.groq_reasoning_effort)
    raise RuntimeError(f"Unknown LLM_PROVIDER '{s.llm_provider}' (use groq or claude)")
