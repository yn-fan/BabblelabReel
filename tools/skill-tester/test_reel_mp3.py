"""Python/JavaScript parity tests; header fixtures are NOT playable music."""

import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills/reel/scripts"))
from mp3_audio import Mp3Error, mp3_duration

JS = ROOT / "skills/reel/assets/remotion-starter/scripts/validate-mp3.mjs"
MUSIC_JS = JS.with_name("validate-music.mjs")


def frame(version=3, bitrate=9, rate=0, mono=False, padding=0):
    """Synthetic framing only: zero payload is not decoded audio evidence."""
    header = (0xFFE00000 | version << 19 | 1 << 17 | 1 << 16 |
              bitrate << 12 | rate << 10 | padding << 9 | (3 if mono else 0) << 6)
    rates = (44100, 48000, 32000)
    bitrates = ((0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
                if version == 3 else
                (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160))
    size = ((144000 if version == 3 else 72000) * bitrates[bitrate] //
            (rates[rate] // {3: 1, 2: 2, 0: 4}[version])) + padding
    return header.to_bytes(4, "big") + bytes(size - 4)


def xing(audio, count, marker=b"Xing"):
    tag = bytearray(frame())
    tag[36:52] = marker + struct.pack(">III", 3, count, len(tag) + len(audio))
    return bytes(tag) + audio


class Mp3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = ROOT / (".reel-mp3-tests-" + uuid.uuid4().hex)
        cls.work.mkdir()
        cls.addClassCleanup(shutil.rmtree, cls.work)

    def js_result(self, audio):
        path = self.work / "fixture.mp3"
        path.write_bytes(audio)
        result = subprocess.run(
            ["node", "--input-type=module", "-e",
             "import {measureMp3Duration} from " + json.dumps(JS.as_uri()) + ";"
             "try {console.log(JSON.stringify({duration:measureMp3Duration(process.argv[1])}));}"
             "catch(e) {console.log(JSON.stringify({error:e.message}));}", str(path)],
            capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout)

    def assert_duration(self, audio, expected):
        self.assertAlmostEqual(mp3_duration(audio), expected, places=12)
        result = self.js_result(audio)
        self.assertEqual(result, {"duration": mp3_duration(audio)})

    def assert_rejected(self, audio):
        with self.assertRaises(Mp3Error):
            mp3_duration(audio)
        self.assertIn("error", self.js_result(audio))

    def test_cbr_vbr_versions_sample_rates_channels_padding(self):
        for version in (3, 2, 0):
            for rate_index, base_rate in enumerate((44100, 48000, 32000)):
                for mono in (False, True):
                    with self.subTest(version=version, rate=base_rate, mono=mono):
                        rate = base_rate // {3: 1, 2: 2, 0: 4}[version]
                        audio = b"".join(frame(version, b, rate_index, mono, b % 2)
                                         for b in (9, 9, 10, 7))
                        self.assert_duration(audio, 4 * (1152 if version == 3 else 576) / rate)

    def test_id3_headers_footer_and_trailing_id3v1(self):
        audio = frame() * 3
        for version in (2, 3, 4):
            tag = b"ID3" + bytes((version, 0, 0, 0, 0, 0, 5)) + b"hello"
            self.assert_duration(tag + audio + b"TAG" + bytes(125), 3456 / 44100)
        header = b"ID3\x04\x00\x10\x00\x00\x00\x05"
        self.assert_duration(header + b"hello" + b"3DI" + header[3:] + audio, 3456 / 44100)

    def test_xing_info_counts_exclude_metadata_frame(self):
        audio = frame() + frame(bitrate=10) + frame()
        for marker in (b"Xing", b"Info"):
            self.assert_duration(xing(audio, 3, marker), 3456 / 44100)
        tag = bytearray(frame())
        tag[36:44] = b"Xing" + bytes(4)
        self.assert_duration(bytes(tag) + audio, 3456 / 44100)

    def test_reject_malformed_truncated_or_unknown_streams(self):
        audio = frame() * 3
        invalid = [
            b"", frame(), b"junk" + audio, audio + b"junk", audio[:-1],
            audio + b"\xff", b"ID3", b"ID3\x04\x00\x00\x80\x00\x00\x00" + audio,
            b"ID3\x05\x00\x00\x00\x00\x00\x00" + audio,
            b"ID3\x03\x00\x01\x00\x00\x00\x00" + audio,
            b"ID3\x03\x00\x00\x00\x00\x7f\x7f" + audio,
            b"ID3\x04\x00\x10\x00\x00\x00\x00" + audio,
            frame() + frame(rate=1), frame() + frame(mono=True),
            xing(audio, 0), xing(audio, 4), xing(audio, 3)[:-len(frame())],
            frame() + xing(audio, 3),
        ]
        for bit in (1 << 16, 1 << 17):
            invalid.append((int.from_bytes(audio[:4], "big") ^ bit).to_bytes(4, "big") + audio[4:])
        for mask, value in ((15 << 12, 0), (15 << 12, 15 << 12),
                            (3 << 10, 3 << 10), (3 << 19, 1 << 19),
                            (3, 2), (0xFFE00000, 0)):
            header = int.from_bytes(audio[:4], "big") & ~mask | value
            invalid.append(header.to_bytes(4, "big") + audio[4:])
        bad_bytes = bytearray(xing(audio, 3))
        bad_bytes[48:52] = struct.pack(">I", 1)
        invalid.append(bytes(bad_bytes))
        bad_flags = bytearray(xing(audio, 3))
        bad_flags[40:44] = struct.pack(">I", 16)
        invalid.append(bytes(bad_flags))
        short_xing = bytearray(frame(bitrate=1))
        short_xing[36:44] = b"Xing" + struct.pack(">I", 15)
        invalid.append(bytes(short_xing) + audio)
        vbri = bytearray(audio)
        vbri[36:40] = b"VBRI"
        invalid.append(bytes(vbri))
        for index, item in enumerate(invalid):
            with self.subTest(index=index):
                self.assert_rejected(item)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "optional real encoder/decoder tools not installed")
    def test_real_encoded_audio_against_ffprobe_and_decoded_duration(self):
        # Locally generated test tones only, never music acquisition or AI evidence.
        for rate, quality, mono in ((44100, ["-b:a", "128k"], False),
                                    (44100, ["-b:a", "128k", "-write_xing", "0"], False),
                                    (48000, ["-q:a", "4"], False),
                                    (22050, ["-q:a", "5"], True)):
            path = self.work / "encoded.mp3"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                            f"sine=frequency=440:duration=1.2:sample_rate={rate}",
                            "-ac", "1" if mono else "2", "-c:a", "libmp3lame", *quality,
                            str(path)], capture_output=True, check=True)
            audio = path.read_bytes()
            measured = mp3_duration(audio)
            self.assert_duration(audio, measured)
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                    "format=duration", "-of", "json", str(path)],
                                   capture_output=True, text=True, check=True)
            # ffprobe versions differ in whether the LAME gapless trim is applied.
            self.assertLess(abs(measured - float(json.loads(probe.stdout)["format"]["duration"])),
                            2304 / rate)
            decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path),
                                      "-f", "s16le", "-ac", "1", "-ar", str(rate), "pipe:1"],
                                     capture_output=True, check=True).stdout
            self.assertLess(abs(measured - len(decoded) / (2 * rate)), 2304 / rate)

    def test_incompetech_provenance_and_attribution_fail_closed(self):
        project = self.work / "project"
        audio_dir = project / "public/audio"
        audio_dir.mkdir(parents=True)
        source_dir = project / "src/reel"
        source_dir.mkdir(parents=True)
        (source_dir / "MusicCredits.tsx").write_text("export const MUSIC_CREDITS_RENDERER_VERSION = 1;")
        (source_dir / "Reel.tsx").write_text(
            "import {MusicCredits} from './MusicCredits';\n"
            "<MusicCredits durationInFrames={DURATION_IN_FRAMES} />")
        audio = frame() * 90
        (audio_dir / "fixture.mp3").write_bytes(audio)
        duration = mp3_duration(audio)
        provenance = {
            "schemaVersion": 1, "success": True, "instrumental": True,
            "kind": "licensed-library-music", "provider": "incompetech",
            "audioFormat": "mp3", "durationSeconds": duration,
            "creator": "Kevin MacLeod", "creditCreators": "Kevin MacLeod (incompetech.com)",
            "title": "Nonplayable parser fixture", "trackId": "USUAN1100001",
            "license": "CC-BY-4.0", "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
            "attributionRequired": True, "allowsProjectRedistribution": True,
            "sourceUrl": "https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100001",
            "sourceDownloadUrl": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Test%20Fixture.mp3",
            "sourceCatalogSha256": "a" * 64, "sourceLicenseSha256": "b" * 64,
            "sourceFileSha1": hashlib.sha1(audio).hexdigest(),
            "sourceSha256": hashlib.sha256(audio).hexdigest(),
            "outputSha256": hashlib.sha256(audio).hexdigest(),
            "verifiedAt": "2026-09-11T12:00:00Z", "selectionRationale": "Test only",
        }
        credit = (f"{provenance['title']} - {provenance['creditCreators']}\n"
                  f"{provenance['license']}; {provenance['licenseUrl']}\n"
                  f"{provenance['sourceUrl']}\n"
                  "Edited for this video: excerpt, fades, and volume mix.")
        provenance["attributionText"] = credit
        license_text = (credit + "\n\nOriginal recording licensed by its creator under the linked license.\n"
                        f"Source catalog SHA-256: {provenance['sourceCatalogSha256']}\n"
                        f"Source verified: {provenance['verifiedAt']}\n")
        (audio_dir / "fixture.mp3.license.txt").write_text(license_text)
        story = {"format": {"fps": 30}, "audio": {"music": {
            "src": "audio/fixture.mp3", "provenanceRef": "audio/provenance.json",
            "durationSeconds": duration, "startSeconds": 0, "endSeconds": 1,
            "sourceStartSeconds": 0, "volume": 0.2, "duckVolume": 0.1,
            "fadeInSeconds": 0, "fadeOutSeconds": 0,
            "duckAttackSeconds": 0.1, "duckReleaseSeconds": 0.1, "attribution": credit,
        }}}

        def validate(value=provenance):
            (audio_dir / "provenance.json").write_text(json.dumps(value))
            result = subprocess.run(
                ["node", "--input-type=module", "-e",
                 "import {validateMusic} from " + json.dumps(MUSIC_JS.as_uri()) + ";"
                 "console.log(JSON.stringify(validateMusic(" + json.dumps(story) +
                 ",2,()=>{throw new Error('unexpected WAV reader')})));"],
                cwd=project, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)

        self.assertEqual(validate(), [])
        without_site_credit = {key: value for key, value in provenance.items() if key != "creditCreators"}
        self.assertTrue(any("Incompetech requires Kevin MacLeod attribution" in error
                            for error in validate(without_site_credit)))
        changes = [
            {"provider": "arbitrary"}, {"license": "CC0-1.0"}, {"creator": "Other"},
            {"sourceRevisionId": 123}, {"trackId": "no-isrc"}, {"trackId": "GBABC1100001"},
            {"sourceSha256": "c" * 64},
            {"sourceCatalogSha256": "invalid"}, {"sourceLicenseSha256": "invalid"},
            {"sourceFileSha1": "c" * 40}, {"audioFormat": "wav"},
            {"sourceUrl": provenance["sourceUrl"] + "&extra=1"},
            {"sourceUrl": provenance["sourceUrl"].replace("?isrc=", "?other=")},
            {"sourceDownloadUrl": provenance["sourceDownloadUrl"] + "?download=1"},
            {"sourceDownloadUrl": provenance["sourceDownloadUrl"].replace("Test%20Fixture", "%2Fbad")},
            {"sourceDownloadUrl": provenance["sourceDownloadUrl"].replace("incompetech.com", "evil.example")},
            {"sourceDownloadUrl": provenance["sourceDownloadUrl"].replace("Test%20Fixture", "../bad")},
            {"verifiedAt": "not-a-date"}, {"attributionText": "missing credit"},
            {"kind": "ai-generated-music", "provider": "ace-step"},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.assertTrue(validate({**provenance, **change}))
        story["audio"]["music"]["attribution"] = "missing visible credit"
        self.assertTrue(validate())
        story["audio"]["music"]["attribution"] = credit
        (audio_dir / "fixture.mp3.license.txt").write_text("wrong license")
        self.assertTrue(validate())
        (audio_dir / "fixture.mp3.license.txt").write_text(license_text)
        (source_dir / "Reel.tsx").write_text("missing renderer")
        self.assertTrue(validate())


if __name__ == "__main__":
    unittest.main()
