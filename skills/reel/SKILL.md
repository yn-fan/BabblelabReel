---
name: babblelabreel
description: 'Acquire authorized video links, compress local videos or meet file-size limits, create Remotion films, FFmpeg edits or experimental Jianying drafts. Supports Douyin, Xiaohongshu, Bilibili, YouTube and Instagram; bare links prompt for intent. Download/compression-only tasks stop before production. Use for demos, Vlogs, beat-aligned montages, storyboards, captions, narration and matching BGM. Preserve source rights and approvals; WeChat Channels needs a separate client path.'
argument-hint: 'babblelabreel [goal + links, assets or location] — [optional: download, duration, format, render request]'
metadata:
  version: 260922.1
---

<!-- USER_HOME-banner -->
> **Artifact routing.** Use the logical destinations from `skills/_shared/SHARED.md`; do not construct user filesystem paths in this skill.

# BabblelabReel — video acquisition, compression and story-first editing

Standalone entry: resolve the bundle root as this file's grandparent's parent and read `AGENTS.md` there. Bind `BABBLELABREEL_ROOT` to it. Read `skills/_shared/SHARED.md` once. Audio/image instructions refer to the bundled children, not an external Emma installation.

Turn a goal and links/assets/location into the requested downloaded media,
editable source, preview, movie or draft.
Infer implementation: no technology/JSON questionnaire, universal creator style or product shell.

## 1. Understand the outcome

**Help only:** for how-to, examples or first-use explanation, read
[quickstart.md](references/quickstart.md); return concise prompts and output/limits.
Stop: no generation, directories, installs, network/provider calls or readiness
execution. Production need not preload the tutorial.

**Compression only:** for smaller files, sharing/upload limits, or a requested
MB ceiling, load [video-compression.md](references/video-compression.md).
Use a verified local source, preserve the original and deliver a measured
compressed copy. This branch exits before story lock, scaffold, BGM or editing;
post-render compression runs only when requested. Remote inputs first pass
the acquisition gates below; preserve their receipts and rights.

**Specified-link intent comes first.** For supported video links/share text with
no stated purpose, or explicit identification, metadata, download or acquisition
diagnosis, load [video-acquisition.md](references/video-acquisition.md).
For bare links, ask once with the host question tool whether to download,
inspect metadata, or leave them alone; wait before network access or setup.
An explicit scoped request goes straight to the relevant rights/dependency gates,
without asking its intent again. Summary/analysis/reference requests remain in
their stated scope, not automatic downloads. Unavailable question UI keeps the
operation pending; do not loop or treat it as consent.
Acquisition-only completion reports verified local files, measured quality and
file reveal, then exits without story lock, scaffold, BGM or rendering. If the
user also requested compression or editing, carry acquired files and provenance
into that branch. Metadata is not a download; download rights are not
reuse rights. WeChat Channels remains a separate client-assisted boundary.

Reuse context for audience, outcome, assets, brand, duration, format, audio, captions, destination and evidence.
Ask one focused question only for a material gap such as missing required assets
or an ambiguous app-native outcome. Separate music, installation, and privacy
approvals below remain real gates, not another general intake questionnaire.
Show compact **what I will make / what I need / next preview**, not internal logs.
Planning-only requests produce the plan, not builds, synthesis, or installation.

Infer safe defaults: 16:9, 1920×1080, 30fps; duration from the script/task;
supplied brand or restrained neutral treatment; no narration unless requested; editable
source first and render only when requested. Use 60fps only when fast cursor
motion, kinetic type, source footage, or explicit treatment benefits from it.
Preserve existing source audio and soundtracks on repairs unless changes were requested.

## 2. Select and load only the needed production branch

Choose by story/deliverable, not tool availability; lock story before treatment/build.

| Outcome | Required reference before planning/building |
|---|---|
| Save or inspect specified video links; diagnose acquisition | [video-acquisition.md](references/video-acquisition.md); no production steps unless a film was also requested |
| Compress a video or meet an upload-size limit | [video-compression.md](references/video-compression.md); separate verified copy, no story or music changes |
| Animated UI, product film, code-driven motion; improve/render a composition | [remotion-production.md](references/remotion-production.md); it owns scaffold, npm, `story.json`, deterministic animation, and composition QA |
| Supplied-footage edit, Vlog, montage, beat alignment, storyboard extraction | [footage-editing.md](references/footage-editing.md); it owns local inspection, `edit-plan.json`, FFmpeg commands and limits |
| Explicit editable domestic desktop Jianying draft | Also [jianying-handoff.md](references/jianying-handoff.md); retain the footage plan, separate tracks and experimental compatibility boundary |

Hybrid work loads both branches: render the Remotion segment, keep its editable
source, then treat it as footage. Do not impose Remotion files, scaffold, Node or
npm on footage/native projects. Their schemas include isolated BGM staging;
that adapter does not turn a footage deliverable into a Remotion project.

Before an **actual build**, run this local, read-only check for the selected engine:

```bash
python3 "{BABBLELABREEL_ROOT}/skills/reel/scripts/preflight_reel.py" --engine remotion
```

Use `ffmpeg` or `jianying` instead as selected; pass `--captions`, `--credits`,
`--transitions`, `--music`, and `--narration` only for selected features.
Rerun only when requirements or dependency state change; for a new Remotion
scaffold, recheck with `--project PATH` after authorized setup. That argument
checks Remotion dependencies only, not footage/native plans. Native text needs no libass. Never block
Remotion on missing FFmpeg or the optional Jianying package. Read the JSON
readiness/checks/actions; missing dependencies block only dependent work.
Help resolve blockers with scoped consent, not command dumps; continue planning,
asset review and narration discussion.
If Python/terminal is unavailable, report the host limitation; do not claim a
check ran. Readiness proves prerequisites only, never render or native-opening success.

For authorized online acquisition, use `--engine download` (add
`--metadata-only` for a probe). This reuses the downloader's local doctor and
approved environment discovery, without production filters or native-editor
dependencies. Offline link identification needs no downloader probe.

## 3. Lock story, sources, and media

Before implementation, write `REEL.md` and the selected engine's timeline.
Record brief/archetype, treatment, script source, required opening/sequence/close,
approved omissions, source ledger, capture/privacy evidence, timed shot/media
plan, acceptance criteria, and real/generated/concept/placeholder distinctions.
The timeline is `src/reel/story.json` only for Remotion; footage/native uses
`edit-plan.json`. Keep stable scene/shot/beat IDs and source references in the
ledger where the engine schema has no corresponding field.

Match the archetype: launch = promise/task/proof/minimal close; vision = reality/
tension/future/principles/invitation; task demo = entry through result; narrated
workflow = complete approved script; promo = promise/evidence/brief-led CTA;
social short = one moment; Vlog = coherent source ranges and meaningful speech.
For launch or vision intent without conflicting direction, load and apply
[video-type-defaults.md](references/video-type-defaults.md), including exact
timing, media floors, three style frames, motion test, and failure conditions.
Record `product-launch`, `vision-video`, or `custom` and deliberate overrides in
`REEL.md` (also `story.json` for Remotion); other engines retain equivalent gates
without inventing unsupported JSON fields. Do not blend presets or default to slides.

Never invent capabilities, customer results, identities, data, endorsements, or
metrics. For product tasks record entry/goal, exact source-backed affordance,
before state, visible action/acknowledgement, resulting state, and relevant undo,
error, empty, loading, permission, responsive/overflow states or explicit exclusions.
Show the source-linked state ledger in task plans/completion reports, not promises
of accuracy; repairs name actual replacement controls/states.
Concept behavior must be explicitly requested and labeled, never called shipped.

For every archetype, choose media during lock: source UI for actions, diagrams for
relationships, imagery/footage for situations, emotion and futures. Record medium,
reason, asset/generation need by shot/beat. Prefer supplied assets; use `image-generator` after lock and before
affected shots when imagery is needed. Respect graphic-only briefs; no decorative
quota. Required imagery blocked? Preserve the plan and obtain suitable assets or
an explicit provider/asset fallback; never silently substitute UI or diagrams.
Generated scenes may be stylized but are not evidence; meet vision's raster/
footage floor rather than using avatar glyphs or CSS silhouettes as human context.

## 4. Preserve narration and its inline keyframes

For narrated work, draft actual speech in `narration.md` beside `REEL.md` during
story lock and keep it synchronized with the approved engine timeline/script.
Only headings, spoken words, and keyframe images—no synopsis, timestamps,
requirements, scene notes, standalone captions, comments, or status.
Put each real project-relative Markdown image immediately before the words at its
first visual entry (after a scene heading for its opening); split mid-sentence
text at that phrase without rewriting, omitting, or reordering speech. Use concise
alt text, resolve all links, replace provisional frames with rendered matches,
and report missing frames outside the document; never insert placeholder links
or collect images at a section's ends. Silent work needs no invented narration.

Preserve script/order, stable sentence/phrase scene IDs, and approved omissions/
rewrites. After lock use child `audio-generator`, default `--mode enhanced` (Kokoro).
It owns host/backend/voice checks and dependency/model consent. Do not implement
project-local TTS or silently retry basic mode after failure. Accept another
supported mode/voice only when explicitly chosen; reject an unlabeled voice track
whose provenance does not match the brief.
Measure successful WAVs, retain sidecars, require `mode: enhanced` and Kokoro
engine/model unless explicitly overridden, and record provenance, gain, durations
and boundary headroom. Use phrase-timed captions ending within the narration,
not one caption for a whole scene. Remotion's reference owns its exact audio
fields/quality gate; footage/native records equivalent evidence with its own plan.
Preserve supplied speech/transcripts separately; transcription needs verified
local tooling or explicit provider authorization, never invented words.

## 5. Approve treatment, assets, and soundtrack

Treatment cannot rewrite story/product locks. Creator references need an eight-row
`Treatment map` **before promising similarity**, in `REEL.md` or the planning-only
response: shot scale, edit pacing, camera continuity, composition, typography, source-asset fidelity, transitions,
audio rhythm. Each row records observed/unknown, transfer decision, implementation,
verification frame/playback check. Storyboard original choreography; motif lists
fail. For Tim Kochjar load [tim-kochjar-study.md](references/tim-kochjar-study.md),
copy canonical `Reference evidence` cells unchanged and keep unknowns unknown.
Never imply affiliation, trace shots, reuse reference branding/media, or claim
the original prompt/system was recovered; results are `reference-derived treatment`.

Keep supplied footage, frames and speech local by default. Inspect actual host
tools, not assumed APIs; obtain separate consent for installs, model downloads,
paid calls or private uploads. Capture only synthetic, sanitized or explicitly
approved production data; wait for stable UI/fonts, retain full frame/layout/
cutout evidence and viewport/DPR. Crop source UI rather than redraw it inaccurately.
Record generated assets' prompt, provider/model, source, shot and placeholder state.
Preserve licensed media/fonts/logos and provenance; never download reference-film media.
For icons reuse the product family; Microsoft UI uses verified host Fluent
search/retrieval or individual official Fluent System Icons SVGs. Verify name,
size and Regular/Filled variant; no guessed paths, full-library downloads or
hand-drawn substitutes. Report inaccessible assets.

For authorized linked footage, use the acquisition reference, verify the local
receipt and intended reuse rights, and retain source/provenance in the selected
engine's ledger before importing media. Keep signed links/cookies out of the
editable project's distributable assets; acquisition is not evidence of depicted
product behavior or endorsement.

For new production or requested BGM, load [ai-bgm.md](references/ai-bgm.md):
derive direction from locked story/emotion/pacing/narration, obtain the **real**
direction decision before generation, and audition before final acceptance.
Only explicit delegation covers a gate; direction delegation alone does not
waive audition. Respect silence/supplied music and preserve unrelated repair audio.
Use hosted AI then automatic mood-matched licensed-library backup without another
switch question; disclose actual provenance/license/credits, not AI success for
a library result. Cloud AI is experimental, quota-limited, and has no verified
successful soundtrack yet. Send abstract music direction only, never private
scripts/identifiers/screenshots. Strict AI-only/local-only remains strict; local
setup needs separate dependency/model permission. Both paths failing is a blocker,
not permission for paid calls or silent delivery. Preview fades/ducking and
listen to opening, dense speech, transitions and ending for masking, pumping,
clipping, vocals and abrupt cuts. Beat/onset suggestions never override protected
speech, captions, story or ending without deliberate timeline revision.

## 6. Verify the actual output, then deliver

Run gates in order; do not polish past an earlier failure:
1. **Story:** required phrases/task steps, opening/order/close and omissions match;
   sources, ranges, overlaps and duration agree with the engine plan; narration
   links/inline positions, measured audio, phrase captions and BGM rights/acceptance pass.
2. **Product/usability:** source ledger proves actions/states; text/feedback remains
   readable at playback size; captions/overlays do not cover the demonstrated action.
3. **Temporal/technical:** inspect opening motion, outgoing/cut/incoming boundary
   frames and each transition; compare readable-hold frames 10–15 frames apart;
   check drift, clipping, overlap, z-order, blanks, assets, spring tails, transforms.
4. **Treatment:** six-frame contact sheet shows progression and one coherent
   visual system, not repeating slides or ambient drift; assigned imagery actually
   appears; preset early/middle/late frames, durations, style frames and motion test
   pass all failure conditions; creator similarity passes all eight map dimensions.

Use the branch's validation/preview/render commands, render only when requested,
and inspect/play actual output at normal speed: dimensions/fps/duration, streams,
head/tail, assets, glyphs/safe areas, dense holds, motion, source sound, narration,
music fades/mix and credits. Static checks or metadata are not playback evidence.
For Jianying distinguish bundle generation, verified opening in the named native
app/version, and verified native export; compatibility is experimental, Mac
import unverified, export manual unless the host has verified supported automation.
Missing tools block only dependent claims, never justify pretending success.

For a requested smaller delivery copy or upload-size ceiling after rendering,
follow [video-compression.md](references/video-compression.md) on the verified
master. Preserve that master, editable source and all credits; verify the
compressed copy separately instead of changing a locked timeline.

Report source path plus preview/render/draft path, engine, archetype/treatment,
composition ID or edit-plan path, format/duration/fps, asset/concept/placeholders,
and exact omissions/limitations. Retain editable sources/audio/license sidecars; a draft is not a movie.
