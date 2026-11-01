"""The compose stack is valid in every mode, and the VPS mode exposes nothing but TLS."""

import json
import os
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
        # Only PATH and HOME from the caller, so a stray APP_RELEASE in a shell cannot change the result.
        env={"PATH": os.environ["PATH"], "HOME": os.environ["HOME"], "WORKSHOP_DIR": str(ROOT)},
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_default_stack_is_valid():
    services = config(BASE)["services"]
    expected = {"clickstack", "subscription-app", "postgres-db", "docs-loader", "traffic"}
    expected |= {"librechat", "mongodb", "mcp-clickhouse", "sre-control"}
    assert expected <= set(services)
    assert "load-generator" not in services
    # LibreChat caches MCP tool schemas; a rebuilt MCP server must restart it or it rejects valid calls.
    deps = services["librechat"]["depends_on"]
    assert deps["sre-control"]["restart"] is True and deps["mcp-clickhouse"]["restart"] is True


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


def test_no_port_binds_all_interfaces():
    """sre-control holds the docker socket and the approval page; a published port must not reach the LAN."""
    for name, svc in config(BASE)["services"].items():
        for p in svc.get("ports", []):
            assert p.get("host_ip") == "127.0.0.1", f"{name} publishes {p['published']} on every interface"
    caddy = {int(p["published"]): p.get("host_ip") for p in config(VPS)["services"]["caddy"]["ports"]}
    assert set(caddy) == {80, 443}, "only Caddy faces the network on the VPS"


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
    assert set(re.findall(r'url\("(\w+)",\s*\d+\)', source)) == set(VPS_ROUTES)


def test_generate_env_replaces_change_me(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("generate_env", ROOT / "scripts/generate_env.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    target = tmp_path / "copied"
    target.write_text((ROOT / ".env.example").read_text())
    gen.main(target)
    values = gen.read(target)
    for key in gen.GENERATED:
        assert values[key] != gen.PLACEHOLDER, key
    assert target.read_text().count("CREDS_KEY=") == 1, "a copied example must not gain duplicate lines"
    assert gen.main(target) == 2, "no ingestion key yet means ClickStack must be started to get one"
    target.write_text(target.read_text().replace("HYPERDX_API_KEY=change-me", "HYPERDX_API_KEY=hdx-test"))
    assert gen.main(target) == 1, "the Anthropic key is still only yours to supply"


def test_readme_runs_env_before_compose():
    steps = (ROOT / "README.md").read_text().split("## Start the lab")[1].split("4. Open the pages")[0]
    assert steps.index("make env") < steps.index("make up")
    assert "docker compose" not in steps, "a fresh clone has no .env until make env writes it"


def test_env_example_lists_every_required_variable():
    compose = (ROOT / "docker-compose.all-in-one.yml").read_text()
    used = set(re.findall(r"\$\{([A-Z_0-9]+)", compose))
    defaulted = set(re.findall(r"\$\{([A-Z_0-9]+):?-", compose))
    listed = set(re.findall(r"^([A-Z_0-9]+)=", (ROOT / ".env.example").read_text(), re.M))
    # WORKSHOP_DIR is set by the Makefile, not by the learner.
    missing = used - defaulted - listed - {"WORKSHOP_DIR"}
    assert not missing, f"the example file lacks {sorted(missing)}"
