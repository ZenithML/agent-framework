# <Domain Name> — Design

**Status:** Draft
**Last Updated:** YYYY-MM-DD

## Architecture

### Component / Hook Design

### Data Model

### Data Flow

## Decisions

<!-- One row per non-obvious decision. No TBD rows — resolve before implementation. -->

| # | Question | Options Considered | Decision | Rationale |
|---|----------|--------------------|----------|-----------|

## Failure Modes & Degradation Matrix

<!-- Mandatory. Cover at least Transport/Network, Concurrency/State, and Boundary & Payloads. Each entry must specify Failure Condition, Expected System Behavior, and Test Scenario (mapped to BDD test scenarios). -->

| Category | Failure Condition | Expected System Behavior | Test Scenario |
|---|---|---|---|
| Transport/Network | <timeouts, connection drop, 429 rate limit backoff> | <expected degradation/retry behavior> | <BDD scenario> |
| Concurrency/State | <race conditions, dirty reads, idempotent re-try> | <expected state consistency behavior> | <BDD scenario> |
| Boundary & Payloads | <nulls, empty collections, oversized payloads, schema violations> | <expected validation/rejection behavior> | <BDD scenario> |

## Test Scenarios

### Unit Tests

<!-- Behaviour-focused, not implementation-focused. One bullet per test case. -->

- <describe unit test scenario>

### BDD Scenarios

<!-- Map directly to acceptance criteria in requirements.md. -->

- **Scenario:** Given ... When ... Then ...

### BDD Traceability

<!-- Every BDD scenario must trace to at least one acceptance criterion. -->

| BDD Scenario | Component(s) / Module(s) | Notes |
|---|---|---|

### QA Scenarios

<!-- Observable behaviour tests. Must be executable without reading source code. -->

- <describe observable behaviour to verify>

## Edge Cases & Error Handling

- <describe edge case or error handling behaviour>
