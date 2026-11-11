# Multi-agent architecture

## Roles

- **Inventory analyst**: summarizes assets, categories, locations, and movement history.
- **Risk explainer**: explains the existing deterministic attention score and lists its contributing rules.
- **Maintenance planner**: drafts maintenance follow-up suggestions based on history; it cannot schedule or close work orders.
- **Data quality auditor**: finds missing serial numbers, locations, and inconsistent metadata.
- **Audit summarizer**: prepares a human-readable movement history.

## Boundaries

Agents are read-only. Asset handover, return, transfer, maintenance, and retirement must continue through the existing movement endpoint and its state-transition validation. Agents cannot mutate asset records or movement history. The current shared-token authentication limitation must be considered before remote agent exposure.

## Acceptance

Every score explanation shows the exact rules and points; the heuristic score is never described as a probability of failure. All asset data access requires the existing API token and future per-user authorization.
