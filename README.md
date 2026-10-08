# MC-：史蒂夫移民红沙

红色沙漠 × Minecraft 的物品背包／建造实验原型。

仓库：[dhcy-Asion/MC-](https://github.com/dhcy-Asion/MC-)。当前开发目录为桌面的 `CrimsonMC`。

开发入口：[AGENTS.md](AGENTS.md) 规定开发和上传流程；
[当前交接](docs/current-state.md) 保存本轮优先级、现场状态与下一项实验；
[模块架构与接口](docs/architecture.md) 说明已实现行为；
[当前状态与里程碑](docs/progress.md) 保存验收标准、证据和下一步。
M1 文档与只读诊断基线已完成；M6a 独立物品背包已有实现。2026-10-06 最新要求为
启用 mod 后持续显示史蒂夫、兼容红沙和 MC 装备、MC 方块外观及创意工坊分发。
底部九格真实库存快捷栏已完成常驻显示、库存后台刷新和断线恢复的游戏内检查，保留原 UI；
角色资产已推进至真实红沙骨骼的离线 PAC 候选，六种基线方块已导出真实模型/纹理，
临时原木对照已显示像素纹理，史蒂夫块体已出现但装配错位；正式建造仍使用蓝色代理。
可复建步骤见 [资产管线](docs/asset-pipeline.md)。
完整验收见 [需求记录](docs/steve-character.md)，
工坊支持与发布资格见 [分发准备](docs/workshop-distribution.md)。

2026-10-07：单块 Y 轴原木的临时材质对照已在红沙显示 MC 像素纹理，并通过原生碰撞／
清理检查；定位到生成 PAMI 的 XML 声明格式问题。修复后三轴包已读回 27 项并逐轴
通过碰撞／清理，侧向放置后每轴可见的三个面朝向也已核对。背面、底面、纹理采样
与全部光照仍待验收，正式建造仍用蓝色代理。同步现在保存未决操作，并在原生端核对
游戏实例和对象快照；失败后请使用“恢复方块”，避免重复提交消耗材料的放置。

史蒂夫已具备可重建的私有头身资源及临时测试包。十一资源首测及补齐头描述文件的
十二资源手动实测均仍显示原角色，外观切换未通过；新头身名称仅在外观选项表读到。
只读诊断已确认当前初始 app 是 Macduff 00000，进一步定位原部件注册表缺少两个私有
名称。十三资源注册 v1 包随后出现进入闪退，撤回后同一存档正常；已定位注册部件
列表与私有 prefab 不一致。v2 对照可正常进入，MC 块体已出现，但定位错开并与原装
部件混叠，测试后已恢复；详见[进度记录](docs/progress.md)。模型装配、动画、装备及持续
外观仍待完成，尚不能作为可用人物。安装／恢复方法见[资产管线](docs/asset-pipeline.md)。

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

已在这台电脑的红沙 **1.0.0.2976** 上跑通。红沙地图、人物和战斗继续运行，后台真实 Minecraft Java **1.21.1** 管理实验背包、方块和拆除掉落。按用户最新要求，原型合成已移除，可直接添加物品。红沙使用原生一米蓝色网格实体显示这些方块并提供碰撞。

**这是可用的背包／建造实验，不是完整 MC 移植。** 正式建造尚未接入 MC 材质、客户端画面、红石、生物或完整生存玩法；几种材料目前外观相同。没有安装 PCL2 离线客户端，也不需要登录 MC 客户端来使用这个服务端原型。

## 从 GitHub 安装原型

需要 Windows、自己的红沙安装、Git 和 PATH 中可用的 Python 3。只在红沙 1.0.0.2976 验证；仓库不包含红沙本体、MC 游戏程序、个人存档或运行缓存。

```powershell
git clone https://github.com/dhcy-Asion/MC-.git CrimsonMC
cd CrimsonMC
powershell -NoProfile -ExecutionPolicy Bypass -File tools/prepare_environment.ps1 -AcceptMinecraftEula
powershell -NoProfile -ExecutionPolicy Bypass -File tools/install_red_side.ps1 -GameRoot "E:\SteamLibrary\steamapps\common\Crimson Desert"
.\"Start Prototype.cmd"
```

准备脚本下载并校验固定版本的 Java、Gradle、ASI 加载器、官方中文语言文件及物品图标，建立本机服务端配置，使用仓库中的编译插件。`-AcceptMinecraftEula` 表示接受 [Minecraft EULA](https://www.minecraft.net/eula)；已有实验存档、配置和 EULA 文件会保留。安装红沙插件前须退出红沙。

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

新版插件加载后，屏幕底部显示 MC 风格九格快捷栏（背包第 1～9 槽），F8 关闭仍更新。
按 F8 打开菜单后可点击快捷格选择，仍可通过原 36 格面板选择所有槽。服务端选择第
10～36 槽时，快捷栏如实显示槽号，不高亮一个错误的快捷格。断线时标为不可用；
关闭菜单时快捷栏不占用游戏鼠标／按键。此栏尚无心形血量、饥饿／经验值或可见手持模型，
不改变红沙原角色 UI。常驻布局、后台刷新、断线恢复已实测；本轮 F8 自动短按未完成
菜单开关/点击验收，输入门控已通过离屏检查，仍需单独游戏内确认。

1. 双击本目录的 **Start Prototype.cmd**。首次启动后台可能需要几十秒。它会复用已经运行的服务，并打开 Steam 中的红沙。
2. 进入红沙世界，按 **F8**。右侧是 **MC 物品控制台与建造**。默认只显示 MC 面板；勾选“显示红沙世界构建器”可打开原来的红沙资源工具，该工具不是 MC 物品目录。面板较短时，在右侧面板内向下滚动，或拖动右下角拉高窗口。旧安装如仍用 Insert 且触发 Steam 截图，保存退出游戏后运行 `powershell -NoProfile -ExecutionPolicy Bypass -File tools/set_menu_key.ps1`，再启动游戏；只改原型菜单键，其余设置保留。
3. **物品目录**包含 MC 1.21.1 的 1332 种非空气物品类型，每个 ID 独立一项。名称来自固定版本官方简体中文语言文件，可搜索中文名称或 `minecraft:diamond_sword` 等 ID。目录以图片网格显示，鼠标悬停显示中文名称、物品 ID、最大堆叠及放置支持情况。点击图标按 MC 最大堆叠领取 64／16／1；背包放不下整组时完全回滚。展开 **直接添加物品（控制台方式）**，输入完整／裸 ID 或中文／英文名称与数量（1～6400）；同名物品需使用 ID，放不下全部数量则完全回滚。未接入原生用途的物品也能领取。图标为物品类型预览，不显示实际附魔、药水效果、染色或耐久变化；这些组件仍保存在 MC 中。图标加载时暂显示问号。
4. 上方 **36 格背包**以图片显示物品，右下角是数量；点击选择当前物品，可选择空槽。悬停显示完整中文名、物品 ID 和数量，长名称不会挤在格子内。**消耗一个非方块物品**只扣所选格 1 件，用完变空，不自动从其他格补充。目前只实现库存选择，尚无红沙可见手持模型，弓／桶／食物用途也未接入。
5. 放置六种基线方块时，先展开底部 **建造操作**，点击 **在角色前方建立实验原点**。再选中背包里的原木、木板、圆石、泥土、石头或工作台，展开 **放置选中方块**，填写 **0 / 0 / 0** 并放置；会只扣所选格。目录中其他方块会标注“放置待接入”。已有建筑时不能移动原点。
6. 建造操作中仍可 **拆除指定方块**／**拆除最后一块**，掉落由真实 MC 计算。原型没有合成按钮或合成 API；工作台物品和已有工作台方块保留，不提供合成交互。这不修改原版 MC 游戏本身的配方资源。
7. 按 **F8**关闭菜单，继续红沙玩法。重新打开红沙后，先启动后台，再点击 **恢复方块**，将 MC 保存的建筑重新生成在原点。

“在角色前方放置”沿相机方向取附近格子并按地面／当前列高度放置；第一版不是鼠标瞄准任意方块的完整 MC 操作方式。实验范围 X/Z -16～16、Y 0～31，最多 128 个红沙方块。拆除为即时拆除，MC 掉落测试固定使用钻石镐，不包含生存模式破坏时间或工具消耗。

实验背包与红沙背包独立。原有材料、建筑和物品组件保留，旧状态自动迁移为 schema 2，保存选中格和完整方块属性（含原木朝向）。重新启动不会重新发放初始材料；自由领取需要主动点击按钮。背包操作不依赖实验原点，方块放置仍需要。当前面板没有朝向选择控件，红沙中仍显示蓝色代理。

也可在本仓库的 PowerShell 控制台直接输入：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/give_item.ps1 -Item minecraft:diamond_sword -Count 1
```

先启动后台；此命令向同一个 MC 实验背包添加物品，不是向红沙原版背包添加。
准备脚本下载并校验官方 MC 1.21.1 `zh_cn` 文件到忽略上传的 `downloads/`；文件缺失或哈希不符时权威 API 停用，运行准备脚本修复，不回退到猜测译名。自定义命名／耐久等 ItemStack 组件保留。

物品图标来自固定版本的 [Minecraft Item Gallery](https://github.com/TinyTank800/MinecraftAllImages)，来源和哈希见 `config/item-icons.json`。下载图片不上传 Git，也不打进 ASI；安装／更新脚本将本机缓存复制到原型自己的 `cdmodkit/mc-icons/` 并记录所有文件哈希。已有安装先退出红沙、运行准备脚本，再执行 `tools/update_red_side.ps1`；图标缺失可重新运行准备和更新。

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

- `runtime/authority-checks.json`：当前正式 MC 只读目录／名称检查和必拒绝请求；1332 个官方名称逐项一致，正式材料不变。计数添加、堆叠、回滚和保存检查在独立测试世界执行。
- `runtime/bridge-checks.json`：MC 扣材料 → 红沙生成碰撞 → 恢复不重复生成 → 拆除返还 → 碰撞消失。
- `runtime/restart-checks.json`：正常停止／重新启动 MC 和桥接，背包、版本号和圆石方块保存一致，重新连接后原生碰撞存在，最后拆除测试方块并归还材料。
- `runtime/red-side-probe.json`：独立原生物理探针测试。放置后高度增加约 1.034 米，拆除后恢复原值。这证明原生物理探针碰撞；未据此声称完成所有角色、NPC、战斗碰撞行为测试。
- 可公开的测试摘要见 [docs/validation.json](docs/validation.json)，原始运行日志和存档留在本机。
- 背包检查摘要见 [docs/inventory-validation.json](docs/inventory-validation.json)。`python tools/check_inventory.py` 使用独立世界 8768／25580，不操作正式 8766 材料；桥接与原生协议检查分别为 `check_inventory_bridge.py`、`check_inventory_ui.py`。
- 实验状态每次成功修改后原子写入；崩溃恢复使用已记录方块／空气墓碑修复实验坐标。operationId 收据仅保存在内存，不保证跨崩溃重试恰好一次。
- MC 是权威；红沙实体生成失败时，MC 修改可能已经成功，此时使用“恢复方块”修复显示，避免重复下达放置操作。

原生适配器基于 [Crimson Desert World Builder](https://github.com/Moon-yungg/crimson-desert-world-builder)，固定提交 `4dcedc8dfe1592fdee0528894389221291900b8d`；新增面板与探针 API 保存在 `red-side-patches/`，对上游的差异保存在 `red-side-patches/upstream.patch`。ASI 加载器使用 [Ultimate ASI Loader v9.7.4](https://github.com/ThirteenAG/Ultimate-ASI-Loader/releases/tag/v9.7.4)。遵循这些组件各自许可证，本目录保留上游源代码和许可证。

MC 模块源代码在 `minecraft/src/`，桥接在 `bridge/`。构建入口 `tools/build_minecraft.ps1` 与 `tools/build_worldbuilder.py`。固定依赖 Fabric Loader 0.16.10、Fabric API 0.102.1+1.21.1、Loom 1.8.13、Java 21、Gradle 8.10.2。运行采用本地开发服务端；升级或完整客户端嵌入需要继续开发。
