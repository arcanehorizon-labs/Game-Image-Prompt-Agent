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
    "player_spacecraft":("player spacecraft","player ship","spacecraft","ship","scrapper","needle","tug"),
    "player_character":("hero","thief","protagonist"),
    "guard_enemy":("guard",),
    "enemy_character":("enemy","monster"),
    "security_camera":("camera",),
    "security_laser":("laser",),
    "door":("door",),
    "extraction_gate":("extraction gate","extraction beacon","extraction","gate"),
    "salvage_pickup":("salvage","scrap pickup","scrap"),
    "fuel_cell_pickup":("fuel cell","energy cell"),
    "planet":("planet",),
    "moon":("moon",),
    "asteroid":("asteroid",),
    "gas_giant":("gas giant","gas_giant"),
    "star":("star",),
    "black_hole":("black hole","black_hole"),
    "space_wreck":("space station","wreck"),
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
    "ship_trail":("ship trail","flight trail","orbital trail"),
    "launch_impulse":("launch impulse","thruster"),
    "salvage_collection_burst":("collection burst","salvage burst"),
    "shield_impact":("shield impact","shield hit"),
    "explosion":("explosion",),
    "gravity_distortion":("gravity distortion",),
    "speed_lines":("speed lines",),
    "star_heat_effect":("star heat","heat effect"),
    "splash_screen":("splash","launchscreen","launch_screen"),
    "launcher_icon":("launcher","app icon","app_icon","icon_foreground","ic_launcher"),
    "feature_graphic":("feature graphic","feature_graphic"),
}

MISSING_REFERENCE_CLASSIFIERS=(
    ("launcher_asset","launcher_icon",("launcher","app_icon","app icon","icon_foreground","mipmap")),
    ("splash_asset","splash_screen",("splash","launchscreen","launch_screen")),
    ("store_asset","feature_graphic",("feature_graphic","feature graphic")),
    ("character","player_character",("player","hero","thief")),
    ("enemy","guard_enemy",("guard",)),
    ("gameplay_object","security_camera",("camera",)),
    ("gameplay_object","security_laser",("laser",)),
    ("gameplay_object","door",("door",)),
    ("gameplay_object","exit",("exit",)),
    ("gameplay_object","loot",("loot","diamond","treasure")),
    ("prop","terminal",("terminal","console")),
    ("environment_texture","floor_tile",("floor",)),
    ("environment_texture","wall_tile",("wall",)),
    ("ui","menu_ui",("menu",)),
    ("ui","button_ui",("button",)),
    ("ui","panel_ui",("panel",)),
    ("vfx","visual_effect",("vfx","particle","effect")),
)

def slug(value: str,fallback: str="asset") -> str:
    value=re.sub(r"[^a-z0-9]+","_",value.lower()).strip("_")
    return value[:56].rstrip("_") or fallback

def load_dimensions(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["defaults"]

def _ratio(width: int,height: int) -> str:
    value=Fraction(width,height)
    return f"{value.numerator}:{value.denominator}"

def build_art_style(analysis: dict,override: dict | None=None) -> dict:
    if override:
        result=dict(override)
        result.setdefault("schema_version",1)
        result.setdefault("game",{"title":analysis["game_title"]})
        result["game"]["title"]=analysis["game_title"]
        result.setdefault("sources",[])
        if not any(item.get("type")=="user" and item.get("reference")=="style override" for item in result["sources"] if isinstance(item,dict)):
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
    if not repo_scan:
        return []
    concept=candidate.get("concept","")
    aliases=CONCEPT_ALIASES.get(concept,(concept.replace("_"," "),))
    matches=[]
    for image in repo_scan.get("images",[]):
        haystack=(" "+image.get("stem","")+" "+image.get("path","").lower().replace("_"," ").replace("-"," ")+" ")
        if any(alias in haystack for alias in aliases):
            matches.append(image)
    return matches[:50]

def _dominant_existing_dimensions(matches: list[dict]) -> tuple[int,int] | None:
    sizes=[(item.get("width"),item.get("height")) for item in matches if item.get("width") and item.get("height")]
    if not sizes:
        return None
    size,count=Counter(sizes).most_common(1)[0]
    return size if count>=max(1,len(sizes)//2) else None

def _classify_missing_reference(path: str) -> tuple[str,str] | None:
    lower=path.lower().replace("\\","/").replace("-","_")
    for category,concept,markers in MISSING_REFERENCE_CLASSIFIERS:
        if any(marker in lower for marker in markers):
            return category,concept
    return None

def _missing_reference_candidates(repo_scan: dict | None,existing_concepts: set[str]) -> list[dict]:
    result=[]
    if not repo_scan:
        return result
    for item in repo_scan.get("missing_references",[]):
        classification=_classify_missing_reference(item["asset_path"])
        if not classification:
            continue
        category,concept=classification
        if concept in existing_concepts:
            continue
        existing_concepts.add(concept)
        result.append({
            "category":category,
            "concept":concept,
            "description":concept.replace("_"," "),
            "confidence":"derived",
            "derivation":"missing_repository_reference",
            "section":"Repository reference",
            "source_text":f"Referenced but missing resource: {item['asset_path']}",
            "target_path":item["asset_path"],
            "referenced_from":item.get("referenced_from",[]),
        })
    return result

def _repository_platform_candidates(repo_scan: dict | None,existing_concepts: set[str]) -> list[dict]:
    result=[]
    if not repo_scan:
        return result
    platforms=set(repo_scan.get("platforms",[]))

    def add(category: str,concept: str,description: str,derivation: str) -> None:
        if concept in existing_concepts:
            return
        existing_concepts.add(concept)
        result.append({
            "category":category,
            "concept":concept,
            "description":description,
            "confidence":"derived",
            "derivation":derivation,
            "section":"Repository platform detection",
            "source_text":f"Derived from repository platforms: {', '.join(sorted(platforms))}",
        })

    if {"android","ios"} & platforms:
        add("launcher_asset","launcher_icon","launcher icon","repository_mobile_platform_requires_launcher_icon")
        add("splash_asset","splash_screen","splash screen","repository_mobile_platform_requires_splash_visual")
    if "android" in platforms:
        add("store_asset","feature_graphic","store feature graphic","repository_android_platform_requires_feature_graphic")
    return result

def build_manifest(analysis: dict,defaults: dict,repo_scan: dict | None=None) -> dict:
    assets=[]
    names={}
    candidates=list(analysis["asset_candidates"])
    concepts={candidate.get("concept") for candidate in candidates}
    candidates.extend(_repository_platform_candidates(repo_scan,concepts))
    candidates.extend(_missing_reference_candidates(repo_scan,concepts))

    missing_by_concept={}
    for item in (repo_scan or {}).get("missing_references",[]):
        classification=_classify_missing_reference(item["asset_path"])
        if classification:
            missing_by_concept.setdefault(classification[1],[]).append(item)

    for candidate in candidates:
        category=candidate["category"]
        concept=candidate.get("concept",slug(candidate["description"]))
        base=f"{category}_{slug(concept)}"
        names[base]=names.get(base,0)+1
        asset_id=base if names[base]==1 else f"{base}_{names[base]:02d}"

        key=CATEGORY_DEFAULT_MAP.get(category,"object_sprite")
        fallback=defaults[key]
        matches=_repository_matches(candidate,repo_scan)
        existing_dimensions=_dominant_existing_dimensions(matches)
        missing_matches=missing_by_concept.get(concept,[])

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

        target_path=candidate.get("target_path")
        if not target_path and missing_matches:
            target_path=missing_matches[0]["asset_path"]
        filename=Path(target_path).name if target_path else f"{asset_id}.png"

        existing_paths=[item["path"] for item in matches]
        generation_required=not bool(matches)
        reason=(
            "existing_semantic_resource" if matches
            else "missing_repository_reference" if target_path
            else "derived_requirement" if candidate["confidence"]=="derived"
            else "gdd_requirement"
        )
        requirement_type="repository" if reason=="missing_repository_reference" or candidate.get("derivation","").startswith("repository_") else ("rule" if candidate["confidence"]=="derived" else "gdd")
        requirement_reference=(
            target_path if reason=="missing_repository_reference"
            else candidate.get("derivation",candidate["section"])
        )

        assets.append({
            "asset_id":asset_id,
            "filename":filename,
            "target_path":target_path,
            "category":category,
            "concept":concept,
            "description":candidate["description"],
            "dimensions":{"width":width,"height":height,"aspect_ratio":_ratio(width,height),"source":dimension_source},
            "output":{"format":"png","alpha":alpha},
            "generation":{"required":generation_required,"reason":reason},
            "existing_matches":existing_paths,
            "referenced_from":candidate.get("referenced_from",[]) or [source for item in missing_matches for source in item.get("referenced_from",[])],
            "source_trace":{"requirement":{
                "type":requirement_type,
                "reference":requirement_reference,
                "text":" ".join(candidate.get("source_texts",[])[:3]) or candidate.get("source_text",candidate["description"]),
            }},
            "confidence":candidate["confidence"],
        })
    return {"schema_version":1,"game":analysis["game_title"],"status":"awaiting_asset_inventory_approval","assets":assets}
