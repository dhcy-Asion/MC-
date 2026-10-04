# Project instructions

This repository is the Crimson Desert × Minecraft prototype. The user's active
working copy is the desktop `CrimsonMC` directory, attached to
`https://github.com/dhcy-Asion/MC-`. Do project work in this repository rather than
the earlier copy under Desktop/Git.

## 开始工作与交接

新聊天先阅读本文件、[README.md](README.md)、[docs/architecture.md](docs/architecture.md)、
[docs/progress.md](docs/progress.md) 和 [CHANGELOG.md](CHANGELOG.md)，再查看实际 Git 状态和相关源码。
历史聊天、忽略目录中的研究脚本和进程地址不能作为唯一交接资料。

`docs/architecture.md` 描述已经存在的模块和接口；`docs/progress.md` 记录当前里程碑、
验收条件、检查结果、关键决策及下一步。用户需求细节保存在 `docs/steve-character.md`。
代码事实与文档不一致时，先查清实际行为，修正文档，不能用文档证明功能已经实现。

## 按可验证的里程碑开发

1. 开始前确认 `docs/progress.md` 中当前里程碑的范围、前置条件和验收标准。
   用户当次指令可以调整优先级；及时记录这一调整。
2. 每次只处理当前里程碑相关的代码。后续功能只记录计划，不能顺手改背包、战斗、
   角色或全局输入。用户最新选择先让背包独立可用：当前 M6a 为物品目录、整组领取、
   36 格选择与实际消耗；M2 原生角色研究保持未完成，不安装未验收的切换记录器。
3. 完成后运行相关检查，在进度文件写明日期、命令、结果、证据及未验证项，再标记完成。
   只读探针运行成功不等于第四角色创建成功；构建成功不等于游戏内行为验证成功。
4. 未达到验收标准时保留在进行中，记录具体障碍和下一项可执行检查，不能为了收尾
   把后续阶段或尚未实现的功能标为完成。
5. 对接口、存档格式、原生调用、角色身份和需求范围作出的关键决策，及时写入架构或
   进度文件，并注明依据。最终答复说明本里程碑结果及剩余限制。

## 模块边界与源码规则

- Minecraft 是材料、配方、方块和掉落的权威。桥接和原生 UI 不重复实现 MC 配方，
  不自行改库存后假装 MC 已接受。
- 原生调用必须在已验证的游戏线程机制中执行，网络请求不能阻塞渲染线程。
  原生排队返回的 UID／ticket 只表示受理，完成情况需要实际查询或验证。
- 项目维护的原生面板源码在 `red-side-patches/`；上游变化进入 `upstream.patch`。
  `vendor/` 是忽略的固定提交工作副本，不能只改 vendor 而遗漏可重建的补丁／准备步骤。
- API 或存档格式改动需要同步修改调用方、架构文档和迁移规则；保留已有实验材料和建筑。
  保存失败、超时及部分完成要显式处理，不能盲目重复消费材料的请求。
- 原生研究必须区分“静态候选”“只读观测”和“行为已验证”。先核对游戏版本及 SHA，
  再核对 RTTI、边界和回链；未知布局停止解释。找到函数签名不证明调用 ABI 或副作用。
- 新增第四角色必须保留原版三人身份，换装、生成 NPC 或绘制心形 HUD 均不能代替这一验收。
  不用虚构血量、库存或手持模型充当完成。新增依赖保留固定来源和许可证。

## 相关检查

只运行与当前改动有关的检查；文档和只读诊断阶段无需重启、安装游戏插件或改变 MC 材料。

| 改动 | 相关检查 |
| --- | --- |
| 文档／诊断 | 检查相对链接和 JSON；`python tools/check_character_probe.py`；Python 语法检查；已支持版本运行只读探针 |
| MC 规则 | `tools/build_minecraft.ps1` 构建；按变更运行 `tools/check_authority.py` 或新增有意义的规则检查 |
| 背包 | MC 构建；`python tools/check_inventory.py` 使用独立测试世界；`python tools/check_inventory_bridge.py`；`python tools/check_inventory_ui.py`；原生构建和游戏内面板检查 |
| 跨游戏方块同步 | `tools/check_bridge.py`；保存／重启改动再运行 `tools/check_restart.py` |
| 原生源码 | 准备固定上游、构建、补丁可重建检查及相关游戏内行为验证；更新插件前关闭游戏 |
| Git 同步脚本 | `python tools/check_sync.py`，使用其临时仓库，不重写用户仓库历史 |

运行中的验证可能改变实验材料或方块。先阅读脚本的前置条件与清理逻辑，保护用户建筑，
记录实际副作用。不要为不相关的文档修改运行会消费材料的检查。

## 每次 AI 修改结束时上传

用户已明确授权：每次完成项目修改并
执行必要验证后，提交并上传到 GitHub；不使用定时任务或后台监控上传。

每次修改任务结束前必须：

1. 检查实际改动，完成相关验证，如实记录通过、失败或未验证的结果。
2. 更新 docs/progress.md，并在 CHANGELOG.md 追加当天日期、具体修改内容和验证结果，
   不编造已完成的功能。
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
