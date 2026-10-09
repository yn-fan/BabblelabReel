"""Offline bounded Incompetech adapter contracts; no downloads or disk fixtures."""

from email.message import Message
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills/reel/scripts"))
import incompetech_bgm as music


BRIEF = {"libraryTags": ["uplifting", "piano"], "story": "PRIVATE STORY",
         "prompt": "PRIVATE PROMPT"}
TRACK = {
    "uuid": "12345", "title": "Fixture", "filename": "Fixture Music.mp3",
    "length": "00:01:00", "instruments": "Piano, Drums", "genre": "4",
    "bpm": "100", "description": "A bright instrumental.",
    "feel": "Bright, Uplifting", "uploaded": "2026-01-01", "isrc": "USUAN2600001",
    "collection": "999", "wav": None,
}
LICENSE = (
    "<html>Title Kevin MacLeod (incompetech.com)<br>"
    "Licensed under Creative Commons: By Attribution 4.0<br>"
    "https://creativecommons.org/licenses/by/4.0/</html>"
).encode()
AUDIO = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" * 100


class Response(io.BytesIO):
    def __init__(self, body, url=None, status=200):
        super().__init__(body)
        self.url, self.status = url, status
        self.headers = Message()
        self.headers["Content-Length"] = str(len(body))

    def geturl(self):
        return self.url

    def read1(self, size):
        return self.read(min(size, 30))


class Opener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        result.url = result.url or request.full_url
        return result


def provider(license_bytes=LICENSE, records=None, audio=AUDIO):
    p = music.IncompetechMusic()
    p._opener = Opener(Response(license_bytes),
                       Response(json.dumps(records or [TRACK]).encode()), Response(audio))
    return p


class SelectionTests(unittest.TestCase):
    def test_all_confirmed_tags_required_and_no_invented_instruments(self):
        for tags in (["calm"], ["guitar"], ["techno"], ["ambient"], ["lofi"],
                     ["warm"], ["uplifting", "strings"], ["soft"]):
            with self.subTest(tags=tags):
                self.assertEqual(music.rank_catalog([TRACK], {"libraryTags": tags}, 20), [])
        result = music.rank_catalog([TRACK], BRIEF, 60)
        self.assertEqual(result[0]["trackId"], TRACK["isrc"])
        self.assertEqual(music.rank_catalog([TRACK], BRIEF, 61), [])

    def test_conflicting_moods_not_silently_selected(self):
        record = dict(TRACK, feel="Bright, Dark, Uplifting")
        self.assertEqual(music.rank_catalog([record], BRIEF, 10), [])
        record = dict(TRACK, feel="Calming, Driving")
        self.assertEqual(music.rank_catalog([record], {"libraryTags": ["calm"]}, 10), [])

    def test_novel_tags_and_invalid_records_do_not_poison_pool(self):
        novel = dict(TRACK, feel="Ren Faire, Medieval", genre="999")
        malformed = [None, {}, dict(TRACK, length="99:99:99"), dict(TRACK, filename="../a.mp3"),
                     dict(TRACK, isrc="GBABC2600001"), dict(TRACK, isrc="USUAN٢٦٠٠٠٠١")]
        result = music.rank_catalog(malformed + [novel, TRACK], BRIEF, 10)
        self.assertEqual(len(result), 1)

    def test_vocals_and_local_negation(self):
        for field in ("description", "instruments"):
            for value in ("Vocals", "Choir", "with lyrics", "Choral strings", "Singing"):
                self.assertEqual(music.rank_catalog([dict(TRACK, **{field: value})], BRIEF, 10), [])
        for text in ("No vocals.", "Without lyrics.", "Vocal-free instrumental.",
                     "No vocals. But includes choir."):
            result = music.rank_catalog([dict(TRACK, description=text)], BRIEF, 10)
            self.assertEqual(bool(result), "choir" not in text)

    def test_deterministic_shortest_candidate_and_tie_break(self):
        tracks = [dict(TRACK, isrc="USUAN2600003", length="00:02:00"),
                  dict(TRACK, isrc="USUAN2600002"), TRACK]
        self.assertEqual([t["trackId"] for t in music.rank_catalog(tracks, BRIEF, 10)],
                         ["USUAN2600001", "USUAN2600002", "USUAN2600003"])

    def test_reject_invalid_inputs(self):
        for duration in (0, -1, True, float("inf"), float("nan"), "10"):
            with self.assertRaisesRegex(music.LibraryBgmError, "input:"):
                music.rank_catalog([TRACK], BRIEF, duration)
        for brief in ({}, {"libraryTags": ["invented"]},
                      {"libraryTags": ["piano"], "allowAttribution": "yes"}):
            with self.assertRaisesRegex(music.LibraryBgmError, "input:"):
                music.rank_catalog([TRACK], brief, 10)


class NetworkTests(unittest.TestCase):
    def test_acquire_bytes_private_brief_never_transmitted_truthful_hashes(self):
        p = provider()
        result = p.acquire(BRIEF, 10)
        self.assertEqual(result["audio"], AUDIO)
        self.assertEqual(result["audioFormat"], "mp3")
        evidence = result["provenance"]
        self.assertEqual(evidence["sourceFileSha1"], hashlib.sha1(AUDIO).hexdigest())
        self.assertEqual(evidence["sourceSha256"], hashlib.sha256(AUDIO).hexdigest())
        self.assertEqual(evidence["sourceCatalogSha256"],
                         hashlib.sha256(json.dumps([TRACK]).encode()).hexdigest())
        self.assertEqual(evidence["sourceLicenseSha256"], hashlib.sha256(LICENSE).hexdigest())
        self.assertEqual(evidence["provider"], "incompetech")
        self.assertEqual(evidence["licenseUrl"], music.LICENSE_URL)
        self.assertEqual(evidence["creditCreators"], "Kevin MacLeod (incompetech.com)")
        self.assertTrue(evidence["allowsProjectRedistribution"])
        self.assertTrue(evidence["attributionRequired"])
        self.assertNotIn("sourceRevisionId", evidence)
        self.assertTrue(evidence["verifiedAt"].endswith("Z"))
        self.assertEqual(p.last_evidence["eligibleTracks"], 1)
        self.assertEqual(len(p._opener.requests), 3)
        for req, timeout in p._opener.requests:
            self.assertIsNone(req.data)
            self.assertNotIn("PRIVATE", str(req.__dict__))
            self.assertGreater(timeout, 0)

    def test_attribution_disabled_no_network(self):
        p = provider()
        with self.assertRaisesRegex(music.LibraryBgmError, "attribution:"):
            p.acquire(dict(BRIEF, allowAttribution=False), 10)
        self.assertEqual(p._opener.requests, [])

    def test_license_must_be_current_and_exact(self):
        for bad in (b"<html>login</html>", LICENSE.replace(b"4.0", b"3.0"),
                    LICENSE.replace(b"Kevin MacLeod", b"Other Creator"), b"\xff"):
            p = provider(license_bytes=bad)
            with self.assertRaisesRegex(music.LibraryBgmError, "license:"):
                p.acquire(BRIEF, 10)
            self.assertEqual(len(p._opener.requests), 1)

    def test_selection_failure_does_not_download(self):
        p = provider(records=[dict(TRACK, feel="Dark")])
        with self.assertRaisesRegex(music.LibraryBgmError, "selection:"):
            p.acquire(BRIEF, 10)
        self.assertEqual(len(p._opener.requests), 2)

    def test_non_mp3_and_bad_json(self):
        with self.assertRaisesRegex(music.LibraryBgmError, "audio:"):
            provider(audio=b"<html>blocked</html>").acquire(BRIEF, 10)
        p = provider()
        p._opener.responses[1] = Response(b"{")
        with self.assertRaisesRegex(music.LibraryBgmError, "catalog:"):
            p.acquire(BRIEF, 10)

    def test_strict_fixed_origin_path_and_redirects(self):
        for url in (
            "http://incompetech.com/music/royalty-free/pieces.json",
            music.CATALOG_URL + "?story=private",
            music.CATALOG_URL.replace("incompetech.com", "evil.example"),
            music.CATALOG_URL.replace("incompetech.com", "x@incompetech.com"),
            music.CATALOG_URL.replace("incompetech.com", "incompetech.com:443"),
            music.AUDIO_PREFIX + "../evil.mp3",
            music.AUDIO_PREFIX + "%2fsecret.mp3",
            music.AUDIO_PREFIX + "%252e%252e%252fsecret.mp3",
            music.AUDIO_PREFIX + "abc.mp3#fragment",
        ):
            with self.subTest(url=url), self.assertRaisesRegex(music.LibraryBgmError, "url:"):
                music._safe_url(url, "audio" if ".mp3" in url else "catalog")
        p = provider()
        p._opener.responses[0].url = "https://evil.example"
        with self.assertRaisesRegex(music.LibraryBgmError, "redirect:"):
            p.acquire(BRIEF, 10)
        with self.assertRaisesRegex(music.LibraryBgmError, "redirect:"):
            music._NoRedirect().redirect_request(None, None, 302, "", {}, music.CATALOG_URL)

    def test_bounded_sizes_truncation_and_encodings(self):
        for length in ("999999999", "-1", "abc", "1"):
            p = provider()
            p._opener.responses[0].headers.replace_header("Content-Length", length)
            with self.assertRaises(music.LibraryBgmError):
                p.acquire(BRIEF, 10)
        p = provider()
        del p._opener.responses[0].headers["Content-Length"]
        with patch.object(music, "MAX_LICENSE_BYTES", 5):
            with self.assertRaisesRegex(music.LibraryBgmError, "size:"):
                p.acquire(BRIEF, 10)
        p = provider()
        p._opener.responses[0].headers["Content-Encoding"] = "gzip"
        with self.assertRaisesRegex(music.LibraryBgmError, "response:"):
            p.acquire(BRIEF, 10)

    def test_explicit_network_categories_no_retries_or_payload_leak(self):
        failures = [(TimeoutError("PRIVATE"), "timeout:"),
                    (URLError("PRIVATE"), "network:"),
                    (HTTPError(music.CATALOG_URL, 403, "PRIVATE", {}, io.BytesIO()), "http:")]
        for failure, category in failures:
            p = provider()
            p._opener.responses[0] = failure
            with self.assertRaisesRegex(music.LibraryBgmError, category) as caught:
                p.acquire(BRIEF, 10)
            self.assertNotIn("PRIVATE", str(caught.exception))
            self.assertEqual(len(p._opener.requests), 1)

    def test_cumulative_deadline_and_no_stale_license_reuse(self):
        p = provider()
        with patch.object(music.time, "monotonic", side_effect=[0, 0, 0, 601]):
            with self.assertRaisesRegex(music.LibraryBgmError, "timeout:"):
                p.acquire(BRIEF, 10)
        p = provider()
        p.acquire(BRIEF, 10)
        p._opener = Opener(Response(b"License removed"))
        with self.assertRaisesRegex(music.LibraryBgmError, "license:"):
            p.acquire(BRIEF, 10)
        self.assertIsNone(p.last_evidence)


if __name__ == "__main__":
    unittest.main()
