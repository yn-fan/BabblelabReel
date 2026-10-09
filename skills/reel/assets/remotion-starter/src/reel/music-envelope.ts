import type {CaptionCue, MusicTrackConfig, NarrationTrack} from './content';

export const narrationGain = (
  narration: NarrationTrack,
  music?: MusicTrackConfig | null,
) => narration.volume * (1 - (music?.volume ?? 0));

export const musicTiming = (music: MusicTrackConfig, fps: number) => {
  const from = Math.round(music.startSeconds * fps);
  const end = Math.round(music.endSeconds * fps);
  return {
    from,
    durationInFrames: end - from,
    trimBefore: Math.round(music.sourceStartSeconds * fps),
  };
};

const smoothRamp = (position: number) => {
  const t = Math.min(1, Math.max(0, position));
  return t * t * (3 - 2 * t);
};

export const musicGain = (
  frame: number,
  fps: number,
  music: MusicTrackConfig,
  narration: NarrationTrack | null,
  cues: readonly Pick<CaptionCue, 'startSeconds' | 'endSeconds'>[],
): number => {
  const {from, durationInFrames} = musicTiming(music, fps);
  const end = from + durationInFrames;
  if (!Number.isFinite(frame) || !(fps > 0) || frame < from || frame >= end) {
    return 0;
  }
  const time = frame / fps;
  const fadeIn = music.fadeInSeconds === 0
    ? 1
    : smoothRamp((frame - from) / (music.fadeInSeconds * fps));
  const fadeOut = music.fadeOutSeconds === 0
    ? 1
    : smoothRamp((end - 1 - frame) / (music.fadeOutSeconds * fps));
  let gain = music.volume;
  if (narration) {
    const duck = music.duckVolume;
    for (const cue of cues) {
      if (cue.startSeconds >= narration.durationSeconds) {
        continue;
      }
      const cueEnd = Math.min(cue.endSeconds, narration.durationSeconds);
      const outside = time < cue.startSeconds
        ? (music.duckAttackSeconds === 0
          ? 1
          : smoothRamp((cue.startSeconds - time) / music.duckAttackSeconds))
        : time >= cueEnd
          ? (music.duckReleaseSeconds === 0
            ? 1
            : smoothRamp((time - cueEnd) / music.duckReleaseSeconds))
          : 0;
      // Minimum overlapping ramps prevents a reset to full volume in phrase gaps.
      gain = Math.min(gain, duck + (music.volume - duck) * outside);
    }
  }
  return Math.max(0, Math.min(1, gain * Math.min(fadeIn, fadeOut)));
};
