"""Provider-backed image generation with deterministic staging and validation."""
from __future__ import annotations

from io import BytesIO
from math import sqrt
from pathlib import Path
import json
import shutil

from PIL import Image
import yaml

from .io import write_json, write_text, write_yaml
from .providers.base import GenerationRequest, ImageProvider
from .workflow import validate_project

MIN_PIXELS = 655_360
MAX_PIXELS = 8_294_400
MAX_EDGE = 3840
MAX_ASPECT_RATIO = 3.0
MULTIPLE = 16


def _round_to_multiple(value: float) -> int:
    return max(MULTIPLE, int(round(value / MULTIPLE)) * MULTIPLE)


def choose_provider_canvas(width: int, height: int) -> tuple[int, int]:
    """Choose the closest OpenAI-compatible canvas without changing orientation."""
    if width <= 0 or height <= 0:
        raise ValueError("Production dimensions must be positive.")

    ratio = width / height
    if ratio > MAX_ASPECT_RATIO or ratio < 1 / MAX_ASPECT_RATIO:
        raise ValueError(
            f"Aspect ratio {width}:{height} exceeds the OpenAI Images 3:1 limit."
        )

    pixels = width * height
    exact_supported = (
        width % MULTIPLE == 0
        and height % MULTIPLE == 0
        and pixels >= MIN_PIXELS
        and pixels <= MAX_PIXELS
        and width <= MAX_EDGE
        and height <= MAX_EDGE
    )
    if exact_supported:
        return width, height

    scale = 1.0
    if pixels < MIN_PIXELS:
        scale = sqrt(MIN_PIXELS / pixels)
    elif pixels > MAX_PIXELS:
        scale = sqrt(MAX_PIXELS / pixels)

    candidate_width = _round_to_multiple(width * scale)
    candidate_height = _round_to_multiple(height * scale)

    while candidate_width * candidate_height < MIN_PIXELS:
        if width >= height:
            candidate_width += MULTIPLE
        else:
            candidate_height += MULTIPLE

    if (
        candidate_width > MAX_EDGE
        or candidate_height > MAX_EDGE
        or candidate_width * candidate_height > MAX_PIXELS
    ):
        raise ValueError(
            f"Cannot map production size {width}x{height} to a supported OpenAI Images canvas."
        )

    return candidate_width, candidate_height


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be an object")
    return data


def _asset_maps(out: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    manifest = yaml.safe_load((out / "ASSET_MANIFEST.yaml").read_text(encoding="utf-8"))
    assets = {asset["asset_id"]: asset for asset in manifest["assets"]}
    specs: dict[str, dict] = {}
    for path in sorted((out / "specs").glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        specs[spec["asset_id"]] = spec
    return assets, specs


def _save_production_image(
    raw: bytes,
    destination: Path,
    width: int,
    height: int,
    output_format: str,
    alpha_required: bool,
) -> dict[str, object]:
    """Decode, resize, encode, and validate one generated image."""
    with Image.open(BytesIO(raw)) as source:
        source.load()
        source_size = source.size
        image = source.copy()

    if image.size != (width, height):
        image = image.resize((width, height), Image.Resampling.LANCZOS)

    normalized_format = output_format.lower()
    if normalized_format == "jpg":
        normalized_format = "jpeg"

    if alpha_required:
        if normalized_format not in {"png", "webp"}:
            raise ValueError("Transparent assets must use PNG or WebP output.")
        if "A" not in image.getbands():
            raise ValueError("Provider output is missing the required alpha channel.")
        image = image.convert("RGBA")
    elif normalized_format in {"jpg", "jpeg"}:
        image = image.convert("RGB")

    destination.parent.mkdir(parents=True, exist_ok=True)
    save_format = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}[normalized_format]
    image.save(destination, format=save_format)

    with Image.open(destination) as verified:
        verified.load()
        if verified.size != (width, height):
            raise ValueError(
                f"Generated file has {verified.size[0]}x{verified.size[1]}, "
                f"expected {width}x{height}."
            )
        if alpha_required and "A" not in verified.getbands():
            raise ValueError("Generated file lost its required alpha channel.")

    return {
        "source_width": source_size[0],
        "source_height": source_size[1],
        "production_width": width,
        "production_height": height,
        "format": normalized_format,
        "alpha_required": alpha_required,
    }


def _review_markdown(records: list[dict]) -> str:
    lines = [
        "# Generated Image Review",
        "",
        "Review every staged image visually before running gipa approve-images.",
        "Running the approval command is the explicit human approval signal; GIPA never commits images.",
        "",
    ]
    for record in records:
        lines.extend(
            [
                f"## {record['asset_id']}",
                "",
                f"- Status: {record['status']}",
                f"- Variant: {record['variant']}",
                f"- Model: {record['model']}",
                f"- Staged file: {record['staged_path']}",
                f"- Intended target: {record.get('target_path') or 'NOT SET'}",
                "",
            ]
        )
    return "\n".join(lines)


def generate_images(
    out: Path,
    provider: ImageProvider | None,
    *,
    model: str = "gpt-image-2.5-flare",
    quality: str = "high",
    variant: str = "A",
    asset_ids: set[str] | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict:
    """Generate one reviewed prompt variant per selected asset into the staging area."""
    if variant not in {"A", "B", "C"}:
        raise ValueError("Variant must be A, B, or C.")

    validation_errors = validate_project(out)
    if validation_errors:
        raise ValueError("GIPA project validation must pass before image generation.")

    prompt_pack = _load_json(out / "prompts" / "chatgpt_images.json")
    assets, specs = _asset_maps(out)
    selected = [
        record
        for record in prompt_pack.get("prompts", [])
        if record.get("variant") == variant
        and (not asset_ids or record.get("asset_id") in asset_ids)
    ]
    if not selected:
        raise ValueError("No prompts matched the requested asset selection.")

    records: list[dict] = []
    generated_root = out / "generated" / "openai"

    for prompt in selected:
        asset_id = prompt["asset_id"]
        asset = assets.get(asset_id)
        spec = specs.get(asset_id)
        if not asset or not spec:
            raise ValueError(f"Missing manifest/spec data for asset '{asset_id}'.")

        if not asset.get("generation", {}).get("required", False):
            continue

        prod = spec["dimensions"]["production"]
        width, height = int(prod["width"]), int(prod["height"])
        canvas_width, canvas_height = choose_provider_canvas(width, height)
        output_format = str(spec["output"]["format"]).lower()
        extension = "jpg" if output_format == "jpeg" else output_format
        staged_path = generated_root / f"{asset_id}.{extension}"

        base_record = {
            "asset_id": asset_id,
            "variant": variant,
            "provider": "openai",
            "model": model,
            "quality": quality,
            "request_size": f"{canvas_width}x{canvas_height}",
            "production_size": f"{width}x{height}",
            "staged_path": str(staged_path),
            "target_path": asset.get("target_path"),
        }

        if staged_path.exists() and not overwrite:
            records.append({**base_record, "status": "skipped_existing"})
            continue

        if dry_run:
            records.append({**base_record, "status": "dry_run"})
            continue

        if provider is None:
            raise ValueError("An image provider is required unless --dry-run is used.")

        request_format = "png" if spec["output"].get("alpha") else (
            "jpeg" if output_format in {"jpg", "jpeg"} else output_format
        )
        result = provider.generate(
            GenerationRequest(
                asset_id=asset_id,
                prompt=prompt["text"],
                model=model,
                size=f"{canvas_width}x{canvas_height}",
                quality=quality,
                output_format=request_format,
                transparent=bool(spec["output"].get("alpha")),
            )
        )
        technical = _save_production_image(
            result.data,
            staged_path,
            width,
            height,
            output_format,
            bool(spec["output"].get("alpha")),
        )
        records.append(
            {
                **base_record,
                "status": "generated",
                "technical_validation": "pass",
                "technical": technical,
                "provider_metadata": result.metadata,
            }
        )

    if asset_ids:
        found = {record["asset_id"] for record in records}
        missing = sorted(asset_ids - found)
        if missing:
            raise ValueError(f"Requested assets were not generated or staged: {', '.join(missing)}")

    payload = {
        "schema_version": 1,
        "provider": "openai",
        "model": model,
        "quality": quality,
        "variant": variant,
        "dry_run": dry_run,
        "images": records,
    }
    write_json(out / "GENERATION_MANIFEST.json", payload)
    write_text(out / "GENERATION_REVIEW.md", _review_markdown(records))

    state = yaml.safe_load((out / "STATE.yaml").read_text(encoding="utf-8"))
    state["phase"] = "image_generation"
    state["status"] = "complete" if dry_run else "awaiting_human_approval"
    state["outputs"]["generation_manifest"] = str(out / "GENERATION_MANIFEST.json")
    state["outputs"]["generation_review"] = str(out / "GENERATION_REVIEW.md")
    state["next_action"] = (
        {
            "type": "run_command",
            "command": f"gipa generate --out {out} --provider openai",
            "message": "Dry run passed. Run image generation without --dry-run when ready.",
        }
        if dry_run
        else {
            "type": "human_review",
            "artifact": str(out / "GENERATION_REVIEW.md"),
            "message": "Review every staged image, then run gipa approve-images.",
        }
    )
    write_yaml(out / "STATE.yaml", state)
    return payload


def approve_generated_images(out: Path, game_root: Path, *, overwrite: bool = False) -> dict:
    """Copy visually approved staged images to explicit manifest target paths."""
    generation = _load_json(out / "GENERATION_MANIFEST.json")
    assets, _ = _asset_maps(out)
    candidates = [
        record for record in generation.get("images", [])
        if record.get("status") in {"generated", "skipped_existing"}
    ]
    if not candidates:
        raise ValueError("No generated images are available for approval.")

    operations: list[tuple[Path, Path, str]] = []
    missing_targets: list[str] = []
    for record in candidates:
        asset_id = record["asset_id"]
        asset = assets[asset_id]
        target_path = asset.get("target_path")
        if not target_path:
            missing_targets.append(asset_id)
            continue

        relative = Path(str(target_path))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Asset '{asset_id}' has an unsafe target_path: {target_path}")

        source = Path(record["staged_path"])
        destination = game_root / relative
        operations.append((source, destination, asset_id))

    if missing_targets:
        raise ValueError(
            "Explicit target_path is required before image approval for: "
            + ", ".join(sorted(missing_targets))
        )

    for source, destination, asset_id in operations:
        if not source.exists():
            raise ValueError(f"Staged image is missing for '{asset_id}': {source}")
        if destination.exists() and not overwrite:
            raise ValueError(
                f"Target already exists for '{asset_id}': {destination}. "
                "Use --overwrite only after reviewing the replacement."
            )

    copied: list[dict[str, str]] = []
    for source, destination, asset_id in operations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(
            {"asset_id": asset_id, "source": str(source), "destination": str(destination)}
        )

    state = yaml.safe_load((out / "STATE.yaml").read_text(encoding="utf-8"))
    state["phase"] = "image_approval"
    state["status"] = "complete"
    state["outputs"]["approved_images"] = copied
    state["next_action"] = {
        "type": "none",
        "message": "Approved images were copied to the game repository. No git commit was created.",
    }
    write_yaml(out / "STATE.yaml", state)
    return {"schema_version": 1, "approved": copied}
