"""Human-readable review and prompt rendering."""
from __future__ import annotations
from collections import defaultdict

def review_markdown(style: dict,manifest: dict,repo_scan: dict | None=None) -> str:
    lines=[
        f"# Asset Review — {manifest['game']}","",
        f"Art style confidence: **{style['confidence']}**",
        f"Proposed assets: **{len(manifest['assets'])}**","",
    ]
    if style["confidence"]=="uncertain":
        lines += ["## Blocking clarification","","The GDD leaves material visual-style decisions unresolved. Provide an approved style override before prompt generation.",""]
        questions=style.get("visual_style",{}).get("unresolved_questions",[])
        if questions:
            lines += ["### Unresolved style questions",""]+[f"- {q}" for q in questions]+[""]
    lines += ["## Proposed assets","","| Asset | Category | Size | Alpha | Generate | Existing matches | Source |","|---|---|---:|:---:|:---:|---:|---|"]
    for asset in manifest["assets"]:
        d=asset["dimensions"]
        lines.append(
            f"| {asset.get('concept',asset['asset_id'])} | {asset['category']} | {d['width']}×{d['height']} | "
            f"{'yes' if asset['output']['alpha'] else 'no'} | {'yes' if asset['generation']['required'] else 'no'} | "
            f"{len(asset.get('existing_matches',[]))} | {asset['source_trace']['requirement']['reference']} |"
        )
    if repo_scan and repo_scan.get("enabled"):
        lines += ["","## Repository scan","",f"Existing images found: **{len(repo_scan.get('images',[]))}**",f"Source image references found: **{len(repo_scan.get('references',[]))}**"]
    lines += ["","## Next step",""]
    if style["confidence"]=="uncertain":
        lines.append("Rerun gipa plan with --style-file <approved-style.yaml>.")
    else:
        lines.append("Review ASSET_MANIFEST.yaml, then run gipa approve --out .ai-assets.")
    return "\n".join(lines)+"\n"

def prompts_markdown(game: str,provider: str,records: list[dict]) -> str:
    lines=[f"# {provider} Image Prompts — {game}",""]
    for record in records:
        lines += [
            f"## {record['asset_id']} — Variant {record['variant']}","",
            f"Target: **{record['production_dimensions']['width']} × {record['production_dimensions']['height']} px**","",
            "~~~text",record["text"].rstrip(),"~~~","",
        ]
    return "\n".join(lines)

def batch_prompts_markdown(game: str,provider: str,records: list[dict]) -> str:
    """Render one copy/paste batch prompt per category using default Variant A."""
    groups=defaultdict(list)
    for record in records:
        if record["variant"]=="A":
            groups[str(record.get("category","assets"))].append(record)
    lines=[f"# {provider} Batch Image Prompts — {game}",""]
    for category,items in sorted(groups.items()):
        lines += [f"## {category} batch","", "~~~text",
            f"Generate a cohesive {category} asset batch for '{game}'. Maintain identical visual language, palette, lighting philosophy, material treatment, camera rules, and detail density across all outputs. Generate each listed asset as a separate image; do not combine them into one atlas or collage.",""]
        for index,record in enumerate(items,1):
            lines += [f"ASSET {index}: {record['asset_id']}",record["text"].rstrip(),""]
        lines += ["~~~",""]
    return "\n".join(lines)
