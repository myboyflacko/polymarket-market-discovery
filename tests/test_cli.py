from types import SimpleNamespace

import pytest

from polymarket_market_discovery import cli


def test_cli_exposes_all_three_layers_and_all() -> None:
    parser = cli.build_parser()

    for service in ("discovery", "markets", "orderbooks", "all"):
        assert parser.parse_args(["run", service]).service == service
        assert parser.parse_args(["schedule", service]).service == service


def test_strategy_option_is_repeatable() -> None:
    args = cli.build_parser().parse_args(
        [
            "run",
            "discovery",
            "--strategy",
            "whale_leaderboard_intersection",
            "--strategy",
            "whale_leaderboard_intersection",
        ]
    )

    assert args.strategy == [
        "whale_leaderboard_intersection",
        "whale_leaderboard_intersection",
    ]


def test_run_all_is_sequential_and_fail_fast(monkeypatch, capsys) -> None:
    calls: list[str] = []

    class Service:
        def __init__(self, name: str, result: SimpleNamespace) -> None:
            self.name = name
            self.result = result

        async def run(self):
            calls.append(self.name)
            return self.result

    monkeypatch.setattr(
        cli,
        "build_discovery_service",
        lambda names: Service(
            "discovery",
            SimpleNamespace(
                status="completed",
                run_id="d",
                discovered_market_count=1,
                observation_count=1,
            ),
        ),
    )
    monkeypatch.setattr(
        cli,
        "build_market_service",
        lambda size: Service(
            "markets",
            SimpleNamespace(
                status="skipped",
                run_id=None,
                checked_market_count=0,
                created_market_count=0,
                updated_market_count=0,
            ),
        ),
    )
    monkeypatch.setattr(
        cli,
        "build_orderbook_service",
        lambda size: pytest.fail("orderbooks must not run after skipped markets"),
    )

    assert cli.main(["run", "all"]) == 0
    assert calls == ["discovery", "markets"]
    assert "Markets skipped" in capsys.readouterr().out
