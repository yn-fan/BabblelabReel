import {Audio} from '@remotion/media';
import {staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {reelStory} from './content';
import {musicGain, musicTiming} from './music-envelope';

export const MusicTrack = () => {
  // Mounted at composition level: neither shot cuts nor source trim reset gain.
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const music = reelStory.audio.music;
  if (!music) {
    return null;
  }
  return (
    <Audio
      src={staticFile(music.src)}
      {...musicTiming(music, fps)}
      loop={false}
      volume={musicGain(frame, fps, music, reelStory.audio.narration, reelStory.captionCues)}
      onError={() => 'fail'}
    />
  );
};
