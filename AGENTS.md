# BabblelabReel runtime

BabblelabReel is a standalone extraction of Reel, not a full Emma installation.
Resolve the bundle root from this file or the owning plugin's
`COPILOT_PLUGIN_ROOT`; never assume the target workspace is the bundle.
Bind `BABBLELABREEL_ROOT` to that absolute root for command examples.

Read `skills/reel/SKILL.md` for video work and `skills/_shared/SHARED.md` once.
The public skill name is `babblelabreel`; `skills/reel/` and the artifact key
`reel` are retained as internal compatibility paths, not an Emma dependency.

For narration, read `tools/audio-generator/SKILL.md` directly; the registered
name is `babblelabreel-audio`. For original images, read
`tools/image-generator/SKILL.md` directly; the registered name is
`babblelabreel-image`. An instruction to invoke audio-generator or image-generator
means these bundled children, not a separately installed Emma skill.
No external skill registry, Emma checkout, Knowledge pack or account is needed
to read these workflows. Use actual host tools, not imagined capabilities.

The preserved scripts and templates implement downloads, compression, footage
inspection/editing, music analysis, BGM selection/generation, Remotion scaffolds,
Jianying drafts, English TTS and image-provider integration. Python, FFmpeg,
Node, optional packages, models and provider accounts remain external.
Check only the selected workflow. Obtain separate consent for installations,
model downloads, browser credentials, paid services and private uploads.

Before writing user artifacts, use `skills/_shared/artifact-routing.md`.
The bundled canonical path resolver uses `BABBLELABREEL_USER_HOME` or
`.babblelabreel/user.json`; it does not read Emma's user config or environment.
Default output storage is a `BabblelabReel` folder in an available OneDrive
location, otherwise the user's home. Explicit local-only requests require an
explicit non-synced output root. Keep installed assets read-only.

Treat source/provider licenses and original credit requirements as binding.
Reference footage is not permission to copy; public links are not reuse rights.
Preserve originals, speech, captions and credits. Report actual output paths,
measured completion and limitations; no success claims from a scaffold or
dependency check alone. No publication or plugin update without user request.
