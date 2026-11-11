# AIControlHub

**An AI system inventory and risk-based software release review workflow.**

AIControlHub records proposed AI systems, ownership, structured risk records,
reviewed control evidence and versioned release decisions. Release requests are
checked against required evidence, unresolved high-severity risks and the
assessment revision. An accountable system owner cannot approve their own
release through the application workflow.

The control categories use the four NIST AI Risk Management Framework functions:
**GOVERN, MAP, MEASURE and MANAGE**. The controls in this repository are small,
illustrative engineering requirements. They are not an authoritative mapping
to NIST subcategories and do not constitute NIST, ISO or legal certification.

NIST reference: <https://airc.nist.gov/airmf-resources/playbook/>

## Implemented features

- SQLite-backed inventory with an impact tier, named owner and use case.
- Required controls based on an explicitly selected impact tier.
- Evidence references, SHA-256 digests and recorded reviewer identity.
- Risk register, severity, mitigation record and release blockers.
- Release request snapshots that become stale after assessment changes.
- Independent release approval field, rationale and approval history.
- Transactional database writes and a verifiable application-level hash chain.
- REST API, OpenAPI documentation, browser inventory console and CLI demo.
- Unit tests, concurrency tests and GitHub Actions for Python 3.11–3.13.

## Install and test

Python 3.11 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
ruff check .
```

## Run a reproducible governance case

```bash
aicontrolhub demo --database runs/demo.sqlite3
aicontrolhub verify --database runs/demo.sqlite3
```

The demo registers a high-impact **synthetic** AI system, records an open high
risk, and requests a release. The first gate is blocked by missing evidence and
the unresolved risk. After recorded mitigation and reviewed control evidence,
the original release request is stale. A new release request is approved by a
reviewer distinct from the accountable owner. The audit chain is checked.

The demo uses fictional identity labels and synthetic evidence identifiers.
Its recorded review fields are workflow data; no real human verification occurs.

## API and browser console

```bash
aicontrolhub serve --database runs/local.sqlite3 --port 8093
```

Open <http://127.0.0.1:8093/> for the local system inventory and registration
console. Open <http://127.0.0.1:8093/docs> for the full OpenAPI interface,
including evidence recording, risk management and release approval.

REST endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/v1/systems` | Register an AI system |
| GET | `/v1/systems/{id}` | List controls, risks and releases |
| PUT | `/v1/systems/{id}/controls/{control}` | Record evidence metadata |
| POST | `/v1/systems/{id}/risks` | Register a risk |
| POST | `/v1/systems/{id}/risks/{risk}/mitigate` | Record a mitigation |
| POST | `/v1/systems/{id}/releases` | Request a release |
| GET | `/v1/releases/{id}/gate` | Inspect release blockers |
| POST | `/v1/releases/{id}/approve` | Record an approval |
| GET | `/v1/events/verify` | Check the local event hash chain |

## Limitations and security assumptions

- **Local development only:** The service has no login, authenticated
  signatures, tenant isolation, CSRF protection or production access control.
  User-supplied actor names are not verified identities. Never expose it
  publicly or treat a recorded approval as an authenticated authorization.
- Evidence references and digests are accepted as metadata. The system does
  not fetch or independently verify referenced artifacts or their reviewers.
- The SHA-256 audit chain detects some record modifications but is not
  tamperproof when an attacker can rewrite the database and all hashes. It is
  not an independently retained legal or regulatory audit record.
- Risk severity is supplied by a human; this software does not assess AI
  model safety, bias or technical reliability automatically.
- This is not a model evaluation system, NIST certification, ISO 42001 audit,
  or automated compliance assessment.

All example records are synthetic. Keep personal details, protected data,
client materials, unpublished research records and API keys out of Git.
SQLite files are ignored under `runs/`.

## Project structure

```text
src/aicontrolhub/store.py  Transactions, controls, risks, release gates and events
src/aicontrolhub/models.py API input validation
src/aicontrolhub/api.py    Local REST API
src/aicontrolhub/cli.py    Demo and server commands
src/aicontrolhub/web/       Browser inventory console
tests/                    Workflow and HTTP integration tests
docs/                     Design, trust boundaries and roadmap
.github/workflows/ci.yml  Multi-version CI
```

See [docs/roadmap.md](docs/roadmap.md) for challenging follow-up engineering
work, including authenticated roles, evidence provenance, expiring approvals,
policy migration and external governance controls.

License: MIT.
