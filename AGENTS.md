# Agent Rules

1. At the start of every new chat and before answering every user prompt, read `PROJECT-SPEC.md` and `ARCHITECTURE.md` in full; treat them as the technical source of truth.
2. Work on one phase at a time. Do not start Phase 1 until Phase 0 is documented and explicitly signed off by the human.
3. Use English for code, comments, tests, and commit messages; record design decisions in `docs/decisions.md`.
4. Never invent or bypass the Kelpie contract. Use only the reference implementation, `docs/kelpie_docs`, and the redacted probe evidence.
5. Keep credentials, confidential samples, model responses, and token values out of the repository; names of environment variables are safe to document.
6. Follow the spec's tests-first workflow and preserve the architecture's replaceable adapters and lazy heavy dependencies.
