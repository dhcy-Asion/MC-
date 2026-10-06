# 当前状态与分阶段计划

更新日期：2026-10-06（Asia/Shanghai）。当前开发目录为桌面 `CrimsonMC`，仓库为
[dhcy-Asion/MC-](https://github.com/dhcy-Asion/MC-)。新聊天先读
[../AGENTS.md](../AGENTS.md)、[architecture.md](architecture.md) 和本文件。

用户已于 2026-10-06 将剩余移植工作设为持续目标并要求开始执行，之后再次要求继续。
目标已建立且未标记完整移植完成。此前一轮触及 usageLimited；用户继续后已恢复 active，
当前继续原生资产与实机探针工作，没有自行改为 complete/paused/blocked。
来源、路线和实测保护见 [../MODLOG.md](../MODLOG.md)。

## 当前里程碑

**当前优先 M4a：启用期间持续为史蒂夫、两套装备与参考图 HUD，进行中。**
2026-10-06 用户要求所有方块与 MC 一致、mod 启用后持续 Steve、兼容红沙及 MC 全部
装备／物品、第三人称随装备改变、保留原 UI 并新增参考图 HUD、支持工坊下载。
用户已回答范围问题：禁用／卸载 mod 后恢复原外观；心形条显示红沙真实 HP，继续
红沙战斗规则。旧“不能穿红沙装备”和独立 MC 生存生命要求已被覆盖。
最新完整验收在 [steve-character.md](steve-character.md)；独立第四身份不再是本轮门槛。
本次落地小步为真实库存九格快捷栏，常驻显示、后台刷新与断线恢复已有游戏内证据，
F8 开关及点击仍待验收。模型资产已推进为真实红沙 palette 的离线 Steve PAC 候选，
六种基线方块的 14 项真实几何/UV/纹理已导出，详见 [asset-pipeline.md](asset-pipeline.md)。
持续角色替换、全方块、装备、心形条和工坊仍未完成；只读身份解码、资产导出及构建
不能替代游戏内验收。仍需实际身体到外观控制器的安全回链、刷新线程、原生资源、
骨骼／动画／装备绑定与恢复生命周期。
本轮已补齐原木三轴 PAM/PAMI、Steve 七资源 prefab 候选，以及官方 vanilla 注册表
（1060 种方块、26684 个合法状态）。用户恢复授权后已实际生成一块诊断原木：登记
成功，但模型未显示、未检测到一米碰撞，原生加载验收失败。对象已清理、MC 状态不变；
游戏正常退出后临时 0041 已恢复，38 个原索引/元数据哈希一致。下一步定位实际加载
失败环节；不把离线解包、场景对象指针或注册表覆盖当作游戏内功能完成。
随后为读取诊断构建并安装新 ASI、再次临时挂载原木 0041。一次 Escape 中断后用户
再次明确恢复授权：真实引擎读取 **15/15 项首次成功**，蓝块六项、Y 轴原木六项及三
张纹理的长度/头部/FNV 全部与已校验本地资源一致，MC 状态不变。正常退出后第二次
收据 `51159fa10a564fa392027e71af157471` 也已 restored，38 个原文件哈希一致，
0041/active receipt 已移除。下一步核对装配/实例化，不能再把目录树猜测当成根因。
随后已在新进程复试正常原木（读回成功后仍不显示/碰撞失败），并通过 A 蓝 prefab
别名实测：同一新逻辑路径显示蓝块且物理增量 1.1521 米。A 对象已清理，MC 不变。
**最新状态：A 收据 `ece6ea42e8154e878fb9be88a8511944` 仍 installed，0041 仍挂载；
退出指令后红沙 PID 69700 仍运行，窗口捕获连续显示其它游戏，已请用户正常退出后
恢复包。不要运行中改索引，也不要重复删除已清理 UID。** B PAMI 对照已离线准备，
尚未生成对应 overlay 或实测。详细证据与恢复顺序见末节。
静态结果见 [native-character-contract.md](native-character-contract.md)，路线复核见
[native-character-feasibility.md](native-character-feasibility.md)。

M1 已完成并提交为 `1bb0775`。M6a 独立背包保持进行中：全物品官方中文图标目录、
中文悬停、整组领取、控制台按数量添加、36 格选择和实际消耗已实现，兼容六种方块放置。
用户已确认游戏内图片／悬停显示，按钮点击验收仍保留未验证；可见手持和装备用途尚未接入。

## 已有可用基线

- 红沙 1.0.0.2976 + 真实 MC Java 1.21.1，保留红沙地图／人物／战斗。
- F8 面板可操作实验库存和六种后端方块；原型合成入口已取消，旧建筑与工作台保留，面板建造下拉框列五种材料。
- 红沙以一米蓝色实体显示 MC 建筑并提供经探针验证的碰撞；没有 MC 材质。
- 128 个原生代理上限，33×32×33 实验范围；库存与建筑可保存、重启恢复。
- 既有合成、回滚、原生方块碰撞及重启检查摘要在 [validation.json](validation.json)。
  这是此前基线的检查记录，不代表在本次 M1 重新运行了全部游戏行为测试。
- 尚无游戏内 Steve 模型、第四个 F1 角色、装备接管、心形 HUD、完整手持和准星放置。
  本轮新增底部九格库存 HUD；离线 Steve 资产不等于已加载到红沙。
  MC 后端仍为 SimpleInventory，不是 PlayerInventory；世界仍配置为创造／和平。

## 已确认的需求和优先级

原始长期目标包括独立第四 Steve 和 MC 生存规则，当前只保留研究记录。
最新选择为复用原版控制身份，启用期间持续 Steve，禁用恢复；允许红沙装备和 MC 装备，
心形 UI 使用红沙真实血量与战斗规则。本轮先验收九格，完整模型／方块／装备按最新表推进。
完整背包支持按最大堆叠免费领取、选择／手持、使用消耗及方块放置；具体物品用途逐步接入。
详见 [steve-character.md](steve-character.md)。

用户最初选择先验证第四角色，随后同意先让背包独立可用。当前存档曾报告三人均解锁；本轮实际确认
能切达米安，翁卡暂时无法切换，不能把翁卡行为记为通过。用户随后要求以仓库文档
交接并逐个里程碑推进，因此本次收束为 M1。

## 里程碑与验收门槛

| 阶段 | 范围 | 可验证的完成条件 | 状态 |
| --- | --- | --- | --- |
| M0 已有原型 | MC 建造／合成与原生代理 | 配方／库存回滚、方块碰撞、恢复不重复及正常重启保存通过 | 已有基线 |
| M1 文档和诊断 | 规则、模块接口、进度、只读探针 | 文档与源码一致、链接有效；诊断保护检查通过；支持 EXE 的只读采样成功；不发布原始进程数据 | 已完成 |
| M2 原生角色接口验证 | 实际受控身份、F1 名单、原生请求和创建生命周期 | 区分角色 ID／Actor UID／佣兵 No；确认 F1 实际路径；确认新增身份需要的名单、创建、状态及保存接口和调用约定 | 进行中，未完成 |
| M3 独立第四角色 | 创建与注册、F1 选择、控制、生命周期 | 原版三人保留，第四独立身份可切入／切出；重载、死亡、骑乘及任务强制回切不串状态；有游戏内证据 | 未开始，依赖 M2 |
| M4 Steve 模型和装备（旧独立身份方案） | 原独立第四角色及装备隔离设计 | 旧方案只保留研究，当前按 M4a 的两套装备要求验收 | 旧方案未开始，不作为当前门槛 |
| M4a 持续史蒂夫模式（最新优先） | 复用当前角色控制，启用持续 Steve、禁用恢复，两套装备及方块 | 身体模型／动画／两套装备正确，重载／强制换角色仍应用，禁用恢复；九格 HUD 独立验收 | 进行中；九格常驻/刷新/断线实测通过，F8 点击待验收；离线 Steve PAC 与基线方块已生成，原生显示未接入 |
| M5 红沙真实心形血量（新范围） | 保留红沙战斗规则，将真实 HP／最大 HP 显示为心形 | 与原 UI 受伤、治疗、最大 HP 变化一致，切人物不串读数；不显示虚构饥饿／经验 | 未实现，须验证读取链和行为事件 |
| M6a 独立背包 | 全物品目录、整组领取、36 格选择、消耗与现有方块放置 | 原版64/16/1、满背包与未知物品回滚、只扣所选格、耗尽不跨格替补、保存迁移、面板实测 | 保留进行中，本轮优先 M4a／HUD |
| M6b 可见手持和鼠标建造 | 物品手持模型、准星命中面放置 | 红沙手持真实模型、正确面放置／遮挡／距离与鼠标输入联动通过 | 未开始；手持资产依赖 M4，输入与射线另验收 |
| M7 工坊分发 | 发行方支持、资源与 mod 发布资格、订阅安装／更新／卸载 | 支持及许可有依据、干净环境和真实工坊订阅流程通过 | 公开支持／发布资格未确认；见 [workshop-distribution.md](workshop-distribution.md) |

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
4. M1 中达米安是用户报告的身份，原生 ID 当时未确认。一个客户端候选与 server possessor
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

3. 最新优先级是 **M4a 可逆史蒂夫模式**。先核对实际身体的外观对象／线程与资产绑定，
   不写猜测的原生指针；M2/M3 的独立第四身份不再阻塞本轮，M6a 未验收按钮保留。
   不消耗用户实验材料。
4. 获得明确的新角色创建／登记契约后才进入 M3；每完成一个里程碑检查、更新本文件、
   写 CHANGELOG 并通过同步脚本正常推送。当前用户已要求继续两项修改。

## 决策记录

| 日期 | 决策 | 理由／依据 |
| --- | --- | --- |
| 2026-10-04 | 先集中验证第四角色，背包暂缓 | 用户明确选择；完整需求已记录 |
| 2026-10-04 | 本次先交付 M1 文档与只读基线 | 用户要求新聊天仅凭仓库交接、按可验证里程碑推进 |
| 2026-10-04 | 保留角色候选与身份未知标记 | 两个 child 同时存在；坐标／HP 关联不能证明独立角色 ID |
| 2026-10-04 | 固定版本和 SHA，未知布局停止解释 | 本机读取发现来源 realm 标签与实际 manager 类型不一致 |
| 2026-10-04 | 每次修改收尾上传一次，无定时任务 | 用户持续授权；失败保留本地历史，不强推 |
| 2026-10-04 | 用户要求继续两项修改，启动 M2 | M1 已完成；先验证原版真实切换请求和身份，不用猜测封包创建角色 |
| 2026-10-04 | 调整为先完成 M6a 独立背包 | 用户明确答复“是，先让背包部分可用”；第四角色研究不再阻塞材料领取 |
| 2026-10-04 | 将选择与可见手持分开验收 | 本阶段选中的是 MC 库存格；原生手持点／模型和角色接口尚未验证，不能称已经拿在手里 |

M1 收尾状态：本地验收通过并已上传。M6a 的构建、检查和实测结果在本次收尾追加。

## M6a 交付与检查记录

本阶段按用户最新答复独立推进背包，不安装 M2 被动切换候选。后端仍为
SimpleInventory，新增 selectedSlot，不能据此声称拥有生存玩家、装备槽或原生手持。

已实现：

- 真实 MC 注册表的 1332 个非空气物品类型目录，原版名称／最大堆叠／方块元数据。
- 36 格背包、全组免费领取、服务端选中格、空格选择、非方块显式消耗。
- 六种基线方块从选中格放置，用完变空且不从其他格替补；旧坐标／前方算法保留。
- schema 1 保存选择、原有 ItemStack 组件和建筑；旧无版本状态校验后无损迁移，
  未知未来版本不覆盖。operationId 绑定路径及正文，冲突拒绝。
- 异步面板，每项“获取一组”、搜索／50 项分页、库存选择和最近操作信息；后端暂时
  不在线时，恢复后会重新拉目录。界面标注手持模型／其他方块／物品用途尚未接入。

已执行：

| 命令／检查 | 结果与边界 |
| --- | --- |
| `tools/build_minecraft.ps1` | 最终源码构建通过；第一次隔离测试发现 Gson 省略 selectedItem:null，修复 serializeNulls 后重新构建与全测 |
| `python tools/check_inventory.py` | 独立 8768／25580 测试世界 13 项全部通过；64/16/1、未知物品、选空、最后所选块／物品、三配方、掉落、写盘失败／部分插入回滚、receipt 冲突、重启组件与未来格式拒绝；正常停服，无强停 |
| `python tools/check_inventory_bridge.py` | 15 项隔离 HTTP 检查通过；库存不依赖红沙／原点，分页与坏参数拒绝、选中坐标转换、原生同步失败／响应丢失不重试 |
| `python tools/check_inventory_ui.py` | C++ 主机解码检查通过：分页、完整 36 槽、边界、重复／截断／超量响应、失败不覆盖已知状态 |
| `python tools/build_worldbuilder.py` | 原生构建通过，固定上游提交未变；新源码均可由准备脚本复制 |
| `tools/prepare_environment.ps1 -SourceBuild` | 固定上游／MinHook／ImGui 与所有本项目补丁副本检查通过；反向补丁检查通过 |
| Python 语法检查 | 新增三个检查脚本与桥接通过 |
| 正式 8766 状态迁移 | 先备份再启动；与备份相比 revision／36 格／touched 全部不变，仅新增 schemaVersion=1、selectedSlot=0 |
| 发布与安装 | 构建 ASI／JAR 已复制至 artifacts；安装清单校验后更新自己的 ASI，版本／EXE SHA 与已验证配置一致 |

公开摘要见 [inventory-validation.json](inventory-validation.json)。原始测试世界、日志与
状态备份只留 runtime／backups；运行中界面验证尚在进行，不能据此标记完整手持或
鼠标建造完成。当前不消耗用户已有材料，隔离检查生成／消耗的材料只在测试世界。

下一项验收：进入已启动存档，按 Insert，确认新版目录／36 格可见，验证一个新物品的
领取、选中和消耗按钮；自动短按 Insert 未被游戏菜单捕获，已经请求用户物理按一次。
完成后更新本段及公开摘要，再提交上传。


## 2026-10-04 控制台直接添加与准确中文名称复核

用户提供另一份 AI 的项目进度 DOCX，要求检查并直接修复问题、完成其未做的工作。
文档保留于本机 output，不作为唯一验收证据；本次对照未提交源码、构建产物和实际服务重新验证。
文档中“没有英文字母”不能证明译名正确；逐词词表和合并目录／默认选择重名物品的遗留逻辑已移除。
同时修复 ASI 的发布 build.json 过期问题，标题／说明／交接文档与新接口同步。
不修改原版 MC 的配方资源，只移除本原型的合成操作。

本次补充的验收标准：

1. 原型无合成按钮，旧 /ui/craft 返回 404、/api/craft 返回 400，库存与 revision 不变。
2. 1332 个非空气物品各有独立 ID；默认 stack 名称逐项等于官方 1.21.1 简体中文翻译；16 色羊毛独立。
3. 控制台接受完整／裸 ID、精确中文／英文名称与整数数量；同名时明确拒绝并要求 ID；仅写入唯一实验背包。
4. 整组仍按 MC 64／16／1；计数添加按原版堆叠分格，未知物品、坏数量、容量不足、写盘失败不留部分添加；重试不重复添加。
5. 已有材料、建筑、选择、耐久与自定义名称保留；没有存档 schema 变化。测试不消费正式已有材料。
6. 原生和 MC 构建成功、补丁可重建、发布与安装哈希一致；F8 可打开面板。游戏内领取／选择／消耗点击单独记录，不以 HTTP 检查代替。
7. 背包和目录使用按 ID 对应的图片，鼠标悬停显示完整中文名称、ID 和数量／最大堆叠；不将组件类型预览冒充实际属性外观。

关键决策：官方 zh_cn 文件由准备脚本固定 hash 下载到 ignored downloads，不上传原版资源，也不打入插件 JAR；加载失败停用 API，不回退为猜测译名。
用户报告 Insert 只触发 Steam 截图：日志确认插件加载／渲染初始化正常，故菜单键改为 F8。
只更改安装拥有的设置文件中的 key_toggle；先备份、保留其余设置，不修改 Steam 设置。安装默认和启动提示同步，面板显示实际设置键。

已重新执行：MC 构建通过；15 项真实隔离世界规则检查全部通过且正常停服；18 项隔离桥接 HTTP 检查通过；中文 C++ 解码检查通过；原生构建／固定源码准备及反向补丁检查通过。
正式 8766 check_authority 改为只读取与必拒绝请求，1332 项官方名称匹配及 7 个拒绝请求通过，正式背包状态保持不变。
新版 ASI 安装哈希核对成功，后台已启动。Python／PowerShell 语法、文档链接、JSON 与 Git 格式在收尾继续检查。
首次新测试中 MC 将 custom_name JSON 对象归一化为字符串，修正测试夹具为 CODEC 规范形式后全测通过；实际自定义文本无丢失。
桥接摘要改为中文名称后同步修正旧英文摘要断言，18 项重测通过。

游戏内 F8 打开及中文名称由用户确认／截图验证；用户继续要求改为图片并在悬停显示中文名，见下段。公开最新摘要见 inventory-validation.json。
M2／M3／M4／M5／M6b 仍未完成，不把领取／选择称为可见手持或物品用途。


## 2026-10-04 物品图片与中文悬停提示

用户指出英文名称来自 World Builder 主窗口，并要求 MC 物品以图片显示、鼠标悬停出现中文名字。
World Builder 列出的是红沙场景资源，不是 MC 物品。默认改为只显示 MC 面板，复选框可打开原工具。
源码复核发现最初隐藏方案跳过 editor::Draw 的后台刷新；最终补丁保留每帧排队、保存、放置等任务，只控制窗口显示。
Play Mode／放置模式沿用显示路径；此修正构建、补丁与安装已验证，最终版本的游戏内后台任务行为未实测。

背包与目录改为自适应图片格：背包角落显示槽号／实际数量；目录点击图标获取一组。
悬停显示 MC 返回的完整中文名称、物品 ID、数量／堆叠和放置支持，不用截断名称填满格子。
图标加载／缺失暂显示问号；中文名称不会因图片未加载而丢失。

图标采用 Minecraft Item Gallery 固定提交 8888a461f088c6b907f13c14f25a12d90a481ae3 的
1.21.1 游戏导出图。ZIP SHA-256 固定在 config/item-icons.json；1332 个独立 ID 全覆盖，
1325 项同名图，7 项按明确映射使用同类型组件预览，界面注明属性外观不随实际组件变化。
不改变 MC 的药水效果、附魔、自定义名称、耐久或库存，不把图片当作已经接入手持模型／世界材质。
所有 ZIP／PNG 都在 ignored downloads；来源和 MIT 工具许可保留，图片不上传或打入 ASI。
安装脚本拒绝非自有文件及链接目录，全部 1332 文件写入安装清单，卸载沿用哈希校验保护。

验收证据与结果：

- python tools/prepare_item_icons.py：1332 张 RGBA PNG 的 CRC／数据完整性与固定 ZIP 哈希通过。
- python tools/check_item_icons.py：与真实 8766 目录逐项 ID 比对，1332／1332、文件名独立、来源映射／哈希一致；损坏／截断 PNG 被拒绝。只读，无库存修改。
- 独立 Pillow 解码全部 1332 张成功、无全透明图；抽样拼图目视确认原木、木板、台阶、楼梯、16 色羊毛中的样本、工具、粗铜、食物和特殊类型对应。
- 原生最终构建通过；SourceBuild 固定源码与反向补丁检查通过；中文协议／18 项桥接检查重测通过。
- MC 清除未使用的旧翻译字段后再次构建通过；规则行为无变更。15 项真实隔离规则检查仍为本次功能验证依据。
- 用户确认“图片已显示，悬停显示橡木原木”：图片版界面验收通过。先前用户也确认 F8 可打开，截图显示中文橡木原木、圆石、泥土等。
- 最终 ASI 与 artifacts／安装清单哈希一致，所有 1332 张安装图片哈希一致；设置仍为 F8，原有背包 revision=10 与材料不变。
- 正式 check_authority.py 再次通过：1332 项官方名称、7 个必拒绝请求，用户状态不变。

用户按 Escape 停止了自动界面操作；后续界面证据为用户实际确认。
游戏内直接添加／领取／选择／消耗按钮点击尚未复测，相关后端行为已在隔离世界／HTTP 检查通过。
本次中文与图片需求已获得用户画面确认；M6a 整体保留进行中，下一步验收一个新加物品的按钮操作，
不消耗已有材料。M2／M3／M4／M5／M6b 的未完成状态保持不变。

收尾检查：Python AST、全部 PowerShell 脚本解析、已跟踪 JSON 与 Markdown 相对链接、上传范围检查通过。Git 格式检查发现 upstream.patch 的合法空白上下文行被视为源码行尾空格；剥除会损坏补丁，故保留协议原样，并仅对 .patch 配置 whitespace=-blank-at-eol；反向补丁与普通差异格式检查通过。最终游戏进程 /api/status 确认 ready=true、buildOk=true、版本 1.0.0.2976；这不替代后台刷新行为验收。

## 2026-10-06 持续目标：HUD 实测和真实资产管线

接手时保留全部未提交的 HUD、模型及诊断工作，未重置文件或存档。
参考库固定提交为 `671544554523eb3ae8048c18d4eb8973f5f19652`；
其知识库没有红沙专用笔记，GTA 客户端颜色/深度合成不等于当前 1.21.1 原生内容适配。

### 九格修复、构建和游戏内结果

- 修复建造请求快于一帧时未失效旧库存的竞态：提交带正文的修改立即要求 MC 回读，
  不自动重试消费。新用例在旧实现失败，修复后通过。
- 游戏实测发现上游 OnPresent 关闭菜单时提前返回，HUD 和轮询均未执行；已移除该返回，
  保留关闭时全部输入捕获标志清零。差异进入 upstream.patch，反向检查与固定 SourceBuild 通过。
- `check_hotbar_ui.py`、原生库存解码、18 项隔离桥接 HTTP 检查通过；原生插件构建通过。
  最终 ASI SHA256 为 `461ce7e6b3f9b959aa56d1d9ec46fe7c1c2d0d0c6a7875d02f814fc98e3d771e`，
  build/artifacts/实际安装保持一致；游戏 ready/buildOk 为 true。
- 用户授权短暂接管、正常退出和重启。此前存档备份到本机
  `backups/before-hud-20261006/red-saves`，更新脚本另保存旧 ASI；未强杀游戏。
- 实际 2560×1440 游戏画面中原 UI 与九格栏同时存在。关闭菜单时后台选择第九空槽后
  显示/高亮真实第九槽；恢复原第二槽后正确回显。暂时停止桥接时变为离线、图片变暗且
  高亮消失；恢复桥接后自行重新确认库存。没有使用虚构满值生命/饥饿/经验条。
- 本轮选择检查前后 inventory/36 slots/blocks 相同，selectedSlot 恢复为 1；revision 从
  16 增为 18，仅两次选格修改。未领取/消费材料或放置/拆除建筑。正式只读名称及七个
  必拒绝请求检查通过，1332 项官方名称一致。
- 证据留本机 `runtime/hud-world-closed-20261006.png`、`hud-world-refresh-20261006.png`、
  `hud-world-disconnected-20261006.png` 与 `hud-inventory-check.json`。
  本轮自动 F8 短按未完成菜单开关/点击验收，工具还检测到物理用户输入，未绕过输入保护。
  菜单点击、其它分辨率实机和世界构建器后台放置仍须单独验收。

### 模型资产和验证

- `build_steve_asset.py` 实际官方客户端模型导出及 13 项检查通过；诊断基线 6 项、角色目录
  22 项保护检查通过，均不调用原生外观函数。
- 新 `build_block_assets.py` 导出六类 14 项真实模型和九张原版纹理；1062 个客户端资源文件、
  6766 模型选项的模型/纹理依赖可解析。7 组独立检查通过。141 ID/158 选项缺少 cuboid
  elements，明确保留特殊渲染研究，未拿立方体替代。清单不是完整注册/合法状态验收。
- 新 `prepare_native_steve.py` 只读实际红沙归档与固定 MIT CDMW 工具链：447 骨、189 palette、
  13162 模板顶点；无编辑 PAC 重建字节相同。候选为 288 顶点/144 三角，四个 LOD 保留完整
  Steve 几何，保留原 palette/draw descriptors/runtime metadata，真实权重与 UV 回读通过。
  修复默认 LOD 会把远距离模型减为三个三角的问题，也修复报告输出链接检查遗漏。
- `py -3.12 -B tools/check_native_steve.py --rebuild` 15 项全通过；根代理另执行默认检查为
  14 通过/1 重建项跳过。独立审查核对实际输出哈希、骨索引、面绕序和原木三轴端纹。
  全部官方/派生资源留 ignored build/downloads，未写原版归档或安装候选模型。

下一步：真实原木的原生 PAC/材质/纹理/prefab 加载与碰撞；Steve 的皮肤材质、原生骨变换、
动画/贴合、受控外观及可恢复的持续应用。两套装备、真实 HP 心形、全部特殊方块与工坊仍未完成。
完整离线复建步骤见 [asset-pipeline.md](asset-pipeline.md)。提交/上传结果以实际同步结果为准。

收尾：32 项改动的 Python AST/JSON/相对链接与本地资源上传边界检查通过；已改 PowerShell
解析、Git 差异格式、原生 build/artifacts/实际安装哈希一致检查通过。`um publish check`
对 88 个 Git 可见文件的独立快照返回 0 failures/0 warnings；未包含 ignored 资源、存档或日志。
该 lint 未使用 --game（本项目编译的 ASI 也已安装在游戏目录，字节相同不表示原版文件）。
同步脚本临时仓库检查通过，真实提交/推送由收尾调用执行。

## 2026-10-06 继续目标：原生原木、Steve 材质与可恢复 overlay

持续目标恢复为 active。实现和验证的本轮小步如下：

- `prepare_native_block.py` 只读实际 0000 模板，生成三轴静态 PAM/PAMLOD、Standard
  PAMI、原 HKX/meshinfo 和重定位 prefab，共 21 项候选；不是角色 PAC。无编辑重建
  字节相同，24 顶点/12 三角，三轴使用真实 MC 端纹/侧纹 UV，远 LOD 保留完整立方体。
  `py -3.12 -B tools/check_native_block.py --rebuild` 13 项通过，真实重建全部一致。
- `prepare_steve_material.py` 生成真实皮肤 BC3、BC5U normal、DXT1 常量图及 Plain PBR
  身体材质候选。保留原 PAC palette/运行属性，18 个材质包装/6 组变体回读；没有
  actor/prefab 引用或控制外观接入。`check_steve_material.py --rebuild` 14 项通过。
- 两套 DDS 使用独立 Pillow 12.2.0 解码全部 mip；原木底层最大 RGB 误差 4/平均
  1.705729、低 mip 最大误差 21，Steve 底层最大 4/平均 1.479367/alpha 误差 0。
  没有声称压缩无损、透明裁切/原生过滤/光照/动画或装备正确。
- `prepare_asset_overlay.py` 为两套候选分别预演独立 PAMT/PAZ 与 PAPGT/PATHC；
  原木 21 项/56736 字节 PAZ，Steve 5 项/332752 字节 PAZ。原 39 项挂载记录与
  PATHC 291531 项/654 header/12 collision 保留，新 DDS 各增加三项。0036～0040
  是已有可选保留目录，不当作空闲；本机选 0041。完整 DDS 使用 raw flags=0，
  不继承 PartialDDS 存储；材质按原 LZ4/ChaCha 编码。两套 13 项预演检查通过，
  包内逐项解码与输入一致；预演阶段只写 ignored build。
- `install_asset_probe.py` 仅允许本项目 21 项原木，重新检查源索引与所有权，先备份
  metadata/存档，PAPGT 最后挂载；恢复先解除挂载，不覆盖后续存档。15 项隔离
  安装/故障回滚/硬中断/并发锁/外部修改保护检查通过，检查未修改真实游戏。
- `python tools/check_native_block_probe.py` 最终 25 项隔离 HTTP 检查通过，初始 fixture
  改为真实非空 Untitled 1。覆盖原生创建项目/精确初始归属、赋项目前失败清理、外部
  项目变化拒绝、自动保存及中途启用拒绝、缺日志/跨进程/丢响应/碰撞与清理失败。
  不调用真实对象 API，visualVerified 始终 false，画面证据另验收。

### 首次安装和中断记录（后续已恢复，见下一节）

实际执行 `py -3.12 -B tools/install_asset_probe.py --install --plan build/native-asset-overlay`
成功，收据 ID 为 `ff31f4892ff445aea30b78628f83e094`，状态 installed，自有目录 0041。
metadata 与两根合计 36 份存档备份在本机
`backups/asset-probe-ff31f4892ff445aea30b78628f83e094`。没有修改原版 PAZ/PAMT/PAPK/PAVER。
原 PAPGT SHA256 为 `2997a04a76e5812d3a4b7840ac0615cdfc3d7d865244e133023c415b5f918646`，
原 PATHC 为 `5d2f9d61c661e2c628c5482d026358e7ca049ad6deec9a92c17ba547870353ef`。

启动现有后台并进入红沙世界成功，原生 ready/buildOk=true、版本 1.0.0.2976，原 UI 与
九格仍显示。发现上游 POST objects 会 EnsureEditingProject，首次新 UID 默认属于
当前编辑项目/可能创建空 Untitled，并写设置；探针修正精确记录初始归属与失败清理，
要求项目 autosave=0，不调用项目保存或删除旧项目。正式当前已有 Untitled 1、对象数 0。
这项真实行为不能称为完全无项目副作用；诊断项目不会自动成为正式 MC 桥接资源映射。

用户回复空地“就绪”后，Computer Use 返回物理 Escape 停止信号。本轮即停止界面操作，
**尚未调用 --spawn，未消费 MC 材料、未创建原木、未验收原生显示/碰撞，也未执行恢复。**
收尾时游戏 PID 57428 仍运行，故不在运行中改索引。0041 与 active receipt 保留；下一次
必须先检查当前进程和收据，再在用户正常退出游戏后运行
`py -3.12 -B tools/install_asset_probe.py --restore`，核对原 metadata 哈希和目录删除。
若继续同一进程测试，应先检查新鲜玩家/相机及项目状态，只生成一个 journalled 对象，
分别验收登记、实际碰撞、画面，再在同一进程清理并退出恢复。不能盲目重放消费请求。

新依赖许可证与来源已记录，资源/存档/运行证据留本机，公开内容为转换/保护工具和文档。
完整 Steve、持续外观/卸载恢复、两套装备、正式全部方块映射、真实 HP 心形与工坊均未完成。

Steve 下一项具体离线检查：克隆真实 nude prefab 的新 crimsonmc 路径，将 CD_Nude
SkinnedMeshComponent 的 PAC 引用指向候选，保留 CD_Underwear 与 PAB/PABC/PAPR。
只读研究在内存里完成一处路径替换/六处 pointer relocation；尚未产出或加载该 prefab。
原生 app_xml 是 NPC 外观名单，不能据此推定当前 Kliff 受控身体；必须另查实际外观回链
与刷新生命周期，不把新场景物体或共享旧 PAC 替换称为持续 Steve 模式。

收尾：十个新 Python 工具语法、公开 JSON/Markdown 相对链接、Git 差异格式通过；
99 个公开文件没有新增游戏素材、运行日志、存档或备份，Pillow 许可证与本机原文一致。
源代码提交/推送结果以本轮实际 sync_github 输出为准。

## 2026-10-06 恢复验证：原木加载失败、清理与原始资源恢复

用户明确恢复游戏接管并确认前方平坦。旧进程已结束，重新进入世界后核对支持版本与
ready/buildOk，正式探针在新游戏实例中只提交一次原木生成。之前陡坡被前置检查拒绝；
新工具最多探测七个附近位置，逐点检查中心/四角并避开登记对象，全部不合格不生成。
`python -B tools/check_native_block_probe.py` 最终 **28/28 通过**，含近处候选、全陡坡拒绝
和用户对象保留；中间一次检查被中断，确认进程不存在后完整重跑通过。

实际运行 `python -B tools/probe_native_block.py --spawn`：选中前方 4 米位置，五点地面
高差 0.07922 米。新 UID 被登记，原生日志返回 SceneObjectClient，随后物理验证失败
（未检测到一米碰撞增量）；实际游戏画面也没有原木。**加载/显示/碰撞未通过**，返回
指针或 pending=0 不能证明资源读取成功。证据留本机 `runtime/native-block-probe.json`
及 `native-oak-before-20261006.jpg`、`native-oak-load-failed-20261006.jpg`。

同一进程执行 `--cleanup` 成功，登记对象移除、地面回到原高度。日志 phase=cleaned、
registryRemoved/collisionRemovedVerified/mcStateUnchanged=true；MC revision 18、36 槽
内容与建筑不变。项目自动保存保持关闭，无新编辑项目，诊断没有显式保存旧项目。
正常退出后再次核对，settings.txt 和原 Untitled 1.cdproj 哈希也与测试前相同。
随后通过游戏退出确认正常退出，确认进程结束，再执行 `install_asset_probe.py --restore`
成功。收据 `ff31f4892ff445aea30b78628f83e094` 转历史 restored，active receipt 与 0041
目录不存在；原 34 份 PAMT、PAPGT/PATHC/PAPK/PAVER 共 **38 文件**哈希全部匹配安装前。
未回滚游戏后来存档，未替换 ASI/JAR，测试对象和临时包均已收尾。

离线核对未发现缺失的同名配套文件：真实蓝块与候选均为 PAM/PAMI/PAMLOD/HKX/
meshinfo/prefab 六类；新旧 flags、folder hashes 与资源引用可核对。当前没有新路径
实际读取跟踪，不能据此确定挂载或文件格式哪层失败。下一步通过已有引擎读取契约
获取固定白名单资源的实际读取结果，再决定修复；不盲目重复生成和消费 MC 材料。

### 同轮离线资产与真实注册表

- 新 `prepare_steve_prefab.py` / `check_steve_prefab.py`：完整解析真实 nude prefab 的
  CD_Nude/CD_Underwear，仅修改前者的 PAC 路径；一次等长路径改动、六处指针重定位，
  其它字节保持一致，逆改与原文相同。保留内衣和 descriptor 原文及真实 PAB/PABC/PAPR
  依赖。`py -3.12 -B tools/check_steve_prefab.py --rebuild` **16/16 通过**。
- 七资源报告在 `build/steve-prefab/steve-prefab-report.json`，新增 prefab 与 descriptor
  合并原五项皮肤/模型资源；全部集成标志 false。七资源 overlay **13/13 通过**，PAZ
  334976 字节。该次预演基于尚挂载 0041 的快照规划 0042，恢复原木后计划过期，须
  重建再验证。**Steve 包未安装**；受控身体/动画/装备/持续应用仍未实现。
- 新 `build_block_registry.py` / `check_block_registry.py` 使用固定官方 1.21.1 数据生成
  入口（客户端及 46 个库哈希验证），实际生成 **1060 种方块、26684 个合法状态**。
  完整检查属性乘积、唯一默认状态、两种 ID 空间连续/唯一，与所有客户端资源关联。
  1062 个资源文件中额外的 item_frame/glow_item_frame 不在方块注册表。真实报告及资源
  留 ignored build；没有启动客户端/服务端世界，没有更改当前权威库存。
  CLI 审查修复相对客户端/Java 路径因切换 cwd 失效，以及自定义输出与已验证输入的
  同路径/硬链接冲突；拒绝发生在生成器启动前，输入保持完整。
  `python -B tools/check_block_registry.py --rebuild` 最终 **10/10 通过**，含实际相对路径
  重建和 NTFS 硬链接拒绝。这是 vanilla 注册表，不是 Fabric 运行时注册表，也不表示全部
  状态的红沙模型/碰撞、特殊渲染或物品用途已经实现。

### 为定位失败新增固定资源读取接口

新增 `mc_resource_probe.h/.cpp` 与可复建上游补丁；POST 只接受 27 个蓝块/原木固定
枚举，返回 ticket 后在游戏线程一次处理一项。原生存储与解码长度都先限定 16KiB，
分离 guarded load/metadata/read/release，取得 handler 后只尝试释放一次。旧
GameReadFile/Range 逐字与固定上游一致。结果只含长度、头部、FNV-1a64 及释放状态；
最多 16 条队列/结果、30 秒 TTL，过期但未执行的任务仍占槽，已完成结果可淘汰以支持
27 项顺序诊断。只对首 64 字节全零的异常最多重试三次，不在游戏线程 sleep。

`python -B tools/check_native_resources.py` **22 项隔离行为 + 2 项源码边界检查通过**：
实际 backend 提取到 host harness、异常释放、双尺寸上限、队列停滞跨 TTL、未知枚举、
严格请求和顺序 27 项；不连接游戏。新客户端 `probe_native_resources.py` 默认 15 项，
校验本地蓝块/候选 SHA，再比较引擎长度/头部/FNV，要求同游戏实例与 MC 状态保持。
`py -3.12 -B tools/check_native_resource_probe.py` **22/22 通过**，均为隔离 HTTP。
超时不重提，完整报告只写新的 ignored runtime 文件；不生成实体或消费材料。

完整 ASI 编译成功，SHA256 `ad8835ecddd4938b39ce9735e12e15ee2cbad6b269bf3c546c32277ddd39d95c`，
12751872 字节。`prepare_environment.ps1 -SourceBuild` 验证固定上游、补丁及新文件复制
通过，未改已有 vendor；42 个 Python AST、7 个公开 JSON、50 个 Markdown 相对链接、
PowerShell 解析和 Git diff 格式检查通过。108 个 Git 可见文件没有 ignored 资源混入。
安装及实机资源读取结果另记；这些离线检查不改变上一节原木加载失败的结论。

### 读取诊断安装后的再次接管中断（之后已恢复，见下节）

独立源码审查无阻断问题。成功构建后更新 artifacts/native 与实际插件安装，三份 ASI
SHA 均为 `ad8835ecddd4938b39ce9735e12e15ee2cbad6b269bf3c546c32277ddd39d95c`；
原插件留在 backups，更新脚本重新核对 1332 图标及安装清单。没有修改 MC JAR。
再次执行 `install_asset_probe.py --install --plan build/native-asset-overlay` 成功，新的
active receipt 为 `51159fa10a564fa392027e71af157471`，目录 0041，备份在
`backups/asset-probe-51159fa10a564fa392027e71af157471`。

启动游戏后首次定位窗口，Computer Use 立即报告用户物理 Escape 停止。之后没有再
调用 Computer Use，也没有向资源读取/生成 API 发请求。只读收尾确认游戏 PID 14624
（22:49:36 启动）仍运行、收据 installed，所以没有运行中恢复索引。**新读取接口尚无
实机读取结果；本次没有新增诊断实体。** 此处 PID 只为本次记录，下次必须重新枚举。

下一次若只恢复包，先正常退出红沙，再执行 `py -3.12 -B tools/install_asset_probe.py
--restore`，核对新收据转 restored、0041/active receipt 消失及原始 38 文件哈希。
若用户重新授权继续游戏接管，再获取新鲜窗口/游戏实例状态，执行资源读取客户端，
随后退出恢复。上次 spawn journal 已 cleaned，不能把旧 UID 用于新的游戏实例。
整个持续目标仍未完成；没有因界面接管中断将目标擅自标记暂停或完成。

## 2026-10-06 原生读取实测完成，第二次临时包已恢复

用户回复“恢复接管并完成诊断及恢复”后重新定位真实红沙窗口，游戏已进入法则大书库。
执行 `py -3.12 -B tools/probe_native_resources.py --output
runtime/native-resource-read-20261006-first.json`，退出码 0。默认 **15/15** 均第一次
读取成功，handler 均释放；蓝块/Y 轴原木各六项与三张 DDS 的长度、头 16 字节及
FNV-1a64 全部与本地 SHA256 校验过的模板/候选一致。gameInstanceUnchanged 与
mcStateUnchanged 均 true。没有生成新实体，没有提交库存操作。

关键实际长度：蓝块 prefab 1845、Y 轴原木 prefab 1840；meshinfo 均 3754，PAM 均
2276，HKX 均 1512；蓝块/原木 PAMLOD 1032/1288、PAMI 727/760。PAMI 原生 flags=48，
其余受检文件 flags=0。三张 DDS 分别 5608/11088/5608 字节。FNV 是非密码学摘要，
本次证明当前进程可定位并读回这些资源；没有宣称引擎返回 SHA256 或验收画面/碰撞。
X/Z 两轴此轮未读。第一次失败的 spawn 属于早先的游戏进程，不能据此证明本进程在
显式读取之后再次 spawn 仍然失败；本轮按约定只读诊断，没有复试生成。

通过游戏正常退出确认关闭，查询进程不存在后执行 `install_asset_probe.py --restore`
成功。第二次收据 `51159fa10a564fa392027e71af157471` 为 restored，active receipt 与
0041 不存在；原 34 份 PAMT、PAPGT/PATHC/PAPK/PAVER 共 38 文件哈希全部匹配原值。
没有回滚后来存档，诊断版 ASI 保留正常安装，资源读取报告仅在 ignored runtime。

这项实机证据将后续工作从“包能否读到”推进到“改后的 prefab/mesh/material 如何
实例化”：不要安装此前仅用于假设检验的目录树控制包。下一对照须区分新 prefab 名称
与改动资源内容，或从真实装配结构找到具体不一致；仍不把能读文件当作能渲染模型。

## 2026-10-06 装配对照与 Steve 骨骼证据

固定 EXE 静态回链显示，场景生成走独立的 ResourceReferencePath 缓存/装配流程，
与本次原始文件读取不同。原有创建标志已经开启异步入场；没有依据修改标志或调用
未知 ABI。非空 SceneObjectClient 仍不能证明模型完成装配。真实 prefab 只有一个
MeshComponent，原木候选只改 PAMI 路径；逆改与原模板逐字节一致。meshinfo 的多个
字符串数组与通用 prefab 解码器不同，其解码报错不能证明文件损坏，未修改不明字段。

新增 `prepare_native_block_control.py` / `check_native_block_control.py`，在独立
`build/native-block-blue-alias` 制作 `blue-template-alias`：只将 Y prefab 换成固定原蓝块
1845 字节全文，原 PAMI 引用保留；另 20 项候选和所有模板字节保持。固定来源、唯一
差异、控制伪装、源变化、已有输出及真实 NTFS junction 等 **16/16 通过**。报告删去
原候选的几何结论，只保留来源、文件与全部 false 的集成标志。A 后续实机结果见下节。

安装器现在强制单一候选报告，逐项绑定资源 SHA/本地路径，收据新增 `probeVariant`、
`candidateReport` 和 `candidateReportSha256`。资源读回日志也记录试验身份，拒绝
伪装为普通原木的完整蓝 prefab；客户端 **23/23**、普通包安装/恢复 **16/16** 隔离
检查通过。对象日志的生成前安装核对与旧日志清理兼容性检查另记实际结果。

新增 `analyze_steve_rig.py` / `check_steve_rig.py`，固定九项真实输入与 CDMW 源码，
独立解析 447 骨 PAB、423 条 PABC，六个映射关节均在 PABC 覆盖内，另 24 骨未覆盖。
全 PAB bind×inverse 最大误差 9.21e-8，local×parent 与 global 最大差 4.35e-6。
288 顶点候选的中立变形最大位移 1.81e-6 米，与固定 CDMW 中立核心逐点一致；
**`py -3.12 -B tools/check_steve_rig.py --rebuild` 10/10 通过**。

六个关节中心仍偏离 0.231～0.356 米。MC 头/身体中心相同，原生两中心相距
0.6027556838 米，证明单一全局仿射变换无法同时修复。逐部位平移会让五个原接触面
分离约 0.573～0.625 米、脚底抬至 0.25448 米；没有采用此办法修改资产。报告里的
30 度关节旋转及逐关节 retarget 公式只是合成数学证据，不是实测游戏动画。

左右关节 X 符号相同，原生眼/脚趾链支持朝向 -Z，而当前 Steve 面向 +Z。原始 nude
prefab 实例没有序列化朝向变换，我方导入仅位置缩放与 UV V 翻转；actor 父变换仍未知。
下一静态候选应独立 Z 反射并修改法线/三角绕序、重算切线，不能用会翻左右的 Y 轴
180 度替代。当前工具只输出 ignored 报告，没有改 PAC/PAB，没有安装或控制 Steve。

### 新进程读取后再生成的实际结果

普通候选第三次临时安装收据 `27f848014a544ad3ae97920ab10e9dc3`，独立进程 PID 67640
（23:11:02 启动）进入法则大书库。资源报告
`runtime/native-resource-read-20261006-fresh-spawn.json` 再次 **15/15 一致**。随后仅执行
一次 `probe_native_block.py --spawn --journal runtime/native-block-fresh-read-20261006.json`，
前方 4 米首候选五点高度差 0.11035 米，通过场地检查，生成请求 UID 1 登记成功。
在该同一新进程中仍未看到原木，碰撞检查超时失败；这次明确是在资源读取成功之后
复试，不能再把失败仅归于早先进程。截图保存在 ignored runtime；没有重复生成。

同进程清理通过：registryRemoved/collisionRemovedVerified/mcStateUnchanged 均 true，
清理后地面差为 0。未新增编辑项目，settings 前后 SHA 相同。正常退出后第三次收据
已 restored，active receipt/0041 不存在，34 份原 PAMT 加四个 metadata **38/38** 哈希
一致；没有回滚存档。该次失败碰撞循环未保存每次 hit 数值，只保留超时结果，不能
事后编造数值；后续探针补充有界采样证据以便准确解释失败。

### A 蓝 prefab 别名已显示且通过碰撞；退出后恢复待完成

普通包恢复后，`build/native-blue-alias-overlay` 按恢复后的索引重新预演：21 项解包
逐字节一致，PAZ 56752 字节；`check_asset_overlay.py --output ... --verify-game`
**13/13**、`check_asset_probe.py --plan ...` **16/16** 隔离安装/恢复通过。
随后实际安装 A，收据 `ece6ea42e8154e878fb9be88a8511944`，启动 PID 69700
（23:22:32）。`runtime/native-resource-blue-alias-20261006.json` 的 15 项全部读回一致，
明确标为 blue-template-alias；Y prefab 长度 1845，读回原蓝模板摘要。

`runtime/native-block-blue-alias-20261006.json`，runId
`8c7c46e9-bb97-477b-8d8f-be05aa7489df`，同一新逻辑 prefab 路径只生成一次 UID 1。
位置与前次正常候选相差约 1 毫米，前方首候选五点差 0.11011 米。
**实际看到蓝块**，截图 `runtime/native-blue-alias-visible-20261006.jpg`；原生首次
碰撞采样地面增量 **1.152100 米**，落在原一米判定阈值内。日志的 visualVerified
仍 false，因为 CLI 不执行画面判定；这里的显示结论来自实际截图，且仅对 A 蓝块有效。
同进程精确清理完成，registryRemoved/collisionRemovedVerified/mcStateUnchanged 均
true，清理后增量 0；未新增项目。不能把此结果表述为原木模型或 MC 材质已完成。

这个对照证明新 prefab 路径可以实例化，失败进一步局限到改动的 PAMI/模型资源链。
新增 B `blue-material-alias` 只将新 Y PAMI 换为原蓝块完整 727 字节，正常原木 prefab
保持；另 20 项及所有模板不变。输出 `build/native-block-blue-material-alias`，报告 SHA
`61dceae254482c25180c16df7b3756d4d049477dbf8fa3d74c1826e6915a84eb`。两种控制最终
**21/21** 检查通过，A 报告仍逐字节兼容；资源客户端扩展后 **23/23**。实体检查最终
**41/41**，包含两种对照非 Y 拒绝、真实安装收据/文件绑定、旧日志清理、加载器错误
统一处理，以及创建/移除碰撞超时的有界实际采样摘要。B 未安装或实测。

A 清理后通过界面发送正常退出及确认，但进程仍存在。恢复器明确以“Close Crimson
Desert before changing the asset probe”拒绝，未写索引。重新定位/激活目标窗口后捕获
仍显示另一游戏，因此未发送进一步键鼠，已请求用户切回或正常退出。此处并非用户
Escape 停止，也没有强制终止进程。最新 A 收据仍 installed，备份保留在
`backups/asset-probe-ece6ea42e8154e878fb9be88a8511944`。

恢复顺序：确认红沙已关闭，运行 `py -3.12 -B tools/install_asset_probe.py --restore`，
验证收据 restored、0041/active receipt 移除，以及 sourceIndexes/untouchedGameFiles/
metadataBefore 合并的 38 项原哈希。然后才按恢复后快照准备 B overlay 并进行单次
实测。不要把已有 A 挂载收入 B 的元数据基线；不要拿已清理 UID 对新进程操作。
本轮 ASI/JAR 没有再次改动；源/控制独立审查无阻断。46 个 Python AST、7 个公开 JSON、
51 个 Markdown 相对链接及六项角色探针保护检查通过，资源和原始证据仍留 ignored。
