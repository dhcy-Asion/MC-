"""Exercise synchronization against temporary local Git repos, never GitHub."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sync_under_test", ROOT / "tools/sync_github.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def git(cwd, *args):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, encoding="utf-8").strip()


(ROOT / "runtime").mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="sync-check-", dir=ROOT / "runtime") as directory:
    base = Path(directory).resolve()
    base.relative_to((ROOT / "runtime").resolve())  # keep automatic cleanup in the ignored workspace
    bare, local, other = base / "remote.git", base / "local", base / "other"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(bare)], check=True, capture_output=True)
    subprocess.run(["git", "init", "--initial-branch=main", str(local)], check=True, capture_output=True)
    git(local, "config", "user.name", "Sync Check")
    git(local, "config", "user.email", "test@example.invalid")
    git(local, "remote", "add", "origin", str(bare))
    (local / ".gitignore").write_text("runtime/\nbackups/\n")
    (local / "example.txt").write_text("first\n")
    (local / "backups").mkdir()
    (local / "backups/save.txt").write_text("local-only")
    module.ROOT, module.REMOTE = local, str(bare)
    module.sync("Initial test")
    first = git(local, "rev-parse", "HEAD")
    assert git(bare, "rev-parse", "main") == first
    assert "backups/save.txt" not in git(local, "ls-files")
    module.sync("No change")
    assert git(local, "rev-parse", "HEAD") == first, "No-op created a duplicate commit"
    (local / "example.txt").write_text("second\n")
    module.sync("Second test")
    assert git(local, "rev-parse", "HEAD") != first
    subprocess.run(["git", "clone", str(bare), str(other)], check=True, capture_output=True)
    git(other, "config", "user.name", "Other Check")
    git(other, "config", "user.email", "other@example.invalid")
    (other / "other.txt").write_text("remote change\n")
    git(other, "add", "--all")
    git(other, "commit", "-m", "Remote test")
    git(other, "push", "origin", "main")
    remote_commit = git(bare, "rev-parse", "main")
    (local / "example.txt").write_text("diverged\n")
    try:
        module.sync("Local divergence test")
        raise AssertionError("Divergent push was accepted")
    except RuntimeError:
        pass
    assert git(bare, "rev-parse", "main") == remote_commit, "Remote history was overwritten"
    assert (local / "example.txt").read_text() == "diverged\n", "Local work was discarded"
    assert git(local, "log", "-1", "--format=%s") == "Local divergence test"
print("PASS: commit/push, ignored saves, unchanged no-op, divergence preserves both histories")
