import re
from pathlib import Path


WORKFLOW = (Path(__file__).parents[2] / ".github/workflows/ci.yml").read_text()


def test_workflow_covers_expected_pull_request_events_and_targets() -> None:
    for expected in (
        "dev",
        "main",
        "opened",
        "synchronize",
        "reopened",
        "ready_for_review",
    ):
        assert re.search(rf"^\s+- {expected}$", WORKFLOW, re.MULTILINE)
    assert "workflow_dispatch:" in WORKFLOW
    assert "github.event.pull_request.draft == false" in WORKFLOW


def test_main_target_requires_dev_source() -> None:
    assert '"$BASE_REF" == "main" && "$HEAD_REF" == "dev"' in WORKFLOW
    assert "Only pull requests from dev may target main." in WORKFLOW


def test_workflow_runs_all_required_checks() -> None:
    for expected in (
        "pytest",
        "ruff check .",
        "ruff format --check .",
        "python -m build",
        "python -m twine check dist/*",
        "polymarket-market-discovery --help",
        "python -m pip_audit .",
        "docker compose config --quiet",
        "docker compose build scheduler cli",
        "aquasecurity/trivy-action@",
    ):
        assert expected in WORKFLOW
    assert WORKFLOW.count("if: always()") >= 2


def test_workflow_is_hardened_and_cached() -> None:
    for expected in (
        "permissions:\n  contents: read",
        "concurrency:",
        "cancel-in-progress: true",
        "cache: pip",
        "name: CI",
    ):
        assert expected in WORKFLOW


def test_actions_are_major_or_sha_pinned() -> None:
    actions = re.findall(r"^\s+uses: ([^\s#]+)", WORKFLOW, re.MULTILINE)
    assert actions
    assert all(re.search(r"@(v\d+|[0-9a-f]{40})$", action) for action in actions)


def test_container_smoke_is_read_only_and_offline() -> None:
    for expected in (
        "--network none",
        "--read-only",
        "--cap-drop ALL",
        "no-new-privileges",
    ):
        assert expected in WORKFLOW
