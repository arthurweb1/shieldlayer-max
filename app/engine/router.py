import json
from typing import AsyncGenerator, Optional

import httpx

VALID_BACKENDS = {"LOCAL", "CLOUD"}


class HybridRouter:
    """Routes LLM calls to LOCAL (vLLM) or CLOUD (OpenAI-compatible) backend.

    When constructed with local_config + cloud_config, route_for(identity)
    selects the appropriate backend per org policy.
    """

    def __init__(
        self,
        backend_type: str,
        base_url: str,
        model: str,
        api_key: str,
        local_config: Optional[dict] = None,
        cloud_config: Optional[dict] = None,
    ):
        if backend_type not in VALID_BACKENDS:
            raise ValueError(f"backend_type must be one of {VALID_BACKENDS}, got '{backend_type}'")
        self._backend = backend_type
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._local_config = local_config
        self._cloud_config = cloud_config

    def route_for(self, identity) -> "HybridRouter":
        """Return a single-backend HybridRouter scoped to the org's allowed backend.

        Admin org: uses cloud_config if available.
        All other orgs: always LOCAL regardless of global backend_type.
        Falls back to a clone of self when no dual config is available.
        """
        if identity.org_id == "admin" and self._cloud_config:
            cfg = self._cloud_config
            return HybridRouter(
                backend_type="CLOUD",
                base_url=cfg["base_url"],
                model=cfg["model"],
                api_key=cfg.get("api_key", ""),
            )
        if self._local_config:
            cfg = self._local_config
            return HybridRouter(
                backend_type="LOCAL",
                base_url=cfg["base_url"],
                model=cfg["model"],
                api_key="",
            )
        # No dual config — return a clone of self (backward-compatible)
        return HybridRouter(
            backend_type=self._backend,
            base_url=self._base_url,
            model=self._model,
            api_key=self._api_key,
        )

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
        """Streaming completion. Yields text tokens as they arrive."""
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
