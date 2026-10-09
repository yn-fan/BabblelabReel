# Browser capability setup

The image browser workflows require a visible external Chrome session exposed
through the host's Chrome DevTools MCP. Use already configured host tools first.
BabblelabReel does not bundle Chrome, an MCP binary or an authenticated profile.

If unavailable, report that precise blocker. With the user's explicit setup
permission, follow the current host's MCP configuration UI or documented
`copilot mcp add --help` procedure and the official
[Chrome DevTools MCP installation instructions](https://github.com/ChromeDevTools/chrome-devtools-mcp).
Confirm the package/version, launch command and profile destination before
writing host configuration; package acquisition requires installation consent.
Use a visible stable Chrome window and preserve user sign-in/MFA boundaries.
Restart the host if needed and inspect the exposed tools before claiming ready.

Do not invoke Emma's initializer, assume another plugin is installed, use an
embedded/headless browser as a silent substitute, or inherit private browser
access merely from a request to generate an image. Provider, cost and upload
gates in `tools/image-generator/SKILL.md` remain binding.
