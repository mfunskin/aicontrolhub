# Architecture and workflow

The API receives validated Pydantic request objects. The SQLite store executes
writes in `BEGIN IMMEDIATE` transactions, so a control update, risk change or
release approval is recorded with its audit event atomically. Read operations
return the current system record and related controls, risks and releases.

Each AI system has an assessment revision. Recording evidence, registering a
risk or mitigating a risk increments it. A release request references a fixed
revision. The release gate returns blockers when mandatory controls lack
reviewed evidence, a high/critical risk remains open, or the assessment was
revised after the release request. A recorded approval retains historical
status but its gate can become stale if the assessment later changes.

The evidence catalog uses illustrative controls grouped by the four NIST AI
RMF functions. It does not claim to cover every risk, industry obligation or
framework subcategory. Impact classification and control evidence require
human judgment.

An append-only event table chains each event's SHA-256 digest to the previous
row. Because both rows and hashes are kept in the same SQLite database, this
is a local integrity check, not a protected third-party audit ledger.

The initial web console supports inventory viewing and registration. The
OpenAPI interface exposes the full recorded governance workflow. The server
binds only to loopback and has no authenticated user system.
