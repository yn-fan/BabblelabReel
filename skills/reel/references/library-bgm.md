# Automatic licensed music backup

Use this path when `auto` cannot produce AI music, or when library music is
explicitly requested. Keep the already confirmed direction. Select the best
eligible track automatically; ask no extra question about switching providers.
The user still receives the actual track and mixed preview for the existing
audition gate. Explicit AI-only/local-only, silence, and supplied music win.

## Search by the approved direction

Derive one to eight `libraryTags` from the approved emotion, instrumentation,
and energy using the controlled vocabulary in `scripts/library_bgm.py`. Add
them to `music-brief.json` before direction review/fingerprinting. Tags are
agent-authored abstract musical properties, not keywords copied from private
product material. Users do not select filenames or edit JSON.

Default library acquisition searches Incompetech's current first-party index,
maps its mood/instrument/genre metadata to the approved tags, and downloads
only the selected matching MP3. The research snapshot contained 1,442 records;
that is a discovery pool, not a guarantee that every track is instrumental,
matches a direction, or remains downloadable. This is a public index used by
the artist's site, not a supported public API or permission to bulk mirror.
Follow the adapter's bounded requests and surface service/rate-limit failures.

If this source is unavailable or has no eligible match, the helper attempts
the reviewed Commons directory in `assets/music-library.json`. This secondary
source retains 14 pinned CC0/CC BY recordings. Source failure details remain
in the result/provenance; no source switch requires another user question.

Selection ranks matching tags and requires a source long enough for the composition.
Never claim a metadata match establishes audible quality or precise emotional
changes at scene boundaries. An unmatched direction is a surfaced limitation;
do not silently choose an unrelated track merely to fill the audio slot.
Tags describing mood are editorial inferences; not every musical direction is
covered. Current source metadata verification does not imply successful
download, instrumental-content verification, or audition.

Completion: tags represent the direction and the selected catalog track meets
the duration and matching rules.

## Acquire and preserve the license

The library accepts Incompetech's CC BY 4.0 originals and reviewed Wikimedia
Commons CC0/CC BY 3.0/4.0 recordings whose source checks pass.
Recheck the original page/license and file
identity at acquisition, use bounded official requests, and verify hashes.
Keep the creator, title, source URLs, source revision, license URL, verification
time, and selection rationale. Incompetech uses its ISRC, current catalog and
license-page hashes instead of a fabricated Commons revision. Its required
composer/site credit is `Kevin MacLeod (incompetech.com)`. CC0 removes attribution requirements, but source
credit remains useful provenance. Check both composition and recording rights;
a public-domain composition alone does not license a newer recording.
Internal corporate use is not presumed noncommercial and is not an exemption
from licensing. NC, ND, and SA licenses remain outside this simplified workflow.

CC BY selection automatically writes a visible end credit with the title,
creator and explicitly credited contributors, license link, source link, and
modification notice. It also writes
`<audio-file>.license.txt` beside the recording. Preserve both in project
handoffs and include the credit in exported video; the provenance validator
rejects missing or changed required credits. The credits component must be
present in existing projects before importing CC BY tracks. MP3 imports also
need the current `validate-music.mjs` and `validate-mp3.mjs` in older projects.
If the user
explicitly prohibits any credits, set `allowAttribution: false` in the approved
brief to skip Incompetech and select CC0-only Commons candidates instead of
removing required credit from a CC BY recording.

`--provider auto` performs this acquisition after one hosted failure. When a
real blocker is already known, for example an unexpired quota failure, use:

```bash
python3 skills/reel/scripts/generate_bgm.py generate --provider auto \
  --known-ai-blocker quota --project "PROJECT_DIR" \
  --brief "PROJECT_DIR/music-brief.json" --name "story-underscore"
```

For an explicitly requested library soundtrack, use `--provider library`.
Neither mode asks for source-switch approval or treats fallback as AI success.
Strict hosted/local commands never fall back.
`--library-source auto` is the default. Use `--library-source incompetech` or
`--library-source commons` only for an explicitly requested source or a scoped
diagnostic; these source overrides do not fall back to another library.

Downloads can be slow and Commons can rate-limit requests. A real 10 MB source
download in the development environment took about six minutes; this is not an
instant or offline guarantee. `--timeout` remains bounded and configurable.
For Commons, to reuse a previously downloaded original, resolve the cache through
`tools/scripts/user_paths.py cache reel`, then pass its `bgm-library` child as
`--library-cache`. Files must be named `<catalog-id>.<audioFormat>`. The cache
is read-only to this helper: it still fetches current license/source metadata
and verifies the original bytes' hash; a corrupt cached file fails rather than
being trusted or silently replaced.

The imported MP3/WAV/FLAC uses the same bounded music track, duration checks,
fades, and narration ducking as generated audio. Preserve the active soundtrack
when preparing a replacement, using the candidate-project workflow in
`ai-bgm.md`. Licensing does not permit changing the user's approved script.

Completion: actual downloaded audio passes source/license/hash and duration
checks, and its `licensed-library-music` sidecar passes project validation.

## Honest delivery

Library provenance uses `provider: incompetech` or `wikimedia-commons`, the exact allowed
license/version and matching `attributionRequired`, with
`allowsProjectRedistribution: true` and source evidence. CC BY also requires
matching `attributionText` and `audio.music.attribution` for visible credits.
It does not contain a model, generation seed, or AI prompt hash.
Record a hosted failure or an explicitly known blocker when fallback occurs.
Source URLs and metadata may be packaged; include downloaded raw audio in a
project only when its validated rights permit redistribution.

If all eligible source attempts fail licensing, download, or duration
verification, stop and report the remaining blockers. Do not expand to NC/ND/SA music,
Pixabay scraping, paid sources, procedural tones, or silence. New catalog
entries need individual rights/source review; report download and audition
status separately rather than implying every catalog entry has been played.

Completion: disclose that library music was used, identify its source/license,
and retain the separate pending/accepted/delegated audition decision. Never
label it as original AI-generated music.
