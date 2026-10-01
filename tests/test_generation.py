from base64 import b64encode
from io import BytesIO

from PIL import Image

from gipa.generation import choose_provider_canvas
from gipa.providers.base import GenerationRequest
from gipa.providers.openai_images import OpenAIImagesProvider


def test_provider_canvas_preserves_supported_exact_size() -> None:
    assert choose_provider_canvas(1024, 1024) == (1024, 1024)
    assert choose_provider_canvas(1536, 1024) == (1536, 1024)


def test_provider_canvas_scales_small_asset_to_supported_request() -> None:
    width, height = choose_provider_canvas(512, 512)
    assert width % 16 == 0
    assert height % 16 == 0
    assert width * height >= 655_360


def test_provider_canvas_rejects_extreme_aspect_ratio() -> None:
    try:
        choose_provider_canvas(2048, 256)
    except ValueError as exc:
        assert "3:1" in str(exc)
    else:
        raise AssertionError("Expected unsupported aspect ratio to be rejected")


def test_openai_provider_decodes_base64_and_forwards_generation_options() -> None:
    buffer = BytesIO()
    Image.new("RGBA", (1024, 1024)).save(buffer, format="PNG")
    encoded = b64encode(buffer.getvalue()).decode("ascii")

    class Datum:
        b64_json = encoded

    class Response:
        data = [Datum()]

    class Images:
        def __init__(self) -> None:
            self.kwargs = None

        def generate(self, **kwargs):
            self.kwargs = kwargs
            return Response()

    class Client:
        def __init__(self) -> None:
            self.images = Images()

    client = Client()
    provider = OpenAIImagesProvider(client=client)
    result = provider.generate(
        GenerationRequest(
            asset_id="floor",
            prompt="test prompt",
            model="gpt-image-2.5-flare",
            size="1024x1024",
            quality="high",
            output_format="png",
            transparent=True,
        )
    )

    assert result.data == buffer.getvalue()
    assert client.images.kwargs["model"] == "gpt-image-2.5-flare"
    assert client.images.kwargs["background"] == "transparent"
    assert client.images.kwargs["output_format"] == "png"
