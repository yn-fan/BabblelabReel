# Local footage, Vlogs, and music-aligned edits

Use this branch for supplied live-action clips, travel/life Vlogs, rough cuts,
montages, and beat-aligned edits. Use Remotion instead when the main work is
animated UI, generated graphics, or code-driven titles. Hybrid work renders the
Remotion segment first, then treats the rendered file as an ordinary clip;
retain its editable source. Choose the engine by the deliverable, not by which
tool happened to be available first.

For supplied platform links rather than local media, run the authorized
`video-acquisition.md` branch first. Import only its verified local receipts,
retain rights/source evidence, and then continue this plan; a metadata response
or a media URL is not a playable local clip. If only downloading was requested,
stop after acquisition instead of starting this branch.

For size reduction without editorial changes, use
[video-compression.md](video-compression.md) instead. If a montage also has a
delivery-size limit, finish and verify the master first, then compress a
separate copy; retain the master, editable source and all credits.

## 1. Preflight and inspect

Resolve the Reel `OUTPUT_DIR` binding before writing user artifacts. Preserve
the originals. A footage project contains `REEL.md`, `edit-plan.json`, selected
media or documented local media references, `analysis/`, `storyboard/`, and
`out/` when a render is requested. There is no Node installation requirement
for this branch. Python 3.9+, `ffmpeg`, and `ffprobe` are required; subtitle
rendering additionally requires an FFmpeg build with the subtitles/libass filter.
Report missing tools and obtain installation consent rather than installing
them or substituting an unverified cloud service.

Run the following on each selected source, not the entire user disk:

```bash
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/analyze_media.py" inspect "clip.mp4"
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/analyze_media.py" storyboard "clip.mp4" \
  --at 0 2 5 --output "OUTPUT_DIR/{slug}/analysis/clip-01"
```

Choose times inside the measured duration, with at most 48 samples per call.
The output is local JPEG frames, `frames.json`, and an HTML contact sheet.
Open and inspect the images with available host vision tools. Metadata and
frame extraction are **not** semantic understanding, scene detection, or proof
of motion quality. Review additional timestamps or playback for ambiguous
actions, shake, focus, flashes, and cut continuity.

Record a source ledger in `REEL.md`: source ID/path, measured duration and
streams, sampled timestamps, observed subject/action/shot scale, usable ranges,
natural audio worth preserving, privacy/rights, selection or rejection reason.
Interpretation must cite the inspected frames; unknown location, identity,
chronology, or emotion stays unknown. If host image inspection is unavailable,
report it and use user descriptions only as unverified planning input.

Keep footage, extracted images, and speech local by default. The linked Vlog
project's visual-model provider is not an BabblelabReel dependency or authorization to
upload private footage.

## 2. Lock the editorial story

Select an intentional opening, progression, and close. Travel is one archetype,
not the default: apply the user's product, family, event, or internal-work
context. Vary shot scale and duration when the source supports it; avoid random
shuffling or mandatory effects. Choose meaningful source in/out points before
fitting music. Preserve speech, action completion, readable holds, and natural
sound. Keep a record of authorized omissions.

Build a storyboard from the **selected ranges in planned order**, with each
thumbnail pointing to its source timestamp, editorial purpose, proposed
timeline position, and audio treatment. Show an early preview before expensive
rendering when the user requested review. Explicit full-production delegation
permits proceeding, but does not turn metadata into a visual review.

For existing speech, use supplied timed captions or an already available,
authorized local transcription tool. Whisper is optional, not bundled: check
its actual CLI/version, model availability, and language support before use.
Installing a package, downloading a model, paid inference, or uploading voice
needs the applicable consent. Transcription failure is a blocker for required
speech captions, not permission to invent text. Review names, punctuation,
first/last words and timing; retain the original transcript separately from
edited captions. Generated narration still follows `audio-generator` and the
locked-script/`narration.md` contract.

## 3. Measure music and suggest cuts

Use supplied music first. For automatic music, retain `ai-bgm.md`'s direction
approval, AI-first/library backup, provenance, and audition gates. Its existing
generator publishes into a Remotion project; for footage-only acquisition use
a temporary, valid music-staging Reel under the same bound run, with the real
locked story/duration and approval. Copy the acquired audio and its unmodified
provenance/license files into the footage project. Never fabricate approval or
send private footage/story text to music services.

Analyze the **actual selected audio**, not a guessed BPM or an unrelated track:

```bash
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/analyze_media.py" beats "music.mp3" \
  --fps 30 > "OUTPUT_DIR/{slug}/analysis/beats.json"
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/analyze_media.py" snap \
  --beats "OUTPUT_DIR/{slug}/analysis/beats.json" --fps 30 \
  --cuts 60 120 180 --tolerance 3 --minimum-shot 12
```

The dependency-free detector measures positive RMS-energy peaks at 10ms
resolution. Its output is **onset candidates**, not a guaranteed beat/downbeat
grid. Silence produces no candidates. Sustained/ambient music and syncopated
rhythm need listening-based decisions; never synthesize evenly spaced beats
and claim they were detected. Analysis is bounded to a 20-minute excerpt.

`snap` returns proposals only. It matches fps, limits movement, preserves cut
order and a minimum inter-cut duration; it does not rewrite the project.
For each accepted proposal, revise source ranges and adjacent clip lengths,
account for transition overlap, revalidate source handles and the final
duration, and inspect the last shot's minimum hold. Keep fixed narration,
captions, protected story beats and the ending fixed unless their change was
explicitly part of the brief. Audible rhythm wins over maximizing the number
of snapped cuts.

## 4. Implement the local timeline

Use `scripts/edit_video.py --help` and its `validate`/`render` subcommands.
`edit-plan.json` is frame-based at the selected output fps; source starts are
seconds. All media paths resolve locally relative to the plan. Trim only
measured ranges; the backend normalizes dimensions, timestamps, and audio
streams for mixed sources. An outgoing fade overlaps the next clip, so final
duration is the sum of clip durations minus transition overlaps. Most edits
should remain hard cuts.

Minimal six-second example (both source files must contain the requested ranges):

```json
{
  "version": 1,
  "output": {"fps": 30, "width": 1280, "height": 720},
  "clips": [
    {
      "path": "media/opening.mp4",
      "sourceStart": 0,
      "durationFrames": 90,
      "transition": {"type": "fade", "durationFrames": 15}
    },
    {"path": "media/detail.mp4", "sourceStart": 2, "durationFrames": 105}
  ],
  "audio": {"sourceVolume": 1}
}
```

Optional fields:

| Field | Contract |
|---|---|
| `audio.music` | `{path, volume?, fadeInFrames?, fadeOutFrames?, ducking?}`; starts at zero, must cover the output, default gain `.25`, fades `0` |
| `audio.narration` | `{path, volume?}`; starts at zero, default gain `1`, may not extend beyond the output |
| `audio.sourceVolume` | Default `1`; explicit `0` mutes natural sound |
| `captions` | `[{startFrame, endFrame, text}]`; phrase-level absolute ranges, exclusive end |
| `attribution` | `{text, startFrame?, endFrame?}`; exact required credit text, default full timeline |

Ducking defaults on when an external narration track exists; set it explicitly
for a deliberate mix choice. Natural speech inside footage is preserved but
is not automatically identified as a ducking sidechain. Review and deliberately
lower the music, or prepare a separately aligned narration track, rather than
claiming the renderer detected source speech. Gains are bounded to 0–2.

The renderer accepts integer fps 1–60, even dimensions 64–3840, at most 100 clips,
and at most one hour. Source starts round to the nearest output frame; inspect
the normalized plan before accepting frame-sensitive speech cuts.

```bash
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/edit_video.py" validate \
  "OUTPUT_DIR/{slug}/edit-plan.json"
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/edit_video.py" render \
  "OUTPUT_DIR/{slug}/edit-plan.json" --output "OUTPUT_DIR/{slug}/out/reel.mp4"
```

Captions and attribution require libass; without it the renderer reports a
blocker instead of dropping text. Use a supported build with consent, or the
existing Remotion branch if the user authorizes changing the implementation.
Keep legal text legible in the top credit area and leave captions below.
The final movie's `.licenses.txt` companion preserves the exact attribution
text; additionally retain the acquisition JSON/license sidecars with the music.
Attribution is explicit input: the renderer does not infer a recording's
license from its filename or website.

The backend's supported effects are deliberately bounded. For more complex
kinetic text, masks, tracked overlays or arbitrary filters/keyframes, implement
and render a Remotion segment, or use the native editor handoff. Do not put
unsupported effects in JSON and imply they ran. Rendering must fail explicitly
on unknown fields, invalid ranges, missing fonts/filters/media, or unsafe output
collisions.

Use phrase-level captions with safe areas, readable contrast and verified glyph
coverage. Preserve source audio unless the plan explicitly changes its volume.
Mix BGM with fades and speech ducking; listen to source speech as well as added
narration. Keep mandatory music credits visible and retain the exact companion
license/provenance. A successful FFmpeg process does not prove rights clearance.

## 5. Verify and deliver

Run plan validation first. When rendering is requested, render to a new output
file and inspect the **actual** MP4: dimensions/fps/duration, video/audio
streams, decoded opening/end, each transition's outgoing/midpoint/incoming
frames, subtitle glyphs and safe areas, source sound, narration intelligibility,
BGM fades and credits. Play it at normal speed.

Retain editable source selections, timing, transcript/captions, and music
provenance. Report the selected engine and any unsupported or unverified part.
For a Jianying deliverable, follow `jianying-handoff.md`; a draft is not a
rendered video, and a JSON file alone is not proof that the app opened it.
