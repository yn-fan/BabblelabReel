import {createHash} from 'node:crypto';
import {readFileSync, realpathSync, statSync} from 'node:fs';
import {resolve, sep} from 'node:path';
import {measureMp3Duration} from './validate-mp3.mjs';

const isObject = (value) =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
const nonempty = (value) => typeof value === 'string' && value.trim().length > 0;
const sha256 = (value) => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
const durationTolerance = 0.000001;

const localAudioPath = (value, extension) => {
  const extensions = Array.isArray(extension) ? extension : [extension];
  if (
    typeof value !== 'string' ||
    !value.startsWith('audio/') ||
    !extensions.some((candidate) => value.endsWith(candidate)) ||
    value.split('/').some((part) =>
      !/^[A-Za-z0-9_.-]+$/.test(part) || part === '.' || part === '..')
  ) {
    throw new Error(`must be a local public/audio ${extension} path without traversal`);
  }
  const root = resolve(realpathSync(process.cwd()), 'public', 'audio');
  const path = realpathSync(resolve(process.cwd(), 'public', value));
  if (!path.startsWith(root + sep)) {
    throw new Error('must not escape public/audio through a symlink');
  }
  if (!statSync(path).isFile()) {
    throw new Error('must point to a regular file');
  }
  return path;
};

const measureFlacDuration = (path) => {
  const audio = readFileSync(path);
  if (audio.length < 44 || audio.toString('ascii', 0, 4) !== 'fLaC') {
    throw new Error('not a native FLAC file');
  }
  let offset = 4;
  let duration;
  while (offset + 4 <= audio.length) {
    const header = audio[offset];
    const kind = header & 0x7f;
    const size = audio.readUIntBE(offset + 1, 3);
    const start = offset + 4;
    if (start + size > audio.length || kind === 127 || (offset === 4 && kind !== 0)) {
      throw new Error('invalid or truncated FLAC metadata');
    }
    if (kind === 0) {
      if (size !== 34 || duration !== undefined) {
        throw new Error('invalid FLAC STREAMINFO');
      }
      const packed = audio.readBigUInt64BE(start + 10);
      const rate = Number(packed >> 44n);
      const channels = Number((packed >> 41n) & 7n) + 1;
      const bits = Number((packed >> 36n) & 31n) + 1;
      const samples = Number(packed & ((1n << 36n) - 1n));
      if (rate < 8000 || rate > 192000 || ![1, 2].includes(channels) ||
          ![16, 24, 32].includes(bits) || samples === 0) {
        throw new Error('FLAC must declare a nonempty mono/stereo PCM stream');
      }
      duration = samples / rate;
    }
    offset = start + size;
    if (header & 0x80) {
      if (duration === undefined || offset + 2 > audio.length ||
          audio[offset] !== 0xff || (audio[offset + 1] & 0xfe) !== 0xf8) {
        throw new Error('FLAC has no audio frame after metadata');
      }
      return duration;
    }
  }
  throw new Error('incomplete FLAC metadata');
};

export const validateMusic = (story, compositionDuration, measureWav) => {
  const music = story.audio?.music;
  if (music === undefined || music === null) {
    return [];
  }
  const errors = [];
  const fail = (message) => errors.push(`audio.music ${message}`);
  if (!isObject(music)) {
    fail('must be an object or null');
    return errors;
  }
  if (music.attribution !== undefined && !nonempty(music.attribution)) {
    fail('attribution must be a nonempty string when provided');
  }
  const numericFields = [
    'durationSeconds', 'startSeconds', 'endSeconds', 'sourceStartSeconds',
    'volume', 'duckVolume', 'fadeInSeconds', 'fadeOutSeconds',
    'duckAttackSeconds', 'duckReleaseSeconds',
  ];
  for (const field of numericFields) {
    if (!Number.isFinite(music[field]) || music[field] < 0) {
      fail(`${field} must be a finite non-negative number`);
    }
  }
  const fps = story.format?.fps;
  const toFrame = (seconds) => Math.round(seconds * fps);
  const range = music.endSeconds - music.startSeconds;
  const frames = toFrame(music.endSeconds) - toFrame(music.startSeconds);
  if (!(music.durationSeconds > 0)) {
    fail('durationSeconds must be positive');
  }
  if (!(range > 0) || music.endSeconds > compositionDuration) {
    fail('startSeconds/endSeconds must be a positive range bounded by the composition');
  }
  if (!(frames >= 1) || toFrame(music.endSeconds) > toFrame(compositionDuration)) {
    fail('range must occupy at least one frame within the composition');
  }
  if (music.volume > 1 || music.duckVolume > music.volume) {
    fail('volume must be 0..1 and duckVolume must be 0..volume');
  }
  for (const field of ['fadeInSeconds', 'fadeOutSeconds']) {
    if (
      music[field] > range ||
      (music[field] > 0 && music[field] * fps < 1)
    ) {
      fail(`${field} must be zero or at least one frame and not exceed the music range`);
    }
  }
  if (music.fadeInSeconds + music.fadeOutSeconds > range) {
    fail('fade lengths together must not exceed the music range');
  }
  for (const field of ['duckAttackSeconds', 'duckReleaseSeconds']) {
    if (!(music[field] * fps >= 1) || music[field] > compositionDuration) {
      fail(`${field} must be at least one frame and not exceed the composition`);
    }
  }
  let audioPath;
  let provenancePath;
  // Validate both paths before reading either file's contents.
  for (const [field, extension] of [['src', ['.wav', '.flac', '.mp3']], ['provenanceRef', '.json']]) {
    try {
      const path = localAudioPath(music[field], extension);
      if (field === 'src') audioPath = path;
      else provenancePath = path;
    } catch (error) {
      fail(`${field} ${error.message}`);
    }
  }
  if (!audioPath || !provenancePath) {
    return errors;
  }
  let measured;
  try {
    measured = music.src.endsWith('.mp3') ? measureMp3Duration(audioPath)
      : music.src.endsWith('.flac') ? measureFlacDuration(audioPath) : measureWav(audioPath, true);
    if (Math.abs(measured - music.durationSeconds) > durationTolerance) {
      fail('durationSeconds must match the measured full audio duration');
    }
    if (
      music.sourceStartSeconds + range > measured + 1e-9 ||
      (toFrame(music.sourceStartSeconds) + frames) / fps > measured + 1e-9
    ) {
      fail('source duration must cover the requested range plus trim, including frame quantization; no looping');
    }
  } catch (error) {
    fail(`src must be a readable WAV, FLAC or MP3 file: ${error.message}`);
  }
  let provenance;
  try {
    provenance = JSON.parse(readFileSync(provenancePath, 'utf8'));
  } catch {
    fail('provenanceRef must contain valid JSON');
    return errors;
  }
  if (!isObject(provenance)) {
    fail('provenanceRef must contain a JSON object');
    return errors;
  }
  for (const [field, expected] of Object.entries({
    schemaVersion: 1,
    success: true,
    instrumental: true,
  })) {
    if (provenance[field] !== expected) {
      fail(`provenance ${field} must be ${JSON.stringify(expected)}`);
    }
  }
  if (provenance.kind === 'ai-generated-music') {
    if (music.src.endsWith('.mp3')) {
      fail('MP3 is supported only for licensed-library-music');
    }
    if (!['ace-step', 'huggingface'].includes(provenance.provider)) {
      fail('provenance provider must be ace-step or huggingface');
    }
    if (
      provenance.provider === 'huggingface' &&
      (provenance.space !== 'ACE-Step/Ace-Step-v1.5' ||
        provenance.model !== 'acestep-v15-turbo')
    ) {
      fail('hosted provenance must identify the official Space and standard turbo model');
    }
    for (const field of ['model', 'licenseNote']) {
      if (!nonempty(provenance[field])) {
        fail(`provenance ${field} must be a nonempty string`);
      }
    }
    if (!Number.isSafeInteger(provenance.seed) || provenance.seed < 0) {
      fail('provenance seed must be a non-negative safe integer');
    }
    if (!sha256(provenance.promptSha256)) {
      fail('provenance promptSha256 must be 64 lowercase hexadecimal characters');
    }
  } else if (provenance.kind === 'licensed-library-music') {
    const incompetech = provenance.provider === 'incompetech';
    const licenses = {
      'CC0-1.0': ['https://creativecommons.org/publicdomain/zero/1.0/', false],
      'CC-BY-4.0': ['https://creativecommons.org/licenses/by/4.0/', true],
      'CC-BY-3.0': ['https://creativecommons.org/licenses/by/3.0/', true],
    };
    const license = Object.hasOwn(licenses, provenance.license) ? licenses[provenance.license] : undefined;
    if (!license) {
      fail('library provenance license must be CC0-1.0, CC-BY-3.0 or CC-BY-4.0');
    } else {
      if (provenance.licenseUrl !== license[0] || provenance.attributionRequired !== license[1]) {
        fail('library provenance license URL and attribution requirement must match its license');
      }
      if (license[1]) {
        try {
          const renderer = readFileSync(resolve('src/reel/MusicCredits.tsx'), 'utf8');
          const reel = readFileSync(resolve('src/reel/Reel.tsx'), 'utf8');
          if (!renderer.includes('export const MUSIC_CREDITS_RENDERER_VERSION = 1;') ||
              !reel.includes("import {MusicCredits} from './MusicCredits';") ||
              !reel.includes('<MusicCredits durationInFrames={DURATION_IN_FRAMES} />')) {
            fail('CC BY requires the integrated music credits renderer; upgrade the project or use CC0');
          }
        } catch {
          fail('CC BY requires the music credits renderer; upgrade the project or use CC0');
        }
        const expectedCredit =
          `${provenance.title} - ${provenance.creditCreators ?? provenance.creator}\n` +
          `${provenance.license}; ${provenance.licenseUrl}\n` +
          `${provenance.sourceUrl}\n` +
          'Edited for this video: excerpt, fades, and volume mix.';
        if (provenance.attributionText !== expectedCredit || music.attribution !== expectedCredit) {
          fail('CC BY music requires complete visible attribution matching the original source');
        }
        if (provenance.creditCreators !== undefined &&
            (!nonempty(provenance.creditCreators) || !provenance.creditCreators.includes(provenance.creator))) {
          fail('CC BY credit must retain the source creator and credited contributors');
        }
        try {
          const licensePath = localAudioPath(music.src + '.license.txt', '.txt');
          if (readFileSync(licensePath, 'utf8').trim() !== (
            expectedCredit + '\n\nOriginal recording licensed by its creator under the linked license.\n' +
            (incompetech ? `Source catalog SHA-256: ${provenance.sourceCatalogSha256}`
              : `Source revision: ${provenance.sourceRevisionId}`) +
            `\nSource verified: ${provenance.verifiedAt}`
          )) {
            fail('CC BY license file must retain its attribution and source evidence');
          }
        } catch {
          fail('CC BY music requires its companion .license.txt file');
        }
      }
    }
    if (!['wikimedia-commons', 'incompetech'].includes(provenance.provider)) {
      fail('library provenance provider must be wikimedia-commons or incompetech');
    }
    for (const [field, expected] of Object.entries({
      allowsProjectRedistribution: true,
    })) {
      if (provenance[field] !== expected) {
        fail(`library provenance ${field} must be ${JSON.stringify(expected)}`);
      }
    }
    for (const field of ['title', 'creator', 'selectionRationale']) {
      if (!nonempty(provenance[field])) {
        fail(`library provenance ${field} must be a nonempty string`);
      }
    }
    if (!incompetech &&
        (!Number.isSafeInteger(provenance.sourceRevisionId) || provenance.sourceRevisionId <= 0)) {
      fail('library provenance sourceRevisionId must identify the verified source revision');
    }
    if (incompetech) {
      if (provenance.license !== 'CC-BY-4.0' || provenance.creator !== 'Kevin MacLeod' ||
          provenance.creditCreators !== 'Kevin MacLeod (incompetech.com)') {
        fail('Incompetech requires Kevin MacLeod attribution under CC-BY-4.0');
      }
      if (!music.src.endsWith('.mp3') || provenance.audioFormat !== 'mp3') {
        fail('Incompetech requires original MP3 audio');
      }
      if (typeof provenance.trackId !== 'string' ||
          !/^USUAN[0-9]{7}$/.test(provenance.trackId)) {
        fail('Incompetech trackId must be a supported composer ISRC');
      }
      if ('sourceRevisionId' in provenance) {
        fail('Incompetech uses catalog evidence, not a Commons source revision');
      }
      for (const field of ['sourceCatalogSha256', 'sourceLicenseSha256', 'sourceSha256']) {
        if (!sha256(provenance[field])) {
          fail(`Incompetech ${field} must be 64 lowercase hexadecimal characters`);
        }
      }
      if (provenance.sourceSha256 !== createHash('sha256').update(readFileSync(audioPath)).digest('hex')) {
        fail('Incompetech sourceSha256 must match the original audio');
      }
    }
    if (typeof provenance.sourceFileSha1 !== 'string' || !/^[0-9a-f]{40}$/.test(provenance.sourceFileSha1)) {
      fail('library provenance sourceFileSha1 must be 40 lowercase hexadecimal characters');
    } else if (provenance.sourceFileSha1 !== createHash('sha1').update(readFileSync(audioPath)).digest('hex')) {
      fail('library provenance sourceFileSha1 must match the original audio');
    }
    if (!nonempty(provenance.verifiedAt) || !/(Z|\+00:00)$/.test(provenance.verifiedAt) ||
        !Number.isFinite(Date.parse(provenance.verifiedAt))) {
      fail('library provenance verifiedAt must be a UTC ISO timestamp');
    }
    for (const [field, host, prefix] of (incompetech ? [
      ['sourceUrl', 'incompetech.com', '/music/royalty-free/index.html'],
      ['sourceDownloadUrl', 'incompetech.com', '/music/royalty-free/mp3-royaltyfree/'],
    ] : [
      ['sourceUrl', 'commons.wikimedia.org', '/wiki/File:'],
      ['sourceDownloadUrl', 'upload.wikimedia.org', '/wikipedia/commons/'],
    ])) {
      try {
        const url = new URL(provenance[field]);
        if (url.protocol !== 'https:' || url.host !== host || url.username || url.password ||
            !url.pathname.startsWith(prefix) || (!incompetech && url.search) || url.hash) {
          fail(`library provenance ${field} must identify the trusted source`);
        }
        if (incompetech && field === 'sourceUrl' &&
            provenance[field] !== `https://${host}${prefix}?isrc=${provenance.trackId}`) {
          fail('Incompetech sourceUrl must identify exactly its ISRC catalog entry');
        }
        if (incompetech && field === 'sourceDownloadUrl') {
          const filename = decodeURIComponent(url.pathname.slice(prefix.length));
          if (url.search || !filename.endsWith('.mp3') || filename.length <= 4 ||
              /[/\\\x00-\x1f\x7f]/.test(filename) || filename === '..mp3' ||
              provenance[field] !== `https://${host}${url.pathname}`) {
            fail('Incompetech sourceDownloadUrl must identify a single original MP3 filename');
          }
        }
      } catch {
        fail(`library provenance ${field} must be a valid source URL`);
      }
    }
    if (['model', 'seed', 'promptSha256', 'generation'].some((field) => field in provenance)) {
      fail('library provenance must not impersonate AI-generated music');
    }
  } else {
    fail('provenance kind must be ai-generated-music or licensed-library-music');
  }
  if (provenance.audioFormat !== undefined &&
      (!['wav', 'flac', 'mp3'].includes(provenance.audioFormat) ||
       !music.src.endsWith(`.${provenance.audioFormat}`))) {
    fail('provenance audioFormat must match the audio extension');
  }
  if (
    !sha256(provenance.outputSha256) ||
    provenance.outputSha256 !== createHash('sha256').update(readFileSync(audioPath)).digest('hex')
  ) {
    fail('provenance outputSha256 must match the audio SHA-256');
  }
  if (
    !Number.isFinite(provenance.durationSeconds) ||
    !(provenance.durationSeconds > 0) ||
    (measured !== undefined &&
      Math.abs(provenance.durationSeconds - measured) > durationTolerance)
  ) {
    fail('provenance durationSeconds must match the measured full audio duration');
  }
  return errors;
};
