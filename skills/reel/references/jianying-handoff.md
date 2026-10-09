# Editable domestic Jianying handoff

Use only when the user requests a native editable Jianying draft. Keep Remotion
for code-driven motion and FFmpeg for a directly rendered montage. A Jianying
draft is not a CapCut project, a cloud share, or an exported movie.

## Preflight

Resolve the Reel output binding. Record the exact domestic desktop Jianying
version and OS; compatibility depends on the installed editor's draft schema.
Do not infer an application version from the OS or promise all current versions.
The optional `pyJianYingDraft` dependency is not bundled or installed by BabblelabReel. Check its package
version and license, and obtain consent before installing dependencies.

Reel targets the source API at
`GuanYixuan/pyJianYingDraft@c3318066d964744e2bfc66f75c71745fe8cea52a`,
which uses `TrackSpec` / `append_tracks` and writes `draft_content.json`.
The user-supplied skill uses a different vendored fork writing `draft_info.json`.
These are not interchangeable. The maintained package documents generation on
Mac/Linux but a Windows-dependent export path; current Mac import is unverified.
Check `video-editing-integrations.md` for exact source/license evidence.

Use a **new staging directory**, outside the live application draft database.
Preserve separate clip, narration, music, and caption tracks. Copy selected
media with stable filenames and retain source/license sidecars, so the draft
does not depend on the originals remaining in place. The current adapter uses
absolute paths to the copied media: **keep the staging directory in place**.
Moving the bundle requires relinking and another native-opening check; do not
call it a relocation-safe package. Keep the frame-based edit plan as the
engine-neutral source of truth.

## Bundled adapter

After confirming the destination is outside the editor's live database:

```bash
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/export_jianying.py" \
  --plan "OUTPUT_DIR/{slug}/edit-plan.json" \
  --staging-root "OUTPUT_DIR/{slug}/jianying-staging" \
  --target-app-version "{actual installed version}" \
  --confirm-staging-only
```

The staging root must be absent or empty, with an existing parent. This command
does not install dependencies, discover the app, or register a draft in its
database. Missing/incompatible `pyJianYingDraft` fails before output mutation.
It retains copied media and adjacent sidecars; repeat `--sidecar PATH` for
additional explicitly selected provenance/license evidence.

The adapter reuses the FFmpeg branch's strict v1 plan and media-bound checks,
without requiring FFmpeg render filters/encoders for native tracks. It maps
straight cuts, source volume, separate narration/music, ordinary music fades,
non-overlapping captions, and verbatim credit text into native tracks.
Times convert from frames to integer microseconds. `handoff.json` records the
dependency/API contract, requested target version, and unverified native status.

Overlapping fades/transitions, sidechain ducking, overlapping captions and
delayed source-audio offsets are explicitly unsupported. A plan with music and
narration defaults to ducking in the local renderer: preserve that intent and
report the conversion blocker, or deliberately author an agreed static mix
with `audio.music.ducking:false`. Do not toggle it silently to make export pass.
Filters/keyframes are not fields in this v1 schema; use the advanced authoring
branch below when requested, with its separate compatibility review.

The dependency was unavailable in the implementation environment. Contract
tests with faithful API doubles and missing-dependency failures do not establish
successful generation with the real package or native opening/export.

## Compatibility and fidelity

Translate only the adapter's verified feature subset. A native editor supports
more than an exporter: availability of UI transitions, filters, stickers,
keyframes, captions or speech synthesis is not evidence that the export library
can reproduce them. Record every requested effect as supported, rendered into
a labeled segment, manually pending, or blocked.

For a filter or keyframe unsupported by the adapter, retain its precise intent
and target ranges in `REEL.md` and disclose that native completion is pending.
If a pre-rendered Remotion/FFmpeg segment is used, keep its editable source and
state that the internal layers are flattened in the native clip. Do not claim
native editability of a rendered overlay or silently discard an effect.

Preserve required music credits as a visible editable text segment and a
companion license file. Keep narration and music separate. Preview fading,
ducking, source sound and caption wrapping in the actual editor; equivalent
JSON timing does not prove equivalent mixing or typography.

### Advanced native effects

For requested native filters, transforms or keyframes beyond the adapter,
author a project-local script only against the installed dependency's verified
API; keep it with the editable project. The researched source exposes:

- `AudioSegment.add_fade(in_duration, out_duration)` and
  `VideoSegment.add_fade(...)`: integer **microseconds**, affecting audio.
- `AudioSegment.add_keyframe(time_offset, volume)`: segment-relative integer
  microseconds and linear volume values. This is not signal-dependent
  `sidechaincompress`; preserve that distinction.
- `VisualSegment.add_keyframe(property, time_offset, value)`: enum-selected
  alpha, scale, rotation and other native properties. Verify coordinate units
  before translating a crop/pan; do not mix uniform and independent-axis scale.
- `VideoSegment.add_filter(filter_type, intensity)`: a native `FilterType`
  preset with intensity 0–100. Inspect available enums instead of guessing
  localized preset names or equating a preset to an FFmpeg filter string.
- `VideoSegment.add_transition(transition_type, duration=...)`: attaches to
  the preceding segment and does not itself move clip start/duration.

Add effects **before** inserting their segments into the script, so dependent
materials are registered. All offsets and values must be finite, inside the
segment, and intentionally authored. Same-track temporal overlaps are rejected
by this library: overlapping FFmpeg fade coordinates cannot be copied as native
transition timing. Preserve the separate editable plan and report incompatible
transitions rather than silently changing the duration.

These APIs were source-verified, not native-render verified. If the dependency
is missing or different, block only that requested native feature; do not
silently flatten it, install another fork, or promise the generated project
will work in the user's Mac application.

## Import and native export

On macOS, generate the supported draft bundle, then have the user open/import
it through their installed desktop Jianying. Do not guess a user-specific
draft path, overwrite an existing draft, register a project by editing the
application's database, or automate inaccessible UI through assumed controls.
If the application lacks a portable import route, obtain the user-selected
draft location and follow the installed version's documented workflow.

Native export remains a manual step unless the current host actually exposes a
verified supported automation path. Windows-only UI automation is not a Mac
export solution. A separately rendered FFmpeg preview can be delivered when
requested, clearly distinguished from the eventual native export.

Completion reports distinguish:

- **Bundle generated:** validated timeline and local assets were written.
- **Native opening verified:** the named application/version actually opened
  the draft and showed the expected tracks, timing, captions and media.
- **Native export verified:** the editor actually produced a playable movie
  whose metadata and content were checked.

If only the first state was achieved, say so. If the optional dependency or
compatible editor is absent, preserve the validated edit plan and report the
specific blocker; do not rename arbitrary JSON to `draft_content.json` and
claim a functioning native project.
