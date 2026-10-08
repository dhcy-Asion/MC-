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

### 2026-10-07 原版资源会话的完整 Scene 双采样

临时原木包恢复后，以原版资源启动新游戏实例，运行
`py -3.12 -B tools/probe_appearance_controller.py --pid 36352 --output
runtime/appearance-render-typed-20261007.json`，本次 **observed**，两次样本完全一致。
控制器恰好出现在 owner 的 45 个组件中一次，唯一 CharacterScene、Scene→owner、
参数资源→Scene 弱回链均通过；实际渲染链接的 SkinnedMeshComponent 精确反射
类型通过，其对象与受控 owner 不同。资源选择容器有两个非空输入，当前 index=1；
此基础采样不解引用所选资源，renderedDescriptorVerified 与外观应用仍 false。

原始截图和报告绑定于 `runtime/appearance-render-context-20261007.json`，本机
会话 `36352:134358196715607705` 的进程时间及固定 EXE SHA 前后相同，MC 完整
API 保持 revision 22。此前三份 gate 拒绝报告仍保留；新成功记录来自新分支和新
实例，不更改旧失败结果。本次没有安装资源、创建对象、消费材料或写游戏内存。

### 2026-10-07 私有全身资产与装备遮挡的缺口

对固定 `0009/0.pamt` 的七份原文、四个已观测 prefab 和两套七资源候选逐项核对后，
确认旧候选只重定向 CD_Nude，仍带 CD_Underwear。实际四 prefab 共 11 个蒙皮对象：
身体 2 个，头 7 个（头、左右眼、眉、睫毛、牙和面部绒毛），独立 Hair 和 Beard
各 1 个。原始共享身体也被 Lorenzo appearance 消费；直接覆盖它会改变其他使用者。
私有替换必须同时处理这些部件，空眉选项组或 FF 默认回退均不能代替排除原部件。

实际 Macduff 身体 descriptor 使用 `01_0002.pabc`、`BaseCharacterScale=1.02571`
和 `macduff.hkt`；旧候选仅复制 `00_0001.pabc` 的模板，不具有当前描述符等价性。
需要保留当前绑定基线的私有描述符；最终 actor-local 选择/组合不能借改共享基线来
规避恢复。后续允许单独验证有明确共享范围、可恢复的 meshparam 覆盖候选，见末节；
私有 meshparam／preset／decoration 的 actor-local 绑定与加载、恢复尚未实现。

原文还证明部件名、shrink tag 与装备遮挡耦合：44 条 partshrink 规则涉及 Nude、
Underwear、Hair、Beard，postfix `_F` 中部分规则按 CD_Head 等名字隐藏。现候选把
Steve 头装在 CD_Nude 下的 PAC draw 0，尚无 CD_Head 等价遮挡映射。静态 appearance
的 8 个常规 Armor 基底和 4 个 Preview 条目不是当前装备状态，也不代表全装备覆盖。
必须独立处理 Steve 头／帽层与身体的组合及装备行为，再做实际换装对照。
原文、固定索引来源和报告留在 `build/steve-fullbody-review-20261007/`；此检查只读，
没有安装资源或更改原版存档。

### 2026-10-07 两个选择资源的身份头观测

schema 4 的 `--render-resource-identities` 为可选只读扩展：从同一次受控 Scene
已验证的两个输入中，每个非空资源只读自身的 8 字节 vtable，随后仅在主模块内读
候选 locator 的 24 字节。标准主对象 COL 门禁通过才读最多 192 字节且必须 NUL
终止的 ASCII RTTI 名称。即使名称成功也不准入未知布局，exactResourceClassVerified
仍 false。默认模式不解引用这两个资源；新增两个消费代码窗口固定在 EXE 上。

两项同级资源分别记录失败；失败项不再跟随其未知字段，但可以读另一项的身份。
最终重新核对 Scene、参数回链、渲染类型、pair/index 和成功身份后，任一项失败仍
拒绝整个结果，不提升稳定性或描述符标记。失败时没有完成 sample 末尾的完整
controller 复读或第二样本，所以部分头信息不能称为完整稳定受控身份。
`check_appearance_controller.py` **62/62**、固定 EXE **27/27** 字节窗口通过。

实际首次 `runtime/appearance-render-resources-20261007.json` 在 slot 0 拒绝。
扩展同级记录后，`runtime/appearance-render-resource-pair-20261007.json` 读到两项
都是 vtable RVA `0x5B3FC58`；`vtable-8` 都指向 `0x3600C0`，已读 24 字节为
`mov al,1; ret`、填充和后一小函数开头，sig 并非 1，均不是有效 COL。
当前 index=1，因此最后报告 selectedResourceDereferenced=true 仅指读了选中资源
的 8 字节身份头；没有读 `+0x68`、descriptor、PABC 或资源名称。整体 rejected，
所有全局成功标记和应用标记 false。基础模式另存
`runtime/appearance-render-schema4-baseline-20261007.json`，双采样仍 observed。

固定 EXE 后续只读静态检查确认 3 个生产调用均先分配 `0xA0` 字节；构造跳转
`0x2CC7F00→0x109DB720` 在 `0x109DB74F` 写上述 vtable，析构
`0x2CC7AA0→0x109D5170→0x2CC7970→0x109D0B40` 在 `0x109D0B57`
写回并释放内部引用。`+0x10/+0x14/+0x15/+0x16` 的引用计数／失效消费有字节依据；
资源 `+0x68` 也有消费者，但嵌套对象类型未确定。此表的后续地址含析构代码，不能
直接套用 CharacterScene 的 slot-8 反射 getter 规则。没有用 exact vtable 独自
升级为已知 descriptor，也没有调用这些函数。

可复建脚本 `build/steve-render-scene-research-20261007/inspect_unknown_selector_resource.py`
和 `unknown-selector-resource-static.json` 保留 12 个关键字节窗口及 7 个有界片段。
它们只是固定 EXE 的构造／释放事实，精确类名、嵌套资源类型和应用／恢复合同仍未完成。

### 2026-10-07 构造证据限定的嵌套引用双采样

新增互斥的 `--render-resource-links`（schema 5）；原默认与 RTTI 模式仍为 schema 4。
这条路径不放宽旧 COL 门禁，而是使用独立的构造／clone／consumer 合同：构造在
`0x109DB74F` 写 vtable `0x5B3FC58`，`0x109DB78F` 将 +68 置零，clone 在
`0x2CC7E55` 受引用复制该字段，`0x2DEFE18` 的 pair/index 消费链读选中资源 +68。
新增四个 pin 只由新模式要求，固定 EXE 共 **31/31** 窗口通过。

对至多两个非空父资源，每项只读 parent[0]、parent+68、非空 nested[0] 三个 QWORD。
父 vtable 必须精确匹配；嵌套 vtable 只检查主映像范围，不读取 COL、名字、descriptor
或其它嵌套字段，不准入其类型。两项分别记录失败；成功项重读、Scene/参数/类型/
pair/index/owner 完整回链和两次采样全部一致才设置 renderResourceLinksObserved。
空父或空嵌套引用是 notReady，漂移与读取失败不提升为成功，末尾模块变化清除标志。
隔离检查 **76/76** 通过，包括未解释字节不读、两个模式互斥和最终模块／摘要变化。

实机 `runtime/appearance-linked-headers-20261007.json` 在同一原版资源会话
`36352:134358196715607705` 完成双采样：两个父资源 +68 指向同一非空对象，嵌套
vtable RVA 为 `0x5B426C0`，当前 index=1。整体 observed、完整受控链及链接标志为 true；
nestedClassVerified、nestedLayoutInterpreted、renderedDescriptorVerified、外观应用
和 Steve 加载仍 false。这证明当前选中资源的一个受引用链接稳定，并不证明资源名称、
PABC、描述符应用函数或线程 ABI。没有调用游戏函数、写内存、创建对象或改变 MC 库存。

### 声明 PAC/PAB 输入路径：schema 6

`--render-input-paths` 与 `--render-resource-identities`、`--render-resource-links`
互斥，默认模式保持 schema 4，links 保持 schema 5。新增模式不沿无名资源 +68 猜测
descriptor，而从已经通过精确反射门禁的受控 SkinnedMeshComponent 读取两项声明输入：

| 字段 | 固定身份和消费证据 |
| --- | --- |
| component `+0xD8` | PAC 文件输入属性，构造 vtable RVA `0x5B37368` |
| component `+0xE8` | PAB 文件输入属性，构造 vtable RVA `0x5B43050` |
| property `+0x1A`、`+0x10` | flag 的掩码 `0x08` 位为零且直接 owner 精确回指该 Skinned component；弱 owner 分支拒绝 |
| property `+0x28 → holder[0]` | 原生字符串消费链指向字符字节；holder 须对齐，字符地址允许非 QWORD 对齐 |

构造／owner／文件扩展名与字符串消费者共增加 13 个固定字节窗口，连同基础 27 个，
该模式 **40/40** 窗口经固定 EXE 核对。每项最多逐字节读取 512 字节且必须包含 NUL，
只接受可打印 ASCII；地址、vtable 或回链失败在进入后续布局前停止。空属性、空 holder、
空字符指针或空字符串为 notReady，不当作已加载资源。扩展名是否为 pac/pab 只作
`extensionMatchesNativeInput` 记录，不据此证明文件存在或已被引擎消费。

两项分别保留成功或失败证据，失败项不继续解释未知字段。包括 NUL 在内的全部实际
读取字节加入本次 Scene 稳定性复读；Scene/参数/弱链/pair/index/owner 必须完整，
两次样本相同且最终代码、模块与 EXE 摘要未变化，才可提升 `renderInputPathsObserved`。
缺失基础 Scene 字段时，即使两条字符串可读也不提升完整观测。输出仍限定新建的
ignored runtime JSON，拒绝覆盖已有证据。

隔离检查当前 **93/93** 通过，覆盖三个模式互斥、坏 vtable／owner／字符串、弱分支
提前拒绝、非对齐字符地址、同级失败记录、读取中漂移、模块变化及部分 Scene 不晋升。
这只证明声明输入的只读合同；`selectedRenderResourceEquivalenceVerified`、
`renderedDescriptorVerified`、`appearanceApplicationVerified`、`appearanceRestoreVerified`
和 `steveModelLoaded` 均保持 false。该模式不调用任何原生函数、不写内存或改变选择。
本轮实际 `runtime/appearance-render-input-paths-20261007.json` 两样本完全一致：PAC
属性的类型／owner 正确但声明为空，PAB 声明为 `character/model/1_pc/1_phm/phm_01.pab`。
完整链稳定，整体如实为 notReady、renderInputPathsObserved=false；不能从空声明推断
没有实际渲染 PAC。详情见进度，不凭声明路径宣称 Steve 已显示。

### 私有资源组合及有界共享外观试验

当前离线 assembly 已组合十项私有资源：头身 PAC/PAMI、三 DDS、独立 CD_Nude/CD_Head
prefab 和当前身体 descriptor。身体使用实际 01_0002 neutral 补偿；头原 PAC 不变，
因为 Head0001 的 207 条 PABC 记录未包含其唯一加权骨 93。PAB 回退与身体继承的
数值比较是两个候选假设，尚未证明原生头身合并、HeadScale、动态动画及装备语义。
组合 **12/12** 离线检查不代表原生准入。

首次显示试验的候选只在固定 Kliff meshparam 的默认 Body/Head MeshSet 中将原
basename 改为 `crimsonmc_steve_body_1_21_1`／`crimsonmc_steve_head_1_21_1`；两处
逆替换逐字恢复原 XML，**12/12** 离线检查通过。七组选择、PABC、Hair/Beard 和装备
均保持，FF 不作隐藏。该文件由 Macduff 00000/00002 等共享消费者使用；静态扫描
不能证明全部运行时实例，因此这条试验明确不是 actor-local，不覆盖共享 nude PAC。

十一资源专用 overlay 与 `steve-mesh-parameters` 事务种类提供临时包安装／恢复入口，
原木 CLI 默认 `oak-log` 不变，两种 owner/收据不能交叉恢复；安装恢复必须关闭游戏，
恢复不覆盖后来存档。候选准入和关闭游戏的包事务均不能证明外观刷新 ABI、跨重载
自动持续 Steve 或实际恢复。新包故障检查 **21/21** 通过，实机验收另行记录；窗口接管
在物理 Escape 后停止，获得用户再次授权才恢复。首测新会话已实际读到 Body／Head
两个私有 basename，均为合法的默认选项 0；这仍是选项声明。用户随后反馈实际仍是
原角色，外观切换未通过。随后再次
收到物理 Escape 停止；用户退出后临时包已恢复，详细证据见进度。流程及精确资源范围见
[asset-pipeline.md](asset-pipeline.md)。

### 首测反馈与初始装配分支

用户补充首测进入世界后仍看到原角色，因此结论为选项配置已加载、外观切换未通过。
固定 EXE 的 `0x46B100` 初始装配读取 Appearance 资源 `+0x38` 的 16 字节 Name 记录；
`0x2438A40` 解析器将这些 Name 与 Customization MeshParamFile 分别保存。故选项表
中的私有 basename 不能单独证明原始 app 部件被替换。当前两个已知 Macduff app 的
Nude／Head Name 仍是原名，具体受控实例使用哪份 app 尚待读取。

`0x72C230` 消费 controller `+0xF8/+0x100/+0x104` 的指针／count／capacity，元素
为三字节 slot/oldRaw/newRaw。空队列跳过；new FF 经 preset/default 解析后，与 raw
old 相同也跳过。`0x72C31B` 的 old FF 分支不删除旧选项，因此 FF→0 不能视为完整换装；
0→0 则不执行替换。初始装配仍可能通过 `0x72C5D0→0x92F2B90` 排入 FF→FF。
本次没有采样实际队列，不能断定空队列就是失败原因，也没有执行这些写入或调用。

上游 controller vtable slot 1 在此 EXE 为 `0x723A00→0x723A10` 反射元数据 getter，
并非已证明的 update 回调。World Builder pump 固定签名唯一命中 `0x42820E0`，但两者
线程等价未验证；不从上游 hook 命名推断安全调用线程。磁盘研究的 45 个固定字节窗口、
10 条精确 direct xref 通过，只是本版本代码证据。下一步只读初始 Appearance loader
input key，模型实际显示与动画仍以游戏内结果为准。

### 初始 Appearance loader key：schema 7

`--render-input-paths` 保留原 PAC/PAB 输入，新增精确 Skinned `+0x168→holder[0]` 的
直接 held string。构造 `0x2D9702A` 初始化该字段；`0x46B278..0x46B290` 把初始
Appearance 资源 +30 复制进刚分配的 Skinned。loader `0x2439DB6..0x2439DD0` 保留
task+18 路径 holder，`0x243A340..0x243A347` 写入输出资源 +30；随后解析 Appearance。
新增六个指令边界窗口，共 46 个固定窗口验证，只有此 SHA 准入。

样本中的 `characterScene.renderInputPaths.initialAppearanceInput.path` 是初始加载
输入键；允许记录不透明键，不凭扩展名认定已载入文件。只允许对齐 holder，字符是
有界字节地址；最多读取 512 字节，含 NUL，仅可打印 ASCII。字段、holder[0]、每个
字符及 NUL 都加入完整 Scene 回读，再检查受控 owner 全链和两次样本一致。缺失或空
为 notReady，越界／类型／短读／漂移拒绝；末尾模块或 SHA 变化清除顶层成功标记。

顶层 `initialAppearanceInputObserved` 与 `renderInputPathsObserved` 分别表达稳定
初始 key 和全部三项输入齐备。PAC 为空但初始 key 稳定时，前者可为 true，后者为
false 且整体 notReady。默认及其他模式不读取 +168；默认 schema 4、links schema 5
不变。**103/103** 隔离检查通过，新字段随后已实测（见下文手动十二资源记录）。它不证明加载完成、
实际头身 PAC、装备或已执行外观替换，不提升任何 Steve／应用／descriptor 标记。

### HP 候选诊断的语义修正

原角色诊断把 current=base+norm 及 max(base,+30) 当成生命检查，固定 EXE 不支持
这两个推断。唯一命中的 stat commit `0xC7EFDE0` 在 `0xC7EFEEA..0xC7EFF16` 写入
norm=max(committed-base,0)，再写 stored current。因此受伤后 current<base、norm=0
可以成立，旧检查会错误拒绝正常受伤状态。字段 +30 在提交路径用于阈值／+52 latch，
尚未证明是 HUD 最大值；第三方补满生命的写入策略不能代替读取语义。

当前 `probe_characters.py` 只保留原始字段 `current_stored_raw/base_raw/norm_raw/
floor_raw/field_30_raw`、entry_id=0 和有界数值检查。完整读长必须为 0x38 字节；
短读或首 ID 非零返回空。`plausibility_scope=bounded_raw_fields_only`，身份、时间投影、
最大值、单位及 HUD 就绪标记均 false。13 项隔离检查包括受伤、零值、越界及短读；
这只是诊断修复，没有接入心形 HUD。

静态 getter `0x17AD810` 取 base +18；`0x17AD670→0x17B4040` 的 current 可依据元数据
模式及时间、速率字段投影，不能始终用 stored +08。`0x17AF510` 的通用比例为
(projectedCurrent-floor)/(base+norm-floor)；主生命类别消费者 `0x367400` 调用 base 和
current getter，并按 `0x5D736F4` 的 1000.0 换算后比较 current/base。它是具体原生
消费者，但尚未识别为 HUD 控件，也不证明任意首条 ID 0 记录就是当前角色生命。

后续须从已验证受控 Client 身份出发，固定 Status 组件 RTTI／回链、元数据索引和
单条 0x90 记录边界，重读完整链；然后确定实际 HP 模式、投影时钟及 UI 最大值策略，
与受伤、治疗、最大 HP 变化和切角色逐项对照。当前不导入扫描前 32 条记录等启发式，
不调用 native getter、不写状态。历史满血快照不能替代上述行为验收。

### 手动十二资源实测与 PAPPT 目录缺口

用户手动进入十二资源头描述文件对照后，明确反馈仍是原角色。schema 7 的两次完整
受控链稳定，独立 `initialAppearanceInputObserved=true`，实际输入键为
`character/appearance/1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000.app_xml`。
PAC 声明仍为空、PAB 仍为 `character/model/1_pc/1_phm/phm_01.pab`，因此整体 notReady、
`renderInputPathsObserved=false` 正确保留。运行时 Body/Head 选项仍是两私有 basename，
raw/preset FF 回退 default 0。该观测只确定初始 app 与选项，未读最终渲染 descriptor。

固定 EXE 的 `0x46CA30..0x46CA4D` 经 `0x3D0C50` 查询 World+A8 所指目录的 +70 名称表，
缺项直接跳过这条初始 Appearance 部件。初始化 `0x2C99670→0x1099BDF0→0x2C98880`
枚举 `character/bin__` 下 `.pappt`，按 header／part count／字符串记录建立 stem→folder
表 +70 和部件 metadata +50；第二段建立 +90 表。世界创建代码 `0xACFA96..0xACFA9E`
保存该目录至 World+A8，`0xACFBC6` 发布 World global；服务归属链后续补充如下，
目前仍没有新增 live 目录解码器或原生调用。

`0x2C9EDE0→0x109A8BA0` 用 +70 的 folder/stem 组成 `character/prefab/.../*.prefab`
逻辑路径；`0x2C9EFB0→0x109A8E20` 从 +90 构成同根 `.prefabdata_xml`，缺项返回失败。
第二段不是仅为“头模型”服务，原始身体和头部均在其中；不能只登记两个 part 行而
遗漏两条描述文件目录行。未发现这两个解析分支的自动旧 basename 回退。

真实原 `character/bin__/partprefabtable.pappt` 两段分别有 15566／2630 条记录，当前
身体和头部原 stem 各唯一出现，两私有 stem 在两段均缺失。此前测试包未包含此表；
添加 prefab／描述文件不等于向目录登记名称。磁盘研究 **37 个代码窗口、6 个字符串**
及固定原表完整解析／逐字重建通过。这支持优先十三资源注册表对照；customization
追加后是否正确覆盖原部件、实际显示／尺度／动画仍须实测。HKX 未有强制依赖证据，
不因原 PAC 邻接 HKX 就向候选添加未经验证的物理资源。

后续另核 **25 个窗口、3 个构造 vtable**：World+E0 为固定 VT `0x5D20718` 的父对象，
其 +2B8 与 World+F0 的服务对象相同；服务构造 `0x2D14A75` 设置 VT `0x5B41078`，
getter `0x723B90` 只返回 service+40068。该指针须与 World+A8 及 global `0x6C8CF10`
一致，catalog[0] 须回到 service+40018 的文件接口。`0x2D16192` 分配目录 0xF0 字节，
`0x2D162BF` 写 global，`0x2D162E0` 写 service 字段。World+F0 的赋值位于
`0xACFB15..0xACFB1D`，不能误用 +E8。目录非多态，不把首字段解释为 vtable；这些
匿名固定构造合同也不意味着取得标准 RTTI 类名。名称 hash 的 seed 为 0xC5EDE，
算法、桶边界与碰撞处理仍待独立核对，不套用零 seed 的档案路径 hash 直接读取表。

2026-10-08 收束为 `probe_part_catalog.py`：已核对 hashlittle seed 0xC5EDE，不包含
NUL、不转大小写或归一化路径。固定 EXE 的 Python 字节解释与 CDMW 在长度 0..128
的四种对齐共 516 项一致。实现只查询四个固定 stem 的 +70／+90 两张 inline map，
各桶最多 31 项，节点 +0 必须回指 bucketIndex*31+slot；同 hash 仍核完整名称，
含真实碰撞反例。原名对应的两个目录必须同时正确，才可将私有名字缺失提升为已观测。
header、整桶、匹配节点、holder、含 NUL 字符串和整个受控归属链完整回读及双采样；
clear epoch 并非每次插入的计数，不能代替字节稳定检查。84 个固定窗口和 21 项隔离
检查通过，末尾同句柄／EXE 失败会清掉顶层及嵌套成功标记。

2026-10-08 十三资源 v2 已首次完成目录实读：两表计数 15568／2632，两个私有名称
分别存在于两张 map，目录与固定 donor 相同；原名基线、完整依赖回读及双采样通过。
`runtime/steve-part-table-v2-20261008-catalog.json` 保留原始证据。初始 app 再次为
Macduff 00000；PAC 声明空、PAB 为 phm_01.pab，路径模式整体仍 notReady。
用户另提供实际图像：MC 块体可见但错位，与原服装／发型／装备混叠；此图像证据
不回填探针的模型／渲染／应用验证标记。该实例已正常退出，测试资源和最新存档
均完成恢复核对。此前十三资源 v1 的注册部件数与私有 prefab 不一致且进入闪退，
不能用 v1 的候选检查取代新版实机事实，详见进度。

### 受控 Hp 单条记录的静态合同补充

后续固定 EXE 研究已建立精确 ClientStatusActorComponent（vtable `0x558D868`）：
受控 child+68 组件表的 +20 为该组件，组件+8 回 child、+18 指 root、root[0] 回组件。
组件 +30 为 CharacterInfo key，0xFFFF 无效。StatusInfoManager（global `0x6D69AE8`）
的 +A0 来自原生按名称 `Hp` 初始化的 u16 key，不再猜 HP=0 或首条状态就是生命。
命名初始化 `0x25C6C00` 使用 `0x59B86C0` 的 Hp/Fatal/KnockOut 字符串表，失败为 FFFF。

三种精确 metadata manager 的已加载表为 +8 keyCount、+58 指针表；必须 key<count
且选中项非空，不能调用空槽后的 lazy loader。CharacterInfo +5B8 给出 group key；
StatusInfo[Hp] +14 给出索引，进入 StatusGroupInfo +58 的 int32 QII 映射（count +60、
capacity +64），再要求非负 mappedIndex<root+60 的条目数，只读取 root+58 中一条
0x90 记录并核其 u16 key=Hp。root+64 没有 capacity 证据。group regenerate-list 的
单项 Hp key 可以另行核对，但 rootCount=listCount 未被证明为生命周期不变量。
加上更新计数 `0xC7EFF02` 短窗口共 21 个静态窗口、4 种 RTTI 已核对。计数 +48 的
递增不提供原子快照保证，全部实际依赖仍须回读，随后完成第二次完整采样。

初版错误地将 StatusInfo+0 serialized `_key` 与 manager 的 u16 表索引等同，首次
实读在此拒绝。扩展 allocation 窗口 `0x584C70..0x584EA4` 明确：调用者 ordinal*8
选中 loaded slot，反序列化原对象写入该槽；record+8 `_stringKey` 的 holder[0]
字符串被复制、转小写并插入另一名称字典。这两种 key 没有相等合同。schema 2 保留
原 DWORD 为 rawMetadataKeyU32，另沿该字符串链最多读取 64 字节到 NUL，严格要求
原始串恰为 `Hp`，所有字符／终止符／holder／原 key 均加入回读；不猜低 16 位或模拟
名称归一化以放宽准入。21 项检查包含不同 serialized key、非零 ordinal、错名和漂移。

修正版实机两样本及 71 项依赖稳定：命名 Hp ordinal=0、serialized key=1000000、
stringKey=`Hp`，characterKey=0、groupKey=1、regenerateType=1、mappedIndex=0，
stored/base 均为 300000，norm/floor/field30 为 0，更新计数 0。这是精确身份和原始
记录观测，不能直接宣称 300 点当前／最大生命；投影、单位、分母和受伤／治疗行为
尚待验收。成功和首版失败报告都保留在 ignored runtime，心形 HUD 尚未接线。

后续静态核对了原生 Hp 数值消费者：StatGauge 主类别 0 取 current `0x17AD670`
和 base `0x17AD810`，分别按有符号整数朝零截断 /1000；基础数值上限来自 entry+18，
不能用 norm 或 +30。mode 1 helper `0x17B4040` 直接取 stored+8，但外层遇到
ClientStatus+273 非零会改取固定 global 的值，所以旧样本不足以证明 current。
独立 UI 选择器／受控身份／最终分段链另有静态证据；条宽还受配置和动画影响。
不继续扩展缓存镜像研究来阻碍当前人物显示主线。

`--current-gate` 小扩展加入上述两段固定代码窗口及 +273 单字节，默认 schema 2
读取保持，开启为 schema 3。全链／全依赖稳定后才生成候选标记；28 项检查通过。
新字节未在实机采样，候选不宣称行为、单位或心形 HUD 已验证。
