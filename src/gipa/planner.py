"""Asset planning and dimension resolution."""
from __future__ import annotations
from fractions import Fraction
from pathlib import Path
import re
import yaml

CATEGORY_DEFAULT_MAP={
    "environment_texture":"seamless_environment_texture",
    "environment_background":"background_landscape",
    "character":"character_source","enemy":"character_source",
    "prop":"object_sprite","ui":"object_sprite","vfx":"object_sprite",
    "launcher_asset":"object_sprite","splash_asset":"splash_landscape",
    "store_asset":"background_landscape","gameplay_object":"object_sprite","visual_only":"object_sprite",
}

def slug(value: str,fallback: str="asset") -> str:
    """Create deterministic filesystem-safe IDs from descriptive prose."""
    value=re.sub(r"[^a-z0-9]+","_",value.lower()).strip("_")
    return value[:56].rstrip("_") or fallback

def load_dimensions(path: Path) -> dict:
    """Load deterministic dimension defaults."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))["defaults"]

def _ratio(width: int,height: int) -> str:
    value=Fraction(width,height)
    return f"{value.numerator}:{value.denominator}"

def build_art_style(analysis: dict) -> dict:
    """Convert GDD style evidence into the authoritative style artifact."""
    evidence=analysis["style_evidence"]
    if not evidence:
        return {"schema_version":1,"game":{"title":analysis["game_title"]},"visual_style":{"status":"uncertain","summary":[]},"sources":[{"type":"gdd","reference":"No explicit art direction found"}],"confidence":"uncertain"}
    return {
        "schema_version":1,
        "game":{"title":analysis["game_title"]},
        "visual_style":{"status":"resolved","summary":[item["text"] for item in evidence]},
        "mobile_readability":{"enabled":True,"avoid_micro_detail":True,"silhouette_priority":"high"},
        "sources":[{"type":"gdd","reference":item["section"]} for item in evidence[:10]],
        "confidence":"explicit",
    }

def build_manifest(analysis: dict,defaults: dict,repo_scan: dict | None=None) -> dict:
    """Build a traceable proposed asset inventory from GDD evidence."""
    assets=[]
    names={}
    existing={item["filename"].lower() for item in (repo_scan or {}).get("images",[])}
    for candidate in analysis["asset_candidates"]:
        category=candidate["category"]
        base=f"{category}_{slug(candidate['description'])}"
        names[base]=names.get(base,0)+1
        asset_id=base if names[base]==1 else f"{base}_{names[base]:02d}"
        key=CATEGORY_DEFAULT_MAP.get(category,"object_sprite")
        dim=defaults[key]
        filename=f"{asset_id}.png"
        assets.append({
            "asset_id":asset_id,"filename":filename,"category":category,"description":candidate["description"],
            "dimensions":{"width":int(dim["width"]),"height":int(dim["height"]),"aspect_ratio":dim.get("aspect_ratio") or _ratio(int(dim["width"]),int(dim["height"])),"source":{"type":"category_default","rule":key}},
            "output":{"format":"png","alpha":bool(dim.get("alpha",True))},
            "generation":{"required":filename.lower() not in existing,"reason":"existing_filename" if filename.lower() in existing else ("derived_requirement" if candidate["confidence"]=="derived" else "gdd_requirement")},
            "source_trace":{"requirement":{"type":"rule" if candidate["confidence"]=="derived" else "gdd","reference":candidate.get("derivation",candidate["section"]),"text":candidate["description"]}},
            "confidence":candidate["confidence"],
        })
    return {"schema_version":1,"game":analysis["game_title"],"status":"awaiting_asset_inventory_approval","assets":assets}
