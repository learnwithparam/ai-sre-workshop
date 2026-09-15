"""The compose stack is valid in every mode, and the VPS mode exposes nothing but TLS."""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ["docker", "compose", "--env-file", ".env.example", "-f", "docker-compose.all-in-one.yml"]
VPS = [*BASE, "-f", "docker-compose.vps.yml"]

# Every hostname Caddy serves, and the upstream behind it. Each UI has its own login.
VPS_ROUTES = {
    "app": "subscription-app:8000",  # the customer-facing product, public by design
    "otlp": "clickstack:4318",  # browser telemetry ingest, needs the ingestion key
    "hyperdx": "clickstack:8080",  # HyperDX login
    "chat": "librechat:3080",  # LibreChat login, registration disabled
    "sre": "sre-control:8090",  # approver login
}


def config(cmd: list[str], *extra: str) -> dict:
    out = subprocess.run(
        [*cmd, *extra, "config", "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin", "WORKSHOP_DIR": str(ROOT)},
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_default_stack_is_valid():
    services = config(BASE)["services"]
    expected = {"clickstack", "subscription-app", "postgres-db", "docs-loader", "traffic"}
    expected |= {"librechat", "mongodb", "mcp-clickhouse", "sre-control"}
    assert expected <= set(services)
    assert "load-generator" not in services


def test_browser_load_profile_is_valid():
    assert "load-generator" in config(BASE, "--profile", "browser-load")["services"]


def test_vps_override_is_valid():
    services = config(VPS)["services"]
    assert "caddy" in services


def test_vps_publishes_only_web_ports():
    published = {
        (name, int(p["published"]))
        for name, svc in config(VPS)["services"].items()
        for p in svc.get("ports", [])
    }
    assert published == {("caddy", 80), ("caddy", 443)}


def test_every_vps_ui_requires_login():
    caddyfile = (ROOT / "caddy/Caddyfile").read_text()
    routes = dict(re.findall(r"^(\w+)\.\{\$PUBLIC_DOMAIN\}\s*\{\s*reverse_proxy\s+(\S+)", caddyfile, re.M))
    assert routes == VPS_ROUTES
    librechat = config(VPS)["services"]["librechat"]["environment"]
    assert librechat["ALLOW_REGISTRATION"] == "false"
    assert librechat["ALLOW_SOCIAL_LOGIN"] == "false"
    sre = config(VPS)["services"]["sre-control"]["environment"]
    assert sre["SRE_APPROVER_PASSWORD"], "approval pages need a password on the VPS"


def test_e2e_targets_derive_from_public_domain():
    source = (ROOT / "e2e/lib/config.ts").read_text()
    assert "PUBLIC_DOMAIN" in source
    assert source.count("localhost") == 1, "local URLs must come from the one url() helper"
    assert set(re.findall(r'url\("(\w+)",\s*\d+\)', source)) == set(VPS_ROUTES) - {"otlp"}
