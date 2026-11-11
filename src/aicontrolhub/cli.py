"""CLI for a repeatable governance workflow and local API."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import uvicorn

from aicontrolhub.api import create_app
from aicontrolhub.models import (
    ApproveRelease,
    ControlEvidence,
    CreateRelease,
    CreateRisk,
    CreateSystem,
    MitigateRisk,
)
from aicontrolhub.store import CONTROL_CATALOG, Store


def demo(database: Path) -> dict:
    store = Store(database)
    system = store.create_system(CreateSystem(
        name="Synthetic document triage assistant",
        owner="engineering-owner",
        impact="high",
        purpose="Classify synthetic internal documents and propose a routing category",
    ))
    sys_id = system["id"]
    risk = store.add_risk(sys_id, CreateRisk(
        title="Unexpected disclosure through generated responses",
        severity="high",
        owner="security-reviewer",
    ))
    artifact = hashlib.sha256(b"synthetic-review-artifact-v1").hexdigest()
    release = store.request_release(sys_id, CreateRelease(version="1.0.0", artifact_sha256=artifact))
    before = store.gate(release["id"])
    # This demo intentionally records a risk decision before the final evidence and release.
    store.mitigate_risk(sys_id, risk["id"], MitigateRisk(
        actor="security-reviewer",
        mitigation="Scoped output handling and incident response review are recorded",
    ))
    for control_id in CONTROL_CATALOG:
        store.add_evidence(sys_id, control_id, ControlEvidence(
            artifact_ref=f"artifacts/{control_id.lower()}-review.txt",
            artifact_sha256=artifact,
            reviewer="independent-reviewer",
            summary=f"Documented synthetic test and manual assessment for {control_id}",
        ))
    # Assessment changes invalidate the older release request.
    stale = store.gate(release["id"])
    new_release = store.request_release(sys_id, CreateRelease(
        version="1.0.1", artifact_sha256=artifact,
    ))
    ready = store.gate(new_release["id"])
    approved = store.approve_release(new_release["id"], ApproveRelease(
        approver="governance-approver",
        rationale="Required evidence reviewed and open high-severity risk resolved",
    ))
    return {
        "system_id": sys_id,
        "original_blockers": before["blockers"],
        "stale_blockers": stale["blockers"],
        "ready": ready["allowed"],
        "release_status": approved["status"],
        "event_chain": store.verify_events(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aicontrolhub")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Serve the local API and browser console")
    serve.add_argument("--database", type=Path, default=Path("runs/aicontrolhub.sqlite3"))
    serve.add_argument("--port", type=int, default=8093)
    demonstration = sub.add_parser("demo", help="Run a synthetic governance case")
    demonstration.add_argument("--database", type=Path, default=Path("runs/demo.sqlite3"))
    verify = sub.add_parser("verify", help="Verify the append-only event hash chain")
    verify.add_argument("--database", type=Path, default=Path("runs/aicontrolhub.sqlite3"))
    args = parser.parse_args(argv)
    if args.command == "serve":
        uvicorn.run(create_app(args.database), host="127.0.0.1", port=args.port)
        return 0
    if args.command == "demo":
        result = demo(args.database)
    else:
        result = Store(args.database).verify_events()
    print(json.dumps(result, indent=2))
    return 0 if result.get("valid", True) is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
