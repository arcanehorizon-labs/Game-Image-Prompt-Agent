# Game Image Prompt Agent (GIPA)

GIPA turns a game's GDD and bounded repository evidence into a reviewable asset plan, provider-independent prompts, and optionally staged images generated through an explicit provider command.

OpenAI Images is the first execution provider. Generation is never hidden: it requires the `generate` command and `OPENAI_API_KEY`. Generated images are staged for human visual review before they can be copied into game asset paths, and GIPA never creates git commits for generated images.

## Workflow

1. Plan assets from the GDD and optional repository evidence.
2. Human-review the asset inventory and set any required implementation-specific dimensions and `target_path` values.
3. Approve the inventory and compile canonical/provider prompt packs.
4. Validate the prompt package.
5. Run an optional generation dry run.
6. Generate one selected prompt variant per asset with OpenAI Images.
7. Deterministically resize/encode to exact production dimensions and validate dimensions/alpha.
8. Human-review every staged image.
9. Run `approve-images` to copy approved images to explicit game-repository target paths.
10. Commit/integrate through the normal game/Factory workflow.

## Install

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
~~~

## End-to-end OpenAI Images usage

~~~powershell
gipa plan --gdd "E:\game\docs\GDD.md" --game-root "E:\game" --out "E:\game\.ai-assets"

# Review/edit ART_STYLE.yaml, ASSET_MANIFEST.yaml and ASSET_REVIEW.md.
# Before image approval, generated assets must have explicit target_path values.

gipa approve --out "E:\game\.ai-assets"
gipa prompts --out "E:\game\.ai-assets"
gipa validate-project --out "E:\game\.ai-assets"

# No API call and no charge:
gipa generate --out "E:\game\.ai-assets" --provider openai --dry-run

# Set the secret only in the environment/session.
$env:OPENAI_API_KEY = "<your key>"

# Default: variant A, high quality, gpt-image-2.5-flare.
gipa generate --out "E:\game\.ai-assets" --provider openai

# Optional targeted or higher-precision generation:
gipa generate --out "E:\game\.ai-assets" --provider openai --asset ch01_floor_main
gipa generate --out "E:\game\.ai-assets" --provider openai --model gpt-image-2.5-sunburst --quality xhigh

# Review GENERATION_REVIEW.md and every image under generated/openai.
gipa approve-images --out "E:\game\.ai-assets" --game-root "E:\game"
~~~

Use `--overwrite` only after reviewing an intended replacement. API keys are never written into GIPA state, manifests, logs, or repository files.

## OpenAI model policy

The provider currently supports:
- `gpt-image-2.5-flare` — default for fast high-quality everyday generation.
- `gpt-image-2.5-sunburst` — available when editing/precision quality is more important.

Quality is configurable: `low`, `medium`, `high`, `xhigh`, `max`, or `auto`.

GIPA maps production dimensions onto an OpenAI-compatible generation canvas when necessary, then deterministically resizes the staged result to the exact approved production dimensions. Unsupported aspect ratios greater than 3:1 are blocked instead of distorted.

## Outputs

~~~text
.ai-assets/
  STATE.yaml
  ART_STYLE.yaml
  ASSET_MANIFEST.yaml
  ASSET_REVIEW.md
  GDD_ANALYSIS.json
  REPOSITORY_SCAN.json
  specs/
  prompts/
  VALIDATION.md
  GENERATION_MANIFEST.json
  GENERATION_REVIEW.md
  generated/
    openai/
      <asset-id>.<format>
~~~

## Safety and review guarantees

- Inventory approval remains mandatory before prompt compilation.
- Prompt validation must pass before provider execution.
- Provider calls only happen from explicit generation commands.
- Existing staged images are not overwritten by default.
- Generated images are not copied into game assets before explicit visual approval.
- Copying requires an explicit relative `target_path` in the reviewed manifest.
- Existing game targets are not overwritten by default.
- GIPA never commits generated images.
- Missing art direction remains a blocker; the provider cannot invent the visual identity.

## Provider independence

Canonical prompts and structured asset specs remain the semantic source of truth. OpenAI is implemented behind the provider-neutral `ImageProvider` interface. Future providers can be added without changing planning, prompt semantics, staging, technical validation, or visual-review rules.
