# 原生角色契约：静态线索、只读观测与待验证条件

更新于 2026-10-07，仅针对 EXE `1.0.0.2976`、SHA256
`57da440d72f4db974f25fef047cf84c4dadd999a88cb2a3c5af4c9bd67fde1e7`。
前半部分为磁盘静态分析，末节另记当前身体到外观控制器的真实只读观测。
没有执行外观请求、生成人物、登记第四身份或应用 Steve。
RVA 是此 SHA 的定位入口，不是跨版本接口或可复用堆地址。

## 切换请求与身份命名空间

`TrocTrStartChangeFocusActorReq` RTTI 的 vtable 为 `0x5B244F8`，slot 2
handler 为 `0x298D940`。静态 ABI 为
`uint32_t* __fastcall(void* handler, uint32_t* result, const void* envelope)`，
handler 返回原结果指针；不能套通用八参数 thunk，也不能仅凭类名主动发送。

envelope `+0` 为发送者，`+0x10` 为 u16 总长度，`+0x18` 为缓冲指针。
封包头长 5，头 `+3` 的 u16 payload 长度须等于总长减 5；payload 必须恰好 5 字节，
包含 u32 CharacterInfo key 和 u8 选项。业务进入 `0x294D5B0`。
u8 非零会跳过部分可用性门槛，尚不知道正常 F1 用值；不绕过这些门槛。

**外层结果 0 只代表请求派发完成，不能证明切换成功。** handler `+0x21` 禁用时也
返回 0，业务错误另行 ACK。必须同时记录用户 F1 操作、请求 key 及实际受控身份变化。

owned lookup `0x214E7A0 → 0xE4B8080` 遍历发送者组件表 `+0x110` 中的记录：
候选 pointer array `+0x18`、u32 count `+0x20`。每条记录：

| 字段 | 静态含义／限制 |
| --- | --- |
| u16 `+0x20` | **CharacterInfo 目录行号**，不是 MercenaryInfo No；`0xFFFF` 无效 |
| i64 `+0x28` | owned Mercenary No 候选，`-1` 无效 |
| u32 `+0x50` | Actor handle 候选，不是角色 key |

getter `0x389570` 按零起始行号读取 CharacterInfo global `0x6D69A48`；目录候选
count `+8`、record-pointer array `+0x58`。记录首 u32 与切换请求 key 比较，记录
`+0xBE` 是另外的 MercenaryInfo 目录引用候选；禁止混用三个命名空间。

StatusActorComponent 的 u16 `+0x30` 同样进入这个 CharacterInfo getter。
旧快照的 0／3 因而是**行号线索**，不能直接叫角色 key。
固定 World Builder 的 `notes/characterinfo.tsv` 顺序含 key 1 Kliff、两个 Kliff
变体、key 4 Damian、Damian 变体、key 6 Oongka；仍需实际加载目录的 key／RTTI／
状态 owner 回链确认，不能靠静态表加一推导所有 key。

## 创建与保存尚未解决

World Builder 的 `TrocTrSpawnCharacterCheatReq` 产生场景 NPC／编辑器 UID。
它不提供 owned 状态、F1 名单或 MercenarySaveData 生命周期。AI ownership 切换
也不是主角控制权。生成 NPC 或修改已有三人模型都不能通过第四角色验收。

当前 SHA 的三个 cheat handler 只解析有效参数并返回 0，没有业务创建调用：
Hire `0x2A302D0`、ChangeHiredWithSummon `0x2A195E0`、Discharge `0x2A304D0`。
`FrameEventRegistMercenaryReq → 0x2C49EA0 → 0x2BACCD0` 有真实业务，但要求
ServerMercenaryClanActorComponent `+0x150` 的近期登记条件记录匹配及有效时限，
不是任意角色 ID 的通用注册 API。

MercenarySaveData vtable `0x58B3520`，ctor `0x18AE8C0` 至少初始化 `0x2E0` 字节。
字段 setter 的静态线索：mercenaryNo u64 `+0x30`（`0x18A3380`）、ownedCharacterKey
u32 `+0x38`（`0x18A38B0`）、IndexedString name `+0x40`（`0x18A3CD0`），装备和库存
是带 dirty 追踪的容器。没有验证实例、插入 ABI 或保存回读；不能裸追加 owned 指针。

## 回到 M2 时的具体步骤

1. 先重新检查 EXE SHA、进程、精确 RTTI 和稳定目录边界；旧堆地址无效。
2. 外部只读采样目录 key、Status 行号、owned No 和 Actor handle，用回链关联当前身体。
3. 需要记录请求时，先审核独立三参数被动 thunk，版本／SHA／vtable／序言全部门禁，
   最多 32 条定长记录；原函数仅调用一次、原返回值透传，不主动发送请求。
4. 对一次实际 F1 切换与回切关联控制身份；翁卡不可切时记录提示，不强行解除限制。
5. 继续定位生产角色创建、owned 保存入库和 F1 列表构建；全部验证后才开始 M3。

被动观察候选与原始反汇编留在忽略的 `vendor/research/`，尚未集成或安装。
新聊天按本页重建必要探针；不把存在本机的研究候选当作已经发布的功能。

## 2026-10-07 当前身体到外观控制器的只读路线

本段服务于最新“复用当前身体的 Steve 模式”，不新增第四身份。固定 EXE 的生产
调用者 `0x629870` 内 `0x6298DD` 代码链为 actor `+0x68` 组件表、表 `+0x40`
ClientCharacterControlActorComponent、组件 `+0xB8` 中间结构、结构 `+0x20`
CharacterCustomizationController；随后调用 `0x72C5D0`、`0x72C0A0`、`0x726C50`。
这些 RVA 仅证明本 SHA 的静态调用关系，未用作本轮的原生调用入口。

新只读探针从固定 World global `0x6D69190` 出发，要求三条 RIP anchor 一致、manager
与 user 的当前身体指针一致、身体反向 user 一致，组件 `+8` 反向当前身体。控制器
主 vtable 必须为 `0x559DD98`、RTTI 必须精确；`+0x10` owner 与 `+0x60` 弱引用
holder 的 `+8` target 减 `0x28` 一致，target `+0x15` 失效标志为零。owner 必须为
SceneObjectClient，`+0x210` 的组件数组在有界 count 内恰好包含该控制器一次。

控制器分配大小 `0x140` 来自构造调用；mesh `+0xA0` 和 decoration `+0xB0` 选择数组
的指针/count/capacity 分别位于容器 `+0/+8/+0xC`，字节步长由固定 resize helper
`0x3D2BE0` 与 mesh setter `0x92F2B90` 的逐字节复制支持。只读工具仍不解释中间
结构类型，不写这些数组，也不调用刷新函数；后续 schema 2 探针补充的已加载选项
资源只读合同见本节末尾，不能反推首次观测已完成该检查。

工具 [probe_appearance_controller.py](../tools/probe_appearance_controller.py) 限定固定
链、4KiB 单次读取上限和两次稳定采样，复用版本/SHA、VirtualQueryEx 可读页与只读
进程权限。完整链任一部分不符就保留失败证据并停止解释，无任意地址参数、堆扫描或
HTTP 写入。17 项隔离检查通过，随后取得下述实际只读关联；应用、恢复和跨重载
生命周期仍未验证。

### 2026-10-07 实际受控身体链观测

用户恢复接管后的同一受支持游戏实例中，实际运行只读探针，证据在本机 ignored
`runtime/appearance-controller-20261007.json`。两次采样稳定，当前身体/user 回链、
控制组件/身体回链、精确 RTTI 和控制器/SceneObjectClient owner 回链均满足门禁。
owner 组件数组 count/capacity 为 **45/64**，其中该控制器恰好出现一次。

mesh 选择数组 count/capacity **16/16**，16 字节均为 `0xFF`；decoration 为
**250/250**，其中 117 字节非零。这里只报告容器及选择字节，不推断资源表上界或
每项身体/装备槽含义。静态消费者对 `0xFF` 有默认/preset 回退路径，不能将全 FF
解释为“所有 mesh 隐藏”，也不能据此写入任意选择值；实际加载选项边界仍未验证。

本次没有原生函数调用、游戏内存写入、堆扫描或 Steve 模型加载，输出中的
appearanceApplicationVerified/appearanceRestoreVerified/steveModelLoaded 均为 false。
两次稳定采样也不等于原子快照。下一步需建立实际加载的 descriptor/mesh 选项、原生
刷新线程及恢复契约；只读找到当前控制器不足以直接实施身体/装备替换。原始堆地址仅
保存在本机观测文件，不作为以后进程的固定入口。

### 2026-10-07 已加载选项资源与 FF 回退

只读报告 schema 2 增加以下精确资源类型，仍限固定 EXE SHA、RTTI/COL 与 vtable。
资源名由 `+0x20` 的字符串 holder 的 `+0` 字符指针读取，依据原生 `0x48D670`；
最多 512 字节、每次 32 字节。若跨入不可读页，即使更早可能存在结束符也保守拒绝，
不跳过缺失页拼接名称。读取的名称仅为数据，不作为文件路径或指令执行。

| controller 字段 | 精确资源类 | vtable RVA | 已核对目录 |
| --- | --- | --- | --- |
| `+0x128` | CustomizationMeshParamData | `0x559F0D0` | `+0x28` QII，group stride `0x58` |
| `+0x110` | CharacterCustomizationData | `0x559F150` | mesh `+0x38`、decoration `+0x28` QII 字节数组；null 合法 |
| `+0x130` | CustomizationDecorationParamData | `0x559F110` | `+0x48` QII，group stride `0x98` |

mesh group `+0` 是 option QII，`+0x10` 为默认字节。固定 `0x72C230` 消费链的
`0x72C2B5` 先检查 preset 状态和相应字节：当前选择 FF 时使用非 FF preset，
否则用 group 默认，再与真实 option count 比较；超界走跳过路径，不能解释为
“全部隐藏”。option stride `0x120` 由 `0x72C3F9..0x72C40D` 的计算支持，option
`+0` 的 prefab 引用数组／8 字节 holder 步长由 `0x72C4B1..0x72C51C` 支持。
这里只解引用当前有界候选，不猜测未选 option 的身体／装备槽语义。

decoration group 的 `+0x7E..+0x83` 为已观察的类别、模式、声明 min/max/default、
palette 索引输入；`+0x3C` 为关联 mesh slot 输入。`0x735F70` 等后续消费还会依据
未解码 palette／mesh 修正范围，因此不把声明 max 当作最终可写上界。

`check_appearance_controller.py` **28/28**、既有角色 **6/6** 通过；直接读取固定
EXE 重新核对 **10 个代码窗口逐字一致**及三类 RTTI。实际新进程的独立输出
`runtime/appearance-options-20261007.json` 两次稳定，显示：

- mesh 资源 `character/descriptors/customizationmeta/meshparam_example_kliff.xml`，
  **7 组／capacity 8**，选项数 **2,2,7,7,0,0,0**。
- preset `character/descriptors/customization/cd_pc/cd_phm_macduff_customization.paccd_xml`，
  当前与 preset 的 mesh 数组各 **16/16、全 FF**。前四组选 default 0，后三个空组
  原生应跳过。额外 9 个选择明确 unmapped；meshGroupChoiceBoundsVerified=true
  只覆盖实际 group，完整数组的 loadedOptionBoundsVerified=false。
- 四个候选名称为 `cd_phm_00_nude_01_0002_macduff`、
  `cd_phm_00_head_00_0001_macduff`、`cd_phm_00_hair_00_0022_player` 和
  `cd_phm_00_beard_00_0005_06_player`。它们不是实际已渲染 descriptor 的证明。
- decoration 资源 `character/descriptors/customizationmeta/decorationparam_player.xml`，
  **250/250**，声明输入已读；computedBounds、renderedDescriptor、slotSemantics、
  appearanceApplication／Restore、Steve 加载均保持 false。

下一步在已界定 owner `+0x210` 组件数组中，按 `0x4736A0` 的实际反射类型查找
CharacterScene；其目标反射元数据来自 `0x4667A0` 返回的 global `0x6D6C850`，
不能仅凭名字或扫描堆猜实例。Scene `+0xA0` 与 `+0x78` 弱渲染组件、组件 `+0xA8`
源缓冲的本轮合同及观测边界见下节。静态更新路线 `0x726C50 → 0x72C230 → 0x7267B0
→ 0x726E40` 尚未证明调用 ABI、线程或可恢复副作用，当前不得作为主动调用入口。

随后从固定 `0009/0.pamt` 只读解出本次三份 meta/preset 与四个非空组 prefab，
七项原文与结构报告仅保存在 ignored
`build/steve-appearance-research-20261007/observed-native-resources/`。meshparam
SHA256 `5c35726023151b024bbd10b03481bd0bb2c6c0ba745fcefe68907d20c07e40b5` 的
UIKey 将七组命名为 Body、Head、Hair、Beard、Mustache、Whiskers、Eyebrows，
数量／默认／名称与实机一致；这是原文声明的分类，不是已验证装备槽合同。

实际 `cd_phm_00_nude_01_0002_macduff.prefab` SHA256
`0184309bae4ded9d51e07269ddebea8ed6f6b08701c59a077f9d866d6002e757` 的 CD_Nude
引用 `character/model/1_pc/1_phm/nude/cd_phm_00_nude_00_0001.pac`，与现有 Steve
PAC 模板建立真实资源关联；但其 prefab／SkeletonVariation 不能等同先前的 00_0001
prefab 候选。它保留 CD_Underwear；另有头／眼／牙／眉、头发和胡须输入。共享身体
资源也被其它静态 appearance 索引引用，不能对共享 nude 全局替换并声称仅作用当前
玩家。私有资源合成和各部分保留／隐藏／装备绑定规则仍需明确。

### 2026-10-07 CharacterScene 与实际渲染组件的类型门禁

schema 3 只读工具沿已验证 SceneObjectClient owner `+0x210` 的有界组件数组定位
唯一精确 CharacterScene vtable `0x5B409A0`。其 slot `+8` 必须指向 getter
`0x2D091C0 → 0x4667A0`，反射元数据 global `0x6D6C850` 必须通过主对象
COL／精确 RTTI `ReflectMetaObjectBind<CharacterScene>` 与 vtable `0x557CFC0`
门禁。Scene 自身没有有效主 MSVC COL，工具不伪造其 RTTI 名称。

Scene `+0x60 → holder+8 → owner+0x28` 验证受控 owner 回链；Scene `+0xA0`
的参数资源要求构造 vtable `0x5B38478`，只读已知 `0x58` 字节前缀，并验证资源
`+0x50 → holder+8 → Scene+0x28`。构造分配 `0x200` 字节不是解释剩余字段的
许可。弱目标 `+0x15` 失效标志必须为零；Scene `+0x10` 不解释为 owner。

本轮实际报告 `runtime/appearance-scene-20261007.json`、
`runtime/appearance-scene-ready-20261007.json` 及
`runtime/appearance-scene-rejection-detail-20261007.json` 均保存首次采样的部分
Scene／参数回链，随后在 Scene `+0x78` 渲染弱链目标的类型门禁处拒绝。
每份报告均未完成两次稳定采样；`stableTwoSamples`、`characterSceneObserved`、
`sceneRenderSelectorObserved` 均为 false，不能用部分前缀代替完整链验收。

详细拒绝证据给出目标 vtable RVA **`0x5B4C6C0`**；其 `vtable-8` 指向
`0x2DA79E0`，已读 24 字节与固定 EXE 逐字匹配。该位置实际是
`sub rcx,0x28; jmp 0x2DA3FA0` 的代码跳板及填充／下一函数开头，五项 COL
检查均失败。它不是 SceneObjectClient 的有效主 COL，也不是等待加载即可接受的
RTTI 证据；此前将该 vtable 暂称 SceneObjectBase 的研究推测已纠正。

磁盘静态核验确定该构造写入与反射类型如下，原始字节与报告仅留 ignored
`build/steve-render-scene-research-20261007/actual-render-identity-static.json`：

| 严格身份条件 | 固定 EXE 证据 |
| --- | --- |
| SkinnedMeshComponent 构造写入精确 vtable `0x5B4C6C0` | `0x2D96D6A..0x2D96D74` |
| vtable slot `+8` 精确 getter／factory | `0x2D88B10` JMP `0x360220` |
| factory 写入反射元数据 vtable `0x55739A0` | `0x36026F` |
| factory 返回元数据 global `0x6D6A160` | `0x3602B3` |
| 元数据有效主 COL、精确 RTTI | `ReflectMetaObjectBind<SkinnedMeshComponent>` |

工具据此增加独立 SkinnedMeshComponent 分支，要求上述代码字节、精确 vtable／
getter 和已类型验证的反射元数据，沿既有受控 owner → 唯一 CharacterScene →
`+0x78` 弱链进入；不猜新 owner 字段。旧 SceneObjectClient 精确 RTTI 分支保留，
其它类型仍拒绝，不将 COL 失败当作反射名称回退。SkinnedMeshComponent 自身的
`primaryMsvcRttiVerified` 仍为 false。

隔离命令 `py -3.12 -B tools/check_appearance_controller.py` **48/48 通过**；固定
SHA EXE 重新读取的 **25/25 代码窗口逐字匹配**。检查覆盖未知／损坏类型拒绝、
失败字段保留、反射 getter／COL／RTTI／vtable、全局边界、重复读取及部分样本
不晋升成功。新增严格分支尚未实机完成双采样；用户退出游戏后不追加探针。

通过身份后，工具最多读取组件 `+0xA8` 的不透明容器与其 `+0x18/+0x20` 两个
资源指针、`+0x28` 的 0／1 选择字节；所选资源和缓冲不解引用，不解码 descriptor。
实际资源类型、当前已渲染 mesh、身体／装备槽仍未验证。下一步先核对该容器的
生产／构造类型及资源消费者：固定 `0x726E40` 在 `0x726F03` 以组件 `+0xA8`
进入 `0x2DF0240`，返回真后在 `0x726F13` 以组件 `+0xB8` 进入 `0x2DD52D0`。
这些函数包含资源引用更新及后续操作，不能用孤立指针替换代替完整应用／恢复合同。
调用 ABI、游戏线程上下文、私有外观切换、恢复、跨重载持续应用及 Steve 加载均
未验证；本轮没有调用原生函数或写入游戏内存。
