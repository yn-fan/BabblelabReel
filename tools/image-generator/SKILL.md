---
name: babblelabreel-image
description: Generate and save raster images through a visible external Chrome browser using Microsoft 365 Copilot or MAI Playground, or through the Azure OpenAI image API. Use whenever the user asks BabblelabReel to generate, create, render, or edit an image, illustration, visual, icon, background, or bitmap asset. Supports browser sign-in, provider selection, Azure discovery and provisioning, and project-safe output handling.
---

Resolve the bundle root two directories above this file. Read its `AGENTS.md` and shared artifact routing; run relative commands from that root. This is a bundled BabblelabReel child, not a dependency on the original Emma plugin.


# Image Generator

Generate an image through one of three user-authorized providers and save the
result under the resolved `USER_HOME/outputs/image-generator/` directory.

## Provider selection

Honor an explicit provider. Otherwise default to **Microsoft 365 Copilot** and
state that choice before opening Chrome. The user can explicitly request either
alternative:

1. **Microsoft 365 Copilot (default)** — visible Chrome; best when the user
   already has a licensed work or personal Copilot identity.
2. **MAI Playground** — visible Chrome; best for trying preview MAI image
   models without Azure provisioning.
3. **Azure OpenAI API** — best for reproducible CLI generation and automation;
   usage may consume Azure credit or incur charges.

Do not silently switch away from the default after authentication, licensing,
policy, quota, or content-safety failures. Explain the failure and use
`ask_user` to offer MAI Playground or Azure OpenAI.

## Shared preparation

1. Resolve the output root:

   ```bash
   python3 tools/scripts/user_paths.py output image-generator
   ```

2. Choose a new descriptive filename. Do not overwrite an existing image unless
   explicitly requested.
3. Build a production prompt containing subject, composition, style/material,
   exact text requirements, aspect ratio, and concrete exclusions. If the
   installed `gpt-image-2-style-library` is available and the user asks for
   prompt refinement or a named visual style, invoke it before generation.
4. Never put credentials, access tokens, tenant identifiers, or private source
   URLs in the prompt or output metadata.
5. Before sending a reference image to any provider, confirm the user intended
   to upload that file to the selected service.

## Browser providers

Read `references/browser-providers.md`, then use the Chrome DevTools MCP tools.
The browser must be the visible external Chrome window launched by that MCP:

- Do not use the embedded Browser canvas.
- Do not use headless browser automation.
- Do not request or handle the user's password, MFA code, or recovery secret.
- If sign-in is required, pause and ask the user to finish it in the visible
  Chrome window, then continue from a fresh page snapshot.
- Interact from accessibility snapshots and semantic labels. Do not rely on
  stale coordinates or guessed CSS selectors.
- Download the generated image through the product UI, locate the completed
  download, and copy it into the resolved output root with a new filename.
- Report the provider, saved path, and any model name the UI disclosed. Do not
  claim a model identity that the UI did not show.

If Chrome DevTools MCP is unavailable, follow the bundled [browser setup](../../references/browser-setup.md). Report missing tools and obtain scoped host-configuration and installation consent; the full Emma initializer is not required or included.

## Azure OpenAI provider

Read `references/azure-openai.md`. Before changing Azure resources, use a hard
gate that states the selected subscription, resource group, account, region,
model/version, deployment SKU/capacity, and that API usage may consume credit or
incur charges.

Ask the user to sign in to the Azure subscription they personally control. Do
not reuse a work subscription merely because Azure CLI is already signed in.
The sign-in happens through Azure CLI/device login; never ask for credentials in
chat.

Always remind eligible users before provisioning:

> You may be eligible for the Visual Studio subscriber monthly Azure credit
> benefit (commonly up to USD 150): https://my.visualstudio.com/Benefits

Run discovery first:

```bash
python3 tools/image-generator/scripts/azure_image.py discover
```

If an accessible `gpt-image-2` deployment exists, configure and use it. If no
image deployment exists, try to provision one after the hard gate:

```bash
python3 tools/image-generator/scripts/azure_image.py provision \
  --subscription SUBSCRIPTION_ID \
  --resource-group RESOURCE_GROUP \
  --account-name ACCOUNT_NAME \
  --location westus3 \
  --yes
```

Add `--create-resource` only when no suitable Azure OpenAI resource exists and
the user confirmed creation of the named resource. If Azure denies resource or
deployment creation, report the exact missing permission or quota; do not
success-shape the failure.

Generate after discovery/provisioning:

```bash
python3 tools/image-generator/scripts/azure_image.py generate \
  --prompt "PROMPT" \
  --output "descriptive-name.png" \
  --size 1024x1024 \
  --quality low
```

The CLI uses `AZURE_OPENAI_API_KEY` when present; otherwise it obtains an
in-memory Microsoft Entra token from Azure CLI. Never ask the user to paste an
API key into chat.

## Completion

A run is complete only when the image exists in
`USER_HOME/outputs/image-generator/` and is non-empty. Report provider, output
path, size/aspect ratio, and whether a reference image was uploaded.
