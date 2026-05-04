"""Pluggable remediation suggestions for participant CLI failures.

Some CLIs return non-zero with stderr that hints at a fix the user
needs to take (Gemini's "not in a trusted directory" sandbox prompt
is the canonical example). Without this module, the user has to
context-switch to a terminal to fix it. With it, the dispatcher
attaches a structured `Remediation` to the error, the UI surfaces
it as an inline action button next to the failing message, and one
click runs the fix server-side.

Adding a new rule:

  1. Write `_match` and `_apply` functions for the new error.
  2. Append a `RemediationRule` to `_RULES`.
  3. The transport adapter calls `detect()` on every non-zero exit;
     the API surfaces matched remediations to the UI; the UI POSTs
     to `/api/canvas/remediations/apply` to run `apply()`.

Each rule is keyed by a stable `id` so the UI can display a
human-readable title/description without round-tripping to derive
them.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class RemediationError(RuntimeError):
    """Raised when an `apply` step can't complete cleanly."""


@dataclass(frozen=True)
class Remediation:
    """A suggested fix attached to a failed invocation.

    Carries everything the UI needs to render a one-line action
    card: the human-readable title + description, plus the IDs the
    server needs to run the action (`id` + the failing `handle`).
    """

    id: str
    title: str
    description: str
    handle: str


@dataclass(frozen=True)
class RemediationRule:
    id: str
    title: str
    description: str
    match: Callable[[str, str], bool]
    apply: Callable[[Path, str], str]


# ---------------------------------------------------------------------- #
# Public API
# ---------------------------------------------------------------------- #


def detect(handle: str, stderr: str) -> Remediation | None:
    """Walk the rule list, return the first match (if any)."""
    for rule in _RULES:
        if rule.match(handle, stderr):
            return Remediation(
                id=rule.id,
                title=rule.title,
                description=rule.description,
                handle=handle,
            )
    return None


def apply(remediation_id: str, workspace: Path, handle: str) -> str:
    """Run the named rule's `apply` step. Returns a summary string."""
    rule = next((r for r in _RULES if r.id == remediation_id), None)
    if rule is None:
        raise RemediationError(f"unknown remediation: {remediation_id!r}")
    return rule.apply(workspace, handle)


# ---------------------------------------------------------------------- #
# Rules
# ---------------------------------------------------------------------- #


def _gemini_trust_match(handle: str, stderr: str) -> bool:
    """Gemini CLI: `not running in a trusted directory`."""
    if "gemini" not in handle.lower():
        return False
    text = stderr.lower()
    return "trusted directory" in text or "trust this directory" in text


def _gemini_trust_apply(workspace: Path, handle: str) -> str:
    """Append ``--skip-trust`` to the participant's CLI command.

    This is the one fix that's guaranteed to work without poking at
    Gemini's internal config files. The user keeps the trust check
    in every other directory; only this workspace's invocations
    skip it.
    """
    pmd = workspace / "registers" / "participants.md"
    if not pmd.is_file():
        raise RemediationError("participants.md not found in this workspace")

    target_handle = handle if handle.startswith("@") else f"@{handle}"
    text = pmd.read_text(encoding="utf-8")
    out_lines: list[str] = []
    edited = False
    for raw in text.splitlines(keepends=False):
        if not edited and _row_matches_handle(raw, target_handle):
            new_row = _inject_flag(raw, "--skip-trust")
            if new_row != raw:
                out_lines.append(new_row)
                edited = True
                continue
        out_lines.append(raw)

    if not edited:
        raise RemediationError(
            f"could not locate {target_handle} in participants.md, "
            "or `--skip-trust` is already present"
        )

    pmd.write_text(
        "\n".join(out_lines) + ("\n" if text.endswith("\n") else ""),
        encoding="utf-8",
    )
    return f"Added --skip-trust to {target_handle}'s CLI command. You can resend now."


def _row_matches_handle(line: str, handle: str) -> bool:
    """Is `line` the table row for `handle`?

    Tolerates variable whitespace and the optional leading pipe.
    """
    stripped = line.lstrip()
    if not stripped.startswith("|"):
        return False
    # First non-empty cell after the leading pipe is the handle.
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    return bool(cells) and cells[0] == handle


def _inject_flag(line: str, flag: str) -> str:
    """Append `flag` to the CLI Command cell (3rd column) of a
    participants.md table row.

    Returns `line` unchanged if the flag is already present, or if
    the line doesn't have the expected pipe layout.
    """
    cells = line.split("|")
    # Layout: '' | handle | display | cli | model | ... | ''
    if len(cells) < 5:
        return line
    cmd = cells[3]
    if flag in cmd:
        return line
    leading_ws = cmd[: len(cmd) - len(cmd.lstrip())]
    trailing_ws = cmd[len(cmd.rstrip()) :]
    cells[3] = f"{leading_ws}{cmd.strip()} {flag}{trailing_ws}"
    return "|".join(cells)


def _codex_trust_match(handle: str, stderr: str) -> bool:
    """Codex CLI: ``Not inside a trusted directory and --skip-git-repo-check was not specified``."""
    if "codex" not in handle.lower():
        return False
    text = stderr.lower()
    return "not inside a trusted directory" in text or "--skip-git-repo-check" in text


def _codex_trust_apply(workspace: Path, handle: str) -> str:
    """Append ``--skip-git-repo-check`` to the participant's CLI command.

    Same surgical fix as `_gemini_trust_apply`: edit the cli_command
    cell so future invocations carry the flag. Other directories
    keep Codex's git-repo check intact.
    """
    pmd = workspace / "registers" / "participants.md"
    if not pmd.is_file():
        raise RemediationError("participants.md not found in this workspace")

    target_handle = handle if handle.startswith("@") else f"@{handle}"
    text = pmd.read_text(encoding="utf-8")
    out_lines: list[str] = []
    edited = False
    for raw in text.splitlines(keepends=False):
        if not edited and _row_matches_handle(raw, target_handle):
            new_row = _inject_flag(raw, "--skip-git-repo-check")
            if new_row != raw:
                out_lines.append(new_row)
                edited = True
                continue
        out_lines.append(raw)

    if not edited:
        raise RemediationError(
            f"could not locate {target_handle} in participants.md, "
            "or `--skip-git-repo-check` is already present"
        )

    pmd.write_text(
        "\n".join(out_lines) + ("\n" if text.endswith("\n") else ""),
        encoding="utf-8",
    )
    return f"Added --skip-git-repo-check to {target_handle}'s CLI command. You can resend now."


def _is_rosetta() -> bool:
    """Are we running an x86_64 Python on Apple Silicon (arm64) hardware?

    This is the silent kill for any participant CLI whose native helper
    is platform-tagged: child processes inherit the conductor's x86_64
    arch via Rosetta, then fail to find their arm64-tagged helper.
    """
    import platform

    if platform.system() != "Darwin":
        return False
    interp = platform.machine()  # the running interpreter's arch
    try:
        # `uname -m` reflects the kernel's native arch; on Apple Silicon
        # this is "arm64" even when the calling process is x86_64.
        kernel = subprocess.run(
            ["uname", "-m"], capture_output=True, text=True, timeout=2, check=False
        ).stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return kernel == "arm64" and interp == "x86_64"


def _codex_arch_mismatch_match(handle: str, stderr: str) -> bool:
    """Codex CLI: missing-binary error caused by Rosetta arch mismatch.

    The user's terminal codex works fine because the shell is arm64;
    the conductor's child inherits x86_64 because the conductor venv
    was bootstrapped with an Intel Python, and codex looks for the
    x64-tagged native helper (which arm64 npm never installed).

    Distinguished from the plain ``codex-missing-binary`` rule by
    actually inspecting the running process's arch — if we're on
    Apple Silicon and running x86_64, this is the cause, not a
    half-finished npm install.
    """
    if "codex" not in handle.lower():
        return False
    text = stderr.lower()
    if "missing optional dependency" not in text or "@openai/codex" not in text:
        return False
    return _is_rosetta()


def _codex_arch_mismatch_apply(_workspace: Path, _handle: str) -> str:
    """Surface the arch-fix recipe.

    We can't fix this from inside the running conductor — the venv's
    Python interpreter is what's wrong, and replacing it requires the
    process to exit. So this remediation's ``apply`` returns the exact
    commands to run instead; the UI renders multi-line summaries as a
    monospace block so the user can copy-paste.
    """
    return (
        "The conductor is running under Rosetta (x86_64) on Apple Silicon, "
        "so child processes can't find their arm64 native helpers.\n\n"
        "Fix it from your terminal:\n\n"
        "    # 1. Make sure uv itself is arm64\n"
        "    file $(which uv)\n"
        "    # If x86_64, reinstall:\n"
        "    curl -LsSf https://astral.sh/uv/install.sh | sh\n\n"
        "    # 2. Rebuild the conductor venv with arm64 Python\n"
        "    pkill -f 'quorum_conductor.*serve'\n"
        "    cd <quorum-repo>/conductor\n"
        "    rm -rf .venv\n"
        "    uv sync --python 3.12\n\n"
        "    # 3. Restart the conductor from source\n"
        "    uv run python -m quorum_conductor serve --path <workspace>\n\n"
        "Verify: file .venv/bin/python should report arm64."
    )


def _codex_missing_binary_match(handle: str, stderr: str) -> bool:
    """Codex CLI: ``Missing optional dependency @openai/codex-<plat>``.

    Plain version — runs *after* the arch-mismatch rule above, so by
    the time we reach here we know the cause is a half-finished npm
    install rather than a Rosetta arch trap.
    """
    if "codex" not in handle.lower():
        return False
    text = stderr.lower()
    return "missing optional dependency" in text and "@openai/codex" in text


def _codex_missing_binary_apply(_workspace: Path, _handle: str) -> str:
    """Reinstall the global Codex CLI via ``npm install -g``.

    The Codex CLI installs platform-specific subpackages (e.g.
    ``@openai/codex-darwin-x64``) as optional dependencies; partial
    installs leave a working `codex` shim that fails at runtime
    with a clear "missing optional dependency" message. Re-running
    the global install pulls the right binary for this machine.
    """
    try:
        result = subprocess.run(
            ["npm", "install", "-g", "@openai/codex"],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except FileNotFoundError as e:
        raise RemediationError(
            "`npm` is not on PATH for the conductor process. "
            "Install Node.js + npm, or run `npm install -g @openai/codex` "
            "manually in your terminal."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise RemediationError("`npm install` timed out after 3 minutes.") from e

    if result.returncode != 0:
        combined = (result.stderr or "") + "\n" + (result.stdout or "")
        if _is_eacces(combined):
            raise RemediationError(
                "Your global npm prefix needs root write permission. "
                "Run this in your terminal once:\n\n"
                "    sudo npm install -g @openai/codex\n\n"
                "Or, to avoid sudo for future installs, point npm at a "
                "user-writable prefix:\n"
                "    mkdir -p ~/.npm-global\n"
                "    npm config set prefix '~/.npm-global'\n"
                "    echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.zshrc"
            )
        excerpt = (result.stderr or result.stdout or "").strip()[:200]
        raise RemediationError(
            f"`npm install -g @openai/codex` failed: {excerpt or '(no output)'}"
        )

    return "Reinstalled Codex globally. You can resend now."


def _is_eacces(text: str) -> bool:
    """Spot npm's permission-denied output in any of its surface forms."""
    lower = text.lower()
    return (
        "eacces" in lower
        or "permission denied" in lower
        or "operation not permitted" in lower
    )


_RULES: list[RemediationRule] = [
    RemediationRule(
        id="gemini-trust",
        title="Trust this workspace for Gemini",
        description=(
            "Adds `--skip-trust` to @gemini's CLI command in "
            "registers/participants.md so Gemini can read canvas.md "
            "and artifacts/. Other directories keep Gemini's trust "
            "check intact."
        ),
        match=_gemini_trust_match,
        apply=_gemini_trust_apply,
    ),
    RemediationRule(
        id="codex-trust",
        title="Trust this workspace for Codex",
        description=(
            "Adds `--skip-git-repo-check` to @codex's CLI command in "
            "registers/participants.md so Codex runs in directories "
            "that aren't git repos. Other directories keep Codex's "
            "trust check intact."
        ),
        match=_codex_trust_match,
        apply=_codex_trust_apply,
    ),
    RemediationRule(
        id="codex-arch-mismatch",
        title="Conductor is running under Rosetta",
        description=(
            "On Apple Silicon, an x86_64 conductor process makes Codex "
            "look for a native helper that arm64 npm never installed. "
            "Rebuild the conductor's venv with arm64 Python and restart."
        ),
        match=_codex_arch_mismatch_match,
        apply=_codex_arch_mismatch_apply,
    ),
    RemediationRule(
        id="codex-missing-binary",
        title="Reinstall Codex CLI",
        description=(
            "Codex's platform-specific binary is missing — runs "
            "`npm install -g @openai/codex` to put it back. Takes "
            "around 30 seconds. Requires `npm` on the conductor's "
            "PATH and global-npm write permission."
        ),
        match=_codex_missing_binary_match,
        apply=_codex_missing_binary_apply,
    ),
]
