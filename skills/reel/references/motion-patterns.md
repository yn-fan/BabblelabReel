# Reel motion pattern library

## Contents

- Plan motion before code
- Cinematic frame hierarchy and captions
- Stability model
- Transition and entrance patterns
- Product UI choreography
- Generated-image and ambient motion
- Timing guidance and Remotion recipes
- Review checklist

Use motion to explain change, preserve context, and direct attention. More
animation is valuable when it makes the story easier to follow; motion that
competes with narration or UI content makes a reel feel less polished.

## Plan motion before code

Add these fields to each shot in `story.json` and mirror them in `REEL.md`:

| Field | Question |
|---|---|
| Entrance | How does the viewer discover this scene? |
| Primary action | What changes their understanding? |
| Secondary motion | What supports the action without competing? |
| Hold | How long is the final state readable? |
| Exit | What visual relationship leads to the next scene? |

Use three timing domains deliberately:

1. **Scene time** defines narrative coverage and composition duration.
2. **Absolute shot and beat time** lets validation compare visuals, captions,
   and spoken phrases on one timeline.
3. **Component-local time** starts at zero inside a `Sequence` and should be
   derived at the boundary instead of stored as another source of truth.

Every shot should contain at least one beat that changes attention,
understanding, product state, or continuity. A beat can align to a verbatim
spoken anchor, but narration does not require constant animation.

For a typical 45–60 second reel, combine:

- one slow camera move per beat;
- one meaningful UI or content action;
- restrained continuous background motion;
- a readable hold after the action;
- only the transitions needed to explain chapter or spatial relationships.

Do not force all five into a short title card. Quiet beats create contrast for
high-motion moments.

Keep transition frequency lower than scene frequency. Most cuts should be clean
or resolved through content choreography; use a full-frame transition only at a
meaningful chapter change. Repeating one wipe on every cut makes the transition
itself the story.

## Cinematic frame hierarchy

A reel is watched in time; it should not require the viewer to scan a slide.
Build each shot from these layers:

1. **Dominant subject** — one product crop, person, object, action, or claim.
2. **Supporting context** — at most two subdued groups that explain the subject.
3. **Subtitle layer** — open lower-third text that does not resemble product UI.

At 1080p, the dominant subject should occupy roughly 55–80% of the usable frame.
Avoid shrinking an entire application, browser, title, progress rail, caption
card, and multiple callouts into one composition. When several UI regions matter,
show them as successive shots or camera crops.

Use the thumbnail test: reduce the frame until details disappear. If no single
shape or subject dominates, the composition is too distributed. Use the squint
test for contrast: the eye should land on the intended action before titles,
labels, or decoration.

Persistent chrome is usually presentation grammar. Remove repeated step pills,
stage trackers, author blocks, and title bars unless they are real product UI.
Show scene titles briefly, then clear the frame for the action.

## Captions

Captions are a playback layer, not another card in the composition:

- use an open lower third, centered or left-aligned to the shot;
- keep to one or two lines and roughly 28–42px at 1080p;
- use sentence case and natural phrase breaks;
- protect contrast with text shadow, outline, or a subtle full-width gradient
  scrim;
- keep generous bottom safe area and avoid covering the demonstrated action;
- do not use a rounded rectangle, border, drop-shadow card, speech bubble, or
  persistent footer panel for routine narration.

If a caption needs a large opaque box to remain readable, simplify or reframe
the shot behind it.

## Stability model

Assign each animated element to one plane before implementation:

| Plane | Contains | Motion rule |
|---|---|---|
| Stable content | Product windows, captions, tables, dense cards, one-pixel borders | May enter, then resolves to exact final geometry for the readable hold |
| Focused action | Cursor, selected row, progress fill, typed text, active control | Moves only while demonstrating the product action |
| Ambient | Light fields, texture, sparse particles, decorative objects | May move continuously at low contrast without transforming stable content |
| Transition | Masks, shutters, veils, shared elements | Exists only near a justified scene or chapter boundary |

Keep transforms on the narrowest useful element. A scene-level camera transform
combined with a component-level entrance creates nested fractional coordinates,
so movement that looks small in code can make the entire UI shimmer.

Hard-settle entrances before the hold. Springs approach their destination
asymptotically and can leave a barely visible tail; after the planned settle
frame, return the exact final transform rather than continuing to evaluate the
spring. During a hold, prefer no parent `transform` property over a mathematically
equivalent fractional transform.

Use a motion budget for dense UI:

- one parent entrance, ending before reading begins;
- focused child animation only while the state changes;
- no continuous parent scale, sinusoidal float, or parallax;
- no scale pulse on text, borders, captions, or progress rails;
- whole-pixel settled positions for crisp rasterization;
- ambient movement behind or outside the product surface.

## Transition selection

Choose by narrative relationship rather than novelty.

| Relationship | Pattern | Use when | Avoid when |
|---|---|---|---|
| Same object, new state | Shared-element move | A prompt becomes a result, a card opens, or a selection becomes detail | Geometry cannot align convincingly |
| Cause to effect | Match cut | Shapes, cursor position, or composition can bridge the action | The visual similarity is weak |
| Forward progression | Directional push | Moving through workflow steps or chronological stages | Adjacent scenes have unrelated layouts |
| Hidden to revealed | Mask or curtain wipe | Revealing UI, a proof point, or a new environment | Dense content needs immediate reading |
| Macro to detail | Depth zoom | Moving from claim to interface or from page to component | Text would blur or scale excessively |
| Parallel ideas | Split or cross dissolve | Comparing options or showing simultaneous inputs | A hard decision or causal change is needed |
| Reset or emphasis | Clean cut | A proof point, contradiction, or conclusion should land sharply | Continuity between scenes matters |
| Completion | Settle and breathe | CTA, approval, or final package | The beat still contains unfinished action |

Use a transition seam that exists on both sides of the cut. For example, an
outgoing color curtain should fully cover the final outgoing frame and begin
fully covering the first incoming frame before sliding away. This prevents a
blank flash between `Sequence` segments.

Do not rotate through a generic color array. Use the destination section's
established accent, or a pale neutral surface with a thin brand accent. Avoid
full-screen saturated green, orange, red, or purple unless the brand or story
explicitly calls for that color and the transition is a deliberate focal moment.

## Entrance patterns

- **Mask reveal:** animate `clipPath` or an overflow-hidden child to reveal
  content without moving the whole layout.
- **Depth settle:** combine a small scale change with opacity and 8–24 pixels of
  travel. Keep perspective subtle.
- **Staggered hierarchy:** reveal title, primary surface, then supporting details
  at 4–8 frame intervals.
- **Draw-on:** animate SVG stroke dash offset for paths, connectors, or diagrams.
- **Focus rack:** lower opacity or add slight blur to secondary surfaces while
  the primary item resolves sharply.
- **Split assembly:** move two related panels from opposite directions and let
  them lock into one layout.

Avoid sending every item upward from the same distance. Vary direction and
timing according to layout and reading order.

## Product UI choreography

Product scenes should demonstrate state changes, not just display screenshots.
The source-backed task contract decides which states are valid; motion may
explain those states but must not invent product behavior.

- Type text at a readable cadence, pause, then submit.
- Move a cursor toward the next action before the UI changes.
- Animate hover, press, loading, success, and resulting content as distinct
  states.
- Show an acknowledgement between input and result when the product provides
  one; do not jump from click to success merely because it animates cleanly.
- Represent error, empty, permission, undo, overflow, or responsive behavior
  when it is part of the demonstrated task.
- Reveal lists or rows in reading order.
- Interpolate progress bars and numeric counters rather than showing final
  values immediately.
- Use a controlled crop or camera push for small details instead of enlarging
  every label.
- Once dense UI is readable, keep its parent container stable on whole-pixel
  coordinates. Continuous subpixel translation or scale makes text, one-pixel
  borders, and shadows appear to shake.
- Do not apply sinusoidal floating motion to an entire product window. Move
  ambient layers or a focused child element instead.
- End entrance springs explicitly. Do not let a low-amplitude spring tail run
  through the readable hold.
- Avoid nested camera and component transforms on text-heavy surfaces. If a
  camera move is necessary, finish it before revealing fine text and borders.
- Use opacity or glow for an active pulse instead of repeatedly scaling the
  control's parent.
- Let the completed state hold for at least 1–2 seconds.
- Keep cursor paths short and intentional; remove the cursor when it is not
  guiding attention.

For supplied recordings, use time remapping, crop changes, and callout overlays
sparingly. Do not fake product behavior that the source does not show.

## Generated-image motion

Raster imagery still benefits from deterministic motion:

- use a slow Ken Burns pan or push over 3–7 seconds;
- separate foreground and background only when masks or layered source assets
  support credible parallax;
- animate light overlays or atmospheric particles independently from the image;
- transition from a real-world object or screen shape into matching product UI
  geometry;
- avoid large zooms that expose generation artifacts.

Generate enough resolution for the largest crop used in the composition.

## Ambient motion

Ambient motion should be visible when watched for a few seconds, not distracting
at a glance:

- gradient or light-field drift;
- grid or texture translation;
- low-count particles with deterministic paths;
- gentle floating of decorative objects;
- subtle active-state pulse;
- moving sheen used once per scene, not continuously.

Keep ambient motion slower than interactive motion and lower in contrast.

## Timing guidance

- Fast UI response: 6–12 frames.
- Entrance or exit: 10–24 frames.
- Cursor travel: 12–30 frames.
- Typed prompt: about 6–10 characters per second unless intentionally accelerated.
- Major camera move: 30–90 frames.
- Readable hold: at least 30–60 frames depending on density.
- CTA hold: at least 60 frames.

Time to narration beats rather than distributing animation evenly. Put important
changes just before or on the emphasized word so the viewer has time to see the
result. Record the spoken substring as a `speech` beat anchor rather than
estimating its location again inside the component.

## Remotion recipes

### Spring entrance

```tsx
const settleFrame = delay + 20;
const progress = frame >= settleFrame ? 1 : spring({
  frame: frame - delay,
  fps,
  durationInFrames: 20,
  config: {damping: 22, stiffness: 120, mass: 0.9},
});

const style = {
  opacity: progress,
  transform: `translateY(${interpolate(progress, [0, 1], [24, 0])}px)
    scale(${interpolate(progress, [0, 1], [0.97, 1])})`,
};
```

The explicit settle frame prevents an asymptotic spring tail from moving dense
content during its hold. Apply this transform to the entering component, not to
an ancestor that also contains already-readable UI.

### Mask reveal

```tsx
const reveal = interpolate(frame, [start, start + 20], [0, 100], {
  extrapolateLeft: 'clamp',
  extrapolateRight: 'clamp',
});

const style = {
  clipPath: `inset(0 ${100 - reveal}% 0 0 round 18px)`,
};
```

### Type and submit

```tsx
const characters = Math.floor(
  interpolate(frame, [typeStart, typeEnd], [0, prompt.length], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  }),
);
const visiblePrompt = prompt.slice(0, characters);
const submitted = frame >= submitFrame;
```

### Seam-covering wipe

```tsx
const outgoingX = interpolate(
  frame,
  [durationInFrames - 18, durationInFrames - 1],
  [102, 0],
  {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
);
```

Use the next scene's wipe color on the outgoing side and the same color on the
incoming side.

## Review checklist

- Every moving element has a narrative or attention purpose.
- Every product action and state change maps to a recorded source reference.
- Required script phrases appear in order with no unapproved omissions.
- One dominant subject is obvious in every shot at thumbnail size.
- Product UI is shown at a readable crop rather than scaled down to fit a slide.
- Persistent step, title, and progress chrome is absent unless it is product UI.
- Captions read as subtitles and are not enclosed in cards or bubbles.
- Motion hierarchy remains clear when narration is playing.
- Scene boundaries do not flash blank frames.
- Dense UI is stable while the viewer reads it.
- Important states appear long enough to understand.
- Text, borders, and shadows do not shimmer during scale transforms.
- Generated imagery remains sharp at the maximum crop.
- Motion remains deterministic and frame-driven.
- Reduced-motion or static presentation remains understandable when required.

### Stability sampling

Do not rely on one representative still:

1. render the last outgoing, cut, and first incoming frame at every boundary;
2. render two frames 10–15 frames apart from each dense readable hold;
3. compare the hold samples for parent position, scale, border sharpness, and
   text rasterization;
4. inspect source for transforms on scene roots and product-window parents;
5. play the dense scenes and chapter transitions at normal speed.

Background or child-state changes may differ between hold samples. The product
window's outer geometry should not.
