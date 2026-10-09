"""Bounded first-party website catalog acquisition, NOT a supported public API.

Only public fixed URLs leave the host. Selection is local; no brief is sent.
Each acquisition verifies the current FAQ, reads one catalog and downloads one
original. The official detail page renders that same catalog and the FAQ's
credit template, so fetching it again adds no independent track-rights evidence.
No retries, alternate hosts, bulk downloads, or persistent license cache.
The caller must measure the MP3 before draft publication, then decode/audition
the mixed video before final delivery under Reel's existing approval policy.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
from http.client import HTTPException
import json
import math
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from library_bgm import CONTROLLED_TAGS, LICENSES, LibraryBgmError, LibraryMusic


ORIGIN = "https://incompetech.com"
CATALOG_URL = ORIGIN + "/music/royalty-free/pieces.json"
LICENSE_PAGE_URL = ORIGIN + "/music/royalty-free/faq.html"
PAGE_PREFIX = ORIGIN + "/music/royalty-free/index.html?isrc="
AUDIO_PREFIX = ORIGIN + "/music/royalty-free/mp3-royaltyfree/"
LICENSE_URL = LICENSES["CC-BY-4.0"][0]
MAX_CATALOG_BYTES = 8 * 1024 * 1024
MAX_LICENSE_BYTES = 1024 * 1024
MAX_AUDIO_BYTES = 64 * 1024 * 1024
USER_AGENT = "EmmaReelLibrary/1.1 (bounded first-party licensed music acquisition)"

# Editorial mapping of explicit catalog metadata, not inferred instrumentation.
MOODS = {
    "calm": {"calming", "relaxed"}, "relaxed": {"relaxed", "calming"},
    "reflective": {"reflective", "somber"}, "mellow": {"relaxed", "calming"},
    "warm": {"warm"}, "energetic": {"energetic", "driving", "action"},
    "driving": {"driving"}, "dark": {"dark", "eerie"},
    "sad": {"sad", "somber"}, "uplifting": {"uplifting", "bright"},
    "playful": {"bouncy", "humorous", "playful"},
    "dramatic": {"epic", "intense", "dramatic"},
    "tense": {"suspenseful", "unnerving", "tense"},
}
INSTRUMENTS = {
    "keyboard": r"\b(?:keyboard|keyboards|piano|organ|synth|synths|synthesizer)\b",
    "piano": r"\bpiano\b", "guitar": r"\bguitars?\b",
    "strings": r"\b(?:strings|violin|viola|cello|violins|cellos)\b",
    "drums": r"\b(?:drums?|drum kit|drum machine)\b",
}
# Official index.html genre table. Electronica != techno, soundtrack != ambient.
GENRES = {"4": "classical", "11": "jazz", "19": "rock"}
CONFLICTS = {
    "uplifting": {"dark", "eerie", "somber", "sad", "unnerving"},
    "calm": {"action", "aggressive", "driving", "intense", "unnerving"},
    "relaxed": {"action", "aggressive", "driving", "intense", "unnerving"},
    "mellow": {"action", "aggressive", "driving", "intense", "unnerving"},
    "playful": {"somber", "sad"},
    "sad": {"bright", "uplifting", "humorous"},
    "dark": {"bright", "uplifting"},
}


def _positive(value, label):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 < value <= 86400):
        raise LibraryBgmError(f"input: {label} must be positive and <= 86400")
    return float(value)


def _safe_url(value, kind):
    try:
        if not isinstance(value, str) or any(ord(c) <= 32 or ord(c) >= 127 for c in value):
            raise ValueError
        p = urlsplit(value)
        decoded = unquote(p.path)
        if (p.scheme != "https" or p.netloc != "incompetech.com"
                or p.username or p.password or p.port or p.fragment
                or "\\" in decoded or "%" in decoded
                or any(x in (".", "..") for x in decoded.split("/"))
                or any(ord(c) < 32 for c in decoded)):
            raise ValueError
        valid = (
            (kind == "catalog" and value == CATALOG_URL)
            or (kind == "license" and value == LICENSE_PAGE_URL)
            or (kind == "page" and value.startswith(PAGE_PREFIX)
                and re.fullmatch(r"USUAN[0-9]{7}", p.query.removeprefix("isrc=")))
            or (kind == "audio" and value.startswith(AUDIO_PREFIX) and not p.query
                and re.fullmatch(r"[^/\\]+\.mp3", decoded.removeprefix(
                    "/music/royalty-free/mp3-royaltyfree/")))
        )
        if not valid:
            raise ValueError
    except ValueError:
        raise LibraryBgmError("url: source outside fixed trusted Incompetech endpoints") from None
    return value


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if fp:
            fp.close()
        raise LibraryBgmError("redirect: Incompetech redirects are not permitted")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _verify_license(raw):
    try:
        parser = _Text()
        parser.feed(raw.decode("utf-8"))
        text = " ".join(" ".join(parser.parts).split())
    except (UnicodeError, ValueError):
        raise LibraryBgmError("license: unreadable current FAQ") from None
    if not all(s in text for s in (
        "Kevin MacLeod (incompetech.com)",
        "Licensed under Creative Commons: By Attribution 4.0",
        LICENSE_URL,
    )):
        raise LibraryBgmError("license: current FAQ does not confirm required CC BY 4.0 credit")


def _duration(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:[0-5]\d:[0-5]\d", value):
        raise ValueError
    h, m, s = map(int, value.split(":"))
    result = h * 3600 + m * 60 + s
    if not 0 < result <= 86400:
        raise ValueError
    return result


def _has_vocals(track):
    for key in ("instruments", "description"):
        value = track[key].lower()
        # Negation is local; unrelated template language must not imply vocals.
        value = re.sub(
            r"\b(?:no|without)\s+(?:any\s+)?(?:vocals?|voices?|lyrics?|choirs?|singing)\b"
            r"|\b(?:vocals?|lyrics?)[- ]free\b", "", value,
        )
        if re.search(r"\b(?:vocals?|vocalist|voices?|lyrics?|choirs?|choral|singing|singer)\b", value):
            return True
    return False


def _entry(record):
    if not isinstance(record, dict):
        return None
    try:
        if not all(isinstance(record[k], str) for k in (
            "title", "filename", "isrc", "feel", "instruments", "genre", "description",
        )):
            return None
        title, filename, isrc = record["title"].strip(), record["filename"], record["isrc"]
        if (not title or len(title) > 500 or any(ord(c) < 32 for c in title)
                or not re.fullmatch(r"USUAN[0-9]{7}", isrc)
                or not filename.endswith(".mp3") or len(filename) > 255
                or any(c in filename for c in "/\\%")
                or filename in (".", "..") or any(ord(c) < 32 for c in filename)):
            return None
        duration = _duration(record["length"])
        source = _safe_url(PAGE_PREFIX + isrc, "page")
        audio = _safe_url(AUDIO_PREFIX + quote(filename, safe=""), "audio")
        if _has_vocals(record):
            return None
        feels = {v.strip().lower() for v in record["feel"].split(",")}
        tags = {tag for tag, values in MOODS.items() if feels & values}
        tags.update(tag for tag, pattern in INSTRUMENTS.items()
                    if re.search(pattern, record["instruments"], re.I))
        if record["genre"] in GENRES:
            tags.add(GENRES[record["genre"]])
        # Explicit labels are useful even if future catalog entries use text genres.
        if record["genre"].lower() in {"ambient", "lofi", "techno", "classical", "jazz", "rock"}:
            tags.add(record["genre"].lower())
        if record["genre"] == "7":
            tags.add("electronic")
        tags.update(feels & {"soft", "rhythmic", "acoustic"})
        assert tags <= CONTROLLED_TAGS
        return {
            "trackId": isrc, "title": title, "sourceTitle": title,
            "sourceUrl": source, "sourceDownloadUrl": audio,
            "durationSeconds": duration, "tags": sorted(tags), "feel": sorted(feels),
        }
    except (KeyError, ValueError):
        # A malformed or novel record cannot invalidate the whole catalog.
        return None


def rank_catalog(catalog, brief, minimum_duration):
    """Offline deterministic ranking; every confirmed tag must match explicitly."""
    tags = set(LibraryMusic.validate_brief(brief))
    minimum = _positive(minimum_duration, "minimum_duration")
    if not brief.get("allowAttribution", True):
        raise LibraryBgmError("attribution: Incompetech requires visible CC BY credit")
    if not isinstance(catalog, list) or not catalog:
        raise LibraryBgmError("catalog: expected a nonempty website catalog array")
    candidates = []
    for record in catalog:
        track = _entry(record)
        if (track is None or track["durationSeconds"] < minimum
                or not tags <= set(track["tags"])
                or any(set(track["feel"]) & CONFLICTS.get(tag, set()) for tag in tags)):
            continue
        track["selectionRationale"] = (
            "Confirmed tags matched explicit Incompetech feel/instrument/genre metadata: "
            + ", ".join(sorted(tags))
            + f". Catalog duration {track['durationSeconds']}s covers {minimum:g}s. "
            "Metadata inference is not listening verification; caller must measure audio "
            "and human audition must confirm instrumental and aesthetic suitability."
        )
        candidates.append(track)
    # Minimize download duration; stable public identifier breaks ties.
    return sorted(candidates, key=lambda t: (t["durationSeconds"], t["trackId"]))


class IncompetechMusic:
    def __init__(self, timeout=600, cache_dir=None):
        self.timeout = _positive(timeout, "timeout")
        self.cache_dir = cache_dir  # Accepted for provider compatibility; no disk writes.
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())
        self.last_evidence = None

    def _fetch(self, url, kind, maximum, deadline):
        _safe_url(url, kind)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LibraryBgmError("timeout: Incompetech cumulative deadline exhausted")
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
        try:
            with self._opener.open(request, timeout=remaining) as response:
                if response.geturl() != url:
                    raise LibraryBgmError("redirect: response URL changed")
                if response.status != 200:
                    raise LibraryBgmError(f"http: Incompetech status {response.status}")
                size = response.headers.get("Content-Length")
                if size is not None and (not size.isdigit() or int(size) > maximum):
                    raise LibraryBgmError("size: invalid or excessive response length")
                if response.headers.get("Content-Encoding", "identity") != "identity":
                    raise LibraryBgmError("response: encoded response not supported")
                chunks, total = [], 0
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise LibraryBgmError("timeout: Incompetech cumulative deadline exhausted")
                    # urllib's initial socket timeout alone would reset for each read.
                    fp = getattr(response, "fp", None)
                    sock = getattr(getattr(fp, "raw", None), "_sock", None)
                    if sock is not None:
                        sock.settimeout(remaining)
                    chunk = response.read1(min(65536, maximum + 1 - total))
                    if time.monotonic() > deadline:
                        raise LibraryBgmError("timeout: Incompetech cumulative deadline exhausted")
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > maximum:
                        raise LibraryBgmError("size: response exceeds bounded byte limit")
                    chunks.append(chunk)
                if not total or (size is not None and total != int(size)):
                    raise LibraryBgmError("response: empty or truncated response")
                return b"".join(chunks)
        except HTTPError as exc:
            exc.close()
            raise LibraryBgmError(f"http: Incompetech status {exc.code}; no retry or bypass") from None
        except (TimeoutError, socket.timeout):
            raise LibraryBgmError("timeout: Incompetech request deadline exhausted") from None
        except (URLError, HTTPException, OSError):
            raise LibraryBgmError("network: Incompetech unavailable; no retry or bypass") from None

    def acquire(self, brief, minimum_duration):
        self.last_evidence = None
        LibraryMusic.validate_brief(brief)
        _positive(minimum_duration, "minimum_duration")
        if not brief.get("allowAttribution", True):
            raise LibraryBgmError("attribution: Incompetech requires visible CC BY credit")
        deadline = time.monotonic() + self.timeout
        license_bytes = self._fetch(LICENSE_PAGE_URL, "license", MAX_LICENSE_BYTES, deadline)
        _verify_license(license_bytes)
        catalog_bytes = self._fetch(CATALOG_URL, "catalog", MAX_CATALOG_BYTES, deadline)
        try:
            catalog = json.loads(catalog_bytes)
        except (ValueError, UnicodeError, RecursionError):
            raise LibraryBgmError("catalog: invalid website catalog JSON") from None
        candidates = rank_catalog(catalog, brief, minimum_duration)
        if not candidates:
            raise LibraryBgmError("selection: no instrumental track matches all confirmed tags and duration")
        selected = candidates[0]
        audio = self._fetch(selected["sourceDownloadUrl"], "audio", MAX_AUDIO_BYTES, deadline)
        # Structural/decoded duration validation belongs to Reel's audio parser.
        if not (audio.startswith(b"ID3") or (len(audio) >= 2 and audio[0] == 255 and audio[1] & 224 == 224)):
            raise LibraryBgmError("audio: response is not recognizable MP3 data")
        provenance = {
            k: selected[k] for k in (
                "trackId", "title", "sourceTitle", "sourceUrl", "sourceDownloadUrl",
                "selectionRationale",
            )
        }
        provenance.update({
            "kind": "licensed-library-music", "provider": "incompetech",
            "creator": "Kevin MacLeod", "creditCreators": "Kevin MacLeod (incompetech.com)",
            "license": "CC-BY-4.0", "licenseUrl": LICENSE_URL,
            "attributionRequired": True, "allowsProjectRedistribution": True,
            "verifiedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "sourceFileSha1": hashlib.sha1(audio).hexdigest(),
            "sourceSha256": hashlib.sha256(audio).hexdigest(),
            "sourceCatalogSha256": hashlib.sha256(catalog_bytes).hexdigest(),
            "sourceLicenseSha256": hashlib.sha256(license_bytes).hexdigest(),
            "sourceCatalogUrl": CATALOG_URL, "sourceLicenseUrl": LICENSE_PAGE_URL,
        })
        self.last_evidence = {
            "catalogRecords": len(catalog), "eligibleTracks": len(candidates),
            "catalogDurationSeconds": selected["durationSeconds"], "provenance": provenance.copy(),
            "note": "Eligible count is specific to confirmed tags, duration and vocal exclusions.",
        }
        return {"audio": audio, "audioFormat": "mp3", "provenance": provenance}
