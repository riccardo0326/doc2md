# Kelpie Probe Example

Status: **verified through the local Kelpie proxy** on 2026-10-22.

The probe is `scripts/kelpie_probe.py`. It is a standalone script that does not
import `ai4tc_webapp` and does not print secrets or model output. It supports
the reference service-account path and the local Kelpie CLI proxy. The verified
run used `http://127.0.0.1:18080`, started with `kelpie serve run`:

1. The local proxy supplies authentication, or `KelpieClient.from_service_account(...)`
   obtains a refreshing access token for the direct path.
2. `OpenAI(base_url=<endpoint>/openai/v1, ...)` is created.
3. `client.responses.create(...)` is called once with text and once with a native
   Responses API `input_text` + `input_image` data URL.
4. Only request shape, latency, output block types, output length, and token usage
   fields are printed.

Verified proxy run:

```powershell
$env:KELPIE_PROXY_BASE_URL = "http://127.0.0.1:18080"
python scripts/kelpie_probe.py --model DARE-NoCloud-Helios --max-output-tokens 400
```

Redacted observations:

```text
models: gpt-6-luna-gwc (azure-gwc), DARE-NoCloud-Nova (vllm-qwen3-8-flash-next), DARE-NoCloud-Helios (vllm-qwen3-8-27b), gpt-5.6-luna-gwc (azure-gwc)
DARE-NoCloud-Nova text: 0.885 s, usage 73/38/111, completed; image: HTTP 400 input_image validation error
DARE-NoCloud-Helios text: 1.555 s, usage 73/76/149, completed; image: 1.312 s, usage 131/107/238, completed, output 54 chars
```

The image probe used a one-pixel PNG data URL. The maximum accepted image size
and safe concurrent request count are not established yet.

Direct service-account run, if the target deployment uses the reference app's
transport, requires the variable names below. Never put their values in this
repository:

```powershell
$env:KELPIE_SERVICE_ACCOUNT_KEY_FILE = "<path-to-service-account-json>"
$env:LLM_GATEWAY_ENDPOINT = "<DARE-gateway-host>"
$env:LLM_VISION_DEPLOYMENT = "<vision-deployment>"
python scripts/kelpie_probe.py --image path\to\small-test-image.png
```

The direct service-account path was not exercised because the local proxy was
available and no service-account environment variables were present in the
session.

## Expected Redacted Shapes

Text request:

```json
{
  "endpoint": "/openai/v1/responses",
  "input": "string",
  "model": "<deployment-name>",
  "auth": "Kelpie access-token callable"
}
```

Image-plus-text request:

```json
{
  "endpoint": "/openai/v1/responses",
  "input": "user.content[input_text,input_image]",
  "image": "data-url-base64"
}
```

The reference application expresses the same multimodal content through
LangChain as `{"type": "text"}` plus
`{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}`.
The probe uses the corresponding native Responses API shape so the future thin
client does not need LangChain as a runtime dependency.

## Sources

- `scripts/kelpie_probe.py` in this repository.
- `C:\Users\rp99480\dev\ai4tc_webapp\utils\kelpie_client.py`.
- `C:\Users\rp99480\dev\ai4tc_webapp\backend\services\ingestion\vision\pdf_extraction.py`.
- `C:\Users\rp99480\dev\ai4tc_webapp\tests\check_kelpie_vision.py`.
- `docs/kelpie_docs/Configuration - Kelpie CLI.html`.
- `docs/kelpie_docs/Token Lifecycle - Kelpie CLI.html`.
