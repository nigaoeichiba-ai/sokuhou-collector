"""Call a writer / reader model without an API key: Claude Code's non-interactive mode (claude -p) and codex exec (both flat-rate plans).

A test (or a dry run) replaces the backend with set_backend(fn), fn(model, prompt, system) -> str.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

CODEX_MODEL = os.environ.get("KOBO_CODEX_MODEL", "gpt-5.6-sol")     # 'gpt-5.5' is refused with a ChatGPT account (2026-11-04)
CLAUDE_MODELS = ("haiku", "sonnet", "opus", "fable")
MODELS = CLAUDE_MODELS + ("codex",)
# the family decides who may read whose text: the reader is never of the writer's family
FAMILY = {m: "claude" for m in CLAUDE_MODELS} | {"codex": "codex"}


def _claude_exe() -> str:
    for c in (os.environ.get("KOBO_CLAUDE"), shutil.which("claude"), str(Path.home() / ".local" / "bin" / "claude.exe")):
        if c and Path(c).exists():
            return c
    raise RuntimeError("claude CLI not found (set KOBO_CLAUDE)")


def _codex_exe() -> str:
    c = os.environ.get("KOBO_CODEX") or shutil.which("codex")
    if not c:
        raise RuntimeError("codex CLI not found (set KOBO_CODEX)")
    return c


def _run_claude(model: str, prompt: str, system: str | None, timeout: int) -> str:
    # an empty folder as the working directory: no CLAUDE.md, no project memory; --safe-mode: no skills/plugins/hooks; --tools "": text only
    with tempfile.TemporaryDirectory(prefix="kobo_") as tmp:
        cmd = [_claude_exe(), "-p", "--model", model, "--safe-mode", "--tools", "", "--no-session-persistence", "--output-format", "text"]
        if system:
            cmd += ["--system-prompt", system]
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=tmp, timeout=timeout)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"claude {model} failed ({r.returncode}): {(r.stderr or r.stdout)[-400:]}")
    return r.stdout.strip()


def _run_codex(prompt: str, system: str | None, timeout: int) -> str:
    with tempfile.TemporaryDirectory(prefix="kobo_") as tmp:
        out = Path(tmp) / "last.txt"
        text = (system + "\n\n" + prompt) if system else prompt
        cmd = [_codex_exe(), "exec", "-m", CODEX_MODEL, "--skip-git-repo-check", "-s", "read-only", "--ephemeral", "-C", tmp, "-o", str(out), "-"]
        r = subprocess.run(cmd, input=text, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=tmp, timeout=timeout)
        res = out.read_text(encoding="utf-8").strip() if out.exists() else ""
    if not res:
        raise RuntimeError(f"codex failed ({r.returncode}): {(r.stderr or r.stdout)[-400:]}")
    return res


def _real(model: str, prompt: str, system: str | None = None, timeout: int = 900) -> str:
    if model == "codex":
        return _run_codex(prompt, system, timeout)
    if model in CLAUDE_MODELS:
        return _run_claude(model, prompt, system, timeout)
    raise ValueError(f"unknown model {model}")


_backend = _real


def set_backend(fn) -> None:
    global _backend
    _backend = fn or _real


def call(model: str, prompt: str, system: str | None = None, retries: int = 1) -> str:
    """One model call; one retry on a failure (a usage limit or a dropped process)."""
    last = None
    for i in range(retries + 1):
        try:
            return _backend(model, prompt, system)
        except Exception as e:          # noqa: BLE001  (the message goes to the record)
            last = e
            if i < retries:
                time.sleep(5)
    raise RuntimeError(str(last))


def other_family(model: str, prefer: str = "codex") -> str:
    """A reader for a text written by `model`: `prefer` when it is of another family, else the strongest model of the other family."""
    if FAMILY.get(prefer) != FAMILY.get(model):
        return prefer
    return "opus" if FAMILY.get(model) == "codex" else "codex"
