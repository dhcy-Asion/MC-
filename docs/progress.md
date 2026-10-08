# 当前状态与分阶段计划

更新日期：2026-10-08（Asia/Shanghai）。当前开发目录为桌面 `CrimsonMC`，仓库为
[dhcy-Asion/MC-](https://github.com/dhcy-Asion/MC-)。新聊天先读
[../AGENTS.md](../AGENTS.md)、[architecture.md](architecture.md) 和本文件。

本轮现场状态：2026-10-08 十三资源注册 v1 包进入游戏后闪退，收据
`90cdf0fca1ce4095aedc43d3515a1525` 已实际恢复；38 项原始哈希匹配，无 0041／active
receipt，36 个最新存档、完整 MC 状态、原点及 ASI 保持。用户随后确认恢复后同一
存档可正常进入、不再闪退。已发现新增注册项与私有 prefab 的组件列表不一致，
v2 已修复并通过候选／事务检查；实际正常进入，MC 块体已显示但定位错开且与原装备
混叠，完整外观未通过。用户退出后，v2 收据 `045d94ec45d74007a5dfd1c53dd8e00a` 已
恢复，原资源、最新存档与 MC 状态保持。随后原生头单引用对照已检查并安装，
用户随后确认原生头正常连接在肩膀上方，正常退出后收据
`57b18550c3e344c19278ecd6f0b9d2c6` 已恢复。新原生头模板／共同父骨候选离线检查
与事务通过后安装并有实际运行会话；核实进程结束后收据
`5dfe1a43fa9846d6a1f1399bd42a4e2d` 已恢复，38项原文件及退出时最新存档／MC保持。
该次恢复后用户补充MC头仍错位或未显示，外观未通过，不把原生采样记为显示通过。
随后已准备并安装只改原字节头PAMI的十三资源对照；当前收据
`5249d2f2339844f3a5b27b77d1353a66` 为 installed，有待实测／退出恢复的0041。
安装前核实实际游戏关闭，文件、最新存档／完整schema3 MC／原点／ASI保持；
当前等待用户手动进入同一存档并反馈方块头位置，不能宣称新对照已修复外观。
当前交接见 [current-state.md](current-state.md)。
用户手动启动／退出的选择保持，自动接管停止。

用户已于 2026-10-06 将剩余移植工作设为持续目标并要求开始执行，之后再次要求继续。
目标已建立且未标记完整移植完成。2026-10-08 工具重新核实持续目标状态为 active，
按用户授权的多智能体分工推进，没有缩减完整范围。
来源、路线和实测保护见 [../MODLOG.md](../MODLOG.md)。

## 当前里程碑

**当前优先 M4a：完整持续 Steve、仅 MC 装备与原装备禁用，进行中；新增 M5a MC 攻击。**
2026-10-08 用户更新持续目标：mod 启用后人物完整变成 Steve，不能使用红沙任何装备，
只能使用 MC 装备；点击控制栏物品加入 MC 背包；攻击完全变为 MC 模式，单击击退敌人。
该要求覆盖 2026-10-06 的两套装备及红沙战斗约定；禁用／卸载恢复、全方块、第三人称
装备变化、原 UI 与真实状态 HUD、分发要求保持。生命值来源未改为独立 MC 生存生命。
最新完整验收在 [steve-character.md](steve-character.md)；独立第四身份不再是本轮门槛。
当前可用的是真实 MC 库存／六类方块与蓝色原生碰撞代理，以及底部九格库存 HUD。
常驻显示、后台刷新与断线恢复已有实机证据；F8 开关／按钮点击仍待验收。全物品官方
中文图标、悬停、整组领取、按数量添加和 36 格选择／消耗已实现，具体手持及用途未接入。

MC 存档已升级 schema 3，增加四格人体护甲存储并保留完整 properties；原木 x/y/z
状态可放置并重启恢复。护甲存取及保存已验证，原生穿戴／效果与装备禁用尚未接入。
1060 种方块的 26684 个合法状态、原版模型选择及面几何已有离线导出，不能据此称全
方块已进入红沙。Steve 七资源 prefab／原生 palette PAC 仍为离线候选，持续外观、
骨骼／动画／MC 装备、原装备禁用、MC 攻击、心形血量和工坊均未完成。
已有独立分段蒙皮候选在合成姿态检查中使原来没有响应的肘／膝／手／足骨链带动远端，12 项真实资源
检查通过。本轮进一步拆出头／帽和身体／四肢两 PAC，完整四 LOD 记录保持，7 项检查
通过；私有 CD_Nude／CD_Head prefab 16 项检查通过。旧分件仍使用 00_0001 neutral；
当前 01_0002 配置与实机动画须单独验证，离线分件不是已装配的原生人物。
独立当前 neutral 补偿候选的 13 项检查通过，将该配置的离线中立回放最大误差从
约 8.9 cm 降到 0.0271 mm。现在已组合为 10 项私有头身资源：身体使用当前补偿，
头部按独立 Head0001 变体保留原字节，12 项真实重建检查通过；原生动画尚未验收。
Kliff meshparam 候选只改两个 MeshFileName，12 项检查通过。已生成含该 XML 的
11 项临时测试包，保留原发须、装备、HeadScale 0.92 与 CharacterScale 1.02571；
这些部分可能遮挡／影响首次显示，不能宣称已实现完整 Steve。

原木加载失败已定位到 PAMI XML 声明，并以单变量 C 对照验证。新一轮侧向放置消除
角色遮挡，X/Y/Z 在相同视角可见的三个面（-X、+Y、+Z）朝向分别核对通过，27 项
资源读回、三轴碰撞和清理通过；背面、底面、全部光照和采样仍未验收。正式建造
仍是蓝代理；纯模型选择层没有生产准入配置。
本轮收据 `178c07aa03734bc49e7a7395df9bafe1` 已在实际进程退出后 restored，38 项
原始哈希一致，无 0041／active receipt／测试对象。材料、36 格与选中格保持，revision
因四次合法建造操作由 18 增至 22。原有放置原点已逐字恢复并正常重启桥接，保留后来
游戏存档。历次失败／对照和恢复记录保留在文末，不代表当前未恢复状态。

外观探针已实机稳定读取当前身体→外观控制器→owner，以及 7 组 mesh 选项与 250 组
装饰声明；没有写入外观、执行刷新或加载 Steve。CharacterScene 及其参数资源已获得
部分实读证据，实际渲染组件被严格识别为 SkinnedMeshComponent；专门只读分支
已在恢复原版资源后的新游戏实例完成双采样，Scene、参数回链与资源选择字段稳定。
可选资源身份头读取中两个实读资源的候选 RTTI 位置均为代码，因此旧结果保留 rejected。
独立的构造／消费者限定模式已完成 76 项检查与实机双采样：两项父资源 +68 指向同一
嵌套头，vtable RVA 0x5B426C0；类型、descriptor 与应用 ABI 仍未准入。没有执行换装。
新增 schema 6 输入属性模式的 93 项隔离检查、40 个固定 EXE 字节窗口通过。实际
双采样完整链稳定，PAB 声明为 `character/model/1_pc/1_phm/phm_01.pab`，PAC 声明
为空；整体如实为 notReady，不能把输入属性等同于最终所选渲染模型。诊断前后完整
MC 状态保持、原生对象 0、38 项原始资源哈希一致；这是安装前基线。
随后十一资源包已完成一次真实安装／启动／退出后恢复。新会话的受控外观选项表
实际包含两私有 basename，Body/Head 的默认候选均为 0 且合法，确认新配置被读取；
窗口接管再次被物理 Escape 停止，未取得游戏内模型画面。用户随后明确反馈进入世界后
仍是原来的红沙角色，因此首测外观切换未通过；配置读取不能替代实际装配。
用户退出后按实际进程结束恢复；原始文件一致，无临时目录／待恢复收据，最新存档
逐文件保持、MC 完整状态未变。没有把这次配置观测记为持续 Steve 已实现。
随后已准备只增加原字节头描述文件的十二资源对照，8 项候选检查和 23 项事务检查
通过，旧十一项 payload 不变；schema 7 初始 Appearance key 诊断 103 项检查通过。
用户授权此次对照后实际安装成功，但启动请求被工具报告的物理 Escape 停止，确认
无游戏进程后立即恢复。38 项原始文件与 36 项最新存档一致，MC revision 22 保持；
没有游戏内对照结果或新 key 观测。接管保持停止，原始资源已恢复，无待清理项。
持久操作日志及
会话／对象条件已接入正式蓝代理同步，实机放置／恢复／拆除、后台重启验证通过。
现有观测不证明所选渲染资源、应用 ABI、刷新线程或恢复生命周期。

资产细节见 [asset-pipeline.md](asset-pipeline.md)，静态／只读证据见
[native-character-contract.md](native-character-contract.md)，路线见
[native-character-feasibility.md](native-character-feasibility.md)。M1 基线提交为 `1bb0775`，
M4a 与 M6a 保持进行中，完整移植目标仍为 active。

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
最新选择为复用原版控制身份，启用期间完整持续 Steve，禁用恢复；仅 MC 装备，
禁止全部红沙装备，单击 MC 攻击与实际敌人击退。心形 UI 仍须真实血量来源，
未重新要求独立 MC 生存生命。模型／方块／装备／攻击按最新表分别验收。
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
| M4 Steve 模型和装备（旧独立身份方案） | 原独立第四角色及装备隔离设计 | 旧方案只保留研究，当前按 M4a 的 MC 装备及原装备禁用验收 | 旧方案未开始，不作为当前门槛 |
| M4a 持续史蒂夫模式（最新优先） | 复用当前角色控制，启用完整持续 Steve、仅 MC 装备、禁用恢复及方块 | 身体／动画／MC 装备正确，无原部件混叠；所有红沙装备使用入口被禁用；重载保持，停用恢复 | 进行中；九格常驻/刷新/断线实测通过，F8 点击待验收；MC 块体已显示但旧包装配错位，新头包等待画面；装备限制未实现 |
| M5 真实心形血量 | 将真实 HP／最大 HP 显示为心形 | 与真实受伤、治疗、最大 HP 变化一致，切人物不串读数；不显示虚构饥饿／经验 | 未实现，须验证读取链和行为事件 |
| M5a MC 攻击／击退（2026-10-08 新要求） | 原攻击抑制、MC 单击输入、实际敌人命中／伤害／击退、MC 装备规则 | 一次点击一次攻击，菜单不攻击；实际目标、遮挡／距离／间隔与击退方向正确；MC 装备效果及耐久一致，停用恢复 | 未实现；当前无原生目标／伤害／击退调用合同 |
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

3. 最新优先级是 **M4a 启用期间持续 Steve、禁用恢复**。先核对实际身体的外观对象／线程与资产绑定，
   不写猜测的原生指针；M2/M3 的独立第四身份不再阻塞本轮，M6a 未验收按钮保留。
   不消耗用户实验材料。
4. 当前不以独立新身份 M3 作为门槛；继续把当前 rig 补偿与私有头身部件组合，定位
   实际渲染资源与应用／恢复接口。每完成一个里程碑检查、更新本文件、写 CHANGELOG
   并通过同步脚本正常推送，保持完整持续目标未完成。

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

### A 蓝 prefab 别名已显示且通过碰撞；后续已恢复

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
Escape 停止，也没有强制终止进程。当时 A 收据仍 installed，备份保留在
`backups/asset-probe-ece6ea42e8154e878fb9be88a8511944`。

恢复顺序：确认红沙已关闭，运行 `py -3.12 -B tools/install_asset_probe.py --restore`，
验证收据 restored、0041/active receipt 移除，以及 sourceIndexes/untouchedGameFiles/
metadataBefore 合并的 38 项原哈希。然后才按恢复后快照准备 B overlay 并进行单次
实测。不要把已有 A 挂载收入 B 的元数据基线；不要拿已清理 UID 对新进程操作。
本轮 ASI/JAR 没有再次改动；源/控制独立审查无阻断。46 个 Python AST、7 个公开 JSON、
51 个 Markdown 相对链接及六项角色探针保护检查通过，资源和原始证据仍留 ignored。

随后只读复核进程已退出，按上述恢复顺序执行成功：A 收据 restored，0041 与
active receipt 消失，38 项原哈希全部匹配。无需用户再处理先前退出请求。随后按
恢复后的元数据生成 `build/native-blue-material-overlay`（0041，21 项，PAZ 56704），
作为 B 对照的新独立计划，未携入 A 挂载。

### B PAMI 对照已安装，窗口显示受阻，尚未实测

B 计划封装与真实索引检查 **13/13**、隔离安装/恢复 **16/16** 通过。确认红沙无进程
及无窗口后实际安装 B，收据 `1c37bb00badf44bfb1eaca55fb36e8d8`，备份在
`backups/asset-probe-1c37bb00badf44bfb1eaca55fb36e8d8`。新进程 PID 70052，
23:38:09 启动。虽然枚举得到唯一红沙窗口，激活和重新捕获仍持续显示另一款游戏，
没有依据向目标菜单盲发按键；本次未进行 B 资源读取或生成，没有新的诊断 UID。
已请求用户手动切回红沙，或正常退出后恢复包；不将经过时间当作答复，也没有强杀。

如果继续 B：先重新枚举真实窗口/进程并确认进入世界，再执行资源客户端
`--assets build/native-block-blue-material-alias/native-block-report.json`，使用新的 runtime
输出路径；成功后才单次 `--spawn`（新独立 journal），查验、清理、正常退出和恢复。
如果先恢复：确认进程不存在后 `install_asset_probe.py --restore`，核对最新 B 收据、
0041/active receipt 和原始 38 项哈希。旧 A/普通原木对象均已 cleaned，不可重复删除。
本次持续目标仍 active，完整原木/Steve/装备/HUD 血量/工坊尚未完成。

## 2026-10-06 B 材质路径实测与后续单变量对照

本轮确认游戏仍为 PID 70052 / 创建时间 `134357746894596369`，先执行 B 资源读取
客户端，因主菜单 `ready=false` 在预检停止，未提交任何资源读取或生成请求。日志
`runtime/native-resource-blue-material-20261006.json` 的 results 为空，MC 前快照尚未
取得，因此 mcStateUnchanged=false 表示未能证明前后相同，不能解释为库存已改变。
新增诊断记录失败时实际 status/HTTP 状态，场景未就绪与版本失败可在文件中区分。

随后获得正确红沙主菜单画面，正常继续载入存档；原生 ready/buildOk 成功后执行
`probe_native_resources.py --assets build/native-block-blue-material-alias/native-block-report.json
--output runtime/native-resource-blue-material-ready-20261006.json`。runId
`f45a5d3e319a456cbcf7e7edc2375070`，**15/15 首次 read 且摘要一致**，同进程、MC 状态
保持。蓝模板/Y 原木/三张 DDS 均由本地 SHA 校验后的候选对照，不把读取当显示。

确认实际世界及空地后，仅一次执行 `probe_native_block.py --spawn --journal
runtime/native-block-blue-material-20261006.json`：runId
`47f5f2c3-80e6-4196-9462-a23425e2a57b`、UID 1、variant `blue-material-alias`，位置
`(-10662.134321374773, 1794.85202, -3702.0926325653973)`。实际看到蓝色立方体，截图
`runtime/native-blue-material-visible-20261006.jpg`；首次碰撞增量 **1.152100 米**，
hit Y=1795.86377。CLI visualVerified 仍 false，显示结论由独立画面核对给出。

同进程、同日志 `--cleanup` 成功：registryRemoved/collisionRemovedVerified/
mcStateUnchanged 均 true，清理后地面增量为 0。没有新项目，settings SHA 保持
`f95d3f7e835d9b51f6bdf233ad8b67dda2ac7b951d7661d151299d886ea3a35e`。此结果证明
正常原木 prefab 与新 PAMI 路径可装配原版蓝模型；还未证明正常原木 PAM/DDS 成功。

只读 PAMI 差异研究记录于 ignored `build/pami-serialization-research`。普通 760 字节
PAMI 含固定 39 字节 XML 声明；只删除该前缀得到 721 字节，独立 ET/DOM 树语义与原
普通候选一致。原游戏模板 727 字节无声明；CDMW/WB 的工具解析器不构成游戏原生
解析规则证据，所以 XML 声明仍是待实测因素，尚未宣布根因。

新增 C `oak-pami-no-declaration` 固定对照，输出 `build/native-block-oak-no-declaration`，
只改 Y PAMI、另 20 项及全部模板字节保持。候选 PAMI SHA
`13594ac365e4dcb4f52f652c4a892c845bf9524b700d1fe521a88cf9e22fa07d`，记录原资源 SHA、
精确移除前缀与语义验证；来源不能是另一对照，A/B 报告保持字节兼容。生成器实际
检查 **27/27** 通过；资源客户端 **24/24** 通过，包含预检失败保留实际状态、零提交，
以及拒绝将去声明候选伪装成普通原木。实体探针加入 C 身份/Y 轴限制，最终完整
**42/42** 通过；初轮既有 test18 写临时日志遇 WinError5，单项和完整重跑通过，未
修改该断言或放宽保护。C 报告 SHA
`e9f91de76d859831537f74377e55aec6d0cb5959eede8da991acd8f1258b6819`。
C 当时未封装/安装/实测，需先正常退出并恢复 B；后续恢复结果见下节。

清理后红沙窗口采集又出现另一游戏画面，重新选择/激活仍未解决，未盲发退出快捷键。
已请求用户正常退出；本轮 B 收据仍 installed、备份保留，无未清理诊断对象。
不要将先前 A 的 restored 当作本轮 B 已恢复，也不要在游戏运行中改元数据。

### Steve 独立朝向候选

新增 `prepare_steve_orientation.py` 和 `check_steve_orientation.py`，固定前轮七资源
prefab 报告、骨骼分析报告及九项真实输入，输出独立 `build/steve-orientation`。
只修改 PAC：保持 X/Y、反射 Z、反射法线 Z、每个三角反序一次；四级 LOD 每级
288 顶点/144 三角，共 1152 条记录和 576 个三角。原模型的对称 Z 量化范围允许用
`qZ=32767-qZ` 做精确 15 位反射，descriptor/bounds 不变。其余六项候选、十个模板、
骨 palette/权重/UV/不透明字段均逐字节保持。

固定 CDMW 普通 writer 不写 authored tangents，不能仅设置 Python tangents 就声称
已写入原生数据。本工具对已验证的原生记录字段重建 UV frame；真实 donor 的 packed
方向对应 UV V 导数，bit31 对 U-from-cross 的符号关系由 11476 个唯一强样本支持
（5 正/11471 负、无矛盾）。这是 **source-backed empirical**，不是 shader ABI 或
实机验收；未知布局、矛盾样本、缺少顶点 frame 均停止输出。

`py -3.12 -B tools/check_steve_orientation.py --rebuild` **13/13 通过**，包含独立原始
字节 frame/几何核对、四级绕序、前后 no-edit writer 往返及真实重建逐字节一致。
最大位置反射误差约 `2.78e-17` 米，方向编码误差约 `0.000978`。候选 PAC SHA
`8f7b32db6063b7cc8ec71278a8ede09a9e375c2dfd80dedef13283ef77cc0539`，报告 SHA
`368bc03aa89f6d6eeb6be8d755488d48a8ee88907c3e50fffa711e8bc5949892`。
仍未安装 Steve，也未修复 MC/原生关节中心差异或验证实时动画/父变换/装备。

### 2026-10-07 恢复结果与停止接管

用户明确回复“已正常退出红沙”后，确认 PID 70052 已不存在，B 收据
`1c37bb00badf44bfb1eaca55fb36e8d8` 恢复成功，合并 sourceIndexes/untouchedGameFiles/
metadataBefore 的 38 个原文件全部匹配，0041/active receipt 移除。

依据恢复后的游戏快照构建 `build/native-oak-no-declaration-overlay`：0041、21 项、
PAZ 56704 字节，所有 payload 解包一致。`check_asset_overlay.py --output
build/native-oak-no-declaration-overlay --verify-game` **13/13**，`check_asset_probe.py
--plan build/native-oak-no-declaration-overlay` 隔离检查 **16/16**。随后安装 C 收据
`c6f59e15b4a54fc1939c9b2769658ec7`，但启动 Computer Use 时工具报告用户物理 Escape
停止，未再调用窗口工具或执行资源/实体诊断。只读核对无 CrimsonDesert 进程后立即
恢复 C，最新收据 restored、0041/active receipt 消失，38 个原始哈希再次全部一致。
因此没有待恢复临时包、没有未清理诊断实体；C 的游戏内行为仍未验证。

新增 `probe_appearance_controller.py` / `check_appearance_controller.py`，只申请
PROCESS_VM_READ/QUERY_INFORMATION，沿固定代码支持的当前身体组件链定位外观
控制器；精确 RTTI、双向 owner 关联、代码字节和两次稳定采样均要求满足，未知布局
停止，输出只写本机新 runtime JSON。**17/17** 隔离检查和既有角色保护 **6/6** 通过；
还未读取真实新进程或应用/恢复外观。静态依据见 [native-character-contract.md](native-character-contract.md)。
朝向候选独立审查与真实原始记录检查未发现阻断，仍不称动画/控制绑定完成。

共同静态验证：50 个 Python AST、7 个公开 JSON、修改文档的 22 个相对链接和
`git diff --check` 通过。本轮 ASI/JAR 未改，MC revision18/原材料保持。持续目标仍进行
中，游戏接管需明确恢复；不以此次 Escape 将完整目标误记 complete 或 paused。

## 2026-10-07 完整方块状态与模型映射

本轮补上“原木 ID 相同但朝向不同”的基础状态边界：MC 仍是实际放置、属性域、掉落、
材料及保存的权威。`Authority.java` 将已提交的 touched 记录从 block ID 改为完整
`BlockState`，存档升级为 schema 2。放置接口接受可选字符串对象 `properties`，例如
`{"axis":"x"}`；MC 原生 Property 校验属性名称和值，未指定属性使用默认值。两个 MC
放置入口及四个桥接放置入口均支持透传，桥接只检查对象/字符串长度，不复制属性域。

`GET /api/state` 对已记录坐标读取真实世界的非空气方块，返回完整 properties 和当前
注册表的 stateId。磁盘只存 block ID 与完整 properties，不保存易随版本变化的原始
stateId。版本 0/1 经完整校验后按原版默认属性迁移，保留 36 格 ItemStack 组件、选择、
revision、建筑及空气墓碑；版本 2 缺失/错误属性、未知未来版本均停止启动权威接口，
不覆盖原文件。失败回滚及启动修复使用已提交日志；尚不跟踪控制台外部编辑、邻居更新
或动态状态，不能把这些场景的真实世界快照恢复也算作完成。

### 真实服务检查与正式存档迁移

| 命令/步骤 | 本次实际结果 |
| --- | --- |
| `pwsh -NoProfile -File tools/build_minecraft.ps1` | MC 构建通过；新 JAR 21188 字节，SHA256 `eeb9ecc2a77349b2927b50cda0a6350dcefd95325378ad379c95f4f952aa8b38` |
| `py -3.12 -B tools/check_block_states.py` | 独立 8768/25580 世界 **7 组通过**：schema 1 迁移、三轴实际 stateId、两个入口、收据/非法属性、写盘失败回滚、正常重启、空气墓碑修复及坏存档保护；正常停服，无强停 |
| `py -3.12 -B tools/check_inventory.py` | 独立世界 **15 组通过**；1332 个实际物品/官方中文、36 格/组件/选择、64/16/1 堆叠、满背包/写盘回滚、掉落、正常重启和未来 schema 拒绝保持；正常停服，无强停 |
| `py -3.12 -B tools/check_inventory_bridge.py` | 隔离 HTTP **25 项通过**，含四条放置路由属性透传、格式拒绝及原生失败后不重放已消费请求 |
| `pwsh -NoProfile -File tools/start_prototype.ps1 -NoGame` | 第一次由 PowerShell 7 启动 PowerShell 5 子进程时，`Get-FileHash` 模块载入失败；改为复用 `$PSHOME` 对应引擎后，真实 MC/桥接启动成功。该步骤未启动红沙 |
| `py -3.12 -B tools/check_authority.py` | 正式服务只读及 **7 项拒绝请求通过**，1332 项官方名称一致，用户状态保持 |

新测试原始证据分别在 ignored `runtime/block-state-checks.json`、
`runtime/inventory-checks.json`、`runtime/authority-checks.json`。正式升级前确认后台未运行，
完整世界备份至 `backups/schema2-20261007-104139-a51027b8`，19 个世界文件哈希记录，
并保留旧 JAR 和桥接原点。启动后记录在 `runtime/schema2-upgrade-checks.json`：原存档
schema 1→2，仅两个空气墓碑新增 `properties:{}`；revision 18、selectedSlot 1、
全部 36 格及物品组件、桥接原点保持，blocks 仍为空。原木 14、圆石 64、泥土 32、木板 2、
木棍 4、工作台 1 均保持。新构建产物已更新到 `artifacts/minecraft/`。

### 全部合法状态的原版模型选择

新增 `build_block_state_models.py` / `check_block_state_models.py`。使用固定官方
MC 1.21.1 客户端、映射及原版注册表报告，独立 Java 进程仅初始化注册表，调用原始
BlockModelDefinition/Variant 解析器、BlockStateModelLoader/Selector 谓词，并与
Python 独立选择结果逐状态比较；未启动世界、MC 客户端或游戏服务。

```powershell
py -3.12 -B tools/build_block_state_models.py
py -3.12 -B tools/check_block_state_models.py --rebuild
```

已存在的输出不覆盖；重跑生成须指定新的 ignored build 输出。需要前置方块注册表和
资源覆盖报告，缺失官方依赖可显式加 `--download`。相对 JDK 路径在隔离工作目录执行
前解析为绝对路径。固定输入 SHA、原版类哈希、依赖树、输出目录及输入前后摘要均检查。

真实覆盖 **1060 种方块、26684 个合法状态、6529 个组、6762 个选项、1921 个模型**，
全部状态及选项与原版 Java **零差异**，另 21 个谓词边界案例一致。保留 variants 精确
匹配、multipart 所有同时生效组、组内全部加权备选、旋转及 uvlock，不随机选一个模型
或用默认状态替代其它状态。1062 个资源文件中另两个为未注册的 item_frame/glow_item_frame，
因此注册状态映射不将它们计入 1060 个方块。

`check_block_state_models.py --rebuild` **14/14 通过**，含重新执行原版 Java 后五个输出
文件逐字一致、每个原始选择、三轴原木、栅栏多部件、75 组多备选/6 组非默认权重、
特殊渲染、合法空墙组合、来源变动与输出保护。1921 模型中 1849 有 JSON elements，
72 为空模型；RenderShape 从真实原版状态读取：MODEL 24334、INVISIBLE 1934、
ENTITYBLOCK_ANIMATED 416。空气/流体、箱子等特殊情况保持分类，不用立方体代替。

产物在 `build/block-state-models-1.21.1`：选择表 SHA256
`574053e2d0a5d6bde2b3c72a4479420c2ea12375caac77debab46efee737f74e`，报告 SHA256
`e52b62c1e877232007db234bd5a58d3ffb8f354069d77a08cefa2056b76d19e3`。
选择表通过精确 `(model,x,y,uvlock)` 对接几何；依赖表保留原纹理/动画元数据和摘要。
这仍是固定 vanilla 离线映射，不代表运行 Fabric 注册表或红沙原生模型已全量接通。

### 全资源模型几何及真实纹理

新增 `build_block_model_geometry.py` / `check_block_model_geometry.py`，从固定客户端
全部 1062 个方块资源文件提取 6766 个选择、1925 个模型，按精确选择元组去重得到
**5163 个几何变体：5091 个有面、72 个为空**。比注册状态映射多出的四个模型选择来自
两个未注册的物品展示框资源，不把资源数量当作合法方块数量。

```powershell
py -3.12 -B tools/build_block_model_geometry.py
py -3.12 -B tools/check_block_model_geometry.py --rebuild
```

真实原版 FaceBakery 组件方法处理元素旋转/rescale、模型变换、朝向、绕序与 uvlock，
输出 **51059 个面**，其中元素旋转面 3852、rescale 面 1218、tint 面 403、退化面 160。
原始零厚度/退化几何保留，退化三角法线为 null；空模型和特殊渲染不生成虚构立方体。
这未运行完整客户端 baking，独立 UV 没有图集缩边和图集摆放；实际 render layers、
染色、动画、遮挡剔除、碰撞及原生导入均未实现。

973 张原 PNG 及 47 份动画元数据逐字保持。独立 Pillow 12.2.0 解码所有 PNG：565 张
不透明、360 张二值 alpha、48 张分数 alpha；分类是纹理事实，不等于已实现正确渲染层。
最终 **14/14 检查通过**，包括全部 51059 面的独立旋转/rescale 数学核对、原始顶点/UV
关联、16 种立方旋转/96 面的 uvlock 世界投影、全部 6762 个合法状态模型选项与几何的
精确元组关联，以及完整原版 Java 重建逐字一致、新 build 根目录及相对客户端/JDK路径。

产物在 `build/block-model-geometry-1.21.1`：manifest SHA256
`917755b2d860950b82ab90ab1fa7268bf7ebbe07bcdaca26046cc16da6df16f3`，geometry SHA256
`bf7da867191441a330a50445de22c4f608d002472180529c9d4d180e2f515df4`。原资源及派生
输出全部 ignored，仅工具/公开说明上传。细节和限制见 [asset-pipeline.md](asset-pipeline.md)。

当前运行时仍限六种方块及蓝色碰撞代理，没有朝向选择 UI；完整形状/碰撞、流体、染色、
方块实体、动画和全部物品用途继续未完成。模型及映射报告的原生集成标志均为 false。
本节的后端/离线检查不包含正在进行的 C 原木游戏内对照；实机结果必须另行记录。

## 2026-10-07 C 对照首次显示／碰撞与生成器修复

用户明确回复恢复接管并完成测试及恢复后，挂载 C 收据
`c2fb925c9d2b423996d764886408cf1a`。新进程 PID 4900，EXE 版本/哈希仍为固定已支持
版本；世界 ready/buildOk 后执行 `probe_native_resources.py`，15 项资源全部首次读回
且长度/头部/FNV 匹配，实例和 MC 状态保持。日志为
`runtime/native-resource-oak-no-declaration-20261007.json`。

Y 轴实体探针 runId `6618070e-0a9a-4c2a-a307-e2dd1b23d252`，UID 1。普通原木 prefab、
PAM、纹理与其他 20 项资源均未改，唯一差别为 Y PAMI 删除 39 字节声明。实际画面
出现 MC 像素原木侧面/顶面，部分被角色遮挡；物理探针高度增量 **1.15198 米**。
截图留 `runtime/native-oak-no-declaration-visible-20261007.jpg`，人工画面观察另记
`runtime/native-oak-no-declaration-visual-20261007.json`；不篡改自动探针的
visualVerified=false 字段，也不据局部可见画面宣称所有面、UV、光照/采样已正确。

随后使用同一进程/UID 清理，实体注册表 404、碰撞增量回到 **0**，MC 状态不变。
`runtime/native-block-oak-no-declaration-20261007.json` 当前 phase=cleaned、
registryRemoved/collisionRemovedVerified/mcStateUnchanged 均为 true。诊断未消费
MC 材料，没有将对象写入 MC 建筑；正式桥接仍使用原蓝色代理。

成功 C 与此前新进程普通候选失败、A/B 对照成功相结合，支持修复这一固定生成格式。
`prepare_native_block.py` 的 PAMI 改为 `xml_declaration=False`，并校验原模板 SHA
和三轴白名单；Steve 的原 SkinnedMesh 材质本来就没有此声明，未将该结论推广到它。
新的默认输出 `build/native-block-declaration-fixed` 拒绝非空目录，保留历史普通和
A/B/C 输入。新普通报告标记 `materialSerialization=pami-utf8-no-declaration-v1`；
资源客户端还要求三轴 PAMI 全部等于固定真实模板推导的完整字节，单有标签或只改 Y
不能冒充普通包。资源读取 CLI 默认改为新候选目录，历史对照仍显式使用历史报告。

新包 21 项候选中只有三份 PAMI 改变（每份 760→721 字节），Y 与实际成功 C 逐字
相同。报告 SHA256 `7fd02bb439f52738b829472c2fa7cdc658be3123ebb733252187eaac21287417`。
`check_native_block.py --output build/native-block-declaration-fixed --rebuild` **17/17**、
`check_native_resource_probe.py` **27/27**、历史对照 **27/27**、实体探针 **42/42** 通过。
首次新测试的 XML 根标签断言误写，核对真实模板为 StaticMeshInstance 后修正并通过，
没有改模板或放宽字节比较。新三轴包未安装，X/Z 仍未实机验收。

本次还运行既有 `probe_appearance_controller.py`，在同一真实进程中两次稳定采样
通过，当前身体/组件/控制器/owner 双向关联一致，owner 组件 count/capacity=45/64，
控制器恰好一次。mesh count/capacity=16/16，全部 FF；decoration=250/250，其中
117 字节非零。FF 不能解释为隐藏全部网格，静态消费者存在 preset/default 回退。
加载选项边界仍未核对，没有调用原生函数或写内存；Steve 应用/恢复仍为 false。
原始地址仅保留本机 `runtime/appearance-controller-20261007.json`，公开说明见
[native-character-contract.md](native-character-contract.md)。

测试清理后 Alt+F4 已打开红沙“是否结束游戏”确认框；自动点击/短按未完成确认。
已请求用户手动结束游戏。后续独立确认进程已退出，再运行 `install_asset_probe.py
--restore` 成功；收据 `c2fb925c9d2b423996d764886408cf1a` 已归档为 restored。
34 个 sourceIndexes、2 个 untouchedGameFiles 与 2 个 metadataBefore 的并集共
38 项哈希全部一致，0041 与 active receipt 均不存在；没有覆盖退出时更新的存档。
结果在 `runtime/asset-probe-restore-c-20261007-checks.json`。初次独立核查误加了
不存在的 resource 子目录，修正为收据 gameRoot 后逐项重算通过，未修改游戏文件。

收尾静态检查：55 个 Python AST、7 个公开 JSON、修改文档的相对文件链接、启动脚本
PowerShell 语法及 `git diff --check` 通过。新原木检查的固定模板/成功 Y 哈希证明为
必需项，本机历史包额外逐字比较；模拟干净环境缺少历史包时必需检查仍通过，历史
比较明确跳过，不要求重新生成已知失败格式。ASI 未改，JAR 已更新，所有官方/派生
模型、纹理、世界、截图、地址和安装备份仍 ignored。

## 2026-10-07 修复后三轴包与实际外观选项

先确认前次进程已退出，恢复 C 收据 `c2fb925c9d2b423996d764886408cf1a`，独立核对
38 项原哈希。然后从原始索引准备 `build/native-declaration-fixed-overlay`；
`check_asset_overlay.py --output build/native-declaration-fixed-overlay --verify-game`
**13/13**、`check_asset_probe.py --plan build/native-declaration-fixed-overlay`
**16/16** 通过。包报告 SHA256 为
`2c1c2efeeff1d80e2ce4fab5401fbeadab6417c41ada79b71ace73d5a6d207c9`，候选仍为
`7fd02bb439f52738b829472c2fa7cdc658be3123ebb733252187eaac21287417`。

临时安装新收据 `5c89c03dc0614c7ba5066598062c0711` 后正常启动游戏。首轮读取遇到
原生 ready=false，**零资源提交**，保留失败记录；其 mcBefore 尚未采样，故报告
mcStateUnchanged=false 不是材料改变证据。实际 ready=true 后使用新输出文件重试，
`probe_native_resources.py --group all` **27/27 首次读回匹配**，前后同一实例，MC
状态摘要不变，证据 `runtime/native-resource-declaration-fixed-ready-20261007.json`。

同一实例逐个生成／清理三轴，每次仅一块，未提交 MC 放置操作：

| axis | runId | UID | 登记／碰撞／清理 | MC 状态 |
| --- | --- | --- | --- | --- |
| x | `dd69669c-87db-4ce2-9437-91c8a5ca34f5` | 1 | 通过 | 保持 |
| y | `46b5d878-ab6b-47de-b7aa-cb00a48c66aa` | 2 | 通过 | 保持 |
| z | `f26d4a2e-c14d-4be8-afe8-b75f808b8000` | 3 | 通过 | 保持 |

三个日志为 `runtime/native-block-declaration-fixed-{x,y,z}-20261007.json`，全部
phase=cleaned、登记移除、碰撞回到 0。相对原地面增量均 **1.15198 m**，但放置点
用了最高地面加 0.03 m，相对放置原点碰撞顶面为 **1.01163 m**；不要把地面高差
解释为模型高度。库存 revision 18、选择 1、36 格和材料不变，没有新增编辑项目。

每轴真实截图及独立观察保存在 `runtime/native-oak-declaration-fixed-*-partial-20261007.jpg`
和对应 `*-visual-20261007.json`。X 可见局部端面，Y 可见浅色顶面和局部竖纹侧面，
Z 可见局部横向树皮；均被角色遮挡，因此只记可见，axisAppearanceVerified 与
allFacesUvLightingVerified 仍 false，自动日志 visualVerified 也保持 false。
自动短按未能完成侧移；已取消移开角色的待办。三个对象清理后打开正常退出确认框，
自动 Space／点击未完成退出；用户随后确认已退出。独立检查实际进程消失，再运行
`install_asset_probe.py --restore` 成功；本次收据已 restored，原始 38 项哈希全部
一致，无 0041／active receipt，恢复后 MC 完整 API 状态与测试前一致。
证据 `runtime/asset-probe-restore-declaration-fixed-20261007-checks.json`，保留后来
存档，没有强制结束游戏或恢复旧存档。

新增 [native_block_models.py](../bridge/native_block_models.py) 纯选择层，按 MC 完整
properties 匹配确切原木轴，逐状态验收身份、候选／包摘要、固定 EXE 及当前会话
资源范围需一致。显式 blue 支持现有六类；native 对未验收轴及另五类明确拒绝。
[check_native_block_models.py](../tools/check_native_block_models.py) **14/14** 通过。
此模块不读取报告／截图或验证安装文件，不自带生产准入，也未接线到 service.py；
实际验证适配器、原生受理后的持久操作日志和替换确认仍需实现，正式建造仍为蓝块。

只读外观工具扩展到精确 RTTI/vtable 的 meshParams、preset、decorationParams，
固定 EXE 10 个代码窗口逐字核对；**28/28** 隔离检查、既有角色 **6/6** 通过。
实际运行 `probe_appearance_controller.py --pid 59252 --output
runtime/appearance-options-20261007.json` 成功，两次稳定采样完全相同：

- mesh 实际 **7 组／capacity 8**，option counts 为 **2,2,7,7,0,0,0**；选择和
  preset 各 16 字节全 FF，四个非空组使用 default 0，三个空组按静态消费者跳过。
- 四个候选名称分别含 nude、head、hair、beard；这只是实际资源输入名称，还未核对
  渲染 Scene／装备槽含义。额外 9 个选择明确记为 unmapped，完整选择边界不称通过。
- decoration **250/250**，仅记录声明范围／默认与 preset 输入；动态 palette 与
  mesh 相关的最终范围尚未解析，computedBounds、renderedDescriptor、slotSemantics
  和所有应用／恢复标记仍 false。

下一步从已核对 owner 组件数组定位真实 CharacterScene 与渲染资源归属，再建立
刷新线程和恢复生命周期。当前没有外观写入、原生调用或 Steve 加载。
七份实际名称对应的原始资源已从固定归档只读解包并留 ignored build；实际 Macduff
身体 prefab 指向既有 Steve 的原生 PAC 模板，资源关联成立，但还保留 underwear，
另有原头／眼／牙、头发／胡须。原文将七组命名为身体／头／毛发等，不含已证明的
护甲／武器槽，详见 [native-character-contract.md](native-character-contract.md)。
收尾四个 Python AST、修改文档相对链接、11 个本地证据 JSON 与 diff 检查通过。

## 2026-10-07 侧向三轴显示、持久同步与原生条件实测

在前次包恢复后，正常停止 MC／桥接，将 19 个世界文件逐项备份并验证哈希，再更新
后端。更新后完整 MC API 与原 revision 18 相同，备份位于本机
`backups/native-sync-20261007-114124-ceb0d31a`，不是回滚后续存档的来源。

新增 `bridge/native_identity.py` 以 QUERY_LIMITED_INFORMATION 查询实际进程时间、
路径和固定 EXE 摘要，HTTP 写携带 PID 与创建时间组合的会话标识。原生 status 发布
两个条件能力；创建／项目归属／删除在分派前检查会话。归属与删除在项目、地面操作、
注册表锁内比较最后 GET 的项目、prefab、全部变换及 hidden，成功才修改并返回
conditional；删除在解锁后派发已有游戏线程清理。旧无 header 诊断兼容，正式桥接
不接受缺少条件能力的旧插件。原生接口保留 busy／unsupported／object_changed 的
区别，动态／standin／C5 及不适合安全删除的已移动对象明确拒绝。

`bridge/native_reconcile.py` 已接入正式蓝代理同步：材料写前持久化 MC 意图，创建／
归属／删除前保存对应原生操作，flush/fsync 后原子替换；新对象集合确认后才清理旧
对象。未知 MC 结果阻止再次建造，Restore 只重新读取权威，不重发扣料；丢失创建
响应没有可靠 UID 时保持阻断，不按位置猜对象。进程重启不沿用旧 UID；同进程对象
属性冲突保留日志，不重新认领。繁忙拒绝可重新读回再评估；非 404 错误不等于删除。
独立领取／选格不因建造未决而锁住。这里确认对象注册表，不能替代碰撞或视觉验收。

本轮相关检查（均已实际运行，隔离测试不使用用户 MC 世界）：

| 命令（`py -3.12 -B tools/` 前缀） | 结果／范围 |
| --- | --- |
| `check_native_identity.py` | 12/12；实际生产 MSYS Python 也通过，覆盖权限／句柄、创建时间、HTTP 条件及拒绝 |
| `check_native_reconcile.py` | 38/38；部分完成、丢响应、保存失败、MC 变化、会话和对象竞争 |
| `check_inventory_bridge.py` | 27/27；未决建造阻断、库存独立及不重发材料操作 |
| `check_native_session.py` | 13 组；生产 HTTP 条件解析、重复／空 header、同 PID 不同创建时间、六文件补丁重建 |
| `check_native_objects.py` | 12 组；生产条件变更、十字段/单 ULP、真实锁竞争、零错误写入与解锁后清理 |
| `check_native_resources.py` | 22 组；既有资源队列及释放不回归 |
| `check_native_block_probe.py` | 45/45；新增侧向位置优先、坡地回退和失败零生成 |
| `check_appearance_controller.py` | 48/48；精确 Scene／SkinnedMesh 类型、弱回链、边界与失败标记 |

完整 ASI 构建成功并安装，产物 SHA256
`49353e088b04549c6aa15487914ba3230ba612ef9a68572a1ad179db12f51649`，12,766,720 字节；
仓库和实际安装逐字摘要相同，1332 图标安装核对通过，原插件备份保留。固定上游仍为
`4dcedc8dfe1592fdee0528894389221291900b8d`，不是改动上游版本。

临时侧向显示检查复用固定候选与包摘要（见前节），安装前
`check_asset_overlay.py --output build/native-declaration-fixed-overlay --verify-game`
13/13 通过。本轮收据 `178c07aa03734bc49e7a7395df9bafe1`，游戏
`instanceId=57868:134358187330630563`；原生 status 的两个条件能力都为 true。
27/27 原生资源首次读回匹配，证据 `runtime/native-resource-side-view-20261007.json`。

`probe_native_block.py --spawn axis=x --side-view`（依次使用 x/y/z）在同一平坦候选点逐轴生成，
每次只留一块并在截图后清理。相对原地面碰撞增量 1.05311 m，相对放置点顶面
1.01187 m；前者包含原地面与放置点高差。UID 1/2/3 全部删除，碰撞回到 0，
三个探针的 MC 完整 API 均不变。

| 轴 | runId | 相同视角可见面核对 |
| --- | --- | --- |
| x | `0a8444a0-54ec-4de4-b9de-59abaa8aae59` | -X 端面，+Y 与 +Z 树皮 |
| y | `223eebe0-75ed-48df-86e3-ee570ba2c8b2` | +Y 端面，两竖侧面树皮 |
| z | `654f0161-9105-4fd3-899b-23d4303e012b` | +Z 端面，-X 横向树皮，顶部树皮 |

原始截图 `runtime/native-oak-side-view-{x,y,z}-20261007.jpg` 均无角色遮挡，逐轴
人工观察在同名 `*-visual-20261007.json`，绑定原始截图和自动日志摘要。
`axisAppearanceVerifiedForVisibleFaces=true`，但 allSixFacesVerified、全部 UV/光照
与 formalProfileEnabled 仍 false；自动日志 visualVerified 不会因截图存在而置 true。
正式桥接仍不准入材质资产，其他五类外观和全方块也不据此称已完成。

真实 `check_bridge.py` 放置木板 UID 4，碰撞增量 1.04187 m，恢复复用同一个 UID；
针对本测试对象验证四个请求：旧创建时间 DELETE→409 sessionMismatch，错误项目
DELETE 和错误 X 的 project POST→409 object_changed/零修改，缺十字段的会话
DELETE→400。每次完整对象及 MC 状态均不变，随后合法拆除归还材料并消除碰撞。
证据 `runtime/bridge-checks.json` 及 `bridge-sync-conditional-20261007.stdout.json`。

真实 `check_restart.py prepare` 放置圆石 UID 5，再正常停止 MC 和桥接、保持游戏
运行，`start_prototype.ps1 -NoGame` 后 `check_restart.py verify` 通过。保存的 MC
状态完整恢复，原生对象在后台停止前后快照相同，Restore 仍复用 UID 5，拆除归还圆石。
这是同一游戏内的后台重启，不宣称本轮实际重新启动了游戏来检验 UID 竞争。
最终 revision 18→20→22，除 revision 外完整 API 与最初相同：原木 14、圆石 64、
泥土 32、木板 2、木棍 4、工作台 1，selectedSlot=1，blocks=[]；原生对象 total=0，
碰撞回到原地面。重启证据 `runtime/restart-checks.json`；总体前后状态、19 文件
备份及原点恢复证据在 `runtime/native-sync-validation-20261007-context.json`。

外观初次及稳定画面重试均在渲染类型检查处拒绝。详细报告证明原 controlled owner、
唯一 CharacterScene 及 params 弱回链已获得部分实读，而 Scene+0x78 实际指向
SkinnedMeshComponent；该 VT 前面的指针是代码跳板，不是标准 primary COL。
新增分支限定 exact VT、slot-8 getter、固定 factory/构造窗口和 typed reflection
metadata；固定 EXE 的 25 个代码窗口全部一致。新分支尚未做实机双采样，原报告
顶部稳定／Scene／selector 标记均为 false，不把部分样本升级为通过。selected 资源
不解引用，没有执行外观 ABI、刷新、装备或 Steve 切换。具体证据与下一消费者在
[native-character-contract.md](native-character-contract.md)。

所有对象清理后正常退出自动短按仍停在确认框。用户第一次答复后独立发现游戏还在
运行，保持资源不动；用户再次确认窗口完全关闭后，实际进程消失，再执行
`install_asset_probe.py --restore`。收据已 restored，34 个原索引、2 个未改元数据、
2 个恢复元数据共 38 个原始 SHA256 全部一致，无 0041／active receipt。
原锚点逐字恢复后只正常重启桥接，MC API 保持 revision 22；未恢复旧 MC 世界或旧
红沙存档。证据 `runtime/asset-probe-restore-side-view-20261007-checks.json`。

收尾 14 个变更 Python 的 AST、6 个变更 Markdown 的 40 处相对文件链接、变更 JSON、
三轴视觉证据与清理状态、恢复上下文及 `git diff --check` 通过。并行只读审查未发现
同步／原生条件或新增渲染类型分支的阻塞问题。原始地址、资源、截图、备份和世界
仍在 ignored 路径，只有项目自建 ASI 及其构建摘要作为原生产物更新。

下一步先在合适的正常游戏会话做精确 SkinnedMesh 分支双采样，再沿已定位的渲染
消费者研究可逆应用和刷新生命周期；方块仍需其余面、正式安装／验证适配器以及其它
种类的独立验收。持续目标保持 active，完整 Steve、装备、心形 HP 和分发仍未完成。

## 2026-10-07 完整 Scene 观测与可弯曲 Steve 候选

本轮开始检查实际 Git 为 `5c61d28`、工作区干净、游戏进程不存在、临时包已恢复；
上一轮属于完成实测、恢复和代码交付的实质进展。继续 M4a，未改变完整目标或标记完成。

使用现有授权正常启动原版资源游戏。启动工具未暴露窗口，但实际 PID 36352 已存在，
因此不重复启动；等准确窗口和 native ready 后载入存档，做只读诊断，没有安装资源、
改插件、创建对象或消费材料。当前完整控制链到 SkinnedMeshComponent 的两次样本
完全一致；Scene／参数资源的弱回链和两个选择输入通过，旧分支的未知类型拒绝不再
是该组件的阻塞。实际数据与截图留在 `runtime/appearance-render-typed-20261007.*`。

新增 schema 4 可选资源身份模式，限定两个已有输入和标准 primary RTTI 头，不传入
任意进程地址、不读取未知字段、不调用虚函数。一项失败保留其证据并独立读另一项，
任一失败则整体 rejected；默认不读资源身份头。62/62 隔离检查、固定 EXE 27 个
代码窗口通过。实机两项均使用 VT5B3FC58，其候选 COL 实为代码，因此拒绝，不放宽
成猜测类型。新默认模式另做完整双采样仍 observed，资源模式的拒绝不被改写为成功。
精确文件、静态构造/析构路径和未完成边界见
[native-character-contract.md](native-character-contract.md)。

资源依赖检查进一步证明原七项候选仍保留内衣，原头 7 项、Hair 和 Beard 独立；
共享 body 也被其他角色引用。当前 Macduff 描述符的 01_0002.pabc、1.02571 scale、
ragdoll 不等价于旧候选 00_0001 模板。装备遮挡依赖 CD_Head、shrink 等命名，Steve
头放在 CD_Nude 中尚无等价覆盖。下一资产组合必须解决这些缺口，不能全局替换共享身体。

新增独立 [prepare_steve_segmented.py](../tools/prepare_steve_segmented.py) 和
[check_steve_segmented.py](../tools/check_steve_segmented.py)。保留 MC 静态表面/UV，
按真实 PAB 关节高度细分四肢；原来完全不受下段骨影响的远端，现在按实际 palette
跟随 Forearm_sub/Hand、Calf_Sub/Foot。旧候选、原生默认和游戏资源不变。
`py -3.12 -B tools/check_steve_segmented.py --rebuild` **12/12**（含真实重建）通过；
4 LOD 每级 1056 顶点/528 三角形，仅 PAC 变化。24 个合成弯曲、真实 inverse bind、
独立 UV/面面积/绕序和 byte 权重检查通过，不能作为实际动画/装备验收。
精确误差、哈希和复建命令见 [asset-pipeline.md](asset-pipeline.md)。该候选仍用旧
PABC；头部连接、旋转中心及 current descriptor/装备遮挡保持未完成。

本轮结束前 MC 完整 API 与启动前一致，revision 22、blocks=[]，原生登记 total=0；
无临时包、active receipt 或待清理测试对象。根记录
`runtime/appearance-render-context-20261007.json` 绑定四份新报告、MC 与原生对象。
游戏保留正常运行，可继续普通游戏；本轮没有待退出后恢复的资源或后台探针进程。
只读审查未发现身份头扩展或分段候选阻塞问题；完整持续目标仍 active。
收尾 4 个变更 Python AST、6 个文档的 38 处相对链接、候选 17 文件摘要、4 份实机
报告摘要与状态关系、`git diff --check` 通过；所有生成资源、地址、截图和存档保持 ignored。

下一步优先完成当前 01_0002 描述符与分段模型的绑定对照、Steve 头/身体分件和原部件
排除；渲染资源继续沿已确认的 0xA0 构造/释放链核对嵌套描述符及应用线程，随后才能
做可恢复的受控人物切换。不能用新增离线候选代替启用即持续 Steve 的验收。

## 2026-10-07 头身分件、当前 neutral 补偿与嵌套资源实读

上一轮退出／恢复工作已结束；收到迟到的“窗口已关闭”回复后先核对实际状态，当前
是后来已启动的同一原版资源会话，未误对运行游戏执行恢复。38 项原始文件重新计算
SHA 全部一致，无 0041、active receipt 或测试对象。

新增头／帽 PAC 与身体／四肢 PAC，四 LOD 分别 48／1008 顶点、24／504 三角，完整
40-byte 顶点记录、拓扑、UV 和 skin 与合并源逐字保持。每 PAC 有独立同名 PAMI，
共用三 DDS；七资源不带旧 combined prefab／descriptor。私有 prefab 工具从原版
0009 索引直接提取当前身体／头，只保留 CD_Nude／CD_Head，保留各自正确 name-pointee
footer 后改路径，连同当前 body descriptor 共三资源。它避免了通用数组删除留下
错误 footer、但 CDMW walk_complete 仍为 true 的实测边界问题。

两份 manifest 的十个唯一资源静态路径匹配；外部 PAB/PABC/PAPR/ragdoll、wrinkle
XML、breath key、原发须 appearance、head scale 和装备/partshrink 仍未共同验收。
分件仍使用旧 neutral，不能把静态路径闭合视为当前角色已经适配。

另一个独立 current-rig 候选从固定索引提取真实 01_0002 PABC，420 记录、416 个
中立矩阵与旧配置不同；十四个实际赋权骨都覆盖。共享 PAB/PAPR 与旧版字节相同。
原 descriptor 的五字段及 1.02571 scale 保持。按已编码权重混合矩阵后求逆预变形，
重新解码量化 PAC 回放，将当前 neutral 最大偏移 **0.088770 m** 降为
**2.705741e-5 m**。只允许改 bbox、位置、法线和 V frame，UV／skin／拓扑不改。
非均匀形变下按协向量/方向分别运输目标 frame，法线 dot≥0.999594、V dot≥0.999721。
该 combined 候选仍带原内衣，尚未与分件结合；没有证明原生 shader、动态姿态或装备。

新 `--render-resource-links` 与旧 RTTI 诊断互斥，只在固定构造／消费窗口成立时读
两项父资源 vtable／+68／nested vtable 三个 QWORD。实机完整受控链双采样 observed，
两个 +68 指向同一非空 nested，vtable RVA `0x5B426C0`；class／layout／descriptor／
application／Steve loaded 全部 false。旧 RTTI 拒绝结果保留。没有写进程、执行函数、
安装资源、改变插件或创建原生对象。

| 检查 | 本轮结果 |
| --- | --- |
| `py -3.12 -B tools/check_steve_parts.py --rebuild` | **7/7**；真实重建、四 LOD 完整 union／palette／材质、破坏字节及输入／输出拒绝 |
| `py -3.12 -B tools/check_steve_parts_prefab.py --rebuild` | **16/16**；独立原始语法、完整模板逆向恢复、stale footer 反例、真实索引提取后重建 |
| `py -3.12 -B tools/check_steve_current_rig.py --rebuild` | **13/13**；真实索引提取后重建、byte 权重／量化回放、非对称 shear／127:128 混合反例、覆盖与写入范围拒绝 |
| `py -3.12 -B tools/check_appearance_controller.py` | **76/76**；默认不读、独立父项错误、空链、漂移、最终 owner/pair/module 与互斥模式 |
| 固定 EXE 字节窗口 | **31/31**；默认 27 加 linked 模式 4，实际只读采样通过 |

本地报告 SHA256：

- `build/steve-parts/steve-parts-report.json`：`b868ca5d9aa19f6cacae3af4afc8a744be98e966fa3cddbe072d67c3bb33db5d`。
- `build/steve-parts-prefab/steve-parts-prefab-report.json`：`9aefc59a11e321cb0f46baebc6b8a6ca04caaca98b80da956d8250df43adc3f7`。
- `build/steve-current-rig/steve-current-rig-report.json`：`da3bd0c0d899c280d26ad1c8d9ca188d9600eeaaf5d2f74a6c4e614a06287585`。
- `runtime/appearance-linked-headers-20261007.json`：`374ba1763752d41755cc090a656458eaa099ad50664489ebad8130bb2a7b1812`。

`runtime/appearance-linked-context-20261007-before.json`／`-after.json` 记录同一实例
`36352:134358196715607705`，MC 完整状态均为 revision 22、36 格与选择未变，原生
对象 0。重新核对原包记录在 `runtime/appearance-linked-restoration-20261007.json`。
没有待恢复项，正常运行游戏不受本轮候选影响。独立审查未发现分件或补偿写入范围
的阻塞问题；所有资产、报告、存档及进程地址仍留 ignored 路径。
收尾 8 个 Python AST、6 份文档的 38 处相对链接、三个候选的 33 项文件哈希和
`git diff --check` 通过；本轮四组相关检查共 112 项通过，没有为此重复运行无关存档／建造测试。

下一步把已验证补偿用于私有头身组合，并继续从 `0x5B426C0` 自身的构造/消费者核对
嵌套类型和实际资源路径，不能把相邻 vtable 的 getter 当作本类成员。之后才接通
受控应用、重载保持和恢复，完整持续目标仍 active。

## 2026-10-07 十一资源首测包、实际选项读取与恢复

当前身体补偿已组合到两私有头身 PAC、对应材质、三 DDS、两 prefab 和一个 descriptor。
固定十项资源的纯准入验证完整报告、三个来源报告、模板及 payload；原生 Head0001
变体未覆盖唯一赋权头骨 93，因此头保留原 split 字节。PAB 回退误差约 2.42e-8 m，
假设继承身体 neutral 时约 7.06e-5 m；这两种离线假设不证明原生合并语义。
身体仍为 2.705741e-5 m 中立回放误差，HeadScale 0.92／CharacterScale 1.02571 保留。

新增 appearance 候选仅将固定 Kliff meshparam 中默认 Body／Head 的 MeshFileName
改为私有 basename；逆替换逐字恢复原模板。七组选项、PABC、发须、装备和其余 XML
均保持。其作用范围是使用同一 meshparam 的实例，尚非 actor-local 或启用即持续模式。
原 app 内的 Prefab 引用未改，实际最终装配消费和装备遮挡必须独立验收。

新专用 overlay 包含十项新资源及一项原路径替换，安装种类为
`steve-mesh-parameters`。原木 CLI 保持 oak-log，错误种类在恢复写入前拒绝，共用
active receipt／锁防止两包并存。Windows 本地报告路径先规范分隔符再检查 build
边界；游戏虚拟路径保持严格 POSIX。测试夹具复用完整事务，故障仅注入隔离副本，
真实游戏和个人存档不被测试修改。

| 检查 | 结果 |
| --- | --- |
| `py -3.12 -B tools/check_steve_assembly.py --rebuild` | **12/12**；十资源完整重建、四 LOD、纯 loader 和损坏拒绝 |
| `py -3.12 -B tools/check_steve_appearance.py --rebuild` | **12/12**；真实提取、仅两属性变化及逆向恢复 |
| `py -3.12 -B tools/check_steve_probe.py --rebuild` | **21/21**；真实包往返、发布／恢复故障、后来存档、并发、错种类、越界和精确重建 |
| `py -3.12 -B tools/check_asset_overlay.py --verify-game` | **13/13**；扩展后的通用原木预演回归，在临时包安装前运行 |
| `py -3.12 -B tools/check_asset_probe.py` | **16/16**；共用事务扩展后的原木回归，在临时包安装前运行 |
| `py -3.12 -B tools/check_appearance_controller.py` | **93/93**；新增输入路径模式及既有只读合同 |
| 固定 EXE 字节窗口 | 输入路径模式 **40/40**；默认 27 加专用 13 |

首次 Steve 故障检查发现 Windows 本地路径被按虚拟路径拒绝，修复后重跑。
测试继承时误保留的原木单报告用例也已由 Steve 双报告用例正确覆盖；最终 21 项全过，
没有以跳过失败充当成功。所有源代码检查和独立资源范围审查未发现本轮阻塞问题。

原版会话的 `--render-input-paths` 双采样稳定：PAC 声明为空，PAB 声明为
`character/model/1_pc/1_phm/phm_01.pab`。两属性类型和 owner 成立，但整体 notReady；
这不是“无渲染模型”的证据。报告是 `runtime/appearance-render-input-paths-20261007.json`，
诊断前后完整 MC 状态、原生对象 0、会话与 38 项原始文件保持。

用户重新授权后正常退出游戏，确认实际进程结束才安装。真实收据
`eb24ffb9f1354a6aa94127a9e54a11e3` 绑定十一资源包，所有安装文件及原始索引复核一致，
游戏启动到标题界面。前台画面反复被另一游戏覆盖，用户随后回复已进入世界，但
工具再次报告物理 Escape；立刻停止窗口输入，没有获得 Steve 模型截图。

在同一次新会话完成一次默认只读双采样，报告
`runtime/steve-first-display-options-20261007.json`：受控 controller／Scene／Skinned
完整链稳定；已加载的 `meshparam_example_kliff.xml` 中，group 0／1 的名字分别为
`crimsonmc_steve_body_1_21_1`／`crimsonmc_steve_head_1_21_1`。两组 rawChoice／preset
均 FF，按原生已知规则回退 groupDefault 0，候选在合法范围。这证明新配置进入了
运行时选项表；未读取最终选中模型 descriptor，所有外观应用／Steve 显示标志仍 false。

用户确认退出后再次核对所有 CrimsonDesert 进程结束，专用恢复入口返回 restored。
`runtime/steve-first-display-20261007-installed.json`、`-before-restore.json`、
`-restored.json` 绑定实际收据、原始文件和 MC 状态；恢复后 38 项原始文件一致，
0041 和 active receipt 均不存在，恢复前后的最新存档逐文件相同，完整 MC 状态保持
revision 22。没有创建测试对象、消耗材料、更换 ASI 或写游戏进程内存。

本地报告 SHA256：

- assembly：`2f167887d0abcae102f293d98f34c6421b52d7b5153eb1b9393e2d6da57b8f33`。
- appearance：`a4f8712cc74967dbe1a0c5dc5e239f388538397a164d4accec7012786673f1f9`。
- overlay：`792a9d00664e466925d63b1752228c53cecf960975359aec1b0bace861dcecbb`。
- 原版输入路径观测：`a2f3449f8b02cd260092e66e05abfddbe9a358dfcc18516653c9619971ef6948`。
- 临时包新选项观测：`96828904e12dacae944085dedea3c0440cc099f8990647dbb103ad9860f558b3`。

下一步需要恢复窗口接管或用户提供实际画面证据，验证头身显示、动画、尺度和装备
遮挡，再调整原生装配。两份 skinned pac_xml 无 XML 声明，但去掉了原模板 BOM，
若加载失败可作单变量格式对照；原木静态 PAMI 的成功不能外推为此处已验收。
当前游戏已关闭，测试包已恢复，无待清理项；窗口接管保持停止，完整目标仍 active。
提交前 12 个 Python AST、7 份文档的 55 条相对链接及 `git diff --check` 通过；
实际恢复核对 38 个原始文件和 36 个最新存档文件。资产、原始报告、地址与存档均
留 ignored 路径，待提交仅源代码和文档。

2026-10-07 后续用户明确反馈：该次临时包进入世界后仍是原来的红沙角色。首测
结论据此更新为**新选项表已读、人物外观切换未通过**，不能继续仅记“没有观察”。
现有新包只改 meshparam；两个已知 Macduff app 的 Nude／Head Prefab 仍引用原名。
下一项优先核对初始 appearance 装配与 customization 应用时机，再准备有界对照；
没有黑色／透明模型的证据，暂不将故障归因于材质、BOM 或骨骼。

## 2026-10-07 首测结果修正、头描述文件对照与初始外观输入诊断

用户已明确首测仍是原角色，因此后续不以“没有截图”代替失败结果。磁盘分析区分了
初始 Appearance 的 Name 装配与 customization 变更队列：新默认名称出现在选项表，
不足以证明原 app 部件已移除。FF→0 跳过旧部件删除，0→0 跳过变化；没有实际队列
采样，不能直接认定失败原因。原生线程／刷新 ABI 仍未准入，详见角色契约。

新增固定 Head0001 描述文件的原字节复制工具，单资源报告严格核对 466 字节、七字段、
flags 48 和同 basename 配套路径。十二资源包的旧十一项 payload 与纹理注册表逐字
相同；只增加私有头 `.prefabdata_xml`，保留十一资源默认包。安装器仅接受固定二／三
报告集合，完整收据与包哈希区分两种 variant，复用关闭游戏、备份、锁和故障恢复。
该依赖对照的依据是原生配套文件与固定 CDMW 关系解析，不是已证明的加载必需条件。

只读输入模式升为 schema 7，增加 exact Skinned +168 初始 Appearance loader key；
新增六个生产链窗口并保留两项 PAC/PAB 门禁。字段／holder／全部字符与 NUL 回读、
完整受控链和两样本稳定后才提升独立标志。当前未取得实机新 key，不据此修改 app。
同时修正旧 HP 诊断：受伤 current<base、norm=0 不再被错误拒绝；保留有界原始数值，
删除未经证明的 max(base,+30) 推断。真实 HP、最大值、单位及 HUD 就绪均保持未验证。

| 本轮检查 | 结果 |
| --- | --- |
| `py -3.12 -B tools/check_steve_head_descriptor.py --rebuild` | **8/8**，真实固定原档重建、七字段与字节、纯 loader、故障拒绝 |
| `py -3.12 -B tools/check_steve_probe.py --rebuild` | **21/21**，保留十一资源默认行为 |
| `py -3.12 -B tools/check_steve_probe.py --head-descriptor --rebuild` | **23/23**，完整安装／恢复故障与精确单文件增量，70.448 秒 |
| `py -3.12 -B tools/check_appearance_controller.py` | **103/103**，初始 key、边界、NUL、链漂移与模式隔离 |
| 固定 EXE 输入模式 | **46/46** 字节窗口；独立初始装配静态研究 45 窗口、10 direct xref |
| `py -3.12 -B tools/check_character_probe.py` | **13/13**，角色守门及受伤／零值／边界／短读 |

真实安装收据 `417c1f278c624a958152d75211072670`，variant 为
`steve-kliff-head-descriptor-v1`。安装后原索引、metadata、包哈希和 MC 状态核对一致；
请求启动时工具再次报告物理 Escape，立即停止 UI 调用。实际进程查询无红沙，记录
恢复前最新存档后执行专用 restore，返回 restored。38 项原始文件一致，36 个最新
存档逐文件保持，MC 完整状态 revision 22、原点及 ASI 摘要不变；无 0041 或 active
receipt。没有加载存档、消费材料或生成对象，不能把这次包事务记为显示测试通过。
证据保留在 ignored `runtime/steve-head-control-20261007-{before-install,installed,
before-restore,restored}.json`，补录脚本曾误用收据字段名，已改为实际 `planSha256` 后
核对完成；该记录错误未影响已成功的安装事务。

本地候选报告 SHA256 为
`aa2c47076fd327c12bb85bce6b1bf4899931d754a6cc627bc855acfea1e98262`，十二资源包报告为
`58478e5d9dc0c4648dd73d8a8a21daa32ef6eb9b2a06389ba3c73167041844c8`。
两项独立只读审查未发现包范围／恢复合同或新诊断稳定性问题。下一步仍是取得初始
appearance key，并实际验证这一单变量对照；恢复接管须用户重新明确授权，或由用户
手动启动／退出。当前游戏关闭、资源恢复，持续目标 active，完整 Steve／装备／HP
HUD／全部方块与分发均未完成。
提交前 9 个 Python 文件语法、7 份文档的 55 条相对链接和 `git diff --check` 通过。
本轮提交范围仅源代码与文档；游戏资源、候选包、原始证据、备份和存档均留本机忽略目录。

## 2026-10-07 手动头描述文件对照、部件注册表与受控 Hp 诊断

用户选择自行启动、进入存档和退出；本轮没有窗口接管调用。实际安装十二资源包的
新收据为 `64cefed193bc4014914e78495471dc67`，不是此前已恢复的 417c 收据。用户进入后
明确反馈仍是原角色，故头描述文件单项增补没有通过显示验收。schema 7 在该会话
完整双采样稳定：当前初始 app 为 `cd_phm_macduff_00000.app_xml`，PAB 为原 `phm_01.pab`、
PAC 声明为空。初始输入独立标记为 true，整体为 notReady，所有实际应用标记仍 false。
诊断前后材料、36 格、revision 22、原点与 ASI 保持，原生对象 0。

固定 EXE 的 37 个窗口／6 个字符串核对明确 Name→prefab 和描述文件依赖 PAPPT 两段
目录。原表的两个私有 stem 都不存在。新增 `prepare_steve_part_table.py` 固定原表
2130295 字节，两段各追加 Body／Head 两行；原 18196 行、字段、顺序及保留字节完整
保持，只有两计数和新行不同，逆操作逐字恢复。生成 2130624 字节、flags 50 的单旧
路径替换候选。`check_steve_part_table.py --rebuild` **8/8** 通过，包括真实固定 CDMW
完整解析／重建与全部旧候选保持。

新增显式二选一的 `prepare_steve_app.py --variant macduff-00000|macduff-00002`，每份
报告只改自身 Nude／Head 的两个 Name，保留其他原字节。实际只观察到 00000，00002
只是独立备用候选；不同时替换两份 app。`check_steve_app.py --rebuild` **8/8** 通过。

包入口扩为严格 11／12／13／14 项：十三在十二基础上只加 PAPPT，十四再加一份显式
app；缺头描述文件、缺注册表、未知报告、旧路径冒充私有新增均拒绝。默认十一包与
Steve 专用恢复 kind、所有权、锁保持；新 variant 与完整 plan SHA 绑定。纯准入和
独立源码审查通过；十三／十四包尚待当前资源恢复后完成真实封装／事务检查，不能安装。

新增独立 `probe_health.py`，不再猜 Hp=0／首条记录：精确受控 ClientStatus 和回链，
三种 metadata manager、名称 Hp key、有界单项映射、0x90 完整记录、全部依赖回读及
同句柄身份／存活校验。初版隔离检查 **18/18**、固定 EXE **21** 窗口／4 种类型通过。
第一次实际只读在 `Selected status metadata key differs from named Hp` 拒绝，未输出
成功值。回查确认序列化 `_key` 与 u16 表索引来自不同来源，不能相等比较；schema 2
保留原 DWORD 并沿固定生成链读取精确 `_stringKey=Hp`，最多 64 字节 NUL 字符串，
全部字节及 holder 纳入回读。修正版 **21/21** 检查通过；实际双采样成功，71 项依赖
稳定，Hp ordinal 0／serialized key 1000000／stringKey Hp，character 0、group 1、
regenerateType 1、mappedIndex 0，stored/base 原值 300000，norm/floor/field30=0。
投影值、最大值、单位、原子快照与 HUD 就绪始终 false。没有写游戏内存、调用原生
函数或改变材料，旧失败证据没有覆盖。

旧十一／十二包的无重建回归已执行，但本轮还不能记为全部通过：临时包仍安装，
测试收尾要求实际 metadata 等于原始 before，因此拒绝。逐项复核 active 收据的 41
项文件哈希均一致，没有发生测试写入游戏。十二包未知报告用例还发现新增可选集合
使旧长度门禁不足，已修复为先白名单拒绝未知／重复报告名再读文件，严格集合不变。
独立审查和十一／十二包的未知报告定向拒绝检查通过；等待恢复后重跑完整检查，
不修改或绕过原始收尾要求。当前 10 个 Python 文件语法、55 条本地文档链接和
`git diff --check` 通过；本次保存阶段性源码，不把新增包声明为可安装或显示已通过。

本轮运行证据留在 ignored `runtime/steve-head-control-manual-20261007-*`、
`runtime/steve-head-control-manual-inputs-20261007.json` 和
`runtime/typed-health-head-control-20261007.json`（初版拒绝）及
`runtime/typed-health-stringkey-head-control-20261007.json`（schema 2 成功）。当前安装／恢复以本文件顶部现场状态
为准；用户手动退出请求仍待完成，不把之前的 restored 记录当成本轮已恢复。

## 2026-10-08 收束分工、恢复旧包并验证注册修正版

用户要求多智能体与持续目标配合推进，并确认完成修改需同步 GitHub。新增精简
`current-state.md` 作为交接入口，主控负责安装／实机／恢复，独立子代理仅收束已有
目录与 HP 诊断；不再为等待游戏扩大逆向支线。完整项目范围保持。

实际检查发现红沙已退出、MC／桥接也停止。原在线记录器因连接被拒没有生成成功
记录，随即使用独立离线恢复记录器采集持久文件，未伪造在线 API。恢复收据
`64cefed193bc4014914e78495471dc67` 成功；38 项原始哈希、36 个最新存档、MC 持久状态
revision 22、原点和 ASI 一致，0041／active receipt 消失。证据位于
`runtime/steve-head-recovery-20261008-{before-restore,restored}.json`。随后以 `-NoGame`
正常启动 MC 和桥接，完整在线 MC 状态与原安装前快照相同，游戏未自动启动。

十三资源注册包已实际封装，全部 13 项解包逐字一致，PAZ 743120 字节。报告 SHA256
`22633e19d57ade19d090e84a26641c5385c53b328941ddb48a1aa20fd66f7b6c`。
仅供后续对照的十四资源 Macduff 00000 包也已封装，PAZ 744240 字节，报告 SHA256
`58bfd8539820892721276792ae1e0dbf8667e3d5b282bd546eeff8b96574e3f8`；不会同时安装。

| 本轮检查 | 结果 |
| --- | --- |
| `check_steve_probe.py --rebuild` | 21/21，全新重建及隔离安装／恢复通过 |
| `check_steve_probe.py --head-descriptor --rebuild` | 23/23，77.365 秒；上轮收尾失败在恢复后的原版状态重跑通过 |
| `check_steve_probe.py --part-table --rebuild` | 23/23，92.556 秒；精确单项增加、报告依赖与恢复通过 |
| `check_steve_probe.py --app-variant macduff-00000 --rebuild` | 24/24，85.208 秒；单 app 增量、禁止另一个 app、完整事务与重建通过 |
| `check_asset_overlay.py --verify-game` | 13/13，原始 metadata／索引保持 |
| `check_part_catalog.py` | 21/21，84 固定窗口、四名称两目录、碰撞、边界与漂移 |
| `check_health_probe.py` | 28/28，默认 schema 2 和可选 current-gate schema 3 隔离保持 |

四个诊断源码经过独立审查，无需修改。目录及可选 HP 门禁尚待新游戏会话只读实测；
未写进程内存，未更新 ASI，不把目录成员或条件候选提升为 Steve／HUD 行为完成。

所有封装检查完成后，实际安装十三资源注册包；新收据
`90cdf0fca1ce4095aedc43d3515a1525`，variant `steve-kliff-part-table-v1`，绑定上述十三包
报告 SHA。安装前后文件全部匹配，完整 MC 状态、原点及 ASI 不变。证据为
`runtime/steve-part-table-20261008-before-install.json`／`-installed.json`。已请求用户
手动进入并反馈实际外观，随后读取受控目录。当前尚未实测显示，亦尚未恢复新包；
十四包未安装。新的交接文件明确区分当前 active 收据和已经 restored 的历史收据。

## 2026-10-08 十三包闪退恢复与组件注册 v2

用户报告进入后闪退；现场确认原进程已结束。执行
`build/record-steve-part-table-20261008.py before-restore`、
`tools/install_steve_probe.py --restore`、同脚本 `restored` 均成功。收据
`90cdf0fca1ce4095aedc43d3515a1525` 已恢复，38 项原始哈希匹配，0041 与 active receipt
消失；36 个最新存档、完整 MC 状态 revision 22、原点与 ASI 保持。用户手动重新
进入同一存档后确认“可以正常进入，不再闪退”，新会话 MC 状态再次核对不变。
证据在 `runtime/steve-crash-20261008/incident.json` 和旧十三包恢复前后快照。

已保存失败会话的 cdmodkit.log，最后记录在 10:21:10 的角色创建阶段，没有异常
堆栈；10:19～10:25 的 Windows Application 1000／1001／1002 未找到匹配红沙记录。
未把旧 WER 挂起报告或日志最后一行当作崩溃根因。

独立资产审查确认：原 PAPPT 两 donor 行与原 prefab 的组件名逐项相等，分别是身体
2 项、头部 7 项；新私有 prefab 已只保留 CD_Nude／CD_Head，但 v1 注册行仍沿用
2／7 项，声明了不存在的 CD_Underwear 及六个头部细件。实际二进制解码和 assembly
哈希均核对一致。两私有名称在原两段中无同 hash 项，未发现排序要求的依据。
这是一处明确的跨资源不一致；未取得堆栈，尚不能断定是唯一闪退原因。

v2 只缩减新 body／head part 行的组件列表。原 15566 个 part 行、2630 个 descriptor
行及两条新 descriptor 行逐字保持，其他 12 项资源不变。新 PAPPT 2130527 字节，
SHA256 `832897bfe3322f2e76abd192ee4ca2d1f09a9b2ed6d40fa3ec9e79382f224ea5`，报告
SHA256 `50bd6289f50558f2c20158d232f976c210b45494ffefd746ccdd54f79a5cde14`。
封装发布前及安装准入都新增真实 prefab 解码后的组件列表核对；旧多部件报告及
payload 被拒绝。旧包／失败证据保留，旧收据恢复不经过新版准入。

| 检查 | 实际结果 |
| --- | --- |
| `check_steve_part_table.py --rebuild` | 10/10，32.332 秒；真实原／私有 prefab 对照及旧错误拒绝 |
| `check_steve_probe.py --part-table --rebuild` | 24/24，100.971 秒；新版封装、事务、真实组件交叉检查 |
| `check_steve_probe.py --app-variant macduff-00000 --rebuild` | 25/25，104.524 秒；备用十四资源新版兼容 |
| v1／v2 payload 差异及旧计划拒绝 | 两包都只改变 PAPPT；旧十三／十四准入拒绝，十一／十二准入保持 |
| 独立封装／安装代码审查 | 未发现阻断；CDMW 加载顺序、延迟 import、旧恢复及十四继承检查正确 |

十三包输出 `build/steve-part-table-v2-probe-overlay`，13 项／PAZ 743040 字节，报告
SHA256 `19b5ae4841a63795324f642a8332fec23aca1783ed4af3804affd1237fdd54dc`。
备用十四包输出 `build/steve-app-macduff-00000-part-table-v2-probe-overlay`，14 项／
PAZ 744160 字节，报告 SHA256
`7d045575a9bce1ceca356d6d8e853466e70db3aa27e0e657726b5c4b14d33449`，没有实际安装。
差异证据保存在 `runtime/steve-crash-20261008/v2-delta.json`。

用户正常退出后，核实无进程、原始文件一致，已安装新版十三包；收据
`045d94ec45d74007a5dfd1c53dd8e00a`，variant `steve-kliff-part-table-v2`。
新版快照脚本 `build/record-steve-part-table-v2-20261008.py` 固定上述计划 SHA，
before-install／installed 均通过；文件、MC、原点与 ASI 保持。已请求用户手动
进入同一存档，待实际结果及退出恢复；没有写外观内存、换 ASI 或消费材料。
当前修复验收仍分两步：先能正常进入，再核验 Steve 显示；不能以检查数量代替结果。

随后新会话 PID 82292（10:35:56 启动）已出现受控角色；10:38 的 in-world 快照通过，
完整 MC、原点、ASI 及所有安装文件保持，未重现 v1 进入即闪退。首次实际目录探针
`runtime/steve-part-table-v2-20261008-catalog.json` 为 observed：part／descriptor 表
计数分别 15568／2632，两私有头身均 present 且目录正确，原名基线成立、全部依赖及
两次采样稳定。新表已实际加载，这不等于模型渲染。
`runtime/steve-part-table-v2-20261008-appearance.json` 再次实读初始 app 为 00000；
PAC 声明仍空、PAB 为 phm_01.pab，整体 notReady，未宣称已选中渲染资源。用户实际
外观反馈仍待确认，临时 v2 包仍安装中，需游戏退出后恢复。

用户随后明确反馈“正常进入，显示的不是原角色也不是史蒂夫”，并附图。
`runtime/steve-crash-20261008/v2-user-visible-overlap.png` 可见 MC 方块头、蓝绿躯干和
紫色下肢，位置与原角色明显错开，并与原衣服、头发及装备混叠；MC 资源已开始显示，
完整人物装配未通过。图片无法单独区分旧 Nude／Head 重复、装备保留和蒙皮定位原因。
主控请求用户正常退出后，已完成 v2 before-restore、专用恢复和 restored 全部检查：
38 项原始哈希一致，无 0041／active receipt，36 个最新存档、完整 MC、原点与 ASI
保持。v2 当前无待清理项。下一项限定为定位／骨架与旧部件残留的分开诊断，备用
十四资源单 app v2 仍未安装，不把应用名改变当成骨架修复。

## 2026-10-08 原生头单引用定位对照

两项限定静态审查已收束。衣服、裤子、手套、靴子来自初始 app 的独立 Armor
CD_Upperbody／CD_Lowerbody／CD_Hand／CD_Foot；主头发、胡须来自 Hair 与运行时
mesh group 2／3。当前图像不证明旧裸体／头重复。备用十四包只改 Nude／Head Name，
不改变这些装备、发型或骨架，本轮暂不增加 app 变量。

位置审查直接解码既有 PAC：head LOD0 48、body 1008 记录的 guide 为零，byte39
低六位为 63；头槽 8→PAB93、身体槽 136→PAB25 与固定 palette 一致，源位置没有
图像中量级的整体左偏。固定报告中 head 两个 neutral 假设最大差约 0.000070628 m，
body 补偿前最大 0.08877 m；这些离线值不证明原生装配正确，也未定位可直接修复的
索引错误。本轮不凭截图平移零件或盲目补骨 93。

新增 `prepare_steve_head_mesh_control.py` 与检查器：仅把固定私有 CD_Head prefab 的
`_skinnedMeshFile` 指回原生 `character/model/1_pc/1_phm/head/head/cd_phm_00_head_00_0001_macduff.pac`。
1918→1921 字节，只有一个引用和六个必需长度／指针字段变化，非路径语义完全保持；
结果等于原生 donor 保留首个完整 CD_Head 组件的原字节。payload SHA256
`c2d0af7e8bd3b90cc394545c852266356a7f48f0753052d536988698fab01601`；候选报告 SHA256
`254501ee9de5bdae3a90cf66f8871ed53f7d20ed679101efcdfbc59c2e107861`。候选及原资源只留
ignored build。真实重建、CDMW 独立往返、语义／footer、纯加载与拒绝检查 **9/9**
通过（10.341 秒）。

封装严格限定在已准入 v2 十三包内覆盖一个私有 prefab，保留原 assembly 和覆盖
候选的双重来源；不放宽通用 duplicate 规则。独立五报告集合须同时有 meshparam、
head descriptor、PAPPT，禁止与 app 控制混合；variant
`steve-kliff-native-head-part-table-v2`。`check_steve_probe.py --native-head --rebuild`
**27/27** 通过（91.390 秒），包括完整事务、十二资源保持、原摘要、缺依赖及混合拒绝。
6 个 Python 文件 AST、62 个本地文档链接和 diff 格式检查通过。

包 `build/steve-native-head-probe-overlay` 共 13 项、PAZ 743056 字节，计划 SHA256
`043c8b22e074da3d24e2c6c2e25f388f4ce57865b289de97f365be508b7503a5`。与 v2 的唯一
payload 差异为私有头 prefab，其余 12 项和 metadata-before 相同，证据
`runtime/steve-crash-20261008/native-head-delta.json`。固定计划快照脚本
`build/record-steve-native-head-20261008.py` 已完成 before-install／installed。

主控确认游戏关闭且资源已恢复后，实际安装此对照，收据
`57b18550c3e344c19278ecd6f0b9d2c6`。安装文件、完整 MC、原点与 ASI 保持；已请求
用户手动进入同一存档并反馈原生头是否正常连接，待实机和退出恢复。这是诊断，
不会把原生头当作 Steve 完成。结果仅区分私有 PAC 及依赖与共同装配路径，不能仅凭
原生头正常就认定是权重错误；原生 PAC 会使用自己的材质链。

2026-10-08 10:57 核实新实例 PID 18364（10:55:22 启动）仍运行，原生头收据仍
installed。新 `in-world` 快照成功：全部文件、完整 MC、原点与 ASI 保持。外观输入
诊断两次稳定读取受控链、Scene 和初始 app，但 PAC 声明依旧空，整体 notReady；
这不是新会话闪退或模型加载失败的证明。用户头部位置反馈尚待，未恢复正在运行的
游戏资源。持续目标工具同时重新核实为 active，替代此前 usageLimited 元数据。

2026-10-08 离线原生头 PAC 结构检查发现：原生头声明 3 LOD，实际几何节为
2／3／4；自建 Steve 头沿用身体模板的 4 LOD 与 1／2／3／4。文件偏移 80 的 flags
分别为 `0x00000002`／`0x01000082`，含义未解释；自建头 section0 的未知尾部
`[447,63218)` 共 62,771 字节与身体 donor 逐字相同。现有门禁证明 donor 保持，
不证明这些元数据适合独立头。这是下一候选的结构约束，尚未证明游戏错位根因。
固定 CDMW `mesh_parser.py` 按 `4-section_index` 解码，`mesh_pac_builder.py`
1097／1198／1322 行却按 `n_lods` 判断／重建；直接换原生头 donor 会把原节 4
当作额外节保留，并重建 1～3。必须先验证精确 3 LOD 布局适配，不能盲改 flags。
报告与原生提取件在 ignored `build/steve-head-pac-format-research-20261008/`，原生
头 SHA256 `779cc8247bd72e49c8a86c7cec2535682371d2adff07380e8fe9e9288cab539d`。
主控再次核实原生头会话 PID 18364 仍运行，恢复请求已发给用户；未写运行中资源。

随后用户直接反馈“原生头正常连接在肩膀上方，已退出”。核实实际进程结束后，按
before-restore → 专用 `install_steve_probe.py --restore` → restored 顺序执行成功。
38 项原始文件哈希、36 个最新存档、完整 MC 状态、原点及 ASI 均保持，0041 与 active
receipt 消失。用户观察和恢复证据关联保存在 ignored
`runtime/steve-crash-20261008/native-head-visual-result.json`；未回填 native 渲染成功标记。
原生 PAC 能在同一私有 prefab／descriptor／登记路径正确连接，下一步优先私有 PAC
及材质／绑定链，不能据此证明单一根因；身体错位和装备覆盖仍是未完成项。

原生头显式三 LOD 原型在 ignored
`build/steve-native-head-rebuild-research-20261008/` 已完成原件 259,413 字节逐字自重建，
额外 48 条真实原生记录／16 面控制各层均为 2016 字节，几何节 2／3／4 全部重新生成，
没有旧节 4 残留。只改变已解释 counts／offset，未知 metadata 保持，不修改 CDMW。
旧 Steve 头 48 点／24 面要求 Head93，原生 192 项 palette 不含该骨，原型明确拒绝。
另一独立报告 `build/steve-native-head-binding-research-20261008/binding-report.json`
（SHA256 `96c4c779298a01dd8d18bd35db86f4fe741c167419dd9e440191d41e8d387458`）
确认全部 192 项为 122/B_face_com 的直接子骨，共同父链 122→93→60→40→24→16→13→0；
Head PABC 覆盖 122 和全部 192 子骨，不覆盖 93。slot8 实际为 214/B_Eyeside_12_R，
不能沿用旧身体模板的 slot8→93。3431 个原生顶点正权重独立核对通过。
下一独立候选采用明确共同父骨 122：保持 palette 长度192，只替换固定 slot0 的四字节
hash，其他191项和未知数据保持；清除旧脸／eyecover几何，把48点全部绑定新slot0，
按真实 Head PABC neutral 逆补偿。这是显式新绑定策略，须独立核对量化回放、UV、
三 LOD 和材质映射后再封装；未宣称实际表情／动画或整体 Steve 外观通过。

## 2026-10-08 原生头模板与共同父骨的独立候选

新增 `prepare_steve_native_head_root.py` 与独立 `check_steve_native_head_root.py`。
固定原生头3LOD／2、3、4节，主draw各层48点／24面，原生eyecover清零；palette192
项只有已定位slot0从骨194的hash改到明确共同父骨122/B_face_com，其他191项与未知
metadata保持。所有顶点raw权重255／0…，绑定slot0；HeadPABC覆盖122。按真实中立
矩阵逆补偿，并与固定CDMW交叉核对，量化回放最大误差
`1.6295988343182753e-7 m`，normal／packed V最小dot分别为
`0.9999999999999706`／`0.9999980887382965`。全部UV／拓扑保持；六种材质变体各保留
原Steve head shader／纹理，将wrapper映射到原生main-head与空eyecover两draw。

生成入口只读原版0009，核对EXE／索引／精确条目flags1／解码SHA；不再依赖研究
目录。纯loader不加载CDMW或读取游戏，从包内五份固定template/provenance重构
PAC／PAMI并逐字准入，未知报告字段、篡改、路径逸出、布尔类型和输出覆盖拒绝。
最终 `py -3.12 -X utf8 -B tools/check_steve_native_head_root.py --rebuild`
9/9通过，19.823秒。独立扫描确认metadata中唯一可解析192项表在count344/hash346，
不依赖CDMW最长表扫描的隐式选择。此前基础9/9后收紧kind和包内来源，因此最终重跑。

PAC96721字节，SHA256
`182fc7385116a74536adf3f6603c057d4103f885bf1c6519d62d6689ea877660`；PAMI SHA256
`442b56d40caf42e31f082123577483d195e107504a6cb85bcba556a3638c8ff9`；候选报告
SHA256 `2d850067c97a7d44762eadb68154dbbb992aa2010f3851b63e3b0e8dfd6085a8`。
`--head-root-report` 接入独立五报告十三包，强制descriptor和PAPPTv2，与app及
head-mesh-control互斥；只允许覆盖固定旧assembly头PAC和PAMI两路径，双旧SHA／
新候选重构／完整来源同时检查，其他11payload与metadata-before保持。一般重复路径
保护不放宽。旧默认11、descriptor12、v2十三、原生头十三和00000 app十四纯准入通过；
00002十四计划本机不存在，未执行该计划。组件列表交叉核对仍为CD_Nude／CD_Head。
`check_steve_probe.py --native-head-root --rebuild` 28/28通过，97.477秒，含安装、
最新存档保持、故障回滚、完整重建、双payload/来源篡改及混合报告拒绝。

新包 `build/steve-native-head-root-probe-overlay` 13条，PAZ768192字节，计划SHA256
`2b3bd9241cf5711cc06f479e18bd0210629260471911945338d37af4973d4ff0`。确认游戏关闭
后顺序执行新的before-install、专用安装、installed快照，收据
`5dfe1a43fa9846d6a1f1399bd42a4e2d` installed，variant
`steve-kliff-native-head-root-part-table-v2`；安装文件、完整MC、原点、ASI核对保持。
证据前缀 `runtime/steve-native-head-root-20261008`，独立脚本
`build/record-steve-native-head-root-20261008.py` 绑定该计划，禁止覆写旧阶段。已请求用户
手动进入同一存档反馈MC头是否正确连接并暂留运行；后续记录in-world、退出恢复。
仍不把静态中立回放等同原生蒙皮／表情／scale或实际显示；身体、装备及持续外观未完成。

## 2026-10-08 身体模板、普通skin与空draw的限时复核

本轮头部测试包仍installed，核实游戏尚未启动，没有替换／恢复它。主控直接以固定
CDMW解析原current 01_0002 prefab（SHA
`0184309bae4ded9d51e07269ddebea8ed6f6b08701c59a077f9d866d6002e757`），CD_Nude原本
引用 `character/model/1_pc/1_phm/nude/cd_phm_00_nude_00_0001.pac`，私有身体使用的
donor与原部件一致；不能仅按文件名把它换成猜测的01_0002网格。

独立限时身体审查写入 ignored
`build/steve-body-deformation-research-20261008/{audit.py,report.json}`，report SHA256
`629841944e2da2121a8abe026eacdf8e356ea8a9aa2015996bf7b0cca56a52c7`。固定donor、
身体候选8f26d6…、PAB及当前420条PABC前后核对保持。189项palette唯一在count447／
hash449，全部被PABC覆盖；候选13个实际加权骨及父链也覆盖，13骨均出现在原生真实
记录中。三个原descriptor保留，Head／Hand四层counts为0，身体各层1008点／504面，
每节43344字节，start／split／local索引闭合，没有旧几何尾。metadata仅改既有
counts／offset及main六float bbox，`[447,63218)`62771字节保持；其中1231以后的
运行时语义未解释，不能据此提升为蒙皮ABI已验证。

slot→PAB映射：身体136→25/Spine_Sub；右臂56→138/UpArmTwist、100→356/Forearm_sub、
78→355/Hand；左臂51→133、92→349、82→348；右腿138→17/Thigh、140→48/Calf_Sub、
144→46/Foot；左腿176→18、161→54、160→53，外层与对应内层相同。六slot包括
零权重项全部合法，raw权重总和255，原／新记录gate均63。

固定 `pac_cloth_guides.py:97–99` 取flags bits8–11，`0x01000082`为layout0，返回
无guide区块；不能把bit7／bit24当作cloth启用，也不能把metadata当runtime render_flags。
每层byte38为252×32、253×16、254×48、255×912；`pac_jiggle_skinning.py:112–130`
在有runtime buffer且blend>0等条件下使用全byte或低4bits，骨override可优先。该参考
标注游戏1.0.0.2944，当前1.0.0.2976的render_flags／buffer／override尚未读证；
不会仅因此清零、置255或宣称动态变形为错位根因。embedded-volume helper会因忽略
空descriptor而拒绝候选，这是mesh_parser:1618／pabv_parser:254的工具限制，不能
补写成引擎加载失败。原图小腿处棕色块尚未映射到逻辑部件，Armor遮挡不证明旧Nude
重复。本轮未找到新确证静态缺陷，收束该支线；下一步仍是新版头实际位置与必要的
身体／装备显示对照，未改源码、游戏、材料或当前测试包。

2026-10-08 后续阻塞审计：新版MC头请求发出后，连续三轮均未收到其视觉结果，
实际红沙进程查询及安装事务的game_running均为false。第一轮完成新候选／事务／
安装，第二轮完成身体独立结构复核；第三轮重新核实当前收据5dfe1a43…仍installed，
41项实际文件均匹配，没有可等待的游戏会话。独立离线工作已收束，下一实验取决于
当前包实际显示，不能重复安装或猜测结果。持续目标工具已返回 `blocked`；完整移植
未完成，也未缩小目标。现有手动进入／头部反馈请求保持，当前临时包保留供测试。
用户反馈后核实实例并继续in-world及退出恢复；不能复用旧PID或覆写阶段证据。

## 2026-10-08 — 新目标、目录点击链路与当前头部会话

用户更新持续目标为完整持续 Steve、禁止所有红沙装备、仅 MC 装备、控制栏点击
物品进入背包，以及 MC 单击攻击／实际敌人击退。两套装备和红沙战斗约定成为历史；
新增 M5a，不把 HP HUD 或物品扣数当作战斗完成。AGENTS、README、需求、架构及
当前状态已同步范围；完整其他要求保持。

独立库存审查直接核对 `mc_inventory_ui.cpp` 目录 IconButton→`/ui/grant`、
`bridge/service.py`→`/api/grant`、`Authority.java` 原版最大堆叠→36格 SimpleInventory
的实现。当前每点击一次整组领取，64／16／1来自MC；全部放不下及保存失败整次回滚。
九格和36格点击只选择，领取不自动改选中格。无需重做领取接口，游戏内“点击→实际
数量增加→九格同步→保存”仍待验收；没有可见手持、穿戴、装备效果或装备禁用实现。

已重新核实实际新游戏会话（原始PID／时间仅留runtime），API ready=true、角色位置
可读。绑定脚本写入 `runtime/steve-native-head-root-20261008-in-world.json`：41项当前
文件匹配，原点／ASI保持；MC只有revision22→25不同，库存、selectedSlot和方块
相同。原脚本严格完整MC相等断言因此退出1，不能写成实机检查全通过，也不能猜测
revision变化原因。保留证据，不重复写该阶段。本机记录脚本已改为安装时校验安装前
状态，恢复时保留before-restore的最新完整MC与存档，同时仍记录安装前差异。
没有修改实际MC库存、游戏文件或ASI。

`...-appearance.json` 精确受控链双采样稳定、初始Appearance输入可读；PAC声明为空，
整体notReady，与此前限制一致。nativeFunctionsInvoked／gameMemoryWritten／
appearanceApplicationVerified／steveModelLoaded均false。当前MC头位置仍待用户画面
结果，随后实际退出再恢复；不能把上次“原生头正常”移植成此包MC头结论。

Windows Application事件审查限安装11:23:47→11:57:33，1000／1001／1002合计0；
结果在ignored `build/steve-head-root-launch-audit-20261008/application-events.json`。
缺事件不证明没启动、没闪退或已通过，近期报告可能延迟；未枚举WER个人目录。
此前blocked为历史状态，用户更新目标后工具重新核实active，当前新会话已出现。

装备／攻击独立审查：当前GroundHit没有敌人handle，原生API没有attack／damage／
knockback／equip，NPC编辑器移动不能替代击退。固定Trinity
`e0d287e002a1947a74eacedc21b95bb021d9f5fe` 的DamageApply声明11参数，现有hook
只缩放原攻击；EquipBatch只捕获并透传，未提供拒绝全部装备的行为合同。本项目已发现
其realm标签存在歧义，不能直接复制偏移或声明并调用。固定Universal Modder
`671544554523eb3ae8048c18d4eb8973f5f19652` 的MC／GTA战斗示例依赖ScriptHookV，
不含红沙适配，不能转接GTA native hash。下一项是定向原生合同验证与一个敌人的
单击闭环，不扩大为无边界扫描或用未接线状态模块声称功能完成。

本轮验证：`py -3.12 -X utf8 -B tools/check_character_probe.py` **13/13通过**；七份
交接文档的56个相对文件链接及本机记录脚本AST通过。没有重跑消耗材料的检查，也
没有改存档schema、启动／退出游戏或安装插件。Git同步仍按本仓库普通提交／推送流程。

## 2026-10-08 — MC 四格护甲存储与当前后台升级

持续目标保持完整 Steve、仅 MC 装备及 MC 单击攻击／敌人击退。本轮并行交付可独立
验证的护甲存储，不把它标成原生人物已经穿戴。MC `Authority.java` 使用固定1.21.1的
`Equipment.fromStack/getSlotType`、`EquipmentSlot.split` 和实际
`EnchantmentHelper/PREVENT_ARMOR_CHANGE`，提供四个人体槽 head/chest/legs/feet。
选中格转入一件、更换返还旧件、卸下返还36格，全部沿用原有原子保存／完整回滚；
动物 BODY、手持和非穿戴物拒绝，武器仍保留在背包，手持用途另接。保留真实
ItemStack的耐久、名称、附魔、染色及纹饰，不伪造玩家的创造模式豁免或装备属性。

存档schema3新增四槽，0/1/2迁移时保留最新背包、选中格、revision及完整方块属性／
墓碑，护甲初始化为空。完整快照先用真实 `ItemStack.VALIDATED_CODEC` 和注册表／
槽位／数量验证，再替换运行状态；坏值、未来schema或旧格式夹带未知equipment停用
API并保持原始字节。背包聚合不重复计入已存护甲。

新增 `GET /api/equipment`、`POST /api/equip-selected` 和 `POST /api/unequip`；桥接提供
对应 `/ui/` 路由，查询以JSON保留完整组件，操作严格验证正文／槽名，只提交一次UUID。
回复丢失不自动重试，MC拒绝不吞掉，旧后端404不伪造为空。运行时应用两个标志始终
false，状态文本明确没有连接穿戴或效果；尚未增加面板穿戴按钮。

验证按8768/25580共用隔离世界顺序执行，均正常关闭：

- `tools/build_minecraft.ps1` 成功；自身JAR23800字节，SHA256
  `775004abb805d3324a2aded0912f45f0594100f6d8ca7ea9043f8d7128205ae7`。
  检查ZIP仅含本原型类／metadata后复制到 tracked artifacts；没有原MC程序。
- `py -3.12 -X utf8 -B tools/check_equipment.py` **22/22组通过**：三代迁移、24件常规
  护甲及10种附加穿戴、64/16/1领取、组件／交换／正常重启、操作ID、满包／保存失败
  回滚、真实绑定限制及九种坏存档拒绝。证据 `runtime/equipment-checks.json`。
- `check_inventory.py` **15/15组通过**、`check_block_states.py` **7/7组通过**，仅将
  当前schema预期改为3；对应 `runtime/inventory-checks.json`、`block-state-checks.json`。
- `check_equipment_bridge.py` **8/8通过**，原 `check_inventory_bridge.py` **27/27通过**。
  最初导入旧TestCase导致重复发现旧27项，已改模块引用并最终仅计新8项；不把重复
  执行增加为独立覆盖。同ID不同组件互换／自定义组件删除patch尚未专项检查。

主控备份最新在线状态与正常停止后状态到 ignored
`backups/equipment-backend-update-20261008`，保存旧自身JAR；正常执行
`tools/stop_prototype.ps1` 和 `tools/start_prototype.ps1 -NoGame`，两者exit0，游戏
继续保持原会话／测试包。实际后台schema2→3，revision25不变，四护甲空；停止时
完整最新状态与迁移后状态只差schema和新增equipment。部署后10项核对全部true：
原背包／选中格／方块／revision、三接口装备读取一致、四槽为空、不声称应用、同游戏
实例、原点、同头部收据与ASI保持。阶段证据
`runtime/equipment-backend-update-20261008-{before,stopped,after}.json`，不覆盖。
没有在生产背包执行穿脱／消耗。公开摘要见[equipment-validation.json](equipment-validation.json)。

## 2026-10-08 — 原生装备和攻击合同的有界前置检查

新增 `probe_equipment.py` 与独立 `check_equipment_probe.py`。固定EXE版本／SHA、
六个代码窗口、精确Client装备RTTI与受控actor回链；component+90经descriptor+8数组／
+10计数，最多64条，逐条完整读取D0字节及+C8原始u16槽标签。整条依赖回读及同一
Reader句柄双采样，数组变化、重复标签、错误owner／类型／身份拒绝，不选回退角色；
输出只允许ignored runtime新文件。隔离保护检查 **22/22通过**。主控对当前实际实例
采样exit0，14条稳定且受控表成立，证据
`runtime/steve-native-head-root-20261008-equipment.json`。不解释物品ID或嵌套所有权；
nativeFunctionsInvoked／gameMemoryWritten／restorableSnapshot／equipmentBlocked
均false，不能逐字拷回原始指针记录来“恢复”。

静态装备检查先只覆盖.text导致“找不到批量候选”的判断，后已纠正：当前EXE还在
可执行.rsrc／.xtls含代码。唯一当前批量候选为0x980A50..0x98126A，旧参考偏移不能
复用；四参数形状及F0列表不等于清空API。共享apply有8个调用者，其中7个绕过批量
候选，只hook一处不足以禁止全部装备。原Trinity重建快照仅投影字段，完整D0记录
仍含未解码嵌套指针／effects状态，恢复与拒绝顺序未验证。ignored研究目录
`build/steve-equipment-contract-research-20261008` 保留完整报告与固定反汇编。
下一步定向核对共享apply／七个非批量路径，先验证合同再做装备清除与禁用。

伤害静态报告在 `build/steve-combat-contract-research-20261008`。固定11参数候选的
既有dispatcher仍传null来源，null不能解释为“不会受伤”。一个非null调用者62B870的
slot5来自入口上下文+8、slot1来自+18，但同段先取数再用 -1000-current，尚不能证明
它是常规敌人命中路径。来源／目标类型、敌我关系及击退合同仍未知，未调用任何函数。
两份报告SHA256分别为
`f55be30dbcd55af81ad8d1c3093bb6401f58273f9727d96314ae4c1d7ed0081c` 和
`d49b3ff54eb912039c8789a923b892355fc040a946eae59c26b82770ab2466f5`。
完整史蒂夫显示、原生装备禁用及攻击闭环保留未完成；当前MC头位置请求仍待用户
画面结果，实际退出后按最新before-restore保存并恢复测试包。

发布前核对本轮七个变更Python文件AST、七份交接文档60个相对文件链接、公开JSON
均通过；三份MC隔离报告计数和正常退出标志、实际后台10项核对及自身JAR与成功构建
逐字一致，`git diff --check`通过。所有个人库存、快照、地址、原游戏记录与备份保持
ignored。持续目标仍active；原生共享apply调用覆盖和伤害上下文构造分别由独立子代理
进行只读定向核对，主控保留游戏安装／恢复独占，不因后台完成而宣称完整移植交付。

## 2026-10-08 — 新头测试会话结束后的实际恢复

后台升级与同步后，主控实际进程查询确认红沙已经结束，未自动关闭或重启游戏。
顺序执行当前候选绑定脚本 `before-restore`、`tools/install_steve_probe.py --restore`、
同脚本 `restored`，全部exit0；收据5dfe1a43…已restored，38项原文件哈希匹配，
0041及active receipt消失。退出时36个最新红沙存档、完整MC schema3/revision25、
原点和ASI保持；latestMcStatePreserved／laterSavesPreserved均true。
mcUnchanged仍false表示安装前schema2/revision22与当前合法升级后状态不同，不能
为了改成true而回滚用户材料。两阶段JSON独立保留在
`runtime/steve-native-head-root-20261008-{before-restore,restored}.json`。

未收到当前MC方块头的视觉结论，应用／装配验收仍未知，不用稳定读链替代显示。
新版MC／桥接后台继续运行。已改为询问退出前观察结果，不要求用户再启动已恢复包。
用户询问能否直接使用MC模型：继续沿用原版Steve几何／皮肤导出路线；红沙格式、
骨骼／动画及独立装备部件仍需适配，不用重画外形代替装配问题。

用户随后明确选择“方块头仍错位或没有显示”，当前头候选实机未通过；选项没有
进一步区分两种情况，不能据此断定骨骼绑定或某个字段是唯一根因。新的离线复核
比较原slot0骨194与候选122、原生头真实记录及MC目标坐标；正式候选需独立检查后
才进入下轮安装，不重复安装已失败包。`SteveModelDump.java`确实调用固定官方客户端
的classic宽臂模型构造并导出实际cuboid面／UV；`build_steve_asset.py`核对官方
64×64宽臂Steve皮肤SHA。这条原版模型路线保持，游戏内装配失败不等于改成手绘替代。

装备共享apply定向报告
`build/steve-equipment-apply-contract-20261008/report.json` SHA256
`a99145d59c773f02622f59ecb2aed749e57cda6600bbe0cb894851c7db0c135e`，固定EXE前后SHA、
8函数／call pin及两个完整helper窗口核对通过，未访问实际进程。99fd90在apply前
已经修改D0记录+80/+90/+88；五个旁路不检查结果，996cd0在之后无条件析构／清空
+208/+210队列。apply正常路径只写out DWORD0，不证明下游无错误，也没有写前拒绝
合同。Client虚槽+160是旁路9853f0；Server/Common另指20c8160，持久化覆盖未证明。
最小下一项限制为Client+140→20c2d90、Client+148→980500以及Common/Server+148→
20c2dd0的完整分支／首次表写入／已有拒绝出口；不能据此安装一个返回失败hook。

伤害上下文报告
`build/steve-combat-context-contract-20261008/combat-context-contract-review.json`
SHA256 `ca295bf1b8c0327e7c91c10db38a82cd1cc0beccca57838324e606290ce400f8`。
唯一精确已知直接caller5F792B的C由createdObject+68→组件表+20取得；重读已有固定
构造／binder窗口，确认ClientStatusActorComponent主vtable558D868、C+8=owner、
C+18=status root且root[0]=C。这是自身owner与自身root，不能当不同攻击者／敌人。
getter与DamageApply两次读C+18的跨调用一致性未知，delta为-1000-getter输出槽qword，
没有证明当前HP或自然命中行为。5份JSON、26原始块、8份来源摘要及3脚本AST通过，
仅固定磁盘、未访问进程。下一项仅选另一条已有caller，追来源／目标生产链是否闭合
为两个不同owner；当前仍不可调用伤害或声称击退。没有覆盖旧报告。

原版MC头部空间有界报告
`build/steve-head-bind-space-20261008/report.json` SHA256
`8ff7040c87a7bb57d69b6181cf4d9d3b1a84baf14e058fd16ab0f0d77ee86c6c`。按既有UV的V翻转
与Z反射，MC head/hat实际导出面与当前目标最大误差1.24349e-5 m；122单PABC neutral
最大位移2.90085e-7 m，194主要是毫米级平移，最大3.51725 mm。三层原始weights交叉
核对，没有发现明确静态坐标／绑定缺陷；共享CDMW单PABC约定并不证明引擎skin语义。
有界metadata矩阵匹配未命中，也不能证明没有其他bind编码。仅四字节恢复原palette194
的离线PAC原型已保留，其余bytes相同；变化太小，**不建议为弱位置假设立即再安装**，
未封装为正式包。早先两个审核脚本的顶点顺序／UV假设失败保留，最终audit-v3成功，
没有覆写已有报告。

主控另核对源码：`prepare_steve_material.py`把原18个SkinnedMeshSkin wrapper改为
SkinnedMeshStandard四参数与render_flag4；当前原生头root生成器继续复制此Steve
材质。因此当前候选还有未验证的shader／蒙皮合同变化，不能说只改了几何／palette。
下一更强的单变量是核对固定原生头原字节PAMI与当前两draw覆盖，若对应成立，只换
PAMI、保持失败PAC与另11资源，先验位置（贴图可暂用原生头）；仅是假设对照，
尚未构建／安装，不据此宣称材质是根因。

材质补充报告单独写入 `build/steve-head-bind-space-20261008/material-addendum.json`，
SHA256 `e8fc138901bddd4675d969a39bc7f4d12e4b9f4c03f16c2b646402f7ad426496`；旧报告及
v2均不覆盖。只读0009双提取固定
`character/modelproperty/1_pc/1_phm/head/head/cd_phm_00_head_00_0001_macduff.pac_xml`，
flags50、16149字节，原件SHA256
`440a9e68a2e1ef425d9eef90cb0c50895f6888cb01c301eb7f04efa8197ba9a5`。draw名称与当前PAC
相同；原件只有Index0/1/2三变体，每层EyeCover一个参数，主draw分别Wrinkle14／
Wrinkle14／WrinkleAging16参数，失败包则六变体的两draw均Standard四参数。
此差异不证明shader根因，也不证明原生3变体无效；单变量应完整保留原件，不能
为了迎合旧六variant检查而强扩或盲改shader名。下一轮为独立原字节PAMI候选准入／
只变一资源的十三包封装，再实际头位置与退出恢复，暂用原生贴图；尚未构建或安装。

装备表边界报告 `build/steve-equipment-table-boundary-20261008/report.json` SHA256
`03ffe34348acee6934e9d3fc939a0cf36de929a01835c9f513153697fe79267e`。五E9入口及五完整
body固定字节/pdata/unwind、48正常分支、三个精确类型虚表和EXE前后SHA核对通过；
仅固定磁盘EXE中.xtls重定向静态研究，未接进程。插入重复tag、删除缺tag有既有写前拒绝；
插入复制并可能扩容，删除先处理关联索引，再清理目标／搬移末项／析构、减count
并写0结果。6cf6f40／6cf7d30无file-backed值，额外全局WORD写／EH handler语义未知，
没有自创错误名或解释。局部拒绝不等于全装备禁用、服务端保存或安全可调用ABI；
下一装备门槛是固定来源物品身份／拥有关系、当前线程生命周期与持久化可逆合同，
未扩展effects或全图。主控优先落实上述材质单变量候选，装备／攻击保持独立未完成。

恢复／研究交接发布前检查：公开JSON、七份交接文档60个相对链接、六份静态报告
固定摘要、原生头PAMI16149字节／SHA及实际恢复证据全部核对通过，`git diff --check`
通过。本次只更新四份交接／公开摘要，不上传原件、快照或ignored研究目录；没有重跑
已通过的MC规则检查、启动游戏、改安装或消费材料。持续目标active，下轮优先独立
PAMI原字节对照的生成／准入／十三资源封装，正式显示与全功能验收仍未完成。

## 2026-10-08 保留 MC 几何的原生头材质单变量对照

依据上轮失败反馈与完整PAMI差异，新增
`tools/prepare_steve_head_native_material.py` 和独立
`tools/check_steve_head_native_material.py`。固定0009中原生头PAMI双次读取、EXE／
索引／flags／来源SHA均核对；只把完整16149字节原件放到私有头PAMI路径。三变体、
两draw、EyeCover与SkinWrinkle/Aging shader、全部参数／顺序／原生纹理保持原字节，
不强扩成六变体、不做XML重序列化。完整合同与CLI见[asset-pipeline.md](asset-pipeline.md)。

候选报告 `build/steve-head-native-material/steve-head-native-material-report.json` SHA256
`1ca1972751b346ce8afd9da684ab3d419ef60a92e557a53be1b111145cdb7c7a`。包内四份固定来源为
原生PAMI、失败PAMI、保留PAC和固定head-root报告；纯loader不加载CDMW或读取游戏，
重构整个规范报告逐字比对，拒绝未知字段／重复JSON键／路径逸出／类型及字节篡改。
snapshot为绝对Path，沿用发布前来源回读。所有integration能力仍为false。

`prepare_asset_overlay.py`、`prepare_steve_probe_overlay.py` 与 `install_steve_probe.py`
增加严格六报告模式：assembly、appearance、head-descriptor、v2 part-table、head-root、
head-native-material必须同在，与app及head-mesh互斥。先应用head-root两覆盖，再只改
固定失败PAMI；通用重复路径、旧路径覆盖和存储flags保护保持。失败PAC SHA
`182fc7385116a74536adf3f6603c057d4103f885bf1c6519d62d6689ea877660` 保持；旧PAMI
`442b56d40caf42e31f082123577483d195e107504a6cb85bcba556a3638c8ff9` 替换为原件
`440a9e68a2e1ef425d9eef90cb0c50895f6888cb01c301eb7f04efa8197ba9a5`。新十三包中只有
这一资源变化，其他12项row／localPath／payload及metadata-before／pathc保持。

本轮相关检查：

- `py -3.12 -X utf8 -B tools/check_steve_head_native_material.py --rebuild` **10/10通过**，
  包含真实固定来源重建、完整合同、纯加载、来源／报告／路径与输出拒绝保护。
- `py -3.12 -X utf8 -B tools/check_steve_probe.py --head-native-material --rebuild`
  **28/28通过，95.864秒**，包含真实新输出重建、逐项解包、只改一PAMI、隔离安装／
  故障回滚／恢复、最新存档保持，以及缺依赖／混控／篡改后重算哈希的拒绝。
- 独立审查确认测试22覆盖父类同名方法，无重复错误断言；strict六报告在hash前排除
  非法组合。旧十一／十二／v2注册／原生头／共同父骨及新材质计划纯准入通过；
  历史`steve-app-macduff-00000-probe-overlay`仍引用旧v1注册报告，被组件合同拒绝。
  该历史包不是v2回归通过记录，不能重装或放宽准入；已有v2单app支持未被删除。

新计划 `build/steve-head-native-material-probe-overlay/reports/overlay-report.json` SHA256
`991fa0fcf756bfec6138a3be13f651658721fb2a0a2b9f9e7dbe724871d39048`；PAZ768912字节，
13项payload往返、边界／校验和及PAMT无编辑重建一致。安装variant为
`steve-kliff-native-head-root-original-material-part-table-v2`。这份诊断暂用原生头贴图，
实际MC头几何／UV和palette保持，最终MC皮肤尚未完成；不证明shader是错位根因。

核实实际游戏关闭、无active receipt／0041且38项原始文件匹配后，沿已授权手动进出
流程实际安装新包。收据 `5249d2f2339844f3a5b27b77d1353a66` 为 installed，kind为
`steve-mesh-parameters`。新记录器 `build/record-steve-head-native-material-20261008.py`
绑定此variant／计划SHA，证据前缀 `runtime/steve-head-native-material-20261008-`。
before-install／installed两阶段均exit0；41项安装文件、36个存档、完整MC schema3／
revision25、原点及ASI核对保持。阶段输出拒绝覆盖，恢复须比较退出时最新MC／存档。

当前临时包在游戏目录中，已请求用户手动进入同一存档、反馈方块头位置并先保持运行。
尚无本包游戏内位置结果；之后需实际新会话核对及必要只读采样，用户正常退出并确认
进程结束后恢复。头／身体／动画、持续外观、MC装备穿戴、红沙装备禁用与MC攻击仍未完成。
current-state已缩短为现场入口，历史证据留在本文件，不复制旧PID作为当前地址。

本轮另一项有界静态伤害审查：
`build/steve-combat-owner-pair-20261008/combat-owner-pair-review-v2.json` SHA256
`56b242368064909d724d452a01ccece21df00378b63c635f2741727354e3f042`。仅选择已有39行列表中
call209C573，完整pdata窗口209BDC0..209CB2C，3436字节，窗口SHA
`0529743fe686bf116aede3e3cb2fbb6aed50bbe25bc9450bfb8cd7a01fbab774`。两形参链独立，
但窗口没有具体输入构造、精确攻击者／敌人类型或两条owner回链，指针比较也不证明
敌我；40字节尾部为switch数据，未当作指令。结论typed ownerpair unavailable，未访问
游戏进程／写内存／调用伤害或击退。不能将此线索当作MC单击攻击完成。

发布前六份相关源码与新ignored记录器共7份AST、七份文档67个相对链接／围栏、四份
候选／计划／安装阶段JSON及两个报告固定摘要核对通过，`git diff --check`通过。
本轮没有修改MC规则、重建ASI／JAR或消费材料；源码／文档正常同步，游戏原件及
runtime／backups／build保持忽略。持续目标active，等待当前单变量实机结果并继续完成。
