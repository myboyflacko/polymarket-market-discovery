from pathlib import Path
from types import SimpleNamespace

import pytest

from polymarket_market_discovery import cli


def test_cli_exposes_all_three_layers_and_all() -> None:
    parser = cli.build_parser()

    for service in ("discovery", "markets", "orderbooks", "all"):
        assert parser.parse_args(["run", service]).service == service

    schedule_args = parser.parse_args(["schedule"])
    assert (schedule_args.discovery_interval, schedule_args.markets_interval) == (900, 900)
    assert schedule_args.orderbooks_interval == 300
    with pytest.raises(SystemExit):
        parser.parse_args(["schedule", "all"])


def test_manual_orderbooks_registry_age_can_be_overridden() -> None:
    parser = cli.build_parser()
    assert parser.parse_args(["run", "orderbooks"]).market_registry_max_age_seconds == 1800
    args = parser.parse_args(
        ["run", "orderbooks", "--market-registry-max-age-seconds", "60"]
    )
    assert args.market_registry_max_age_seconds == 60


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


def test_run_all_dispatches_to_pipeline_coordinator(monkeypatch, capsys) -> None:
    calls: list[str] = []

    class Coordinator:
        async def run_once(self):
            calls.append("pipeline")
            return SimpleNamespace(
                status="partial", discovery=None, markets=None, orderbooks=None,
                errors={"discovery": "unavailable"},
            )

    monkeypatch.setattr(cli, "build_pipeline_coordinator", lambda args, *, scheduled: Coordinator())

    assert cli.main(["run", "all"]) == 0
    assert calls == ["pipeline"]
    assert "Pipeline partial" in capsys.readouterr().out


def test_scheduler_derives_registry_age_from_market_interval(monkeypatch) -> None:
    captured: list[tuple[int, int]] = []
    async def run(**kwargs):
        return None
    service = SimpleNamespace(run=run)
    monkeypatch.setattr(cli, "build_discovery_service", lambda names: service)
    monkeypatch.setattr(cli, "build_market_service", lambda size: service)
    monkeypatch.setattr(
        cli, "build_orderbook_service",
        lambda size, max_age: captured.append((size, max_age)) or service,
    )
    args = cli.build_parser().parse_args(["schedule", "--markets-interval", "120"])
    cli.build_pipeline_coordinator(args, scheduled=True)
    assert captured == [(50, 240)]


def test_container_runtime_uses_coordinator_command() -> None:
    root = Path(__file__).resolve().parents[1]
    assert 'CMD ["polymarket-market-discovery", "schedule"]' in (root / "Dockerfile").read_text()
    assert 'command: ["polymarket-market-discovery", "schedule"]' in (root / "docker-compose.yml").read_text()
