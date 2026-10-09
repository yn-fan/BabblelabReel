# Content-matched AI background music

Use this workflow as part of new video production, or when adding a requested
soundtrack to an existing video. Reel handles music direction, cloud generation,
download, and mixing, with user direction confirmation before generation and
listening acceptance before final delivery. Users need no separate site or local
music model. Respect explicit silence, supplied soundtracks, and planning-only
requests. Unrelated repairs preserve existing audio.

The default `auto` mode tries the official ACE-Step Hugging Face Space once,
then automatically searches Incompetech by the confirmed mood and imports a
matching licensed MP3 if the hosted path fails. The pinned Commons library is
a secondary backup, not the limit of the searchable music pool.
The initial direction confirmation and later audition remain; switching to
the library requires no extra user question. Disclose the actual source.
Explicit AI-only or local-only requests use their strict provider modes.
The packaged adapters use Python's standard library; no local model,
third-party Python package, paid service, or shared embedded credential is
required. Speech remains Audio Generator's responsibility. Free compute is
quota-limited and may require login or waiting; availability is not guaranteed.
The AI branch is an experimental shared demo, not a production music service.
Live AI attempts have not yet produced a verified soundtrack. Library success
does not establish AI success; API compatibility alone is insufficient.
Provider evidence and alternatives are in [ai-bgm-research.md](ai-bgm-research.md).

## 1. Match the story before generating

Read the locked story, treatment, scene purposes, shot timing, and narration
density. Write a short music direction in the project's `REEL.md` with:

- The emotional arc, linked to actual scene IDs and time ranges.
- Energy, tempo, instrumentation, and musical density suited to the treatment.
- How the music leaves space for narration and resolves at the video's ending.
- The reason these choices fit this story, plus any approved silence.

A tense-to-hopeful vision film might move from a sparse low pulse into warm
piano and open synth textures. A fast product reveal may need a restrained
electronic groove; a careful workflow explanation may need minimal percussion.
These are examples, not preset soundtracks. Describe audible qualities rather
than requesting a named artist, a copyrighted song, or a reference recording.

Save `music-brief.json` in the existing Reel project:

```json
{
  "direction": {
    "emotion": "Focused, then warm and hopeful",
    "arc": "Sparse tension in the opening; steadier movement through the task; a gentle resolution at the close",
    "instruments": "Soft electronic pulse, warm piano, open synth textures",
    "pace": "Moderate and restrained, without a dramatic drop",
    "narration": "An unobtrusive supporting layer with room for spoken phrases"
  },
  "prompt": "Original instrumental underscore. Sparse, slightly tense electronic pulse at first; gradually open into warm piano and soft synth textures; finish with a gentle hopeful resolution. Restrained percussion, unobtrusive melody, room for spoken narration, no vocals.",
  "rationale": "The opening introduces coordination friction, the task section becomes focused, and the final scene resolves the uncertainty.",
  "instrumental": true,
  "bpm": 96,
  "keyScale": "C Major",
  "timeSignature": "4",
  "seed": 42,
  "libraryTags": ["calm", "piano"]
}
```

Replace the example with the video's actual direction. The prompt is the only
creative text sent to the public service; source scripts, product identifiers,
screenshots, private claims, and the rationale stay out of the request.
The prompt must describe only abstract music: mood, instruments, tempo,
density, progression, and ending. Do not copy source wording into it.
Treat generation as probabilistic: a seed records intent, not a guarantee of
identical output across hardware/model versions or precise musical beat sync.
For automatic/library modes, follow [library-bgm.md](library-bgm.md) to choose
matching musical tags from this direction before computing approval. This is
agent-authored selection metadata, not another question for the user.

Completion: the brief explains the content-to-music relationship without
changing the story or requesting unlicensed imitation.

## 2. Confirm the direction

Run the local-only review command; it neither contacts a provider nor writes
approval. When music already exists, prepare the isolated candidate project
described in step 6 first; leave the active soundtrack untouched:

```bash
python3 skills/reel/scripts/generate_bgm.py review --provider auto \
  --project "PROJECT_DIR" --brief "PROJECT_DIR/music-brief.json" \
  --name "story-underscore"
```

Present its direction and rationale as one compact, plain-language card in the
user's language. Tie the emotional arc to actual scenes/times, explain the
pace, sound, narration relationship, and ending, and disclose the selected free
shared provider with licensed backup and automatic credits when required. Ask one focused question using the host's question tool:
use this direction, adjust it, or no BGM. Users can describe adjustments in
ordinary language; they need not choose BPM, keys, or instruments themselves.
Keep independent video work moving, but stop before music generation.

On approval, add this object to `music-brief.json`, using the review command's
actual fingerprint and a local reference to the user's actual decision:

```json
"approval": {
  "mode": "approved",
  "fingerprint": "<fingerprint returned by review>",
  "decisionRef": "<user response reference or short decision excerpt>"
}
```

Reel writes this record; users are not asked to edit JSON. Approval of the video
brief, a default soundtrack preference, or approval to implement this feature
is not approval of a particular music direction. A child agent returns the
card to its parent and waits for the real decision; it cannot approve for the user.

For a changed direction, revise the card and prompt together and obtain the
updated decision. For no BGM, record silence and skip generation. Only explicit
delegation of music choice, such as "you decide, go ahead", permits
`mode: "delegated"` with that instruction as `decisionRef`; an agent's preference
or silence is not delegation. Preserve its scope: delegation of direction alone
does not waive audition. An explicit end-to-end delegation may waive both gates,
with separate direction and audition decisions recorded in `REEL.md`.

The helper rejects missing approval, missing decision evidence, and stale
fingerprints before contacting either provider. The fingerprint binds the
brief, seed, duration, scenes, shots, and treatment; edits invalidate approval.
It is a consistency guard, not authentication of who approved. The decision
reference stays local; public provenance records only the mode and fingerprint.
Existing briefs must add the direction card and approval record before their
next generation; existing audio and story schemas remain compatible.

Completion: the current direction is explicitly approved or delegated, or
silence is recorded. Pending decisions consume no generation quota.

## 3. Choose the delivery mode

Use `--provider auto` for ordinary production. The generate command checks the
hosted service and handles failures itself; a separate failing preflight must
not stop the library path. When diagnosing an explicitly AI-only request,
inspect the hosted service from the BabblelabReel root:

```bash
python3 skills/reel/scripts/generate_bgm.py preflight --provider huggingface
```

This inspects the current Gradio contract and the standard
`acestep-v15-turbo` option, without starting GPU inference. API compatibility
does not prove that a GPU slot is available. Use the default anonymous path;
if the service requires authentication, the user may explicitly supply their
own `REEL_HF_TOKEN` through the environment. Never bundle a shared token,
read another application's credentials, or expose a token in the video project.

The hosted adapter targets one fixed official HTTPS Space. It does not reuse
the local `/release_task` API, duplicate a Space, or alter the hosted service.
Quota and queue policies belong to the host. Keep each request within the
adapter's 120-second video limit; do not split videos into repeated jobs or
rotate accounts/endpoints to bypass limits.

Completion: the selected hosted contract is compatible; report authentication,
quota, runtime, or contract drift as blockers when encountered.

## 4. Produce a draft soundtrack

`PROJECT_DIR` below is the existing project, either a standalone Reel under its
resolved `OUTPUT_DIR` or an explicitly supplied repository target. Do not create
another user-home resolver.

```bash
python3 skills/reel/scripts/generate_bgm.py generate \
  --provider auto \
  --project "PROJECT_DIR" \
  --brief "PROJECT_DIR/music-brief.json" \
  --name "story-underscore"
```

The AI branch requests seeded instrumental FLAC covering the composition duration
(rounded up to whole seconds, with ACE-Step's 10-second minimum),
waits for one queued job with a bounded timeout, measures the native FLAC, writes
`public/audio/story-underscore.flac` plus its `.flac.json` sidecar, and attaches
`audio.music` to `src/reel/story.json` for preview, not final acceptance.
It preserves narration and refuses an
existing music track or colliding filenames. On generation failure, the story
remains unchanged. Do not automatically resubmit a failed or timed-out job.
If failure output contains `eventId`, retain it in the run's diagnostic record
to inspect that job without creating another.
On quota/login/network/runtime/contract failures or unusable generated audio,
`auto` selects and imports a matching CC0/CC BY recording using
[library-bgm.md](library-bgm.md), with no switch-confirmation question.
It reports the fallback and records library provenance rather than AI provenance.
If a real quota/auth/service blocker is already known, pass
`--known-ai-blocker quota`, `auth`, or `unavailable` to `auto` instead of sending
another hosted request. This records that AI was skipped, not attempted.
Do not invent a blocker or use this flag to pretend an AI attempt occurred.
If a timed-out job may still run, retain its ID; do not resubmit it.

Input, approval, changed-story, collision, or publication failures remain errors,
not reasons to bypass safeguards through fallback. If library acquisition also
fails, preserve the story and report both failures. Explicit AI-only requests
use `--provider huggingface` and stop on failure; explicit local requests remain
local. No paid providers, embedded credentials, unverified-license tracks,
silent-video substitution, or manual website links stand in for completion.

The official Space offers FLAC/MP3 rather than WAV. FLAC preserves lossless
audio and is played directly through Remotion's media component; no converter
installation or lossy substitution is needed. Local generation still uses WAV.

An AI sidecar records the provider/Space/model, seed, prompt hash, audio hash, measured
duration, instrumental request, and license note. Keep the actual brief in the
project for editorial review. The sidecar is lineage evidence, not proof of
musical quality, absence of vocals, or legal clearance for a particular use.
Library sidecars instead record the original source, license evidence, selected
track, and file hashes. The result's actual `kind`/`provider`, not the attempted
AI path, determines the soundtrack label in delivery.
For CC BY recordings, preserve the generated end credit and companion license
file. See `library-bgm.md` for attribution and no-credit constraints.

Completion: the helper returns `success: true`, the audio and sidecar exist,
`npm run validate` accepts the attached music track, and audition is pending
in `REEL.md`. Generation success is not a listening decision.

## 5. Explicit local alternative

Use a local service only when the user selected it; do not fall back from cloud
generation automatically. Existing helper calls without `--provider` retain
their local provider selection for compatibility, but now require the same
direction approval as hosted generation. A configured local service uses:

```bash
python3 skills/reel/scripts/generate_bgm.py preflight --provider local --base-url http://127.0.0.1:8001
python3 skills/reel/scripts/generate_bgm.py generate --provider local \
  --project "PROJECT_DIR" --brief "PROJECT_DIR/music-brief.json" \
  --model acestep-v15-turbo --name "local-underscore" \
  --base-url http://127.0.0.1:8001
```

Local preflight requires a loaded standard turbo model with `text2music`
support. Unknown readiness is a blocker, not permission to initialize a model.
Optional authentication uses `ACE_STEP_API_KEY` from the environment. Only
loopback HTTP origins are accepted. The local composition limit is 600 seconds.
Installation, dependency/model downloads, and remote tunnels require separate
permission. Keep all credentials out of briefs, provenance, and committed files.

## 6. Audition before final delivery

The starter's optional music track plays local WAV, native FLAC, or library MP3. Its bounded range and
source offset are explicit; it does not loop a short file or extend the video.
The shared gain envelope fades in/out and ducks around actual caption timing
when narration exists. Start conservatively, then adjust `volume`, `duckVolume`,
fades, and attack/release in `audio.music` after listening. Caption cues must
match speech timing for ducking to work; arbitrary text timing is not enough.
Existing projects need the shared music component and validator integration
from the starter before the new JSON field can produce sound.

Provide the actual generated audio and a playable mixed preview for the user,
clearly labeled as a draft. Ask whether to keep it, adjust the mix, change the
music direction, or use no BGM. Record the track path/hash, preview path, current
mix settings, decision, and decision reference in the project's `REEL.md`.
Keep audition pending until the user responds; approval of the earlier direction
does not establish approval of the generated result. A waived audition records
explicit delegation, never a claim that the user listened.

For volume, ducking, or fade feedback, reuse the same audio, adjust the mix,
and return a revised preview without a new provider job. For a direction
mismatch, return to the direction card before generating a replacement.
A request to try another take in the same direction authorizes one new seed
and generation: refresh its fingerprint and record that request rather than
asking the same direction question again. Never regenerate in a silent loop.

For replacement generation, preserve the active story and all existing audio.
Work in an isolated candidate project copy, removing `audio.music` only from
that copy and using a fresh output name. After listening acceptance, transfer
the candidate audio/sidecar without overwriting existing files and update only
the original story's music track; first verify its story/timing still matches
the approved candidate. Retain the previous assets. The helper's existing-track
guard is not permission to clear the active soundtrack before a replacement.

Listen to the generated track first, then the mixed opening, densest speech,
scene changes, and ending. Reject unintended vocals, masking, pumping, harsh
transients, clipping, mismatched emotion, or a cut-off musical phrase. Regenerate
only through the decision flow above or adjust the bounded mix, preserving the approved
script. Gain limits are not loudness normalization or a mastering guarantee.
Short outputs fail instead of being looped silently.

If rendering was requested, inspect the resulting video's audio stream and
listen to the actual mix. A mocked provider response, successful schema check,
or silent test WAV does not prove live AI generation or soundtrack quality.
If agent playback is unavailable, disclose that limitation and rely on the
user's actual listening feedback; do not invent an audio-quality assessment.

Completion: the specific audio and mix are accepted, audition is explicitly
delegated, or silence is approved. Only then finalize the mix and deliver a
final render. A pending audition may be delivered as an editable draft, not a
completed soundtrack. Confirmation improves aesthetic alignment, not the
hosted service's reliability.
