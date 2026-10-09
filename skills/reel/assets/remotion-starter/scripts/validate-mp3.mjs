import {readFileSync} from 'node:fs';

// Framing inspection, not decoding: match mp3_audio.py, excluding Xing/Info
// metadata frames but retaining every audio frame's encoder delay/padding.
export const measureMp3Duration = (path) => {
  const audio = readFileSync(path);
  let start = 0;
  let end = audio.length;
  const text = (offset, length) => audio.toString('latin1', offset, offset + length);
  if (text(0, 3) === 'ID3') {
    if (end < 10) throw new Error('truncated ID3v2 header');
    const [version, revision, flags] = audio.subarray(3, 6);
    const allowed = {2: 0xc0, 3: 0xe0, 4: 0xf0};
    if (!Object.hasOwn(allowed, version) || revision === 255 || (flags & ~allowed[version])) {
      throw new Error('unsupported ID3v2 header');
    }
    if (audio.subarray(6, 10).some((value) => value & 0x80)) {
      throw new Error('invalid ID3v2 synchsafe size');
    }
    const size = audio[6] * 2 ** 21 + audio[7] * 2 ** 14 + audio[8] * 128 + audio[9];
    start = 10 + size;
    if (version === 4 && (flags & 0x10)) {
      if (text(start, 3) !== '3DI' || !audio.subarray(start + 3, start + 10).equals(audio.subarray(3, 10))) {
        throw new Error('invalid ID3v2 footer');
      }
      start += 10;
    }
    if (start > end) throw new Error('truncated ID3v2 tag');
  }
  if (end - start >= 128 && text(end - 128, 3) === 'TAG') end -= 128;
  let offset = start;
  let frames = 0;
  let samples = 0;
  let stream;
  let declaredFrames;
  let declaredBytes;
  while (offset < end) {
    if (offset + 4 > end) throw new Error('truncated MPEG header');
    const header = audio.readUInt32BE(offset);
    const version = (header >>> 19) & 3;
    const layer = (header >>> 17) & 3;
    const bitrateIndex = (header >>> 12) & 15;
    const rateIndex = (header >>> 10) & 3;
    if ((header >>> 21) !== 0x7ff || version === 1 || layer !== 1 ||
        [0, 15].includes(bitrateIndex) || rateIndex === 3 || (header & 3) === 2) {
      throw new Error('invalid or unsupported MPEG Layer III header');
    }
    if (!(header & (1 << 16))) throw new Error('CRC-protected MP3 is unsupported');
    const rate = [44100, 48000, 32000][rateIndex] / ({3: 1, 2: 2, 0: 4}[version]);
    const bitrates = version === 3
      ? [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
      : [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160];
    const channels = ((header >>> 6) & 3) === 3 ? 1 : 2;
    const signature = `${version}:${rate}:${channels}`;
    if (stream !== undefined && signature !== stream) {
      throw new Error('MP3 stream parameters change between frames');
    }
    stream = signature;
    const size = Math.floor((version === 3 ? 144000 : 72000) * bitrates[bitrateIndex] / rate)
      + ((header >>> 9) & 1);
    const sideSize = version === 3 ? (channels === 1 ? 17 : 32) : (channels === 1 ? 9 : 17);
    const frameEnd = offset + size;
    if (size <= 4 + sideSize || frameEnd > end) throw new Error('invalid or truncated MPEG frame');
    const marker = offset + 4 + sideSize;
    if (['Xing', 'Info'].includes(text(marker, 4))) {
      if (offset !== start || marker + 8 > frameEnd) throw new Error('invalid Xing/Info frame');
      const flags = audio.readUInt32BE(marker + 4);
      if (flags & ~15) throw new Error('unsupported Xing/Info flags');
      let cursor = marker + 8;
      for (const [bit, length] of [[1, 4], [2, 4], [4, 100], [8, 4]]) {
        if (flags & bit) {
          if (cursor + length > frameEnd) throw new Error('truncated Xing/Info fields');
          if (bit === 1) declaredFrames = audio.readUInt32BE(cursor);
          else if (bit === 2) declaredBytes = audio.readUInt32BE(cursor);
          cursor += length;
        }
      }
    } else {
      if (text(offset + 36, 4) === 'VBRI') throw new Error('VBRI metadata is unsupported');
      frames += 1;
      samples += version === 3 ? 1152 : 576;
    }
    offset = frameEnd;
  }
  if (frames < 2 || stream === undefined) throw new Error('MP3 must contain at least two complete audio frames');
  if (declaredFrames !== undefined && declaredFrames !== frames) {
    throw new Error('Xing/Info frame count does not match the complete stream');
  }
  if (declaredBytes !== undefined && declaredBytes !== end - start) {
    throw new Error('Xing/Info byte count does not match the complete stream');
  }
  return samples / Number(stream.split(':')[1]);
};
