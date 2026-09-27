"""Command-line entry point for the deterministic GIPA foundation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .validation import load_yaml, validate_manifest_rules, validate_schema


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _schema_path(name: str) -> Path:
    return _project_root() / "schemas" / name


def command_status(args: argparse.Namespace) -> int:
    """Print a compact state summary without mutating project files."""
    state_path = Path(args.state)
    if not state_path.exists():
        print(f"GIPA state not found: {state_path}")
        return 2
    state = load_yaml(state_path)
    print(f"phase: {state.get('phase', 'unknown')}")
    print(f"status: {state.get('status', 'unknown')}")
    next_action = state.get("next_action", {})
    print(f"next_action: {next_action.get('type', 'unknown')}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    """Validate one supported machine-readable artifact."""
    path = Path(args.path)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 2

    document = load_yaml(path)
    schema_name = {
        "state": "state.schema.json",
        "art-style": "art-style.schema.json",
        "manifest": "asset-manifest.schema.json",
        "asset-spec": "asset-spec.schema.json",
    }[args.kind]

    errors = validate_schema(document, _schema_path(schema_name))
    if args.kind == "manifest":
        errors.extend(validate_manifest_rules(document))

    if errors:
        print("GIPA validation FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("GIPA validation PASS")
    print(f"kind: {args.kind}")
    print(f"file: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the stable GIPA-0 CLI surface."""
    parser = argparse.ArgumentParser(prog="gipa")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Show current agent state")
    status.add_argument("--state", default=".ai-assets/STATE.yaml")
    status.set_defaults(func=command_status)

    validate = subparsers.add_parser("validate", help="Validate a GIPA artifact")
    validate.add_argument("kind", choices=["state", "art-style", "manifest", "asset-spec"])
    validate.add_argument("path")
    validate.set_defaults(func=command_validate)

    return parser


def main() -> None:
    """Run the CLI and expose the command result as the process exit code."""
    args = build_parser().parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
