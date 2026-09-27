"""End-to-end GIPA v1 workflow."""
from __future__ import annotations
from pathlib import Path
import json
import yaml
from .gdd import analyze_gdd
from .io import write_json, write_text, write_yaml
from .planner import build_art_style, build_manifest, load_dimensions
from .prompts import adapt_chatgpt, adapt_gemini, compile_canonical, prompt_record
from .render import prompts_markdown, review_markdown
from .repository import scan_repository
from .specs import build_asset_spec
from .validation import validate_manifest_rules, validate_schema

PACKAGE_ROOT=Path(__file__).resolve().parents[2]

def _schema(name: str) -> Path:
    return PACKAGE_ROOT/"schemas"/name

def _load_style_override(style_file: Path | None) -> dict | None:
    if not style_file:
        return None
    if not style_file.exists():
        raise ValueError(f"Style override file not found: {style_file}")
    data=yaml.safe_load(style_file.read_text(encoding="utf-8"))
    if not isinstance(data,dict):
        raise ValueError("Style override must be a YAML mapping.")
    return data

def plan(gdd: Path,out: Path,game_root: Path | None=None,style_file: Path | None=None) -> dict:
    """Analyze a GDD and create the proposed human-review asset plan."""
    analysis=analyze_gdd(gdd)
    style=build_art_style(analysis,_load_style_override(style_file))
    repo_scan=scan_repository(game_root) if game_root else {"enabled":False,"images":[],"references":[]}
    defaults=load_dimensions(PACKAGE_ROOT/"config"/"dimensions.yaml")
    manifest=build_manifest(analysis,defaults,repo_scan)
    out.mkdir(parents=True,exist_ok=True)
    write_yaml(out/"ART_STYLE.yaml",style)
    write_yaml(out/"ASSET_MANIFEST.yaml",manifest)
    write_json(out/"GDD_ANALYSIS.json",analysis)
    write_json(out/"REPOSITORY_SCAN.json",repo_scan)
    write_text(out/"ASSET_REVIEW.md",review_markdown(style,manifest,repo_scan))
    status="blocked" if style["confidence"]=="uncertain" else "awaiting_human_approval"
    state={
        "schema_version":1,"phase":"asset_inventory","status":status,
        "inputs":{
            "gdd":{"path":str(gdd)},
            "repository_scan":{"enabled":bool(game_root),"root":str(game_root) if game_root else None},
            "style_override":{"enabled":bool(style_file),"path":str(style_file) if style_file else None},
        },
        "outputs":{"art_style":str(out/"ART_STYLE.yaml"),"manifest":str(out/"ASSET_MANIFEST.yaml"),"review":str(out/"ASSET_REVIEW.md")},
        "counts":{"total_assets":len(manifest["assets"]),"explicit":sum(a["confidence"]=="explicit" for a in manifest["assets"]),"derived":sum(a["confidence"]=="derived" for a in manifest["assets"]),"uncertain":sum(a["confidence"]=="uncertain" for a in manifest["assets"])},
        "next_action":{
            "type":"resolve_blocker" if status=="blocked" else "human_review",
            "artifact":str(out/"ASSET_REVIEW.md"),
            "message":"Provide an approved style override and rerun plan." if status=="blocked" else "Review and approve the asset inventory.",
        },
    }
    write_yaml(out/"STATE.yaml",state)
    return state

def approve(out: Path) -> dict:
    """Approve a non-blocked asset inventory and create asset specifications."""
    state=yaml.safe_load((out/"STATE.yaml").read_text(encoding="utf-8"))
    style=yaml.safe_load((out/"ART_STYLE.yaml").read_text(encoding="utf-8"))
    manifest=yaml.safe_load((out/"ASSET_MANIFEST.yaml").read_text(encoding="utf-8"))
    if state.get("status")=="blocked" or style.get("confidence")=="uncertain":
        raise ValueError("Art style is unresolved; rerun plan with an approved style override before approval.")
    manifest["status"]="approved"
    write_yaml(out/"ASSET_MANIFEST.yaml",manifest)
    specs_dir=out/"specs"
    for asset in manifest["assets"]:
        if asset["generation"]["required"]:
            write_yaml(specs_dir/f"{asset['asset_id']}.yaml",build_asset_spec(asset))
    state["phase"]="asset_specs"; state["status"]="complete"; state["outputs"]["specs"]=str(specs_dir)
    state["next_action"]={"type":"run_command","command":f"gipa prompts --out {out}","message":"Compile the approved prompt pack."}
    write_yaml(out/"STATE.yaml",state)
    return state

def prompts(out: Path) -> dict:
    """Compile canonical plus ChatGPT/Gemini prompt packs from approved specs."""
    state=yaml.safe_load((out/"STATE.yaml").read_text(encoding="utf-8"))
    manifest=yaml.safe_load((out/"ASSET_MANIFEST.yaml").read_text(encoding="utf-8"))
    style=yaml.safe_load((out/"ART_STYLE.yaml").read_text(encoding="utf-8"))
    if manifest.get("status")!="approved":
        raise ValueError("Asset manifest must be approved before prompt compilation.")
    records={"canonical":[],"chatgpt_images":[],"gemini_images":[]}
    for spec_path in sorted((out/"specs").glob("*.yaml")):
        spec=yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        for variant in ("A","B","C"):
            canonical=compile_canonical(spec,style,variant)
            records["canonical"].append(prompt_record(spec,"canonical",canonical,variant))
            records["chatgpt_images"].append(prompt_record(spec,"chatgpt_images",adapt_chatgpt(canonical),variant))
            records["gemini_images"].append(prompt_record(spec,"gemini_images",adapt_gemini(canonical),variant))
    prompt_dir=out/"prompts"; prompt_dir.mkdir(parents=True,exist_ok=True)
    for provider,items in records.items():
        write_json(prompt_dir/f"{provider}.json",{"schema_version":1,"provider":provider,"prompts":items})
    write_text(prompt_dir/"IMAGE_PROMPTS.md",prompts_markdown(manifest["game"],"Canonical",records["canonical"]))
    write_text(prompt_dir/"CHATGPT_IMAGE_PROMPTS.md",prompts_markdown(manifest["game"],"ChatGPT Images",records["chatgpt_images"]))
    write_text(prompt_dir/"GEMINI_IMAGE_PROMPTS.md",prompts_markdown(manifest["game"],"Gemini Images",records["gemini_images"]))
    state["phase"]="prompt_compilation"; state["status"]="complete"; state["outputs"]["prompts"]=str(prompt_dir)
    state["next_action"]={"type":"run_command","command":f"gipa validate-project --out {out}","message":"Validate the completed prompt package."}
    write_yaml(out/"STATE.yaml",state)
    return state

def validate_project(out: Path) -> list[str]:
    """Validate final machine-readable artifacts and prompt invariants."""
    errors=[]
    state=yaml.safe_load((out/"STATE.yaml").read_text(encoding="utf-8"))
    style=yaml.safe_load((out/"ART_STYLE.yaml").read_text(encoding="utf-8"))
    manifest=yaml.safe_load((out/"ASSET_MANIFEST.yaml").read_text(encoding="utf-8"))
    errors += validate_schema(state,_schema("state.schema.json"))
    errors += validate_schema(style,_schema("art-style.schema.json"))
    errors += validate_schema(manifest,_schema("asset-manifest.schema.json"))
    errors += validate_manifest_rules(manifest)
    if style.get("confidence")=="uncertain":
        errors.append("art style is unresolved")
    specs_dir=out/"specs"
    if not specs_dir.exists():
        errors.append(f"missing specs directory: {specs_dir}")
    else:
        for spec_path in sorted(specs_dir.glob("*.yaml")):
            spec=yaml.safe_load(spec_path.read_text(encoding="utf-8"))
            errors += [f"{spec_path.name}: {e}" for e in validate_schema(spec,_schema("asset-spec.schema.json"))]
    for name in ("canonical","chatgpt_images","gemini_images"):
        path=out/"prompts"/f"{name}.json"
        if not path.exists():
            errors.append(f"missing prompt pack: {path}")
            continue
        payload=json.loads(path.read_text(encoding="utf-8"))
        errors += [f"{path.name}: {e}" for e in validate_schema(payload,_schema("prompt-pack.schema.json"))]
        for record in payload.get("prompts",[]):
            d=record["production_dimensions"]
            marker=f"{d['width']} × {d['height']} pixels"
            if marker not in record["text"]:
                errors.append(f"{path.name}/{record['asset_id']}: missing exact production dimensions in prompt")
    write_text(out/"VALIDATION.md","# Validation\n\n"+("PASS\n" if not errors else "FAILED\n\n"+"\n".join(f"- {e}" for e in errors)+"\n"))
    return errors
