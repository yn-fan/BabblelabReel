# Browser image providers

Use only the visible external stable Chrome window launched by Chrome DevTools
MCP. Its default is `headless=false` and its persistent profile preserves user
sign-in between sessions. Never substitute BabblelabReel's embedded Browser canvas.

## Common browser sequence

1. Call the Chrome DevTools page-list action. Reuse the provider tab if one
   already exists; otherwise open a new page.
2. Navigate to the provider URL and take an accessibility snapshot.
3. If the page requests authentication, ask the user to complete sign-in in the
   visible browser. Do not inspect password or MFA fields.
4. After the user confirms, take a new snapshot. Select controls by accessible
   name and current snapshot identity.
5. Submit the prepared prompt once. Generation can be billable or rate-limited,
   so do not retry automatically after a completed submission.
6. Wait for the product's completion state, take a fresh snapshot, and activate
   its Download or Save control.
7. Wait for the browser download to finish. Identify the newest matching image
   in the user's Downloads directory created after the download action. Reject
   partial files such as `.crdownload`.
8. Copy the file to the resolved image-generator output directory. Preserve its
   actual format and use a unique descriptive filename.

If labels or layout differ, use the live accessibility snapshot to adapt. Never
use coordinate clicking when a semantic control is available.

## Microsoft 365 Copilot

Start at:

`https://copilot.cloud.microsoft/`

If that unified endpoint is unavailable for the signed-in tenant, use:

`https://m365.cloud.microsoft/create`

From the current UI, select **Create**, then **Create an image** or the equivalent
image card. Enter the prompt, select the requested style and shape when those
controls are present, and activate **Create**. Generated images may also remain
in the user's Copilot Library.

Treat licensing, tenant policy, and content-policy notices as terminal for that
attempt. Do not try to bypass tenant controls.

## MAI Playground

Start at:

`https://playground.microsoft.ai/chat`

MAI Playground is a limited preview. Select an image-capable MAI model or image
mode shown by the current UI, enter the prompt, and generate. Prefer
`MAI-Image-2` only when that exact model is available; otherwise report the
actual model shown and let the user choose whether to continue.

Do not claim service stability or production support. Treat preview limits,
waitlists, geography restrictions, and content-policy notices as terminal for
that attempt.

