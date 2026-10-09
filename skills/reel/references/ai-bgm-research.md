# AI BGM integration research

Research date: 2026-09-10. Primary-source review with live integration attempts
recorded below. No local model installation, paid call, or successful live
audio-quality evaluation was performed.

## Decision

The initial implementation used a local **ACE-Step 1.5** service. The shared
skill now prioritizes the official free hosted Space so each user does not need
to install a model. Local generation remains an explicit alternative.
Keep generation outside Remotion rendering and persist the resulting audio
before playback. Integrate the protocol with an independently authored,
standard-library adapter rather than copying a model runtime into BabblelabReel.

Both paths select the standard `acestep-v15-turbo` checkpoint. The skill does
not install models or automatically replace existing music. The music brief maps the video's
emotional arc to tempo, instrumentation, density, and resolution; model output
still requires listening. API compatibility is not evidence of musical quality.

## Alternatives and reuse assessment

| Candidate | Relevant capability | Licensing and deployment | Decision |
|---|---|---|---|
| [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) | Official hosted Gradio demo and separate local REST API | MIT code; official unified weights card is MIT-labelled and permits commercial generated music. Hosted compute has quotas; local use requires separately provisioned models. | Hosted demo is the skill default; local REST is an explicit alternative. |
| [ElevenLabs official music skill](https://github.com/elevenlabs/skills/tree/9edcbd4b80ed57b8e07a3f86ea520333969fbc3c/music) | A real first-party skill; official Music API supports `music_v2`, duration, and forced instrumental output | Skill code is MIT; hosted service and output rights have separate paid-plan/use-case terms. Requires a key and prompt transmission. | Useful hosted alternative, not implemented or used as an automatic fallback. |
| [AudioCraft / MusicGen](https://github.com/facebookresearch/audiocraft/blob/896ec7c47f5e5d1e5aa1e4b260c4405328bf009d/model_cards/MUSICGEN_MODEL_CARD.md) | In-process Python text-to-music generation | Code MIT, pretrained weights CC-BY-NC 4.0. Documented medium-model recommendation is 16 GB GPU memory; source selects CUDA or CPU, not automatic MPS. | Reject as the general commercial default. |
| [Stable Audio Open](https://huggingface.co/stabilityai/stable-audio-open-1.0) / [stable-audio-tools](https://github.com/Stability-AI/stable-audio-tools) | Up to 47-second 44.1 kHz stereo generation | Tools MIT; weights have separate Community License registration/revenue terms and gated access. Model card says it is better at sound effects/field recordings than music. | Consider later for specialist sound assets, not the first BGM provider. |

ACE-Step evidence:
[code license and output warning](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/README.md#license),
[official weights card](https://huggingface.co/ACE-Step/Ace-Step1.5/blob/19671f406d603126926c1b7e2adc169acbcade22/README.md),
[checkpoint mapping and automatic downloads](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/acestep/api/model_download.py),
[macOS launcher](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/start_api_server_macos.sh).
The launcher configures MLX on Apple Silicon and has a PyTorch fallback, but can
also install dependencies. BabblelabReel connects to an existing service instead of
running that launcher. CUDA VRAM claims do not establish a Mac memory minimum.
The default turbo weights come from `ACE-Step/Ace-Step1.5`, not an assumed
same-named Hugging Face repository.

Other licensing evidence:
[MusicGen code/weights distinction](https://github.com/facebookresearch/audiocraft/blob/896ec7c47f5e5d1e5aa1e4b260c4405328bf009d/model_cards/MUSICGEN_MODEL_CARD.md),
[MusicGen hardware/interface](https://github.com/facebookresearch/audiocraft/blob/896ec7c47f5e5d1e5aa1e4b260c4405328bf009d/docs/MUSICGEN.md),
[Stable Audio weight license](https://huggingface.co/stabilityai/stable-audio-open-1.0/blob/f21265c1e2710b3bd2386596943f0007f55f802e/LICENSE.md),
[Stable Audio limitations](https://huggingface.co/stabilityai/stable-audio-open-1.0#limitations).
Model licensing does not guarantee that an output is unique, copyrightable, or
non-infringing. Verify the chosen checkpoint and intended distribution use.

## Hosted contract and limitations

The [official Space](https://huggingface.co/spaces/ACE-Step/Ace-Step-v1.5)
exposes [Gradio API metadata](https://ace-step-ace-step-v1-5.hf.space/gradio_api/info).
The published `generation_wrapper` selects a model and accepts custom-mode
prompt, lyrics, BPM, key, time signature, seed, duration, batch size, and output
format. Its API is separate from the local REST server below. The adapter checks
the positional contract before submission, explicitly selects standard turbo,
requests one instrumental FLAC, and downloads the returned Gradio audio artifact.
The hosted format selector exposes MP3/FLAC, not WAV; native FLAC playback
avoids requiring a local conversion tool. Its STREAMINFO supplies sample count
and sample rate for duration; actual decoding/playback remains an acceptance gate.

The public `/info` schema omits state/layout components; it is not the raw wire
schema. The adapter also validates `/config`: `generation_wrapper` requires
54 input slots, including a null state slot at index 40 and four trailing state
slots, and returns 55 output slots. The initial adapter incorrectly sent only
the 49 documented inputs and expected 38 documented outputs. This mismatch is
reproduced in a wire-level regression test, rather than relying on mocks shaped
like the documentation.

Submission remains `POST /gradio_api/call/generation_wrapper`. With no supplied
session hash, Gradio assigns the event ID as the session hash. Read that job via
`GET /gradio_api/queue/data?session_hash=<event-id>` and validate its event IDs.
This retains `output.error` for categorized, redacted failures; the simplified
`/call/.../<event-id>` stream projects only `output.data`, yielding `error: null`
and hiding the reason. Reading a consumed stream again is not a replay and
cannot recover the earlier failure.
Sources: [Space handler](https://huggingface.co/spaces/ACE-Step/Ace-Step-v1.5/blob/7403460e9b34972f760317b56048f6cb9d4a3a11/acestep/gradio_ui/events/__init__.py#L739),
[Gradio input validation](https://github.com/gradio-app/gradio/blob/gradio%406.2.0/gradio/blocks.py#L1704),
[queue transport](https://github.com/gradio-app/gradio/blob/gradio%406.2.0/gradio/routes.py#L1328),
[session identity](https://github.com/gradio-app/gradio/blob/gradio%406.2.0/gradio/queueing.py#L52).

[ZeroGPU usage tiers](https://huggingface.co/docs/hub/spaces-zerogpu#usage-tiers)
provide free shared compute with account-dependent quotas and queue priorities.
The [Space source](https://huggingface.co/spaces/ACE-Step/Ace-Step-v1.5/blob/7403460e9b34972f760317b56048f6cb9d4a3a11/app.py)
sets a queue limit of 20 and can expose both standard and XL model choices.
Free quotas count GPU-runtime time, not output music duration. A running app or
published endpoint does not establish successful inference or an availability
guarantee. Anonymous access can fail; use only the user's explicitly configured
token when necessary, never a shared credential or quota-bypass mechanism.

Integration observation on 2026-09-10: one anonymous 10-second standard-turbo
submission was accepted, but did not return usable audio. The retained evidence
did not establish the cause, so neither quota, authentication, model failure,
nor caller parameters can be ruled in. Native FLAC playback was exercised
separately with an explicitly synthetic codec fixture; this is not evidence of
successful cloud music generation. Treat the hosted path as experimental,
not a production-availability guarantee. New failures retain a safe `eventId`
when available so the existing job can be inspected without resubmission.

Follow-up verification on 2026-09-10 reproduced the old adapter's opaque
failure on a synthetic 10-second brief and identified the wire-schema mismatch
above. After correcting the transport, a second real submission still failed
with a categorized runtime error and published no audio. The exact remaining
cause was not retained in that run. Successful hosted generation and the full
generated-music-to-video path therefore remain unverified; do not describe
the integration as ready for general use. Raw run artifacts remain in the
user's Reel report directory, not this repository.

A final bounded diagnostic request explicitly reported ZeroGPU quota exhaustion:
180 seconds requested, zero remaining, with a wait of approximately 24 hours.
No further jobs were submitted. This establishes the current quota blocker,
not the cause of the preceding generic runtime failure. Waiting for the stated
reset or using an explicitly authorized personal token is required for another
live attempt; neither guarantees successful generation.

## Verified local ACE-Step API contract

Pinned source: `ace-step/ACE-Step-1.5` commit
`ca1e85fe9430179831e6bc6be790c332190a3866`.

1. `GET /v1/models` returns an envelope with `code: 200`, `error: null`,
   and `data.models`. Each inventory row includes `name`, `is_loaded`, and
   `supported_task_types`. The inventory can contain downloaded-but-unloaded
   models; require `is_loaded: true` and `text2music` support. Do not treat
   missing readiness fields as success or invoke `/v1/init` automatically.
   [Source](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/acestep/api/http/model_service_routes.py#L63-L125).
2. `POST /release_task` accepts `task_type: text2music`, model, prompt,
   `lyrics: "[Instrumental]"`, `audio_format: wav`, duration in seconds,
   `batch_size: 1`, `inference_steps: 8`, `use_random_seed: false`, and seed.
   Instrumentality is derived from lyrics, not a made-up `instrumental` API
   field. Duration is documented as 10-600 seconds.
   [Request fields](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/docs/en/API.md#L136-L205),
   [instrumental detection](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/acestep/api/server_utils.py#L135-L143).
3. Supply BPM, key scale, and time signature; disable `thinking`, `sample_mode`,
   `use_format`, `use_cot_caption`, and `use_cot_language`. `thinking: false`
   alone does not prevent LM metadata completion. A deliberately DiT-only
   deployment can separately configure upstream `ACESTEP_INIT_LLM=false`.
   [Documented LM triggers](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/docs/en/API.md#L160-L180).
4. Submission returns `data.task_id`. Poll `POST /query_result` with
   `{"task_id_list":["id"]}`. `data` is an array of tasks; status `0` is
   queued/running, `1` succeeded, `2` failed. A successful task's `result` is
   itself a JSON-encoded array string. Parse it and read the successful entry's
   `file`. Unknown task IDs can remain status `0`, so use an overall deadline.
   [Protocol](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/docs/en/API.md#L373-L428),
   [implementation](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/acestep/api/http/query_result_service.py).
5. `GET /v1/audio?path=...` returns audio bytes. Resolve the returned URL
   against the selected service; enforce the same origin and exact route.
   Optional service authentication uses an Authorization header.
   [Audio route](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/acestep/api/http/audio_route.py),
   [authentication](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/acestep/api/http/auth.py).

The adapter's loopback-only origin, disabled redirects/proxies, response caps,
deadline, no automatic resubmission, WAV measurement, output hash, protected
filenames, and story-change guard are BabblelabReel safeguards, not upstream claims.
The brief and seed aid reproducibility but do not guarantee identical bytes
across machines or model revisions.

## Hosted option, deliberately deferred

The [official ElevenLabs music skill](https://github.com/elevenlabs/skills/blob/9edcbd4b80ed57b8e07a3f86ea520333969fbc3c/music/SKILL.md)
and [API reference](https://elevenlabs.io/docs/api-reference/music/compose)
describe `POST /v1/music?output_format=mp3_44100_128`, `xi-api-key`,
and a body containing prompt, `music_length_ms`, `model_id: music_v2`,
and `force_instrumental: true`. The simple endpoint returns audio bytes directly,
not a queued task. Milliseconds differ from ACE-Step's seconds.

Before implementing or using it, obtain permission for paid remote generation
and prompt transmission, then check account-specific limits and
[Music Terms](https://elevenlabs.io/music-terms) /
[Model-Specific Terms](https://elevenlabs.io/eleven-music-model-specific-terms).
The source skill's MIT license does not license the service or generated music.
Its video-to-music path uploads video; a sanitized text brief is the more
appropriate future integration boundary for private product work.

## Integration acceptance

Respect requested silence and preserve audio during unrelated repairs. New
video production recommends BGM for direction confirmation and later audition,
unless the brief opts out or supplies audio. Automatic production now uses
licensed-library backup on hosted failure without another switch-confirmation
question; explicit AI-only/local-only requests stay strict. Persist music
separately from speech with source-specific provenance (AI prompt/model/seed
or the library recording's source/license evidence), measured
duration, and a hash. Use deterministic fades and caption-timed ducking.
Reject missing/short/malformed audio and unauthorized download destinations.
Finally listen for mood fit, vocals, speech masking, pumping, clipping, and
musical endings; mocked protocol tests cannot establish those properties.
