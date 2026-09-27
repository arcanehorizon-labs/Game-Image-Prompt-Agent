"""Bounded deterministic GDD parsing for Markdown, text, DOCX, and text PDFs."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
from docx import Document
from pypdf import PdfReader
from .io import read_text

@dataclass(frozen=True)
class Section:
    title: str
    body: str

def read_gdd(path: Path) -> str:
    """Read a supported GDD format as normalized text."""
    suffix=path.suffix.lower()
    if suffix in {".md",".markdown",".txt"}:
        return read_text(path)
    if suffix==".docx":
        doc=Document(path)
        lines=[]
        for paragraph in doc.paragraphs:
            text=paragraph.text.strip()
            if not text:
                continue
            style=(paragraph.style.name or "").strip().lower() if paragraph.style else ""
            if style=="title":
                lines.append("# "+text)
            elif style.startswith("heading"):
                match=re.search(r"(\d+)",style)
                level=int(match.group(1)) if match else 2
                lines.append("#"*max(1,min(level,6))+" "+text)
            else:
                lines.append(text)
        return "\n\n".join(lines)
    if suffix==".pdf":
        reader=PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    raise ValueError(f"Unsupported GDD format: {path.suffix}. Use .md, .txt, .docx, or .pdf.")

def parse_sections(text: str) -> list[Section]:
    """Split Markdown-like text into heading sections while preserving content."""
    matches=list(re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$",text))
    if not matches:
        return [Section("Document",text.strip())]
    result=[]
    for index,match in enumerate(matches):
        end=matches[index+1].start() if index+1<len(matches) else len(text)
        result.append(Section(match.group(1).strip(),text[match.end():end].strip()))
    return result

def _clean_filename_title(path: Path) -> str:
    value=path.stem
    value=re.sub(r"^\d+[_ -]+","",value)
    value=re.sub(r"(?i)[_ -]+game[_ -]+concept.*$","",value)
    value=value.replace("_"," ").replace("-"," ").strip()
    return re.sub(r"\s+"," ",value)

def game_title(path: Path,text: str) -> str:
    """Use a real document title when present; reject numbered section headings."""
    for match in re.finditer(r"(?m)^#\s+(.+?)\s*$",text):
        candidate=match.group(1).strip()
        lower=candidate.lower()
        if re.match(r"^\d+\s*[.)-]",candidate):
            continue
        if any(lower.startswith(prefix) for prefix in ("purpose","scope","overview","high concept","introduction")):
            continue
        return candidate
    return _clean_filename_title(path)

def _sentences(text: str) -> list[str]:
    return [p.strip(" -*\t") for p in re.split(r"[\r\n]+|(?<=[.!?])\s+",text) if p.strip(" -*\t")]

def _dimensions(text: str) -> dict | None:
    match=re.search(r"\b(\d{2,5})\s*[x×]\s*(\d{2,5})\b",text,re.I)
    return {"width":int(match.group(1)),"height":int(match.group(2))} if match else None

def _alpha(text: str) -> bool | None:
    lower=text.lower()
    if any(term in lower for term in ("transparent background","with transparency","alpha channel","transparent png")):
        return True
    if any(term in lower for term in ("opaque background","no transparency","without transparency")):
        return False
    return None

STYLE_SECTION_TERMS=("art direction","art style","visual style","visual direction","aesthetic","look and feel")
STYLE_SIGNAL_TERMS=("stylized","realistic","cartoon","pixel","low-poly","low poly","neon","gothic","cyberpunk","hand-painted","hand painted","3d","2d","palette","lighting","silhouette","readability","top-down","high-angle","high angle","geometric","premium")
STYLE_QUESTION_TERMS=("tone","style","visual","look","aesthetic","palette","art direction")
PLATFORM_TERMS={"android":"android","ios":"ios","iphone":"ios","ipad":"ios","mobile":"mobile","windows":"windows","desktop":"desktop","pc":"desktop"}
EXCLUDED_SECTION_TERMS=("out of mvp","out of scope","explicitly out","success metric","prototype metric","decision required","open question","questions","ai-assisted","ai assisted","retention direction","monetization","risks")
NEGATIVE_SENTENCE_PREFIXES=("do not ","don't ","should not ","must not ","avoid ","how ","why ","what ","should ","can players ","players can ","is there ")

ASSET_CONCEPTS=(
    ("character","player_character",("player","protagonist","hero","thief")),
    ("enemy","guard_enemy",("guard","guards")),
    ("enemy","enemy_character",("enemy","enemies","monster","monsters")),
    ("gameplay_object","security_camera",("camera","cameras","security camera")),
    ("gameplay_object","security_laser",("laser","lasers","laser beam")),
    ("gameplay_object","door",("door","doors")),
    ("gameplay_object","exit",("exit","exits")),
    ("gameplay_object","loot",("loot","diamond","treasure")),
    ("prop","terminal",("terminal","security terminal","console")),
    ("prop","crate",("crate","crates")),
    ("prop","chest",("chest","chests")),
    ("environment_texture","floor_tile",("floor tile","floor","flooring")),
    ("environment_texture","wall_tile",("wall tile","wall","walls")),
    ("environment_texture","terrain_texture",("terrain","texture")),
    ("environment_background","background",("background","backdrop")),
    ("ui","menu_ui",("menu","main menu")),
    ("ui","hud_ui",("hud","heads-up display","heads up display")),
    ("ui","button_ui",("button","buttons")),
    ("ui","panel_ui",("panel","panels")),
    ("vfx","visual_effect",("vfx","particle","particles","effect","effects")),
    ("splash_asset","splash_screen",("splash","splash screen","loading screen")),
    ("launcher_asset","launcher_icon",("launcher icon","app icon","game icon")),
    ("store_asset","feature_graphic",("feature graphic","store artwork","promotional art","promo art")),
)

ENVIRONMENT_CONTEXT_TERMS=("room","rooms","corridor","corridors","grid","tilemap","board","facility","office","vault","museum","warehouse","bank")
STEALTH_CONCEPTS={"player_character","guard_enemy","security_camera","security_laser","door"}

def _is_excluded_section(title: str) -> bool:
    lower=title.lower()
    return any(term in lower for term in EXCLUDED_SECTION_TERMS)

def _looks_like_question_or_nonrequirement(sentence: str) -> bool:
    lower=sentence.strip().lower()
    return sentence.strip().endswith("?") or any(lower.startswith(prefix) for prefix in NEGATIVE_SENTENCE_PREFIXES)

def extract_style_evidence(sections: list[Section]) -> tuple[list[dict],list[dict]]:
    """Return declarative style evidence plus unresolved style questions."""
    evidence=[]
    questions=[]
    for section in sections:
        lower_title=section.title.lower()
        is_style_section=any(term in lower_title for term in STYLE_SECTION_TERMS)
        for sentence in _sentences(section.body):
            lower=sentence.lower()
            if sentence.endswith("?") and any(term in lower for term in STYLE_QUESTION_TERMS):
                questions.append({"text":sentence,"section":section.title})
                continue
            if is_style_section and any(term in lower for term in STYLE_SIGNAL_TERMS):
                evidence.append({"text":sentence,"section":section.title})
    return evidence[:40],questions[:20]

def extract_platform_evidence(sections: list[Section]) -> list[dict]:
    """Find explicit platform mentions."""
    evidence=[]
    seen=set()
    for section in sections:
        if _is_excluded_section(section.title):
            continue
        for sentence in _sentences(section.body):
            lower=sentence.lower()
            for token,platform in PLATFORM_TERMS.items():
                if re.search(rf"\b{re.escape(token)}\b",lower) and platform not in seen:
                    seen.add(platform)
                    evidence.append({"platform":platform,"section":section.title,"text":sentence})
    return evidence

def extract_asset_candidates(sections: list[Section]) -> list[dict]:
    """Extract concrete asset concepts and aggregate all supporting GDD evidence."""
    by_key={}
    order=[]
    for section in sections:
        lower_title=section.title.lower()
        if _is_excluded_section(section.title) or any(term in lower_title for term in STYLE_SECTION_TERMS):
            continue
        for sentence in _sentences(section.body):
            if _looks_like_question_or_nonrequirement(sentence):
                continue
            lower=sentence.lower()
            for category,concept,terms in ASSET_CONCEPTS:
                matched=[term for term in terms if re.search(rf"\b{re.escape(term)}\b",lower)]
                if not matched:
                    continue
                key=(category,concept)
                if key not in by_key:
                    by_key[key]={
                        "category":category,
                        "concept":concept,
                        "description":concept.replace("_"," "),
                        "matched_terms":[],
                        "source_texts":[],
                        "sections":[],
                        "section":section.title,
                        "confidence":"explicit",
                    }
                    order.append(key)
                candidate=by_key[key]
                for term in matched:
                    if term not in candidate["matched_terms"]:
                        candidate["matched_terms"].append(term)
                candidate["source_texts"].append(sentence)
                if section.title not in candidate["sections"]:
                    candidate["sections"].append(section.title)
                explicit_dimensions=_dimensions(sentence)
                if explicit_dimensions and "dimensions" not in candidate:
                    candidate["dimensions"]=explicit_dimensions
                alpha=_alpha(sentence)
                if alpha is not None and "alpha" not in candidate:
                    candidate["alpha"]=alpha
    for candidate in by_key.values():
        candidate["source_text"]=candidate["source_texts"][0]
    return [by_key[key] for key in order][:250]

def infer_required_assets(candidates: list[dict],platforms: list[dict],sections: list[Section]) -> list[dict]:
    """Add high-confidence platform and gameplay baseline assets with traceable derivations."""
    result=list(candidates)
    concepts={item.get("concept") for item in candidates}
    all_text=" ".join(section.body.lower() for section in sections if not _is_excluded_section(section.title))
    has_environment_context=any(re.search(rf"\b{re.escape(term)}s?\b",all_text) for term in ENVIRONMENT_CONTEXT_TERMS)
    stealth_signal=bool(concepts & STEALTH_CONCEPTS)

    def add(category: str,concept: str,description: str,derivation: str) -> None:
        if concept in {item.get("concept") for item in result}:
            return
        result.append({
            "category":category,"concept":concept,"description":description,
            "matched_terms":[],"source_text":"Derived production requirement",
            "source_texts":["Derived production requirement"],"sections":["Derived requirement"],
            "section":"Derived requirement","confidence":"derived","derivation":derivation,
        })

    if stealth_signal and has_environment_context:
        add("environment_texture","floor_tile","floor tile","stealth_environment_requires_floor_surface")
        add("environment_texture","wall_tile","wall tile","stealth_environment_requires_wall_surface")

    mobile=any(item["platform"] in {"android","ios","mobile"} for item in platforms)
    if mobile:
        add("launcher_asset","launcher_icon","launcher icon","mobile_platform_requires_launcher_icon")
        add("splash_asset","splash_screen","splash screen","mobile_game_requires_launch_visual")

    android=any(item["platform"]=="android" for item in platforms)
    if android:
        add("store_asset","feature_graphic","store feature graphic","android_store_presence_requires_feature_graphic")

    return result

def analyze_gdd(path: Path) -> dict:
    """Return deterministic evidence extracted from a supported GDD."""
    text=read_gdd(path)
    sections=parse_sections(text)
    style,style_questions=extract_style_evidence(sections)
    platforms=extract_platform_evidence(sections)
    assets=infer_required_assets(extract_asset_candidates(sections),platforms,sections)
    return {
        "game_title":game_title(path,text),
        "source_format":path.suffix.lower(),
        "sections":[{"title":s.title,"body":s.body} for s in sections],
        "style_evidence":style,
        "style_questions":style_questions,
        "platform_evidence":platforms,
        "asset_candidates":assets,
        "style_status":"uncertain" if style_questions or not style else "resolved",
    }
