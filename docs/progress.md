# 当前状态与分阶段计划

更新日期：2026-10-04（Asia/Shanghai）。当前开发目录为桌面 `CrimsonMC`，仓库为
[dhcy-Asion/MC-](https://github.com/dhcy-Asion/MC-)。新聊天先读
[../AGENTS.md](../AGENTS.md)、[architecture.md](architecture.md) 和本文件。

## 当前里程碑

**M1：开发文档与可重复只读诊断基线，已完成本地验收。**
本次只完成 M1，不开始 M2 的新增角色接口实现。M1 的交付物是开发规则、实际架构、
明确验收标准和已验证版本的只读探针，不是第四个可玩人物。

## 已有可用基线

- 红沙 1.0.0.2976 + 真实 MC Java 1.21.1，保留红沙地图／人物／战斗。
- Insert 面板可操作实验库存、三种原版配方、六种后端方块；面板当前列五种材料。
- 红沙以一米蓝色实体显示 MC 建筑并提供经探针验证的碰撞；没有 MC 材质。
- 128 个原生代理上限，33×32×33 实验范围；库存与建筑可保存、重启恢复。
- 既有合成、回滚、原生方块碰撞及重启检查摘要在 [validation.json](validation.json)。
  这是此前基线的检查记录，不代表在本次 M1 重新运行了全部游戏行为测试。
- 尚无 Steve 模型、第四个 F1 角色、装备接管、心形 HUD、MC 生存伤害、完整手持和准星放置。
  MC 后端仍为 SimpleInventory，不是 PlayerInventory；世界仍配置为创造／和平。

## 已确认的需求和优先级

保留原版三人，新增独立 Steve 并用 F1 切换；Steve 仅穿 MC 装备，采用 MC 生存攻击、
护甲、受伤计算和真实心形血量。完整背包阶段支持按最大堆叠免费领取、选择／手持、
使用消耗及方块放置；弓、桶、食物等具体用途逐步接入。
详见 [steve-character.md](steve-character.md)。

用户选择先验证第四角色，暂不更新背包。当前存档曾报告三人均解锁；本轮实际确认
能切达米安，翁卡暂时无法切换，不能把翁卡行为记为通过。用户随后要求以仓库文档
交接并逐个里程碑推进，因此本次收束为 M1。

## 里程碑与验收门槛

| 阶段 | 范围 | 可验证的完成条件 | 状态 |
| --- | --- | --- | --- |
| M0 已有原型 | MC 建造／合成与原生代理 | 配方／库存回滚、方块碰撞、恢复不重复及正常重启保存通过 | 已有基线 |
| M1 文档和诊断 | 规则、模块接口、进度、只读探针 | 文档与源码一致、链接有效；诊断保护检查通过；支持 EXE 的只读采样成功；不发布原始进程数据 | 已完成 |
| M2 原生角色接口验证 | 实际受控身份、F1 名单、原生请求和创建生命周期 | 区分角色 ID／Actor UID／佣兵 No；确认 F1 实际路径；确认新增身份需要的名单、创建、状态及保存接口和调用约定 | 下一阶段，未完成 |
| M3 独立第四角色 | 创建与注册、F1 选择、控制、生命周期 | 原版三人保留，第四独立身份可切入／切出；重载、死亡、骑乘及任务强制回切不串状态；有游戏内证据 | 未开始，依赖 M2 |
| M4 Steve 模型和装备 | 模型／骨骼／动画／手持点，MC 装备与红沙装备隔离 | Steve 实际站立、移动、攻击和换装可见；原版三人装备不变；模型预览不能代替此检查 | 未开始，依赖 M3 |
| M5 MC 生存和心形血量 | 真实 MC 玩家 tick、攻击／护甲／受伤、原生事件桥接 | 输入和伤害来源可追踪；MC 规则决定生命；护甲、冷却、耐久、死亡与真实心形 HUD 联动通过 | 未开始，依赖 M3/M4 |
| M6 背包和鼠标建造 | 物品目录、领取／选择／手持／消费、瞄准面放置 | 堆叠64/16/1、满背包回滚、最后一个物品耗尽、正确面放置／遮挡／距离、保存迁移通过 | 延后，依用户当前优先级 |

M2 的研究可能证明某个原生路线不可用。此时记录确切失败证据、未解决接口和替代方案；
不能越过门槛把换装或 NPC 生成当作 M3 完成。用户后续可以调整阶段顺序，需记录。

## M1 交付与检查记录

交付文件：根目录 AGENTS／README 导航；`docs/architecture.md`、本文件和人物需求记录；
`tools/probe_characters.py`、`tools/check_character_probe.py`、固定诊断配置及 Trinity MIT 声明。

已执行：

- `python tools/check_character_probe.py`：6 项保护检查通过，覆盖未知版本／SHA、冲突／缺失
  锚点、错误 manager 布局、损坏容量、多个不同指针和坐标关联不等于身份确认。
- `python -m py_compile tools/probe_characters.py tools/check_character_probe.py`：通过。
- `tools/probe_characters.py` 对本轮 Windows 游戏进程只读采样成功，输出
  `runtime/character-tracked-probe.json`；当次指定的 PID 仅留本机，重启后不可复用。
  一般运行可省略 `--pid`，自动查找唯一游戏进程。
- 文档相对链接及固定配置／基线摘要 JSON 解析通过；`git diff --check` 通过。
- CLI 边界检查通过：请求把原始诊断写入 `docs/` 时，在访问游戏进程前拒绝，未产生文件。
- 已跟踪文件未包含 runtime／备份／下载／vendor／构建缓存；收尾继续核对实际待上传文件。
- GitHub 同步由本次提交前的收尾脚本执行，最终状态见本机 `runtime/github-sync-status.json`
  及提交／远端 HEAD；不在提交正文中预先宣称推送成功。

当前已检查 EXE：版本 `1.0.0.2976`，SHA256
`57da440d72f4db974f25fef047cf84c4dadd999a88cb2a3c5af4c9bd67fde1e7`。
新电脑即使版本号相同，SHA 不同也先停止诊断，重新验证，不能直接更新配置跳过检查。
本次不构建／更换 ASI 或 MC JAR，不运行会消费材料或创建方块的检查。

## 原生研究已经确认的事实

1. 固定 Trinity 提交的四个 manager 锚点在当前 EXE 均唯一命中并一致；stat-commit 和
   damage-apply 各有一个签名匹配。这是定位事实，不是已验证调用 ABI 或伤害接管。
2. 来源所谓 client/server 两条链在本机均到同一个 **ServerActorManager**，其列表包含
   大量普通场景 actor。不能据此把场景数量当作 F1 名单，不能把 server 布局套给 client。
3. 独立 world-root 签名有 15 处一致引用；RTTI 可找到真正的 ClientActorManager、
   ClientUserActor 及 child 候选。达米安快照包含两个不同 child，均可回指 user；
   不同 child 不一定表示短暂过渡，不能默认取第一个或要求两者总相同。
4. 达米安是用户报告的身份，原生 ID 仍未确认。一个客户端候选与 server possessor
   回链人物的 local XYZ／sector 一致，且与 manager 指针一致；这是身体关联证据。
5. 可只读观察真实 StatusActorComponent、装备、角色控制、库存、TransformSync 等组件。
   HP 候选具备类型／回链及数值检查，但尚无与 MC 生命或原生伤害的行为桥接。
6. 现有模型工具支持资产／外观修改，未提供已验证的第四人物注册流程；Steve 资产导入
   和新增角色身份必须分别通过。详见人物需求记录的固定来源。

本机原始证据保存在忽略的 `runtime/character-*.json`。可重复探针已经在仓库内，不需要
旧聊天或 ignored 研究 checkout 才能运行。探针输出中的 native ID／F1 注册验证标记
仍为 false，不能将退出码 0 解读为 Steve 已实现。

## 静态候选与未知项：M2 的入口

以下为当前 SHA 的本机磁盘只读分析结果，只是进一步验证的入口，不可执行原生调用：

- `TrocTrChangePlayerbleCharacterReq` 的三项参数至少前两项属于 MissionInfo／stageinfo，
  不能只凭类名当成 F1 角色选择。`CharacterHudSwitch` 也包含 HUD 绘制属性，不能推定为名单。
- `StartChangeFocusActorReq` 是更强候选，静态路径按 CharacterInfo 键进入已有佣兵／actor
  切换；需要实际 F1 入口及参数关联验证。`SelectMercenarySpawnReq` 操作已有佣兵记录，
  不是新增注册证明。完整反汇编只留本机；下表保留当前 SHA 的定位入口，下一阶段先复核。
- MercenaryInfo 的 `_isPlayable`、`_isSelectMercenarySpawn` 等字段有静态线索，但其
  “可玩”概念可能包含载具／佣兵类别，不等于 F1 可选主角。不同版本 schema 字段次序不同。
- 原生角色表、owned mercenary 状态、client/server 创建、F1 菜单及存档生命周期需要
  一起解决；目前没有已验证的新 ID 注册和安全原生调用接口。

| 当前 EXE 的静态入口 | 相对模块基址 RVA／候选布局 | 限制 |
| --- | --- | --- |
| StartChangeFocusActorReq | vtable `0x5B244F8`，handler `0x298D940` → `0x294D5B0` | 候选封包为 u32 + u8；尚未关联实际 F1 操作 |
| SelectMercenarySpawnReq | `0x2A306A0` → `0x2C49670` → `0x2B9EBD0` | 已有佣兵 No + 三个位置 float，不是新增名单登记 |
| MercenaryInfo manager | global `0x6D69A60`，候选 count +8、record-pointer array +0x58 | 原生类型／记录界限需再次只读核对，不调用 getter 加载 |
| CharacterInfo manager | global `0x6D69A48`，候选相同目录布局，record +0xBE 为 MercenaryKey 线索 | 不是独立可玩身份或存档创建 API |

这些是静态相对地址，不是可复用的堆指针；不写入生产适配器，不以它们跳过版本、
RTTI、结构、参数和调用线程验证。没有固定三人限制的直接证据，也没有成功新增人物的证据。

## 新聊天的下一步

1. 阅读开发规则和实际接口，核对 `git status`、安装清单及本机版本；不要复用旧 PID／地址。
2. 如需重新采样，在红沙已进入世界后执行：

   ```powershell
   python tools/check_character_probe.py
   python tools/probe_characters.py --output runtime/character-next.json
   ```

3. M1 通过后下一阶段是 **M2 原生角色接口验证**。先复核 F1 实际控制／名单路径与身份，
   记录可复现的签名、结构检查、必要字段和失败条件；暂不实现完整库存或生存伤害。
4. 获得明确的新角色创建／登记契约后才进入 M3；每完成一个里程碑检查、更新本文件、
   写 CHANGELOG 并通过同步脚本正常推送。用户当次只要求 M1，本次不自动继续 M2。

## 决策记录

| 日期 | 决策 | 理由／依据 |
| --- | --- | --- |
| 2026-10-04 | 先集中验证第四角色，背包暂缓 | 用户明确选择；完整需求已记录 |
| 2026-10-04 | 本次先交付 M1 文档与只读基线 | 用户要求新聊天仅凭仓库交接、按可验证里程碑推进 |
| 2026-10-04 | 保留角色候选与身份未知标记 | 两个 child 同时存在；坐标／HP 关联不能证明独立角色 ID |
| 2026-10-04 | 固定版本和 SHA，未知布局停止解释 | 本机读取发现来源 realm 标签与实际 manager 类型不一致 |
| 2026-10-04 | 每次修改收尾上传一次，无定时任务 | 用户持续授权；失败保留本地历史，不强推 |

M1 收尾状态：本地验收通过；下一里程碑为 M2。本次只完成 M1，收尾正常提交和上传。
