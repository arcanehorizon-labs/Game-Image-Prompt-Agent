from pathlib import Path
import yaml
from gipa.workflow import approve, plan, prompts, validate_project

ROOT=Path(__file__).resolve().parents[1]

def test_end_to_end_prompt_workflow(tmp_path: Path) -> None:
    out=tmp_path/".ai-assets"
    state=plan(ROOT/"examples"/"SAMPLE_GDD.md",out)
    assert state["status"]=="awaiting_human_approval"
    manifest=yaml.safe_load((out/"ASSET_MANIFEST.yaml").read_text(encoding="utf-8"))
    assert manifest["assets"]
    assert (out/"ASSET_REVIEW.md").exists()
    approve(out)
    assert list((out/"specs").glob("*.yaml"))
    prompts(out)
    assert (out/"prompts"/"CHATGPT_IMAGE_PROMPTS.md").exists()
    assert (out/"prompts"/"GEMINI_IMAGE_PROMPTS.md").exists()
    assert validate_project(out)==[]

def test_missing_art_style_blocks_plan(tmp_path: Path) -> None:
    gdd=tmp_path/"plain.md"
    gdd.write_text("# Plain Game\n\n## Rules\nMove pieces to reach the exit.",encoding="utf-8")
    state=plan(gdd,tmp_path/"out")
    assert state["status"]=="blocked"
