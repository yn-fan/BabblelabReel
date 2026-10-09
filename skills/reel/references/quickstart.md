# Reel quick start

Reel handles video links, material and production in one workflow. Share an
authorized video link, attach local material, or describe the film you want;
BabblelabReel chooses the appropriate steps. You do not need to pick Remotion versus
FFmpeg, write JSON, or install the four upstream skills separately.

Installing BabblelabReel makes the skill available. Downloading and rendering still need
their selected workflow's tools; BabblelabReel checks them and asks before
installing missing dependencies.

## Start in your BabblelabReel-enabled host

1. After installing or updating BabblelabReel, start a new conversation so the current
   plugin can load. Use a workspace where your source files are accessible.
2. Paste a supported video link/share text, or attach your script, screenshots,
   local footage or project. A local folder path also works when accessible.
3. Say whether to download, inspect metadata, edit, or render an MP4. If you
   provide only a video link, BabblelabReel asks what you want before acting. Download-only
   requests do not start movie production or ask about music.

**A first video with minimal dependencies**

> Use Reel to create a 15-second product teaser from these screenshots. No audio. Render an MP4.

No audio avoids optional music/speech providers; it does not remove the local
rendering requirements. Use supplied screenshots for the actual product, not
invented UI. If BabblelabReel is not available in the host, follow the repository's
[installation guide](../../../README.md#install); do not paste shell commands
into an unrelated chat and expect the plugin to appear.

## Copy a prompt

| Goal | Example |
|---|---|
| Download your video | `Download my video from this link at the highest available quality.` |
| Metadata only | `Check this video's available resolution without downloading it.` |
| Smaller video | `Compress this video for sharing. Keep the original, resolution and sound.` |
| Upload-size limit | `Compress this video to at most 20 MB. Keep the full duration and audio.` |
| Download and edit | `I have permission to use these videos. Download them, make a 30-second montage, and render an MP4.` |
| Product demo | `Use Reel to make a 30-second demo from this script and UI. Render an MP4.` |
| Footage montage | `Use Reel to cut these clips into a 20-second montage with matching music. Render it.` |
| Vlog with supplied music | `Edit these clips to this music. Keep the dialogue intact and export an MP4.` |
| Narrated explainer | `Turn this script into a narrated video with captions. Keep every sentence and render it.` |
| Improve an existing project | `Improve the pacing in this Reel project. Preserve its story and audio, then render it.` |
| Add a soundtrack | `Add calm, uplifting music to this Reel and render it.` |
| Preview before finishing | `Show me the storyboard before rendering the full video.` |
| Editable native draft | `Prepare an editable Jianying draft from these clips. Check compatibility first.` |
| Help only | `What can Reel do, and what should I provide?` |

You can give instructions in your own language. These English prompts are
short examples, not required syntax. Product context, length, aspect ratio and
music direction can all be described naturally. You do not need to say "AI BGM."

## Video links: download first, edit only when requested

Reel accepts specified **Douyin, Xiaohongshu, Bilibili, YouTube and Instagram**
links/share text through its extractor path. Platform changes, access controls,
region and the selected login state can prevent acquisition; this is not a
guarantee that every link works. WeChat Channels requires a separate
client-assisted route and is not an automatic URL download.

For a bare link, BabblelabReel offers download, metadata only, or no action. An explicit
download request does not need the same intent question again. Download only
your own, authorized, or license-permitted media. Public access alone does not
grant reuse rights; making a new film needs permission for that use too.

BabblelabReel prefers the highest native resolution available to the current extractor/
session and reports the saved file's measured dimensions. Ask for **required 4K**
if lower resolution is unacceptable: unavailable 4K remains a blocker, not an
upscaled or quietly downgraded delivery.

If login is needed, BabblelabReel requests access to the specific browser/profile or
cookie file; download permission does not authorize reading all browser accounts.
It does not bypass verification, DRM or paywalls. Missing tools need installation
consent; existing approved environments are reused.

After a verified download, BabblelabReel normally reveals the saved file/folder and
provides its path. Remote/headless hosts may provide only the path/link. Say
"do not open the folder" to opt out. A successful download is not automatically
a request to edit, add music, or publish it.

## Compress an existing video

Give BabblelabReel the local file and say "make it smaller" or specify a size limit such
as 20 MB. It uses local FFmpeg, leaves the original untouched, and produces a
separate MP4 only after checking real size savings and any requested limit.
MB means 1,000,000 bytes. A plain compression request does not add music,
change the story, upload the video or scaffold a new film project.

Compression is lossy; a smaller file is not proof of unchanged visual quality.
The default keeps resolution and timing. Downscaling requires your request,
for example "at most 720 pixels high." BabblelabReel reports unsupported media or an
unachievable limit instead of silently cutting the ending, dropping tracks or
reducing resolution. Keep the original and all required source/music credits.

The first version targets progressive 8-bit SDR, constant-frame-rate videos
with supported audio, up to 4 GiB/one hour. HDR, variable-frame-rate phone
recordings, rotation metadata and embedded subtitle tracks need a separate
conversion decision, not silent conversion. For a download-and-compress request, link permissions
and a verified downloaded file come first. Installing BabblelabReel does not bundle
FFmpeg binaries; missing local tools require installation consent.

## What to provide

Usually **the source material and desired outcome** are enough to start.
Add a deadline/duration, audience, brand reference, or aspect ratio when it
matters. BabblelabReel infers safe defaults and asks only for missing information that
would change the result.

For a truthful product demo, provide screenshots, recordings, a working
prototype, or a source-backed description of the flow. For a montage, provide
local clips or authorized video links and identify speech or moments that must stay. For an existing
Reel, provide the editable project folder, not only its final movie. Music you
supply must have suitable usage rights; internal company use is not automatically
license-exempt.

If you have only an idea, ask for a script/storyboard first. Missing product
evidence will not be replaced by invented functionality.

## What happens next

BabblelabReel briefly tells you what it will make, any missing input/dependency, and the
next result or preview. A download request follows the link workflow above.
For a film, it then locks the story, selects material, checks the relevant tools,
builds the timeline, and reviews the output.

- **Music:** BabblelabReel recommends a direction and asks for approval, then tries
  hosted AI and automatically uses suitable licensed library music if AI fails.
  It does not ask again merely to switch music sources. You hear a preview
  before final acceptance; required credits stay visible.
- **Narration:** the script comes before synthesis. Required words are preserved;
  pronunciation, timing and caption coverage need review.
- **Feedback:** describe changes such as "slower cuts," "less energetic music,"
  or "keep this sentence." BabblelabReel revises the existing project instead of starting
  an unrelated one.
- **Delivery:** a requested MP4 is delivered with its editable project and
  relevant sources/credits. A Jianying draft is clearly labeled as a draft, not
  an exported video. A help-only request creates nothing.

To delegate music direction **and** listening approval:

> Choose the music and finalize it without asking me.

That delegates creative choices; it does not authorize paid services, private
data uploads, dependency installation, or ignoring licenses.

## First-run requirements and honest limits

You do not need everything in this table. BabblelabReel checks only the chosen workflow.

| Workflow | Local requirements | What installing BabblelabReel does not guarantee |
|---|---|---|
| Specified-link download | Python helper, an approved working yt-dlp runtime, FFmpeg and ffprobe; metadata-only needs no media encoders | Platform/login compatibility or 4K availability; one authorized Douyin/Chrome download was verified, not every platform/account |
| Product films and animated graphics | Python, Node.js, the project's package manager, Remotion dependencies and a supported browser | Project dependencies/browser availability, fonts or the organization's Remotion license entitlement |
| Local footage editing | Python 3.9+, FFmpeg and ffprobe | A particular FFmpeg build's filters/encoders; subtitle and credit burn-in needs libass |
| Local video compression | Python 3.9+, FFmpeg with libx264/AAC, and ffprobe | Guaranteed savings at unchanged visual quality, arbitrary tiny limits, or support for all source tracks/color formats |
| Native Jianying handoff | Media tools plus the optional compatible `pyJianYingDraft` API and target editor | Experimental compatibility; current Mac opening/export is not verified, native export is manual |
| Generated narration or transcription | The selected approved speech/transcription capability | A bundled voice model, Whisper installation, or automatic model downloads |
| Automatic music | The selected provider or library must be reachable | Free cloud GPU quota or successful AI generation; library recordings are labeled accurately |

Source materials stay local unless you explicitly authorize a service that
needs them. Automatic music sends abstract musical direction, not your product
script or screenshots.

If a check fails, BabblelabReel identifies the smallest blocker and asks for any required
installation/provider consent. It continues independent script or storyboard
work where possible. It does not remove captions, credits, required music or
speech simply to make a render succeed.

For developers or support, the read-only diagnostic is:

```bash
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/preflight_reel.py" --engine remotion
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/preflight_reel.py" --engine remotion --project "PROJECT_DIR"
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/preflight_reel.py" --engine ffmpeg --captions --credits --music
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/preflight_reel.py" --engine jianying
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/preflight_reel.py" --engine download
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/preflight_reel.py" --engine download --metadata-only
python "{BABBLELABREEL_ROOT}/skills/reel/scripts/preflight_reel.py" --engine compress
```

BabblelabReel runs the matching check for you. A ready result means only the listed local
prerequisites passed; it is not proof of successful rendering, music generation,
or native editor compatibility.
