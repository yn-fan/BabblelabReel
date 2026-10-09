# Story-first Remotion production prompt

This prompt is for the Remotion branch. For local footage/Vlog editing or native
Jianying delivery, delegate the corresponding `footage-editing.md` or
`jianying-handoff.md` workflow instead; keep its timeline and export boundary.

Use this framework when delegating implementation to a coding agent. Replace
every bracketed field. Do not add a creator treatment, marketing arc, palette,
proof metric, prompt box, cursor, or CTA unless the locked brief calls for it.

```text
Create an editable, deterministic Remotion product video.

Production contract
- Video archetype: [PRODUCT LAUNCH / VISION VIDEO / PRODUCT TASK DEMO / NARRATED WORKFLOW / PROMO / SOCIAL SHORT]
- Optimized preset: [product-launch / vision-video / custom]
- Audience and viewing context: [AUDIENCE]
- Outcome: [WHAT THE VIEWER SHOULD UNDERSTAND OR DO]
- Format: [DIMENSIONS, ASPECT RATIO, FPS]
- Duration basis: [LOCKED SCRIPT / SOURCE TASK / EXPLICIT LIMIT]
- Treatment: [NEUTRAL / BRAND-SPECIFIC / NAMED REFERENCE ATTRIBUTE MAP]
- Composition ID: [ID]
- Delivery: editable source first; render only when requested

Story lock
- Script source: [FILE, USER TEXT, OR NONE]
- Required opening: [VERBATIM OR INTENT]
- Required sequence: [ORDERED SCENE IDS]
- Required conclusion: [VERBATIM OR INTENT]
- Approved omissions or rewrites: [EXPLICIT LIST OR NONE]

Do not omit, shorten, or reorder locked narration to fit a visual recipe. Map
every sentence or deliberate phrase to a scene ID. Encode contiguous absolute
shot ranges, visual or speech beats, phrase-level caption cues, and the measured
narration track in `story.json`; do not leave editorial timing only in prose or
component constants.

For narrated work, follow remotion-production.md's `narration.md` contract: use it for script
discussion with only section headings, actual spoken script, and inline
keyframes. Place each image immediately before the words at its visual entry
point, including mid-sentence changes. Keep technical notes in `REEL.md`.

Source and product-task contract
- Source assets: [FILES, CAPTURES, CODE, SPECS]
- User goal and entry point: [GOAL / ENTRY]
- Actions and state transitions: [BEFORE -> ACTION -> ACKNOWLEDGEMENT -> RESULT]
- Edge states in scope: [LOADING / EMPTY / ERROR / PERMISSION / UNDO / RESPONSIVE]
- Mock boundary: [EXPLICIT CONCEPTUAL ELEMENTS OR NONE]
- Evidence and claims: [SOURCE REFERENCES]

Do not invent product behavior, people, customer data, capabilities, metrics, or
endorsements. Label conceptual behavior in the brief and story source.

Treatment
- Brand tokens: [PALETTE, TYPE, LOGO, SPACING]
- Shot scale and framing: [ATTRIBUTE MAP]
- Camera behavior: [ATTRIBUTE MAP]
- Transition character: [ATTRIBUTE MAP]
- Asset treatment: [ATTRIBUTE MAP]
- Sound rhythm: [ATTRIBUTE MAP]

Treatment decisions may shape presentation but may not change the story or
product-task contract. If a creator reference is requested, distinguish verified
facts, observable attributes, and unknown production decisions. Create original
choreography and never claim an exact clone.

For product-launch or vision-video, load the matching contract in
references/video-type-defaults.md. Apply its duration, story allocation, shot
cadence, asset mix, motion/camera grammar, audio posture, style-frame test, and
failure conditions unless this brief records an explicit override. Do not blend
the two presets into a generic treatment.

For a people-centered vision-video, verify the preset's minimum human-context
scene count before full implementation. Only approved raster imagery or footage
with a recognizable person, environment, or human action satisfies the asset
floor. Do not substitute CSS silhouettes, avatar glyphs, abstract diagrams, or
kinetic type after an image provider fails. Surface the blocked asset and wait
for suitable supplied media or an explicit provider/asset fallback decision.

For a creator reference, write a treatment map before code:
| Dimension | Reference evidence | Transfer decision | Implementation | Verification |
| Shot scale | | | | |
| Edit pacing | | | | |
| Camera continuity | | | | |
| Composition | | | | |
| Typography | | | | |
| Source-asset fidelity | | | | |
| Transitions | | | | |
| Audio rhythm | | | | |

A motif list is not a treatment map. Colors, ribbons, rounded windows, prompt
boxes, and cursors cannot by themselves support a similarity claim.
When a reference study provides a canonical evidence map, copy its evidence
boundaries and preserve every `unknown`; do not invent hidden production
decisions to make the treatment sound complete.

Motion
- Drive every visual change from Remotion frames.
- Use Sequence for scene-local timing.
- Keep scene time, absolute shot/beat time, and component-local time distinct.
- Give every shot a dominant subject, camera behavior, content action, readable
  hold, boundary policy, and at least one beat. The neutral starter supports
  `cut` and final `end`; extend it only after implementing the custom transition.
- Use an executable starter camera mode: `static`, `push-in`, `pull-out`,
  `pan-left`, `pan-right`, or `controlled-crop`.
- Anchor speech beats to verbatim substrings of the locked scene narration.
- Break long scenes into phrase-level shots; do not leave one composition fixed
  under a paragraph of narration.
- Give each scene a meaningful state, focus, crop, object, or evidence change.
- Plan entrance, primary action, readable hold, and continuity-preserving exit.
- Separate stable content, focused action, ambient, and transition layers.
- Hard-settle dense UI parent geometry before readable holds.
- Keep most cuts clean; choose other transitions only for a narrative relationship.
- Do not use ambient drift as a substitute for story progression.

Composition
- Make one subject dominant in each shot.
- Show product UI at a readable crop.
- Keep titles transient and captions as open one- or two-line lower thirds.
- Avoid persistent presentation chrome unless it belongs to the product.
- Preserve caption safe areas and keep overlays away from demonstrated actions.

Assets and audio
- Use supplied captures or code for product UI.
- Use image-generator only for original non-UI imagery when needed.
- Use audio-generator enhanced mode for requested narration unless the brief
  explicitly selects another supported mode. Require successful Kokoro
  provenance, do not silently fall back to basic synthesis, and do not add
  project-local TTS.
- Measure generated audio before finalizing scene duration.
- Record the public-relative audio path, measured duration, volume, and
  provenance reference in `story.json.audio.narration`. Set `qualityGate` to
  `enhanced-kokoro`; use `user-approved-alternative` with an `approvalNote` only
  after an explicit user choice.
- Render narration through the shared audio track and render non-overlapping
  phrase cues through the shared open-caption layer.
- Record source and generation provenance.
- For new video production, follow references/ai-bgm.md to recommend BGM by
  default: derive the direction card from emotion, pace, and narration density.
  Return the card to the user-facing parent for confirmation; generate only
  with the actual approval or explicit delegation bound to the current brief.
  Use the built-in auto mode: try hosted AI once, then automatically select
  matching CC0/CC BY music on failure without asking to switch; preserve the
  automatic end credit and license file for CC BY. Respect
  explicit AI-only/local-only requests. Attach measured
  audio/provenance as draft `audio.music`. Preview fades and speech
  ducking, then obtain listening acceptance before final delivery. Mix-only
  feedback reuses the audio; direction changes return to confirmation. Respect
  requested silence or supplied music; preserve audio during unrelated repairs.
  Send no private product content. Disclose fallback with library source and
  license, never as AI generation. If both paths fail, report the blocker instead
  of omitting BGM, sending the user to generate it manually, or making paid calls.
  Planning-only requests do not start generation.

Implementation
- Keep story and timing in src/reel/story.json.
- Keep scenes, shots, beats, audio, and caption cues machine-readable and
  validator-enforced.
- Keep presentation components separate from story data.
- Use staticFile() and Remotion media components for local assets.
- Keep all Remotion packages on one exact version.
- Add dependencies only inside the affected workspace.

Quality gates, in order
1. Story integrity: required opening, sequence, conclusion, and narration coverage.
2. Product correctness: source-backed controls, actions, acknowledgements, results,
   and relevant edge states. Include the state ledger and exact source references;
   a prose promise of accuracy does not pass.
3. Temporal stability: boundary triplets, paired dense-hold frames, opening-motion
   playback, clipping, overlap, blank frames, and transition cadence.
4. Visual treatment: focal hierarchy, system coherence, temporal progression,
   preset asset floor, failure-condition, or reference-attribute comparison when
   applicable.

Run npm run validate, npm run check, npm run compositions, npm run qa:plan, and
npm run still. Render the frames listed in `out/review-plan.json` for a
consistent opening, boundary, readable-hold, caption, and final-frame review.
When an MP4 is requested, render and inspect the final media rather than treating
static checks as completion.
```
