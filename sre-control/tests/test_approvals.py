"""Human-in-the-loop rules: the agent proposes, only a human decision lets anything run."""

import pytest

from sre_control.approvals import ApprovalRequired, InvalidTransition


def test_execute_without_approval_refuses(remediations, rollback, runner):
    with pytest.raises(ApprovalRequired):
        remediations.execute(rollback.action_id, executed_by="ai-sre")
    assert runner.calls == []
    assert remediations.status(rollback.action_id).state == "pending"


def test_execute_twice_runs_once(remediations, rollback, runner):
    remediations.approve(rollback.action_id, approver="oncall@example.com")
    first = remediations.execute(rollback.action_id, executed_by="ai-sre")
    second = remediations.execute(rollback.action_id, executed_by="ai-sre")
    assert runner.calls == [("rollback_release", "subscription-app", {"release": "v1"})]
    assert first == second
    assert remediations.status(rollback.action_id).state == "executed"


def test_reject_never_executes(remediations, rollback, runner):
    remediations.reject(rollback.action_id, approver="oncall@example.com", reason="wrong target")
    with pytest.raises(ApprovalRequired):
        remediations.execute(rollback.action_id, executed_by="ai-sre")
    assert runner.calls == []
    assert remediations.status(rollback.action_id).state == "rejected"


def test_edit_resets_to_pending_and_still_needs_approval(remediations, rollback, runner):
    remediations.reject(rollback.action_id, approver="oncall@example.com", reason="restart instead")
    remediations.edit(
        rollback.action_id,
        editor="oncall@example.com",
        action="restart_service",
        target="subscription-app",
        params={},
    )
    state = remediations.status(rollback.action_id)
    assert (state.state, state.action, state.target) == ("pending", "restart_service", "subscription-app")
    with pytest.raises(ApprovalRequired):
        remediations.execute(rollback.action_id, executed_by="ai-sre")
    remediations.approve(rollback.action_id, approver="oncall@example.com")
    remediations.execute(rollback.action_id, executed_by="ai-sre")
    assert runner.calls == [("restart_service", "subscription-app", {})]


def test_decisions_only_apply_to_pending_actions(remediations, rollback):
    remediations.approve(rollback.action_id, approver="oncall@example.com")
    remediations.execute(rollback.action_id, executed_by="ai-sre")
    with pytest.raises(InvalidTransition):
        remediations.reject(rollback.action_id, approver="oncall@example.com", reason="late")
    with pytest.raises(InvalidTransition):
        remediations.approve(rollback.action_id, approver="oncall@example.com")


def test_audit_records_every_step_with_actor_and_time(remediations, rollback, store):
    remediations.approve(rollback.action_id, approver="oncall@example.com")
    remediations.execute(rollback.action_id, executed_by="ai-sre")
    events = store.events(action_id=rollback.action_id)
    kinds = [e.kind for e in events]
    assert kinds == ["remediation_proposed", "remediation_approved", "remediation_executed"]
    assert [e.actor for e in events] == ["ai-sre", "oncall@example.com", "ai-sre"]
    assert all(e.ts is not None for e in events)
    assert events == sorted(events, key=lambda e: e.ts)


def test_proposing_twice_returns_the_waiting_proposal(remediations, rollback, incident, store, known_trace):
    again = remediations.propose(
        incident_id=incident.id, action="restart_service", target="subscription-app", params={},
        root_cause="retry", service="subscription-backend", release="v2", trace_ids=[known_trace],
        proposed_by="ai-sre",
    )  # fmt: skip
    assert again.action_id == rollback.action_id
    assert len(store.events(incident_id=incident.id, kind="remediation_proposed")) == 1
