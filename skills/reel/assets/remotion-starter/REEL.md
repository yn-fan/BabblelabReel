# REPLACE_ME video title

## Brief

- Archetype: narrated workflow
- Preset: custom; use `product-launch` or `vision-video` when the intent matches
- Audience: REPLACE_ME
- Outcome: REPLACE_ME
- Format: 1920×1080, 30fps
- Duration basis: locked script or source-backed task
- Treatment: neutral; replace with supplied brand direction

## Story lock

- Script source: REPLACE_ME supplied script or `none`
- Required opening: REPLACE_ME
- Required sequence: opening → context → task → outcome → conclusion
- Required conclusion: REPLACE_ME
- Approved omissions: none

Do not animate production content until these fields and
`src/reel/story.json` agree.

## Source and task contract

| Source ID | Type | Reference | What it proves |
|---|---|---|---|
| source-1 | concept placeholder | REPLACE_ME | REPLACE_ME |

For product tasks, record the entry state, action, acknowledgement, resulting
state, and relevant error, empty, loading, permission, undo, overflow, and
responsive behavior.

## Capture manifest

| Capture ID | Source ID | Route/state | Full frame | Layout | Cutouts | Viewport/DPR | Privacy |
|---|---|---|---|---|---|---|---|

Keep this table aligned with `story.json.captures`. Product captures belong
under `public/captures/` and must record the source they prove, route and visible
state, full-frame image, page-space layout JSON, optional element cutouts,
capture viewport and device scale factor, and privacy class. Use only synthetic,
sanitized, or explicitly approved production data. Format route/state as
`/route :: visible state`, cutouts as comma-separated paths or `none`, and
viewport/DPR as `1920x1080@2x`.

## Timeline

| Time | Scene ID | Purpose | Visual change | Product state | Copy/audio | Source |
|---|---|---|---|---|---|---|
| 0–4s | opening | Preserve the introduction | Title is revealed | Subject introduced | REPLACE_ME | source-1 |
| 4–11s | context | Establish context | Focus moves between facts | Context understood | REPLACE_ME | source-1 |
| 11–23s | task | Demonstrate one action | Before → acknowledgement → result | REPLACE_ME | REPLACE_ME | source-1 |
| 23–30s | outcome | Explain the result | Prior state is replaced | Result understood | REPLACE_ME | source-1 |
| 30–35s | conclusion | Preserve the conclusion | Final statement holds | Story complete | REPLACE_ME | source-1 |

## Shot and motion plan

| Shot ID | Scene ID | Time | Dominant subject | Camera | Content action | Hold | Exit |
|---|---|---|---|---|---|---|---|
| opening-1 | opening | 0–4s | REPLACE_ME opening subject | push-in | Reveal the opening phrase | 1s | cut |
| context-1 | context | 4–11s | REPLACE_ME context subject | pan-left | Shift focus between source-backed facts | 1s | cut |
| task-1 | task | 11–23s | REPLACE_ME product action | controlled-crop | Show before, acknowledgement, and result | 2s | cut |
| outcome-1 | outcome | 23–30s | REPLACE_ME resulting state | pull-out | Resolve the demonstrated outcome | 2s | cut |
| conclusion-1 | conclusion | 30–35s | REPLACE_ME conclusion | static | Hold the conclusion | 2s | end |

The table above must match `story.json.shots`. Shot ranges are absolute,
contiguous, and together cover the full composition. The neutral starter
supports `cut` and final `end`; add another boundary value only after its
transition is implemented and validated in source. Camera must be `static`,
`push-in`, `pull-out`, `pan-left`, `pan-right`, or `controlled-crop`; these
values drive the starter's shot-level camera wrapper.

## Speech and beat timing

| Beat ID | Shot ID | Time | Kind | Spoken anchor | Visual purpose |
|---|---|---|---|---|---|
| opening-reveal | opening-1 | 0.5s | action | none | Reveal the opening phrase |
| context-first-fact | context-1 | 4.5s | state | none | Focus the first source-backed fact |
| context-second-fact | context-1 | 8s | state | none | Focus the second source-backed fact |
| task-before | task-1 | 11.5s | state | none | Show the source-backed state before action |
| task-action | task-1 | 16s | action | none | Show the product acknowledgement |
| task-result | task-1 | 20s | state | none | Show the source-backed resulting state |
| outcome-resolve | outcome-1 | 25s | state | none | Resolve the resulting state |
| conclusion-hold | conclusion-1 | 31s | state | none | Begin the final readable hold |

For narration, record the approved WAV, measured duration, provenance,
`qualityGate`, and `approvalNote` in `story.json.audio.narration`. Use
`enhanced-kokoro` by default; use `user-approved-alternative` only with the
user's decision in `approvalNote`. Add phrase-level `captionCues` and `speech`
beats; each speech beat's `anchorText` must be a verbatim substring of that
scene's locked narration.

## Optional background music

Existing `audio.narration` is unchanged and starts at composition frame zero.
`audio.music` may be omitted or `null` (no music). Otherwise all fields below
are required; music is one composition-level track, not restarted at shot cuts:

The scaffold itself is silent. During new video production, follow Reel's
`references/ai-bgm.md` to recommend, confirm, generate, and audition the cloud
soundtrack. Hosted failure automatically selects matching CC0/CC BY music,
without another switch-confirmation question. Explicit AI-only/local-only
requests remain strict. Acquisition attaches a draft track, not an accepted final mix.
Record an explicit silence/supplied-music decision or unresolved provider
blocker instead of treating a missing requested soundtrack as completed.

### Music decisions

- Direction: pending. Record the emotional arc with scene/time references,
  sound, pace, narration relationship, and rationale in `music-brief.json`.
- Direction decision: pending. Record approval or explicit delegation and its
  actual user-response reference; keep its current helper fingerprint in the brief.
- Audition: pending. Record the generated track path/hash, playable mixed
  preview path, mix settings, user decision, and response reference here.
  Explicitly waived audition is delegated, not listened/approved.
- Source: pending. Record AI generation or licensed-library selection honestly,
  including the original source/license and any automatic fallback reason.
- Revisions: record mix-only changes without generating again; a new direction
  requires an updated direction decision. Keep the active track until its
  replacement is accepted. Final delivery waits for acceptance or delegation.

```json
{
  "src": "audio/music.flac",
  "durationSeconds": 40,
  "provenanceRef": "audio/music.flac.json",
  "startSeconds": 0,
  "endSeconds": 35,
  "sourceStartSeconds": 2,
  "volume": 0.18,
  "duckVolume": 0.06,
  "fadeInSeconds": 1,
  "fadeOutSeconds": 2,
  "duckAttackSeconds": 0.25,
  "duckReleaseSeconds": 0.5
}
```

- `src` is a local PCM/IEEE-float RIFF/WAVE, native FLAC or library MP3 under `public/audio/`;
  `provenanceRef` is a local JSON sidecar in the same tree. Paths use
  slash-separated ASCII letters, digits, `_`, `-`, and `.`; traversal,
  absolute/remote paths, URL encoding, and symlink escapes are rejected.
- `durationSeconds` is the **measured full source audio**, not the selected cut.
  Both declared durations must match within one microsecond. WAV uses its
  byte rate and data size; FLAC uses STREAMINFO's sample rate and sample count;
  MP3 uses validated MPEG audio frames and sample counts.
  Decoding and listening remain required; metadata is not an audio-quality test.
- `startSeconds`/`endSeconds` are absolute composition times, bounded by the
  composition, with an exclusive end. Start, end, and source trim use
  `Math.round(seconds * fps)`. The cut must occupy at least one frame.
- `sourceStartSeconds` is a nonnegative source trim. The source must cover
  trim plus the entire cut in both seconds and rounded frames. There is no
  looping, stretching, or automatic padding.
- All numeric fields must be finite numbers. `volume` is `0..1`;
  `duckVolume` is `0..volume`. Fade lengths are zero (disabled) or at least
  one frame, and their sum must not exceed the cut length. Attack/release
  must each be at least one frame and no longer than the composition.
- Gain uses deterministic smoothstep ramps at absolute composition frames.
  Enabled fades reach zero at the first/last music frames. When narration
  exists, caption intervals drive anticipatory duck attack and post-phrase
  release; overlapping ramps take their minimum to avoid phrase-gap jumps.
  The duck target remains the configured `duckVolume`. When music exists,
  narration gain is `narration.volume * (1 - music.volume)` throughout the
  narration, reserving stable headroom without jumps at music boundaries.
  Thus the two track gains together never exceed `1`, even outside duck
  windows. For example, narration `1` with music `0.18` becomes `0.82`;
  music remains audible at its configured duck gain `0.06` under speech.
  Absent/null music leaves narration gain unchanged. Without narration,
  captions do not duck music. Listen to the final mix: this envelope is not
  a loudness normalizer or a substitute for accurately timed captions.

The provider-generated sidecar has this required provenance schema:

```json
{
  "schemaVersion": 1,
  "success": true,
  "kind": "ai-generated-music",
  "provider": "huggingface",
  "space": "ACE-Step/Ace-Step-v1.5",
  "model": "acestep-v15-turbo",
  "promptSha256": "<64 lowercase hex characters>",
  "outputSha256": "<SHA-256 of the exact audio bytes, 64 lowercase hex characters>",
  "durationSeconds": 40,
  "instrumental": true,
  "seed": 42,
  "licenseNote": "<nonempty license and usage note>"
}
```

`model` and `licenseNote` must be nonempty strings; `seed` must be a
nonnegative JavaScript-safe integer. SHA-256 binds the sidecar to the local
audio, but does not independently attest the provider or grant usage rights.
Local provenance uses `provider: ace-step` and does not require `space`.
Hosted provenance requires the exact Space and standard turbo model above.
Library music instead uses `kind: licensed-library-music` and
`provider: incompetech` or `wikimedia-commons`, with verified CC0 or CC BY source/license evidence and
project redistribution permission as defined in `references/library-bgm.md`.
It contains no AI model, seed, or prompt hash. Both kinds retain measured
duration and an audio hash; a library success is not proof that AI generated music.
CC BY music requires its generated `audio.music.attribution` end credit and
the companion `<audio-file>.license.txt`; preserve both when editing or
delivering the project. CC0 does not add a required credit.
Automatic library selection searches current Incompetech metadata by the
confirmed mood before using the small pinned Commons backup. Only selected
audio is downloaded; a catalog match is not proof of audible suitability.
`npm run validate` verifies music and provenance only when music is present;
it never fetches or generates audio.

## Acceptance criteria

- Every required script phrase maps to a scene ID in the approved order.
- Shot ranges are contiguous, cover every scene, and contain every visual beat.
- Narration duration, provenance, speech anchors, and caption coverage validate.
- Captions are phrase-timed instead of remaining visible for a whole scene.
- Every demonstrated action and state change maps to a source reference.
- Mock behavior is explicitly labeled as conceptual.
- Captions use an open lower third and do not cover the demonstrated action.
- Dense product UI settles to fixed whole-pixel geometry before reading begins.
- Boundary triplets contain no blank frames or clipping.
- Paired dense-hold frames show no parent drift or scale shimmer.
- The opening animation is inspected in motion.
- A six-frame contact sheet shows meaningful temporal progression.
- Selected preset style frames and motion test form one coherent visual system.
- No selected preset failure condition remains true.
- The final render matches the requested format and media streams.

## Evidence and placeholders

- Every `REPLACE_ME` value is unresolved and blocks `npm run validate`.
- The starter is deliberately neutral and does not include a proof metric, CTA,
  creator treatment, customer data, or shipped product behavior.
- Use supplied UI or source-backed code for production product scenes.
