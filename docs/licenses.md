# Phase 0 License Report

Generated from the temporary Phase 0 environment on 2026-10-22 with
`pip-licenses==5.5.5 --format=markdown`. This is the complete installed
dependency tree for the Phase 0 verification environment, including
`docling`, `kelpie-sdk`, `openai`, `tiktoken`, and the synthetic-PDF test tool.
It is not yet the final project lockfile.

The explicit check
`pip-licenses --fail-on "GPL;AGPL;LGPL;SSPL"` passed. `torch` reports a
combined license expression containing `BSL-1.0`, which is outside the
allow-list in `PROJECT-SPEC.md`. The human accepted this as a documented Phase
0 exception on 2026-10-22; the exception is recorded in `docs/decisions.md`.

| Name | Version | License |
|---|---:|---|
| Faker | 40.43.0 | MIT |
| Jinja2 | 3.1.6 | BSD |
| MarkupSafe | 3.0.4 | BSD-3-Clause |
| PyJWT | 2.15.1 | MIT |
| PyYAML | 6.0.3 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| accelerate | 1.15.0 | Apache |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| attrs | 26.1.0 | MIT |
| beautifulsoup4 | 4.15.0 | MIT |
| certifi | 2026.10.19 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| colorama | 0.4.6 | BSD |
| colorlog | 6.12.0 | MIT |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| defusedxml | 0.7.1 | PSF |
| dill | 0.4.1 | BSD |
| distro | 1.9.0 | Apache |
| doclang | 0.7.3 | Apache-2.0 |
| docling | 2.141.0 | MIT |
| docling-core | 2.103.1 | MIT |
| docling-ibm-models | 4.0.4 | MIT |
| docling-parse | 7.22.4 | MIT |
| docling-slim | 2.141.0 | MIT |
| et-xmlfile | 2.0.0 | MIT |
| filelock | 4.2.4 | MIT |
| filetype | 1.2.0 | MIT |
| fsspec | 2026.9.0 | BSD-3-Clause |
| h11 | 0.16.0 | MIT |
| hf-xet | 1.7.0 | Apache-2.0 |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD |
| huggingface-hub | 1.33.0 | Apache |
| idna | 3.20 | BSD-3-Clause |
| jiter | 0.17.0 | MIT |
| jsonref | 1.1.0 | MIT |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| kelpie-sdk | 1.0.0 | Apache-2.0 |
| langcodes | 3.5.1 | MIT |
| latex2mathml | 3.81.1 | MIT |
| lxml | 6.1.3 | BSD-3-Clause |
| mail-parser | 4.8.0 | Apache-2.0 |
| markdown-it-py | 4.2.0 | MIT |
| marko | 2.2.4 | MIT |
| mdurl | 0.1.2 | MIT |
| mpire | 2.10.2 | MIT |
| mpmath | 1.3.0 | BSD |
| multiprocess | 0.70.19 | BSD |
| networkx | 3.7 | BSD-3-Clause |
| numpy | 2.5.4 | BSD-3-Clause / 0BSD / MIT / Zlib / CC0-1.0 |
| olefile | 0.47 | BSD |
| omegaconf | 2.4.0 | BSD |
| openai | 1.109.1 | Apache |
| opencv-python-headless | 5.0.0.93 | Apache |
| openpyxl | 3.1.5 | MIT |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pandas | 3.1.0 | BSD-3-Clause |
| pdfminer.six | 20260107 | MIT |
| pdfplumber | 0.11.10 | MIT |
| pillow | 12.3.0 | MIT-CMU |
| pluggy | 1.7.0 | MIT |
| polyfactory | 3.5.0 | MIT |
| psutil | 7.2.2 | BSD-3-Clause |
| pyclipper | 1.4.0 | MIT |
| pycparser | 3.11 | BSD-3-Clause |
| pydantic | 2.14.1 | MIT |
| pydantic-settings | 2.16.1 | MIT |
| pydantic-core | 2.50.1 | MIT |
| pylatexenc | 2.11 | MIT |
| pypdfium2 | 5.14.0 | BSD-3-Clause / Apache-2.0 / dependency licenses |
| python-dateutil | 3.0.0 | Apache / BSD |
| python-docx | 1.2.0 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| python-oxmsg | 0.0.2 | MIT |
| python-pptx | 1.0.2 | MIT |
| pywin32 | 312 | PSF |
| rapidocr | 3.10.0 | Apache-2.0 |
| referencing | 0.37.0 | MIT |
| regex | 2026.9.29 | Apache-2.0 / CNRI-Python |
| reportlab | 5.1.0 | BSD |
| requests | 2.34.2 | Apache |
| rich | 15.0.0 | MIT |
| rpds-py | 2026.9.1 | MIT |
| rtree | 1.4.1 | MIT |
| safetensors | 0.8.0 | Apache |
| scipy | 1.18.1 | BSD |
| semchunk | 3.2.5 | MIT |
| shapely | 2.2.0 | BSD-3-Clause |
| shellingham | 1.5.4 | ISC |
| six | 1.17.0 | MIT |
| sniffio | 1.3.1 | Apache / MIT |
| soupsieve | 3.0.4 | MIT |
| sympy | 1.14.0 | BSD |
| tabulate | 0.10.0 | MIT |
| tiktoken | 0.14.0 | MIT |
| tokenizers | 0.23.3 | Apache |
| torch | 2.14.1 | Apache / BSD / BSL-1.0 / MIT |
| torchvision | 0.29.1 | BSD |
| tqdm | 4.70.1 | MPL-2.0 / MIT |
| transformers | 5.20.2 | Apache-2.0 |
| tree-sitter | 0.26.0 | MIT |
| tree-sitter-c | 0.24.2 | MIT |
| tree-sitter-javascript | 0.25.0 | MIT |
| tree-sitter-python | 0.25.0 | MIT |
| tree-sitter-typescript | 0.23.2 | MIT |
| typer | 0.26.8 | MIT |
| typing-inspection | 0.4.4 | MIT |
| typing-extensions | 4.16.0 | PSF-2.0 |
| tzdata | 2026.5 | Apache-2.0 |
| urllib3 | 2.8.0 | MIT |
| websockets | 16.1.1 | BSD-3-Clause |
| xlsxwriter | 3.3.0 | BSD-2-Clause |
