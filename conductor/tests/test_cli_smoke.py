"""4j integration sweep — exercise the public CLI end-to-end.

We invoke `quorum_conductor.cli:main` directly rather than spawning a
subprocess, so the test stays fast and assertions can read state at
each step. Coverage:

  init → plan (creates seed) → step (runs one fake invocation)
        → status (cost shows up) → archive

This is the closest thing we have to a vertical-slice exercise from
the conductor side. The real vertical slice (Phase 5) drives the same
flow with a real CLI agent.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from quorum_conductor.cli import main
from quorum_conductor.events import read_events

GOOD_PROPOSAL = textwrap.dedent(
    """\
    ### [PROPOSAL] @fake-cli · 2026-04-29T01:00:00Z

    ## Position

    A baseline manifest is enough for v1.

    ## Reasoning

    Two artifacts cover the SaaS scope.

    ## Assumptions

    none

    ## Risks I see

    none

    ## Alternatives I considered

    - One mega-doc — set aside for cohesion reasons.

    ## Tagging

    - @human-rohan: review.
    """
)


def _write_fake_cli(path: Path, *, output: str = GOOD_PROPOSAL) -> Path:
    path.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import sys
            sys.stdin.read()
            sys.stdout.write({output!r})
            """
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _write_participants(workspace: Path, fake_cli: Path) -> None:
    (workspace / "registers" / "participants.md").write_text(
        "| Handle | Display Name | CLI Command | Model | Transport | Quota | "
        "Permission Capability | Account Label | Health |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        f"| @fake-cli | Fake | {sys.executable} {fake_cli} | fake | cli | 30/5 | "
        "fine_grained | (none) | green |\n"
        "| @human-rohan | You | (manual) | n/a | manual | unlimited | n/a | (none) | n/a |\n",
        encoding="utf-8",
    )


def test_cli_full_flow(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    workspace = tmp_path / "demo"
    fake = _write_fake_cli(tmp_path / "fake.py")

    # init
    assert main(["init", str(workspace)]) == 0
    assert (workspace / "state.yaml").is_file()
    capsys.readouterr()  # discard

    _write_participants(workspace, fake)

    # plan — should bootstrap the seed deliberation and show one item.
    assert main(["plan", "--path", str(workspace)]) == 0
    plan_out = capsys.readouterr().out
    assert "opened seed deliberation" in plan_out
    assert "#0001" in plan_out

    # step — runs one invocation.
    rc = main(["step", "--path", str(workspace)])
    assert rc == 0, capsys.readouterr().out
    step_out = capsys.readouterr().out
    assert "appended : yes" in step_out

    # The deliberation file now contains the move.
    delib = workspace / "deliberations" / "0001-outcome-manifest.md"
    assert "[PROPOSAL] @fake-cli" in delib.read_text(encoding="utf-8")

    # status — cost section is rendered.
    assert main(["status", "--path", str(workspace)]) == 0
    status_out = capsys.readouterr().out
    assert "cost" in status_out
    assert "spent" in status_out
    assert "$50.00" in status_out  # default ceiling
    assert "$0.00" not in status_out or "/ $50.00" in status_out

    # events.jsonl carries the right sequence.
    events = list(read_events(workspace / "runtime" / "events" / "events.jsonl"))
    types = [e["type"] for e in events]
    assert "routing_decision" in types
    assert "agent_started" in types
    assert "move_appended" in types
    assert "agent_completed" in types

    # archive (one-way for v1; unarchive is intentionally not surfaced
    # via CLI — see docs-specs/system-flow-stages.md Q6).
    assert main(["archive", "--path", str(workspace), "--reason", "test"]) == 0
    capsys.readouterr()
    assert main(["status", "--path", str(workspace)]) == 0
    out = capsys.readouterr().out
    assert "ARCHIVED" in out


def test_cli_run_respects_cost_ceiling(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    workspace = tmp_path / "ws"
    fake = _write_fake_cli(tmp_path / "fake.py")
    assert main(["init", str(workspace)]) == 0
    capsys.readouterr()
    _write_participants(workspace, fake)

    # Slam the ceiling down to a dollar's worth so a single fake invocation
    # cannot fit. Add @fake-cli to the existing usd_per_invocation block.
    defaults_path = workspace / "registers" / "routing-defaults.yaml"
    body = defaults_path.read_text(encoding="utf-8")
    if "usd_per_invocation:" in body:
        body = body.replace(
            "usd_per_invocation:",
            "usd_per_invocation:\n  '@fake-cli': 1.0",
            1,
        )
    else:
        body += "\nusd_per_invocation:\n  '@fake-cli': 1.0\n"
    defaults_path.write_text(body, encoding="utf-8")

    config_path = workspace / "config.yaml"
    config_body = config_path.read_text(encoding="utf-8").replace(
        "ceiling_usd: 50.0", "ceiling_usd: 0.50"
    )
    config_path.write_text(config_body, encoding="utf-8")

    # First step should run (cumulative spend was $0 ≤ $0.50).
    assert main(["step", "--path", str(workspace)]) == 0
    capsys.readouterr()

    # Second step is blocked by the ceiling — current spend is $1.00 ≥ $0.50.
    rc = main(["step", "--path", str(workspace)])
    out = capsys.readouterr().out
    assert rc == 2, out
    assert "cost ceiling reached" in out
