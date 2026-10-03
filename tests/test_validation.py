from pathlib import Path

from gipa.validation import (
    load_yaml,
    validate_manifest_rules,
    validate_schema,
    validate_state_transition,
)


ROOT = Path(__file__).resolve().parents[1]


def test_example_state_matches_schema() -> None:
    state = load_yaml(ROOT / "examples" / "STATE.yaml")
    assert validate_schema(state, ROOT / "schemas" / "state.schema.json") == []


def test_example_manifest_matches_schema_and_rules() -> None:
    manifest = load_yaml(ROOT / "examples" / "ASSET_MANIFEST.yaml")
    assert validate_schema(manifest, ROOT / "schemas" / "asset-manifest.schema.json") == []
    assert validate_manifest_rules(manifest) == []


def test_duplicate_asset_id_is_rejected() -> None:
    manifest = load_yaml(ROOT / "examples" / "ASSET_MANIFEST.yaml")
    manifest["assets"].append(dict(manifest["assets"][0], filename="other.png"))
    errors = validate_manifest_rules(manifest)
    assert any("duplicate asset_id" in error for error in errors)


def test_duplicate_filename_is_rejected() -> None:
    manifest = load_yaml(ROOT / "examples" / "ASSET_MANIFEST.yaml")
    manifest["assets"].append(dict(manifest["assets"][0], asset_id="other"))
    errors = validate_manifest_rules(manifest)
    assert any("duplicate filename" in error for error in errors)


def test_dimension_ratio_mismatch_is_rejected() -> None:
    manifest = load_yaml(ROOT / "examples" / "ASSET_MANIFEST.yaml")
    manifest["assets"][0]["dimensions"]["width"] = 1920
    errors = validate_manifest_rules(manifest)
    assert any("do not match aspect ratio" in error for error in errors)


def test_missing_alpha_decision_is_rejected() -> None:
    manifest = load_yaml(ROOT / "examples" / "ASSET_MANIFEST.yaml")
    del manifest["assets"][0]["output"]["alpha"]
    errors = validate_manifest_rules(manifest)
    assert any("output.alpha" in error for error in errors)


def test_phase_cannot_move_backwards() -> None:
    previous = {"phase": "asset_specs", "status": "in_progress"}
    current = {"phase": "asset_inventory", "status": "in_progress"}
    assert "phase cannot move backwards" in validate_state_transition(previous, current)
