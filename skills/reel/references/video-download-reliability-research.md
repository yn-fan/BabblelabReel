# Video downloader reliability: primary-source review

Reviewed September 19, 2026. This note records GitHub source research, not
platform compatibility tests. The local observations in
[video-acquisition.md](video-acquisition.md#quality-and-operational-lessons)
are separate evidence. No media links, cookies or private artifact paths were
sent to GitHub; alternative downloaders were not installed or run.

## Decision

Keep yt-dlp as the default. Repair dependency discovery, error classification
and quality reporting before adding another extractor. Host question failures
and stale installed skill versions are separate integration problems: replacing
the downloader cannot fix them. Specialized alternatives require deliberate
selection, credential/output review and an authorized live test.

## yt-dlp

The inspected revision is
[`c7fb478d21e9e59524befbe23f7801bb267fb880`](https://github.com/yt-dlp/yt-dlp/tree/c7fb478d21e9e59524befbe23f7801bb267fb880).
Its [manifest](https://github.com/yt-dlp/yt-dlp/blob/c7fb478d21e9e59524befbe23f7801bb267fb880/pyproject.toml#L17-L28)
requires Python 3.10+ and declares Unlicense; bundled dependencies have their
own obligations. Compare the actual installed version before applying these
observations to an older release.

**Bilibili.** The extractor uses `SESSDATA` presence as its login signal and
parses the formats returned by the platform. It compares returned and advertised
qualities and can emit a missing-premium-formats hint. Anonymous paths exist,
including `try_look`; successful metadata does not prove full-length media or
4K availability. Cookie presence is not server-validated entitlement. Do not
invent a universal anonymous resolution ceiling or promise that login unlocks
every resolution. Sources:
[format parsing](https://github.com/yt-dlp/yt-dlp/blob/c7fb478d21e9e59524befbe23f7801bb267fb880/yt_dlp/extractor/bilibili.py#L55-L106),
[play URL request](https://github.com/yt-dlp/yt-dlp/blob/c7fb478d21e9e59524befbe23f7801bb267fb880/yt_dlp/extractor/bilibili.py#L213-L239),
[anonymous path](https://github.com/yt-dlp/yt-dlp/blob/c7fb478d21e9e59524befbe23f7801bb267fb880/yt_dlp/extractor/bilibili.py#L828-L835).

**Douyin.** When the detail response lacks the expected `aweme_detail`
dictionary, the extractor reports "Fresh cookies (not necessarily logged in)
are needed". A nearby TODO concerns verification-challenge signature cookies.
This is a broad site-response/verification hint, not proof of an expired login.
[Source](https://github.com/yt-dlp/yt-dlp/blob/c7fb478d21e9e59524befbe23f7801bb267fb880/yt_dlp/extractor/tiktok.py#L1492-L1508).
[Issue yt-dlp/yt-dlp#9667](https://github.com/yt-dlp/yt-dlp/issues/9667)
contains reports despite supplied cookies; a
[maintainer suggestion](https://github.com/yt-dlp/yt-dlp/issues/9667#issuecomment-2049769127)
describes manually completing a challenge and using fresh logged-out cookies
for public videos. That suggestion is not a universal fix or authorization
to automate verification bypass.

**Browser profiles.** The documented syntax is
`BROWSER[+KEYRING][:PROFILE][::CONTAINER]`. An unspecified profile defaults to
the most recently accessed one; Chromium implementation selects a cookie
database by modification time. A person being logged into Chrome does not prove
the default-selected profile holds that session. Offer a specifically authorized
profile rather than cycling through all profiles. Database access and DPAPI
decryption failures are local failures, not website login diagnoses.
Sources:
[CLI syntax](https://github.com/yt-dlp/yt-dlp/blob/c7fb478d21e9e59524befbe23f7801bb267fb880/README.md#L717-L735),
[Chromium selection](https://github.com/yt-dlp/yt-dlp/blob/c7fb478d21e9e59524befbe23f7801bb267fb880/yt_dlp/cookies.py#L302-L319),
[DPAPI handling](https://github.com/yt-dlp/yt-dlp/blob/c7fb478d21e9e59524befbe23f7801bb267fb880/yt_dlp/cookies.py#L1098-L1101).

**Quality.** `best` selects a combined audio/video format, not necessarily the
highest separate video stream. `bestvideo*+bestaudio/best` permits separate
streams; FFmpeg merges them. Reel already uses this selector. Keep requested,
available and verified saved quality separate. A required resolution must stop
when absent; best-available selection must disclose its actual resolution.
[Selection documentation](https://github.com/yt-dlp/yt-dlp/blob/c7fb478d21e9e59524befbe23f7801bb267fb880/README.md#L1514-L1541).

## Alternatives and integration costs

| Repository | Verified source evidence | Decision |
|---|---|---|
| [nilaoda/BBDown](https://github.com/nilaoda/BBDown) | Current archive README says updates/support stopped. Historical 1.6.3 targeted .NET 8, MIT, with quality/codec preferences, login and FFmpeg/MP4Box merging. | Historical Bilibili specialization, not a maintained automatic replacement. Historical features do not establish present compatibility. |
| [Johnserf-Seed/f2](https://github.com/Johnserf-Seed/f2) | Python 3.10+, Apache-2.0; Douyin implementation selects ABogus/XBogus signing. Auto-cookie writes credentials to config. Single-video filter uses the first bitrate entry. | A separately approved Douyin adapter experiment, not guaranteed higher quality or a drop-in credential-safe fallback. |
| [iawia002/lux](https://github.com/iawia002/lux) | Go 1.24 source, MIT, FFmpeg merging; Douyin uses Goja/X-Bogus and first PlayAddr URL. Bilibili requests quality 127 and iterates returned DASH streams. | Different extraction path, not proof of better quality, current success or entitlement bypass. |

BBDown evidence:
[archive README](https://github.com/nilaoda/BBDown/blob/1b2fbd4372d0b9840d28072f7914ae9887508e5d/README.md#L1-L21),
[historical .NET target](https://github.com/nilaoda/BBDown/blob/45622f79cd766e0fc6f5cbd49fcf4960340f35c3/BBDown/BBDown.csproj#L4-L7),
[historical options](https://github.com/nilaoda/BBDown/blob/45622f79cd766e0fc6f5cbd49fcf4960340f35c3/README.md#L98-L120).
Historical third-party parsing modes may expose account privileges; they are
outside Reel's local-only acquisition contract.

F2 evidence:
[manifest](https://github.com/Johnserf-Seed/f2/blob/7dab3e2ffffaa2535834d28fca99dbc2e89fa9d3/pyproject.toml#L5-L12),
[signing choice](https://github.com/Johnserf-Seed/f2/blob/7dab3e2ffffaa2535834d28fca99dbc2e89fa9d3/f2/apps/douyin/crawler.py#L97-L104),
[cookie persistence](https://github.com/Johnserf-Seed/f2/blob/7dab3e2ffffaa2535834d28fca99dbc2e89fa9d3/f2/apps/douyin/cli.py#L65-L80),
[first bitrate](https://github.com/Johnserf-Seed/f2/blob/7dab3e2ffffaa2535834d28fca99dbc2e89fa9d3/f2/apps/douyin/filter.py#L1407-L1411).

Lux evidence:
[runtime](https://github.com/iawia002/lux/blob/dd00f6d258d80b6684a0b9402d7124e5c18ef42f/go.mod#L1-L11),
[license](https://github.com/iawia002/lux/blob/dd00f6d258d80b6684a0b9402d7124e5c18ef42f/LICENSE#L1-L7),
[Douyin implementation](https://github.com/iawia002/lux/blob/dd00f6d258d80b6684a0b9402d7124e5c18ef42f/extractors/douyin/douyin.go#L66-L138),
[Bilibili request](https://github.com/iawia002/lux/blob/dd00f6d258d80b6684a0b9402d7124e5c18ef42f/extractors/bilibili/bilibili.go#L381-L386).

## Limits and follow-through

These are source-level findings, not exhaustive security/license audits or live
platform guarantees. Evil0ctal's service remains an unassessed lead from the
supplied archive, not a recommended fallback. Issue counts and popularity are
not reliability evidence.

Reel should discover its approved runtime, offer numeric format inspection,
support explicit profile selection, and report bounded recoverable failures.
Retain user-authorized attempts and file verification before considering a
specialized backend. Keep the installed-plugin activation step separate from
source fixes; never rewrite an immutable plugin cache to claim deployment.
