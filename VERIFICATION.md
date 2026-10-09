# Export verification

Verified on macOS on 2026-10-09. This is a local standalone snapshot of the
source commit recorded in `PROVENANCE.json`, not a claim to track future Emma
releases.

- Entire tracked Reel tree included, including scripts, assets, Remotion
  template, references and evaluations; complete audio/image child trees and
  their runtime-path dependencies included.
- Reel: 272 tests, 271 passed, one existing libass-dependent skip.
- Audio: 23 tests on existing Python 3.13, 22 passed, one opt-in live
  model-integration skip. The system Python 3.9 is below Audio Generator's
  minimum; it is suitable for the Reel helpers but not all audio paths.
- Images: six offline tests passed.
- Actual local fixture rendering/compression is covered by Reel regressions.
  Compression dependency preflight passed on this machine.
- Relocated bundle ran with all `EMMA_*` environment variables removed:
  compression preflight, offline URL planning and isolated output resolution
  succeeded without reading an Emma checkout or config.
- Native Copilot local-marketplace installation succeeded in a temporary,
  offline `COPILOT_HOME`. Native skill listing recognized `babblelabreel`,
  `babblelabreel-audio` and `babblelabreel-image`. This CLI loads local
  marketplace plugins live from their directory rather than copying them.
  Keep the directory present after installation.
- Local Markdown links resolve within the package; no symbolic links.

No production user video, credentials, browser profile, downloaded model,
music recording or optional dependency environment was copied. No real
user plugin registration was changed. No provider generation/download or
native Jianying opening/export was performed during packaging.

Compatibility and prerequisite checks do not prove live provider availability,
model synthesis quality, visual review or native editor compatibility.
