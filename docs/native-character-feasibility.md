# 第四角色路线复核：目录扩展、原生列表与仍缺少的接口

2026-10-04（Asia/Shanghai）。本轮只读检查针对红沙 EXE `1.0.0.2976`，重新计算
SHA256 为 `57da440d72f4db974f25fef047cf84c4dadd999a88cb2a3c5af4c9bd67fde1e7`。
没有写游戏内存、调用游戏函数、安装 hook、修改游戏归档或创建人物。
原有切换封包及保存字段的静态合同见 [native-character-contract.md](native-character-contract.md)。

用户随后调整本轮范围：允许在 F1 之外切换，并明确接受沿用当前红沙人物的移动／控制，
进入史蒂夫模式时改变外观，退出后恢复原外观。因此下文第四身份的缺口属于原路线研究，
不再作为本轮模式切换的前置条件；模型、原生装备隐藏／恢复、MC 装备和方块使用仍须验收。

## 新确认的目录容器扩展路径

固定 CDMW 提交 `787680f97502522e90ec3dd1ea1889ca86452985` 的
[structured_binary_editor.py](https://github.com/Ratty123/CDMW-Full/blob/787680f97502522e90ec3dd1ea1889ca86452985/cdmw/core/structured_binary_editor.py#L315)
提供 `append_table_rows(payload, header, rows)`。它追加记录正文和目录中的 key／offset，
增加原格式宽度的记录数，再解析返回结果；拒绝已有 key、新记录间重复 key、短于 key
的记录和计数溢出。记录字段编码仍由调用方负责。

这与
[archive_entry_addition.py 的 PAMT 文件登记](https://github.com/Ratty123/CDMW-Full/blob/787680f97502522e90ec3dd1ea1889ca86452985/cdmw/core/archive_entry_addition.py#L84)
是两层不同的操作：后者增加模型等文件的归档索引，前者扩展一个表的记录目录。
两者都没有提供第四可玩身份、owned 状态或 F1 注册流程。不能把新增文件与新增角色等同。

本轮下载的该固定 Python 文件 SHA256 为
`1bceb3dc084d8522f94535a17291a321eea42cb1fa139083cab7807e15dec832`；只在内存中
构造测试表，五项检查通过：原记录保留且追加 key／offset 正确、拒绝已有 key、
拒绝新记录重复 key、拒绝短记录、拒绝一字节计数从 255 增为 256。
脚本副本和检查结果留在忽略上传的 `runtime/`。这证明工具的容器行为，
没有用实际 CharacterInfo／MercenaryInfo 正文验收，也没有验证游戏加载扩展表。

## 原生 UI 的新增静态定位

在当前 EXE 中重新核对 `UIGamePlayControlCommonMercenaryList`：vtable RVA
`0x56AF660`，完整对象定位器 `0x5E197E0`，类型描述符 `0x6AE8FE0`；
定位器 signature=1、base offset=0、self RVA 和精确 RTTI 名称均匹配。
vtable slot 175 指向 `0xEDCFA0`，`.pdata` 边界为 `[0xEDCFA0, 0xEDD2D8)`。

该函数的静态行为：

- 检查输入索引小于 `this + 0x188` 的 u32 数量，然后从 `this + 0x180`
  的数组按八字节读取一项。该路径使用运行时数量，不是直接以常量 3 检查索引。
- `this + 0x178` 等于 `0x16` 时，进入组件 `+0x110` 的 lookup `0x2146170`；
  返回记录的 u16 `+0x20` 进入 CharacterInfo getter `0x389570`。
- 随后的原生业务仍根据状态值和 UI 上下文分支；此函数没有新身份分配、
  CharacterInfo 行追加或 MercenarySaveData 创建调用。

这些是**静态候选**。尚未观察到实际 F1 UI 调用该类，`0x16` 的名单用途、数组项身份、
名单填充和请求发送路径也未完成验证。不能据此宣称 F1 已支持第四项，
也不能反向宣称整个游戏存在固定三人限制。函数中的 `mov r15d, 3` 用于栈上清理标记，
不能当作角色数量证据。原始反汇编和 vtable 记录只留忽略目录。

另一个 `UIGamePlayControlRootCharacterList` 可定位到 `SelectCharacter` 字符串，
但本轮也没有证据将它与存档内 F1 切换关联；不得仅根据类名选择 hook。

## 当前目录观测与创建／保存边界

本轮配套只读目录探针观察到 CharacterInfo 7250 行、MercenaryInfo 21 行；
原版三人的 CharacterInfo 行号／key 为 `0/1`、`3/4`、`5/6`。
MercenaryInfo 的 playable 标记也出现在坐骑、龙和战争机器类别上，
不能用它直接生成 F1 主角名单。原生目录观测不等于拥有这些角色。

当前角色组件 `+0x110` 的精确 RTTI 是 `ServerMercenaryClanActorComponent`。
首次探针因旧类型猜测不符而停止；随后独立静态回链确认切换业务 `0x294DA9B`
确实经该组件调用 `0x214E7A0 → 0xE4B8080`，后者使用已记录的有界容器布局。
RTTI 继承为 `ServerMercenaryClanActorComponent → CommonMercenaryClanActorComponent →
IActorComponent → Noncopyable`，没有假定的 `ServerMercenaryActorComponent` 基类。
改用精确类型、核对 owner 回链后，重新只读采样得到稳定的 15 条 owned 记录，
包含 Damian 行 3／key 4、Oongka 行 5／key 6，以及坐骑、observer、NPC／动物。
这不是 15 个 F1 主角，也没有证明第四身份创建或实际控制切换。
完整 CharacterInfo／MercenaryInfo 的记录字段编码尚未验证；即使容器可扩展，
也仍缺少新增 key 的引用一致性及当前版本加载证据。

现有 `FrameEventRegistMercenaryReq` 的生产业务会验证事件上下文、已有 owned 状态、
去重和内部事务；其入口不是可任意提交新角色 key 的通用注册 API。
MercenarySaveData 的静态字段和 dirty 容器尚未建立安全插入、同步和保存回读合同。
不能直接追加指针或复制原版三人存档来绕过这些步骤。

当前 [Character Creator 的角色枚举](https://github.com/Khione95/Crimson-Desert-Character-Creator/blob/b845222f771df8fb70fc720e191c609655480fb7/CharacterCreator/CharacterCreator/characters.h)
经在线复核仍只有 Kliff、Damiane、Oongka；其外观编辑不能补足第四身份接口。
当日 `main` 经 `git ls-remote` 核对仍为该固定提交；未引入其代码或作为依赖。

## 用户接受的史蒂夫模式：可复用的外观路线

Character Creator 固定提交的
[addresses.cpp](https://github.com/Khione95/Crimson-Desert-Character-Creator/blob/b845222f771df8fb70fc720e191c609655480fb7/CharacterCreator/CharacterCreator/addresses.cpp#L17)
记录 PE timestamp `0x6AB28F00`、image size `0x173AB000`；本轮读取本机 EXE 得到的
这两个值完全匹配。上游定位包含 `CharacterCustomizationController` vtable
`0x559DD98`、SetDecoration `0x72BF80`、QueueMeshChange `0x72CFB0`、
Rebuild `0x726C50`、ParseAppearance `0x2438A40`。匹配版本并不等于调用已经验收。

上游
[game.h / game.cpp](https://github.com/Khione95/Crimson-Desert-Character-Creator/blob/b845222f771df8fb70fc720e191c609655480fb7/CharacterCreator/CharacterCreator/game.cpp)
描述外观控制器的 16 个 mesh 选择值、250 个 decoration 值及已加载选项的边界。
其 `GameSetMesh` 只选择现有 meshparam 选项；`ApplyDesired` 在控制器更新线程排队
`{slot, old, new}`、写选择值并重建外观。上游通过私有 meshparam 的隐藏选项数区分
原版三人，不能直接移植这项识别假设。换装时机、加载／预览副本和恢复原值都需本项目验证。

当前磁盘中 QueueMeshChange `0x72CFB0` 是到 `0x92F94A0` 的保护跳转，
没有该入口的 `.pdata` 边界。随后同一 SHA 门禁下读取运行中的目标代码，
观察到 `[0x92F94A0, 0x92F95C9)` 的正常函数路径，末尾为 `ret` 和 INT3：
RCX 指向 `{data, u32 count, u32 capacity}`，RDX 指向三个字节；
追加到 `data + count * 3` 时复制 u16 加 u8，并增加 count。
扩容和原内容复制同样使用三字节元素。这只读佐证了上游排队三字节记录的参数语义，
没有调用该函数，也没有验证排队后模型刷新。原始代码证据只留 `runtime/`。

原生控制器与实际受控身体的回链、Steve 选项加载、红沙装备部件的隐藏／恢复
和 MC 手持／护甲绑定尚未验证。这里提供定位线索，尚无可直接启用的模式切换 API。

CDMW 的
[Imported armour and skinning](https://github.com/Ratty123/CDMW-Full/blob/787680f97502522e90ec3dd1ea1889ca86452985/cdmw/ui/new_item/README.md)
路线要求已解析的目标 PAB／bone palette，可对未绑定模型从匹配的模板／身体转移权重，
但没有提供外部骨名或动画重定向。Steve 的方块身体需要先生成原生可加载的 PAC、材质、
prefab 和 meshparam 绑定；OBJ／glTF 预览、通用蒙皮或文件导出都不能代替游戏内模型验收。
MC 装备同样需要目标骨骼／socket、材质和动态装备部件的绑定证据。
Character Creator 未发现项目自身许可证，本轮仅阅读定位事实，不复制实现。

## 下一项可执行检查

本轮模式路线先核对当前身体与外观控制器的回链、原生更新线程、有效选项和重建 ABI；
然后在离线副本上完成 Steve PAC／材质／prefab／meshparam，再逐项验证进入、退出、
恢复外观、隐藏／恢复红沙装备和 MC 装备绑定。没有通过这些检查前不安装猜测的换装调用。

保留的第四身份研究后续步骤：

1. 持续核对精确 RTTI、owner 回链和稳定边界，将目录行号、CharacterInfo key、
   Mercenary No、Actor handle 分别记录。
2. 在原版 F1 切换和回切时关联 UI、请求及实际受控身体；同一时间记录名单填充，
   验证上述 UI 候选是否参与。请求观测需要独立审核并验证的被动记录器，不能主动发包。
3. 按当前版本的真实读取函数核对两张表完整字段／引用编码，再对只读导出的副本
   验证容器往返；不写生产归档。随后定位原生 owned 创建、保存、同步和控制迁移。
4. 新身份创建和保存合同完整后才集成 Steve 模型、装备绑定与方块输入；
   原版三人回切、重载、死亡、骑乘和任务强制切换需分别验收。

本轮史蒂夫模式及其装备功能尚未通过游戏内验收；目录／静态检查成功不能代替它们。

## 2026-10-06 源码复核与诊断工具保护

本次先复核实际源码，再执行离线保护检查，没有打开游戏进程、调用游戏函数、写游戏
内存、改存档或安装插件。`python tools/check_character_probe.py` 的 6 项检查通过；
`python tools/check_character_roster.py` 的 22 项检查通过，包含本次补充的三个案例。

`probe_character_roster.py` 保留固定 EXE 版本与 SHA、精确 RTTI、完整有界目录、owner
回链和前后复读门槛；目录行号、CharacterInfo key、Mercenary No 和 Actor handle 分开
输出，控制权／F1 名单／新增身份的验证标志保持 false。本次修复两项实际保护缺口：
输出路径及其祖先出现 symlink／junction 时提前拒绝，`runtime` 被链接到公共目录不能
成为新的输出信任根；owned 记录的 CharacterInfo 索引既不在实际目录内又不是原生
`0xFFFF` 无效值时拒绝整组解释。合法 `0xFFFF` 只记录 unknown，不推定人物身份。
外部读数不是原子快照；通过这些检查仍不证明独立第四角色或外观切换已经实现。

现有原生桥接支持玩家坐标、渲染相机、游戏线程排队、已有 prefab 生成及物理探针。
[`bridge/service.py`](../bridge/service.py) 的 `PREFAB` 与 `Bridge.sync` 把六种基线方块
全部映射到同一个一米蓝色实体；没有已实现的 MC blockstate → mesh／材质映射。
[`upstream.patch`](../red-side-patches/upstream.patch) 也未增加角色外观写接口。固定
World Builder 的 HTTP API 说明其文件覆盖用于 level／prefab／表，不能据此推定它
已经支持新增纹理和 mesh。真实 MC 方块外观仍需要已验证的原生资源加载与模型格式。

已有 Steve 工具读取固定官方客户端的真实经典模型，导出本机 glTF；六个 MC 刚性
关节在本轮进一步绑定到真实红沙 palette，生成了离线 PAC 候选；候选使用部分辅助/扭转骨，
尚无材质／prefab／meshparam、动画验收、装备 socket 或游戏加载证据。
其配置中的原生集成标志全部 false，可作为资产准备工具，不能当作
已经切换史蒂夫或支持穿戴装备的验收成果。

真实模板与候选的来源、LOD/权重检查及复建命令见 [asset-pipeline.md](asset-pipeline.md)。

历史外观扫描只提供控制器候选：记录的 mesh／decoration 数量均为零，owner 类型
为 `SceneObjectClient`，没有已验证的当前身体回链。宽范围指针扫描也没有证明中间
对象的真实边界，不能把扫描偏移直接加入外观写入适配器。下一项仍是同一 SHA 下
验证实际受控身体、外观对象边界与 owner 回链，再验证加载选项和更新线程；通过后
才可验证可恢复的模型替换。此段是对既有研究记录的审核，未声称今天重新取得了
运行时控制器或任何外观行为证据。
