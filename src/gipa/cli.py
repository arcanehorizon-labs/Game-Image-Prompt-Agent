"""Command-line entry point for GIPA."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
from .validation import load_yaml, validate_manifest_rules, validate_schema
from .workflow import approve, plan, prompts, validate_project

def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]

def _schema_path(name: str) -> Path:
    return _project_root()/"schemas"/name

def command_status(args: argparse.Namespace) -> int:
    """Print a compact state summary without mutating project files."""
    state_path=Path(args.state)
    if not state_path.exists():
        print(f"GIPA state not found: {state_path}")
        return 2
    state=load_yaml(state_path)
    print(f"phase: {state.get('phase','unknown')}")
    print(f"status: {state.get('status','unknown')}")
    print(f"next_action: {state.get('next_action',{}).get('type','unknown')}")
    return 0

def command_validate(args: argparse.Namespace) -> int:
    """Validate one supported machine-readable artifact."""
    path=Path(args.path)
    if not path.exists():
        print(f"File not found: {path}",file=sys.stderr)
        return 2
    document=load_yaml(path)
    schema_name={"state":"state.schema.json","art-style":"art-style.schema.json","manifest":"asset-manifest.schema.json","asset-spec":"asset-spec.schema.json"}[args.kind]
    errors=validate_schema(document,_schema_path(schema_name))
    if args.kind=="manifest":
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

def command_plan(args: argparse.Namespace) -> int:
    """Create the art-style and asset-inventory review package."""
    state=plan(Path(args.gdd),Path(args.out),Path(args.game_root) if args.game_root else None)
    print(f"phase: {state['phase']}")
    print(f"status: {state['status']}")
    print(f"review: {state['outputs']['review']}")
    return 1 if state["status"]=="blocked" else 0

def command_approve(args: argparse.Namespace) -> int:
    """Approve the inventory and materialize asset specifications."""
    state=approve(Path(args.out))
    print(f"phase: {state['phase']}")
    print(f"status: {state['status']}")
    print(f"specs: {state['outputs']['specs']}")
    return 0

def command_prompts(args: argparse.Namespace) -> int:
    """Compile canonical, ChatGPT Images, and Gemini Images prompt packs."""
    state=prompts(Path(args.out))
    print(f"phase: {state['phase']}")
    print(f"status: {state['status']}")
    print(f"prompts: {state['outputs']['prompts']}")
    return 0

def command_validate_project(args: argparse.Namespace) -> int:
    """Validate the complete generated package."""
    errors=validate_project(Path(args.out))
    if errors:
        print("GIPA project validation FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("GIPA project validation PASS")
    return 0

def build_parser() -> argparse.ArgumentParser:
    """Build the stable GIPA CLI surface."""
    parser=argparse.ArgumentParser(prog="gipa")
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("plan",help="Read a GDD and create an asset inventory for review")
    p.add_argument("--gdd",required=True)
    p.add_argument("--game-root")
    p.add_argument("--out",default=".ai-assets")
    p.set_defaults(func=command_plan)
    a=sub.add_parser("approve",help="Approve the reviewed inventory and create asset specs")
    a.add_argument("--out",default=".ai-assets")
    a.set_defaults(func=command_approve)
    pr=sub.add_parser("prompts",help="Compile canonical and provider-specific prompt packs")
    pr.add_argument("--out",default=".ai-assets")
    pr.set_defaults(func=command_prompts)
    vp=sub.add_parser("validate-project",help="Validate the completed GIPA output package")
    vp.add_argument("--out",default=".ai-assets")
    vp.set_defaults(func=command_validate_project)
    status=sub.add_parser("status",help="Show current agent state")
    status.add_argument("--state",default=".ai-assets/STATE.yaml")
    status.set_defaults(func=command_status)
    validate=sub.add_parser("validate",help="Validate a GIPA artifact")
    validate.add_argument("kind",choices=["state","art-style","manifest","asset-spec"])
    validate.add_argument("path")
    validate.set_defaults(func=command_validate)
    return parser

def main() -> None:
    """Run the CLI and expose the command result as the process exit code."""
    args=build_parser().parse_args()
    try:
        code=args.func(args)
    except (ValueError,OSError) as exc:
        print(f"GIPA ERROR: {exc}",file=sys.stderr)
        code=2
    raise SystemExit(code)

if __name__=="__main__":
    main()
