# Phase 0 Discovery

Status: **signed off by the human; Phase 2 complete on 2026-10-22**.

Date: 2026-10-22

This is the canonical Phase 0 report required by `PROJECT-SPEC.md` and
`ARCHITECTURE.md`. The reference project at
`C:\Users\rp99480\dev\ai4tc_webapp` was treated as read-only. No `.env`, service

## Executive Result

The Kelpie integration convention is verified end to end through the local
Kelpie CLI reverse proxy. The reference project uses the Kelpie SDK only for
authentication and the OpenAI Python SDK for an OpenAI-compatible DARE gateway.
The production route is the Responses API, not Chat Completions. Vision content
is sent as base64 data URLs.

Phase 0 is signed off with the documented A3 sample exception. Phases 1 and 2
are complete; the remaining real-document requirement applies before benchmark
work. Docling hard-path artifacts are an enterprise provisioning prerequisite,
not a runtime download.

## Environment

Evidence was collected on the current workstation, not on the future EDAG
machine if those are different.

| Item | Observation | Status |
|---|---|---|
| OS | Windows 11, AMD64 | verified |
| Python | `python --version`: 3.14.7; `py -3 --version`: 3.14.6 | verified, newer than the >=3.11 target |
| CPU | 12 logical processors | verified |
| RAM | 16,802,504,704 bytes, approximately 15.7 GiB | verified |
| pip | 26.2.1 | verified |
| uv | command not found | use pip unless uv is installed on the target machine |
| Docker | `docker compose ps` could not connect to Docker Desktop | not available locally |
| Kelpie CLI | 1.5.4; foreground proxy on `127.0.0.1:18080` | verified |

The Phase 0 packages were installed into the temporary environment
`C:\Users\rp99480\AppData\Local\Temp\opencode\doc2md-phase0-venv`; the
repository was not modified by that installation.

`tesseract` is not installed on this workstation. The enterprise hard path
therefore requires pre-provisioned Docling artifacts; runtime OCR/model
downloads are outside the supported conversion perimeter.

## PDF And Docling

Installed versions in the temporary environment:

| Package | Version |
|---|---:|
| `pdfplumber` | 0.11.10 |
| `pypdfium2` | 5.14.0 |
| `docling` | 2.141.0 |
| `kelpie-sdk` | 1.0.0 |
| `openai` | 1.109.1 |
| `httpx` | 0.28.1 |
| `pydantic` | 2.14.1 |
| `pydantic-settings` | 2.16.1 |
| `tiktoken` | 0.14.0 |
| `pip-licenses` | 5.5.5 |
| `reportlab` | 5.1.0 (synthetic fixture generation only) |

The installed API matches the architecture more closely than the original
placeholder contract:

```text
DocumentConverter(...)
DocumentConverter.convert(source, headers=None, raises_on_error=True,
                          max_num_pages=..., max_file_size=...,
                          page_range=(1, ...), ...)
```

`page_range` exists, so a sub-PDF is not required for the normal routed-page
path. The implementation still needs a small integration test to verify exact
page numbering and the configured OCR/table options.

### Conversion Smoke Test

A synthetic two-page PDF was generated in the temporary directory. Docling
downloaded its model artifacts from Hugging Face and converted both pages on
CPU successfully.

| Measurement | Result |
|---|---:|
| `DocumentConverter()` initialization | 0.23 s |
| two-page `convert()` call | 205.37 s |
| approximate conversion time per page | 102.7 s |
| process RSS before conversion | 369.4 MiB |
| process RSS after conversion | 1,152.9 MiB |
| result page count | 2 |
| `export_to_markdown()` | available |

The conversion time includes model loading during the first conversion. These
numbers are a first cold-start observation, not a benchmark. The console also
reported unauthenticated Hugging Face downloads and Windows symlink-cache
warnings. Telemetry settings from the project spec still need to be applied by
the project runtime.

## Kelpie Reference Implementation

### Primary Files

| Reference path | Evidence |
|---|---|
| `utils/kelpie_client.py` | central lazy client, auth, OpenAI transport, text and embedding calls |
| `utils/llm_loader.py` | runtime model selection and LangChain wrapping |
| `config/llm_gateway_settings.py` | environment aliases and timeout settings |
| `.env.example` | documented environment variable names and example deployment names |
| `backend/services/ingestion/vision/pdf_extraction.py` | PDF rendering and multimodal message shape |
| `backend/services/ingestion/vision/image_extraction.py` | standalone image-plus-text shape |
| `tests/check_kelpie_install.py` | raw Responses API text diagnostic |
| `tests/check_kelpie_vision.py` | real multimodal diagnostic |
| `tests/check_kelpie_langchain_wrap.py` | Responses API LangChain wrapper |
| `utils/llm_errors.py` | retry and failure classification |

The added local documentation is under `docs/kelpie_docs/`. Its source HTML
identifies the internal Kelpie manual. It documents OAuth 2.0 Authorization
Code + PKCE, the OIDC host `oauth.ai.container.edag`, Windows storage under
`%APPDATA%\kelpie\`, access-token caching, and refresh behavior. It does not
document the DARE LLM payload or model catalog, so those facts still come from
the reference source and the runtime probe.

### Transport And Authentication

The reference uses:

```text
kelpie-sdk==1.0.0
from kelpie import KelpieClient
KelpieClient.from_service_account(KELPIE_SERVICE_ACCOUNT_KEY_FILE, ...)
```

`get_kelpie_client()` is lazy and cached. It reads the credential path from
`KELPIE_SERVICE_ACCOUNT_KEY_FILE` and passes `kelpie.get_access_token` as the
OpenAI SDK `api_key` callable. The token is therefore refreshed by Kelpie when
needed rather than stored in this repository.

The gateway client is constructed as:

```text
OpenAI(
    base_url=<LLM_GATEWAY_ENDPOINT>/openai/v1,
    api_key=kelpie.get_access_token,
    http_client=httpx.Client(..., trust_env=True),
    max_retries=0,
)
```

The reference's normal endpoint host is
`https://models.ai.container.edag`; the path suffix `/openai/v1` is appended by
`utils/kelpie_client.py::_build_base_url()`.

The following names are configuration names only; no values were recorded:

- `KELPIE_SERVICE_ACCOUNT_KEY_FILE`
- `LLM_GATEWAY_ENDPOINT`
- `LLM_GATEWAY_API_KEY` (legacy compatibility field, not the Kelpie bearer token)
- `LLM_CHAT_DEPLOYMENT`
- `LLM_VISION_DEPLOYMENT`
- `LLM_EMBEDDING_DEPLOYMENT`
- `LLM_TIMEOUT` / `LLM_REQUEST_TIMEOUT_SECONDS`
- `LLM_MAX_RETRIES` (declared in settings but not used by the transport)
- `SSL_CERT_FILE` / `SSL_CERT_DIR`

The new Kelpie manual describes interactive CLI credentials in `%APPDATA%`,
whereas the current workstation also exposes a local reverse-proxy mode. These
are different authentication modes and must not be conflated.

The local proxy was observed as:

```text
kelpie serve run
base URL: http://127.0.0.1:18080/openai/v1
```

`kelpie serve status` reports only the background-daemon state and returned
`No daemon is running` while the foreground process was listening. A direct
`GET /openai/v1/models` returned the model catalog recorded below.

### Model Selection

Resolution in `utils/llm_loader.py` is:

1. explicit runtime config;
2. project `project_model_config`;
3. environment/settings fallback.

For vision, only the deployment name is overridden in this order:

1. project `vision_deployment`;
2. `LLM_VISION_DEPLOYMENT`;
3. the resolved chat deployment.

Endpoint and credentials remain from the winning runtime-config source.

### Request Shapes

Text calls use the Responses API:

```text
client.responses.create(
    model=model,
    instructions=instructions,
    input=input,
    max_output_tokens=max_output_tokens,
    store=False,
    temperature=0,
)
```

The reference reads `response.output_text` for direct calls.

Vision calls in the reference use LangChain's equivalent of this content:

```json
{
  "content": [
    {"type": "text", "text": "..."},
    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
  ]
}
```

`load_gpt_model(vision=True)` sets `use_responses_api=True` and omits
`temperature` and `top_p`, because the reference states that vision deployments
reject those parameters. Chat Completions is retained only as a truthy
compatibility field for LangChain validation; effective calls use
`root_client.responses.create()` / the async equivalent. The reference
documents `403 endpoint_deprecated` for the old Chat Completions path.

The future thin client can use the native Responses API equivalent:

```json
{
  "input": [{
    "role": "user",
    "content": [
      {"type": "input_text", "text": "..."},
      {"type": "input_image", "image_url": "data:image/jpeg;base64,..."}
    ]
  }]
}
```

That mapping is implemented and redacted in `scripts/kelpie_probe.py` and was
verified through the local proxy.

### Response And Usage

The reference directly exposes text via `response.output_text` and embeddings
via `response.data[*].embedding`. Its LangChain diagnostic reads
`AIMessage.usage_metadata`, but the production helper `send_prompt()` returns
only text and discards usage. The raw Responses object is therefore the safest
place for `KelpieVisionBackend` to capture `input_tokens`, `output_tokens`, and
`total_tokens`.

The local proxy returned usage on all successful calls. The probe observed
`response.output` items of types `reasoning` and `message`, with content types
`reasoning_text` and `output_text`. If a service response has no usage, the
doc2md adapter must use its configured estimation method and set `estimated=true`
as required by the architecture.

### Timeouts, Retries, And Limits

Static reference behavior:

- default socket/request timeout is 600 seconds through `LLM_TIMEOUT`;
- OpenAI SDK retries are explicitly disabled (`max_retries=0`);
- application retry logic retries only HTTP 502, after 5, 10, and 25 seconds;
- connection failures and timeouts become user-facing gateway errors;
- PDF vision batches use two pages at 120 DPI and recursively split a batch on
  HTTP 413 / request-too-large errors;
- image ingestion sends original PNG/JPEG/WEBP bytes and has no fixed byte or
  pixel maximum in the reference;
- no dedicated 429/rate-limit policy is present in the reference;
- `LLM_MAX_RETRIES` exists in settings but `_gateway_max_retries()` returns 0.

This differs from the doc2md contract, which requires timeout plus jittered
retries for timeouts, 429, and 5xx. The doc2md adapter must implement its own
policy behind `VisionBackend`, rather than blindly inheriting the reference's
502-only policy. The real maximum accepted image size and safe concurrency are
open until the probe and a controlled size/concurrency test run.

### TLS And Proxy Quirks

The reference uses `httpx` with `trust_env=True`. Its code reports a corporate
TLS-inspection proxy and prepares a CA bundle through `SSL_CERT_FILE`; it never
uses `verify=False`. The copied Kelpie manual documents the OIDC and local token
storage paths but does not define a DARE gateway proxy header.

For doc2md, use the existing environment/system CA configuration or a documented
machine setup. Do not copy the reference repository's certificates or secrets
into doc2md without an explicit licensing/security decision.

## Model Catalog Assessment

| Deployment name found in the reference | Intended role | Vision-capable | Locally hosted | Evidence status |
|---|---|---:|---:|---|
| `gpt-6-luna-gwc` | catalog chat deployment | not tested | `azure-gwc`, not accepted as local | proxy catalog |
| `gpt-5.6-luna-gwc` | current chat default in reference | not tested | `azure-gwc`, not accepted as local | proxy catalog |
| `DARE-NoCloud-Nova` | text/judge candidate | **no**: image probe returned 400 | `vllm-qwen3-8-flash-next`, local candidate | live probe |
| `DARE-NoCloud-Helios` | vision candidate | **yes**: image probe completed | `vllm-qwen3-8-27b`, local candidate | live probe |
| `qwen3-embedding` | embeddings, expected 1024 dimensions | no | not applicable | static config |

Recommended split, subject to confirmation: `DARE-NoCloud-Helios` for vision and
`DARE-NoCloud-Nova` for the text judge. Nova can judge extracted text but cannot
receive page images; Helios should be used for image-aware judging if that is a
requirement.

## Other Phase 0 Items

### Current System Baseline

The current EDAG software is explicitly unavailable until next week in the
project spec. Its CLI/API invocation and token source remain pending. This is
not required to begin the text-only Phase 1 once Phase 0 is signed off, and it
remains a Phase 7 dependency.

### Sample Documents

Two confidential samples are present under `docs/samples/` and are git-ignored:

| File | Pages | Size |
|---|---:|---:|
| `Lastenheft_ Bratpfannenradio_IMG.pdf` | 5 | 1,586,583 bytes |
| `Lastenheft Abschmink-Flinte_002 (Gant).pdf` | 5 | 264,296 bytes |

Only metadata was inspected; content was not copied or printed. The spec
requires at least six documents in `samples/`; the human accepted a temporary
A3 exception for Phase 1. Real samples remain required before benchmark work.

### Token Estimation

`tiktoken==0.14.0` is installed in the temporary environment and
`cl100k_base` loads offline. A smoke calculation for
`Übergröße and office with umlauts Straße` returned 13 tokens. The actual
Kelpie deployment encoding was not confirmed, so this is suitable only as a
flagged estimate until the service reports usage or the model owner confirms an
encoding. German text must remain covered by tests.

### Licensing

The full temporary environment report is in `docs/licenses.md`. The
`pip-licenses --fail-on "GPL;AGPL;LGPL;SSPL"` check found no matching forbidden
license. However, Docling's installed CPU dependency tree includes `torch` with
an SPDX expression containing `BSL-1.0`; BSL is not in the project's explicit
allow-list. The human accepted this as a documented Phase 0 exception on
2026-10-22.

## Recommended Integration

Use a thin native adapter in `src/doc2md/vision/kelpie.py` after sign-off:

- use the authenticated local proxy as the primary transport on the EDAG
  workstation, with the direct `kelpie-sdk` transport retained as the reference
  deployment option;
- depend on `openai` and keep the proxy/service-account choice behind the thin
  adapter; do not depend on `ai4tc_webapp` or its LangChain wrapper;
- create the proxy client lazily and normalize its base URL to `/openai/v1`;
- use `responses.create()` for both text and image-plus-text calls;
- omit `temperature` and `top_p` for vision calls;
- extract response usage before returning `VisionResult`, with estimation only
  when usage is absent;
- keep timeout/retry policy in doc2md and add 429/5xx handling required by the
  architecture;
- bound concurrency conservatively at one until a target-machine load test
  establishes a safe value;
- redact request/response data in logs and never log image bytes or full prompts.

Do not import the reference project and do not copy its implementation. The
recommendation is a thin reimplementation; the local proxy convention is live,
while the direct service-account path remains static-reference evidence.

## Open Items

- [x] Run `scripts/kelpie_probe.py` through the local proxy with text and image
  calls.
- [x] Record redacted response shapes, usage fields, and latency in
  `docs/kelpie-example.md`.
- [x] Confirm the model split: `DARE-NoCloud-Helios` for vision and
  `DARE-NoCloud-Nova` for judge.
- [x] Select the local Kelpie proxy as the primary transport.
- [x] Human accepted a documented BSL-1.0 `torch` exception for this discovery.
- [x] Accept the A3 exception: two real five-page samples now, and synthetic
  fixtures for Phase 1 until four additional documents arrive.
- [x] Confirm Python 3.14 as the current target runtime.
- [x] Set the initial safe vision concurrency to `max_workers=1`; load testing
  remains a later tuning task.

Human sign-off: `go` was given on 2026-10-22 with the A3 sample-set exception
above. Four additional real documents remain required before benchmark work.

## Follow-up hard-path verification (2026-10-27)

The existing Hugging Face cache contains the Docling TableFormer artifacts but
does not contain the required `docling-project/docling-layout-heron` directory
inside the configured artifact tree. The official command
`docling-tools models download-hf-repo` was attempted in a temporary directory
and failed because the workstation corporate TLS chain presents a self-signed
certificate. TLS verification was not disabled. No model artifacts or sample
PDFs were added to the repository. The scanned OCR acceptance remains blocked
until the enterprise artifact bundle is provisioned through the approved
machine setup.

## Follow-up hard-path verification (2026-10-27)

The existing Hugging Face cache contains the Docling TableFormer artifacts but
does not contain the required `docling-project/docling-layout-heron` directory
inside the configured artifact tree. The official command
`docling-tools models download-hf-repo` was attempted in a temporary directory
and failed because the workstation corporate TLS chain presents a self-signed
certificate. TLS verification was not disabled. No model artifacts or sample
PDFs were added to the repository. The scanned OCR acceptance remains blocked
until the enterprise artifact bundle is provisioned through the approved
machine setup.
