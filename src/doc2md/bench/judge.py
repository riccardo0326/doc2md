from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from ..config import Config, VisionConfig
from ..vision.kelpie import KelpieVisionBackend

CRITERIA = (
    "text_fidelity",
    "special_characters",
    "table_fidelity",
    "figure_usefulness",
    "reading_order",
)


class JudgeParseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    scores: dict[str, int] = Field(default_factory=dict)
    judge_error: str | None = None


class JudgeBackend(Protocol):
    def judge(self, prompt: str, *, image_png: bytes | None = None) -> str: ...


class KelpieJudgeBackend:
    def __init__(self, config: VisionConfig) -> None:
        self._vision = KelpieVisionBackend(config)

    def judge(self, prompt: str, *, image_png: bytes | None = None) -> str:
        return self._vision.complete(prompt, image_png=image_png).text


def _prompt_prefix() -> str:
    path = Path(__file__).resolve().parents[3] / "prompts" / "judge.v1.txt"
    return path.read_text(encoding="utf-8").strip()


def parse_judge_response(text: str) -> JudgeParseResult:
    decoder = json.JSONDecoder()
    parsed: object | None = None
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[index:])
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(parsed, dict):
        return JudgeParseResult(judge_error="response did not contain a JSON object")
    scores: dict[str, int] = {}
    for criterion in CRITERIA:
        value = parsed.get(criterion)
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 2:
            return JudgeParseResult(judge_error=f"invalid score for {criterion}")
        scores[criterion] = value
    return JudgeParseResult(scores=scores)


def judge_run(
    run_dir: str | Path,
    *,
    backend: JudgeBackend | None = None,
    config: Config | None = None,
) -> Path:
    directory = Path(run_dir)
    review_path = directory / "review" / "review_sheet.csv"
    if backend is None:
        backend = KelpieJudgeBackend((config or Config()).vision)
    records: list[dict[str, object]] = []
    with review_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for label in sorted(
                key.removeprefix("output_") for key in row if key.startswith("output_")
            ):
                prompt = (
                    _prompt_prefix()
                    + "\n\nScore the candidate output below using integer scores from 0 to 2. "
                    f"Return JSON with exactly these keys: {', '.join(CRITERIA)}.\n\n"
                    f"Candidate output:\n{row[f'output_{label}']}"
                )
                image_path = row.get("page_image_path", "")
                image_file = Path(image_path)
                if image_path and not image_file.is_absolute():
                    image_file = directory / image_file
                image = image_file.read_bytes() if image_path and image_file.is_file() else None
                try:
                    parsed = parse_judge_response(backend.judge(prompt, image_png=image))
                    records.append(
                        {
                            "sample_id": row["sample_id"],
                            "label": label,
                            "scores": parsed.scores,
                            "judge_error": parsed.judge_error,
                        }
                    )
                except Exception as error:  # noqa: BLE001 - judge failures are isolated
                    records.append(
                        {
                            "sample_id": row["sample_id"],
                            "label": label,
                            "scores": {},
                            "judge_error": f"{type(error).__name__}: {error}",
                        }
                    )
    path = directory / "scores_judge.json"
    path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
