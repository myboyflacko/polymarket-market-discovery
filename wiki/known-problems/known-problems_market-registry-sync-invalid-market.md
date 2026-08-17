---
title: Invalid market fails the complete market registry sync
created: 2026-08-17
updated: 2026-08-17
status: active
tags: [operations, system]
sources:
  - https://github.com/myboyflacko/polymarket-market-discovery/blob/08265bddbf6b836280b063bc393aafc2d846cde9/src/polymarket_market_discovery/markets/service.py#L43-L110
  - https://github.com/myboyflacko/polymarket-market-discovery/blob/08265bddbf6b836280b063bc393aafc2d846cde9/src/polymarket_market_discovery/markets/repository.py#L87-L230
  - https://github.com/myboyflacko/polymarket-market-discovery/blob/08265bddbf6b836280b063bc393aafc2d846cde9/src/polymarket_market_discovery/orderbooks/service.py#L51-L60
confidence: high
---

# Invalid market fails the complete market registry sync

## Status

Known and unresolved.

## Current behavior

A market registry run retrieves and validates every requested Gamma market
before completing the run. The repository then writes all valid payloads in one
database transaction. An exception for any individual market fails the complete
run, including otherwise valid markets.

Known triggers include:

- Gamma omits a requested condition ID from both the open and closed queries.
- A Gamma payload is malformed or does not contain exactly two distinct outcome
  tokens.
- A stored market receives a different token set, outcome, or outcome index.
- A token ID is already assigned to another market.

## Consequences

- No valid market from the affected run is created or updated.
- Input discovery runs remain unsynchronized and are retried in the next
  registry run, including the same invalid market.
- A persistently invalid market can therefore block all subsequent registry
  progress.
- Existing canonical market data remains available but becomes increasingly
  stale.
- Orderbook collection is skipped after the last completed registry sync exceeds
  the configured freshness threshold.

## Safety property

The all-or-nothing transaction prevents partial registry state and preserves the
last known good market universe. The problem affects progress and freshness, not
the atomicity of stored registry data.

## Operational detection and mitigation

The registry sync run is persisted with status `failed` and its error message.
Until per-market isolation exists, operators must identify the offending
condition ID, confirm the Gamma response and token identity, and restore a
successful registry run before the orderbook freshness window expires.

## Desired behavior

Valid markets should continue through the registry sync when another market is
invalid. Failures should be recorded per condition ID and retried or quarantined
without discarding valid updates. Discovery progress must remain traceable so a
partial run neither loses an invalid market nor retries every valid market
indefinitely.
