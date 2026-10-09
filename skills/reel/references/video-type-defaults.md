# Reel optimized video defaults

Use these presets when the user's intent clearly matches and the brief does not
provide conflicting direction. A preset is a production starting point, not a
theme: supplied product behavior, brand, evidence, script, and delivery
requirements still take precedence.

Do not blend presets by default. Record the selected preset and every deliberate
override in `REEL.md` and `story.json`.

## Product launch video

Use for a new product, feature, capability, or major improvement that needs to
be understood and believed. Tim Kochjar's public Remotion demo belongs to this
type; its creator-specific visual treatment remains optional.

### Default contract

| Dimension | Optimized default |
|---|---|
| Viewer outcome | Understand one promise, see it work, and remember one credible reason to care |
| Duration | Target 60 seconds; normally 45–90 seconds |
| Format | 16:9, 1920×1080, 60fps for kinetic UI; use 30fps when the source and motion do not benefit from 60fps |
| Story | Introduction → intent → visible work → core task → proof → close |
| Shot cadence | Mostly 2–5 seconds; no unchanged narrated shot longer than 2.5 seconds without an intentional hold |
| Product evidence | Real capture or source-backed UI is the dominant asset |
| Camera | Macro-to-micro progression: brand world → full product → focused action → resulting state |
| Copy | Sparse claims; one message per shot |
| Audio | Recommend free hosted AI BGM with CC0/CC BY backup and required credits, confirm direction and audition (see `ai-bgm.md`); respect supplied music or explicit silence; interaction accents when available; narration uses enhanced Kokoro when requested |
| Close | Minimal product mark and brief CTA only when the launch brief provides one |

### Story allocation

1. **Introduction — 5–8%:** quiet brand or product reveal.
2. **Intent — 10–15%:** the user's goal, prompt, or trigger.
3. **Visible work — 15–20%:** progress, reasoning, loading, or orchestration
   states that make the result feel earned.
4. **Core task — 35–45%:** a complete source-backed interaction from entry
   through acknowledgement and result.
5. **Proof — 10–15%:** one sourced metric, comparison, or observable outcome.
6. **Close — 5–10%:** settle, product identity, and optional CTA.

Omit visible work or proof when the product and evidence do not support them.
Never invent a metric to complete the arc.

### Visual and motion defaults

- Alternate sparse context shots with readable product close-ups.
- Keep one continuous spatial logic across brand, prompt, product, and proof.
- Use a cursor only when it explains a real action.
- Use a source-backed state change as the primary motion in every product shot.
- Keep detailed UI parents fixed during reading; use controlled crops and short
  camera moves between states.
- Create at least three distinct visual states per ten seconds of active
  explanation. A state is a new crop, action, result, subject, or evidence view;
  ambient drift does not count.
- Build three style frames—introduction, core task, and close—and a 6–10 second
  motion test before implementing the whole timeline.

### Product launch failure conditions

- The film is a feature checklist or a sequence of titled slides.
- Product UI is too small to read at normal playback size.
- A click jumps directly to success without acknowledgement.
- A claim or proof point has no source.
- The same window, split layout, transition, or camera distance dominates most
  of the film.
- Decoration moves while the product story remains static.

## Vision video

Use for a future-state product or organizational narrative: why change matters,
what a better experience feels like, and the direction the team is pursuing. A
vision video is not a roadmap recital, feature tour, or product launch with
softer language.

### Default contract

| Dimension | Optimized default |
|---|---|
| Viewer outcome | Feel the present tension, imagine a coherent better future, and understand the directional invitation |
| Duration | Target 90 seconds; normally 60–120 seconds |
| Format | 16:9, 1920×1080, 30fps; use 60fps only for source footage or motion that needs it |
| Story | Present reality → human tension → possibility → future vignettes → principles → invitation |
| Shot cadence | Mostly 3–7 seconds; no unchanged narrated shot longer than 4 seconds without an intentional emotional hold |
| Evidence | Human context and grounded scenarios lead; product UI supports rather than dominates |
| Asset floor | At least three approved human or environmental raster/footage scenes for a people-centered story; vector glyphs do not satisfy this floor |
| Camera | Observational establishing shots, motivated pushes, human-scale details, and match cuts across present/future states |
| Copy | Narration carries the argument; on-screen copy is sparse and complementary |
| Audio | Enhanced Kokoro narration when a script is approved; recommend free hosted AI BGM with CC0/CC BY backup and required credits, confirm direction and audition (see `ai-bgm.md`); respect supplied music or explicit silence |
| Close | A directional statement or invitation, not a feature CTA |

### Story allocation

1. **Present reality — 10–15%:** establish a recognizable current situation.
2. **Human tension — 10–15%:** show the cost, friction, or unmet need without
   exaggerating harm.
3. **Possibility — 10–15%:** introduce the future principle, not a list of
   features.
4. **Future vignettes — 35–45%:** show two to four connected scenarios in which
   behavior, environment, or outcomes visibly change.
5. **Principles and credibility — 10–15%:** name the design principles,
   constraints, or evidence that make the direction coherent.
6. **Invitation — 5–10%:** end with what the audience should believe, discuss,
   or help make real.

### Visual and motion defaults

- Lead with people, situations, environments, or meaningful objects. Use
  supplied footage and imagery first; use Image Generator for original
  non-product scenes when needed.
- For a people-centered story, at least three future-state shots must use
  approved supplied or generated raster imagery/footage with a recognizable
  person, environment, or human action. CSS silhouettes, avatar glyphs, abstract
  diagrams, and kinetic type may connect scenes but do not satisfy this asset
  floor.
- Keep vector-only motion graphics below roughly 35% of runtime by default.
  Override only when the brief explicitly asks for an abstract graphic film.
- If Image Generator fails with the selected provider, do not turn the planned
  human scenes into vector diagrams and continue. Surface the blocked asset,
  preserve the provider boundary, and proceed only with suitable supplied media
  or an explicit user-approved asset/provider fallback.
- Treat conceptual future UI as conceptual and keep it visually consistent
  across vignettes.
- Target roughly 20–40% product UI runtime unless the brief calls for a product-
  heavy vision; avoid making interfaces the only visual evidence.
- Use match cuts, repeated human actions, or environmental motifs to connect
  present and future. Do not use decorative transitions as the connective idea.
- Let one or two emotional holds breathe, but change subject, scale, context, or
  state throughout the rest of the narration.
- Build three style frames—present reality, future vignette, and invitation—and
  a 10–15 second motion-and-audio test before full production.

### Vision video failure conditions

- The film is a roadmap, feature grid, or presentation with narration.
- Every scene uses the same UI shell or split layout.
- Aspirational claims are presented as shipped behavior or proven outcomes.
- Generated people, product UI, typography, and color belong to visibly
  different visual worlds.
- Captions duplicate large on-screen claims or cover the emotional subject.
- The future is described but never shown through a changed human situation.
- Most future vignettes are kinetic type, UI, diagrams, or avatar glyphs because
  planned human-context imagery was unavailable.

## Shared preset gates

Before full implementation:

1. confirm the preset matches the requested viewer outcome;
2. approve or self-critique the three style frames as one coherent system;
3. confirm the selected preset's asset floor is met with approved production
   media rather than placeholders or vector substitutes;
4. inspect the motion test at normal playback speed with audio;
5. revise if it reads as slides, a dashboard, or unrelated visual genres.

Before final render:

1. render an early, middle, and late frame for every scene;
2. verify the contact sheet shows changes in subject, scale, action, and state;
3. inspect every shot that exceeds the preset's maximum static duration;
4. confirm small product text is replaced by a readable crop;
5. reject the result when a preset failure condition remains true.
