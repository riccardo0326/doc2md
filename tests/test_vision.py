from __future__ import annotations

import pytest

from doc2md.errors import VisionError
from doc2md.vision.fake import FakeVisionBackend


def test_fake_vision_backend_is_deterministic() -> None:
    backend = FakeVisionBackend()

    first = backend.describe_image(b"image-bytes", prompt_id="describe_image.v1")
    second = backend.describe_image(b"image-bytes", prompt_id="describe_image.v1")

    assert first == second
    assert first.text.startswith("[fake description of ")
    assert first.usage.total_tokens == first.usage.input_tokens + first.usage.output_tokens
    assert first.usage.estimated


def test_fake_vision_backend_can_fail_selected_hashes() -> None:
    backend = FakeVisionBackend(fail_on={"2c86"})

    with pytest.raises(VisionError):
        backend.describe_image(b"image-bytes", prompt_id="describe_image.v1")
