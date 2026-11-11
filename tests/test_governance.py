from __future__ import annotations

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from aicontrolhub.models import (
    ApproveRelease,
    ControlEvidence,
    CreateRelease,
    CreateRisk,
    CreateSystem,
    MitigateRisk,
)
from aicontrolhub.store import CONTROL_CATALOG, GovernanceError, Store

ARTIFACT = hashlib.sha256(b"test artifact").hexdigest()


def create_system(store, impact="high", owner="product-owner"):
    return store.create_system(CreateSystem(
        name="Synthetic AI assistant",
        purpose="Respond to simulated customer support tickets",
        owner=owner,
        impact=impact,
    ))


def add_all_evidence(store, system_id):
    for control in CONTROL_CATALOG:
        store.add_evidence(system_id, control, ControlEvidence(
            artifact_ref=f"review/{control}.md",
            artifact_sha256=ARTIFACT,
            reviewer="external-reviewer",
            summary="Reproduced the synthetic controls review using a test fixture",
        ))


def request(store, system_id, version="v1"):
    return store.request_release(system_id, CreateRelease(
        version=version, artifact_sha256=ARTIFACT,
    ))


def test_create_and_list_system(store):
    system = create_system(store)
    assert system["revision"] == 1
    assert store.list_systems()[0]["name"] == "Synthetic AI assistant"
    detail = store.system(system["id"])
    assert len(detail["controls"]) == 4
    assert detail["risks"] == []


def test_missing_controls_block_high_impact(store):
    system = create_system(store)
    release = request(store, system["id"])
    gate = store.gate(release["id"])
    assert gate["allowed"] is False
    assert len(gate["blockers"]) == 4
    assert "missing_reviewed_evidence:MAN-01" in gate["blockers"]


def test_lower_impact_requires_fewer_controls(store):
    system = create_system(store, "low")
    for control in ("GOV-01", "MAP-01"):
        store.add_evidence(system["id"], control, ControlEvidence(
            artifact_ref="review/one.md", artifact_sha256=ARTIFACT,
            reviewer="external-reviewer", summary="Reviewed synthetic evidence and scope",
        ))
    release = request(store, system["id"])
    assert store.gate(release["id"])["allowed"] is True


def test_owner_cannot_self_review_evidence(store):
    system = create_system(store)
    with pytest.raises(GovernanceError, match="reviewer must differ"):
        store.add_evidence(system["id"], "GOV-01", ControlEvidence(
            artifact_ref="review/one.md", artifact_sha256=ARTIFACT,
            reviewer="PRODUCT-OWNER", summary="Review by the accountable system owner",
        ))
    assert store.system(system["id"])["revision"] == 1


def test_invalid_evidence_hash():
    with pytest.raises(ValidationError, match="artifact_sha256"):
        ControlEvidence(artifact_ref="evidence.md", artifact_sha256="not-a-hash",
                        reviewer="reviewer", summary="Synthetic controls review summary")


def test_high_risk_blocks_after_evidence(store):
    system = create_system(store)
    risk = store.add_risk(system["id"], CreateRisk(
        title="Unauthorized disclosure", severity="high", owner="risk-lead",
    ))
    add_all_evidence(store, system["id"])
    release = request(store, system["id"])
    assert f"unresolved_risk:{risk['id']}" in store.gate(release["id"])["blockers"]
    with pytest.raises(GovernanceError, match="release gate blocked"):
        store.approve_release(release["id"], ApproveRelease(
            approver="approval-board", rationale="This has enough supporting evidence",
        ))
    assert store.gate(release["id"])["status"] == "requested"


def test_risk_mitigation_and_independent_approval(store):
    system = create_system(store)
    risk = store.add_risk(system["id"], CreateRisk(
        title="Unexpected exposure", severity="critical", owner="risk-lead",
    ))
    store.mitigate_risk(system["id"], risk["id"], MitigateRisk(
        actor="risk-lead", mitigation="Documented controls and reviewed incident escalation",
    ))
    add_all_evidence(store, system["id"])
    release = request(store, system["id"])
    assert store.gate(release["id"])["allowed"] is True
    with pytest.raises(GovernanceError, match="cannot approve own release"):
        store.approve_release(release["id"], ApproveRelease(
            approver="product-owner", rationale="I consider this acceptable for deployment",
        ))
    approved = store.approve_release(release["id"], ApproveRelease(
        approver="release-chair", rationale="Evidence and documented risk mitigation reviewed",
    ))
    assert approved["status"] == "approved"
    assert approved["approved_by"] == "release-chair"
    with pytest.raises(GovernanceError, match="not awaiting approval"):
        store.approve_release(release["id"], ApproveRelease(
            approver="release-chair", rationale="Attempt to approve the same request twice",
        ))


def test_revision_change_makes_existing_release_stale(store):
    system = create_system(store, impact="low")
    release = request(store, system["id"])
    store.add_risk(system["id"], CreateRisk(
        title="Potential output ambiguity", severity="low", owner="risk-lead",
    ))
    gate = store.gate(release["id"])
    assert "assessment_changed_since_release_request" in gate["blockers"]


def test_approved_release_becomes_stale_if_assessment_changes(store):
    system = create_system(store, "high")
    add_all_evidence(store, system["id"])
    release = request(store, system["id"])
    store.approve_release(release["id"], ApproveRelease(
        approver="release-chair", rationale="Completed all required evidence reviews",
    ))
    store.add_risk(system["id"], CreateRisk(
        title="Newly discovered risk", severity="critical", owner="risk-lead",
    ))
    gate = store.gate(release["id"])
    assert gate["allowed"] is False
    assert gate["status"] == "approved"  # historical approval, not current clearance
    assert any(x.startswith("unresolved_risk:") for x in gate["blockers"])


def test_duplicate_release_version_fails_atomically(store):
    system = create_system(store)
    request(store, system["id"], "1.0")
    with pytest.raises(GovernanceError, match="already exists"):
        request(store, system["id"], "1.0")
    assert len(store.system(system["id"])["releases"]) == 1


def test_cross_system_risk_mitigation_denied(store):
    first = create_system(store)
    second = create_system(store, owner="other-owner")
    risk = store.add_risk(first["id"], CreateRisk(
        title="Source contamination", severity="high", owner="risk-lead",
    ))
    with pytest.raises(GovernanceError, match="does not belong"):
        store.mitigate_risk(second["id"], risk["id"], MitigateRisk(
            actor="risk-lead", mitigation="Mitigated only within the original system",
        ))
    assert store.system(first["id"])["risks"][0]["status"] == "open"


def test_event_hash_chain_detects_modification(store):
    system = create_system(store)
    add_all_evidence(store, system["id"])
    assert store.verify_events()["valid"] is True
    with sqlite3.connect(store.path) as conn:
        conn.execute("UPDATE events SET actor='someone-else' WHERE id=1")
    assert store.verify_events()["valid"] is False


def test_concurrent_system_creation_keeps_hash_chain(tmp_path):
    path = tmp_path / "shared.sqlite3"
    store = Store(path)

    def add(index):
        return create_system(store, owner=f"owner-{index}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(add, range(12)))
    assert len(set(item["id"] for item in created)) == 12
    assert store.verify_events()["checked"] == 12
    assert store.verify_events()["valid"] is True


def test_unknown_system_and_control_rejected(store):
    with pytest.raises(GovernanceError, match="unknown system"):
        store.system("not-there")
    system = create_system(store)
    with pytest.raises(GovernanceError, match="unknown control"):
        store.add_evidence(system["id"], "INVALID", ControlEvidence(
            artifact_ref="review/one.md", artifact_sha256=ARTIFACT,
            reviewer="reviewer", summary="Valid review summary content",
        ))
