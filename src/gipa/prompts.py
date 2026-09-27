"""Canonical prompt compilation and lightweight provider adapters."""
from __future__ import annotations

def _style_lines(style: dict) -> list[str]:
    return [str(item).strip() for item in style.get("visual_style",{}).get("summary",[]) if str(item).strip()]

def compile_canonical(spec: dict, style: dict, variant: str = "A") -> str:
    """Compile a prompt from structured data without changing semantics."""
    prod = spec["dimensions"]["production"]
    alpha = "transparent background" if spec["output"]["alpha"] else "opaque background"
    treatments = {"A":"balanced production treatment","B":"cleaner treatment with lower decorative detail density","C":"richer treatment with moderate detail while preserving readability"}
    lines = [
        f"Create one production image asset for the game '{style['game']['title']}'.","",
        "ASSET",spec["subject"]["primary"],"",
        "PURPOSE",str(spec["purpose"]),"",
        "ART DIRECTION",*(_style_lines(style) or ["Use the approved project art style exactly."]),"",
        "COMPOSITION AND CAMERA",
        f"Camera/view: {spec.get('camera',{}).get('view','game_appropriate')}.",
        f"Perspective: {spec.get('camera',{}).get('perspective','controlled')}.",
        f"Seamless: {'yes' if spec.get('composition',{}).get('seamless') else 'no'}.","",
        "MUST INCLUDE",*[f"- {x}" for x in spec["visual_requirements"]["include"]],"",
        "DO NOT INCLUDE",*[f"- {x}" for x in spec["visual_requirements"]["exclude"]],"",
        "TECHNICAL TARGET",
        f"Exact production size: {prod['width']} × {prod['height']} pixels.",
        f"Aspect ratio: {spec['dimensions']['aspect_ratio']}.",
        f"Output: {spec['output']['format'].upper()}, {alpha}.",
        f"Variant: {variant} — {treatments[variant]}.","",
        "Do not change the requested gameplay semantics, camera rules, dimensions, or project visual identity.",
    ]
    return "\n".join(lines).strip()+"\n"

def adapt_chatgpt(canonical: str) -> str:
    """Add minimal ChatGPT Images framing without semantic drift."""
    return "Generate one standalone production image. Follow the specification exactly and do not add unrequested objects.\n\n"+canonical

def adapt_gemini(canonical: str) -> str:
    """Add minimal Gemini Images framing without semantic drift."""
    return "Create one standalone game-production image from the following specification. Preserve every required constraint and avoid semantic additions.\n\n"+canonical

def prompt_record(spec: dict, provider: str, text: str, variant: str) -> dict:
    """Create one machine-readable prompt record."""
    return {"asset_id":spec["asset_id"],"variant":variant,"production_dimensions":dict(spec["dimensions"]["production"]),"text":text,"provider":provider}
