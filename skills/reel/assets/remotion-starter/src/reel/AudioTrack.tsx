import {Audio} from '@remotion/media';
import {staticFile} from 'remotion';
import {reelStory} from './content';
import {narrationGain} from './music-envelope';

export const AudioTrack = () => {
  const narration = reelStory.audio.narration;

  if (!narration) {
    return null;
  }

  return (
    <Audio
      src={staticFile(narration.src)}
      volume={narrationGain(narration, reelStory.audio.music)}
    />
  );
};
