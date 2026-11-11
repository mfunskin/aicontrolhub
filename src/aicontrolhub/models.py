"""Validated API inputs for a local AI system inventory and release process."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreateSystem(StrictModel):
    name: str = Field(min_length=3, max_length=100)
    owner: str = Field(min_length=2, max_length=100)
    purpose: str = Field(min_length=10, max_length=2000)
    impact: Literal["low", "moderate", "high"]


class ControlEvidence(StrictModel):
    artifact_ref: str = Field(min_length=3, max_length=500)
    artifact_sha256: str
    reviewer: str = Field(min_length=2, max_length=100)
    summary: str = Field(min_length=10, max_length=1000)

    @field_validator("artifact_sha256")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("artifact_sha256 must be 64 lowercase hex characters")
        return value


class CreateRisk(StrictModel):
    title: str = Field(min_length=3, max_length=160)
    severity: Literal["low", "moderate", "high", "critical"]
    owner: str = Field(min_length=2, max_length=100)


class MitigateRisk(StrictModel):
    actor: str = Field(min_length=2, max_length=100)
    mitigation: str = Field(min_length=10, max_length=2000)


class CreateRelease(StrictModel):
    version: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
    artifact_sha256: str

    @field_validator("artifact_sha256")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        return ControlEvidence.valid_digest(value)


class ApproveRelease(StrictModel):
    approver: str = Field(min_length=2, max_length=100)
    rationale: str = Field(min_length=10, max_length=2000)
