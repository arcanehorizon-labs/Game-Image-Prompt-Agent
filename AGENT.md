# Game Image Prompt Agent

## Purpose

Convert a game's GDD and optional bounded repository evidence into a deterministic, reviewable image-asset plan, production-ready prompts, and explicitly requested staged image generation.

## Non-goals

GIPA does not silently call providers, visually approve its own output, overwrite game assets by default, or create git commits for generated images.

## Core rules

1. GDD and repository evidence are authoritative.
2. Do not invent a missing visual identity. Missing material art direction blocks planning.
3. Distinguish evidence from category defaults and record the source of dimensions.
4. Build and review the asset inventory before compiling prompts.
5. Exact production dimensions and aspect ratio must appear in every prompt.
6. Use one ART_STYLE.yaml as the visual source of truth.
7. Compile a canonical provider-independent prompt before provider adapters.
8. Provider adapters may change framing, never semantics.
9. Visual-only environment textures must exclude baked gameplay geometry, markers, UI, loot, exits, characters, and collision information unless explicitly required.
10. Existing assets discovered by bounded repository inspection must be reported rather than silently overwritten.
11. The reviewed ASSET_MANIFEST.yaml is authoritative after approval.
12. Generate individual source assets; atlas construction is outside image generation.
13. Three prompt variants may vary detail treatment only, not gameplay semantics or technical requirements.
14. Keep repository inspection bounded and local.
15. Human review is mandatory between planning and prompt compilation.
16. Provider execution must be an explicit command; no hidden network calls.
17. Provider secrets must come from environment/secrets storage and must never be persisted in project artifacts.
18. Generated images must pass deterministic technical validation before visual review.
19. Human visual review is mandatory before generated images are copied into game asset target paths.
20. GIPA never creates git commits for generated images.
