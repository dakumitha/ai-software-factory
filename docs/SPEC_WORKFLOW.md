# Specification Workflow

The specification layer stores immutable, versioned project specifications in SQLite. Each requirement needs a unique ID, a description, and at least one acceptance criterion. Open questions prevent approval until resolved.

## API contract

- `POST /projects/{project_id}/specifications` creates a specification revision.
- `GET /projects/{project_id}/specifications` lists revisions.
- `GET /specifications/{spec_id}` retrieves a revision.
- `POST /specifications/{spec_id}/approve` approves a revision only when no open questions remain.
- `GET /specifications/{spec_id}/events` retrieves the approval audit trail.
- `POST /specifications/{spec_id}/plan` builds a deterministic starter plan.

A plan is not code execution. Generated plans require owner approval and later execution by an isolated agent adapter. The API is not safe for public exposure until authentication, authorization, rate limits, and TLS are configured.
