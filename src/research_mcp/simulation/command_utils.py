"""Command and path utilities for local simulation tools."""

from __future__ import annotations

import asyncio
import shlex
from pathlib import Path
from typing import Any

SHELL_CONTROL_CHARS = ("|", "&", ";", "<", ">", "`", "$(", "\n", "\r")
COMSOL_MODEL_SUFFIXES = {".mph"}


def require_file(file_path: str) -> Path:
    path = Path(file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return path


def validate_executable_command(command: str) -> str:
    if not command or not command.strip():
        raise ValueError("Executable command cannot be empty")
    if any(token in command for token in SHELL_CONTROL_CHARS):
        raise ValueError("Executable command cannot contain shell control characters")
    stripped = command.strip()
    path_candidate = Path(stripped.strip('"')).expanduser()
    if path_candidate.exists() and path_candidate.is_file():
        return str(path_candidate.resolve())
    try:
        parts = shlex.split(stripped)
    except ValueError as exc:
        raise ValueError("Executable command is not a valid command string") from exc
    if len(parts) != 1:
        raise ValueError("Executable command must be a single executable path or command name")
    return parts[0]


def split_extra_args(extra_args: str) -> list[str]:
    if not extra_args:
        return []
    if any(token in extra_args for token in SHELL_CONTROL_CHARS):
        raise ValueError("Extra arguments cannot contain shell control characters")
    try:
        return shlex.split(extra_args)
    except ValueError as exc:
        raise ValueError("Extra arguments are not a valid argument string") from exc


def resolve_working_dir(working_dir: str, default: Path) -> Path:
    path = Path(working_dir).expanduser().resolve() if working_dir else default.resolve()
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Working directory not found: {path}")
    return path


def resolve_output_path(
    output_path: str,
    default_dir: Path | None = None,
    allowed_suffixes: set[str] | None = None,
    create_parent: bool = True,
) -> Path:
    raw_path = Path(output_path).expanduser()
    if default_dir and not raw_path.is_absolute():
        path = (default_dir / raw_path).resolve()
    else:
        path = raw_path.resolve()
    suffix = path.suffix.lower()
    if allowed_suffixes is not None and suffix not in allowed_suffixes:
        allowed = ", ".join(sorted(allowed_suffixes))
        raise ValueError(f"Unsupported output suffix '{suffix}'. Allowed suffixes: {allowed}")
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def run_command(args: list[str], cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    if not cwd.exists() or not cwd.is_dir():
        raise FileNotFoundError(f"Working directory not found: {cwd}")
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {
            "status": "timeout",
            "command": args,
            "cwd": str(cwd),
            "timeout_seconds": timeout_seconds,
        }
    return {
        "status": "ok" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "command": args,
        "cwd": str(cwd),
        "stdout": stdout.decode(errors="replace")[-8000:],
        "stderr": stderr.decode(errors="replace")[-8000:],
    }
