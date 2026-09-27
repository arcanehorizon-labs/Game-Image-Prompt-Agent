# Game Image Prompt Agent (GIPA)

GIPA reads a game's GDD, optionally inspects a bounded game repository, creates a reviewable image-asset inventory, and compiles production-ready prompts for ChatGPT Images and Gemini Images with exact target dimensions and a shared game art direction.

GIPA does not generate images. Image generation remains a manual step so users can review quality before committing assets.

## Workflow

1. Read the GDD and extract traceable visual-style and asset evidence.
2. Optionally scan the game repository for existing images and source references.
3. Produce ART_STYLE.yaml, ASSET_MANIFEST.yaml, and ASSET_REVIEW.md.
4. Stop for human approval.
5. Generate one structured specification per required asset.
6. Compile three variants per asset: canonical, ChatGPT Images, and Gemini Images.
7. Validate schemas, filenames, dimensions, alpha decisions, and exact-dimension text in prompts.

If the GDD does not provide enough art-direction evidence, planning is blocked instead of inventing the game's visual identity.

## Install

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
~~~

## End-to-end usage

~~~powershell
gipa plan --gdd "E:\game\docs\GDD.md" --game-root "E:\game" --out "E:\game\.ai-assets"
~~~

Review ART_STYLE.yaml, ASSET_MANIFEST.yaml, and ASSET_REVIEW.md. You may edit the manifest before approval, for example to replace a category fallback dimension with a known implementation-specific dimension.

~~~powershell
gipa approve --out "E:\game\.ai-assets"
gipa prompts --out "E:\game\.ai-assets"
gipa validate-project --out "E:\game\.ai-assets"
gipa status --state "E:\game\.ai-assets\STATE.yaml"
~~~

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
    <asset-id>.yaml
  prompts/
    canonical.json
    chatgpt_images.json
    gemini_images.json
    IMAGE_PROMPTS.md
    CHATGPT_IMAGE_PROMPTS.md
    GEMINI_IMAGE_PROMPTS.md
  VALIDATION.md
~~~

## Dimension precedence

The intended resolution order is implementation requirement, existing resource convention, explicit GDD requirement, platform requirement, project configuration, documented category fallback, then human clarification.

The current v1 planner records fallback dimensions explicitly as category_default. Repository inspection is bounded and never silently overrides a reviewed manifest. A user can replace fallback dimensions in ASSET_MANIFEST.yaml before approval; those reviewed values become authoritative for specs and prompts.

## Prompt consistency

All prompts are compiled from the same structured specification and ART_STYLE.yaml. Provider adapters add only lightweight framing and must not change dimensions, aspect ratio, camera, asset semantics, required or forbidden elements, or project art direction.

Three visual-treatment variants are emitted for each asset while preserving those invariants.

## Repository inspection

Repository scanning is optional. It is bounded by file count and file size, excludes common build/cache directories, inventories existing images, and finds direct image-path references in common source/config files. It does not perform broad semantic indexing or send repository content to an external provider.

## v1 scope

Implemented:
- GDD Markdown/text parsing;
- art-direction evidence extraction;
- asset candidate discovery;
- human review gate;
- optional bounded repository scan;
- deterministic category dimension fallbacks;
- structured asset specs;
- gameplay-aware exclusions for environment textures;
- three prompt variants;
- ChatGPT Images and Gemini Images prompt adapters;
- schema/package validation;
- end-to-end CLI;
- automated tests.

Not implemented by design:
- automatic image generation;
- automatic commits of generated images;
- hidden provider calls;
- arbitrary visual-style invention when the GDD is ambiguous.

## Validation sample

~~~powershell
gipa plan --gdd examples/SAMPLE_GDD.md --out .tmp-assets
gipa approve --out .tmp-assets
gipa prompts --out .tmp-assets
gipa validate-project --out .tmp-assets
~~~

Expected final line:

~~~text
GIPA project validation PASS
~~~


## Unresolved art direction

If the GDD contains unresolved visual questions, planning intentionally returns `status: blocked`. Supply an approved style contract instead of letting the agent invent one:

~~~powershell
gipa plan \
  --gdd "E:\game\docs\GDD.docx" \
  --game-root "E:\game" \
  --style-file "E:\game\APPROVED_ART_STYLE.yaml" \
  --out "E:\game\.ai-assets"
~~~

The style file uses the same structure as `ART_STYLE.yaml`.

## Production prompt outputs

In addition to individual prompt packs, GIPA writes category batch packs:

- `BATCH_PROMPTS.md`
- `CHATGPT_BATCH_PROMPTS.md`
- `GEMINI_BATCH_PROMPTS.md`

Each image prompt contains the exact target production dimensions and instructs the image generator to use a closest-larger same-aspect-ratio canvas when the interface cannot emit the exact pixel dimensions. Final crop/resize remains deterministic.

## Existing resource reconciliation

With `--game-root`, GIPA reads existing PNG/JPEG/WebP dimensions and alpha information. Concrete GDD concepts such as player, guard, camera, laser, door, floor, and wall are matched against existing filenames. Matching resources are recorded in `existing_matches` and are not regenerated by default. Their dimensions take precedence over category fallback dimensions unless the GDD explicitly specifies dimensions.
