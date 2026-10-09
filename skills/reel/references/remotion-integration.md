# Remotion integration guidance

Framework setup verified 2026-08-27; official skills rechecked 2026-09-19.

## Official sources

- Existing-project installation:
  https://www.remotion.dev/docs/brownfield
- Agent Skills:
  https://www.remotion.dev/docs/ai/skills
- Official Agent Skills repository:
  https://github.com/remotion-dev/skills
- Rendering:
  https://www.remotion.dev/docs/cli/render

## BabblelabReel repository strategy

BabblelabReel has no root application package. Do not create a root `package.json` or
install Remotion at repository root.

Keep the integration layered:

1. `skills/reel/SKILL.md` owns the workflow and quality contract.
2. `skills/reel/assets/remotion-starter/` is a version-pinned, source-owned
   scaffold.
3. `skills/reel/scripts/scaffold_reel.py` safely materializes that scaffold into
   `OUTPUT_DIR/{slug}`.
4. Generated projects install and render from their own package root.
5. Existing user repositories receive Remotion only in the affected package or
   workspace.

This avoids coupling BabblelabReel's Python/control-plane tooling to Node and keeps large
render dependencies out of plugin installation.

## Existing application

For a brownfield React or Node project:

1. inspect the package manager, workspace boundaries, Node version, TypeScript
   setup, and existing `remotion` path aliases;
2. choose a dedicated `remotion/` or `video/` source folder;
3. add `remotion` and `@remotion/cli` at the same exact version;
4. add only the capabilities that are needed:
   - `@remotion/player` for playback inside a React app;
   - `@remotion/renderer` for Node-side rendering;
   - `@remotion/media` for video and audio;
   - `@remotion/lambda` only for an approved Lambda architecture;
5. add workspace-local `studio`, `compositions`, `still`, and `render` scripts;
6. use a dedicated `public/` asset subtree and `staticFile()`;
7. enable the Remotion ESLint rules if the repository already uses ESLint.

Avoid a generic "editor" integration unless the product actually needs users to
edit videos. A product reel needs compositions and rendering, not a SaaS editor.

## Version discipline

All `remotion` and `@remotion/*` packages must share an exact version. The
bundled scaffold uses `4.0.514`, the newest stable package verified on npm when
this reference was written. Remotion's docs repository was already describing
`4.0.518`, which was not publicly installable from npm at that time.

Update the scaffold deliberately:

1. inspect npm distribution tags;
2. choose a stable release, not an alpha unless the user requests prerelease
   behavior;
3. update every Remotion package together;
4. reinstall and render the starter;
5. run BabblelabReel's control-plane checks.

## Agent support

Official Remotion Agent Skills can be installed into a target repository with:

```bash
npx skills add remotion-dev/skills
```

Do this only with user approval because it writes agent configuration to the
target. At source snapshot `bbb139d5ba3709b1ffeb27184e9579c681230a08`, the most relevant
official skills are:

- `remotion-best-practices` as the official task router;
- `remotion-create` for new projects;
- `remotion-markup` for frame-driven markup, media, timing, and transitions;
- `remotion-captions` for timed caption data and authorized transcription;
- `remotion-multimedia` for media tooling;
- `remotion-studio` for preview;
- `remotion-render` for export;
- `remotion-docs` for current API lookup.

Reel remains the story-and-craft orchestrator. Official skills supply current
framework mechanics. Load only the selected task's skill/reference, not the
entire upstream library. Use installed official skills when present; otherwise
consult the corresponding official source on demand. Installation is optional
and requires approval, not a prerequisite for using Reel's existing scaffold.

For mixed video, animated titles, captions, or crossfades, consult
[`remotion-markup`](https://github.com/remotion-dev/skills/tree/bbb139d5ba3709b1ffeb27184e9579c681230a08/skills/remotion-markup)
and [`remotion-captions`](https://github.com/remotion-dev/skills/tree/bbb139d5ba3709b1ffeb27184e9579c681230a08/skills/remotion-captions)
as needed. Source trim time, composition time and segment-local frame time are
different coordinates. `TransitionSeries` overlap subtracts from the timeline;
overlay transitions do not. Recompute duration and caption positions whenever
overlap changes, and verify boundary frames. Captions may use the official
`text/startMs/endMs/timestampMs/confidence` format at an integration boundary;
convert explicitly to Reel's frame-based cues rather than relabeling units.
Installing/transcribing with Whisper remains optional and consent-gated.

## Licensing and upstream boundaries

The skills mirror has no explicit standalone license at the verified snapshot.
Link or install the official package with consent rather than vendoring its
text. The [Remotion runtime license](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md)
is separate: organizational/commercial use may require a Company License.
Internal corporate video production is not automatically exempt. Verify the
user organization's entitlement before production deployment; do not imply
that public skill access licenses the runtime.

For the full four-project comparison and source evidence, load
`video-editing-integrations.md` when evaluating reuse or revising these adapters.

## Validation ladder

Use the cheapest useful proof first:

1. TypeScript check.
2. Composition enumeration.
3. Representative stills, including scene boundaries.
4. Generate `out/review-plan.json` with `npm run qa:plan`, then render its
   opening burst, boundary triplets, readable-hold pairs, caption samples, and
   final frame.
5. Studio inspection.
6. Full render when requested.
7. `ffprobe` metadata and sampled-frame review of the final MP4.

Do not run a full render after every copy edit. Do not call a project complete
from static checks when the deliverable is the MP4.
