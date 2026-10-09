# Local video compression

Use for "make this video smaller", email/upload limits, a required MB ceiling,
or a smaller delivery copy of a finished Reel. FFmpeg is the media engine,
not a separately installed agent skill. Reuse the local executable; no upstream
source checkout, cloud upload, npm package or model is needed.

## 1. Resolve the source and requested constraint

For a local file, compress only the selected source. For a remote link, first
follow `video-acquisition.md` with its rights/authentication gates; carry only
verified local files and their source receipts forward. Explicit download-and-
compress intent needs no repeated intent question. Compression does not grant
reuse rights or authorize publishing the result.

Use these two modes:

- **Smaller copy:** default constant-quality encoding; actual output must be
  smaller than the input to count as success. Do not promise a percentage saving.
- **Size ceiling:** interpret MB as decimal 1,000,000 bytes; preserve an explicit
  user-supplied byte limit exactly. Two-pass bitrate budgeting is an estimate
  until the complete encoded file passes the measured ceiling.

Keep full duration, frame cadence, dimensions and audio by default. Downscale
only when requested, using a maximum height that never upscales. A user asking
for "no quality loss" has not authorized lossy encoding: explain this branch's
H.264/AAC tradeoff and obtain agreement, rather than labeling it lossless.
Do not reduce resolution, remove sound/tracks, trim footage or discard captions
to satisfy a size limit without a separate explicit decision.

Compression-only requests exit through this reference. No `REEL.md` story lock,
Remotion scaffold, editing plan, soundtrack selection or narration synthesis is
required. For an existing production, compress the verified final master rather
than changing its timeline or repeatedly recompressing intermediates.

## 2. Check only the local compression tools

```bash
python3 "{BABBLELABREEL_ROOT}/skills/reel/scripts/preflight_reel.py" --engine compress
```

Python 3.9+, FFmpeg with libx264/AAC, and ffprobe are required. Missing tools
block compression, not independent planning; request scoped installation
consent instead of downloading binaries automatically. Readiness proves only
the local capabilities, not source compatibility or successful compression.

The helper supports a deliberately bounded subset of ordinary SDR video.
Version 1 accepts a single progressive 8-bit YUV420, constant-frame-rate stream
(1–60 fps), even square-pixel dimensions, and up to eight supported mono/stereo
audio tracks. Sources are bounded to 4 GiB and one hour. See `--help` for exact
geometry, sample-rate and timing limits. Rotation, variable frame rate,
HDR/10-bit, embedded captions/subtitle tracks, chapters and extra non-audio
streams are blocked; burned-in captions remain part of the image.
Unsupported stream arrangements, geometry, color or timing must remain explicit
blockers; FFmpeg supporting a format does not mean this wrapper preserves it.
Use the helper's error to explain the specific issue. Keep the original and
request an appropriate conversion decision; never silently flatten HDR or
discard subtitle/data/attachment tracks.

## 3. Write a separate compressed copy

Resolve the normal Reel ArtifactContext before the first output write. Use the
existing run/master binding for child compression. Create the bound output
parent and choose a fresh name, normally `OUTPUT_DIR/{slug}/out/compressed.mp4`.
An explicitly authorized existing project destination follows that project's
boundaries. Do not write into BabblelabReel's source/plugin tree or overwrite originals.

```bash
# Smaller copy using the default quality setting
python3 "{BABBLELABREEL_ROOT}/skills/reel/scripts/compress_video.py" "input.mp4" \
  --output "OUTPUT_DIR/{slug}/out/compressed.mp4"

# Complete file no larger than 20,000,000 bytes
python3 "{BABBLELABREEL_ROOT}/skills/reel/scripts/compress_video.py" "input.mp4" \
  --output "OUTPUT_DIR/{slug}/out/under-20mb.mp4" --target-mb 20

# Only when the user requested downscaling
python3 "{BABBLELABREEL_ROOT}/skills/reel/scripts/compress_video.py" "input.mp4" \
  --output "OUTPUT_DIR/{slug}/out/720-high.mp4" --max-height 720
```

Use `--help` for supported controls. Users need not supply codec flags or CRF
numbers. Quality and size-ceiling modes are distinct; a bitrate estimate is
not a byte-limit guarantee. Do not use FFmpeg `-fs` or `-t` to force compliance:
stopping writes/ending the movie early fails full-content preservation.

The helper stages encodes, validates the actual media and publishes without
overwriting. A too-large file, no savings, unsupported input, encoder failure
or failed verification must remain a failure, not a delivered "compressed"
file. Respect the helper's bounded retries; ask about relaxing an infeasible
constraint rather than launching an unbounded re-encode loop.

## 4. Verify, preserve credits and deliver

Require successful full decoding and measured output duration, geometry,
frame/audio continuity and size. Technical verification is not perceptual QA:
inspect readable UI/caption text and high-motion sections; listen to speech and
the ending using available host tools. Report any playback inspection that
could not be performed instead of claiming unchanged quality.

Preserve the source/acquisition receipt and every applicable credit, license
and attribution sidecar. Keep them associated with the compressed copy; the
helper copies the canonical source's `.licenses.txt` companion verbatim and
without overwrite, but other external credits are the caller's responsibility.
General container metadata is not copied: carry relevant author/source/rights
information into the retained provenance, rather than relying on MP4 tags.
The helper is not a rights validator. Source SHA-256 and the new output hash refer
to different files: add derived-output provenance, never rewrite a downloaded
source's receipt to describe the transcode.

Append the output and truthful helper result to the bound `REPORT_DIR/_manifest.json`
using the normal artifact contract. Report a local output link, before/after
bytes, percentage saved, actual dimensions/duration, mode and any loss/limits.
A requested ceiling passes only when actual bytes meet it and the full content
checks also pass. Keep the original and editable master.

## Upstream evidence and dependency boundary

- [FFmpeg/FFmpeg](https://github.com/FFmpeg/FFmpeg) is the user-supplied upstream
  media-tool repository, not a Copilot skill package.
- [FFmpeg manual](https://ffmpeg.org/ffmpeg.html) documents stream mapping,
  two-pass `-pass` / `-passlogfile`, rotation and output options. Its `-fs`
  description warns that the resulting file can exceed the requested byte
  limit; it is not a valid complete-video size-ceiling implementation.
- [libx264 options](https://ffmpeg.org/ffmpeg-codecs.html#libx264_002c-libx264rgb)
  document constant-quality CRF and bitrate controls; CRF does not target a
  fixed final file size.
- [FFmpeg legal notes](https://ffmpeg.org/legal.html) govern the selected build's
  licensing. This integration invokes an independently installed executable;
  it does not vendor FFmpeg/x264 source or binaries or determine the user's
  codec/distribution rights.
