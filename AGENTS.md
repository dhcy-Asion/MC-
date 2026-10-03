# Project instructions

This repository is the Crimson Desert × Minecraft prototype. The user's active
working copy is the desktop `CrimsonMC` directory, attached to
`https://github.com/dhcy-Asion/MC-`. Do project work in this repository rather than
the earlier copy under Desktop/Git.

## 每次 AI 修改结束时上传

开始修改前阅读 README.md 和 CHANGELOG.md。用户已明确授权：每次完成项目修改并
执行必要验证后，提交并上传到 GitHub；不使用定时任务或后台监控上传。

每次修改任务结束前必须：

1. 检查实际改动，完成相关验证，如实记录通过、失败或未验证的结果。
2. 在 CHANGELOG.md 追加当天日期、具体修改内容和验证结果，不编造已完成的功能。
3. 从本仓库执行 `python tools/sync_github.py --message "具体说明本次修改内容"`。
   提交说明应明确描述改动，不使用只有“更新”“同步”含义的笼统说明。
4. 确认推送结果，在最终答复说明修改内容、验证结果及 GitHub 提交链接。

上传失败时保留本地提交和文件，报告原因，不得称已上传成功。用户当次明确要求
不上传时，以当次要求为准。只有咨询、查看而没有文件修改时，不创建无意义提交。
不要通过更改远端或分支绕过上传失败，不重新创建定时上传任务。

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
