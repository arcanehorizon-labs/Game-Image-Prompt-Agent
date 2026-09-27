"""Optional bounded repository inspection."""
from __future__ import annotations
from pathlib import Path
import re

IMAGE_EXTENSIONS = {".png",".jpg",".jpeg",".webp"}
TEXT_EXTENSIONS = {".cpp",".cc",".cxx",".h",".hpp",".json",".yaml",".yml",".xml",".gradle",".cmake",".txt"}
MAX_FILES = 4000
MAX_TEXT_BYTES = 512_000

def _bounded_files(root: Path):
    count = 0
    for path in root.rglob("*"):
        if count >= MAX_FILES:
            return
        if not path.is_file() or any(part in {".git",".venv","build",".gradle",".cxx"} for part in path.parts):
            continue
        count += 1
        yield path

def scan_repository(root: Path) -> dict:
    """Collect existing image names and bounded source references."""
    images, references = [], []
    if not root.exists():
        return {"enabled": True, "root": str(root), "status": "missing", "images": [], "references": []}
    for path in _bounded_files(root):
        rel = path.relative_to(root).as_posix()
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            images.append({"path": rel, "filename": path.name})
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > MAX_TEXT_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in re.finditer(r"['\"]([^'\"]+\.(?:png|jpg|jpeg|webp))['\"]", text, flags=re.I):
            references.append({"source": rel, "asset_path": match.group(1).replace("\\", "/")})
            if len(references) >= 1000:
                break
    return {"enabled": True, "root": str(root), "status": "ok", "images": images[:1000], "references": references[:1000]}
