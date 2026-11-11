from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from aicontrolhub.api import create_app
from aicontrolhub.cli import demo, main

ARTIFACT = hashlib.sha256(b"sample").hexdigest()


def test_api_registration_inventory_and_dashboard(tmp_path):
    with TestClient(create_app(tmp_path / "db.sqlite3")) as client:
        assert client.get("/").status_code == 200
        assert "AIControlHub" in client.get("/").text
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/healthz").json() == {"status": "ok"}
        assert len(client.get("/v1/catalog").json()) == 4
        assert client.get("/v1/systems").json() == []
        response = client.post("/v1/systems", json={
            "name": "Synthetic casework assistant", "owner": "model-owner",
            "purpose": "Categorize fictional casework examples for staff review", "impact": "low",
        })
        assert response.status_code == 201
        system_id = response.json()["id"]
        assert len(client.get(f"/v1/systems/{system_id}").json()["controls"]) == 4
        assert len(client.get("/v1/systems").json()) == 1
        assert client.get("/v1/events/verify").json()["valid"] is True


def test_api_release_workflow_and_validation(tmp_path):
    with TestClient(create_app(tmp_path / "db.sqlite3")) as client:
        response = client.post("/v1/systems", json={
            "name": "Synthetic release control", "owner": "owner",
            "purpose": "Review synthetic model use and deployment decisions", "impact": "low",
        })
        sid = response.json()["id"]
        assert client.post("/v1/systems", json={"name": "bad"}).status_code == 422
        assert client.get("/v1/systems/no-such-system").status_code == 404
        release = client.post(f"/v1/systems/{sid}/releases", json={
            "version": "1.0", "artifact_sha256": ARTIFACT,
        })
        assert release.status_code == 201
        rid = release.json()["id"]
        assert client.get(f"/v1/releases/{rid}/gate").json()["allowed"] is False
        assert client.post(f"/v1/releases/{rid}/approve", json={
            "approver": "other", "rationale": "Cannot approve without control reviews",
        }).status_code == 409
        for control in ("GOV-01", "MAP-01"):
            response = client.put(f"/v1/systems/{sid}/controls/{control}", json={
                "artifact_ref": "review/one.txt", "artifact_sha256": ARTIFACT,
                "reviewer": "reviewer", "summary": "Reviewed simulated evidence for this control",
            })
            assert response.status_code == 200
        assert "assessment_changed_since_release_request" in client.get(
            f"/v1/releases/{rid}/gate"
        ).json()["blockers"]
        newest = client.post(f"/v1/systems/{sid}/releases", json={
            "version": "1.0.1", "artifact_sha256": ARTIFACT,
        }).json()
        assert client.get(f"/v1/releases/{newest['id']}/gate").json()["allowed"] is True
        approved = client.post(f"/v1/releases/{newest['id']}/approve", json={
            "approver": "independent-approver",
            "rationale": "All mandatory reviewed evidence has been recorded",
        })
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert client.get("/v1/events/verify").json()["valid"] is True


def test_api_does_not_accept_extra_fields(tmp_path):
    with TestClient(create_app(tmp_path / "db.sqlite3")) as client:
        result = client.post("/v1/systems", json={
            "name": "Valid system", "owner": "owner",
            "purpose": "Assess a synthetic simulation workflow", "impact": "high",
            "override_gate": True,
        })
        assert result.status_code == 422


def test_cli_demo_and_verify(tmp_path, capsys):
    path = tmp_path / "example.sqlite3"
    result = demo(path)
    assert result["ready"] is True
    assert result["release_status"] == "approved"
    assert result["event_chain"]["checked"] == 10
    assert result["stale_blockers"] == ["assessment_changed_since_release_request"]
    assert main(["verify", "--database", str(path)]) == 0
    assert '"valid": true' in capsys.readouterr().out
