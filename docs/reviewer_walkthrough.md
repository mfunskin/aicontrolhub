# Reviewer walkthrough

Run the test suite and the synthetic CLI demo. The initial release request
fails because required reviewed evidence is absent and a high risk is open.
The subsequent evidence and mitigation records invalidate the old request.
A new release is approved by a different actor, and the local event hash chain
verifies successfully.

Inspect `store.py` for the transactional gate, revision consistency and
risk blocker checks. Examine the tests for self-approval rejection, cross-system
risk integrity, database concurrency, stale approval handling and event
tampering. Use the browser console for inventory and `/docs` for the complete
workflow.

This is software for tracking governance decisions, not an automatic proof of
trustworthiness or compliance. The first release has no verified user identity
or evidence authenticity. Those are explicit roadmap items.
