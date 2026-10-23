from __future__ import annotations

import base64
import os
import random
import time
from pathlib import Path
from typing import Any, Callable

from ..config import VisionConfig
from ..errors import VisionError, VisionUnavailable
from ..models import Usage
from .base import VisionResult


class KelpieVisionBackend:
    name = "kelpie"

    def __init__(self, config: VisionConfig) -> None:
        self.config = config
        self.model = (
            config.kelpie.model.strip()
            or os.environ.get("KELPIE_MODEL", "").strip()
            or os.environ.get("LLM_VISION_DEPLOYMENT", "").strip()
            or os.environ.get("LLM_CHAT_DEPLOYMENT", "").strip()
        )
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        base_url = (
            self.config.kelpie.base_url.strip()
            or os.environ.get("KELPIE_PROXY_BASE_URL", "").strip()
        ).rstrip("/")
        if not base_url or not self.model:
            raise VisionUnavailable(
                "Kelpie proxy and model are not configured; set KELPIE_PROXY_BASE_URL "
                "and KELPIE_MODEL or configure vision.kelpie."
            )
        if not base_url.endswith("/openai/v1"):
            base_url += "/openai/v1"
        try:
            import httpx
            from openai import OpenAI
        except ImportError as error:
            raise VisionUnavailable("Install the OpenAI client for Kelpie vision calls.") from error
        self._client = OpenAI(
            base_url=base_url,
            api_key=os.environ.get("KELPIE_PROXY_API_KEY", "unused"),
            http_client=httpx.Client(timeout=self.config.timeout_s, trust_env=True),
            timeout=self.config.timeout_s,
            max_retries=0,
        )
        return self._client

    @staticmethod
    def _prompt(prompt_id: str) -> str:
        root = Path(__file__).resolve().parents[3]
        prompt_path = root / "prompts" / f"{prompt_id}.txt"
        try:
            return prompt_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError as error:
            raise VisionError(f"Prompt file not found: {prompt_path}") from error

    @staticmethod
    def _usage(response: Any) -> Usage:
        usage = getattr(response, "usage", None)
        if usage is None:
            raise VisionError("Kelpie response did not include token usage")

        def value(*names: str) -> int:
            for name in names:
                candidate = getattr(usage, name, None)
                if candidate is None and isinstance(usage, dict):
                    candidate = usage.get(name)
                if candidate is not None:
                    return int(candidate)
            return 0

        return Usage(
            input_tokens=value("input_tokens", "prompt_tokens"),
            output_tokens=value("output_tokens", "completion_tokens"),
            total_tokens=value("total_tokens"),
            estimated=False,
        )

    def _call(self, operation: Callable[[], Any]) -> Any:
        attempts = max(0, self.config.max_retries)
        for attempt in range(attempts + 1):
            try:
                return operation()
            except Exception as error:  # noqa: BLE001 - classify gateway failures
                status = getattr(error, "status_code", None)
                transient = status == 429 or (isinstance(status, int) and status >= 500)
                transient = transient or type(error).__name__ in {
                    "APITimeoutError",
                    "APIConnectionError",
                }
                if not transient or attempt >= attempts:
                    if type(error).__name__ in {"APITimeoutError", "APIConnectionError"}:
                        raise VisionUnavailable(f"Kelpie request unavailable: {error}") from error
                    raise VisionError(f"Kelpie request failed: {error}") from error
                delay = min(2**attempt, 16) + random.random()
                time.sleep(delay)
        raise VisionError("Kelpie retry loop exhausted")

    def complete(self, prompt: str, *, image_png: bytes | None = None) -> VisionResult:
        content: list[dict[str, str]] = [{"type": "input_text", "text": prompt}]
        if image_png is not None:
            encoded = base64.b64encode(image_png).decode("ascii")
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{encoded}",
                }
            )
        started = time.perf_counter()
        response = self._call(
            lambda: self._get_client().responses.create(
                model=self.model,
                input=[{"role": "user", "content": content}],
                max_output_tokens=self.config.max_tokens,
                store=False,
            )
        )
        return VisionResult(
            text=str(getattr(response, "output_text", "") or ""),
            usage=self._usage(response),
            model=self.model,
            latency_s=time.perf_counter() - started,
            request_id=getattr(response, "id", None),
        )

    def describe_image(
        self, image_png: bytes, *, prompt_id: str, lang: str = "auto"
    ) -> VisionResult:
        prompt = self._prompt(prompt_id)
        if lang != "auto":
            prompt = f"Language hint: {lang}\n\n{prompt}"
        encoded = base64.b64encode(image_png).decode("ascii")
        started = time.perf_counter()
        response = self._call(
            lambda: self._get_client().responses.create(
                model=self.model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_image",
                                "image_url": f"data:image/png;base64,{encoded}",
                            },
                        ],
                    }
                ],
                max_output_tokens=self.config.max_tokens,
                store=False,
            )
        )
        return VisionResult(
            text=str(getattr(response, "output_text", "") or ""),
            usage=self._usage(response),
            model=self.model,
            latency_s=time.perf_counter() - started,
            request_id=getattr(response, "id", None),
        )

    def transcribe_page(
        self, image_png: bytes, *, prompt_id: str, lang: str = "auto"
    ) -> VisionResult:
        return self.describe_image(image_png, prompt_id=prompt_id, lang=lang)
