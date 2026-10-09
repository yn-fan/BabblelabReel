# Specified video acquisition

Use this branch for supplied share URLs/text, not keyword search, account
archiving, playlists, or arbitrary footage editing. It adapts the user-supplied
`video-download.zip` into Reel; its independent skill name and OpenAI agent
registration are intentionally not installed. The helper is
`skills/reel/scripts/download_video.py` under `BABBLELABREEL_ROOT`.

## Bare-link intent gate

When a user supplies a YouTube, Bilibili, Instagram, Douyin, Xiaohongshu or
WeChat Channels video link/share text **without a stated purpose**, ask one
question in their language: "要下载这个视频吗？" Use the host question tool with
choices "下载", "只解析元数据", "暂不处理"; for multiple links ask once about the
supplied batch. Recognize the platform locally; wait for the answer before
network access, dependency preflight, artifact writes or production setup.
Without an answer, keep the operation pending.

For WeChat Channels, state alongside the question that automatic link download
is unavailable and an authorized local export or separate client-assisted path
is needed. Do not promise that choosing download enables automatic capture.

Read the current request and established conversation intent before asking.
An explicit download request or prior scoped confirmation proceeds to the
rights/dependency gates below without a second download-intent question.
Explicit metadata-only, offline identification, summary, analysis, or
reference-treatment requests keep their requested scope; a URL incidental to
those tasks does not trigger a download offer. Reference-film restrictions
still apply. A yes to downloading grants neither reuse rights, installation
permission, browser/cookie access, nor client capture consent.

## Confirmation interaction

Use the host's `ask_user` (or equivalent interactive question tool) with explicit
`choices` for every unresolved consent gate. Ask one scoped question at a time;
reuse permissions already established for these links in the conversation.
For unknown download rights, ask "这条视频的下载权限属于哪种情况？" with choices
"我自己的作品", "已获作者授权", "许可允许下载", "暂不下载". Map the first three
selections to `owned`, `authorized`, and `licensed`; the last stops acquisition.
Dependency installation and exact browser/cookie access retain separate option
questions only when needed. Proceed after the selection without requiring a
typed phrase, a repeated confirmation, or a copy-pasted command.

An unavailable/cancelled question or an automated "user not available; work
autonomously" response is a **host interaction blocker**, not a user's selection.
Keep the pending operation and any earlier permissions; report the blocker once
in one sentence, then pause that operation. Do not repeat the same question on
automatic continuation, claim the user saw a popup, or substitute a demand to
type an authorization phrase. Retry the interactive tool only when the user
explicitly asks to reopen the choices or the host reports interaction restored.
Only a returned selection or an unambiguous voluntary user authorization
satisfies the gate.

## Identify the blocked layer

Before choosing a downloader workaround, distinguish:

| Layer | Evidence and next action |
|---|---|
| Host interaction | No selection was returned and no helper ran: pending consent, not a platform/download failure. In an unavailable interactive host, retain the pending intent and stop only that operation; independent requested diagnostics may continue. |
| Installed capability | Resolve the active `BABBLELABREEL_ROOT`; check that its acquisition reference and helper actually exist. A newer source checkout does not activate them in the installed plugin. Report a source-only fix as such; perform plugin updates only through the authorized update workflow. |
| Local dependencies | Run doctor with the normal interpreter. Existing managed environments are discovered automatically; repair an incomplete environment rather than reinstalling into another directory. |
| Extraction/transport | Only an actual helper invocation establishes a platform error. Preserve its distinct dependency, network, cookie-store, authentication or extractor status. |
| Saved media | A `resolved` metadata result proves extraction, not download. Require the verified local receipt for `downloaded`. |

For a user-requested failure investigation, anonymous `--probe` can isolate
metadata/extractor health without a media download or browser access. It does
not establish download rights or authorize reuse of cookies from another item.
For repository selection or extractor-specific gaps, consult
[video-download-reliability-research.md](video-download-reliability-research.md)
and compare the installed version against its pinned evidence before changing
backends. The host question UI is outside this repository; test definitions
cannot prove that it displays a popup or accepts a choice in the current host.

## Choose and complete one operation

1. **Scope and rights.** Identify the exact supplied links and requested operation.
   Use `--plan` for offline recognition, `--probe` for online metadata only, or
   default mode for a download. Download only owned, explicitly authorized, or
   license-permitted media; establish the applicable rights before setting
   `--rights owned|authorized|licensed`. These flags record a declaration, not
   independent legal verification. A public link is not permission to reuse.
   Preserve Reel's prohibition on downloading/reusing reference-film media;
   use reference URLs only for observation. Never bypass DRM, paywalls, or
   access controls.
2. **Local preflight.** Run `python "<BABBLELABREEL_ROOT>/skills/reel/scripts/download_video.py"
   --doctor` for online work, or the unified `preflight_reel.py --engine download`.
   Add `--metadata-only` to the unified check for probe-only work.
   The helper supports Python 3.9+; the selected yt-dlp runtime must separately
   satisfy its own Python requirements (current releases require Python 3.10+).
   Probe needs yt-dlp; download additionally needs ffmpeg and ffprobe on PATH.
   YouTube may need a supported JS runtime; the helper selects existing Deno,
   then Node, without installing either. A missing JS runtime is advisory, not
   proof every platform is blocked. Doctor never contacts a platform.
   Doctor reports full download readiness; missing ffmpeg/ffprobe does not block
   a metadata-only request when yt-dlp is available.
3. **Bind artifacts.** Before probe/download, load
   `skills/_shared/artifact-routing.md`. Use the host's stable run ID, alias,
   feature and any master bindings; read an existing run manifest before
   continuing. Pass `--run-id`, and the applicable `--alias`, `--feature-name`,
   `--master-skill`, `--master-run-id`, `--master-feature-name`. The helper uses
   `user_paths.py::ArtifactContext`; it does not accept arbitrary output roots.
   Each invocation appends a unique `video-acquisition-*.json` report and indexes
   it in `REPORT_DIR/_manifest.json` (also the owner's manifest for child runs).
   Downloaded media lives under `OUTPUT_DIR/videos/<acquisition-id>/item-N/`.
   Probe intermediates stay in reports; plan/doctor write nothing.
4. **Run once per requested batch.** Supply original share text on **stdin**
   through the host's safe process API, or pipe an already-authorized local
   private input file into the helper. Use argument arrays for options, never
   interpolate share text into shell source. Multiple URLs are deduplicated in
   first-seen order; signed query bytes are preserved in memory and passed to
   yt-dlp on stdin, not child argv. Example option sets:

   ```text
   download_video.py --plan
   download_video.py --probe --run-id <bound-run-id>
   download_video.py --rights owned --run-id <bound-run-id> --timeout 600 --max-mb 2048
   ```

   Pass the same host binding on subsequent calls. `--timeout` bounds each item,
   not the whole batch. `--max-mb` defaults to 2048 MiB per media file; yt-dlp's
   estimate is an early limit, not a hard network/disk quota. The final merged
   file is checked again. Each link selects at most its first video; live and
   upcoming streams are excluded. No playlist or image-post expansion.
   Supply signed URLs separated from adjacent ASCII punctuation/Markdown:
   when a query or fragment exists the helper preserves trailing bytes rather
   than guessing which characters are part of a signature.
5. **Verify and report actual state.** Only `downloaded` includes a local,
   nonempty, contained file validated by ffprobe for a video stream and finite
   positive duration, with measured bytes and SHA-256. `resolved` means curated
   metadata only (video detection, duration and sanitized numeric format
   dimensions/frame rates/bitrates, which can remain unknown). `formats` is
   deduplicated and capped at 256 with an explicit `formats_truncated` flag;
   it is an available-format inventory, not proof of the saved media's quality.
   `planned` proves only offline routing. A zero backend exit, a submitted job,
   CDN URL, stale receipt, audio-only file or screenshot is not a downloaded
   video. Failed items remain explicit alongside successful ones; partial runs
   return nonzero. Return local links only for verified `downloaded` entries.
   Failed/oversized/partial media is not deliverable; cleanup requires explicit
   scope and consent rather than deleting unrelated files.
6. **Reveal the saved file by default.** After successful verification, use the
   host's local file-reveal capability without another confirmation. On macOS,
   call `open -R <verified-absolute-file>`; on Windows, use Explorer's
   `/select,<verified-absolute-file>` argument; on a Linux desktop, open the
   containing directory with `xdg-open`. Pass paths as process arguments, never
   interpolate them into shell source. For a batch, open its acquisition folder
   once if any files succeeded; keep failed items clearly distinguished.
   Respect an explicit no-open request. Probe, plan and failed downloads do not
   trigger file reveal. The helper remains headless: the calling agent owns
   this desktop step. In a remote/headless host or if the opener fails, state
   that limitation once and provide the absolute path and local file link.
   A successful opener command proves only that the OS accepted the request,
   not that a window was visible to the user. Reveal failure does not turn a
   verified download into a failed download or trigger another download.

**Acquisition-only completion:** return each source index, platform, operation
status, measured resolution/duration/size, and verified local file links if any.
Keep the sanitized provenance report discoverable in the manifest. Complete the
file-reveal step, then stop; no Remotion project, story/BGM question, or render.
The helper reports source host plus exact-input SHA-256, never full URLs,
queries, fragments, cookies, raw extractor JSON, titles, or raw stderr.
Correlate to the user's original input by source index/hash. Keep signed source
text and any detailed permission evidence in their existing private/grounding
bindings; do not paste tokens into chat, reports, logs, or commits.

## Dependencies and credentials

The helper uses yt-dlp from the selected Python interpreter (`-m yt_dlp`), then
an existing PATH executable, then the existing
`COPILOT_PLUGIN_DATA/dependencies/reel-video` environment, then
`STATE_DIR/dependencies/reel-video` resolved through `ArtifactContext`.
Managed discovery is read-only: a bounded local version probe checks the
environment before using it. An existing but broken environment returns
`dependency_error`; discovery never installs or silently skips it.
For a missing dependency, report the precise missing tool and ask
for separate installation permission. With that permission, reuse an existing
user-managed environment or place an external venv under
`COPILOT_PLUGIN_DATA/dependencies/reel-video` when the host supplies it; otherwise
use `STATE_DIR/dependencies/reel-video` via `user_paths.py`. Run the helper with
the normal Python; it resolves `bin/python` on POSIX or `Scripts/python.exe` on
Windows inside the existing managed environment. An explicitly chosen custom
environment may still run the helper with its own Python.
Install `yt-dlp[default]` only in that approved environment; provision ffmpeg/
ffprobe and JS runtimes through the user's approved platform/package manager.
Never write the installed plugin cache, merged Knowledge, or a skill-local venv.

`--cookies <Netscape-file>` and `--browser <name>` are mutually exclusive and
require `--allow-auth`, set only after explicit consent to that exact cookie
file/browser login state. Keep credentials in `PRIVATE_DIR`; yt-dlp may update
its cookie jar. A general request to download is not login-state consent.
Use one authorized retry per selected browser for `needs_login`; never auto-read
a browser profile. In the context of a pending download/login blocker, "I have
logged in with Chrome/Safari; download it" authorizes that named browser for
that pending item. Continue without another consent question. Merely mentioning
a browser elsewhere is not authorization. Retain scoped permissions through
retries; a newly named browser may replace a previously blocked one.
When the user identifies a particular Chrome/Firefox/etc. profile, pass
`--browser-profile "Profile 1"` (or its actual simple profile name) with the
authorized browser. The helper accepts a name, not arbitrary paths, keyrings
or container expressions; Safari profile selection is not supported. Without
this option yt-dlp chooses its default profile, which may not be the one the
user logged into. Diagnose that mismatch rather than scanning other profiles.
No credentials go to third-party parsers. Automatic backend switching,
certificate installation, proxy changes and packet capture are not part of
this helper.

## Recovery

| Status | Next action |
|---|---|
| `unsupported_url`, `no_links` | Request a complete supported HTTP(S) share link; don't guess or search for it |
| `missing_dependency` | Name the missing local tools; no automatic installation |
| `dependency_error` | The existing managed environment is invalid or cannot run; request scoped repair, not another blind install |
| `needs_login` | Seek scoped login-state consent, or request an authorized local file |
| `browser_access_denied` | Explain local OS/browser-store access denial; preserve download consent and wait for permission repair or an explicitly selected alternative browser |
| `browser_cookie_error` | Cookie database/profile/decryption failed; diagnose the selected store before asking the user to log in again |
| `site_response_or_verification_blocked` | Douyin's fresh-cookie hint can also mean an incomplete site response or verification challenge, not necessarily a missing login; allow at most one scoped user-assisted retry |
| `requested_quality_unavailable` | The required format was not returned; report available formats with a probe, without silently lowering the requirement |
| `rate_limited` | Stop retries; user may complete verification themselves or retry later |
| `network_error`, `timeout` | Report the network/time limit, not unsupported platform |
| `unavailable` | State the upstream result, without inferring deletion |
| `extractor_or_download_error` | Consult backend limitations below; no silent fallback |
| `no_video_metadata`, `live_not_supported`, `no_video_saved` | Report image/live/filter/size uncertainty; no success claim |
| `validation_failed`, `local_error`, `invalid_request` | Report the fixed reason/type and correct only the identified local issue |
| `needs_wechat_capture` | Explain the client-assisted limitation and prefer an authorized local export |

For platform-specific failure or tool-selection questions, load
[video-acquisition-backends.md](video-acquisition-backends.md). Its candidates
are advisory and do not authorize installing or invoking another backend.

## Quality and operational lessons

Prefer the highest native resolution offered by the current extractor/session,
then the extractor's remaining quality ranking. Preserve source video rather
than re-encoding or enlarging it. Container MP4 and a large file size do not
prove 4K; bitrates across different codecs are not direct quality comparisons.
For an explicit 4K request, inspect the available formats with the approved
login state first using `--probe` and its sanitized numeric format inventory;
keep media URLs and raw metadata private.
Compare the selected format against ffprobe's actual saved dimensions.
Report "highest available through this extractor/login session", not "the
platform has no 4K". If 4K is absent, report the actual maximum and retain any
already-downloaded matching file rather than downloading it again. Seek an
authorized higher-resolution source if needed; never label an upscale native 4K.

For **required** 4K, add `--min-resolution 2160` to the download invocation.
It requires both native dimensions to meet the floor, for landscape or portrait,
and verifies the actual saved dimensions again. Missing dimensions or an
upstream format below that floor cannot report success. Best-available requests
omit this option; a user-approved lower-resolution fallback is a new explicit
decision, not an automatic retry. `--min-resolution` is download-only: use an
unfiltered `--probe` to inspect available numeric formats first.

The September 2026 macOS trial established these bounded observations:

- An external Python environment with `yt-dlp[default]`, existing ffmpeg/
  ffprobe and Node completed one authorized Douyin download with Chrome login
  state. This is not all-platform, all-account or Windows verification.
- Safari cookie access failed with an OS `PermissionError`. The prior generic
  `needs_login` classification hid this distinction. Diagnose using fixed error
  categories only; never print cookie contents or raw extractor errors.
  Logged-in Safari is not proof that the agent can read its cookie store.
  Explain relevant macOS privacy settings without changing them or bypassing
  OS protections; the user may instead authorize another logged-in browser.
- The accessible format inventory topped out at 1288 x 720, 30 fps. The saved
  HEVC video was approximately 46.8 seconds and 5.6 MB, confirmed by ffprobe.
  No 4K variant appeared in that session; this says nothing about the author's
  original file or variants exposed by another authorized source.
- A local file link alone left the user asking where the file was. File reveal
  belongs in completion, not as an optional offer after delivery.
- Later Bilibili triage reached metadata anonymously, reported about 477
  seconds and offered up to 1920 x 1080 at 30 fps in that format inventory;
  it did not download or validate that video's media. The earlier
  bare-link turn had never reached extraction. Separate these two observations
  rather than reporting the unattempted request as a site failure.
- Default Python originally reported missing yt-dlp even though the approved
  external environment was ready. Managed discovery now covers both supported
  dependency locations. Cookie extraction progress originally caused unrelated
  network errors to be labelled `needs_login`; classification now uses the
  actual error line and distinguishes local write and browser-store failures.

These lessons are sanitized operating evidence, not a replay instruction.
Actual share links, private paths, credentials and per-user permission records
stay in the user's run context, outside the distributed skill.

## Optional compression or film handoff

When the user also requested a smaller file or an upload-size limit, hand the
verified local download to [video-compression.md](video-compression.md).
Keep the downloaded original, acquisition receipt and credits; the smaller
transcoded copy gets its own measured output evidence. Compression alone does
not require the film-production steps below.

Only when the user also requested a film, resume Reel's story-first workflow
with its selected production engine. Download-only requests have already
completed and must not enter these steps. Select media by shot/beat purpose;
check the actual license or scoped
permission covers the intended use and editable-project distribution. Record
the rights basis, source index/hash, acquisition report, local file SHA-256,
measured duration and intended shot in `REEL.md`'s source/task contract and
media choices. Check the file still matches the recorded hash and probe it
before reuse; a stale receipt does not prove an unchanged asset.

| Production engine | Handoff |
|---|---|
| Remotion | Register the source in `story.json`, copy only selected verified footage into `public/`, and use a local `staticFile()` reference; retain acquisition evidence privately |
| FFmpeg footage/Vlog | Follow `footage-editing.md`; use verified local files in `edit-plan.json`, bounded source ranges and the existing source ledger; no Remotion scaffold required |
| Jianying | Start from the footage plan and follow `jianying-handoff.md`; carry the source evidence as explicit sidecars and preserve the draft's compatibility/absolute-path limits |

Preserve required author marks, watermarks and attribution. The music
`attribution` field is not a substitute for video-source credits; the agent must
retain all applicable credits when composing overlays or native text tracks.
Keep cookies, signed source text and acquisition intermediates out of all
distributable media/project folders. Reuse the same ArtifactContext/master
binding for acquisition and production; never relocate unrelated user originals.
Acquisition does not prove product behavior, endorsement, license ownership,
or the authenticity of a depicted event.
