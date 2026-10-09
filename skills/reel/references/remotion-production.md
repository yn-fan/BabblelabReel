# Remotion production contract

Load this reference before planning or changing a Remotion composition, not
for ordinary footage edits or native drafts. Apply [Reel's universal gates](../SKILL.md)
first; this reference specifies their Remotion files, implementation, and checks.
Run the selected-engine readiness check from Reel before building. Its local
prerequisite results are not evidence of successful generation or rendering.

The starter also treats timing as production data: scenes define the narrative
contract, shots define contiguous visual ranges, beats attach actions or spoken
phrases to exact times, and caption cues drive the playback layer. Read
[video-talkcraft-study.md](video-talkcraft-study.md) when
the user asks about TalkCraft or when extending Reel's timing, QA, or iteration
architecture. The study records transferable ideas and the noncommercial-license
boundary; never copy TalkCraft source or templates into Reel.

Read [video-shotcraft-study.md](video-shotcraft-study.md)
when a product demo needs real-page capture, shot-pattern selection, page-space
camera work, or stronger review evidence. ShotCraft is Apache-licensed, but Reel
still uses independently authored contracts and does not import its media,
reference-film expression, recipe library, or sample visual treatment.

Tim Kochjar's public demo is one optional treatment reference, not Reel's
foundation. Load [tim-kochjar-study.md](tim-kochjar-study.md)
only when the user explicitly requests that reference or independently asks for
the same observable treatment. The exact prompt, source, timing map, and
production decisions are not public, so motif matching alone must never be
described as reproducing his work.

## Output contract

For a new standalone Remotion video, create:

```text
OUTPUT_DIR/{reel-slug}/
  REEL.md
  narration.md            # narrated work: script with inline keyframes
  package.json
  package-lock.json       # after dependency installation
  tsconfig.json
  scripts/
  src/
    reel/story.json       # source, script, scene, and state contract
    reel/AudioTrack.tsx   # source-backed narration playback
    reel/CaptionTrack.tsx # phrase-timed open captions
  public/
  out/
    reel.mp4              # only when the user requests a render
    preview.png
```

Use a supplied target when the user asks to add Remotion to an existing
repository. Follow that repository's instructions and package boundaries. Never
add a root `package.json` or Remotion dependencies to BabblelabReel itself.

## Route the request

| Request | Action |
|---|---|
| New standalone product video | Materialize the neutral scaffold into `OUTPUT_DIR/{reel-slug}` and replace its placeholder story |
| Add video to an existing app/repo | Read [remotion-integration.md](remotion-integration.md) and preserve its package architecture |
| Improve an existing composition | Read its brief, full script, source contract, entry point, root, composition, timing model, and scripts; edit in place |
| Render an existing composition | Verify the composition ID, story coverage, dependency state, and output path before rendering |

## 1. Classify the video before choosing a treatment

Choose the archetype from the user's outcome. Do not force every story into a
prompt-to-result launch arc.

| Archetype | Story contract |
|---|---|
| Product launch video | Use the optimized launch preset: one promise, a source-backed task, credible proof, and a minimal close |
| Vision video | Use the optimized vision preset: present reality, human tension, future vignettes, principles, and invitation |
| Product task demo | Show one source-backed task from entry through resulting state |
| Narrated workflow or explainer | Preserve the supplied introduction, sequence, qualifications, and conclusion; narration controls duration |
| Promo reel | Establish a promise, demonstrate evidence, and use a CTA only when the brief needs one |
| Social short | Communicate one moment or change with minimal context |
| Footage montage / Vlog | Select source ranges for a coherent sequence; preserve meaningful speech and distinguish measured timing from visual interpretation |
| Reference treatment | Apply observable attributes after the story is locked; never infer hidden production choices |

Infer only behavior-safe defaults when information is absent:

- 16:9, 1920×1080, 30fps;
- duration derived from the script or demonstrated task;
- neutral treatment using supplied brand tokens;
- no narration unless requested;
- new video productions confirm a BGM direction, then try hosted AI with
  automatic mood-search library backup; respect silence and supplied soundtracks;
- editable source first, render only when requested.

Use 60fps when fast cursor motion, kinetic type, source footage, or an explicit
reference benefits from it. Do not select 60fps merely because a public reference
used it.

When the intent is a product launch or future-state vision and the user has not
provided conflicting production direction, load
[video-type-defaults.md](video-type-defaults.md) and apply
the matching optimized preset. Record `product-launch` or `vision-video` in
`story.json`; use `custom` for other archetypes. The preset establishes positive
story, shot, asset, motion, audio, and quality defaults. Record deliberate
overrides instead of quietly blending both presets or falling back to a generic
neutral slide treatment.

Capture product, audience, outcome, source assets, brand tokens, aspect ratio,
audio, captions, delivery, and evidence boundaries. Never invent customer
results, product capabilities, people, company data, endorsements, or proof
metrics.

## 2. Lock the story and product behavior

Write `REEL.md` and `src/reel/story.json` before implementation.
They are the production source of truth.

Choose media by narrative purpose during story lock, for every archetype,
including explainers and `custom`; do not wait for the user to request images.
Use source-backed UI for product actions, diagrams for relationships or
mechanisms, and prioritize illustration/footage for situations, emotion,
imagined futures, and visual metaphors. Respect explicit graphic-only direction;
do not impose an image quota or generate images for decoration.

Record each visual beat's medium, selection reason, and asset reference or
generation need in the `REEL.md` shot plan, keyed by shot/beat ID. Use suitable
supplied media first; when needed imagery is absent, invoke `image-generator`
after story lock and before implementing the affected shots. Illustrations may
be stylized, not only photorealistic; never present fictional scenes as evidence.
Follow section 6 for provider permissions and provenance. If required imagery
is blocked, report it and wait for suitable supplied media or an explicit
asset/provider fallback decision; do not silently substitute diagrams or UI.
The starter's text/CSS scenes are placeholders, not a media recommendation.

For icons, reuse project assets and the established product icon family.
For Microsoft UI, inspect host-exposed Fluent MCP tools and use their verified
icon search/retrieval capabilities; do not assume SVG access from the server name.
If unavailable or unsupported, fetch individual official Fluent System Icons
SVGs on demand, not the full library. Verify icon name, size and Regular/Filled
variant; never guess paths or hand-draw replacements. Other products retain
their own icon family. If assets cannot be obtained, report the limitation.

`REEL.md` must contain:

```markdown
# [Video title]

## Brief
- Archetype:
- Preset: product-launch / vision-video / custom
- Audience:
- Outcome:
- Format:
- Duration basis:
- Treatment:

## Story lock
- Script source:
- Required opening:
- Required sequence:
- Required conclusion:
- Approved omissions:

## Source and task contract
| Source ID | Type | Reference | What it proves |
|---|---|---|---|

## Capture manifest
| Capture ID | Source ID | Route/state | Full frame | Layout | Cutouts | Viewport/DPR | Privacy |
|---|---|---|---|---|---|---|---|

## Timeline
| Time | Scene ID | Purpose | Visual change | Product state | Copy/audio | Source |
|---|---|---|---|---|---|---|

## Shot and motion plan
| Shot ID | Scene ID | Time | Dominant subject | Camera | Content action | Hold | Exit |
|---|---|---|---|---|---|---|---|

### Media choices
| Shot / beat ID | Medium | Narrative reason | Asset reference / generation need |
|---|---|---|---|

## Acceptance criteria
- [Observable checks]

## Evidence and placeholders
- [Source or explicit placeholder]
```

For narrated work, create `narration.md` beside `REEL.md` as the user-facing
script for discussion and revision during story lock. Draft the actual script
there first, then insert keyframes as they become available; keep it synchronized
with the approved narration in `story.json`, including subsequent user edits.

- Include only section headings, actual spoken script, and embedded keyframe
  images. No synopsis, requirements, timestamps, scene descriptions, production
  notes, standalone image labels/captions, HTML comments, or status text.
  Keep those details in `REEL.md` or the conversation.
- Insert each keyframe at the point its visual first appears in the narration,
  immediately before the corresponding words. A new scene's opening frame goes
  after its section heading and before its script. For a mid-paragraph or
  mid-sentence visual change, split the text at that exact phrase and insert the
  image there without rewriting, omitting, or reordering the spoken words.
  Do not collect all frames at the beginning or end of a section.
- Use Markdown images with concise alt text and project-relative paths to
  actual keyframe files. Do not insert broken links or descriptive placeholders;
  report missing frames outside the document. Replace provisional storyboard
  frames with matching rendered frames when available.
- Do not invent narration for silent videos. This document complements, rather
  than replaces, the technical production contract in `REEL.md`.

For narration production:

1. preserve the full approved script in scene order;
2. give every sentence or deliberate phrase a stable scene ID;
3. record any omission or rewrite under `Approved omissions`;
4. synthesize audio only after the script is locked;
5. measure the actual WAVs and leave explicit headroom before scene boundaries.
6. record the public-relative WAV path, measured duration, volume, and provenance
   reference in `story.json.audio.narration`, plus `qualityGate:
   enhanced-kokoro` and an empty `approvalNote`;
7. map phrase-level captions to absolute `captionCues` and emphasized spoken
   substrings to `speech` beats.

Do not silently shorten, reorder, or replace the introduction because a visual
treatment suggests a different opening.

For every Remotion production, make the plan executable in `story.json`:

- `shots` are absolute, contiguous ranges that cover the full composition and
  remain inside their referenced scene;
- each shot has one dominant subject, camera behavior, content action, readable
  hold, and boundary policy. The neutral starter supports honest hard cuts and
  a final `end`; implement custom choreography before extending the schema with
  match, push, mask, or dissolve transitions;
- use one of the starter's executable camera modes: `static`, `push-in`,
  `pull-out`, `pan-left`, `pan-right`, or `controlled-crop`;
- every shot contains at least one visual or speech `beat`;
- speech beats use a verbatim `anchorText` from the locked scene narration;
- caption cues are non-overlapping, phrase-sized ranges inside their scene.
- `captures` records every real-product full frame, page-space layout, and
  optional cutout set. Each entry includes a source reference, route/state,
  viewport and device scale factor, and `synthetic`, `sanitized`, or explicitly
  `approved-production` privacy classification. Shots using captured UI set
  `captureRef`; do not commit customer data or an unproven production state.

Keep scene time, absolute composition time, and shot-local animation time
distinct. Convert absolute shot and beat values to local frame offsets only at
the component boundary.

For product demonstrations, define each action before animating:

- entry point and user goal;
- source-backed control or affordance;
- state before action;
- visible action and acknowledgement;
- resulting state;
- undo, error, empty, loading, permission, or responsive state when relevant;
- source reference proving the behavior.

Mock behavior is allowed only for explicit concept work. Label it in `REEL.md`
and `story.json`; do not present it as shipped product behavior.

A product-task plan or completion report must show the state ledger with source
references. Statements such as `make the flow truthful`, `show loading`, or
`use the real UI` are intentions, not proof. For repairs, inspect the real
capture, component, or specification and name the exact affordance and states
that replace the invented sequence.

## 3. Choose a treatment after the locks

A treatment controls palette, typography, framing, asset mix, camera behavior,
transition character, and sound rhythm. It must not change required story beats
or product behavior.

Use supplied brand and product evidence first. When no treatment is requested,
choose a restrained neutral system that supports the archetype and source
material. Do not default to luminous ribbons, centered prompt boxes, cursors,
rounded product windows, isolated proof metrics, dark cinematic fields, or any
other previously successful reel.

For an explicit creator reference:

1. separate verified facts, observable attributes, and unknown decisions;
2. add a `Treatment map` to `REEL.md` with rows for shot scale, edit pacing,
   camera continuity, composition, typography, source-asset fidelity,
   transitions, and audio rhythm;
3. state which attributes can transfer to this story and which cannot;
4. storyboard original choreography using the user's product and evidence;
5. compare the preview against that attribute map before claiming similarity.

Each treatment-map row records `observed or unknown`, `transfer decision`,
`implementation`, and `verification frame or playback check`. A plan that only
lists colors, ribbons, rounded windows, prompt boxes, cursors, or generic
`cinematic` motion fails this gate. Polish comes from the full temporal and asset
system, not recognizable motifs.

For any response that proposes or promises creator-reference similarity, show
the eight-row treatment map first. Write it in `REEL.md` during production or in
the response when the user requests planning only. Do not compress it into a
prose list of recognizable motifs.

For the Tim Kochjar reference, copy the `Reference evidence` cells from the
canonical map in `tim-kochjar-study.md`. Do not upgrade an `unknown` production
decision to an observation. Add the user's transfer decision, planned
implementation, and verification check as separate columns.

The standalone scaffold includes the dormant template
`src/reel/treatments/tim-kochjar-reference.json`. Activate it only by setting
`story.json` treatment to `tim-kochjar-reference`, then complete all eight rows.
`npm run validate` rejects an active map with unresolved fields.

Do not imply affiliation, reuse reference branding or media, trace shots, or say
the original prompt was used.

## 4. Materialize and install the neutral scaffold

Scaffold, package installation, and composition commands apply only to Remotion.
Follow Reel's scoped installation-consent gate; run no installation for help or
planning-only requests.

Resolve the final destination through `OUTPUT_DIR`, then run:

```bash
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/scaffold_reel.py" "OUTPUT_DIR/{reel-slug}" --name "{reel-slug}"
```

The destination must be absent or empty. The scaffold is intentionally plain and
contains `REPLACE_ME` markers. Replace the story and source contract before
production.

From the generated project root:

1. with installation consent, run `npm install` when dependencies are not installed;
2. keep every `remotion` and `@remotion/*` package on the same exact version;
3. run `npm run validate` to reject unresolved story/source placeholders;
4. run `npm run check`, `npm run compositions`, and `npm run still`.

Use another package manager only when the target repository already establishes
it. Dependency installation stays inside the generated or affected workspace.

## 5. Build one deterministic timeline

Use one composition with `Sequence` segments. Keep story/timing data separate
from presentation components.

Drive composition structure from `story.json.shots` and `story.json.beats`
rather than burying editorial timing in component constants. This does not mean
every frame must move: dense product UI should still settle to exact geometry,
and clean cuts remain valid when continuity does not require a transition.

For `product-launch` and `vision-video`, plan shots before implementation using
the selected preset's cadence and failure conditions. A scene may contain
multiple shots; do not map a long narration paragraph to one fixed composition.
Create the preset's three style frames and motion test before building the full
timeline. If those samples look like slides, a dashboard, or unrelated visual
genres, revise the treatment before scaling the problem to the complete video.

- Derive visual changes from `useCurrentFrame()`, `interpolate()`, or `spring()`.
- Avoid CSS animation, CSS transition, timers, nondeterministic randomness, and
  runtime network state.
- Clamp interpolation at scene boundaries.
- Use Remotion media components and `staticFile()` for local assets.
- Give every scene a meaningful state, focus, crop, object, or evidence change.
  Ambient drift alone is not story progression.
- Compose around one dominant subject. Show product UI at a readable crop rather
  than shrinking a whole application beside explanatory chrome.
- Keep titles transient and captions as open one- or two-line lower thirds.
- Separate stable content, focused action, ambient, and transition layers.
- Hard-settle dense UI parent geometry before readable holds; animate the
  relevant child state instead of floating or scaling the entire surface.
- Choose transitions by narrative relationship. Keep most cuts clean and reserve
  full-frame transitions for genuine chapter changes.
- Hold completed states long enough to understand at normal playback speed.

Read [motion-patterns.md](motion-patterns.md) when the video
needs nontrivial choreography. Its recipes are options, not a quota or default
visual language.
For trimmed footage, caption integration, or overlapping transitions, consult
the relevant official Remotion skills through
[remotion-integration.md](remotion-integration.md).
Keep the project's pinned versions and account for overlap in duration.

## 6. Use assets and audio responsibly

**AI BGM:** for new video production or a requested soundtrack addition, follow
[ai-bgm.md](ai-bgm.md) for direction confirmation,
generation, automatic mood-search library backup, and user audition gates. Use its automatic
path by default so users need no local model installation. Planning-only tasks
do not generate audio. Respect explicit silence and supplied soundtracks;
repairs preserve existing audio unless soundtrack changes were requested. Derive
the music direction from the locked story, emotional progression, shot pacing,
and narration density; obtain the direction decision before generating, register
its provenance in `audio.music`, and preview fades and narration ducking.
Finalize only after listening acceptance or explicitly delegated audition.
Keep the story intact. Send only abstract musical direction to the public
service, never product identifiers, scripts, screenshots, or private details.
On hosted failure, select library music in the approved direction without
another switch-confirmation question, and disclose its actual source/license.
Explicit AI-only/local-only requests remain strict. If both paths fail, report
the blocker rather than using paid calls or delivering silence. Local setup remains an explicit
alternative requiring separate dependency/model-download permission.
For provider selection or licensing questions, consult
[ai-bgm-research.md](ai-bgm-research.md).

- Prefer supplied screenshots, recordings, code, and design exports when
  accuracy matters.
- For explicitly authorized linked footage selected by the shot plan, follow
  [video-acquisition.md](video-acquisition.md); verify its receipt and reuse
  rights, register source/provenance, then copy only chosen files into `public/`.
  Keep source-video credits distinct from the music credit requirement.
- For browser-captured product UI, save coordinated full-frame images, layout
  JSON, and optional element cutouts under `public/captures/`, then register
  them in `story.json.captures`. Capture only seeded synthetic, sanitized, or
  explicitly approved production data; wait for fonts and stable UI state.
- Crop or direct source UI; do not redraw it inaccurately when a source exists.
- Use `image-generator` for original people, places, objects, or cinematic
  establishing imagery beyond product UI. Record prompt, provider/model, source
  artifact, intended shot, and placeholder status.
- Keep product UI source-based. Generated UI is only for labeled concept work.
- Keep licensed media, fonts, logos, and footage under `public/`.

For `vision-video`, complete the selected preset's asset gate before full
implementation. When the story depends on human change, approved supplied
footage or generated raster scenes must carry those moments; avatar glyphs,
CSS silhouettes, diagrams, and kinetic type do not count as human-context
imagery. If Image Generator cannot complete with the selected provider, stop
that asset path and surface the blocker. Do not silently finish the vision film
as vector-only motion graphics, switch image providers without approval, or
mark the style-frame gate complete. Continue only with suitable supplied assets
or an explicit user decision about the asset/provider fallback.
- Never download or reuse media from a reference video.

When narration is requested and the user has not selected a mode, request
Audio Generator's **enhanced mode**. Enhanced mode is Reel's quality default
because it uses Kokoro across supported Windows and macOS hosts and avoids the
more mechanical platform voices used by basic synthesis. Audio Generator still
owns platform checks, dependencies, compatible backend/model selection,
narrator defaults, synthesis, and provenance; Reel selects the enhanced quality
tier, not a hard-coded voice or runtime.

Load and run `audio-generator` as a child capability. Pass `--mode enhanced`
through its supported entry point, and do not silently retry with basic mode
when enhanced preflight or synthesis fails. Report the blocker and follow Audio
Generator's dependency-permission rules instead. Respect an explicit user
request for basic mode, another supported mode, or a particular compatible
voice.

Before accepting narration, require the successful sidecar to report
`mode: enhanced` and a Kokoro engine/model unless the user explicitly chose
otherwise. Copy successful WAVs and sidecars into `public/audio/`, record them
in `REEL.md` and `story.json.audio.narration`, measure their duration, validate
that the JSON provenance reports enhanced mode and Kokoro, and add phrase-level
caption cues. Use `qualityGate: user-approved-alternative` plus the user's
decision in `approvalNote` only when they explicitly chose another supported
mode. The starter renders the approved narration through
`AudioTrack.tsx` and captions through `CaptionTrack.tsx`; do not leave one
caption visible for an entire narrated scene. Reel must not implement ad hoc
project-local TTS or use an unlabeled existing voice track whose provenance does
not match the production brief.

## 7. Run quality gates in order

Do not spend time polishing a composition that fails an earlier gate.

### Gate A — story integrity

- Every required script phrase and task step maps to a scene.
- Remotion shots cover the complete timeline without gaps or overlaps, each shot contains
  a beat, and speech beats point to verbatim narration anchors.
- The opening, sequence, conclusion, and approved omissions match `REEL.md`.
- For narrated work, `narration.md` contains only headings, spoken script, and
  keyframes; its script matches the approved narration, image links resolve,
  and each frame precedes the words at its actual visual entry point.
- Audio provenance and measured duration are recorded; captions are timed to
  phrases, remain inside their scene, and finish within the narration track.
- Requested BGM has valid AI-generation or licensed-library provenance, covers its playback
  range, and matches the approved emotional direction. Listen to the mixed
  opening, densest narration, transitions, and ending for masking, pumping,
  clipping, unintended vocals, and abrupt cuts before accepting the soundtrack.

### Gate B — product and usability correctness

- Every demonstrated control, action, acknowledgement, and resulting state
  matches the recorded source.
- The state ledger names the exact source reference and visible affordance for
  each action; a prose promise of accuracy is insufficient.
- Relevant loading, empty, error, permission, undo, responsive, and overflow
  behavior is represented or explicitly out of scope.
- Captions and overlays do not cover the demonstrated action.
- Product text, affordances, and feedback remain readable at playback size.

### Gate C — temporal and technical stability

- Render the last outgoing, cut, and first incoming frame at every boundary.
- Compare two frames 10–15 frames apart from every dense readable hold; stable
  parent geometry must not drift.
- Inspect the opening animation as a sequence, not one still.
- Check for clipping, overlap, z-order errors, blank frames, missing assets,
  long spring tails, nested transforms, and repetitive transition cadence.
- For Remotion, run `npm run qa:plan` and render the listed opening burst, shot-boundary
  triplets, readable-hold pairs, caption samples, and final frame.

### Gate D — visual treatment

- For every archetype, compare rendered shots with the media choices in
  `REEL.md`: required imagery must appear in its assigned shots, not just exist
  on disk. Reject diagram/UI substitutes chosen merely for implementation ease.
- Thumbnail frames have a clear focal subject.
- Typography, palette, camera, transitions, and asset treatment form one system.
- A six-frame contact sheet shows temporal progression rather than repeated
  slides or decorative ambient motion.
- For an optimized preset, the early/middle/late contact sheet, shot durations,
  style frames, and motion test satisfy the selected preset and none of its
  failure conditions remain true. Do not mark this gate complete from source
  inspection or a single still.
- If a creator reference was explicit, compare against the documented attribute
  map across all eight dimensions. Motif similarity alone fails this gate.
- Describe a creator-informed result as reference-derived, never identical.

Use Remotion Studio for Remotion playback inspection:

```bash
npm run studio -- --no-open
```

When a browser canvas is available, open the Studio URL there.

## 8. Render only when requested

Use the target script or:

```bash
npx remotion render src/index.ts ProductReel out/reel.mp4 --codec=h264
```

Inspect the final file's dimensions, frame rate, duration, video/audio streams,
head and tail, assets, captions, dense holds, and opening motion. Do not report a
rendered-video task complete from TypeScript or still checks alone.

## Completion report

State:

- source project path;
- selected engine;
- archetype and treatment;
- composition ID, format, duration, and frame rate;
- rendered path when applicable;
- real, generated, conceptual, and placeholder assets or behaviors;
- any omitted source, audio, claim, or unresolved validation issue.

For a Tim Kochjar-informed result, say `reference-derived treatment`. Never claim
his original prompt or production system was recovered.
