"""The few Lightdash REST calls the CLI does not cover.

Authentication reuses whatever `lightdash login` stored, so a developer never handles a second
token; CI passes LIGHTDASH_API_KEY / LIGHTDASH_PROJECT_UUID explicitly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml

CLI_CONFIG = Path.home() / ".config" / "lightdash" / "config.yaml"


@dataclass(frozen=True)
class LightdashAuth:
    server_url: str
    api_key: str
    project_uuid: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"ApiKey {self.api_key}"}


def resolve_auth(project_uuid: str | None = None) -> LightdashAuth:
    cli: dict = {}
    if CLI_CONFIG.exists():
        cli = yaml.safe_load(CLI_CONFIG.read_text()) or {}
    context = cli.get("context", {})
    api_key = os.environ.get("LIGHTDASH_API_KEY") or context.get("apiKey")
    server = (
        os.environ.get("LIGHTDASH_URL") or context.get("serverUrl") or "https://app.lightdash.cloud"
    )
    project = project_uuid or os.environ.get("LIGHTDASH_PROJECT_UUID") or context.get("project")
    if not api_key or not project:
        raise RuntimeError(
            "No Lightdash credentials: run `lightdash login <url>` or set LIGHTDASH_API_KEY and "
            "LIGHTDASH_PROJECT_UUID."
        )
    return LightdashAuth(server_url=server.rstrip("/"), api_key=api_key, project_uuid=project)


def project_name(auth: LightdashAuth) -> str:
    r = requests.get(
        f"{auth.server_url}/api/v1/projects/{auth.project_uuid}", headers=auth.headers, timeout=30
    )
    r.raise_for_status()
    return r.json()["results"]["name"]


def restrict_explores_to_tag(auth: LightdashAuth, tag: str) -> None:
    """Only dbt models carrying `tag` become explores.

    Staging and intermediate models stay in the warehouse for lineage and debugging, but a BI
    user should never see them: the marts are the contract.
    """
    r = requests.patch(
        f"{auth.server_url}/api/v1/projects/{auth.project_uuid}/tablesConfiguration",
        headers=auth.headers,
        json={"tableSelection": {"type": "WITH_TAGS", "value": [tag]}},
        timeout=30,
    )
    r.raise_for_status()
