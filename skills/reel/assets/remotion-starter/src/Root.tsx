import {Composition} from 'remotion';
import {
  DURATION_IN_FRAMES,
  FPS,
  ProductReel,
  REEL_HEIGHT,
  REEL_WIDTH,
} from './reel/Reel';

export const RemotionRoot = () => {
  return (
    <Composition
      id="ProductReel"
      component={ProductReel}
      durationInFrames={DURATION_IN_FRAMES}
      fps={FPS}
      width={REEL_WIDTH}
      height={REEL_HEIGHT}
    />
  );
};
