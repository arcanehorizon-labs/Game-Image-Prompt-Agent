"""Asset specification generation."""
from __future__ import annotations

CATEGORY_EXCLUSIONS = {
    "environment_texture":["characters","enemies","loot","exits","UI","text","logos","navigation markers","collision boundaries","puzzle geometry"],
    "environment_background":["UI","text","logos","navigation markers"],
    "character":["UI","text","logos","unrelated characters"],
    "enemy":["UI","text","logos","unrelated characters"],
    "prop":["UI","text","logos","unrelated props"],
    "ui":["photorealistic scene clutter"],
}

def build_asset_spec(asset: dict) -> dict:
    """Create one structured prompt-ready specification from an approved asset."""
    dims, category = asset["dimensions"], asset["category"]
    return {
        "schema_version":1,"asset_id":asset["asset_id"],
        "subject":{"primary":asset.get("description",asset["asset_id"])},
        "purpose":category,
        "camera":{"view":"orthographic_top_down" if category=="environment_texture" else "game_appropriate","perspective":"none" if category=="environment_texture" else "controlled"},
        "composition":{"seamless":category=="environment_texture","directional_bias":False if category=="environment_texture" else None},
        "dimensions":{"production":{"width":dims["width"],"height":dims["height"]},"aspect_ratio":dims["aspect_ratio"],"source":dims["source"]},
        "output":dict(asset["output"]),
        "visual_requirements":{"include":[asset.get("description",asset["asset_id"])],"exclude":CATEGORY_EXCLUSIONS.get(category,["UI","text","logos"])},
        "style_profile":{"source":"../ART_STYLE.yaml"},"source_trace":asset["source_trace"],"confidence":asset["confidence"],
    }
