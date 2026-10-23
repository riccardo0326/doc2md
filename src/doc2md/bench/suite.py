from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..errors import ConfigError


class SuiteDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    path: Path
    tags: list[str] = Field(default_factory=list)


class SuitePipeline(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str


class BaselineConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    command: str | None = None


class BenchmarkSuite(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    repetitions: int = 3
    cold_cache: bool = True
    documents: list[SuiteDocument]
    pipelines: list[SuitePipeline]
    baseline_current: BaselineConfig | None = None


_PIPELINES = {"tiered", "full-vision", "docling-only", "baseline_current"}


def load_suite(path: str | Path) -> BenchmarkSuite:
    suite_path = Path(path)
    try:
        with suite_path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"unable to load benchmark suite {suite_path}: {error}") from error

    suite_data = raw.get("suite")
    if not isinstance(suite_data, dict):
        raise ConfigError("benchmark suite must contain a [suite] table")
    documents_data = raw.get("documents", [])
    pipelines_data = raw.get("pipelines", [])
    if not isinstance(documents_data, list) or not isinstance(pipelines_data, list):
        raise ConfigError("benchmark suite documents and pipelines must be arrays")
    try:
        documents = [
            SuiteDocument.model_validate(
                {**document, "path": suite_path.parent / str(document["path"])}
            )
            for document in documents_data
        ]
        pipelines = [SuitePipeline.model_validate(pipeline) for pipeline in pipelines_data]
        baseline = (
            BaselineConfig.model_validate(raw["baseline_current"])
            if "baseline_current" in raw
            else None
        )
        suite = BenchmarkSuite(
            name=str(suite_data["name"]),
            repetitions=int(suite_data.get("repetitions", 3)),
            cold_cache=bool(suite_data.get("cold_cache", True)),
            documents=documents,
            pipelines=pipelines,
            baseline_current=baseline,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ConfigError(f"invalid benchmark suite {suite_path}: {error}") from error
    if suite.repetitions < 1:
        raise ConfigError("benchmark suite repetitions must be at least 1")
    unknown = sorted({pipeline.name for pipeline in suite.pipelines} - _PIPELINES)
    if unknown:
        raise ConfigError(f"unknown benchmark pipeline(s): {', '.join(unknown)}")
    if not suite.documents:
        raise ConfigError("benchmark suite must contain at least one document")
    if not suite.pipelines:
        raise ConfigError("benchmark suite must contain at least one pipeline")
    return suite
