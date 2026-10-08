# Project instructions

This repository is the Crimson Desert × Minecraft prototype. The user's active
working copy is the desktop `CrimsonMC` directory, attached to
`https://github.com/dhcy-Asion/MC-`. Do project work in this repository rather than
the earlier copy under Desktop/Git.

## 开始工作与交接

新聊天先阅读本文件、[docs/current-state.md](docs/current-state.md)、[README.md](README.md)、[docs/architecture.md](docs/architecture.md)、
[docs/progress.md](docs/progress.md) 和 [CHANGELOG.md](CHANGELOG.md)，再查看实际 Git 状态和相关源码。
历史聊天、忽略目录中的研究脚本和进程地址不能作为唯一交接资料。

`docs/current-state.md` 是精简的当前交接入口，历史过程保留在 progress 中。子任务只
获得必要文件、明确问题及验收条件，修改文件责任互斥。主控独占实际游戏安装、
操作与恢复；最多三个子代理按独立工作启用，不为填满名额扩展研究范围。

`docs/architecture.md` 描述已经存在的模块和接口；`docs/progress.md` 记录当前里程碑、
验收条件、检查结果、关键决策及下一步。用户需求细节保存在 `docs/steve-character.md`。
代码事实与文档不一致时，先查清实际行为，修正文档，不能用文档证明功能已经实现。

## 按可验证的里程碑开发

1. 开始前确认 `docs/progress.md` 中当前里程碑的范围、前置条件和验收标准。
   用户当次指令可以调整优先级；及时记录这一调整。
2. 每次只处理当前里程碑相关的代码。后续功能只记录计划，不能顺手改背包、战斗、
   角色或全局输入。用户最新选择先让背包独立可用：当前 M6a 为物品目录、整组领取、
   36 格选择与实际消耗；此前新增取消原型合成、控制台直加、准确中文名称及图片悬停提示。
   2026-10-04 最新优先级为史蒂夫模型、方块和装备使用；用户已明确接受不走 F1、
   当时复用当前红沙角色移动／控制的“史蒂夫模式”，退出时恢复原外观。该动作范围已被
   2026-10-08 下方最新要求覆盖。当前推进 M4a
   可逆外观模式及其资产／原生接口前置验证，独立第四身份不再是本轮门槛。
   M6a 保留已有功能与未验收项；不安装未验收的记录器，不把资产导出记为游戏内模式完成。
   2026-10-06 用户覆盖此前范围：启用 mod 后持续使用史蒂夫（重载仍保持），允许使用
   红沙及 MC 两套装备，第三人称随装备变化；新增参考图风格底部 HUD、保留原 UI，
   所有方块与 MC 一致，并要求创意工坊分发。
   2026-10-08 用户再次覆盖装备和战斗范围：mod 启用时人物完整变成 Steve，禁止使用
   所有红沙装备，只能使用 MC 装备；点击控制栏物品目录加入 MC 背包；左键单击执行
   MC 单击攻击并造成实际伤害／击退，不再保留红沙战斗方式。用户进一步要求动作系统
   使用 MC 实际状态、时序与六个刚性关节的运动；不能继续套用红沙人物动画或只改动作名称。
   复用受控身份不豁免动作要求。MC 姿态来源、原生播放／控制、输入转换和真实攻击效果
   分别验收，离线姿态导出不等于游戏内动作已应用。最新验收见 docs/steve-character.md。
   当前可独立完成真实库存九格 HUD；角色、生命／饥饿、装备和工坊资格分别保留未完成。
   MC 四格人体护甲存储已接入 schema3 与桥接，只提供真实 ItemStack 转移／保存；
   nativeApplied／runtimeApplied=false，不等于人物穿戴、原装备禁用或攻击已经实现。
   默认服装空Armor对照已实测：用户反馈原服装消失，但左手缺失、背部装备仍重叠、
   头部过大；退出后已恢复，最新存档与完整MC保持。随后单独验证身体原字节
   PAMI合同，沿用空Armor和其余资源，没有同时猜测缩头、改皮肤或写装备存档。
   身体原PAMI独立10项、完整包隔离事务28项检查通过，已实际安装并取得用户反馈：
   左手出现、身体和四肢在观测姿势下无错位；用户确认头部没有五官，背部原装备仍在。
   同会话只读owner目录20项，6项primary RTTI可观测、14项未解析；render-input-paths
   双采样稳定但notReady，不能据此识别背部资源或宣称装备移除。身体包已正常退出恢复，
   收据069425…为restored，退出最新存档／完整MC／原点／ASI保持，不复用旧会话地址。
   下一项头部MC主颜色贴图使用独立候选：保留原生头材质合同，只改三个
   主draw路径；封装从固定身体14资源／8报告计划本地组合为严格9报告，另外13项
   保持，不读取实际游戏元数据。包已构建，完整隔离检查31/31通过；身体恢复后已实际
   安装，收据bbdda1…现为restored，当前无active／0041。用户实测头位置仍正常，但没有
   正确Steve五官，MC头皮肤未通过；同会话in-world文件核对通过，render-input双采样
   稳定但notReady，不能证明材质／DDS实际读取。正常退出后已核实进程结束并恢复，
   38项原文件、退出最新36存档／完整MC／原点／ASI保持，终态见current-state。
   下一头UV十报告包已完成32/32隔离重建／事务检查并实测，f4541c…现为restored；
   用户确认五官仍不正确、头位置正常。相对九报告只改144个主V字段，其他13项保持；
   双计划材质读取客户端46/46通过，首次引擎PAMI读取16134字节／flags50及摘要匹配，
   不证明renderer选择。五阶段exit0，38原文件、退出最新36存档／MC保持，无active／0041；
   后续检查渲染材质和通道，不重复相同UV对照。下一透明帽层候选12/12通过，严格11报告／
   14资源完整本地包已生成，e86048…；只换头PAC，内头／UV／材质和其余13项保持。
   三计划材质客户端69/69通过，完整事务检查及当前安装状态详见current-state。
   已有active、关闭游戏、原始元数据与索引门禁均不得绕过。
   人工服装和身体姿势反馈不能替代完整人物、头比例、MC皮肤、动态装备禁止或MC动作验收。
3. 完成后运行相关检查，在进度文件写明日期、命令、结果、证据及未验证项，再标记完成。
   只读探针运行成功不等于第四角色创建成功；构建成功不等于游戏内行为验证成功。
4. 未达到验收标准时保留在进行中，记录具体障碍和下一项可执行检查，不能为了收尾
   把后续阶段或尚未实现的功能标为完成。
5. 对接口、存档格式、原生调用、角色身份和需求范围作出的关键决策，及时写入架构或
   进度文件，并注明依据。最终答复说明本里程碑结果及剩余限制。

## 模块边界与源码规则

- Minecraft 是材料、配方、方块和掉落的权威。桥接和原生 UI 不重复实现 MC 配方，
  不自行改库存后假装 MC 已接受。
  当前原型按用户要求不提供合成；只移除原型合成入口，不删除原版 MC 配方资源。中文名称使用固定官方 zh_cn，保持每个物品 ID 独立，同名输入必须拒绝并要求 ID，不能逐词拼接或合并物品。
- 物品图片按 MC ID 映射，来源／版本／哈希固定，下载资源留在 ignored downloads。
  组件变体只作同类型预览，不伪造实际药水、附魔或染色组件。隐藏 World Builder 窗口不能停止它的后台排队／保存刷新。
- 原生调用必须在已验证的游戏线程机制中执行，网络请求不能阻塞渲染线程。
  原生排队返回的 UID／ticket 只表示受理，完成情况需要实际查询或验证。
- 项目维护的原生面板源码在 `red-side-patches/`；上游变化进入 `upstream.patch`。
  `vendor/` 是忽略的固定提交工作副本，不能只改 vendor 而遗漏可重建的补丁／准备步骤。
- API 或存档格式改动需要同步修改调用方、架构文档和迁移规则；保留已有实验材料和建筑。
  保存失败、超时及部分完成要显式处理，不能盲目重复消费材料的请求。
- 原生研究必须区分“静态候选”“只读观测”和“行为已验证”。先核对游戏版本及 SHA，
  再核对 RTTI、边界和回链；未知布局停止解释。找到函数签名不证明调用 ABI 或副作用。
- 若以后新增第四角色，必须保留原版三人身份，换装、生成 NPC 或绘制心形 HUD 均不能代替该验收。
  当前用户已授权复用原版控制身份的史蒂夫模式，需如实标明此范围，并验收外观／装备恢复；
  此模式不声称拥有独立第四原生身份或 MC 生存伤害规则。
  最新“永久”要求指 mod 启用期间自动持续应用并跨重载，原版外观及存档仍须有恢复路径；
  2026-10-08 当前必须禁止 Steve 使用所有红沙装备；不能只隐藏模型当作禁用完成。
  最新动作系统必须使用固定 MC 的实际状态、时序和刚性四肢运动；红沙骨架中立补偿、
  合成旋转或原生动画继续驱动均不能作为 MC 动作完成的证据。原生控制接口和动作切换、
  单击挥击、实际伤害／击退、禁用恢复分别记录，未知接口不调用、不写入。
  真实生命／饥饿接入前不绘制虚构满值状态条。
  2026-10-06 用户确认禁用／卸载后恢复，心形条显示红沙真实 HP、继续红沙战斗规则，
  独立 MC 生存生命未被重新要求。2026-10-08 攻击要求已改为 MC 单击攻击／击退，
  覆盖“继续红沙战斗规则”；HP 显示仍须真实来源。M5a 与 HUD 分别验收。
  不用虚构血量、库存或手持模型充当完成。新增依赖保留固定来源和许可证。

## 相关检查

只运行与当前改动有关的检查；文档和只读诊断阶段无需重启、安装游戏插件或改变 MC 材料。

| 改动 | 相关检查 |
| --- | --- |
| 文档／诊断 | 检查相对链接和 JSON；`python tools/check_character_probe.py`；Python 语法检查；已支持版本运行只读探针 |
| MC 规则 | `tools/build_minecraft.ps1` 构建；按变更运行 `tools/check_authority.py` 或新增有意义的规则检查 |
| 方块属性／存档迁移 | `py -3.12 -B tools/check_block_states.py` 使用独立世界；与 `check_inventory.py` 顺序运行（共用 8768／25580）；桥接转发运行 `check_inventory_bridge.py`；原生实际显示仍须另验收 |
| 背包 | MC 构建；`python tools/check_inventory.py` 使用独立测试世界；`python tools/check_inventory_bridge.py`；`python tools/check_inventory_ui.py`；原生构建和游戏内面板检查 |
| MC 护甲存储／schema3 | MC 构建；`py -3.12 -B tools/check_equipment.py`、`check_inventory.py`、`check_block_states.py`顺序使用独立8768/25580世界；`check_equipment_bridge.py`及旧桥接检查；原生穿戴／属性／装备禁用另验 |
| 原生装备表只读观测 | `py -3.12 -B tools/check_equipment_probe.py`；固定当前版本SHA、6个代码窗口、精确Client类型与owner回链、完整D0记录回读及双采样；实采仅主控，不能据此写回、禁止装备或声称恢复 |
| 受控owner组件身份目录 | `py -3.12 -B tools/check_owner_components.py`；独立只读完整16字节目录及count×8有序成员、primary RTTI、双采样／同句柄进程身份；匿名槽不猜布局，登记成员不证明背部资源／owner回链／装备禁用；实采仅主控 |
| 受控Skinned未命名对象身份 | `py -3.12 -B tools/check_owner_skinned_object.py`；精确受控Scene／Skinned、11固定代码窗口及owner回链，每样本最多新增97字节语义读取、统一依赖末回读／双采样／同handle身份；23/23离线通过，未实采，不解释pose／palette，不调用／写入 |
| 跨游戏方块同步 | `tools/check_bridge.py`；保存／重启改动再运行 `tools/check_restart.py` |
| 持久同步／原生条件 | `py -3.12 -B tools/check_native_identity.py`、`check_native_reconcile.py`、`check_inventory_bridge.py`；原生条件运行 `check_native_session.py`、`check_native_objects.py` 并回建 ASI，相关实机往返见上一项；隔离检查不修改用户世界 |
| 独立方块模型选择层 | `py -3.12 -B tools/check_native_block_models.py`；当前仅纯状态／证据范围匹配，未接默认桥接，不能替代实际安装、加载和显示验证 |
| 原生源码 | 准备固定上游、构建、补丁可重建检查及相关游戏内行为验证；更新插件前关闭游戏 |
| 九格 HUD | `python tools/check_hotbar_ui.py`；原生库存解码、桥接检查；原生构建／可重建源码及游戏内关闭／打开 F8、断线恢复验证 |
| Steve 离线资产 | `python tools/build_steve_asset.py`；`python tools/check_steve_asset.py`；产物留 ignored build，不安装为原生角色 |
| MC离线动作姿态基准 | `py -3.12 -B tools/check_steve_pose.py --rebuild`；固定官方client／21类／46外部依赖与Java工具，真实PlayerEntityModel求值站立／转头／行走，各40tick＋endpoint；明确ArmorStandEntity夹具，非Player、无World／tick，nativeApplied=false；未知动作和原生控制另验 |
| MC蹲伏／挥击模型输入样本 | `py -3.12 -B tools/check_steve_action_pose.py --rebuild`；固定29类／46依赖及旧基准，43个官方模型求值样本，9/9通过；model.sneaking与实体CROUCHING分开，固定右主手的OFF是左副手，指定progress不是tick周期；旧三组基准保持 |
| MC真实世界玩家上下文 | `py -3.12 -B tools/check_steve_player_context.py`只做preflight；显式`--run`使用独立8768/25580世界，与inventory／equipment／block-state检查串行；25项实测，正常构造未连接／未注册／未生成的ServerPlayer，官方状态setter与protected挥击步骤，无完整tick／客户端／原生应用；主控运行并核对生产MC不变 |
| 固定Steve头材质读取诊断 | `py -3.12 -B tools/check_steve_head_material_probe.py`、原生变化时`check_native_resources.py`；仅steve_head_pami固定别名／16KiB／flags50，分别固定九／十／十一报告计划SHA和variant、active收据、实际41文件、EXE实例与MC状态门禁；客户端69/69通过，读取匹配不证明renderer选择或MC皮肤；实采仅主控 |
| Steve头主UV方向单变量候选 | `py -3.12 -B tools/check_steve_head_uv_control.py --rebuild`；固定当前头PAC／PAMI／DDS／报告，只翻三LOD共144个主UV V half字段，逐字逆恢复，独立MC accessor／BC3区域核对；shader反V与实机皮肤另验 |
| Steve头UV十报告封装 | `py -3.12 -B tools/check_steve_head_uv_overlay.py --rebuild`；固定九报告本地计划，仅头PAC改变，其他13项编码／flags／orig_size保持；原始metadata／PATHC保持，PAMT及PAPGT按实际CRC重建，严格10报告完整准入；实际安装／恢复与皮肤结果见current-state |
| Steve固定透明帽层候选 | `py -3.12 -B tools/check_steve_head_visible_layer.py --rebuild`；固定UV PAC／PAMI／DDS／报告，每LOD只删36个hat索引及必要计数／位置更新，48records／base索引保持，216字节精确逆恢复；真实MC／BC3／CDMW与重建12/12通过，实机遮挡和五官另验 |
| Steve透明帽层十一报告封装 | `py -3.12 -B tools/check_steve_head_visible_layer_overlay.py --rebuild`；固定十报告本地包，仅换头PAC，其他13项编码保持，独立headVisibleLayerComposition；单次完整readSnapshot含manifest／六文件／候选及composition来源，冲突拒绝／最终回读，不跨调用缓存或写入JSON；安装恢复结果见current-state |
| Steve 分段蒙皮候选 | `py -3.12 -B tools/check_steve_segmented.py --rebuild`；真实 palette、四 LOD 表面／UV、原始 byte 权重、inverse bind 与合成弯曲；仍使用旧模板 PABC，不代表当前角色描述符、装备或实机动画验收 |
| Steve 头身分件／私有 prefab | `py -3.12 -B tools/check_steve_parts.py --rebuild` 和 `check_steve_parts_prefab.py --rebuild`；四 LOD 完整记录并集、逐模型材质依赖、原生部件名与严格 footer／路径往返；旧分件 rig 与当前 descriptor 未共同验收，不能直接安装为完整人物 |
| Steve 当前 neutral 补偿 | `py -3.12 -B tools/check_steve_current_rig.py --rebuild`；固定当前 PABC／descriptor、实际 byte 权重及量化后中立回放，UV／skin／拓扑保持；独立 combined 候选，不代表原生 shader／动画或私有分件已应用 |
| Steve 私有十资源组合 | `py -3.12 -B tools/check_steve_assembly.py --rebuild`；固定来源与十项纯准入、身体补偿及头原字节；Head PABC 缺骨 93，原生头身 merge/scale 未验，不能以离线假设代替显示 |
| Steve 两属性外观候选 | `py -3.12 -B tools/check_steve_appearance.py --rebuild`；固定原版 0009 提取、只改 Body/Head 默认 basename、逆替换逐字恢复；保留 Hair/Beard 与装备，Kliff 共享资源不是 actor-local |
| Steve 头描述文件对照 | `py -3.12 -B tools/check_steve_head_descriptor.py --rebuild`；只增加私有头同名的原字节 HeadPrefabData，七字段和外部引用保持；不能据此断定它是首测未切换的原因 |
| Steve 部件名称注册 | `py -3.12 -B tools/check_steve_part_table.py --rebuild`；固定 PAPPT 的两段各追加身体／头部两行，新 part 行的组件列表必须匹配私有 prefab，全部旧行保持；v1 沿用原版多组件列表的包已闪退并恢复，不得重装；目录存在不等于显示验收 |
| Steve 原生头网格对照 | `py -3.12 -B tools/check_steve_head_mesh_control.py --rebuild`，封装后 `check_steve_probe.py --native-head --rebuild`；仅替换已注册私有 CD_Head 的一个 PAC 引用，其余十二资源保持，与 app 对照互斥；用于区分私有网格资源链和装配，不是人物修复 |
| Steve 原生头共同父骨候选 | `py -3.12 -B tools/check_steve_native_head_root.py --rebuild`，封装后 `check_steve_probe.py --native-head-root --rebuild`；固定原生三 LOD 布局、仅 palette slot0→B_face_com122、完整 UV／权重／中立回放；仅覆盖私有头 PAC／材质，其他十一项保持，动画和实际位置须另验 |
| Steve 原生头原字节材质对照 | `py -3.12 -B tools/check_steve_head_native_material.py --rebuild`；封装后 `check_steve_probe.py --head-native-material --rebuild`；严格六报告，保持失败共同父骨 PAC 及其余十二资源，仅换固定原生头 PAMI 的三变体／两draw完整字节；暂用原生纹理验证位置，不等于最终MC皮肤或装配修复 |
| Steve 默认服装渲染对照 | `py -3.12 -B tools/check_steve_clothing_control.py --rebuild`；封装后 `check_steve_probe.py --clothing --rebuild`；严格七报告、14资源，在已通过头位置的13资源上仅增加固定00000 app的空Armor；保留Body/Head/Hair等外部XML及12行逆恢复，不等于全部动态装备禁止 |
| Steve 原生身体原字节材质对照 | `py -3.12 -B tools/check_steve_body_native_material.py --rebuild`；封装后 `check_steve_probe.py --body-native-material --rebuild`；严格八报告、14资源，须完整空Armor控制，只换身体PAMI为50017字节原件；其余13项（含当前补偿PAC）保持，暂用原生纹理，左手／身体／动画另验 |
| Steve 头部MC主颜色贴图候选 | `py -3.12 -B tools/check_steve_head_basecolor.py --rebuild`；离线只换原生头PAMI三处baseColor路径，保留其余原字节并逐字逆恢复；固定已有头PAC／DDS／原生头报告，不新增纹理，独立10项通过，实机MC皮肤另验 |
| Steve 头部MC主颜色贴图九报告封装 | `py -3.12 -B tools/prepare_steve_head_basecolor_overlay.py`；`py -3.12 -X utf8 -B tools/check_steve_head_basecolor_overlay.py --rebuild`；固定身体14项／8报告本地计划与六文件，仅改头PAMI为第9报告，其他13编码／flags／orig_size／资源行保持；固定CDMW源离线打包、不读实际游戏元数据；14项／9报告、31/31通过，身体恢复后实际安装，头位置人工通过、Steve五官未通过 |
| Steve 初始 app 引用 | `py -3.12 -B tools/check_steve_app.py --rebuild`；00000／00002 必须显式二选一，每报告仅改一份 app 的 Nude/Head Name；不得猜受控实例实际 app，不同时改两份 app |
| 原生方块／皮肤候选 | Python 3.12 运行相应 prepare/check_native_block 或 prepare/check_steve_material；真实模板往返、几何／UV、独立纹理解码；资源留 ignored build |
| Steve prefab 候选 | `py -3.12 -B tools/check_steve_prefab.py --rebuild`；真实模板单路径替换/逆向往返、其它对象与骨骼依赖保持；不是受控身体切换 |
| 全方块注册表 | `python -B tools/check_block_registry.py --rebuild`；固定 vanilla 数据生成器、合法状态乘积/ID/默认状态及客户端资源核对，不启动世界 |
| 全状态模型映射 | `py -3.12 -B tools/check_block_state_models.py --rebuild`；固定原版 Java 谓词／解析、全部合法状态及加权／多部件组合，不启动世界 |
| 全资源面几何 | `py -3.12 -B tools/check_block_model_geometry.py --rebuild`；原版 FaceBakery、独立旋转／UV 检查、Pillow 纹理及全状态选项连接，不启动世界、不将 alpha 像素当作 render layer |
| 独立资源包预演 | `py -3.12 -B tools/check_asset_overlay.py --verify-game`；原索引保留、完整 DDS、逐项解包、路径与报告输出保护；预演不写游戏 |
| 临时原木资源探针 | `py -3.12 -B tools/check_asset_probe.py`（隔离副本）；`python tools/check_native_block_probe.py`（隔离 HTTP）；实际安装／恢复先关闭游戏并核对备份／所有权，实机显示与碰撞另验收 |
| 临时 Steve 十一资源探针 | `py -3.12 -B tools/check_steve_probe.py --rebuild`（隔离副本）；独立 `install_steve_probe.py` 安装／恢复 kind=steve-mesh-parameters，原木 CLI 默认 oak-log 不变；共用锁与收据但拒绝交叉恢复，不覆盖后续存档；实机显示和恢复单独验收 |
| 临时 Steve 十二资源对照 | `py -3.12 -B tools/check_steve_probe.py --head-descriptor --rebuild`；单独输出，不替换默认十一资源；旧十一项逐字相同，仅增加固定头描述文件，沿用 Steve 专用收据／恢复事务 |
| 临时 Steve 注册／app 对照 | `py -3.12 -B tools/check_steve_probe.py --part-table --rebuild` 检查十三资源注册包；`--app-variant macduff-00000 --rebuild` 检查十四资源单 app 对照；app 必须带头描述文件和注册表，默认十一／十二资源范围保持；完整事务需原临时包先恢复 |
| 外观只读输入路径 | `py -3.12 -B tools/check_appearance_controller.py`；schema 7 的 `--render-input-paths` 与 RTTI／links 模式互斥，固定 46 个静态窗口及两次全链采样；声明 PAC/PAB 与初始 Appearance 输入，均不证明实际 descriptor 或 Steve 加载 |
| 受控 Hp 单条诊断 | `py -3.12 -B tools/check_health_probe.py`；固定 EXE、ClientStatus 与三种 metadata 类型、名称 Hp key／单条映射、完整依赖双采样与同句柄进程身份；实机 `probe_health.py` 只读，不投影当前值或声明 HUD 最大值 |
| 私有部件目录诊断 | `py -3.12 -B tools/check_part_catalog.py`；固定四名称、两目录、构造归属链、桶／节点／完整名称碰撞核对及双采样；原名基线成立才提升缺失结果，不把目录存在等同模型显示 |
| 原生资源读取客户端 | `py -3.12 -B tools/check_native_resource_probe.py`，使用隔离 HTTP/假进程身份及真实本地资源摘要；实际引擎读取单独记录，不等于模型显示 |
| 原生资源读取接口 | `python -B tools/check_native_resources.py`；真实 backend 的隔离 host、故障释放/尺寸/队列测试、旧读取函数与补丁回建；完整 ASI 构建后再实测 |
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
