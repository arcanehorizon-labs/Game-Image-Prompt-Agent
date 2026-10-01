"""OpenAI Images API provider adapter."""
from __future__ import annotations

import base64
import os
from typing import Any

from .base import GenerationRequest, GenerationResult


class OpenAIImagesProvider:
    """Generate image bytes through the OpenAI Images API."""

    name = "openai"
    supported_models = {
        "gpt-image-2.5-flare",
        "gpt-image-2.5-sunburst",
    }

    def __init__(self, api_key: str | None = None, client: Any | None = None) -> None:
        if client is not None:
            self._client = client
            return

        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "OPENAI_API_KEY is required for OpenAI image generation. "
                "Store it in the environment, not in the repository."
            )

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ValueError(
                "The OpenAI provider requires the 'openai' Python package. "
                "Reinstall GIPA with its current dependencies."
            ) from exc

        self._client = OpenAI(api_key=key)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Call the Images API and decode the returned base64 image."""
        if request.model not in self.supported_models:
            raise ValueError(
                f"Unsupported OpenAI image model '{request.model}'. "
                f"Supported models: {', '.join(sorted(self.supported_models))}"
            )

        kwargs: dict[str, object] = {
            "model": request.model,
            "prompt": request.prompt,
            "size": request.size,
            "quality": request.quality,
            "output_format": request.output_format,
        }
        if request.transparent:
            kwargs["background"] = "transparent"

        response = self._client.images.generate(**kwargs)
        if not getattr(response, "data", None):
            raise ValueError("OpenAI Images API returned no image data.")

        encoded = getattr(response.data[0], "b64_json", None)
        if not encoded:
            raise ValueError("OpenAI Images API response did not contain b64_json image data.")

        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("OpenAI Images API returned invalid base64 image data.") from exc

        return GenerationResult(
            data=image_bytes,
            model=request.model,
            metadata={"provider": self.name, "size": request.size, "quality": request.quality},
        )
