# Video TalkCraft reference study

Research date: 2026-09-04

Source revision:
[`Vincentwei1021/video-talkcraft@6c43c0f`](https://github.com/Vincentwei1021/video-talkcraft/tree/6c43c0f8c7f260d372610c25ac9587f720db8d14)

## Boundary

Video TalkCraft is useful as public evidence of a narration-first Remotion
workflow, but its repository uses the
[PolyForm Noncommercial 1.0.0 license](https://github.com/Vincentwei1021/video-talkcraft/blob/6c43c0f8c7f260d372610c25ac9587f720db8d14/LICENSE).
Do not copy its source, templates, cards, prose, media, sound effects, or
workbench into BabblelabReel. Reel independently implements general production ideas and
keeps its own neutral visual, product-correctness, and repository contracts.

## Transferable architecture

The strongest reusable idea is that editorial timing should be data rather than
scattered component constants. TalkCraft separates narration timing, shot
ranges, camera state, and review automation across its
[`timing.ts`](https://github.com/Vincentwei1021/video-talkcraft/blob/6c43c0f8c7f260d372610c25ac9587f720db8d14/template/motion-systems/timing.ts),
[`shots.ts`](https://github.com/Vincentwei1021/video-talkcraft/blob/6c43c0f8c7f260d372610c25ac9587f720db8d14/template/motion-systems/shots.ts),
and
[`qa_extract.py`](https://github.com/Vincentwei1021/video-talkcraft/blob/6c43c0f8c7f260d372610c25ac9587f720db8d14/scripts/qa_extract.py).

Reel adopts the principle through independently authored contracts:

| Idea | Reel implementation |
|---|---|
| One editorial timeline | `story.json` stores scenes, absolute shots, beats, caption cues, and measured narration |
| Spoken-word alignment | Speech beats carry a verbatim narration anchor; the validator checks the substring |
| Shot-level planning | Contiguous shot ranges cover every scene and record subject, camera, action, hold, and boundary |
| Playback-layer captions | `CaptionTrack.tsx` selects phrase cues by absolute frame |
| Repeatable visual review | `qa:plan` creates opening, boundary, hold, caption, and final-frame anchors |

## Patterns Reel intentionally rejects

Do not transfer a universal always-moving rule, a prohibition on clean cuts, a
fixed pastel or Apple-like visual system, or sample-specific camera and
environment timings. These conflict with Reel's source-first treatment model and
its requirement that dense product UI settle to exact geometry.

Do not adopt source-similarity checks like TalkCraft's
[`card_lint.py`](https://github.com/Vincentwei1021/video-talkcraft/blob/6c43c0f8c7f260d372610c25ac9587f720db8d14/scripts/card_lint.py).
Reel validates behavior, timing, readability, evidence, and output—not textual
similarity to another creator's implementation.

Defer a full timeline workbench until repeated production evidence justifies the
maintenance cost. Remotion Studio plus a schema-validated story and deterministic
review manifest provides the useful control surface without turning BabblelabReel into a
separate editor application.
