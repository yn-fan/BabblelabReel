import {useCurrentFrame} from 'remotion';
import {reelStory} from './content';

const fontFamily = '"Segoe UI", Inter, Arial, sans-serif';

export const MUSIC_CREDITS_RENDERER_VERSION = 1;

export const musicCreditsStartFrame = (durationInFrames: number, fps: number) =>
  Math.max(0, durationInFrames - Math.round(5 * fps));

export const musicCreditsVisible = (
  attribution: string | undefined,
  frame: number,
  durationInFrames: number,
  fps: number,
) =>
  Boolean(attribution) &&
  frame >= musicCreditsStartFrame(durationInFrames, fps) &&
  frame < durationInFrames;

// Budget a full em per UTF-16 unit, including spaces, rather than relying on
// browser font measurement. This deliberately overestimates our font stack.
export const musicCreditsLineCount = (text: string, columns: number) => {
  const capacity = Math.max(1, Math.floor(columns));
  return text.split('\n').reduce((total, paragraph) => {
    let lines = 1;
    let used = 0;
    for (const token of paragraph.match(/\S+|[^\S\n]+/gu) ?? []) {
      if (used && used + token.length > capacity) {
        lines += 1;
        used = 0;
      }
      const extraLines = Math.max(0, Math.ceil(token.length / capacity) - 1);
      lines += extraLines;
      used += token.length - extraLines * capacity;
    }
    return total + lines;
  }, 0);
};

export const musicCreditsLayout = (
  attribution: string,
  width: number,
  height: number,
  captions: string[] = [],
) => {
  const scale = Math.min(width, height) / 1080;
  const margin = 38 * scale;
  const padding = 24 * scale;
  const textWidth = width - 2 * (margin + padding);
  const captionScale = height / 1080;
  // Match CaptionTrack's geometry, reserving every overlapping cue so the
  // credit panel stays stationary when captions change.
  const captionHeight = captions.length
    ? Math.max(
        ...captions.map((text) =>
          musicCreditsLineCount(
            text,
            (width - 320 * captionScale) / (36 * captionScale),
          ) * 45 * captionScale,
        ),
      ) + 62 * captionScale
    : 0;
  const availableHeight = Math.min(
    height * 0.42,
    height - captionHeight - 2 * margin,
  );

  for (let size = 28; size >= 20; size -= 0.5) {
    const fontSize = size * scale;
    const lineHeight = fontSize * 1.35;
    const estimatedHeight =
      musicCreditsLineCount(attribution, textWidth / fontSize) * lineHeight +
      2 * padding;
    if (estimatedHeight <= availableHeight) {
      return {margin, padding, fontSize, lineHeight, estimatedHeight};
    }
  }

  throw new Error(
    'Music attribution cannot fit legibly above captions. Use a track with ' +
      'shorter attribution or revise the video layout; do not truncate credits.',
  );
};

export const MusicCredits = ({
  durationInFrames,
}: {
  durationInFrames: number;
}) => {
  const frame = useCurrentFrame();
  const attribution = reelStory.audio.music?.attribution;
  const {width, height, fps} = reelStory.format;

  if (!attribution || !musicCreditsVisible(attribution, frame, durationInFrames, fps)) {
    return null;
  }

  const startSeconds = musicCreditsStartFrame(durationInFrames, fps) / fps;
  const captions = reelStory.captionCues
    .filter((cue) =>
      cue.endSeconds > startSeconds &&
      cue.startSeconds < durationInFrames / fps,
    )
    .map((cue) => cue.text);
  const layout = musicCreditsLayout(attribution, width, height, captions);

  return (
    <div
      data-testid="music-credits"
      style={{
        position: 'absolute',
        zIndex: 90,
        top: layout.margin,
        left: layout.margin,
        right: layout.margin,
        padding: layout.padding,
        boxSizing: 'border-box',
        backgroundColor: '#000',
        color: '#fff',
        fontFamily,
        fontSize: layout.fontSize,
        lineHeight: `${layout.lineHeight}px`,
        fontWeight: 400,
        textAlign: 'left',
        whiteSpace: 'pre-wrap',
        overflowWrap: 'anywhere',
        pointerEvents: 'none',
      }}
    >
      {attribution}
    </div>
  );
};
