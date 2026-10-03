"""Commit/push this prototype's changes, preserving the user's Git history."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "git@github.com:dhcy-Asion/MC-.git"
BRANCH = "main"


def git(*args):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(["git", *args], cwd=ROOT, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"git {args[0]} failed")
    return result.stdout.strip()


def write_status(data):
    path = ROOT / "runtime/github-sync-status.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"time_utc": datetime.now(timezone.utc).isoformat(), **data},
                               ensure_ascii=False, indent=2), encoding="utf-8")


def sync(message):
    if Path(git("rev-parse", "--show-toplevel")).resolve() != ROOT:
        raise RuntimeError("This directory is not the root of its own repository")
    if git("remote", "get-url", "origin") != REMOTE or git("remote", "get-url", "--push", "origin") != REMOTE:
        raise RuntimeError("Unexpected GitHub remote; synchronization refused")
    if git("branch", "--show-current") != BRANCH:
        raise RuntimeError("Expected main branch; synchronization refused")
    for marker in ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD", "rebase-merge", "rebase-apply"):
        if (ROOT / ".git" / marker).exists():
            raise RuntimeError("Git operation in progress; synchronization deferred")
    if git("ls-files", "--unmerged"):
        raise RuntimeError("Unresolved files; synchronization deferred")
    # The repository ignore rules omit local runtime, downloaded game files and saves.
    git("add", "--all", "--", ".")
    staged = git("diff", "--cached", "--name-only", "-z").split("\0")
    for name in filter(None, staged):
        if name.startswith(("runtime/", "backups/", "downloads/", "vendor/", "build/", "minecraft/.gradle/", "minecraft/build/")):
            raise RuntimeError(f"Local-only path was staged; synchronization refused: {name}")
        path = ROOT / name
        if path.exists() and path.stat().st_size > 50 * 1024 * 1024:
            raise RuntimeError(f"File exceeds the project's 50 MiB limit: {name}")
    committed = False
    if any(staged):
        git("commit", "-m", message)
        committed = True
    # A normal push rejects remote divergence and leaves the local commit intact.
    git("push", "origin", "HEAD:refs/heads/main")
    head = git("rev-parse", "HEAD")
    remote_head = git("ls-remote", "origin", "refs/heads/main").split()[0]
    if head != remote_head:
        raise RuntimeError("Remote changed after push; synchronization could not be verified")
    result = {"status": "synced", "committed": committed, "commit": head, "repository": "https://github.com/dhcy-Asion/MC-"}
    write_status(result)
    print(json.dumps(result, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", default="Sync CrimsonMC project changes")
    args = parser.parse_args()
    lock_path = ROOT / "runtime/github-sync.lock"
    lock_path.parent.mkdir(exist_ok=True)
    # A kernel file lock releases on process exit; concurrent sync calls do not commit twice.
    with lock_path.open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0"); lock.flush()
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print('{"status":"busy"}')
            return
        try:
            sync(args.message)
        except Exception as error:
            write_status({"status": "failed", "error": str(error)})
            print(str(error), file=sys.stderr)
            raise SystemExit(1)


if __name__ == "__main__":
    main()
