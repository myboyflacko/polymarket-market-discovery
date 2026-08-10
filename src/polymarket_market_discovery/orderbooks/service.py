from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from polymarket_market_discovery.core.db.lock import pipeline_lock
from polymarket_market_discovery.core.db.recovery import recover_orphaned_runs
from polymarket_market_discovery.core.time import ensure_utc
from polymarket_market_discovery.orderbooks.domain import OrderBookCollectionResult
from polymarket_market_discovery.orderbooks.parser import parse_orderbook_payload
from polymarket_market_discovery.orderbooks.repository import (
    complete_orderbook_collection_run,
    create_orderbook_collection_run,
    fail_orderbook_collection_run,
    snapshot_collectable_markets,
)
from polymarket_market_discovery.polymarket.client import get_polymarket_client
from polymarket_market_discovery.polymarket.params.orderbook import (
    OrderBookRequest,
    OrderBooksParams,
)


class OrderbookCollectionService:
    def __init__(self, *, batch_size: int = 50) -> None:
        if batch_size < 1 or batch_size > 500:
            raise ValueError("Orderbook batch size must be between 1 and 500")
        self.batch_size = batch_size

    async def run(self, *, now: datetime | None = None) -> OrderBookCollectionResult:
        started_at = ensure_utc(now or datetime.now(UTC))
        with pipeline_lock() as acquired:
            if not acquired:
                return OrderBookCollectionResult(
                    run_id=None,
                    status="skipped",
                    skip_reason="pipeline_locked",
                    generated_at=started_at,
                )
            recover_orphaned_runs(recovered_at=started_at)
            return await self._run_locked(started_at=started_at)

    async def _run_locked(self, *, started_at: datetime) -> OrderBookCollectionResult:
        run_id = _build_run_id(started_at)
        create_orderbook_collection_run(
            run_id=run_id,
            started_at=started_at,
            config_json={"batch_size": self.batch_size},
        )
        try:
            items = snapshot_collectable_markets(run_id=run_id, selected_at=started_at)
            client = get_polymarket_client()
            snapshots = []
            errors_by_token: dict[str, str] = {}
            for batch in _batches(items, self.batch_size):
                try:
                    response = await client.get_order_books(
                        OrderBooksParams(
                            root=[
                                OrderBookRequest(token_id=item.token_id)
                                for item in batch
                            ]
                        )
                    )
                    if not isinstance(response, list):
                        raise ValueError("CLOB books response must be a list")
                except Exception as exc:
                    for item in batch:
                        errors_by_token[item.token_id] = str(exc)
                    continue

                payload_by_token: dict[str, dict[str, Any]] = {}
                for payload in response:
                    if not isinstance(payload, dict):
                        continue
                    token_id = str(
                        payload.get("asset_id") or payload.get("token_id") or ""
                    )
                    if token_id:
                        if token_id in payload_by_token:
                            errors_by_token[token_id] = "CLOB returned duplicate token"
                        payload_by_token[token_id] = payload
                for item in batch:
                    if item.token_id in errors_by_token:
                        continue
                    payload = payload_by_token.get(item.token_id)
                    if payload is None:
                        errors_by_token[item.token_id] = "CLOB omitted requested token"
                        continue
                    payload_condition_id = payload.get("market")
                    if (
                        payload_condition_id is not None
                        and str(payload_condition_id) != item.condition_id
                    ):
                        errors_by_token[item.token_id] = "CLOB returned wrong market"
                        continue
                    try:
                        snapshots.append(
                            parse_orderbook_payload(
                                condition_id=item.condition_id,
                                token_id=item.token_id,
                                payload=payload,
                                generated_at=started_at,
                            )
                        )
                    except Exception as exc:
                        errors_by_token[item.token_id] = str(exc)

            status = complete_orderbook_collection_run(
                run_id=run_id,
                snapshots=snapshots,
                errors_by_token=errors_by_token,
                finished_at=datetime.now(UTC),
            )
        except Exception as exc:
            fail_orderbook_collection_run(
                run_id=run_id,
                finished_at=datetime.now(UTC),
                error_message=str(exc),
            )
            raise

        return OrderBookCollectionResult(
            run_id=run_id,
            status=status,
            selected_market_count=len({item.condition_id for item in items}),
            selected_token_count=len(items),
            success_count=len(snapshots),
            failure_count=len(errors_by_token),
            snapshots=snapshots,
            generated_at=started_at,
        )


def _build_run_id(generated_at: datetime) -> str:
    return f"{generated_at.strftime('%Y%m%dT%H%M%S%fZ')}-orderbooks"


def _batches[T](items: list[T], size: int) -> list[list[T]]:
    return [items[index : index + size] for index in range(0, len(items), size)]
