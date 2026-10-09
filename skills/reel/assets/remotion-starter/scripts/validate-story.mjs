import {createHash} from 'node:crypto';
import {existsSync, readFileSync, statSync} from 'node:fs';
import {extname, resolve} from 'node:path';
import {inflateSync} from 'node:zlib';
import {validateMusic} from './validate-music.mjs';

const allowPlaceholders = process.argv.includes('--allow-placeholders');
const storyPath = resolve(process.cwd(), 'src/reel/story.json');
const briefPath = resolve(process.cwd(), 'REEL.md');
const storyText = readFileSync(storyPath, 'utf8');
const briefText = readFileSync(briefPath, 'utf8');
const story = JSON.parse(storyText);
const errors = [];
const supportedSceneKinds = new Set([
  'opening',
  'context',
  'task',
  'outcome',
  'close',
]);
const supportedPresets = new Set(['custom', 'product-launch', 'vision-video']);
const supportedBoundaries = new Set([
  'cut',
  'end',
]);
const supportedBeatKinds = new Set([
  'speech',
  'action',
  'state',
  'transition',
]);
const supportedCameras = new Set([
  'static',
  'push-in',
  'pull-out',
  'pan-left',
  'pan-right',
  'controlled-crop',
]);
const supportedPrivacyClasses = new Set([
  'synthetic',
  'sanitized',
  'approved-production',
]);
const epsilon = 0.01;
const normalizeSpeech = (value) =>
  String(value ?? '')
    .normalize('NFKC')
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '');
const toFrame = (seconds) => Math.round(seconds * story.format.fps);
const measureWavDurationSeconds = (path, strict = false) => {
  const wav = readFileSync(path);
  if (
    wav.length < 44 ||
    wav.toString('ascii', 0, 4) !== 'RIFF' ||
    wav.toString('ascii', 8, 12) !== 'WAVE'
  ) {
    throw new Error('not a RIFF/WAVE file');
  }

  let byteRate;
  let dataSize;
  let blockAlign;
  if (strict && wav.readUInt32LE(4) + 8 !== wav.length) {
    throw new Error('invalid RIFF size');
  }
  for (let offset = 12; offset + 8 <= wav.length; ) {
    const chunkId = wav.toString('ascii', offset, offset + 4);
    const chunkSize = wav.readUInt32LE(offset + 4);
    const chunkStart = offset + 8;
    const chunkEnd = chunkStart + chunkSize;
    if (chunkEnd > wav.length) {
      throw new Error(`truncated ${chunkId || 'unknown'} chunk`);
    }
    if (chunkId === 'fmt ' && chunkSize >= 16) {
      if (strict) {
        const format = wav.readUInt16LE(chunkStart);
        const channels = wav.readUInt16LE(chunkStart + 2);
        const sampleRate = wav.readUInt32LE(chunkStart + 4);
        const bits = wav.readUInt16LE(chunkStart + 14);
        blockAlign = wav.readUInt16LE(chunkStart + 12);
        if (
          byteRate !== undefined ||
          ![1, 3].includes(format) ||
          channels < 1 ||
          sampleRate < 1 ||
          !(format === 1 ? [8, 16, 24, 32] : [32, 64]).includes(bits) ||
          blockAlign !== channels * bits / 8 ||
          wav.readUInt32LE(chunkStart + 8) !== sampleRate * blockAlign
        ) {
          throw new Error('invalid or unsupported PCM/float fmt chunk');
        }
      }
      byteRate = wav.readUInt32LE(chunkStart + 8);
    } else if (chunkId === 'data') {
      if (strict && dataSize !== undefined) {
        throw new Error('multiple data chunks');
      }
      dataSize = chunkSize;
    }
    offset = chunkEnd + (chunkSize % 2);
    if (strict && offset !== wav.length && offset + 8 > wav.length) {
      throw new Error('truncated chunk header or padding');
    }
  }

  if (!(byteRate > 0) || dataSize === undefined) {
    throw new Error('missing usable fmt or data chunk');
  }
  if (strict && (!(dataSize > 0) || dataSize % blockAlign !== 0)) {
    throw new Error('empty or incomplete sample data');
  }
  return dataSize / byteRate;
};
const timEvidenceHash =
  '7ce314184b985465da49ef70bc4d0b0b263f68ff445829330df6e8befa78f30c';
const timTreatmentPath = resolve(
  process.cwd(),
  'src/reel/treatments/tim-kochjar-reference.json',
);

const requiredTopLevel = [
  'title',
  'archetype',
  'preset',
  'treatment',
  'scriptLocked',
  'format',
  'brand',
  'sourceTruth',
  'captures',
  'scenes',
  'shots',
  'beats',
  'audio',
  'captionCues',
];

for (const field of requiredTopLevel) {
  if (!(field in story)) {
    errors.push(`Missing top-level field: ${field}`);
  }
}

if (!supportedPresets.has(story.preset)) {
  errors.push(
    `Unsupported preset ${story.preset ?? '<missing>'}; expected ${[...supportedPresets].join(', ')}`,
  );
}

if (!Array.isArray(story.sourceTruth) || story.sourceTruth.length === 0) {
  errors.push('sourceTruth must contain at least one source');
}

if (!Array.isArray(story.scenes) || story.scenes.length === 0) {
  errors.push('scenes must contain at least one scene');
}

for (const heading of [
  '## Brief',
  '## Story lock',
  '## Source and task contract',
  '## Capture manifest',
  '## Timeline',
  '## Shot and motion plan',
  '## Speech and beat timing',
  '## Acceptance criteria',
  '## Evidence and placeholders',
]) {
  if (!briefText.includes(heading)) {
    errors.push(`REEL.md is missing ${heading}`);
  }
}

if (story.preset && story.preset !== 'custom') {
  const presetPath = resolve(
    process.cwd(),
    `src/reel/presets/${story.preset}.json`,
  );
  if (!existsSync(presetPath)) {
    errors.push(`Optimized preset definition is missing: ${story.preset}`);
  } else {
    const preset = JSON.parse(readFileSync(presetPath, 'utf8'));
    if (preset.id !== story.preset) {
      errors.push(
        `Preset definition id ${preset.id ?? '<missing>'} does not match ${story.preset}`,
      );
    }
  }

  if (!briefText.includes(`Preset: ${story.preset}`)) {
    errors.push(`REEL.md must record Preset: ${story.preset}`);
  }

  const shotSection =
    briefText.split('## Shot and motion plan')[1]?.split(/\n## /)[0] ?? '';
  const plannedSceneIds = new Set(
    shotSection
      .split(/\r?\n/)
      .filter((line) => line.trim().startsWith('|'))
      .map((line) => line.split('|').map((cell) => cell.trim()))
      .filter(
        (cells) =>
          cells.length > 3 &&
          cells[1] &&
          cells[1] !== 'Shot ID' &&
          !/^[-:]+$/.test(cells[1]),
      )
      .map((cells) => cells[2]),
  );
  for (const scene of story.scenes ?? []) {
    if (!plannedSceneIds.has(scene.id)) {
      errors.push(
        `Optimized preset ${story.preset} requires a shot plan for scene ${scene.id}`,
      );
    }
  }
}

for (const field of ['width', 'height', 'fps']) {
  if (!(story.format?.[field] > 0)) {
    errors.push(`format.${field} must be positive`);
  }
}

const sourceIds = new Set();
for (const source of story.sourceTruth ?? []) {
  for (const field of ['id', 'type', 'ref', 'proves']) {
    if (!String(source[field] ?? '').trim()) {
      errors.push(`Source ${source.id ?? '<unknown>'} is missing ${field}`);
    }
  }
  if (sourceIds.has(source.id)) {
    errors.push(`Duplicate source id: ${source.id}`);
  }
  sourceIds.add(source.id);
}

const captureIds = new Set();
const validateCapturePath = (capture, field, value) => {
  const normalized = String(value ?? '').replaceAll('\\', '/');
  if (
    !normalized.startsWith('captures/') ||
    normalized.includes('..') ||
    /^https?:/i.test(normalized)
  ) {
    errors.push(
      `Capture ${capture.id ?? '<unknown>'} ${field} must be a local public/captures path`,
    );
    return undefined;
  }
  const fullPath = resolve(process.cwd(), 'public', normalized);
  if (!existsSync(fullPath)) {
    errors.push(
      `Capture ${capture.id ?? '<unknown>'} ${field} does not exist in public/: ${normalized}`,
    );
    return undefined;
  }
  return fullPath;
};
const validateCapturePng = (capture, field, path) => {
  if (!path) {
    return undefined;
  }
  if (extname(path).toLowerCase() !== '.png') {
    errors.push(`Capture ${capture.id} ${field} must be a PNG file`);
    return undefined;
  }
  if (statSync(path).size > 134217728) {
    errors.push(
      `Capture ${capture.id} ${field} exceeds the 128 MB compressed PNG limit`,
    );
    return undefined;
  }
  const image = readFileSync(path);
  const pngSignature = Buffer.from([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
  ]);
  if (image.length < 45 || !image.subarray(0, 8).equals(pngSignature)) {
    errors.push(`Capture ${capture.id} ${field} must have a valid PNG header`);
    return undefined;
  }

  let offset = 8;
  let width;
  let height;
  let bitDepth;
  let colorType;
  let compressionMethod;
  let filterMethod;
  let interlace;
  const imageData = [];
  let foundIend = false;
  let foundPalette = false;
  const crc32 = (buffer) => {
    let crc = 0xffffffff;
    for (const byte of buffer) {
      crc ^= byte;
      for (let bit = 0; bit < 8; bit += 1) {
        crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
      }
    }
    return (crc ^ 0xffffffff) >>> 0;
  };
  try {
    while (offset + 12 <= image.length) {
      const chunkLength = image.readUInt32BE(offset);
      const chunkType = image.toString('ascii', offset + 4, offset + 8);
      const dataStart = offset + 8;
      const dataEnd = dataStart + chunkLength;
      const chunkEnd = dataEnd + 4;
      if (chunkEnd > image.length) {
        throw new Error(`truncated ${chunkType || 'unknown'} chunk`);
      }
      const expectedCrc = image.readUInt32BE(dataEnd);
      const actualCrc = crc32(image.subarray(offset + 4, dataEnd));
      if (actualCrc !== expectedCrc) {
        throw new Error(`invalid ${chunkType || 'unknown'} chunk checksum`);
      }
      if (chunkType === 'IHDR') {
        if (offset !== 8 || chunkLength !== 13) {
          throw new Error('invalid IHDR chunk');
        }
        width = image.readUInt32BE(dataStart);
        height = image.readUInt32BE(dataStart + 4);
        bitDepth = image[dataStart + 8];
        colorType = image[dataStart + 9];
        compressionMethod = image[dataStart + 10];
        filterMethod = image[dataStart + 11];
        interlace = image[dataStart + 12];
      } else if (chunkType === 'IDAT') {
        imageData.push(image.subarray(dataStart, dataEnd));
      } else if (chunkType === 'PLTE') {
        foundPalette = true;
      } else if (chunkType === 'IEND') {
        if (chunkLength !== 0) {
          throw new Error('invalid IEND chunk');
        }
        foundIend = true;
        offset = chunkEnd;
        break;
      }
      offset = chunkEnd;
    }

    const colorModes = new Map([
      [0, {channels: 1, bitDepths: [1, 2, 4, 8, 16]}],
      [2, {channels: 3, bitDepths: [8, 16]}],
      [3, {channels: 1, bitDepths: [1, 2, 4, 8]}],
      [4, {channels: 2, bitDepths: [8, 16]}],
      [6, {channels: 4, bitDepths: [8, 16]}],
    ]);
    const colorMode = colorModes.get(colorType);
    if (
      !(width > 0) ||
      !(height > 0) ||
      !colorMode ||
      !colorMode.bitDepths.includes(bitDepth) ||
      (colorType === 3 && !foundPalette) ||
      compressionMethod !== 0 ||
      filterMethod !== 0 ||
      interlace !== 0 ||
      imageData.length === 0 ||
      !foundIend ||
      offset !== image.length
    ) {
      throw new Error('incomplete or unsupported PNG structure');
    }
    const rowBytes = Math.ceil(
      (width * colorMode.channels * bitDepth) / 8,
    );
    const expectedBytes = (rowBytes + 1) * height;
    if (
      width > 32768 ||
      height > 32768 ||
      expectedBytes > 268435456
    ) {
      throw new Error('decoded image dimensions exceed the capture limit');
    }
    const pixels = inflateSync(Buffer.concat(imageData), {
      maxOutputLength: expectedBytes,
    });
    if (pixels.length !== expectedBytes) {
      throw new Error('decoded pixel data has an unexpected size');
    }
    for (let row = 0; row < height; row += 1) {
      if (pixels[row * (rowBytes + 1)] > 4) {
        throw new Error(`scanline ${row} has an invalid filter type`);
      }
    }
    return {width, height};
  } catch (error) {
    errors.push(
      `Capture ${capture.id} ${field} must be a readable non-interlaced PNG: ${error.message}`,
    );
    return undefined;
  }
};
const validateBounds = (capture, value, path) => {
  if (Array.isArray(value)) {
    value.forEach((entry, index) =>
      validateBounds(capture, entry, `${path}[${index}]`),
    );
    return;
  }
  if (!value || typeof value !== 'object') {
    errors.push(`Capture ${capture.id} layout ${path} must contain bounds`);
    return;
  }
  for (const field of ['x', 'y', 'width', 'height']) {
    if (
      typeof value[field] !== 'number' ||
      !Number.isFinite(value[field]) ||
      (field !== 'x' && field !== 'y' && !(value[field] > 0))
    ) {
      errors.push(
        `Capture ${capture.id} layout ${path}.${field} must be a finite ${field === 'x' || field === 'y' ? 'number' : 'positive number'}`,
      );
    }
  }
};

if (!Array.isArray(story.captures)) {
  errors.push('captures must be an array');
}
const captures = Array.isArray(story.captures) ? story.captures : [];
for (const capture of captures) {
  if (!capture || typeof capture !== 'object' || Array.isArray(capture)) {
    errors.push('captures entries must be objects');
    continue;
  }
  for (const field of [
    'id',
    'sourceRef',
    'route',
    'state',
    'fullFrameSrc',
    'layoutSrc',
    'cutoutSrcs',
    'viewport',
    'privacyClass',
  ]) {
    if (!(field in capture)) {
      errors.push(`Capture ${capture.id ?? '<unknown>'} is missing ${field}`);
    }
  }
  if (captureIds.has(capture.id)) {
    errors.push(`Duplicate capture id: ${capture.id}`);
  }
  captureIds.add(capture.id);
  if (!sourceIds.has(capture.sourceRef)) {
    errors.push(
      `Capture ${capture.id} references unknown source ${capture.sourceRef}`,
    );
  }
  for (const field of ['id', 'route', 'state']) {
    if (!String(capture[field] ?? '').trim()) {
      errors.push(`Capture ${capture.id ?? '<unknown>'} has empty ${field}`);
    }
  }
  if (!supportedPrivacyClasses.has(capture.privacyClass)) {
    errors.push(
      `Capture ${capture.id} has unsupported privacyClass ${capture.privacyClass}`,
    );
  }
  for (const field of ['width', 'height', 'deviceScaleFactor']) {
    if (
      typeof capture.viewport?.[field] !== 'number' ||
      !Number.isFinite(capture.viewport[field]) ||
      !(capture.viewport[field] > 0) ||
      (field !== 'deviceScaleFactor' && !Number.isInteger(capture.viewport[field]))
    ) {
      errors.push(`Capture ${capture.id} viewport.${field} must be positive`);
    }
  }
  const layoutPath = validateCapturePath(
    capture,
    'layoutSrc',
    capture.layoutSrc,
  );
  const fullFramePath = validateCapturePath(
    capture,
    'fullFrameSrc',
    capture.fullFrameSrc,
  );
  const fullFrameDimensions = validateCapturePng(
    capture,
    'fullFrameSrc',
    fullFramePath,
  );
  if (!Array.isArray(capture.cutoutSrcs)) {
    errors.push(`Capture ${capture.id} cutoutSrcs must be an array`);
  } else {
    for (const cutoutSrc of capture.cutoutSrcs) {
      const cutoutPath = validateCapturePath(
        capture,
        'cutoutSrcs entry',
        cutoutSrc,
      );
      validateCapturePng(capture, 'cutoutSrcs entry', cutoutPath);
    }
  }
  if (layoutPath) {
    try {
      if (statSync(layoutPath).size > 10485760) {
        throw new Error('layout JSON exceeds the 10 MB limit');
      }
      const layout = JSON.parse(readFileSync(layoutPath, 'utf8'));
      if (!layout || typeof layout !== 'object' || Array.isArray(layout)) {
        errors.push(`Capture ${capture.id} layoutSrc must contain a JSON object`);
      } else if (
        typeof layout.pageWidth !== 'number' ||
        !Number.isFinite(layout.pageWidth) ||
        !(layout.pageWidth > 0) ||
        typeof layout.pageHeight !== 'number' ||
        !Number.isFinite(layout.pageHeight) ||
        !(layout.pageHeight > 0) ||
        !layout.elements ||
        typeof layout.elements !== 'object' ||
        Array.isArray(layout.elements)
      ) {
        errors.push(
          `Capture ${capture.id} layoutSrc must define positive pageWidth/pageHeight and an elements object`,
        );
      } else {
        if (
          layout.pageWidth !== capture.viewport.width ||
          fullFrameDimensions?.width !==
            Math.round(layout.pageWidth * capture.viewport.deviceScaleFactor) ||
          fullFrameDimensions?.height !==
            Math.round(layout.pageHeight * capture.viewport.deviceScaleFactor)
        ) {
          errors.push(
            `Capture ${capture.id} full frame, layout, viewport, and DPR dimensions must agree`,
          );
        }
        for (const [key, bounds] of Object.entries(layout.elements)) {
          validateBounds(capture, bounds, `elements.${key}`);
        }
      }
    } catch {
      errors.push(`Capture ${capture.id} layoutSrc must contain valid JSON`);
    }
  }
}

const sceneIds = new Set();
const timelineSection = briefText.split('## Timeline')[1]?.split(/\n## /)[0] ?? '';
const timelineRows = timelineSection
  .split(/\r?\n/)
  .filter((line) => line.trim().startsWith('|'))
  .map((line) => line.split('|').map((cell) => cell.trim()))
  .filter(
    (cells) =>
      cells.length > 2 &&
      cells[2] !== 'Scene ID' &&
      !/^[-:]+$/.test(cells[2]),
  );
const timelineSceneIds = timelineRows.map((cells) => cells[2]);
const requiredSceneFields = [
  'id',
  'kind',
  'durationSeconds',
  'purpose',
  'headline',
  'detail',
  'items',
  'narration',
  'action',
  'stateBefore',
  'stateAfter',
  'sourceRef',
];

for (const scene of story.scenes ?? []) {
  for (const field of requiredSceneFields) {
    if (!(field in scene)) {
      errors.push(`Scene ${scene.id ?? '<unknown>'} is missing ${field}`);
    }
  }

  if (sceneIds.has(scene.id)) {
    errors.push(`Duplicate scene id: ${scene.id}`);
  }
  sceneIds.add(scene.id);

  if (!(scene.durationSeconds > 0)) {
    errors.push(`Scene ${scene.id} must have a positive durationSeconds`);
  }

  for (const field of [
    'id',
    'kind',
    'purpose',
    'headline',
    'action',
    'stateBefore',
    'stateAfter',
    'sourceRef',
  ]) {
    if (!String(scene[field] ?? '').trim()) {
      errors.push(`Scene ${scene.id ?? '<unknown>'} has empty ${field}`);
    }
  }

  if (!Array.isArray(scene.items)) {
    errors.push(`Scene ${scene.id} items must be an array`);
  }

  if (!supportedSceneKinds.has(scene.kind)) {
    errors.push(
      `Scene ${scene.id} has unsupported kind ${scene.kind}; expected ${[...supportedSceneKinds].join(', ')}`,
    );
  }

  if (String(scene.caption ?? '').trim()) {
    errors.push(
      `Scene ${scene.id} uses legacy caption; move phrase timing to captionCues`,
    );
  }

  if (!sourceIds.has(scene.sourceRef)) {
    errors.push(`Scene ${scene.id} references unknown source ${scene.sourceRef}`);
  }
}

  const duration = (story.scenes ?? []).reduce(
    (sum, scene) => sum + scene.durationSeconds,
    0,
  );
  errors.push(...validateMusic(story, duration, measureWavDurationSeconds));
  const sceneRanges = new Map();
  let sceneStart = 0;
  for (const scene of story.scenes ?? []) {
    sceneRanges.set(scene.id, {
      start: sceneStart,
      end: sceneStart + scene.durationSeconds,
      scene,
    });
    sceneStart += scene.durationSeconds;
  }

  const shotIds = new Set();
  const shotsByScene = new Map();
  let expectedShotStart = 0;
  let expectedShotStartFrame = 0;
  for (const shot of story.shots ?? []) {
    for (const field of [
      'id',
      'sceneId',
      'startSeconds',
      'durationSeconds',
      'dominantSubject',
      'camera',
      'contentAction',
      'holdSeconds',
      'boundary',
    ]) {
      if (!(field in shot)) {
        errors.push(`Shot ${shot.id ?? '<unknown>'} is missing ${field}`);
      }
    }

    if (shotIds.has(shot.id)) {
      errors.push(`Duplicate shot id: ${shot.id}`);
    }
    shotIds.add(shot.id);

    const sceneRange = sceneRanges.get(shot.sceneId);
    if (!sceneRange) {
      errors.push(`Shot ${shot.id} references unknown scene ${shot.sceneId}`);
    }
    if (!(shot.durationSeconds > 0)) {
      errors.push(`Shot ${shot.id} must have a positive durationSeconds`);
    }
    if (!(shot.startSeconds >= 0)) {
      errors.push(`Shot ${shot.id} must have a non-negative startSeconds`);
    }
    if (
      !(shot.holdSeconds > 0) ||
      shot.holdSeconds > shot.durationSeconds ||
      toFrame(shot.holdSeconds) < 2
    ) {
      errors.push(
        `Shot ${shot.id} holdSeconds must occupy at least two frames and not exceed its duration`,
      );
    }
    if (!supportedBoundaries.has(shot.boundary)) {
      errors.push(
        `Shot ${shot.id} has unsupported boundary ${shot.boundary}`,
      );
    }
    if (!supportedCameras.has(shot.camera)) {
      errors.push(`Shot ${shot.id} has unsupported camera ${shot.camera}`);
    }
    if ('captureRef' in shot) {
      if (
        typeof shot.captureRef !== 'string' ||
        !shot.captureRef.trim()
      ) {
        errors.push(`Shot ${shot.id} captureRef must be a non-empty string`);
      } else if (!captureIds.has(shot.captureRef)) {
        errors.push(
          `Shot ${shot.id} references unknown capture ${shot.captureRef}`,
        );
      }
    }
    if (
      Number.isFinite(shot.startSeconds) &&
      Number.isFinite(shot.durationSeconds) &&
      toFrame(shot.startSeconds + shot.durationSeconds) <=
        toFrame(shot.startSeconds)
    ) {
      errors.push(
        `Shot ${shot.id} must occupy at least one frame at ${story.format.fps}fps`,
      );
    }
    for (const field of ['dominantSubject', 'camera', 'contentAction']) {
      if (!String(shot[field] ?? '').trim()) {
        errors.push(`Shot ${shot.id ?? '<unknown>'} has empty ${field}`);
      }
    }
    if (Math.abs(shot.startSeconds - expectedShotStart) > epsilon) {
      errors.push(
        `Shot ${shot.id} must start at ${expectedShotStart}s; found ${shot.startSeconds}s`,
      );
    }
    if (toFrame(shot.startSeconds) !== expectedShotStartFrame) {
      errors.push(
        `Shot ${shot.id} must start on contiguous frame ${expectedShotStartFrame}; found ${toFrame(shot.startSeconds)}`,
      );
    }
    expectedShotStart = shot.startSeconds + shot.durationSeconds;
    expectedShotStartFrame = toFrame(expectedShotStart);

    if (
      sceneRange &&
      (shot.startSeconds < sceneRange.start - epsilon ||
        shot.startSeconds + shot.durationSeconds > sceneRange.end + epsilon)
    ) {
      errors.push(`Shot ${shot.id} falls outside scene ${shot.sceneId}`);
    }

    const sceneShots = shotsByScene.get(shot.sceneId) ?? [];
    sceneShots.push(shot);
    shotsByScene.set(shot.sceneId, sceneShots);
  }

  if (!Array.isArray(story.shots) || story.shots.length === 0) {
    errors.push('shots must contain at least one shot');
  } else if (Math.abs(expectedShotStart - duration) > epsilon) {
    errors.push(
      `Shots must cover the ${duration}s composition; found ${expectedShotStart}s`,
    );
  }

  for (const scene of story.scenes ?? []) {
    if (!shotsByScene.has(scene.id)) {
      errors.push(`Scene ${scene.id} requires at least one shot`);
    }
  }

  const beatIds = new Set();
  const beatCountByShot = new Map();
  const visualBeatCountByScene = new Map();
  const speechBeatScenes = new Set();
  const speechBeats = [];
  let previousBeatAt = -1;
  for (const beat of story.beats ?? []) {
    for (const field of [
      'id',
      'sceneId',
      'shotId',
      'atSeconds',
      'kind',
      'anchorText',
      'purpose',
    ]) {
      if (!(field in beat)) {
        errors.push(`Beat ${beat.id ?? '<unknown>'} is missing ${field}`);
      }
    }

    if (beatIds.has(beat.id)) {
      errors.push(`Duplicate beat id: ${beat.id}`);
    }
    beatIds.add(beat.id);
    if (!supportedBeatKinds.has(beat.kind)) {
      errors.push(`Beat ${beat.id} has unsupported kind ${beat.kind}`);
    }
    if (!String(beat.purpose ?? '').trim()) {
      errors.push(`Beat ${beat.id} has empty purpose`);
    }
    if (!(beat.atSeconds >= 0) || beat.atSeconds < previousBeatAt - epsilon) {
      errors.push(`Beat ${beat.id} is not in chronological order`);
    }
    previousBeatAt = beat.atSeconds;

    const shot = (story.shots ?? []).find((candidate) => candidate.id === beat.shotId);
    if (!shot) {
      errors.push(`Beat ${beat.id} references unknown shot ${beat.shotId}`);
    } else {
      if (shot.sceneId !== beat.sceneId) {
        errors.push(
          `Beat ${beat.id} scene ${beat.sceneId} does not match shot ${shot.id}`,
        );
      }
      if (
        beat.atSeconds < shot.startSeconds - epsilon ||
        beat.atSeconds >=
          shot.startSeconds + shot.durationSeconds - epsilon
      ) {
        errors.push(`Beat ${beat.id} falls outside shot ${shot.id}`);
      }
      const beatFrame = toFrame(beat.atSeconds);
      const shotStartFrame = toFrame(shot.startSeconds);
      const shotEndFrame = toFrame(
        shot.startSeconds + shot.durationSeconds,
      );
      if (beatFrame < shotStartFrame || beatFrame >= shotEndFrame) {
        errors.push(
          `Beat ${beat.id} must resolve within shot ${shot.id}'s frame range`,
        );
      }
      if (
        beat.kind === 'speech' ||
        beat.kind === 'action' ||
        beat.kind === 'state'
      ) {
        beatCountByShot.set(shot.id, (beatCountByShot.get(shot.id) ?? 0) + 1);
      }
      if (beat.kind === 'action' || beat.kind === 'state') {
        visualBeatCountByScene.set(
          beat.sceneId,
          (visualBeatCountByScene.get(beat.sceneId) ?? 0) + 1,
        );
      }
    }

    if (beat.kind === 'speech') {
      const scene = sceneRanges.get(beat.sceneId)?.scene;
      const anchor = String(beat.anchorText ?? '').trim();
      if (!anchor) {
        errors.push(`Speech beat ${beat.id} requires anchorText`);
      } else if (!String(scene?.narration ?? '').includes(anchor)) {
        errors.push(
          `Speech beat ${beat.id} anchorText is not in scene ${beat.sceneId} narration`,
        );
      }
      speechBeatScenes.add(beat.sceneId);
      speechBeats.push(beat);
    }
  }

  if (!Array.isArray(story.beats) || story.beats.length === 0) {
    errors.push('beats must contain at least one visual or speech beat');
  }
  for (const shot of story.shots ?? []) {
    if (!beatCountByShot.has(shot.id)) {
      errors.push(
        `Shot ${shot.id} requires at least one speech, action, or state beat`,
      );
    }
  }
  for (const scene of story.scenes ?? []) {
    const minimumVisualBeats =
      scene.kind === 'context' || scene.kind === 'task'
        ? Math.max(scene.items.length, 1)
        : scene.items.length;
    if ((visualBeatCountByScene.get(scene.id) ?? 0) < minimumVisualBeats) {
      errors.push(
        `Scene ${scene.id} requires enough action or state beats for its visual phases`,
      );
    }
  }

  for (const [index, shot] of (story.shots ?? []).entries()) {
    const expectedBoundary =
      index === story.shots.length - 1 ? 'end' : 'cut';
    if (shot.boundary !== expectedBoundary) {
      errors.push(
        `Shot ${shot.id} boundary must be ${expectedBoundary} in the neutral starter`,
      );
    }
  }

  const captionIds = new Set();
  const captionScenes = new Set();
  let previousCaptionEnd = 0;
  for (const cue of story.captionCues ?? []) {
    for (const field of [
      'id',
      'sceneId',
      'startSeconds',
      'endSeconds',
      'text',
    ]) {
      if (!(field in cue)) {
        errors.push(`Caption cue ${cue.id ?? '<unknown>'} is missing ${field}`);
      }
    }
    if (captionIds.has(cue.id)) {
      errors.push(`Duplicate caption cue id: ${cue.id}`);
    }
    captionIds.add(cue.id);
    if (!String(cue.text ?? '').trim()) {
      errors.push(`Caption cue ${cue.id} has empty text`);
    }
    if (!(cue.startSeconds >= 0) || !(cue.endSeconds > cue.startSeconds)) {
      errors.push(`Caption cue ${cue.id} has an invalid time range`);
    }
    if (
      Math.ceil(cue.startSeconds * story.format.fps) >=
      Math.ceil(cue.endSeconds * story.format.fps)
    ) {
      errors.push(
        `Caption cue ${cue.id} must contain at least one rendered frame`,
      );
    }
    if (cue.startSeconds < previousCaptionEnd - epsilon) {
      errors.push(`Caption cue ${cue.id} overlaps the previous caption cue`);
    }
    previousCaptionEnd = cue.endSeconds;

    const sceneRange = sceneRanges.get(cue.sceneId);
    if (!sceneRange) {
      errors.push(`Caption cue ${cue.id} references unknown scene ${cue.sceneId}`);
    } else if (
      cue.startSeconds < sceneRange.start - epsilon ||
      cue.endSeconds > sceneRange.end + epsilon
    ) {
      errors.push(`Caption cue ${cue.id} falls outside scene ${cue.sceneId}`);
    }
    captionScenes.add(cue.sceneId);
  }

  if (!Array.isArray(story.captionCues)) {
    errors.push('captionCues must be an array');
  }

  for (const beat of speechBeats) {
    const beatFrameSeconds = toFrame(beat.atSeconds) / story.format.fps;
    const activeCue = (story.captionCues ?? []).find(
      (cue) =>
        cue.sceneId === beat.sceneId &&
        beatFrameSeconds >= cue.startSeconds &&
        beatFrameSeconds < cue.endSeconds,
    );
    if (
      !activeCue ||
      !normalizeSpeech(activeCue.text).includes(
        normalizeSpeech(beat.anchorText),
      )
    ) {
      errors.push(
        `Speech beat ${beat.id} must align with a caption cue containing its anchorText`,
      );
    }
  }

  const narrationScenes = (story.scenes ?? []).filter((scene) =>
    String(scene.narration ?? '').trim(),
  );
  const narrationTrack = story.audio?.narration;
  let measuredNarrationDuration;
  if (narrationScenes.length > 0) {
    if (!narrationTrack) {
      errors.push('Narrated stories require audio.narration');
    }
    for (const scene of narrationScenes) {
      if (!captionScenes.has(scene.id)) {
        errors.push(`Narrated scene ${scene.id} requires a caption cue`);
      }
      if (!speechBeatScenes.has(scene.id)) {
        errors.push(`Narrated scene ${scene.id} requires a speech beat`);
      }
      const captionText = (story.captionCues ?? [])
        .filter((cue) => cue.sceneId === scene.id)
        .map((cue) => cue.text)
        .join(' ');
      if (normalizeSpeech(captionText) !== normalizeSpeech(scene.narration)) {
        errors.push(
          `Caption cues for scene ${scene.id} must cover its locked narration`,
        );
      }
    }
  } else if (narrationTrack) {
    errors.push('audio.narration is present but no scene contains narration');
  }

  if (!story.audio || !('narration' in story.audio)) {
    errors.push('audio.narration must be present and may be null');
  }
  if (narrationTrack) {
    for (const field of [
      'src',
      'durationSeconds',
      'provenanceRef',
      'qualityGate',
      'approvalNote',
      'volume',
    ]) {
      if (!(field in narrationTrack)) {
        errors.push(`audio.narration is missing ${field}`);
      }
    }
    const src = String(narrationTrack.src ?? '').replaceAll('\\', '/');
    if (
      !src.startsWith('audio/') ||
      src.includes('..') ||
      /^https?:/i.test(src)
    ) {
      errors.push('audio.narration.src must be a local public/audio path');
    }
    const audioPath = resolve(process.cwd(), 'public', src);
    if (src.startsWith('audio/') && !existsSync(audioPath)) {
      errors.push(`audio.narration.src does not exist in public/: ${src}`);
    } else if (src.startsWith('audio/')) {
      try {
        measuredNarrationDuration = measureWavDurationSeconds(audioPath);
        const durationTolerance = Math.max(0.05, 1 / story.format.fps);
        if (
          Number.isFinite(narrationTrack.durationSeconds) &&
          Math.abs(
            measuredNarrationDuration - narrationTrack.durationSeconds,
          ) >
            durationTolerance
        ) {
          errors.push(
            `audio.narration.durationSeconds must match the measured WAV duration (${measuredNarrationDuration.toFixed(3)}s)`,
          );
        }
      } catch (error) {
        errors.push(
          `audio.narration.src must be a readable WAV file: ${error.message}`,
        );
      }
    }
    if (
      !(narrationTrack.durationSeconds > 0) ||
      narrationTrack.durationSeconds > duration + epsilon ||
      (measuredNarrationDuration !== undefined &&
        measuredNarrationDuration > duration + epsilon)
    ) {
      errors.push(
        `audio.narration.durationSeconds must be within the ${duration}s composition`,
      );
    }
    if (
      !(narrationTrack.volume >= 0) ||
      !(narrationTrack.volume <= 1)
    ) {
      errors.push('audio.narration.volume must be between 0 and 1');
    }
    const provenanceRef = String(
      narrationTrack.provenanceRef ?? '',
    ).replaceAll('\\', '/');
    if (!provenanceRef) {
      errors.push('audio.narration.provenanceRef is required');
    } else if (
      !provenanceRef.startsWith('audio/') ||
      provenanceRef.includes('..') ||
      /^https?:/i.test(provenanceRef)
    ) {
      errors.push(
        'audio.narration.provenanceRef must be a local public/audio path',
      );
    } else if (!existsSync(resolve(process.cwd(), 'public', provenanceRef))) {
      errors.push(
        `audio.narration.provenanceRef does not exist in public/: ${provenanceRef}`,
      );
    } else {
      let provenance;
      try {
        provenance = JSON.parse(
          readFileSync(
            resolve(process.cwd(), 'public', provenanceRef),
            'utf8',
          ),
        );
      } catch {
        errors.push(
          `audio.narration.provenanceRef must contain valid JSON: ${provenanceRef}`,
        );
      }

      if (
        !provenance ||
        typeof provenance !== 'object' ||
        Array.isArray(provenance)
      ) {
        errors.push(
          `audio.narration.provenanceRef must contain a JSON object: ${provenanceRef}`,
        );
      } else {
        if (narrationTrack.qualityGate === 'enhanced-kokoro') {
          const engineName = String(
            provenance.engine?.name ?? provenance.engine ?? '',
          ).toLowerCase();
          const modelId = String(
            provenance.model?.id ?? provenance.model ?? '',
          ).toLowerCase();
          if (
            provenance.mode !== 'enhanced' ||
            !['kokoro-onnx', 'mlx-audio'].includes(engineName) ||
            !modelId.includes('kokoro')
          ) {
            errors.push(
              'audio.narration provenance must report enhanced mode and Kokoro',
            );
          }
        } else if (
          narrationTrack.qualityGate === 'user-approved-alternative'
        ) {
          if (!String(narrationTrack.approvalNote ?? '').trim()) {
            errors.push(
              'user-approved-alternative narration requires approvalNote',
            );
          }
        } else {
          errors.push(
            `Unsupported audio.narration.qualityGate: ${narrationTrack.qualityGate}`,
          );
        }
      }
    }
    const finalCueEnd = (story.captionCues ?? []).at(-1)?.endSeconds ?? 0;
    const audioDuration =
      measuredNarrationDuration ?? narrationTrack.durationSeconds;
    if (finalCueEnd > audioDuration + epsilon) {
      errors.push('Caption cues extend beyond audio.narration.durationSeconds');
    }
  }

const storySceneIds = (story.scenes ?? []).map((scene) => scene.id);
if (JSON.stringify(timelineSceneIds) !== JSON.stringify(storySceneIds)) {
  errors.push(
    `REEL.md timeline scene order must be ${storySceneIds.join(' -> ')}; found ${timelineSceneIds.join(' -> ') || '<none>'}`,
  );
}

const parseTimestamp = (value) => {
  const normalized = value.trim().replace(/s$/i, '');
  if (normalized.includes(':')) {
    const parts = normalized.split(':').map(Number);
    if (parts.length !== 2 || parts.some((part) => Number.isNaN(part))) {
      return Number.NaN;
    }
    return parts[0] * 60 + parts[1];
  }
  return Number(normalized);
};

let expectedStart = 0;
for (let index = 0; index < Math.min(timelineRows.length, storySceneIds.length); index += 1) {
  const range = timelineRows[index][1].split(/\s*[–-]\s*/);
  const actualStart = range.length === 2 ? parseTimestamp(range[0]) : Number.NaN;
  const actualEnd = range.length === 2 ? parseTimestamp(range[1]) : Number.NaN;
  const expectedEnd = expectedStart + story.scenes[index].durationSeconds;

  if (
    Number.isNaN(actualStart) ||
    Number.isNaN(actualEnd) ||
    Math.abs(actualStart - expectedStart) > 0.01 ||
    Math.abs(actualEnd - expectedEnd) > 0.01
  ) {
    errors.push(
      `REEL.md timeline range for ${story.scenes[index].id} must be ${expectedStart}-${expectedEnd}s; found ${timelineRows[index][1]}`,
    );
  }
  expectedStart = expectedEnd;
}

const hasNarration = (story.scenes ?? []).some((scene) =>
  String(scene.narration ?? '').trim(),
);
if (hasNarration && story.scriptLocked !== true) {
  errors.push('scriptLocked must be true when narration is present');
}

const shotSection =
  briefText.split('## Shot and motion plan')[1]?.split(/\n## /)[0] ?? '';
const briefShotRows = shotSection
  .split(/\r?\n/)
  .filter((line) => line.trim().startsWith('|'))
  .map((line) => line.split('|').map((cell) => cell.trim()))
  .filter(
    (cells) =>
      cells.length > 2 &&
      cells[1] &&
      cells[1] !== 'Shot ID' &&
      !/^[-:]+$/.test(cells[1]),
  );
const briefShotIds = briefShotRows.map((cells) => cells[1]);
const storyShotIds = (story.shots ?? []).map((shot) => shot.id);
if (JSON.stringify(briefShotIds) !== JSON.stringify(storyShotIds)) {
  errors.push(
    `REEL.md shot order must be ${storyShotIds.join(' -> ')}; found ${briefShotIds.join(' -> ') || '<none>'}`,
  );
}
for (
  let index = 0;
  index < Math.min(briefShotRows.length, story.shots?.length ?? 0);
  index += 1
) {
  const row = briefShotRows[index];
  const shot = story.shots[index];
  const range = row[3].split(/\s*[–-]\s*/);
  const start = range.length === 2 ? parseTimestamp(range[0]) : Number.NaN;
  const end = range.length === 2 ? parseTimestamp(range[1]) : Number.NaN;
  const hold = parseTimestamp(row[7]);
  if (
    row[2] !== shot.sceneId ||
    Number.isNaN(start) ||
    Number.isNaN(end) ||
    Number.isNaN(hold) ||
    Math.abs(start - shot.startSeconds) > epsilon ||
    Math.abs(end - shot.startSeconds - shot.durationSeconds) > epsilon ||
    row[4] !== shot.dominantSubject ||
    row[5] !== shot.camera ||
    row[6] !== shot.contentAction ||
    Math.abs(hold - shot.holdSeconds) > epsilon ||
    row[8] !== shot.boundary
  ) {
    errors.push(
      `REEL.md shot row for ${shot.id} must match its executable story contract`,
    );
  }
}

const captureSection =
  briefText.split('## Capture manifest')[1]?.split(/\n## /)[0] ?? '';
const briefCaptureRows = captureSection
  .split(/\r?\n/)
  .filter((line) => line.trim().startsWith('|'))
  .map((line) => line.split('|').map((cell) => cell.trim()))
  .filter(
    (cells) =>
      cells.length > 2 &&
      cells[1] &&
      cells[1] !== 'Capture ID' &&
      !/^[-:]+$/.test(cells[1]),
  );
const briefCaptureIds = briefCaptureRows.map((cells) => cells[1]);
const storyCaptureIds = captures.map((capture) => capture.id);
if (JSON.stringify(briefCaptureIds) !== JSON.stringify(storyCaptureIds)) {
  errors.push(
    `REEL.md capture order must be ${storyCaptureIds.join(' -> ') || '<none>'}; found ${briefCaptureIds.join(' -> ') || '<none>'}`,
  );
}
for (
  let index = 0;
  index < Math.min(briefCaptureRows.length, captures.length);
  index += 1
) {
  const row = briefCaptureRows[index];
  const capture = captures[index];
  const expectedCutouts = capture.cutoutSrcs.length
    ? capture.cutoutSrcs.join(', ')
    : 'none';
  const expectedViewport =
    `${capture.viewport.width}x${capture.viewport.height}` +
    `@${capture.viewport.deviceScaleFactor}x`;
  if (
    row[2] !== capture.sourceRef ||
    row[3] !== `${capture.route} :: ${capture.state}` ||
    row[4] !== capture.fullFrameSrc ||
    row[5] !== capture.layoutSrc ||
    row[6] !== expectedCutouts ||
    row[7] !== expectedViewport ||
    row[8] !== capture.privacyClass
  ) {
    errors.push(
      `REEL.md capture row for ${capture.id} must match its executable story contract`,
    );
  }
}

const beatSection =
  briefText.split('## Speech and beat timing')[1]?.split(/\n## /)[0] ?? '';
const briefBeatRows = beatSection
  .split(/\r?\n/)
  .filter((line) => line.trim().startsWith('|'))
  .map((line) => line.split('|').map((cell) => cell.trim()))
  .filter(
    (cells) =>
      cells.length > 2 &&
      cells[1] &&
      cells[1] !== 'Beat ID' &&
      !/^[-:]+$/.test(cells[1]),
  );
const briefBeatIds = briefBeatRows.map((cells) => cells[1]);
const storyBeatIds = (story.beats ?? []).map((beat) => beat.id);
if (JSON.stringify(briefBeatIds) !== JSON.stringify(storyBeatIds)) {
  errors.push(
    `REEL.md beat order must be ${storyBeatIds.join(' -> ')}; found ${briefBeatIds.join(' -> ') || '<none>'}`,
  );
}
for (
  let index = 0;
  index < Math.min(briefBeatRows.length, story.beats?.length ?? 0);
  index += 1
) {
  const row = briefBeatRows[index];
  const beat = story.beats[index];
  const atSeconds = parseTimestamp(row[3]);
  const expectedAnchor = String(beat.anchorText ?? '').trim() || 'none';
  if (
    row[2] !== beat.shotId ||
    Number.isNaN(atSeconds) ||
    Math.abs(atSeconds - beat.atSeconds) > epsilon ||
    row[4] !== beat.kind ||
    row[5] !== expectedAnchor
  ) {
    errors.push(
      `REEL.md beat row for ${beat.id} must match shot, time, kind, and spoken anchor`,
    );
  }
}

if (
  !allowPlaceholders &&
  (storyText.includes('REPLACE_ME') || briefText.includes('REPLACE_ME'))
) {
  errors.push('Unresolved REPLACE_ME markers remain in story.json or REEL.md');
}

if (story.treatment === 'tim-kochjar-reference') {
  if (!existsSync(timTreatmentPath)) {
    errors.push('Tim Kochjar treatment selected but its treatment map is missing');
  } else {
    const treatmentText = readFileSync(timTreatmentPath, 'utf8');
    const treatment = JSON.parse(treatmentText);
    const expectedDimensions = [
      'shot-scale',
      'edit-pacing',
      'camera-continuity',
      'composition',
      'typography',
      'source-asset-fidelity',
      'transitions',
      'audio-rhythm',
    ];
    const dimensions = new Map(
      (treatment.dimensions ?? []).map((dimension) => [
        dimension.name,
        dimension,
      ]),
    );

    for (const name of expectedDimensions) {
      const dimension = dimensions.get(name);
      if (!dimension) {
        errors.push(`Tim Kochjar treatment map is missing ${name}`);
        continue;
      }
      for (const field of [
        'referenceEvidence',
        'transferDecision',
        'implementation',
        'verification',
      ]) {
        if (!String(dimension[field] ?? '').trim()) {
          errors.push(`Treatment dimension ${name} is missing ${field}`);
        }
      }
    }

    const evidencePayload = JSON.stringify(
      (treatment.dimensions ?? []).map(
        ({name, referenceEvidence}) => ({name, referenceEvidence}),
      ),
    );
    const evidenceHash = createHash('sha256')
      .update(evidencePayload)
      .digest('hex');
    if (evidenceHash !== timEvidenceHash) {
      errors.push(
        'Tim Kochjar treatment reference evidence differs from the canonical map',
      );
    }

    if (!allowPlaceholders && treatmentText.includes('REPLACE_ME')) {
      errors.push('Tim Kochjar treatment map contains unresolved REPLACE_ME markers');
    }
  }
}

if (errors.length > 0) {
  console.error('Story validation failed:');
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exit(1);
}

console.log(
  `Story valid: ${story.scenes.length} scenes, ${duration}s, ${story.archetype}, treatment=${story.treatment}`,
);
