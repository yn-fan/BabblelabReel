"""Offline Commons contract tests; only isolated cache fixtures are written."""

import copy
from email.message import Message
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("reel_library_bgm", ROOT / "skills/reel/scripts/library_bgm.py")
library = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(library)
CATALOG = json.loads((ROOT / "skills/reel/assets/music-library.json").read_text())
BRIEF = {"libraryTags": ["lofi", "warm"], "story": "PRIVATE STORY", "prompt": "PRIVATE PROMPT"}

# Actual current Commons formatversion=1 response shape and page wikitext,
# File:Lofi_music_001.wav revision 1026770115. Only audio bytes/size/SHA-1
# are replaced by a small generated PCM fixture below, never a remote fixture.
WIKITEXT = """=={{int:filedesc}}==
{{Information
|description={{en|1=LoFi Music}}
|date=2024-03-08
|source={{own}}
|author=[[User:Luisalvaz|Luisalvaz]]
|permission=
|other versions=
}}

=={{int:license-header}}==
{{self|cc-zero}}

[[Category:Lofi hip hop]]"""
FILE_URL = "https://upload.wikimedia.org/wikipedia/commons/f/f5/Lofi_music_001.wav"
PAGE_URL = "https://commons.wikimedia.org/wiki/File:Lofi_music_001.wav"


def wav():
    samples = b"\x10\x00\x20\x00" * 100
    return (
        b"RIFF" + struct.pack("<I", 36 + len(samples)) + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 2, 44100, 176400, 4, 16)
        + b"data" + struct.pack("<I", len(samples)) + samples
    )


def fixture():
    audio = wav()
    track = copy.deepcopy(CATALOG["tracks"][1])
    track["sizeBytes"] = len(audio)
    track["sourceFileSha1"] = hashlib.sha1(audio).hexdigest()
    metadata = {
        "License": {"value": "cc0", "source": "commons-templates", "hidden": ""},
        "LicenseShortName": {"value": "CC0", "source": "commons-desc-page", "hidden": ""},
        "LicenseUrl": {"value": "http://creativecommons.org/publicdomain/zero/1.0/deed.en",
                       "source": "commons-desc-page", "hidden": ""},
        "UsageTerms": {"value": "Creative Commons Zero, Public Domain Dedication",
                       "source": "commons-desc-page"},
        "AttributionRequired": {"value": "false", "source": "commons-desc-page", "hidden": ""},
        "Restrictions": {"value": "", "source": "commons-desc-page", "hidden": ""},
        "Credit": {"value": '<span class="int-own-work" lang="en">Own work</span>',
                   "source": "commons-desc-page"},
        "Artist": {"value": '<a href="//commons.wikimedia.org/wiki/User:Luisalvaz" title="User:Luisalvaz">Luisalvaz</a>',
                   "source": "commons-desc-page"},
        "Categories": {"value": "CC-Zero|Self-published work|Lofi hip hop", "source": "commons-categories"},
        "ImageDescription": {"value": "LoFi Music", "source": "commons-desc-page"},
    }
    data = {"batchcomplete": "", "query": {"pages": {"146213401": {
        "pageid": 146213401, "ns": 6, "title": "File:Lofi music 001.wav",
        "imagerepository": "local",
        "imageinfo": [{
            "size": len(audio), "width": 0, "height": 0,
            "duration": 166.1539455782313, "sha1": hashlib.sha1(audio).hexdigest(),
            "mime": "audio/wav", "descriptionurl": PAGE_URL,
            "url": FILE_URL + "?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original",
            "extmetadata": metadata,
        }],
        "revisions": [{
            "revid": 1026770115, "parentid": 937701129, "timestamp": "2025-05-01T23:25:35Z",
            "slots": {"main": {"contentmodel": "wikitext", "contentformat": "text/x-wiki", "*": WIKITEXT}},
        }],
    }}}}
    return track, data, audio


def page(data):
    return data["query"]["pages"]["146213401"]


class Response(io.BytesIO):
    def __init__(self, data, mime="application/json", status=200, length=True, fragment=4096):
        super().__init__(json.dumps(data).encode() if isinstance(data, dict) else data)
        self.headers = Message()
        self.headers["Content-Type"] = mime
        if length:
            self.headers["Content-Length"] = str(len(self.getvalue()))
        self.status, self.url, self.fragment = status, None, fragment
        self.on_read = None

    def geturl(self):
        return self.url

    def read1(self, size):
        if self.on_read:
            self.on_read()
        return self.read(min(size, self.fragment))


class Opener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if response.url is None:
            response.url = request.full_url
        return response


class SelectionTests(unittest.TestCase):
    def test_no_credit_brief_excludes_attribution_tracks(self):
        track = copy.deepcopy(CATALOG["tracks"][0])
        track["attributionRequired"] = True
        with patch.object(library, "_catalog", return_value=[track]):
            self.assertEqual(library.LibraryMusic.select({"libraryTags": ["ambient"]}, 10)["id"], track["id"])
            with self.assertRaisesRegex(library.LibraryBgmError, "no curated track"):
                library.LibraryMusic.select({"libraryTags": ["ambient"], "allowAttribution": False}, 10)
            with self.assertRaisesRegex(library.LibraryBgmError, "boolean"):
                library.LibraryMusic.select({"libraryTags": ["ambient"], "allowAttribution": "no"}, 10)

    def test_catalog_actual_pins_and_independent_license_shape(self):
        tracks = library._catalog()
        self.assertGreaterEqual(len(tracks), 14)
        self.assertGreaterEqual(sum(t["attributionRequired"] for t in tracks), 4)
        self.assertEqual([t["id"] for t in tracks[:3]], [
            "wilfredor-ambient-ck61", "luisalvaz-lofi-001", "luisalvaz-techno-001",
        ])
        self.assertEqual(hashlib.sha256(WIKITEXT.encode()).hexdigest(),
                         tracks[1]["sourceWikitextSha256"])
        self.assertEqual(tracks[0]["sourceFileSha1"], "fbe9e5fbe4b727fac1608dec68c94a956d9cbd65")
        self.assertTrue(all(t["license"] in library.LICENSES for t in tracks))

    def test_rank_mood_genre_and_instrument_without_network(self):
        cases = [
            (["ambient", "keyboard"], "wilfredor-ambient-ck61"),
            (["warm", "lofi"], "luisalvaz-lofi-001"),
            (["energetic", "techno", "electronic"], "luisalvaz-techno-001"),
            (["piano"], "wilfredor-ambient-ck61"),
        ]
        with patch.object(library, "build_opener", side_effect=AssertionError("network")), patch.object(
            library, "_catalog", return_value=CATALOG["tracks"][:3]
        ):
            for tags, expected in cases:
                with self.subTest(tags=tags):
                    result = library.LibraryMusic.select({"libraryTags": tags}, 60)
                    self.assertEqual(result["id"], expected)
                    self.assertIn("not a listening assessment", result["selectionRationale"])

    def test_absent_malformed_unknown_and_unmatched_direction(self):
        for tags in (None, [], "ambient", ["AMBIENT"], ["private mood"], ["calm"] * 9,
                     ["calm", "calm"], [True], [{}], ["dark", "piano"], ["jazz", "electronic"],
                     ["warm", "piano"], ["dark", "calm", "piano"], ["calm", "energetic"]):
            with self.subTest(tags=tags), patch.object(
                library, "_catalog", return_value=CATALOG["tracks"][:3]
            ), self.assertRaises(library.LibraryBgmError):
                library.LibraryMusic.select({"libraryTags": tags}, 60)
        for brief in (None, {}, [], "story"):
            with self.assertRaises(library.LibraryBgmError):
                library.LibraryMusic.select(brief, 60)

    def test_too_short_and_invalid_durations(self):
        for duration in (0, -1, True, "60", float("inf"), float("nan"), 200):
            with self.subTest(duration=duration), patch.object(
                library, "_catalog", return_value=CATALOG["tracks"][:3]
            ), self.assertRaises(library.LibraryBgmError):
                library.LibraryMusic.select({"libraryTags": ["ambient"]}, duration)

    def test_catalog_supports_more_than_eight_distinct_recordings(self):
        data = copy.deepcopy(CATALOG)
        data["tracks"] = []
        for index in range(12):
            track = copy.deepcopy(CATALOG["tracks"][0])
            filename = f"Fixture_{index}.flac"
            track.update(
                id=f"fixture-{index}",
                fileTitle=f"File:Fixture {index}.flac",
                sourceUrl=f"https://commons.wikimedia.org/wiki/File:{filename}",
                sourceDownloadUrl=f"https://upload.wikimedia.org/wikipedia/commons/a/ab/{filename}",
            )
            data["tracks"].append(track)
        with patch.object(Path, "read_text", return_value=json.dumps(data)):
            self.assertEqual(len(library._catalog()), 12)

    def test_duplicate_recording_cannot_inflate_catalog(self):
        data = copy.deepcopy(CATALOG)
        duplicate = copy.deepcopy(data["tracks"][0])
        duplicate["id"] = "different-id-same-recording"
        data["tracks"].append(duplicate)
        with patch.object(Path, "read_text", return_value=json.dumps(data)):
            with self.assertRaisesRegex(library.LibraryBgmError, "catalog:"):
                library._catalog()

    def test_unsafe_or_unknown_catalog_entries_fail_before_network(self):
        for key, value in [
            ("license", "CC-BY-4.0"), ("attributionRequired", True),
            ("allowsProjectRedistribution", False), ("sourceDownloadUrl", "http://127.0.0.1/file.wav"),
            ("sourceUrl", "https://example.com/wiki/File:Lofi_music_001.wav"),
            ("sourceFileSha1", "unknown"), ("durationSeconds", 0), ("tags", ["made-up"]),
            ("sourceRevisionId", True), ("audioFormat", "mp3"), ("sizeBytes", 500000000),
        ]:
            data = copy.deepcopy(CATALOG)
            data["tracks"][1][key] = value
            with self.subTest(key=key), patch.object(Path, "read_text", return_value=json.dumps(data)):
                with self.assertRaises(library.LibraryBgmError):
                    library.LibraryMusic.select(BRIEF, 60)


class AcquisitionTests(unittest.TestCase):
    def test_cc_by_requires_exact_original_license_and_attribution(self):
        for version in ("3.0", "4.0"):
            track, data, audio = fixture()
            license_id = f"CC-BY-{version}"
            policy = library.LICENSES[license_id]
            text = WIKITEXT.replace("cc-zero", f"cc-by-{version}")
            track.update(
                license=license_id, licenseUrl=policy[0], attributionRequired=True,
                sourceWikitextSha256=hashlib.sha256(text.encode()).hexdigest(),
            )
            page(data)["revisions"][0]["slots"]["main"]["*"] = text
            ext = page(data)["imageinfo"][0]["extmetadata"]
            for key, value in {
                "License": policy[2], "LicenseShortName": policy[3],
                "UsageTerms": policy[4], "LicenseUrl": policy[0].rstrip("/"),
                "AttributionRequired": "true",
            }.items():
                ext[key]["value"] = value
            with self.subTest(version=version):
                result, _ = self.run_fixture(data=data, audio=audio, track=track)
                self.assertEqual(result["provenance"]["license"], license_id)
                self.assertTrue(result["provenance"]["attributionRequired"])
                ext["License"]["value"] = f"cc-by-nc-{version}"
                with self.assertRaisesRegex(library.LibraryBgmError, "license:"):
                    self.run_fixture(data=data, audio=audio, track=track)

    def test_cached_original_still_checks_current_license_and_hash(self):
        track, data, audio = fixture()
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            path = cache / f"{track['id']}.wav"
            path.write_bytes(audio)
            for mutation in ("valid", "corrupt", "changed-license"):
                with self.subTest(mutation=mutation):
                    response = copy.deepcopy(data)
                    path.write_bytes(audio if mutation != "corrupt" else b"x" * len(audio))
                    if mutation == "changed-license":
                        page(response)["imageinfo"][0]["extmetadata"]["License"]["value"] = "cc-by"
                    client = library.LibraryMusic(cache_dir=cache)
                    client._opener = Opener(Response(response))
                    with patch.object(library, "_catalog", return_value=[track]):
                        if mutation == "valid":
                            self.assertEqual(client.acquire(BRIEF, 60)["audio"], audio)
                        else:
                            with self.assertRaisesRegex(library.LibraryBgmError, "hash|license"):
                                client.acquire(BRIEF, 60)
                    self.assertEqual(len(client._opener.requests), 1)

    def run_fixture(self, data=None, audio=None, track=None, audio_response=None):
        original_track, original_data, original_audio = fixture()
        track = track or original_track
        data = original_data if data is None else data
        audio = original_audio if audio is None else audio
        client = library.LibraryMusic()
        client._opener = Opener(Response(data), audio_response or Response(audio, "audio/wav"))
        with patch.object(library, "_catalog", return_value=[track]):
            result = client.acquire(BRIEF, 60)
        return result, client

    def test_success_schema_privacy_and_current_evidence(self):
        result, client = self.run_fixture()
        self.assertEqual(set(result), {"audio", "audioFormat", "provenance"})
        self.assertEqual(result["audio"], wav())
        self.assertEqual(result["audioFormat"], "wav")
        p = result["provenance"]
        expected = {
            "kind": "licensed-library-music", "provider": "wikimedia-commons",
            "license": "CC0-1.0", "licenseUrl": "https://creativecommons.org/publicdomain/zero/1.0/",
            "sourceUrl": PAGE_URL, "sourceDownloadUrl": FILE_URL, "creator": "Luisalvaz",
            "title": "Lofi music 001", "sourceRevisionId": 1026770115,
            "attributionRequired": False, "allowsProjectRedistribution": True,
        }
        self.assertEqual({k: p[k] for k in expected}, expected)
        self.assertFalse({"model", "seed", "promptSha256", "schemaVersion", "success"} & p.keys())
        self.assertEqual(p["sourceFileSha1"], hashlib.sha1(wav()).hexdigest())
        self.assertEqual(p["sourceSha256"], hashlib.sha256(wav()).hexdigest())
        self.assertTrue(p["verifiedAt"].endswith("Z"))
        self.assertEqual(len(client._opener.requests), 2)
        for request, timeout in client._opener.requests:
            self.assertNotIn("PRIVATE", request.full_url)
            self.assertIsNone(request.data)
            self.assertIsNone(request.get_header("Authorization"))
            self.assertIsNotNone(request.get_header("User-agent"))
            self.assertLessEqual(timeout, 120)
        query = parse_qs(urlsplit(client._opener.requests[0][0].full_url).query)
        self.assertEqual(query["titles"], ["File:Lofi music 001.wav"])
        self.assertNotIn("libraryTags", query)
        self.assertEqual(client.last_evidence["response"]["query"]["pages"]["146213401"]["revisions"][0]["revid"],
                         1026770115)

    def test_current_license_or_creator_failure(self):
        for key, value in [
            ("License", "cc-by-4.0"), ("LicenseShortName", "CC BY"),
            ("LicenseUrl", "https://example.com/CC0"), ("AttributionRequired", "true"),
            ("Restrictions", "No commercial use"), ("Credit", "Internet"),
            ("Artist", "Somebody else"), ("Categories", "Items with disputed copyright"),
            ("ImageDescription", "License review needed"),
        ]:
            track, data, _ = fixture()
            page(data)["imageinfo"][0]["extmetadata"][key]["value"] = value
            with self.subTest(key=key), self.assertRaisesRegex(library.LibraryBgmError, "license"):
                self.run_fixture(data=data, track=track)

    def test_changed_page_hash_size_duration_and_urls(self):
        for key, value in [
            ("sha1", "a" * 40), ("size", 100), ("duration", 1), ("mime", "audio/mpeg"),
            ("url", "https://127.0.0.1/file.wav"),
            ("url", FILE_URL + "?redirect=elsewhere"),
            ("descriptionurl", "https://example.com/license"),
        ]:
            _, data, _ = fixture()
            page(data)["imageinfo"][0][key] = value
            with self.subTest(key=key), self.assertRaises(library.LibraryBgmError):
                self.run_fixture(data=data)
        for mutate in (
            lambda p: p["revisions"][0].update(revid=999),
            lambda p: p["revisions"][0]["slots"]["main"].update({"*": WIKITEXT + "{{delete}}"}),
        ):
            _, data, _ = fixture()
            mutate(page(data))
            with self.assertRaisesRegex(library.LibraryBgmError, "changed"):
                self.run_fixture(data=data)

    def test_malformed_api_never_downloads(self):
        for data in (b"<html>bad</html>", {}, {"error": {"code": "maxlag"}}, {"query": {"pages": []}}):
            client = library.LibraryMusic()
            client._opener = Opener(Response(data))
            with self.assertRaises(library.LibraryBgmError):
                client.acquire(BRIEF, 60)
            self.assertEqual(len(client._opener.requests), 1)

    def test_input_failure_and_changed_hash_do_not_download(self):
        client = library.LibraryMusic()
        client._opener = Opener()
        client.last_evidence = {"old": "evidence"}
        with self.assertRaises(library.LibraryBgmError):
            client.acquire({"libraryTags": ["made-up"]}, 60)
        self.assertEqual(client._opener.requests, [])
        self.assertIsNone(client.last_evidence)
        _, data, _ = fixture()
        page(data)["imageinfo"][0]["sha1"] = "1" * 40
        client._opener = Opener(Response(data))
        with self.assertRaisesRegex(library.LibraryBgmError, "changed"):
            client.acquire(BRIEF, 60)
        self.assertEqual(len(client._opener.requests), 1)

    def test_corruption_truncation_oversize_and_html(self):
        for audio in (wav()[:-4], wav() + b"extra", wav()[:-1] + b"!"):
            with self.subTest(size=len(audio)), self.assertRaises(library.LibraryBgmError):
                self.run_fixture(audio=audio)
        response = Response(wav()[:-4], "audio/wav")
        response.headers.replace_header("Content-Length", str(len(wav())))
        with self.assertRaisesRegex(library.LibraryBgmError, "truncated"):
            self.run_fixture(audio_response=response)
        with self.assertRaisesRegex(library.LibraryBgmError, "content type"):
            self.run_fixture(audio_response=Response(b"<html>not audio</html>", "text/html"))
        track, data, _ = fixture()
        html = b"<html>" + b"x" * 100
        track.update(sizeBytes=len(html), sourceFileSha1=hashlib.sha1(html).hexdigest())
        page(data)["imageinfo"][0].update(size=len(html), sha1=track["sourceFileSha1"])
        with self.assertRaisesRegex(library.LibraryBgmError, "container"):
            self.run_fixture(track=track, data=data, audio=html)

    def test_transport_limits_missing_length_encoding_and_incomplete_read(self):
        for length in ("-1", "0", "NaN", "500000000", "1.5"):
            response = Response(wav(), "audio/wav")
            response.headers.replace_header("Content-Length", length)
            with self.subTest(length=length), self.assertRaisesRegex(library.LibraryBgmError, "size"):
                self.run_fixture(audio_response=response)
        response = Response(wav() + b"oversize", "audio/wav", length=False)
        with self.assertRaisesRegex(library.LibraryBgmError, "byte limit"):
            self.run_fixture(audio_response=response)
        result, _ = self.run_fixture(audio_response=Response(wav(), "audio/wav", length=False))
        self.assertEqual(result["audio"], wav())
        response = Response(wav(), "audio/wav")
        response.headers["Content-Encoding"] = "gzip"
        with self.assertRaisesRegex(library.LibraryBgmError, "encoding"):
            self.run_fixture(audio_response=response)

    def test_full_original_range_is_single_bounded_request(self):
        response = Response(wav(), "audio/wav", status=206)
        response.headers["Content-Range"] = f"bytes 0-{len(wav()) - 1}/{len(wav())}"
        result, client = self.run_fixture(audio_response=response)
        self.assertEqual(result["audio"], wav())
        self.assertEqual(client._opener.requests[1][0].get_header("Range"), f"bytes=0-{len(wav()) - 1}")
        self.assertEqual(len(client._opener.requests), 2)
        for content_range in ("bytes 0-127/444", "bytes 1-444/445", "bytes 0-443/*", None):
            response = Response(wav(), "audio/wav", status=206)
            if content_range:
                response.headers["Content-Range"] = content_range
            with self.subTest(content_range=content_range), self.assertRaisesRegex(library.LibraryBgmError, "range"):
                self.run_fixture(audio_response=response)

    def test_redirect_and_errors_never_retry(self):
        for error in (
            HTTPError(FILE_URL, 302, "redirect", {}, io.BytesIO()),
            HTTPError(FILE_URL, 429, "limited", {}, io.BytesIO()),
            HTTPError(FILE_URL, 403, "PRIVATE server payload", {}, io.BytesIO()),
            URLError("PRIVATE upstream"), TimeoutError("PRIVATE"),
        ):
            client = library.LibraryMusic()
            client._opener = Opener(error)
            with self.assertRaises(library.LibraryBgmError) as raised:
                client.acquire(BRIEF, 60)
            self.assertNotIn("PRIVATE", str(raised.exception))
            self.assertEqual(len(client._opener.requests), 1)
        response = Response(wav(), "audio/wav")
        response.url = "https://example.com/redirect"
        with self.assertRaisesRegex(library.LibraryBgmError, "redirect"):
            self.run_fixture(audio_response=response)
        with self.assertRaisesRegex(library.LibraryBgmError, "redirect"):
            library._NoRedirect().redirect_request(None, None, 302, "", {}, FILE_URL)

    def test_rate_limit_retry_after_is_reported_without_retry(self):
        client = library.LibraryMusic()
        client._opener = Opener(HTTPError(
            FILE_URL, 429, "limited", {"Retry-After": "600"}, io.BytesIO(),
        ))
        with self.assertRaisesRegex(library.LibraryBgmError, "Retry-After 600s"):
            client.acquire(BRIEF, 60)
        self.assertEqual(len(client._opener.requests), 1)

    def test_timeout_validation(self):
        for value in (0, -1, True, float("inf"), float("nan"), "120"):
            with self.subTest(value=value), self.assertRaises(library.LibraryBgmError):
                library.LibraryMusic(timeout=value)

    def test_total_deadline_applies_to_trickled_reads(self):
        client = library.LibraryMusic(timeout=1)
        clock = [10.0]
        response = Response(b"{}" * 50, fragment=1)
        response.on_read = lambda: clock.__setitem__(0, clock[0] + 0.6)
        client._opener = Opener(response)
        with patch.object(library.time, "monotonic", side_effect=lambda: clock[0]):
            with self.assertRaisesRegex(library.LibraryBgmError, "deadline"):
                client.acquire(BRIEF, 60)
        self.assertEqual(len(client._opener.requests), 1)

    def test_url_allowlist_no_credentials_ports_local_or_encoded_traversal(self):
        for url in (
            "http://upload.wikimedia.org/wikipedia/commons/f/f5/test.wav",
            "https://user:pass@upload.wikimedia.org/wikipedia/commons/f/f5/test.wav",
            "https://upload.wikimedia.org:443/wikipedia/commons/f/f5/test.wav",
            "https://upload.wikimedia.org.evil.test/wikipedia/commons/f/f5/test.wav",
            FILE_URL + "#fragment", FILE_URL + "?token=secret",
            "https://upload.wikimedia.org/wikipedia/commons/f/f5/%2e%2e/test.wav",
            "https://upload.wikimedia.org/wikipedia/commons/f/f5/%0atest.wav",
            "file:///etc/passwd",
        ):
            with self.subTest(url=url), self.assertRaises(library.LibraryBgmError):
                library._safe_url(url, "audio")


if __name__ == "__main__":
    unittest.main()
