# Engineering roadmap

## 1. Authentication, authorization and roles

Implement verified identities with scoped roles for system owners, reviewers,
risk officers and release approvers. Enforce separation of duties using those
verified identities, not client-supplied names. Add session security and CSRF
protection for the management interface.

## 2. Evidence and provenance

Build a content-addressed artifact store, immutable artifact versions, reviewer
signatures, checksum validation and control expiration. Store evidence behind
access controls with provenance and retention policies.

## 3. Policy versioning and approvals

Develop versioned control catalogs and configurable impact gates, including
accepted-risk exceptions, approval expiration, renewal and revocation.

## 4. Reporting and framework mapping

Add clearly sourced references to NIST AI RMF subcategories and the Generative
AI Profile with auditable mapping versions and explicit gaps. Avoid implying
that passing application checks establishes regulatory compliance.

## 5. Production data architecture

Move to PostgreSQL with robust isolation, migrations, event replay, backup and
recovery tests. Implement a trusted audit-sink/export path to detect complete
event-log replacement.

## 6. Management dashboard

Expand the local inventory console to support role-authenticated control
reviews, risk dashboards, release history and cross-system reporting.
