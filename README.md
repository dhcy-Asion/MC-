# MC-：史蒂夫移民红沙

红色沙漠 × Minecraft 的第一版建造／合成实验原型。

仓库：[dhcy-Asion/MC-](https://github.com/dhcy-Asion/MC-)。当前开发目录为桌面的 `CrimsonMC`。

开发入口：[AGENTS.md](AGENTS.md) 规定开发和上传流程；
[模块架构与接口](docs/architecture.md) 说明已实现行为；
[当前状态与里程碑](docs/progress.md) 保存验收标准、证据和下一步。
本次 M1 建立文档与只读诊断基线，第四角色和背包后续修改尚未实现。

## 给 AI 的修改要求

使用 AI 修改本项目时，请先阅读本文件、[AGENTS.md](AGENTS.md)、架构及进度文件。
按可验证里程碑推进，只修改当前里程碑相关代码，完成后运行相关检查并更新进度。
用户已授权：**每次修改并完成必要验证后，执行一次 GitHub 提交与上传，并说明这次改了什么。无需定时上传。**

每次任务结束前，AI 必须完成以下步骤：

1. 检查本次改动，执行与改动有关的验证；记录实际结果，未验证的部分如实说明。
2. 更新 [docs/progress.md](docs/progress.md)，并在 [CHANGELOG.md](CHANGELOG.md) 追加本次修改的日期、具体修改内容及验证结果。
3. 执行 `python tools/sync_github.py --message "具体描述本次修改"`，将修改和记录一并提交、推送到 `main`。提交说明应写明改动，例如“修复方块恢复时重复生成”，不要只写“更新”或“同步”。
4. 向用户报告修改内容、验证结果和 GitHub 提交链接。上传失败时保留本地成果并说明原因，不得声称已上传。

没有文件改动的咨询或查看任务无需创建提交。若用户当次明确要求不上传，以当次要求为准。README 是约定说明；执行上传依赖 AI 遵循这些要求及本机 GitHub 登录可用。

已在这台电脑的红沙 **1.0.0.2976** 上跑通。红沙地图、人物和战斗继续运行，后台真实 Minecraft Java **1.21.1** 管理实验背包、原版合成配方、方块和拆除掉落。红沙使用原生一米蓝色网格实体显示这些方块并提供碰撞。

**这是可用的建造／合成实验，不是完整 MC 移植。** 暂无 MC 材质、客户端画面、红石、生物或完整生存玩法；几种材料目前外观相同。没有安装 PCL2 离线客户端，也不需要登录 MC 客户端来使用这个服务端原型。

## 从 GitHub 安装原型

需要 Windows、自己的红沙安装、Git 和 PATH 中可用的 Python 3。只在红沙 1.0.0.2976 验证；仓库不包含红沙本体、MC 游戏程序、个人存档或运行缓存。

```powershell
git clone https://github.com/dhcy-Asion/MC-.git CrimsonMC
cd CrimsonMC
powershell -NoProfile -ExecutionPolicy Bypass -File tools/prepare_environment.ps1 -AcceptMinecraftEula
powershell -NoProfile -ExecutionPolicy Bypass -File tools/install_red_side.ps1 -GameRoot "E:\SteamLibrary\steamapps\common\Crimson Desert"
.\"Start Prototype.cmd"
```

准备脚本下载并校验固定版本的 Java、Gradle 和 ASI 加载器，建立本机服务端配置，使用仓库中的编译插件。`-AcceptMinecraftEula` 表示接受 [Minecraft EULA](https://www.minecraft.net/eula)；已有实验存档、配置和 EULA 文件会保留。安装红沙插件前须退出红沙。

首次启动时 Gradle 下载官方 MC 和 Fabric 开发依赖，可能比后续启动慢。仓库中的 `artifacts/native/cdmodkit.asi` 和 `artifacts/minecraft/crimsonmc-authority-0.1.0.jar` 是本原型自己的构建成果，第三方声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

需要从源码重编译原生插件时，先运行准备脚本的 `-SourceBuild` 选项取得固定提交并应用补丁，再用 MSYS2 UCRT64 GCC 和 `python tools/build_worldbuilder.py` 构建。MC 模块用 `tools/build_minecraft.ps1` 构建。

## 修改结束后上传 GitHub

后续 AI 在桌面 `CrimsonMC` 中完成项目修改后，通过 `tools/sync_github.py` 提交并推送到本仓库的 `main`。项目说明 `AGENTS.md` 记录了这一持续授权，`CHANGELOG.md` 保存每次的修改内容。已取消定时上传；手动编辑文件时，可自行执行以下命令。

手动同步入口：

```powershell
python tools/sync_github.py --message "描述本次修改"
```

同步遵循 `.gitignore`，本机下载、存档、备份和运行日志不上传。只进行普通推送；远端历史发生分叉或认证失败时保留本地提交并报告，不强推或自动重置文件。最近结果保存在本机 `runtime/github-sync-status.json`。新电脑需要自行配置具有仓库写入权限的 GitHub SSH 登录。

## 开始使用

1. 双击本目录的 **Start Prototype.cmd**。首次启动后台可能需要几十秒。它会复用已经运行的服务，并打开 Steam 中的红沙。
2. 进入红沙世界，按 **Insert**。右侧是 **MC 建造与合成原型**。面板较短时，在右侧面板内向下滚动，或拖动右下角拉高窗口。
3. 选择空旷、平坦位置，点击 **在角色前方建立实验原点**。已有 MC 建筑时不能移动原点；先拆除所有方块。
4. 材料选择“橡木木板”，坐标保持 **0 / 0 / 0**，点击 **放置指定方块**。会扣除一个 MC 木板并出现一米实体。将 Y 改成 1、2 可以堆高；X/Z 改成邻近整数可以并排放置。
5. **拆除指定方块**按坐标拆除；**拆除最后一块**按创建顺序拆除。掉落由真实 MC 方块逻辑计算后回到实验背包。
6. 合成按钮支持 **1 原木 → 4 木板、2 木板 → 4 木棍、4 木板 → 1 工作台**，通过 MC 自己的配方管理器执行。工作台暂时只是一种可放置方块，没有额外交互界面。
7. 按 **Insert**关闭菜单，继续红沙玩法。重新打开红沙后，先启动后台，再点击 **恢复方块**，将 MC 保存的建筑重新生成在原点。

“在角色前方放置”沿相机方向取附近格子并按地面／当前列高度放置；第一版不是鼠标瞄准任意方块的完整 MC 操作方式。实验范围 X/Z -16～16、Y 0～31，最多 128 个红沙方块。拆除为即时拆除，MC 掉落测试固定使用钻石镐，不包含生存模式破坏时间或工具消耗。

实验背包与红沙背包独立。初始提供 16 原木、64 圆石、32 泥土，验证合成已消耗部分材料并产生木棍和工作台。重新启动不会重新发放材料。

## 保存与关闭

- **Stop Prototype.cmd**正常停止 MC 和桥接后台，保留建筑、材料和红沙游戏。它不会自动拆除当前红沙实体；需要清场时先在面板拆除方块。
- MC 存档与实际区块：`runtime/minecraft-server/crimsonmc-lab/`；实验状态：该目录的 `crimsonmc-state.json`。
- 红沙坐标锚点：`runtime/bridge-origin.json`。不要只删锚点而保留 MC 建筑。
- 原有红沙存档备份：`backups/before-install-20261003-224317/`。
- 所有网络服务仅监听本机。端口：8765 红沙插件、8766 MC 权威服务、8767 桥接、25579 MC 服务端。关闭后台后，游戏里的面板会显示连接错误。

## 卸载红沙侧

退出红沙，再在 PowerShell 执行 `powershell -NoProfile -ExecutionPolicy Bypass -File tools/uninstall_red_side.ps1`。脚本根据 `runtime/installation.json` 校验，只删除本次安装且仍匹配哈希的文件；修改过的设置、日志和项目会保留。此次没有覆盖原始游戏程序或资源包。

游戏更新后不要假定兼容。当前验证仅覆盖此本地版本；原生适配器会检查游戏版本。出现连接错误可查看 `runtime/*stdout.log`、`runtime/*stderr.log` 和游戏目录 `bin64/cdmodkit/cdmodkit.log`。

## 技术记录

- `runtime/authority-checks.json`：真实 MC 合成、材料不足回滚、同一进程重复 operationId 不重复消费、MC 方块放置和掉落测试。
- `runtime/bridge-checks.json`：MC 扣材料 → 红沙生成碰撞 → 恢复不重复生成 → 拆除返还 → 碰撞消失。
- `runtime/restart-checks.json`：正常停止／重新启动 MC 和桥接，背包、版本号和圆石方块保存一致，重新连接后原生碰撞存在，最后拆除测试方块并归还材料。
- `runtime/red-side-probe.json`：独立原生物理探针测试。放置后高度增加约 1.034 米，拆除后恢复原值。这证明原生物理探针碰撞；未据此声称完成所有角色、NPC、战斗碰撞行为测试。
- 可公开的测试摘要见 [docs/validation.json](docs/validation.json)，原始运行日志和存档留在本机。
- 实验状态每次成功修改后原子写入；崩溃恢复使用已记录方块／空气墓碑修复实验坐标。operationId 收据仅保存在内存，不保证跨崩溃重试恰好一次。
- MC 是权威；红沙实体生成失败时，MC 修改可能已经成功，此时使用“恢复方块”修复显示，避免重复下达放置操作。

原生适配器基于 [Crimson Desert World Builder](https://github.com/Moon-yungg/crimson-desert-world-builder)，固定提交 `4dcedc8dfe1592fdee0528894389221291900b8d`；新增面板与探针 API 保存在 `red-side-patches/`，对上游的差异保存在 `red-side-patches/upstream.patch`。ASI 加载器使用 [Ultimate ASI Loader v9.7.4](https://github.com/ThirteenAG/Ultimate-ASI-Loader/releases/tag/v9.7.4)。遵循这些组件各自许可证，本目录保留上游源代码和许可证。

MC 模块源代码在 `minecraft/src/`，桥接在 `bridge/`。构建入口 `tools/build_minecraft.ps1` 与 `tools/build_worldbuilder.py`。固定依赖 Fabric Loader 0.16.10、Fabric API 0.102.1+1.21.1、Loom 1.8.13、Java 21、Gradle 8.10.2。运行采用本地开发服务端；升级或完整客户端嵌入需要继续开发。
