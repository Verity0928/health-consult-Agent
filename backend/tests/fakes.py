from pydantic import BaseModel, ValidationError

from app.llm_client import LLMParseError


class FakeLLMClient:
    """Deterministic test double for LLMClientProtocol. No network calls."""

    def __init__(self):
        self._json_queue: list[dict] = []
        self._text_queue: list[str] = []
        self._embed_queue: list[list[list[float]]] = []
        self.embed_calls: list[tuple[list[str], str]] = []

    def queue_json(self, response: dict) -> None:
        self._json_queue.append(response)

    def queue_text(self, response: str) -> None:
        self._text_queue.append(response)

    def queue_embeddings(self, vectors: list[list[float]]) -> None:
        self._embed_queue.append(vectors)

    def complete_json(self, system_prompt: str, user_prompt: str, schema: type[BaseModel]) -> BaseModel:
        if not self._json_queue:
            raise AssertionError("no queued json response")
        data = self._json_queue.pop(0)
        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            raise LLMParseError(str(exc)) from exc

    def complete_text(self, system_prompt: str, user_prompt: str) -> str:
        if not self._text_queue:
            raise AssertionError("no queued text response")
        return self._text_queue.pop(0)

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        self.embed_calls.append((texts, model))
        if not self._embed_queue:
            raise AssertionError("no queued embeddings")
        return self._embed_queue.pop(0)
