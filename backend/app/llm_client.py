import json
import re
from typing import Optional, Protocol

import httpx
from pydantic import BaseModel, ValidationError


class LLMParseError(Exception):
    """Raised when an LLM response is not valid JSON or fails schema validation."""


class LLMClientProtocol(Protocol):
    def complete_json(self, system_prompt: str, user_prompt: str, schema: type[BaseModel]) -> BaseModel: ...

    def complete_text(self, system_prompt: str, user_prompt: str) -> str: ...


_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fences(text: str) -> str:
    return _CODE_FENCE_RE.sub("", text).strip()


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, transport: Optional[httpx.BaseTransport] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._transport = transport

    def complete_text(self, system_prompt: str, user_prompt: str) -> str:
        with httpx.Client(timeout=60, transport=self._transport) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    def complete_json(self, system_prompt: str, user_prompt: str, schema: type[BaseModel]) -> BaseModel:
        raw = self.complete_text(system_prompt, user_prompt)
        try:
            data = json.loads(_strip_code_fences(raw))
            return schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise LLMParseError(str(exc)) from exc
