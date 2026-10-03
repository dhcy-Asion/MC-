# Project instructions

This repository is the Crimson Desert × Minecraft prototype. The user's active
working copy is the desktop `CrimsonMC` directory, attached to
`https://github.com/dhcy-Asion/MC-`. Do project work in this repository rather than
the earlier copy under Desktop/Git.

The user explicitly requested that future project changes automatically sync to
GitHub. After completing and verifying each requested project change, run
`python tools/sync_github.py --message "Describe the finished change"` from this
repository and report failures. A scheduled local heartbeat also calls the script
to catch manual edits. Do not change its remote or branch to bypass a failure.

Keep all personal saves, backups, runtime data, credentials, downloaded game
binaries and build caches ignored. Update the checked-in `artifacts/` binaries
only after a successful relevant build, and preserve third-party notices. Do not
upload the Crimson Desert installation or Minecraft server/client binaries.

Never force-push, reset user changes, or resolve remote divergence automatically.
The sync script commits local changes then uses a normal fast-forward push. If
remote commits diverge, report the condition and preserve both histories.

The game is an experimental integration: genuine Minecraft 1.21.1 owns inventory,
recipes, blocks and drops; native blue cubes are collision proxies. Do not describe
it as a complete Minecraft client or a full game port. Game-side runtime checks
may change experimental inventory; use them only when relevant and describe their
effects. Keep startup, restart and uninstall operations scoped to this prototype.
