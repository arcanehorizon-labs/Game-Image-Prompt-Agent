from pathlib import Path
import yaml
from docx import Document
from gipa.workflow import approve, plan, prompts, validate_project

ROOT=Path(__file__).resolve().parents[1]

def test_end_to_end_prompt_workflow(tmp_path: Path) -> None:
    out=tmp_path/".ai-assets"
    state=plan(ROOT/"examples"/"SAMPLE_GDD.md",out)
    assert state["status"]=="awaiting_human_approval"
    manifest=yaml.safe_load((out/"ASSET_MANIFEST.yaml").read_text(encoding="utf-8"))
    assert manifest["assets"]
    assert not any(a["description"].startswith("Premium stylized") for a in manifest["assets"])
    assert any(a["category"]=="environment_texture" for a in manifest["assets"])
    assert any(a["category"]=="environment_background" for a in manifest["assets"])
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

def test_explicit_dimensions_and_alpha_override_fallback(tmp_path: Path) -> None:
    gdd=tmp_path/"dimensions.md"
    gdd.write_text(
        "# Dimension Game\n\n"
        "## Art Direction\nStylized 3D with clean shapes and cyan lighting.\n\n"
        "## Assets\nCreate a floor tile at 1536 x 768 with an opaque background.\n"
        "Create a hero character at 1024 × 2048 with a transparent background.\n",
        encoding="utf-8",
    )
    out=tmp_path/"out"
    plan(gdd,out)
    manifest=yaml.safe_load((out/"ASSET_MANIFEST.yaml").read_text(encoding="utf-8"))
    floor=next(a for a in manifest["assets"] if a["category"]=="environment_texture")
    hero=next(a for a in manifest["assets"] if a["category"]=="character")
    assert (floor["dimensions"]["width"],floor["dimensions"]["height"])==(1536,768)
    assert floor["dimensions"]["source"]["type"]=="gdd"
    assert floor["output"]["alpha"] is False
    assert (hero["dimensions"]["width"],hero["dimensions"]["height"])==(1024,2048)
    assert hero["output"]["alpha"] is True

def test_docx_gdd_is_supported(tmp_path: Path) -> None:
    gdd=tmp_path/"game.docx"
    doc=Document()
    doc.add_heading("DOCX Game",level=1)
    doc.add_heading("Art Direction",level=2)
    doc.add_paragraph("Stylized 3D neon visual style with controlled lighting.")
    doc.add_heading("Assets",level=2)
    doc.add_paragraph("A 2048 x 2048 seamless floor tile.")
    doc.save(gdd)
    out=tmp_path/"out"
    state=plan(gdd,out)
    assert state["status"]=="awaiting_human_approval"
    manifest=yaml.safe_load((out/"ASSET_MANIFEST.yaml").read_text(encoding="utf-8"))
    assert manifest["assets"][0]["dimensions"]["width"]==2048
