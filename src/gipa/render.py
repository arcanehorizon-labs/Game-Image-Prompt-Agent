"""Human-readable review and prompt rendering."""
from __future__ import annotations

def review_markdown(style: dict, manifest: dict, repo_scan: dict | None = None) -> str:
    """Render the proposed inventory for human approval."""
    lines=[
        f"# Asset Review — {manifest['game']}","",
        f"Art style confidence: **{style['confidence']}**",
        f"Proposed assets: **{len(manifest['assets'])}**","",
    ]
    if style["confidence"]=="uncertain":
        lines += ["## Blocking clarification","","The GDD does not contain enough explicit visual-style evidence. Define or approve the game's art direction before prompt generation.",""]
    lines += ["## Proposed assets","","| Asset ID | Category | Size | Alpha | Generate | Source |","|---|---|---:|:---:|:---:|---|"]
    for asset in manifest["assets"]:
        d=asset["dimensions"]
        lines.append(f"| {asset['asset_id']} | {asset['category']} | {d['width']}×{d['height']} | {'yes' if asset['output']['alpha'] else 'no'} | {'yes' if asset['generation']['required'] else 'no'} | {asset['source_trace']['requirement']['reference']} |")
    if repo_scan and repo_scan.get("enabled"):
        lines += ["","## Repository scan","",f"Existing images found: **{len(repo_scan.get('images',[]))}**",f"Source image references found: **{len(repo_scan.get('references',[]))}**"]
    lines += ["","## Next step","","Review ASSET_MANIFEST.yaml, adjust any inferred dimensions or filenames if needed, then run gipa approve --out .ai-assets."]
    return "\n".join(lines)+"\n"

def prompts_markdown(game: str, provider: str, records: list[dict]) -> str:
    """Render prompt records in a copy/paste-friendly Markdown document."""
    lines=[f"# {provider} Image Prompts — {game}",""]
    for record in records:
        lines += [
            f"## {record['asset_id']} — Variant {record['variant']}","",
            f"Target: **{record['production_dimensions']['width']} × {record['production_dimensions']['height']} px**","",
            "~~~text",record["text"].rstrip(),"~~~","",
        ]
    return "\n".join(lines)
