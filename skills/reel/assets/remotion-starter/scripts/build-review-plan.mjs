import {mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {dirname, resolve} from 'node:path';

const storyPath = resolve(process.cwd(), 'src/reel/story.json');
const outputPath = resolve(process.cwd(), 'out/review-plan.json');
const story = JSON.parse(readFileSync(storyPath, 'utf8'));
const fps = story.format.fps;
const durationSeconds = Math.max(
  ...story.shots.map((shot) => shot.startSeconds + shot.durationSeconds),
);
const durationInFrames = Math.round(durationSeconds * fps);
const frames = new Map();
const shotEvidence = [];

const addFrame = (frame, purpose) => {
  const clamped = Math.max(0, Math.min(durationInFrames - 1, Math.round(frame)));
  const purposes = frames.get(clamped) ?? new Set();
  purposes.add(purpose);
  frames.set(clamped, purposes);
};

const openingScene = story.scenes[0];
const openingBeat =
  story.beats.find(
    (beat) =>
      beat.sceneId === openingScene.id &&
      (beat.kind === 'action' || beat.kind === 'state'),
  ) ?? story.beats.find((beat) => beat.sceneId === openingScene.id);
const openingFrame = Math.round((openingBeat?.atSeconds ?? 0) * fps);
for (const offset of [-1, 0, fps / 3, (fps * 2) / 3]) {
  addFrame(openingFrame + offset, 'opening-motion');
}

for (const [index, shot] of story.shots.entries()) {
  if (index < story.shots.length - 1) {
    const cutFrame = Math.round(
      (shot.startSeconds + shot.durationSeconds) * fps,
    );
    addFrame(cutFrame - 1, `boundary:${shot.id}:${shot.boundary}:outgoing`);
    addFrame(cutFrame, `boundary:${shot.id}:${shot.boundary}`);
    addFrame(cutFrame + 1, `boundary:${shot.id}:${shot.boundary}:incoming`);
  }
}

for (const shot of story.shots) {
  const shotStartFrame = Math.round(shot.startSeconds * fps);
  const shotEndFrame = Math.round(
    (shot.startSeconds + shot.durationSeconds) * fps,
  );
  const holdFrames = Math.round(shot.holdSeconds * fps);
  const entryFrame = shotStartFrame;
  const visualBeat =
    story.beats.find(
      (beat) => beat.shotId === shot.id && beat.kind === 'action',
    ) ??
    story.beats.find(
      (beat) => beat.shotId === shot.id && beat.kind === 'state',
    );
  const focusFrame = Math.max(
    shotStartFrame,
    Math.min(
      shotEndFrame - 1,
      Math.round((visualBeat?.atSeconds ?? shot.startSeconds) * fps),
    ),
  );
  const settleFrame = Math.max(
    shotStartFrame,
    shotEndFrame - holdFrames,
  );
  const compareFrame = Math.min(
    shotEndFrame - 1,
    settleFrame + Math.min(15, Math.round(fps / 2)),
  );
  addFrame(entryFrame, `shot:${shot.id}:entry`);
  const focusKind = visualBeat?.kind ?? 'entry';
  addFrame(focusFrame, `shot:${shot.id}:focus:${focusKind}`);
  addFrame(settleFrame, `hold:${shot.id}:start`);
  addFrame(compareFrame, `hold:${shot.id}:compare`);
  shotEvidence.push({
    shotId: shot.id,
    captureRef: shot.captureRef ?? null,
    entryFrame,
    focusFrame,
    focusKind,
    settleFrame,
    compareFrame,
  });
}

for (const cue of story.captionCues) {
  addFrame(
    ((cue.startSeconds + cue.endSeconds) / 2) * fps,
    `caption:${cue.id}`,
  );
}

addFrame(durationInFrames - 1, 'final-frame');

const plan = {
  schemaVersion: 2,
  compositionId: 'ProductReel',
  fps,
  durationInFrames,
  shotEvidence,
  frames: [...frames.entries()]
    .sort(([left], [right]) => left - right)
    .map(([frame, purposes]) => ({
      frame,
      seconds: Number((frame / fps).toFixed(3)),
      purposes: [...purposes].sort(),
      output: `out/review/frame-${String(frame).padStart(6, '0')}.png`,
    })),
};

mkdirSync(dirname(outputPath), {recursive: true});
writeFileSync(outputPath, `${JSON.stringify(plan, null, 2)}\n`, 'utf8');
console.log(
  `Review plan written: ${plan.frames.length} frames -> ${outputPath}`,
);
