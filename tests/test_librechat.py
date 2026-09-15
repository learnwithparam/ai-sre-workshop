"""LibreChat is wired to OpenRouter and both MCP servers, and the model id is written once."""

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "librechat/librechat.yaml").read_text())
MODEL = "deepseek/deepseek-v4-flash"


def test_openrouter_endpoint_uses_the_env_key():
    (endpoint,) = CONFIG["endpoints"]["custom"]
    assert endpoint["name"] == "OpenRouter"
    assert endpoint["baseURL"] == "https://openrouter.ai/api/v1"
    assert endpoint["apiKey"] == "${OPENROUTER_API_KEY}"
    assert endpoint["models"]["default"] == [MODEL]
    assert endpoint["models"]["fetch"] is False


def test_the_ai_sre_spec_is_enforced_with_both_mcp_servers():
    specs = CONFIG["modelSpecs"]
    assert specs["enforce"] is True
    (spec,) = specs["list"]
    assert spec["name"] == "ai-sre"
    assert spec["preset"]["endpoint"] == "OpenRouter"
    assert spec["preset"]["model"] == MODEL
    assert set(spec["mcpServers"]) == {"sre", "clickhouse"}
    assert "propose_remediation" in spec["preset"]["promptPrefix"]


def test_both_mcp_servers_send_a_bearer_token():
    servers = CONFIG["mcpServers"]
    assert servers["sre"]["url"] == "http://sre-control:8090/mcp"
    assert servers["sre"]["headers"]["Authorization"] == "Bearer ${SRE_MCP_TOKEN}"
    assert servers["clickhouse"]["url"] == "http://mcp-clickhouse:8000/mcp"
    assert servers["clickhouse"]["headers"]["Authorization"] == "Bearer ${CLICKHOUSE_MCP_AUTH_TOKEN}"
    assert all(s["requiresOAuth"] is False for s in servers.values())


def test_the_model_id_is_written_once():
    files = subprocess.run(
        ["git", "grep", "-l", "--untracked", MODEL, "--", ":!*.md", ":!*.html", ":!tests/", ":!evidence/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert files == ["librechat/librechat.yaml"]
    assert len(re.findall(re.escape(MODEL), (ROOT / "librechat/librechat.yaml").read_text())) == 2
