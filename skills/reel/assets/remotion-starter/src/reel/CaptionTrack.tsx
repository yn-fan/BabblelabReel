import {useCurrentFrame} from 'remotion';
import {reelStory} from './content';

const fontFamily = '"Segoe UI", Inter, Arial, sans-serif';

export const CaptionTrack = () => {
  const frame = useCurrentFrame();
  const seconds = frame / reelStory.format.fps;
  const cue = reelStory.captionCues.find(
    (candidate) =>
      seconds >= candidate.startSeconds && seconds < candidate.endSeconds,
  );

  if (!cue) {
    return null;
  }

  const scale = reelStory.format.height / 1080;
  const scene = reelStory.scenes.find((candidate) => candidate.id === cue.sceneId);
  const usesSurface =
    scene?.kind === 'context' || scene?.kind === 'outcome';

  return (
    <div
      style={{
        position: 'absolute',
        zIndex: 100,
        left: 160 * scale,
        right: 160 * scale,
        bottom: 62 * scale,
        color: usesSurface
          ? reelStory.brand.surfaceForeground
          : reelStory.brand.foreground,
        fontFamily,
        fontSize: 36 * scale,
        fontWeight: 560,
        lineHeight: 1.25,
        textAlign: 'center',
        textShadow: usesSurface
          ? '0 1px 12px rgba(255,255,255,.9)'
          : '0 2px 4px rgba(0,0,0,.9), 0 6px 24px rgba(0,0,0,.72)',
        whiteSpace: 'pre-line',
      }}
    >
      {cue.text}
    </div>
  );
};
