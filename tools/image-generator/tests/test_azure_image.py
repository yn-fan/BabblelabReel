from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "azure_image.py"
SPEC = importlib.util.spec_from_file_location("azure_image", SCRIPT)
assert SPEC and SPEC.loader
azure_image = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = azure_image
SPEC.loader.exec_module(azure_image)


class AzureImageTests(unittest.TestCase):
    def test_generation_request_uses_v1_endpoint_and_deployment(self) -> None:
        request = azure_image.build_generation_request(
            endpoint="https://example.openai.azure.com/",
            deployment="my-image-deployment",
            prompt="A blue circle",
            size="1024x1024",
            quality="low",
            output_format="png",
            api_key=None,
            access_token="test-token",
        )

        self.assertEqual(
            request.full_url,
            "https://example.openai.azure.com/openai/v1/images/generations",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "my-image-deployment")
        self.assertEqual(body["output_format"], "png")

    def test_api_key_auth_uses_azure_header(self) -> None:
        request = azure_image.build_generation_request(
            endpoint="https://example.openai.azure.com",
            deployment="gpt-image-2",
            prompt="A blue circle",
            size="1024x1024",
            quality="medium",
            output_format="webp",
            api_key="test-key",
            access_token=None,
        )

        self.assertEqual(request.get_header("Api-key"), "test-key")
        self.assertIsNone(request.get_header("Authorization"))

    def test_output_path_stays_in_canonical_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.object(azure_image, "output_dir", return_value=root):
                output = azure_image.resolve_output_path("concepts/hero.png")
                self.assertEqual(output, (root / "concepts" / "hero.png").resolve())
                with self.assertRaises(azure_image.AzureImageError):
                    azure_image.resolve_output_path("../outside.png")

    def test_provision_requires_confirmation(self) -> None:
        parser = azure_image.build_parser()
        args = parser.parse_args(
            [
                "provision",
                "--subscription",
                "sub",
                "--resource-group",
                "group",
                "--account-name",
                "account",
            ]
        )

        with self.assertRaisesRegex(azure_image.AzureImageError, "--yes"):
            azure_image.provision(args)

    def test_resource_permission_error_is_not_treated_as_missing(self) -> None:
        with mock.patch.object(
            azure_image,
            "run_az",
            side_effect=azure_image.AzureImageError("AuthorizationFailed"),
        ):
            with self.assertRaisesRegex(
                azure_image.AzureImageError, "AuthorizationFailed"
            ):
                azure_image.get_resource("sub", "group", "account")

    def test_model_availability_checks_version_and_sku(self) -> None:
        models = [
            {
                "model": {
                    "name": "gpt-image-2",
                    "version": "2026-04-21",
                    "skus": [{"name": "GlobalStandard"}],
                }
            }
        ]
        with mock.patch.object(azure_image, "run_az", return_value=models):
            azure_image.ensure_model_available(
                "sub",
                "westus3",
                "gpt-image-2",
                "2026-04-21",
                "GlobalStandard",
            )
            with self.assertRaisesRegex(azure_image.AzureImageError, "not available"):
                azure_image.ensure_model_available(
                    "sub",
                    "westus3",
                    "gpt-image-2",
                    "2026-04-21",
                    "ProvisionedManaged",
                )


if __name__ == "__main__":
    unittest.main()
