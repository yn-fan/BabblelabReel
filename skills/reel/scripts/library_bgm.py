"""Reviewed CC0/CC BY Commons library; stdlib only, no search or credentials.

LibraryMusic.select(brief, minimum_duration) is an offline static helper.
Only libraryTags are used from the brief; neither tags nor story leave the host.
Acquisition performs one current-page verification and one original download.
The caller owns publication, audio measurement and subsequent human audition.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
from http.client import HTTPException
import json
import math
from pathlib import Path
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


CATALOG_PATH = Path(__file__).resolve().parents[1] / "assets/music-library.json"
API_URL = "https://commons.wikimedia.org/w/api.php"
LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
LICENSES = {
    "CC0-1.0": (LICENSE_URL, False, "cc0", "CC0", "Creative Commons Zero, Public Domain Dedication", "cc-zero"),
    "CC-BY-4.0": (
        "https://creativecommons.org/licenses/by/4.0/", True, "cc-by-4.0",
        "CC BY 4.0", "Creative Commons Attribution 4.0", "cc-by-4.0",
    ),
    "CC-BY-3.0": (
        "https://creativecommons.org/licenses/by/3.0/", True, "cc-by-3.0",
        "CC BY 3.0", "Creative Commons Attribution 3.0", "cc-by-3.0",
    ),
}
MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_AUDIO_BYTES = 128 * 1024 * 1024
USER_AGENT = "EmmaReelLibrary/1.1 (bounded licensed music acquisition; https://github.com/gim-home/Emma)"
GENRE_TAGS = frozenset({"ambient", "lofi", "techno", "classical", "jazz", "rock"})
MOOD_TAGS = frozenset({
    "calm", "relaxed", "reflective", "mellow", "warm", "energetic", "driving",
    "dark", "sad", "uplifting", "playful", "dramatic", "tense",
})
INSTRUMENT_TAGS = frozenset({"keyboard", "piano", "guitar", "strings", "drums"})
TEXTURE_TAGS = frozenset({"soft", "electronic", "rhythmic", "acoustic"})
CONTROLLED_TAGS = GENRE_TAGS | MOOD_TAGS | INSTRUMENT_TAGS | TEXTURE_TAGS


class LibraryBgmError(ValueError):
    """Explicit failure without private brief or arbitrary remote payload text."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if fp is not None:
            fp.close()
        raise LibraryBgmError("redirect: library requests must not redirect")


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _plain(value: str) -> str:
    parser = _PlainText()
    parser.feed(value)
    return "".join(parser.parts).strip()


def _number(value, label: str, maximum: float) -> float:
    if (
        isinstance(value, bool) or not isinstance(value, (int, float))
        or not math.isfinite(value) or not 0 < value <= maximum
    ):
        raise LibraryBgmError(f"input: {label} must be a finite positive number <= {maximum}")
    return float(value)


def _safe_url(value: str, kind: str) -> str:
    if not isinstance(value, str) or any(ord(c) <= 32 or ord(c) >= 127 for c in value):
        raise LibraryBgmError("url: invalid library URL")
    try:
        url = urlsplit(value)
        if (
            url.scheme != "https" or url.username or url.password or url.port
            or url.fragment or "\\" in unquote(url.path)
            or any(p in (".", "..") for p in unquote(url.path).split("/"))
            or any(ord(c) < 32 for c in unquote(value))
        ):
            raise ValueError
    except ValueError:
        raise LibraryBgmError("url: unsafe library URL") from None
    if kind == "api":
        valid = url.netloc == "commons.wikimedia.org" and url.path == "/w/api.php"
    elif kind == "page":
        valid = (
            url.netloc == "commons.wikimedia.org" and url.path.startswith("/wiki/File:")
            and not url.query
        )
    else:
        valid = (
            url.netloc == "upload.wikimedia.org"
            and re.fullmatch(r"/wikipedia/commons/[0-9a-f]/[0-9a-f]{2}/[^/]+\.(wav|flac)", url.path)
            and not url.query
        )
    if not valid:
        raise LibraryBgmError("url: source is outside the fixed Commons endpoints")
    return value


def _original_url(value: str) -> str:
    """Commons imageinfo adds these public analytics fields; never follow a redirect."""
    if not isinstance(value, str):
        raise LibraryBgmError("url: invalid original-file URL")
    try:
        parts = urlsplit(value)
        if parts.query and sorted(parse_qsl(parts.query, strict_parsing=True)) != sorted([
            ("utm_source", "commons.wikimedia.org"),
            ("utm_campaign", "imageinfo"), ("utm_content", "original"),
        ]):
            raise ValueError
    except ValueError:
        raise LibraryBgmError("url: unexpected original-file query parameters") from None
    return _safe_url(parts._replace(query="").geturl(), "audio")


def _catalog() -> list[dict]:
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        if data["schemaVersion"] != 1 or not isinstance(data["tracks"], list) or not data["tracks"]:
            raise ValueError
        tracks = data["tracks"]
        ids = set()
        source_files = set()
        for track in tracks:
            policy = LICENSES.get(track["license"])
            if (
                track["id"] in ids or not re.fullmatch(r"[a-z0-9-]+", track["id"])
                or track["sourceDownloadUrl"] in source_files
                or track["audioFormat"] not in ("wav", "flac")
                or policy is None or track["licenseUrl"] != policy[0]
                or track["attributionRequired"] is not policy[1]
                or track["allowsProjectRedistribution"] is not True
                or not isinstance(track["sourceRevisionId"], int)
                or isinstance(track["sourceRevisionId"], bool) or track["sourceRevisionId"] <= 0
                or not re.fullmatch(r"[0-9a-f]{40}", track["sourceFileSha1"])
                or not re.fullmatch(r"[0-9a-f]{64}", track["sourceWikitextSha256"])
                or not isinstance(track["tags"], list) or not track["tags"]
                or any(t not in CONTROLLED_TAGS for t in track["tags"])
                or not all(isinstance(track[k], str) and track[k].strip()
                           for k in ("title", "creator", "rightsEvidence", "tagEvidence"))
                or ("creditCreators" in track and (
                    not isinstance(track["creditCreators"], str)
                    or track["creator"] not in track["creditCreators"]
                ))
            ):
                raise ValueError
            _number(track["durationSeconds"], "catalog duration", 86400)
            _number(track["sizeBytes"], "catalog size", MAX_AUDIO_BYTES)
            if not isinstance(track["sizeBytes"], int):
                raise ValueError
            _safe_url(track["sourceUrl"], "page")
            _safe_url(track["sourceDownloadUrl"], "audio")
            if (
                unquote(urlsplit(track["sourceUrl"]).path[len("/wiki/"):]).replace("_", " ")
                != track["fileTitle"]
                or unquote(urlsplit(track["sourceDownloadUrl"]).path.rsplit("/", 1)[1]).replace("_", " ")
                != track["fileTitle"].removeprefix("File:")
                or not track["fileTitle"].endswith("." + track["audioFormat"])
            ):
                raise ValueError
            ids.add(track["id"])
            source_files.add(track["sourceDownloadUrl"])
        return tracks
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        raise LibraryBgmError("catalog: invalid, unsafe or unsupported curated music entry") from None


class LibraryMusic:
    def __init__(self, timeout: float = 120, cache_dir: Path | None = None):
        self.timeout = _number(timeout, "timeout", 86400)
        self.cache_dir = cache_dir
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())
        self.last_evidence: dict | None = None

    @staticmethod
    def validate_brief(brief: dict) -> list[str]:
        tags = brief.get("libraryTags") if isinstance(brief, dict) else None
        if (
            not isinstance(tags, list) or not 1 <= len(tags) <= 8
            or any(not isinstance(tag, str) or tag not in CONTROLLED_TAGS for tag in tags)
            or len(set(tags)) != len(tags)
        ):
            raise LibraryBgmError("input: libraryTags requires 1-8 unique controlled English tags")
        if "allowAttribution" in brief and type(brief["allowAttribution"]) is not bool:
            raise LibraryBgmError("input: allowAttribution must be a boolean")
        return tags

    @staticmethod
    def select(brief: dict, minimum_duration: float) -> dict:
        """Return a copied catalog entry with selectionRationale; never accesses network."""
        minimum = _number(minimum_duration, "minimum_duration", 86400)
        tags = LibraryMusic.validate_brief(brief)
        wanted = set(tags)
        candidates = []
        for track in _catalog():
            if not brief.get("allowAttribution", True) and track["attributionRequired"]:
                continue
            available = set(track["tags"])
            overlap = wanted & available
            # Texture overlap must not silently override any requested mood/instrument.
            if any((wanted & group) - available
                   for group in (GENRE_TAGS, MOOD_TAGS, INSTRUMENT_TAGS)):
                continue
            if not overlap or track["durationSeconds"] < minimum:
                continue
            score = sum(
                5 if tag in GENRE_TAGS else 4 if tag in MOOD_TAGS
                else 3 if tag in INSTRUMENT_TAGS else 1 for tag in overlap
            )
            candidates.append((score, len(overlap) / len(wanted), track))
        if not candidates:
            raise LibraryBgmError("selection: no curated track matches the approved tags and duration")
        candidates.sort(key=lambda row: (-row[0], -row[1], row[2]["id"]))
        track = copy.deepcopy(candidates[0][2])
        matching = ", ".join(sorted(wanted & set(track["tags"])))
        track["selectionRationale"] = (
            f"Approved direction tags matched curated metadata: {matching}. "
            f"Source duration {track['durationSeconds']:.3f}s covers {minimum:.3f}s. "
            "Mood/texture fit is metadata-based inference, not a listening assessment; "
            "human audition must confirm instrumental suitability and aesthetic fit."
        )
        return track

    @staticmethod
    def _remaining(deadline: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LibraryBgmError("timeout: library acquisition deadline expired")
        return remaining

    def _fetch(self, url: str, kind: str, limit: int, deadline: float) -> bytes:
        _safe_url(url, kind)
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json" if kind == "api" else "audio/flac, audio/wav",
            "Accept-Encoding": "identity",
        }
        if kind == "audio":
            # Commons advertises byte ranges. Ask for the entire pinned original in
            # one bounded request, not fragments/retries or an unbounded stream.
            headers["Range"] = f"bytes=0-{limit - 1}"
        request = Request(url, headers=headers)
        try:
            with self._opener.open(request, timeout=self._remaining(deadline)) as response:
                if response.geturl() != url or 300 <= response.status < 400:
                    raise LibraryBgmError("redirect: library requests must not redirect")
                if response.status == 206 and kind == "audio":
                    if response.headers.get("Content-Range") != f"bytes 0-{limit - 1}/{limit}":
                        raise LibraryBgmError("size: library range does not cover the full original")
                elif response.status != 200:
                    raise LibraryBgmError("network: library source did not return a complete response")
                mime = response.headers.get_content_type()
                allowed = {"application/json"} if kind == "api" else {
                    "audio/flac", "audio/x-flac", "audio/wav", "audio/x-wav", "audio/wave",
                    "application/octet-stream",
                }
                if mime not in allowed or response.headers.get("Content-Encoding", "identity") != "identity":
                    raise LibraryBgmError("format: unexpected library content type or encoding")
                length = response.headers.get("Content-Length")
                if length is not None:
                    if not re.fullmatch(r"[0-9]+", length) or not 0 < int(length) <= limit:
                        raise LibraryBgmError("size: invalid or oversized library Content-Length")
                    length = int(length)
                chunks, total = [], 0
                while True:
                    remaining = self._remaining(deadline)
                    sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
                    if sock is not None:
                        sock.settimeout(remaining)
                    chunk = response.read1(min(65536, limit + 1 - total))
                    self._remaining(deadline)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > limit:
                        raise LibraryBgmError("size: library response exceeds byte limit")
                if length is not None and total != length:
                    raise LibraryBgmError("size: truncated library response")
                return b"".join(chunks)
        except HTTPError as error:
            error.close()
            if 300 <= error.code < 400:
                raise LibraryBgmError("redirect: library requests must not redirect") from None
            if error.code == 429:
                retry_after = error.headers.get("Retry-After", "") if error.headers else ""
                wait = f"; Retry-After {retry_after}s" if re.fullmatch(r"[0-9]{1,8}", retry_after) else ""
                raise LibraryBgmError(f"quota: Commons rate limit{wait}; no retry attempted") from None
            raise LibraryBgmError("network: Commons HTTP failure; no retry attempted") from None
        except (TimeoutError, socket.timeout):
            raise LibraryBgmError("timeout: library acquisition timed out") from None
        except (URLError, OSError, HTTPException):
            raise LibraryBgmError("network: library acquisition failed; no retry attempted") from None

    def _verify(self, track: dict, deadline: float) -> dict:
        url = API_URL + "?" + urlencode({
            "action": "query", "format": "json", "prop": "imageinfo|revisions",
            "iiprop": "url|size|sha1|mime|extmetadata",
            "rvprop": "ids|timestamp|content", "rvslots": "main",
            "titles": track["fileTitle"], "maxlag": "5",
        })
        raw = self._fetch(url, "api", MAX_METADATA_BYTES, deadline)
        try:
            data = json.loads(raw)
            pages = data["query"]["pages"]
            if "error" in data or "warnings" in data or not isinstance(pages, dict) or len(pages) != 1:
                raise ValueError
            page = next(iter(pages.values()))
            revision = page["revisions"][0]
            info = page["imageinfo"][0]
            ext = info["extmetadata"]
            text = revision["slots"]["main"]["*"]
            policy = LICENSES[track["license"]]
            license_url, attribution, license_code, license_name, usage_terms, license_template = policy
            def meta(key):
                value = ext[key]["value"]
                if not isinstance(value, str):
                    raise ValueError
                return value
            if (
                page["title"] != track["fileTitle"] or page["ns"] != 6
                or page["imagerepository"] != "local" or "missing" in page
                or revision["revid"] != track["sourceRevisionId"]
                or hashlib.sha256(text.encode("utf-8")).hexdigest() != track["sourceWikitextSha256"]
            ):
                raise LibraryBgmError("changed: source page revision changed; curator review required")
            if (
                meta("License") != license_code or meta("LicenseShortName") != license_name
                or meta("UsageTerms") != usage_terms
                or meta("AttributionRequired") != str(attribution).lower() or meta("Restrictions").strip()
                or meta("LicenseUrl") not in {
                    license_url, license_url.replace("https:", "http:"),
                    license_url.rstrip("/"), license_url.replace("https:", "http:").rstrip("/"),
                    license_url + "deed.en", license_url.replace("https:", "http:") + "deed.en",
                }
                or _plain(meta("Credit")) != "Own work"
                or _plain(meta("Artist")) != track["creator"]
                or not re.search(r"\{\{self\|" + re.escape(license_template) + r"\}\}", text, re.I)
                or not re.search(r"\|source\s*=\s*\{\{own\}\}", text, re.I)
                or re.search(
                    r"copyvio|deletion request|copyright violation|license review|disputed|noncommercial",
                    meta("Categories") + " " + meta("ImageDescription"), re.I,
                )
            ):
                raise LibraryBgmError("license: current source does not match the reviewed own-work CC0/CC BY license")
            if (
                info["sha1"] != track["sourceFileSha1"]
                or info["size"] != track["sizeBytes"]
                or info["mime"] != "audio/" + track["audioFormat"]
                or not math.isclose(_number(info["duration"], "source duration", 86400),
                                    track["durationSeconds"], rel_tol=0, abs_tol=0.001)
                or _original_url(info["url"]) != track["sourceDownloadUrl"]
                or _safe_url(info["descriptionurl"], "page") != track["sourceUrl"]
            ):
                raise LibraryBgmError("changed: original file metadata changed; curator review required")
        except LibraryBgmError:
            raise
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, RecursionError):
            raise LibraryBgmError("schema: invalid Commons verification response") from None
        self.last_evidence = {
            "requestUrl": url, "verifiedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "response": data,
        }
        return info

    def acquire(self, brief: dict, minimum_duration: float) -> dict:
        self.last_evidence = None
        track = self.select(brief, minimum_duration)
        deadline = time.monotonic() + self.timeout
        info = self._verify(track, deadline)
        cached = self.cache_dir / f"{track['id']}.{track['audioFormat']}" if self.cache_dir else None
        if cached is not None and (cached.exists() or cached.is_symlink()):
            if cached.is_symlink() or not cached.is_file() or cached.stat().st_size != track["sizeBytes"]:
                raise LibraryBgmError("cache: cached original must be a regular file of the expected size")
            audio = cached.read_bytes()
        else:
            audio = self._fetch(track["sourceDownloadUrl"], "audio", track["sizeBytes"], deadline)
        if len(audio) != info["size"] or hashlib.sha1(audio).hexdigest() != info["sha1"]:
            raise LibraryBgmError("hash: downloaded bytes do not match the current and curated SHA-1")
        # These are only container checks. Curated byte identity prevents substitution;
        # the shared publisher measures the full stream before accepting it for a Reel.
        if track["audioFormat"] == "flac":
            valid = len(audio) > 42 and audio[:4] == b"fLaC" and audio[4:8] in (
                b"\x00\x00\x00\x22", b"\x80\x00\x00\x22",
            )
        else:
            valid = (
                len(audio) >= 44 and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"
                and int.from_bytes(audio[4:8], "little") + 8 == len(audio)
            )
        if not valid:
            raise LibraryBgmError("format: source is not the declared native WAV/FLAC container")
        self._remaining(deadline)
        provenance = {
            "kind": "licensed-library-music", "provider": "wikimedia-commons",
            "trackId": track["id"], "license": track["license"], "licenseUrl": track["licenseUrl"],
            "sourceUrl": track["sourceUrl"], "sourceDownloadUrl": track["sourceDownloadUrl"],
            "title": track["title"], "creator": track["creator"],
            "creditCreators": track.get("creditCreators", track["creator"]),
            "sourceRevisionId": track["sourceRevisionId"], "sourceFileSha1": info["sha1"],
            "sourceSha256": hashlib.sha256(audio).hexdigest(),
            "sourceWikitextSha256": track["sourceWikitextSha256"],
            "verifiedAt": self.last_evidence["verifiedAt"],
            "attributionRequired": track["attributionRequired"], "allowsProjectRedistribution": True,
            "selectionRationale": track["selectionRationale"],
        }
        return {"audio": audio, "audioFormat": track["audioFormat"], "provenance": provenance}
