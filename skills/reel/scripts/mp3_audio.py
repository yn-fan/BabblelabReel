"""Strict Layer III frame-duration inspection, without a decoder dependency.

This validates framing, not compressed sample contents or acoustic quality.
Xing/Info metadata frames are excluded; encoder delay/padding is deliberately
not subtracted, so every complete audio frame contributes its full sample count.
"""


class Mp3Error(ValueError):
    """Unsupported, malformed, or truncated MP3 stream."""


def mp3_duration(audio: bytes) -> float:
    if not isinstance(audio, bytes):
        raise Mp3Error("MP3 input must be bytes")
    start, end = 0, len(audio)
    if audio.startswith(b"ID3"):
        if end < 10:
            raise Mp3Error("truncated ID3v2 header")
        version, revision, flags = audio[3:6]
        allowed = {2: 0xC0, 3: 0xE0, 4: 0xF0}
        if version not in allowed or revision == 255 or flags & ~allowed[version]:
            raise Mp3Error("unsupported ID3v2 header")
        if any(value & 0x80 for value in audio[6:10]):
            raise Mp3Error("invalid ID3v2 synchsafe size")
        size = sum(value << shift for value, shift in zip(audio[6:10], (21, 14, 7, 0)))
        start = 10 + size
        if version == 4 and flags & 0x10:
            if audio[start:start + 10] != b"3DI" + audio[3:10]:
                raise Mp3Error("invalid ID3v2 footer")
            start += 10
        if start > end:
            raise Mp3Error("truncated ID3v2 tag")
    if end - start >= 128 and audio[end - 128:end - 125] == b"TAG":
        end -= 128
    offset, frames, samples = start, 0, 0
    stream = None
    declared_frames = declared_bytes = None
    while offset < end:
        if offset + 4 > end:
            raise Mp3Error("truncated MPEG header")
        header = int.from_bytes(audio[offset:offset + 4], "big")
        version = (header >> 19) & 3
        layer = (header >> 17) & 3
        bitrate_index, rate_index = (header >> 12) & 15, (header >> 10) & 3
        if (header >> 21 != 0x7FF or version == 1 or layer != 1 or
                bitrate_index in (0, 15) or rate_index == 3 or header & 3 == 2):
            raise Mp3Error("invalid or unsupported MPEG Layer III header")
        if not header & (1 << 16):
            raise Mp3Error("CRC-protected MP3 is unsupported")
        rates = (44100, 48000, 32000)
        rate = rates[rate_index] // {3: 1, 2: 2, 0: 4}[version]
        bitrates = ((0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
                    if version == 3 else
                    (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160))
        channels = 1 if (header >> 6) & 3 == 3 else 2
        signature = (version, rate, channels)
        if stream is not None and signature != stream:
            raise Mp3Error("MP3 stream parameters change between frames")
        stream = signature
        size = (144000 if version == 3 else 72000) * bitrates[bitrate_index] // rate
        size += (header >> 9) & 1
        side_size = (17 if channels == 1 else 32) if version == 3 else (9 if channels == 1 else 17)
        frame_end = offset + size
        if size <= 4 + side_size or frame_end > end:
            raise Mp3Error("invalid or truncated MPEG frame")
        marker = offset + 4 + side_size
        is_metadata = audio[marker:marker + 4] in (b"Xing", b"Info")
        if is_metadata:
            if offset != start or marker + 8 > frame_end:
                raise Mp3Error("invalid Xing/Info frame")
            flags = int.from_bytes(audio[marker + 4:marker + 8], "big")
            if flags & ~15:
                raise Mp3Error("unsupported Xing/Info flags")
            cursor = marker + 8
            for bit, length in ((1, 4), (2, 4), (4, 100), (8, 4)):
                if flags & bit:
                    if cursor + length > frame_end:
                        raise Mp3Error("truncated Xing/Info fields")
                    value = int.from_bytes(audio[cursor:cursor + length], "big")
                    if bit == 1:
                        declared_frames = value
                    elif bit == 2:
                        declared_bytes = value
                    cursor += length
        else:
            if audio[offset + 36:offset + 40] == b"VBRI":
                raise Mp3Error("VBRI metadata is unsupported")
            frames += 1
            samples += 1152 if version == 3 else 576
        offset = frame_end
    if frames < 2 or stream is None:
        raise Mp3Error("MP3 must contain at least two complete audio frames")
    if declared_frames is not None and declared_frames != frames:
        raise Mp3Error("Xing/Info frame count does not match the complete stream")
    if declared_bytes is not None and declared_bytes != end - start:
        raise Mp3Error("Xing/Info byte count does not match the complete stream")
    return samples / stream[1]
