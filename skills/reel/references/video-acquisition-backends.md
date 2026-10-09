# Video acquisition backend boundaries

The supplied archive included `references/backends.md` and `references/research.md`
dated 2026-09-19. Their repository claims and one reported YouTube download are
**supplied research, not BabblelabReel live verification**. Initial integration used
offline tests, simulated extractors and local fixtures. A subsequent authorized
macOS/Chrome Douyin download succeeded; see the bounded trial observations in
[video-acquisition.md](video-acquisition.md#quality-and-operational-lessons).
Other platform paths remain unverified live. Upstream support varies by version,
region, login, format and platform changes.

## Implemented path

[yt-dlp](https://github.com/yt-dlp/yt-dlp) owns extraction; Reel owns input
deduplication, bounded invocation, statuses, local-file verification and
sanitized provenance. Domain routing covers YouTube, Bilibili, Instagram,
Douyin and Xiaohongshu. This is an attempted extractor path, not a guarantee
of successful download or a promise of highest quality/no watermark.
Consult the installed version's help and upstream
[supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)
when diagnosing a concrete link. Never forward a private link to a demo service.
For commit-pinned extractor behavior and current alternative-project status,
load [video-download-reliability-research.md](video-download-reliability-research.md).
Douyin's fresh-cookie hint is not definitive login failure; Bilibili format
availability is session-dependent, not a promise of 4K.

## Advisory alternatives, not installed adapters

| Platform | Candidate | Boundary |
|---|---|---|
| Douyin | [F2](https://github.com/Johnserf-Seed/f2) | Inspect installed CLI help for single-work scope; local credential configuration only |
| Douyin | [Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API) | Separate self-hosted service; no adapter or public-service fallback is bundled |
| Xiaohongshu | [XHS-Downloader](https://github.com/JoeanAmier/XHS-Downloader) | Verify the actual installed API and saved file; historical database records are not file receipts |
| Instagram | [Instaloader](https://github.com/instaloader/instaloader) | Account/archive/album workflows are separate scope, not an automatic expansion |
| Bilibili | [lux](https://github.com/iawia002/lux) | Explicitly selected CLI alternative; verify current arguments and authorization |

The supplied study described lux as MIT, F2 and the Douyin API as Apache-2.0,
XHS-Downloader as GPL-3.0 and Instaloader as MIT. Recheck exact versions and
licenses before integration/distribution; no third-party extractor code from
these projects is included here. The archive's API examples, star counts and
browser-cookie support claims are not maintained runtime contracts.
BBDown is archived in the inspected upstream snapshot; do not add it as an
automatically maintained Bilibili fallback. F2's auto-cookie path persists
credentials to configuration, so it is not a drop-in replacement for Reel's
explicit browser-state boundary.
Any future adapter needs a separate scoped implementation, permission review,
the same provenance boundary and local ffprobe validation, not success inferred
from HTTP 200 or `download: true`.

## WeChat Channels: honest manual boundary

Recognized WeChat domains return `needs_wechat_capture` without network access
or a downloader dependency. A share card without an HTTP(S) URL yields
`no_links`; request a link or authorized local export instead of pretending to
resolve the card. Broad `weixin.qq.com` recognition is only a conservative
handoff hint; it does not prove a page is a Channels video.

The supplied research names
[wx_channels_download](https://github.com/ltaoo/wx_channels_download) as a
macOS/Windows client-assisted proxy/certificate capture tool, not a general URL
API. It reports MIT + Commons Clause licensing, including commercial limits.
This integration neither installs nor invokes it. Prefer a user-provided,
authorized local recording/export. If the user explicitly requests a separate
capture setup, inspect the tool/version and explain system trust, proxy and
administrator implications first; those changes require their own approvals
and host UI permissions. Never bypass access controls or auto-enable capture.

The archive also names the archived
[WeChatVideoDownloader](https://github.com/lecepin/WeChatVideoDownloader) with
unverified licensing, and
[res-downloader](https://github.com/putyy/res-downloader) as an unverified lead.
Neither is a supported fallback or bundled dependency.
