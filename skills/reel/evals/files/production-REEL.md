# Approve a design direction

## Brief

- Archetype: product task demo
- Preset: custom
- Audience: product team
- Outcome: understand the complete approval interaction
- Format: 1920×1080, 30fps
- Duration basis: source-backed task
- Treatment: neutral

## Story lock

- Script source: none
- Required opening: introduce the approval task
- Required sequence: opening → task → conclusion
- Required conclusion: confirm approval
- Approved omissions: none

## Source and task contract

| Source ID | Type | Reference | What it proves |
|---|---|---|---|
| spec-approval-flow | supplied spec | eval fixture | Submission is acknowledged before approval |

## Capture manifest

| Capture ID | Source ID | Route/state | Full frame | Layout | Cutouts | Viewport/DPR | Privacy |
|---|---|---|---|---|---|---|---|

## Timeline

| Time | Scene ID | Purpose | Visual change | Product state | Copy/audio | Source |
|---|---|---|---|---|---|---|
| 0–3s | opening | Introduce task | Reveal title | Task is clear | No narration | spec-approval-flow |
| 3–12s | task | Show interaction | Before → acknowledgement → result | Direction becomes approved | No narration | spec-approval-flow |
| 12–16s | conclusion | Confirm result | Hold result | Story complete | No narration | spec-approval-flow |

## Shot and motion plan

| Shot ID | Scene ID | Time | Dominant subject | Camera | Content action | Hold | Exit |
|---|---|---|---|---|---|---|---|
| opening-1 | opening | 0–3s | Approval task | static | Reveal the task | 1s | cut |
| task-1 | task | 3–12s | Approval control and result | controlled-crop | Select, acknowledge, and approve | 2s | cut |
| conclusion-1 | conclusion | 12–16s | Approved result | static | Hold the result | 3s | end |

## Speech and beat timing

| Beat ID | Shot ID | Time | Kind | Spoken anchor | Visual purpose |
|---|---|---|---|---|---|
| opening-reveal | opening-1 | 0.5s | action | none | Reveal the approval task |
| task-before | task-1 | 3.5s | state | none | Show the selected direction before approval |
| task-acknowledgement | task-1 | 7s | state | none | Show acknowledgement before approval |
| task-result | task-1 | 10s | state | none | Show the approved resulting state |
| conclusion-hold | conclusion-1 | 12.5s | state | none | Begin the final hold |

## Acceptance criteria

- The submission acknowledgement appears before approval.
- All demonstrated states map to the supplied specification.
- The composition remains readable at normal playback size.

## Evidence and placeholders

- All behavior comes from the supplied evaluation fixture.
