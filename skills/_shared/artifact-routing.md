# Standalone artifact routing

Use the bundled `tools/scripts/user_paths.py::ArtifactContext`, which delegates
to `runtime_config.py`. No external Emma installation is consulted.
The namespace is `BABBLELABREEL_USER_HOME`, `BABBLELABREEL_STATE_HOME`,
`BABBLELABREEL_USER_ALIAS`, and `.babblelabreel/user.json`.
The public name is BabblelabReel; the existing artifact skill keys `reel`,
`audio-generator` and `image-generator` remain internal compatibility keys.

Resolve an output root or report run from the package root:

```bash
python3 tools/scripts/user_paths.py output reel
python3 tools/scripts/user_paths.py report reel --run-id RUN_ID
```

`OUTPUT_DIR` holds final media/projects. `REPORT_DIR` holds safe reports and
`_manifest.json`; `CACHE_DIR` holds regenerable data; `STATE_DIR` holds durable
configuration; `GROUNDING_DIR` holds approved source material; `PRIVATE_DIR`
holds secrets/authentication. Follow the helper's accepted flags for feature
and master/child binding. Keep one stable run ID and propagate master binding
to children where supported. Audio/image standalone scripts retain their
canonical child output paths; register those files in the parent manifest.

Read an existing manifest before appending. Preserve its artifacts and run
identity; register paths relative to the report where supported and otherwise
use the helper's proven external artifact location. Never replace prior
receipts with claims about new outputs. Keep signed source URLs/cookies out of
shareable receipts. Explicit user destinations are honored for supported
helpers after path validation; other helpers use the canonical resolver.

Default storage may be in OneDrive. For private local-only work, select a
non-synced absolute `BABBLELABREEL_USER_HOME` before creating artifacts. Validate
and create only the resolved directory. Keep outputs outside installed assets.
No credentials, private host mappings or user content belong in this package.
