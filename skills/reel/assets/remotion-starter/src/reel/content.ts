import rawStory from './story.json';

export type SourceTruth = {
  id: string;
  type: string;
  ref: string;
  proves: string;
};

export type CaptureSource = {
  id: string;
  sourceRef: string;
  route: string;
  state: string;
  fullFrameSrc: string;
  layoutSrc: string;
  cutoutSrcs: string[];
  viewport: {
    width: number;
    height: number;
    deviceScaleFactor: number;
  };
  privacyClass: 'synthetic' | 'sanitized' | 'approved-production';
};

type RawCaptureSource = Omit<CaptureSource, 'privacyClass'> & {
  privacyClass: string;
};

export type ReelScene = {
  id: string;
  kind: string;
  durationSeconds: number;
  purpose: string;
  headline: string;
  detail: string;
  items: string[];
  caption?: string;
  narration: string;
  action: string;
  stateBefore: string;
  stateAfter: string;
  sourceRef: string;
};

export type ReelShot = {
  id: string;
  sceneId: string;
  startSeconds: number;
  durationSeconds: number;
  dominantSubject: string;
  camera: 'static' | 'push-in' | 'pull-out' | 'pan-left' | 'pan-right' | 'controlled-crop';
  contentAction: string;
  holdSeconds: number;
  boundary: 'cut' | 'end';
  captureRef?: string;
};

export type ReelBeat = {
  id: string;
  sceneId: string;
  shotId: string;
  atSeconds: number;
  kind: 'speech' | 'action' | 'state' | 'transition';
  anchorText: string;
  purpose: string;
};

export type CaptionCue = {
  id: string;
  sceneId: string;
  startSeconds: number;
  endSeconds: number;
  text: string;
};

export type NarrationTrack = {
  src: string;
  durationSeconds: number;
  provenanceRef: string;
  qualityGate: string;
  approvalNote: string;
  volume: number;
};

export type MusicTrackConfig = {
  src: string;
  attribution?: string;
  durationSeconds: number;
  provenanceRef: string;
  startSeconds: number;
  endSeconds: number;
  sourceStartSeconds: number;
  volume: number;
  duckVolume: number;
  fadeInSeconds: number;
  fadeOutSeconds: number;
  duckAttackSeconds: number;
  duckReleaseSeconds: number;
};

export type ReelStory = {
  title: string;
  archetype: string;
  preset: 'custom' | 'product-launch' | 'vision-video';
  treatment: string;
  scriptLocked: boolean;
  format: {
    width: number;
    height: number;
    fps: number;
  };
  brand: {
    background: string;
    surface: string;
    foreground: string;
    surfaceForeground: string;
    muted: string;
    accent: string;
  };
  sourceTruth: SourceTruth[];
  captures: CaptureSource[];
  scenes: ReelScene[];
  shots: ReelShot[];
  beats: ReelBeat[];
  audio: {
    narration: NarrationTrack | null;
    music?: MusicTrackConfig | null;
  };
  captionCues: CaptionCue[];
};

const parsePreset = (value: string): ReelStory['preset'] => {
  switch (value) {
    case 'custom':
      return 'custom';
    case 'product-launch':
      return 'product-launch';
    case 'vision-video':
      return 'vision-video';
    default:
      throw new Error(`Unsupported Reel preset: ${value}`);
  }
};

const parseBoundary = (value: string): ReelShot['boundary'] => {
  switch (value) {
    case 'cut':
      return 'cut';
    case 'end':
      return 'end';
    default:
      throw new Error(`Unsupported Reel shot boundary: ${value}`);
  }
};

const parseCamera = (value: string): ReelShot['camera'] => {
  switch (value) {
    case 'static':
      return 'static';
    case 'push-in':
      return 'push-in';
    case 'pull-out':
      return 'pull-out';
    case 'pan-left':
      return 'pan-left';
    case 'pan-right':
      return 'pan-right';
    case 'controlled-crop':
      return 'controlled-crop';
    default:
      throw new Error(`Unsupported Reel camera mode: ${value}`);
  }
};

const parseBeatKind = (value: string): ReelBeat['kind'] => {
  switch (value) {
    case 'speech':
      return 'speech';
    case 'action':
      return 'action';
    case 'state':
      return 'state';
    case 'transition':
      return 'transition';
    default:
      throw new Error(`Unsupported Reel beat kind: ${value}`);
  }
};

const parsePrivacyClass = (
  value: string,
): CaptureSource['privacyClass'] => {
  switch (value) {
    case 'synthetic':
      return 'synthetic';
    case 'sanitized':
      return 'sanitized';
    case 'approved-production':
      return 'approved-production';
    default:
      throw new Error(`Unsupported Reel capture privacy class: ${value}`);
  }
};

export const reelStory: ReelStory = {
  ...rawStory,
  preset: parsePreset(rawStory.preset),
  captures: rawStory.captures.map((capture: RawCaptureSource) => ({
    ...capture,
    privacyClass: parsePrivacyClass(capture.privacyClass),
  })),
  shots: rawStory.shots.map((shot) => ({
    ...shot,
    camera: parseCamera(shot.camera),
    boundary: parseBoundary(shot.boundary),
  })),
  beats: rawStory.beats.map((beat) => ({
    ...beat,
    kind: parseBeatKind(beat.kind),
  })),
};
