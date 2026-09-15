"""A proposal is stored only when its evidence exists in telemetry and its action is in policy."""

import pytest

from sre_control.approvals import Ungrounded
from sre_control.policy import PolicyError


@pytest.fixture
def propose(remediations, incident, known_trace):
    base = dict(
        action="rollback_release",
        target="subscription-app",
        params={"release": "v1"},
        root_cause="Release v2 fails subscribe requests",
        service="subscription-backend",
        release="v2",
        trace_ids=[known_trace],
        proposed_by="ai-sre",
    )
    return lambda **overrides: remediations.propose(incident_id=incident.id, **{**base, **overrides})


def test_ungrounded_proposal_is_rejected(propose, incident, store, known_trace):
    with pytest.raises(Ungrounded, match="f{32}"):
        propose(trace_ids=[known_trace, "f" * 32])
    assert store.events(incident_id=incident.id, kind="remediation_proposed") == []


def test_proposal_needs_at_least_one_trace(propose):
    with pytest.raises(Ungrounded):
        propose(trace_ids=[])


def test_unknown_service_is_rejected(propose):
    with pytest.raises(Ungrounded, match="payments"):
        propose(service="payments")


def test_release_never_seen_is_rejected(propose):
    with pytest.raises(Ungrounded, match="v9"):
        propose(release="v9")


def test_action_outside_policy_is_rejected(propose):
    with pytest.raises(PolicyError):
        propose(action="drop_table", target="users", params={})
    with pytest.raises(PolicyError):
        propose(action="restart_service", target="clickstack", params={})
    with pytest.raises(PolicyError):
        propose(params={"release": "v2; rm -rf /"})


def test_grounded_proposal_is_pending(propose, remediations):
    assert remediations.status(propose().action_id).state == "pending"
