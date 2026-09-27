# Game Image Prompt Agent (GIPA)

GIPA converts a game's GDD and bounded repository evidence into a validated image-asset plan and, in later phases, production-ready prompts for image generators such as ChatGPT Images and Gemini Images.

## Current milestone: GIPA-0

GIPA-0 establishes the deterministic foundation only:

- project/config structure;
- JSON Schemas for state, art style, asset manifests, asset specs, and prompt packs;
- deterministic manifest validation;
- duplicate asset/file detection;
- dimension-to-aspect-ratio validation;
- explicit alpha-decision validation;
- state-transition validation;
- `gipa status` and `gipa validate` CLI commands;
- tests for the above behavior.

No LLM, prompt generation, provider integration, or image generation is implemented in GIPA-0.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

## CLI

Validate the example state:

```powershell
gipa validate state examples/STATE.yaml
```

Validate the example asset manifest:

```powershell
gipa validate manifest examples/ASSET_MANIFEST.yaml
```

Show project state:

```powershell
gipa status --state examples/STATE.yaml
```

## Planned phases

| Phase | Scope |
|---|---|
| GIPA-0 | Deterministic foundation, config, schemas, CLI and tests |
| GIPA-1 | GDD parsing and art-style extraction |
| GIPA-2 | Asset inventory and gameplay-semantic classification |
| GIPA-3 | Bounded repository inspection and dimension/naming resolution |
| GIPA-4 | Human approval gate and asset specifications |
| GIPA-5 | Canonical prompt compiler and provider adapters |
| GIPA-6 | Validation hardening and AI Game Factory integration contract |

## Design principle

A provider-independent canonical specification is the semantic source of truth. Provider adapters may alter capability-specific syntax later, but they must not change asset meaning, visual identity, dimensions, or gameplay constraints.
