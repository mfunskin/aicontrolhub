"""Transactional SQLite store for system inventory, controls, risks, and releases.

A governance record is evidence of recorded decisions, not an independent
certification or confirmation of any upstream artifact's authenticity.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from aicontrolhub.models import (
    ApproveRelease,
    ControlEvidence,
    CreateRelease,
    CreateRisk,
    CreateSystem,
    MitigateRisk,
)

CONTROL_CATALOG = {
    "GOV-01": ("GOVERN", "Named owner and documented accountability"),
    "MAP-01": ("MAP", "Intended use, users, and deployment context"),
    "MEA-01": ("MEASURE", "Documented testing and limitations"),
    "MAN-01": ("MANAGE", "Operational monitoring and incident response"),
}
REQUIRED = {
    "low": ("GOV-01", "MAP-01"),
    "moderate": ("GOV-01", "MAP-01", "MEA-01"),
    "high": tuple(CONTROL_CATALOG),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def object_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


class GovernanceError(ValueError):
    """Invalid workflow state or unknown record."""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS systems (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, owner TEXT NOT NULL,
                    purpose TEXT NOT NULL, impact TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS controls (
                    system_id TEXT NOT NULL REFERENCES systems(id),
                    control_id TEXT NOT NULL, function TEXT NOT NULL, title TEXT NOT NULL,
                    artifact_ref TEXT, artifact_sha256 TEXT, reviewer TEXT,
                    summary TEXT, reviewed_at TEXT,
                    PRIMARY KEY (system_id, control_id)
                );
                CREATE TABLE IF NOT EXISTS risks (
                    id TEXT PRIMARY KEY, system_id TEXT NOT NULL REFERENCES systems(id),
                    title TEXT NOT NULL, severity TEXT NOT NULL, owner TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open', mitigation TEXT
                );
                CREATE TABLE IF NOT EXISTS releases (
                    id TEXT PRIMARY KEY, system_id TEXT NOT NULL REFERENCES systems(id),
                    version TEXT NOT NULL, artifact_sha256 TEXT NOT NULL,
                    revision INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'requested',
                    approved_by TEXT, approved_at TEXT, rationale TEXT,
                    UNIQUE(system_id, version)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, system_id TEXT NOT NULL,
                    action TEXT NOT NULL, actor TEXT NOT NULL, details TEXT NOT NULL,
                    recorded_at TEXT NOT NULL, previous_hash TEXT NOT NULL,
                    hash TEXT NOT NULL
                );
                """
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def require(db: sqlite3.Connection, table: str, identifier: str) -> dict:
        # Table is chosen only by internal code, never from user input.
        if table not in {"systems", "risks", "releases"}:
            raise GovernanceError("invalid record category")
        result = object_dict(db.execute(f"SELECT * FROM {table} WHERE id=?", (identifier,)).fetchone())
        if result is None:
            raise GovernanceError(f"unknown {table[:-1]}: {identifier}")
        return result

    @staticmethod
    def event(db: sqlite3.Connection, system_id: str, action: str, actor: str, details: dict):
        previous = db.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
        last = previous["hash"] if previous else ""
        timestamp = now()
        encoded = json.dumps(details, sort_keys=True, separators=(",", ":"))
        payload = json.dumps(
            [system_id, action, actor, encoded, timestamp, last],
            separators=(",", ":"),
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        db.execute(
            "INSERT INTO events(system_id,action,actor,details,recorded_at,previous_hash,hash) "
            "VALUES(?,?,?,?,?,?,?)",
            (system_id, action, actor, encoded, timestamp, last, digest),
        )

    def create_system(self, data: CreateSystem) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            system_id = uuid4().hex[:16]
            db.execute(
                "INSERT INTO systems(id,name,owner,purpose,impact,created_at) VALUES(?,?,?,?,?,?)",
                (system_id, data.name, data.owner, data.purpose, data.impact, now()),
            )
            for control_id, (function, title) in CONTROL_CATALOG.items():
                db.execute(
                    "INSERT INTO controls(system_id,control_id,function,title) VALUES(?,?,?,?)",
                    (system_id, control_id, function, title),
                )
            self.event(db, system_id, "system_created", data.owner, {"impact": data.impact})
            return self.require(db, "systems", system_id)

    def list_systems(self) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM systems ORDER BY created_at,id")]

    def system(self, system_id: str) -> dict:
        with self.connect() as db:
            system = self.require(db, "systems", system_id)
            system["controls"] = [dict(r) for r in db.execute(
                "SELECT * FROM controls WHERE system_id=? ORDER BY control_id", (system_id,)
            )]
            system["risks"] = [dict(r) for r in db.execute(
                "SELECT * FROM risks WHERE system_id=? ORDER BY id", (system_id,)
            )]
            system["releases"] = [dict(r) for r in db.execute(
                "SELECT * FROM releases WHERE system_id=? ORDER BY version", (system_id,)
            )]
            return system

    def add_evidence(self, system_id: str, control_id: str, data: ControlEvidence) -> dict:
        if control_id not in CONTROL_CATALOG:
            raise GovernanceError("unknown control")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            system = self.require(db, "systems", system_id)
            if data.reviewer.casefold() == system["owner"].casefold():
                raise GovernanceError("control evidence reviewer must differ from system owner")
            db.execute(
                "UPDATE controls SET artifact_ref=?,artifact_sha256=?,reviewer=?,summary=?,"
                "reviewed_at=? WHERE system_id=? AND control_id=?",
                (data.artifact_ref, data.artifact_sha256, data.reviewer,
                 data.summary, now(), system_id, control_id),
            )
            db.execute("UPDATE systems SET revision=revision+1 WHERE id=?", (system_id,))
            self.event(db, system_id, "control_evidence_recorded", data.reviewer,
                       {"control_id": control_id, "artifact_sha256": data.artifact_sha256})
            return dict(db.execute(
                "SELECT * FROM controls WHERE system_id=? AND control_id=?",
                (system_id, control_id),
            ).fetchone())

    def add_risk(self, system_id: str, data: CreateRisk) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.require(db, "systems", system_id)
            risk_id = uuid4().hex[:16]
            db.execute(
                "INSERT INTO risks(id,system_id,title,severity,owner,status) "
                "VALUES(?,?,?,?,?,'open')",
                (risk_id, system_id, data.title, data.severity, data.owner),
            )
            db.execute("UPDATE systems SET revision=revision+1 WHERE id=?", (system_id,))
            self.event(db, system_id, "risk_registered", data.owner,
                       {"risk_id": risk_id, "severity": data.severity})
            return self.require(db, "risks", risk_id)

    def mitigate_risk(self, system_id: str, risk_id: str, data: MitigateRisk) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            risk = self.require(db, "risks", risk_id)
            if risk["system_id"] != system_id:
                raise GovernanceError("risk does not belong to system")
            if risk["status"] != "open":
                raise GovernanceError("risk is already mitigated")
            db.execute("UPDATE risks SET status='mitigated',mitigation=? WHERE id=?",
                       (data.mitigation, risk_id))
            db.execute("UPDATE systems SET revision=revision+1 WHERE id=?", (system_id,))
            self.event(db, system_id, "risk_marked_mitigated", data.actor, {"risk_id": risk_id})
            return self.require(db, "risks", risk_id)

    def request_release(self, system_id: str, data: CreateRelease) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            system = self.require(db, "systems", system_id)
            release_id = uuid4().hex[:16]
            try:
                db.execute(
                    "INSERT INTO releases(id,system_id,version,artifact_sha256,revision) "
                    "VALUES(?,?,?,?,?)",
                    (release_id, system_id, data.version, data.artifact_sha256,
                     system["revision"]),
                )
            except sqlite3.IntegrityError as exc:
                raise GovernanceError("release version already exists") from exc
            self.event(db, system_id, "release_requested", system["owner"],
                       {"release_id": release_id, "version": data.version})
            return self.require(db, "releases", release_id)

    @staticmethod
    def gate_for(db: sqlite3.Connection, release: dict) -> dict:
        system = Store.require(db, "systems", release["system_id"])
        blockers: list[str] = []
        if release["revision"] != system["revision"]:
            blockers.append("assessment_changed_since_release_request")
        controls = {row["control_id"]: dict(row) for row in db.execute(
            "SELECT * FROM controls WHERE system_id=?", (system["id"],)
        )}
        for control_id in REQUIRED[system["impact"]]:
            item = controls[control_id]
            if not item["reviewed_at"] or not item["artifact_sha256"]:
                blockers.append(f"missing_reviewed_evidence:{control_id}")
        for row in db.execute(
            "SELECT id FROM risks WHERE system_id=? AND severity IN ('high','critical') "
            "AND status='open' ORDER BY id", (system["id"],)
        ):
            blockers.append(f"unresolved_risk:{row['id']}")
        return {
            "release_id": release["id"],
            "system_id": system["id"],
            "impact": system["impact"],
            "release_version": release["version"],
            "assessment_revision": system["revision"],
            "release_revision": release["revision"],
            "status": release["status"],
            "allowed": len(blockers) == 0,
            "blockers": blockers,
        }

    def gate(self, release_id: str) -> dict:
        with self.connect() as db:
            return self.gate_for(db, self.require(db, "releases", release_id))

    def approve_release(self, release_id: str, data: ApproveRelease) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            release = self.require(db, "releases", release_id)
            system = self.require(db, "systems", release["system_id"])
            if data.approver.casefold() == system["owner"].casefold():
                raise GovernanceError("system owner cannot approve own release")
            if release["status"] != "requested":
                raise GovernanceError("release is not awaiting approval")
            gate = self.gate_for(db, release)
            if not gate["allowed"]:
                raise GovernanceError("release gate blocked: " + ", ".join(gate["blockers"]))
            db.execute(
                "UPDATE releases SET status='approved',approved_by=?,approved_at=?,"
                "rationale=? WHERE id=?",
                (data.approver, now(), data.rationale, release_id),
            )
            self.event(db, system["id"], "release_approved", data.approver,
                       {"release_id": release_id, "version": release["version"]})
            return self.require(db, "releases", release_id)

    def verify_events(self) -> dict:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM events ORDER BY id").fetchall()
            previous = ""
            for number, row in enumerate(rows, 1):
                payload = json.dumps(
                    [row["system_id"], row["action"], row["actor"],
                     row["details"], row["recorded_at"], row["previous_hash"]],
                    separators=(",", ":"),
                )
                digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                if row["previous_hash"] != previous or digest != row["hash"]:
                    return {"valid": False, "checked": number - 1, "failed_event_id": row["id"]}
                previous = row["hash"]
            return {"valid": True, "checked": len(rows), "last_hash": previous}
