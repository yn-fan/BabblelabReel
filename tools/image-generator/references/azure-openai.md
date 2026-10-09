# Azure OpenAI image generation

## Authentication and ownership

Use an Azure subscription the user personally controls for this workflow. Check:

```bash
az account show
```

If it is not the intended personal subscription, ask the user to sign in:

```bash
az login
```

The user completes browser/device authentication directly. Then select the
intended subscription with `az account set --subscription SUBSCRIPTION_ID`.
Never ask for credentials or copy an access token into chat.

Before provisioning, remind the user that eligible Visual Studio subscribers
may activate monthly Azure credit, commonly up to USD 150, at:

`https://my.visualstudio.com/Benefits`

Benefit eligibility and amount are determined by the user's subscription; do
not promise the credit.

## Discovery

`azure_image.py discover` inventories enabled subscriptions, Azure OpenAI or AI
Services resources, and deployments. Prefer an existing successful
`gpt-image-2` deployment.

If no deployment exists, select a resource in a region where Azure reports
`gpt-image-2` availability. Current defaults are:

- model: `gpt-image-2`
- model version: `2026-04-21`
- deployment SKU: `GlobalStandard`
- capacity: `1`
- preferred region for a new resource: `westus3`

These defaults can become stale. Before provisioning, inspect current regional
availability:

```bash
az cognitiveservices model list \
  --subscription SUBSCRIPTION_ID \
  --location REGION \
  --query "[?model.name=='gpt-image-2']"
```

## Provisioning permissions

Deployment creation requires
`Microsoft.CognitiveServices/accounts/deployments/write`. Creating a new
resource also requires resource-group and Cognitive Services account write
permissions. Quota or offer restrictions can still block a permitted request.

Provisioning is an explicit, potentially billable cloud mutation. Present the
hard gate from the parent tool before passing `--yes`.

## Runtime configuration

The CLI accepts flags or these environment variables:

```text
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_DEPLOYMENT
AZURE_OPENAI_API_KEY
AZURE_SUBSCRIPTION_ID
```

Prefer Entra authentication through Azure CLI. Use an API key only when the
user already configured `AZURE_OPENAI_API_KEY` outside chat.

Generation uses the Azure OpenAI v1 image endpoint:

```text
POST {endpoint}/openai/v1/images/generations
```

The request body passes the deployment name as `model`. Successful image data
is decoded from `data[0].b64_json`.

