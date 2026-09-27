"""Optional bounded repository inspection."""
from __future__ import annotations
from pathlib import Path
import re
from PIL import Image

IMAGE_EXTENSIONS={".png",".jpg",".jpeg",".webp"}
TEXT_EXTENSIONS={".cpp",".cc",".cxx",".h",".hpp",".json",".yaml",".yml",".xml",".gradle",".cmake",".txt",".md"}
MAX_FILES=4000
MAX_TEXT_BYTES=512_000

def _ignored_part(part: str) -> bool:
    lower=part.lower()
    return lower in {".git",".venv",".gradle",".cxx","deriveddata",".ai-assets"} or lower=="build" or lower.startswith("build_") or lower.startswith("cmake-build")

def _bounded_files(root: Path):
    count=0
    for path in root.rglob("*"):
        if count>=MAX_FILES:
            return
        if not path.is_file() or any(_ignored_part(part) for part in path.parts):
            continue
        count+=1
        yield path

def _image_metadata(path: Path,rel: str) -> dict:
    item={"path":rel,"filename":path.name,"stem":path.stem.lower()}
    try:
        with Image.open(path) as image:
            item["width"],item["height"]=image.size
            item["mode"]=image.mode
            item["alpha"]="A" in image.getbands()
    except Exception:
        item["width"]=None; item["height"]=None; item["mode"]=None; item["alpha"]=None
    return item

def _normalize_asset_path(value: str) -> str:
    return value.replace("\\","/").lstrip("./")

def _is_relevant_asset_reference(value: str) -> bool:
    lower=value.lower()
    return any(marker in lower for marker in ("content/","resources/","assets/","art/"))

def scan_repository(root: Path) -> dict:
    """Collect source-image metadata and detect referenced-but-missing art resources."""
    images=[]
    references=[]
    if not root.exists():
        return {"enabled":True,"root":str(root),"status":"missing","images":[],"references":[],"missing_references":[]}
    for path in _bounded_files(root):
        rel=path.relative_to(root).as_posix()
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(_image_metadata(path,rel))
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            if path.stat().st_size>MAX_TEXT_BYTES:
                continue
            text=path.read_text(encoding="utf-8",errors="ignore")
        except OSError:
            continue
        for match in re.finditer(r"['\"]([^'\"]+\.(?:png|jpg|jpeg|webp))['\"]",text,flags=re.I):
            asset_path=_normalize_asset_path(match.group(1))
            if _is_relevant_asset_reference(asset_path):
                references.append({"source":rel,"asset_path":asset_path})
            if len(references)>=2000:
                break

    existing_paths={item["path"].lower() for item in images}
    existing_names={item["filename"].lower() for item in images}
    missing=[]
    seen=set()
    for ref in references:
        asset_path=ref["asset_path"]
        key=asset_path.lower()
        basename=Path(asset_path).name.lower()
        if key in existing_paths or basename in existing_names or key in seen:
            continue
        seen.add(key)
        missing.append({"asset_path":asset_path,"referenced_from":[ref["source"]]})

    by_path={item["asset_path"]:item for item in missing}
    for ref in references:
        item=by_path.get(ref["asset_path"])
        if item and ref["source"] not in item["referenced_from"]:
            item["referenced_from"].append(ref["source"])

    return {
        "enabled":True,"root":str(root),"status":"ok",
        "images":images[:1500],
        "references":references[:2000],
        "missing_references":missing[:500],
    }
