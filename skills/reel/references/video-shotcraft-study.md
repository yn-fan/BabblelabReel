# Video ShotCraft reference study

Research date: 2026-09-04

Source revision:
[`Vincentwei1021/video-shotcraft@6c116cb`](https://github.com/Vincentwei1021/video-shotcraft/tree/6c116cbd24eeb43c99d396696b509f8d88e58789)

## Boundary

Video ShotCraft is available under
[Apache License 2.0](https://github.com/Vincentwei1021/video-shotcraft/blob/6c116cbd24eeb43c99d396696b509f8d88e58789/LICENSE).
Its repository architecture can inform Reel, but bundled screenshots, third-party
reference films, audio, branding, and sample treatments retain their own rights
and provenance constraints. Reel independently implements the general production
ideas below instead of importing its recipe library, media, or Ink Press style.

## Transferable architecture

ShotCraft's strongest contribution is a product-capture pipeline rather than a
universal visual look. Its capture template coordinates full-page screenshots,
element cutouts, and layout bounds in one page-space coordinate system. Its
production pipeline also treats styleframes, feature-to-shot mapping, holds, and
validation frames as explicit evidence before full rendering.

Reel adopts the useful principles through its own contracts:

| Idea | Reel implementation |
|---|---|
| Real-page capture provenance | `story.json.captures` records source, route/state, full frame, layout, cutouts, viewport/DPR, and privacy class |
| Capture-to-shot traceability | A shot may use `captureRef`; validation rejects missing manifests or files |
| Hold-first timing | Every shot has a positive rendered hold and deterministic settle/compare frames |
| Evidence-oriented QA | `qa:plan` emits entry, primary visual beat, settle, and comparison frames for every shot |
| Resolution-safe camera behavior | Camera translation derives from composition dimensions rather than fixed 1080p offsets |

## Deferred ideas

A typed recipe registry could eventually help select product-demo shot patterns
by intent, asset need, energy, and known failure mode. Do not add a large recipe
library until repeated Reel productions reveal stable patterns worth maintaining.

A page-space camera can improve close-ups of real product captures, but it needs
resolution-independent geometry, safe overlays, and tests across aspect ratios.
Do not copy ShotCraft's fixed 1920x1080 `PageCam` implementation into the neutral
starter.

Music-grid timing and alternate audio mixes are useful when a brief calls for
beat-driven editing. They should remain optional because narrated workflow and
vision films may not use music.

## Patterns Reel intentionally rejects

Do not transfer the Ink Press palette, ten-shot structure, fixed timing,
hard-coded canvas coordinates, camera shake, tech-house sound vocabulary,
unverified audio files, demo screenshots, or absolute SFX frame numbers.

Do not treat first-frame smoke renders as sufficient QA. Reel keeps boundary,
action, hold, caption, and final-frame evidence. Do not make JianYing export a
core dependency; its platform/version constraints and draft metadata make it an
optional future adapter at most.
