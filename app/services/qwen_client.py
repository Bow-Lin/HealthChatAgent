# services/deepseek_client.py
import os
import time
import httpx
from typing import Any, Dict, List, Optional

class QwenError(RuntimeError):
    pass

class QwenClient:
    """Thin client for Qwen Chat Completions API (OpenAI-compatible)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        backoff_factor: float = 0.6,
    ) -> None:
        self.base_url = base_url or os.getenv("QWEN_BASE", "http://127.0.0.1:11434/v1")
        self.api_key = api_key or os.getenv("QWEN_API_KEY")
        self.model = model or os.getenv("QWEN_MODEL", "qwen3:0.6b-q4_K_M")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        if not self.api_key:
            raise QwenError("QWEN_API_KEY is not configured")

        # Single AsyncClient can be shared if you manage lifecycle externally.
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.2,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Perform a non-streaming chat completion and return assistant text.
        Raises QwenError on failure.
        """
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if extra:
            payload.update(extra)

        headers = {"Authorization": f"Bearer {self.api_key}"}

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                res = await self._client.post("/chat/completions", headers=headers, json=payload)
                # Retry on 429/5xx
                if res.status_code in (429, 500, 502, 503, 504):
                    raise QwenError(f"Transient HTTP {res.status_code}: {res.text[:200]}")
                res.raise_for_status()
                data = res.json()
                # Defensive parsing
                choices = data.get("choices") or []
                if not choices:
                    raise QwenError(f"Empty choices: {data!r}")
                message = choices[0].get("message") or {}
                content = message.get("content")
                if not isinstance(content, str):
                    raise QwenError(f"Invalid content: {message!r}")
                return content
            except Exception as e:  # network or parsing
                last_exc = e
                if attempt >= self.max_retries:
                    break
                sleep_s = self.backoff_factor * (2 ** attempt)
                # NOTE: No blocking sleep in async path; use asyncio.sleep
                import asyncio
                await asyncio.sleep(sleep_s)

        raise QwenError(f"Qwen chat failed after retries: {last_exc}")
