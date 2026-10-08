# 当前交接状态

更新：2026-10-08，Asia/Shanghai。历史证据见 [progress.md](progress.md)，完整验收见
[steve-character.md](steve-character.md)。开始／恢复时核对实际 Git、游戏进程与收据，
不能复用已结束会话的 PID 或地址。

## 当前目标与能力

持续目标 **active**。mod启用期间完整且跨重载显示Steve，**动作系统也用MC**；禁止
全部红沙装备，仅MC装备；目录点击加入真实MC背包；MC单击攻击及实际敌人伤害／击退。
全方块、原UI、真实状态HUD、禁用／卸载恢复及分发保持。旧身体反馈等待条件已解除，
受阻审计重新从零开始，完整目标仍未完成。

真实MC Java1.21.1管理36格Mod背包、六类方块与四格护甲存储。官方classic Steve几何／UV
及固定皮肤已导出，正在适配红沙骨骼／材质。九格HUD常驻／刷新／断线恢复已实测，
目录领取接口已有，实机按钮待验收；正式建造仍用蓝色碰撞代理，真实HP尚未接HUD。
完整MC schema3／revision25、选择格1、材料／建筑保持；四格护甲为空，人物装备应用未实现。

## 已成立的外观结果及边界

- 十一／十二资源仍显示原角色。十三资源注册v1进入闪退，恢复后原存档正常；新PAPPT行
  组件列表不匹配私有prefab，v2已改成各一项。旧v1勿重装。
- v2块体首次出现但错位、原部件混叠。原生头引用位置正常；MC共同父骨头曾错位／缺失。
  恢复完整原字节头PAMI后，用户确认方块头连接肩膀上方。仅缩小到完整材质合同差异，
  不能认定单一shader字段根因。
- 清空固定Macduff00000 app默认Armor，用户确认原服装消失，当次左手缺失、背装备重叠、
  头过大；收据 `2feb0ddf41b3488fba9eb226cf8fb672` 已恢复。
- 随后仅换完整原生身体PAMI，用户确认**左手出现、身体和四肢没有错位**；另确认
  “没有无关”指**头没有五官**，背部原装备仍在。只覆盖观测姿势；头比例、全MC皮肤、
  动作、重载与原装备禁用未通过。

## 身体对照已实测并恢复

- plan：`build/steve-body-native-material-probe-overlay`，14资源／严格8报告。
- SHA：`fa1f38ec686644fdebeddd53ad09429aab87083495da12155b5b6f3248b8e341`。
- receipt：`069425c3a6a0430fa9c576e3afe8f20b`，kind=steve-mesh-parameters，**restored**。
- recorder：`build/record-steve-body-native-material-20261008.py`；同名runtime前缀。
  五阶段各exit0，41安装文件、38恢复原文件、退出时36个最新存档、完整MC／原点／ASI保持。
  身体PAMI为50017字节原件，6变体×3draw；PAC／骨骼／scale／shrink及其余13资源保持。
- 人工结果和澄清在 `...-visual-result.json`，绑定收据、计划及三个采样摘要。受控owner的
  20成员双采样稳定，仅6槽标准primary RTTI，14槽未解析，控制器恰一次；目录存在不证明
  背部资源和owner回链，匿名槽不能猜类型。
- `probe_appearance_controller.py --render-input-paths` 双采样稳定但 **notReady／exit1**，
  Scene／选择／初始app可读，PAC/PAB声明不完整；没有descriptor／资源身份准入。
  未写内存、刷新、移除装备或修改装备存档。身体会话已结束。

## 最新头部主颜色贴图对照：皮肤未通过，已恢复

身体包恢复、实际游戏关闭并核对基线后，已串行安装下一项：

- plan：`build/steve-head-basecolor-probe-overlay`，14资源／严格9报告，PAZ770800字节。
- SHA：`29b813224b362f8d2e751a8ae31968846a55d96410f290ffd10deb00322078e5`。
- variant：`steve-kliff-original-head-body-material-empty-armor-head-basecolor-part-table-v2`。
- receipt：`bbdda1c5304f4cfe884a1e8ca1fdeed6`，kind=steve-mesh-parameters，**restored**。
- recorder：`build/record-steve-head-basecolor-20261008.py`；同名runtime前缀。
  五阶段各exit0，41安装文件／38恢复原文件、退出时36最新存档、完整MC／原点／ASI保持。
  用户反馈“头部没出现正确的史蒂夫五官、头的位置仍正常”；人工头位置通过，MC脸部
  未通过，本轮render-input双采样稳定而notReady。实际进程结束后已恢复，**无active
receipt／0041、无待恢复包**。用户手动启动、进入、退出，自动接管停止。
- 相对身体对照只换头PAMI三个主baseColor路径（16149→16134字节）；shader、EyeCover、
  SkinWrinkle／Aging参数、其他纹理和头PAC保持，固定已有DDS不新增。身体原PAMI及其余
  13项完整保持。人工结果与限制在 `runtime/steve-head-basecolor-20261008-visual-result.json`。
  文件匹配不证明renderer实际选择该PAMI或DDS；该次会话ASI尚无Steve头读取别名，未取得引擎读回。
- 候选10/10、完整本地封装／隔离事务31/31通过；固定源计划及六文件本地组合，不读取
  实际游戏元数据。标准安装仍核对active、游戏关闭、原始元数据与34个源索引。

## 上次实测：头UV未解决五官，已恢复

- 新包：`build/steve-head-uv-probe-overlay`，14资源／严格10报告；计划SHA
  `b27484b952059015920635a23cf489a2881d23ba86e554b0b80f7157a03e7c10`。
- 收据：`f4541cd031434b238e22b637efe64de2`，kind=steve-mesh-parameters，**restored**。
  该次已核实游戏退出并恢复，恢复时无active receipt／0041。用户手动启动／退出偏好继续适用；
  新对照包当前状态见下一节。
- 相对上一头baseColor包只翻三LOD共144个主UV V字段，头PAC从182fc…变为c0df7…；
  头PAMI／DDS及另外13项完整行和编码保持，几何位置、骨骼权重不变。UV候选不是已验证修复。
- 完整隔离事务／真实本地重建32/32通过，552.366秒；九个旧canonical计划纯准入通过。
  双计划头材质客户端46/46通过，82.870秒，含跨计划收据／variant拒绝。无需更换ASI。
- recorder：`build/record-steve-head-uv-20261008.py`，同名runtime前缀。
  五阶段均exit0；41项安装文件／38恢复原文件、退出时最新36存档、完整MC schema3/revision25、
  选择格1、原点／ASI保持。用户反馈“五官仍不正确，头的位置正常”，UV单变量未解决五官。
- 新会话in-world核对通过；固定`steve_head_pami`引擎读取首次实采成功：16134字节、flags50、
  storedSize1694，FNV `3a4d0e960a22bdf3`／head16与候选一致，ticket1、一次提交和一次读取，
  handler已释放；前后同实例、完整MC与41文件保持。报告为同名前缀`-material-read.json`，
  人工结果为`-visual-result.json`。成功只证明文件可解析，renderer选材质／DDS采样仍未证。
  用户正常退出后已核实进程结束，恢复时保持退出最新存档，旧会话PID／地址不得复用。

## 当前现场：透明帽层完整对照包

固定十报告UV包已本地组合为严格11报告／14资源，新计划为
`build/steve-head-visible-layer-probe-overlay`，manifest17784字节，PAZ770576字节，SHA
`e86048837217e7cd85ac957d12db2b05b3315449234e8639668ebf627665add1`；variant为
`steve-kliff-original-head-body-material-empty-armor-head-basecolor-head-uv-visible-layer-part-table-v2`。
仅头PAC由c0df7…替换为7c222d…；另外13项完整资源行、编码、flags及orig_size保持，
PAMI／DDS与内头顶点／UV／骨骼保持。独立`headVisibleLayerComposition`固定基线来源；
原metadata-before及PATHC不变，PAMT／PAPGT按实际归档CRC重建。

三计划材质客户端`check_steve_head_material_probe.py`已69/69通过（134.101秒），每版
分别绑定完整SHA／variant／收据，跨计划拒绝；固定别名及16KiB范围保持，无需更新ASI。
标准`load_plan`返回单次完整`readSnapshot`供新封装复用，不跨调用缓存，不序列化到
收据或manifest；来源冲突与最终回读保持。完整安装／恢复隔离及真实重建检查34/34通过
（808.297秒），class cleanup与生产前后快照通过，子代理已停止所有生产读取。
旧2～10报告共11个分支纯准入通过，CLI相对／绝对路径归一化2项针对检查通过，四份
最终源码摘要在`build/steve-head-visible-layer-overlay-check-20261008/report.json`。
主控随后实际安装，收据`fc6a856085ab493985d6ebf3d40a66f3`，kind=steve-mesh-parameters，
**installed／active，0041存在，临时包尚待实测后恢复**。标准安装命令exit0；
`record-steve-head-visible-layer-20261008.py`的before-install／installed两阶段均exit0，
安装前38原件匹配，安装后41文件匹配，最新36存档、完整MC schema3/revision25／选择格1、
原点和ASI保持，安装时游戏关闭。已请求用户手动启动、进入同一存档反馈五官／位置，
并保持运行；当前没有该包的人工视觉结果或新live样本，遮挡假设未验证。
收到反馈后先新鲜核对PID／创建时间／包／MC，执行in-world recorder、绑定新计划的
`probe_steve_head_material.py`以及已有23项检查的`probe_owner_skinned_object.py`只读诊断。
随后请求正常退出，核实进程结束，before-restore→标准restore→restored，保持退出最新
存档及MC。主控独占实际会话，不复用旧PID，不为只读诊断另开一次启动。

## 独立工作与剩余前置

MC动作由客户端算法生成。固定官方client／Yarn的PlayerEntityModel、BipedEntityModel与
PlayerEntityRenderer三个类摘要已匹配，含setAngles／animateModel／animateArms。
现有SteveModelDump仅导静态几何，glTF没有animations；红沙多骨蒙皮／合成弯曲不是MC刚体
动作。官方算法离线站立／转头／行走基准现已完成，9/9隔离重建检查通过；真实模型方法
各调用123次，三组各40tick＋endpoint、六部件TRS与原始字段完整保存。夹具为正常构造的
ArmorStandEntity，非Player，无World／tick；8个状态getter逐帧前后核对。固定client、21类、
46外部JAR；产物 `build/steve-pose-1.21.1`，独立JVM逐字一致，原六份工具／产物保持。
新增 `build/steve-action-pose-1.21.1`：官方模型蹲伏输入1帧、固定右主手MAIN／OFF各21个
progress样本，共43帧，29类及46依赖固定；独立重建9/9通过（15.454秒）。实体仍是
null-World ArmorStand／STANDING；model.sneaking不冒充真实CROUCHING，OFF为左副手，
指定progress不代表tick周期。六部件原始字段／TRS保留官方左右不对称结果。

真实世界前置也已实测：`tools/check_steve_player_context.py --run`在独立ServerWorld正常
构造ServerPlayer子类，仅暴露官方protected tickHandSwing；25项通过，正常退出，生产源码／
build保持。官方setter可切左右主手、sneaking和CROUCHING并恢复，8次挥击步骤进度回零。
玩家没有连接、注册或生成到世界，没有调用完整entity/player tick、客户端模型或伤害。
首次隔离实验与提升为tracked工具后的路径验证各通过一次，证据分别为
`runtime/mc-player-context-pjydwbq2`和`runtime/mc-player-context-1hec_dws`。
后续`tools/check_steve_player_tick.py --run`已执行完整官方world.tickEntity→player.playerTick，
每个不同server tick一次。正常构造ServerPlayNetworkHandler／ClientConnection，无传输
连接或玩家注册；独立世界九块石地板，11次真实物理暖机后采四组32帧（站／蹲×MAIN／OFF）。
两入口各43次，实际年龄12..43，前帧位置／挥击复制、Pose切换和每段挥击回零成立，网络
任务队列实测4项；保留正常重力末速度，不写age／velocity／onGround或私有字段。
首次证据`runtime/mc-player-tick-4tm1bcz6`，tracked路径验证`runtime/mc-player-tick-uxn5vmag`，
均正常退出0且源码／build保持。每帧保存真实delta0/.5/1 getter输入，供六关节模型回放。
未注册／生成玩家，不调用handler.tick；仍不代表完整连接生命周期、客户端renderer或
原生实时应用。随后固定首次成功capture已接通六基础关节官方模型回放：32个after帧
×delta0/.5/1，共96次真实求值，保留actual progress／Pose与自然age；8/8独立JVM重建
通过（16.853秒），79项来源／输出快照和旧12工具／产物保持。产物
`build/steve-player-pose-1.21.1`，report SHA
`77dc04a8dd90b23765485298e4430ec2513d6c94c1212fb252314e555ffdb9c7`。
来源Player与模型ArmorStand夹具分开，仅限空手RIGHT、站／蹲、MAIN／OFF、静止六关节；
`--source`只接受固定首次capture，并非任意新采样。renderer／原生／战斗仍false，
持物／跳落及完整游戏动作继续另验。
原生API没有经过当前EXE验证、绑定受控owner的姿态／控制器应用入口。固定EXE有界审计
已排除旧coop两个落在指令内部的RVA；下一候选为精确Skinned+1C0的未命名owner-keyed对象，
仅vtable／弱owner／原owner回链有静态依据，骨骼palette、单位、ABI与线程未知。
最小只读身份诊断`probe_owner_skinned_object.py`已完成，主控复跑23/23离线检查通过；
11固定代码窗口，每样本最多97字节新增语义读取，统一依赖回读、双采样及同handle身份，
错误／变化清除成功标志。尚未实采，不为该诊断单独要求用户启动游戏；下次有必要会话再执行。
MC动作实时应用与完整系统未实现。
`+0x110`直接callee后续审计已辨明回调wrapper及弱句柄指针vector，常量8是容量，不能当骨骼数；
该分支未提供TRS／矩阵数组生产证据，不扩展现有只读工具的读取范围。
原生资源路线中，固定CDMW的PAA仅为启发式旋转预览，无完整writer／no-op往返／可靠时序
或人物播放派发。另一视觉路线可考虑六刚体对象：现有MoveMany支持三轴Rot（YXZ）及
统一scale，但缺完整owner朝向／父绑定、无碰撞部件、六件完成回执及临时层生命周期；
默认live重插可能闪烁。它能减少未知骨骼ABI，尚未证明人物跟随。报告
`build/steve-rigid-render-contract-20261008/report.json`固定11份源码；先验证pivot／单位／
四元数映射，再有必要实测一件无碰撞载体。不能把散置props或旧Euler直接复制当MC动作。

背部具体组件→prefab/PAC链未定位。14条raw装备记录只为观察；共享apply和表增删局部拒绝
不等于安全全禁装／恢复。攻击者／敌人类型、owner链和伤害／击退ABI尚缺，不调用候选函数，
不以移动NPC代替击退。固定EXE有界追踪唯一直接调用0x209a4bb→0x209bdc0，调用者
0x209a220仍转发上游A/B参数；未闭合两者具体类型、构造及owner回链，结果unavailable。
该路径已停止，不从参数外形猜测敌我身份或扩大原生调用。
头UV方向候选已离线完成，11/11重建检查通过；只翻三LOD共144个
V half字段，逐字逆恢复，其余PAC／PAMI／DDS保持。旧脸域若直接按DDS行序采样为透明，
翻V后落在有眼鼻嘴的非透明区域，但shader是否再反V仍未证明。产物
`build/steve-head-uv-control`，PAC SHA `c0df7b6e6fbe90038b8e277839ef59b26aa4cbba560f30770d82eec9acf50b55`，
report SHA `56790fa5efb6a2b38ed5938f217d4ddc25b11d5b87c18a6640721fd15ae3a3af`。
该单变量已接入严格10报告／14资源可逆封装，实测并恢复；翻V未解决五官。离线审计确认
同一main draw含内头与外帽，帽UV六区共6144texel全RGBA0，内头六区alpha255；原生材质
是否discard透明alpha未知。仅去掉透明帽面索引的离线候选已完成，保留内头／全部
顶点／UV／材质，用于检验遮挡假设，避免重复相同UV对照。孤立PAC仍不能
单独安装。正确五官、头比例、背部原装备及完整人物尚未验收。

下一候选：`build/steve-head-visible-layer/steve-head-visible-layer-report.json`，报告SHA
`6d68aa3eff9428fe9f7c63838fdbed10097a4c17ef0da940648b24ea972e6501`；PAC96505字节／flags1，
SHA `7c222d1cb2d475d7e487c8cad87967afc63d27a1fa14b99d35c62a24f762d9ca`。
`check_steve_head_visible_layer.py --rebuild` 12/12通过（10.781秒），独立MC／BC3／三LOD
CDMW解析、保守bbox、完整字段／索引逆恢复、纯准入和来源／报告篡改拒绝覆盖。没有安装。
对应严格11报告／14资源整包已生成；当前安装检查进度、计划及现场见上方“当前现场”。
完整五官、渲染器材质选择与透明遮挡仍须实际验证，单PAC的离线通过不提升这些状态。

主控独占游戏安装、采样、恢复、后台和Git；最多三个子代理按独立范围执行。完成相关检查、
文档和普通GitHub推送后交付。游戏资源／存档／runtime／build保持忽略。

新固定头PAMI读取诊断已实现：仅一个steve_head_pami别名，16KiB／flags50、分别固定九／十／十一报告计划／
active收据／实际41文件／同EXE实例／完整MC门禁。三计划客户端69/69、原生23/23及旧客户端27/27
检查通过；固定上游重放45份源码经CRLF规范化一致，ASI构建并已更新实际安装及发布artifact，
SHA `9d5cdc8eebbad47010f4d6e15e3afe74d630ace00332cd7032ac216c3494efe7`。原ASI备份保留，
38原文件、最新存档／MC／原点保持。新诊断已在十报告UV会话实采成功，只证明路径可读取，renderer
材质选择／DDS采样保持未验证；不为诊断开放任意路径或增加DDS／PAC读取上限。
