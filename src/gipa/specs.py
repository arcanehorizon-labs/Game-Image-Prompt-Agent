"""Asset specification generation."""
from __future__ import annotations

CATEGORY_EXCLUSIONS={
    "environment_texture":["characters","enemies","loot","exits","UI","text","logos","navigation markers","collision boundaries","puzzle geometry","baked doors","baked cameras"],
    "environment_background":["UI","text","logos","navigation markers","baked gameplay geometry"],
    "character":["UI","text","logos","unrelated characters","background scene clutter"],
    "enemy":["UI","text","logos","unrelated characters","background scene clutter"],
    "prop":["UI","text","logos","unrelated props","background scene clutter"],
    "gameplay_object":["UI","text","logos","unrelated gameplay objects","background scene clutter"],
    "ui":["photorealistic scene clutter","characters unless explicitly requested"],
    "vfx":["text","logos","UI chrome"],
    "launcher_asset":["small unreadable text","UI chrome"],
    "splash_asset":["UI chrome","loading bar baked into artwork","small unreadable text"],
    "store_asset":["UI chrome","small unreadable text"],
}

def _style_is_top_down(style: dict) -> bool:
    text=" ".join(str(x).lower() for x in style.get("visual_style",{}).get("summary",[]))
    return "top-down" in text or "top down" in text or "high-angle" in text or "high angle" in text

def _semantic_camera(asset: dict,style: dict | None) -> dict:
    category=asset["category"]
    concept=asset.get("concept","")
    top_down=_style_is_top_down(style or {})
    if category=="environment_texture":
        return {"view":"strict_orthographic_top_down","perspective":"none"}
    if concept in {"player_spacecraft","planet","moon","asteroid","gas_giant","star","black_hole","space_wreck","extraction_gate","salvage_pickup","fuel_cell_pickup"}:
        return {"view":"centered_2d_gameplay_plane","perspective":"none"}
    if top_down and category in {"character","enemy","prop","gameplay_object"}:
        return {"view":"top_down_game_readable","perspective":"controlled_minimal"}
    return {"view":"game_appropriate","perspective":"controlled"}

def build_asset_spec(asset: dict,style: dict | None=None) -> dict:
    """Create one structured prompt-ready specification from an approved asset."""
    dims=asset["dimensions"]
    category=asset["category"]
    camera=_semantic_camera(asset,style)
    return {
        "schema_version":1,
        "asset_id":asset["asset_id"],
        "subject":{"primary":asset.get("description",asset["asset_id"])},
        "purpose":category,
        "camera":camera,
        "composition":{
            "seamless":category=="environment_texture",
            "directional_bias":False if category=="environment_texture" else None,
            "isolated_subject":category in {"character","enemy","prop","gameplay_object","vfx"},
        },
        "dimensions":{
            "production":{"width":dims["width"],"height":dims["height"]},
            "aspect_ratio":dims["aspect_ratio"],
            "source":dims["source"],
        },
        "output":dict(asset["output"]),
        "visual_requirements":{
            "include":[asset.get("description",asset["asset_id"])],
            "exclude":CATEGORY_EXCLUSIONS.get(category,["UI","text","logos"]),
        },
        "semantic_context":{
            "requirement":asset.get("source_trace",{}).get("requirement",{}).get("text",""),
        },
        "style_profile":{"source":"../ART_STYLE.yaml"},
        "source_trace":asset["source_trace"],
        "confidence":asset["confidence"],
    }
