"""Provider-neutral image generation contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class GenerationRequest:
    """One provider-neutral image-generation request."""

    asset_id: str
    prompt: str
    model: str
    size: str
    quality: str
    output_format: str
    transparent: bool


@dataclass(frozen=True)
class GenerationResult:
    """Raw provider result before deterministic post-processing."""

    data: bytes
    model: str
    metadata: dict[str, object] = field(default_factory=dict)


class ImageProvider(Protocol):
    """Minimal interface implemented by concrete image providers."""

    name: str

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate one image and return its raw encoded bytes."""
        ...
