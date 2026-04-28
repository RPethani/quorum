"""End-to-end test of plan → run → events for the loop runner.

Uses two deliberations and two fake CLIs so we can verify parallelism
does not corrupt either file.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from quorum_conductor.core import plan
from quorum_conductor.events import EventLogger, read_events
from quorum_conductor.paths import WorkspacePaths
from quorum_conductor.transport.runner import run_items_sync
from quorum_conductor.workspace import InitOptions, init_workspace

GOOD_PROPOSAL_TEMPLATE = textwrap.dedent(
    """\
    ### [PROPOSAL] @{handle} · 2026-04-28T14:32:18Z

    ## Position

    Proposing.

    ## Reasoning

    Because.

    ## Assumptions

    none

    ## Risks I see

    none

    ## Alternatives I considered

    - none — obvious choice.

    ## Tagging

    - @human-rohan: review.
    """
)


def _make_cli(tmp_path: Path, name: str, output: str) -> Path:
    script = tmp_path / f"{name}.py"
    script.write_text(
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
    script.chmod(0o755)
    return script


def _participants(paths: WorkspacePaths, cli_a: Path, cli_b: Path) -> None:
    paths.participants.write_text(
        "| Handle | Display Name | CLI Command | Model | Transport | Quota | "
        "Permission Capability | Account Label | Health |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        f"| @cli-a | A | {sys.executable} {cli_a} | x | cli | 30/5 | fine_grained | (none) | green |\n"
        f"| @cli-b | B | {sys.executable} {cli_b} | x | cli | 30/5 | fine_grained | (none) | green |\n"
        "| @human-rohan | You | (manual) | n/a | manual | unlimited | n/a | (none) | n/a |\n",
        encoding="utf-8",
    )


def _seed_two_delibs(paths: WorkspacePaths) -> None:
    for i, handle in [(1, "@cli-a"), (2, "@cli-b")]:
        path = paths.deliberations / f"000{i}-test.md"
        path.write_text(
            "---\n"
            f'id: "000{i}"\n'
            "title: t\n"
            "status: OPEN\n"
            "protocol_version: 0.1\n"
            "roles:\n"
            f'  proposer: "{handle}"\n'
            "  critics: []\n"
            "  synthesizer: null\n"
            '  decider: "@human-rohan"\n'
            "tags: []\n"
            "---\n\n## Question\n\nq\n\n## Contributions\n\n## Open Questions\n\n## Decision\n",
            encoding="utf-8",
        )


def test_runner_processes_two_deliberations_in_one_pass(tmp_path: Path) -> None:
    paths = init_workspace(InitOptions(target=tmp_path / "quorum"))
    cli_a = _make_cli(tmp_path, "a", GOOD_PROPOSAL_TEMPLATE.format(handle="cli-a"))
    cli_b = _make_cli(tmp_path, "b", GOOD_PROPOSAL_TEMPLATE.format(handle="cli-b"))
    _participants(paths, cli_a, cli_b)
    _seed_two_delibs(paths)

    result = plan(paths)
    runnable = result.runnable()
    assert len(runnable) == 2

    events = EventLogger(paths.events_jsonl)
    results = run_items_sync(runnable, paths=paths, events=events, max_concurrent=2)

    assert all(r.status == "ok" for r in results), [r.error for r in results]
    bodies = [
        (paths.deliberations / "0001-test.md").read_text(encoding="utf-8"),
        (paths.deliberations / "0002-test.md").read_text(encoding="utf-8"),
    ]
    assert "[PROPOSAL] @cli-a" in bodies[0]
    assert "[PROPOSAL] @cli-b" in bodies[1]

    types = [e["type"] for e in read_events(paths.events_jsonl)]
    assert types.count("agent_started") == 2
    assert types.count("move_appended") == 2
    assert types.count("agent_completed") == 2
