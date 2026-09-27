"""Deterministic validation for GIPA machine-readable artifacts."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import json

import yaml
from jsonschema import Draft202012Validator


class ValidationFailure(ValueError):
    """Raised when a GIPA artifact violates deterministic project rules."""


def load_yaml(path: Path) -> dict:
    """Load one YAML document and require a mapping at the document root."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValidationFailure(f"{path}: root must be a mapping")
    return data


def validate_schema(document: dict, schema_path: Path) -> list[str]:
    """Return stable, human-readable JSON Schema validation errors."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    return [f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors]


def _ratio(value: str) -> Fraction:
    left, right = value.split(":", 1)
    return Fraction(int(left), int(right))


def validate_manifest_rules(document: dict) -> list[str]:
    """Validate cross-field manifest rules that JSON Schema cannot express clearly."""
    errors: list[str] = []
    assets = document.get("assets", [])
    ids: set[str] = set()
    filenames: set[str] = set()

    for index, asset in enumerate(assets):
        prefix = f"assets/{index}"
        asset_id = asset.get("asset_id")
        filename = asset.get("filename")

        if asset_id in ids:
            errors.append(f"{prefix}: duplicate asset_id '{asset_id}'")
        if asset_id:
            ids.add(asset_id)

        if filename in filenames:
            errors.append(f"{prefix}: duplicate filename '{filename}'")
        if filename:
            filenames.add(filename)

        dimensions = asset.get("dimensions", {})
        width = dimensions.get("width")
        height = dimensions.get("height")
        aspect_ratio = dimensions.get("aspect_ratio")
        if width and height and aspect_ratio:
            if Fraction(width, height) != _ratio(aspect_ratio):
                errors.append(
                    f"{prefix}: dimensions {width}x{height} do not match aspect ratio {aspect_ratio}"
                )

        output = asset.get("output", {})
        if "alpha" not in output:
            errors.append(f"{prefix}: output.alpha decision is required")

    return errors


def validate_state_transition(previous: dict, current: dict) -> list[str]:
    """Reject backwards or approval-skipping state transitions."""
    errors: list[str] = []
    phase_order = {
        "foundation": 0,
        "art_style": 1,
        "asset_inventory": 2,
        "asset_specs": 3,
        "prompt_compilation": 4,
        "validation": 5,
    }
    before = phase_order.get(previous.get("phase"), -1)
    after = phase_order.get(current.get("phase"), -1)
    if after < before:
        errors.append("phase cannot move backwards")

    if previous.get("phase") == "asset_inventory" and previous.get("status") == "awaiting_human_approval":
        if current.get("phase") != "asset_inventory" and previous.get("status") != "complete":
            errors.append("asset inventory approval cannot be skipped")

    return errors
