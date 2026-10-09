#!/usr/bin/env python3
"""Discover, provision, and call Azure OpenAI image deployments."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_SCRIPTS = REPO_ROOT / "tools" / "scripts"
if str(TOOLS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(TOOLS_SCRIPTS))

from user_paths import output_dir  # noqa: E402


DEFAULT_MODEL = "gpt-image-2"
DEFAULT_MODEL_VERSION = "2026-04-21"
DEFAULT_DEPLOYMENT = "gpt-image-2"
DEFAULT_LOCATION = "westus3"
DEFAULT_SKU = "GlobalStandard"
DEFAULT_CAPACITY = 1
VALID_FORMATS = {"png", "jpeg", "webp"}
VALID_QUALITIES = {"low", "medium", "high", "auto"}


class AzureImageError(RuntimeError):
    """Expected command, Azure, or image API failure."""


def emit(payload: Dict[str, Any], exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


def fail(message: str, **details: Any) -> int:
    return emit({"success": False, "error": message, **details}, 1)


def _az_command(args: Sequence[str]) -> List[str]:
    if os.name != "nt":
        return ["az", *args]
    command_line = subprocess.list2cmdline(["az", *args])
    return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command_line]


def run_az(args: Sequence[str], *, parse_json: bool = True) -> Any:
    command = _az_command([*args, "--only-show-errors"])
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError as error:
        raise AzureImageError("Azure CLI is not installed or is not on PATH.") from error

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise AzureImageError(detail or f"Azure CLI exited with code {completed.returncode}.")
    if not parse_json:
        return completed.stdout.strip()
    try:
        return json.loads(completed.stdout or "null")
    except json.JSONDecodeError as error:
        raise AzureImageError("Azure CLI returned invalid JSON.") from error


def discover(subscription: Optional[str] = None) -> Dict[str, Any]:
    if subscription:
        subscriptions = [
            run_az(["account", "show", "--subscription", subscription, "-o", "json"])
        ]
    else:
        raw = run_az(["account", "list", "-o", "json"])
        subscriptions = [
            item for item in (raw or []) if item.get("state") == "Enabled"
        ]

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for sub in subscriptions:
        sub_id = str(sub.get("id", ""))
        if not sub_id:
            continue
        try:
            accounts = run_az(
                [
                    "cognitiveservices",
                    "account",
                    "list",
                    "--subscription",
                    sub_id,
                    "-o",
                    "json",
                ]
            )
        except AzureImageError as error:
            errors.append({"subscriptionId": sub_id, "error": str(error)})
            continue

        normalized_accounts: List[Dict[str, Any]] = []
        for account in accounts or []:
            if account.get("kind") not in {"OpenAI", "AIServices"}:
                continue
            name = account.get("name")
            group = account.get("resourceGroup")
            if not name or not group:
                continue
            try:
                deployments = run_az(
                    [
                        "cognitiveservices",
                        "account",
                        "deployment",
                        "list",
                        "--subscription",
                        sub_id,
                        "--resource-group",
                        group,
                        "--name",
                        name,
                        "-o",
                        "json",
                    ]
                )
            except AzureImageError as error:
                errors.append(
                    {
                        "subscriptionId": sub_id,
                        "account": str(name),
                        "error": str(error),
                    }
                )
                deployments = []

            normalized_deployments = []
            for deployment in deployments or []:
                properties = deployment.get("properties") or {}
                model = properties.get("model") or {}
                model_name = str(model.get("name", ""))
                if "image" not in model_name.lower() and "dall" not in model_name.lower():
                    continue
                normalized_deployments.append(
                    {
                        "name": deployment.get("name"),
                        "model": model_name,
                        "version": model.get("version"),
                        "state": properties.get("provisioningState"),
                        "sku": (deployment.get("sku") or {}).get("name"),
                        "capacity": (deployment.get("sku") or {}).get("capacity"),
                    }
                )

            normalized_accounts.append(
                {
                    "name": name,
                    "resourceGroup": group,
                    "kind": account.get("kind"),
                    "location": account.get("location"),
                    "endpoint": (account.get("properties") or {}).get("endpoint"),
                    "imageDeployments": normalized_deployments,
                }
            )

        results.append(
            {
                "subscriptionId": sub_id,
                "subscriptionName": sub.get("name"),
                "isDefault": bool(sub.get("isDefault")),
                "accounts": normalized_accounts,
            }
        )

    return {
        "success": True,
        "subscriptions": results,
        "errors": errors,
        "imageDeploymentCount": sum(
            len(account["imageDeployments"])
            for sub in results
            for account in sub["accounts"]
        ),
    }


def get_resource(
    subscription: str, resource_group: str, account_name: str
) -> Optional[Dict[str, Any]]:
    try:
        return run_az(
            [
                "cognitiveservices",
                "account",
                "show",
                "--subscription",
                subscription,
                "--resource-group",
                resource_group,
                "--name",
                account_name,
                "-o",
                "json",
            ]
        )
    except AzureImageError as error:
        message = str(error).lower()
        if "resourcenotfound" in message or "could not be found" in message:
            return None
        raise


def ensure_model_available(
    subscription: str, location: str, model_name: str, model_version: str, sku: str
) -> None:
    models = run_az(
        [
            "cognitiveservices",
            "model",
            "list",
            "--subscription",
            subscription,
            "--location",
            location,
            "-o",
            "json",
        ]
    )
    for entry in models or []:
        model = entry.get("model") or {}
        skus = {item.get("name") for item in (model.get("skus") or [])}
        if (
            model.get("name") == model_name
            and model.get("version") == model_version
            and sku in skus
        ):
            return
    raise AzureImageError(
        f"{model_name} version {model_version} with SKU {sku} is not available "
        f"in {location} for this subscription."
    )


def provision(args: argparse.Namespace) -> Dict[str, Any]:
    if not args.yes:
        raise AzureImageError(
            "Provisioning requires --yes after the user confirms the subscription, "
            "resource, region, model, SKU, capacity, and possible Azure charges."
        )

    account = get_resource(
        args.subscription, args.resource_group, args.account_name
    )
    created_resource = False
    location = str(account.get("location")) if account else args.location
    ensure_model_available(
        args.subscription,
        location,
        args.model_name,
        args.model_version,
        args.sku,
    )
    if account is None:
        if not args.create_resource:
            raise AzureImageError(
                "The Azure OpenAI resource does not exist. Re-run with "
                "--create-resource only after the user confirms resource creation."
            )
        run_az(
            [
                "group",
                "create",
                "--subscription",
                args.subscription,
                "--name",
                args.resource_group,
                "--location",
                args.location,
                "-o",
                "json",
            ]
        )
        run_az(
            [
                "cognitiveservices",
                "account",
                "create",
                "--subscription",
                args.subscription,
                "--resource-group",
                args.resource_group,
                "--name",
                args.account_name,
                "--location",
                args.location,
                "--kind",
                "OpenAI",
                "--sku",
                "S0",
                "--custom-domain",
                args.account_name,
                "-o",
                "json",
            ]
        )
        created_resource = True
        account = get_resource(
            args.subscription, args.resource_group, args.account_name
        )
        if account is None:
            raise AzureImageError("Azure reported success but the new resource is unavailable.")

    existing = run_az(
        [
            "cognitiveservices",
            "account",
            "deployment",
            "list",
            "--subscription",
            args.subscription,
            "--resource-group",
            args.resource_group,
            "--name",
            args.account_name,
            "-o",
            "json",
        ]
    )
    for deployment in existing or []:
        if deployment.get("name") != args.deployment_name:
            continue
        properties = deployment.get("properties") or {}
        model = properties.get("model") or {}
        if (
            model.get("name") == args.model_name
            and properties.get("provisioningState") == "Succeeded"
        ):
            return {
                "success": True,
                "createdResource": created_resource,
                "createdDeployment": False,
                "deployment": args.deployment_name,
                "model": args.model_name,
                "state": properties.get("provisioningState"),
                "endpoint": (account.get("properties") or {}).get("endpoint"),
                "subscriptionId": args.subscription,
            }
        raise AzureImageError(
            f"Deployment name {args.deployment_name!r} already exists with a "
            "different model or incomplete state."
        )

    deployment = run_az(
        [
            "cognitiveservices",
            "account",
            "deployment",
            "create",
            "--subscription",
            args.subscription,
            "--resource-group",
            args.resource_group,
            "--name",
            args.account_name,
            "--deployment-name",
            args.deployment_name,
            "--model-name",
            args.model_name,
            "--model-version",
            args.model_version,
            "--model-format",
            "OpenAI",
            "--sku-name",
            args.sku,
            "--sku-capacity",
            str(args.capacity),
            "-o",
            "json",
        ]
    )
    properties = deployment.get("properties") or {}
    return {
        "success": True,
        "createdResource": created_resource,
        "createdDeployment": True,
        "deployment": deployment.get("name"),
        "model": (properties.get("model") or {}).get("name"),
        "modelVersion": (properties.get("model") or {}).get("version"),
        "state": properties.get("provisioningState"),
        "sku": (deployment.get("sku") or {}).get("name"),
        "capacity": (deployment.get("sku") or {}).get("capacity"),
        "endpoint": (account.get("properties") or {}).get("endpoint"),
        "subscriptionId": args.subscription,
    }


def _validate_endpoint(endpoint: str) -> str:
    normalized = endpoint.strip().rstrip("/")
    if not normalized.startswith("https://"):
        raise AzureImageError("Azure OpenAI endpoint must use HTTPS.")
    return normalized


def _output_format(name: str) -> str:
    suffix = Path(name).suffix.lower().lstrip(".")
    if suffix == "jpg":
        suffix = "jpeg"
    if suffix not in VALID_FORMATS:
        raise AzureImageError("Output extension must be .png, .jpg, .jpeg, or .webp.")
    return suffix


def resolve_output_path(value: Optional[str]) -> Path:
    root = output_dir(REPO_ROOT, "image-generator").resolve()
    root.mkdir(parents=True, exist_ok=True)
    if value:
        candidate = Path(value).expanduser()
        resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    else:
        resolved = root / f"generated-{time.strftime('%Y%m%d-%H%M%S')}.png"
    if not resolved.is_relative_to(root):
        raise AzureImageError(f"Output must stay under {root}.")
    return resolved


def get_access_token(subscription: Optional[str]) -> str:
    args = [
        "account",
        "get-access-token",
        "--resource",
        "https://cognitiveservices.azure.com",
        "--query",
        "accessToken",
        "-o",
        "tsv",
    ]
    if subscription:
        args.extend(["--subscription", subscription])
    token = run_az(args, parse_json=False).strip()
    if not token:
        raise AzureImageError("Azure CLI returned an empty access token.")
    return token


def build_generation_request(
    *,
    endpoint: str,
    deployment: str,
    prompt: str,
    size: str,
    quality: str,
    output_format: str,
    api_key: Optional[str],
    access_token: Optional[str],
) -> urllib.request.Request:
    if quality not in VALID_QUALITIES:
        raise AzureImageError(
            f"Quality must be one of: {', '.join(sorted(VALID_QUALITIES))}."
        )
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    elif access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    else:
        raise AzureImageError("Azure OpenAI authentication is missing.")
    body = {
        "model": deployment,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": quality,
        "output_format": output_format,
    }
    return urllib.request.Request(
        f"{_validate_endpoint(endpoint)}/openai/v1/images/generations",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )


def _request_json(request: urllib.request.Request) -> Dict[str, Any]:
    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
                message = (payload.get("error") or {}).get("message") or raw
            except json.JSONDecodeError:
                message = raw or str(error)
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise AzureImageError(f"Azure image API HTTP {error.code}: {message}") from error
            retry_after = error.headers.get("Retry-After")
            time.sleep(float(retry_after) if retry_after else 2 ** attempt)
            last_error = error
        except urllib.error.URLError as error:
            if attempt == 2:
                raise AzureImageError(f"Azure image API network error: {error.reason}") from error
            time.sleep(2 ** attempt)
            last_error = error
    raise AzureImageError(f"Azure image API request failed: {last_error}")


def generate(args: argparse.Namespace) -> Dict[str, Any]:
    endpoint = args.endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
    deployment = args.deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    subscription = args.subscription or os.environ.get("AZURE_SUBSCRIPTION_ID")
    if not endpoint:
        raise AzureImageError(
            "Set AZURE_OPENAI_ENDPOINT or pass --endpoint after discovery/provisioning."
        )
    if not deployment:
        raise AzureImageError(
            "Set AZURE_OPENAI_DEPLOYMENT or pass --deployment after discovery/provisioning."
        )
    output = resolve_output_path(args.output)
    output_format = _output_format(output.name)
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    auth_mode = "api-key" if api_key else "entra-id"
    url = f"{_validate_endpoint(endpoint)}/openai/v1/images/generations"

    if args.dry_run:
        return {
            "success": True,
            "dryRun": True,
            "provider": "azure-openai",
            "authMode": auth_mode,
            "endpoint": url,
            "deployment": deployment,
            "output": str(output),
            "params": {
                "prompt": args.prompt,
                "n": 1,
                "size": args.size,
                "quality": args.quality,
                "output_format": output_format,
            },
        }

    access_token = None if api_key else get_access_token(subscription)
    request = build_generation_request(
        endpoint=endpoint,
        deployment=deployment,
        prompt=args.prompt,
        size=args.size,
        quality=args.quality,
        output_format=output_format,
        api_key=api_key,
        access_token=access_token,
    )
    payload = _request_json(request)
    data = payload.get("data") or []
    encoded = data[0].get("b64_json") if data else None
    if not encoded:
        raise AzureImageError("Azure image API returned no base64 image data.")
    try:
        image = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as error:
        raise AzureImageError("Azure image API returned invalid base64 image data.") from error
    if not image:
        raise AzureImageError("Azure image API returned an empty image.")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image)
    return {
        "success": True,
        "provider": "azure-openai",
        "authMode": auth_mode,
        "deployment": deployment,
        "output": str(output),
        "size": args.size,
        "quality": args.quality,
        "format": output_format,
        "bytes": len(image),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover, provision, and use Azure OpenAI image deployments."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser(
        "discover", help="List Azure OpenAI resources and image deployments."
    )
    discover_parser.add_argument("--subscription")

    provision_parser = subparsers.add_parser(
        "provision", help="Create a GPT image deployment after explicit confirmation."
    )
    provision_parser.add_argument("--subscription", required=True)
    provision_parser.add_argument("--resource-group", required=True)
    provision_parser.add_argument("--account-name", required=True)
    provision_parser.add_argument("--location", default=DEFAULT_LOCATION)
    provision_parser.add_argument("--deployment-name", default=DEFAULT_DEPLOYMENT)
    provision_parser.add_argument("--model-name", default=DEFAULT_MODEL)
    provision_parser.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    provision_parser.add_argument("--sku", default=DEFAULT_SKU)
    provision_parser.add_argument("--capacity", type=int, default=DEFAULT_CAPACITY)
    provision_parser.add_argument("--create-resource", action="store_true")
    provision_parser.add_argument("--yes", action="store_true")

    generate_parser = subparsers.add_parser(
        "generate", help="Generate one image through the Azure OpenAI v1 API."
    )
    generate_parser.add_argument("--prompt", required=True)
    generate_parser.add_argument("--output")
    generate_parser.add_argument("--endpoint")
    generate_parser.add_argument("--deployment")
    generate_parser.add_argument("--subscription")
    generate_parser.add_argument("--size", default="1024x1024")
    generate_parser.add_argument(
        "--quality", choices=sorted(VALID_QUALITIES), default="low"
    )
    generate_parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "discover":
            return emit(discover(args.subscription))
        if args.command == "provision":
            if args.capacity < 1:
                raise AzureImageError("Deployment capacity must be at least 1.")
            return emit(provision(args))
        if args.command == "generate":
            return emit(generate(args))
        raise AzureImageError(f"Unknown command: {args.command}")
    except AzureImageError as error:
        return fail(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
