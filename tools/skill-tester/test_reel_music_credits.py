"""Dependency-free credit timing/layout tests and renderer wiring contracts."""

import json
from pathlib import Path
import shutil
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "skills/reel/assets/remotion-starter/src/reel"


@unittest.skipUnless(shutil.which("node"), "Node.js is required")
class ReelMusicCreditsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
            ["node", "--input-type=module", "-"],
            input=r"""
import {readFileSync} from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
const source = readFileSync(
  'skills/reel/assets/remotion-starter/src/reel/MusicCredits.tsx', 'utf8',
);
const helpers = source.split('export const MusicCredits =')[0]
  .replace(/^import .*;$/gm, '');
const {MUSIC_CREDITS_RENDERER_VERSION: rendererVersion,
  musicCreditsStartFrame: start, musicCreditsVisible: visible,
  musicCreditsLayout: layout, musicCreditsLineCount: lines} =
  await import('data:text/javascript;base64,' +
    Buffer.from(stripTypeScriptTypes(helpers)).toString('base64'));
const attribution =
  'Quiet morning - Example musician\n' +
  'CC BY 4.0; https://creativecommons.org/licenses/by/4.0/\n' +
  'https://commons.wikimedia.org/wiki/File:' +
  '%E9%9F%B3%E6%A8%82_'.repeat(18) + '.ogg\n' +
  'Edited for this video: excerpt, fades, and volume mix.';
const formats = [[1920, 1080], [1080, 1920], [1280, 720], [720, 1280]];
const layouts = formats.map(([width, height]) => {
  const captions = ['This is the final caption.', 'A second final caption.'];
  const value = layout(attribution, width, height, captions);
  const captionScale = height / 1080;
  const captionTop = height - 62 * captionScale -
    Math.max(...captions.map(text =>
      lines(text, (width - 320 * captionScale) / (36 * captionScale)))) *
      45 * captionScale;
  return {width, height, captionTop, ...value};
});
let oversizedError;
try {
  layout('https://example.org/' + 'x'.repeat(100000), 1920, 1080);
} catch (error) {
  oversizedError = error.message;
}
let crowdedError;
try {
  layout(attribution, 1080, 1920, ['caption '.repeat(500)]);
} catch (error) {
  crowdedError = error.message;
}
console.log(JSON.stringify({
  rendererVersion,
  timing: [24, 30, 60, 29.97].map(fps => {
    const duration = Math.round(20 * fps);
    const from = start(duration, fps);
    return {fps, duration, from, before: visible('credit', from - 1, duration, fps),
      first: visible('credit', from, duration, fps),
      last: visible('credit', duration - 1, duration, fps),
      after: visible('credit', duration, duration, fps)};
  }),
  short: {from: start(90, 30), first: visible('credit', 0, 90, 30),
    last: visible('credit', 89, 90, 30), after: visible('credit', 90, 90, 30)},
  exactFive: start(150, 30),
  absent: [undefined, ''].map(text => [0, 449, 450, 599].map(frame =>
    visible(text, frame, 600, 30))),
  wraps: [lines('a\nb\n\nc', 20), lines('x'.repeat(101), 20),
    lines('aaaa bbbb', 6), lines('a\n', 20)],
  layouts, oversizedError, crowdedError,
}));
""",
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.result = json.loads(result.stdout)

    def test_final_five_seconds_have_exact_frame_boundaries(self):
        for timing in self.result["timing"]:
            with self.subTest(fps=timing["fps"]):
                self.assertEqual(
                    timing["from"],
                    timing["duration"] - round(5 * timing["fps"]),
                )
                self.assertFalse(timing["before"])
                self.assertTrue(timing["first"])
                self.assertTrue(timing["last"])
                self.assertFalse(timing["after"])

    def test_short_clip_shows_credits_without_extending_duration(self):
        self.assertEqual(
            self.result["short"],
            {"from": 0, "first": True, "last": True, "after": False},
        )
        self.assertEqual(self.result["exactFive"], 0)

    def test_absent_or_empty_attribution_never_shows(self):
        self.assertEqual(self.result["absent"], [[False] * 4] * 2)

    def test_wrapping_preserves_newlines_and_budgets_long_urls(self):
        self.assertEqual(self.result["wraps"], [4, 6, 2, 2])

    def test_long_encoded_urls_fit_landscape_portrait_and_caption_clearance(self):
        for layout in self.result["layouts"]:
            with self.subTest(width=layout["width"], height=layout["height"]):
                scale = min(layout["width"], layout["height"]) / 1080
                self.assertGreaterEqual(layout["fontSize"], 20 * scale)
                self.assertLessEqual(layout["fontSize"], 28 * scale)
                self.assertLessEqual(layout["estimatedHeight"], layout["height"] * 0.42)
                self.assertLess(
                    layout["margin"] + layout["estimatedHeight"],
                    layout["captionTop"],
                )

    def test_impossible_layout_fails_instead_of_hiding_legal_text(self):
        for key in ("oversizedError", "crowdedError"):
            self.assertIn("cannot fit legibly", self.result[key])
            self.assertIn("do not truncate", self.result[key])

    def test_actual_jsx_is_wired_to_music_attribution_and_original_timeline(self):
        credits = (SOURCE_ROOT / "MusicCredits.tsx").read_text(encoding="utf-8")
        reel = (SOURCE_ROOT / "Reel.tsx").read_text(encoding="utf-8")
        content = (SOURCE_ROOT / "content.ts").read_text(encoding="utf-8")
        self.assertEqual(self.result["rendererVersion"], 1)
        self.assertIn("attribution?: string;", content)
        self.assertIn("import {MusicCredits} from './MusicCredits';", reel)
        self.assertIn(
            "<MusicCredits durationInFrames={DURATION_IN_FRAMES} />", reel
        )
        self.assertLess(reel.index("<MusicCredits "), reel.index("<CaptionTrack />"))
        self.assertIn("const frame = useCurrentFrame();", credits)
        self.assertIn("reelStory.audio.music?.attribution", credits)
        self.assertIn(
            "!musicCreditsVisible(attribution, frame, durationInFrames, fps)",
            credits,
        )
        self.assertIn("return null;", credits)
        self.assertIn("{attribution}", credits)
        self.assertIn("whiteSpace: 'pre-wrap'", credits)
        self.assertIn("overflowWrap: 'anywhere'", credits)
        self.assertIn("backgroundColor: '#000'", credits)
        self.assertIn("color: '#fff'", credits)
        for forbidden in (
            "textOverflow", "lineClamp", "overflow: 'hidden'", ".slice(",
            ".substring(", "decodeURI", "Sequence", "interpolate",
        ):
            self.assertNotIn(forbidden, credits)
        self.assertIn(
            "seconds(shot.startSeconds + shot.durationSeconds),", reel
        )


if __name__ == "__main__":
    unittest.main()
