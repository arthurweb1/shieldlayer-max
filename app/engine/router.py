import json
from typing import AsyncGenerator

import httpx

VALID_BACKENDS = {"LOCAL", "CLOUD"}


class HybridRouter:
    """Routes LLM calls to LOCAL (vLLM) or CLOUD (OpenAI-compatible) backend.

    The masked prompt is sent to whichever backend is configured.
    PII has already been stripped by ShieldEngine before reaching the router.
    The client always receives OpenAI-compatible responses.
    """

    def __init__(self, backend_type: str, base_url: str, model: str, api_key: str):
        if backend_type not in VALID_BACKENDS:
            raise ValueError(f"backend_type must be one of {VALID_BACKENDS}, got '{backend_type}'")
        self._backend = backend_type
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _payload(self, prompt: str, stream: bool = False) -> dict:
        return {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }

    async def complete(self, prompt: str) -> str:
        """Non-streaming completion. Returns full response text."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(prompt, stream=False),
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Streaming completion. Yields text tokens as they arrive.

        Both LOCAL and CLOUD backends use OpenAI SSE format:
        data: {"choices":[{"delta":{"content":"token"}}]}
        """
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(prompt, stream=True),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
