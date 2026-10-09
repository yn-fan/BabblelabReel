# Video-editing capability evidence

Verified 2026-09-19. These are external implementation references, not installed
dependencies, runtime instructions, or evidence of successful native export.
BabblelabReel's new local helpers are original implementations; no upstream skill text,
draft schema templates, media, or code is vendored.

## Source snapshots and adoption

| Source | Verified snapshot | License evidence | What Reel adopts |
|---|---|---|---|
| [FFmpeg skill](https://github.com/kajisho5/ffmpeg-skill/tree/195dbd58f2cce1ba65106b4c89724357dd84e6dc) | `195dbd58` | [MIT](https://github.com/kajisho5/ffmpeg-skill/blob/195dbd58f2cce1ba65106b4c89724357dd84e6dc/LICENSE) | Local media measurement, bounded onset-based cut suggestions, explicit transition overlap, audio mixing, caption/filter preflight |
| [Jianying editor skill](https://github.com/luoluoluo22/jianying-editor-skill/tree/32c56928ded4f9e2c2b80e099dc7abb793d2c30b) | `32c56928` | [MIT wrapper plus Apache-2.0 vendored dependency](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/LICENSE) | Optional editable-track handoff with fresh output, explicit compatibility and manual-export boundaries |
| [AI video editing skill](https://github.com/znyupup/ai-video-editing-skill/tree/b6429ab550a64c595dc68d42c47cf2b489a50619) | `b6429ab5` | [MIT](https://github.com/znyupup/ai-video-editing-skill/blob/b6429ab550a64c595dc68d42c47cf2b489a50619/LICENSE) | Observed footage ledger, narrative selection, local contact sheets/storyboard, speech-boundary and finished-video checks |
| [Official Remotion skills](https://github.com/remotion-dev/skills/tree/bbb139d5ba3709b1ffeb27184e9579c681230a08) | `bbb139d5` | No standalone license found in this mirror; link/install with consent rather than redistribute | On-demand official framework mechanics; existing frame-driven Remotion workflow remains the product-film branch |

### FFmpeg: useful measurement, not automatic editorial judgment

The upstream [beat implementation](https://github.com/kajisho5/ffmpeg-skill/blob/195dbd58f2cce1ba65106b4c89724357dd84e6dc/scripts/_common/decision.py)
uses RMS/onset strength, autocorrelation, confidence and onset-supported beats.
[Cut alignment](https://github.com/kajisho5/ffmpeg-skill/blob/195dbd58f2cce1ba65106b4c89724357dd84e6dc/scripts/cut.py)
moves existing cut points within tolerances, not a semantic shot scheduler.
Reel deliberately implements the smaller **measured onset-candidate** contract;
it does not claim BPM/downbeat estimation or the upstream detector's confidence
calibration. Its `snap` proposals operate on output frames, while source ranges
remain separately validated.

The upstream also offers [local transcription backends](https://github.com/kajisho5/ffmpeg-skill/blob/195dbd58f2cce1ba65106b4c89724357dd84e6dc/scripts/_common/asr.py).
Reel does not auto-install ASR/models, arbitrary FFmpeg filters, or every upstream
command. Requested unsupported effects remain explicit instead of ignored.

### Jianying: fork and maintained dependency differ

The supplied skill's [writer](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/vendor/pyJianYingDraft/draft_folder.py)
writes `draft_info.json`; its
[native exporter](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/auto_exporter.py)
explicitly returns `manual_export_required` outside Windows. Its wrapper has
overwrite/recreation defaults that Reel does not adopt.

The independently maintained
[pyJianYingDraft source snapshot](https://github.com/GuanYixuan/pyJianYingDraft/tree/c3318066d964744e2bfc66f75c71745fe8cea52a)
is Apache-2.0 and identifies version `0.3.0`. Its
[demo](https://github.com/GuanYixuan/pyJianYingDraft/blob/c3318066d964744e2bfc66f75c71745fe8cea52a/demo.py)
uses `TrackSpec` / `append_tracks`; its writer uses `draft_content.json`.
That source API is not a guarantee that a PyPI artifact carrying the same version
has identical methods. A dependency/API probe is mandatory.

Native [audio fades/keyframes](https://github.com/GuanYixuan/pyJianYingDraft/blob/c3318066d964744e2bfc66f75c71745fe8cea52a/pyJianYingDraft/audio_segment.py)
and [visual filters/transitions](https://github.com/GuanYixuan/pyJianYingDraft/blob/c3318066d964744e2bfc66f75c71745fe8cea52a/pyJianYingDraft/video_segment.py)
are source-verified APIs. They do not establish equivalence to FFmpeg sidechain
ducking or its overlapping transition timeline; same-track overlap is rejected
by the draft library. Effects must be registered before segment insertion.

The upstream [platform and export documentation](https://github.com/GuanYixuan/pyJianYingDraft/blob/c3318066d964744e2bfc66f75c71745fe8cea52a/README.md)
is more conservative than the skill fork: Mac/Linux can generate drafts, but
the documented export path relies on Windows Jianying. Current Mac import
compatibility is **unverified**, not implied by draft generation. Neither source
establishes international CapCut compatibility.

### Vlog: source review and privacy matter

The supplied project's
[storyboard helper](https://github.com/znyupup/ai-video-editing-skill/blob/b6429ab550a64c595dc68d42c47cf2b489a50619/scripts/gen_storyboard.py)
extracts source frames into an HTML preview. Its
[skill](https://github.com/znyupup/ai-video-editing-skill/blob/b6429ab550a64c595dc68d42c47cf2b489a50619/SKILL.md)
also describes external visual-model uploads and local ASR model downloads.
Reel adopts the analysis-to-storyboard workflow, not those provider assumptions.
Host vision is used only when actually available; third-party footage upload
and optional model acquisition remain consent-gated.

### Remotion: preserve the official owner

See `remotion-integration.md` for relevant official skills, version discipline,
transition timing and licensing. Topics such as transitions, audio and timing
are reference documents, not invented skill names. The public skills repository
does not grant a blanket enterprise license for the Remotion rendering runtime.
