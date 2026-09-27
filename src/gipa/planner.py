"""Asset planning, style resolution, and repository evidence reconciliation."""
from __future__ import annotations
from collections import Counter
from fractions import Fraction
from pathlib import Path
import re
import yaml

CATEGORY_DEFAULT_MAP={
    "environment_texture":"seamless_environment_texture",
    "environment_background":"background_landscape",
    "character":"character_source","enemy":"character_source",
    "prop":"object_sprite","gameplay_object":"object_sprite","ui":"object_sprite","vfx":"object_sprite",
    "launcher_asset":"object_sprite","splash_asset":"splash_landscape",
    "store_asset":"background_landscape","visual_only":"object_sprite",
}

CONCEPT_ALIASES={
    "player_character":("player","hero","thief","protagonist"),
    "guard_enemy":("guard",),
    "enemy_character":("enemy","monster"),
    "security_camera":("camera",),
    "security_laser":("laser",),
    "door":("door",),
    "exit":("exit",),
    "loot":("loot","diamond","treasure"),
    "terminal":("terminal","console"),
    "crate":("crate",),
    "chest":("chest",),
    "floor_tile":("floor","tile"),
    "wall_tile":("wall","tile"),
    "terrain_texture":("terrain","texture"),
    "background":("background","backdrop"),
    "menu_ui":("menu",),
    "hud_ui":("hud",),
    "button_ui":("button",),
    "panel_ui":("panel",),
    "visual_effect":("vfx","effect","particle"),
    "splash_screen":("splash",),
    "launcher_icon":("icon","launcher"),
    "feature_graphic":("feature","graphic"),
}

def slug(value: str,fallback: str="asset") -> str:
    """Create deterministic filesystem-safe IDs."""
    value=re.sub(r"[^a-z0-9]+","_",value.lower()).strip("_")
    return value[:56].rstrip("_") or fallback

def load_dimensions(path: Path) -> dict:
    """Load deterministic dimension defaults."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))["defaults"]

def _ratio(width: int,height: int) -> str:
    value=Fraction(width,height)
    return f"{value.numerator}:{value.denominator}"

def build_art_style(analysis: dict,override: dict | None=None) -> dict:
    """Create the style contract; an explicit user override resolves GDD ambiguity."""
    if override:
        result=dict(override)
        result.setdefault("schema_version",1)
        result.setdefault("game",{"title":analysis["game_title"]})
        result["game"]["title"]=analysis["game_title"]
        result.setdefault("sources",[])
        result["sources"].append({"type":"user","reference":"style override"})
        result["confidence"]="explicit"
        result.setdefault("visual_style",{})
        result["visual_style"]["status"]="resolved"
        return result

    evidence=analysis["style_evidence"]
    questions=analysis.get("style_questions",[])
    uncertain=bool(questions) or not evidence
    return {
        "schema_version":1,
        "game":{"title":analysis["game_title"]},
        "visual_style":{
            "status":"uncertain" if uncertain else "resolved",
            "summary":[item["text"] for item in evidence],
            "unresolved_questions":[item["text"] for item in questions],
        },
        "mobile_readability":{"enabled":True,"avoid_micro_detail":True,"silhouette_priority":"high"},
        "sources":[{"type":"gdd","reference":item["section"]} for item in evidence[:10]] or [{"type":"gdd","reference":"No explicit resolved art direction found"}],
        "confidence":"uncertain" if uncertain else "explicit",
    }

def _repository_matches(candidate: dict,repo_scan: dict | None) -> list[dict]:
    """Return existing images with filenames strongly related to a concrete concept."""
    if not repo_scan:
        return []
    concept=candidate.get("concept","")
    aliases=CONCEPT_ALIASES.get(concept,(concept.replace("_"," "),))
    matches=[]
    for image in repo_scan.get("images",[]):
        haystack=(" "+image.get("stem","")+" "+image.get("path","").lower().replace("_"," ").replace("-"," ")+" ")
        if any(re.search(rf"\b{re.escape(alias)}\b",haystack) for alias in aliases):
            matches.append(image)
    return matches[:50]

def _dominant_existing_dimensions(matches: list[dict]) -> tuple[int,int] | None:
    sizes=[(item.get("width"),item.get("height")) for item in matches if item.get("width") and item.get("height")]
    if not sizes:
        return None
    size,count=Counter(sizes).most_common(1)[0]
    return size if count>=max(1,len(sizes)//2) else None

def build_manifest(analysis: dict,defaults: dict,repo_scan: dict | None=None) -> dict:
    """Build a traceable proposed inventory using GDD and existing repository evidence."""
    assets=[]
    names={}
    for candidate in analysis["asset_candidates"]:
        category=candidate["category"]
        concept=candidate.get("concept",slug(candidate["description"]))
        base=f"{category}_{slug(concept)}"
        names[base]=names.get(base,0)+1
        asset_id=base if names[base]==1 else f"{base}_{names[base]:02d}"

        key=CATEGORY_DEFAULT_MAP.get(category,"object_sprite")
        fallback=defaults[key]
        matches=_repository_matches(candidate,repo_scan)
        existing_dimensions=_dominant_existing_dimensions(matches)

        if "dimensions" in candidate:
            width=int(candidate["dimensions"]["width"]); height=int(candidate["dimensions"]["height"])
            dimension_source={"type":"gdd","reference":candidate["section"]}
        elif existing_dimensions:
            width,height=existing_dimensions
            dimension_source={"type":"existing_resource","references":[item["path"] for item in matches[:10]]}
        else:
            width=int(fallback["width"]); height=int(fallback["height"])
            dimension_source={"type":"category_default","rule":key}

        if "alpha" in candidate:
            alpha=bool(candidate["alpha"])
        else:
            known_alpha=[item.get("alpha") for item in matches if item.get("alpha") is not None]
            alpha=Counter(known_alpha).most_common(1)[0][0] if known_alpha else bool(fallback.get("alpha",True))

        filename=f"{asset_id}.png"
        existing_paths=[item["path"] for item in matches]
        generation_required=not bool(matches)
        assets.append({
            "asset_id":asset_id,
            "filename":filename,
            "category":category,
            "concept":concept,
            "description":candidate["description"],
            "dimensions":{"width":width,"height":height,"aspect_ratio":_ratio(width,height),"source":dimension_source},
            "output":{"format":"png","alpha":alpha},
            "generation":{
                "required":generation_required,
                "reason":"existing_semantic_resource" if matches else ("derived_requirement" if candidate["confidence"]=="derived" else "gdd_requirement"),
            },
            "existing_matches":existing_paths,
            "source_trace":{"requirement":{
                "type":"rule" if candidate["confidence"]=="derived" else "gdd",
                "reference":candidate.get("derivation",candidate["section"]),
                "text":candidate.get("source_text",candidate["description"]),
            }},
            "confidence":candidate["confidence"],
        })
    return {"schema_version":1,"game":analysis["game_title"],"status":"awaiting_asset_inventory_approval","assets":assets}
