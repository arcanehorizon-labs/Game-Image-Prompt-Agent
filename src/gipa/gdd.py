"""Bounded deterministic GDD parsing."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
from .io import read_text

@dataclass(frozen=True)
class Section:
    title: str
    body: str

def parse_sections(text: str) -> list[Section]:
    """Split Markdown-like text into heading sections while preserving content."""
    matches = list(re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", text))
    if not matches:
        return [Section("Document", text.strip())]
    result = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result.append(Section(match.group(1).strip(), text[match.end():end].strip()))
    return result

def game_title(path: Path, text: str) -> str:
    """Prefer the first Markdown H1, then fall back to the filename stem."""
    match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    return match.group(1).strip() if match else path.stem.replace("_", " ").replace("-", " ")

def _sentences(text: str) -> list[str]:
    return [p.strip(" -*\t") for p in re.split(r"[\r\n]+|(?<=[.!?])\s+", text) if p.strip(" -*\t")]

STYLE_TERMS = ("art style","art direction","visual","aesthetic","palette","lighting","stylized","realistic","cartoon","pixel","low-poly","low poly","neon","gothic","cyberpunk","hand-painted","hand painted","3d","2d")
ASSET_KEYWORDS = {
    "character": ("character","hero","player","protagonist"),
    "enemy": ("enemy","guard","boss","monster"),
    "environment_background": ("background","backdrop","environment"),
    "environment_texture": ("floor","wall","tile","texture","terrain"),
    "prop": ("prop","crate","chest","terminal","vehicle","obstacle"),
    "ui": ("ui","hud","button","panel","menu"),
    "vfx": ("vfx","particle","effect","explosion","glow"),
    "splash_asset": ("splash","loading screen"),
    "launcher_asset": ("launcher icon","app icon","game icon"),
    "store_asset": ("store","feature graphic","promotional","promo"),
}

def extract_style_evidence(sections: list[Section]) -> list[dict]:
    """Collect traceable sentences likely to describe art direction."""
    evidence = []
    for section in sections:
        heading_hit = any(term in section.title.lower() for term in STYLE_TERMS)
        for sentence in _sentences(section.body):
            if heading_hit or any(term in sentence.lower() for term in STYLE_TERMS):
                evidence.append({"text": sentence, "section": section.title})
    return evidence[:40]

def extract_asset_candidates(sections: list[Section]) -> list[dict]:
    """Extract conservative asset candidates from asset-oriented sentences."""
    candidates, seen = [], set()
    for section in sections:
        for sentence in _sentences(section.body):
            lower = sentence.lower()
            for category, keywords in ASSET_KEYWORDS.items():
                if any(re.search(rf"\b{re.escape(k)}s?\b", lower) for k in keywords):
                    key = (category, lower)
                    if key not in seen:
                        seen.add(key)
                        candidates.append({"category": category, "description": sentence, "section": section.title, "confidence": "explicit"})
                    break
    return candidates[:250]

def analyze_gdd(path: Path) -> dict:
    """Return deterministic evidence extracted from a Markdown/text GDD."""
    text = read_text(path)
    sections = parse_sections(text)
    style = extract_style_evidence(sections)
    return {
        "game_title": game_title(path, text),
        "sections": [{"title": s.title, "body": s.body} for s in sections],
        "style_evidence": style,
        "asset_candidates": extract_asset_candidates(sections),
        "style_status": "resolved" if style else "uncertain",
    }
