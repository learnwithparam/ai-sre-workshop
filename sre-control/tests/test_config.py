"""sre-control refuses to boot with a missing setting and names every one that is missing."""

import pytest

from sre_control.config import REQUIRED, ConfigError, load_settings

FULL = {
    "CLICKHOUSE_HOST": "clickstack",
    "CLICKHOUSE_READER_USER": "sre_agent",
    "CLICKHOUSE_READER_PASSWORD": "r",
    "CLICKHOUSE_WRITER_USER": "sre_control",
    "CLICKHOUSE_WRITER_PASSWORD": "w",
    "SRE_MCP_TOKEN": "t",
    "SRE_APPROVER_EMAIL": "oncall@example.com",
    "SRE_APPROVER_PASSWORD": "p",
    "SRE_SESSION_SECRET": "s",
    "SRE_PUBLIC_URL": "http://localhost:8090",
    "CHAT_PUBLIC_URL": "http://localhost:3080",
    "WORKSHOP_DIR": "/srv/ai-sre-workshop",
}


def test_full_settings_load():
    settings = load_settings(FULL)
    assert settings.clickhouse_host == "clickstack"
    assert settings.detector_interval_s == 10


def test_every_missing_setting_is_named():
    with pytest.raises(ConfigError) as err:
        load_settings({"CLICKHOUSE_HOST": "clickstack"})
    for name in set(REQUIRED) - {"CLICKHOUSE_HOST"}:
        assert name in str(err.value)


@pytest.mark.parametrize("name", sorted(FULL))
def test_an_empty_value_counts_as_missing(name):
    with pytest.raises(ConfigError, match=name):
        load_settings({**FULL, name: ""})
