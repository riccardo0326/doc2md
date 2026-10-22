"""Probe the Kelpie convention used by the ai4tc_webapp reference project.

The probe intentionally uses only environment-variable names and never prints
credentials, access tokens, image bytes, or full model responses. It exercises
one text Responses API call and one text-plus-image Responses API call. Set
``KELPIE_PROXY_BASE_URL`` to use an authenticated local Kelpie daemon; otherwise
the reference project's service-account SDK path is used.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

_DEFAULT_IMAGE_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
    "AScY42YAAAAASUVORK5CYII="
)
_DATA_URL_RE = re.compile(r"data:image/[^,]+,[A-Za-z0-9+/=_-]+")


def _arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=(
            os.environ.get("KELPIE_MODEL", "").strip()
            or os.environ.get("LLM_VISION_DEPLOYMENT", "").strip()
            or os.environ.get("LLM_CHAT_DEPLOYMENT", "").strip()
        ),
        help="deployment to probe (default: KELPIE_MODEL or LLM_VISION_DEPLOYMENT)",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="list redacted model metadata and exit without an AI call",
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="optional image path; defaults to a one-pixel PNG",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("LLM_TIMEOUT", "120")),
        help="HTTP timeout in seconds (default: LLM_TIMEOUT or 120)",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=int(os.environ.get("KELPIE_MAX_OUTPUT_TOKENS", "400")),
        help="maximum output tokens for each call (default: 400)",
    )
    return parser


def _usage(response: Any) -> dict[str, int] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None

    def value(*names: str) -> int:
        for name in names:
            candidate = getattr(usage, name, None)
            if candidate is None and isinstance(usage, dict):
                candidate = usage.get(name)
            if candidate is not None:
                return int(candidate)
        return 0

    return {
        "input_tokens": value("input_tokens", "prompt_tokens"),
        "output_tokens": value("output_tokens", "completion_tokens"),
        "total_tokens": value("total_tokens"),
    }


def _redact_error(error: Exception) -> str:
    message = _DATA_URL_RE.sub("data:image/[redacted]", str(error))
    message = " ".join(message.split())
    return message[:400]


def _image_data(path: Path | None) -> tuple[str, str]:
    if path is None:
        return "image/png", _DEFAULT_IMAGE_B64

    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return mime, base64.b64encode(path.read_bytes()).decode("ascii")


def _record(kind: str, started: float, response: Any, request_shape: dict[str, Any]) -> None:
    output_text = str(getattr(response, "output_text", "") or "")
    output_items = getattr(response, "output", None) or []
    output_item_types = [getattr(item, "type", None) for item in output_items]
    content_types = [
        getattr(content, "type", None)
        for item in output_items
        for content in (getattr(item, "content", None) or [])
    ]
    print(
        json.dumps(
            {
                "kind": kind,
                "latency_s": round(time.perf_counter() - started, 3),
                "request_shape": request_shape,
                "response_shape": {
                    "has_output_text": bool(output_text),
                    "output_chars": len(output_text),
                    "output_item_types": output_item_types,
                    "content_types": content_types,
                    "status": getattr(response, "status", None),
                    "usage": _usage(response),
                },
            },
            sort_keys=True,
        )
    )


def main() -> int:
    args = _arg_parser().parse_args()
    proxy_base_url = os.environ.get("KELPIE_PROXY_BASE_URL", "").strip()
    key_file = os.environ.get("KELPIE_SERVICE_ACCOUNT_KEY_FILE", "").strip()
    endpoint = os.environ.get("LLM_GATEWAY_ENDPOINT", "").strip()
    model = args.model.strip()

    missing: list[tuple[str, str]] = []
    if not args.list_models:
        missing.append(("KELPIE_MODEL or LLM_VISION_DEPLOYMENT", model))
    if not proxy_base_url:
        missing.extend(
            (name, value)
            for name, value in (
                ("KELPIE_SERVICE_ACCOUNT_KEY_FILE", key_file),
                ("LLM_GATEWAY_ENDPOINT", endpoint),
            )
            if not value
        )
    missing = [name for name, value in missing if not value]
    if missing:
        print("Missing required configuration: " + ", ".join(missing), file=sys.stderr)
        return 2

    credential_path: Path | None = None
    if not proxy_base_url:
        credential_path = Path(key_file).expanduser()
        if not credential_path.is_file():
            print(
                "KELPIE_SERVICE_ACCOUNT_KEY_FILE does not point to a readable file "
                "(path redacted).",
                file=sys.stderr,
            )
            return 2

    try:
        import httpx
        from kelpie import KelpieClient
        from openai import OpenAI
    except ImportError as error:
        print(f"Missing probe dependency: {type(error).__name__}: {error}", file=sys.stderr)
        return 2

    base_url = (proxy_base_url or endpoint).rstrip("/")
    if not base_url.endswith("/openai/v1"):
        base_url += "/openai/v1"
    http_client = httpx.Client(timeout=args.timeout, trust_env=True)
    try:
        if proxy_base_url:
            api_key = os.environ.get("KELPIE_PROXY_API_KEY", "unused")
        else:
            assert credential_path is not None
            kelpie = KelpieClient.from_service_account(
                str(credential_path),
                http_client=http_client,
            )
            api_key = kelpie.get_access_token
        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=http_client,
            timeout=args.timeout,
            max_retries=0,
        )

        if args.list_models:
            models = client.models.list()
            print(
                json.dumps(
                    [
                        {
                            "id": item.id,
                            "owned_by": getattr(item, "owned_by", None),
                        }
                        for item in models.data
                    ],
                    sort_keys=True,
                )
            )
            return 0

        started = time.perf_counter()
        text_response = client.responses.create(
            model=model,
            instructions="You are a concise technical assistant.",
            input="Reply with exactly one word: ok. Do not reason aloud.",
            max_output_tokens=args.max_output_tokens,
            store=False,
            temperature=0,
        )
        _record(
            "text",
            started,
            text_response,
            {"endpoint": "/openai/v1/responses", "input": "string"},
        )

        mime, encoded_image = _image_data(args.image)
        image_message = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Describe the image in one short sentence. Do not reason aloud.",
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime};base64,{encoded_image}",
                    },
                ],
            }
        ]
        started = time.perf_counter()
        image_response = client.responses.create(
            model=model,
            input=image_message,
            max_output_tokens=args.max_output_tokens,
            store=False,
        )
        _record(
            "image_text",
            started,
            image_response,
            {
                "endpoint": "/openai/v1/responses",
                "input": "user.content[input_text,input_image]",
                "image": "data-url-base64",
            },
        )
    except Exception as error:  # noqa: BLE001 - the probe must report any gateway failure
        status = getattr(error, "status_code", None)
        suffix = f" status_code={status}" if status is not None else ""
        message = f"Probe failed: {type(error).__name__}{suffix}: {_redact_error(error)}"
        print(message, file=sys.stderr)
        return 1
    finally:
        http_client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
