"""
iFlow API Client
Used to call iFlow platform AI model services
"""

import os
from typing import (
    Optional,
    Dict,
    Any,
    List,
    Union,
    Iterator,
    AsyncIterator,
)
from openai import OpenAI, AsyncOpenAI
from pydantic import BaseModel


class Message(BaseModel):
    """Message model"""
    role: str  # "system", "user", "assistant"
    content: str


class IFlowClient:
    """iFlow API Client class"""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://apis.iflow.cn/v1"):
        """
        Initialize iFlow Client.

        Args:
            api_key: iFlow API key, if not provided will get from environment variable IFLLOW_API_KEY
            base_url: API base URL, default is iFlow API address
        """
        self.api_key = api_key or os.getenv("IFLOW_API_KEY")
        if not self.api_key:
            raise ValueError(
                "iFlow API key not provided, please set api_key parameter "
                "or IFLLOW_API_KEY environment variable"
            )

        self.base_url = base_url
        self.sync_client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )
        self.async_client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    # ---------- internal helpers ----------

    @staticmethod
    def _extract_content_from_chunk(chunk: Any) -> Optional[str]:
        """
        Given a ChatCompletionChunk, extract incremental content text.

        We only care about `choices[0].delta.content` for now.
        """
        if not chunk or not getattr(chunk, "choices", None):
            return None
        choice = chunk.choices[0]
        delta = getattr(choice, "delta", None)
        if not delta:
            return None
        # For OpenAI v1 client, `delta.content` may be str | None
        return getattr(delta, "content", None)

    # ---------- sync API ----------

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "qwen3-max",  # Default to use qwen3-max model
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1000,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[str, Iterator[str]]:
        """
        Get chat completion.

        Args:
            messages: Message list, format is
                [{"role": "user", "content": "message content"}, ...]
            model: Model name to use
            temperature: Temperature parameter, controls output randomness
            max_tokens: Maximum output token count
            stream: Whether to use streaming output
            **kwargs: Other parameters passed to API

        Returns:
            - If stream=False: returns full text string.
            - If stream=True: returns an iterator of text chunks (str).
        """
        if not stream:
            # Non-streaming: normal one-shot completion
            response = self.sync_client.chat.completions.create(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                **kwargs,
            )
            if response and response.choices and len(response.choices) > 0:
                return response.choices[0].message.content or ""
            raise RuntimeError("Invalid response from API: no choices returned")

        # Streaming mode: return an iterator of incremental chunks
        stream_resp = self.sync_client.chat.completions.create(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        def _iter_text() -> Iterator[str]:
            for chunk in stream_resp:
                content = self._extract_content_from_chunk(chunk)
                if content:
                    # Yield incremental piece of text
                    yield content

        return _iter_text()

    # ---------- async API ----------

    async def achat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "qwen3-max",
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1000,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[str, AsyncIterator[str]]:
        """
        Asynchronously get chat completion.

        Args:
            messages: Message list
            model: Model name to use
            temperature: Temperature parameter
            max_tokens: Maximum output token count
            stream: Whether to use streaming output
            **kwargs: Other parameters passed to API

        Returns:
            - If stream=False: returns full text string.
            - If stream=True: returns an async iterator of text chunks (str).
        """
        if not stream:
            # Non-streaming async call
            response = await self.async_client.chat.completions.create(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                **kwargs,
            )
            if response and response.choices and len(response.choices) > 0:
                return response.choices[0].message.content or ""
            raise RuntimeError("Invalid response from API: no choices returned")

        # Streaming async call: first create the stream, then async-iterate
        stream_resp = await self.async_client.chat.completions.create(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        async def _aiter_text() -> AsyncIterator[str]:
            async for chunk in stream_resp:
                content = self._extract_content_from_chunk(chunk)
                if content:
                    yield content

        return _aiter_text()

    # ---------- models ----------

    def list_models(self) -> Any:
        """
        List available models.

        Returns:
            Model list
        """
        return self.sync_client.models.list()


# Test function
def test_iflow_client() -> Optional[str]:
    """Test iFlow Client functionality (non-streaming)"""
    try:
        api_key = os.getenv("IFLOW_API_KEY")
        if not api_key:
            print("IFLOW_API_KEY not set, skipping test")
            return None

        client = IFlowClient()
        print("client create success")

        messages = [
            {"role": "user", "content": "Hello, please briefly introduce artificial intelligence"}
        ]

        # Non-streaming test
        response = client.chat_completion(
            messages=messages,
            model="qwen3-coder-plus",
            temperature=0.7,
            max_tokens=500,
            stream=False,
        )
        print("Non-stream API call successful!")
        print(f"Response: {response}")

        # Streaming test
        print("\nStreaming response:")
        stream_iter = client.chat_completion(
            messages=messages,
            model="qwen3-coder-plus",
            temperature=0.7,
            max_tokens=500,
            stream=True,
        )
        for chunk in stream_iter:
            print(chunk, end="", flush=True)
        print()

        return str(response)

    except Exception as e:
        print(f"API call failed: {e}")
        return None


if __name__ == "__main__":
    api_key = os.getenv("IFLOW_API_KEY")
    if api_key:
        test_iflow_client()
    else:
        print("IFLOW_API_KEY not set, skipping test")
