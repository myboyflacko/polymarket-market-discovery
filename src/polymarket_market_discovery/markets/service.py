from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from polymarket_market_discovery.core.db.lock import pipeline_lock
from polymarket_market_discovery.core.db.recovery import recover_orphaned_runs
from polymarket_market_discovery.core.time import ensure_utc
from polymarket_market_discovery.markets.domain import (
    MarketRegistrySyncResult,
    MarketTokenPayload,
    PolymarketMarketPayload,
)
from polymarket_market_discovery.markets.repository import (
    complete_market_sync_run,
    create_market_sync_run,
    fail_market_sync_run,
    get_market_sync_input,
)
from polymarket_market_discovery.polymarket.client import get_polymarket_client


class MarketRegistryService:
    def __init__(self, *, batch_size: int = 100) -> None:
        if batch_size < 1 or batch_size > 100:
            raise ValueError("Gamma market batch size must be between 1 and 100")
        self.batch_size = batch_size

    async def run(self, *, now: datetime | None = None) -> MarketRegistrySyncResult:
        started_at = ensure_utc(now or datetime.now(UTC))
        with pipeline_lock() as acquired:
            if not acquired:
                return MarketRegistrySyncResult(
                    run_id=None,
                    status="skipped",
                    generated_at=started_at,
                    skip_reason="pipeline_locked",
                )
            recover_orphaned_runs(recovered_at=started_at)
            return await self._run_locked(started_at=started_at)

    async def _run_locked(self, *, started_at: datetime) -> MarketRegistrySyncResult:
        sync_input = get_market_sync_input()
        if not sync_input.discovery_run_ids and not sync_input.condition_ids:
            return MarketRegistrySyncResult(
                run_id=None,
                status="skipped",
                generated_at=started_at,
                skip_reason="no_markets_to_sync",
            )
        run_id = _build_run_id(started_at)
        create_market_sync_run(
            run_id=run_id,
            started_at=started_at,
            input_discovery_run_ids=sync_input.discovery_run_ids,
        )
        try:
            client = get_polymarket_client()
            payloads: list[PolymarketMarketPayload] = []
            for condition_batch in _batches(sync_input.condition_ids, self.batch_size):
                payloads.extend(
                    await _retrieve_market_batch(client, condition_batch)
                )
            created_count, updated_count = complete_market_sync_run(
                run_id=run_id,
                payloads=payloads,
                discovery_run_ids=sync_input.discovery_run_ids,
                checked_at=datetime.now(UTC),
            )
        except Exception as exc:
            fail_market_sync_run(
                run_id=run_id,
                finished_at=datetime.now(UTC),
                error_message=str(exc),
            )
            raise

        return MarketRegistrySyncResult(
            run_id=run_id,
            status="completed",
            input_discovery_run_ids=sync_input.discovery_run_ids,
            checked_market_count=len(payloads),
            created_market_count=created_count,
            updated_market_count=updated_count,
            generated_at=started_at,
        )


async def _retrieve_market_batch(
    client: Any, condition_ids: list[str]
) -> list[PolymarketMarketPayload]:
    open_rows = await client.get_gamma_markets(condition_ids, closed=False)
    payload_by_condition = _index_gamma_payloads(
        [parse_gamma_market(row) for row in open_rows], requested_ids=condition_ids
    )
    missing_ids = sorted(set(condition_ids) - payload_by_condition.keys())
    if missing_ids:
        closed_rows = await client.get_gamma_markets(missing_ids, closed=True)
        payload_by_condition.update(
            _index_gamma_payloads(
                [parse_gamma_market(row) for row in closed_rows],
                requested_ids=missing_ids,
            )
        )
        missing_ids = sorted(set(condition_ids) - payload_by_condition.keys())
        if missing_ids:
            raise ValueError(
                f"Gamma omitted requested markets: {', '.join(missing_ids)}"
            )
    return [payload_by_condition[condition_id] for condition_id in condition_ids]


def _index_gamma_payloads(
    payloads: list[PolymarketMarketPayload], *, requested_ids: list[str]
) -> dict[str, PolymarketMarketPayload]:
    unexpected_ids = sorted(
        {payload.condition_id for payload in payloads} - set(requested_ids)
    )
    if unexpected_ids:
        raise ValueError(
            f"Gamma returned unexpected markets: {', '.join(unexpected_ids)}"
        )

    indexed: dict[str, PolymarketMarketPayload] = {}
    for payload in payloads:
        existing = indexed.get(payload.condition_id)
        if existing is None:
            indexed[payload.condition_id] = payload
        elif existing == payload:
            raise ValueError(f"Gamma returned duplicate market {payload.condition_id}")
        else:
            raise ValueError(
                f"Gamma returned conflicting market {payload.condition_id}"
            )
    return indexed


def parse_gamma_market(row: dict[str, Any]) -> PolymarketMarketPayload:
    condition_id = required_string(row, "conditionId")
    token_ids = parse_string_list(row.get("clobTokenIds"), field="clobTokenIds")
    outcomes = parse_string_list(row.get("outcomes"), field="outcomes")
    if len(token_ids) != 2 or len(outcomes) != 2:
        raise ValueError(f"Market {condition_id} must have exactly two outcome tokens")
    if len(set(token_ids)) != 2 or len(set(outcomes)) != 2:
        raise ValueError(f"Market {condition_id} has duplicate outcome tokens")
    event_id = optional_string(row.get("eventId"))
    if event_id is None and isinstance(row.get("events"), list) and row["events"]:
        first_event = row["events"][0]
        if isinstance(first_event, dict):
            event_id = optional_string(first_event.get("id"))
    question = optional_string(row.get("question"))
    return PolymarketMarketPayload(
        condition_id=condition_id,
        event_id=event_id,
        slug=optional_string(row.get("slug")),
        title=optional_string(row.get("title")) or question,
        question=question,
        end_date=parse_datetime(row.get("endDate")),
        active=optional_bool(row.get("active")),
        closed=optional_bool(row.get("closed")),
        archived=optional_bool(row.get("archived")),
        enable_order_book=optional_bool(row.get("enableOrderBook")),
        tokens=[
            MarketTokenPayload(token_id=token_id, outcome=outcome, outcome_index=index)
            for index, (token_id, outcome) in enumerate(
                zip(token_ids, outcomes, strict=True)
            )
        ],
        raw_payload=row,
    )


def parse_string_list(value: Any, *, field: str) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Gamma field {field} must contain a JSON list") from exc
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"Gamma field {field} must be a list of strings")
    return value


def required_string(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None or str(value) == "":
        raise ValueError(f"Gamma market missing required field {key}")
    return str(value)


def optional_string(value: Any) -> str | None:
    return None if value is None or str(value) == "" else str(value)


def optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in {"true", "1"}:
            return True
        if value.lower() in {"false", "0"}:
            return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def parse_datetime(value: Any) -> datetime | None:
    if value is None or str(value) == "":
        return None
    text = str(value)
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text[:-1]).replace(tzinfo=UTC)
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(f"Invalid Gamma datetime: {value!r}") from exc


def _batches[T](items: list[T], size: int) -> list[list[T]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _build_run_id(generated_at: datetime) -> str:
    return f"{generated_at.strftime('%Y%m%dT%H%M%S%fZ')}-markets"
