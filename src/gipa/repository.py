"""Optional bounded repository inspection."""
from __future__ import annotations
from pathlib import Path
import re
from PIL import Image

IMAGE_EXTENSIONS={".png",".jpg",".jpeg",".webp"}
TEXT_EXTENSIONS={".cpp",".cc",".cxx",".h",".hpp",".json",".yaml",".yml",".xml",".gradle",".cmake",".txt",".md"}
MAX_FILES=4000
MAX_TEXT_BYTES=512_000

def _bounded_files(root: Path):
    count=0
    for path in root.rglob("*"):
        if count>=MAX_FILES:
            return
        if not path.is_file() or any(part in {".git",".venv","build",".gradle",".cxx","DerivedData"} for part in path.parts):
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
        item["width"]=None
        item["height"]=None
        item["mode"]=None
        item["alpha"]=None
    return item

def scan_repository(root: Path) -> dict:
    """Collect existing image metadata and bounded source references."""
    images=[]
    references=[]
    if not root.exists():
        return {"enabled":True,"root":str(root),"status":"missing","images":[],"references":[]}
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
            references.append({"source":rel,"asset_path":match.group(1).replace("\\","/")})
            if len(references)>=2000:
                break
    return {
        "enabled":True,
        "root":str(root),
        "status":"ok",
        "images":images[:1500],
        "references":references[:2000],
    }
