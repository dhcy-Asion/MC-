# 当前交接状态

更新：2026-10-08，Asia/Shanghai。这里只保留当前决定和下一步；历史证据见
[progress.md](progress.md)，完整范围见 [steve-character.md](steve-character.md)。
开始／恢复工作时重新核对 Git、进程和实际安装收据，不能把本文当作现场事实的替代。

## 当前交付点

优先让 Steve 在现有存档中实际显示，并证明可恢复原资源。完整目标还包括持续外观、
动画／MC 装备及原装备禁用、MC 单击攻击／击退、全方块、真实状态 HUD 与分发；
当前交付点不缩减完整验收范围。2026-10-08 用户新要求覆盖“两套装备／红沙战斗”，
控制栏物品目录点击加入 MC 背包仍沿用已有领取接口；实机点击验收未完成。

并行已完成 MC 四格护甲存储、schema3迁移及桥接查询／存取，真实MC22组、旧背包15组、
方块7组、装备桥接8项及旧桥接27项通过。后台已正常更新，最新36格、选中格、方块及
revision25保持，护甲初始化为空；原生穿戴、效果、红沙装备禁用与MC攻击仍未实现。
摘要见[equipment-validation.json](equipment-validation.json)。当前头部测试包已实际恢复，
用户随后反馈MC方块头仍错位或未显示，本轮外观未通过；MC后台schema3继续运行，
无待恢复资源。

- 十一资源及十二资源头描述文件实测均仍是原角色。
- 已实读当前初始 app 为 Macduff 00000；运行时选项表有两私有名字，不代表加载成功。
- 原 PAPPT 两段缺私有名字。十三资源 v1 加注册表后，用户报告进入游戏闪退；恢复
  原资源后同一存档可正常进入。此包实机失败，不能继续安装旧十四资源包。
- 已确认静态缺陷：新增注册项沿用原版身体 2／头 7 个组件，而私有 prefab 各只有
  CD_Nude／CD_Head 一个组件；原版两者列表逐项相等。v2 已修正新行列表与跨资源检查。
- 修复只改 PAPPT 新行中的部件列表；模型、材质、骨架与 app 保持。静态缺陷成立，
  v2 本次实机正常进入且未重现闪退；没有异常堆栈证明唯一根因。
- 用户截图已出现 MC 方块头／蓝绿身体／紫色下肢，但位置错开并与红沙衣服、头发及
  装备混叠。**模型资源可见，完整外观装配失败**；不是原来的“资源没有显示”阶段。
  原衣服主要来自独立 Armor，头发来自 Hair，不足以证明旧 Nude／Head 重复。
  原生头单引用对照中用户确认头正常连接，优先修正自建头的网格／材质／绑定链。

## 现场和恢复

- 2026-10-08 已核实游戏关闭，并恢复十二资源收据
  `64cefed193bc4014914e78495471dc67`；38 项原始哈希匹配，0041 和 active receipt 消失。
- 恢复前后 36 个最新红沙存档、MC 持久状态 revision 22、原点与 ASI 保持。
- 当时 MC／桥接后台已停止，本次恢复比较的是持久文件，未伪造在线 API 状态。
- 十三资源 v1 收据 `90cdf0fca1ce4095aedc43d3515a1525` 已在进程退出后实际恢复。
  当时无临时包、0041 或 active receipt；38 项原始哈希匹配，36 个最新存档、
  完整 MC 状态、原点与 ASI 保持。用户手动启动新会话后确认可正常进入、不再闪退；
  新会话再次核对完整 MC 状态不变。
- 十三资源 v2 收据 `045d94ec45d74007a5dfd1c53dd8e00a` 已实测并在用户正常退出后
  恢复。该阶段无 active receipt／0041；38 项原始哈希、36 个最新
  存档、完整 MC 状态、原点与 ASI 均核对保持。
- 原生头单引用对照已实测，用户确认正常连接在肩膀上方；收据
  `57b18550c3e344c19278ecd6f0b9d2c6` 已在实际退出后恢复，38 项原始哈希、36 个
  最新存档、完整 MC、原点与 ASI 均保持。
- 新原生头模板／共同父骨候选 9/9、完整十三包28/28通过并已实际启动采样；
  收据 `5dfe1a43fa9846d6a1f1399bd42a4e2d` 已在核实实际进程结束后 restored，
  variant `steve-kliff-native-head-root-part-table-v2`。**当前无active receipt／0041**；
  38项原始文件、退出时36个最新存档、最新完整MC schema3/revision25、原点和ASI保持。
  用户恢复后补充反馈该MC头仍错位或未显示；本轮实机未通过，不能沿用上一原生头
  对照的“正常”结论。分组选项不能进一步区分具体错位位置与缺失，根因仍待验证。
- 游戏启动、进入和退出仍由用户手动完成；主控独占安装、游戏诊断与恢复操作。
- 本次恢复证据：`runtime/steve-part-table-v2-20261008-{before-restore,restored}.json`。
  闪退日志及恢复后用户对照记录：`runtime/steve-crash-20261008/`。日志在角色创建处
  中断，没有异常堆栈；指定时段 Windows 应用事件未找到匹配的崩溃记录。
- 持续目标未完成；2026-10-08 用户已更新目标，工具重新核实为 `active`。已观察到
  当前测试曾有新游戏会话，原生 ready=true 且角色位置可读；现在实际进程已结束并恢复，
  已收到退出前MC头未通过的反馈，不要求用户重启已恢复的包。
  此前三轮核实时没有运行中的游戏会话，历史 blocked 不再代表当前状态。

## 本轮交接

| 工作 | 负责人 | 状态／验收 |
| --- | --- | --- |
| 闪退恢复、封装交叉检查与 v2 事务 | 主控 | v1 已恢复，原版进入正常；v2 十三／十四包分别 24/24、25/25 通过 |
| 原生头候选 | crash_asset_audit | 完成 9/9；只改引用及必需长度／指针，原 donor 首组件逐字一致 |
| 显示错位分析 | steve_position_audit | 未定位明确 palette／坐标错误；建议原生头引用对照，不盲目补骨或平移 |
| 原生头封装接入 | diagnostic_review | 独立五报告集合、固定单路径覆盖及 app 互斥；主控完成 27/27 包检查 |
| v2 游戏内对照 | 主控＋用户手动进出游戏 | 正常进入，目录双采样通过；截图显示错位及混叠，已退出恢复；十四包未安装 |
| 原生头游戏内对照 | 主控＋用户手动进出游戏 | 用户确认连接正常；已退出恢复，文件／最新存档／MC 保持 |
| 原生头／自建头 PAC 结构差异 | steve_position_audit | 三 LOD 原字节自重建及 48 条原生记录控制通过；Head93 不在原生 palette，旧绑定不可直接移植 |
| 原生头共同父骨候选 | crash_asset_audit＋steve_position_audit | 生成器／独立检查器完成，最终9/9通过；明确 slot0→B_face_com122，其余191项和未知数据保持 |
| 新头候选封装与安装 | diagnostic_review＋主控 | 完整28/28通过；实机头仍错位或未显示，已退出恢复，最新存档／schema3保持 |
| 身体结构复核 | steve_position_audit＋主控 | 原current prefab已确认引用同一00_0001 donor；189项palette/PABC覆盖、四层边界与13加权骨核对通过，未找到新确证错位字段 |

目录成员与用户实际画面分别记录；探针不因为截图而回填 native rendered 成功标记。
HP 仍未接入 HUD，不在当前外观排障中扩展无关逆向支线。

新增原生装备只读探针22/22保护检查通过，实采精确Client组件、owner回指和14条D0
记录均双样本稳定；物品身份／嵌套指针未解码，应用、禁用及可恢复标志均false。
当前数据可证明观察链有效，不能当作完整原装备恢复备份。原始证据为
`runtime/steve-native-head-root-20261008-equipment.json`。

head_bind_space已完成离线复核：原版MC头/hat与当前目标空间约定核对保持，194/122
neutral只差毫米，没有明确静态坐标缺陷；不为弱假设再安装palette194同类包。
已实提取固定原生head PAMI：两draw名称相同，原件3变体分别使用EyeCover及
SkinWrinkle/Aging，失败包6变体均Standard。下一更强单变量仅换原字节PAMI、保持
失败PAC/另11资源，先验位置，暂用原生贴图；按原生完整3变体合同准入，不能强扩成6。
尚未封装或安装，shader／头身merge／缩放根因未确认，MC几何／皮肤路线保持。

装备共享apply最新静态检查已经否定把它当安全写前禁装入口：一个caller预先改表，
多个caller忽略结果，且存在清空队列路径；正常apply仅写0结果。下一步仅固定三个
真实表操作入口的首次写入与已有拒绝出口。该有界检查现已完成，插入重复tag、删除
缺tag确有局部写前拒绝；删除会修改关联索引、清理／搬移记录及计数，原字节不能
复制恢复。5完整body、48正常分支核对通过，安全调用／服务端持久化／全禁装仍未知。

伤害上下文定向复核已把62B870的已知caller闭合为ClientStatusActorComponent的
自身owner／status root链；并非两个不同攻击者／敌人，不能用于MC攻击或击退。
下一项只追另一条已有DamageApply caller的来源／目标生产链，确认是否两个不同owner；
不构造未验证伤害调用。完整固定窗口与报告见progress。

旧十三包未取得 in-world 探针结果，不能补填成功记录；before-restore／restored 已完成。
v2 使用独立 `build/steve-part-table-v2` 与 `build/steve-part-table-v2-probe-overlay`，
variant 为 `steve-kliff-part-table-v2`，不能复用 v1 快照脚本中的固定计划／收据绑定。
新版脚本 `build/record-steve-part-table-v2-20261008.py` 及同名 runtime 证据前缀，
已完成 before-install／installed／in-world／before-restore／restored。
`runtime/steve-part-table-v2-20261008-catalog.json` 实读两表私有头／身均 present，
目录正确、原名基线正确、完整依赖与双采样稳定；新名称注册加载已得到直接证据。
`...-appearance.json` 再次确认 Macduff 00000 初始 app，PAB 声明存在、PAC 声明空，
整体仍为 notReady；没有 Steve 渲染／应用成功标记。读取时 PID 82292，后续须重新
核对实例，不能复用地址；该实例已正常退出。用户画面保存于 ignored
`runtime/steve-crash-20261008/v2-user-visible-overlap.png`，供定位与混叠分析。
计划 SHA256 为
`19b5ae4841a63795324f642a8332fec23aca1783ed4af3804affd1237fdd54dc`。

**已恢复的原生头包**：`build/steve-native-head-probe-overlay`，计划 SHA256
`043c8b22e074da3d24e2c6c2e25f388f4ce57865b289de97f365be508b7503a5`。
快照脚本 `build/record-steve-native-head-20261008.py` 和同名 runtime 前缀；已完成
before-install／installed／in-world／before-restore／restored。新会话 PID 18364
（10:55:22 启动）已退出；此前实读受控链，
两次采样稳定；`runtime/steve-native-head-20261008-appearance.json` 为 notReady，
未把原来就为空的 PAC 声明提升为渲染资源身份。文件、完整 MC、原点与 ASI 保持。
用户确认原生头正常连接，原话和恢复证据记录于 ignored
`runtime/steve-crash-20261008/native-head-visual-result.json`。其余十二资源与 v2
完全相同，未启用 app 对照；可缩小到私有网格资源链，不能单独证明骨权重为根因。

原生头 PAC 为 3 LOD，实际几何节为 2／3／4；自建头来自 4 LOD 身体模板，节为
1／2／3／4。偏移 80 的 flags 分别为 `0x00000002` 与 `0x01000082`，差异 bit 的
含义未知，不直接翻位。自建头 `[447,63218)` 的 62,771 字节未知元数据仍与身体
donor 相同，现有检查只证明身体 donor 保持，不能证明独立头适配。
固定 CDMW parser 按 `4-section` 读取，但 builder 按 `n_lods-section` 重建，
直接传入原生头 donor 会保留原节 4 并写入节 1～3；下一候选必须显式处理布局，
不能把 donor 替换当成修复。证据在 ignored
`build/steve-head-pac-format-research-20261008/{structure-report,metadata-difference}.json`。

**已实测并恢复的 MC 头包**：`build/steve-native-head-root-probe-overlay`，计划SHA256
`2b3bd9241cf5711cc06f479e18bd0210629260471911945338d37af4973d4ff0`。
候选报告SHA256 `2d850067c97a7d44762eadb68154dbbb992aa2010f3851b63e3b0e8dfd6085a8`；
快照脚本 `build/record-steve-native-head-root-20261008.py`，同名runtime前缀。
before-install／installed／in-world／before-restore／restored均已有阶段记录；
in-world完整MC相等断言退出1，差异及恢复保护详见下段，不能合称全部通过。
新包只有头PAC及其PAMI两项变化，其余11项与v2保持；head prefab恢复使用私有MC路径，
与原生头引用对照互斥。用户反馈MC头仍错位或未显示，真实头外观未通过；
动画、身体与装备错位仍未完成。当前包已恢复，不再等待该包启动。

身体限时复核证据：ignored `build/steve-body-deformation-research-20261008/report.json`，
SHA256 `629841944e2da2121a8abe026eacdf8e356ea8a9aa2015996bf7b0cca56a52c7`。
原01_0002 prefab本就引用00_0001 PAC，不能因名字不同另换donor。身体候选13个实际
加权骨及全部189个palette项被当前420条PABC覆盖；四层各1008点／504面，边界闭合。
metadata flags不是运行时render_flags；`0x01000082`在固定guide解码器中layout为0，
不应简称“cloth启用”。每层96条byte38继承252／253／254，其是否参与jiggle还取决于
运行时buffer／override；旧参考针对1.0.0.2944，未在当前2976验证，不据此直接改字段。
暂未发现新的确证静态错误；当前MC头未通过，优先上述PAMI单变量，身体／装备另验。

该包in-world只读核实：当时收据5dfe1a43…／installed，41项文件均匹配，新会话已运行。
`runtime/steve-native-head-root-20261008-in-world.json` 已记录 API ready 与对象快照。
脚本的完整 MC 相等断言未通过：只有 revision 从22变25，库存、选中格及方块内容相同；
原点和 ASI 保持，不能写成完整MC状态未变。随后受控外观双采样稳定，初始 app 可读，
整体仍notReady（声明PAC为空），不代表Steve显示成功。后台升级schema3后，核实
实际进程结束再恢复，保留退出时最新MC／36个存档；当前无active receipt或0041。
用户随后补充头仍错位或未显示，不重复安装失败包或要求用户回退安装前状态。
记录脚本的restored以before-restore的
最新MC作比较（latestMcStatePreserved），仍分别记录与安装前的差异；原阶段证据不可覆写。

## 协作规则

最多一个主控和三个子代理，按实际独立工作启用。子任务只带问题、必要文件、所有权和
验收条件，不复制完整聊天；交付结论、证据位置、修改文件、检查结果及剩余问题。
文件修改责任互斥，所有游戏资源操作由主控串行执行。每 30～45 分钟审视当前支线是否
改变下一步行动；没有新证据时收束并选择下一实验。向用户报告实际能力与阻碍，
检查数量不能代替功能验收。完成验证后更新进度、记录并正常提交／推送 GitHub。
