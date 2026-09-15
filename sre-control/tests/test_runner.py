"""The runner can only build the two commands policy allows, with no shell and no free text."""

import pytest

from sre_control.policy import PolicyError
from sre_control.runner import build_command

PROJECT = "/srv/ai-sre-workshop"


def test_rollback_redeploys_the_previous_release():
    cmd, env = build_command("rollback_release", "subscription-app", {"release": "v1"}, PROJECT)
    assert cmd == [
        "docker", "compose", "--project-directory", PROJECT,
        "-f", f"{PROJECT}/docker-compose.all-in-one.yml",
        "up", "-d", "--no-deps", "--wait", "subscription-app",
    ]  # fmt: skip
    assert env == {"APP_RELEASE": "v1"}


def test_restart_restarts_one_named_service():
    cmd, env = build_command("restart_service", "docs-loader", {}, PROJECT)
    assert cmd[-2:] == ["restart", "docs-loader"]
    assert env == {}


@pytest.mark.parametrize(
    ("action", "target", "params"),
    [
        ("restart_service", "clickstack", {}),
        ("restart_service", "docs-loader; reboot", {}),
        ("rollback_release", "subscription-app", {"release": "v2"}),
        ("rollback_release", "subscription-app", {"release": "v1", "extra": "x"}),
        ("exec", "subscription-app", {}),
    ],
)
def test_anything_else_is_refused(action, target, params):
    with pytest.raises(PolicyError):
        build_command(action, target, params, PROJECT)
