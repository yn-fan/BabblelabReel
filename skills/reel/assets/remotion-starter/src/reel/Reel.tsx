import type {ReactNode} from 'react';
import {
  AbsoluteFill,
  Easing,
  Sequence,
  interpolate,
  useCurrentFrame,
} from 'remotion';
import {AudioTrack} from './AudioTrack';
import {MusicTrack} from './MusicTrack';
import {MusicCredits} from './MusicCredits';
import {CaptionTrack} from './CaptionTrack';
import {
  reelStory,
  type ReelBeat,
  type ReelScene,
  type ReelShot,
} from './content';

export const FPS = reelStory.format.fps;
export const REEL_WIDTH = reelStory.format.width;
export const REEL_HEIGHT = reelStory.format.height;

const seconds = (value: number) => Math.round(value * FPS);
const fontFamily = '"Segoe UI", Inter, Arial, sans-serif';
const hasSceneCaptions = (sceneId: string) =>
  reelStory.captionCues.some((cue) => cue.sceneId === sceneId);

type SceneTiming = {
  from: number;
  durationInFrames: number;
  shots: ReelShot[];
  beats: Array<ReelBeat & {localFrame: number}>;
};

const sceneTimeline = reelStory.scenes.map((scene) => {
  const shots = reelStory.shots.filter((shot) => shot.sceneId === scene.id);
  const startSeconds = shots[0].startSeconds;
  const endSeconds = Math.max(
    ...shots.map((shot) => shot.startSeconds + shot.durationSeconds),
  );
  const from = seconds(startSeconds);
  const durationInFrames = seconds(endSeconds) - from;
  const beats = reelStory.beats
    .filter((beat) => beat.sceneId === scene.id)
    .map((beat) => ({
      ...beat,
      localFrame: seconds(beat.atSeconds) - from,
    }));

  return {
    scene,
    from,
    durationInFrames,
    timing: {from, durationInFrames, shots, beats},
  };
});

export const DURATION_IN_FRAMES = Math.max(
  ...reelStory.shots.map((shot) =>
    seconds(shot.startSeconds + shot.durationSeconds),
  ),
);

const progress = (frame: number, start: number, duration: number) =>
  interpolate(frame, [start, start + duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

const settledProgress = (frame: number, start: number, duration: number) =>
  frame >= start + duration ? 1 : progress(frame, start, duration);

const visualBeats = (timing: SceneTiming) =>
  timing.beats.filter(
    (beat) => beat.kind === 'action' || beat.kind === 'state',
  );

const primaryVisualBeat = (timing: SceneTiming) =>
  visualBeats(timing)[0] ?? timing.beats[0];

const activeVisualBeatIndex = (frame: number, timing: SceneTiming) => {
  let activeIndex = 0;
  visualBeats(timing).forEach((beat, index) => {
    if (frame >= beat.localFrame) {
      activeIndex = index;
    }
  });
  return activeIndex;
};

const SceneFrame = ({
  children,
  surface = false,
}: {
  children: ReactNode;
  surface?: boolean;
}) => (
  <AbsoluteFill
    style={{
      boxSizing: 'border-box',
      overflow: 'hidden',
      padding: '88px 112px',
      background: surface
        ? reelStory.brand.surface
        : reelStory.brand.background,
      color: surface
        ? reelStory.brand.surfaceForeground
        : reelStory.brand.foreground,
      fontFamily,
    }}
  >
    {children}
  </AbsoluteFill>
);

const ShotFrame = ({
  shot,
  durationInFrames,
  children,
}: {
  shot: ReelShot;
  durationInFrames: number;
  children: ReactNode;
}) => {
  const frame = useCurrentFrame();
  const holdFrames = seconds(shot.holdSeconds);
  const settleFrames = Math.max(1, durationInFrames - holdFrames);
  const cameraProgress = settledProgress(frame, 0, settleFrames);
  const panDistance = Math.max(1, Math.floor(REEL_WIDTH * 0.02));
  const cropDistance = Math.max(1, Math.floor(REEL_HEIGHT * 0.02));
  let transform: string | undefined;

  switch (shot.camera) {
    case 'push-in':
      transform = `scale(${interpolate(cameraProgress, [0, 1], [1, 1.04])})`;
      break;
    case 'pull-out':
      transform = `scale(${interpolate(cameraProgress, [0, 1], [1.04, 1])})`;
      break;
    case 'pan-left':
      transform = `translateX(${Math.round(interpolate(cameraProgress, [0, 1], [panDistance, 0]))}px) scale(1.05)`;
      break;
    case 'pan-right':
      transform = `translateX(${Math.round(interpolate(cameraProgress, [0, 1], [-panDistance, 0]))}px) scale(1.05)`;
      break;
    case 'controlled-crop':
      transform = `translateY(${Math.round(interpolate(cameraProgress, [0, 1], [cropDistance, 0]))}px) scale(1.06)`;
      break;
    case 'static':
      transform = undefined;
      break;
  }

  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <AbsoluteFill
        style={{
          transform,
          transformOrigin: 'center center',
        }}
      >
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const OpeningScene = ({
  scene,
  timing,
  sceneFrameOffset,
}: {
  scene: ReelScene;
  timing: SceneTiming;
  sceneFrameOffset: number;
}) => {
  const frame = useCurrentFrame() + sceneFrameOffset;
  const reveal = settledProgress(
    frame,
    primaryVisualBeat(timing).localFrame,
    24,
  );

  return (
    <SceneFrame>
      <div
        style={{
          position: 'absolute',
          left: 112,
          top: 154,
          width: 5,
          height: 170 * reveal,
          background: reelStory.brand.accent,
        }}
      />
      <div
        style={{
          maxWidth: 1450,
          marginTop: 180,
          clipPath: `inset(0 ${100 - reveal * 100}% 0 0)`,
        }}
      >
        <div
          style={{
            fontSize: 100,
            lineHeight: 1,
            letterSpacing: -5,
            fontWeight: 650,
          }}
        >
          {scene.headline}
        </div>
        <div
          style={{
            marginTop: 38,
            maxWidth: 940,
            color: reelStory.brand.muted,
            fontSize: 34,
            lineHeight: 1.35,
          }}
        >
          {scene.detail}
        </div>
      </div>
    </SceneFrame>
  );
};

const ContextScene = ({
  scene,
  timing,
  sceneFrameOffset,
}: {
  scene: ReelScene;
  timing: SceneTiming;
  sceneFrameOffset: number;
}) => {
  const frame = useCurrentFrame() + sceneFrameOffset;
  const activeIndex = Math.min(
    activeVisualBeatIndex(frame, timing),
    Math.max(scene.items.length - 1, 0),
  );
  const activeStart = visualBeats(timing)[activeIndex].localFrame;
  const itemProgress = settledProgress(frame, activeStart, 18);
  const activeItem = scene.items[activeIndex] ?? scene.detail;

  return (
    <SceneFrame surface>
      <div
        style={{
          marginTop: 70,
          maxWidth: 1400,
          fontSize: 34,
          lineHeight: 1.05,
          color: '#6b6d72',
        }}
      >
        {scene.headline}
      </div>
      <div
        style={{
          position: 'absolute',
          left: 112,
          right: 160,
          top: 330,
          fontSize: 82,
          lineHeight: 1.08,
          letterSpacing: -3,
          fontWeight: 620,
          opacity: itemProgress,
          transform:
            itemProgress === 1
              ? undefined
              : `translateY(${Math.round((1 - itemProgress) * 20)}px)`,
        }}
      >
        {activeItem}
      </div>
    </SceneFrame>
  );
};

const TaskScene = ({
  scene,
  timing,
  sceneFrameOffset,
}: {
  scene: ReelScene;
  timing: SceneTiming;
  sceneFrameOffset: number;
}) => {
  const frame = useCurrentFrame() + sceneFrameOffset;
  const phaseIndex = Math.min(
    activeVisualBeatIndex(frame, timing),
    Math.max(scene.items.length - 1, 0),
  );
  const phaseStart = visualBeats(timing)[phaseIndex].localFrame;
  const phaseProgress = settledProgress(frame, phaseStart, 18);
  const activeItem = scene.items[phaseIndex] ?? scene.action;
  const phaseLabel = ['Before', 'Action and acknowledgement', 'Result'][phaseIndex];

  return (
    <SceneFrame>
      <div
        style={{
          position: 'absolute',
          left: 112,
          right: 112,
          top: 96,
          display: 'flex',
          justifyContent: 'space-between',
          color: reelStory.brand.muted,
          fontSize: 24,
        }}
      >
        <span>{scene.headline}</span>
        <span>{scene.sourceRef}</span>
      </div>
      <div
        style={{
          position: 'absolute',
          left: 112,
          top: 310,
          color: reelStory.brand.muted,
          fontSize: 26,
          opacity: phaseProgress,
        }}
      >
        {phaseLabel}
      </div>
      <div
        style={{
          position: 'absolute',
          left: 112,
          right: 160,
          top: 375,
          fontSize: 78,
          lineHeight: 1.08,
          letterSpacing: -3,
          fontWeight: 620,
          opacity: phaseProgress,
          clipPath: `inset(0 ${100 - phaseProgress * 100}% 0 0)`,
        }}
      >
        {activeItem}
      </div>
      <div
        style={{
          position: 'absolute',
          left: 112,
          bottom: 150,
          maxWidth: 1180,
          color: reelStory.brand.muted,
          fontSize: 28,
          lineHeight: 1.35,
        }}
      >
        {scene.detail}
      </div>
    </SceneFrame>
  );
};

const OutcomeScene = ({
  scene,
  timing,
  sceneFrameOffset,
}: {
  scene: ReelScene;
  timing: SceneTiming;
  sceneFrameOffset: number;
}) => {
  const frame = useCurrentFrame() + sceneFrameOffset;
  const result = settledProgress(
    frame,
    primaryVisualBeat(timing).localFrame,
    24,
  );

  return (
    <SceneFrame surface>
      <div
        style={{
          position: 'absolute',
          left: 112,
          right: 112,
          top: 150,
          fontSize: 30,
          color: '#6b6d72',
        }}
      >
        {scene.stateBefore}
      </div>
      <div
        style={{
          maxWidth: 1500,
          marginTop: 210,
          fontSize: 94,
          lineHeight: 1.02,
          letterSpacing: -5,
          fontWeight: 650,
          clipPath: `inset(0 ${100 - result * 100}% 0 0)`,
        }}
      >
        {scene.headline}
      </div>
      <div
        style={{
          marginTop: 38,
          maxWidth: 1080,
          fontSize: 34,
          lineHeight: 1.35,
          opacity: result,
        }}
      >
        {scene.detail}
      </div>
      <div
        style={{
          position: 'absolute',
          left: 112,
          bottom: hasSceneCaptions(scene.id) ? 190 : 106,
          fontSize: 26,
          color: '#6b6d72',
        }}
      >
        {scene.stateAfter}
      </div>
    </SceneFrame>
  );
};

const CloseScene = ({
  scene,
  timing,
  sceneFrameOffset,
}: {
  scene: ReelScene;
  timing: SceneTiming;
  sceneFrameOffset: number;
}) => {
  const frame = useCurrentFrame() + sceneFrameOffset;
  const reveal = settledProgress(
    frame,
    primaryVisualBeat(timing).localFrame,
    24,
  );

  return (
    <SceneFrame>
      <div
        style={{
          maxWidth: 1460,
          marginTop: 265,
          fontSize: 90,
          lineHeight: 1.03,
          letterSpacing: -4,
          fontWeight: 650,
          opacity: reveal,
        }}
      >
        {scene.headline}
      </div>
      <div
        style={{
          marginTop: 34,
          maxWidth: 900,
          fontSize: 32,
          lineHeight: 1.4,
          color: reelStory.brand.muted,
          opacity: reveal,
        }}
      >
        {scene.detail}
      </div>
    </SceneFrame>
  );
};

const Scene = ({
  scene,
  timing,
  sceneFrameOffset,
}: {
  scene: ReelScene;
  timing: SceneTiming;
  sceneFrameOffset: number;
}) => {
  switch (scene.kind) {
    case 'opening':
      return (
        <OpeningScene
          scene={scene}
          timing={timing}
          sceneFrameOffset={sceneFrameOffset}
        />
      );
    case 'context':
      return (
        <ContextScene
          scene={scene}
          timing={timing}
          sceneFrameOffset={sceneFrameOffset}
        />
      );
    case 'task':
      return (
        <TaskScene
          scene={scene}
          timing={timing}
          sceneFrameOffset={sceneFrameOffset}
        />
      );
    case 'outcome':
      return (
        <OutcomeScene
          scene={scene}
          timing={timing}
          sceneFrameOffset={sceneFrameOffset}
        />
      );
    case 'close':
      return (
        <CloseScene
          scene={scene}
          timing={timing}
          sceneFrameOffset={sceneFrameOffset}
        />
      );
    default:
      throw new Error(`Unsupported Reel scene kind: ${scene.kind}`);
  }
};

export const ProductReel = () => (
  <AbsoluteFill>
    <AudioTrack />
    <MusicTrack />
    {reelStory.shots.map((shot) => {
      const from = seconds(shot.startSeconds);
      const durationInFrames =
        seconds(shot.startSeconds + shot.durationSeconds) - from;
      const sceneTiming = sceneTimeline.find(
        (item) => item.scene.id === shot.sceneId,
      );

      if (!sceneTiming) {
        throw new Error(`Missing scene timing for shot ${shot.id}`);
      }

      return (
        <Sequence
          key={shot.id}
          from={from}
          durationInFrames={durationInFrames}
          name={shot.id}
        >
          <ShotFrame shot={shot} durationInFrames={durationInFrames}>
            <Scene
              scene={sceneTiming.scene}
              timing={sceneTiming.timing}
              sceneFrameOffset={from - sceneTiming.from}
            />
          </ShotFrame>
        </Sequence>
      );
    })}
    <MusicCredits durationInFrames={DURATION_IN_FRAMES} />
    <CaptionTrack />
  </AbsoluteFill>
);
